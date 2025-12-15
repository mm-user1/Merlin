"""Optuna-based Bayesian optimization engine for S_01 TrailingMA."""
from __future__ import annotations

import bisect
import logging
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

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
    """Generic optimization configuration for any strategy."""

    # Required fields
    csv_file: Any
    strategy_id: str
    enabled_params: Dict[str, bool]
    param_ranges: Dict[str, Tuple[float, float, float]]
    param_types: Dict[str, str]
    fixed_params: Dict[str, Any]

    # Execution settings
    worker_processes: int = 1
    warmup_bars: int = 1000

    # Strategy-specific execution defaults
    contract_size: float = 1.0
    commission_rate: float = 0.0005
    risk_per_trade_pct: float = 1.0

    # Optimization control
    filter_min_profit: bool = False
    min_profit_threshold: float = 0.0
    score_config: Optional[Dict[str, Any]] = None
    optimization_mode: str = "optuna"


@dataclass
class OptimizationResult:
    """Generic optimization result for any strategy."""

    params: Dict[str, Any]
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
# Process-level cache for parallel workers
# ============================================================================
# Each worker process maintains its own cache to avoid reloading data
_PROCESS_CACHE: Dict[str, Any] = {}


def _get_cached_data(
    csv_file: Any,
    csv_data: Optional[str],
    start_ts: Optional[pd.Timestamp],
    end_ts: Optional[pd.Timestamp],
    warmup_bars: int,
    strategy_id: str,
    use_date_filter: bool,
) -> Dict[str, Any]:
    """
    Get or load cached data for this worker process.

    Each parallel worker process calls this on first trial,
    then reuses cached data for subsequent trials.

    Args:
        csv_file: File path or file-like object (used if csv_data is None)
        csv_data: Pre-read CSV content as string (preferred for file uploads)
        start_ts: Start timestamp for date filtering
        end_ts: End timestamp for date filtering
        warmup_bars: Number of warmup bars
        strategy_id: Strategy identifier
        use_date_filter: Whether to apply date filtering
    """
    import io

    # Create cache key from parameters
    if csv_data is not None:
        # Use hash of data for cache key when we have pre-read content
        file_key = f"preloaded_{hash(csv_data[:1000]) if len(csv_data) > 1000 else hash(csv_data)}"
    else:
        file_key = str(csv_file) if not hasattr(csv_file, 'name') else csv_file.name
    cache_key = f"{file_key}:{start_ts}:{end_ts}:{warmup_bars}:{strategy_id}"

    if cache_key not in _PROCESS_CACHE:
        from strategies import get_strategy
        from .backtest_engine import prepare_dataset_with_warmup

        logger.debug(f"Worker {os.getpid()} loading data for cache key: {cache_key[:50]}...")

        # Use pre-read data if available, otherwise load from file
        if csv_data is not None:
            df = load_data(io.StringIO(csv_data))
        else:
            df = load_data(csv_file)

        trade_start_idx = 0

        if use_date_filter and (start_ts is not None or end_ts is not None):
            df, trade_start_idx = prepare_dataset_with_warmup(
                df, start_ts, end_ts, warmup_bars
            )

        strategy_class = get_strategy(strategy_id)

        _PROCESS_CACHE[cache_key] = {
            'df': df,
            'trade_start_idx': trade_start_idx,
            'strategy_class': strategy_class,
        }
        logger.debug(f"Worker {os.getpid()} cache initialized: {len(df)} rows")

    return _PROCESS_CACHE[cache_key]


