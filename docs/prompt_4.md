# Phase 4: Metrics Extraction to metrics.py

**Migration Phase:** 4 of 9
**Complexity:** 🔴 HIGH
**Risk:** 🔴 HIGH
**Estimated Effort:** 8-12 hours
**Priority:** 🚨 HIGH-RISK PHASE #1

---

## Context and Background

### Project Overview

You are working on **S01 Trailing MA v26 - TrailingMA Ultralight**, a cryptocurrency/forex trading strategy backtesting and optimization platform. This phase focuses on extracting all metrics calculation logic from `backtest_engine.py` into a dedicated `metrics.py` module.

### Previous Phases Completed

- ✅ **Phase -1: Test Infrastructure Setup** - pytest configured, comprehensive test suite in place
- ✅ **Phase 0: Regression Baseline for S01** - Baseline established and verified (Net Profit: 230.75%, Trades: 93)
- ✅ **Phase 1: Core Extraction** - Engines moved to `src/core/`
- ✅ **Phase 2: Export Extraction** - Export logic centralized in `src/core/export.py`
- ✅ **Phase 3: Grid Search Removal** - Grid Search deleted, Optuna-only architecture

### Current State After Phase 3

```
src/
├── core/
│   ├── __init__.py
│   ├── backtest_engine.py         # ⚠️ Contains metrics calculation - TO BE EXTRACTED
│   ├── optuna_engine.py           # ✅ Uses metrics from backtest_engine
│   ├── walkforward_engine.py      # ✅ Uses metrics from backtest_engine
│   └── export.py                  # ✅ Formats metrics for CSV
├── strategies/
│   ├── base.py
│   └── s01_trailing_ma/
│       ├── strategy.py
│       └── config.json
├── server.py                       # ✅ Returns metrics in API responses
└── run_backtest.py                 # ✅ Displays metrics in CLI
```

**All tests passing** (21/21). Regression baseline maintained (Net Profit: 230.75%, Max DD: 20.03%, Trades: 93).

---

## The Problem: Metrics Scattered in backtest_engine.py

Currently, `backtest_engine.py` contains **two distinct responsibilities**:

### 1. **Trade Simulation** (should remain)
- Bar-by-bar strategy execution
- Position management
- Order execution
- Trade record generation
- Data structures: `TradeRecord`, `StrategyResult`

### 2. **Metrics Calculation** (should be extracted)
- Basic metrics: net profit, max drawdown, win rate
- Advanced metrics: Sharpe, RoMaD, Profit Factor, Ulcer Index, Consistency
- Helper functions: monthly returns calculation, etc.

### Current Metrics Implementation (backtest_engine.py)

**Lines 526-723:** Metrics calculation functions

```python
# Line 526-567: Monthly returns calculation
def calculate_monthly_returns(
    trades: List[TradeRecord],
    initial_balance: float,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp
) -> List[float]:
    """Calculate monthly percentage returns for Sharpe and Consistency."""
    # ... implementation

# Line 569-591: Profit Factor
def calculate_profit_factor(trades: List[TradeRecord]) -> Optional[float]:
    """Calculate Profit Factor (gross profit / gross loss)."""
    # ... implementation

# Line 594-621: Sharpe Ratio
def calculate_sharpe_ratio(monthly_returns: List[float], risk_free_rate: float = 0.02) -> Optional[float]:
    """Calculate annualized Sharpe Ratio from monthly returns."""
    # ... implementation

# Line 623-649: Ulcer Index
def calculate_ulcer_index(equity_curve: List[float]) -> Optional[float]:
    """Calculate Ulcer Index (downside volatility measure)."""
    # ... implementation

# Line 651-669: Consistency Score
def calculate_consistency_score(monthly_returns: List[float]) -> Optional[float]:
    """Calculate percentage of profitable months."""
    # ... implementation

# Line 671-723: Advanced Metrics Aggregator
def calculate_advanced_metrics(
    result: StrategyResult,
    trades: List[TradeRecord],
    initial_balance: float,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    risk_free_rate: float = 0.02
) -> None:
    """
    Calculate all advanced metrics and populate StrategyResult.

    Modifies result in-place by setting:
    - sharpe_ratio
    - profit_factor
    - romad
    - ulcer_index
    - recovery_factor
    - consistency_score
    """
    # ... implementation
```

**StrategyResult structure (lines 48-87):**

```python
@dataclass
class StrategyResult:
    """Complete result of a strategy backtest."""
    trades: List[TradeRecord]
    equity_curve: List[float]
    balance_curve: List[float]
    timestamps: List[pd.Timestamp]

    # Basic metrics
    net_profit: float = 0.0
    net_profit_pct: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Advanced metrics (calculated by calculate_advanced_metrics)
    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    romad: Optional[float] = None  # Return Over Maximum Drawdown
    ulcer_index: Optional[float] = None
    recovery_factor: Optional[float] = None
    consistency_score: Optional[float] = None
```

---

## Objective

**Goal:** Extract all metrics calculation logic from `backtest_engine.py` into a dedicated `metrics.py` module by:

1. **Creating `src/core/metrics.py`** with clean data structures and functions
2. **Defining metric data structures:**
   - `BasicMetrics` - Net profit, drawdown, trades, win rate
   - `AdvancedMetrics` - Sharpe, RoMaD, Profit Factor, Ulcer, Consistency
   - `WFAMetrics` - Walk-Forward Analysis aggregated metrics (future)
3. **Moving calculation functions** from backtest_engine.py to metrics.py
4. **Implementing parity tests** (OLD vs NEW must be bit-exact)
5. **Updating all consumers** (backtest_engine, optuna_engine, walkforward_engine)
6. **Removing OLD code** from backtest_engine.py

**Critical Constraints:**
- **Bit-exact compatibility:** Metrics must produce identical results (tolerance < 1e-10)
- **Regression baseline maintained:** Net Profit 230.75%, Max DD 20.03%, Trades 93
- **All tests passing:** Including new parity tests
- **No performance degradation:** Metrics calculation overhead must be minimal

---

## Architecture Principles

### Data Structure Ownership

Following the principle **"structures live where they're populated"**:

- **TradeRecord, StrategyResult** → `backtest_engine.py` (populated during simulation) ✅ Unchanged
- **BasicMetrics, AdvancedMetrics** → `metrics.py` (calculated from StrategyResult) ⬅️ **NEW**
- **WFAMetrics** → `metrics.py` (aggregated metrics) ⬅️ **NEW**
- **OptimizationResult** → `optuna_engine.py` (created during optimization) ✅ Unchanged

### Metrics Module Responsibility

**metrics.py ONLY calculates metrics:**
- Single Responsibility Principle
- Other modules consume metrics
- Clear separation of concerns
- **Does NOT orchestrate** - just calculates and returns

### Why This Is High Risk

1. **Bit-exact compatibility required:** Any tiny change in formula breaks comparability
2. **Multiple consumers:** backtest_engine, optuna_engine, walkforward_engine all depend on metrics
3. **Floating-point sensitivity:** Order of operations matters: `(a+b)+c ≠ a+(b+c)`
4. **Complex metrics:** Sharpe ratio, Ulcer Index have multi-step calculations
5. **Regression baseline dependency:** Net Profit 230.75% must remain exact

