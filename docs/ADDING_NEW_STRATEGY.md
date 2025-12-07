# Adding a New Strategy

This guide explains how to onboard a new strategy into the platform using the hybrid architecture (typed strategies + generic core).

## Quick Start

```bash
# 1. Create directory
mkdir -p src/strategies/s05_mystrategy

# 2. Create files
touch src/strategies/s05_mystrategy/__init__.py
cat > src/strategies/s05_mystrategy/config.json <<'JSON'
{
  "id": "s05_mystrategy",
  "name": "S05 My Strategy",
  "version": "v01",
  "description": "Brief description",
  "parameters": {}
}
JSON
touch src/strategies/s05_mystrategy/strategy.py
```

## Step 1: Create Strategy Directory

1. Choose a unique strategy id (e.g., `s05_mystrategy`).
2. Create a new directory under `src/strategies/` with that id.
3. Add `__init__.py` so Python treats the directory as a package.

## Step 2: Define `config.json`

`config.json` declares metadata and parameter schema in camelCase.

```json
{
  "id": "s05_mystrategy",
  "name": "S05 My Strategy",
  "version": "v01",
  "description": "Short description of the idea",
  "parameters": {
    "rsiLen": {
      "type": "int",
      "label": "RSI Length",
      "default": 14,
      "min": 2,
      "max": 100,
      "group": "Indicators"
    },
    "threshold": {
      "type": "float",
      "label": "Entry Threshold",
      "default": 0.5,
      "min": 0.0,
      "max": 1.0
    }
  }
}
```

**Rules**
- Parameter names must match Pine Script names exactly and remain camelCase.
- Allowed `type` values: `int`, `float`, `select`, `options`, `bool`, `boolean`.
- `select`/`options` entries must include a non-empty `options` array.
- Do **not** add feature flags; use parameter definitions instead.

## Step 3: Define Params Dataclass (camelCase)

Implement a typed dataclass inside `strategy.py`.

```python
from dataclasses import dataclass
from typing import Any, Dict, Optional
import pandas as pd

@dataclass
class S05Params:
    """S05 strategy parameters - camelCase matching Pine Script."""
    use_backtester: bool = True
    use_date_filter: bool = True
    start: Optional[pd.Timestamp] = None
    end: Optional[pd.Timestamp] = None
    rsiLen: int = 14
    threshold: float = 0.5

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "S05Params":
        """Direct mapping - no snake_case/camelCase conversion."""
        start = d.get("start")
        end = d.get("end")
        if isinstance(start, str):
            start = pd.Timestamp(start, tz="UTC")
        if isinstance(end, str):
            end = pd.Timestamp(end, tz="UTC")

        return cls(
            use_backtester=bool(d.get("backtester", True)),
            use_date_filter=bool(d.get("dateFilter", True)),
            start=start,
            end=end,
            rsiLen=int(d.get("rsiLen", cls.rsiLen)),
            threshold=float(d.get("threshold", cls.threshold)),
        )
```

**Rules**
- Field names stay camelCase (except internal `use_backtester`, `use_date_filter`, `start`, `end`).
- Do **not** add `to_dict()`; use `dataclasses.asdict` where needed.
- `from_dict` must map directly without snake_case fallbacks.

## Step 4: Implement Strategy Class

Implement trading logic in `strategy.py` using the dataclass.

```python
from typing import Any, Dict
import pandas as pd

from core.backtest_engine import StrategyResult
from strategies.base import BaseStrategy

class S05MyStrategy(BaseStrategy):
    STRATEGY_ID = "s05_mystrategy"
    STRATEGY_NAME = "S05 My Strategy"
    STRATEGY_VERSION = "v01"

    @staticmethod
    def run(df: pd.DataFrame, params: Dict[str, Any], trade_start_idx: int = 0) -> StrategyResult:
        p = S05Params.from_dict(params)
        # Implement entry/exit logic using `p` and `df`
        # Return StrategyResult containing trades and metrics
```

**Rules**
- Strategy runs receive dict params, immediately convert with `from_dict`.
- Keep logic self-contained; core modules are strategy-agnostic.

## Step 5: Register Strategy

Strategies are auto-discovered. Ensure:
- `config.json` and `strategy.py` both exist.
- `strategy.py` defines one class with `STRATEGY_ID`, `STRATEGY_NAME`, `STRATEGY_VERSION`, and a static `run` method.

`strategies/__init__.py` will register the strategy on import; no manual registry edits needed.

## Step 6: Test

1. Add unit tests mirroring existing S01/S04 coverage.
2. Add regression baselines if needed (metrics, trades CSV).
3. Run `pytest -v` and ensure all naming consistency tests pass.

## Common Mistakes to Avoid
- ❌ Using snake_case parameter names (`ma_type`, `rsi_len`).
- ❌ Adding conversion helpers (`to_dict`, snake→camel translators`).
- ❌ Hardcoding parameters in core layers (`optuna_engine`, `export`).
- ❌ Omitting `options` for `select` parameters.

## Architecture Guarantees
- ✅ Frontend renders parameters automatically from `config.json`.
- ✅ Optimization and CSV export include parameters via config-driven schemas.
- ✅ Core layers stay strategy-agnostic (`OptimizationResult.params: Dict[str, Any]`).
- ✅ Adding new strategies requires only config + strategy module (no UI/core edits).
