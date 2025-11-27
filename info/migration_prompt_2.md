# Migration Prompt 2: Extract Strategy & Create Registry

## Objective

Extract the current S01 strategy logic from `backtest_engine.py` into a separate strategy module and create an auto-discovery registry system.

## Prerequisites

Complete **migration_prompt_1.md** before starting this stage.

## Context

The S01 Trailing MA strategy logic is currently embedded in `backtest_engine.py` as the `run_strategy()` function. We need to move this logic into `src/strategies/s01_trailing_ma/strategy.py` while keeping the original function intact for backward compatibility.

---

## ⚠️ Important: Separation of Concerns

Before implementing the strategy module, understand the **strict separation** between Platform and Strategy:

### **Strategies are responsible for:**
✅ Trading logic (when to enter/exit positions)
✅ Computing indicators (MA, ATR, RSI, MACD, etc.)
✅ Calculating metrics (profit %, drawdown, sharpe ratio, etc.)
✅ Generating trade records (entry/exit timestamps, prices, PnL)

### **The platform is responsible for:**
✅ Date filtering and warmup period management
✅ Optimization workflows (Grid Search, Optuna, Walk-Forward Analysis)
✅ Filtering results (Score Filter, Net Profit Filter)
✅ CSV/ZIP export functionality
✅ UI rendering and dynamic form generation
✅ Preset management

### **Strategies should NOT:**
❌ Know about optimization settings or optimization mode
❌ Handle date filtering (platform already filtered the data)
❌ Calculate composite scores (platform does this from returned metrics)
❌ Export files or format output (platform handles all exports)
❌ Know whether they're being called from backtest, optimizer, or WFA

### **Strategies are pure functions:**
```python
# Given the same inputs, always produce the same output (deterministic)
result = strategy.run(df, params, trade_start_idx)
# Strategy doesn't maintain state, doesn't know about external context
```

**Why this matters:**
- ✅ Strategies stay simple and focused on trading logic only
- ✅ Platform features (optimization, filtering, export) work with ALL strategies
- ✅ Easy to test strategies independently
- ✅ Adding new strategies doesn't require changing platform code

**Example:** When Score Filter is enabled in the UI, the **platform** calculates composite score from metrics and filters results. The **strategy** just returns metrics (sharpe, romad, etc.) - it doesn't even know Score Filter exists.

---

## Tasks

### Task 2.1: Create S01 Strategy Module

Create `src/strategies/s01_trailing_ma/strategy.py` by extracting logic from `backtest_engine.py`.

**Steps:**

1. Open `src/backtest_engine.py` and locate the `run_strategy()` function (approximately line 380-940)

2. Create `src/strategies/s01_trailing_ma/strategy.py` with the following structure:

