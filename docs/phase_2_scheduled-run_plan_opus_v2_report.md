# Phase 2 Scheduled Run Update - Implementation Report

## 1. Summary

This update implements a robust **Run Queue** for Merlin's Start page, allowing users to queue multiple Optuna/WFA runs and execute them sequentially.

Primary goals from the v2 plan were implemented with additional reliability hardening:

- Queue UI added to Start page.
- Queue persistence via `localStorage`.
- Sequential execution over queued items and item CSV sources.
- Safe cancel behavior with re-entry guard.
- Results page state integration using valid modes (`optuna` / `wfa` only).
- Constraint tooltip operator rendering fixed.
- Label numbering uniqueness fixed.
- Queue source handling supports both absolute paths and browser file uploads.

No backend routes were modified.

## 2. Problems Solved

The implementation addresses the key previously identified issues:

1. **Cancel re-entry bug**  
   Fixed by adding a `queueRunning` guard and cancel branch in `submitOptimization()`.  
   Repeated button clicks during queue run no longer re-enter `runQueue()`.

2. **Results mode compatibility**  
   Queue writes optimization state using actual item mode (`optuna` or `wfa`) and never uses a custom `queue` mode.

3. **Constraint tooltip mismatch**  
   Tooltip operator is derived from metric name (`<=` for DD/CL/Ulcer metrics, otherwise `>=`) instead of a missing `operator` field.

4. **Label index duplication**  
   Queue uses monotonic `nextIndex` and preserves it across clear operations (no index reuse).

5. **Browser file picker incompatibility**  
   Queue no longer requires absolute filesystem paths for every source.  
   It now supports two source types:
   - `path` (absolute filesystem path)
   - `file` (browser-selected file content)

6. **Mid-item restart duplication risk**  
   Added per-item persisted source cursor (`sourceCursor`) plus counters.  
   On cancellation/restart, processed sources are not repeated.

7. **Terminal status accuracy edge case**  
   Fixed queue completion state logic so:
   - cancellation between items still persists `status: cancelled`
   - all-failed queue runs persist `status: error` (not `completed`)

## 3. Implemented Changes

## 3.1 New file

- `src/ui/static/js/queue.js`

Implemented queue management end-to-end:

- Storage and migration-safe loading:
  - `loadQueue()`, `saveQueue()`, `normalizeQueueItem()`
  - Schema: `{ items, nextIndex }` with source model migration:
    - legacy: `csvPaths[]`
    - current: `sources[]` (`path` / `file`)
- Validation and collection:
  - `collectQueueSources()`, `collectQueueItem()`
  - Auto-detects and stores:
    - path sources when absolute path is available
    - file sources when only browser file object is available
- File blob persistence:
  - IndexedDB store `merlinQueueFiles/files`
  - `putQueuedFileBlob()`, `getQueuedFileBlob()`, cleanup for stale/removed keys
- UI rendering and state:
  - `renderQueue()`, `updateRunButtonState()`, `setQueueItemState()`
  - Queue row tooltips include source type counts (`PATH` / `FILE`)
- Execution orchestration:
  - `runQueue()` sequentially executes queued items and CSV sources
  - Maintains `queueRunning` re-entry guard
  - Persists source-level progress (`sourceCursor`, `successCount`, `failureCount`)
  - Updates optimization state for Results page continuity
  - Finalizes optimization status correctly (`completed` / `cancelled` / `error`)
  - Sends `csvPath` for path sources and multipart `file` for file sources
- Cancel helpers:
  - Uses `AbortController` for in-flight request abort
  - Best-effort server cancel notification via `cancelOptimizationRequest()`

## 3.2 Updated files

- `src/ui/static/js/ui-handlers.js`
  - `submitOptimization()` now:
    - Detects non-empty queue
    - Starts queue when idle
    - Cancels queue when running (abort + best-effort server cancel API call)

- `src/ui/static/js/main.js`
  - Added queue initialization in `DOMContentLoaded`.
  - Added listeners for:
    - `#addToQueueBtn`
    - `#clearQueueBtn`
  - Queue button handlers are async-safe (`await addToQueue`, `await clearQueue`)

- `src/ui/templates/index.html`
  - Added **Run Queue** section between **Database Target** and **Run Optimization** button.
  - Added `<script src="/static/js/queue.js"></script>` before `dataset-preview.js`.

- `src/ui/static/css/style.css`
  - Added queue section/list/item styles.
  - Added running/completed/failed/skipped visual states.
  - Added check/cross pseudo-element icons for completed/failed states.
  - Added `runOptimizationBtn` queue-active and queue-cancel button variants.

