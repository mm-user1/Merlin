## Base rules for project:

Act as an experienced Python and Pinescript developer with trading and crypto algorithmic trading expertise.
IMPORTANT: Work strictly according to the given specifications. Any deviations are prohibited without my explicit consent.
IMPORTANT: The script must be maximally efficient and fast.
IMPORTANT: The GUI must use a light theme.

"./data" folder is used for examples, market data files etc.
"./docs" folder is used for documentation, plans, reference scripts etc.
"./src" is the main project folder

Always use this interpreter for Python and tests: C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe (e.g., `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q`).

# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with this repository.

## Project: Merlin

Cryptocurrency trading strategy backtesting and Optuna optimization platform with a Flask SPA frontend.

## Running the Application

### Web Server

```bash
cd src/ui
python server.py
```

Server runs at http://0.0.0.0:5000

### CLI Backtest

```bash
cd src
python run_backtest.py --csv ../data/raw/OKX_LINKUSDT.P,\ 15\ 2025.05.01-2025.11.20.csv
```

### Tests

```bash
pytest tests/ -v
```

### Dependencies

```bash
pip install -r requirements.txt
```

Key: Flask, pandas, numpy, matplotlib, optuna==4.4.0

## Architecture

### Core Principles

1. **Config-driven design** - Parameter schemas in `config.json`, UI renders dynamically
2. **camelCase naming** - End-to-end: Pine Script → config.json → Python → CSV
3. **Optuna-only optimization** - Grid search removed
4. **Strategy isolation** - Each strategy owns its params dataclass
5. **Rolling WFA (Phase 2)** - Calendar-based IS/OOS windows, stitched OOS equity, annualized WFE
6. **Database persistence** - All optimization results automatically saved to SQLite, browsable through web UI

### Directory Structure

```
src/
├── core/               # Engines + utilities
│   ├── backtest_engine.py    # Trade simulation, TradeRecord, StrategyResult
│   ├── optuna_engine.py      # Optimization, OptimizationResult, OptunaConfig
│   ├── walkforward_engine.py # WFA orchestration
│   ├── metrics.py            # BasicMetrics, AdvancedMetrics calculation
│   ├── storage.py            # SQLite database operations
│   └── export.py             # Trade CSV export functions
├── indicators/         # Technical indicators
│   ├── ma.py           # 11 MA types via get_ma()
│   ├── volatility.py   # ATR, NATR
│   └── oscillators.py  # RSI, StochRSI
├── strategies/         # Trading strategies
│   ├── base.py         # BaseStrategy class
│   ├── s01_trailing_ma/
│   └── s04_stochrsi/
├── storage/            # Database storage (gitignored)
│   ├── studies.db      # SQLite database (WAL mode)
│   └── journals/       # SQLite journal files
└── ui/                 # Web interface
    ├── server.py       # Flask API
    ├── templates/
    │   ├── index.html  # Start page (configuration)
    │   └── results.html # Results page (studies browser)
    └── static/
        ├── js/
        │   ├── main.js     # Start page logic
        │   ├── results.js  # Results page logic
        │   └── api.js      # API client
        └── css/
```

### Data Structure Ownership

| Structure                            | Module                        |
| ------------------------------------ | ----------------------------- |
| `TradeRecord`, `StrategyResult`      | `backtest_engine.py`          |
| `BasicMetrics`, `AdvancedMetrics`    | `metrics.py`                  |
| `OptimizationResult`, `OptunaConfig` | `optuna_engine.py`            |
| Strategy params dataclass            | Each strategy's `strategy.py` |

## Parameter Naming Rules

**CRITICAL: Use camelCase everywhere**

- ✅ `maType`, `closeCountLong`, `rsiLen`, `stopLongMaxPct`
- ❌ `ma_type`, `close_count_long`, `rsi_len`, `stop_long_max_pct`

Internal control fields (`use_backtester`, `start`, `end`) may use snake_case but are excluded from UI/config.

**Do NOT add:**

- `to_dict()` methods - use `dataclasses.asdict(params)` instead
- Snake↔camel conversion helpers
- Feature flags

## Adding New Strategies

See `docs/ADDING_NEW_STRATEGY.md` for complete guide.

Quick checklist:

