
# Target Architecture Overview
# Unified Core + Strategies + Optimization

**Version:** 2.0
**Date:** 2025-11-27
**Status:** Updated with final architecture decisions
**Scope:** Final target state of the project after migration from legacy architecture to new clean architecture.

---

## 0. Core Architecture Principles

### Data Structure Ownership

Following the principle **"structures live where they're populated"**:

- **TradeRecord, StrategyResult** → `backtest_engine.py` (populated during simulation)
- **BasicMetrics, AdvancedMetrics** → `metrics.py` (calculated from StrategyResult)
- **OptimizationResult, OptunaConfig** → `optuna_engine.py` (created during optimization)
- **WFAMetrics** → `metrics.py` (aggregated metrics calculation)
- **StrategyParams** → `strategies/<strategy_name>/strategy.py` (each strategy owns its params)

**No separate `types.py`** - structures imported directly from their "home" modules.

### Key Architectural Decisions

1. **StrategyParams location:** Each strategy defines its own params dataclass inside `strategy.py`
   - Rationale: Better encapsulation, each strategy owns its parameter structure
   - Impact: No shared StrategyParams, easier to add new strategies with different parameters

2. **metrics.py responsibility:** ONLY calculates metrics, doesn't orchestrate
   - Rationale: Single responsibility, other modules consume metrics
   - Impact: Cleaner separation of concerns

3. **Frontend separation timing:** UI refactoring happens AFTER core migration
   - Rationale: UI doesn't affect backend logic, logical to clean up last
   - Impact: Focus on high-risk backend phases first

4. **Grid Search removal:** Optuna is the sole optimizer
   - Rationale: Simplifies codebase, Optuna covers all use cases
   - Impact: One less engine to maintain, faster iterations

---

## 1. High-Level Structure

The project is divided into several logical layers:

- **Core Engines (3 main engines)**
  - `backtest_engine.py`
  - `optuna_engine.py`
  - `walkforward_engine.py`

- **Core Utilities**
  - `metrics.py` — unified metrics calculation layer
  - `export.py` — unified results export layer

- **Domain Layers**
  - `indicators/` — indicator library
  - `strategies/` — strategies and their configurations

- **Interface Layer**
  - `server.py` — HTTP API (Flask)
  - `index.html` + `main.js` + `style.css` — frontend
  - `run_backtest.py` — CLI wrapper for local runs (optional, dev utility)

Goal: all main business logic is concentrated in three engines and several clear auxiliary modules. Strategies and indicators are isolated, UI and wrappers don't depend on internal core details.

---

## 2. Core Engines

### 2.1. `backtest_engine.py` — Backtest Engine

**Purpose:**
Unified module for running a single strategy on given data.

**Main responsibilities:**

1. **Data Preparation**
   - Accept input DataFrame (or already loaded data).
   - Apply:
     - `date_range` filter,
     - warmup (`warmup_bars`),
     - index and column normalization (OHLCV).
   - Return prepared dataset for simulation.

2. **Trade Simulation (bar-by-bar loop)**

- Bar iteration:
  - invoke strategy logic (through main strategy contract, see below),
  - place orders by strategy through its API,
  - execute orders by core considering:
    - volume type (fixed `qty` or equity percentage),
    - commission,
    - contract size.
- Support:
  - entry/exit from position,
  - direction change (as needed).

3. **Results and Data Structures**

`backtest_engine.py` defines and uses basic data structures:

- `TradeRecord` — single trade record:
  - entry/exit time,
  - entry/exit price,
  - volume,
  - commission,
  - PnL and auxiliary fields.

- `StrategyResult` — strategy run result:
  - list of `TradeRecord`,
  - equity-curve / balance-curve,
  - basic aggregates (optional),
  - service information (e.g., run parameters).

Both structures are declared **inside** `backtest_engine.py` (as `dataclass` or TypedDict) and imported by other modules (`metrics.py`, `optuna_engine.py`, `walkforward_engine.py`, tests). No separate `types.py` is used.

> In current code, some metrics are already calculated inside `backtest_engine.py`. Target state — metrics calculation in `metrics.py`, while `StrategyResult` remains a common container for results and metrics.

4. **Contract**

- Input:
  - strategy class / strategy identifier,
  - strategy parameters (`StrategyParams`),
  - trading settings (commission, volume type, etc.),
  - prepared data.
