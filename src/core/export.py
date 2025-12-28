"""
Centralized export utilities for the TrailingMA platform.

Provides pure data-to-string/bytes transformation helpers for trade exports.

The functions in this module do not perform any calculations; they only
format existing data structures into the expected output formats.
"""

from __future__ import annotations

import csv
import json
import re
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from .backtest_engine import TradeRecord
import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .walkforward_engine import WFResult

__all__ = [
    "export_trades_csv",
    "export_trades_zip",
    "export_wfa_trades_history",
    "generate_wfa_output_filename",
    "_extract_symbol_from_csv_filename",
]


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
