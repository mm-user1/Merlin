"""
Centralized export utilities for the TrailingMA platform.

Provides pure data-to-string/bytes transformation helpers for:
- Optuna optimization results
- Walk-Forward Analysis summaries (stubbed)
- Trade history exports (CSV and ZIP)

The functions in this module do not perform any calculations; they only
format existing data structures into the expected output formats.
"""

from __future__ import annotations

import csv
import json
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from .backtest_engine import TradeRecord
from .optuna_engine import OptimizationResult
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "export_optuna_results",
    "export_trades_csv",
    "export_trades_zip",
]


def _format_csv_value(value: Any, formatter: Optional[str]) -> str:
    """Format a single value for CSV output."""

    if value in (None, ""):
        return ""
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
    """Format a fixed parameter value for the parameter block."""

    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def _get_formatter(param_type: str) -> Optional[str]:
    """Map parameter type to CSV formatter string."""

    if param_type == "int":
        return None
    if param_type == "float":
        return "float1"
    if param_type in {"select", "options", "bool"}:
        return None
    return None


def _build_column_specs_for_strategy(
    strategy_id: str,
) -> List[Tuple[str, Optional[str], str, Optional[str]]]:
    """Build CSV column specifications dynamically from strategy config."""

    from strategies import get_strategy_config

    try:
        config = get_strategy_config(strategy_id)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning(f"Could not load config for {strategy_id}: {exc}")
        return _get_default_metric_columns()

    parameters = config.get("parameters", {})
    if not isinstance(parameters, dict):
        logger.warning(f"Invalid parameters in config for {strategy_id}")
        return _get_default_metric_columns()

    specs: List[Tuple[str, Optional[str], str, Optional[str]]] = []

    for param_name, param_spec in parameters.items():
        if not isinstance(param_spec, dict):
            continue

        param_type = str(param_spec.get("type", "float")).lower()
        label = param_spec.get("label", param_name)
        formatter = _get_formatter(param_type)

        specs.append((label, param_name, param_name, formatter))

    specs.extend(_get_metric_columns())
    return specs


