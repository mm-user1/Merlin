# Merlin - Project Overview

Config-driven backtesting and Optuna optimization platform for cryptocurrency trading strategies.

## Project Structure

```
project-root/
├── CLAUDE.md                    # AI assistant guidance
├── README.md                    # Quick start guide
├── requirements.txt             # Python dependencies
├── agents.md                    # GPT Codex agent instructions
│
├── docs/                        # Documentation
│   ├── PROJECT_OVERVIEW.md      # This file
│   └── ADDING_NEW_STRATEGY.md   # Strategy development guide
│
├── data/                        # Data files (not code)
│   ├── raw/                     # Source OHLCV CSV files
│   └── baseline/                # Regression test baselines
│
├── tools/                       # Development utilities
│   ├── generate_baseline_s01.py # Generate regression baselines
│   ├── benchmark_indicators.py  # Indicator performance tests
│   ├── benchmark_metrics.py     # Metrics performance tests
│   └── test_all_ma_types.py     # Test all 11 MA types
│
├── tests/                       # Pytest test suite
│   ├── test_sanity.py           # Infrastructure sanity checks
│   ├── test_regression_s01.py   # S01 baseline regression
│   ├── test_s01_migration.py    # S01 migration validation
│   ├── test_s04_stochrsi.py     # S04 strategy tests
│   ├── test_metrics.py          # Metrics calculation tests
│   ├── test_export.py           # Export functionality tests
│   ├── test_indicators.py       # Indicator tests
│   ├── test_naming_consistency.py # camelCase naming guardrails
│   ├── test_walkforward.py      # Walk-forward analysis tests
│   └── test_server.py           # HTTP API tests
│
└── src/                         # Application source code
    ├── run_backtest.py          # CLI backtest runner
    │
    ├── core/                    # Core engines and utilities
    │   ├── backtest_engine.py   # Trade simulation engine
    │   ├── optuna_engine.py     # Optuna optimization engine
    │   ├── walkforward_engine.py # Walk-forward analysis engine
    │   ├── metrics.py           # Metrics calculation
    │   └── export.py            # CSV export functions
    │
    ├── indicators/              # Technical indicator library
    │   ├── ma.py                # Moving averages (11 types)
    │   ├── volatility.py        # ATR, NATR
    │   ├── oscillators.py       # RSI, StochRSI
    │   └── trend.py             # ADX, trend indicators
    │
    ├── strategies/              # Trading strategies
    │   ├── base.py              # BaseStrategy class
    │   ├── s01_trailing_ma/     # Trailing MA strategy
    │   │   ├── config.json      # Parameter schema
    │   │   └── strategy.py      # Strategy implementation
    │   └── s04_stochrsi/        # StochRSI strategy
    │       ├── config.json
    │       └── strategy.py
    │
    ├── ui/                      # Web interface
    │   ├── server.py            # Flask HTTP API
    │   ├── templates/
    │   │   └── index.html       # Main HTML page
    │   └── static/
    │       ├── js/              # Frontend JavaScript
    │       │   ├── main.js
    │       │   ├── api.js
    │       │   ├── strategy-config.js
    │       │   ├── ui-handlers.js
    │       │   ├── presets.js
    │       │   └── utils.js
    │       └── css/
    │           └── style.css    # Light theme styles
    │
    └── presets/                 # Saved parameter presets
        └── *.json
```

## Architecture

### Core Principles

1. **Config-Driven Design**
   - Backend loads parameter schemas from each strategy's `config.json`
   - Frontend renders UI controls dynamically from `config.json`
   - CSV export builds headers from `config.json`
   - Core modules remain strategy-agnostic

2. **camelCase Naming Convention**
   - Parameter names use camelCase end-to-end: Pine Script → `config.json` → Python → CSV
   - Examples: `maType`, `closeCountLong`, `rsiLen`
   - Internal control fields (`use_backtester`, `start`, `end`) may use snake_case but are excluded from UI/config