---

## Current Metrics Analysis

### Basic Metrics (Currently in StrategyResult)

Calculated during or immediately after simulation:

- `net_profit` - Total profit in currency
- `net_profit_pct` - Total profit as percentage
- `gross_profit` - Sum of all winning trades
- `gross_loss` - Sum of all losing trades (absolute value)
- `max_drawdown` - Maximum peak-to-trough decline in currency
- `max_drawdown_pct` - Maximum drawdown as percentage
- `total_trades` - Total number of trades
- `winning_trades` - Number of profitable trades
- `losing_trades` - Number of unprofitable trades
- `win_rate` - Percentage of winning trades (can be derived)
- `avg_win` - Average winning trade size (can be derived)
- `avg_loss` - Average losing trade size (can be derived)
- `avg_trade` - Average trade PnL (can be derived)

### Advanced Metrics (Currently calculated by calculate_advanced_metrics)

Calculated after simulation completes:

- `sharpe_ratio` - Risk-adjusted return (annualized)
- `profit_factor` - Gross profit / Gross loss
- `romad` - Return Over Maximum Drawdown (net_profit_pct / max_drawdown_pct)
- `ulcer_index` - Downside volatility measure
- `recovery_factor` - Net profit / Maximum drawdown (in currency)
- `consistency_score` - Percentage of profitable months

### Helper Functions

Support advanced metrics calculation:

- `calculate_monthly_returns()` - For Sharpe and Consistency
- `calculate_profit_factor()` - Gross profit ratio
- `calculate_sharpe_ratio()` - Risk-adjusted return
- `calculate_ulcer_index()` - Downside volatility
- `calculate_consistency_score()` - Monthly profitability

---

## Detailed Step-by-Step Instructions

### Step 1: Create metrics.py Structure (60-90 minutes)

**Action:** Create `src/core/metrics.py` with data structures and function signatures.

#### 1.1: Create File with Imports

**Create `src/core/metrics.py`:**

