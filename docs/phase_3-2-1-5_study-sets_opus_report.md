# Phase 3-2-1-5 Study Sets - Implementation Report

## 1. Update Goal

Implemented the Study Sets update for Analytics with persistent DB-backed sets, set-based visibility modes, metric comparison panel, robust state transitions, and full backend/frontend integration.

Primary priorities were reliability, consistency, and alignment with current Merlin architecture.

## 2. Implemented Scope

### 2.1 Backend (Storage + API)

- Added Study Sets schema and lifecycle support in [src/core/storage.py](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/core/storage.py):
  - `ensure_study_sets_tables(...)`
  - `list_study_sets(...)`
  - `create_study_set(...)`
  - `update_study_set(...)`
  - `delete_study_set(...)`
  - `reorder_study_sets(...)`
- Added robust schema details:
  - `study_sets`
  - `study_set_members`
  - case-insensitive unique index for set names (`LOWER(name)`)
  - FKs with cascade:
    - `set_id -> study_sets(id) ON DELETE CASCADE`
    - `study_id -> studies(study_id) ON DELETE CASCADE`
- Added legacy orphan cleanup query for safety during ensure/init.
- Added validation:
  - set name required + max length guard
  - `study_ids` must be array-like
  - `reorder` must contain all set IDs exactly once
  - set membership restricted to existing **WFA** studies only

- Added Analytics Set API endpoints in [src/ui/server_routes_analytics.py](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/server_routes_analytics.py):
  - `GET /api/analytics/sets`
  - `POST /api/analytics/sets`
  - `PUT /api/analytics/sets/<id>`
  - `DELETE /api/analytics/sets/<id>`
  - `PUT /api/analytics/sets/reorder`

- Added API client helpers in [src/ui/static/js/api.js](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/js/api.js):
  - `fetchAnalyticsSetsRequest`
  - `createAnalyticsSetRequest`
  - `updateAnalyticsSetRequest`
  - `deleteAnalyticsSetRequest`
  - `reorderAnalyticsSetsRequest`

### 2.2 Frontend (Analytics UI + State Machine)

- Added new module [src/ui/static/js/analytics-sets.js](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/js/analytics-sets.js) with:
  - Study Sets table rendering
  - All Studies baseline row
  - set checkbox selection (click/shift/ctrl)
  - set focus (alt+click)
  - CRUD actions (save/rename/delete/update focused set)
  - move mode (keyboard-driven reorder)
  - expand/collapse rows (5 vs 10 viewport behavior)
  - collapsible panel logic and summary label
  - per-set metrics computation

- Updated Analytics template in [src/ui/templates/analytics.html](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/templates/analytics.html):
  - inserted Study Sets section between Summary Cards and selection/filter controls
  - added script include for `analytics-sets.js`

- Added Study Sets styles in [src/ui/static/css/style.css](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/css/style.css):
  - panel layout
  - table styling
  - focused row indicator
  - move mode highlighting
  - action row
  - expand toggle integration

- Extended [src/ui/static/js/analytics-table.js](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/js/analytics-table.js):
  - new `visibleStudyIds` option in `renderTable(...)`
  - set-layer visibility + filter-layer visibility composition
  - exported `computeAnnualizedProfitMetrics` for shared Ann.P% calculation

- Updated [src/ui/static/js/analytics-filters.js](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/js/analytics-filters.js):
  - `updateStudies(studies, { emitChange })`
  - silent contextual updates to avoid accidental rerender loops/reset churn

- Updated [src/ui/static/js/analytics.js](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/js/analytics.js):
  - integrated `AnalyticsSets` lifecycle
  - set-driven visibility passed to `AnalyticsTable`
  - contextual filter option recalculation from set-visible subset
  - set-state synchronization (`focusedSetId`, `checkedSetIds`, view mode)
  - Esc priority chain:
    1) clear study focus
    2) cancel set move mode
    3) clear set focus with fallback behavior

## 3. Resolved Design Issues

All key issues from the audit were addressed:

1. **Select All behavior mismatch**
- Kept current Merlin behavior intentionally: `Select All` checks all rows (including hidden).
- Set-subset workflow now relies on explicit selected rows and set/update actions consistent with this behavior.

2. **Ann.P% source mismatch**
- Set metrics now use the same annualization logic path as analytics table (`computeAnnualizedProfitMetrics` export), matching current architecture without backend payload changes.

3. **Orphan membership policy**
- Replaced brittle “keep orphan IDs” approach with FK cascade + cleanup.
- Deleting a study automatically removes set membership references.

4. **Filter reset/render churn risk**
- Introduced silent contextual filter updates (`emitChange: false`).
- Analytics orchestrator now updates context and state deterministically before table render.

5. **Move mode Esc contradiction**
- Final behavior implemented:
  - `Enter` = save reorder
  - `Esc` = cancel reorder and restore original order
  - no auto-save on Esc

6. **State transition inconsistency**
- Implemented deterministic mode handling with explicit All Studies override support.
- Supports “All Studies mode with checked sets retained” behavior.

7. **All Studies semantics**
- All Studies row implemented as **all WFA studies in active DB** on Analytics.

8. **Module routing correctness**
- Implementation uses existing modular backend routes (`server_routes_analytics.py`), no unnecessary route wiring changes in `server.py`.

## 4. Robustness/Future-Proofing Decisions