3. **Data Structure Ownership**
   - Structures live where they're populated:
     - `TradeRecord`, `StrategyResult` → `backtest_engine.py`
     - `BasicMetrics`, `AdvancedMetrics` → `metrics.py`
     - `OptimizationResult`, `OptunaConfig` → `optuna_engine.py`
     - Strategy params dataclass → each strategy's `strategy.py`

4. **Optuna-Only Optimization**
   - Grid search removed; Optuna handles all optimization
   - Supports multiple targets: score, net_profit, romad, sharpe, max_drawdown
   - Budget modes: n_trials, timeout, patience

### Module Responsibilities

#### Core Engines (`src/core/`)

| Module | Purpose |
|--------|---------|
| `backtest_engine.py` | Bar-by-bar trade simulation, position management, data preparation |
| `optuna_engine.py` | Bayesian optimization using Optuna, trial management, pruning |
| `walkforward_engine.py` | Rolling walk-forward analysis with calendar-based IS/OOS windows, stitched OOS equity, and annualized WFE |
| `metrics.py` | Calculate BasicMetrics and AdvancedMetrics (Sharpe, RoMaD, Profit Factor, SQN, Ulcer Index, Consistency) |
| `export.py` | Export results to CSV (Optuna results, WFA summary, trades) |

#### Indicators (`src/indicators/`)

| Module | Indicators |
|--------|------------|
| `ma.py` | SMA, EMA, WMA, DEMA, KAMA, HMA, ALMA, TMA, T3, VWMA, VWAP |
| `volatility.py` | ATR, NATR |
| `oscillators.py` | RSI, StochRSI |
| `trend.py` | ADX |

All indicators accessed via `get_ma()` facade for moving averages.

#### Strategies (`src/strategies/`)

Each strategy contains:
- `config.json` - Parameter schema with types, defaults, min/max, optimization ranges
- `strategy.py` - Params dataclass and strategy class with `run()` method

Strategies auto-discovered by `strategies/__init__.py` if both files exist.

#### UI (`src/ui/`)

- `server.py` - Flask API endpoints for backtest, optimization, presets
- `templates/index.html` - SPA frontend
- `static/js/` - Modular JavaScript (API calls, form generation, event handlers)
- `static/css/style.css` - Light theme styling

### Data Flow

```
User Input (UI/CLI)
       │
       ▼
┌─────────────────┐
│   server.py     │  ← Transforms input, calls engines
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ backtest_engine │ ◄── │   Strategy      │
│                 │     │ (s01/s04/...)   │
└────────┬────────┘     └─────────────────┘
         │                      │
         │              ┌───────┴───────┐
         │              │  indicators/  │
         │              └───────────────┘
         ▼
┌─────────────────┐
│   metrics.py    │  ← Calculates Basic/Advanced metrics
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   export.py     │  ← CSV export
└─────────────────┘
```

For optimization:
```
┌─────────────────┐
│ optuna_engine   │  ← Manages trials
└────────┬────────┘
         │
         ▼ (per trial)
┌─────────────────┐
│ backtest_engine │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   metrics.py    │  ← Score calculation
└─────────────────┘
```

## Running the Application

### Web Server
```bash
cd src/ui
python server.py
```
Opens at http://0.0.0.0:5000

### CLI Backtest
```bash
cd src
python run_backtest.py --csv ../data/raw/OKX_LINKUSDT.P,\ 15\ 2025.05.01-2025.11.20.csv
```

### Tests
```bash
pytest tests/ -v
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | AI assistant instructions (for Claude models) |
| `agents.md` | GPT Codex agent instructions |
| `docs/ADDING_NEW_STRATEGY.md` | How to add new strategies |
| `data/baseline/` | Regression test reference data |
| `tools/generate_baseline_s01.py` | Regenerate S01 baseline |

## Current Strategies

| ID | Name | Description |
|----|------|-------------|
| `s01_trailing_ma` | S01 Trailing MA | Complex trailing MA strategy with 11 MA types, close counts, ATR stops |
| `s04_stochrsi` | S04 StochRSI | StochRSI swing strategy with swing-based stops |

## Adding New Strategies

See `docs/ADDING_NEW_STRATEGY.md` for complete instructions on converting PineScript strategies to Python and integrating them into the platform.