```python
"""
S01 Trailing MA Strategy - v26 Ultralight
Moving Average crossover with trailing stops and ATR-based position sizing
"""

import math
from typing import Dict, Any
import pandas as pd
import numpy as np

from backtest_engine import (
    get_ma, atr, compute_max_drawdown,
    StrategyResult, TradeRecord
)
from strategies.base import BaseStrategy


class S01TrailingMA(BaseStrategy):
    """
    S01 Trailing MA Strategy Implementation

    Entry Logic:
    - Long: Close crosses above MA for N consecutive bars (closeCountLong)
    - Short: Close crosses below MA for N consecutive bars (closeCountShort)

    Exit Logic:
    - ATR-based stops
    - Risk/Reward targets
    - Trailing MA exits
    - Max % loss stops
    - Max days in trade stops
    """

    STRATEGY_ID = "s01_trailing_ma"
    STRATEGY_NAME = "S01 Trailing MA"
    STRATEGY_VERSION = "v26"

    @staticmethod
    def calculate_indicators(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, pd.Series]:
        """
        Calculate all indicators needed for the strategy.

        Note: This method is not used in MVP (no caching optimization).
        Kept for future compatibility.
        """
        return {}

    @staticmethod
    def run(
        df: pd.DataFrame,
        params: Dict[str, Any],
        trade_start_idx: int = 0
    ) -> StrategyResult:
        """
        Execute S01 Trailing MA strategy.

        IMPORTANT: This is a direct copy of the logic from backtest_engine.run_strategy()
        DO NOT modify the trading logic - only adapt it to work with Dict[str, Any] params
        instead of StrategyParams dataclass.
        """

        # Extract parameters from dict (instead of dataclass attributes)
        ma_type = params.get('maType', 'EMA')
        ma_length = params.get('maLength', 45)
        close_count_long = params.get('closeCountLong', 7)
        close_count_short = params.get('closeCountShort', 5)

        # Stop parameters
        stop_long_atr = params.get('stopLongX', 2.0)
        stop_long_rr = params.get('stopLongRR', 3.0)
        stop_long_lp = params.get('stopLongLP', 2)
        stop_short_atr = params.get('stopShortX', 2.0)
        stop_short_rr = params.get('stopShortRR', 3.0)
        stop_short_lp = params.get('stopShortLP', 2)

        # Max stop parameters
        stop_long_max_pct = params.get('stopLongMaxPct', 3.0)
        stop_short_max_pct = params.get('stopShortMaxPct', 3.0)
        stop_long_max_days = params.get('stopLongMaxDays', 2)
        stop_short_max_days = params.get('stopShortMaxDays', 4)

        # Trail parameters
        trail_rr_long = params.get('trailRRLong', 1.0)
        trail_rr_short = params.get('trailRRShort', 1.0)
        trail_ma_long_type = params.get('trailLongType', 'SMA')
        trail_ma_long_length = params.get('trailLongLength', 160)
        trail_ma_long_offset = params.get('trailLongOffset', -1.0)
        trail_ma_short_type = params.get('trailShortType', 'SMA')
        trail_ma_short_length = params.get('trailShortLength', 160)
        trail_ma_short_offset = params.get('trailShortOffset', 1.0)

        # Risk parameters
        risk_per_trade_pct = params.get('riskPerTrade', 2.0)
        contract_size = params.get('contractSize', 0.01)
        commission_rate = params.get('commissionRate', 0.0005)
        atr_period = params.get('atrPeriod', 14)

        # ========================================
        # COPY THE REST OF run_strategy() HERE
        # ========================================

        # Calculate indicators
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]
        times = df.index

        # Main MA
        ma_series = get_ma(close, ma_type, ma_length, volume, high, low)

        # ATR
        atr_series = atr(high, low, close, atr_period)

        # Lowest/Highest for stops
        lowest_long = low.rolling(stop_long_lp, min_periods=1).min()
        highest_short = high.rolling(stop_short_lp, min_periods=1).max()

        # Trail MAs
        trail_ma_long = get_ma(close, trail_ma_long_type, trail_ma_long_length, volume, high, low)
        if trail_ma_long_length > 0:
            trail_ma_long = trail_ma_long * (1.0 + trail_ma_long_offset / 100.0)

        trail_ma_short = get_ma(close, trail_ma_short_type, trail_ma_short_length, volume, high, low)
        if trail_ma_short_length > 0:
            trail_ma_short = trail_ma_short * (1.0 + trail_ma_short_offset / 100.0)

        # Time in range
        time_in_range = np.zeros(len(times), dtype=bool)
        time_in_range[trade_start_idx:] = True

        # Trading loop - COPY EXACTLY FROM backtest_engine.py
        equity = 100.0
        realized_equity = equity
        position = 0
        prev_position = 0
        trades = []
        realized_curve = []

        # ... (COPY ALL THE TRADING LOOP LOGIC FROM backtest_engine.py)
        # This is approximately 500 lines of code
        # DO NOT modify the logic, just copy it exactly

        # Final metrics
        equity_series = pd.Series(realized_curve, index=df.index[:len(realized_curve)])
        net_profit_pct = ((realized_equity - equity) / equity) * 100
        max_drawdown_pct = compute_max_drawdown(equity_series)
        total_trades = len(trades)

        return StrategyResult(
            net_profit_pct=net_profit_pct,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            trades=trades
        )
```

