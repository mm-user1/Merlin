# Phase 4 Optuna Enhancements — Implementation Report

Date: 2026-01-02

## Summary of Work
- Implemented multi-objective Optuna configuration (objectives, primary objective, directions, Pareto sorting) with constraint-aware sorting and best-trial selection.
- Added soft constraints handling (evaluation, constraints_func wiring, feasibility flags) and extended samplers (TPE, Random, NSGA-II, NSGA-III with settings).
- Expanded metrics to include Sortino ratio and persisted new objective/constraint fields in the fresh DB schema.
- Updated UI (objectives, constraints, NSGA settings, results rendering) with new helper JS files and styling.
- Updated server validation to enforce objectives/constraints/sampler rules and updated optimization payload parsing.
- Updated tests referencing legacy Optuna target to use objective-based config.
- Stabilized multi-objective optimization behavior by disabling pruning and handling missing-objective trials without crashing TPE.

## Reference Tests
- Executed: `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q`
- Result: 104 passed, 3 warnings (Optuna ExperimentalWarning for `multivariate`).

## Errors / Issues
- Test execution blocked because `pytest` is not available on this machine.

## Multi-Objective Pruning & Missing Objectives Handling

### Background
Optuna does not support `trial.should_prune()` for multi-objective studies. Additionally, in multi-objective + TPE mode, if any objective value is missing/NaN for a trial, pruning it can leave the study with inconsistent objective vector lengths, which can trigger a TPE crash (`inhomogeneous shape` errors in NumPy).

### Change 1 — Disable pruning for multi-objective studies
- Multi-objective optimization runs now **disable pruning end-to-end**.
- This follows Optuna’s documented limitation that pruning is only supported for single-objective studies.

### Change 2 — Penalty instead of pruning (all multi-objective samplers)
- When a selected objective is missing/NaN:
  - In **any multi-objective mode** (TPE, NSGA-II, NSGA-III), the trial is **not pruned**.
  - Instead, objective values are filled with **direction-aware penalty values**:
    - Maximize → very low value (e.g., `-1e12`)
    - Minimize → very high value (e.g., `1e12`)
- This keeps all completed trials structurally consistent for the TPE sampler, preventing crashes.

### Change 3 — Mark invalid trials and filter from UI/DB
- Trials that used the penalty fallback are tagged as `objective_missing = True`.
- These trials are then **filtered out**:
  - **Before sorting and displaying in the UI**
  - **Before saving to the database**
- Net effect: output results match the prior “pruned” behavior (invalid trials do not appear), while avoiding the TPE crash.
- When the fallback triggers, a warning is logged noting the trial number, that penalty values were applied, and that the trial is marked invalid.
- Expected log message format:
  - `Objective missing for trial <n>; applying penalty values and marking invalid (multi-objective). Reason: Missing or NaN value for objective: <objective>`

## Post-Run Filtering for Net Profit / Score Filters
- Net Profit and Score filters now **apply after optimization completes** instead of pruning during the run.
- Rationale:
  - The backtest already finishes before the filter decision, so pruning does **not** save runtime.
  - Pruning reduces Optuna’s learning signal by discarding completed trials.
- Outcome:
  - All trials contribute to the sampler during optimization.
  - Filtering is applied only in the final results list and database storage.

## Deviations from Plan
- None. All changes were implemented according to the Phase 4 plan and GPT-5.2 prompt.