```python
"""
Metrics calculation module for S01 Trailing MA v26.

This module provides:
- BasicMetrics: Net profit, drawdown, trade statistics
- AdvancedMetrics: Sharpe, RoMaD, Profit Factor, Ulcer Index, Consistency
- Calculation functions that operate on StrategyResult

Architectural note: This module ONLY calculates metrics.
It does NOT orchestrate backtests or optimization.
Other modules (backtest_engine, optuna_engine, walkforward_engine) consume these metrics.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

import pandas as pd
import numpy as np

# Import from backtest_engine (for StrategyResult and TradeRecord)
from .backtest_engine import StrategyResult, TradeRecord

logger = logging.getLogger(__name__)


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class BasicMetrics:
    """
    Basic performance metrics calculated from strategy results.

    These are the fundamental metrics that describe strategy performance:
    - Profitability (net profit, gross profit/loss)
    - Risk (max drawdown)
    - Activity (total trades, win rate)
    - Efficiency (average win/loss sizes)

    All metrics are calculated from the trade list and equity curve.
    """
    net_profit: float                # Total profit in currency
    net_profit_pct: float            # Total profit as percentage
    gross_profit: float              # Sum of all winning trades
    gross_loss: float                # Sum of all losing trades (absolute)
    max_drawdown: float              # Maximum peak-to-trough decline (currency)
    max_drawdown_pct: float          # Maximum drawdown as percentage
    total_trades: int                # Total number of trades
    winning_trades: int              # Number of profitable trades
    losing_trades: int               # Number of unprofitable trades
    win_rate: float                  # Percentage of winning trades
    avg_win: float                   # Average winning trade size
    avg_loss: float                  # Average losing trade size (absolute)
    avg_trade: float                 # Average trade PnL

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "net_profit": self.net_profit,
            "net_profit_pct": self.net_profit_pct,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "avg_trade": self.avg_trade,
        }


@dataclass
class AdvancedMetrics:
    """
    Advanced risk-adjusted metrics for optimization and analysis.

    These metrics provide deeper insight into strategy quality:
    - Risk-adjusted returns (Sharpe, Sortino)
    - Efficiency ratios (Profit Factor, RoMaD, Recovery Factor)
    - Volatility measures (Ulcer Index)
    - Consistency indicators (monthly profitability)

    All values are Optional since they may not be calculable
    (e.g., no trades, insufficient data for monthly returns).
    """
    sharpe_ratio: Optional[float] = None        # Risk-adjusted return
    sortino_ratio: Optional[float] = None       # Downside risk-adjusted return
    profit_factor: Optional[float] = None       # Gross profit / Gross loss
    romad: Optional[float] = None               # Return Over Maximum Drawdown
    recovery_factor: Optional[float] = None     # Net profit / Max drawdown (currency)
    ulcer_index: Optional[float] = None         # Downside volatility measure
    consistency_score: Optional[float] = None   # % of profitable months

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "profit_factor": self.profit_factor,
            "romad": self.romad,
            "recovery_factor": self.recovery_factor,
            "ulcer_index": self.ulcer_index,
            "consistency_score": self.consistency_score,
        }


@dataclass
class WFAMetrics:
    """
    Walk-Forward Analysis aggregate metrics.

    Aggregates metrics across multiple WFA windows to assess:
    - Average performance across windows
    - Consistency between in-sample and out-of-sample
    - Success rate (percentage of profitable windows)
    - Stability measures

    Note: This structure is for future use (Phase 7+).
    Basic version provided here for completeness.
    """
    avg_net_profit_pct: float               # Average net profit across windows
    avg_max_drawdown_pct: float             # Average max drawdown across windows
    successful_windows: int                 # Number of profitable windows
    total_windows: int                      # Total number of windows tested
    success_rate: float                     # Percentage of successful windows
    avg_sharpe_ratio: Optional[float] = None    # Average Sharpe across windows
    avg_romad: Optional[float] = None           # Average RoMaD across windows

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "avg_net_profit_pct": self.avg_net_profit_pct,
            "avg_max_drawdown_pct": self.avg_max_drawdown_pct,
            "successful_windows": self.successful_windows,
            "total_windows": self.total_windows,
            "success_rate": self.success_rate,
            "avg_sharpe_ratio": self.avg_sharpe_ratio,
            "avg_romad": self.avg_romad,
        }


# ============================================================================
# Helper Functions
# ============================================================================

def _calculate_monthly_returns(
    trades: List[TradeRecord],
    initial_balance: float,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp
) -> List[float]:
    """
    Calculate monthly percentage returns from trade list.

    Used by Sharpe ratio and Consistency score calculations.

    Args:
        trades: List of completed trades
        initial_balance: Starting account balance
        start_time: Start of trading period
        end_time: End of trading period

    Returns:
        List of monthly percentage returns

    Note:
        This is a COPY of the function from backtest_engine.py.
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py (lines 526-567)
    pass


def _calculate_profit_factor_value(trades: List[TradeRecord]) -> Optional[float]:
    """
    Calculate Profit Factor (gross profit / gross loss).

    Args:
        trades: List of completed trades

    Returns:
        Profit factor value, or None if no losing trades

    Note:
        This is a COPY of the function from backtest_engine.py.
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py (lines 569-591)
    pass


def _calculate_sharpe_ratio_value(
    monthly_returns: List[float],
    risk_free_rate: float = 0.02
) -> Optional[float]:
    """
    Calculate annualized Sharpe Ratio from monthly returns.

    Args:
        monthly_returns: List of monthly percentage returns
        risk_free_rate: Annual risk-free rate (default 2%)

    Returns:
        Annualized Sharpe ratio, or None if insufficient data

    Note:
        This is a COPY of the function from backtest_engine.py.
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py (lines 594-621)
    pass


def _calculate_ulcer_index_value(equity_curve: List[float]) -> Optional[float]:
    """
    Calculate Ulcer Index (downside volatility measure).

    Measures the depth and duration of drawdowns.
    Lower is better.

    Args:
        equity_curve: List of account balances over time

    Returns:
        Ulcer Index value, or None if insufficient data

    Note:
        This is a COPY of the function from backtest_engine.py.
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py (lines 623-649)
    pass


def _calculate_consistency_score_value(monthly_returns: List[float]) -> Optional[float]:
    """
    Calculate percentage of profitable months.

    Args:
        monthly_returns: List of monthly percentage returns

    Returns:
        Percentage of months with positive returns (0-100)

    Note:
        This is a COPY of the function from backtest_engine.py.
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py (lines 651-669)
    pass


# ============================================================================
# Main Calculation Functions
# ============================================================================

def calculate_basic(result: StrategyResult, initial_balance: float = 10000.0) -> BasicMetrics:
    """
    Calculate basic metrics from strategy result.

    Extracts and calculates fundamental performance metrics:
    - Net profit and percentage
    - Gross profit and gross loss
    - Maximum drawdown
    - Trade statistics (count, win rate, averages)

    Args:
        result: StrategyResult object from backtest
        initial_balance: Starting account balance (default 10000)

    Returns:
        BasicMetrics object with all basic metrics populated

    Example:
        >>> result = run_strategy(df, params, trade_start_idx)
        >>> basic = calculate_basic(result, initial_balance=10000.0)
        >>> print(f"Net Profit: {basic.net_profit_pct:.2f}%")
        Net Profit: 230.75%
    """
    # TODO: Implement calculation logic
    # Extract from result:
    # - Net profit from balance curve
    # - Max drawdown from equity curve
    # - Trade statistics from trade list
    pass


def calculate_advanced(
    result: StrategyResult,
    initial_balance: float = 10000.0,
    risk_free_rate: float = 0.02
) -> AdvancedMetrics:
    """
    Calculate advanced risk-adjusted metrics from strategy result.

    Computes sophisticated metrics that require:
    - Monthly return aggregation (for Sharpe and Consistency)
    - Equity curve analysis (for Ulcer Index)
    - Trade list analysis (for Profit Factor)

    Args:
        result: StrategyResult object from backtest
        initial_balance: Starting account balance (default 10000)
        risk_free_rate: Annual risk-free rate for Sharpe calculation (default 0.02)

    Returns:
        AdvancedMetrics object with all advanced metrics populated

    Note:
        Some metrics may be None if insufficient data
        (e.g., <2 months for Sharpe, no losing trades for Profit Factor)

    Example:
        >>> result = run_strategy(df, params, trade_start_idx)
        >>> advanced = calculate_advanced(result, initial_balance=10000.0)
        >>> print(f"Sharpe: {advanced.sharpe_ratio:.2f}")
        Sharpe: 0.92
    """
    # TODO: Implement calculation logic
    # Steps:
    # 1. Calculate monthly returns (if trades span multiple months)
    # 2. Calculate Sharpe ratio from monthly returns
    # 3. Calculate Profit Factor from trade list
    # 4. Calculate RoMaD (net_profit_pct / max_drawdown_pct)
    # 5. Calculate Ulcer Index from equity curve
    # 6. Calculate Recovery Factor (net_profit / max_drawdown_currency)
    # 7. Calculate Consistency score from monthly returns
    pass


def calculate_for_wfa(wfa_results: List[Dict[str, Any]]) -> WFAMetrics:
    """
    Calculate aggregate WFA metrics from multiple windows.

    Aggregates metrics across Walk-Forward Analysis windows to assess:
    - Average performance
    - Success rate
    - Consistency between IS and OOS

    Args:
        wfa_results: List of dictionaries, each containing:
            - 'is_result': In-sample StrategyResult
            - 'oos_result': Out-of-sample StrategyResult
            - Other WFA metadata

    Returns:
        WFAMetrics object with aggregated statistics

    Note:
        This is a placeholder for future WFA implementation (Phase 7+).
        Basic implementation provided for architecture completeness.

    Example:
        >>> wfa_results = run_walkforward(...)
        >>> wfa_metrics = calculate_for_wfa(wfa_results)
        >>> print(f"Success Rate: {wfa_metrics.success_rate:.1f}%")
        Success Rate: 75.0%
    """
    # TODO: Implement WFA aggregation logic
    # Steps:
    # 1. Extract OOS net_profit_pct from each window
    # 2. Extract OOS max_drawdown_pct from each window
    # 3. Calculate averages
    # 4. Count successful windows (OOS net_profit_pct > 0)
    # 5. Calculate success rate
    # 6. Average Sharpe and RoMaD if available
    pass
```

**Checkpoint:** File created with structure. No implementation yet.

---

### Step 2: Copy Helper Functions (90-120 minutes)

**Action:** Copy metric calculation functions from `backtest_engine.py` to `metrics.py` **exactly** (bit-for-bit).

#### 2.1: Copy calculate_monthly_returns

**From `backtest_engine.py` lines 526-567:**

```python
def _calculate_monthly_returns(
    trades: List[TradeRecord],
    initial_balance: float,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp
) -> List[float]:
    """
    Calculate monthly percentage returns from trade list.

    [COPY EXACT DOCSTRING AND IMPLEMENTATION]
    """
    # COPY LINES 526-567 EXACTLY - DO NOT MODIFY
    # Verify line-by-line match with original
```

**Critical:** Use diff to verify exact match:

```bash
# After copying, extract just this function from both files and compare
diff <(sed -n '526,567p' src/core/backtest_engine.py) \
     <(sed -n 'START,ENDp' src/core/metrics.py)
# Should show ZERO differences (except function name prefix)
```

#### 2.2: Copy calculate_profit_factor

**From `backtest_engine.py` lines 569-591:**

```python
def _calculate_profit_factor_value(trades: List[TradeRecord]) -> Optional[float]:
    """
    Calculate Profit Factor (gross profit / gross loss).

    [COPY EXACT IMPLEMENTATION]
    """
    # COPY LINES 569-591 EXACTLY
```

#### 2.3: Copy calculate_sharpe_ratio

**From `backtest_engine.py` lines 594-621:**

```python
def _calculate_sharpe_ratio_value(
    monthly_returns: List[float],
    risk_free_rate: float = 0.02
) -> Optional[float]:
    """
    Calculate annualized Sharpe Ratio from monthly returns.

    [COPY EXACT IMPLEMENTATION]
    """
    # COPY LINES 594-621 EXACTLY
```

#### 2.4: Copy calculate_ulcer_index