**CRITICAL:** Copy the ENTIRE trading loop from `run_strategy()` without modifications. Only change:
- Parameter access: `params.ma_type` → `params.get('maType', 'EMA')`
- Keep all trading logic identical

### Task 2.2: Create Strategy Registry

Create `src/strategies/__init__.py` with auto-discovery functionality:

```python
"""
Strategy Registry - Auto-discovery system for trading strategies

This module automatically discovers all strategies in the strategies/ directory
and provides a unified interface for accessing them.
"""

import json
import importlib
from pathlib import Path
from typing import Dict, Any, List, Optional

STRATEGIES_DIR = Path(__file__).parent
_REGISTRY: Dict[str, Dict[str, Any]] = {}


def _discover_strategies():
    """
    Auto-discover all strategies by scanning subdirectories.

    Each strategy must have:
    - config.json (metadata and parameters)
    - strategy.py (trading logic)

    Strategies are registered in _REGISTRY dictionary.
    """
    global _REGISTRY

    for item in STRATEGIES_DIR.iterdir():
        # Skip non-directories and private directories
        if not item.is_dir() or item.name.startswith('_'):
            continue

        # Check for required files
        config_file = item / 'config.json'
        strategy_file = item / 'strategy.py'

        if not (config_file.exists() and strategy_file.exists()):
            print(f"Warning: Incomplete strategy in {item.name}, skipping")
            continue

        # Load config
        try:
            with config_file.open('r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {config_file}: {e}")
            continue

        strategy_id = config.get('id', item.name)

        # Dynamically import strategy module
        module_name = f"strategies.{item.name}.strategy"
        try:
            module = importlib.import_module(module_name)

            # Find strategy class (looks for class with 'run' method)
            strategy_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    hasattr(attr, 'run') and
                    hasattr(attr, 'STRATEGY_ID')):
                    strategy_class = attr
                    break

            if strategy_class is None:
                print(f"Warning: No valid strategy class found in {module_name}")
                continue

            # Register strategy
            _REGISTRY[strategy_id] = {
                'class': strategy_class,
                'config': config,
                'path': item
            }

        except Exception as e:
            print(f"Error loading strategy {item.name}: {e}")
            continue


def get_strategy(strategy_id: str):
    """
    Get strategy class by ID.

    Args:
        strategy_id: Strategy identifier (e.g., 's01_trailing_ma')

    Returns:
        Strategy class

    Raises:
        ValueError: If strategy not found
    """
    if strategy_id not in _REGISTRY:
        available = list(_REGISTRY.keys())
        raise ValueError(
            f"Unknown strategy: {strategy_id}. "
            f"Available strategies: {available}"
        )
    return _REGISTRY[strategy_id]['class']


def get_strategy_config(strategy_id: str) -> Dict[str, Any]:
    """
    Get strategy configuration (from config.json).

    Args:
        strategy_id: Strategy identifier

    Returns:
        Dictionary with strategy metadata and parameters

    Raises:
        ValueError: If strategy not found
    """
    if strategy_id not in _REGISTRY:
        raise ValueError(f"Unknown strategy: {strategy_id}")
    return _REGISTRY[strategy_id]['config']


def list_strategies() -> List[Dict[str, Any]]:
    """
    List all available strategies.

    Returns:
        List of dictionaries with strategy metadata:
        [
            {
                'id': 's01_trailing_ma',
                'name': 'S01 Trailing MA',
                'version': 'v26',
                'description': '...',
                ...
            }
        ]
    """
    result = []
    for strategy_id, data in _REGISTRY.items():
        config = data['config']
        result.append({
            'id': strategy_id,
            'name': config.get('name', strategy_id),
            'version': config.get('version', 'unknown'),
            'description': config.get('description', ''),
            'author': config.get('author', '')
        })
    return result


# Auto-discover strategies on module import
_discover_strategies()


# Print discovered strategies (for debugging)
if _REGISTRY:
    print(f"Discovered {len(_REGISTRY)} strategy(ies): {list(_REGISTRY.keys())}")
else:
    print("Warning: No strategies discovered")
```

