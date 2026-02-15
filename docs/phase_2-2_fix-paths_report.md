# Phase 2.2 - CSV Paths Fix Report

## 1. Key Problem

Merlin's current main-page flow with **"Choose files"** sends browser `File` objects to backend. In this mode backend persists uploaded bytes into:

- `C:\Users\mt\AppData\Local\Temp\merlin_uploads\upload_...csv`

Then this temporary file path is stored in DB (`studies.csv_file_path`) and reused for future study operations.

Result:

- source CSVs in the dedicated market-data directory are not referenced directly,
- temporary directory grows over time,
- path persistence behavior does not match intended workflow.

## 2. Goal of This Update

Implement a clean and simple path-first workflow for Chrome:

- one **CSV Directory** input,
- one **Choose Files** button,
- file selection via backend-powered modal browser,
- execution via absolute `csvPath` values,
- no CSV copying in normal UI flow.

Per request, DB migration of old records was intentionally not implemented in this phase.

## 3. Solution Overview

### 3.1 UI/UX Simplification

On Start page, replaced file upload control with:

- `CSV data directory` text input (default value: `C:\Users\mt\Desktop\Strategy\S_Python\Market Data_PY`)
- `Choose Files` button
- selected files list (absolute paths)

`Choose Files` opens a modal file browser (server-backed):

- current directory field
- `Up`, `Open Folder`, `Refresh`
- multi-select list (`Ctrl/Shift` behavior provided by native `<select multiple>`)
- `Add Selected`

### 3.2 Backend CSV Browser Endpoint

Added API endpoint:

- `GET /api/csv/browse?path=<absolute_or_relative_path>`

Behavior:

- resolves directory path,
- validates directory existence,
- enforces allowed roots policy,
- returns subdirectories + `.csv` files with metadata.

### 3.3 Path-First Execution Flow

Start-page execution now uses selected absolute paths only (`csvPath`), not browser `file` payloads.

Updated flows:

- backtest (`/api/backtest`)
- optimize (`/api/optimize`)
- walkforward (`/api/walkforward`)
- queue runs

### 3.4 Strict Upload Control (Compatibility-Safe)

Added config flag:

- `MERLIN_STRICT_CSV_PATH_MODE`

When enabled:

- direct CSV upload (`file`) is rejected in key endpoints,
- user must use `csvPath`.

Default is **off** in this update for backward compatibility and to avoid breaking legacy/test behavior. Path-first is still the default from updated UI.

## 4. Detailed Changes by File

### Backend

- `src/ui/server_services.py`
  - Added CSV root/allowlist helpers.
  - Added directory listing helper for browser modal.
  - Added config constants:
    - `DEFAULT_CSV_ROOT`
    - `CSV_ALLOWED_ROOTS`
    - `STRICT_CSV_PATH_MODE`
  - Added strict-mode upload rejection in `_execute_backtest_request`.

- `src/ui/server_routes_data.py`
  - Added `GET /api/csv/browse` endpoint.
  - Added strict-mode upload rejection in `POST /api/studies/<id>/update-csv-path`.

- `src/ui/server_routes_run.py`
  - Added strict-mode upload rejection in:
    - `POST /api/walkforward`
    - `POST /api/optimize`

### Frontend

- `src/ui/templates/index.html`
  - Replaced upload input block with:
    - `csvDirectory` input
    - `chooseCsvBtn`
  - Added CSV browser modal markup.

- `src/ui/static/css/style.css`
  - Added styles for:
    - directory row,
    - helper note,
    - browser modal sizing/actions,
    - browser list,
    - browser error panel.

- `src/ui/static/js/api.js`
  - Added `browseCsvDirectoryRequest(path)`.

- `src/ui/static/js/ui-handlers.js`
  - Added selected-path state helpers:
    - `normalizeSelectedCsvPaths`
    - `getSelectedCsvPaths`
    - `setSelectedCsvPaths`
  - Added modal browser logic:
    - open/close,
    - directory loading,
    - folder navigation,
    - add selected files.
  - Updated dataset labeling to path-based selections.
  - Updated backtest form building to `csvPath` only for main flow.
  - Updated optimization source collection to path objects.

- `src/ui/static/js/main.js`
  - Bound CSV browser controls on startup.
  - Bound `Choose Files` and `Enter` on directory input.
  - Removed legacy file-input change listener from start page.

- `src/ui/static/js/utils.js`
  - `renderSelectedFiles()` now supports `window.selectedCsvPaths`.

- `src/ui/static/js/queue.js`
  - Queue source collection now path-first from selected absolute paths.
  - Updated queue guidance/error text accordingly.

- `src/ui/static/js/presets.js`
  - Added `window.selectedCsvPaths` state.
  - Clears selected path state when defaults/preset clear path context.

## 5. Runtime Logic After Update

1. User sets/keeps `CSV Directory`.
2. User clicks `Choose Files`.
3. Modal calls `/api/csv/browse`, shows folders + CSVs.
4. User selects files with Ctrl/Shift and clicks `Add Selected`.
5. Start page keeps absolute path list in memory.
6. Backtest/Optimize/WFA/Queue submit `csvPath` only.
7. Backend processes direct file paths.

In default UI flow, CSV is no longer copied to `merlin_uploads`.

## 6. Safety and Compatibility Notes

- Migration script for old DB paths was intentionally not added in this phase (as requested).
- Legacy upload logic remains available behind compatibility mode (strict flag off by default).
- Existing studies are not modified.

## 7. Verification Performed

### Python compile check

- `py -m compileall src/ui/server_services.py src/ui/server_routes_data.py src/ui/server_routes_run.py`

Result: success.

### Automated tests

- `py -m pytest tests/test_server.py -q`
- `py -m pytest tests/test_db_management.py -q`
- `py -m pytest tests/test_sanity.py -q`

Result: all passed.

### Endpoint smoke check

- Called `GET /api/csv/browse` via Flask test client with
  `C:\Users\mt\Desktop\Strategy\S_Python\Market Data_PY`

Result: `200`, valid payload, directory entries returned.

## 8. What Was Explicitly Deferred

- DB migration for old `merlin_uploads` records (to be done later in a separate step).
