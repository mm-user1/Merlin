# Merlin - Project Overview

Config-driven backtesting and Optuna optimization platform for cryptocurrency trading strategies with SQLite database persistence and web-based studies management.

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
    │   ├── storage.py           # SQLite database functions
    │   └── export.py            # Trade CSV export functions
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
    ├── storage/                 # Database storage (gitignored)
    │   ├── .gitkeep             # Directory marker
    │   ├── studies.db           # SQLite database (WAL mode)
    │   └── journals/            # SQLite journal files
    │
    ├── ui/                      # Web interface
    │   ├── server.py            # Flask HTTP API
    │   ├── templates/
    │   │   ├── index.html       # Start page (configuration)
    │   │   └── results.html     # Results page (studies browser)
    │   └── static/
    │       ├── js/              # Frontend JavaScript
    │       │   ├── main.js      # Start page logic
    │       │   ├── results.js   # Results page logic
    │       │   ├── api.js       # API client functions
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
   - Core modules remain strategy-agnostic

2. **camelCase Naming Convention**
   - Parameter names use camelCase end-to-end: Pine Script → `config.json` → Python → Database
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

5. **Database Persistence**
   - All optimization results automatically saved to SQLite database
   - Studies browsable through web UI Results page
   - Trade exports generated on-demand from stored parameters
   - Original CSV files referenced, not duplicated

### Module Responsibilities

#### Core Engines (`src/core/`)

| Module | Purpose |
|--------|---------|
| `backtest_engine.py` | Bar-by-bar trade simulation, position management, data preparation |
| `optuna_engine.py` | Bayesian optimization using Optuna, trial management, pruning, database persistence |
| `walkforward_engine.py` | Rolling walk-forward analysis with calendar-based IS/OOS windows, stitched OOS equity, annualized WFE, database persistence |
| `metrics.py` | Calculate BasicMetrics and AdvancedMetrics (Sharpe, RoMaD, Profit Factor, SQN, Ulcer Index, Consistency) |
| `storage.py` | SQLite database operations: save/load studies, manage trials/windows, handle CSV file references |
| `export.py` | Export trade history to CSV/ZIP (TradingView format) |

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

- `server.py` - Flask API endpoints for backtest, optimization, studies management, presets
- `templates/index.html` - Start page: strategy configuration and optimization launch
- `templates/results.html` - Results page: studies browser, trials/windows display, trade downloads
- `static/js/main.js` - Start page logic and form handling
- `static/js/results.js` - Results page logic and studies management
- `static/js/api.js` - API client functions for both pages
- `static/css/style.css` - Light theme styling for both pages

### Data Flow

#### Optimization Flow (Optuna/WFA)
```
Start Page (index.html)
       │
       ▼
User submits optimization
       │
       ▼
┌─────────────────┐
│   server.py     │  ← Builds OptimizationConfig
└────────┬────────┘
         │
         ▼
┌─────────────────────┐     ┌─────────────────┐
│ optuna_engine/      │ ◄── │   Strategy      │
│ walkforward_engine  │     │ (s01/s04/...)   │
└──────────┬──────────┘     └────────┬────────┘
           │                         │
           │                 ┌───────┴───────┐
           │                 │  indicators/  │
           │                 └───────────────┘
           ▼
┌─────────────────┐
│ backtest_engine │  ← Trade simulation per trial
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   metrics.py    │  ← Score calculation
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   storage.py    │  ← Save study to SQLite database
└────────┬────────┘
         │
         ▼
   studies.db (SQLite)
```

#### Results Viewing Flow
```
Results Page (results.html)
       │
       ▼
GET /api/studies
       │
       ▼
┌─────────────────┐
│   storage.py    │  ← Load study + trials/windows
└────────┬────────┘
         │
         ▼
   Display in UI
       │
       ├─ Click trial → Generate trades on-demand
       ├─ Delete study → Remove from database
       └─ Update CSV path → Update file reference
```

#### Trade Export (On-Demand)
```
User clicks "Download Trades"
       │
       ▼
POST /api/studies/{id}/trials/{n}/trades
       │
       ▼
┌─────────────────┐
│   storage.py    │  ← Load trial params from DB
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ backtest_engine │  ← Re-run strategy with saved params
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   export.py     │  ← Export trades to CSV
└─────────────────┘
```

### Database Schema

SQLite database stored at `src/storage/studies.db` with WAL (Write-Ahead Logging) mode enabled.

#### Tables

**studies** - Optimization study metadata
- Primary key: `study_id` (UUID)
- Unique constraint: `study_name`
- Fields: strategy_id, strategy_version, optimization_mode ('optuna'/'wfa'), status, trial counts, best value, filters applied, configuration JSON, CSV file path, timestamps

**trials** - Individual Optuna trial results (for Optuna mode studies)
- Foreign key: `study_id` → studies
- Unique constraint: (study_id, trial_number)
- Fields: trial parameters (JSON), metrics (net_profit_pct, max_drawdown_pct, sharpe_ratio, romad, etc.), composite score

**wfa_windows** - Walk-Forward Analysis window results (for WFA mode studies)
- Foreign key: `study_id` → studies
- Unique constraint: (study_id, window_number)
- Fields: best parameters (JSON), IS/OOS metrics, IS/OOS equity curves (JSON arrays), WFE

### API Endpoints

#### Page Routes
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve Start page (optimization configuration) |
| `/results` | GET | Serve Results page (studies browser) |

#### Optimization
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/backtest` | POST | Run single backtest (no storage) |
| `/api/optimize` | POST | Run Optuna optimization, save to database |
| `/api/walkforward` | POST | Run WFA, save to database |
| `/api/optimization/status` | GET | Get current optimization state |
| `/api/optimization/cancel` | POST | Cancel running optimization |

#### Studies Management
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/studies` | GET | List all saved studies with summary info |
| `/api/studies/<study_id>` | GET | Load complete study (metadata + trials/windows) |
| `/api/studies/<study_id>` | DELETE | Delete study from database |
| `/api/studies/<study_id>/update-csv-path` | POST | Update CSV file path reference |
| `/api/studies/<study_id>/trials/<trial_number>/trades` | POST | Generate and download trades CSV for trial |

#### Strategy Configuration
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/strategies` | GET | List all available strategies |
| `/api/strategy/<strategy_id>/config` | GET | Get strategy parameter schema |

#### Presets
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/presets` | GET | List all saved presets |
| `/api/presets/<name>` | GET | Load preset values |
| `/api/presets` | POST | Create new preset |
| `/api/presets/<name>` | PUT | Update existing preset |
| `/api/presets/<name>` | DELETE | Delete preset |
| `/api/presets/import-csv` | POST | Import preset from CSV parameter block |

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
