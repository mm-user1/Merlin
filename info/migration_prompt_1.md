# Migration Prompt 1: Base Infrastructure Setup

## Objective

Create the foundational infrastructure for the modular strategy system. This includes directory structure, base class, and configuration file for the existing S01 strategy.

## Context

You are migrating a hardcoded trading strategy system to support multiple strategies. Currently, the S01 Trailing MA strategy is embedded throughout the codebase. The goal is to extract it into a separate module while maintaining backward compatibility.

## Tasks

### Task 1.1: Create Directory Structure

Create the following directory structure:

```bash
mkdir -p src/strategies/s01_trailing_ma
touch src/strategies/__init__.py
touch src/strategies/base.py
```

**Expected files:**
- `src/strategies/__init__.py` (empty for now)
- `src/strategies/base.py` (will be created in Task 1.2)
- `src/strategies/s01_trailing_ma/` (directory)

### Task 1.2: Create Base Strategy Class

Create `src/strategies/base.py` with the following content:

```python
"""
Base Strategy Class
All trading strategies must inherit from this base class.
"""

from typing import Dict, Any
import pandas as pd
from backtest_engine import StrategyResult


class BaseStrategy:
    """
    Abstract base class for all trading strategies.

    All strategy implementations must define:
    - STRATEGY_ID: unique identifier (e.g., "s01_trailing_ma")
    - STRATEGY_NAME: human-readable name (e.g., "S01 Trailing MA")
    - STRATEGY_VERSION: version string (e.g., "v26")
    - run(): main trading logic implementation

    Optionally can define:
    - calculate_indicators(): for caching optimization (not used in MVP)
    """

    STRATEGY_ID = "base"
    STRATEGY_NAME = "Base Strategy"
    STRATEGY_VERSION = "v0"

    @staticmethod
    def calculate_indicators(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, pd.Series]:
        """
        Calculate technical indicators for the strategy.

        This method is optional and used for caching in optimization.
        Not implemented in MVP version.

        Args:
            df: OHLCV DataFrame
            params: Strategy parameters

        Returns:
            Dictionary of indicator name -> pd.Series
            Example: {"rsi": pd.Series(...), "bb_upper": pd.Series(...)}
        """
        return {}

    @staticmethod
    def run(
        df: pd.DataFrame,
        params: Dict[str, Any],
        trade_start_idx: int = 0
    ) -> StrategyResult:
        """
        Execute the trading strategy.

        Args:
            df: OHLCV DataFrame with columns [Open, High, Low, Close, Volume]
            params: Dictionary of strategy parameters
            trade_start_idx: Index to start trading (after warmup period)

        Returns:
            StrategyResult object with metrics and trade history
        """
        raise NotImplementedError("Strategy must implement run() method")
```

**Key points:**
- This is an abstract base class
- All strategies will inherit from it
- Defines the interface that all strategies must follow
- `calculate_indicators()` is optional (for future caching)
- `run()` must be implemented by each strategy

### Task 1.3: Create Config.json for S01 Strategy

Create `src/strategies/s01_trailing_ma/config.json` with all parameters from the current S01 strategy.

**IMPORTANT:** This file contains ALL 30+ parameters. Use the following structure:

```json
{
  "id": "s01_trailing_ma",
  "name": "S01 Trailing MA",
  "version": "v26",
  "description": "Moving Average crossover with trailing stops and ATR-based position sizing",
  "author": "",

  "parameters": {
    "maType": {
      "type": "select",
      "label": "Trend MA Type",
      "options": ["EMA", "SMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"],
      "default": "EMA",
      "group": "Entry",
      "optimize": {
        "enabled": false
      }
    },
    "maLength": {
      "type": "int",
      "label": "MA Length",
      "default": 45,
      "min": 1,
      "max": 500,
      "step": 1,
      "group": "Entry",
      "optimize": {
        "enabled": true,
        "min": 20,
        "max": 200,
        "step": 25
      }
    },
    "closeCountLong": {
      "type": "int",
      "label": "Close Count Long",
      "default": 7,
      "min": 0,
      "max": 50,
      "step": 1,
      "group": "Entry",
      "optimize": {
        "enabled": true,
        "min": 3,
        "max": 15,
        "step": 1
      }
    },
    "closeCountShort": {
      "type": "int",
      "label": "Close Count Short",
      "default": 5,
      "min": 0,
      "max": 50,
      "step": 1,
      "group": "Entry",
      "optimize": {
        "enabled": true,
        "min": 3,
        "max": 15,
        "step": 1
      }
    },

    "commissionRate": {
      "type": "float",
      "label": "Commission Rate",
      "default": 0.0005,
      "min": 0.0,
      "max": 0.01,
      "step": 0.0001,
      "group": "Risk",
      "optimize": {
        "enabled": false
      }
    },
    "contractSize": {
      "type": "float",
      "label": "Contract Size",
      "default": 0.01,
      "min": 0.001,
      "max": 1.0,
      "step": 0.001,
      "group": "Risk",
      "optimize": {
        "enabled": false
      }
    },
    "riskPerTrade": {
      "type": "float",
      "label": "Risk Per Trade (%)",
      "default": 2.0,
      "min": 0.1,
      "max": 10.0,
      "step": 0.1,
      "group": "Risk",
      "optimize": {
        "enabled": false
      }
    },
    "atrPeriod": {
      "type": "int",
      "label": "ATR Period",
      "default": 14,
      "min": 1,
      "max": 100,
      "step": 1,
      "group": "Risk",
      "optimize": {
        "enabled": false
      }
    },

    "stopLongX": {
      "type": "float",
      "label": "Stop Long ATR Multiple",
      "default": 2.0,
      "min": 0.0,
      "max": 10.0,
      "step": 0.1,
      "group": "Stops",
      "optimize": {
        "enabled": false
      }
    },
    "stopLongRR": {
      "type": "int",
      "label": "Stop Long Risk/Reward",
      "default": 3,
      "min": 1,
      "max": 10,
      "step": 1,
      "group": "Stops",
      "optimize": {
        "enabled": false
      }
    },
    "stopLongLP": {
      "type": "int",
      "label": "Stop Long Lookback Period",
      "default": 2,
      "min": 1,
      "max": 50,
      "step": 1,
      "group": "Stops",
      "optimize": {
        "enabled": false
      }
    },
    "stopShortX": {
      "type": "float",
      "label": "Stop Short ATR Multiple",
      "default": 2.0,
      "min": 0.0,
      "max": 10.0,
      "step": 0.1,
      "group": "Stops",
      "optimize": {
        "enabled": false
      }
    },
    "stopShortRR": {
      "type": "int",
      "label": "Stop Short Risk/Reward",
      "default": 3,
      "min": 1,
      "max": 10,
      "step": 1,
      "group": "Stops",
      "optimize": {
        "enabled": false
      }
    },
    "stopShortLP": {
      "type": "int",
      "label": "Stop Short Lookback Period",
      "default": 2,
      "min": 1,
      "max": 50,
      "step": 1,
      "group": "Stops",
      "optimize": {
        "enabled": false
      }
    },
    "stopLongMaxPct": {
      "type": "float",
      "label": "Stop Long Max %",
      "default": 3.0,
      "min": 0.0,
      "max": 50.0,
      "step": 0.5,
      "group": "Stops",
      "optimize": {
        "enabled": false
      }
    },
    "stopShortMaxPct": {
      "type": "float",
      "label": "Stop Short Max %",
      "default": 3.0,
      "min": 0.0,
      "max": 50.0,
      "step": 0.5,
      "group": "Stops",
      "optimize": {
        "enabled": false
      }
    },
    "stopLongMaxDays": {
      "type": "int",
      "label": "Stop Long Max Days",
      "default": 2,
      "min": 0,
      "max": 100,
      "step": 1,
      "group": "Stops",
      "optimize": {
        "enabled": false
      }
    },
    "stopShortMaxDays": {
      "type": "int",
      "label": "Stop Short Max Days",
      "default": 4,
      "min": 0,
      "max": 100,
      "step": 1,
      "group": "Stops",
      "optimize": {
        "enabled": false
      }
    },
    "trailRRLong": {
      "type": "float",
      "label": "Trail RR Long",
      "default": 1.0,
      "min": 0.0,
      "max": 10.0,
      "step": 0.1,
      "group": "Trail",
      "optimize": {
        "enabled": false
      }
    },
    "trailRRShort": {
      "type": "float",
      "label": "Trail RR Short",
      "default": 1.0,
      "min": 0.0,
      "max": 10.0,
      "step": 0.1,
      "group": "Trail",
      "optimize": {
        "enabled": false
      }
    },
    "trailLongType": {
      "type": "select",
      "label": "Trail Long MA Type",
      "options": ["EMA", "SMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"],
      "default": "SMA",
      "group": "Trail",
      "optimize": {
        "enabled": false
      }
    },
    "trailLongLength": {
      "type": "int",
      "label": "Trail Long MA Length",
      "default": 160,
      "min": 0,
      "max": 500,
      "step": 1,
      "group": "Trail",
      "optimize": {
        "enabled": false
      }
    },
    "trailLongOffset": {
      "type": "float",
      "label": "Trail Long Offset %",
      "default": -1.0,
      "min": -10.0,
      "max": 10.0,
      "step": 0.1,
      "group": "Trail",
      "optimize": {
        "enabled": false
      }
    },
    "trailShortType": {
      "type": "select",
      "label": "Trail Short MA Type",
      "options": ["EMA", "SMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"],
      "default": "SMA",
      "group": "Trail",
      "optimize": {
        "enabled": false
      }
    },
    "trailShortLength": {
      "type": "int",
      "label": "Trail Short MA Length",
      "default": 160,
      "min": 0,
      "max": 500,
      "step": 1,
      "group": "Trail",
      "optimize": {
        "enabled": false
      }
    },
    "trailShortOffset": {
      "type": "float",
      "label": "Trail Short Offset %",
      "default": 1.0,
      "min": -10.0,
      "max": 10.0,
      "step": 0.1,
      "group": "Trail",
      "optimize": {
        "enabled": false
      }
    }
  }
}
```