### Task 2.3: Extend StrategyResult with Optional Metrics

**CRITICAL for Stage 6:** The optimizer engines (Grid/Optuna) need additional risk metrics for scoring. These metrics are currently calculated inside `optimizer_engine.py`, but on Stage 6 we'll replace that logic with `strategy.run()`. Therefore, strategies must return these metrics.

**File:** `src/backtest_engine.py`

**Find the `StrategyResult` dataclass (around line 72):**
```python
@dataclass
class StrategyResult:
    net_profit_pct: float
    max_drawdown_pct: float
    total_trades: int
    trades: List[TradeRecord]
```

**Replace with extended version:**
```python
@dataclass
class StrategyResult:
    """
    Result object returned by strategy.run()

    Contains both basic metrics (always required) and advanced metrics
    (optional, used for optimization scoring).
    """

    # Basic metrics (always required)
    net_profit_pct: float
    max_drawdown_pct: float
    total_trades: int
    trades: List[TradeRecord]

    # Advanced metrics (optional, for optimization scoring)
    # These are calculated from trades and equity curve
    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    romad: Optional[float] = None  # Return Over Maximum Drawdown
    ulcer_index: Optional[float] = None
    recovery_factor: Optional[float] = None
    consistency_score: Optional[float] = None  # % of profitable months
```

**Why Optional?**
- Simple backtests may not need these metrics
- Metrics require sufficient data (e.g., Sharpe needs ≥2 monthly periods)
- Failed backtests (no trades) return None for optional metrics

### Task 2.4: Add Metric Calculation Functions to backtest_engine.py

Add helper functions to calculate advanced metrics. These functions will be used by strategies to compute optional metrics.

**File:** `src/backtest_engine.py`

**Add these functions at the end of the file, before `run_strategy()`:**

