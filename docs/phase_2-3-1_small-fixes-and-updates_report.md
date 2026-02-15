# Phase 2.3.1 Small Fixes and Updates Report

## Update Goal
Prevent cancelled optimization / walk-forward queue runs from leaving unfinished studies in the database, preserve safe resume behavior for queued multi-CSV processing, and make queue `Cancel` behave as a graceful stop-after-current action.

## Problem Summary
Before this update:
1. Queue cancel aborted the browser request, but backend processing could continue.
2. A study could still be saved before frontend cancellation became visible.
3. Restarting queue could require manual cleanup of unfinished study rows.
4. Queue cancel semantics were not aligned with desired UX ("finish current run, then stop queue").

## What Was Implemented

### 1) Backend run-token cancellation model
Files:
- `src/ui/server_services.py`
- `src/ui/server_routes_run.py`

Changes:
1. Added run token helpers and cancellation registry in `server_services`:
- `_normalize_run_id(...)`
- `_register_cancelled_run(...)`
- `_is_run_cancelled(...)`
- `_clear_cancelled_run(...)`
- bounded cleanup logic with TTL and max-size limits.

2. Extended `/api/optimization/cancel` in `server_routes_run`:
- accepts `run_id`/`runId` (query/form),
- falls back to current optimization state's run id if omitted,
- marks that specific run token as cancelled.

3. Added request run-id resolution:
- `_resolve_request_run_id(...)` creates a safe unique run id when not provided.

### 2) Cancel-safe cleanup in optimization endpoints
File:
- `src/ui/server_routes_run.py`

Changes:
1. `run_id` is now assigned to each `/api/optimize` and `/api/walkforward` request and included in optimization state.
2. Added cancellation checkpoints:
- immediately after core optimization/walk-forward returns,
- before post-processing phases,
- before final completion state.
3. On cancelled run:
- backend deletes the just-saved study (`delete_study(study_id)`),
- returns `{ status: "cancelled", study_id: null, run_id: ... }`,
- avoids writing additional post-process artifacts.

Result:
- cancelled unfinished runs are not retained in DB.

### 3) Frontend run-id propagation and cancel correlation
Files:
- `src/ui/static/js/api.js`
- `src/ui/static/js/queue.js`
- `src/ui/static/js/ui-handlers.js`
- `src/ui/static/js/results-controller.js`

Changes:
1. Per-source request run-id generation added for queue and normal optimize/WFA flows.
2. `runId` is appended to form payload for `/api/optimize` and `/api/walkforward`.
3. Cancel API call now supports targeted cancel:
- `cancelOptimizationRequest(runId)` -> `/api/optimization/cancel?run_id=...`
4. Active run-id is mirrored into stored optimization state (`run_id`) for cross-tab consistency.
5. API client interprets backend `{status:"cancelled"}` as `AbortError` to preserve existing cancel flow handling.

### 4) Regression tests added
File:
- `tests/test_server.py`

Added tests:
1. `test_optimize_cancelled_run_cleans_up_saved_study`
2. `test_walkforward_cancelled_run_cleans_up_saved_study`

Both verify:
- cancelled run response is returned,
- `study_id` is `None` in response,
- cleanup (`delete_study`) is executed for the cancelled run.

### 5) Queue cancel semantics switched to graceful stop-after-current
Files:
- `src/ui/static/js/queue.js`
- `src/ui/static/js/ui-handlers.js`

Changes:
1. Added queue-level stop flag (`queueStopRequested`) and `requestQueueStopAfterCurrent()` in `queue.js`.
2. While queue is running, clicking `Cancel Queue` now sets stop request instead of aborting active fetch.
3. Queue loop now stops only after current source run reaches a natural completion boundary.
4. If current source finishes successfully, its study is persisted normally.
5. Queue exits before starting next source/item and keeps remaining queue entries for later resume.
6. `sourceCursor` progress remains persisted, so completed source is not re-run.
7. `submitOptimization()` queue-running branch in `ui-handlers.js` now calls `requestQueueStopAfterCurrent()` instead of `optimizationAbortController.abort()`.

### 6) Queue loading changed to explicit on-demand attach
Files:
- `src/ui/static/js/queue.js`
- `src/ui/static/js/main.js`
- `src/ui/static/js/ui-handlers.js`
- `src/ui/templates/index.html`

Changes:
1. Added and wired `Load Queue` action in the queue controls.
2. Queue UI is now detached by default on startup (`queueUiLoaded = false`) and does not auto-attach from stored `merlinRunQueue`.
3. `submitOptimization()` now enters queue mode only when queue is explicitly loaded (`isQueueLoaded()`) or currently running.
4. `+ Add to Queue` now explicitly tries to attach an existing stored queue first, then appends the new item.
5. When adding the first item to a new queue, queue UI is attached immediately so item `#1` is visible and runnable without page refresh.
6. Runtime recovery remains robust:
- queue run start writes runtime marker (`merlinQueueRuntime.active = true`);
- run finish clears it;
- on page reload, startup auto-attaches queue only if runtime marker is active and stored queue items still exist.