- Output:
  - `StrategyResult` — unified result format, which is then consumed by `metrics.py`, `optuna_engine.py`, `walkforward_engine.py` and UI.

---

### 2.2. `optuna_engine.py` — Optimization Engine

**Purpose:**
The only optimizer in the project, using Optuna.

**Main responsibilities:**

1. **Optimization Configuration**

- `OptunaConfig` / `OptimizationConfig`:
  - strategy (id / class),
  - search space description (parameter ranges, types),
  - Optuna parameters (number of trials, sampler, pruner),
  - objective function configuration (which metrics are used in score).
- `OptimizationResult`:
  - parameters,
  - metrics,
  - final score.

Configuration/result structures can be implemented as dataclasses in `optuna_engine.py` itself or next to it.

2. **Integration with `backtest_engine` and `metrics`**

- For each trial:
  - forms `StrategyParams` (set of strategy parameters) from `Trial`,
  - runs `backtest_engine.run_backtest(...)`,
  - passes result to `metrics.calculate_basic/advanced`,
  - aggregates metrics and calculates score.

3. **Optuna Process Management**

- Creating and configuring Optuna study.
- Logic:
  - early stopping (through pruners),
  - if needed — serialization/recovery.
- In future: ability to add seed for reproducibility (currently — not required).

4. **Integration with Export**

- To save optimization results, calls functions from `export.py`, for example:
  - `export_optuna_results(results, path)`.

---

### 2.3. `walkforward_engine.py` — Walk-Forward Engine

**Purpose:**
WFA orchestrator, standing above `optuna_engine` and `backtest_engine`.

**Main responsibilities:**

1. **Window Splitting**

- Dividing the overall dataset into a sequence of in-sample / out-of-sample windows:
  - fixed windows,
  - sliding/rolling windows (as needed).
- Configuration:
  - in-sample length,
  - OOS length,
  - shift step.

2. **In-Sample Optimization**

- On each window:
  - forms `OptimizationConfig`,
  - calls `optuna_engine` to find best parameters,
  - selects best trial by score.

3. **OOS Testing**

- For each in-sample / OOS pair:
  - runs `backtest_engine` with best parameters on OOS segment,
  - gets `StrategyResult` for OOS.

4. **WFA Aggregation**

- Saves:
  - metrics for each window (in-sample, OOS),
  - overall summary metrics for entire WFA.
- Uses `metrics.calculate_basic/advanced` for calculation and if needed `metrics.calculate_for_wfa(...)`.

5. **Export**

- Calls `export.export_wfa_summary(wfa_results, path)` or other `export.py` functions to save results.

---

## 3. Core Utilities

### 3.1. `metrics.py`

**Purpose:**
Single place for calculating all metrics.

**Data Structures:**

- `BasicMetrics`:
  - Net Profit / Net Profit %,
  - Gross Profit / Gross Loss,
  - Max Drawdown / Max DD %,
  - Total Trades,
  - Win Rate, etc.

- `AdvancedMetrics`:
  - Sharpe,
  - Sortino,
  - Ulcer Index,
  - Profit Factor,
  - Consistency,
  - ROMAD, etc.

- `WFAMetrics` (optional):
  - aggregated metrics across all WFA windows (e.g., average Net Profit, average MaxDD, percentage of successful windows, etc.).

These structures are declared **inside** `metrics.py` and imported by other modules (`optuna_engine.py`, `walkforward_engine.py`, UI, tests).

**Functions/Areas of Responsibility:**

- `calculate_basic(result: StrategyResult) -> BasicMetrics`
- `calculate_advanced(result: StrategyResult) -> AdvancedMetrics`
- `calculate_for_wfa(wfa_results) -> WFAMetrics` (if separate format for WFA is needed)

---

### 3.2. `export.py`

**Purpose:**
All data export operations.

**Function Examples:**

- `export_trades_tv(trades, path: str) -> None`
  Export trade list to CSV format understood by TradingView Trading Report Generator.

- `export_optuna_results(results, path: str) -> None`
  Save Optuna optimization results (best parameters, metrics and score) to CSV.

- `export_wfa_summary(wfa_results, path: str) -> None`
  Export Walk-Forward summary by windows and final metrics.

If needed, can also add:

- JSON export,
- Excel export,
- aggregated report generation.

---

## 4. Indicators Layer (`indicators/`)

**Structure:**

