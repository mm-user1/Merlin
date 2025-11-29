# Phase 5: Indicators Package Extraction

**Migration Phase:** 5 of 9
**Complexity:** 🔴 HIGH
**Risk:** 🔴 HIGH
**Estimated Effort:** 10-14 hours
**Priority:** 🚨 HIGH-RISK PHASE #2

---

## Context and Background

### Project Overview

You are working on **S01 Trailing MA v26 - TrailingMA Ultralight**, a cryptocurrency/forex trading strategy backtesting and optimization platform. This phase focuses on extracting all indicator calculation logic from `backtest_engine.py` into a dedicated `indicators/` package.

### Previous Phases Completed

- ✅ **Phase -1: Test Infrastructure Setup** - pytest configured, comprehensive test suite in place
- ✅ **Phase 0: Regression Baseline for S01** - Baseline established and verified
- ✅ **Phase 1: Core Extraction** - Engines moved to `src/core/`
- ✅ **Phase 2: Export Extraction** - Export logic centralized in `src/core/export.py`
- ✅ **Phase 3: Grid Search Removal** - Grid Search deleted, Optuna-only architecture
- ✅ **Phase 4: Metrics Extraction** - All metrics moved to `src/core/metrics.py`

### Current State After Phase 4

```
src/
├── core/
│   ├── __init__.py
│   ├── backtest_engine.py         # ⚠️ Contains indicators - TO BE EXTRACTED
│   ├── optuna_engine.py           # ✅ Uses indicators from backtest_engine
│   ├── walkforward_engine.py      # ✅ Uses indicators from backtest_engine
│   ├── metrics.py                 # ✅ Created in Phase 4
│   └── export.py                  # ✅ Created in Phase 2
├── strategies/
│   ├── base.py
│   └── s01_trailing_ma/
│       ├── strategy.py
│       └── config.json
├── server.py                       # ✅ Imports updated
├── run_backtest.py                 # ✅ Imports updated
└── index.html                      # ✅ UI
```

**All tests passing** (24/24). Regression baseline maintained (Net Profit: 230.75%, Trades: 93).

---

## The Problem: Indicators Embedded in backtest_engine.py

Currently, `backtest_engine.py` contains **indicator calculation logic** that should be extracted:

### Indicators Currently in backtest_engine.py (lines 240-397)

**11 Moving Average Types:**
1. **SMA** (line 244) - Simple Moving Average
2. **EMA** (line 240) - Exponential Moving Average
3. **WMA** (line 248) - Weighted Moving Average
4. **HMA** (line 255) - Hull Moving Average
5. **VWMA** (line 263) - Volume-Weighted Moving Average
6. **VWAP** (line 336) - Volume-Weighted Average Price
7. **ALMA** (line 269) - Arnaud Legoux Moving Average
8. **DEMA** (line 283) - Double Exponential Moving Average
9. **KAMA** (line 289) - Kaufman Adaptive Moving Average
10. **TMA** (line 317) - Triangular Moving Average
11. **T3** (line 330) - T3 Moving Average

**Volatility Indicators:**
- **ATR** (line 386) - Average True Range

**Helper Functions:**
- **get_ma()** (line 344) - Unified interface for all MA types
- **gd()** (line 324) - Helper for T3 calculation

**Constants:**
```python
FACTOR_T3 = 0.7          # T3 smoothing factor
FAST_KAMA = 2            # KAMA fast period
SLOW_KAMA = 30           # KAMA slow period
DEFAULT_ATR_PERIOD = 14  # Default ATR period
VALID_MA_TYPES = {       # Set of valid MA type names
    "SMA", "EMA", "HMA", "WMA", "VWMA", "VWAP",
    "ALMA", "DEMA", "KAMA", "TMA", "T3"
}
```

---

## Objective

**Goal:** Extract all indicator logic from `backtest_engine.py` into `indicators/` package by:

1. **Creating `src/indicators/` package** with proper structure
2. **Extracting 11 MA types** to `indicators/ma.py`
3. **Extracting ATR** to `indicators/volatility.py`
4. **Implementing parity tests** (OLD vs NEW must be bit-exact)
5. **Updating backtest_engine** to import from indicators package
6. **Removing OLD indicator code** from backtest_engine.py
7. **Testing incrementally** after EACH indicator extraction

**Critical Constraints:**
- **Bit-exact compatibility:** Indicators must produce identical results (tolerance < 1e-10)
- **Regression baseline maintained:** Net Profit 230.75%, Max DD 20.03%, Trades 93
- **All tests passing:** Including new parity tests
- **No performance degradation:** Indicator calculation overhead must be minimal
- **Incremental approach:** Extract ONE indicator at a time, test after each

---

## Why This Is High Risk

1. **S01 relies on exact calculations:** Any tiny change = different trades = broken baseline
2. **Floating-point sensitivity:** Order of operations matters: `(a+b)+c ≠ a+(b+c)`
3. **11 different MA types:** Each with unique calculation logic
4. **Dependency chains:** HMA uses WMA, DEMA uses EMA, T3 uses gd() helper
5. **Performance critical:** Indicators called thousands of times per optimization
6. **Multiple consumers:** Used by S01 strategy, Optuna trials, WFA windows

---

## Architecture Principles

### Data Structure Ownership

Following the principle **"structures live where they're populated"**:

- **TradeRecord, StrategyResult** → `backtest_engine.py` (unchanged)
- **BasicMetrics, AdvancedMetrics** → `metrics.py` (Phase 4)
- **Indicators** → `indicators/` package ⬅️ **NEW**
- **OptimizationResult** → `optuna_engine.py` (unchanged)

### Indicators Package Responsibility

**indicators/ ONLY calculates indicators:**
- Pure functions: take Series/DataFrame, return Series
- No side effects, no state
- Strategy-agnostic (generic, reusable)
- Self-contained (no backtest_engine dependencies)

### Package Structure

```
src/indicators/
├── __init__.py              # Package exports
├── ma.py                    # All 11 MA types (SMA, EMA, HMA, WMA, VWMA, VWAP, ALMA, DEMA, KAMA, TMA, T3)
├── volatility.py            # ATR and volatility indicators
├── trend.py                 # Trend indicators (future - placeholder)
├── oscillators.py           # Oscillators (future - placeholder)
└── _utils.py                # Shared utilities (if needed)
```

**Note:** VWMA and VWAP are **moving averages**, not volume indicators - they belong in `ma.py`.

---

## Incremental Extraction Strategy

**CRITICAL:** Do NOT extract all indicators at once! Extract incrementally and test after EACH step.

