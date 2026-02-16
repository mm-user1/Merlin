# Phase 2-3-2 Report: Load Run Parameters From Queue Item

Date: 2026-02-16
Scope: Implement click-to-load of full run configuration from Run Queue items into the main UI form.

## Problem Solved

When queue is loaded, user could not quickly reuse an existing queue item's full configuration (strategy, optimizer setup, WFA/post-process/OOS settings, CSV sources, DB target, etc.) after page reload. Re-adding similar runs required manual reconfiguration.

This update adds direct loading of run settings from a queue item by clicking the item in the Run Queue list.

## What Was Implemented

### 1) Queue Item Click-to-Load Behavior

File: `src/ui/static/js/queue.js`

- Added click handling for each queue row in `renderQueue()`.
- Added keyboard accessibility (`Enter` / `Space`) for queue rows.
- Preserved remove-button behavior (`stopPropagation` remains intact).
- Queue item click-to-load is available both when queue is idle and while queue is running.

### 2) Full Form Restore Pipeline

File: `src/ui/static/js/queue.js`

Added `loadQueueItemIntoForm(itemId)` and supporting helpers that restore the run state into the main UI:

- Strategy restore:
  - Validates strategy id from item.
  - Selects strategy and reloads strategy config (`loadStrategyConfig`) before applying settings.
- CSV restore:
  - Restores selected CSV absolute paths.
  - Restores CSV directory from first source path parent directory.
- Core optimizer restore:
  - Date filter/start/end.
  - Dynamic strategy backtest params from `fixed_params`.
  - Enabled optimizer params and ranges (including select/options params).
  - Budget mode, trials/time/convergence, sampler/pruner/startup/pruning, NSGA fields.
  - Objectives and primary objective.
  - Constraints.
  - Sanitize controls.
  - Min-profit filter and score filter config.
- Run-mode restore:
  - WFA toggle and WFA fields.
  - Post-process (FT/DSR/Stress) fields.
  - OOS test fields with WFA mutual exclusion respected.
- DB target restore:
  - Attempts direct selection.
  - If missing, refreshes DB list and retries.
- UI sync after restore:
  - Re-runs control synchronization hooks and trigger events to keep dependent UI state consistent.

### 3) Future-Proofing via UI Snapshot

File: `src/ui/static/js/queue.js`

- Added `collectQueueUiSnapshot()` in queue item creation.
- Queue items now store `uiSnapshot` containing values/checked state for form controls by id.
- Added `applyQueueUiSnapshot()` during queue item load.
- Restore pipeline now does:
  1. Config-based fallback restore (backward compatible with old queue items).
  2. Snapshot overlay restore (forward-compatible for newly added UI controls/features).

This allows new future controls (with stable ids) to restore without adding dedicated mapping logic each time.

### 4) UX Cue for Clickable Queue Items

File: `src/ui/static/css/style.css`

- Added `.queue-item-clickable` styling:
  - Pointer cursor.
  - Subtle underline on label hover/focus.

### 5) Follow-up: Safe Loading During Active Queue Execution

File: `src/ui/static/js/queue.js`

- Removed the hard block that rejected queue item loading when `queueRunning === true`.
- Added request sequencing (`queueItemLoadRequestId`) so stale click requests do not overwrite newer user actions.
- Added snapshot fallback in click handler:
  - Each row click passes current item snapshot.
  - If item disappears from queue before load completes, restore still works from snapshot.
- Added protection for active run progress UI:
  - While queue is running, click-to-load does not overwrite `optimizerResults` progress text.
  - Load errors during active queue execution go to console warning (instead of replacing run progress output).

## Key Logic and Targets

Primary target achieved: Clicking a queue item loads all run-critical settings into current UI state so user can tweak and re-queue quickly.

Reliability targets addressed:

- No change to execution semantics of existing queue processing.
- Backward compatible with existing queue entries that do not have `uiSnapshot`.
- Uses existing form generation/sync functions to avoid divergent state.
- Keeps queue removal and run controls behavior unchanged.
- Allows parameter loading during active queue execution without interrupting active run logic.
- Prevents queue progress panel corruption during active execution.

## Validation and Tests

### Static Parse Checks (JavaScript)

Executed:

- `node --check src/ui/static/js/queue.js`
- `node --check src/ui/static/js/main.js`
- `node --check src/ui/static/js/ui-handlers.js`

Result: passed.

### Python Regression Tests

Executed with required interpreter:

- `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q tests/test_server.py tests/test_db_management.py`

Result: `34 passed`.

## Errors Encountered

No implementation/runtime errors were encountered during static checks and regression test run.

## Notes

- This update is UI-focused; no backend API contract changes were introduced.
- Queue item load shows a short confirmation text in optimizer results area when queue is idle.
- During active queue execution, queue item loading still works, but progress area text is preserved.
