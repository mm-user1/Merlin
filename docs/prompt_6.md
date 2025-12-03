# Phase 6: StochRSI Strategy Implementation - Task Prompt

## Project Context

You are working on a cryptocurrency/forex trading strategy backtesting platform. The project has already migrated to a clean architecture with separated concerns:

- **Core engines**: `backtest_engine.py`, `optuna_engine.py`, `walkforward_engine.py`
- **Utilities**: `metrics.py` (metrics calculation), `export.py` (results export)
- **Domain layers**: `indicators/` (technical indicators), `strategies/` (strategy implementations)
- **Interface**: `ui/` (Flask server + web UI)

**Current State**: Phases 1-5 completed (core extraction, export, indicators, metrics). The architecture is ready for testing with new strategies.

## Phase 6 Objective

**Goal**: Implement and validate the StochRSI strategy (S_04) to test the new architecture end-to-end BEFORE migrating the complex S01 strategy. This is a critical validation phase.

**Success Criteria**:
1. Convert the PineScript StochRSI strategy to Python
2. Implement it following the project's architecture patterns
3. Achieve performance metrics matching the PineScript version (±5% tolerance)
4. Create comprehensive tests validating the implementation

## Target PineScript Strategy

**Strategy Name**: S_04 StochRSI_v02 no EMA Ultralight

**File Location**: `./docs/S_04 StochRSI_v02 no EMA Ultralight.pine`

### Strategy Logic Overview

The strategy uses Stochastic RSI oscillator combined with swing extremum detection:

**Indicators**:
- RSI (Relative Strength Index)
- Stochastic RSI (stochastic applied to RSI)
- %K line (smoothed StochRSI)
- %D line (smoothed %K)
- Swing highs/lows for trend confirmation

**Entry Conditions**:

**Long Entry**:
1. K crosses over D in oversold zone (both K < osLevel and D < osLevel)
2. After crossover, K must cross above osLevel (resets the signal)
3. New swing low detected: lowest low over last X bars
4. Price stays above swing low for N consecutive bars (trend confirmation)
5. Both conditions (OS crossover flag + trend flag) must be true

**Short Entry**:
1. K crosses under D in overbought zone (both K > obLevel and D > obLevel)
2. After crossover, K must cross below obLevel (resets the signal)
3. New swing high detected: highest high over last X bars
4. Price stays below swing high for N consecutive bars (trend confirmation)
5. Both conditions (OB crossover flag + trend flag) must be true

**Exit Conditions**:
1. **Stop Loss**: Placed at the swing low (for longs) or swing high (for shorts)
2. **Signal Exit**: Opposite StochRSI signal (bearish cross in OB for longs, bullish cross in OS for shorts)

**Position Sizing**:
- Risk-based: `(Equity × RiskPerTrade%) / (EntryPrice - StopPrice)`, rounded to contract size

### Default Parameters

```python
rsiLen = 16          # RSI length
stochLen = 16        # Stochastic length
kLen = 3             # %K smoothing
dLen = 3             # %D smoothing
obLevel = 75.0       # Overbought level
osLevel = 15.0       # Oversold level
extLookback = 23     # Extremum lookback (X bars)
confirmBars = 14     # Bars after extremum (N)
riskPerTrade = 2.0   # Risk % per trade
contractsSize = 0.01 # Contract size
```

### Expected Performance Metrics

**Test Configuration**:
- CSV File: `./data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
- Date Range: 2025-06-01 to 2025-10-01
- Commission: 0.05%
- Initial Capital: 100 USDT

**Expected Results** (from PineScript):
- Net Profit: **113.26%**
- Max Drawdown: **10.99%**
- Total Trades: **52**

**Tolerance**: Python implementation should match within ±5% for all metrics.

## Implementation Requirements

### 1. Create Strategy Files

**Directory**: `src/strategies/s04_stochrsi/`

**Required Files**:
- `__init__.py` (empty or with imports)
- `strategy.py` (main implementation)
- `config.json` (parameter definitions)

### 2. Implement Missing Indicators

**Location**: `src/indicators/oscillators.py`

Currently a placeholder. You need to implement:

```python
def rsi(series: pd.Series, length: int) -> pd.Series:
    """
    Relative Strength Index
    Matches ta.rsi() from PineScript
    """
    # Implementation here