### Extraction Order (LOW to HIGH risk)

**Phase 5.1: Basic MAs** (2-3 hours) - LOWEST RISK
- SMA, EMA, WMA
- Run regression test after EACH ✓

**Phase 5.2: Volume-Weighted MAs** (2 hours) - MEDIUM RISK
- VWMA, VWAP
- Test with S01 using VWMA/VWAP parameters ✓

**Phase 5.3: Volatility Indicators** (2 hours) - MEDIUM RISK
- ATR
- Test with ATR-based stops ✓

**Phase 5.4: Advanced MAs Part 1** (2-3 hours) - HIGH RISK
- HMA, DEMA (both have dependencies on simpler MAs)
- Test incrementally ✓

**Phase 5.5: Advanced MAs Part 2** (3-4 hours) - HIGHEST RISK
- ALMA, KAMA, TMA, T3
- KAMA has complex iterative logic
- T3 uses gd() helper
- Test EACH individually ✓

**Phase 5.6: Integration** (2-3 hours)
- Update backtest_engine imports
- Remove OLD code
- Final validation ✓

---

## Detailed Step-by-Step Instructions

### Step 1: Create Indicators Package Structure (30 minutes)

**Action:** Set up the `indicators/` package with proper structure.

#### 1.1: Create Directory and Files

```bash
mkdir -p src/indicators
touch src/indicators/__init__.py
touch src/indicators/ma.py
touch src/indicators/volatility.py
touch src/indicators/trend.py
touch src/indicators/oscillators.py
```

#### 1.2: Create Package Init File

**Create `src/indicators/__init__.py`:**

```python
"""
Indicators package for S01 Trailing MA v26.

This package provides technical indicators used by trading strategies:
- Moving Averages (11 types)
- Volatility indicators (ATR)
- Trend indicators (placeholder for future)
- Oscillators (placeholder for future)

All indicators are pure functions that operate on pandas Series/DataFrames.
"""

# Moving Averages
from .ma import (
    sma,
    ema,
    wma,
    hma,
    vwma,
    vwap,
    alma,
    dema,
    kama,
    tma,
    t3,
    get_ma,
    VALID_MA_TYPES,
)

# Volatility
from .volatility import (
    atr,
)

__all__ = [
    # Moving Averages
    "sma",
    "ema",
    "wma",
    "hma",
    "vwma",
    "vwap",
    "alma",
    "dema",
    "kama",
    "tma",
    "t3",
    "get_ma",
    "VALID_MA_TYPES",
    # Volatility
    "atr",
]
```

**Checkpoint:** Package structure created, files empty.

---

### Step 2: Extract Basic MAs (Phase 5.1) (2-3 hours)

**Action:** Extract SMA, EMA, WMA - the simplest indicators with no dependencies.

#### 2.1: Create ma.py File Header

**Create `src/indicators/ma.py`:**

```python
"""
Moving Average indicators for S01 Trailing MA v26.

This module implements 11 different moving average types:
- Simple: SMA, WMA
- Exponential: EMA, DEMA
- Adaptive: KAMA
- Low-lag: HMA, ALMA
- Advanced: TMA, T3
- Volume-weighted: VWMA, VWAP

All functions are pure and operate on pandas Series/DataFrames.

Critical: These implementations must remain bit-exact compatible with
the original backtest_engine.py implementations to maintain regression baseline.
"""
import math
from typing import Optional

import numpy as np
import pandas as pd

# Constants (copied from backtest_engine.py)
FACTOR_T3 = 0.7
FAST_KAMA = 2
SLOW_KAMA = 30

VALID_MA_TYPES = {
    "SMA",
    "EMA",
    "HMA",
    "WMA",
    "VWMA",
    "VWAP",
    "ALMA",
    "DEMA",
    "KAMA",
    "TMA",
    "T3",
}


# ============================================================================
# Basic Moving Averages
# ============================================================================

def sma(series: pd.Series, length: int) -> pd.Series:
    """
    Simple Moving Average.

    Calculates the arithmetic mean of the last 'length' values.

    Args:
        series: Input price series
        length: Period length

    Returns:
        SMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 244).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py line 244
    return series.rolling(length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    """
    Exponential Moving Average.

    Applies exponential weighting where recent values have more influence.

    Args:
        series: Input price series
        length: Period length (span)

    Returns:
        EMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 240).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py line 240
    return series.ewm(span=length, adjust=False).mean()


def wma(series: pd.Series, length: int) -> pd.Series:
    """
    Weighted Moving Average.

    Applies linear weighting where recent values have more influence.
    Weight formula: weights = [1, 2, 3, ..., length]

    Args:
        series: Input price series
        length: Period length

    Returns:
        WMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 248).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 248-252
    weights = np.arange(1, length + 1, dtype=float)
    return series.rolling(length, min_periods=length).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )
```

**Checkpoint:** Basic MAs defined. Now test them.

#### 2.2: Test Basic MAs BEFORE Proceeding

**Create `tests/test_indicators.py`:**

```python
"""
Parity tests for indicators extraction (Phase 5).

These tests verify that the NEW indicators/ implementation
produces bit-exact identical results to the OLD backtest_engine.py implementation.

Critical: These tests MUST pass before indicators extraction is considered complete.
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

# Import OLD implementation (from backtest_engine)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core import backtest_engine

# Import NEW implementation (from indicators)
from indicators import ma, volatility


# Test data
@pytest.fixture(scope="module")
def test_series():
    """Create test series for indicator testing."""
    np.random.seed(42)
    data = 100 + np.cumsum(np.random.randn(1000) * 2)
    return pd.Series(data)


class TestMAsParity:
    """Test parity between OLD and NEW MA implementations."""

    def test_sma_parity(self, test_series):
        """Test SMA matches OLD implementation exactly."""
        length = 20

        # OLD way (from backtest_engine)
        old_sma = backtest_engine.sma(test_series, length)

        # NEW way (from indicators.ma)
        new_sma = ma.sma(test_series, length)

        # Bit-exact comparison
        pd.testing.assert_series_equal(old_sma, new_sma)

    def test_ema_parity(self, test_series):
        """Test EMA matches OLD implementation exactly."""
        length = 20

        old_ema = backtest_engine.ema(test_series, length)
        new_ema = ma.ema(test_series, length)

        pd.testing.assert_series_equal(old_ema, new_ema)

    def test_wma_parity(self, test_series):
        """Test WMA matches OLD implementation exactly."""
        length = 20

        old_wma = backtest_engine.wma(test_series, length)
        new_wma = ma.wma(test_series, length)

        pd.testing.assert_series_equal(old_wma, new_wma)


class TestMAEdgeCases:
    """Test MA functions with edge cases."""

    def test_sma_zero_length(self, test_series):
        """Test SMA with zero length."""
        result = ma.sma(test_series, 0)
        # Should return all NaN (same as OLD behavior)
        assert result.isna().all()

    def test_ema_single_value(self):
        """Test EMA with single value."""
        series = pd.Series([100.0])
        result = ma.ema(series, 1)
        assert not result.isna().any()
        assert result.iloc[0] == 100.0


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Run test:**
```bash
pytest tests/test_indicators.py::TestMAsParity::test_sma_parity -v
pytest tests/test_indicators.py::TestMAsParity::test_ema_parity -v
pytest tests/test_indicators.py::TestMAsParity::test_wma_parity -v
```

**Expected:** All 3 tests PASS

**Checkpoint:** Basic MAs validated. Continue to Phase 5.2.

---

### Step 3: Extract Volume-Weighted MAs (Phase 5.2) (2 hours)

**Action:** Extract VWMA and VWAP - require volume data.

#### 3.1: Add to ma.py

**In `src/indicators/ma.py`, add:**

```python
# ============================================================================
# Volume-Weighted Moving Averages
# ============================================================================