**The config.json above contains ALL 22 parameters from S01 strategy:**

**Entry group (4 params):**
- maType, maLength, closeCountLong, closeCountShort

**Risk group - Platform parameters (4 params):**
- commissionRate, contractSize, riskPerTrade, atrPeriod

**Stops group (10 params):**
- stopLongX, stopLongRR, stopLongLP
- stopShortX, stopShortRR, stopShortLP
- stopLongMaxPct, stopShortMaxPct
- stopLongMaxDays, stopShortMaxDays

**Trail group (8 params):**
- trailRRLong, trailRRShort
- trailLongType, trailLongLength, trailLongOffset
- trailShortType, trailShortLength, trailShortOffset

**IMPORTANT about platform parameters (Risk group):**

The 4 "Risk" group parameters have `"optimize": {"enabled": false}`:
- ✅ They WILL appear in Backtester forms (Section 1)
- ❌ They will NOT appear in Optimizer forms (Section 2)
- These are platform/risk management settings, not strategy trading logic
- This separation was implemented based on user requirement to keep platform settings visible but not optimizable

**Reference the current DEFAULT_PRESET in server.py for default values.**

Group parameters logically:
- `"group": "Entry"` - entry logic parameters
- `"group": "Stops"` - stop loss parameters
- `"group": "Trail"` - trailing exit parameters
- `"group": "Risk"` - position sizing and risk management

## Testing

After completing all tasks, verify:

### Test 1.1: Directory Structure
```bash
# Check directories exist
ls -la src/strategies/
ls -la src/strategies/s01_trailing_ma/

# Expected output:
# src/strategies/__init__.py
# src/strategies/base.py
# src/strategies/s01_trailing_ma/config.json
```

### Test 1.2: Base Class Import
```python
# Run in Python console
from strategies.base import BaseStrategy
print(BaseStrategy.STRATEGY_ID)
# Expected: "base"
```

### Test 1.3: Config.json Validation
```python
import json
with open('src/strategies/s01_trailing_ma/config.json', 'r') as f:
    config = json.load(f)

# Verify structure
assert config['id'] == 's01_trailing_ma'
assert config['name'] == 'S01 Trailing MA'
assert 'parameters' in config
assert len(config['parameters']) >= 20  # Should have 20+ parameters

# Verify a sample parameter
ma_type = config['parameters']['maType']
assert ma_type['type'] == 'select'
assert 'EMA' in ma_type['options']
assert ma_type['default'] == 'EMA'

print("✓ Config validation passed")
```

## Reference Test

A comprehensive reference test with specific parameters and expected results is provided in **migration_prompt_5.md** (Stage 5). This test will validate that the migration produces identical results to the original hardcoded implementation.

**Note:** The test can only be executed after completing all migration stages.

## Completion Checklist

- [ ] Directory structure created
- [ ] `base.py` created with BaseStrategy class
- [ ] `config.json` created with all S01 parameters
- [ ] All tests pass
- [ ] Git commit: "Migration Stage 1: Base infrastructure setup"

## Next Stage

Proceed to **migration_prompt_2.md** to extract the S01 strategy logic and create the registry.