```text
src/indicators/
  __init__.py
  ma.py           # SMA, EMA, WMA, KAMA, T3, HMA, etc.
  volatility.py   # ATR, NATR and other volatility indicators
  oscillators.py  # RSI, Stoch, CCI, etc.
  volume.py       # OBV and other volume-based indicators
  trend.py        # ADX and trend indicators
  misc.py         # other indicators and helpers
```

**Usage Rules:**

- All **common** indicators are placed here.
- If an indicator is needed by only one strategy:
  - it can be implemented in the strategy itself as `indicator_<name>` or through `custom_indicators`.

`BaseStrategy` implements fallback:

1. If the strategy class has method `indicator_<name>` — use it.
2. If indicator is specified in `custom_indicators` — use it.
3. Otherwise search for function `name` in `indicators.*` modules.

---

## 5. Strategies Layer (`strategies/`)

### 5.1. `strategies/base.py`

**Purpose:**
Base class for all strategies.

**Main Elements:**

- Main contract at first stage:
  - static method like `run(df, params, trade_start_idx=0) -> StrategyResult`,
  - which calls indicators and implements trading logic in terms of input data and parameters.
- In future (optional) a bar-oriented API `on_bar(ctx)` may be added, if it simplifies PineScript logic porting.
- Access to indicators through fallback mechanism.
- Access to strategy parameters (`StrategyParams`).
- Storage of internal state between bars (if needed).

### 5.2. Concrete Strategies

**Structure:**

```text
src/strategies/
  base.py
  s01_trailing_ma/
    config.json
    strategy.py
  simple_ma/
    config.json
    strategy.py
  s01_trailing_ma_migrated/   # for migration period
    config.json
    strategy.py
  ...
```

Each strategy:

- describes its parameters in `config.json` in unified format:
  - `parameters` block with description:
    - `type` (int/float/select, etc.),
    - `default`, `min`, `max`, `step`,
    - flag/object `optimize` for Optuna (ranges, enabled/disabled),
    - if needed — `label`, `group`, etc. for UI;
- implements trading logic in `strategy.py` (through main contract `run(...)`);
- uses indicators from `indicators/` and/or its own local ones.

Engines (`backtest_engine`, `optuna_engine`, `walkforward_engine`) work only with strategy contract (class + parameters + `config.json`), without knowing internal implementation.

---

## 6. Interface Layer

### 6.1. `server.py` — API

**Role:**

- Accept requests from UI/scripts.
- Transform input data into:
  - strategy parameters (`StrategyParams`),
  - backtest config,
  - optimization / WFA config.
- Call:
  - `backtest_engine.run_backtest(...)`,
  - `optuna_engine.run_optimization(...)`,
  - `walkforward_engine.run_walkforward(...)`,
  - `export.py` functions for export requests.
- Form JSON responses for frontend.

### 6.2. Frontend: `index.html`, `main.js`, `style.css`

- `index.html`:
  - form markup (strategy, parameters, modes),
  - containers for tables/charts.
- `style.css`:
  - interface styling.
- `main.js`:
  - parameter collection,
  - AJAX requests to `server.py`,
  - response processing,
  - DOM update, table and result rendering.

### 6.3. `run_backtest.py` (optional)

- CLI interface for local runs:
  - accepts through arguments: strategy, parameters, data path, optional logging flag (`--debug` / `--log-level`),
  - calls `backtest_engine.run_backtest(...)`,
  - prints metrics or calls `export.py` to save results.

---

## 7. Summary

Target project architecture:

- **3 main engines**:
  - `backtest_engine.py` — trade simulation,
  - `optuna_engine.py` — Optuna optimization,
  - `walkforward_engine.py` — WFA.

- **2 universal modules**:
  - `metrics.py` — metrics calculation (with `BasicMetrics`, `AdvancedMetrics`, `WFAMetrics`),
  - `export.py` — export.

- **2 domain layers**:
  - `indicators/` — indicators,
  - `strategies/` — strategies.

- **Interface Layer**:
  - `server.py` + frontend (HTML/JS/CSS) + optional CLI.

Data structures (`TradeRecord`, `StrategyResult`, `BasicMetrics`, etc.) are defined inside corresponding modules and reused through imports, without separate `types.py`. Simple test strategy and S_01_v2 (through temporary folder `s01_trailing_ma_migrated`) live in `strategies/` and use common architecture.
