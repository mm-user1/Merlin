# Phase 7: S01 Strategy Migration - Task Prompt

**Phase:** 7 of 11
**Complexity:** 🔴 VERY HIGH
**Risk:** 🔴 VERY HIGH
**Estimated Effort:** 16-24 hours
**Priority:** 🚨 HIGHEST RISK PHASE
**Status:** Ready for Execution

---

## Table of Contents

1. [Project Context](#project-context)
2. [Phase 7 Objective](#phase-7-objective)
3. [Why This Is Highest Risk](#why-this-is-highest-risk)
4. [Current vs Target Architecture](#current-vs-target-architecture)
5. [S01 Strategy Logic Overview](#s01-strategy-logic-overview)
6. [Implementation Requirements](#implementation-requirements)
7. [Detailed Implementation Guide](#detailed-implementation-guide)
8. [Testing Strategy](#testing-strategy)
9. [Validation Checklist](#validation-checklist)
10. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
11. [Success Criteria](#success-criteria)

---

## Project Context

You are working on a cryptocurrency/forex trading strategy backtesting platform that is undergoing a major architecture migration. The project has already completed 6 phases of migration:

### Completed Phases

- ✅ **Phase -1**: Test Infrastructure Setup (9 tests passing)
- ✅ **Phase 0**: Regression Baseline for S01 (12 regression tests)
- ✅ **Phase 1**: Core Extraction to `src/core/`
- ✅ **Phase 2**: Export Extraction to `export.py`
- ✅ **Phase 3**: Grid Search Removal (Optuna-only)
- ✅ **Phase 4**: Metrics Extraction to `metrics.py`
- ✅ **Phase 5**: Indicators Package Extraction
- ✅ **Phase 6**: S04 StochRSI Strategy (architecture validation)

### Current Architecture State

**Core engines**:
- `src/core/backtest_engine.py` - Main backtest engine
- `src/core/optuna_engine.py` - Bayesian optimization engine
- `src/core/walkforward_engine.py` - Walk-forward analysis

**Utilities**:
- `src/core/metrics.py` - Metrics calculation
- `src/core/export.py` - Results export

**Domain layers**:
- `src/indicators/` - Technical indicators (11 MA types, ATR, RSI, StochRSI)
- `src/strategies/` - Strategy implementations

**Interface**:
- `src/ui/` - Flask server + web UI (dynamic parameter loading)

### Test Suite Status

- **Total Tests**: 58 passing
- **Regression Tests**: 12 passing (validates S01 baseline)
- **S04 Tests**: 4 passing (validates new architecture)
- **Core Tests**: 42 passing (infrastructure)

---

## Phase 7 Objective

**Goal**: Migrate the S01 Trailing MA strategy from legacy architecture to the new clean architecture while ensuring **bit-exact** compatibility with the existing implementation.

**Strategy**: Use a "duplicate and validate" approach where:
1. Legacy S01 stays in `src/strategies/s01_trailing_ma/` (unchanged)
2. Migrated S01 created in `src/strategies/s01_trailing_ma_migrated/`
3. After validation, migrated version becomes production

**Success Criteria**:
1. ✅ Migrated strategy produces **bit-exact** results (tolerance < 1e-6)
2. ✅ All 93 trades match exactly (timing, prices, PnL)
3. ✅ Net profit: 230.75% (baseline match)
4. ✅ Max drawdown: 20.03% (baseline match)
5. ✅ All 11 MA types tested and validated
6. ✅ Comprehensive test suite passes (20+ tests)

---

## Why This Is Highest Risk

Phase 7 is the most critical and risky phase of the entire migration for these reasons:

### 1. Complexity of S01 Strategy

The S01 strategy is the most complex strategy in the system:

- **11 MA types**: EMA, SMA, HMA, WMA, ALMA, KAMA, TMA, T3, DEMA, VWMA, VWAP
- **Close count logic**: Separate counters for long/short entries
- **ATR-based position sizing**: Risk-based calculation with contract size rounding
- **Multiple stop types**:
  - ATR-based stops (with lookback periods)
  - Max percentage stops
  - Max days stops
- **Trailing exit system**:
  - RR-based activation
  - Separate long/short trailing MAs with different types
  - Offset adjustments (percentage-based)
- **Position management**: Entry/exit commission handling, PnL calculation

### 2. Large Codebase to Migrate

The `run_strategy()` function in `backtest_engine.py` is **~300 lines** of S01-specific logic that must be:
- Extracted completely
- Refactored to use indicators package
- Encapsulated in strategy class
- Validated for exact behavior match

### 3. Zero Tolerance for Deviation

Unlike most software migrations where "close enough" is acceptable, this migration requires:
- **Bit-exact match** with tolerance < 1e-6
- **Every single trade** must match (entry time, exit time, prices, PnL)
- **Any deviation** means the migration has failed

### 4. Production System at Stake

S01 is the production strategy that users depend on:
- Users have optimized parameters
- Users have historical results they compare against
- Any behavior change breaks trust and usability

### 5. Complexity of State Management

The strategy maintains complex state across bars:
- Position state (long/short/flat)
- Counter state (trend counters, trade counters)
- Trail state (activated flags, trail prices)
- Entry state (entry prices, stop prices, target prices, commissions)

One mistake in state management creates divergence that compounds.

---

## Current vs Target Architecture

### Current Architecture (Legacy)

**File**: `src/strategies/s01_trailing_ma/strategy.py` (45 lines)

```python
class S01TrailingMA(BaseStrategy):
    STRATEGY_ID = "s01_trailing_ma"
    STRATEGY_NAME = "S01 Trailing MA"
    STRATEGY_VERSION = "v26"

    @staticmethod
    def run(df: pd.DataFrame, params: Dict[str, Any], trade_start_idx: int = 0) -> StrategyResult:
        """
        Execute S01 Trailing MA strategy via the legacy backtest engine implementation.
        """
        parsed_params = StrategyParams.from_dict(params)
        return run_strategy(df, parsed_params, trade_start_idx)  # ← Delegates to engine!
```

**File**: `src/core/backtest_engine.py` (lines 381-687, ~307 lines)

```python
def run_strategy(df: pd.DataFrame, params: StrategyParams, trade_start_idx: int = 0) -> StrategyResult:
    """
    This function contains ALL the S01-specific logic:
    - Calculate MAs, ATR, trailing MAs (with 11 MA types)
    - Bar-by-bar simulation with close count logic
    - Entry conditions (trend detection based on close counts)
    - Position sizing (risk-based with ATR and contract size)
    - Stop management (ATR-based, max %, max days)
    - Trail management (RR activation, separate long/short trailing MAs)
    - Exit conditions (stops, targets, trails, max days)
    - Commission handling
    - PnL calculation
    - Equity/balance curve generation
    """
    # ~300 lines of S01-specific implementation...
```

**Problem**:
- Strategy logic is in the core engine (violates separation of concerns)
- StrategyParams is in backtest_engine.py (should be in strategy)
- Can't add new strategies without modifying core engine
- Core engine is tightly coupled to S01

### Target Architecture (Clean)

**File**: `src/strategies/s01_trailing_ma_migrated/strategy.py`

```python
@dataclass
class S01Params:
    """
    S01 strategy parameters - lives INSIDE the strategy module.
    This is the target architecture: each strategy owns its params.
    """
    # Main MA
    ma_type: str = "HMA"
    ma_length: int = 50

    # Trailing MAs
    trail_ma_long_type: str = "HMA"
    trail_ma_long_length: int = 30
    trail_ma_long_offset: float = 0.0
    trail_ma_short_type: str = "HMA"
    trail_ma_short_length: int = 30
    trail_ma_short_offset: float = 0.0

    # Entry logic
    close_count_long: int = 3
    close_count_short: int = 3

    # Position sizing
    risk_per_trade_pct: float = 2.0
    contract_size: float = 0.01
    commission_rate: float = 0.0005

    # Stops (ATR-based)
    atr_period: int = 14
    stop_long_atr: float = 2.0
    stop_long_rr: float = 3.0
    stop_long_lp: int = 2
    stop_short_atr: float = 2.0
    stop_short_rr: float = 3.0
    stop_short_lp: int = 2

    # Stops (max %)
    stop_long_max_pct: float = 5.0
    stop_short_max_pct: float = 5.0

    # Stops (max days)
    stop_long_max_days: int = 30
    stop_short_max_days: int = 30

    # Trailing exits
    trail_rr_long: float = 1.0
    trail_rr_short: float = 1.0

    # Date filter
    use_date_filter: bool = True
    use_backtester: bool = True

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "S01Params":
        """Parse from frontend/API payload with camelCase mapping"""
        return S01Params(
            ma_type=d.get('maType', 'HMA'),
            ma_length=int(d.get('maLength', 50)),
            trail_ma_long_type=d.get('trailLongType', 'HMA'),
            trail_ma_long_length=int(d.get('trailLongLength', 30)),
            trail_ma_long_offset=float(d.get('trailLongOffset', 0.0)),
            trail_ma_short_type=d.get('trailShortType', 'HMA'),
            trail_ma_short_length=int(d.get('trailShortLength', 30)),
            trail_ma_short_offset=float(d.get('trailShortOffset', 0.0)),
            close_count_long=int(d.get('closeCountLong', 3)),
            close_count_short=int(d.get('closeCountShort', 3)),
            risk_per_trade_pct=float(d.get('riskPerTrade', 2.0)),
            contract_size=float(d.get('contractSize', 0.01)),
            commission_rate=float(d.get('commissionRate', 0.0005)),
            atr_period=int(d.get('atrPeriod', 14)),
            stop_long_atr=float(d.get('stopLongX', 2.0)),
            stop_long_rr=float(d.get('stopLongRR', 3.0)),
            stop_long_lp=int(d.get('stopLongLP', 2)),
            stop_short_atr=float(d.get('stopShortX', 2.0)),
            stop_short_rr=float(d.get('stopShortRR', 3.0)),
            stop_short_lp=int(d.get('stopShortLP', 2)),
            stop_long_max_pct=float(d.get('stopLongMaxPct', 5.0)),
            stop_short_max_pct=float(d.get('stopShortMaxPct', 5.0)),
            stop_long_max_days=int(d.get('stopLongMaxDays', 30)),
            stop_short_max_days=int(d.get('stopShortMaxDays', 30)),
            trail_rr_long=float(d.get('trailRRLong', 1.0)),
            trail_rr_short=float(d.get('trailRRShort', 1.0)),
            use_date_filter=bool(d.get('dateFilter', True)),
            use_backtester=bool(d.get('backtester', True)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            'maType': self.ma_type,
            'maLength': self.ma_length,
            'trailLongType': self.trail_ma_long_type,
            'trailLongLength': self.trail_ma_long_length,
            'trailLongOffset': self.trail_ma_long_offset,
            'trailShortType': self.trail_ma_short_type,
            'trailShortLength': self.trail_ma_short_length,
            'trailShortOffset': self.trail_ma_short_offset,
            'closeCountLong': self.close_count_long,
            'closeCountShort': self.close_count_short,
            'riskPerTrade': self.risk_per_trade_pct,
            'contractSize': self.contract_size,
            'commissionRate': self.commission_rate,
            'atrPeriod': self.atr_period,
            'stopLongX': self.stop_long_atr,
            'stopLongRR': self.stop_long_rr,
            'stopLongLP': self.stop_long_lp,
            'stopShortX': self.stop_short_atr,
            'stopShortRR': self.stop_short_rr,
            'stopShortLP': self.stop_short_lp,
            'stopLongMaxPct': self.stop_long_max_pct,
            'stopShortMaxPct': self.stop_short_max_pct,
            'stopLongMaxDays': self.stop_long_max_days,
            'stopShortMaxDays': self.stop_short_max_days,
            'trailRRLong': self.trail_rr_long,
            'trailRRShort': self.trail_rr_short,
            'dateFilter': self.use_date_filter,
            'backtester': self.use_backtester,
        }


class S01TrailingMAMigrated(BaseStrategy):
    STRATEGY_ID = "s01_trailing_ma_migrated"
    STRATEGY_NAME = "S01 Trailing MA Migrated"
    STRATEGY_VERSION = "v26"

    @staticmethod
    def run(df: pd.DataFrame, params: Dict[str, Any], trade_start_idx: int = 0) -> StrategyResult:
        """
        Execute S01 Trailing MA strategy with self-contained logic.
        All logic from run_strategy() moved here.
        """
        p = S01Params.from_dict(params)

        # ALL strategy logic implemented here:
        # - Indicator calculations using indicators package
        # - Bar-by-bar simulation
        # - Entry/exit logic
        # - Position management
        # - Commission handling
        # - Result assembly

        # ~300 lines of implementation...
```

**Benefits**:
- ✅ Strategy owns its parameters
- ✅ Strategy encapsulates its logic
- ✅ Core engine is generic (no S01-specific code)
- ✅ Easy to add new strategies
- ✅ Clear separation of concerns

---

## S01 Strategy Logic Overview

Understanding the complete logic is critical for accurate migration. Here's a comprehensive breakdown:

### Entry Logic: Close Count Trend Detection

The strategy enters positions based on how many consecutive closes are above/below the MA:

```python
# Long Entry Conditions:
# 1. Close > MA for closeCountLong consecutive bars (e.g., 7 bars)
# 2. Not already in a long position
# 3. Within trading date range
# 4. ATR is valid (not NaN)
# 5. Lowest low over stopLongLP periods is valid

# Short Entry Conditions:
# 1. Close < MA for closeCountShort consecutive bars (e.g., 5 bars)
# 2. Not already in a short position
# 3. Within trading date range
# 4. ATR is valid (not NaN)
# 5. Highest high over stopShortLP periods is valid

# Implementation pattern:
counter_close_trend_long = 0
counter_close_trend_short = 0

for each bar:
    if close > ma:
        counter_close_trend_long += 1
        counter_close_trend_short = 0
    elif close < ma:
        counter_close_trend_short += 1
        counter_close_trend_long = 0
    else:
        counter_close_trend_long = 0
        counter_close_trend_short = 0

    # Entry signals
    up_trend = (counter_close_trend_long >= close_count_long) and (counter_trade_long == 0)
    down_trend = (counter_close_trend_short >= close_count_short) and (counter_trade_short == 0)
```

### Position Sizing: Risk-Based with ATR

Position size is calculated based on:
1. Risk amount (% of current equity)
2. Stop distance (ATR-based)
3. Contract size rounding

```python
# Long Position Sizing:
# 1. Calculate stop distance
stop_size = atr * stop_long_atr  # e.g., ATR * 2.0
long_stop_price = lowest_low - stop_size
long_stop_distance = close - long_stop_price

# 2. Calculate raw position size
risk_cash = realized_equity * (risk_per_trade_pct / 100)
raw_qty = risk_cash / long_stop_distance

# 3. Round to contract size
if contract_size > 0:
    qty = floor(raw_qty / contract_size) * contract_size

# 4. Verify stop percentage constraint
long_stop_pct = (long_stop_distance / close) * 100
if long_stop_pct <= stop_long_max_pct or stop_long_max_pct <= 0:
    # Open position
    position = 1
    position_size = qty
    entry_price = close
    stop_price = long_stop_price
    target_price = close + long_stop_distance * stop_long_rr

    # Deduct entry commission from balance
    entry_commission = entry_price * position_size * commission_rate
    realized_equity -= entry_commission
```

### Stop Management: Three Types

**1. ATR-Based Stops**:
```python
# Long: Stop below lowest low - ATR buffer
stop_size = atr * stop_long_atr
long_stop_price = lowest_low - stop_size

# Short: Stop above highest high + ATR buffer
stop_size = atr * stop_short_atr
short_stop_price = highest_high + stop_size
```

**2. Max Percentage Stops**:
```python
# Check if stop distance exceeds max %
long_stop_pct = (long_stop_distance / close) * 100
if long_stop_pct > stop_long_max_pct:
    # Don't enter position
    skip_entry = True
```

**3. Max Days Stops**:
```python
# Exit if position held too long
if entry_time_long is not None and stop_long_max_days > 0:
    days_in_trade = floor((current_time - entry_time_long).total_seconds() / 86400)
    if days_in_trade >= stop_long_max_days:
        exit_price = close
        # Close position at market
```

### Trailing Exit System

The most complex part of S01 - a two-stage trailing system:

**Stage 1: Activation (RR-based)**:
```python
# Long Trail Activation:
# When price reaches: entry_price + (entry_price - stop_price) * trail_rr_long
# Example: If RR = 1.0, activates when profit equals initial risk

if not trail_activated_long:
    activation_price = entry_price + (entry_price - stop_price) * trail_rr_long
    if high >= activation_price:
        trail_activated_long = True
        trail_price_long = stop_price  # Initialize at stop price
```

**Stage 2: Trailing (MA-based)**:
```python
# After activation, trail using MA value
if trail_activated_long:
    # Calculate trailing MA
    trail_ma_long_value = get_ma(close, trail_ma_long_type, trail_ma_long_length, ...)

    # Apply offset (percentage)
    trail_ma_long_value = trail_ma_long_value * (1 + trail_ma_long_offset / 100)

    # Update trail price (only move up for longs)
    if trail_ma_long_value > trail_price_long:
        trail_price_long = trail_ma_long_value

    # Exit if price crosses below trail
    if low <= trail_price_long:
        exit_price = trail_price_long if trail_price_long <= high else high
        # Close position
```

**Key Details**:
- Separate trail types for long/short (can be different MA types)
- Separate trail lengths for long/short
- Separate trail offsets for long/short (% adjustment)
- Trail only moves in favorable direction (up for longs, down for shorts)

### Exit Logic Priority Order

When in a position, exits are checked in this order:

```python
# For Long Positions:
if trail_activated_long:
    # 1. Trail exit (if trail activated)
    if low <= trail_price_long:
        exit_at_trail_price()
else:
    # 2. Stop loss
    if low <= stop_price:
        exit_at_stop_price()
    # 3. Target (RR-based)
    elif high >= target_price:
        exit_at_target_price()

# 4. Max days (checked regardless of trail activation)
if days_in_trade >= stop_long_max_days:
    exit_at_market()

# Similar logic for short positions (inverted)
```

### Commission Handling

Commissions are applied at both entry and exit:

```python
# Entry:
entry_commission = entry_price * position_size * commission_rate
realized_equity -= entry_commission  # Deducted from balance immediately

# Exit:
exit_commission = exit_price * position_size * commission_rate
gross_pnl = (exit_price - entry_price) * position_size  # For longs
net_pnl = gross_pnl - exit_commission - entry_commission
realized_equity += gross_pnl - exit_commission
```

### Equity vs Balance Curves

Two separate curves are maintained:

```python
# Balance (realized): Only updates on trade close
realized_curve.append(realized_equity)

# Equity (mark-to-market): Updates every bar
mark_to_market = realized_equity
if position > 0:
    mark_to_market += (close - entry_price) * position_size
elif position < 0:
    mark_to_market += (entry_price - close) * position_size
mtm_curve.append(mark_to_market)
```

---

## Implementation Requirements

### 1. Directory Structure

Create the new strategy folder with all required files:

```bash
mkdir -p src/strategies/s01_trailing_ma_migrated
touch src/strategies/s01_trailing_ma_migrated/__init__.py
touch src/strategies/s01_trailing_ma_migrated/strategy.py
```

### 2. Copy Configuration

Copy the existing config.json (it's already correct):

```bash
cp src/strategies/s01_trailing_ma/config.json \
   src/strategies/s01_trailing_ma_migrated/config.json
```

**Update the strategy ID in config.json**:
```json
{
  "id": "s01_trailing_ma_migrated",
  "name": "S01 Trailing MA Migrated",
  "version": "v26",
  ...
}
```

### 3. Required Imports

Your strategy.py will need these imports:

```python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import math

import numpy as np
import pandas as pd

from core import metrics
from core.backtest_engine import StrategyResult, TradeRecord
from indicators.ma import get_ma
from indicators.volatility import atr
from strategies.base import BaseStrategy
```

### 4. Parameter Dataclass

The S01Params dataclass must include ALL parameters. See the complete definition in the "Target Architecture" section above.

**Critical camelCase Mapping**:

Frontend sends camelCase (e.g., `maLength`), backend uses snake_case (e.g., `ma_length`). The `from_dict()` method handles this conversion.

### 5. Strategy Class

The strategy class must:
- Inherit from `BaseStrategy`
- Define `STRATEGY_ID`, `STRATEGY_NAME`, `STRATEGY_VERSION`
- Implement `run(df, params, trade_start_idx)` method
- Return `StrategyResult` with all required fields

---

## Detailed Implementation Guide

### Step 1: Create S01Params Dataclass (2-3 hours)

**File**: `src/strategies/s01_trailing_ma_migrated/strategy.py`

1. **Define all parameters** (see complete definition in "Target Architecture" section)
2. **Implement `from_dict()`** - Handle camelCase to snake_case mapping
3. **Implement `to_dict()`** - Handle snake_case to camelCase mapping
4. **Add default values** - Match config.json defaults

**Testing**:
```python
# Test parameter parsing
params_dict = {
    'maType': 'EMA',
    'maLength': 50,
    'closeCountLong': 7,
    # ... all other parameters
}
p = S01Params.from_dict(params_dict)
assert p.ma_type == 'EMA'
assert p.ma_length == 50
assert p.close_count_long == 7

# Test round-trip
params_dict_2 = p.to_dict()
assert params_dict == params_dict_2
```

### Step 2: Copy run_strategy() Logic (2-4 hours)

**Goal**: Create an exact copy of `run_strategy()` inside the strategy class.

**Strategy**:
1. Copy lines 381-687 from `backtest_engine.py`
2. Paste into `S01TrailingMAMigrated.run()` method
3. Rename `params` to `p` (consistent with S04)
4. Replace `params.xxx` with `p.xxx`
5. Run comparison test

**Expected Result**: Should produce IDENTICAL results since it's an exact copy.

```python
class S01TrailingMAMigrated(BaseStrategy):
    STRATEGY_ID = "s01_trailing_ma_migrated"
    STRATEGY_NAME = "S01 Trailing MA Migrated"
    STRATEGY_VERSION = "v26"

    @staticmethod
    def run(df: pd.DataFrame, params: Dict[str, Any], trade_start_idx: int = 0) -> StrategyResult:
        """Execute S01 Trailing MA strategy with self-contained logic."""
        p = S01Params.from_dict(params)

        # PASTE THE ENTIRE run_strategy() FUNCTION BODY HERE
        # Lines 382-687 from backtest_engine.py

        if p.use_backtester is False:
            raise ValueError("Backtester is disabled in the provided parameters")

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        # ... rest of implementation (exact copy)
```

**Comparison Test**:
```python
def test_step2_exact_copy():
    """After step 2, results should be identical (exact copy)"""
    df = load_baseline_data()
    params = load_baseline_params()

    # Run legacy
    legacy_result = S01TrailingMA.run(df, params, trade_start_idx=0)

    # Run migrated (exact copy)
    migrated_result = S01TrailingMAMigrated.run(df, params, trade_start_idx=0)

    # Should be IDENTICAL
    assert legacy_result.net_profit_pct == migrated_result.net_profit_pct
    assert legacy_result.total_trades == migrated_result.total_trades
    assert len(legacy_result.trades) == len(migrated_result.trades)
```

### Step 3: Replace Indicator Calculations (4-6 hours)

**Goal**: Replace inline indicator calculations with calls to the indicators package.

**Why This Step**: The indicators package was extracted in Phase 5 and validated to produce bit-exact results. We TRUST these implementations.

**Strategy**: Replace each indicator calculation ONE AT A TIME, testing after each replacement.

#### 3.1: Replace MA Calculation

**OLD (inline in run_strategy)**:
```python
# Lines 390, 395-396 in backtest_engine.py
ma_series = get_ma(close, params.ma_type, params.ma_length, volume, high, low)
trail_ma_long = get_ma(close, params.trail_ma_long_type, params.trail_ma_long_length, volume, high, low)
trail_ma_short = get_ma(close, params.trail_ma_short_type, params.trail_ma_short_length, volume, high, low)
```

**NEW (using indicators package)**:
```python
from indicators.ma import get_ma

ma_series = get_ma(close, p.ma_type, p.ma_length, volume, high, low)
trail_ma_long = get_ma(close, p.trail_ma_long_type, p.trail_ma_long_length, volume, high, low)
trail_ma_short = get_ma(close, p.trail_ma_short_type, p.trail_ma_short_length, volume, high, low)
```

**Note**: `get_ma()` already exists in `indicators.ma` and is bit-exact compatible with the original.

**Test**:
```python
def test_step3_1_ma_calculation():
    """MA calculations should still match after using indicators package"""
    # Run test and verify results still match
    assert_results_match(legacy, migrated)
```

#### 3.2: Replace ATR Calculation

**OLD**:
```python
atr_series = atr(high, low, close, params.atr_period)
```

**NEW**:
```python
from indicators.volatility import atr

atr_series = atr(high, low, close, p.atr_period)
```

**Test**:
```python
def test_step3_2_atr_calculation():
    """ATR calculations should still match after using indicators package"""
    assert_results_match(legacy, migrated)
```

#### 3.3: Replace Rolling Min/Max

**OLD**:
```python
lowest_long = low.rolling(params.stop_long_lp, min_periods=1).min()
highest_short = high.rolling(params.stop_short_lp, min_periods=1).max()
```

**NEW**:
```python
lowest_long = low.rolling(p.stop_long_lp, min_periods=1).min()
highest_short = high.rolling(p.stop_short_lp, min_periods=1).max()
```

**Test**:
```python
def test_step3_3_rolling_calculations():
    """Rolling min/max should still match"""
    assert_results_match(legacy, migrated)
```

#### 3.4: Apply Trail Offsets

**OLD**:
```python
if params.trail_ma_long_length > 0:
    trail_ma_long = trail_ma_long * (1 + params.trail_ma_long_offset / 100.0)
if params.trail_ma_short_length > 0:
    trail_ma_short = trail_ma_short * (1 + params.trail_ma_short_offset / 100.0)
```

**NEW**:
```python
if p.trail_ma_long_length > 0:
    trail_ma_long = trail_ma_long * (1 + p.trail_ma_long_offset / 100.0)
if p.trail_ma_short_length > 0:
    trail_ma_short = trail_ma_short * (1 + p.trail_ma_short_offset / 100.0)
```

**Test**:
```python
def test_step3_4_trail_offsets():
    """Trail offset application should still match"""
    assert_results_match(legacy, migrated)
```

**Verification After Step 3**:
After ALL replacements, run full comparison test:
```python
def test_step3_final_all_indicators_replaced():
    """After replacing all indicators, results should STILL match exactly"""
    df = load_baseline_data()
    params = load_baseline_params()

    legacy_result = S01TrailingMA.run(df, params, trade_start_idx=0)
    migrated_result = S01TrailingMAMigrated.run(df, params, trade_start_idx=0)

    # MUST be bit-exact
    assert abs(legacy_result.net_profit_pct - migrated_result.net_profit_pct) < 1e-6
    assert legacy_result.total_trades == migrated_result.total_trades

    # Check ALL trades match
    for i, (t1, t2) in enumerate(zip(legacy_result.trades, migrated_result.trades)):
        assert t1.entry_time == t2.entry_time, f"Trade {i} entry time mismatch"
        assert t1.exit_time == t2.exit_time, f"Trade {i} exit time mismatch"
        assert abs(t1.entry_price - t2.entry_price) < 1e-6, f"Trade {i} entry price mismatch"
        assert abs(t1.exit_price - t2.exit_price) < 1e-6, f"Trade {i} exit price mismatch"
        assert abs(t1.net_pnl - t2.net_pnl) < 1e-6, f"Trade {i} PnL mismatch"
```

### Step 4: Optional Refactoring (2-3 hours)

**Goal**: Improve code organization WITHOUT changing behavior.

**Warning**: This step is OPTIONAL. Only proceed if you're confident in your changes and can validate each refactor.

#### 4.1: Extract Indicator Calculation Method

```python
class S01TrailingMAMigrated(BaseStrategy):
    # ...

    @staticmethod
    def _calculate_indicators(df: pd.DataFrame, p: S01Params) -> Dict[str, pd.Series]:
        """Calculate all indicators needed for the strategy."""
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        indicators = {}
        indicators['ma'] = get_ma(close, p.ma_type, p.ma_length, volume, high, low)
        indicators['atr'] = atr(high, low, close, p.atr_period)
        indicators['lowest_long'] = low.rolling(p.stop_long_lp, min_periods=1).min()
        indicators['highest_short'] = high.rolling(p.stop_short_lp, min_periods=1).max()

        indicators['trail_ma_long'] = get_ma(close, p.trail_ma_long_type, p.trail_ma_long_length, volume, high, low)
        indicators['trail_ma_short'] = get_ma(close, p.trail_ma_short_type, p.trail_ma_short_length, volume, high, low)

        if p.trail_ma_long_length > 0:
            indicators['trail_ma_long'] = indicators['trail_ma_long'] * (1 + p.trail_ma_long_offset / 100.0)
        if p.trail_ma_short_length > 0:
            indicators['trail_ma_short'] = indicators['trail_ma_short'] * (1 + p.trail_ma_short_offset / 100.0)

        return indicators
```

**Test After Refactor**:
```python
def test_step4_1_indicator_extraction():
    """After extracting indicator calculation, results should still match"""
    assert_results_match(legacy, migrated)
```

#### 4.2: Extract Position Entry Logic

```python
@staticmethod
def _check_long_entry(
    close: float,
    atr_val: float,
    lowest_val: float,
    realized_equity: float,
    p: S01Params
) -> Optional[Dict[str, Any]]:
    """
    Check if long entry conditions are met and calculate position details.

    Returns:
        Dict with entry details if entry is valid, None otherwise.
    """
    stop_size = atr_val * p.stop_long_atr
    long_stop_price = lowest_val - stop_size
    long_stop_distance = close - long_stop_price

    if long_stop_distance <= 0:
        return None

    long_stop_pct = (long_stop_distance / close) * 100
    if p.stop_long_max_pct > 0 and long_stop_pct > p.stop_long_max_pct:
        return None

    risk_cash = realized_equity * (p.risk_per_trade_pct / 100)
    qty = risk_cash / long_stop_distance

    if p.contract_size > 0:
        qty = math.floor(qty / p.contract_size) * p.contract_size

    if qty <= 0:
        return None

    target_price = close + long_stop_distance * p.stop_long_rr

    return {
        'position_size': qty,
        'entry_price': close,
        'stop_price': long_stop_price,
        'target_price': target_price,
        'trail_price': long_stop_price,
    }
```

**Test After Refactor**:
```python
def test_step4_2_entry_logic_extraction():
    """After extracting entry logic, results should still match"""
    assert_results_match(legacy, migrated)
```

#### 4.3: Extract Position Exit Logic

Similar pattern for exit logic. See the implementation pattern above.

**Test After Each Refactor**:
```python
def test_step4_final_all_refactoring_complete():
    """After all refactoring, results should STILL match exactly"""
    assert_results_match(legacy, migrated)
```

### Step 5: Final Validation (2-4 hours)

**Goal**: Comprehensive testing across multiple scenarios.

#### 5.1: Baseline Test (MUST PASS)

```python
def test_final_baseline_match():
    """
    Test with baseline parameters.
    Expected:
    - Net Profit: 230.75%
    - Max Drawdown: 20.03%
    - Total Trades: 93
    """
    df = load_baseline_data()
    params = load_baseline_params()

    result = S01TrailingMAMigrated.run(df, params, trade_start_idx=0)

    # Calculate metrics
    basic = metrics.calculate_basic(result)

    # MUST match baseline exactly
    assert abs(basic.net_profit_pct - 230.75) < 1e-6
    assert abs(basic.max_drawdown_pct - 20.03) < 0.01
    assert basic.total_trades == 93
```

#### 5.2: MA Type Tests (MUST PASS ALL)

Test with all 11 MA types:

```python
@pytest.mark.parametrize("ma_type", [
    "SMA", "EMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"
])
def test_final_ma_type_compatibility(ma_type):
    """Test migrated strategy with all 11 MA types"""
    df = load_baseline_data()
    params = load_baseline_params()
    params['maType'] = ma_type
    params['trailLongType'] = ma_type
    params['trailShortType'] = ma_type

    # Run legacy
    legacy_result = S01TrailingMA.run(df, params, trade_start_idx=0)

    # Run migrated
    migrated_result = S01TrailingMAMigrated.run(df, params, trade_start_idx=0)

    # MUST match exactly
    assert abs(legacy_result.net_profit_pct - migrated_result.net_profit_pct) < 1e-6
    assert legacy_result.total_trades == migrated_result.total_trades
```

#### 5.3: Parameter Variation Tests

Test with different parameter combinations:

```python
def test_final_parameter_variations():
    """Test with various parameter combinations"""
    df = load_baseline_data()

    param_sets = [
        # Conservative
        {'closeCountLong': 10, 'closeCountShort': 10, 'stopLongX': 3.0, 'stopShortX': 3.0},
        # Aggressive
        {'closeCountLong': 3, 'closeCountShort': 3, 'stopLongX': 1.5, 'stopShortX': 1.5},
        # Asymmetric
        {'closeCountLong': 5, 'closeCountShort': 7, 'stopLongX': 2.5, 'stopShortX': 1.8},
    ]

    for param_overrides in param_sets:
        params = load_baseline_params()
        params.update(param_overrides)

        legacy_result = S01TrailingMA.run(df, params)
        migrated_result = S01TrailingMAMigrated.run(df, params)

        # MUST match exactly
        assert abs(legacy_result.net_profit_pct - migrated_result.net_profit_pct) < 1e-6
```

#### 5.4: Edge Case Tests

```python
def test_final_edge_cases():
    """Test edge cases"""
    df = load_baseline_data()

    # Edge case 1: Very short MA
    params = load_baseline_params()
    params['maLength'] = 5
    legacy = S01TrailingMA.run(df, params)
    migrated = S01TrailingMAMigrated.run(df, params)
    assert abs(legacy.net_profit_pct - migrated.net_profit_pct) < 1e-6

    # Edge case 2: Very long MA
    params['maLength'] = 500
    legacy = S01TrailingMA.run(df, params)
    migrated = S01TrailingMAMigrated.run(df, params)
    assert abs(legacy.net_profit_pct - migrated.net_profit_pct) < 1e-6

    # Edge case 3: No trailing
    params['trailRRLong'] = 999.0  # Never activates
    params['trailRRShort'] = 999.0
    legacy = S01TrailingMA.run(df, params)
    migrated = S01TrailingMAMigrated.run(df, params)
    assert abs(legacy.net_profit_pct - migrated.net_profit_pct) < 1e-6
```

---

## Testing Strategy

### Test File Structure

Create comprehensive test file:

**File**: `tests/test_s01_migration.py`

```python
import math
import pytest
import pandas as pd
import json
from pathlib import Path

from strategies.s01_trailing_ma.strategy import S01TrailingMA
from strategies.s01_trailing_ma_migrated.strategy import S01TrailingMAMigrated, S01Params
from core import metrics


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def baseline_metrics():
    """Load baseline metrics from regression baseline."""
    baseline_path = Path("data/baseline/s01_metrics.json")
    with open(baseline_path) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def test_data():
    """Load test dataset."""
    from core.backtest_engine import load_data
    csv_path = "data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
    df = load_data(csv_path)
    return df


@pytest.fixture(scope="module")
def baseline_params(baseline_metrics):
    """Extract baseline parameters."""
    return baseline_metrics["parameters"]


# ============================================================================
# Comparison Test (MOST IMPORTANT)
# ============================================================================

class TestS01Migration:
    """Tests for S01 migration validation."""

    def test_params_dataclass_from_dict(self, baseline_params):
        """Test S01Params can parse baseline parameters."""
        p = S01Params.from_dict(baseline_params)

        # Check critical parameters
        assert p.ma_type == baseline_params['maType']
        assert p.ma_length == baseline_params['maLength']
        assert p.close_count_long == baseline_params['closeCountLong']
        assert p.close_count_short == baseline_params['closeCountShort']

    def test_params_dataclass_to_dict(self, baseline_params):
        """Test S01Params can convert back to dict."""
        p = S01Params.from_dict(baseline_params)
        params_dict = p.to_dict()

        # Critical fields must match
        assert params_dict['maType'] == baseline_params['maType']
        assert params_dict['maLength'] == baseline_params['maLength']

    def test_migrated_runs_without_error(self, test_data, baseline_params):
        """Test that migrated strategy runs without errors."""
        from core.backtest_engine import prepare_dataset_with_warmup

        start_ts = pd.Timestamp(baseline_params["start"], tz="UTC")
        end_ts = pd.Timestamp(baseline_params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        result = S01TrailingMAMigrated.run(df_prepared, baseline_params, trade_start_idx)

        # Basic sanity checks
        assert result is not None
        assert isinstance(result.trades, list)
        assert len(result.equity_curve) > 0
        assert len(result.balance_curve) > 0

    def test_legacy_vs_migrated_exact_match(self, test_data, baseline_params, baseline_metrics):
        """
        THE CRITICAL TEST: Legacy and migrated MUST produce bit-exact results.

        This is the test that validates the entire migration.
        If this passes, the migration is successful.
        """
        from core.backtest_engine import prepare_dataset_with_warmup

        start_ts = pd.Timestamp(baseline_params["start"], tz="UTC")
        end_ts = pd.Timestamp(baseline_params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        # Run legacy
        legacy_result = S01TrailingMA.run(df_prepared, baseline_params, trade_start_idx)

        # Run migrated
        migrated_result = S01TrailingMAMigrated.run(df_prepared, baseline_params, trade_start_idx)

        # Compare basic metrics (MUST be bit-exact)
        assert abs(legacy_result.net_profit_pct - migrated_result.net_profit_pct) < 1e-6, \
            f"Net profit mismatch: {legacy_result.net_profit_pct} vs {migrated_result.net_profit_pct}"

        assert abs(legacy_result.max_drawdown_pct - migrated_result.max_drawdown_pct) < 1e-6, \
            f"Max DD mismatch: {legacy_result.max_drawdown_pct} vs {migrated_result.max_drawdown_pct}"

        assert legacy_result.total_trades == migrated_result.total_trades, \
            f"Total trades mismatch: {legacy_result.total_trades} vs {migrated_result.total_trades}"

        # Compare ALL trades (MUST match exactly)
        assert len(legacy_result.trades) == len(migrated_result.trades)

        for i, (t1, t2) in enumerate(zip(legacy_result.trades, migrated_result.trades)):
            assert t1.entry_time == t2.entry_time, \
                f"Trade {i}: Entry time mismatch"

            assert t1.exit_time == t2.exit_time, \
                f"Trade {i}: Exit time mismatch"

            assert abs(t1.entry_price - t2.entry_price) < 1e-6, \
                f"Trade {i}: Entry price mismatch"

            assert abs(t1.exit_price - t2.exit_price) < 1e-6, \
                f"Trade {i}: Exit price mismatch"

            assert abs(t1.net_pnl - t2.net_pnl) < 1e-6, \
                f"Trade {i}: Net PnL mismatch"

            assert t1.direction == t2.direction, \
                f"Trade {i}: Direction mismatch"

        # Compare equity curves
        assert len(legacy_result.equity_curve) == len(migrated_result.equity_curve)
        for i, (e1, e2) in enumerate(zip(legacy_result.equity_curve, migrated_result.equity_curve)):
            assert abs(e1 - e2) < 1e-6, f"Equity curve mismatch at index {i}"

        print("\n✅ MIGRATION SUCCESSFUL: Bit-exact match achieved!")
        print(f"Net Profit: {migrated_result.net_profit_pct:.2f}%")
        print(f"Max DD: {migrated_result.max_drawdown_pct:.2f}%")
        print(f"Total Trades: {migrated_result.total_trades}")


# ============================================================================
# MA Type Tests
# ============================================================================

class TestS01MigrationMATypes:
    """Test all MA types work correctly."""

    @pytest.mark.parametrize("ma_type", [
        "SMA", "EMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"
    ])
    def test_ma_type_compatibility(self, test_data, baseline_params, ma_type):
        """Test migrated strategy with each MA type."""
        from core.backtest_engine import prepare_dataset_with_warmup

        # Override MA types
        params = baseline_params.copy()
        params['maType'] = ma_type
        params['trailLongType'] = ma_type
        params['trailShortType'] = ma_type

        start_ts = pd.Timestamp(params["start"], tz="UTC")
        end_ts = pd.Timestamp(params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        # Run legacy
        legacy_result = S01TrailingMA.run(df_prepared, params, trade_start_idx)

        # Run migrated
        migrated_result = S01TrailingMAMigrated.run(df_prepared, params, trade_start_idx)

        # MUST match exactly
        assert abs(legacy_result.net_profit_pct - migrated_result.net_profit_pct) < 1e-6, \
            f"{ma_type}: Net profit mismatch"

        assert legacy_result.total_trades == migrated_result.total_trades, \
            f"{ma_type}: Total trades mismatch"


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestS01MigrationEdgeCases:
    """Test edge cases and parameter variations."""

    def test_very_short_ma(self, test_data, baseline_params):
        """Test with very short MA length."""
        from core.backtest_engine import prepare_dataset_with_warmup

        params = baseline_params.copy()
        params['maLength'] = 5

        start_ts = pd.Timestamp(params["start"], tz="UTC")
        end_ts = pd.Timestamp(params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        legacy = S01TrailingMA.run(df_prepared, params, trade_start_idx)
        migrated = S01TrailingMAMigrated.run(df_prepared, params, trade_start_idx)

        assert abs(legacy.net_profit_pct - migrated.net_profit_pct) < 1e-6

    def test_very_long_ma(self, test_data, baseline_params):
        """Test with very long MA length."""
        from core.backtest_engine import prepare_dataset_with_warmup

        params = baseline_params.copy()
        params['maLength'] = 500

        start_ts = pd.Timestamp(params["start"], tz="UTC")
        end_ts = pd.Timestamp(params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        legacy = S01TrailingMA.run(df_prepared, params, trade_start_idx)
        migrated = S01TrailingMAMigrated.run(df_prepared, params, trade_start_idx)

        assert abs(legacy.net_profit_pct - migrated.net_profit_pct) < 1e-6

    def test_no_trailing(self, test_data, baseline_params):
        """Test with trailing disabled (RR set very high)."""
        from core.backtest_engine import prepare_dataset_with_warmup

        params = baseline_params.copy()
        params['trailRRLong'] = 999.0
        params['trailRRShort'] = 999.0

        start_ts = pd.Timestamp(params["start"], tz="UTC")
        end_ts = pd.Timestamp(params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        legacy = S01TrailingMA.run(df_prepared, params, trade_start_idx)
        migrated = S01TrailingMAMigrated.run(df_prepared, params, trade_start_idx)

        assert abs(legacy.net_profit_pct - migrated.net_profit_pct) < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
```

---

## Validation Checklist

Use this checklist to track progress through the migration:

### Phase 7.1: Structure Setup

- [ ] Created `src/strategies/s01_trailing_ma_migrated/` directory
- [ ] Created `__init__.py` file
- [ ] Copied and updated `config.json` with new strategy ID
- [ ] Created `strategy.py` with imports

### Phase 7.2: Parameters

- [ ] Defined S01Params dataclass with all 22+ parameters
- [ ] Implemented `from_dict()` with camelCase mapping
- [ ] Implemented `to_dict()` with snake_case mapping
- [ ] Tested parameter parsing with baseline params
- [ ] Tested round-trip conversion

### Phase 7.3: Logic Migration

- [ ] Copied `run_strategy()` body into strategy class
- [ ] Renamed parameter references (params → p)
- [ ] Test passes: exact copy produces same results
- [ ] Replaced MA calculation with `indicators.ma.get_ma()`
- [ ] Test passes: MA replacement matches
- [ ] Replaced ATR calculation with `indicators.volatility.atr()`
- [ ] Test passes: ATR replacement matches
- [ ] Replaced rolling min/max calculations
- [ ] Test passes: rolling calculations match
- [ ] Applied trail offsets correctly
- [ ] Test passes: trail offsets match

### Phase 7.4: Testing

- [ ] Created `tests/test_s01_migration.py`
- [ ] Test: Parameters parse correctly
- [ ] Test: Migrated strategy runs without errors
- [ ] Test: Legacy vs migrated exact match (CRITICAL)
- [ ] Test: All 11 MA types tested
- [ ] Test: Edge cases (short MA, long MA, no trailing)
- [ ] Test: Multiple parameter combinations
- [ ] All tests passing

### Phase 7.5: Final Validation

- [ ] Run full test suite: `pytest tests/ -v`
- [ ] All 70+ tests passing (58 existing + new S01 migration tests)
- [ ] Baseline metrics match exactly:
  - [ ] Net Profit: 230.75%
  - [ ] Max Drawdown: 20.03%
  - [ ] Total Trades: 93
- [ ] All 93 trades match (entry/exit times, prices, PnL)
- [ ] Equity curve matches exactly
- [ ] No regressions in existing tests

### Phase 7.6: Documentation

- [ ] Updated strategy.py with comprehensive docstrings
- [ ] Documented any deviations (if any)
- [ ] Added inline comments for complex logic
- [ ] Updated migration progress document

### Phase 7.7: Git Commit

- [ ] Committed changes with message: "Phase 7: S01 migration to new architecture"
- [ ] Tagged commit: `git tag phase-7-complete`
- [ ] Pushed to remote

---

## Common Pitfalls and Solutions

### Pitfall 1: Parameter Naming Mismatches

**Problem**: Frontend uses camelCase (`maLength`), backend uses snake_case (`ma_length`).

**Solution**: The `from_dict()` method handles conversion:
```python
@staticmethod
def from_dict(d: Dict[str, Any]) -> "S01Params":
    return S01Params(
        ma_length=int(d.get('maLength', 50)),  # camelCase → snake_case
        # ...
    )
```

**Test**:
```python
params_dict = {'maLength': 50}
p = S01Params.from_dict(params_dict)
assert p.ma_length == 50  # snake_case internally
```

### Pitfall 2: Math Module vs Numpy

**Problem**: Original code uses `math.nan`, `math.isnan()`, `math.floor()`.

**Solution**: Keep using `math` module for consistency:
```python
import math

entry_price = math.nan
if math.isnan(entry_price):
    # ...
qty = math.floor(raw_qty / contract_size) * contract_size
```

**DON'T** mix with numpy:
```python
# WRONG - creates inconsistency
entry_price = np.nan
if math.isnan(entry_price):  # May behave differently
```

### Pitfall 3: Rolling Window Edge Cases

**Problem**: Rolling calculations with `min_periods=1` can produce NaN for first few bars.

**Solution**: Check for NaN before using values:
```python
lowest_long = low.rolling(p.stop_long_lp, min_periods=1).min()

# In loop:
lowest_value = lowest_long.iat[i]
if not np.isnan(lowest_value):
    # Use value
```

### Pitfall 4: Index vs Position Access

**Problem**: Using `.iloc[i]` vs `.iat[i]` inconsistently.

**Solution**: Use `.iat[i]` for single scalar access (faster):
```python
# CORRECT
close_val = close.iat[i]
ma_value = ma_series.iat[i]

# SLOWER (but not wrong)
close_val = close.iloc[i]
```

### Pitfall 5: Trail Price Initialization

**Problem**: Trail price can be NaN initially.

**Solution**: Check before comparison:
```python
if not math.isnan(trail_price_long) and not np.isnan(trail_long_value):
    if np.isnan(trail_price_long) or trail_long_value > trail_price_long:
        trail_price_long = trail_long_value
```

### Pitfall 6: Commission Timing

**Problem**: Forgetting to deduct entry commission from balance.

**Solution**: Deduct entry commission immediately:
```python
# On entry
entry_commission = entry_price * position_size * p.commission_rate
realized_equity -= entry_commission  # ← Critical!

# On exit
exit_commission = exit_price * position_size * p.commission_rate
net_pnl = gross_pnl - exit_commission - entry_commission
realized_equity += gross_pnl - exit_commission
```

### Pitfall 7: Date Filter Logic

**Problem**: `trade_start_idx` defines when trading can start.

**Solution**: Respect `trade_start_idx` and `use_date_filter`:
```python
times = df.index
if p.use_date_filter:
    time_in_range = np.zeros(len(times), dtype=bool)
    time_in_range[trade_start_idx:] = True
else:
    time_in_range = np.ones(len(times), dtype=bool)

# In loop:
can_open_long = (
    up_trend and
    position == 0 and
    time_in_range[i] and  # ← Check this!
    # ... other conditions
)
```

### Pitfall 8: Max Days Calculation

**Problem**: Days calculation requires proper timestamp handling.

**Solution**: Use total_seconds() and integer division:
```python
if entry_time_long is not None and p.stop_long_max_days > 0:
    days_in_trade = int(math.floor((time - entry_time_long).total_seconds() / 86400))
    if days_in_trade >= p.stop_long_max_days:
        exit_price = c
```

### Pitfall 9: Stop Price Capping

**Problem**: Trail exit price should not exceed high (for longs).

**Solution**: Cap exit price:
```python
if trail_activated_long:
    if low <= trail_price_long:
        # Cap at high of the bar
        exit_price = h if trail_price_long > h else trail_price_long
```

### Pitfall 10: Position State Management

**Problem**: Position variables must be reset after exit.

**Solution**: Reset ALL position state:
```python
if exit_price is not None:
    # ... calculate PnL, append trade ...

    # Reset ALL state
    position = 0
    position_size = 0.0
    entry_price = math.nan
    stop_price = math.nan
    target_price = math.nan
    trail_price_long = math.nan
    trail_activated_long = False
    entry_time_long = None
    entry_commission = 0.0
```

---

## Success Criteria

Phase 7 is successful when ALL of these criteria are met:

### 1. Bit-Exact Match (CRITICAL)

```python
# Run test:
pytest tests/test_s01_migration.py::TestS01Migration::test_legacy_vs_migrated_exact_match -v

# Expected output:
# ✅ MIGRATION SUCCESSFUL: Bit-exact match achieved!
# Net Profit: 230.75%
# Max DD: 20.03%
# Total Trades: 93
# PASSED
```

**Tolerance**: < 1e-6 (effectively bit-exact)

### 2. All MA Types Work

```python
# Run test:
pytest tests/test_s01_migration.py::TestS01MigrationMATypes -v

# Expected output:
# test_ma_type_compatibility[SMA] PASSED
# test_ma_type_compatibility[EMA] PASSED
# test_ma_type_compatibility[HMA] PASSED
# ... (all 11 types)
# test_ma_type_compatibility[VWAP] PASSED
```

### 3. Edge Cases Pass

```python
# Run test:
pytest tests/test_s01_migration.py::TestS01MigrationEdgeCases -v

# Expected output:
# test_very_short_ma PASSED
# test_very_long_ma PASSED
# test_no_trailing PASSED
```

### 4. Full Test Suite Passes

```python
# Run full test suite:
pytest tests/ -v

# Expected output:
# 70+ tests passing (58 existing + new S01 migration tests)
# No failures or errors
```

### 5. Baseline Metrics Match

```python
# Verify baseline:
python tools/generate_baseline_s01.py

# Expected output:
# Net Profit: 230.75%     ✅ EXACT MATCH
# Max Drawdown: 20.03%    ✅ EXACT MATCH
# Total Trades: 93        ✅ EXACT MATCH
```

### 6. No Regressions

```python
# Run regression tests:
pytest tests/test_regression_s01.py -v -m regression

# Expected output:
# All 12 regression tests PASSED (unchanged)
```

### 7. Code Quality

- [ ] Code is readable and well-documented
- [ ] No hardcoded magic numbers (use parameters)
- [ ] No duplicated logic
- [ ] Consistent naming conventions
- [ ] Type hints where appropriate

### 8. Git Commit

- [ ] Changes committed with descriptive message
- [ ] Tagged: `git tag phase-7-complete`
- [ ] Pushed to remote

---

## Next Steps After Phase 7

After Phase 7 is complete and validated:

**DO NOT** delete legacy code yet. Legacy cleanup happens in Phase 9 after UI is fixed in Phase 8.

**Phase 8** (Next): Dynamic Optimizer + CSS Extraction
- Fix hardcoded S01 parameters in UI
- Make optimizer form dynamic (like backtest form)
- Extract CSS to separate file

**Phase 9**: Legacy Code Cleanup
- Delete legacy S01 implementation
- Promote migrated version to production
- Delete run_strategy() from backtest_engine.py

**Phase 10**: Full Frontend Separation
- Modularize JavaScript
- Separate HTML/CSS/JS

**Phase 11**: Documentation
- Update all docs to reflect migration completion

---

## Project Files Reference

### Key Files You'll Modify

- **NEW**: `src/strategies/s01_trailing_ma_migrated/strategy.py` (~400 lines)
- **NEW**: `src/strategies/s01_trailing_ma_migrated/config.json` (copy from legacy)
- **NEW**: `src/strategies/s01_trailing_ma_migrated/__init__.py` (empty)
- **NEW**: `tests/test_s01_migration.py` (~300 lines)

### Key Files You'll Read

- `src/core/backtest_engine.py` (lines 381-687: `run_strategy()`)
- `src/strategies/s01_trailing_ma/strategy.py` (legacy implementation)
- `src/strategies/s01_trailing_ma/config.json` (parameter definitions)
- `src/strategies/s04_stochrsi/strategy.py` (reference for new architecture)
- `data/baseline/s01_metrics.json` (expected results)

### Documentation

- `./docs/PROJECT_MIGRATION_PLAN_upd.md` - Full migration plan
- `./docs/PROJECT_TARGET_ARCHITECTURE.md` - Target architecture
- `./docs/PROJECT_STRUCTURE.md` - Directory structure
- `./docs/BASELINE_FIX_SUMMARY.md` - Baseline validation details

---

## Final Notes

### Time Estimates

- **Optimistic**: 16 hours
- **Realistic**: 20 hours
- **Pessimistic**: 24 hours

Break into sessions:
- Session 1 (4h): Setup + Parameters
- Session 2 (4h): Copy logic + initial test
- Session 3 (4h): Replace indicators + test
- Session 4 (4h): Final validation + edge cases
- Session 5 (4h): Buffer for debugging

### When You Get Stuck

1. **Compare line-by-line**: Use a diff tool to compare legacy vs migrated
2. **Check intermediate values**: Add logging to compare MA values, ATR values, etc.
3. **Isolate the divergence**: Find the FIRST bar where results differ
4. **Check state variables**: Counters, flags, prices - print them every bar
5. **Review pitfalls**: Check the "Common Pitfalls" section above

### Debug Strategy

If results don't match:

```python
# Add debug logging in the bar loop:
for i in range(len(df)):
    # ... strategy logic ...

    if i < 100:  # Debug first 100 bars
        print(f"Bar {i}:")
        print(f"  Close: {c:.2f}, MA: {ma_value:.2f}")
        print(f"  Counter Long: {counter_close_trend_long}, Short: {counter_close_trend_short}")
        print(f"  Position: {position}, Size: {position_size:.4f}")
        if position != 0:
            print(f"  Entry: {entry_price:.2f}, Stop: {stop_price:.2f}")
```

Run legacy and migrated side-by-side and compare output. Find the FIRST difference.

### Confidence Checks

Before submitting:

1. ✅ All tests pass
2. ✅ Baseline matches exactly
3. ✅ Tested with all 11 MA types
4. ✅ Tested edge cases
5. ✅ No regressions in existing tests
6. ✅ Code is clean and documented
7. ✅ Git commit created and pushed

---

## Conclusion

Phase 7 is the most critical phase of the migration. Success requires:

- **Precision**: Bit-exact match, no approximations
- **Patience**: Test after every change
- **Persistence**: Debug carefully when results differ
- **Validation**: Comprehensive testing across all scenarios

The stakes are high, but the architecture is sound. The indicators package has been validated. The S04 strategy proves the new architecture works. Now it's time to migrate S01 with the same rigor.

**Good luck! This is the hardest phase, but also the most rewarding.**

---

**Project Repository**: `/home/user/S_01_v26-TrailingMA-Ultralight`

**Key Commands**:
```bash
# Run S01 migration tests
pytest tests/test_s01_migration.py -v -s

# Run full test suite
pytest tests/ -v

# Run regression tests
pytest tests/test_regression_s01.py -v -m regression

# Generate baseline (for verification)
python tools/generate_baseline_s01.py
```

**Report Issues**: If you encounter problems not covered in this prompt, document them clearly with:
1. What you tried
2. What you expected
3. What actually happened
4. Relevant code snippets
5. Test output

---

**End of Phase 7 Prompt**

**Version**: 1.0
**Date**: 2025-12-03
**Author**: Migration Team
**Status**: Ready for Execution