Result:
- normal startup is clean for development/testing workflows;
- persisted queues remain available via explicit `Load Queue` or auto-load on `+ Add to Queue`;
- active run reload scenario still restores queue context safely.

### 7) Queue persistence migrated from browser localStorage to project file storage
Files:
- `src/ui/server_services.py`
- `src/ui/server_routes_data.py`
- `src/ui/static/js/api.js`
- `src/ui/static/js/queue.js`
- `src/ui/static/js/main.js`

Changes:
1. Added backend queue file storage in `src/storage/queue.json` with normalization and atomic write logic:
- `_load_queue_state(...)`
- `_save_queue_state(...)`
- `_clear_queue_state(...)`
- queue payload normalization for items/sources/counters/runtime.
2. Added queue API endpoints:
- `GET /api/queue`
- `PUT /api/queue`
- `DELETE /api/queue`
3. Reworked frontend queue persistence to API-backed state:
- added `fetchQueueStateRequest(...)`, `saveQueueStateRequest(...)`, `clearQueueStateRequest(...)` in `api.js`;
- `queue.js` now keeps an in-memory cache and syncs it to backend storage (instead of localStorage).
4. Queue runtime marker (`active`, `updatedAt`) is now part of queue payload and persisted in `queue.json` while queue has pending items.
5. Queue file lifecycle now aligns with UX target:
- queue file is created when queue has items;
- queue file is removed when queue becomes empty;
- file presence indicates pending/unfinished queue.
6. Added one-time safe migration path:
- if backend queue is empty and legacy localStorage queue exists, frontend migrates it to `queue.json`;
- legacy localStorage keys are cleared after migration.
7. Updated queue UI handlers to await async queue load/save operations and surface queue API errors to UI.

Result:
- queue persistence is moved out of browser storage into project storage (`src/storage/queue.json`);
- queue survives browser localStorage cleanup/profile changes;
- operational behavior of queue runner remains browser-driven as intended.

## Behavior After Update
1. Queue item with multiple CSVs still resumes from first unfinished source (`sourceCursor` behavior unchanged).
2. Main page `Cancel Queue` now means "stop after current run":
- active source is not aborted,
- if active source completes successfully, it is saved to DB,
- queue stops before the next source/item starts.
3. Resuming queue does not re-run already completed and recorded source runs.
4. Run-token hard-cancel cleanup logic remains available for explicit targeted cancel flows, so cancelled runs can still be safely cleaned when true cancellation is used.
5. Saved queue is not auto-loaded on a normal page open; user can explicitly attach it via `Load Queue`.
6. Clicking `+ Add to Queue` on an existing persisted queue attaches that queue first, then adds the new item.
7. If queue run was active and page reloaded, runtime-marker recovery auto-attaches queue state to avoid losing run context.

## Reference Test Results
Executed with:
- `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe`

Commands and outcomes:
1. `-m py_compile src/ui/server_services.py src/ui/server_routes_run.py tests/test_server.py`
- Passed.

2. `-m pytest -q tests/test_server.py -k "cancelled_run_cleans_up_saved_study"`
- Passed: `2 passed`.

3. `-m pytest -q tests/test_db_management.py`
- Passed: `12 passed`.

4. `-m pytest -q tests/test_server.py`
- Passed: `19 passed`.

5. `-m pytest -q tests/test_server.py tests/test_db_management.py` (final regression run after queue cancel semantic switch)
- Passed: `31 passed`.

6. `-m pytest -q tests/test_server.py tests/test_db_management.py` (regression rerun after on-demand queue loading update)
- Passed: `31 passed`.

7. `-m pytest -q tests/test_server.py -k "queue_api"`
- Passed: `3 passed`.

8. `-m pytest -q tests/test_server.py tests/test_db_management.py` (final regression after queue storage migration)
- Passed: `34 passed`.

## Errors Encountered
1. Initial targeted pytest run failed before test execution due OS permission denial in default pytest temp directory (`C:\Users\mt\AppData\Local\Temp\pytest-of-mt`).
2. Resolved by updating new tests to use a workspace-local temporary directory under `tests/.tmp_server_cancel`.
3. Re-ran tests successfully afterward.

## Robustness and Future-Proofing Notes
1. Run-token cancellation is scoped per request and resilient to overlapping/restarted runs.
2. Registry is bounded (TTL + max size) to avoid unbounded in-memory growth.
3. Cleanup path is defensive and logs failures without crashing route handlers.
4. Queue resume semantics are preserved and queue cancel now uses explicit graceful stop-after-current boundaries.

## Final Outcome
The update addresses all current targets:
1. cancelled unfinished runs can be cleaned safely with run-token cancellation;
2. queue `Cancel` now stops after the current run while preserving completed DB writes and avoiding re-run of already completed sources;
3. queue persistence is explicit and UX-safe (`Load Queue` / auto-attach-on-add) without forced startup auto-loading, while keeping active-run reload recovery;
4. queue storage is now project-local (`src/storage/queue.json`) with robust API-backed persistence and cleanup semantics.