def stoch_rsi(rsi_series: pd.Series, length: int) -> pd.Series:
    """
    Stochastic RSI: (RSI - MIN(RSI, length)) / (MAX(RSI, length) - MIN(RSI, length)) * 100
    """
    # Implementation here
```

**Critical**: Ensure bit-exact or near-exact match with PineScript calculations.

### 3. Strategy Implementation Structure

**File**: `src/strategies/s04_stochrsi/strategy.py`

Key components to implement:
- `S04Params` dataclass with all parameters and `from_dict()` method
- `S04StochRSI(BaseStrategy)` class with `STRATEGY_ID`, `STRATEGY_NAME`, `STRATEGY_VERSION`
- `run()` method implementing the full bar-by-bar logic

Implementation steps in `run()`:
1. Parse parameters using `S04Params.from_dict(params)`
2. Calculate indicators (RSI, StochRSI, K, D)
3. Initialize state variables (flags, swing detection variables)
4. Bar-by-bar loop: update flags, detect swings, check entries/exits, update curves
5. Return `StrategyResult` with trades, equity_curve, balance_curve, timestamps

### 4. Config JSON Structure

**File**: `src/strategies/s04_stochrsi/config.json`

Create config.json following the project's standard format with 12 parameters organized in 4 groups:
- **StochRSI**: rsiLen(16), stochLen(16), kLen(3), dLen(3) - first two optimizable
- **Levels**: obLevel(75.0), osLevel(15.0) - both optimizable
- **Trend Confirmation**: extLookback(23), confirmBars(14) - both optimizable
- **Position Sizing**: riskPerTrade(2.0), contractSize(0.01) - not optimizable
- **Backtest Settings**: initialCapital(100.0), commissionPct(0.05) - not optimizable

See `src/strategies/s01_trailing_ma/config.json` for reference structure.

## Implementation Guide

### Step 1: Implement RSI and StochRSI Indicators

**File**: `src/indicators/oscillators.py`

```python
import numpy as np
import pandas as pd


def rsi(series: pd.Series, length: int) -> pd.Series:
    """
    Relative Strength Index (RSI)

    Matches TradingView's ta.rsi() implementation.

    Formula:
    - Change = Close[i] - Close[i-1]
    - Gain = Change if Change > 0 else 0
    - Loss = -Change if Change < 0 else 0
    - AvgGain = RMA(Gain, length)
    - AvgLoss = RMA(Loss, length)
    - RS = AvgGain / AvgLoss
    - RSI = 100 - (100 / (1 + RS))

    Args:
        series: Price series (typically Close)
        length: RSI period

    Returns:
        RSI values as pd.Series
    """
    # Use Wilder's smoothing (RMA/SMMA)
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    # Wilder's smoothing = EWM with alpha = 1/length
    avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi_values = 100.0 - (100.0 / (1.0 + rs))

    return rsi_values


def stoch_rsi(close: pd.Series, rsi_len: int, stoch_len: int) -> pd.Series:
    """
    Stochastic RSI

    Applies stochastic formula to RSI values.

    Formula:
    - RSI = rsi(close, rsi_len)
    - StochRSI = (RSI - MIN(RSI, stoch_len)) / (MAX(RSI, stoch_len) - MIN(RSI, stoch_len)) * 100

    Args:
        close: Close price series
        rsi_len: RSI period
        stoch_len: Stochastic period

    Returns:
        StochRSI values as pd.Series
    """
    rsi_values = rsi(close, rsi_len)

    rsi_min = rsi_values.rolling(window=stoch_len).min()
    rsi_max = rsi_values.rolling(window=stoch_len).max()

    denominator = rsi_max - rsi_min
    stoch_rsi_values = pd.Series(0.0, index=close.index)

    mask = denominator != 0
    stoch_rsi_values[mask] = ((rsi_values[mask] - rsi_min[mask]) / denominator[mask]) * 100.0

    return stoch_rsi_values
