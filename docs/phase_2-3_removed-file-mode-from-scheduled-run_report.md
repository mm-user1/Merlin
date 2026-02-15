# Phase 2-3 Report: Removed File-Mode from Scheduled Run Queue

## 1. Objective
Implement an absolute-path-only CSV workflow across Merlin scheduled runs and aligned run endpoints, with focus on:

1. Removing queue file-mode compatibility (`FILE` source type + IndexedDB blob storage).
2. Using absolute filesystem `csvPath` everywhere for scheduled run execution.
3. Eliminating stale/unreachable file-upload branches in UI and backend run entrypoints.
4. Keeping behavior reliable, consistent, and simpler to maintain.
5. Making queue label numbering UX predictable by resetting visible `#N` numbering when queue is empty.

## 2. Problem Solved
Before this update, code still contained legacy dual-mode handling:

1. Queue supported both `PATH` and `FILE` sources, including IndexedDB file blob persistence.
2. Main UI run code still contained `File` object branches that were no longer used by the current page flow.
3. Backend run endpoints still accepted multipart `file` upload branches (behind strict-mode semantics), creating unnecessary complexity and policy ambiguity.
4. Some stale references remained for a removed `csvFile` input on the main page.
5. Queue `nextIndex` label counter was monotonic even after queue became empty, causing confusing labels like `#100`/`#1000` for a fresh queue.

This created avoidable complexity and made the absolute-path policy harder to reason about.

## 3. Implemented Scope
### 3.1 Queue Simplification (`src/ui/static/js/queue.js`)
Implemented path-only queue model:

1. Removed file-mode and IndexedDB branches:
   - Removed file DB constants/state.
   - Removed blob persistence/load/delete utilities.
   - Removed stale-file cleanup flow.
2. Removed queue file source metadata:
   - Removed `fileKey`, `_file`, `type: 'file'` handling.
3. Queue item source normalization now accepts only absolute paths:
   - `normalizeQueueSource(...)` now keeps only absolute paths and drops invalid/legacy non-absolute entries.
4. Queue execution now always sends `csvPath`:
   - Removed `file` append branch from run payload.
5. Queue add/remove/clear no longer performs file-key storage cleanup operations.
6. Tooltip/source summary updated to path-only wording.
7. Added queue label counter reset logic when queue is empty:
   - New helper `computeQueueNextIndex(...)` centralizes `nextIndex` normalization.
   - `loadQueue(...)` and `saveQueue(...)` now force `nextIndex = 1` when `items.length === 0`.
   - If items remain in queue, numbering continuity is preserved.

Net effect: scheduled queue is now strictly path-driven and significantly smaller.

### 3.2 Main UI Run Flow Cleanup (`src/ui/static/js/ui-handlers.js`)
Removed stale `File` branches and hardened validation:

1. Added `isAbsoluteFilesystemPath(...)` helper.
2. Walk-forward loop:
   - Removed `File` object handling.
   - Added absolute-path validation per source before request.
   - Always appends `csvPath`.
3. Optimization loop:
   - Removed `File` object handling.
   - Added pre-check for invalid selected path(s).
   - Added per-source absolute-path validation before request.
   - Always appends `csvPath`.
4. Backtest run:
   - Added absolute-path validation for primary source.
   - Updated error text to match path-only behavior.

### 3.3 Preset Cleanup (`src/ui/static/js/presets.js`)
Removed stale main-page file-input references:

1. Removed `csvFile` DOM lookup/reset logic.
2. Simplified selected-files render call to use path-based state only.

### 3.4 Backend Absolute-Path Enforcement (`src/ui/server_routes_run.py`, `src/ui/server_routes_data.py`, `src/ui/server_services.py`)
Aligned server entrypoints to path-only behavior:

1. `/api/walkforward` (`server_routes_run.py`):
   - Removed upload branch.
   - `csvPath` is now mandatory.
2. `/api/optimize` (`server_routes_run.py`):
   - Removed upload branch.
   - `csvPath` is now mandatory.
3. Study CSV update endpoint (`/api/studies/<id>/update-csv-path`, `server_routes_data.py`):
   - Removed upload branch.
   - `csvPath` only; uses shared resolver with explicit `csvPath is required.` message.
4. Backtest execution resolver (`_execute_backtest_request` in `server_services.py`):
   - Removed upload branch.
   - `csvPath` only.
5. Removed now-unused upload helper `_persist_csv_upload(...)` and related imports from `server_services.py`.
6. Kept exported `STRICT_CSV_PATH_MODE` flag as constant `True` for API metadata compatibility (`strict_path_mode` response field), but runtime now enforces path-only behavior directly.

## 4. Key Logic and Targets
This update targets reliability and consistency by enforcing a single data-source contract:

1. UI selection source: absolute file paths from directory browser.
2. Queue storage format: only `{ type: "path", path: "<absolute>" }`.
3. API run payload: only `csvPath` for backtest/optimize/walk-forward and study CSV-path updates.
4. Resolver policy: absolute path + file existence + allowed roots.
5. Queue label numbering policy:
   - Empty queue => `nextIndex = 1`.
   - Non-empty queue => preserve monotonic continuity for pending items.

Migration behavior:

1. Legacy queue records with invalid/non-absolute/old file-mode source data are safely ignored during normalization.
2. No hard crash occurs when old localStorage entries exist; invalid items are dropped.
3. Legacy oversized `nextIndex` values are auto-normalized to `1` as soon as stored queue items are empty.

## 5. Files Changed
1. `src/ui/static/js/queue.js`
2. `src/ui/static/js/ui-handlers.js`
3. `src/ui/static/js/presets.js`
4. `src/ui/server_routes_run.py`
5. `src/ui/server_routes_data.py`
6. `src/ui/server_services.py`

Diff summary:

1. 6 files changed
2. 121 insertions
3. 471 deletions

## 6. Verification and Reference Tests
### 6.1 JavaScript syntax checks
1. `node --check src/ui/static/js/queue.js` -> passed
2. `node --check src/ui/static/js/ui-handlers.js` -> passed
3. `node --check src/ui/static/js/presets.js` -> passed

### 6.2 Full Python test suite
Command used:

`C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q`

Result:

1. `180 passed`
2. `3 warnings` (Optuna experimental warning, pre-existing/non-blocking)
3. No failures

### 6.3 Follow-up Validation (Queue Numbering Reset)
After adding `nextIndex` reset-on-empty logic in `queue.js`:

1. `node --check src/ui/static/js/queue.js` -> passed
2. `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q` -> `180 passed`, `3 warnings`, `0 failed`

## 7. Errors Encountered During Implementation
1. No runtime or test failures after code changes.
2. No functional regressions detected by automated tests.

## 8. Final Outcome
The update fully removes scheduled-run file-mode compatibility and enforces a single absolute-path workflow for CSV sources across queue and run entrypoints. The implementation is materially simpler, clearer, and consistent with the target policy.

The system is now ready to operate in absolute-path-only mode without legacy queue file-mode branches, and queue label numbering now restarts at `#1` whenever queue is truly empty.
