"""Optuna-based Bayesian optimization engine for S_01 TrailingMA."""
from __future__ import annotations

import bisect
import logging
import multiprocessing as mp
import tempfile
import time
from dataclasses import asdict, dataclass, fields
from decimal import Decimal
from pathlib import Path
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


# ---------------------------------------------------------------------------
# Multi-process helpers (module-level for pickling)
# ---------------------------------------------------------------------------


def _trial_set_result_attrs(
    trial: optuna.Trial,
    result: OptimizationResult,
    objective_value: float,
    target: str,
) -> None:
    """
    Persist key metrics into trial.user_attrs for cross-process aggregation.
    """
    trial.set_user_attr("merlin.params", dict(result.params))
    trial.set_user_attr("merlin.net_profit_pct", float(result.net_profit_pct))
    trial.set_user_attr("merlin.max_drawdown_pct", float(result.max_drawdown_pct))
    trial.set_user_attr("merlin.total_trades", int(result.total_trades))
    trial.set_user_attr("merlin.objective_value", float(objective_value))
    trial.set_user_attr("merlin.target", str(target))

    if result.romad is not None:
        trial.set_user_attr("merlin.romad", float(result.romad))
    if result.sharpe_ratio is not None:
        trial.set_user_attr("merlin.sharpe_ratio", float(result.sharpe_ratio))
    if result.profit_factor is not None:
        trial.set_user_attr("merlin.profit_factor", float(result.profit_factor))
    if result.ulcer_index is not None:
        trial.set_user_attr("merlin.ulcer_index", float(result.ulcer_index))
    if result.recovery_factor is not None:
        trial.set_user_attr("merlin.recovery_factor", float(result.recovery_factor))
    if result.consistency_score is not None:
        trial.set_user_attr("merlin.consistency_score", float(result.consistency_score))


def _result_from_trial(trial: optuna.trial.FrozenTrial) -> OptimizationResult:
    """
    Rebuild OptimizationResult from persisted user_attrs.
    """
    attrs = trial.user_attrs
    result = OptimizationResult(
        params=dict(attrs.get("merlin.params") or trial.params),
        net_profit_pct=float(attrs.get("merlin.net_profit_pct", 0.0)),
        max_drawdown_pct=float(attrs.get("merlin.max_drawdown_pct", 0.0)),
        total_trades=int(attrs.get("merlin.total_trades", 0)),
        romad=attrs.get("merlin.romad"),
        sharpe_ratio=attrs.get("merlin.sharpe_ratio"),
        profit_factor=attrs.get("merlin.profit_factor"),
        ulcer_index=attrs.get("merlin.ulcer_index"),
        recovery_factor=attrs.get("merlin.recovery_factor"),
        consistency_score=attrs.get("merlin.consistency_score"),
        score=0.0,
    )
    setattr(result, "optuna_trial_number", trial.number)
    setattr(result, "optuna_value", trial.value)
    return result


def _materialize_csv_to_temp(csv_source: Any) -> Tuple[str, bool]:
    """
    Ensure CSV source is a file path string usable by worker processes.

    Returns (path_string, needs_cleanup)
    """
    if isinstance(csv_source, (str, Path)):
        return str(csv_source), False

    if hasattr(csv_source, "name") and csv_source.name:
        possible_path = Path(csv_source.name)
        if possible_path.exists() and possible_path.is_file():
            return str(possible_path), False

    if hasattr(csv_source, "read"):
        if hasattr(csv_source, "seek"):
            try:
                csv_source.seek(0)
            except Exception:
                pass

        content = csv_source.read()
        if isinstance(content, str):
            content = content.encode("utf-8")

        temp_dir = Path(tempfile.gettempdir()) / "merlin_optuna_csv"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / f"optimization_{int(time.time())}_{id(csv_source)}.csv"
        Path(temp_path).write_bytes(content)
        logger.info("Materialized CSV to temp file: %s", temp_path)
        return str(temp_path), True

    return str(csv_source), False