def vwma(series: pd.Series, volume: pd.Series, length: int) -> pd.Series:
    """
    Volume-Weighted Moving Average.

    Calculates MA weighted by volume. Recent high-volume bars have more influence.

    Args:
        series: Input price series
        volume: Volume series
        length: Period length

    Returns:
        VWMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 263).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 263-266
    weighted = (series * volume).rolling(length, min_periods=length).sum()
    vol_sum = volume.rolling(length, min_periods=length).sum()
    return weighted / vol_sum


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Volume-Weighted Average Price.

    Calculates cumulative VWAP using typical price (HLC/3).

    Args:
        high: High price series
        low: Low price series
        close: Close price series
        volume: Volume series

    Returns:
        VWAP values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 336).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 336-341
    typical = (high + low + close) / 3
    tp_vol = typical * volume
    cumulative = tp_vol.cumsum()
    cumulative_vol = volume.cumsum()
    return cumulative / cumulative_vol
```

#### 3.2: Test Volume-Weighted MAs

**Add to `tests/test_indicators.py`:**

```python
@pytest.fixture(scope="module")
def test_volume():
    """Create test volume series."""
    np.random.seed(43)
    return pd.Series(np.random.randint(1000, 10000, 1000))


@pytest.fixture(scope="module")
def test_ohlcv():
    """Create test OHLCV data."""
    np.random.seed(44)
    close = 100 + np.cumsum(np.random.randn(1000) * 2)
    high = close + np.random.rand(1000) * 2
    low = close - np.random.rand(1000) * 2
    volume = np.random.randint(1000, 10000, 1000)

    return pd.DataFrame({
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    })


class TestVolumeMAsParity:
    """Test parity for volume-weighted MAs."""

    def test_vwma_parity(self, test_series, test_volume):
        """Test VWMA matches OLD implementation exactly."""
        length = 20

        old_vwma = backtest_engine.vwma(test_series, test_volume, length)
        new_vwma = ma.vwma(test_series, test_volume, length)

        pd.testing.assert_series_equal(old_vwma, new_vwma)

    def test_vwap_parity(self, test_ohlcv):
        """Test VWAP matches OLD implementation exactly."""
        old_vwap = backtest_engine.vwap(
            test_ohlcv['High'],
            test_ohlcv['Low'],
            test_ohlcv['Close'],
            test_ohlcv['Volume']
        )
        new_vwap = ma.vwap(
            test_ohlcv['High'],
            test_ohlcv['Low'],
            test_ohlcv['Close'],
            test_ohlcv['Volume']
        )

        pd.testing.assert_series_equal(old_vwap, new_vwap)
```

**Run tests:**
```bash
pytest tests/test_indicators.py::TestVolumeMAsParity -v
```

**Expected:** 2/2 tests PASS

**Checkpoint:** Volume-weighted MAs validated. Continue to Phase 5.3.

---

### Step 4: Extract Volatility Indicators (Phase 5.3) (2 hours)

**Action:** Extract ATR - used for stop-loss calculations.

#### 4.1: Create volatility.py

**Create `src/indicators/volatility.py`:**

```python
"""
Volatility indicators for S01 Trailing MA v26.

This module implements volatility-based indicators:
- ATR (Average True Range)
- NATR (Normalized ATR) - future
- Bollinger Bands - future

All functions are pure and operate on pandas Series/DataFrames.
"""
import pandas as pd

DEFAULT_ATR_PERIOD = 14


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """
    Average True Range.

    Measures market volatility by decomposing the entire range of price movement.
    True Range is the max of:
    - High - Low
    - |High - Previous Close|
    - |Low - Previous Close|

    ATR is the exponential moving average of True Range.

    Args:
        high: High price series
        low: Low price series
        close: Close price series
        period: ATR period (default 14)

    Returns:
        ATR values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 386).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 386-396
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()
```

#### 4.2: Test ATR

**Add to `tests/test_indicators.py`:**

```python
class TestVolatilityParity:
    """Test parity for volatility indicators."""

    def test_atr_parity(self, test_ohlcv):
        """Test ATR matches OLD implementation exactly."""
        period = 14

        old_atr = backtest_engine.atr(
            test_ohlcv['High'],
            test_ohlcv['Low'],
            test_ohlcv['Close'],
            period
        )
        new_atr = volatility.atr(
            test_ohlcv['High'],
            test_ohlcv['Low'],
            test_ohlcv['Close'],
            period
        )

        pd.testing.assert_series_equal(old_atr, new_atr)
```

**Run test:**
```bash
pytest tests/test_indicators.py::TestVolatilityParity -v
pytest tests/test_regression_s01.py -v  # Full regression
```

**Expected:** All tests PASS

**Checkpoint:** ATR validated. Continue to Phase 5.4.

---

### Step 5: Extract Advanced MAs Part 1 (Phase 5.4) (2-3 hours)

**Action:** Extract HMA and DEMA - both depend on simpler MAs.

#### 5.1: Add to ma.py

**In `src/indicators/ma.py`, add:**

```python
# ============================================================================
# Advanced Moving Averages Part 1 (with dependencies)
# ============================================================================