def _get_metric_columns() -> List[Tuple[str, Optional[str], str, Optional[str]]]:
    """Return universal metric column specifications."""

    return [
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


def _get_default_metric_columns() -> List[Tuple[str, Optional[str], str, Optional[str]]]:
    """Fallback columns when strategy config is unavailable."""

    return _get_metric_columns()


def export_optuna_results(
    results: List[OptimizationResult],
    fixed_params: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]],
    *,
    filter_min_profit: bool = False,
    min_profit_threshold: float = 0.0,
    optimization_metadata: Optional[Dict[str, Any]] = None,
    strategy_id: str = "s01_trailing_ma",
) -> str:
    """
    Export Optuna optimization results to CSV format string.

    The CSV has three sections:
    1. Optuna Metadata (optional) - optimization method, trials, best value, etc.
    2. Fixed Parameters - parameters that were NOT varied during optimization
    3. Results Table - one row per trial with varied params + metrics

    Args:
        results: List of OptimizationResult objects
        fixed_params: Parameters that were held constant (excluded from results table)
        filter_min_profit: If True, filter out results below threshold
        min_profit_threshold: Minimum net_profit_pct to include (if filtering enabled)
        optimization_metadata: Dict with optimization details (method, trials, time, etc.)

    Returns:
        CSV content as string
    """

    output = StringIO()

    if isinstance(fixed_params, Mapping):
        fixed_items = list(fixed_params.items())
    else:
        fixed_items = list(fixed_params)
    fixed_lookup = {name: value for name, value in fixed_items}

    if optimization_metadata:
        output.write("Optuna Metadata\n")
        output.write(f"Method,{optimization_metadata.get('method', 'Optuna')}\n")

        if optimization_metadata.get("method") == "Optuna":
            output.write(f"Target,{optimization_metadata.get('target', 'Composite Score')}\n")
            output.write(f"Total Trials,{optimization_metadata.get('total_trials', 0)}\n")
            output.write(f"Completed Trials,{optimization_metadata.get('completed_trials', 0)}\n")
            output.write(f"Pruned Trials,{optimization_metadata.get('pruned_trials', 0)}\n")
            output.write(f"Best Trial Number,{optimization_metadata.get('best_trial_number', 0)}\n")
            output.write(f"Best Value,{optimization_metadata.get('best_value', 0)}\n")
            output.write(f"Optimization Time,{optimization_metadata.get('optimization_time', '-')}\n")
        else:
            output.write(f"Total Combinations,{optimization_metadata.get('total_combinations', 0)}\n")
            output.write(f"Optimization Time,{optimization_metadata.get('optimization_time', '-')}\n")

        output.write("\n")

    output.write("Fixed Parameters\n")
    output.write("Parameter Name,Value\n")
    for name, value in fixed_items:
        formatted_value = _format_fixed_param_value(value)
        output.write(f"{name},{formatted_value}\n")
    output.write("\n")

    column_specs = _build_column_specs_for_strategy(strategy_id)

    filtered_columns = [
        spec for spec in column_specs if spec[1] is None or spec[1] not in fixed_lookup
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
            params_dict = getattr(item, "params", {}) or {}
            if frontend_name is not None and frontend_name in params_dict:
                value = params_dict.get(frontend_name)
            else:
                value = getattr(item, attr_name, "")
            row_values.append(_format_csv_value(value, formatter))
        output.write(",".join(row_values) + "\n")

    return output.getvalue()


def export_trades_csv(
    trades: List[TradeRecord],
    path: Optional[str] = None,
    *,
    symbol: str = "LINKUSDT",
) -> str:
    """Export trade history to TradingView-compatible CSV format.

    Args:
        trades: List of TradeRecord objects
        path: Optional file path to write CSV (if None, just return string)
        symbol: Trading symbol used for all rows

    Returns:
        CSV content as string
    """

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "Symbol",
            "Type",
            "Entry Time",
            "Entry Price",
            "Exit Time",
            "Exit Price",
            "Profit",
            "Profit %",
            "Size",
        ]
    )

    for trade in trades:
        direction_raw = trade.direction or trade.side or "long"
        direction = "Short" if str(direction_raw).lower() == "short" else "Long"
        entry_time = trade.entry_time.strftime("%Y-%m-%d %H:%M:%S") if trade.entry_time else ""
        exit_time = trade.exit_time.strftime("%Y-%m-%d %H:%M:%S") if trade.exit_time else ""
        entry_price = 0.0 if trade.entry_price is None else float(trade.entry_price)
        exit_price = 0.0 if trade.exit_price is None else float(trade.exit_price)
        profit_value = 0.0 if trade.net_pnl is None else float(trade.net_pnl)
        profit_pct_value = 0.0 if trade.profit_pct is None else float(trade.profit_pct)
        size_value = 0.0 if trade.size is None else float(trade.size)

        writer.writerow(
            [
                symbol,
                direction,
                entry_time,
                f"{entry_price:.2f}",
                exit_time,
                f"{exit_price:.2f}",
                f"{profit_value:.2f}",
                f"{profit_pct_value:.2f}%",
                f"{size_value:.2f}",
            ]
        )

    csv_content = output.getvalue()

    if path:
        Path(path).write_text(csv_content, encoding="utf-8")

    return csv_content


def export_trades_zip(
    trades: List[TradeRecord],
    metrics: Dict[str, Any],
    path: Optional[str] = None,
) -> bytes:
    """Export trades and summary metrics as a ZIP archive containing CSV and JSON."""

    zip_buffer = BytesIO()

    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as zipf:
        trades_csv = export_trades_csv(trades)
        zipf.writestr("trades.csv", trades_csv)

        summary = {
            "metrics": metrics or {},
            "total_trades": len(trades),
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        }
        zipf.writestr("summary.json", json.dumps(summary, indent=2))

    zip_content = zip_buffer.getvalue()

    if path:
        Path(path).write_bytes(zip_content)

    return zip_content
