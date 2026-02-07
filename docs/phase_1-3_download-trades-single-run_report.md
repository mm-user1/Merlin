# Phase 1-3 Report: Backtester "Trades" Single-Run Download

## Purpose

Replace the Backtester left-panel `Cancel` button with a `Trades` action that performs:

1. Backtest run (same output behavior as `Run`)
2. Trades CSV download for the same strategy/parameters/data selection

Requirements addressed:

- Refactor to avoid duplicated backend backtest logic
- Reuse existing export pipeline (`core/export.py`)
- Preserve all existing Results-page "Download Trades" variants without behavior changes
- Keep implementation concise, robust, and consistent

## Scope

Modified files:

1. `src/ui/server_services.py`
2. `src/ui/server_routes_run.py`
3. `src/ui/static/js/api.js`
4. `src/ui/static/js/ui-handlers.js`
5. `src/ui/static/js/main.js`
6. `src/ui/templates/index.html`

No changes were made to Results-page trade-download endpoints/controllers.

## Implementation

### Phase 1: Backend Refactor (remove duplicated backtest execution path)

Added shared helper in `src/ui/server_services.py`:

- `_parse_warmup_bars(...)`
- `_execute_backtest_request(strategy_id)`

`_execute_backtest_request(...)` centralizes the full single-backtest flow:

1. Parse warmup
2. Resolve input CSV from file upload or saved path
3. Parse/validate payload JSON
4. Load strategy
5. Load dataset
6. Apply date alignment + warmup window
7. Validate strategy parameters
8. Execute `strategy.run(...)`

It returns a normalized result payload (including `result`, `payload`, `csv_name`) or a `(message, status)` error tuple.

### Phase 2: New Backtester Trades Endpoint

Updated `src/ui/server_routes_run.py`:

- `/api/backtest` now delegates execution to `_execute_backtest_request(...)` (same JSON output contract as before).
- Added new endpoint:
  - `POST /api/backtest/trades`
  - Reuses the same execution helper
  - Exports CSV using existing `_send_trades_csv(...)`, which internally uses `export_trades_csv(...)` from `core/export.py`
  - Generates filename:
    - `backtest_{strategy}_{source}_trades.csv`

This preserves existing export formatting and symbol extraction logic, while avoiding duplicated backtest execution code in routes.

### Phase 3: UI Behavior Change (`Cancel` -> `Trades`)

Updated `src/ui/templates/index.html`:

- Replaced button:
  - from `id="cancelBtn"` / label `Cancel`
  - to `id="tradesBtn"` / label `Trades`

Updated `src/ui/static/js/main.js`:

- Removed reset/default binding for old cancel button
- Added click binding for `tradesBtn` -> `runBacktestAndDownloadTrades`

Updated `src/ui/static/js/ui-handlers.js`:

- Refactored Backtester run flow into reusable logic:
  - `buildBacktestRequestFormData(...)`
  - `triggerDownloadFromResponse(...)`
  - `executeBacktestRun({ downloadTrades })`
- `runBacktest(...)` now delegates to `executeBacktestRun({ downloadTrades: false })`
- Added `runBacktestAndDownloadTrades(...)` using `executeBacktestRun({ downloadTrades: true })`
- `Trades` behavior:
  - runs normal backtest request (`/api/backtest`) and renders results
  - then requests CSV download (`/api/backtest/trades`) for the same payload

Updated `src/ui/static/js/api.js`:

- Added `downloadBacktestTradesRequest(formData)` for `POST /api/backtest/trades`

## Compatibility and Non-Regression

### Existing Results-page "Download Trades" variants

No functional changes were made to:

- `src/ui/server_routes_data.py` trade-download endpoints
- `src/ui/static/js/results-controller.js` download flow

All previous variants remain routed and handled exactly as before.

### Export consistency

CSV generation still uses `core/export.py` (`export_trades_csv`) through existing server helper path.

## Validation Performed

### 1) Python syntax check

Command:

- `py -3 -m py_compile src/ui/server_services.py src/ui/server_routes_run.py`

Result:

- Passed

### 2) Targeted regression tests

Command:

- `py -3 -m pytest tests/test_server.py tests/test_export.py -q`

Result:

- `17 passed`

This includes server route tests and export tests, covering existing download-related server behavior.

### 3) Full suite check (required venv interpreter)

Command:

- `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q`

Observed:

- `154 passed`, `3 warnings`

Assessment:

- Full suite passed in the project-required environment.
- Server/download flows relevant to this update are green in both targeted and full-suite runs.

### 4) Manual endpoint smoke verification

Executed a Flask test-client script that:

1. Posts to `POST /api/backtest` with generated OHLCV CSV and strategy defaults
2. Posts to `POST /api/backtest/trades` with the same payload

Observed:

- `/api/backtest` returned `200` with metrics payload
- `/api/backtest/trades` returned `200`, `text/csv`, valid `Content-Disposition`, and expected CSV header:
  - `Symbol,Side,Qty,Fill Price,Closing Time`

## Result

Implemented update successfully:

- Backtester now has `Trades` button in place of `Cancel`
- `Trades` performs backtest + trades download for current Backtester selection
- Backend logic was refactored to a shared execution path, reducing duplication
- Export behavior remains based on existing `export.py` path
- Existing Results-page trade-download variants remain unchanged and validated via targeted tests