def hma(series: pd.Series, length: int) -> pd.Series:
    """
    Hull Moving Average.

    Fast, low-lag MA that reduces delay while improving smoothness.
    Formula: WMA(2*WMA(n/2) - WMA(n), sqrt(n))

    Args:
        series: Input price series
        length: Period length

    Returns:
        HMA values as pd.Series

    Dependencies:
        Requires wma() function

    Note:
        This is a COPY of the function from backtest_engine.py (line 255).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 255-260
    if length <= 0:
        return pd.Series(np.nan, index=series.index)
    half_length = max(1, length // 2)
    sqrt_length = max(1, int(math.sqrt(length)))
    return wma(2 * wma(series, half_length) - wma(series, length), sqrt_length)


def dema(series: pd.Series, length: int) -> pd.Series:
    """
    Double Exponential Moving Average.

    Reduces lag compared to single EMA.
    Formula: 2*EMA - EMA(EMA)

    Args:
        series: Input price series
        length: Period length

    Returns:
        DEMA values as pd.Series

    Dependencies:
        Requires ema() function

    Note:
        This is a COPY of the function from backtest_engine.py (line 283).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 283-286
    e1 = ema(series, length)
    e2 = ema(e1, length)
    return 2 * e1 - e2
```

#### 5.2: Test Advanced MAs Part 1

**Add to `tests/test_indicators.py`:**

```python
class TestAdvancedMAsPart1:
    """Test parity for advanced MAs (HMA, DEMA)."""

    def test_hma_parity(self, test_series):
        """Test HMA matches OLD implementation exactly."""
        length = 20

        old_hma = backtest_engine.hma(test_series, length)
        new_hma = ma.hma(test_series, length)

        pd.testing.assert_series_equal(old_hma, new_hma)

    def test_dema_parity(self, test_series):
        """Test DEMA matches OLD implementation exactly."""
        length = 20

        old_dema = backtest_engine.dema(test_series, length)
        new_dema = ma.dema(test_series, length)

        pd.testing.assert_series_equal(old_dema, new_dema)
```

**Run tests:**
```bash
pytest tests/test_indicators.py::TestAdvancedMAsPart1 -v
```

**Expected:** 2/2 tests PASS

**Checkpoint:** HMA and DEMA validated. Continue to Phase 5.5.

---

### Step 6: Extract Advanced MAs Part 2 (Phase 5.5) (3-4 hours)

**Action:** Extract ALMA, KAMA, TMA, T3 - highest complexity.

#### 6.1: Add Remaining MAs to ma.py

**In `src/indicators/ma.py`, add:**

```python
# ============================================================================
# Advanced Moving Averages Part 2 (complex algorithms)
# ============================================================================

def alma(series: pd.Series, length: int, offset: float = 0.85, sigma: float = 6) -> pd.Series:
    """
    Arnaud Legoux Moving Average.

    Uses Gaussian distribution to reduce lag while maintaining smoothness.

    Args:
        series: Input price series
        length: Period length
        offset: Gaussian offset (default 0.85)
        sigma: Gaussian sigma (default 6)

    Returns:
        ALMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 269).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 269-280
    if length <= 0:
        return pd.Series(np.nan, index=series.index)
    m = offset * (length - 1)
    s = length / sigma

    def _alma(values: np.ndarray) -> float:
        weights = np.exp(-((np.arange(len(values)) - m) ** 2) / (2 * s * s))
        weights /= weights.sum()
        return np.dot(weights, values)

    return series.rolling(length, min_periods=length).apply(_alma, raw=True)


def kama(series: pd.Series, length: int) -> pd.Series:
    """
    Kaufman Adaptive Moving Average.

    Adapts to market volatility - fast in trending markets, slow in ranging markets.
    Uses Efficiency Ratio (ER) to adjust smoothing constant.

    Args:
        series: Input price series
        length: Period length

    Returns:
        KAMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 289).
        Must remain bit-exact compatible with original implementation.

    Warning:
        This implementation uses iterative logic and is sensitive to
        floating-point order of operations. Must match EXACTLY.
    """
    # TODO: Copy implementation from backtest_engine.py lines 289-314
    if length <= 0:
        return pd.Series(np.nan, index=series.index)
    mom = series.diff(length).abs()
    volatility = series.diff().abs().rolling(length, min_periods=length).sum()
    er = pd.Series(np.where(volatility != 0, mom / volatility, 0), index=series.index)
    fast_alpha = 2 / (FAST_KAMA + 1)
    slow_alpha = 2 / (SLOW_KAMA + 1)
    alpha = (er * (fast_alpha - slow_alpha) + slow_alpha) ** 2
    kama_values = np.empty(len(series))
    kama_values[:] = np.nan
    for i in range(len(series)):
        price = series.iat[i]
        if np.isnan(price):
            continue
        a = alpha.iat[i]
        if np.isnan(a):
            kama_values[i] = price if i == 0 else kama_values[i - 1]
            continue
        prev = (
            kama_values[i - 1]
            if i > 0 and not np.isnan(kama_values[i - 1])
            else (series.iat[i - 1] if i > 0 else price)
        )
        kama_values[i] = a * price + (1 - a) * prev
    return pd.Series(kama_values, index=series.index)


def tma(series: pd.Series, length: int) -> pd.Series:
    """
    Triangular Moving Average.

    Double-smoothed SMA that reduces lag.
    Formula: SMA(SMA(n/2), n/2+1)

    Args:
        series: Input price series
        length: Period length

    Returns:
        TMA values as pd.Series

    Dependencies:
        Requires sma() function

    Note:
        This is a COPY of the function from backtest_engine.py (line 317).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 317-321
    if length <= 0:
        return pd.Series(np.nan, index=series.index)
    first = sma(series, math.ceil(length / 2))
    return sma(first, math.floor(length / 2) + 1)


def _gd(series: pd.Series, length: int) -> pd.Series:
    """
    Generalized DEMA helper for T3 calculation.

    Internal helper function - not exported.

    Args:
        series: Input price series
        length: Period length

    Returns:
        GD values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 324).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 324-327
    ema1 = ema(series, length)
    ema2 = ema(ema1, length)
    return ema1 * (1 + FACTOR_T3) - ema2 * FACTOR_T3


def t3(series: pd.Series, length: int) -> pd.Series:
    """
    T3 Moving Average.

    Triple exponential smoothing with volume factor.
    Applies _gd() helper three times for advanced smoothing.

    Args:
        series: Input price series
        length: Period length

    Returns:
        T3 values as pd.Series

    Dependencies:
        Requires _gd() helper function

    Note:
        This is a COPY of the function from backtest_engine.py (line 330).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 330-333
    if length <= 0:
        return pd.Series(np.nan, index=series.index)
    return _gd(_gd(_gd(series, length), length), length)