def _run_trial_parallel(
    params_dict: Dict[str, Any],
    csv_file: Any,
    csv_data: Optional[str],
    start_ts: Optional[pd.Timestamp],
    end_ts: Optional[pd.Timestamp],
    warmup_bars: int,
    strategy_id: str,
    use_date_filter: bool,
) -> OptimizationResult:
    """
    Standalone worker function for parallel trial execution.

    This function is called by Optuna's parallel backend (joblib).
    Each worker process caches data on first call.

    Args:
        params_dict: Strategy parameters to evaluate
        csv_file: File path (used if csv_data is None)
        csv_data: Pre-read CSV content as string (avoids file handle race conditions)
        start_ts: Start timestamp for date filtering
        end_ts: End timestamp for date filtering
        warmup_bars: Number of warmup bars
        strategy_id: Strategy identifier
        use_date_filter: Whether to apply date filtering
    """
    cached = _get_cached_data(
        csv_file, csv_data, start_ts, end_ts, warmup_bars, strategy_id, use_date_filter
    )

    df = cached['df']
    trade_start_idx = cached['trade_start_idx']
    strategy_class = cached['strategy_class']

    try:
        result = strategy_class.run(df, params_dict, trade_start_idx)

        basic_metrics = metrics.calculate_basic(result)
        advanced_metrics = metrics.calculate_advanced(result)

        return OptimizationResult(
            params=params_dict.copy(),
            net_profit_pct=basic_metrics.net_profit_pct,
            max_drawdown_pct=basic_metrics.max_drawdown_pct,
            total_trades=basic_metrics.total_trades,
            romad=advanced_metrics.romad,
            sharpe_ratio=advanced_metrics.sharpe_ratio,
            profit_factor=advanced_metrics.profit_factor,
            ulcer_index=advanced_metrics.ulcer_index,
            recovery_factor=advanced_metrics.recovery_factor,
            consistency_score=advanced_metrics.consistency_score,
        )
    except Exception:
        return OptimizationResult(
            params=params_dict.copy(),
            net_profit_pct=0.0,
            max_drawdown_pct=0.0,
            total_trades=0,
        )


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

    def _base_result(params: Dict[str, Any]) -> OptimizationResult:
        return OptimizationResult(
            params=params.copy(),
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
        result = strategy_class.run(df, params_dict, trade_start_idx)

        basic_metrics = metrics.calculate_basic(result)
        advanced_metrics = metrics.calculate_advanced(result)

        return OptimizationResult(
            params=params_dict.copy(),
            net_profit_pct=basic_metrics.net_profit_pct,
            max_drawdown_pct=basic_metrics.max_drawdown_pct,
            total_trades=basic_metrics.total_trades,
            romad=advanced_metrics.romad,
            sharpe_ratio=advanced_metrics.sharpe_ratio,
            profit_factor=advanced_metrics.profit_factor,
            ulcer_index=advanced_metrics.ulcer_index,
            recovery_factor=advanced_metrics.recovery_factor,
            consistency_score=advanced_metrics.consistency_score,
        )
    except Exception:
        return _base_result(params_dict)


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
    """Optuna-based optimizer for Bayesian hyperparameter search with parallel execution."""

    def __init__(self, base_config, optuna_config: OptunaConfig) -> None:
        self.base_config = base_config
        self.optuna_config = optuna_config
        self.trial_results: List[OptimizationResult] = []
        self.best_value: float = float("-inf")
        self.trials_without_improvement: int = 0
        self.start_time: Optional[float] = None
        self.pruned_trials: int = 0
        self.study: Optional[optuna.Study] = None
        self.pruner: Optional[optuna.pruners.BasePruner] = None
        self.param_type_map: Dict[str, str] = {}
        # Worker configuration for parallel execution
        self._worker_config: Dict[str, Any] = {}
        self.n_jobs: int = min(32, max(1, int(base_config.worker_processes)))

    # ------------------------------------------------------------------
    # Search space handling
    # ------------------------------------------------------------------
    def _build_search_space(self) -> Dict[str, Dict[str, Any]]:
        """Construct the Optuna search space from strategy config metadata."""

        from strategies import get_strategy_config

        try:
            strategy_config = get_strategy_config(self.base_config.strategy_id)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Failed to load strategy config for {self.base_config.strategy_id}: {exc}")

        parameters = strategy_config.get("parameters", {}) if isinstance(strategy_config, dict) else {}
        if not isinstance(parameters, dict):
            raise ValueError(f"Invalid parameters section in strategy config for {self.base_config.strategy_id}")

        space: Dict[str, Dict[str, Any]] = {}
        self.param_type_map = {}

        for param_name, param_spec in parameters.items():
            if not isinstance(param_spec, dict):
                continue

            param_type = str(
                self.base_config.param_types.get(param_name, param_spec.get("type", "float"))
            ).lower()
            self.param_type_map[param_name] = param_type

            if not self.base_config.enabled_params.get(param_name, False):
                continue

            optimize_spec = param_spec.get("optimize", {}) if isinstance(param_spec.get("optimize", {}), dict) else {}
            override_range = self.base_config.param_ranges.get(param_name)

            if param_type == "int":
                min_val = optimize_spec.get("min", param_spec.get("min", 0))
                max_val = optimize_spec.get("max", param_spec.get("max", 0))
                step = optimize_spec.get("step", param_spec.get("step", 1))
                if override_range:
                    min_val, max_val, step = override_range
                space[param_name] = {
                    "type": "int",
                    "low": int(round(float(min_val))),
                    "high": int(round(float(max_val))),
                    "step": max(1, int(round(float(step)))) if step is not None else 1,
                }
            elif param_type == "float":
                min_val = optimize_spec.get("min", param_spec.get("min", 0.0))
                max_val = optimize_spec.get("max", param_spec.get("max", 0.0))
                step = optimize_spec.get("step", param_spec.get("step"))
                if override_range:
                    min_val, max_val, step = override_range
                spec: Dict[str, Any] = {
                    "type": "float",
                    "low": float(min_val),
                    "high": float(max_val),
                }
                if step not in (None, 0, 0.0):
                    spec["step"] = float(step)
                space[param_name] = spec
            elif param_type in {"select", "options"}:
                options = param_spec.get("options", [])

                range_override = self.base_config.param_ranges.get(param_name)
                if isinstance(range_override, dict):
                    override_options = range_override.get("values") or range_override.get("options")
                    if isinstance(override_options, (list, tuple)):
                        options = override_options

                fixed_override = self.base_config.fixed_params.get(f"{param_name}_options")
                if isinstance(fixed_override, (list, tuple)) and fixed_override:
                    options = fixed_override

                cleaned_options = [opt for opt in options if str(opt).strip()]
                if not cleaned_options:
                    continue

                space[param_name] = {
                    "type": "categorical",
                    "choices": list(cleaned_options),
                }

            elif param_type in {"bool", "boolean"}:
                space[param_name] = {
                    "type": "categorical",
                    "choices": [True, False],
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
    # Worker configuration setup
    # ------------------------------------------------------------------
    def _setup_worker_config(self) -> None:
        """Prepare configuration for parallel workers.

        Instead of creating a process pool, we store the configuration
        that workers need to initialize themselves. Each worker will
        load and cache data on first use via _get_cached_data().

        IMPORTANT: For file-like objects (e.g., Flask uploads), we read the
        data once here in the main process to avoid race conditions when
        multiple workers try to read the same file handle simultaneously.
        """
        from strategies import get_strategy

        # Validate strategy exists
        try:
            get_strategy(self.base_config.strategy_id)
        except ValueError as e:
            raise ValueError(
                f"Failed to load strategy '{self.base_config.strategy_id}': {e}"
            )

        use_date_filter = bool(self.base_config.fixed_params.get("dateFilter", False))
        start_ts = _parse_timestamp(self.base_config.fixed_params.get("start"))
        end_ts = _parse_timestamp(self.base_config.fixed_params.get("end"))

        # Handle file-like objects (e.g., Flask uploads) by reading once in main process
        # This prevents race conditions when multiple workers try to read the same file
        csv_source = self.base_config.csv_file
        csv_data_for_workers = None

        if hasattr(csv_source, 'read'):
            # It's a file-like object - read content once
            logger.info("Reading uploaded file content in main process to avoid race conditions")
            try:
                # Save current position if possible
                start_pos = csv_source.tell() if hasattr(csv_source, 'tell') else 0
                content = csv_source.read()

                # Handle bytes vs string
                if isinstance(content, bytes):
                    csv_data_for_workers = content.decode('utf-8')
                else:
                    csv_data_for_workers = content

                # Try to reset position for any other code that might need it
                if hasattr(csv_source, 'seek'):
                    csv_source.seek(start_pos)
            except Exception as e:
                logger.warning(f"Could not read file content: {e}, will pass file reference")
                csv_data_for_workers = None

        # Store config for workers - they will load data themselves
        self._worker_config = {
            'csv_file': self.base_config.csv_file if csv_data_for_workers is None else None,
            'csv_data': csv_data_for_workers,  # Pre-read content for file-like objects
            'start_ts': start_ts,
            'end_ts': end_ts,
            'warmup_bars': self.base_config.warmup_bars,
            'strategy_id': self.base_config.strategy_id,
            'use_date_filter': use_date_filter,
        }

        logger.info(
            f"Worker config prepared: n_jobs={self.n_jobs}, "
            f"strategy={self.base_config.strategy_id}, "
            f"data_preloaded={csv_data_for_workers is not None}"
        )

    # ------------------------------------------------------------------
    # Objective evaluation
    # ------------------------------------------------------------------
    def _evaluate_parameters(self, params_dict: Dict[str, Any]) -> OptimizationResult:
        """Evaluate a single parameter combination.

        Uses _run_trial_parallel which handles data caching per worker process.
        """
        if not self._worker_config:
            raise RuntimeError("Worker config not initialized. Call _setup_worker_config() first.")

        return _run_trial_parallel(
            params_dict=params_dict,
            csv_file=self._worker_config['csv_file'],
            csv_data=self._worker_config.get('csv_data'),
            start_ts=self._worker_config['start_ts'],
            end_ts=self._worker_config['end_ts'],
            warmup_bars=self._worker_config['warmup_bars'],
            strategy_id=self._worker_config['strategy_id'],
            use_date_filter=self._worker_config['use_date_filter'],
        )

    def _cast_param_value(self, name: str, value: Any) -> Any:
        param_type = self.param_type_map.get(name, "").lower()
        try:
            if param_type == "int":
                return int(float(value))
            if param_type == "float":
                return float(value)
            if param_type == "bool":
                return bool(value)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return value
        return value

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

        for key, value in (self.base_config.fixed_params or {}).items():
            if value is None or key in params_dict:
                continue
            params_dict[key] = self._cast_param_value(key, value)

        params_dict.setdefault("riskPerTrade", float(self.base_config.risk_per_trade_pct))
        params_dict.setdefault("contractSize", float(self.base_config.contract_size))
        params_dict.setdefault("commissionRate", float(self.base_config.commission_rate))

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
        self._setup_worker_config()

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
            logger.info(f"Starting parallel optimization with n_jobs={self.n_jobs}")
            self.study.optimize(
                lambda trial: self._objective(trial, search_space),
                n_trials=n_trials,
                timeout=timeout,
                n_jobs=self.n_jobs,
                callbacks=callbacks or None,
                show_progress_bar=False,
            )
        except KeyboardInterrupt:
            logger.info("Optuna optimisation interrupted by user")
        finally:
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
