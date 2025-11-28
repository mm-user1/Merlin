## Base rules for project:
Act as an experienced Python and Pinescript developer with trading and crypto algorithmic trading expertise.
IMPORTANT: Work strictly according to the given specifications. Any deviations are prohibited without my explicit consent.
IMPORTANT: The script must be maximally efficient and fast.
IMPORTANT: The GUI must use a light theme.

"./data" folder is used for examples, market data files etc.
"./docs" folder is used for documentation, plans, reference scripts etc.
"./src" is the main project folder

---

## Project Overview

This is a **cryptocurrency trading strategy backtesting and optimization platform** focused on the "Trailing Moving Average" strategy (S01). The project provides both a web interface (Flask SPA) and CLI tools to run single backtests or optimize across thousands of parameter combinations using Bayesian optimization (Optuna).

### Key Features
- **Single Backtest**: Test strategy with specific parameters on OHLCV data
- **Optuna Optimization**: Bayesian optimization with 5 targets (score, net_profit, romad, sharpe, max_drawdown) and 3 budget modes (n_trials, timeout, patience)
- **Walk-Forward Analysis**: Time-series cross-validation with in-sample optimization and out-of-sample testing
- **11 Moving Average Types**: SMA, EMA, WMA, HMA, VWMA, VWAP, ALMA, DEMA, KAMA, TMA, T3
- **Advanced Metrics**: Sharpe, Sortino, RoMaD, Profit Factor, Ulcer Index, Consistency Score
- **CSV Export**: Results with parameter block header + detailed metrics table

### Current Status: Architecture Migration

The project is currently **migrating from legacy S01-centric architecture to clean core architecture**. This migration separates concerns into distinct layers:

**Target Architecture** (after migration):
- **Core Engines** (`src/core/`): `backtest_engine.py`, `optuna_engine.py`, `walkforward_engine.py`
- **Utilities** (`src/core/`): `metrics.py`, `export.py`
- **Indicators** (`src/indicators/`): MA types, ATR, and other indicators
- **Strategies** (`src/strategies/`): Strategy implementations with own parameters
- **UI Layer** (`src/ui/`): Flask server + HTML/CSS/JS frontend

**Migration Plan** (9 phases total):

- Phase -1: Test Infrastructure Setup
- Phase 0: Regression Baseline for S01
- Phase 1: Core Extraction to `src/core/`
- Phase 2: Export Extraction to `export.py`
- Phase 3: Grid Search Removal (Optuna-only)
- Phase 4: Metrics Extraction to `metrics.py`
- Phase 5: Indicators Package Extraction
- Phase 6: Simple Strategy Testing
- Phase 7: S01 Migration via Duplicate
- Phase 8: Frontend Separation
- Phase 9: Logging, Cleanup, Documentation

**Key Migration Principles**:
- Preserve S01 behavior (bit-exact results where possible)
- Test-driven migration with regression tests
- Legacy code remains until new code is validated
- Data structures live where they're populated (no separate `types.py`)
- Each strategy owns its parameter dataclass
