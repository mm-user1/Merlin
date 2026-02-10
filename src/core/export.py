"""
Centralized export utilities for the TrailingMA platform.

Provides pure data-to-string/bytes transformation helpers for trade exports.

The functions in this module do not perform any calculations; they only
format existing data structures into the expected output formats.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from .backtest_engine import TradeRecord
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "export_trades_csv",
    "_extract_symbol_from_csv_filename",
]


def export_trades_csv(
    trades: List[TradeRecord],
    path: Optional[str] = None,
    *,
    symbol: str = "LINKUSDT",
    sort_events_chronologically: bool = True,
) -> str:
    """Export trade history to TradingView-compatible CSV format.

    Each trade produces TWO rows: entry and exit, using the format:
        Symbol,Side,Qty,Fill Price,Closing Time

    Args:
        trades: List of TradeRecord objects
        path: Optional file path to write CSV (if None, just return string)
        symbol: Trading symbol used for all rows
        sort_events_chronologically: Sort entry/exit events by timestamp.
            Disable for stitched WFA exports to preserve per-window sequence.

    Returns:
        CSV content as string
    """

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Symbol", "Side", "Qty", "Fill Price", "Closing Time"])

    def _format_numeric(value: object) -> str:
        if value is None:
            return ""
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return str(value)
        # Trim binary-float artifacts while preserving practical precision.
        normalized = format(number.quantize(Decimal("0.00000001")).normalize(), "f")
        return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized

    events = []
    for trade in trades:
        direction_raw = trade.direction or trade.side or "long"
        is_short = str(direction_raw).lower() == "short"
        entry_side = "Sell" if is_short else "Buy"
        exit_side = "Buy" if is_short else "Sell"

        qty_value = _format_numeric(trade.size)
        entry_price_value = _format_numeric(trade.entry_price)
        exit_price_value = _format_numeric(trade.exit_price)

        events.append(
            {
                "seq": len(events),
                "time": trade.entry_time,
                "row": [symbol, entry_side, qty_value, entry_price_value, ""],
            }
        )
        events.append(
            {
                "seq": len(events),
                "time": trade.exit_time,
                "row": [symbol, exit_side, qty_value, exit_price_value, ""],
            }
        )

    def _event_sort_key(event: dict) -> tuple:
        ts = event.get("time")
        if ts is None:
            return (1, "", int(event.get("seq", 0)))
        # Use lexical ISO key to avoid timezone-aware/naive comparison issues.
        sort_key = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        return (0, sort_key, int(event.get("seq", 0)))

    event_rows = (
        sorted(events, key=_event_sort_key)
        if sort_events_chronologically
        else events
    )
    for event in event_rows:
        ts = event.get("time")
        event["row"][-1] = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        writer.writerow(event["row"])

    csv_content = output.getvalue()

    if path:
        Path(path).write_text(csv_content, encoding="utf-8")

    return csv_content


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
