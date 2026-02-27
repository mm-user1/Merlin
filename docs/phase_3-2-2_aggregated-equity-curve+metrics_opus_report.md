# Phase 3-2-2 Aggregated Equity Curve + Metrics - Implementation Report

## 1. Goal and Scope

Implemented the full Phase 3-2-2 update for Analytics:

- Aggregated portfolio equity curve for multi-study selection
- Portfolio cards upgraded to curve-based metrics (`Profit`, `Ann.P%`, `MaxDD`)
- Added `Ann.P%` card to focus mode and portfolio mode (8-card layout)
- Study Sets curve metrics aligned to the same backend aggregation logic
- Robust backend API contract and validation
- Warning/subtitle UX for overlap/data-quality cases
- Full regression-safe testing for backend aggregation and API behavior

No database schema migration was required.

---

## 2. Core Design Decisions Implemented

### 2.1 Timestamp-accurate aggregation (critical fix)

Aggregation now uses full ISO datetime timestamps (UTC-aware), not date-truncated values.

This guarantees correctness for:

- portfolio curve visualization
- portfolio `profit_pct`
- portfolio `max_drawdown_pct`
- portfolio `ann_profit_pct`

### 2.2 Single source of truth for curve metrics

Curve-based aggregation is now centralized in backend `core/analytics.py`.

Both:

- main portfolio cards/chart
- Study Sets curve metrics

use backend aggregation outputs, ensuring parity.

### 2.3 Conservative performance policy

Implemented conservative, bounded performance controls:

- `study_ids` cap: **500**
- DB query chunking: **200 IDs per chunk**
- in-memory endpoint cache:
  - TTL: **10 seconds**
  - max entries: **256**

These bounds prevent oversized requests and reduce repeated aggregation cost without long-lived stale data.

---

## 3. Backend Changes

### 3.1 New module: `src/core/analytics.py`

Added reusable aggregation utilities:

- input normalization and strict validation
- timestamp parsing with UTC normalization
- duplicate timestamp dedupe (keep latest value)
- overlap detection
- union-grid forward-fill alignment
- normalization to 100 at overlap start
- equal-weight portfolio curve
- drawdown and annualized return calculation
- stable payload shape for success/warning/no-data cases

Key contract notes:

- returns structured payload (never throws for data-quality issues)
- exposes both `overlap_days` (int) and `overlap_days_exact` (float)
- suppresses annualization when overlap span `<= 30` days

### 3.2 Updated routes: `src/ui/server_routes_analytics.py`

Added endpoints:

- `POST /api/analytics/equity`
- `POST /api/analytics/equity/batch`

Implemented:

- strict JSON payload validation (explicit `400` responses)
- `study_ids` shape validation and non-empty enforcement
- cap enforcement (`<= 500`)
- WFA-only row loading
- chunked DB loading
- missing-study handling in response
- conservative per-selection cache

This resolves the prior validation failure path that could return `500` for invalid `study_ids` payload type.

---

## 4. Frontend Changes

### 4.1 API helpers (`src/ui/static/js/api.js`)

Added:

- `fetchAnalyticsEquityRequest(studyIds, signal)`
- `fetchAnalyticsEquityBatchRequest(groups, signal)`

### 4.2 Analytics controller (`src/ui/static/js/analytics.js`)

Implemented multi-study portfolio flow:

- debounced portfolio request (`300ms`)
- in-flight cancellation via `AbortController`
- stale-response guard via request token + selection key
- automatic state reset when focus/selection context changes

Chart logic:

- `0` selected: empty state
- `1` selected: individual study curve
- `2+` selected (no focus): aggregated portfolio curve
- focus mode overrides portfolio

Title/metadata:

- portfolio title: `Portfolio Equity (N studies, D days)`
- chart warning area for overlap/data warnings
- chart subtitle for `used/selected` info when studies are excluded

Summary cards:

- now 8 cards in portfolio and focus modes
- portfolio cards `Profit/Ann.P%/MaxDD` sourced from aggregation payload
- focus `Ann.P%` follows existing annualization rules (`N/A` <=30d, `*` for 31-89d)

### 4.3 Study Sets parity (`src/ui/static/js/analytics-sets.js`)

Replaced client-side curve math divergence with backend batch aggregation:

- sets request grouped metrics through `/api/analytics/equity/batch`
- `All Studies` and each set use backend `ann/profit/maxdd`
- non-curve metrics (`Profitable`, `WFE`, `OOS Wins`) remain local averages/counts

This guarantees set metrics match portfolio logic.

### 4.4 Template/CSS

Updated:

- `src/ui/templates/analytics.html`
  - added chart subtitle container
  - added chart warning container
- `src/ui/static/css/style.css`
  - warning/subtitle/title-indicator styling
  - summary card size reduction (global `.summary-card`) to support 8-card layout consistently

Per your requirement, card sizing is shared between Analytics and Results.

---

## 5. Issues Resolved (Audit Mapping)

Resolved the previously identified issues:

1. Endpoint validation path correctness
2. Intraday precision loss
3. Backend/frontend parity mismatch
4. Warning/banner/subtitle implementation completeness
5. CSS assumption mismatch and card-layout update
6. Scalability/performance safeguards (cap/chunk/cache/debounce/abort)
7. Missing critical tests (contract + endpoint behaviors)
8. Internal behavior consistency (annualization/overlap handling)

---

## 6. Tests and Verification

Interpreter used (project-required):

- `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe`

### 6.1 Syntax checks

- `python -m py_compile src/core/analytics.py src/ui/server_routes_analytics.py tests/test_analytics.py tests/test_server.py` -> OK
- `node --check src/ui/static/js/analytics.js` -> OK
- `node --check src/ui/static/js/analytics-sets.js` -> OK
- `node --check src/ui/static/js/api.js` -> OK

### 6.2 Test runs

- `pytest tests/test_analytics.py -q` -> **8 passed**
- `pytest tests/test_server.py -q` -> **39 passed**
- `pytest tests/ -q` -> **213 passed**, **3 warnings** (existing Optuna experimental warnings)

### 6.3 Note on partial-run behavior

A targeted subset run of `test_server.py` with only selected tests reproduced the existing known temporary-active-DB restoration issue (`tests_session.db` not found) when not running the full module. Full module and full suite runs pass.

---

## 7. Files Added/Modified

### Added

- `src/core/analytics.py`
- `tests/test_analytics.py`
- `docs/phase_3-2-2_aggregated-equity-curve+metrics_opus_report.md`

### Modified

- `src/ui/server_routes_analytics.py`
- `src/ui/static/js/api.js`
- `src/ui/static/js/analytics.js`
- `src/ui/static/js/analytics-sets.js`
- `src/ui/templates/analytics.html`
- `src/ui/static/css/style.css`
- `tests/test_server.py`

---

## 8. Outcome

The update is now implemented as a robust, consistent, and regression-safe solution:

- multi-study portfolio analytics are curve-correct and timestamp-accurate
- cards, chart, and sets are aligned on shared backend aggregation
- API contract is hardened against invalid payloads
- performance safeguards are bounded and conservative
- full suite remains green

