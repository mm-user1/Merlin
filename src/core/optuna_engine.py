"""Optuna-based Bayesian optimization engine for S_01 TrailingMA."""
from __future__ import annotations

import bisect
import logging
import multiprocessing as mp
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import optuna
from optuna.pruners import MedianPruner, PercentilePruner, PatientPruner
from optuna.samplers import RandomSampler, TPESampler
from optuna.trial import TrialState
import pandas as pd

from . import metrics
from .backtest_engine import load_data

logger = logging.getLogger(__name__)


# ============================================================================
# Data structures
# ============================================================================


@dataclass
class OptimizationConfig:
    """Configuration received from the optimizer form (Optuna-only)."""

    csv_file: Any
    worker_processes: int
    contract_size: float
    commission_rate: float
    risk_per_trade_pct: float
    atr_period: int
    enabled_params: Dict[str, bool]
    param_ranges: Dict[str, Tuple[float, float, float]]
    ma_types_trend: List[str]
    ma_types_trail_long: List[str]
    ma_types_trail_short: List[str]
    lock_trail_types: bool
    fixed_params: Dict[str, Any]
    param_types: Optional[Dict[str, str]] = None
    score_config: Optional[Dict[str, Any]] = None

    strategy_id: str = ""
    warmup_bars: int = 1000
    filter_min_profit: bool = False
    min_profit_threshold: float = 0.0
    optimization_mode: str = "optuna"


@dataclass
class OptimizationResult:
    """Represents a single optimization result row."""

    ma_type: str
    ma_length: int
    close_count_long: int
    close_count_short: int
    stop_long_atr: float
    stop_long_rr: float
    stop_long_lp: int
    stop_short_atr: float
    stop_short_rr: float
    stop_short_lp: int
    stop_long_max_pct: float
    stop_short_max_pct: float
    stop_long_max_days: int
    stop_short_max_days: int
    trail_rr_long: float
    trail_rr_short: float
    trail_ma_long_type: str
    trail_ma_long_length: int
    trail_ma_long_offset: float
    trail_ma_short_type: str
    trail_ma_short_length: int
    trail_ma_short_offset: float
    net_profit_pct: float
    max_drawdown_pct: float
    total_trades: int
    romad: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    ulcer_index: Optional[float] = None
    recovery_factor: Optional[float] = None
    consistency_score: Optional[float] = None
    score: float = 0.0


# ============================================================================
# Constants
# ============================================================================

SCORE_METRIC_ATTRS: Dict[str, str] = {
    "romad": "romad",
    "sharpe": "sharpe_ratio",
    "pf": "profit_factor",
    "ulcer": "ulcer_index",
    "recovery": "recovery_factor",
    "consistency": "consistency_score",
}

DEFAULT_SCORE_CONFIG: Dict[str, Any] = {
    "weights": {},
    "enabled_metrics": {},
    "invert_metrics": {},
    "normalization_method": "percentile",
    "filter_enabled": False,
    "min_score_threshold": 0.0,
}


PARAMETER_MAP: Dict[str, Tuple[str, bool]] = {
    "maLength": ("ma_length", True),
    "closeCountLong": ("close_count_long", True),
    "closeCountShort": ("close_count_short", True),
    "stopLongX": ("stop_long_atr", False),
    "stopLongRR": ("stop_long_rr", False),
    "stopLongLP": ("stop_long_lp", True),
    "stopShortX": ("stop_short_atr", False),
    "stopShortRR": ("stop_short_rr", False),
    "stopShortLP": ("stop_short_lp", True),
    "stopLongMaxPct": ("stop_long_max_pct", False),
    "stopShortMaxPct": ("stop_short_max_pct", False),
    "stopLongMaxDays": ("stop_long_max_days", True),
    "stopShortMaxDays": ("stop_short_max_days", True),
    "trailRRLong": ("trail_rr_long", False),
    "trailRRShort": ("trail_rr_short", False),
    "trailLongLength": ("trail_ma_long_length", True),
    "trailLongOffset": ("trail_ma_long_offset", False),
    "trailShortLength": ("trail_ma_short_length", True),
    "trailShortOffset": ("trail_ma_short_offset", False),
}