```

### Step 2: Implement Strategy Logic

Key implementation details:

**Indicator Calculation**:
```python
# Calculate StochRSI components
rsi_values = rsi(df['Close'], p.rsi_len)
stoch_rsi_values = stoch_rsi(df['Close'], p.rsi_len, p.stoch_len)
k = sma(stoch_rsi_values, p.k_len)
d = sma(k, p.d_len)
```

**Crossover Detection**:
```python
# Bullish cross in OS
bull_cross_in_os = (k.iloc[i] > d.iloc[i] and
                    k.iloc[i-1] <= d.iloc[i-1] and
                    k.iloc[i] < p.os_level and
                    d.iloc[i] < p.os_level)

# Bearish cross in OB
bear_cross_in_ob = (k.iloc[i] < d.iloc[i] and
                    k.iloc[i-1] >= d.iloc[i-1] and
                    k.iloc[i] > p.ob_level and
                    d.iloc[i] > p.ob_level)
```

**Swing Detection**:
```python
# Long trend detection
lowest_low = df['Low'].iloc[max(0, i-p.ext_lookback+1):i+1].min()

if pd.isna(swing_low) or lowest_low != swing_low:
    swing_low = lowest_low
    swing_low_count = 0
    trend_long_flag = False

if not pd.isna(swing_low):
    if df['Low'].iloc[i] > swing_low:
        swing_low_count += 1
        if swing_low_count >= p.confirm_bars:
            trend_long_flag = True
    elif df['Low'].iloc[i] < swing_low:
        swing_low = df['Low'].iloc[i]
        swing_low_count = 0
        trend_long_flag = False
```

**Position Sizing**:
```python
# Long position size
stop_distance = entry_price - stop_price
risk_amount = equity * (p.risk_per_trade / 100.0)
raw_size = risk_amount / stop_distance
position_size = np.floor(raw_size / p.contract_size) * p.contract_size

# Apply commission
commission = position_size * entry_price * (p.commission_pct / 100.0)
```

### Step 3: Testing

Create **`tests/test_s04_stochrsi.py`**:

```python
import pandas as pd
import pytest
from strategies.s04_stochrsi.strategy import S04StochRSI, S04Params
from indicators.oscillators import rsi, stoch_rsi
from core import metrics


def load_test_data():
    """Load the reference CSV file"""
    csv_path = "./data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    # Filter to test date range
    df = df.loc['2025-06-01':'2025-10-01']

    return df


def test_rsi_calculation():
    """Test RSI indicator calculation"""
    df = load_test_data()
    rsi_values = rsi(df['Close'], 16)

    # Basic sanity checks
    assert len(rsi_values) == len(df)
    assert rsi_values.min() >= 0.0
    assert rsi_values.max() <= 100.0
    assert not rsi_values.iloc[-100:].isna().all()


def test_stoch_rsi_calculation():
    """Test StochRSI calculation"""
    df = load_test_data()
    stoch_values = stoch_rsi(df['Close'], 16, 16)

    assert len(stoch_values) == len(df)
    assert stoch_values.min() >= 0.0
    assert stoch_values.max() <= 100.0


def test_s04_basic_run():
    """Test S04 strategy runs without errors"""
    df = load_test_data()
    params = S04Params().to_dict() if hasattr(S04Params, 'to_dict') else {
        'rsiLen': 16,
        'stochLen': 16,
        'kLen': 3,
        'dLen': 3,
        'obLevel': 75.0,
        'osLevel': 15.0,
        'extLookback': 23,
        'confirmBars': 14,
        'riskPerTrade': 2.0,
        'contractSize': 0.01,
        'initialCapital': 100.0,
        'commissionPct': 0.05,
    }

    result = S04StochRSI.run(df, params, trade_start_idx=0)

    assert result is not None
    assert isinstance(result.trades, list)
    assert len(result.equity_curve) > 0
    assert len(result.balance_curve) > 0