1. Create `src/strategies/<strategy_id>/` directory
2. Create `config.json` with parameter schema (camelCase)
3. Create `strategy.py` with params dataclass and strategy class
4. Ensure `STRATEGY_ID`, `STRATEGY_NAME`, `STRATEGY_VERSION` class attributes
5. Implement `run(df, params, trade_start_idx) -> StrategyResult` static method
6. Strategy auto-discovered - no manual registration needed

## Database Operations

### Accessing Studies

```python
from core.storage import list_studies, load_study_from_db

# List all saved studies
studies = list_studies()
for study in studies:
    print(f"{study['study_name']}: {study['saved_trials']} trials")

# Load complete study with trials/windows
study_data = load_study_from_db(study_id)
print(study_data['study'])      # Study metadata
print(study_data['trials'])     # Optuna trials (if mode='optuna')
print(study_data['windows'])    # WFA windows (if mode='wfa')
print(study_data['csv_exists']) # Whether CSV file still exists
```

### Understanding Study Storage

**Optuna studies:**

- Saved to `studies` table (metadata) + `trials` table (parameter sets)
- Trials include: params (JSON), metrics, composite score
- Multi-objective studies store objective vectors and Pareto/feasibility flags (constraints)
- Study summaries may include completed/failed/pruned counts; results lists include COMPLETE trials (failed trials are retained only if explicitly stored for debugging)
- Optional filters (by score/profit threshold) may reduce stored trials for UI browsing

**WFA studies:**

- Saved to `studies` table (metadata) + `wfa_windows` table (per-window results)
- Each window includes: best params, IS/OOS metrics, equity curves (JSON arrays)
- WFE (Walk-Forward Efficiency) stored as `best_value`

### Database Location

```
src/storage/studies.db          # Main database (WAL mode)
src/storage/studies.db-wal      # Write-Ahead Log
src/storage/studies.db-shm      # Shared memory
src/storage/journals/           # Temporary Optuna journals
```

**Note:** Database files are gitignored. Only `.gitkeep` files are tracked.

## Common Tasks

### Running Single Backtest

```python
from core.backtest_engine import load_data, prepare_dataset_with_warmup
from strategies.s01_trailing_ma.strategy import S01TrailingMA

df = load_data("data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv")
df_prepared, trade_start_idx = prepare_dataset_with_warmup(df, start, end, warmup_bars=1000)
result = S01TrailingMA.run(df_prepared, params, trade_start_idx)
```

### Calculating Metrics

```python
from core import metrics
basic = metrics.calculate_basic(result, initial_capital=100.0)
advanced = metrics.calculate_advanced(result)
```

### Walk-Forward Analysis (Rolling)

```python
from core.walkforward_engine import WFConfig, WalkForwardEngine

wf_config = WFConfig(
    strategy_id="s01_trailing_ma",
    is_period_days=180,
    oos_period_days=60,
    warmup_bars=1000,
)
engine = WalkForwardEngine(wf_config, base_config_template, optuna_settings)
wf_result = engine.run_wf_optimization(df)
```

### Using Indicators

```python
from indicators.ma import get_ma
from indicators.volatility import atr
from indicators.oscillators import rsi, stoch_rsi

ma_values = get_ma(df["Close"], "HMA", 50)
atr_values = atr(df["High"], df["Low"], df["Close"], 14)
rsi_values = rsi(df["Close"], 14)
```

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Key Test Files

- `test_sanity.py` - Infrastructure checks
- `test_regression_s01.py` - S01 baseline regression
- `test_naming_consistency.py` - camelCase guardrails

### Regenerate S01 Baseline

```bash
python tools/generate_baseline_s01.py
```

## Optuna: Multi-objective & constraints

**Key behavioral rules (keep these consistent across backend + UI):**

- **Single objective vs multi-objective**
  - 1 objective: create study with `direction=...`
  - 2+ objectives: create study with `directions=[...]` and return a tuple of objective values
  - Multi-objective results are a **Pareto front**; UI sorts Pareto-first then by **primary objective**

- **Pruning**
  - Pruning is supported for **single-objective** only.
  - Optuna `Trial.should_prune()` does **not** support multi-objective optimization.

- **Invalid objectives / missing metrics**
  - If an objective value is missing/NaN, return `float("nan")` (or a NaN tuple for multi-objective).
  - Optuna treats NaN returns as **FAILED trials** (study continues).
  - Failed trials are ignored by Optuna samplers (they do not affect future suggestions).

