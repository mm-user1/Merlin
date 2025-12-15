# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cryptocurrency trading strategy backtesting and optimization platform. The system uses a hybrid architecture: typed strategy modules with camelCase parameters, a generic config-driven core (Optuna-only), and a light-themed Flask SPA frontend.

## Running the Application

### Web Server
```bash
cd src/ui
python server.py
```
The server runs at http://0.0.0.0:8000 and serves the SPA from `index.html`.

### CLI Backtest
```bash
cd src
python run_backtest.py --csv ../data/OKX_LINKUSDT.P,\ 15\ 2025.05.01-2025.11.20.csv
```

### Dependencies
```bash
pip install -r requirements.txt
```
Key dependencies: Flask, pandas, numpy, matplotlib, optuna==4.4.0.

## Architecture (Target)

- **Parameter naming:** camelCase end-to-end (Pine → config.json → Python → CSV). No snake_case fallbacks or conversion helpers.
- **Hybrid model:**
  - Strategies own their dataclasses and logic (`src/strategies/<id>/strategy.py`).
  - Core modules remain strategy-agnostic and consume `Dict[str, Any]` parameter dicts (`OptimizationResult.params`).
- **Config-driven:**
  - Backend loads parameter schemas from each strategy's `config.json`.
  - Frontend renders parameter controls directly from `config.json`.
  - CSV export builds headers from `config.json` (no hardcoded fields).
- **Engines:**
  - `core/backtest_engine.py` — single backtests, defines trade/result structures.
  - `core/optuna_engine.py` — the only optimizer (grid search removed).
  - `core/export.py` and `core/metrics.py` — generic metrics + CSV exports.
- **Strategy discovery:** `strategies/__init__.py` auto-loads strategies that contain both `config.json` and `strategy.py`.

## Parameter Naming Rules

- ✅ `maType`, `closeCountLong`, `rsiLen`
- ❌ `ma_type`, `close_count_long`, `rsi_len`
- Internal control fields (`use_backtester`, `use_date_filter`, `start`, `end`) may stay snake_case but are excluded from UI/config.
- Do not add `to_dict` or snake↔camel conversion layers; use `dataclasses.asdict`.

## Performance & Caching

- Backtests and optimizations rely on vectorized pandas/numpy routines.
- Reuse indicator calculations where possible; avoid per-call recomputation inside loops.
- Maintain Optuna-friendly objective functions and avoid expensive logging in hot paths.

## Testing Expectations

- Unit tests live in `tests/` and must pass with camelCase fixtures.
- Naming guardrails: `tests/test_naming_consistency.py` enforces parameter casing, config/dataclass alignment, and absence of feature flags.
- Regression coverage: `tests/test_regression_s01.py` and `tests/test_s01_migration.py` verify baseline behavior using `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`.

## Common Workflow

1. Load or upload OHLCV CSV data.
2. Choose a strategy (`s01_trailing_ma` or `s04_stochrsi`).
3. Configure parameters (camelCase) via UI or API payloads.
4. Run backtest or Optuna optimization; results export to CSV with camelCase headers.
5. Analyze metrics (net profit %, drawdown, Sharpe, RoMaD, etc.) and iterate.

## Development Notes

- Preserve light theme styling in the SPA.
- Keep core modules free of strategy-specific fields; add new strategies via `config.json` + `strategy.py` only.
- Follow `docs/ADDING_NEW_STRATEGY.md` for onboarding new strategies.