def test_s04_reference_performance():
    """
    Test S04 matches reference performance from PineScript.

    Expected (from PineScript):
    - Net Profit: 113.26%
    - Max Drawdown: 10.99%
    - Total Trades: 52

    Tolerance: ±5%
    """
    df = load_test_data()
    params = {
        'rsiLen': 16,
        'stochLen': 16,
        'kLen': 3,
        'dLen': 3,
        'obLevel': 75.0,
        'osLevel': 15.0,
        'extLookback': 23,
        'confirmBars': 14,
        'riskPerTrade': 2.0,
        'contractSize': 0.01,
        'initialCapital': 100.0,
        'commissionPct': 0.05,
    }

    result = S04StochRSI.run(df, params, trade_start_idx=0)

    # Calculate metrics
    basic = metrics.calculate_basic(result)

    # Expected values from PineScript
    expected_net_profit_pct = 113.26
    expected_max_dd_pct = 10.99
    expected_total_trades = 52

    # Tolerance ±5%
    tolerance = 0.05

    assert abs(basic.net_profit_pct - expected_net_profit_pct) / expected_net_profit_pct <= tolerance, \
        f"Net Profit mismatch: {basic.net_profit_pct}% vs expected {expected_net_profit_pct}%"

    assert abs(basic.max_drawdown_pct - expected_max_dd_pct) / expected_max_dd_pct <= tolerance, \
        f"Max DD mismatch: {basic.max_drawdown_pct}% vs expected {expected_max_dd_pct}%"

    # Total trades should be exact or very close
    assert abs(basic.total_trades - expected_total_trades) <= 3, \
        f"Total trades mismatch: {basic.total_trades} vs expected {expected_total_trades}"

    print(f"\n✅ Reference Performance Match:")
    print(f"Net Profit: {basic.net_profit_pct:.2f}% (expected {expected_net_profit_pct}%)")
    print(f"Max DD: {basic.max_drawdown_pct:.2f}% (expected {expected_max_dd_pct}%)")
    print(f"Total Trades: {basic.total_trades} (expected {expected_total_trades})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

## Critical Implementation Notes

### 1. Indicator Accuracy

The RSI calculation MUST match TradingView's implementation:
- Use Wilder's smoothing (exponential moving average with alpha=1/length)
- First RSI value will be NaN for initial bars

### 2. State Management

The strategy requires careful state management:
- Flags persist across bars: `os_cross_long_flag`, `ob_cross_short_flag`
- Swing variables: `swing_low`, `swing_low_count`, `trend_long_flag`
- These are NOT reset every bar, only under specific conditions

### 3. Position Sizing Edge Cases

- Handle division by zero if entry_price == stop_price
- Floor position size to contract size multiples
- Ensure position size > 0 before entering

### 4. Commission Handling

Commission is applied on:
- Entry: deducted from balance
- Exit: deducted from PnL

### 5. Equity vs Balance Curves

- **Balance**: Only updates on trade close (realized PnL)
- **Equity**: Updates every bar (balance + unrealized PnL)

## Deliverables Checklist

- [ ] `src/indicators/oscillators.py` with RSI and StochRSI implementations
- [ ] `src/strategies/s04_stochrsi/strategy.py` with full strategy logic
- [ ] `src/strategies/s04_stochrsi/config.json` with all parameters
- [ ] `src/strategies/s04_stochrsi/__init__.py`
- [ ] `tests/test_s04_stochrsi.py` with comprehensive tests
- [ ] All tests passing with ±5% tolerance on reference metrics
- [ ] Documentation of any deviations from PineScript (if necessary)

## Success Validation

Run the following commands to validate:

```bash
# Run tests
pytest tests/test_s04_stochrsi.py -v

# Expected output:
# test_rsi_calculation PASSED
# test_stoch_rsi_calculation PASSED
# test_s04_basic_run PASSED
# test_s04_reference_performance PASSED
```

If `test_s04_reference_performance` passes, the implementation is successful and the architecture is validated for Phase 7 (S01 migration).

## Questions and Clarifications

If you encounter issues:

1. **Indicator mismatch**: Compare intermediate values (RSI, StochRSI, K, D) with PineScript
2. **Trade count mismatch**: Check entry/exit conditions and flag logic
3. **PnL mismatch**: Verify position sizing calculation and commission handling
4. **Performance far off**: Debug bar-by-bar to find first divergence

Create detailed logging to track state variables and signal conditions during development.

---

**Project Repository**: `/home/user/S_01_v26-TrailingMA-Ultralight`

**Documentation**:
- `./docs/PROJECT_MIGRATION_PLAN_upd.md`
- `./docs/PROJECT_TARGET_ARCHITECTURE.md`
- `./docs/PROJECT_STRUCTURE.md`

**Reference Strategy**: `./docs/S_04 StochRSI_v02 no EMA Ultralight.pine`

**Good luck with the implementation! This is a critical validation phase for the entire architecture.**
