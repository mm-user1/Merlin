"""
Centralized export utilities for the TrailingMA platform.

Provides pure data-to-string/bytes transformation helpers for trade exports.

The functions in this module do not perform any calculations; they only
format existing data structures into the expected output formats.
"""

from __future__ import annotations

import csv
import json
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from .backtest_engine import TradeRecord
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "export_trades_csv",
    "export_trades_zip",
    "_extract_symbol_from_csv_filename",
]


def export_trades_csv(
    trades: List[TradeRecord],
    path: Optional[str] = None,
    *,
    symbol: str = "LINKUSDT",
) -> str:
    """Export trade history to TradingView-compatible CSV format.

    Each trade produces TWO rows: entry and exit, using the format:
        Symbol,Side,Qty,Fill Price,Closing Time

    Args:
        trades: List of TradeRecord objects
        path: Optional file path to write CSV (if None, just return string)
        symbol: Trading symbol used for all rows

    Returns:
        CSV content as string
    """

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Symbol", "Side", "Qty", "Fill Price", "Closing Time"])

    for trade in trades:
        direction_raw = trade.direction or trade.side or "long"
        is_short = str(direction_raw).lower() == "short"
        entry_side = "Sell" if is_short else "Buy"
        exit_side = "Buy" if is_short else "Sell"

        entry_time = trade.entry_time.strftime("%Y-%m-%d %H:%M:%S") if trade.entry_time else ""
        exit_time = trade.exit_time.strftime("%Y-%m-%d %H:%M:%S") if trade.exit_time else ""

        qty_value = "" if trade.size is None else trade.size
        entry_price_value = "" if trade.entry_price is None else trade.entry_price
        exit_price_value = "" if trade.exit_price is None else trade.exit_price

        writer.writerow([symbol, entry_side, qty_value, entry_price_value, entry_time])
        writer.writerow([symbol, exit_side, qty_value, exit_price_value, exit_time])

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