**From `backtest_engine.py` lines 623-649:**

```python
def _calculate_ulcer_index_value(equity_curve: List[float]) -> Optional[float]:
    """
    Calculate Ulcer Index (downside volatility measure).

    [COPY EXACT IMPLEMENTATION]
    """
    # COPY LINES 623-649 EXACTLY
```

#### 2.5: Copy calculate_consistency_score

**From `backtest_engine.py` lines 651-669:**

```python
def _calculate_consistency_score_value(monthly_returns: List[float]) -> Optional[float]:
    """
    Calculate percentage of profitable months.

    [COPY EXACT IMPLEMENTATION]
    """
    # COPY LINES 651-669 EXACTLY
```

**Checkpoint:** All helper functions copied. Verify each with diff.

---

### Step 3: Implement calculate_basic() (60-90 minutes)

**Action:** Implement basic metrics calculation by extracting logic from current `StrategyResult` population.

#### 3.1: Analyze Current Implementation

**In `backtest_engine.py`, search for where basic metrics are set:**

```bash
grep -n "result.net_profit\|result.max_drawdown\|result.total_trades" src/core/backtest_engine.py
```

**Expected locations:**
- Around line 1000-1050: After strategy execution, basic metrics are calculated

#### 3.2: Implement calculate_basic()

```python
def calculate_basic(result: StrategyResult, initial_balance: float = 10000.0) -> BasicMetrics:
    """Calculate basic metrics from strategy result."""

    trades = result.trades
    balance_curve = result.balance_curve
    equity_curve = result.equity_curve

    # Net profit
    if len(balance_curve) > 0:
        net_profit = balance_curve[-1] - initial_balance
        net_profit_pct = (net_profit / initial_balance) * 100.0
    else:
        net_profit = 0.0
        net_profit_pct = 0.0

    # Gross profit and loss
    gross_profit = 0.0
    gross_loss = 0.0
    winning_trades = 0
    losing_trades = 0

    for trade in trades:
        if trade.net_pnl > 0:
            gross_profit += trade.net_pnl
            winning_trades += 1
        elif trade.net_pnl < 0:
            gross_loss += abs(trade.net_pnl)
            losing_trades += 1

    # Maximum drawdown
    max_dd = 0.0
    max_dd_pct = 0.0

    if len(equity_curve) > 0:
        peak = equity_curve[0]
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = peak - value
            if dd > max_dd:
                max_dd = dd

        if peak > 0:
            max_dd_pct = (max_dd / peak) * 100.0

    # Trade statistics
    total_trades = len(trades)
    win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0
    avg_win = (gross_profit / winning_trades) if winning_trades > 0 else 0.0
    avg_loss = (gross_loss / losing_trades) if losing_trades > 0 else 0.0
    avg_trade = (net_profit / total_trades) if total_trades > 0 else 0.0

    return BasicMetrics(
        net_profit=net_profit,
        net_profit_pct=net_profit_pct,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        avg_trade=avg_trade,
    )
```

**Note:** This must match EXACTLY how `backtest_engine.py` currently calculates these values. Compare implementation carefully.

---

### Step 4: Implement calculate_advanced() (90-120 minutes)

**Action:** Implement advanced metrics calculation using the copied helper functions.

```python
def calculate_advanced(
    result: StrategyResult,
    initial_balance: float = 10000.0,
    risk_free_rate: float = 0.02
) -> AdvancedMetrics:
    """Calculate advanced risk-adjusted metrics from strategy result."""

    trades = result.trades
    equity_curve = result.equity_curve
    balance_curve = result.balance_curve
    timestamps = result.timestamps

    # Initialize all metrics as None
    sharpe_ratio = None
    sortino_ratio = None  # Not currently implemented, placeholder
    profit_factor = None
    romad = None
    recovery_factor = None
    ulcer_index = None
    consistency_score = None

    # Calculate Profit Factor
    if len(trades) > 0:
        profit_factor = _calculate_profit_factor_value(trades)

    # Calculate monthly returns (if enough time span)
    monthly_returns = []
    if len(trades) > 0 and len(timestamps) > 0:
        start_time = timestamps[0]
        end_time = timestamps[-1]
        monthly_returns = _calculate_monthly_returns(
            trades, initial_balance, start_time, end_time
        )

    # Calculate Sharpe Ratio
    if len(monthly_returns) >= 2:  # Need at least 2 months
        sharpe_ratio = _calculate_sharpe_ratio_value(monthly_returns, risk_free_rate)

    # Calculate Consistency Score
    if len(monthly_returns) >= 1:
        consistency_score = _calculate_consistency_score_value(monthly_returns)

    # Calculate Ulcer Index
    if len(equity_curve) > 0:
        ulcer_index = _calculate_ulcer_index_value(equity_curve)

    # Calculate RoMaD and Recovery Factor (need basic metrics)
    # Use calculate_basic to get max_drawdown values
    basic = calculate_basic(result, initial_balance)

    if basic.max_drawdown_pct > 0:
        romad = basic.net_profit_pct / basic.max_drawdown_pct

    if basic.max_drawdown > 0:
        recovery_factor = basic.net_profit / basic.max_drawdown

    return AdvancedMetrics(
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        profit_factor=profit_factor,
        romad=romad,
        recovery_factor=recovery_factor,
        ulcer_index=ulcer_index,
        consistency_score=consistency_score,
    )
```

**Critical Check:** Compare this logic with `calculate_advanced_metrics()` in `backtest_engine.py` (lines 671-723).

---

### Step 5: Create Parity Tests (120-180 minutes)

**Action:** Create comprehensive tests to verify OLD and NEW implementations produce identical results.

#### 5.1: Create Test File

**Create `tests/test_metrics.py`:**

