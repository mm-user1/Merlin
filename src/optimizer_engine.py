"""Optimization engine for S_01 TrailingMA grid search."""
from __future__ import annotations

import bisect
import itertools
import multiprocessing as mp
from dataclasses import dataclass
from decimal import Decimal
from typing import IO, Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

import pandas as pd
from tqdm import tqdm

from backtest_engine import DEFAULT_ATR_PERIOD, load_data

# Constants
CHUNK_SIZE = 2000

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


@dataclass
class OptimizationConfig:
    """Configuration received from the optimizer form."""

    csv_file: IO[Any]
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
    score_config: Optional[Dict[str, Any]] = None

    strategy_id: str = "s01_trailing_ma"
    warmup_bars: int = 1000
    filter_min_profit: bool = False
    min_profit_threshold: float = 0.0
    optimization_mode: str = "grid"


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


def _generate_numeric_sequence(
    start: float, stop: float, step: float, is_int: bool
) -> List[Any]:
    if step == 0:
        raise ValueError("Step must be non-zero for optimization ranges.")
    delta = abs(step)
    step_value = delta if start <= stop else -delta
    decimals = max(0, -Decimal(str(step)).normalize().as_tuple().exponent)
    epsilon = delta * 1e-9

    values: List[Any] = []
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

INTERNAL_TO_FRONTEND_MAP: Dict[str, str] = {
    internal: frontend for frontend, (internal, _) in PARAMETER_MAP.items()
}
INTERNAL_TO_FRONTEND_MAP.update(
    {
        "ma_type": "maType",
        "trail_ma_long_type": "trailLongType",
        "trail_ma_short_type": "trailShortType",
    }
)


def generate_parameter_grid(config: OptimizationConfig) -> List[Dict[str, Any]]:
    """Generate the cartesian product of all parameter combinations."""

    if not config.ma_types_trend or not config.ma_types_trail_long or not config.ma_types_trail_short:
        raise ValueError("At least one MA type must be selected in each group.")

    param_values: Dict[str, List[Any]] = {}
    for frontend_name, (internal_name, is_int) in PARAMETER_MAP.items():
        enabled = bool(config.enabled_params.get(frontend_name, False))
        if enabled:
            if frontend_name not in config.param_ranges:
                raise ValueError(f"Missing range for parameter '{frontend_name}'.")
            start, stop, step = config.param_ranges[frontend_name]
            values = _generate_numeric_sequence(start, stop, step, is_int)
        else:
            if frontend_name not in config.fixed_params:
                raise ValueError(f"Missing fixed value for parameter '{frontend_name}'.")
            value = config.fixed_params[frontend_name]
            values = [int(value) if is_int else float(value)]
        param_values[internal_name] = values

    trend_types = [ma.upper() for ma in config.ma_types_trend]
    trail_long_types = [ma.upper() for ma in config.ma_types_trail_long]
    trail_short_types = [ma.upper() for ma in config.ma_types_trail_short]

    param_names = list(param_values.keys())
    param_lists = [param_values[name] for name in param_names]

    combinations: List[Dict[str, Any]] = []

    if config.lock_trail_types:
        trail_short_set = set(trail_short_types)
        paired_trail_types = [trail for trail in trail_long_types if trail in trail_short_set]
        if not paired_trail_types:
            raise ValueError(
                "No overlapping trail MA types available when lock_trail_types is enabled."
            )

        for ma_type in trend_types:
            for paired_type in paired_trail_types:
                for values in itertools.product(*param_lists):
                    combo = dict(zip(param_names, values))
                    combo.update(
                        {
                            "ma_type": ma_type,
                            "trail_ma_long_type": paired_type,
                            "trail_ma_short_type": paired_type,
                        }
                    )
                    combinations.append(combo)
    else:
        for ma_type, trail_long_type, trail_short_type in itertools.product(
            trend_types, trail_long_types, trail_short_types
        ):
            for values in itertools.product(*param_lists):
                combo = dict(zip(param_names, values))
                combo.update(
                    {
                        "ma_type": ma_type,
                        "trail_ma_long_type": trail_long_type,
                        "trail_ma_short_type": trail_short_type,
                    }
                )
                combinations.append(combo)
    return combinations


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




def _run_single_combination(args: Tuple[Dict[str, Any], pd.DataFrame, int, Any]) -> OptimizationResult:
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
        opt_result = _base_result()
        opt_result.net_profit_pct = result.net_profit_pct
        opt_result.max_drawdown_pct = result.max_drawdown_pct
        opt_result.total_trades = result.total_trades
        opt_result.sharpe_ratio = result.sharpe_ratio
        opt_result.profit_factor = result.profit_factor
        opt_result.romad = result.romad
        opt_result.ulcer_index = result.ulcer_index
        opt_result.recovery_factor = result.recovery_factor
        opt_result.consistency_score = result.consistency_score
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