```

#### 6.2: Test Advanced MAs Part 2

**Add to `tests/test_indicators.py`:**

```python
class TestAdvancedMAsPart2:
    """Test parity for complex advanced MAs."""

    def test_alma_parity(self, test_series):
        """Test ALMA matches OLD implementation exactly."""
        length = 20

        old_alma = backtest_engine.alma(test_series, length)
        new_alma = ma.alma(test_series, length)

        pd.testing.assert_series_equal(old_alma, new_alma)

    def test_kama_parity(self, test_series):
        """Test KAMA matches OLD implementation exactly."""
        length = 20

        old_kama = backtest_engine.kama(test_series, length)
        new_kama = ma.kama(test_series, length)

        # KAMA is iterative - check with tolerance
        pd.testing.assert_series_equal(old_kama, new_kama, rtol=1e-10)

    def test_tma_parity(self, test_series):
        """Test TMA matches OLD implementation exactly."""
        length = 20

        old_tma = backtest_engine.tma(test_series, length)
        new_tma = ma.tma(test_series, length)

        pd.testing.assert_series_equal(old_tma, new_tma)

    def test_t3_parity(self, test_series):
        """Test T3 matches OLD implementation exactly."""
        length = 20

        old_t3 = backtest_engine.t3(test_series, length)
        new_t3 = ma.t3(test_series, length)

        pd.testing.assert_series_equal(old_t3, new_t3)


class TestAllMATypes:
    """Test all MA types work via get_ma()."""

    def test_all_ma_types_work(self, test_series, test_volume, test_ohlcv):
        """Ensure all 11 MA types can be calculated."""
        length = 20

        for ma_type in ma.VALID_MA_TYPES:
            if ma_type == "VWMA":
                result = ma.get_ma(test_series, ma_type, length, volume=test_volume)
            elif ma_type == "VWAP":
                result = ma.get_ma(
                    test_ohlcv['Close'],
                    ma_type,
                    length,
                    volume=test_ohlcv['Volume'],
                    high=test_ohlcv['High'],
                    low=test_ohlcv['Low']
                )
            else:
                result = ma.get_ma(test_series, ma_type, length)

            assert result is not None
            assert len(result) == len(test_series) or len(result) == len(test_ohlcv)
```

**Run tests:**
```bash
pytest tests/test_indicators.py::TestAdvancedMAsPart2 -v
pytest tests/test_indicators.py::TestAllMATypes -v
```

**Expected:** All tests PASS

**Checkpoint:** All MAs extracted and validated. Continue to Phase 5.6.

---

### Step 7: Add get_ma() Facade (Phase 5.6) (1 hour)

**Action:** Extract the unified MA interface.

#### 7.1: Add get_ma() to ma.py

**In `src/indicators/ma.py`, add:**

```python
# ============================================================================
# Unified MA Interface
# ============================================================================

def get_ma(
    series: pd.Series,
    ma_type: str,
    length: int,
    volume: Optional[pd.Series] = None,
    high: Optional[pd.Series] = None,
    low: Optional[pd.Series] = None,
) -> pd.Series:
    """
    Unified interface for all MA types.

    Dispatches to the appropriate MA function based on ma_type.

    Args:
        series: Input price series (usually Close)
        ma_type: MA type name (case-insensitive)
        length: Period length
        volume: Volume series (required for VWMA, VWAP)
        high: High series (required for VWAP)
        low: Low series (required for VWAP)

    Returns:
        MA values as pd.Series

    Raises:
        ValueError: If ma_type is not supported or required data missing

    Note:
        This is a COPY of the function from backtest_engine.py (line 344).
        Must remain bit-exact compatible with original implementation.
    """
    # TODO: Copy implementation from backtest_engine.py lines 344-383
    ma_type = ma_type.upper()
    if ma_type not in VALID_MA_TYPES:
        raise ValueError(f"Unsupported MA type: {ma_type}")
    if ma_type != "VWAP" and length == 0:
        return pd.Series(np.nan, index=series.index)
    if ma_type == "SMA":
        return sma(series, length)
    if ma_type == "EMA":
        return ema(series, length)
    if ma_type == "HMA":
        return hma(series, length)
    if ma_type == "WMA":
        return wma(series, length)
    if ma_type == "VWMA":
        if volume is None:
            raise ValueError("Volume data required for VWMA")
        return vwma(series, volume, length)
    if ma_type == "VWAP":
        if any(v is None for v in (high, low, volume)):
            raise ValueError("High, Low, Volume required for VWAP")
        return vwap(high, low, series, volume)
    if ma_type == "ALMA":
        return alma(series, length)
    if ma_type == "DEMA":
        return dema(series, length)
    if ma_type == "KAMA":
        return kama(series, length)
    if ma_type == "TMA":
        return tma(series, length)
    if ma_type == "T3":
        return t3(series, length)
    return ema(series, length)
```

#### 7.2: Test get_ma()

**Add to `tests/test_indicators.py`:**

```python
class TestGetMAFacade:
    """Test get_ma() unified interface."""

    def test_get_ma_parity_all_types(self, test_series, test_volume, test_ohlcv):
        """Test get_ma() matches OLD for all MA types."""
        length = 20

        for ma_type in ma.VALID_MA_TYPES:
            if ma_type == "VWMA":
                old_result = backtest_engine.get_ma(
                    test_series, ma_type, length, volume=test_volume
                )
                new_result = ma.get_ma(
                    test_series, ma_type, length, volume=test_volume
                )
            elif ma_type == "VWAP":
                old_result = backtest_engine.get_ma(
                    test_ohlcv['Close'],
                    ma_type,
                    length,
                    volume=test_ohlcv['Volume'],
                    high=test_ohlcv['High'],
                    low=test_ohlcv['Low']
                )
                new_result = ma.get_ma(
                    test_ohlcv['Close'],
                    ma_type,
                    length,
                    volume=test_ohlcv['Volume'],
                    high=test_ohlcv['High'],
                    low=test_ohlcv['Low']
                )
            else:
                old_result = backtest_engine.get_ma(test_series, ma_type, length)
                new_result = ma.get_ma(test_series, ma_type, length)

            pd.testing.assert_series_equal(old_result, new_result)
