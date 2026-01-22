# Phase 3-3 Win Rate % & Max Consecutive Losses Report (v4)

Date: 2026-01-22

## Summary
- Added `max_consecutive_losses` to basic metrics and Optuna result plumbing (including constraint support).
- Persisted the new metric in SQLite for both Optuna trials and Forward Test results.
- Extended Forward Test and Manual Test pipelines to compute and surface the metric.
- Updated Results UI to show fixed **WR %** and **Max CL** columns and added a constraints row for Max CL.

## Changes Implemented
- Metrics: `BasicMetrics` now computes `max_consecutive_losses` with breakeven counted as a loss streak continuation. (`src/core/metrics.py`)
- Optuna: added `max_consecutive_losses` to `OptimizationResult`, constraint operators, metrics collection, and trial reconstruction. (`src/core/optuna_engine.py`)
- Storage: added `max_consecutive_losses` and `ft_max_consecutive_losses` columns, migration ensures, INSERT, and FT UPDATE plumbing. (`src/core/storage.py`)
- Forward Test: added IS/FT max CL fields, metrics payload keys (unprefixed), and FTResult mapping. (`src/core/post_process.py`)
- Manual Test: added metric to `test_metrics` and `original_metrics`. (`src/ui/server.py`)
- UI: labels/operators, fixed columns, FT/Manual mappings, and constraints row. (`src/ui/static/js/results.js`, `src/ui/static/js/optuna-results-ui.js`, `src/ui/templates/index.html`)
- Tests: added a unit test for max consecutive losses including breakeven behavior. (`tests/test_metrics.py`)

## Tests (Reference)
Dataset requested: `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`

Initial run:
- `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q`
- Result: **1 failed, 136 passed** (30.78s)
- Failure: `tests/test_walkforward.py::test_walkforward_integration_with_sample_data`
  - Error: `ValueError: not enough values to unpack (expected 2, got 1)`
  - Cause: test’s mock `_run_optuna_on_window` returned a single list, but production expects a tuple `(optimization_results, optimization_all_results)`.

After fixing the test mock:
- `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q`
- Result: **137 passed** (24.86s, 3 warnings)
- Note: CLI run timed out in the tool wrapper, but the pytest output shows completion and pass status.

## Deviations / Notes
- Did not add `max_consecutive_losses` as an **objective** (constraint-only per requirement). Accordingly, `OBJECTIVE_DIRECTIONS` was not extended.
- Added one new unit test beyond the plan to validate breakeven streak handling.
- Updated `tests/test_walkforward.py` mock to return a tuple `(results, all_results)` to match `WalkForwardEngine._run_optuna_on_window` contract; this fixes the unpacking error and keeps the test aligned with production behavior.
