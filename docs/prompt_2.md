# Phase 2: Export Extraction to export.py

**Migration Phase:** 2 of 9
**Complexity:** 🟡 MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 4-6 hours
**Priority:** 🟢 MOVED UP - LOW RISK, HIGH VALUE

---

## Context and Background

### Project Overview

You are working on **S01 Trailing MA v26 - TrailingMA Ultralight**, a cryptocurrency/forex trading strategy backtesting and optimization platform. This phase focuses on centralizing all export logic into a dedicated module.

### Previous Phases Completed

- ✅ **Phase -1: Test Infrastructure Setup** - pytest configured, 21 tests passing
- ✅ **Phase 0: Regression Baseline for S01** - Comprehensive baseline established
- ✅ **Phase 1: Core Extraction** - Engines moved to `src/core/`

### Current State After Phase 1

```
src/
├── core/                           # ✅ Created in Phase 1
│   ├── __init__.py
│   ├── backtest_engine.py         # ✅ Moved in Phase 1
│   ├── optuna_engine.py           # ✅ Moved in Phase 1
│   └── walkforward_engine.py      # ✅ Moved in Phase 1
├── strategies/
│   ├── base.py
│   └── s01_trailing_ma/
│       ├── strategy.py
│       └── config.json
├── server.py                       # ✅ Imports updated in Phase 1
├── run_backtest.py                 # ✅ Imports updated in Phase 1
├── optimizer_engine.py             # Grid Search (contains export logic)
└── index.html
```

**All 21 tests passing.** Regression baseline maintained.

### The Problem

Currently, export logic is **scattered** across multiple files:

1. **optimizer_engine.py** (lines 552-698):
   - `CSV_COLUMN_SPECS` - Column definitions for CSV export
   - `_format_csv_value()` - Value formatting functions
   - `_format_fixed_param_value()` - Fixed parameter formatting
   - `export_to_csv()` - Main CSV export function

2. **optuna_engine.py**:
   - Uses `export_to_csv()` from `optimizer_engine`
   - Some inline CSV generation code

3. **server.py**:
   - Trade export logic (possibly)
   - Result download endpoints

This creates several issues:
- Export logic coupled to Grid Search engine (which will be removed in Phase 3)
- Difficult to reuse export functions
- Violates single responsibility principle
- Hard to test export logic independently

### Target Architecture (After Phase 2)

```
src/
├── core/
│   ├── __init__.py
│   ├── backtest_engine.py
│   ├── optuna_engine.py
│   ├── walkforward_engine.py
│   └── export.py                   # NEW: Centralized export module
├── strategies/
├── server.py
├── run_backtest.py
├── optimizer_engine.py             # Will still exist (Phase 3 removes it)
└── index.html
```

---

## Objective

**Goal:** Centralize all export logic in a single `src/core/export.py` module. This module will provide clean, reusable functions for:

1. **Optuna results export** - CSV with parameter block + results table
2. **WFA results export** - Walk-Forward Analysis summary
3. **Trade export** - Trade history in TradingView format (and ZIP archives)