```

**Run test:**
```bash
pytest tests/test_indicators.py::TestGetMAFacade -v
```

**Expected:** Test PASS for all 11 MA types

**Checkpoint:** All indicators extracted. Now integrate.

---

### Step 8: Update backtest_engine.py to Use Indicators (2-3 hours)

**Action:** Replace inline indicator code with imports from `indicators/` package.

#### 8.1: Add Imports to backtest_engine.py

**At top of `src/core/backtest_engine.py`, add:**

```python
# Indicators
from indicators.ma import get_ma, VALID_MA_TYPES
from indicators.volatility import atr
```

#### 8.2: Update Indicator Usage

**Find all places where indicators are called:**

```bash
grep -n "get_ma\|atr\|sma\|ema" src/core/backtest_engine.py
```

**Most likely in `run_strategy()` function:**

**BEFORE:**
```python
# Calculate main MA (inline)
if params.ma_type == "SMA":
    ma_values = sma(df['Close'], params.ma_length)
# ... etc
```

**AFTER:**
```python
# Calculate main MA (from indicators package)
ma_values = get_ma(
    df['Close'],
    params.ma_type,
    params.ma_length,
    volume=df.get('Volume'),
    high=df.get('High'),
    low=df.get('Low')
)

# Calculate ATR (from indicators package)
atr_values = atr(df['High'], df['Low'], df['Close'], params.atr_period)
```

**Note:** Since `get_ma()` and `atr()` have the SAME signatures and names, this should be mostly find-and-replace.

#### 8.3: Remove OLD Indicator Code from backtest_engine.py

**⚠️ CRITICAL:** Only do this AFTER all tests pass!

**Delete from `src/core/backtest_engine.py`:**
- Lines 240-241: `ema()`
- Lines 244-245: `sma()`
- Lines 248-252: `wma()`
- Lines 255-260: `hma()`
- Lines 263-266: `vwma()`
- Lines 269-280: `alma()`
- Lines 283-286: `dema()`
- Lines 289-314: `kama()`
- Lines 317-321: `tma()`
- Lines 324-327: `gd()` (now `_gd()` in ma.py, not exported)
- Lines 330-333: `t3()`
- Lines 336-341: `vwap()`
- Lines 344-383: `get_ma()`
- Lines 386-396: `atr()`

**Delete constants:**
- Lines 12-14: `FACTOR_T3`, `FAST_KAMA`, `SLOW_KAMA`
- Lines 16-28: `VALID_MA_TYPES` (now imported from indicators.ma)

**Keep:**
- Line 15: `DEFAULT_ATR_PERIOD` (used by StrategyParams)

**Verify deletion:**

```bash
# Search for old function names (should find NOTHING in backtest_engine)
grep -n "^def sma\|^def ema\|^def wma\|^def hma\|^def vwma\|^def vwap\|^def alma\|^def dema\|^def kama\|^def tma\|^def t3\|^def gd\|^def get_ma\|^def atr" src/core/backtest_engine.py

# Should return NOTHING (all moved to indicators/)

# Verify they exist in indicators/
grep -n "^def sma\|^def ema" src/indicators/ma.py
grep -n "^def atr" src/indicators/volatility.py
# Should find the functions
```

---

### Step 9: Update Core Package Exports (10 minutes)

**Action:** Export indicators from core package for convenience.

**In `src/core/__init__.py`, add:**

```python
# Import indicators for convenience
import sys
from pathlib import Path

# Add parent directory to path to access indicators package
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

# Now can import indicators
from indicators.ma import VALID_MA_TYPES, get_ma
from indicators.volatility import atr

# ... rest of exports

__all__ = [
    # ... existing exports ...

    # Indicators (re-exported for convenience)
    "VALID_MA_TYPES",
    "get_ma",
    "atr",
]
```

**Alternative (cleaner):**

Don't export from `core/__init__.py`, let code import directly:

```python
# In strategies or other code:
from indicators.ma import get_ma
from indicators.volatility import atr
```

---

### Step 10: Final Testing (90-120 minutes)

**Critical:** This phase must maintain bit-exact compatibility.

#### 10.1: Run Full Test Suite

```bash
pytest tests/ -v
```

**Expected:** All tests passing (27+ tests)

#### 10.2: Run Regression Tests

```bash
pytest tests/test_regression_s01.py -v -m regression
```

**Expected:** 12/12 tests passing

**Critical validations:**
- ✅ Net profit: 230.75% (±0.01%)
- ✅ Max drawdown: 20.03% (±0.01%)
- ✅ Total trades: 93 (exact)

#### 10.3: Test All MA Types with S01

**Create test script `tools/test_all_ma_types.py`:**

```python
"""Test S01 with all 11 MA types to ensure indicators work."""

from pathlib import Path
from core.backtest_engine import load_data, StrategyParams, run_strategy, prepare_dataset_with_warmup
from indicators.ma import VALID_MA_TYPES
import pandas as pd

# Load data
data_path = Path(__file__).parent.parent / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
df = load_data(str(data_path))

# Prepare data
start_ts = pd.Timestamp('2025-05-01', tz='UTC')
end_ts = pd.Timestamp('2025-11-20', tz='UTC')
df_prepared, trade_start_idx = prepare_dataset_with_warmup(df, start_ts, end_ts, 1000)

print(f"Testing S01 with all {len(VALID_MA_TYPES)} MA types...")

results = {}
for ma_type in sorted(VALID_MA_TYPES):
    print(f"\nTesting {ma_type}...", end=" ")

    params = StrategyParams(
        ma_type=ma_type,
        ma_length=50,
        close_count_long=7,
        close_count_short=5,
        trail_ma_long_type=ma_type,
        trail_ma_short_type=ma_type,
    )

    try:
        result = run_strategy(df_prepared, params, trade_start_idx)
        results[ma_type] = {
            'net_profit_pct': result.net_profit_pct,
            'max_dd_pct': result.max_drawdown_pct,
            'total_trades': result.total_trades,
        }
        print(f"✅ Profit: {result.net_profit_pct:.2f}%, Trades: {result.total_trades}")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        results[ma_type] = {'error': str(e)}

print("\n" + "="*60)
print("Summary:")
print("="*60)

for ma_type, res in sorted(results.items()):
    if 'error' in res:
        print(f"{ma_type:8} - ERROR: {res['error']}")
    else:
        print(f"{ma_type:8} - Profit: {res['net_profit_pct']:8.2f}% | DD: {res['max_dd_pct']:7.2f}% | Trades: {res['total_trades']:3d}")

# Check if all passed
all_passed = all('error' not in res for res in results.values())
if all_passed:
    print("\n✅ All 11 MA types working correctly!")
else:
    print("\n❌ Some MA types failed!")
    exit(1)
