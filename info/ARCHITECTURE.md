# Final Architecture Overview

## System Architecture After Migration

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│                         (index.html)                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ Strategy Selector│  │  Warmup Bars     │  │  Date Range   │ │
│  │   Dropdown       │  │   Input Field    │  │   Filters     │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Dynamic Parameter Forms (Generated from JSON)     │  │
│  │  ┌─────────────────┐       ┌──────────────────────────┐  │  │
│  │  │ Backtest Params │       │  Optimizer Params        │  │  │
│  │  │  - Entry        │       │  - Enable/Disable        │  │  │
│  │  │  - Stops        │       │  - Min/Max/Step ranges   │  │  │
│  │  │  - Trail        │       │  - Multi-select options  │  │  │
│  │  │  - Risk         │       └──────────────────────────┘  │  │
│  │  └─────────────────┘                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                          FLASK SERVER                           │
│                          (server.py)                            │
├─────────────────────────────────────────────────────────────────┤
│  NEW ENDPOINTS:                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ GET  /api/strategies              → List all strategies │   │
│  │ GET  /api/strategies/{id}/config  → Get full config     │   │
│  │ GET  /api/strategies/{id}         → Get metadata        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  MODIFIED ENDPOINTS:                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ POST /api/backtest     (+ strategy_id, warmup_bars)     │   │
│  │ POST /api/optimize     (+ strategy_id, warmup_bars)     │   │
│  │ POST /api/walkforward  (+ strategy_id, warmup_bars)     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STRATEGY REGISTRY                          │
│                    (strategies/__init__.py)                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ _discover_strategies()                                    │ │
│  │  - Scans strategies/*/ directories                        │ │
│  │  - Loads config.json                                      │ │
│  │  - Imports strategy.py                                    │ │
│  │  - Registers in _REGISTRY dict                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ get_strategy(id) → Returns strategy class                │ │
│  │ get_strategy_config(id) → Returns config.json            │ │
│  │ list_strategies() → Returns all available strategies     │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       STRATEGY MODULES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ strategies/s01_trailing_ma/                              │  │
│  │  ├── config.json                                         │  │
│  │  │    - Metadata (id, name, version, description)        │  │
│  │  │    - Parameters (with types, defaults, ranges)        │  │
│  │  │    - Optimization settings (enabled, min, max, step)  │  │
│  │  │                                                        │  │
│  │  └── strategy.py                                         │  │
│  │       - class S01TrailingMA(BaseStrategy)                │  │
│  │       - run(df, params, trade_start_idx) → Result        │  │
│  │       - calculate_indicators(df, params) → Dict          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ strategies/s02_new_strategy/  (Future)                   │  │
│  │  ├── config.json                                         │  │
│  │  └── strategy.py                                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ strategies/base.py                                       │  │
│  │  - class BaseStrategy (abstract)                         │  │
│  │  - Defines interface for all strategies                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EXECUTION ENGINES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ backtest_engine.py                                        │ │
│  │  - Common functions: get_ma(), atr(), compute_max_dd()   │ │
│  │  - prepare_dataset_with_warmup(df, start, end, warmup)   │ │
│  │  - StrategyResult, TradeRecord dataclasses               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ optimizer_engine.py (Grid Search - MVP: NO CACHE)        │ │
│  │  - Generates parameter combinations                       │ │
│  │  - Calls strategy.run() for each combination             │ │
│  │  - 6-metric scoring system                               │ │
│  │  - Exports results to CSV                                │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ optuna_engine.py (Bayesian Optimization)                 │ │
│  │  - Smart search using Optuna                             │ │
│  │  - Calls strategy.run() for each trial                   │ │
│  │  - 5 optimization targets                                │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ walkforward_engine.py (Walk-Forward Analysis)            │ │
│  │  - Splits data into IS/OOS windows                       │ │
│  │  - Runs Optuna on each IS window                         │ │
│  │  - Tests Top-K on OOS                                    │ │
│  │  - Aggregates and forward tests                          │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Backtest Flow
```
User selects strategy + parameters
         │
         ▼
UI sends: {strategy_id, warmup_bars, params, csv_file}
         │
         ▼
Server: get_strategy(strategy_id) → strategy_class
         │
         ▼
Server: prepare_dataset_with_warmup(df, start, end, warmup_bars)
         │
         ▼
Server: strategy_class.run(df, params, trade_start_idx)
         │
         ▼
Returns: StrategyResult(profit, dd, trades)
         │
         ▼
UI displays results
```

### 2. Optimization Flow
```
User selects strategy + enables parameters + sets ranges
         │
         ▼
UI sends: {strategy_id, warmup_bars, enabled_params, param_ranges, fixed_params}
         │
         ▼
Server: get_strategy(strategy_id) → strategy_class
         │
         ▼
Optimizer generates N combinations
         │
         ▼
For each combination:
  - prepare_dataset_with_warmup(df, start, end, warmup_bars)
  - strategy_class.run(df, params, trade_start_idx)
  - Calculate scores
         │
         ▼
Export results to CSV (sorted by score/profit)
         │
         ▼
User downloads CSV
```

### 3. Strategy Discovery Flow
```
Page loads
    │
    ▼
UI: GET /api/strategies
    │
    ▼
Registry: list_strategies()
    │
    ▼
Returns: [{id, name, version, description}, ...]
    │
    ▼
UI populates strategy dropdown
    │
    ▼
User selects strategy
    │
    ▼
UI: GET /api/strategies/{id}/config
    │
    ▼
Registry: get_strategy_config(id) → config.json
    │
    ▼
UI generates forms from config.parameters
    │
    ▼
Forms appear dynamically
```

## Key Design Principles

### 1. **Separation of Concerns**
- Strategy logic isolated in strategy.py
- Configuration isolated in config.json
- UI generation driven by config
- Common functions in backtest_engine.py

### 2. **Auto-Discovery**
- No manual registration required
- Just create directory + 2 files
- Strategy appears automatically

### 3. **Universal Warmup**
- User controls warmup bars
- Same warmup logic for all strategies
- No strategy-specific calculations

### 4. **Dynamic UI**
- Forms generated from JSON
- No hardcoded HTML per strategy
- Single JS generator for all strategies

### 5. **Backward Compatibility**
- Old code still works via wrappers
- Gradual migration possible
- No breaking changes

---

## Separation of Concerns: Platform vs Strategy

The system follows a strict separation of responsibilities between the **Platform** and **Strategies**.

### Platform Responsibilities

The platform (optimizer_engine, server.py, UI) handles **workflow orchestration** and **result processing**:

✅ **Data Management:**
- Date filtering and warmup period management
- Multi-file processing
- CSV data loading

✅ **Optimization Workflows:**
- Grid Search (parameter enumeration)
- Optuna (Bayesian optimization)
- Walk-Forward Analysis (time-series cross-validation)

✅ **Result Processing:**
- Score calculation (composite score from multiple metrics)
- Result filtering (Score Filter, Net Profit Filter)
- CSV export with parameter blocks
- Trade history export (ZIP archives)

✅ **User Interface:**
- Strategy selector dropdown
- Dynamic form generation from JSON
- Parameter validation
- Progress tracking
- Preset management

### Strategy Responsibilities

Each strategy (e.g., S01 Trailing MA) handles **trading logic** and **metric calculation**:

🔄 **Trading Logic:**
- Entry/exit signal generation
- Position management
- Stop loss and take profit logic
- Trailing stop logic

🔄 **Indicator Calculations:**
- Moving averages (MA, EMA, SMA, HMA, etc.)
- ATR (Average True Range)
- RSI, MACD, Bollinger Bands, etc.
- Custom indicators

🔄 **Metrics Computation:**
- Net profit percentage
- Maximum drawdown
- Sharpe ratio
- Profit factor
- RoMaD, Ulcer Index, Recovery Factor, Consistency Score

🔄 **Trade Record Generation:**
- Entry/exit timestamps
- Entry/exit prices
- Position side (LONG/SHORT)
- PnL calculations

### Contract (Interface)

**Platform provides to strategy:**
```python
strategy.run(
    df: pd.DataFrame,        # OHLCV data (already filtered and warmed up)
    params: dict,            # Strategy parameters from UI or optimizer
    trade_start_idx: int     # Index where trading should start
) -> StrategyResult
```

**Strategy returns to platform:**
```python
StrategyResult(
    # Financial metrics (required)
    net_profit_pct: float,
    max_drawdown_pct: float,
    total_trades: int,

    # Risk metrics (optional, for Score Formula)
    sharpe_ratio: Optional[float],
    profit_factor: Optional[float],
    romad: Optional[float],
    ulcer_index: Optional[float],
    recovery_factor: Optional[float],
    consistency_score: Optional[float],

    # Trade records (for export)
    trades: List[TradeRecord]
)
```

### Strategy is Agnostic To

**Strategies do NOT know about:**

❌ Whether optimization is running
❌ What optimization method is used (Grid/Optuna/WFA)
❌ Whether filters are enabled (Score Filter, Net Profit Filter)
❌ How many files are being processed
❌ Export settings (CSV format, ZIP compression)
❌ UI state (which parameters are enabled in optimizer)
❌ Preset management
❌ Score formula weights

**Strategies are pure functions:**
```python
# Same inputs → Same output (deterministic)
result1 = strategy.run(df, params, trade_start_idx)
result2 = strategy.run(df, params, trade_start_idx)
assert result1 == result2  # Always true
```

### Benefits of This Separation

✅ **Simplicity:** Strategies focus only on trading logic
✅ **Testability:** Strategies can be tested independently
✅ **Reusability:** Platform features work with all strategies
✅ **Maintainability:** Changes to optimization don't affect strategies
✅ **Extensibility:** New strategies don't require platform changes

### Example: Adding Score Filter

When Score Filter is enabled in the UI:

**Platform does:**
1. Runs optimization (Grid/Optuna/WFA)
2. Collects all results
3. Calculates composite score for each result
4. Filters results by minimum score threshold
5. Exports filtered results to CSV

**Strategy does:**
- Nothing! Strategy doesn't even know Score Filter exists
- Just returns metrics (sharpe, romad, etc.)
- Platform uses those metrics for scoring

---

## Future Enhancements (Post-MVP)

1. **Caching System**
   - Implement `strategy.calculate_indicators()` caching
   - Pre-compute common indicators
   - Significant speed boost for grid search

2. **Hot Reload**
   - Reload strategies without server restart
   - Useful for rapid development

3. **Strategy Validation**
   - Validate config.json schema
   - Validate strategy.py interface
   - Automated tests per strategy

4. **Strategy Marketplace**
   - Import/export strategies as ZIP
   - Share strategies with others
   - Version management

5. **Multi-CSV Support**
   - Optimize across multiple symbols
   - Portfolio backtesting
   - Correlation analysis

## Adding a New Strategy (Post-Migration)

**Step 1:** Create directory
```bash
mkdir src/strategies/s02_my_strategy
```

**Step 2:** Create config.json
```json
{
  "id": "s02_my_strategy",
  "name": "My Strategy",
  "version": "v1",
  "description": "My awesome strategy",
  "parameters": {
    "param1": {
      "type": "int",
      "label": "Parameter 1",
      "default": 10,
      "min": 1,
      "max": 100,
      "optimize": {"enabled": true, "min": 5, "max": 50, "step": 5}
    }
  }
}
```

**Step 3:** Create strategy.py
```python
from strategies.base import BaseStrategy
from backtest_engine import StrategyResult

class S02MyStrategy(BaseStrategy):
    STRATEGY_ID = "s02_my_strategy"
    STRATEGY_NAME = "My Strategy"
    STRATEGY_VERSION = "v1"

    @staticmethod
    def run(df, params, trade_start_idx=0):
        # Your trading logic here
        return StrategyResult(...)
```

**Step 4:** Refresh browser
- Strategy appears in dropdown automatically!

## Configuration Reference

### config.json Structure

```json
{
  "id": "strategy_id",
  "name": "Strategy Name",
  "version": "v1",
  "description": "...",
  "author": "Your Name",

  "parameters": {
    "paramName": {
      "type": "int|float|bool|select",
      "label": "Human Readable Label",
      "default": "value",
      "min": 0,
      "max": 100,
      "step": 1,
      "options": ["A", "B", "C"],
      "group": "Entry",
      "optimize": {
        "enabled": true,
        "min": 0,
        "max": 100,
        "step": 5
      }
    }
  }
}
```

**Field descriptions:**
- `id`: Unique identifier (lowercase, underscores)
- `name`: Display name shown in UI
- `version`: Version string (e.g., "v1", "v2.1")
- `description`: Strategy description
- `author`: Author name (optional)
- `type`: Parameter type (int, float, bool, select)
- `label`: Human-readable label for UI
- `default`: Default value
- `min`: Minimum value (int/float only)
- `max`: Maximum value (int/float only)
- `step`: Step size for sliders/inputs (int/float only)
- `options`: List of options (select type only)
- `group`: Parameter category (Entry, Stops, Trail, Risk)
- `optimize.enabled`: Include in optimization by default? (true/false)
- `optimize.min`: Optimization range minimum
- `optimize.max`: Optimization range maximum
- `optimize.step`: Optimization step size

### strategy.py Interface

```python
class MyStrategy(BaseStrategy):
    # Required class attributes
    STRATEGY_ID = "strategy_id"
    STRATEGY_NAME = "Strategy Name"
    STRATEGY_VERSION = "v1"

    # Optional: for future caching
    @staticmethod
    def calculate_indicators(df, params):
        return {}

    # Required: main trading logic
    @staticmethod
    def run(df, params, trade_start_idx=0):
        # df: pd.DataFrame with OHLCV data
        # params: Dict[str, Any] with all parameters
        # trade_start_idx: start trading from this index

        # Your logic here...

        return StrategyResult(
            net_profit_pct=float,
            max_drawdown_pct=float,
            total_trades=int,
            trades=List[TradeRecord]
        )
```

---

**This architecture provides a clean, extensible foundation for multi-strategy backtesting!**