```python
"""
Parity tests for metrics extraction (Phase 4).

These tests verify that the NEW metrics.py implementation
produces bit-exact identical results to the OLD backtest_engine.py implementation.

Critical: These tests MUST pass before metrics extraction is considered complete.
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

# Import OLD implementation (from backtest_engine)
from core.backtest_engine import (
    StrategyParams,
    run_strategy,
    StrategyResult,
    TradeRecord,
    load_data,
    prepare_dataset_with_warmup,
    calculate_advanced_metrics as OLD_calculate_advanced_metrics,  # OLD
)

# Import NEW implementation (from metrics)
from core.metrics import (
    calculate_basic,
    calculate_advanced,
    BasicMetrics,
    AdvancedMetrics,
)

# Test data paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
BASELINE_PATH = PROJECT_ROOT / "data" / "baseline" / "s01_metrics.json"


@pytest.fixture(scope="module")
def test_data():
    """Load test dataset."""
    df = load_data(str(DATA_PATH))
    return df


@pytest.fixture(scope="module")
def baseline_params():
    """Load baseline parameters."""
    import json
    with open(BASELINE_PATH, 'r') as f:
        baseline = json.load(f)
    return baseline['parameters']


@pytest.fixture(scope="module")
def test_result(test_data, baseline_params):
    """Run backtest and get StrategyResult."""
    params = StrategyParams.from_dict(baseline_params)

    start_ts = pd.Timestamp(baseline_params['start'], tz='UTC')
    end_ts = pd.Timestamp(baseline_params['end'], tz='UTC')
    warmup_bars = 1000

    df_prepared, trade_start_idx = prepare_dataset_with_warmup(
        test_data, start_ts, end_ts, warmup_bars
    )

    result = run_strategy(df_prepared, params, trade_start_idx)
    return result


class TestMetricsParity:
    """Test parity between OLD and NEW metrics implementations."""

    def test_basic_net_profit_matches(self, test_result):
        """Test net profit calculation matches OLD implementation."""
        # OLD way (from StrategyResult directly)
        old_net_profit = test_result.net_profit
        old_net_profit_pct = test_result.net_profit_pct

        # NEW way (from metrics.py)
        basic = calculate_basic(test_result, initial_balance=10000.0)

        # Bit-exact comparison
        assert old_net_profit == basic.net_profit, \
            f"Net profit mismatch: OLD={old_net_profit}, NEW={basic.net_profit}"
        assert old_net_profit_pct == basic.net_profit_pct, \
            f"Net profit % mismatch: OLD={old_net_profit_pct}, NEW={basic.net_profit_pct}"

    def test_basic_max_drawdown_matches(self, test_result):
        """Test max drawdown calculation matches OLD implementation."""
        old_max_dd = test_result.max_drawdown
        old_max_dd_pct = test_result.max_drawdown_pct

        basic = calculate_basic(test_result, initial_balance=10000.0)

        assert old_max_dd == basic.max_drawdown
        assert old_max_dd_pct == basic.max_drawdown_pct

    def test_basic_total_trades_matches(self, test_result):
        """Test total trades count matches OLD implementation."""
        old_total = test_result.total_trades

        basic = calculate_basic(test_result, initial_balance=10000.0)

        assert old_total == basic.total_trades

    def test_basic_win_rate_matches(self, test_result):
        """Test win rate calculation matches OLD implementation."""
        # OLD: Calculate from StrategyResult
        old_winning = test_result.winning_trades
        old_losing = test_result.losing_trades
        old_total = test_result.total_trades
        old_win_rate = (old_winning / old_total * 100.0) if old_total > 0 else 0.0

        # NEW: From BasicMetrics
        basic = calculate_basic(test_result, initial_balance=10000.0)

        assert basic.winning_trades == old_winning
        assert basic.losing_trades == old_losing
        assert basic.win_rate == old_win_rate

    def test_advanced_sharpe_ratio_matches(self, test_result):
        """Test Sharpe ratio calculation matches OLD implementation."""
        # OLD: Already in StrategyResult (calculated by calculate_advanced_metrics)
        old_sharpe = test_result.sharpe_ratio

        # NEW: From AdvancedMetrics
        advanced = calculate_advanced(test_result, initial_balance=10000.0)

        if old_sharpe is None:
            assert advanced.sharpe_ratio is None
        else:
            # Allow tiny floating-point tolerance
            assert advanced.sharpe_ratio is not None
            assert abs(old_sharpe - advanced.sharpe_ratio) < 1e-10, \
                f"Sharpe mismatch: OLD={old_sharpe}, NEW={advanced.sharpe_ratio}"

    def test_advanced_profit_factor_matches(self, test_result):
        """Test Profit Factor calculation matches OLD implementation."""
        old_pf = test_result.profit_factor
        advanced = calculate_advanced(test_result, initial_balance=10000.0)

        if old_pf is None:
            assert advanced.profit_factor is None
        else:
            assert advanced.profit_factor is not None
            assert abs(old_pf - advanced.profit_factor) < 1e-10

    def test_advanced_romad_matches(self, test_result):
        """Test RoMaD calculation matches OLD implementation."""
        old_romad = test_result.romad
        advanced = calculate_advanced(test_result, initial_balance=10000.0)

        if old_romad is None:
            assert advanced.romad is None
        else:
            assert advanced.romad is not None
            assert abs(old_romad - advanced.romad) < 1e-10

    def test_advanced_ulcer_index_matches(self, test_result):
        """Test Ulcer Index calculation matches OLD implementation."""
        old_ulcer = test_result.ulcer_index
        advanced = calculate_advanced(test_result, initial_balance=10000.0)

        if old_ulcer is None:
            assert advanced.ulcer_index is None
        else:
            assert advanced.ulcer_index is not None
            assert abs(old_ulcer - advanced.ulcer_index) < 1e-10

    def test_advanced_consistency_matches(self, test_result):
        """Test Consistency Score calculation matches OLD implementation."""
        old_consistency = test_result.consistency_score
        advanced = calculate_advanced(test_result, initial_balance=10000.0)

        if old_consistency is None:
            assert advanced.consistency_score is None
        else:
            assert advanced.consistency_score is not None
            assert abs(old_consistency - advanced.consistency_score) < 1e-10

    def test_all_basic_metrics_complete(self, test_result):
        """Test that all basic metrics are populated."""
        basic = calculate_basic(test_result, initial_balance=10000.0)

        # All basic metrics should have values (not None)
        assert basic.net_profit is not None
        assert basic.net_profit_pct is not None
        assert basic.gross_profit is not None
        assert basic.gross_loss is not None
        assert basic.max_drawdown is not None
        assert basic.max_drawdown_pct is not None
        assert basic.total_trades is not None
        assert basic.winning_trades is not None
        assert basic.losing_trades is not None
        assert basic.win_rate is not None
        assert basic.avg_win is not None
        assert basic.avg_loss is not None
        assert basic.avg_trade is not None


class TestMetricsEdgeCases:
    """Test metrics calculation with edge cases."""

    def test_zero_trades(self):
        """Test metrics with no trades."""
        # Create empty StrategyResult
        result = StrategyResult(
            trades=[],
            equity_curve=[10000.0],
            balance_curve=[10000.0],
            timestamps=[pd.Timestamp('2025-01-01', tz='UTC')],
        )

        basic = calculate_basic(result, initial_balance=10000.0)

        assert basic.total_trades == 0
        assert basic.net_profit_pct == 0.0
        assert basic.win_rate == 0.0
        assert basic.avg_win == 0.0
        assert basic.avg_loss == 0.0

    def test_all_winning_trades(self):
        """Test metrics with only winning trades."""
        # Create result with 3 winning trades
        trades = [
            TradeRecord(
                direction='Long',
                entry_time=pd.Timestamp('2025-01-01', tz='UTC'),
                exit_time=pd.Timestamp('2025-01-02', tz='UTC'),
                entry_price=100.0,
                exit_price=110.0,
                size=1.0,
                net_pnl=10.0,
            ),
            TradeRecord(
                direction='Long',
                entry_time=pd.Timestamp('2025-01-03', tz='UTC'),
                exit_time=pd.Timestamp('2025-01-04', tz='UTC'),
                entry_price=110.0,
                exit_price=120.0,
                size=1.0,
                net_pnl=10.0,
            ),
            TradeRecord(
                direction='Long',
                entry_time=pd.Timestamp('2025-01-05', tz='UTC'),
                exit_time=pd.Timestamp('2025-01-06', tz='UTC'),
                entry_price=120.0,
                exit_price=130.0,
                size=1.0,
                net_pnl=10.0,
            ),
        ]

        result = StrategyResult(
            trades=trades,
            equity_curve=[10000, 10010, 10020, 10030],
            balance_curve=[10000, 10010, 10020, 10030],
            timestamps=[
                pd.Timestamp('2025-01-01', tz='UTC'),
                pd.Timestamp('2025-01-02', tz='UTC'),
                pd.Timestamp('2025-01-04', tz='UTC'),
                pd.Timestamp('2025-01-06', tz='UTC'),
            ],
        )

        basic = calculate_basic(result, initial_balance=10000.0)

        assert basic.total_trades == 3
        assert basic.winning_trades == 3
        assert basic.losing_trades == 0
        assert basic.win_rate == 100.0
        assert basic.gross_profit == 30.0
        assert basic.gross_loss == 0.0

        advanced = calculate_advanced(result, initial_balance=10000.0)

        # Profit factor undefined (no losses)
        assert advanced.profit_factor is None

    def test_all_losing_trades(self):
        """Test metrics with only losing trades."""
        trades = [
            TradeRecord(
                direction='Long',
                entry_time=pd.Timestamp('2025-01-01', tz='UTC'),
                exit_time=pd.Timestamp('2025-01-02', tz='UTC'),
                entry_price=100.0,
                exit_price=90.0,
                size=1.0,
                net_pnl=-10.0,
            ),
        ]

        result = StrategyResult(
            trades=trades,
            equity_curve=[10000, 9990],
            balance_curve=[10000, 9990],
            timestamps=[
                pd.Timestamp('2025-01-01', tz='UTC'),
                pd.Timestamp('2025-01-02', tz='UTC'),
            ],
        )

        basic = calculate_basic(result, initial_balance=10000.0)

        assert basic.winning_trades == 0
        assert basic.losing_trades == 1
        assert basic.win_rate == 0.0

        advanced = calculate_advanced(result, initial_balance=10000.0)

        # Profit factor = 0 (no wins)
        assert advanced.profit_factor == 0.0


class TestMetricsRegression:
    """Test metrics against baseline values."""

    def test_baseline_net_profit_exact(self, test_result):
        """Test net profit matches baseline EXACTLY."""
        basic = calculate_basic(test_result, initial_balance=10000.0)

        # From baseline: 230.75299101633334%
        expected = 230.75299101633334

        assert abs(basic.net_profit_pct - expected) < 0.01, \
            f"Net profit regression: expected={expected}, actual={basic.net_profit_pct}"

    def test_baseline_max_drawdown_exact(self, test_result):
        """Test max drawdown matches baseline EXACTLY."""
        basic = calculate_basic(test_result, initial_balance=10000.0)

        # From baseline: 20.02549897473176%
        expected = 20.02549897473176

        assert abs(basic.max_drawdown_pct - expected) < 0.01

    def test_baseline_total_trades_exact(self, test_result):
        """Test total trades matches baseline EXACTLY."""
        basic = calculate_basic(test_result, initial_balance=10000.0)

        # From baseline: 93 trades
        expected = 93

        assert basic.total_trades == expected
```

