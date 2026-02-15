# Phase 2-2-1 Report: Use Absolute CSV Paths Everywhere

## 1. Objective
Implement and enforce a consistent CSV path policy across Merlin:

1. CSV data sources must be provided as absolute filesystem paths.
2. Path access must respect configured allowed roots.
3. This policy must be applied consistently across optimization, walk-forward, backtest, OOS/Forward/Manual test flows, and WFA trade/equity exports.
4. Do **not** remove queue file-mode compatibility in this commit (postponed by request).

## 2. Starting Problem
Before this update, behavior was partially migrated to path-based usage but still inconsistent:

1. Directory browsing enforced allowed roots, but direct run-path resolution did not.
2. Strict path mode existed but defaulted to disabled.
3. Several data/trade/equity endpoints still validated CSV path presence with `Path(csv_path).exists()` only, bypassing absolute-path and allowed-root policy checks.
4. Results-page UX still included file-based inputs in some dialogs, which is not reliable in Chrome for absolute path usage.

## 3. Scope Implemented
This update includes:

1. Backend policy hardening (`server_services.py`).
2. Endpoint-wide enforcement (`server_routes_run.py`, `server_routes_data.py`).
3. Results UI migration to absolute-path inputs (`results.html`, `results-controller.js`).
4. Test-environment adaptation to preserve test reliability under stricter allowed-root checks (`tests/conftest.py`).

Excluded intentionally:

1. Queue file-mode compatibility removal (kept for a later commit).

## 4. Detailed Changes

### 4.1 Backend Core Policy (`src/ui/server_services.py`)

1. Enabled strict path mode by default:
   - `STRICT_CSV_PATH_MODE = _parse_env_bool("MERLIN_STRICT_CSV_PATH_MODE", True)` (`src/ui/server_services.py:118`).

2. Hardened `_resolve_csv_path(...)`:
   - Rejects non-absolute paths (`CSV path must be absolute.`).
   - Validates resolved file exists and is a file.
   - Enforces allowed roots via `_is_csv_path_allowed(...)`, raising `PermissionError` if out of policy.
   - References: `src/ui/server_services.py:1023`, `src/ui/server_services.py:1031`, `src/ui/server_services.py:1039`.

3. Updated backtest execution error handling to surface policy errors:
   - Added `PermissionError -> 403`.
   - Preserved meaningful bad-request messages for invalid/empty path.
   - Reference: `_execute_backtest_request(...)` (`src/ui/server_services.py:243`).

### 4.2 Run Endpoints (`src/ui/server_routes_run.py`)

1. `/api/walkforward`:
   - Continued strict-mode upload rejection.
   - Improved path-resolution error mapping for:
     - not found,
     - path points to directory,
     - out-of-allowed-roots,
     - invalid/empty path.
   - References: `src/ui/server_routes_run.py:167`, `src/ui/server_routes_run.py:202`.

2. `/api/optimize`:
   - Same policy and error handling alignment as walk-forward.
   - References: `src/ui/server_routes_run.py:655`, `src/ui/server_routes_run.py:678`.

### 4.3 Data/Trades/Equity Endpoints (`src/ui/server_routes_data.py`)

1. Added shared helper:
   - `_resolve_csv_path_for_response(...)` (`src/ui/server_routes_data.py:183`).
   - Centralizes JSON response mapping for path errors and policy violations.

2. Updated study CSV update endpoint:
   - `/api/studies/<study_id>/update-csv-path` now uses shared resolver when `csvPath` is provided.
   - Reference: `src/ui/server_routes_data.py:314`, `src/ui/server_routes_data.py:342`.

3. Updated manual test path handling:
   - `run_manual_test_endpoint(...)` now validates via resolver, not raw existence check.
   - References: `src/ui/server_routes_data.py:364`, `src/ui/server_routes_data.py:403`.

4. Replaced all legacy `Path(csv_path).exists()` checks with resolver-based validation in:
   - Optuna trial trades export,
   - Forward test trades export,
   - OOS test trades export,
   - Manual test trades export,
   - WFA window equity export,
   - WFA window trades export,
   - WFA stitched trades export.
   - References: `src/ui/server_routes_data.py:596`, `src/ui/server_routes_data.py:646`, `src/ui/server_routes_data.py:704`, `src/ui/server_routes_data.py:766`, `src/ui/server_routes_data.py:916`, `src/ui/server_routes_data.py:988`, `src/ui/server_routes_data.py:1049`.

### 4.4 Results UI Changes (`src/ui/templates/results.html`, `src/ui/static/js/results-controller.js`)

1. Missing CSV modal:
   - Removed file upload control from this flow.
   - Kept a single text input for absolute path.
   - Updated helper text to explicit absolute-path requirement.
   - References:
     - `src/ui/templates/results.html:331`,
     - `src/ui/templates/results.html:332`,
     - `src/ui/static/js/results-controller.js:958`.

2. Manual Test (`new_csv`):
   - Replaced file input with absolute-path text input (`manualDataPath`).
   - Added absolute-path client-side validation before API call.
   - References:
     - `src/ui/templates/results.html:359`,
     - `src/ui/static/js/results-controller.js:1295`,
     - `src/ui/static/js/results-controller.js:1344`,
     - `src/ui/static/js/results-controller.js:1366`.

3. Added path validator in results controller:
   - `isAbsoluteFilesystemPath(...)` (`src/ui/static/js/results-controller.js:43`).

## 5. Test Adaptation

Because policy now enforces allowed roots for resolved CSV paths, test fixtures and synthetic CSV files located under test directories can otherwise fail with `403` in CI/local test runs.

To keep tests valid while preserving production policy:

1. Added session fixture `allow_test_csv_roots` in `tests/conftest.py` (`tests/conftest.py:86`).
2. During tests only, it temporarily sets `server_services.CSV_ALLOWED_ROOTS = [Path.cwd().resolve()]`.
3. Restores original roots after test session.

This is test-only runtime wiring and does not weaken production behavior.

## 6. Verification Performed

### 6.1 Static/Syntax checks

1. `py -m compileall src/ui/server_services.py src/ui/server_routes_run.py src/ui/server_routes_data.py` -> passed.
2. `node --check src/ui/static/js/results-controller.js` -> passed.
3. `node --check src/ui/static/js/queue.js` -> passed.

### 6.2 Automated tests

1. `py -m pytest tests/test_server.py -q` -> 17 passed.
2. `py -m pytest tests/test_db_management.py -q` -> 12 passed.
3. `py -m pytest tests/test_sanity.py -q` -> 9 passed.
4. `py -m pytest tests/test_walkforward.py -q` -> 9 passed.

## 7. Final Behavior After Update

1. Absolute path is required for CSV path resolution.
2. Allowed-root policy is enforced during actual run-time path usage, not only directory browsing.
3. Strict mode now blocks direct CSV upload by default (`file` field), pushing clients toward absolute `csvPath`.
4. OOS Test, Forward Test, Manual Test, and WFA exports are all aligned to the same resolver and policy checks.
5. Queue file-mode compatibility remains present (not removed in this commit).

## 8. Files Changed in This Update

1. `src/ui/server_services.py`
2. `src/ui/server_routes_run.py`
3. `src/ui/server_routes_data.py`
4. `src/ui/templates/results.html`
5. `src/ui/static/js/results-controller.js`
6. `tests/conftest.py`

## 9. Deferred Work (Explicitly Not Included Here)

1. Removal of queue file-mode compatibility and IndexedDB file-path fallback branch from `src/ui/static/js/queue.js`.
2. Optional broader cleanup in non-main UI paths that still mention upload semantics (if needed in a future commit).