```python
# ============================================
# ADVANCED METRICS CALCULATION
# ============================================

def calculate_monthly_returns(
    equity_curve: List[float],
    time_index: pd.DatetimeIndex
) -> List[float]:
    """
    Calculate monthly returns from equity curve.

    Args:
        equity_curve: List of equity values (one per bar)
        time_index: Datetime index aligned with equity_curve

    Returns:
        List of monthly returns (in %)
    """
    if not equity_curve or len(equity_curve) != len(time_index):
        return []

    monthly_returns = []
    current_month = None
    month_start_equity = None

    for i, (equity, timestamp) in enumerate(zip(equity_curve, time_index)):
        month_key = (timestamp.year, timestamp.month)

        if current_month is None:
            # First month
            current_month = month_key
            month_start_equity = equity
        elif month_key != current_month:
            # Month changed - record return
            if month_start_equity is not None and month_start_equity > 0:
                monthly_return = ((equity / month_start_equity) - 1.0) * 100.0
                monthly_returns.append(monthly_return)

            # Start new month
            current_month = month_key
            month_start_equity = equity

    # Record last month if data exists
    if month_start_equity is not None and month_start_equity > 0 and equity_curve:
        last_equity = equity_curve[-1]
        monthly_return = ((last_equity / month_start_equity) - 1.0) * 100.0
        monthly_returns.append(monthly_return)

    return monthly_returns


def calculate_profit_factor(trades: List[TradeRecord]) -> Optional[float]:
    """
    Calculate profit factor (gross profit / gross loss).

    Args:
        trades: List of completed trades

    Returns:
        Profit factor (None if no trades or no data)
    """
    if not trades:
        return None

    gross_profit = sum(t.profit_pct for t in trades if t.profit_pct > 0)
    gross_loss = abs(sum(t.profit_pct for t in trades if t.profit_pct < 0))

    if gross_loss > 0:
        return gross_profit / gross_loss
    elif gross_profit > 0:
        return 999.0  # Infinite profit factor (no losses)
    else:
        return 1.0  # No profit, no loss


def calculate_sharpe_ratio(monthly_returns: List[float], risk_free_rate: float = 0.02) -> Optional[float]:
    """
    Calculate annualized Sharpe ratio.

    Args:
        monthly_returns: List of monthly returns (in %)
        risk_free_rate: Annual risk-free rate (default 2%)

    Returns:
        Sharpe ratio (None if insufficient data)
    """
    if len(monthly_returns) < 2:
        return None

    monthly_array = np.array(monthly_returns, dtype=float)
    if monthly_array.size < 2:
        return None

    avg_return = float(np.mean(monthly_array))
    sd_return = float(np.std(monthly_array, ddof=0))

    if sd_return == 0:
        return None

    # Risk-free rate per month
    rfr_monthly = (risk_free_rate * 100.0) / 12.0

    sharpe = (avg_return - rfr_monthly) / sd_return
    return sharpe


def calculate_ulcer_index(equity_curve: List[float]) -> Optional[float]:
    """
    Calculate Ulcer Index (measure of downside volatility).

    Args:
        equity_curve: List of equity values

    Returns:
        Ulcer Index (in %, None if no data)
    """
    if not equity_curve:
        return None

    equity_array = np.asarray(equity_curve, dtype=float)
    if equity_array.size == 0:
        return None

    # Calculate running maximum
    running_max = np.maximum.accumulate(equity_array)

    # Calculate drawdowns as percentage from peak
    with np.errstate(divide='ignore', invalid='ignore'):
        drawdowns = np.where(running_max > 0, equity_array / running_max - 1.0, 0.0)

    # Ulcer Index = sqrt(sum of squared drawdowns / N)
    drawdown_squared_sum = float(np.square(drawdowns).sum())
    ulcer = math.sqrt(drawdown_squared_sum / equity_array.size) * 100.0

    return ulcer


def calculate_consistency_score(monthly_returns: List[float]) -> Optional[float]:
    """
    Calculate consistency score (% of profitable months).

    Args:
        monthly_returns: List of monthly returns (in %)

    Returns:
        Consistency score (0-100%, None if insufficient data)
    """
    if len(monthly_returns) < 3:
        return None

    total_months = len(monthly_returns)
    profitable_months = sum(1 for ret in monthly_returns if ret > 0)

    consistency = (profitable_months / total_months) * 100.0
    return consistency


def calculate_advanced_metrics(
    equity_curve: List[float],
    time_index: pd.DatetimeIndex,
    trades: List[TradeRecord],
    net_profit_pct: float,
    max_drawdown_pct: float
) -> dict:
    """
    Calculate all advanced metrics from equity curve and trades.

    This is a convenience function that calls all individual metric functions.

    Args:
        equity_curve: List of equity values (one per bar)
        time_index: Datetime index aligned with equity_curve
        trades: List of completed trades
        net_profit_pct: Net profit percentage
        max_drawdown_pct: Maximum drawdown percentage

    Returns:
        Dictionary with all advanced metrics (keys: sharpe_ratio, profit_factor, etc.)
    """
    # Calculate monthly returns
    monthly_returns = calculate_monthly_returns(equity_curve, time_index)

    # Profit factor
    profit_factor = calculate_profit_factor(trades)

    # Sharpe ratio
    sharpe_ratio = calculate_sharpe_ratio(monthly_returns)

    # Ulcer Index
    ulcer_index = calculate_ulcer_index(equity_curve)

    # Consistency score
    consistency_score = calculate_consistency_score(monthly_returns)

    # RoMaD (Return Over Maximum Drawdown)
    romad: Optional[float] = None
    if net_profit_pct >= 0:
        if abs(max_drawdown_pct) < 1e-9:
            romad = net_profit_pct * 100.0  # No drawdown
        elif max_drawdown_pct != 0:
            romad = net_profit_pct / abs(max_drawdown_pct)
        else:
            romad = 0.0
    else:
        romad = 0.0  # Negative profit

    # Recovery Factor (same as RoMaD in this implementation)
    recovery_factor = romad

    return {
        'sharpe_ratio': sharpe_ratio,
        'profit_factor': profit_factor,
        'romad': romad,
        'ulcer_index': ulcer_index,
        'recovery_factor': recovery_factor,
        'consistency_score': consistency_score,
    }
```