**Run tests:**

```bash
pytest tests/test_metrics.py -v
```

**Expected:** All parity tests MUST pass before proceeding.

---

### Step 6: Update backtest_engine.py to Use metrics.py (60-90 minutes)

**Action:** Update `backtest_engine.py` to call metrics functions instead of calculating inline.

#### 6.1: Add Import

**At top of `src/core/backtest_engine.py`:**

```python
# After existing imports, add:
from . import metrics  # NEW: Metrics calculation module
```

#### 6.2: Update run_strategy() Function

**Find where `calculate_advanced_metrics()` is called (around line 1000):**

**BEFORE:**
```python
# Calculate advanced metrics in-place
calculate_advanced_metrics(
    result,
    result.trades,
    initial_balance,
    df_prepared.index[trade_start_idx],
    df_prepared.index[-1],
    risk_free_rate=0.02
)

return result
```

**AFTER:**
```python
# Calculate metrics using metrics.py module
basic_metrics = metrics.calculate_basic(result, initial_balance=initial_balance)
advanced_metrics = metrics.calculate_advanced(result, initial_balance=initial_balance, risk_free_rate=0.02)

# Copy metrics back to result for backward compatibility
result.net_profit = basic_metrics.net_profit
result.net_profit_pct = basic_metrics.net_profit_pct
result.gross_profit = basic_metrics.gross_profit
result.gross_loss = basic_metrics.gross_loss
result.max_drawdown = basic_metrics.max_drawdown
result.max_drawdown_pct = basic_metrics.max_drawdown_pct
result.total_trades = basic_metrics.total_trades
result.winning_trades = basic_metrics.winning_trades
result.losing_trades = basic_metrics.losing_trades

result.sharpe_ratio = advanced_metrics.sharpe_ratio
result.profit_factor = advanced_metrics.profit_factor
result.romad = advanced_metrics.romad
result.ulcer_index = advanced_metrics.ulcer_index
result.recovery_factor = advanced_metrics.recovery_factor
result.consistency_score = advanced_metrics.consistency_score

return result
```

**Note:** This maintains backward compatibility - `StrategyResult` still has all metric fields populated.

---

### Step 7: Update optuna_engine.py to Use metrics.py (30 minutes)

**Action:** Update `optuna_engine.py` to import metrics from `metrics.py`.

**In `src/core/optuna_engine.py`:**

**Add import:**
```python
from . import metrics
```

**Update `_run_single_combination()` function (around line 650):**

**BEFORE:**
```python
# Extract metrics from result
net_profit_pct = result.net_profit_pct
sharpe_ratio = getattr(result, 'sharpe_ratio', None)
profit_factor = getattr(result, 'profit_factor', None)
romad = getattr(result, 'romad', None)
# ... etc
```

**AFTER:**
```python
# Calculate metrics using metrics.py
basic = metrics.calculate_basic(result, initial_balance=10000.0)
advanced = metrics.calculate_advanced(result, initial_balance=10000.0)

# Extract values
net_profit_pct = basic.net_profit_pct
sharpe_ratio = advanced.sharpe_ratio
profit_factor = advanced.profit_factor
romad = advanced.romad
ulcer_index = advanced.ulcer_index
recovery_factor = advanced.recovery_factor
consistency_score = advanced.consistency_score
```

**Note:** This is optional since `StrategyResult` still has metrics populated. But using metrics.py directly is cleaner.

---

### Step 8: Update walkforward_engine.py (30 minutes)

**Action:** Update Walk-Forward engine to use metrics.py.

**In `src/core/walkforward_engine.py`:**

**Add import:**
```python
from . import metrics
```

**Update metric extraction (find where WFA calculates OOS metrics):**

Similar changes as optuna_engine - use `metrics.calculate_basic()` and `metrics.calculate_advanced()` instead of accessing `StrategyResult` attributes directly.

---

### Step 9: Update core/__init__.py Exports (10 minutes)

**Action:** Export metrics data structures from core package.

**In `src/core/__init__.py`, add:**