```

**Run:**
```bash
python tools/test_all_ma_types.py
```

**Expected:** All 11 MA types work, no errors

#### 10.4: Test Optuna Optimization

```bash
python tools/test_optuna_phase5.py
```

**Create if not exists:**

```python
"""Test Optuna optimization after Phase 5 (indicators extraction)."""

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
        'maType': True,  # Test MA type optimization
    },
    'param_ranges': {
        'closeCountLong': (5, 15, 1),
    },
    'ma_types_trend': ['SMA', 'EMA', 'HMA'],  # Test 3 MA types
    'fixed_params': {
        'maLength': 50,
    },
}

# Run optimization
print("Starting Optuna optimization (10 trials, 3 MA types)...")
optimizer = OptunaOptimizer(base_config, optuna_config)
results = optimizer.optimize()

print(f"\nCompleted {len(results)} trials")

# Show best result
best_result = max(results, key=lambda r: r.score)
print(f"\nBest trial:")
print(f"  MA Type: {best_result.ma_type}")
print(f"  Score: {best_result.score:.2f}")
print(f"  Net Profit: {best_result.net_profit_pct:.2f}%")

print("\n✅ Phase 5 Optuna test PASSED")
```

**Expected:** Optimization completes successfully

#### 10.5: Test via UI

**Start server:**
```bash
cd src
python server.py
```

**In browser:**
1. Navigate to `http://localhost:8000`
2. Select S01 strategy
3. Run single backtest
4. **Verify metrics:**
   - Net Profit: 230.75%
   - Max Drawdown: 20.03%
   - Total Trades: 93
5. Run small Optuna optimization (10-20 trials)
6. Verify results download correctly

#### 10.6: Performance Check

**Run benchmark:**

```python
# tools/benchmark_indicators.py
import time
import numpy as np
import pandas as pd
from indicators.ma import get_ma
from indicators.volatility import atr

# Generate test data
np.random.seed(42)
n_bars = 10000
df = pd.DataFrame({
    'Close': 100 + np.cumsum(np.random.randn(n_bars) * 2),
    'High': 102 + np.cumsum(np.random.randn(n_bars) * 2),
    'Low': 98 + np.cumsum(np.random.randn(n_bars) * 2),
    'Volume': np.random.randint(1000, 10000, n_bars)
})

print("Benchmarking indicators...")

# Benchmark MAs
ma_types = ['SMA', 'EMA', 'HMA', 'WMA', 'KAMA']
for ma_type in ma_types:
    start = time.time()
    for _ in range(100):
        result = get_ma(df['Close'], ma_type, 50, volume=df['Volume'])
    duration = time.time() - start
    print(f"{ma_type:6} - 100 calls in {duration:.3f}s ({duration*10:.1f}ms per call)")

# Benchmark ATR
start = time.time()
for _ in range(100):
    result = atr(df['High'], df['Low'], df['Close'], 14)
duration = time.time() - start
print(f"ATR    - 100 calls in {duration:.3f}s ({duration*10:.1f}ms per call)")

print("\n✅ Performance acceptable (indicators fast enough)")
```

**Run:**
```bash
python tools/benchmark_indicators.py
```

**Expected:** Similar or better performance than before Phase 5

---

## Validation Checklist

Before considering Phase 5 complete, verify ALL of the following:

### Code Changes
- [ ] `src/indicators/` package created
- [ ] `indicators/__init__.py` with exports
- [ ] `indicators/ma.py` with all 11 MA types
- [ ] `indicators/volatility.py` with ATR
- [ ] `indicators/trend.py` (placeholder)
- [ ] `indicators/oscillators.py` (placeholder)
- [ ] All MA functions implemented (SMA, EMA, WMA, HMA, VWMA, VWAP, ALMA, DEMA, KAMA, TMA, T3)
- [ ] `get_ma()` facade implemented
- [ ] ATR function implemented
- [ ] Constants moved to appropriate files

### Integration
- [ ] `backtest_engine.py` imports from indicators package
- [ ] `backtest_engine.py` uses `get_ma()` from indicators
- [ ] `backtest_engine.py` uses `atr()` from indicators
- [ ] OLD indicator functions deleted from backtest_engine
- [ ] OLD constants deleted from backtest_engine (except DEFAULT_ATR_PERIOD)

### Testing
- [ ] All parity tests passing: `pytest tests/test_indicators.py -v`
- [ ] All regression tests passing: `pytest tests/test_regression_s01.py -v`
- [ ] Full test suite passing: `pytest tests/ -v`
- [ ] All 11 MA types tested with S01: `python tools/test_all_ma_types.py`
- [ ] Optuna test passing: `python tools/test_optuna_phase5.py`
- [ ] UI test passing: Manual verification via browser

### Behavioral Validation
- [ ] Net profit matches baseline: 230.75% (±0.01%)
- [ ] Max drawdown matches baseline: 20.03% (±0.01%)
- [ ] Total trades matches baseline: 93 (exact)
- [ ] All MA types produce trades (no errors)
- [ ] Optimization scores unchanged

### Code Quality
- [ ] No indicator functions remain in backtest_engine:
  ```bash
  grep -n "^def sma\|^def ema\|^def wma" src/core/backtest_engine.py
  # Should find NOTHING
  ```
- [ ] All imports correct
- [ ] No circular dependencies
- [ ] Docstrings complete
- [ ] Type hints present

### Documentation
- [ ] Function docstrings in indicators/ma.py
- [ ] Function docstrings in indicators/volatility.py
- [ ] Phase 5 completion documented

---

## Git Workflow

```bash
# Stage all changes
git add src/indicators/
git add src/core/backtest_engine.py
git add src/core/__init__.py
git add tests/test_indicators.py
git add tools/test_all_ma_types.py
git add tools/test_optuna_phase5.py
git add tools/benchmark_indicators.py

# Commit
git commit -m "Phase 5: Extract indicators to indicators/ package

- Created src/indicators/ package with clean structure:
  - indicators/ma.py: All 11 MA types (SMA, EMA, WMA, HMA, VWMA, VWAP, ALMA, DEMA, KAMA, TMA, T3)
  - indicators/volatility.py: ATR and volatility indicators
  - indicators/__init__.py: Package exports
  - indicators/trend.py, oscillators.py: Placeholders for future

- Implemented all MA functions:
  - Basic MAs: SMA, EMA, WMA
  - Volume-weighted: VWMA, VWAP
  - Advanced: HMA, DEMA, ALMA, KAMA, TMA, T3
  - Unified get_ma() facade for all types

- Moved constants:
  - VALID_MA_TYPES to indicators/ma.py
  - FACTOR_T3, FAST_KAMA, SLOW_KAMA to indicators/ma.py
  - DEFAULT_ATR_PERIOD kept in backtest_engine (used by StrategyParams)

- Updated backtest_engine.py to use indicators package
- Deleted OLD indicator code from backtest_engine (~150 lines removed)

- Created comprehensive parity tests (tests/test_indicators.py)
- All tests passing (27/27)
- Regression baseline maintained:
  - Net Profit: 230.75% ✅
  - Max Drawdown: 20.03% ✅
  - Total Trades: 93 ✅

- Bit-exact compatibility verified for all 11 MA types
- No performance degradation
- Cleaner separation of concerns
- Prepares for S01 migration (Phase 7)
"

# Tag
git tag phase-5-complete

# Push to remote
git push -u origin claude/mg-3-prompt_5-01FjHu2a7awXZPeQoGJod71e
git push origin phase-5-complete

# Verify
git log -1 --stat
```