**Note:** These functions are extracted from the current `optimizer_engine.py:667-707`. They will be removed from `optimizer_engine.py` on Stage 6.

### Task 2.5: Update S01 Strategy to Calculate and Return Metrics

Now update the S01 strategy's `run()` method to calculate and return advanced metrics.

**File:** `src/strategies/s01_trailing_ma/strategy.py`

**Find the return statement at the end of `run()` method (around line 220):**
```python
        return StrategyResult(
            net_profit_pct=net_profit_pct,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            trades=trades
        )
```

**Replace with extended version that calculates metrics:**
```python
        # Calculate advanced metrics for optimization scoring
        # These are optional - if calculation fails, metrics will be None
        from backtest_engine import calculate_advanced_metrics

        advanced_metrics = calculate_advanced_metrics(
            equity_curve=realized_curve,
            time_index=df.index[:len(realized_curve)],
            trades=trades,
            net_profit_pct=net_profit_pct,
            max_drawdown_pct=max_drawdown_pct
        )

        return StrategyResult(
            net_profit_pct=net_profit_pct,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            trades=trades,

            # Advanced metrics (optional)
            sharpe_ratio=advanced_metrics['sharpe_ratio'],
            profit_factor=advanced_metrics['profit_factor'],
            romad=advanced_metrics['romad'],
            ulcer_index=advanced_metrics['ulcer_index'],
            recovery_factor=advanced_metrics['recovery_factor'],
            consistency_score=advanced_metrics['consistency_score'],
        )
```

**IMPORTANT:** Make sure `realized_curve` (equity curve) is accumulated during the trading loop. This should already exist in the code copied from `run_strategy()`.

**Why this matters:**
- On Stage 6, we'll replace `optimizer_engine._simulate_combination()` with `strategy.run()`
- The optimizer expects all these metrics to calculate composite scores
- By adding metrics now, Stage 6 will work seamlessly

## Testing

### Test 2.1: Strategy Module Import
```python
from strategies.s01_trailing_ma.strategy import S01TrailingMA

# Verify metadata
assert S01TrailingMA.STRATEGY_ID == "s01_trailing_ma"
assert S01TrailingMA.STRATEGY_NAME == "S01 Trailing MA"
assert S01TrailingMA.STRATEGY_VERSION == "v26"

print("✓ S01 strategy module imported successfully")
```

### Test 2.2: Registry Auto-Discovery
```python
from strategies import list_strategies, get_strategy, get_strategy_config

# List strategies
strategies = list_strategies()
print(f"Discovered strategies: {strategies}")

# Should find S01
assert len(strategies) >= 1
assert any(s['id'] == 's01_trailing_ma' for s in strategies)

# Get strategy class
S01 = get_strategy('s01_trailing_ma')
assert S01.STRATEGY_ID == 's01_trailing_ma'

# Get config
config = get_strategy_config('s01_trailing_ma')
assert config['id'] == 's01_trailing_ma'
assert 'parameters' in config

print("✓ Registry working correctly")
```