# Reverse mapping: internal_name -> frontend_name
INTERNAL_TO_FRONTEND_MAP: Dict[str, str] = {
    internal: frontend for frontend, (internal, _) in PARAMETER_MAP.items()
}
INTERNAL_TO_FRONTEND_MAP.update(
    {
        "ma_type": "maType",
        "trail_ma_long_type": "trailLongType",
        "trail_ma_short_type": "trailShortType",
        "risk_per_trade_pct": "riskPerTrade",
        "contract_size": "contractSize",
        "commission_rate": "commissionRate",
        "atr_period": "atrPeriod",
    }
)


# ============================================================================
# Utilities
# ============================================================================


def _generate_numeric_sequence(
    start: float, stop: float, step: float, is_int: bool
) -> List[Union[int, float]]:
    if step == 0:
        raise ValueError("Step must be non-zero for optimization ranges.")
    delta = abs(step)
    step_value = delta if start <= stop else -delta
    decimals = max(0, -Decimal(str(step)).normalize().as_tuple().exponent)
    epsilon = delta * 1e-9

    values: List[Union[int, float]] = []
    index = 0

    while True:
        raw_value = start + index * step_value
        if step_value > 0:
            if raw_value > stop + epsilon:
                break
        else:
            if raw_value < stop - epsilon:
                break

        if is_int:
            values.append(int(round(raw_value)))
        else:
            rounded_value = round(raw_value, decimals)
            if rounded_value == 0:
                rounded_value = 0.0
            values.append(float(rounded_value))

        index += 1

    if not values:
        if is_int:
            values.append(int(round(start)))
        else:
            rounded_start = round(start, decimals)
            values.append(float(0.0 if rounded_start == 0 else rounded_start))
    return values


def _parse_timestamp(value: Any) -> Optional[pd.Timestamp]:
    if value in (None, ""):
        return None
    try:
        ts = pd.Timestamp(value)
    except (ValueError, TypeError):  # pragma: no cover - defensive
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts


def _run_single_combination(
    args: Tuple[Dict[str, Any], pd.DataFrame, int, Any]
) -> OptimizationResult:
    """
    Worker function to run a single parameter combination using strategy.run().

    Args:
        args: Tuple of (params_dict, df, trade_start_idx, strategy_class)

    Returns:
        OptimizationResult with metrics for this combination
    """

    params_dict, df, trade_start_idx, strategy_class = args

    def _as_int(key: str, default: int = 0) -> int:
        try:
            return int(float(params_dict.get(key, default)))
        except (TypeError, ValueError):
            return int(default)

    def _as_float(key: str, default: float = 0.0) -> float:
        try:
            return float(params_dict.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    def _base_result() -> OptimizationResult:
        return OptimizationResult(
            ma_type=str(params_dict.get("ma_type", "")),
            ma_length=_as_int("ma_length"),
            close_count_long=_as_int("close_count_long"),
            close_count_short=_as_int("close_count_short"),
            stop_long_atr=_as_float("stop_long_atr"),
            stop_long_rr=_as_float("stop_long_rr"),
            stop_long_lp=max(1, _as_int("stop_long_lp", 1)),
            stop_short_atr=_as_float("stop_short_atr"),
            stop_short_rr=_as_float("stop_short_rr"),
            stop_short_lp=max(1, _as_int("stop_short_lp", 1)),
            stop_long_max_pct=_as_float("stop_long_max_pct"),
            stop_short_max_pct=_as_float("stop_short_max_pct"),
            stop_long_max_days=_as_int("stop_long_max_days"),
            stop_short_max_days=_as_int("stop_short_max_days"),
            trail_rr_long=_as_float("trail_rr_long"),
            trail_rr_short=_as_float("trail_rr_short"),
            trail_ma_long_type=str(params_dict.get("trail_ma_long_type", "")),
            trail_ma_long_length=_as_int("trail_ma_long_length"),
            trail_ma_long_offset=_as_float("trail_ma_long_offset"),
            trail_ma_short_type=str(params_dict.get("trail_ma_short_type", "")),
            trail_ma_short_length=_as_int("trail_ma_short_length"),
            trail_ma_short_offset=_as_float("trail_ma_short_offset"),
            net_profit_pct=0.0,
            max_drawdown_pct=0.0,
            total_trades=0,
            sharpe_ratio=None,
            profit_factor=None,
            romad=None,
            ulcer_index=None,
            recovery_factor=None,
            consistency_score=None,
        )

    try:
        strategy_payload = {
            INTERNAL_TO_FRONTEND_MAP.get(key, key): value
            for key, value in params_dict.items()
        }

        result = strategy_class.run(df, strategy_payload, trade_start_idx)

        basic_metrics = metrics.calculate_basic(result)
        advanced_metrics = metrics.calculate_advanced(result)

        opt_result = _base_result()
        for key, value in params_dict.items():
            if not hasattr(opt_result, key):
                setattr(opt_result, key, value)
        opt_result.net_profit_pct = basic_metrics.net_profit_pct
        opt_result.max_drawdown_pct = basic_metrics.max_drawdown_pct
        opt_result.total_trades = basic_metrics.total_trades
        opt_result.sharpe_ratio = advanced_metrics.sharpe_ratio
        opt_result.profit_factor = advanced_metrics.profit_factor
        opt_result.romad = advanced_metrics.romad
        opt_result.ulcer_index = advanced_metrics.ulcer_index
        opt_result.recovery_factor = advanced_metrics.recovery_factor
        opt_result.consistency_score = advanced_metrics.consistency_score
        return opt_result
    except Exception:
        return _base_result()


def calculate_score(
    results: List[OptimizationResult],
    config: Optional[Dict[str, Any]],
) -> List[OptimizationResult]:
    """Calculate composite score for optimization results."""

    if not results:
        return results

    if config is None:
        config = {}

    normalized_config = DEFAULT_SCORE_CONFIG.copy()
    normalized_config.update({k: v for k, v in (config or {}).items() if v is not None})

    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y", "on"}:
                return True
            if lowered in {"false", "0", "no", "n", "off"}:
                return False
        return False

    weights = normalized_config.get("weights") or {}
    enabled_metrics = normalized_config.get("enabled_metrics") or {}
    invert_metrics = normalized_config.get("invert_metrics") or {}
    filter_enabled = _as_bool(normalized_config.get("filter_enabled", False))
    try:
        min_score_threshold = float(normalized_config.get("min_score_threshold", 0.0))
    except (TypeError, ValueError):
        min_score_threshold = 0.0
    min_score_threshold = max(0.0, min(100.0, min_score_threshold))

    normalization_method_raw = normalized_config.get("normalization_method", "percentile")
    normalization_method = (
        str(normalization_method_raw).strip().lower() if normalization_method_raw is not None else "percentile"
    )
    if normalization_method not in {"", "percentile"}:
        normalization_method = "percentile"

    metrics_to_normalize: List[str] = []
    for metric in SCORE_METRIC_ATTRS:
        if _as_bool(enabled_metrics.get(metric, False)):
            metrics_to_normalize.append(metric)

    normalized_values: Dict[str, Dict[int, float]] = {}
    for metric_name in metrics_to_normalize:
        attr_name = SCORE_METRIC_ATTRS[metric_name]
        metric_values = [
            getattr(item, attr_name)
            for item in results
            if getattr(item, attr_name) is not None
        ]
        if not metric_values:
            normalized_values[metric_name] = {id(item): 50.0 for item in results}
            continue
        sorted_vals = sorted(float(value) for value in metric_values)
        total = len(sorted_vals)
        normalized_values[metric_name] = {}
        invert = _as_bool(invert_metrics.get(metric_name, False))
        for item in results:
            value = getattr(item, attr_name)
            if value is None:
                rank = 50.0
            else:
                idx = bisect.bisect_left(sorted_vals, float(value))
                rank = (idx / total) * 100.0
                if invert:
                    rank = 100.0 - rank
            normalized_values[metric_name][id(item)] = rank

    for item in results:
        item.score = 0.0
        score_total = 0.0
        weight_total = 0.0
        for metric_name in metrics_to_normalize:
            weight_raw = weights.get(metric_name, 0.0)
            try:
                weight = float(weight_raw)
            except (TypeError, ValueError):
                weight = 0.0
            weight = max(0.0, min(1.0, weight))
            if weight <= 0:
                continue
            score_total += normalized_values[metric_name][id(item)] * weight
            weight_total += weight
        if weight_total > 0:
            item.score = score_total / weight_total

    if filter_enabled:
        results = [item for item in results if item.score >= min_score_threshold]

    return results


@dataclass
class OptunaConfig:
    """Configuration parameters that control Optuna optimisation."""

    target: str = "score"
    budget_mode: str = "trials"  # "trials", "time", or "convergence"
    n_trials: int = 500
    time_limit: int = 3600  # seconds
    convergence_patience: int = 50
    enable_pruning: bool = True
    sampler: str = "tpe"  # "tpe" or "random"
    pruner: str = "median"  # "median", "percentile", "patient", "none"
    warmup_trials: int = 20
    save_study: bool = False
    study_name: Optional[str] = None


class OptunaOptimizer:
    """Optuna-based optimizer for Bayesian hyperparameter search using multiprocess evaluation."""

    def __init__(self, base_config, optuna_config: OptunaConfig) -> None:
        self.base_config = base_config
        self.optuna_config = optuna_config
        self.pool: Optional[mp.pool.Pool] = None
        self.trial_results: List[OptimizationResult] = []
        self.best_value: float = float("-inf")
        self.trials_without_improvement: int = 0
        self.start_time: Optional[float] = None
        self.pruned_trials: int = 0
        self.study: Optional[optuna.Study] = None
        self.pruner: Optional[optuna.pruners.BasePruner] = None
        self.effective_param_map: Dict[str, Tuple[str, bool]] = dict(PARAMETER_MAP)

    # ------------------------------------------------------------------
    # Search space handling
    # ------------------------------------------------------------------
    def _build_search_space(self) -> Dict[str, Dict[str, Any]]:
        """Construct the Optuna search space from the optimiser configuration."""

        space: Dict[str, Dict[str, Any]] = {}

        param_map: Dict[str, Tuple[str, bool]] = dict(PARAMETER_MAP)
        for name, param_type in (self.base_config.param_types or {}).items():
            if name not in param_map:
                is_int = str(param_type).lower() == "int"
                param_map[name] = (name, is_int)

        self.effective_param_map = param_map

        for frontend_name, (internal_name, is_int) in param_map.items():
            if not self.base_config.enabled_params.get(frontend_name):
                continue

            if frontend_name not in self.base_config.param_ranges:
                raise ValueError(f"Missing range for parameter '{frontend_name}'.")

            start, stop, step = self.base_config.param_ranges[frontend_name]
            low = min(float(start), float(stop))
            high = max(float(start), float(stop))
            step_value = abs(float(step)) if step else 0.0

            if is_int:
                if low == high:
                    low = high = round(low)
                spec: Dict[str, Any] = {
                    "type": "int",
                    "low": int(round(low)),
                    "high": int(round(high)),
                }
                int_step = max(1, int(round(step_value))) if step_value else 1
                spec["step"] = int_step
            else:
                spec = {
                    "type": "float",
                    "low": float(low),
                    "high": float(high),
                }
                if step_value:
                    spec["step"] = float(step_value)
                if low > 0 and high / max(low, 1e-9) > 100:
                    spec["log"] = True

            space[internal_name] = spec

        trend_types = [ma.upper() for ma in self.base_config.ma_types_trend]
        trail_long_types = [ma.upper() for ma in self.base_config.ma_types_trail_long]
        trail_short_types = [ma.upper() for ma in self.base_config.ma_types_trail_short]

        include_ma_types = bool(trend_types or trail_long_types or trail_short_types)

        if include_ma_types:
            if not trend_types or not trail_long_types:
                raise ValueError("At least one MA type must be selected in each group.")

            space["ma_type"] = {"type": "categorical", "choices": trend_types}

            if self.base_config.lock_trail_types:
                short_set = {ma.upper() for ma in trail_short_types}
                paired = [ma for ma in trail_long_types if ma in short_set] or trail_long_types
                space["trail_ma_long_type"] = {"type": "categorical", "choices": paired}
            else:
                if not trail_short_types:
                    raise ValueError(
                        "At least one trail short MA type must be selected when lock_trail_types is disabled."
                    )
                space["trail_ma_long_type"] = {
                    "type": "categorical",
                    "choices": trail_long_types,
                }
                space["trail_ma_short_type"] = {
                    "type": "categorical",
                    "choices": trail_short_types,
                }

        return space

    # ------------------------------------------------------------------
    # Sampler / pruner factories
    # ------------------------------------------------------------------
    def _create_sampler(self) -> optuna.samplers.BaseSampler:
        if self.optuna_config.sampler == "random":
            return RandomSampler()
        return TPESampler(
            n_startup_trials=max(0, int(self.optuna_config.warmup_trials)),
            multivariate=True,
            constant_liar=True,
        )

    def _create_pruner(self) -> Optional[optuna.pruners.BasePruner]:
        if not self.optuna_config.enable_pruning or self.optuna_config.pruner == "none":
            return None
        if self.optuna_config.pruner == "percentile":
            return PercentilePruner(
                percentile=25.0,
                n_startup_trials=max(0, int(self.optuna_config.warmup_trials)),
            )
        if self.optuna_config.pruner == "patient":
            return PatientPruner(
                wrapped_pruner=MedianPruner(
                    n_startup_trials=max(0, int(self.optuna_config.warmup_trials))
                ),
                patience=3,
            )
        return MedianPruner(
            n_startup_trials=max(0, int(self.optuna_config.warmup_trials))
        )

    # ------------------------------------------------------------------
    # Worker pool initialisation
    # ------------------------------------------------------------------
    def _collect_lengths(self, frontend_key: str) -> Iterable[int]:
        if self.base_config.enabled_params.get(frontend_key):
            start, stop, step = self.base_config.param_ranges[frontend_key]
            sequence = _generate_numeric_sequence(start, stop, step, True)
        else:
            value = self.base_config.fixed_params.get(frontend_key, 0)
            sequence = [value]
        return [int(round(val)) for val in sequence]

    def _setup_worker_pool(self) -> None:
        """Initialize the worker pool for Optuna optimization."""

        from strategies import get_strategy

        try:
            strategy_class = get_strategy(self.base_config.strategy_id)
        except ValueError as e:
            raise ValueError(
                f"Failed to load strategy '{self.base_config.strategy_id}': {e}"
            )

        from .backtest_engine import prepare_dataset_with_warmup

        df = load_data(self.base_config.csv_file)

        use_date_filter = bool(self.base_config.fixed_params.get("dateFilter", False))
        start_ts = _parse_timestamp(self.base_config.fixed_params.get("start"))
        end_ts = _parse_timestamp(self.base_config.fixed_params.get("end"))

        trade_start_idx = 0
        if use_date_filter and (start_ts is not None or end_ts is not None):
            try:
                df, trade_start_idx = prepare_dataset_with_warmup(
                    df, start_ts, end_ts, self.base_config.warmup_bars
                )
            except Exception as exc:
                raise ValueError(f"Failed to prepare dataset with warmup: {exc}")

        self.df = df
        self.trade_start_idx = trade_start_idx
        self.strategy_class = strategy_class

        processes = min(32, max(1, int(self.base_config.worker_processes)))
        self.pool = mp.Pool(processes=processes)

    # ------------------------------------------------------------------
    # Objective evaluation
    # ------------------------------------------------------------------
    def _evaluate_parameters(self, params_dict: Dict[str, Any]) -> OptimizationResult:
        if self.pool is None:
            raise RuntimeError("Worker pool is not initialised.")

        args = (params_dict, self.df, self.trade_start_idx, self.strategy_class)
        return self.pool.apply(_run_single_combination, (args,))

    def _prepare_trial_parameters(self, trial: optuna.Trial, search_space: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        params_dict: Dict[str, Any] = {}

        for key, spec in search_space.items():
            p_type = spec["type"]
            if p_type == "int":
                params_dict[key] = trial.suggest_int(
                    key,
                    int(spec["low"]),
                    int(spec["high"]),
                    step=int(spec.get("step", 1)),
                )
            elif p_type == "float":
                if spec.get("log"):
                    params_dict[key] = trial.suggest_float(
                        key,
                        float(spec["low"]),
                        float(spec["high"]),
                        log=True,
                    )
                else:
                    step = spec.get("step")
                    if step:
                        params_dict[key] = trial.suggest_float(
                            key,
                            float(spec["low"]),
                            float(spec["high"]),
                            step=float(step),
                        )
                    else:
                        params_dict[key] = trial.suggest_float(
                            key,
                            float(spec["low"]),
                            float(spec["high"]),
                        )
            elif p_type == "categorical":
                params_dict[key] = trial.suggest_categorical(key, list(spec["choices"]))

        if self.base_config.lock_trail_types:
            trail_type = params_dict.get("trail_ma_long_type")
            if trail_type is not None:
                params_dict["trail_ma_short_type"] = trail_type

        for frontend_name, (internal_name, is_int) in self.effective_param_map.items():
            if self.base_config.enabled_params.get(frontend_name):
                continue
            value = self.base_config.fixed_params.get(frontend_name)
            if value is None:
                continue
            params_dict[internal_name] = int(round(float(value))) if is_int else float(value)

        # Add global configuration parameters that are not in PARAMETER_MAP
        # These are always fixed and must be passed to the strategy
        params_dict.update({
            "risk_per_trade_pct": self.base_config.risk_per_trade_pct,
            "contract_size": self.base_config.contract_size,
            "commission_rate": self.base_config.commission_rate,
            "atr_period": self.base_config.atr_period,
        })

        return params_dict

    def _objective(self, trial: optuna.Trial, search_space: Dict[str, Dict[str, Any]]) -> float:
        params_dict = self._prepare_trial_parameters(trial, search_space)

        result = self._evaluate_parameters(params_dict)

        if self.base_config.filter_min_profit and (
            result.net_profit_pct < float(self.base_config.min_profit_threshold)
        ):
            self.pruned_trials += 1
            raise optuna.TrialPruned("Below minimum profit threshold")

        # For composite score target, calculate score dynamically based on all results so far
        score_config = self.base_config.score_config or DEFAULT_SCORE_CONFIG
        objective_value: float

        if self.optuna_config.target == "score":
            # Add current result to accumulated results
            temp_results = self.trial_results + [result]
            # Calculate scores for all results using percentile ranking
            scored_results = calculate_score(temp_results, score_config)
            # Get the score of the current (last) result
            if scored_results:
                result = scored_results[-1]
                objective_value = float(result.score)
            else:
                objective_value = 0.0
        elif self.optuna_config.target == "net_profit":
            objective_value = float(result.net_profit_pct)
        elif self.optuna_config.target == "romad":
            objective_value = float(result.romad or 0.0)
        elif self.optuna_config.target == "sharpe":
            objective_value = float(result.sharpe_ratio or 0.0)
        elif self.optuna_config.target == "max_drawdown":
            objective_value = -float(result.max_drawdown_pct)
        else:
            objective_value = float(result.romad or 0.0)

        # Check score threshold filter (only applies when score is calculated)
        if self.optuna_config.target == "score" and score_config.get("filter_enabled"):
            min_score = float(score_config.get("min_score_threshold", 0.0))
            if result.score < min_score:
                self.pruned_trials += 1
                raise optuna.TrialPruned("Below minimum score threshold")

        if self.pruner is not None:
            trial.report(objective_value, step=0)
            if trial.should_prune():
                self.pruned_trials += 1
                raise optuna.TrialPruned("Pruned by Optuna")

        self.trial_results.append(result)
        setattr(result, "optuna_trial_number", trial.number)
        setattr(result, "optuna_value", objective_value)

        if objective_value > self.best_value:
            self.best_value = objective_value
            self.trials_without_improvement = 0
        else:
            self.trials_without_improvement += 1

        return objective_value

    # ------------------------------------------------------------------
    # Main execution entrypoint
    # ------------------------------------------------------------------
    def optimize(self) -> List[OptimizationResult]:
        logger.info(
            "Starting Optuna optimisation: target=%s, budget_mode=%s",
            self.optuna_config.target,
            self.optuna_config.budget_mode,
        )

        self.start_time = time.time()
        self.trial_results = []
        self.best_value = float("-inf")
        self.trials_without_improvement = 0
        self.pruned_trials = 0

        search_space = self._build_search_space()
        self._setup_worker_pool()

        sampler = self._create_sampler()
        self.pruner = self._create_pruner()

        storage = None
        if self.optuna_config.save_study:
            storage = optuna.storages.RDBStorage(
                url="sqlite:///optuna_study.db",
                engine_kwargs={"connect_args": {"timeout": 30}},
            )

        study_name = self.optuna_config.study_name or f"strategy_opt_{int(time.time())}"

        self.study = optuna.create_study(
            study_name=study_name,
            direction="maximize",
            sampler=sampler,
            pruner=self.pruner,
            storage=storage,
            load_if_exists=self.optuna_config.save_study,
        )

        timeout = None
        n_trials = None
        callbacks = []

        if self.optuna_config.budget_mode == "time":
            timeout = max(60, int(self.optuna_config.time_limit))
        elif self.optuna_config.budget_mode == "trials":
            n_trials = max(1, int(self.optuna_config.n_trials))
        elif self.optuna_config.budget_mode == "convergence":
            n_trials = 10000

            def convergence_callback(study: optuna.Study, _trial: optuna.Trial) -> None:
                if self.trials_without_improvement >= int(self.optuna_config.convergence_patience):
                    study.stop()
                    logger.info(
                        "Stopping optimisation due to convergence threshold (patience=%s)",
                        self.optuna_config.convergence_patience,
                    )

            callbacks.append(convergence_callback)

        try:
            self.study.optimize(
                lambda trial: self._objective(trial, search_space),
                n_trials=n_trials,
                timeout=timeout,
                callbacks=callbacks or None,
                show_progress_bar=False,
            )
        except KeyboardInterrupt:
            logger.info("Optuna optimisation interrupted by user")
        finally:
            if self.pool is not None:
                self.pool.close()
                self.pool.join()
                self.pool = None
            self.pruner = None

        end_time = time.time()
        optimisation_time = end_time - (self.start_time or end_time)

        logger.info(
            "Optuna optimisation completed: trials=%s, best_value=%s, time=%.1fs",
            len(self.study.trials) if self.study else 0,
            getattr(self.study, "best_value", float("nan")),
            optimisation_time,
        )

        # Calculate scores for all results using percentile ranking
        score_config = self.base_config.score_config or DEFAULT_SCORE_CONFIG
        self.trial_results = calculate_score(self.trial_results, score_config)

        if self.study:
            completed_trials = sum(1 for trial in self.study.trials if trial.state == TrialState.COMPLETE)
            pruned_trials = sum(1 for trial in self.study.trials if trial.state == TrialState.PRUNED)
            best_trial_number = self.study.best_trial.number if self.study.best_trial else None
            best_value = self.study.best_value if completed_trials else None
        else:
            completed_trials = len(self.trial_results)
            pruned_trials = self.pruned_trials
            best_trial_number = None
            best_value = None

        summary = {
            "method": "Optuna",
            "target": self.optuna_config.target,
            "budget_mode": self.optuna_config.budget_mode,
            "total_trials": len(self.study.trials) if self.study else len(self.trial_results),
            "completed_trials": completed_trials,
            "pruned_trials": pruned_trials,
            "best_trial_number": best_trial_number,
            "best_value": best_value,
            "optimization_time_seconds": optimisation_time,
        }
        setattr(self.base_config, "optuna_summary", summary)

        if self.optuna_config.target == "max_drawdown":
            self.trial_results.sort(key=lambda item: float(item.max_drawdown_pct))
        elif self.optuna_config.target == "score":
            self.trial_results.sort(key=lambda item: float(item.score), reverse=True)
        elif self.optuna_config.target == "net_profit":
            self.trial_results.sort(key=lambda item: float(item.net_profit_pct), reverse=True)
        elif self.optuna_config.target == "romad":
            self.trial_results.sort(key=lambda item: float(item.romad or float("-inf")), reverse=True)
        elif self.optuna_config.target == "sharpe":
            self.trial_results.sort(
                key=lambda item: float(item.sharpe_ratio or float("-inf")), reverse=True
            )
        else:
            self.trial_results.sort(key=lambda item: float(item.score), reverse=True)

        return self.trial_results


def run_optuna_optimization(base_config, optuna_config: OptunaConfig) -> List[OptimizationResult]:
    """Execute Optuna optimisation using the provided configuration."""

    optimizer = OptunaOptimizer(base_config, optuna_config)
    return optimizer.optimize()


def run_optimization(config: OptimizationConfig) -> List[OptimizationResult]:
    """Compat wrapper that executes Optuna optimization only."""

    if not getattr(config, "strategy_id", ""):
        raise ValueError("strategy_id must be specified in OptimizationConfig.")

    if getattr(config, "optimization_mode", "optuna") != "optuna":
        raise ValueError("Only Optuna optimization is supported in Phase 3.")

    optuna_config = OptunaConfig(
        target=getattr(config, "optuna_target", "score"),
        budget_mode=getattr(config, "optuna_budget_mode", "trials"),
        n_trials=int(getattr(config, "optuna_n_trials", 500) or 500),
        time_limit=int(getattr(config, "optuna_time_limit", 3600) or 3600),
        convergence_patience=int(getattr(config, "optuna_convergence", 50) or 50),
        enable_pruning=bool(getattr(config, "optuna_enable_pruning", True)),
        sampler=getattr(config, "optuna_sampler", "tpe"),
        pruner=getattr(config, "optuna_pruner", "median"),
        warmup_trials=int(getattr(config, "optuna_warmup_trials", 20) or 20),
        save_study=bool(getattr(config, "optuna_save_study", False)),
        study_name=getattr(config, "optuna_study_name", None),
    )

    return run_optuna_optimization(config, optuna_config)