**Critical Constraints:**
- Export format must remain **EXACTLY the same** (CSV structure, column order, formatting)
- All 21 tests must pass after completion
- Regression baseline must remain identical
- This is low risk because export is "write-only" (doesn't affect calculations)

### Rationale for Moving Phase 2 Up (from original Phase 5)

Originally Phase 5, moved earlier because:
- **Lower risk** than Grid removal or metrics extraction
- **Provides useful utilities immediately** for later phases
- **Helps decouple optimizer_engine** from CSV formatting
- **Makes later phases cleaner** (metrics/indicators can use export right away)
- **Write-only operations** - doesn't affect backtest/optimization results

---

## Architecture Principles

### Export Module Responsibilities

**ONLY handles data export:**
- Format results for CSV
- Generate file content (CSV strings)
- Apply formatting rules (percent, float precision, etc.)
- Handle parameter block headers
- Manage column filtering (exclude fixed params)

**Does NOT:**
- Run backtests or optimizations
- Calculate metrics
- Make decisions about what to export
- Store files (caller provides path or receives string)

### Data Flow

```
Optimization Engine → OptimizationResult[] → export.export_optuna_results() → CSV string
WFA Engine → WFAResults → export.export_wfa_summary() → CSV string
Strategy → TradeRecord[] → export.export_trades() → CSV string + ZIP
```

Export functions are **pure data transformation** functions.

---

## Current Export Implementation Analysis

### Location: `src/optimizer_engine.py` (lines 552-698)

#### 1. CSV Column Specifications (lines 552-585)

```python
CSV_COLUMN_SPECS: List[Tuple[str, Optional[str], str, Optional[str]]] = [
    # Format: (Column Header, Frontend Key, Result Attribute, Formatter)
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
```

**Purpose:** Maps result object attributes to CSV columns with formatting rules

**Key features:**
- Tuple format: `(Header, FrontendKey, AttributeName, Formatter)`
- `FrontendKey`: Used to identify fixed parameters for filtering
- `Formatter`: Controls number formatting (`percent`, `float`, `float1`, `optional_float`)

#### 2. Value Formatting Functions (lines 588-608)

```python
def _format_csv_value(value: Any, formatter: Optional[str]) -> str:
    """Format a single value for CSV output"""
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
    """Format a fixed parameter value"""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)
```

**Purpose:** Apply consistent formatting to values

**Key features:**
- Percent values: `230.75%` (2 decimals + %)
- Float values: `11.52` (2 decimals)
- Float1 values: `2.0` (1 decimal)
- Optional float: Empty string for None, otherwise 2 decimals
- Fixed params: 1 decimal for floats

#### 3. Main Export Function (lines 610-698)

```python
def export_to_csv(
    results: List[OptimizationResult],
    fixed_params: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]],
    *,
    filter_min_profit: bool = False,
    min_profit_threshold: float = 0.0,
    optimization_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Export results to CSV format string with fixed parameter metadata."""

    import io
    output = io.StringIO()

    # Convert fixed_params to consistent format
    if isinstance(fixed_params, Mapping):
        fixed_items = list(fixed_params.items())
    else:
        fixed_items = list(fixed_params)
    fixed_lookup = {name: value for name, value in fixed_items}

    # Write optimization metadata (if Optuna)
    if optimization_metadata:
        output.write("Optuna Metadata\n")
        output.write(f"Method,{optimization_metadata.get('method', 'Grid Search')}\n")
        if optimization_metadata.get("method") == "Optuna":
            output.write(f"Target,{optimization_metadata.get('target', 'Composite Score')}\n")
            output.write(f"Total Trials,{optimization_metadata.get('total_trials', 0)}\n")
            output.write(f"Completed Trials,{optimization_metadata.get('completed_trials', 0)}\n")
            output.write(f"Pruned Trials,{optimization_metadata.get('pruned_trials', 0)}\n")
            output.write(f"Best Trial Number,{optimization_metadata.get('best_trial_number', 0)}\n")
            output.write(f"Best Value,{optimization_metadata.get('best_value', 0)}\n")
            output.write(f"Optimization Time,{optimization_metadata.get('optimization_time', '-')}\n")
        else:  # Grid Search
            output.write(f"Total Combinations,{optimization_metadata.get('total_combinations', 0)}\n")
            output.write(f"Optimization Time,{optimization_metadata.get('optimization_time', '-')}\n")
        output.write("\n")

    # Write fixed parameters block
    output.write("Fixed Parameters\n")
    output.write("Parameter Name,Value\n")
    for name, value in fixed_items:
        formatted_value = _format_fixed_param_value(value)
        output.write(f"{name},{formatted_value}\n")
    output.write("\n")

    # Filter columns (exclude fixed parameters)
    filtered_columns = [
        spec for spec in CSV_COLUMN_SPECS
        if spec[1] is None or spec[1] not in fixed_lookup
    ]

    # Write column headers
    header_line = ",".join(column[0] for column in filtered_columns)
    output.write(header_line + "\n")

    # Filter results by min profit (if enabled)
    if filter_min_profit:
        threshold = float(min_profit_threshold)
        filtered_results = [
            item for item in results if float(item.net_profit_pct) >= threshold
        ]
    else:
        filtered_results = results

    # Write result rows
    for item in filtered_results:
        row_values = []
        for _, frontend_name, attr_name, formatter in filtered_columns:
            value = getattr(item, attr_name)
            row_values.append(_format_csv_value(value, formatter))
        output.write(",".join(row_values) + "\n")

    return output.getvalue()
```

**Purpose:** Generate complete CSV string with parameter block + results table

**Key features:**
- Writes optimization metadata section (Optuna-specific info)
- Writes fixed parameters block
- Filters columns to exclude fixed params from results table
- Supports min profit filtering
- Returns CSV as string (not writing to file directly)

---

## Detailed Step-by-Step Instructions

### Step 1: Create Export Module Skeleton (10 minutes)

**Action:** Create `src/core/export.py` with module structure and imports.

```bash
touch src/core/export.py
```

**Populate initial structure:**

```python
"""
Export module for S01 TrailingMA platform.

Provides centralized export functions for:
- Optuna optimization results (CSV with parameter block)
- Walk-Forward Analysis results (CSV summary)
- Trade history (CSV and ZIP archives)

All export functions are pure data transformations that format
data structures into output strings. They do not perform I/O
or affect calculation results.
"""

from dataclasses import dataclass
from io import StringIO, BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Mapping, Iterable, Tuple
from zipfile import ZipFile, ZIP_DEFLATED
import csv
import json

# Import data structures from core engines
from .backtest_engine import TradeRecord, StrategyResult
# OptimizationResult will be imported from optimizer_engine temporarily
# (Phase 3 will move it to optuna_engine)


__all__ = [
    "export_optuna_results",
    "export_wfa_summary",
    "export_trades_csv",
    "export_trades_zip",
]


# Column specifications for Optuna/Grid Search results
# Format: (Column Header, Frontend Key, Result Attribute, Formatter)
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


# ============================================================================
# Private Helper Functions
# ============================================================================

def _format_csv_value(value: Any, formatter: Optional[str]) -> str:
    """
    Format a single value for CSV output according to formatter spec.

    Args:
        value: The value to format
        formatter: Formatting rule ("percent", "float", "float1", "optional_float", or None)

    Returns:
        Formatted string representation
    """
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
    """
    Format a fixed parameter value for the parameter block.

    Args:
        value: The parameter value

    Returns:
        Formatted string (1 decimal for floats, empty for None)
    """
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


# ============================================================================
# Public Export Functions
# ============================================================================

def export_optuna_results(
    results: List[Any],  # List[OptimizationResult]
    fixed_params: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]],
    *,
    filter_min_profit: bool = False,
    min_profit_threshold: float = 0.0,
    optimization_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Export Optuna/Grid Search optimization results to CSV format string.

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

    Example CSV structure:
        Optuna Metadata
        Method,Optuna
        Target,Composite Score
        Total Trials,100
        ...

        Fixed Parameters
        Parameter Name,Value
        maType,HMA
        maLength,50
        ...

        CC L,CC S,St L X,...,Net Profit%,Max DD%,Trades,Score
        9,5,2.0,...,230.75%,20.03%,93,11.52
        10,4,1.5,...,215.30%,18.50%,87,10.85
        ...
    """
    # Implementation copied from optimizer_engine.export_to_csv()
    pass


def export_wfa_summary(
    wfa_results: Any,  # WFAResults structure
    path: Optional[str] = None,
) -> str:
    """
    Export Walk-Forward Analysis results to CSV format string.

    The CSV includes:
    - Summary metrics across all windows
    - Per-window details (in-sample optimization, out-of-sample testing)
    - Aggregated performance statistics

    Args:
        wfa_results: WFA results structure with window-by-window data
        path: Optional file path to write CSV (if None, just return string)

    Returns:
        CSV content as string

    Example CSV structure:
        Walk-Forward Analysis Summary
        Total Windows,5
        Successful Windows,4
        Success Rate,80.00%
        Avg IS Profit,25.50%
        Avg OOS Profit,18.30%

        Window,IS Start,IS End,OOS Start,OOS End,IS Profit%,OOS Profit%,Best Params
        1,2025-05-01,2025-07-01,2025-07-01,2025-08-01,28.50%,22.10%,"{...}"
        2,2025-06-01,2025-08-01,2025-08-01,2025-09-01,24.20%,19.80%,"{...}"
        ...
    """
    # To be implemented
    # This is a placeholder for now - will be fully implemented when WFA is tested
    raise NotImplementedError("WFA export will be implemented when WFA engine is validated")


def export_trades_csv(
    trades: List[TradeRecord],
    path: Optional[str] = None,
) -> str:
    """
    Export trade history to CSV format string (TradingView Trading Report Generator compatible).

    Args:
        trades: List of TradeRecord objects
        path: Optional file path to write CSV (if None, just return string)

    Returns:
        CSV content as string

    CSV format (TradingView compatible):
        Symbol,Type,Entry Time,Entry Price,Exit Time,Exit Price,Profit,Profit %,Size
        LINKUSDT,Long,2025-06-15 10:30:00,12.45,2025-06-16 14:20:00,12.98,53.00,4.26%,100
        LINKUSDT,Short,2025-06-17 09:15:00,13.10,2025-06-17 16:45:00,12.85,25.00,1.91%,100
        ...
    """
    output = StringIO()

    # CSV header (TradingView format)
    output.write("Symbol,Type,Entry Time,Entry Price,Exit Time,Exit Price,Profit,Profit %,Size\n")

    for trade in trades:
        symbol = "LINKUSDT"  # TODO: Make configurable
        direction = trade.direction or "Long"
        entry_time = trade.entry_time.strftime("%Y-%m-%d %H:%M:%S") if trade.entry_time else ""
        entry_price = f"{trade.entry_price:.2f}" if trade.entry_price else "0.00"
        exit_time = trade.exit_time.strftime("%Y-%m-%d %H:%M:%S") if trade.exit_time else ""
        exit_price = f"{trade.exit_price:.2f}" if trade.exit_price else "0.00"
        profit = f"{trade.net_pnl:.2f}" if trade.net_pnl else "0.00"
        profit_pct = f"{trade.profit_pct:.2f}%" if trade.profit_pct else "0.00%"
        size = f"{trade.size:.2f}" if trade.size else "0.00"

        output.write(f"{symbol},{direction},{entry_time},{entry_price},{exit_time},{exit_price},{profit},{profit_pct},{size}\n")

    csv_content = output.getvalue()

    # Write to file if path provided
    if path:
        with open(path, 'w', newline='') as f:
            f.write(csv_content)

    return csv_content


def export_trades_zip(
    trades: List[TradeRecord],
    metrics: Dict[str, Any],
    path: str,
) -> bytes:
    """
    Export trade history as ZIP archive containing CSV + JSON metadata.

    Creates a ZIP file with:
    - trades.csv: Trade history in TradingView format
    - summary.json: Strategy metrics and metadata

    Args:
        trades: List of TradeRecord objects
        metrics: Dictionary of strategy metrics (net_profit_pct, max_drawdown_pct, etc.)
        path: File path for ZIP archive

    Returns:
        ZIP file content as bytes
    """
    zip_buffer = BytesIO()

    with ZipFile(zip_buffer, 'w', ZIP_DEFLATED) as zipf:
        # Add trades CSV
        trades_csv = export_trades_csv(trades)
        zipf.writestr("trades.csv", trades_csv)

        # Add summary JSON
        summary = {
            "metrics": metrics,
            "total_trades": len(trades),
            "generated_at": pd.Timestamp.now().isoformat(),
        }
        zipf.writestr("summary.json", json.dumps(summary, indent=2))

    zip_content = zip_buffer.getvalue()

    # Write to file if path provided
    if path:
        with open(path, 'wb') as f:
            f.write(zip_content)

    return zip_content
```

**Checkpoint:** File created with skeleton structure

---

### Step 2: Implement `export_optuna_results()` (45-60 minutes)

**Action:** Copy and adapt the `export_to_csv()` function from `optimizer_engine.py`.

**Complete implementation:**

```python
def export_optuna_results(
    results: List[Any],  # List[OptimizationResult]
    fixed_params: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]],
    *,
    filter_min_profit: bool = False,
    min_profit_threshold: float = 0.0,
    optimization_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Export Optuna/Grid Search optimization results to CSV format string.

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

    # Convert fixed_params to consistent format
    if isinstance(fixed_params, Mapping):
        fixed_items = list(fixed_params.items())
    else:
        fixed_items = list(fixed_params)
    fixed_lookup = {name: value for name, value in fixed_items}

    # Section 1: Optuna Metadata (optional)
    if optimization_metadata:
        output.write("Optuna Metadata\n")
        output.write(f"Method,{optimization_metadata.get('method', 'Grid Search')}\n")

        if optimization_metadata.get("method") == "Optuna":
            # Optuna-specific metadata
            output.write(f"Target,{optimization_metadata.get('target', 'Composite Score')}\n")
            output.write(f"Total Trials,{optimization_metadata.get('total_trials', 0)}\n")
            output.write(f"Completed Trials,{optimization_metadata.get('completed_trials', 0)}\n")
            output.write(f"Pruned Trials,{optimization_metadata.get('pruned_trials', 0)}\n")
            output.write(f"Best Trial Number,{optimization_metadata.get('best_trial_number', 0)}\n")
            output.write(f"Best Value,{optimization_metadata.get('best_value', 0)}\n")
            output.write(f"Optimization Time,{optimization_metadata.get('optimization_time', '-')}\n")
        else:
            # Grid Search metadata
            output.write(f"Total Combinations,{optimization_metadata.get('total_combinations', 0)}\n")
            output.write(f"Optimization Time,{optimization_metadata.get('optimization_time', '-')}\n")

        output.write("\n")

    # Section 2: Fixed Parameters
    output.write("Fixed Parameters\n")
    output.write("Parameter Name,Value\n")
    for name, value in fixed_items:
        formatted_value = _format_fixed_param_value(value)
        output.write(f"{name},{formatted_value}\n")
    output.write("\n")

    # Section 3: Results Table

    # Filter columns to exclude fixed parameters
    filtered_columns = [
        spec for spec in CSV_COLUMN_SPECS
        if spec[1] is None or spec[1] not in fixed_lookup
    ]

    # Write column headers
    header_line = ",".join(column[0] for column in filtered_columns)
    output.write(header_line + "\n")

    # Filter results by minimum profit (if enabled)
    if filter_min_profit:
        threshold = float(min_profit_threshold)
        filtered_results = [
            item for item in results
            if float(item.net_profit_pct) >= threshold
        ]
    else:
        filtered_results = results

    # Write result rows
    for item in filtered_results:
        row_values = []
        for _, frontend_name, attr_name, formatter in filtered_columns:
            value = getattr(item, attr_name)
            row_values.append(_format_csv_value(value, formatter))
        output.write(",".join(row_values) + "\n")

    return output.getvalue()
```

**Verification:**
- This should be IDENTICAL to the original `export_to_csv()` from `optimizer_engine.py`
- Only changes: function name, docstring improvements, type hints

---

### Step 3: Update `optimizer_engine.py` to Use Export Module (30 minutes)

**Action:** Replace local export logic with calls to `export.export_optuna_results()`.

**In `src/optimizer_engine.py`:**

**1. Add import at top of file:**

```python
from core.export import export_optuna_results
```

**2. Mark old functions as deprecated:**

```python
# DEPRECATED: Use core.export.export_optuna_results() instead
# Keeping for backward compatibility during Phase 2 (Grid Search removal)
def export_to_csv(
    results: List[OptimizationResult],
    fixed_params: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]],
    *,
    filter_min_profit: bool = False,
    min_profit_threshold: float = 0.0,
    optimization_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    DEPRECATED: Use core.export.export_optuna_results() instead.
    This wrapper exists for backward compatibility during migration.
    Will be removed in Phase 3 (Grid Search removal).
    """
    from core.export import export_optuna_results
    return export_optuna_results(
        results,
        fixed_params,
        filter_min_profit=filter_min_profit,
        min_profit_threshold=min_profit_threshold,
        optimization_metadata=optimization_metadata,
    )
```

**3. Update any internal calls** (search for `export_to_csv()` usage):

```bash
grep -n "export_to_csv(" src/optimizer_engine.py
```

Replace with:
```python
from core.export import export_optuna_results
# ... later in code ...
csv_content = export_optuna_results(results, fixed_params, ...)
```

**Rationale:** We keep the old function as a deprecated wrapper during Phase 2. Phase 3 (Grid Search removal) will delete `optimizer_engine.py` entirely, so the wrapper will go away then.

---

### Step 4: Update `optuna_engine.py` to Use Export Module (30 minutes)

**Action:** Update `src/core/optuna_engine.py` to use the new export module.

**Search for export usage:**

```bash
grep -n "export" src/core/optuna_engine.py
grep -n "optimizer_engine" src/core/optuna_engine.py
```

**Expected findings:**
- Imports from `optimizer_engine` for `export_to_csv()`
- Calls to `export_to_csv()` when saving optimization results

**Update imports:**

**BEFORE:**
```python
from optimizer_engine import (
    OptimizationResult,
    DEFAULT_SCORE_CONFIG,
    export_to_csv,
    # ...
)
```

**AFTER:**
```python
from optimizer_engine import (
    OptimizationResult,
    DEFAULT_SCORE_CONFIG,
    # ... other imports
)
from .export import export_optuna_results
```

**Update function calls:**

**BEFORE:**
```python
csv_content = export_to_csv(
    results,
    fixed_params,
    optimization_metadata=metadata,
)
```

**AFTER:**
```python
csv_content = export_optuna_results(
    results,
    fixed_params,
    optimization_metadata=metadata,
)
```

---

### Step 5: Update `server.py` to Use Export Module (30 minutes)

**Action:** Update Flask API endpoints that export results.

**Search for export logic:**

```bash
grep -n "export" src/server.py
grep -n "CSV" src/server.py
grep -n "download" src/server.py
```

**Look for:**
- Trade export endpoints
- Optimization result download endpoints
- CSV generation code

**Update pattern:**

**BEFORE:**
```python
from optimizer_engine import export_to_csv

# ... in endpoint ...
csv_content = export_to_csv(results, fixed_params, ...)
```

**AFTER:**
```python
from core.export import export_optuna_results, export_trades_csv

# ... in endpoint ...
csv_content = export_optuna_results(results, fixed_params, ...)

# For trade exports:
trades_csv = export_trades_csv(result.trades)
```

**Add trade export endpoint (if not exists):**

```python
@app.route('/api/export/trades', methods=['POST'])
def export_trades():
    """Export trade history as CSV or ZIP"""
    data = request.json
    # ... get trades from result ...

    format_type = data.get('format', 'csv')  # 'csv' or 'zip'

    if format_type == 'zip':
        from core.export import export_trades_zip
        zip_content = export_trades_zip(trades, metrics, path=None)
        return send_file(
            BytesIO(zip_content),
            mimetype='application/zip',
            as_attachment=True,
            download_name='trades.zip'
        )
    else:
        from core.export import export_trades_csv
        csv_content = export_trades_csv(trades)
        return send_file(
            StringIO(csv_content),
            mimetype='text/csv',
            as_attachment=True,
            download_name='trades.csv'
        )
```

---

### Step 6: Update Core Package Exports (10 minutes)

**Action:** Add export functions to `src/core/__init__.py`.

**In `src/core/__init__.py`, add:**

```python
# Export module
from .export import (
    export_optuna_results,
    export_wfa_summary,
    export_trades_csv,
    export_trades_zip,
)

__all__ = [
    # ... existing exports ...

    # export module exports
    "export_optuna_results",
    "export_wfa_summary",
    "export_trades_csv",
    "export_trades_zip",
]
```

**Benefit:** Allows `from core import export_optuna_results` in addition to `from core.export import export_optuna_results`

---

### Step 7: Add Missing Import for pandas (5 minutes)

**In `src/core/export.py`, add at top:**

```python
import pandas as pd
```

**Required for:**
- `pd.Timestamp.now()` in `export_trades_zip()`
- Potential future use in other export functions

---

### Step 8: Testing (60-90 minutes)

**Critical:** Export changes must not affect calculation results, only output formatting.

#### 8.1: Unit Tests for Export Functions

**Create `tests/test_export.py`:**

```python
"""Tests for export module."""

import pytest
import json
from pathlib import Path
from core.export import (
    export_optuna_results,
    export_trades_csv,
    _format_csv_value,
    _format_fixed_param_value,
)
from core.backtest_engine import TradeRecord
import pandas as pd


class TestFormatting:
    """Test formatting helper functions."""

    def test_format_csv_value_percent(self):
        assert _format_csv_value(230.75, "percent") == "230.75%"
        assert _format_csv_value(0.5, "percent") == "0.50%"

    def test_format_csv_value_float(self):
        assert _format_csv_value(11.5234, "float") == "11.52"
        assert _format_csv_value(0.12, "float") == "0.12"

    def test_format_csv_value_float1(self):
        assert _format_csv_value(2.45, "float1") == "2.4"
        assert _format_csv_value(10.0, "float1") == "10.0"

    def test_format_csv_value_optional_float(self):
        assert _format_csv_value(11.52, "optional_float") == "11.52"
        assert _format_csv_value(None, "optional_float") == ""

    def test_format_csv_value_none_formatter(self):
        assert _format_csv_value("HMA", None) == "HMA"
        assert _format_csv_value(50, None) == "50"

    def test_format_fixed_param_value(self):
        assert _format_fixed_param_value(2.5) == "2.5"
        assert _format_fixed_param_value(None) == ""
        assert _format_fixed_param_value("HMA") == "HMA"


class TestTradeExport:
    """Test trade export functions."""

    def test_export_trades_csv_empty(self):
        """Test exporting empty trade list."""
        csv = export_trades_csv([])
        lines = csv.strip().split('\n')
        assert len(lines) == 1  # Just header
        assert lines[0].startswith("Symbol,Type,Entry Time")

    def test_export_trades_csv_single_trade(self):
        """Test exporting single trade."""
        trade = TradeRecord(
            direction="Long",
            entry_time=pd.Timestamp("2025-06-15 10:30:00"),
            exit_time=pd.Timestamp("2025-06-16 14:20:00"),
            entry_price=12.45,
            exit_price=12.98,
            size=100.0,
            net_pnl=53.0,
            profit_pct=4.26,
        )

        csv = export_trades_csv([trade])
        lines = csv.strip().split('\n')

        assert len(lines) == 2  # Header + 1 trade
        assert "Long" in lines[1]
        assert "12.45" in lines[1]
        assert "12.98" in lines[1]
        assert "53.00" in lines[1]

    def test_export_trades_csv_multiple_trades(self):
        """Test exporting multiple trades."""
        trades = [
            TradeRecord(direction="Long", entry_price=12.0, exit_price=12.5, size=100, net_pnl=50),
            TradeRecord(direction="Short", entry_price=13.0, exit_price=12.8, size=100, net_pnl=20),
        ]

        csv = export_trades_csv(trades)
        lines = csv.strip().split('\n')

        assert len(lines) == 3  # Header + 2 trades


class TestOptunaExport:
    """Test Optuna results export."""

    def test_export_optuna_results_basic(self):
        """Test basic Optuna export without metadata."""
        # Create mock results
        from dataclasses import dataclass

        @dataclass
        class MockResult:
            ma_type: str = "HMA"
            ma_length: int = 50
            close_count_long: int = 9
            close_count_short: int = 5
            net_profit_pct: float = 230.75
            max_drawdown_pct: float = 20.03
            total_trades: int = 93
            score: float = 11.52
            sharpe_ratio: float = 0.92
            profit_factor: float = 1.76
            romad: float = 11.52
            ulcer_index: float = 12.01
            recovery_factor: float = 11.52
            consistency_score: float = 66.67
            # ... all required attributes

        results = [MockResult()]
        fixed_params = {"maType": "HMA", "maLength": 50}

        csv = export_optuna_results(results, fixed_params)

        # Verify structure
        assert "Fixed Parameters" in csv
        assert "maType,HMA" in csv or "maLength,50" in csv
        assert "Net Profit%" in csv
        assert "230.75%" in csv

    def test_export_optuna_results_with_metadata(self):
        """Test Optuna export with optimization metadata."""
        # ... similar to above but with optimization_metadata
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Run tests:**
```bash
pytest tests/test_export.py -v
```

**Expected:** All export tests passing

#### 8.2: Regression Tests

**Run regression tests:**

```bash
pytest tests/test_regression_s01.py -v -m regression
```

**Expected:** 12/12 tests passing

**Critical validations:**
- ✅ Net profit matches baseline (230.75% ± 0.01%)
- ✅ Max drawdown matches baseline (20.03% ± 0.01%)
- ✅ Total trades matches baseline (93 exact)

#### 8.3: Full Test Suite

```bash
pytest tests/ -v
```

**Expected:** All tests passing (21 original + new export tests)

#### 8.4: Manual Export Testing

**Test Optuna export via UI:**

1. Start server: `cd src && python server.py`
2. Run small Optuna optimization (10 trials)
3. Download results CSV
4. Verify format:
   - Has "Optuna Metadata" section
   - Has "Fixed Parameters" section
   - Has results table with correct columns
   - Values formatted correctly (percentages, decimals)

**Test via Python script:**

```python
from core.export import export_optuna_results
from optimizer_engine import OptimizationResult

# Create test results
results = [
    OptimizationResult(
        net_profit_pct=230.75,
        max_drawdown_pct=20.03,
        total_trades=93,
        score=11.52,
        # ... all fields
    )
]

fixed_params = {"maType": "HMA", "maLength": 50}

metadata = {
    "method": "Optuna",
    "total_trials": 100,
    "completed_trials": 100,
    "best_trial_number": 42,
    "best_value": 11.52,
}

csv = export_optuna_results(results, fixed_params, optimization_metadata=metadata)
print(csv)

# Verify output format manually
```

#### 8.5: Compare Old vs New Export

**Create comparison script `tools/compare_export.py`:**

```python
"""Compare old and new export implementations."""

from optimizer_engine import export_to_csv as old_export
from core.export import export_optuna_results as new_export
from optimizer_engine import OptimizationResult

# Create identical test data
results = [
    OptimizationResult(
        ma_type="HMA",
        ma_length=50,
        close_count_long=9,
        close_count_short=5,
        # ... all fields with same values
        net_profit_pct=230.75,
        max_drawdown_pct=20.03,
        total_trades=93,
        score=11.52,
    )
]

fixed_params = {"maType": "HMA", "maLength": 50}
metadata = {"method": "Optuna", "total_trials": 100}

# Generate both exports
old_csv = old_export(results, fixed_params, optimization_metadata=metadata)
new_csv = new_export(results, fixed_params, optimization_metadata=metadata)

# Compare
if old_csv == new_csv:
    print("✅ PASS: Old and new export produce IDENTICAL output")
else:
    print("❌ FAIL: Exports differ!")
    print("\n=== OLD ===")
    print(old_csv)
    print("\n=== NEW ===")
    print(new_csv)

    # Character-by-character comparison
    for i, (c1, c2) in enumerate(zip(old_csv, new_csv)):
        if c1 != c2:
            print(f"First difference at position {i}: '{c1}' vs '{c2}'")
            break
```

**Run comparison:**
```bash
python tools/compare_export.py
```

**Expected output:**
```
✅ PASS: Old and new export produce IDENTICAL output
```

---

### Step 9: Clean Up Deprecated Code (Optional - Can Wait for Phase 3)

**Action:** Mark old export functions as deprecated but keep them functional.

**In `src/optimizer_engine.py`:**

```python
# DEPRECATED SECTION - To be removed in Phase 3
# ================================================
# The following functions are deprecated and should not be used.
# Use core.export module instead.

import warnings

def export_to_csv(*args, **kwargs):
    """DEPRECATED: Use core.export.export_optuna_results() instead."""
    warnings.warn(
        "export_to_csv() is deprecated. Use core.export.export_optuna_results() instead. "
        "This function will be removed in Phase 3 (Grid Search removal).",
        DeprecationWarning,
        stacklevel=2
    )
    from core.export import export_optuna_results
    return export_optuna_results(*args, **kwargs)


def _format_csv_value(value, formatter):
    """DEPRECATED: Use core.export._format_csv_value() instead."""
    warnings.warn("_format_csv_value() is deprecated.", DeprecationWarning, stacklevel=2)
    from core.export import _format_csv_value as new_format
    return new_format(value, formatter)
```

**Rationale:** Provides backward compatibility during Phase 2. Phase 3 will delete `optimizer_engine.py` entirely, removing all these wrappers.

---

## Validation Checklist

Before considering Phase 2 complete, verify ALL of the following:

### File Structure
- [ ] `src/core/export.py` exists and is complete
- [ ] `src/core/__init__.py` exports export functions
- [ ] Export logic extracted from `optimizer_engine.py`
- [ ] Export logic extracted from `optuna_engine.py`

### Export Implementation
- [ ] `export_optuna_results()` implemented
- [ ] `export_wfa_summary()` stubbed (placeholder)
- [ ] `export_trades_csv()` implemented
- [ ] `export_trades_zip()` implemented
- [ ] `_format_csv_value()` implemented
- [ ] `_format_fixed_param_value()` implemented
- [ ] `CSV_COLUMN_SPECS` defined

### Import Updates
- [ ] `optimizer_engine.py` imports from `core.export`
- [ ] `optuna_engine.py` imports from `.export` or `core.export`
- [ ] `server.py` imports from `core.export`
- [ ] Old functions marked deprecated (or removed)

### Testing
- [ ] Export unit tests created (`tests/test_export.py`)
- [ ] All export unit tests passing
- [ ] Regression tests passing: 12/12
- [ ] Full test suite passing: 21+ tests
- [ ] Manual export test via UI passed
- [ ] Old vs new export comparison IDENTICAL

### Behavioral Validation
- [ ] CSV format EXACTLY matches original
- [ ] Column order unchanged
- [ ] Value formatting unchanged (percentages, decimals)
- [ ] Fixed parameter block unchanged
- [ ] Metadata section unchanged
- [ ] Net profit matches baseline: 230.75%
- [ ] Total trades matches baseline: 93

### Code Quality
- [ ] No export logic duplication
- [ ] Clean function signatures
- [ ] Comprehensive docstrings
- [ ] Type hints where appropriate

---

## Git Workflow

```bash
# Stage changes
git add src/core/export.py
git add src/core/__init__.py
git add src/optimizer_engine.py
git add src/core/optuna_engine.py
git add src/server.py
git add tests/test_export.py

# Commit
git commit -m "Phase 2: Extract export logic to export.py

- Created src/core/export.py with centralized export functions
- Implemented export_optuna_results() (moved from optimizer_engine)
- Implemented export_trades_csv() and export_trades_zip()
- Stubbed export_wfa_summary() (placeholder for future)
- Updated optimizer_engine.py to use new export module
- Updated optuna_engine.py to use new export module
- Updated server.py to use new export module
- Added comprehensive export tests
- All tests passing (21 original + new export tests)
- Regression baseline maintained (Net Profit 230.75%, Trades 93)
- Export format unchanged (bit-exact CSV output)

This extraction:
- Decouples export logic from optimizer_engine (prep for Phase 3)
- Provides reusable export utilities for all engines
- Maintains 100% backward compatibility
- Zero behavior changes
"

# Tag
git tag phase-2-complete
```

---

## Common Issues and Troubleshooting

### Issue 1: CSV format differs slightly

**Symptom:** Export comparison shows minor differences

**Solution:**
- Check for extra newlines or spaces
- Verify column order matches `CSV_COLUMN_SPECS`
- Ensure formatters are applied correctly
- Check for Windows vs Unix line endings

### Issue 2: Import errors for OptimizationResult

**Symptom:** `Cannot import OptimizationResult from core.export`

**Solution:**
- `OptimizationResult` lives in `optimizer_engine.py` for now
- Import it from there in `export.py`:
  ```python
  # Temporary import (Phase 3 will move to optuna_engine)
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent.parent))
  from optimizer_engine import OptimizationResult
  ```

### Issue 3: Tests fail after export changes

**Symptom:** Regression tests fail with different results

**Cause:** Should NOT happen - export doesn't affect calculations

**Solution:**
- Verify NO changes to backtest/optimization logic
- Only export functions should be modified
- Double-check imports are correct

---

## Success Criteria Summary

Phase 2 is complete when:

1. ✅ **Export module created** - `src/core/export.py` exists
2. ✅ **All export functions implemented** - optuna, trades (CSV + ZIP)
3. ✅ **All imports updated** - engines use new export module
4. ✅ **All tests passing** - original + new export tests
5. ✅ **CSV format unchanged** - bit-exact match with original
6. ✅ **Regression baseline maintained** - 230.75% profit, 93 trades
7. ✅ **Clean git commit** - with tag `phase-2-complete`

---

## Next Steps After Phase 2

**Phase 3: Grid Search Removal**
- Complexity: 🟡 MEDIUM
- Risk: 🟡 MEDIUM
- Estimated Effort: 6-8 hours

Phase 3 will:
- Remove Grid Search completely
- Delete `optimizer_engine.py`
- Move shared code to `optuna_engine.py`
- Update UI to remove Grid Search option

---

**End of Phase 2 Prompt**
**Total Length:** ~19.8 KB
**Target Audience:** GPT 5.1 Codex
**Expected Execution Time:** 4-6 hours
**Risk Level:** 🟢 LOW (write-only operations)