```python
# Metrics module exports
from .metrics import (
    BasicMetrics,
    AdvancedMetrics,
    WFAMetrics,
    calculate_basic,
    calculate_advanced,
    calculate_for_wfa,
)

__all__ = [
    # ... existing exports ...

    # Metrics exports
    "BasicMetrics",
    "AdvancedMetrics",
    "WFAMetrics",
    "calculate_basic",
    "calculate_advanced",
    "calculate_for_wfa",
]
```

---

### Step 10: Remove OLD Metric Functions from backtest_engine.py (30 minutes)

**Action:** Delete old metric calculation functions AFTER validation passes.

**⚠️ CRITICAL:** Only do this AFTER all parity tests pass!

**Delete from `backtest_engine.py`:**
- Lines 526-567: `calculate_monthly_returns()`
- Lines 569-591: `calculate_profit_factor()`
- Lines 594-621: `calculate_sharpe_ratio()`
- Lines 623-649: `calculate_ulcer_index()`
- Lines 651-669: `calculate_consistency_score()`
- Lines 671-723: `calculate_advanced_metrics()`

**Keep in StrategyResult:**
- All metric fields (for backward compatibility)
- `to_dict()` method

**Verify deletion:**

```bash
# Search for old function names (should find NOTHING in backtest_engine)
grep -n "def calculate_monthly_returns\|def calculate_profit_factor\|def calculate_sharpe_ratio" src/core/backtest_engine.py
# Should return NOTHING

# Verify they exist in metrics.py
grep -n "def _calculate_monthly_returns\|def _calculate_profit_factor" src/core/metrics.py
# Should find the functions
```

---

### Step 11: Final Testing (90-120 minutes)

**Action:** Run comprehensive test suite to ensure everything still works.

#### 11.1: Run All Tests

```bash
pytest tests/ -v
```

**Expected:** All tests passing (21+ tests, including new metrics tests).

#### 11.2: Run Regression Tests

```bash
pytest tests/test_regression_s01.py -v -m regression
```

**Expected:** 12/12 tests passing

**Critical validations:**
- ✅ Net profit: 230.75% (±0.01%)
- ✅ Max drawdown: 20.03% (±0.01%)
- ✅ Total trades: 93 (exact)

#### 11.3: Test Optuna Optimization

**Create test script `tools/test_optuna_phase4.py`:**

```python
"""Test Optuna optimization after Phase 4 (metrics extraction)."""

from pathlib import Path
from core.optuna_engine import OptunaOptimizer, OptunaConfig
from core.backtest_engine import load_data

# Load data
data_path = Path(__file__).parent.parent / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
df = load_data(str(data_path))

print(f"Loaded {len(df)} bars")

# Configure Optuna
optuna_config = OptunaConfig(
    target="score",
    budget_mode="trials",
    n_trials=10,
    enable_pruning=True,
    sampler="tpe",
)

# Base configuration
base_config = {
    'dataframe': df,
    'warmup_bars': 100,
    'enabled_params': {
        'closeCountLong': True,
        'closeCountShort': True,
    },
    'param_ranges': {
        'closeCountLong': (5, 15, 1),
        'closeCountShort': (3, 10, 1),
    },
    'fixed_params': {
        'maType': 'HMA',
        'maLength': 50,
    },
}

# Run optimization
print("Starting Optuna optimization (10 trials)...")
optimizer = OptunaOptimizer(base_config, optuna_config)
results = optimizer.optimize()

print(f"\nCompleted {len(results)} trials")

# Show best result
best_result = max(results, key=lambda r: r.score)
print(f"\nBest trial:")
print(f"  Score: {best_result.score:.2f}")
print(f"  Net Profit: {best_result.net_profit_pct:.2f}%")
print(f"  RoMaD: {best_result.romad:.2f}")
print(f"  Sharpe: {best_result.sharpe_ratio:.2f}")

print("\n✅ Phase 4 Optuna test PASSED")
```

**Run:**
```bash
python tools/test_optuna_phase4.py
```

**Expected:** Optimization completes successfully with reasonable scores.

#### 11.4: Test via UI

**Start server:**
```bash
cd src
python server.py
```

**In browser:**
1. Navigate to `http://localhost:8000`
2. Select S01 strategy
3. Run single backtest
4. **Verify metrics display:**
   - Net Profit: 230.75%
   - Max Drawdown: 20.03%
   - Total Trades: 93
   - Sharpe Ratio: ~0.92
   - RoMaD: ~11.52

#### 11.5: Performance Check

**Run benchmark:**

```python
# tools/benchmark_metrics.py
import time
from core.backtest_engine import load_data, StrategyParams, run_strategy, prepare_dataset_with_warmup
from core.metrics import calculate_basic, calculate_advanced
import pandas as pd

# Load data
df = load_data("data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv")

# Prepare
params = StrategyParams(ma_type='HMA', ma_length=50)
start_ts = pd.Timestamp('2025-05-01', tz='UTC')
end_ts = pd.Timestamp('2025-11-20', tz='UTC')
df_prepared, trade_start_idx = prepare_dataset_with_warmup(df, start_ts, end_ts, 1000)

# Benchmark
runs = 10
start = time.time()

for i in range(runs):
    result = run_strategy(df_prepared, params, trade_start_idx)
    basic = calculate_basic(result)
    advanced = calculate_advanced(result)

duration = time.time() - start

print(f"Ran {runs} backtests in {duration:.2f}s")
print(f"Average: {duration/runs:.3f}s per backtest")
print(f"Metrics overhead: minimal (included in backtest time)")
```

**Expected:** Similar performance to Phase 3 (±5%).

---

## Validation Checklist

Before considering Phase 4 complete, verify ALL of the following:

### Code Changes
- [ ] `src/core/metrics.py` created with all structures and functions
- [ ] `BasicMetrics` dataclass implemented
- [ ] `AdvancedMetrics` dataclass implemented
- [ ] `WFAMetrics` dataclass implemented (basic version)
- [ ] `calculate_basic()` implemented
- [ ] `calculate_advanced()` implemented
- [ ] `calculate_for_wfa()` implemented (placeholder)
- [ ] Helper functions copied from backtest_engine.py
- [ ] `backtest_engine.py` updated to use metrics.py
- [ ] `optuna_engine.py` updated to use metrics.py
- [ ] `walkforward_engine.py` updated to use metrics.py
- [ ] `src/core/__init__.py` exports metrics structures
- [ ] OLD metric functions deleted from backtest_engine.py

### Testing
- [ ] All parity tests passing: `pytest tests/test_metrics.py -v`
- [ ] All regression tests passing: `pytest tests/test_regression_s01.py -v`
- [ ] Full test suite passing: `pytest tests/ -v`
- [ ] Optuna test passing: `python tools/test_optuna_phase4.py`
- [ ] UI test passing: Manual verification via browser

### Behavioral Validation
- [ ] Net profit matches baseline: 230.75% (±0.01%)
- [ ] Max drawdown matches baseline: 20.03% (±0.01%)
- [ ] Total trades matches baseline: 93 (exact)
- [ ] Sharpe ratio matches baseline: ~0.916 (±0.001)
- [ ] RoMaD matches baseline: ~11.52 (±0.01)
- [ ] All other metrics within tolerance

