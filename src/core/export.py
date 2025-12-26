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
import re
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union, TYPE_CHECKING
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from .backtest_engine import TradeRecord
from .optuna_engine import OptimizationResult
import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .walkforward_engine import WFResult

__all__ = [
    "export_optuna_results",
    "export_trades_csv",
    "export_trades_zip",
    "export_wf_results_csv",
    "export_wfa_trades_history",
    "generate_wfa_output_filename",
    "_extract_symbol_from_csv_filename",
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
        ("SQN", None, "sqn", "optional_float"),
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


def _extract_file_prefix(csv_filename: str) -> str:
    """
    Extract file prefix (exchange, ticker, timeframe) from CSV filename.

    Examples:
        "OKX_LINKUSDT.P, 15 2025.02.01-2025.09.09.csv" -> "OKX_LINKUSDT.P, 15"
        "BINANCE_BTCUSDT, 1h.csv" -> "BINANCE_BTCUSDT, 1h"

    Returns original filename stem if date pattern not found.
    """
    name = Path(csv_filename).stem

    # Remove date pattern if exists (YYYY.MM.DD-YYYY.MM.DD or YYYY-MM-DD--YYYY-MM-DD)
    date_pattern = re.compile(r"\b\d{4}[.\-/]\d{2}[.\-/]\d{2}\b")
    match = date_pattern.search(name)
    if match:
        prefix = name[:match.start()].rstrip()
        return prefix if prefix else name

    return name


def _extract_symbol_from_csv_filename(csv_filename: str) -> str:
    """
    Extract trading symbol from CSV filename in format: EXCHANGE:TICKER

    Format: PREFIX_TICKER,...
    Example: "OKX_LINKUSDT.P, 15 2025.02.01-2025.09.09.csv" -> "OKX:LINKUSDT.P"

    Rules:
    - Prefix (exchange): everything before first "_"
    - Ticker: everything after first "_" until first ","

    Args:
        csv_filename: Name of the CSV file

    Returns:
        Symbol in format "EXCHANGE:TICKER" (e.g., "OKX:LINKUSDT.P")
    """
    name = Path(csv_filename).name

    if "_" not in name:
        return "UNKNOWN:UNKNOWN"

    prefix = name.split("_")[0]
    remainder = name.split("_", 1)[1]

    if "," in remainder:
        ticker = remainder.split(",")[0].strip()
    else:
        ticker = remainder.split()[0] if remainder.split() else "UNKNOWN"

    return f"{prefix}:{ticker}"


def generate_wfa_output_filename(
    csv_filename: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    include_trades: bool = False,
) -> str:
    """
    Generate filename for WFA results.

    Format: EXCHANGE_TICKER TF START-END_Optuna+WFA.csv
    Or:     EXCHANGE_TICKER TF START-END_Optuna+WFA_TRADES.zip

    Args:
        csv_filename: Input CSV filename
        start_date: Start date of analysis period
        end_date: End date of analysis period
        include_trades: If True, generate ZIP filename for trades export

    Returns:
        Formatted filename string

    Examples:
        >>> generate_wfa_output_filename("OKX_LINKUSDT.P, 15.csv", pd.Timestamp("2025-05-01"), pd.Timestamp("2025-09-01"))
        "OKX_LINKUSDT.P, 15 2025.05.01-2025.09.01_Optuna+WFA.csv"
        >>> generate_wfa_output_filename("OKX_LINKUSDT.P, 15.csv", pd.Timestamp("2025-05-01"), pd.Timestamp("2025-09-01"), True)
        "OKX_LINKUSDT.P, 15 2025.05.01-2025.09.01_Optuna+WFA_TRADES.zip"
    """
    prefix = _extract_file_prefix(csv_filename)
    if not prefix:
        prefix = "wfa"

    start_str = start_date.strftime("%Y.%m.%d")
    end_str = end_date.strftime("%Y.%m.%d")

    mode = "Optuna+WFA_TRADES" if include_trades else "Optuna+WFA"
    ext = "zip" if include_trades else "csv"

    return f"{prefix} {start_str}-{end_str}_{mode}.{ext}"


def _export_wfa_trades_to_csv(
    trades: List[TradeRecord],
    symbol: str,
    output_path: str,
) -> None:
    """
    Export trades to TradingView CSV format for WFA.

    Each trade generates TWO rows: entry and exit.

    Format:
        Symbol,Side,Qty,Fill Price,Closing Time
        OKX:LINKUSDT.P,Buy,10,16.30,2025-11-15 00:00:00   (entry)
        OKX:LINKUSDT.P,Sell,10,16.50,2025-11-15 01:00:00  (exit)

    Args:
        trades: List of TradeRecord objects
        symbol: Trading symbol (e.g., "OKX:LINKUSDT.P")
        output_path: Path to save CSV file
    """
    if not trades:
        df = pd.DataFrame(columns=["Symbol", "Side", "Qty", "Fill Price", "Closing Time"])
        df.to_csv(output_path, index=False, encoding="utf-8")
        return

    rows = []
    for trade in trades:
        qty = trade.size

        entry_side = "Buy" if trade.direction == "long" else "Sell"
        rows.append(
            {
                "Symbol": symbol,
                "Side": entry_side,
                "Qty": qty,
                "Fill Price": trade.entry_price,
                "Closing Time": trade.entry_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        exit_side = "Sell" if trade.direction == "long" else "Buy"
        rows.append(
            {
                "Symbol": symbol,
                "Side": exit_side,
                "Qty": qty,
                "Fill Price": trade.exit_price,
                "Closing Time": trade.exit_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8")


def export_wfa_trades_history(
    wf_result: "WFResult",
    df: pd.DataFrame,
    symbol: str,
    output_dir,
) -> List[str]:
    """
    Export trade history for each WFA window's best parameter set.

    This re-runs the strategy for each window on:
    1. IS period
    2. OOS period

    All trades for a window are combined into a single CSV per window,
    sorted by entry time.
    """
    from .backtest_engine import prepare_dataset_with_warmup
    from strategies import get_strategy

    strategy_id = getattr(wf_result, "strategy_id", "")
    if not strategy_id:
        strategy_id = getattr(getattr(wf_result, "config", None), "strategy_id", "")
    if not strategy_id:
        raise ValueError("Walk-forward result is missing strategy_id; cannot export trades.")
    try:
        strategy_class = get_strategy(strategy_id)
    except ValueError as exc:  # noqa: BLE001
        raise ValueError(f"Failed to load strategy '{strategy_id}': {exc}")

    warmup_bars = getattr(wf_result, "warmup_bars", 1000)

    trade_files: List[str] = []

    for window_result in wf_result.windows:
        all_trades = []

        is_df_prepared, is_trade_start_idx = prepare_dataset_with_warmup(
            df, window_result.is_start, window_result.is_end, warmup_bars
        )

        is_params = window_result.best_params.copy()
        is_params["dateFilter"] = True
        is_params["start"] = window_result.is_start
        is_params["end"] = window_result.is_end

        is_result = strategy_class.run(
            is_df_prepared, is_params, is_trade_start_idx
        )

        is_trades = [
            trade for trade in is_result.trades
            if window_result.is_start <= trade.entry_time <= window_result.is_end
        ]
        all_trades.extend(is_trades)

        oos_df_prepared, oos_trade_start_idx = prepare_dataset_with_warmup(
            df, window_result.oos_start, window_result.oos_end, warmup_bars
        )

        oos_params = window_result.best_params.copy()
        oos_params["dateFilter"] = True
        oos_params["start"] = window_result.oos_start
        oos_params["end"] = window_result.oos_end

        oos_result = strategy_class.run(
            oos_df_prepared, oos_params, oos_trade_start_idx
        )

        oos_trades = [
            trade for trade in oos_result.trades
            if window_result.oos_start <= trade.entry_time <= window_result.oos_end
        ]
        all_trades.extend(oos_trades)

        all_trades.sort(key=lambda t: t.entry_time)

        filename = f"window{window_result.window_id}_{window_result.param_id}.csv"
        filepath = Path(output_dir) / filename

        _export_wfa_trades_to_csv(all_trades, symbol, str(filepath))

        trade_files.append(filename)

    return trade_files


def export_wf_results_csv(result: "WFResult", df: Optional[pd.DataFrame] = None) -> str:
    """Export Walk-Forward results to CSV string."""
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")

    def format_ts(value: pd.Timestamp) -> str:
        if isinstance(value, pd.Timestamp):
            return value.strftime("%Y-%m-%d")
        return str(value)

    writer.writerow(["=== WALK-FORWARD ANALYSIS - RESULTS ==="])
    writer.writerow([])

    writer.writerow(["=== CONFIGURATION ==="])
    writer.writerow(["Strategy ID", result.strategy_id])
    writer.writerow(["IS Period (days)", result.config.is_period_days])
    writer.writerow(["OOS Period (days)", result.config.oos_period_days])
    writer.writerow(["Warmup Bars", result.warmup_bars])
    writer.writerow(["Trading Start", format_ts(result.trading_start_date)])
    writer.writerow(["Trading End", format_ts(result.trading_end_date)])
    writer.writerow(["Total Windows", result.total_windows])
    writer.writerow([])

    writer.writerow(["=== STITCHED OOS PERFORMANCE ==="])
    writer.writerow(["Final OOS Net Profit %", f"{result.stitched_oos.final_net_profit_pct:.2f}%"])
    writer.writerow(["Max Drawdown %", f"{result.stitched_oos.max_drawdown_pct:.2f}%"])
    writer.writerow(["Total Trades", result.stitched_oos.total_trades])
    writer.writerow(["WFE (Annualized)", f"{result.stitched_oos.wfe:.2f}%"])
    writer.writerow(["OOS Win Rate", f"{result.stitched_oos.oos_win_rate:.1f}%"])
    writer.writerow([])

    writer.writerow(["=== PER-WINDOW RESULTS ==="])
    writer.writerow(
        [
            "Window",
            "IS Start",
            "IS End",
            "OOS Start",
            "OOS End",
            "Param ID",
            "IS Net Profit %",
            "IS Max DD %",
            "IS Trades",
            "OOS Net Profit %",
            "OOS Max DD %",
            "OOS Trades",
        ]
    )

    for window_result in result.windows:
        writer.writerow(
            [
                window_result.window_id,
                format_ts(window_result.is_start),
                format_ts(window_result.is_end),
                format_ts(window_result.oos_start),
                format_ts(window_result.oos_end),
                window_result.param_id,
                f"{window_result.is_net_profit_pct:.2f}%",
                f"{window_result.is_max_drawdown_pct:.2f}%",
                window_result.is_total_trades,
                f"{window_result.oos_net_profit_pct:.2f}%",
                f"{window_result.oos_max_drawdown_pct:.2f}%",
                window_result.oos_total_trades,
            ]
        )

    writer.writerow([])

    writer.writerow(["=== WINDOW PARAMETERS ==="])
    writer.writerow([])

    try:
        from strategies import get_strategy_config

        config = get_strategy_config(result.strategy_id)
        param_definitions = config.get("parameters", {}) if isinstance(config, dict) else {}
    except Exception:
        param_definitions = {}

    ordered_param_names = list(param_definitions.keys()) if param_definitions else []

    for window_result in result.windows:
        writer.writerow([f"--- Window #{window_result.window_id}: {window_result.param_id} ---"])
        writer.writerow(["Parameter", "Value"])
        params = window_result.best_params
        if ordered_param_names:
            for param_name in ordered_param_names:
                param_spec = param_definitions.get(param_name)
                label = param_spec.get("label", param_name) if isinstance(param_spec, dict) else param_name
                value = params.get(param_name, "N/A")
                writer.writerow([label, value])
        else:
            for param_name, value in params.items():
                writer.writerow([param_name, value])

        writer.writerow([])
        writer.writerow(["Performance Metrics", ""])
        writer.writerow(["IS Net Profit %", f"{window_result.is_net_profit_pct:.2f}%"])
        writer.writerow(["IS Max DD %", f"{window_result.is_max_drawdown_pct:.2f}%"])
        writer.writerow(["IS Trades", window_result.is_total_trades])
        writer.writerow(["OOS Net Profit %", f"{window_result.oos_net_profit_pct:.2f}%"])
        writer.writerow(["OOS Max DD %", f"{window_result.oos_max_drawdown_pct:.2f}%"])
        writer.writerow(["OOS Trades", window_result.oos_total_trades])
        writer.writerow([])
        writer.writerow([])

    return output.getvalue()