---

## Common Issues and Troubleshooting

### Issue 1: Parity Test Fails - MA Values Differ

**Symptom:**
```
AssertionError: Series are different
```

**Cause:** Floating-point accumulation difference or typo in copy

**Solution:**
1. Compare implementation line-by-line with original
2. Check for typos in mathematical operations
3. Verify function signatures match exactly
4. Use `np.allclose()` with very tight tolerance if needed

### Issue 2: KAMA Values Don't Match

**Symptom:**
```
AssertionError: KAMA values differ starting at index 50
```

**Cause:** KAMA uses iterative logic - sensitive to order

**Solution:**
1. Copy KAMA implementation EXACTLY (including loop order)
2. Verify FAST_KAMA and SLOW_KAMA constants match
3. Check alpha calculation formula
4. Compare intermediate values (ER, alpha) for debugging

### Issue 3: Import Error - Circular Dependency

**Symptom:**
```
ImportError: cannot import name 'get_ma' from 'indicators.ma'
```

**Cause:** Circular import between backtest_engine and indicators

**Solution:**
- Indicators should NOT import from backtest_engine
- Only pure pandas/numpy imports in indicators/
- Check `__init__.py` for accidental cross-imports

### Issue 4: VWAP Calculation Different

**Symptom:**
```
VWAP test fails with large differences
```

**Cause:** Cumulative calculation sensitive to order

**Solution:**
1. Verify typical price calculation: `(H+L+C)/3`
2. Check cumsum() usage matches exactly
3. Ensure division order same as original

### Issue 5: T3 Returns All NaN

**Symptom:**
```
T3 returns Series of NaN values
```

**Cause:** Missing `_gd()` helper or incorrect nesting

**Solution:**
1. Ensure `_gd()` helper function copied correctly
2. Verify T3 calls `_gd(_gd(_gd(series, length), length), length)`
3. Check FACTOR_T3 constant value (should be 0.7)

### Issue 6: Performance Degradation

**Symptom:** Backtests take 2x longer after Phase 5

**Cause:** Import overhead or inefficient indicator calls

**Solution:**
1. Profile with `cProfile` to find bottleneck
2. Check for redundant indicator calculations
3. Verify caching still works in Optuna trials
4. Ensure indicators are pure functions (no unnecessary state)

---

## Success Criteria Summary

Phase 5 is complete when:

1. ✅ **All indicators extracted** - 11 MAs + ATR in indicators/ package
2. ✅ **All parity tests passing** - OLD vs NEW bit-exact match
3. ✅ **Regression baseline maintained** - Net Profit 230.75%, Trades 93
4. ✅ **All MA types working** - Test script passes for all 11 types
5. ✅ **Full test suite passing** - 27+ tests green
6. ✅ **Optuna working** - Optimization with MA type variations works
7. ✅ **UI working** - Manual testing successful
8. ✅ **OLD code deleted** - backtest_engine.py cleaner (~150 lines removed)
9. ✅ **Performance maintained** - No degradation
10. ✅ **Clean git commit** - With tag `phase-5-complete`

---

## Next Steps After Phase 5

Once Phase 5 is complete and validated, proceed to:

**Phase 6: Simple Strategy Testing**
- Complexity: 🟡 MEDIUM
- Risk: 🟢 LOW
- Estimated Effort: 8-12 hours

Phase 6 will create a dead-simple MA crossover strategy to validate the entire architecture end-to-end before migrating complex S01 in Phase 7.

---

## Quick Reference Commands

```bash
# ============================================================================
# Package Creation
# ============================================================================

# Create indicators package
mkdir -p src/indicators
touch src/indicators/{__init__.py,ma.py,volatility.py,trend.py,oscillators.py}

# ============================================================================
# Testing
# ============================================================================

# Run indicators parity tests
pytest tests/test_indicators.py -v

# Run specific MA type test
pytest tests/test_indicators.py::TestMAsParity::test_sma_parity -v

# Run all MA types test
pytest tests/test_indicators.py::TestAllMATypes -v

# Run regression tests
pytest tests/test_regression_s01.py -v

# Run full test suite
pytest tests/ -v

# Test all MA types with S01
python tools/test_all_ma_types.py

# Test Optuna optimization
python tools/test_optuna_phase5.py

# Benchmark performance
python tools/benchmark_indicators.py

# ============================================================================
# Verification
# ============================================================================

# Check for remaining indicator functions in backtest_engine (should be empty)
grep -n "^def sma\|^def ema\|^def wma\|^def hma\|^def atr" src/core/backtest_engine.py

# Verify indicators exist in new package
grep -n "^def sma\|^def ema\|^def get_ma" src/indicators/ma.py
grep -n "^def atr" src/indicators/volatility.py

# Check imports
grep -n "from indicators" src/core/backtest_engine.py

# ============================================================================
# Git
# ============================================================================

# Check status
git status

# Stage changes
git add src/indicators/ src/core/backtest_engine.py tests/test_indicators.py tools/

# Commit
git commit -m "Phase 5: Extract indicators to indicators/ package"

# Tag
git tag phase-5-complete

# Push
git push -u origin claude/mg-3-prompt_5-01FjHu2a7awXZPeQoGJod71e
git push origin phase-5-complete

# Verify
git log -1 --stat
```

---

**End of Phase 5 Prompt**

**Total Length:** ~14.5 KB
**Target Audience:** GPT 5.1 Codex
**Expected Execution Time:** 10-14 hours
**Risk Level:** 🔴 HIGH (requires bit-exact compatibility)

**Key Success Metric:** All 11 MA types and ATR produce bit-exact identical results to OLD implementation, with regression baseline maintained (Net Profit: 230.75%, Max DD: 20.03%, Trades: 93).