### Code Quality
- [ ] No references to OLD functions in backtest_engine:
  ```bash
  grep -n "calculate_monthly_returns\|calculate_profit_factor\|calculate_sharpe_ratio\|calculate_ulcer_index\|calculate_consistency_score\|calculate_advanced_metrics" src/core/backtest_engine.py
  # Should find NOTHING or only comments
  ```
- [ ] All imports correct
- [ ] No circular dependencies
- [ ] Docstrings complete

### Documentation
- [ ] Function docstrings in metrics.py
- [ ] Data structure docstrings
- [ ] Phase 4 completion documented
- [ ] Updated MIGRATION_PROGRESS.md (Phase 3 documentation missing, you should update it too)

---

## Git Workflow

```bash
# Stage all changes
git add src/core/metrics.py
git add src/core/backtest_engine.py
git add src/core/optuna_engine.py
git add src/core/walkforward_engine.py
git add src/core/__init__.py
git add tests/test_metrics.py
git add tools/test_optuna_phase4.py
git add tools/benchmark_metrics.py

# Commit
git commit -m "Phase 4: Extract metrics to metrics.py

- Created src/core/metrics.py with clean metric structures:
  - BasicMetrics (net profit, drawdown, trades, win rate, etc.)
  - AdvancedMetrics (Sharpe, RoMaD, Profit Factor, Ulcer, Consistency)
  - WFAMetrics (placeholder for Phase 7+)

- Implemented calculation functions:
  - calculate_basic(): Basic performance metrics
  - calculate_advanced(): Risk-adjusted metrics
  - calculate_for_wfa(): WFA aggregation (placeholder)

- Copied helper functions from backtest_engine.py:
  - _calculate_monthly_returns()
  - _calculate_profit_factor_value()
  - _calculate_sharpe_ratio_value()
  - _calculate_ulcer_index_value()
  - _calculate_consistency_score_value()

- Updated backtest_engine.py to use metrics.py
- Updated optuna_engine.py to use metrics.py
- Updated walkforward_engine.py to use metrics.py
- Deleted OLD metric functions from backtest_engine.py

- Created comprehensive parity tests (tests/test_metrics.py)
- All tests passing (24/24)
- Regression baseline maintained:
  - Net Profit: 230.75% ✅
  - Max Drawdown: 20.03% ✅
  - Total Trades: 93 ✅

- Bit-exact compatibility verified
- No performance degradation
- Cleaner separation of concerns
- Prepares for indicators extraction (Phase 5)
"

# Tag
git tag phase-4-complete

# Verify
git log -1 --stat
```

---

## Common Issues and Troubleshooting

### Issue 1: Parity Test Fails - Net Profit Mismatch

**Symptom:**
```
AssertionError: Net profit mismatch: OLD=2307.53, NEW=2307.52
```

**Cause:** Floating-point accumulation difference

**Solution:**
1. Compare calculation order in OLD vs NEW
2. Ensure identical order of operations
3. Check for intermediate rounding
4. Verify initial_balance parameter matches

### Issue 2: Sharpe Ratio is None When It Should Have Value

**Symptom:**
```
AssertionError: expected Sharpe=0.916, got None
```

**Cause:** Monthly returns calculation issue or insufficient data

**Solution:**
1. Check `_calculate_monthly_returns()` copied correctly
2. Verify timestamps in StrategyResult
3. Ensure start_time and end_time parameters passed correctly
4. Check minimum month requirement (need ≥2 months)

### Issue 3: Import Error - Circular Dependency

**Symptom:**
```
ImportError: cannot import name 'StrategyResult' from 'core.metrics'
```

**Cause:** Circular import between metrics.py and backtest_engine.py

**Solution:**
```python
# In metrics.py, use TYPE_CHECKING:
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .backtest_engine import StrategyResult, TradeRecord
else:
    StrategyResult = Any
    TradeRecord = Any

# Or import at module level (preferred):
from .backtest_engine import StrategyResult, TradeRecord
```

### Issue 4: Performance Degradation

**Symptom:** Backtests take 2x longer after Phase 4

**Cause:** Metrics calculated twice or inefficiently

**Solution:**
1. Verify metrics calculated only ONCE per backtest
2. Check for redundant `calculate_basic()` calls
3. Profile with `cProfile` to find bottleneck
4. Ensure no deep copying of large data structures

### Issue 5: RoMaD Calculation Incorrect

**Symptom:**
```
AssertionError: RoMaD mismatch: OLD=11.52, NEW=inf
```

**Cause:** Division by zero (max_drawdown_pct = 0)

**Solution:**
```python
# In calculate_advanced():
if basic.max_drawdown_pct > 0:
    romad = basic.net_profit_pct / basic.max_drawdown_pct
else:
    romad = None  # Or float('inf') if that matches OLD behavior
```

---

## Success Criteria Summary

Phase 4 is complete when:

1. ✅ **All parity tests passing** - OLD vs NEW bit-exact match
2. ✅ **Regression baseline maintained** - Net Profit 230.75%, Trades 93
3. ✅ **All tests passing** - Full test suite green
4. ✅ **Optuna working** - Optimization produces reasonable scores
5. ✅ **UI working** - Metrics display correctly
6. ✅ **OLD code deleted** - backtest_engine.py cleaner
7. ✅ **Performance maintained** - No degradation
8. ✅ **Clean git commit** - With tag `phase-4-complete`

---

## Next Steps After Phase 4

Once Phase 4 is complete and validated, proceed to:

**Phase 5: Indicators Package Extraction**
- Complexity: 🔴 HIGH
- Risk: 🔴 HIGH
- Estimated Effort: 10-14 hours

Phase 5 will extract all indicators from `backtest_engine.py` into separate `indicators/` package while preserving exact calculation behavior for all 11 MA types.

---

## Quick Reference Commands

```bash
# ============================================================================
# Testing
# ============================================================================

# Run metrics parity tests
pytest tests/test_metrics.py -v

# Run regression tests
pytest tests/test_regression_s01.py -v -m regression

# Run full test suite
pytest tests/ -v

# Test Optuna optimization
python tools/test_optuna_phase4.py

# Benchmark performance
python tools/benchmark_metrics.py

# ============================================================================
# Verification
# ============================================================================

# Check for OLD function references (should find NOTHING)
grep -r "calculate_monthly_returns\|calculate_profit_factor\|calculate_advanced_metrics" src/core/backtest_engine.py

# Verify NEW functions exist
grep -n "def calculate_basic\|def calculate_advanced" src/core/metrics.py

# Check imports
grep -n "from.*metrics import" src/core/*.py

# ============================================================================
# Git
# ============================================================================

# Stage changes
git add src/core/metrics.py src/core/*.py tests/test_metrics.py

# Commit
git commit -m "Phase 4: Extract metrics to metrics.py"

# Tag
git tag phase-4-complete

# Verify
git log -1 --stat
git show phase-4-complete
```

---

**End of Phase 4 Prompt**

**Total Length:** ~20 KB
**Target Audience:** GPT 5.1 Codex
**Expected Execution Time:** 8-12 hours
**Risk Level:** 🔴 HIGH (requires bit-exact compatibility)

**Key Success Metric:** All metrics calculations produce bit-exact identical results to OLD implementation, with regression baseline maintained (Net Profit: 230.75%, Max DD: 20.03%, Trades: 93).