def run_grid_optimization(config: OptimizationConfig) -> List[OptimizationResult]:
    """Execute the grid search optimization using modular strategy system."""

    from strategies import get_strategy

    try:
        strategy_class = get_strategy(config.strategy_id)
    except ValueError as e:
        raise ValueError(f"Failed to load strategy '{config.strategy_id}': {e}")

    df = load_data(config.csv_file)
    combinations = generate_parameter_grid(config)
    total = len(combinations)
    if total == 0:
        raise ValueError("No parameter combinations generated for optimization.")

    use_date_filter = bool(config.fixed_params.get("dateFilter", False))
    start_ts = _parse_timestamp(config.fixed_params.get("start"))
    end_ts = _parse_timestamp(config.fixed_params.get("end"))

    trade_start_idx = 0
    if use_date_filter and (start_ts is not None or end_ts is not None):
        from backtest_engine import prepare_dataset_with_warmup

        try:
            df, trade_start_idx = prepare_dataset_with_warmup(
                df, start_ts, end_ts, config.warmup_bars
            )
        except Exception as exc:
            raise ValueError(f"Failed to prepare dataset with warmup: {exc}")

    worker_args = [
        (combo, df, trade_start_idx, strategy_class)
        for combo in combinations
    ]

    results: List[OptimizationResult] = []
    processes = min(32, max(1, int(config.worker_processes)))

    with mp.Pool(processes=processes) as pool:
        progress_iter = tqdm(
            pool.imap_unordered(_run_single_combination, worker_args, chunksize=CHUNK_SIZE),
            desc="Optimizing",
            total=total,
            unit="combo",
        )
        for result in progress_iter:
            results.append(result)

    score_config = config.score_config or DEFAULT_SCORE_CONFIG
    results = calculate_score(results, score_config)

    if config.filter_min_profit:
        threshold = float(config.min_profit_threshold)
        results = [item for item in results if float(item.net_profit_pct) >= threshold]

    results.sort(key=lambda item: item.net_profit_pct, reverse=True)
    return results


def run_optimization(config: OptimizationConfig) -> List[OptimizationResult]:
    """Router that delegates to grid or Optuna optimization engines."""

    mode = getattr(config, "optimization_mode", "grid")
    if mode == "optuna":
        from optuna_engine import OptunaConfig, run_optuna_optimization

        optuna_config = OptunaConfig(
            target=getattr(config, "optuna_target", "score"),
            budget_mode=getattr(config, "optuna_budget_mode", "trials"),
            n_trials=int(getattr(config, "optuna_n_trials", 500) or 500),
            time_limit=int(getattr(config, "optuna_time_limit", 3600) or 3600),
            convergence_patience=int(
                getattr(config, "optuna_convergence", 50) or 50
            ),
            enable_pruning=bool(getattr(config, "optuna_enable_pruning", True)),
            sampler=getattr(config, "optuna_sampler", "tpe"),
            pruner=getattr(config, "optuna_pruner", "median"),
            warmup_trials=int(
                getattr(config, "optuna_warmup_trials", 20) or 20
            ),
            save_study=bool(getattr(config, "optuna_save_study", False)),
            study_name=getattr(config, "optuna_study_name", None),
        )

        return run_optuna_optimization(config, optuna_config)

    return run_grid_optimization(config)


