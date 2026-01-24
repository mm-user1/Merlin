# Phase 3-4 OOS Test Update Report

Date: 2026-01-24

## Summary of Changes
- Added shared period-test engine (`src/core/testing.py`) and refactored Manual Test to reuse it (now supports `stress_test` source tab).
- Implemented OOS Test period splitting with inclusive boundary semantics and integrated OOS execution into the optimization pipeline.
- Extended database schema for OOS metadata and per-trial metrics; added `save_oos_test_results` persistence.
- Added OOS Test configuration section on Start page and OOS Test tab on Results page (sorted by source order, shows source + source rank).
- Added tests for OOS period splitting and source precedence/order preservation.

## Reference Tests (CSV: `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`)
Command (using required interpreter):
```
C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -v tests\test_post_process.py tests\test_oos_selection.py tests\test_regression_s01.py
```
Results:
- 21 passed

## Full Test Suite
Command (using required interpreter):
```
C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -v tests\
```
Results:
- 142 passed, 3 warnings

Warnings:
- optuna ExperimentalWarning: Argument "multivariate" is experimental (seen in `tests/test_multiprocess_score.py`).

## Errors
- None.

## Deviations / Notes
- Manual Test now includes full advanced metrics (sortino, ulcer, sqn, consistency) in stored results to match OOS metric set; UI now surfaces these fields in Manual Test tables.
