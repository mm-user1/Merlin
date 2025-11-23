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

### Test 2.3: Strategy Execution (Simple Test)
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

# Verify result structure
assert hasattr(result, 'net_profit_pct')
assert hasattr(result, 'max_drawdown_pct')
assert hasattr(result, 'total_trades')

print(f"Net Profit: {result.net_profit_pct:.2f}%")
print(f"Max DD: {result.max_drawdown_pct:.2f}%")
print(f"Trades: {result.total_trades}")
print("✓ Strategy execution successful")
```

## Completion Checklist

- [ ] `strategy.py` created with S01 logic
- [ ] Trading logic copied exactly from `backtest_engine.py`
- [ ] `__init__.py` created with registry
- [ ] Auto-discovery working
- [ ] All tests pass
- [ ] Git commit: "Migration Stage 2: Extract S01 strategy and create registry"

## Next Stage

Proceed to **migration_prompt_3.md** to update server.py with new endpoints.