## 4. Key Logic and Reliability Decisions

## 4.1 Cancel semantics

- Queue cancel from Start page does:
  - Local abort (`AbortController.abort()`), stopping new client requests.
  - Best-effort `POST /api/optimization/cancel` notification.
- This matches Merlin's existing limitation: server-side stop is cooperative and not force-kill.

## 4.2 Queue numbering

- `nextIndex` is monotonic and preserved on clear.
- Ensures queue labels are unique and non-reused over session history.

## 4.3 Resume behavior

- Each item persists progress after every processed source.
- If queue is interrupted, rerun resumes remaining sources for the current item.
- Prevents duplicate execution of already processed CSVs.

## 4.4 Results page integration

- Queue writes state fields consistent with existing Results logic:
  - `status`, `mode`, `strategy`, `strategyId`, `study_id`, `summary`, `dataPath`, etc.
- Final state includes last successful study data to support auto-open behavior.

## 4.5 Terminal status finalization

- Queue final status is now derived from actual outcome:
  - `cancelled` if aborted at any point (including between items)
  - `completed` if at least one queue item succeeded
  - `error` if all queue items failed

## 4.6 Queue Source Modes

- Queue now supports two source modes per item:
  - `PATH`: absolute filesystem path; request payload uses `csvPath`
  - `FILE`: browser-selected file blob; request payload uses multipart `file`
- Mode selection is automatic during queue item collection.
- Legacy queue entries using `csvPaths[]` are migrated to `sources[]` on load/save.

## 4.7 Queue File Blob Lifecycle

- File-mode sources are persisted in IndexedDB by key, referenced from queue item metadata.
- On item removal/completion/clear, file blobs are cleaned up.
- On queue initialization, stale blobs are garbage-collected.
- If a blob is missing during execution, source is marked failed with explicit message; queue continues.

## 5. Validation and Reference Tests

## 5.1 JavaScript syntax checks

Command:

```powershell
node --check src/ui/static/js/queue.js
node --check src/ui/static/js/ui-handlers.js
node --check src/ui/static/js/main.js
```

Result:

- All checks passed (no syntax errors).

## 5.2 Backend regression test subset

Command:

```powershell
py -m pytest -q tests/test_sanity.py tests/test_server.py tests/test_storage.py tests/test_walkforward.py
```

Result:

- `43 passed in 1.80s`

Notes:

- This update is frontend-focused; backend tests were run to confirm no cross-impact/regression.

## 5.3 Full pytest run

Command:

```powershell
py -m pytest -q
```

Result:

- `178 passed, 2 failed, 3 warnings` (27.27s)
- Failing tests:
  - `tests/test_dsr.py::test_calculate_expected_max_sharpe_basic`
  - `tests/test_dsr.py::test_calculate_dsr_high_sharpe_track_length`
- Failure cause in logs: missing SciPy dependency (`No module named 'scipy'`), which is unrelated to queue/frontend changes.

## 6. Errors Encountered During Implementation

1. `pytest` command not available directly in shell (`pytest` not found).  
   Resolved by using Python launcher:
   - `py -m pytest ...`

2. `python -m pytest` pointed to Windows Store stub path and was not reliable in this environment.  
   Resolved by using `py` launcher explicitly.

3. Full test suite includes DSR tests that require SciPy in this environment.  
   Two DSR tests failed due missing optional dependency (`scipy`), not due queue implementation changes.

4. During final audit, one queue terminal-state edge case was found and fixed in `runQueue()`:
   - cancellation between items could leave stale `running` state
   - all-failed queue runs could incorrectly persist `completed`

5. Browser file picker does not always expose absolute paths.  
   Resolved by introducing dual source model with IndexedDB-backed file storage for queue mode.

No code-level runtime or syntax errors remained after final verification.

## 7. Remaining Known Limitations

- Server-side concurrency guard still does not exist in backend endpoints.  
  Queue remains client-sequential and safe in one tab, but concurrent runs from another tab/process remain possible (pre-existing Merlin behavior).

- File-mode queue sources require IndexedDB availability and access.
- A saved relative path string (without an attached file blob) still cannot be executed; user must reselect file.

## 8. Final Outcome

The scheduled-run queue feature is now implemented with robust cancel/re-entry handling, durable queue persistence, source-level resume, and consistent Results integration.

The update achieves the phase target while preserving existing non-queue optimization behavior.
