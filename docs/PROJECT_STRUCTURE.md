
# Project Directory Structure (Personal Use)

This project is designed for personal use, without packaging as a pip package, so all code is placed directly in `src/` without an additional level (such as `app/`).

```text
project-root/
├── README.md
├── requirements.txt                 # project dependencies
├── .gitignore
│
├── docs/                            # documentation
│   ├── PROJECT_TARGET_ARCHITECTURE.md
│   ├── PROJECT_MIGRATION_PLAN.md
│   └── ...                          # additional notes/specs
│
├── data/                            # data files (NOT code)
│   ├── raw/                         # source CSV files with quotes
│   ├── processed/                   # prepared/aggregated datasets (optional)
│   └── baseline/                    # baseline for S_01 regression (metrics/trades)
│
├── tools/                           # development and debugging scripts
│   ├── generate_baseline_s01.py     # generate reference results
│   └── ...                          # converters, one-time utilities, etc.
│
├── tests/                           # automated tests (pytest)
│   ├── test_sanity.py               # basic sanity test for infrastructure
│   ├── test_regression_s01.py       # regression test for S_01 strategy
│   ├── test_backtest_engine.py
│   ├── test_optuna_engine.py
│   ├── test_indicators.py
│   ├── test_metrics.py
│   └── ...
│
├── src/                             # all executable project code
│   ├── core/                        # core: engines + common utilities
│   │   ├── __init__.py
│   │   ├── backtest_engine.py       # main backtest engine
│   │   ├── optuna_engine.py         # sole optimizer (Optuna-only)
│   │   ├── walkforward_engine.py    # WFA engine (wrapper over Optuna + backtest)
│   │   ├── metrics.py               # calculation of all metrics (Basic/Advanced/WFA)
│   │   └── export.py                # results export (CSV for Optuna/WFA/trades)
│   │
│   ├── indicators/                  # indicator library
│   │   ├── __init__.py
│   │   ├── ma.py                    # moving averages (SMA, EMA, HMA, ALMA, KAMA, WMA, TMA, T3, DEMA, VWMA, VWAP)
│   │   ├── volatility.py            # ATR, NATR and other volatility indicators
│   │   ├── oscillators.py           # RSI, Stoch, CCI, etc.
│   │   ├── volume.py                # OBV and other volume-based indicators
│   │   ├── trend.py                 # ADX and trend indicators
│   │   └── misc.py                  # everything else
│   │
│   ├── strategies/                  # strategies and their parameters
│   │   ├── __init__.py
│   │   ├── base.py                  # BaseStrategy + fallback for indicators
│   │   ├── simple_ma/
│   │   │   ├── __init__.py
│   │   │   ├── strategy.py          # simple strategy for architecture testing
│   │   │   └── config.json          # parameter/range descriptions
│   │   ├── s01_trailing_ma/
│   │   │   ├── __init__.py
│   │   │   ├── strategy.py          # current/main S_01 implementation (after migration)
│   │   │   └── config.json          # parameter/range descriptions
│   │   # other strategies will be added here following the same template
│   │
│   ├── ui/                          # server and frontend
│   │   ├── __init__.py
│   │   ├── server.py                # Flask/FastAPI, HTTP API
│   │   ├── templates/
│   │   │   └── index.html           # main HTML page
│   │   └── static/
│   │       ├── js/
│   │       │   └── main.js          # frontend logic
│   │       └── css/
│   │           └── style.css        # styles
│   │
│   └── cli/                         # optional: CLI tools
│       ├── __init__.py
│       └── run_backtest.py          # run backtest from command line (including logging flag)
│
└── ...
```

## Directory Overview

### Core Components (`src/core/`)

The core directory contains the three main engines and shared utilities:

- **`backtest_engine.py`** - Main backtest engine
  - Data preparation (date filtering, warmup, normalization)
  - Bar-by-bar trade simulation
  - Position management and order execution
  - Defines `TradeRecord` and `StrategyResult` data structures

- **`optuna_engine.py`** - Sole optimizer (Grid Search removed)
  - Bayesian optimization using Optuna
  - 5 optimization targets: score, net_profit, romad, sharpe, max_drawdown
  - 3 budget modes: n_trials, timeout, patience
  - Pruning for unpromising trials
  - Defines `OptimizationResult` and `OptunaConfig` data structures