- **Constraints**
  - Constraints are **soft**: infeasible trials are retained but deprioritized in UI and “best” selection.
  - `constraints_func` is evaluated only after **successful** trials; it is not called for failed/pruned trials.
  - Sorting/labeling should follow: feasible Pareto → feasible non-Pareto → infeasible (then by total violation, then primary objective).

- **Concurrency**
  - Keep Merlin’s existing multi-process optimization architecture. Do not replace it with `study.optimize(..., n_jobs=...)` threading.


## UI Notes

### Two-Page Architecture

**Start Page (`/` - index.html):**

- Strategy selection and parameter configuration
- Optuna settings (objectives + primary objective, budget, sampler, pruner, constraints)
- Walk-Forward Analysis settings (IS/OOS periods)
- Run Optuna or Run WFA buttons
- Results automatically saved to database
- Light theme UI with dynamic forms from `config.json`

**Results Page (`/results` - results.html):**

- Studies Manager: List all saved optimization studies
- Study details: View trials (Optuna) or windows (WFA)
- Pareto badge + constraint feasibility indicators for Optuna trials
- Equity curve visualization
- Parameter comparison tables
- Download trades CSV for any trial (on-demand generation)
- Delete studies or update CSV file paths

### Frontend Architecture

- **main.js**: Start page logic, form handling, optimization launch
- **results.js**: Results page logic, studies browser, data visualization
- **api.js**: Centralized API calls for both pages
- **strategy-config.js**: Dynamic form generation from `config.json`
- **ui-handlers.js**: Shared UI event handlers
- **optuna-ui.js**: Optuna Start-page UI helpers (objectives/constraints/sampler panels)
- **optuna-results-ui.js**: Optuna Results-page UI helpers (dynamic columns/badges)
- Forms generated dynamically from `config.json`
- Strategy dropdown auto-populated from discovered strategies
- No hardcoded parameters in frontend

## API Endpoints Reference

### Page Routes

- `GET /` - Serve Start page
- `GET /results` - Serve Results page

### Optimization

- `POST /api/optimize` - Run Optuna optimization, returns study_id
- `POST /api/walkforward` - Run WFA, returns study_id
- `POST /api/backtest` - Run single backtest (no database storage)
- `GET /api/optimization/status` - Get current optimization state
- `POST /api/optimization/cancel` - Cancel running optimization

### Studies Management

- `GET /api/studies` - List all saved studies
- `GET /api/studies/<study_id>` - Load study with trials/windows
- `DELETE /api/studies/<study_id>` - Delete study
- `POST /api/studies/<study_id>/update-csv-path` - Update CSV path
- `POST /api/studies/<study_id>/trials/<trial_number>/trades` - Download trades CSV

### Strategy & Presets

- `GET /api/strategies` - List available strategies
- `GET /api/strategy/<strategy_id>/config` - Get strategy schema
- `GET /api/presets` - List presets
- `POST /api/presets` - Create preset
- `GET/PUT/DELETE /api/presets/<name>` - Load/update/delete preset

## Performance Considerations

- Use vectorized pandas/numpy operations
- Reuse indicator calculations where possible
- Avoid expensive logging in hot paths (optimization loops)
- `trade_start_idx` skips warmup bars in simulation
- Database uses WAL mode for concurrent read access
- Bulk inserts used for saving trials (executemany, not loop)

## Current Strategies

| ID                | Name            | Description                                                  |
| ----------------- | --------------- | ------------------------------------------------------------ |
| `s01_trailing_ma` | S01 Trailing MA | Complex trailing MA with 11 MA types, close counts, ATR stops |
| `s04_stochrsi`    | S04 StochRSI    | StochRSI swing strategy with swing-based stops               |

## Key Files for Reference

| Purpose             | File                                      |
| ------------------- | ----------------------------------------- |
| Full architecture   | `docs/PROJECT_OVERVIEW.md`                |
| Adding strategies   | `docs/ADDING_NEW_STRATEGY.md`             |
| Database operations | `src/core/storage.py`                     |
| Start page logic    | `src/ui/static/js/main.js`                |
| Results page logic  | `src/ui/static/js/results.js`             |
| Flask API endpoints | `src/ui/server.py`                        |
| S04 example         | `src/strategies/s04_stochrsi/strategy.py` |
| config.json example | `src/strategies/s04_stochrsi/config.json` |
| Test baseline       | `data/baseline/`                          |