CSV_COLUMN_SPECS: List[Tuple[str, Optional[str], str, Optional[str]]] = [
    ("MA Type", "maType", "ma_type", None),
    ("MA Length", "maLength", "ma_length", None),
    ("CC L", "closeCountLong", "close_count_long", None),
    ("CC S", "closeCountShort", "close_count_short", None),
    ("St L X", "stopLongX", "stop_long_atr", "float1"),
    ("Stop Long RR", "stopLongRR", "stop_long_rr", "float1"),
    ("St L LP", "stopLongLP", "stop_long_lp", None),
    ("St S X", "stopShortX", "stop_short_atr", "float1"),
    ("Stop Short RR", "stopShortRR", "stop_short_rr", "float1"),
    ("St S LP", "stopShortLP", "stop_short_lp", None),
    ("St L Max %", "stopLongMaxPct", "stop_long_max_pct", "float1"),
    ("St S Max %", "stopShortMaxPct", "stop_short_max_pct", "float1"),
    ("St L Max D", "stopLongMaxDays", "stop_long_max_days", None),
    ("St S Max D", "stopShortMaxDays", "stop_short_max_days", None),
    ("Trail RR Long", "trailRRLong", "trail_rr_long", "float1"),
    ("Trail RR Short", "trailRRShort", "trail_rr_short", "float1"),
    ("Tr L Type", "trailLongType", "trail_ma_long_type", None),
    ("Tr L Len", "trailLongLength", "trail_ma_long_length", None),
    ("Tr L Off", "trailLongOffset", "trail_ma_long_offset", "float1"),
    ("Tr S Type", "trailShortType", "trail_ma_short_type", None),
    ("Tr S Len", "trailShortLength", "trail_ma_short_length", None),
    ("Tr S Off", "trailShortOffset", "trail_ma_short_offset", "float1"),
    ("Net Profit%", None, "net_profit_pct", "percent"),
    ("Max DD%", None, "max_drawdown_pct", "percent"),
    ("Trades", None, "total_trades", None),
    ("Score", None, "score", "float"),
    ("RoMaD", None, "romad", "optional_float"),
    ("Sharpe", None, "sharpe_ratio", "optional_float"),
    ("PF", None, "profit_factor", "optional_float"),
    ("Ulcer", None, "ulcer_index", "optional_float"),
    ("Recover", None, "recovery_factor", "optional_float"),
    ("Consist", None, "consistency_score", "optional_float"),
]


def _format_csv_value(value: Any, formatter: Optional[str]) -> str:
    if formatter == "percent":
        return f"{float(value):.2f}%"
    if formatter == "float":
        return f"{float(value):.2f}"
    if formatter == "float1":
        return f"{float(value):.1f}"
    if formatter == "optional_float":
        if value is None:
            return ""
        return f"{float(value):.2f}"
    return str(value)


def _format_fixed_param_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def export_to_csv(
    results: List[OptimizationResult],
    fixed_params: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]],
    *,
    filter_min_profit: bool = False,
    min_profit_threshold: float = 0.0,
    optimization_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Export results to CSV format string with fixed parameter metadata.

    When ``filter_min_profit`` is enabled, rows whose ``net_profit_pct`` is
    strictly below ``min_profit_threshold`` are omitted from the export. The
    optimisation itself remains unaffected.
    """

    import io

    output = io.StringIO()

    if isinstance(fixed_params, Mapping):
        fixed_items = list(fixed_params.items())
    else:
        fixed_items = list(fixed_params)
    fixed_lookup = {name: value for name, value in fixed_items}

    if optimization_metadata:
        output.write("Optuna Metadata\n")
        output.write(f"Method,{optimization_metadata.get('method', 'Grid Search')}\n")
        if optimization_metadata.get("method") == "Optuna":
            output.write(
                f"Target,{optimization_metadata.get('target', 'Composite Score')}\n"
            )
            output.write(
                f"Total Trials,{optimization_metadata.get('total_trials', 0)}\n"
            )
            output.write(
                f"Completed Trials,{optimization_metadata.get('completed_trials', 0)}\n"
            )
            output.write(
                f"Pruned Trials,{optimization_metadata.get('pruned_trials', 0)}\n"
            )
            output.write(
                f"Best Trial Number,{optimization_metadata.get('best_trial_number', 0)}\n"
            )
            output.write(
                f"Best Value,{optimization_metadata.get('best_value', 0)}\n"
            )
            output.write(
                f"Optimization Time,{optimization_metadata.get('optimization_time', '-')}\n"
            )
        else:
            output.write(
                f"Total Combinations,{optimization_metadata.get('total_combinations', 0)}\n"
            )
            output.write(
                f"Optimization Time,{optimization_metadata.get('optimization_time', '-')}\n"
            )
        output.write("\n")

    output.write("Fixed Parameters\n")
    output.write("Parameter Name,Value\n")
    for name, value in fixed_items:
        formatted_value = _format_fixed_param_value(value)
        output.write(f"{name},{formatted_value}\n")
    output.write("\n")

    filtered_columns = [
        spec for spec in CSV_COLUMN_SPECS if spec[1] is None or spec[1] not in fixed_lookup
    ]

    header_line = ",".join(column[0] for column in filtered_columns)
    output.write(header_line + "\n")

    if filter_min_profit:
        threshold = float(min_profit_threshold)
        filtered_results = [
            item for item in results if float(item.net_profit_pct) >= threshold
        ]
    else:
        filtered_results = results

    for item in filtered_results:
        row_values = []
        for _, frontend_name, attr_name, formatter in filtered_columns:
            value = getattr(item, attr_name)
            row_values.append(_format_csv_value(value, formatter))
        output.write(",".join(row_values) + "\n")

    return output.getvalue()
