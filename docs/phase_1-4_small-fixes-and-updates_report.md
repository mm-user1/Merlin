# Phase 1-4 Small Fixes and Updates Report

Date: 2026-02-11
Project: Merlin (`+Merlin/+Merlin-GH`)

## Scope
This report documents the successful updates completed in this session.

Excluded by request:
- The unsuccessful attempt to resize the filter input field under the `Filter` button is intentionally not included.

---

## Executive Summary
Four targeted updates were completed to improve reliability and operator workflow:

1. Database creation flow was made explicit to prevent accidental creation of a new DB per CSV during multi-source runs.
2. Results-page study sorting was added as an optional mode (`Sort Name`) and integrated with existing filtering behavior.
3. Studies Manager filter-row alignment was adjusted to keep controls visually aligned with the button row.
4. Forward Test `Top Candidates` default was standardized to `10` across UI and backend FT fallback paths.

The implementation focused on minimal, clear logic changes with defensive validation, and no schema changes.

---

## Phase 1: Database Target Reliability Fix

### Problem
When `Database Target` was set to `Create new DB`, multi-CSV optimization/WFA created a new DB for each CSV source, because creation was triggered per run request.

### Root Cause
`dbTarget == "new"` was handled inside run endpoints (`/api/optimize`, `/api/walkforward`) and therefore executed once per source submission.

### Solution
Creation was converted from an implicit run-time side effect to an explicit user action:

- Added a dedicated confirmation button in Start page `Database Target` section:
  - `src/ui/templates/index.html` (`dbCreateBtn`)
- Added frontend handler to create and immediately select the newly created DB:
  - `src/ui/static/js/main.js` (`createAndSelectDatabase`)
- Added frontend pre-run guard to block optimize/WFA if `Create new DB` is still selected and no explicit creation was performed:
  - `src/ui/static/js/ui-handlers.js` (`getDatabaseTargetValidationError`)
- Added backend guard to reject `dbTarget="new"` in run endpoints with a clear 400 error (defense in depth):
  - `src/ui/server_routes_run.py` (`_apply_db_target_from_form`)

### Why this design
- Prevents accidental DB fan-out in multi-source runs.
- Keeps the workflow simple and explicit.
- Ensures safety even if frontend behavior is bypassed.

### Verification
Added/used regression test:
- `tests/test_db_management.py::test_optimize_rejects_new_db_target_without_explicit_create`

This test verifies:
- request is rejected with `400` for `dbTarget="new"`
- active DB remains unchanged
- no new DB file is created as a side effect

---

## Phase 2: Optional Results Sorting (`Sort Name`) Integrated with Filter

### Problem
Studies were displayed in DB insertion order, making side-by-side comparison of related instruments/timeframes difficult.

### Solution
Added optional sort mode in Studies Manager:

- Added `Sort Name` button inside filter row:
  - `src/ui/templates/results.html`
- Added sort state and sorting pipeline:
  - `src/ui/static/js/results-controller.js`
  - `studiesSortByNameActive`
  - `parseTimeframeToMinutes`
  - `extractStudySortIdentity`
  - `compareStudiesByTickerAndTimeframe`
  - `getStudiesForRender`

### Sorting logic
To avoid grouping by strategy prefix (`S01`, `S03`) first, sorting is based on dataset identity:
1. ticker
2. timeframe (normalized to minutes where possible)
3. study name (stable tie-break)

This directly targets the operational use case: compare runs of the same ticker/TF together.

### Filter integration behavior
- Sort works together with filter (filter applies to sorted list).
- Sort button is active only while `Filter` mode is enabled.
- Turning `Filter` off also clears filter text and disables sorting state.

### Why this design
- Minimal UI surface area (single optional button).
- Preserves current workflow.
- Deterministic ordering for cross-run comparison.

### Notes
No backend or DB schema changes were required for this feature.

---

## Phase 3: Studies Manager Control Alignment

### Goal
Align the filter-row controls so that:
- `Sort Name` appears under `Select`
- filter input appears under `Filter`

### Implemented change
Used grid positioning in sidebar filter row:
- `src/ui/static/css/style.css`
  - `manager-filter-row` uses 3-column grid
  - `manager-filter-sort-btn` fixed to column 1
  - `manager-filter-input` fixed to column 2

### Why this design
- Predictable placement with minimal CSS.
- No impact on interaction logic.

---

## Phase 4: Forward Test Default Top Candidates = 10

### Requirement
Set Forward Test default `Top Candidates` from `20` to `10` everywhere relevant to FT.

### Updated locations
1. Start-page UI default value:
- `src/ui/templates/index.html`
  - `#ftTopK` value changed `20 -> 10`

2. Frontend FT config normalization fallback:
- `src/ui/static/js/post-process-ui.js`
  - `topK: normalizeInt(..., 20, ...) -> normalizeInt(..., 10, ...)`

3. Frontend fallback config when `PostProcessUI` is unavailable:
- `src/ui/static/js/ui-handlers.js`
  - fallback `topK: 20 -> 10`

4. Backend FT fallback values (including WFA/Optuna paths):
- `src/ui/server_routes_run.py`
  - WFA post-process config: `get("topK", 5) -> get("topK", 10)`
  - optimize config: `get("topK", 20) -> get("topK", 10)`
  - FT execution config: `get("topK", 20) -> get("topK", 10)`
  - FT result persistence: `get("topK", 20) -> get("topK", 10)`

### Safety note
Only FT defaults were changed.
- DSR defaults were not changed.
- OOS defaults were not changed.

---

## Validation and Test Execution

Python interpreter used:
- `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe`

Executed tests during this session:

1. `python.exe -m pytest tests/test_db_management.py -q`
- Result: `12 passed`

2. `python.exe -m pytest tests/test_server.py -q`
- Result: `17 passed`

3. `python.exe -m pytest tests/test_server.py tests/test_db_management.py tests/test_walkforward.py -q`
- Result: `38 passed`

---

## Risk Assessment

### Low-risk areas
- Changes are localized to UI event handling, sorting/render orchestration, and default fallback values.
- No DB schema migrations.
- Existing endpoint contracts preserved, except intentional rejection of implicit `dbTarget="new"` during run requests.

### Behavioral impact (intentional)
- Users must explicitly create/select a DB before running optimization/WFA when `Create new DB` is chosen.
- Results list can now be optionally sorted for analysis workflows.
- FT default candidate count is now `10` instead of `20`.

---

## Final Outcome
The requested small fixes and updates were implemented with defensive guards, minimal complexity, and verified test coverage in impacted backend paths.