- DB-level referential integrity for set members.
- Case-insensitive uniqueness for set names at DB level.
- Strong API validation and explicit bad-request responses.
- Reorder endpoint enforces complete, unambiguous ordering.
- Frontend state orchestration is centralized in `analytics.js` with explicit sync points.
- Shared annualization logic avoids metric drift between tables.

## 5. Tests Added/Updated

### Updated tests

- [tests/test_server.py](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/tests/test_server.py)
  - CRUD + reorder API flow
  - non-WFA membership rejection
  - member cascade behavior after study delete
  - reorder validation (must include all IDs exactly once)

- [tests/test_storage.py](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/tests/test_storage.py)
  - Study Sets tables existence
  - storage-layer roundtrip (create/update/reorder/list)

## 6. Validation Results

Executed with project-required interpreter:
`C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe`

- `pytest tests/test_server.py -q` -> **32 passed**
- `pytest tests/test_storage.py -q` -> **11 passed**
- `pytest tests/ -q` -> **198 passed**, 3 warnings (existing Optuna experimental warnings)
- `python -m py_compile src/core/storage.py src/ui/server_routes_analytics.py` -> **OK**
- `node --check` on changed JS files -> **OK**

## 7. Errors/Incidents During Implementation

- Running only a narrow subset of `test_server.py` in isolation can fail due pre-existing test fixture assumptions about active DB restoration (`tests_session.db` not yet created).  
  - This is an existing test-environment characteristic, not introduced by this update.
  - Full suite and full `test_server.py` run pass successfully.

## 8. Outcome

Study Sets are now fully implemented end-to-end with robust persistence, deterministic UX/state behavior, validated APIs, and full regression stability across Merlin tests.

## 9. Post-Implementation Corrections (Follow-up Fix Pass)

After user validation, additional UX/behavior fixes were implemented:

1. **Move button no-op fixed**
- Root cause: move mode was enabled during click, then immediately cancelled by document-level outside-click handling after DOM rerender.
- Fix in [src/ui/static/js/analytics-sets.js](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/js/analytics-sets.js):
  - replaced move-mode outside cancel listener from `click` to `pointerdown`
  - robust inside/outside detection (`contains` + `composedPath`)
  - preserves required behavior:
    - `Enter` = save reorder
    - `Esc` = cancel reorder
    - no auto-save on cancel

2. **Added non-focus `Update Set ▾` dropdown**
- Added header-level update control for non-focused mode:
  - [src/ui/templates/analytics.html](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/templates/analytics.html)
  - [src/ui/static/css/style.css](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/css/style.css)
  - [src/ui/static/js/analytics-sets.js](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/js/analytics-sets.js)
- Behavior:
  - shown only when no set is focused, sets exist, and studies are checked
  - dropdown lists all sets
  - selecting target performs **replace-members update** with current checked studies only
  - no `Add to Set` mode introduced

3. **Study Sets table readability improved**
- Increased Study Sets table font from `12px` to `13px` in [src/ui/static/css/style.css](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/css/style.css).

4. **Contextual filter churn mitigation**
- Improved context update stability:
  - `analytics.js`: added filter-context signature/epoch gating so contextual options are recomputed only when set-context actually changes
  - `analytics-filters.js`: `updateStudies(...)` now skips unnecessary rerenders when options/filters are unchanged
- Result: fewer redundant rerenders and fewer unintended contextual resets.

5. **API surface alignment**
- Added `setFocusedSetId(...)` to `window.AnalyticsSets` export for consistency with documented module contract.

## 10. Follow-up Validation

Executed after follow-up fixes with required interpreter:
`C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe`

- `pytest tests/test_server.py -q` -> **32 passed**
- `pytest tests/test_storage.py -q` -> **11 passed**
- `pytest tests/ -q` -> **198 passed**, 3 warnings (existing Optuna experimental warnings)
- `node --check src/ui/static/js/analytics-sets.js` -> **OK**
- `node --check src/ui/static/js/analytics.js` -> **OK**
- `node --check src/ui/static/js/analytics-filters.js` -> **OK**

## 11. UX Consistency Update (Header Update Control Unification)

Implemented additional UX consistency improvements requested after follow-up pass:

1. **Single Update control in header**
- Removed bottom action-row button `Update "Set Name"` from focused-set actions.
- Header control is now the single source of truth for set updates.

2. **Header Update control behavior**
- When a set is focused:
  - header button label = `Update Current Set`
  - click updates focused set with current checked studies only (replace members)
- When no set is focused:
  - header button label = `Update Set ▾`
  - click opens set dropdown; selected set is updated with current checked studies only
- Button is visible whenever sets exist and is disabled when:
  - no checked studies, or
  - move mode is active

3. **Sets table typography parity**
- Increased Study Sets table font from `13px` to `14px` to match Summary Table readability.

### Files updated for this UX consistency pass

- [src/ui/static/js/analytics-sets.js](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/js/analytics-sets.js)
- [src/ui/static/css/style.css](/c:/Users/mt/Desktop/Strategy/S_Python/+Merlin/+Merlin-GH/src/ui/static/css/style.css)

### Validation (post UX consistency pass)

- `node --check src/ui/static/js/analytics-sets.js` -> **OK**
- `pytest tests/test_server.py tests/test_storage.py -q` -> **43 passed**
- `pytest tests/ -q` -> **198 passed**, 3 warnings (existing Optuna experimental warnings)