- **`walkforward_engine.py`** - Walk-Forward Analysis engine
  - Window splitting (in-sample/out-of-sample)
  - Orchestrates Optuna optimization on IS data
  - Tests best parameters on OOS data
  - Aggregates results across windows

- **`metrics.py`** - Unified metrics calculation
  - `BasicMetrics`: net profit, max drawdown, trades, win rate, etc.
  - `AdvancedMetrics`: Sharpe, Sortino, profit factor, RoMaD, Ulcer Index, consistency
  - `WFAMetrics`: aggregated metrics across WFA windows
  - All metrics calculated from `StrategyResult`

- **`export.py`** - Results export
  - `export_optuna_results()`: CSV export with parameter block + results table
  - `export_wfa_summary()`: WFA results by window
  - `export_trades()`: Trade history in TradingView format
  - Consistent column formatting across all exports

### Indicators Library (`src/indicators/`)

Common indicators used by all strategies:

- **`ma.py`** - 11 moving average types
  - Simple: SMA, WMA
  - Exponential: EMA, DEMA
  - Adaptive: KAMA
  - Low-lag: HMA, ALMA
  - Advanced: TMA, T3
  - Volume-weighted: VWMA, VWAP
  - Unified `get_ma()` facade for all MA types

- **`volatility.py`** - Volatility indicators
  - ATR (Average True Range)
  - NATR (Normalized ATR)
  - Other volatility measures

- **`oscillators.py`** - Momentum oscillators
  - RSI, Stochastic, CCI, etc.

- **`volume.py`** - Volume-based indicators
  - OBV (On-Balance Volume)
  - Other volume indicators

- **`trend.py`** - Trend indicators
  - ADX and trend-following indicators

- **`misc.py`** - Miscellaneous indicators and helpers
  - Utility functions
  - Custom indicators

### Strategies Layer (`src/strategies/`)

Strategy implementations with their own parameters:

- **`base.py`** - Base strategy class
  - Main contract: `run(df, params, trade_start_idx) -> StrategyResult`
  - Indicator fallback mechanism (custom → package)
  - Strategy metadata (ID, name, version)

- **`simple_ma/`** - Simple MA crossover strategy
  - Dead-simple test strategy for architecture validation
  - Fast MA / Slow MA crossover logic
  - Stop loss percentage
  - Used to validate entire pipeline before S01 migration

- **`s01_trailing_ma/`** - Production S01 strategy (after migration)
  - Complex trailing MA strategy with 11 MA types
  - Close count entry logic
  - Multiple stop types (ATR-based, max %, max days)
  - Trailing exits with separate long/short MA types
  - Position sizing modes (fixed qty or % of equity)
  - `S01Params` dataclass lives inside strategy.py

- **`s01_trailing_ma/`** - Migrated S01 strategy (legacy folder removed)
  - Used during Phase 7 migration
  - Allows parallel testing: legacy vs migrated
  - Deleted after validation completes

Each strategy contains:
- `strategy.py`: Strategy class with `run()` implementation and params dataclass
- `config.json`: Parameter descriptions in unified format
  - Parameter types, defaults, min/max, step
  - Optimization ranges (can differ from UI ranges)
  - Grouping and labels for UI
  - Enable/disable optimization per parameter

### User Interface (`src/ui/`)

Separated frontend and backend:

- **`server.py`** - Flask HTTP API
  - Endpoints: `/api/backtest`, `/api/optimize`, `/api/presets`
  - Transforms UI input to strategy configs
  - Calls core engines
  - Returns JSON responses

- **`templates/index.html`** - Main HTML page
  - Clean HTML markup only (after Phase 8 separation)
  - Form structure for strategy/parameters
  - Result display containers
  - No inline styles or scripts

- **`static/js/main.js`** - Frontend logic
  - Parameter collection
  - AJAX requests to server
  - Response processing
  - DOM updates and table rendering

- **`static/css/style.css`** - Interface styling
  - Light theme (project requirement)
  - Component styles
  - Layout and positioning

### Command-Line Interface (`src/cli/`)

Optional CLI tools for local runs:

