"""
Walk-Forward Analysis Engine - Rolling WFA (Phase 2)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from copy import deepcopy
import hashlib
import io
import json
import logging
import time

import pandas as pd

from . import metrics
from .backtest_engine import prepare_dataset_with_warmup
from .optuna_engine import OptunaConfig, OptimizationConfig, run_optuna_optimization
from .storage import save_wfa_study_to_db

logger = logging.getLogger(__name__)


@dataclass
class WFConfig:
    """Walk-Forward Analysis Configuration"""

    # Window sizing (calendar-based)
    is_period_days: int = 180
    oos_period_days: int = 60

    # Strategy and warmup
    strategy_id: str = ""
    warmup_bars: int = 1000


@dataclass
class WindowSplit:
    """One IS/OOS window with timestamps"""

    window_id: int
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp


@dataclass
class WindowResult:
    """Results from one WFA window"""

    window_id: int

    # Window boundaries
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp

    # Best parameter set
    best_params: Dict[str, Any]
    param_id: str

    # Performance metrics
    is_net_profit_pct: float
    is_max_drawdown_pct: float
    is_total_trades: int

    oos_net_profit_pct: float
    oos_max_drawdown_pct: float
    oos_total_trades: int

    # OOS equity curve for stitching
    oos_equity_curve: List[float]
    oos_timestamps: List[pd.Timestamp]

    # Optional IS details
    is_best_trial_number: Optional[int] = None
    is_equity_curve: Optional[List[float]] = None


@dataclass
class OOSStitchedResult:
    """Stitched out-of-sample equity curve and summary"""

    final_net_profit_pct: float
    max_drawdown_pct: float
    total_trades: int
    wfe: float
    oos_win_rate: float

    equity_curve: List[float]
    timestamps: List[pd.Timestamp]
    window_ids: List[int]


@dataclass
class WFResult:
    """Complete Walk-Forward Analysis results"""

    config: WFConfig
    windows: List[WindowResult]
    stitched_oos: OOSStitchedResult

    strategy_id: str
    total_windows: int
    trading_start_date: pd.Timestamp
    trading_end_date: pd.Timestamp
    warmup_bars: int


class WalkForwardEngine:
    """Main engine for Walk-Forward Analysis"""

    def __init__(
        self,
        config: WFConfig,
        base_config_template: Dict[str, Any],
        optuna_settings: Dict[str, Any],
        csv_file_path: Optional[str] = None,
    ):
        self.config = config
        self.base_config_template = deepcopy(base_config_template)
        self.optuna_settings = deepcopy(optuna_settings)
        self.csv_file_path = csv_file_path

        from strategies import get_strategy

        try:
            self.strategy_class = get_strategy(config.strategy_id)
        except ValueError as e:  # noqa: BLE001
            raise ValueError(f"Failed to load strategy '{config.strategy_id}': {e}")

    def split_data(
        self,
        df: pd.DataFrame,
        trading_start: pd.Timestamp,
        trading_end: pd.Timestamp,
    ) -> List[WindowSplit]:
        """
        Create rolling walk-forward windows using calendar-based periods.

        All window boundaries are aligned to 00:00 day start to match TradingView behavior.
        """
        if self.config.is_period_days <= 0 or self.config.oos_period_days <= 0:
            raise ValueError("IS and OOS periods must be positive")

        if df.empty:
            raise ValueError("Input dataframe is empty.")

        trading_start_normalized = trading_start.normalize()
        trading_end_normalized = trading_end.normalize() + pd.Timedelta(days=1)

        start_idx = df.index.searchsorted(trading_start_normalized, side="left")
        if start_idx >= len(df):
            raise ValueError(
                f"Normalized trading start {trading_start_normalized.date()} "
                f"is beyond available data range"
            )

        trading_start_aligned = df.index[start_idx]
        if trading_start_aligned.time() != pd.Timestamp("00:00:00").time():
            print(
                "Warning: First trading bar is at "
                f"{trading_start_aligned.time()}, not 00:00. "
                "Window alignment may not match TradingView exactly."
            )

        trading_days = (trading_end_normalized - trading_start_aligned).days
        min_required_days = self.config.is_period_days + self.config.oos_period_days
        if trading_days < min_required_days:
            raise ValueError(
                "Insufficient data for WFA. Need at least "
                f"{min_required_days} days (IS={self.config.is_period_days}d + "
                f"OOS={self.config.oos_period_days}d), but trading period is only "
                f"{trading_days} days."
            )

        max_possible_windows = (trading_days - self.config.is_period_days) // self.config.oos_period_days
        if max_possible_windows < 2:
            raise ValueError(
                f"Configuration produces only {max_possible_windows} window(s). "
                "WFA requires at least 2 windows for meaningful results. "
                "Reduce IS/OOS period lengths or provide more data."
            )

        print("Creating walk-forward windows:")
        print(f"  IS Period: {self.config.is_period_days} days")
        print(f"  OOS Period: {self.config.oos_period_days} days")
        print(f"  Trading Start (aligned to 00:00): {trading_start_aligned}")
        print(f"  Trading End (normalized): {trading_end_normalized.date()}")
        print(f"  Trading Days: {trading_days}")
        print(f"  Maximum Windows: {max_possible_windows}")

        windows: List[WindowSplit] = []
        window_id = 1
        current_start = trading_start_aligned

        while True:
            is_start_target = current_start
            is_end_target = is_start_target + pd.Timedelta(days=self.config.is_period_days)
            oos_start_target = is_end_target
            oos_end_target = oos_start_target + pd.Timedelta(days=self.config.oos_period_days)

            if oos_end_target > trading_end_normalized:
                print(
                    "  Stopping: Window "
                    f"{window_id} OOS end ({oos_end_target.date()}) "
                    f"exceeds trading end ({trading_end.date()})"
                )
                break

            is_start_idx = df.index.searchsorted(is_start_target, side="left")
            is_end_idx = df.index.searchsorted(is_end_target, side="left")
            oos_start_idx = df.index.searchsorted(oos_start_target, side="left")
            oos_end_idx = df.index.searchsorted(oos_end_target, side="left")

            if is_end_idx > 0 and is_end_idx <= len(df):
                is_end_idx -= 1
            if oos_end_idx > 0 and oos_end_idx <= len(df):
                oos_end_idx -= 1

            if (
                is_start_idx >= len(df)
                or is_end_idx >= len(df)
                or oos_start_idx >= len(df)
                or oos_end_idx >= len(df)
            ):
                print(f"  Stopping: Window {window_id} indices exceed dataframe bounds")
                break

            is_bar_count = is_end_idx - is_start_idx + 1
            oos_bar_count = oos_end_idx - oos_start_idx + 1
            min_bars = 100

            if is_bar_count < min_bars:
                print(
                    f"  Warning: Window {window_id} IS has only {is_bar_count} bars "
                    f"(recommended minimum: {min_bars})"
                )
            if oos_bar_count < min_bars:
                print(
                    f"  Warning: Window {window_id} OOS has only {oos_bar_count} bars "
                    f"(recommended minimum: {min_bars})"
                )

            is_start_aligned = df.index[is_start_idx]
            is_end_aligned = df.index[is_end_idx]
            oos_start_aligned = df.index[oos_start_idx]
            oos_end_aligned = df.index[oos_end_idx]

            windows.append(
                WindowSplit(
                    window_id=window_id,
                    is_start=is_start_aligned,
                    is_end=is_end_aligned,
                    oos_start=oos_start_aligned,
                    oos_end=oos_end_aligned,
                )
            )

            print(f"  Window {window_id}:")
            print(f"    IS:  {is_start_aligned} to {is_end_aligned} ({is_bar_count} bars)")
            print(f"    OOS: {oos_start_aligned} to {oos_end_aligned} ({oos_bar_count} bars)")

            # Shift forward by OOS period length (rolling window)
            next_start_target = current_start + pd.Timedelta(days=self.config.oos_period_days)
            next_start_normalized = next_start_target.normalize()
            next_start_idx = df.index.searchsorted(next_start_normalized, side="left")

            if next_start_idx >= len(df):
                print("  Stopping: Next window start would exceed dataframe bounds")
                break

            current_start = df.index[next_start_idx]
            window_id += 1

        if not windows:
            raise ValueError("Failed to create any walk-forward windows with current configuration")

        print(f"Created {len(windows)} windows successfully")
        return windows

    def run_wf_optimization(self, df: pd.DataFrame) -> tuple[WFResult, Optional[str]]:
        """
        Run complete Walk-Forward Analysis.

        Steps:
        1. Split data into rolling windows
        2. Optimize IS per window, test OOS per window
        3. Stitch OOS equity and compute summary metrics
        4. Return results
        """
        print("Starting Walk-Forward Analysis...")
        start_time = time.time()

        fixed_params = self.base_config_template.get("fixed_params", {})
        use_date_filter = fixed_params.get("dateFilter", False)
        start_date = fixed_params.get("start")
        end_date = fixed_params.get("end")

        if use_date_filter and start_date is not None and end_date is not None:
            trading_start = pd.Timestamp(start_date) if not isinstance(start_date, pd.Timestamp) else start_date
            trading_end = pd.Timestamp(end_date) if not isinstance(end_date, pd.Timestamp) else end_date
        else:
            trading_start = df.index[0]
            trading_end = df.index[-1]

        if trading_start.tzinfo is None:
            trading_start = trading_start.tz_localize("UTC")
        if trading_end.tzinfo is None:
            trading_end = trading_end.tz_localize("UTC")

        windows = self.split_data(df, trading_start, trading_end)

        window_results: List[WindowResult] = []

        for window in windows:
            print(f"\n--- Window {window.window_id}/{len(windows)} ---")

            print(
                "IS optimization: dates "
                f"{window.is_start.date()} to {window.is_end.date()}"
            )

            optimization_results = self._run_optuna_on_window(
                df, window.is_start, window.is_end
            )

            if not optimization_results:
                raise ValueError(f"No optimization results for window {window.window_id}.")

            best_result = optimization_results[0]
            best_params = self._result_to_params(best_result)
            param_id = self._create_param_id(best_params)
            best_trial_number = getattr(best_result, "optuna_trial_number", None)

            print(f"Best param ID: {param_id}")

            is_df_prepared, is_trade_start_idx = prepare_dataset_with_warmup(
                df, window.is_start, window.is_end, self.config.warmup_bars
            )

            is_params = best_params.copy()
            is_params["dateFilter"] = True
            is_params["start"] = window.is_start
            is_params["end"] = window.is_end

            is_result = self.strategy_class.run(
                is_df_prepared, is_params, is_trade_start_idx
            )

            is_metrics = metrics.calculate_basic(is_result, initial_balance=100.0)

            print(
                "OOS validation: dates "
                f"{window.oos_start.date()} to {window.oos_end.date()}"
            )

            oos_df_prepared, oos_trade_start_idx = prepare_dataset_with_warmup(
                df, window.oos_start, window.oos_end, self.config.warmup_bars
            )

            oos_params = best_params.copy()
            oos_params["dateFilter"] = True
            oos_params["start"] = window.oos_start
            oos_params["end"] = window.oos_end

            oos_result = self.strategy_class.run(
                oos_df_prepared, oos_params, oos_trade_start_idx
            )

            oos_metrics = metrics.calculate_basic(oos_result, initial_balance=100.0)

            if oos_metrics.total_trades == 0:
                print(
                    "Warning: Window "
                    f"{window.window_id} produced no OOS trades. "
                    "This may indicate overfitting or unsuitable parameters."
                )

            window_results.append(
                WindowResult(
                    window_id=window.window_id,
                    is_start=window.is_start,
                    is_end=window.is_end,
                    oos_start=window.oos_start,
                    oos_end=window.oos_end,
                    best_params=best_params,
                    param_id=param_id,
                    is_net_profit_pct=is_metrics.net_profit_pct,
                    is_max_drawdown_pct=is_metrics.max_drawdown_pct,
                    is_total_trades=is_metrics.total_trades,
                    is_best_trial_number=best_trial_number,
                    is_equity_curve=list(is_result.balance_curve or []),
                    oos_net_profit_pct=oos_metrics.net_profit_pct,
                    oos_max_drawdown_pct=oos_metrics.max_drawdown_pct,
                    oos_total_trades=oos_metrics.total_trades,
                    # Use realized balance curve so stitched net profit matches per-window net profit.
                    oos_equity_curve=list(oos_result.balance_curve or []),
                    oos_timestamps=list(oos_result.timestamps or []),
                )
            )

        stitched_oos = self._build_stitched_oos_equity(window_results)

        wf_result = WFResult(
            config=self.config,
            windows=window_results,
            stitched_oos=stitched_oos,
            strategy_id=self.config.strategy_id,
            total_windows=len(window_results),
            trading_start_date=trading_start,
            trading_end_date=trading_end,
            warmup_bars=self.config.warmup_bars,
        )

        study_id = None
        if self.csv_file_path:
            study_id = save_wfa_study_to_db(
                wf_result=wf_result,
                config=self.base_config_template,
                csv_file_path=self.csv_file_path,
                start_time=start_time,
                score_config=self.base_config_template.get("score_config")
                if isinstance(self.base_config_template, dict)
                else None,
            )

        return wf_result, study_id

    def _build_stitched_oos_equity(self, windows: List[WindowResult]) -> OOSStitchedResult:
        """Build stitched OOS equity curve from stored per-window equity curves."""
        stitched_equity: List[float] = []
        stitched_timestamps: List[pd.Timestamp] = []
        stitched_window_ids: List[int] = []

        current_balance = 100.0
        total_trades = 0

        for i, window_result in enumerate(windows):
            window_equity = list(window_result.oos_equity_curve or [])
            window_timestamps = list(window_result.oos_timestamps or [])

            if window_result.oos_total_trades == 0 or len(window_equity) == 0:
                total_trades += 0
                continue

            start_equity = window_equity[0] if window_equity else 0.0
            if start_equity == 0:
                start_equity = 100.0

            start_idx = 0 if i == 0 else 1

            for j in range(start_idx, len(window_equity)):
                pct_change = (window_equity[j] / start_equity) - 1.0
                new_balance = current_balance * (1.0 + pct_change)
                stitched_equity.append(new_balance)
                if j < len(window_timestamps):
                    stitched_timestamps.append(window_timestamps[j])
                else:
                    stitched_timestamps.append(window_result.oos_start)
                stitched_window_ids.append(window_result.window_id)

            if stitched_equity:
                current_balance = stitched_equity[-1]

            total_trades += window_result.oos_total_trades

        if len(stitched_equity) == 0:
            final_net_profit_pct = 0.0
            max_drawdown_pct = 0.0
        else:
            final_net_profit_pct = (stitched_equity[-1] / 100.0 - 1.0) * 100.0

            peak = stitched_equity[0]
            max_dd = 0.0
            for equity_value in stitched_equity:
                if equity_value > peak:
                    peak = equity_value
                if peak > 0:
                    dd = (peak - equity_value) / peak * 100.0
                    if dd > max_dd:
                        max_dd = dd
            max_drawdown_pct = max_dd

        if windows:
            avg_is_profit = sum(w.is_net_profit_pct for w in windows) / len(windows)
            avg_oos_profit = sum(w.oos_net_profit_pct for w in windows) / len(windows)

            days_per_year = 365.0
            is_annual_factor = days_per_year / self.config.is_period_days
            oos_annual_factor = days_per_year / self.config.oos_period_days

            annualized_is = avg_is_profit * is_annual_factor
            annualized_oos = avg_oos_profit * oos_annual_factor

            if annualized_is != 0:
                wfe = (annualized_oos / annualized_is) * 100.0
            else:
                wfe = 0.0 if annualized_oos <= 0 else 100.0
        else:
            wfe = 0.0

        if windows:
            profitable_oos = sum(1 for w in windows if w.oos_net_profit_pct > 0)
            oos_win_rate = (profitable_oos / len(windows)) * 100.0
        else:
            oos_win_rate = 0.0

        return OOSStitchedResult(
            final_net_profit_pct=final_net_profit_pct,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            wfe=wfe,
            oos_win_rate=oos_win_rate,
            equity_curve=stitched_equity,
            timestamps=stitched_timestamps,
            window_ids=stitched_window_ids,
        )

    def _run_optuna_on_window(self, df: pd.DataFrame, start_time: pd.Timestamp, end_time: pd.Timestamp):
        """Run Optuna optimization for a single WFA window."""
        csv_buffer = self._dataframe_to_csv_buffer(df)

        fixed_params = deepcopy(self.base_config_template.get("fixed_params", {}))
        fixed_params["dateFilter"] = True
        fixed_params["start"] = start_time.isoformat()
        fixed_params["end"] = end_time.isoformat()

        base_config = OptimizationConfig(
            csv_file=csv_buffer,
            strategy_id=self.config.strategy_id,
            enabled_params=deepcopy(self.base_config_template["enabled_params"]),
            param_ranges=deepcopy(self.base_config_template["param_ranges"]),
            param_types=deepcopy(self.base_config_template.get("param_types", {})),
            fixed_params=fixed_params,
            worker_processes=int(self.base_config_template["worker_processes"]),
            warmup_bars=self.config.warmup_bars,
            risk_per_trade_pct=float(self.base_config_template["risk_per_trade_pct"]),
            contract_size=float(self.base_config_template["contract_size"]),
            commission_rate=float(self.base_config_template["commission_rate"]),
            filter_min_profit=bool(self.base_config_template["filter_min_profit"]),
            min_profit_threshold=float(self.base_config_template["min_profit_threshold"]),
            score_config=deepcopy(self.base_config_template.get("score_config", {})),
            optimization_mode="wfa",
        )

        optuna_cfg = OptunaConfig(
            target=self.optuna_settings["target"],
            budget_mode=self.optuna_settings["budget_mode"],
            n_trials=self.optuna_settings["n_trials"],
            time_limit=self.optuna_settings["time_limit"],
            convergence_patience=self.optuna_settings["convergence_patience"],
            enable_pruning=self.optuna_settings["enable_pruning"],
            sampler=self.optuna_settings["sampler"],
            pruner=self.optuna_settings["pruner"],
            warmup_trials=self.optuna_settings["warmup_trials"],
            save_study=self.optuna_settings["save_study"],
            study_name=None,
        )

        results, _study_id = run_optuna_optimization(base_config, optuna_cfg)
        return results

    def _dataframe_to_csv_buffer(self, df_window: pd.DataFrame) -> io.StringIO:
        buffer = io.StringIO()
        working_df = df_window.copy()
        working_df["time"] = working_df.index.view("int64") // 10**9
        ordered_cols = ["time", "Open", "High", "Low", "Close", "Volume"]
        working_df = working_df[ordered_cols]
        working_df.to_csv(buffer, index=False)
        buffer.seek(0)
        return buffer

    def _result_to_params(self, result) -> Dict[str, Any]:
        params = dict(getattr(result, "params", {}) or {})

        params.setdefault("dateFilter", False)
        params.setdefault("start", None)
        params.setdefault("end", None)
        params.setdefault("riskPerTrade", float(self.base_config_template["risk_per_trade_pct"]))
        params.setdefault("contractSize", float(self.base_config_template["contract_size"]))
        params.setdefault("commissionRate", float(self.base_config_template["commission_rate"]))

        return params

    def _create_param_id(self, params: Dict[str, Any]) -> str:
        """Create unique ID for param set using first 2 optimizable parameters."""
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]

        try:
            from strategies import get_strategy_config

            config = get_strategy_config(self.config.strategy_id)
            parameters = config.get("parameters", {}) if isinstance(config, dict) else {}

            optimizable: List[str] = []
            for param_name, param_spec in parameters.items():
                if not isinstance(param_spec, dict):
                    continue
                optimize_cfg = param_spec.get("optimize", {})
                if isinstance(optimize_cfg, dict) and optimize_cfg.get("enabled", False):
                    optimizable.append(param_name)
                if len(optimizable) == 2:
                    break

            label_parts = [str(params.get(param_name, "?")) for param_name in optimizable]
            if label_parts:
                label = " ".join(label_parts)
                return f"{label}_{param_hash}"
        except (ImportError, ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning(
                "Falling back to hash-only param_id for strategy '%s': %s",
                self.config.strategy_id,
                exc,
            )

        return param_hash