### Test 2.3: Strategy Execution with Metrics
```python
import pandas as pd
from strategies import get_strategy

# Load test data
df = pd.read_csv('data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv')
df['Date'] = pd.to_datetime(df['Date'])
df.set_index('Date', inplace=True)

# Get strategy
S01 = get_strategy('s01_trailing_ma')

# Run with default parameters
params = {
    'maType': 'SMA',
    'maLength': 45,
    'closeCountLong': 7,
    'closeCountShort': 5,
    'stopLongX': 2.0,
    'stopLongRR': 3.0,
    # ... (use defaults from config.json)
}

result = S01.run(df, params, trade_start_idx=0)

# Verify basic metrics
assert hasattr(result, 'net_profit_pct')
assert hasattr(result, 'max_drawdown_pct')
assert hasattr(result, 'total_trades')

# Verify advanced metrics exist (may be None if insufficient data)
assert hasattr(result, 'sharpe_ratio')
assert hasattr(result, 'profit_factor')
assert hasattr(result, 'romad')
assert hasattr(result, 'ulcer_index')
assert hasattr(result, 'recovery_factor')
assert hasattr(result, 'consistency_score')

print(f"Net Profit: {result.net_profit_pct:.2f}%")
print(f"Max DD: {result.max_drawdown_pct:.2f}%")
print(f"Trades: {result.total_trades}")
print(f"Sharpe: {result.sharpe_ratio if result.sharpe_ratio else 'N/A'}")
print(f"Profit Factor: {result.profit_factor if result.profit_factor else 'N/A'}")
print(f"RoMaD: {result.romad if result.romad else 'N/A'}")
print("✓ Strategy execution successful with all metrics")
```

### Test 2.4: Verify Metric Calculation Functions
```python
from backtest_engine import (
    calculate_monthly_returns,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_ulcer_index,
    calculate_consistency_score,
    calculate_advanced_metrics,
    TradeRecord
)
import pandas as pd
import numpy as np

# Test monthly returns calculation
equity_curve = [100, 102, 105, 103, 108]
time_index = pd.date_range('2025-01-01', periods=5, freq='D')
monthly_returns = calculate_monthly_returns(equity_curve, time_index)
assert isinstance(monthly_returns, list)
print(f"✓ Monthly returns: {monthly_returns}")

# Test profit factor
trades = [
    TradeRecord(entry_time=pd.Timestamp('2025-01-01'), exit_time=pd.Timestamp('2025-01-02'),
                side='LONG', entry_price=100, exit_price=105, profit_pct=5.0),
    TradeRecord(entry_time=pd.Timestamp('2025-01-03'), exit_time=pd.Timestamp('2025-01-04'),
                side='SHORT', entry_price=105, exit_price=103, profit_pct=2.0),
    TradeRecord(entry_time=pd.Timestamp('2025-01-05'), exit_time=pd.Timestamp('2025-01-06'),
                side='LONG', entry_price=103, exit_price=100, profit_pct=-3.0),
]
pf = calculate_profit_factor(trades)
assert pf is not None and pf > 0
print(f"✓ Profit factor: {pf:.2f}")

# Test advanced metrics function
metrics = calculate_advanced_metrics(
    equity_curve=[100, 105, 103, 108, 110],
    time_index=pd.date_range('2025-01-01', periods=5, freq='D'),
    trades=trades,
    net_profit_pct=10.0,
    max_drawdown_pct=5.0
)
assert 'sharpe_ratio' in metrics
assert 'profit_factor' in metrics
assert 'romad' in metrics
print(f"✓ Advanced metrics calculated: {list(metrics.keys())}")
print("✓ All metric calculation functions working")
```

## Completion Checklist

- [ ] `strategy.py` created with S01 logic
- [ ] Trading logic copied exactly from `backtest_engine.py`
- [ ] **`StrategyResult` extended with Optional metrics**
- [ ] **Metric calculation functions added to `backtest_engine.py`**
- [ ] **S01 strategy updated to calculate and return all metrics**
- [ ] `__init__.py` created with registry
- [ ] Auto-discovery working
- [ ] All tests pass (including metric tests)
- [ ] Git commit: "Migration Stage 2: Extract S01 strategy, add metrics, and create registry"

## Next Stage

Proceed to **migration_prompt_3.md** to update server.py with new endpoints.
