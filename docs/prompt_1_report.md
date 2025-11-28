# Phase 1 Report: Core Extraction to `src/core/`

## Summary
- Created the `src/core` package with a documented `__init__.py` exposing the backtest, Optuna, and walk-forward engines at the package level.
- Moved `backtest_engine.py`, `optuna_engine.py`, and `walkforward_engine.py` into `src/core/` and updated all project imports (CLI, server, strategies, tools, and tests) to reference the new package.
- Adjusted sanity tests to validate the new directory layout and import paths, and refreshed migration progress documentation to mark Phase 1 as complete.

## Reference Tests
- Dataset: `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv` (used by regression suite via `load_data`).
- Commands executed:
  - `pytest tests/ -v` → **21/21 passing**.

## Notes / Deviations
- The new `core/__init__.py` exposes the available walk-forward interfaces (`WFConfig`, `WFResult`, `WalkForwardEngine`, and export helpers) instead of a non-existent `run_walkforward` function; no behavior changes were introduced.

## Errors
- None encountered during this phase.