- **`run_backtest.py`** - CLI backtest runner
  - Accepts strategy, parameters, data path via arguments
  - Logging flags: `--debug`, `--log-level`, `--log-file`
  - Calls `backtest_engine.run_backtest()`
  - Prints metrics or exports results
  - Useful for development and testing without UI

### Supporting Directories

- **`data/`** - Data files (not code)
  - `raw/`: Original OHLCV CSV files
  - `processed/`: Prepared/aggregated datasets (optional)
  - `baseline/`: Regression baseline for S01 (metrics, trades, equity curve)

- **`tools/`** - Development and debugging scripts
  - `generate_baseline_s01.py`: Creates regression baseline
  - Converters, one-time utilities
  - Migration scripts

- **`tests/`** - Automated test suite (pytest)
  - `test_sanity.py`: Infrastructure sanity checks
  - `test_regression_s01.py`: S01 behavior regression tests
  - `test_backtest_engine.py`: Engine unit tests
  - `test_optuna_engine.py`: Optimization tests
  - `test_indicators.py`: Indicator parity tests (old vs new)
  - `test_metrics.py`: Metrics calculation tests
  - Edge case tests throughout

- **`docs/`** - Documentation
  - Architecture documentation
  - Migration plans and reports
  - Strategy development guides
  - Config.json format specifications

## Key Architectural Principles

### Data Structure Ownership

Following the principle "structures live where they're populated":

- `TradeRecord`, `StrategyResult` → `backtest_engine.py`
- `BasicMetrics`, `AdvancedMetrics`, `WFAMetrics` → `metrics.py`
- `OptimizationResult`, `OptunaConfig` → `optuna_engine.py`
- `StrategyParams` → `strategies/<strategy_name>/strategy.py`

**No separate `types.py`** - structures imported directly from their home modules.

### Strategy Parameters

Each strategy defines its own parameter dataclass inside `strategy.py`:
- Better encapsulation
- Each strategy owns its parameter structure
- Easier to add new strategies with different parameters
- No shared StrategyParams

### Metrics Responsibility

`metrics.py` ONLY calculates metrics, doesn't orchestrate:
- Single responsibility principle
- Other modules consume metrics
- Clear separation of concerns

### Frontend Separation

UI refactoring happens AFTER core migration (Phase 8):
- UI doesn't affect backend logic
- Logical to clean up last
- Focus on high-risk backend phases first

### Grid Search Removal

Optuna is the sole optimizer (Grid Search removed in Phase 3):
- Simplifies codebase
- Optuna covers all use cases
- One less engine to maintain
- Faster iterations

## Migration Status

This structure represents the **target state** after migration completion. Current migration phases:

- [x] Phase -1: Test Infrastructure Setup
- [x] Phase 0: Regression Baseline for S01
- [x] Phase 1: Core Extraction to `src/core/`
- [ ] Phase 2: Export Extraction to `export.py`
- [ ] Phase 3: Grid Search Removal
- [ ] Phase 4: Metrics Extraction to `metrics.py`
- [ ] Phase 5: Indicators Package Extraction
- [ ] Phase 6: Simple Strategy Testing
- [ ] Phase 7: S01 Migration via Duplicate
- [ ] Phase 8: Frontend Separation
- [ ] Phase 9: Logging, Cleanup, Documentation

See `PROJECT_MIGRATION_PLAN_upd.md` for detailed migration steps.

## Brief Comments

- **`src/core/`** - Three main engines (`backtest_engine.py`, `optuna_engine.py`, `walkforward_engine.py`) and shared modules `metrics.py` and `export.py`

- **`src/indicators/`** - Common indicators for all strategies. Strategy-specific indicators can live in the strategy itself via `indicator_<name>` methods or `custom_indicators` dict.

- **`src/strategies/`**:
  - `base.py` defines the interface and common functionality
  - `simple_ma/` - training strategy for architecture validation
  - `s01_trailing_ma/` - migrated S01 strategy (production)
  - `s01_trailing_ma/` - main S01 version after migration completion

- **`src/ui/`** - Separate "island" for web interface:
  - `server.py` communicates with core
  - `templates/` + `static/` - frontend

- **`src/cli/`** - Not mandatory, but convenient to have lightweight CLI for local runs without UI (with optional logging)

- **`data/`, `tools/`, `tests/`, `docs/`** - Clearly separated from code to avoid clutter when working with project logic
