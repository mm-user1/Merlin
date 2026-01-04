# Phase 4.1 Fixes Report (GPT-5.2)

Date: 2026-01-03

## Summary of Changes

- Removed residual `merlin.objective_missing` user attributes from Optuna trials.
- Removed penalty-objective handling and the `objective_missing` field from `OptimizationResult`, plus all related filtering in `optuna_engine.py` and `storage.py`.

- Added objective-value sanitization for zero-trade edge cases and returned NaN to mark genuinely missing/non-finite objectives as FAILED (Optuna-compliant) instead of using penalty constants.

- Added total violation magnitude sorting for infeasible trials to align with Optuna’s constrained-dominance behavior.

- Deleted unused `get_best_trial_info()` function.

## Implementation Details

- Issue 1: Objective values now pass through `_extract_objective_values()` -> `_sanitize_objective_values()`. If any objectives remain non-finite after sanitization, the objective function returns `NaN` and the trial is marked FAILED by Optuna (no penalty values, no post-filtering).

- Issue 2: Added `_calculate_total_violation()` and incorporated it into `sort_optimization_results()` to rank infeasible trials by summed violation magnitude before primary objective.

- Issue 3: Removed dead code function `get_best_trial_info()`.

## Tests / Reference Runs

- Ran CLI backtest using the required reference data file:

  - Command: `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe src\run_backtest.py --csv "data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"`

  - Result: Net Profit % = 230.75, Max Portfolio Drawdown % = 20.03, Total Trades = 93

- Full test suite:

  - Command: `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests/ -v`

  - Result: 104 passed, 3 warnings in 24.35s

  - Warnings: Optuna ExperimentalWarning about `multivariate` in TPESampler (from optuna/_experimental.py:32) in multiprocess score tests.

## Errors

- None encountered.

## Deviations / Notes

- The sanitization logic treats "zero trades" as the edge case for normalization. I did not expand "very small" beyond `total_trades <= 0` to avoid masking low-trade trials without explicit guidance.

## Files Modified

- `src/core/optuna_engine.py`

- `src/core/storage.py`

## Files Added

- `docs/phase_4-1_fixes_prompt_gpt-5.2_report.md`
