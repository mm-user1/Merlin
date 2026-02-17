# Phase 2-3-3 Report: Keep Finished Queue Items + No Auto Deletion of Queue File

Date: 2026-02-17
Scope: Main UI queue behavior during/after execution, queue persistence semantics, and run-trigger logic.

## Problems Solved

1. Completed queue items were removed immediately during run, so users could not click finished entries to reload parameters and requeue quick tweaks.
2. Queue storage (`queue.json`) was effectively consumed to empty state on full completion (because items were removed), making finished item history unavailable without manual reconstruction.
3. `Run Optimization` handling used total queue item count, which is no longer correct once completed-history items are retained.

## Implemented Changes

### 1) Persistent Per-Item Final State

File: `src/ui/static/js/queue.js`

- Added normalized final-state model:
  - `finalState = '' | 'completed' | 'failed'`
- Added helpers:
  - `normalizeQueueFinalState(...)`
  - `isQueueItemFinalized(...)`
  - `countQueuePendingItems(...)`
  - `findNextPendingQueueItem(...)`
  - `getQueuePendingCount(...)`
- Queue normalization now preserves and normalizes `finalState` and auto-recovers legacy items that reached full cursor with known success/failure counts.

Result: queue now has explicit distinction between pending and finalized items.

### 2) Runner Processes Pending Items Only

File: `src/ui/static/js/queue.js`

- Refactored queue execution loop to select `findNextPendingQueueItem(...)` instead of always `items[0]`.
- Added `finalizeQueueItem(...)` to persist final state at item completion/failure.
- Removed logic that deleted finished items from `queue.items`.
- On cancel/stop mid-item:
  - unfinished item remains pending (no final state set), so it can continue later.
- On full completion of an item:
  - item remains in list with `finalState` set.

Result: completed/failed entries stay visible and reusable; only pending entries are executed.

### 3) Queue UI Keeps Finished Items Visible

File: `src/ui/static/js/queue.js`

- Queue row rendering now applies persistent state classes from `item.finalState`.
- Tooltip now includes status (`Pending` / `Completed` / `Failed`).
- Finished rows keep remove button locked/hidden (aligned with clear-on-demand workflow).

Result: during and after run, user can see what already finished and click finished items to load parameters.

### 4) No Auto-Clear After Full Completion

Files: `src/ui/static/js/queue.js`

- Because finished items are no longer removed, queue storage is retained after completion.
- Queue file is deleted only when queue becomes empty (e.g., via `Clear` action).

Result: `queue.json` persists finished history until explicit `Clear`.

### 5) Run Button / Submit Logic Uses Pending Count

Files:
- `src/ui/static/js/queue.js`
- `src/ui/static/js/ui-handlers.js`

- `updateRunButtonState()` now shows queue mode based on pending count (not total items).
- `submitOptimization(...)` now starts queue only when `queuePendingCount > 0`.

Result:
- If queue only has finished history, `Run Optimization` behaves as normal optimization (does not enter queue runner).
- Queue execution starts only when there are actual pending items.

### 6) Empty-Pending Feedback

File: `src/ui/static/js/queue.js`

- `runQueue()` now reports: "Queue has no pending items. Completed items are kept until you click Clear." when user tries to run with history-only queue.

## Key Logic and Behavior After Update

1. Finished items remain in queue list and are reusable for click-to-load/tweak/requeue workflows.
2. Pending items are the only runnable items.
3. Cancel mid-item preserves unfinished progress as pending.
4. Full queue completion does not erase queue history.
5. `Clear` remains the explicit action that removes all items and clears queue storage.

## Robustness / Safety Notes

- Execution reliability is preserved: runner is item-config driven and ignores finalized entries.
- Migration-safe normalization handles legacy entries that had no `finalState` field.
- Future-proofed separation of concerns:
  - render/UX can use final state,
  - execution path uses pending filter.

## Reference Validation

### JavaScript Syntax Checks

Executed:

- `node --check src/ui/static/js/queue.js`
- `node --check src/ui/static/js/ui-handlers.js`
- `node --check src/ui/static/js/main.js`

Result: passed.

### Python Regression Tests

Executed with required interpreter:

- `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q tests/test_server.py tests/test_db_management.py`

Result: `34 passed`.

## Errors Encountered

No implementation or test errors after final patch set.

## Modified Files

- `src/ui/static/js/queue.js`
- `src/ui/static/js/ui-handlers.js`
- `docs/phase_2-3-3_keep-unfinished-queue-items+no-auto-deletion-queue-file_report.md`