def _worker_process_entry(
    study_name: str,
    storage_path: str,
    base_config_dict: Dict[str, Any],
    optuna_config_dict: Dict[str, Any],
    n_trials: Optional[int],
    timeout: Optional[int],
    worker_id: int,
) -> None:
    """
    Entry point for multi-process Optuna workers.
    """
    from optuna.storages import JournalStorage
    from optuna.storages.journal import JournalFileBackend, JournalFileOpenLock
    from optuna.study import MaxTrialsCallback

    worker_logger = logging.getLogger(__name__)
    worker_logger.info("Worker %s starting (pid=%s)", worker_id, mp.current_process().pid)

    try:
        base_config = OptimizationConfig(**base_config_dict)
        optuna_config = OptunaConfig(**optuna_config_dict)

        optimizer = OptunaOptimizer(base_config, optuna_config)
        optimizer._prepare_data_and_strategy()
        optimizer.pruner = optimizer._create_pruner()
        worker_sampler = optimizer._create_sampler()

        storage = JournalStorage(
            JournalFileBackend(storage_path, lock_obj=JournalFileOpenLock(storage_path))
        )
        study = optuna.load_study(
            study_name=study_name,
            storage=storage,
            sampler=worker_sampler,
            pruner=optimizer.pruner,
        )
        search_space = optimizer._build_search_space()

        def worker_objective(trial: optuna.Trial) -> float:
            return optimizer._objective_for_worker(trial, search_space)

        callbacks = []
        if n_trials is not None:
            callbacks.append(MaxTrialsCallback(n_trials, states=None))

        worker_logger.info(
            "Worker %s running optimise (n_trials=%s, timeout=%s)", worker_id, n_trials, timeout
        )
        study.optimize(
            worker_objective,
            n_trials=None,
            timeout=timeout,
            callbacks=callbacks or None,
            show_progress_bar=False,
            n_jobs=1,
        )
        worker_logger.info("Worker %s finished", worker_id)
    except Exception as exc:  # pragma: no cover - defensive
        worker_logger.error("Worker %s failed: %s", worker_id, exc, exc_info=True)
        raise


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
        self.df: Optional[pd.DataFrame] = None
        self.trade_start_idx: int = 0
        self.strategy_class: Optional[Any] = None
        self.trial_results: List[OptimizationResult] = []
        self.best_value: float = float("-inf")
        self.trials_without_improvement: int = 0
        self.start_time: Optional[float] = None
        self.pruned_trials: int = 0
        self.study: Optional[optuna.Study] = None
        self.pruner: Optional[optuna.pruners.BasePruner] = None
        self.param_type_map: Dict[str, str] = {}
        self._multiprocess_mode: bool = False

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
    # Data preparation (shared by single and multi process)
    # ------------------------------------------------------------------
    def _prepare_data_and_strategy(self) -> None:
        """Load strategy class and data, apply optional date filtering."""

        from strategies import get_strategy
        from .backtest_engine import prepare_dataset_with_warmup

        try:
            strategy_class = get_strategy(self.base_config.strategy_id)
        except ValueError as exc:
            raise ValueError(f"Failed to load strategy '{self.base_config.strategy_id}': {exc}")

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

    # ------------------------------------------------------------------
    # Objective evaluation
    # ------------------------------------------------------------------
    def _evaluate_parameters(self, params_dict: Dict[str, Any]) -> OptimizationResult:
        if self.df is None or self.strategy_class is None:
            raise RuntimeError("Data and strategy must be prepared before evaluation.")

        args = (params_dict, self.df, self.trade_start_idx, self.strategy_class)
        return _run_single_combination(args)

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
        _trial_set_result_attrs(trial, result, objective_value, self.optuna_config.target)

        if objective_value > self.best_value:
            self.best_value = objective_value
            self.trials_without_improvement = 0
        else:
            self.trials_without_improvement += 1

        return objective_value

    def _objective_for_worker(
        self, trial: optuna.Trial, search_space: Dict[str, Dict[str, Any]]
    ) -> float:
        """
        Objective used inside worker processes (no shared state).
        """
        params_dict = self._prepare_trial_parameters(trial, search_space)
        result = self._evaluate_parameters(params_dict)

        if self.base_config.filter_min_profit and (
            result.net_profit_pct < float(self.base_config.min_profit_threshold)
        ):
            raise optuna.TrialPruned("Below minimum profit threshold")

        if self.optuna_config.target == "score":
            objective_value = float(result.romad or 0.0)
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

        if self.pruner is not None:
            trial.report(objective_value, step=0)
            if trial.should_prune():
                raise optuna.TrialPruned("Pruned by Optuna")

        _trial_set_result_attrs(trial, result, objective_value, self.optuna_config.target)
        return objective_value

    # ------------------------------------------------------------------
    # Main execution entrypoint
    # ------------------------------------------------------------------
    def optimize(self) -> List[OptimizationResult]:
        workers = max(1, int(getattr(self.base_config, "worker_processes", 1) or 1))
        if workers <= 1:
            return self._optimize_single_process()
        return self._optimize_multiprocess(workers)

    def _optimize_single_process(self) -> List[OptimizationResult]:
        logger.info(
            "Starting single-process Optuna optimisation: target=%s, budget_mode=%s",
            self.optuna_config.target,
            self.optuna_config.budget_mode,
        )

        self._multiprocess_mode = False
        self.start_time = time.time()
        self.trial_results = []
        self.best_value = float("-inf")
        self.trials_without_improvement = 0
        self.pruned_trials = 0

        search_space = self._build_search_space()
        self._prepare_data_and_strategy()

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
            self.pruner = None

        return self._finalize_results()

    def _optimize_multiprocess(self, n_workers: int) -> List[OptimizationResult]:
        logger.info(
            "Starting multi-process Optuna optimisation: target=%s, budget_mode=%s, workers=%s",
            self.optuna_config.target,
            self.optuna_config.budget_mode,
            n_workers,
        )

        self._multiprocess_mode = True
        self.start_time = time.time()
        self.trial_results = []
        self.pruned_trials = 0
        self.best_value = float("-inf")
        self.trials_without_improvement = 0

        # Build search space to validate config early
        self._build_search_space()

        csv_path, csv_cleanup = _materialize_csv_to_temp(self.base_config.csv_file)
        base_config_dict = {
            f.name: (csv_path if f.name == "csv_file" else getattr(self.base_config, f.name))
            for f in fields(self.base_config)
        }
        optuna_config_dict = asdict(self.optuna_config)

        from optuna.storages import JournalStorage
        from optuna.storages.journal import JournalFileBackend, JournalFileOpenLock

        journal_dir = Path(tempfile.gettempdir()) / "merlin_optuna_journals"
        journal_dir.mkdir(exist_ok=True)
        timestamp = int(time.time())
        study_name = self.optuna_config.study_name or f"strategy_opt_{timestamp}"
        storage_path = str(journal_dir / f"{study_name}_{timestamp}.journal.log")

        storage = JournalStorage(
            JournalFileBackend(storage_path, lock_obj=JournalFileOpenLock(storage_path))
        )

        sampler = self._create_sampler()
        self.pruner = self._create_pruner()

        self.study = optuna.create_study(
            study_name=study_name,
            direction="maximize",
            sampler=sampler,
            pruner=self.pruner,
            storage=storage,
            load_if_exists=True,
        )

        timeout: Optional[int] = None
        n_trials: Optional[int] = None

        if self.optuna_config.budget_mode == "time":
            timeout = max(60, int(self.optuna_config.time_limit))
            logger.info("Time budget per study: %ss", timeout)
        elif self.optuna_config.budget_mode == "trials":
            n_trials = max(1, int(self.optuna_config.n_trials))
            logger.info("Global trial budget: %s", n_trials)
        elif self.optuna_config.budget_mode == "convergence":
            logger.warning(
                "Convergence budget is not fully supported in multi-process mode; "
                "using trial cap of 10000."
            )
            n_trials = 10000

        processes: List[mp.Process] = []

        try:
            for worker_id in range(n_workers):
                proc = mp.Process(
                    target=_worker_process_entry,
                    args=(
                        study_name,
                        storage_path,
                        base_config_dict,
                        optuna_config_dict,
                        n_trials,
                        timeout,
                        worker_id,
                    ),
                    name=f"OptunaWorker-{worker_id}",
                )
                proc.start()
                processes.append(proc)
                logger.info("Started worker %s (pid=%s)", worker_id, proc.pid)

            logger.info("Waiting for %s workers to finish...", n_workers)
            for worker_id, proc in enumerate(processes):
                proc.join()
                if proc.exitcode == 0:
                    logger.info("Worker %s completed successfully", worker_id)
                else:
                    logger.error("Worker %s exited with code %s", worker_id, proc.exitcode)

        except KeyboardInterrupt:
            logger.info("Optimisation interrupted; terminating workers...")
            for proc in processes:
                if proc.is_alive():
                    proc.terminate()
            for proc in processes:
                proc.join(timeout=5)

        # Reload study to gather results from storage
        self.study = optuna.load_study(study_name=study_name, storage=storage)

        self.trial_results = []
        for trial in self.study.trials:
            if trial.state == TrialState.COMPLETE:
                try:
                    self.trial_results.append(_result_from_trial(trial))
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Failed to rebuild trial %s: %s", trial.number, exc)

        results = self._finalize_results()

        # Cleanup temp CSV and storage if not persisted (after finalization)
        if csv_cleanup:
            try:
                Path(csv_path).unlink(missing_ok=True)
            except Exception:
                logger.debug("Failed to cleanup temp CSV %s", csv_path)

        if not self.optuna_config.save_study:
            try:
                Path(storage_path).unlink(missing_ok=True)
            except Exception:
                logger.debug("Failed to cleanup journal file %s", storage_path)

        self.pruner = None

        return results

    def _finalize_results(self) -> List[OptimizationResult]:
        end_time = time.time()
        optimisation_time = end_time - (self.start_time or end_time)

        logger.info(
            "Optuna optimisation completed: trials=%s, time=%.1fs",
            len(self.study.trials) if self.study else len(self.trial_results),
            optimisation_time,
        )

        score_config = self.base_config.score_config or DEFAULT_SCORE_CONFIG
        self.trial_results = calculate_score(self.trial_results, score_config)

        if self.study:
            completed_trials = sum(1 for trial in self.study.trials if trial.state == TrialState.COMPLETE)
            pruned_trials = sum(1 for trial in self.study.trials if trial.state == TrialState.PRUNED)
            total_trials = len(self.study.trials)
            best_trial_number = self.study.best_trial.number if self.study.best_trial else None
            if self.optuna_config.target == "score" and self.trial_results:
                best_result = max(self.trial_results, key=lambda r: float(r.score))
                best_value = float(best_result.score)
                best_trial_number = getattr(best_result, "optuna_trial_number", best_trial_number)
            else:
                best_value = self.study.best_value if completed_trials else None
        else:
            completed_trials = len(self.trial_results)
            pruned_trials = self.pruned_trials
            total_trials = completed_trials + pruned_trials
            best_trial_number = None
            best_value = None

        summary = {
            "method": "Optuna",
            "target": self.optuna_config.target,
            "budget_mode": self.optuna_config.budget_mode,
            "total_trials": total_trials,
            "completed_trials": completed_trials,
            "pruned_trials": pruned_trials,
            "best_trial_number": best_trial_number,
            "best_value": best_value,
            "optimization_time_seconds": optimisation_time,
            "multiprocess_mode": self._multiprocess_mode,
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
