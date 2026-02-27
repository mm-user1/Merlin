# Phase 3-2-2-1 Small Fixes and Updates - Report

## Changelog

### 2026-02-27 - Entry 1 - Analytics small fixes + robust parity alignment

**Target**

- Align Analytics cards ordering with Summary/Study Sets logic: `Ann.P%` first, `Profit` second.
- Add missing Analytics focused-sidebar settings parity with Results page.
- Keep implementation reliable and regression-safe.

**Implemented**

- Updated Analytics summary cards order in all relevant rendering paths:
- Focus mode cards now start with `ANN.P%`, then `NET PROFIT`.
- Portfolio empty-state cards now start with `Portfolio Ann.P%`, then `Portfolio Profit`.
- Portfolio populated cards now start with `Portfolio Ann.P%`, then `Portfolio Profit`.
- Added missing Optuna rows in Analytics focused sidebar:
- `Sanitize Trades`
- `Filter`
- Added missing WFA rows in Analytics focused sidebar:
- `Check Interval` (adaptive mode rows block)
- `WFA Run Time`
- Added shared formatting helpers in Analytics for robust parity behavior:
- `formatDuration`
- `formatSanitizeLabel`
- `formatFilterLabel`
- `computeRunTimeSeconds`

**Backend contract extensions for parity**

- Extended `/api/analytics/summary` payload source fields:
- `optimization_time_seconds`
- `score_config_json`
- Added output fields:
- `optuna_settings.score_filter_enabled`
- `optuna_settings.score_min_threshold`
- `wfa_settings.run_time_seconds`
- Added safe runtime fallback in backend:
- If `optimization_time_seconds` is absent, runtime is derived from `completed_at_epoch - created_at_epoch` when possible.

**Problems solved**

- Card order inconsistency between Analytics cards and Analytics tables/sets.
- Missing Analytics focused-sidebar settings compared to Results page.
- Incomplete backend contract for full filter/runtime parity.
- Reduced future drift by introducing explicit formatter helpers in Analytics.

**Reference tests and verification**

- `py -3 -m pytest tests/test_server.py` -> `39 passed`
- `py -3 -m pytest tests/test_analytics.py` -> `8 passed`
- Added/updated assertions in `tests/test_server.py` for:
- `wfa_settings.run_time_seconds`
- `optuna_settings.score_filter_enabled`
- `optuna_settings.score_min_threshold`
- runtime fallback from timestamps path
- runtime explicit value path

**Errors encountered**

- `pytest` command was not available directly in shell (`CommandNotFoundException`).
- Resolved by using `py -3 -m pytest`.
- A targeted subset run of two tests produced an existing temporary DB restoration issue (`Database 'tests_session.db' not found`) during teardown.
- Resolved by running the full `tests/test_server.py` module; full module passed.

**Files modified**

- `src/ui/static/js/analytics.js`
- `src/ui/server_routes_analytics.py`
- `tests/test_server.py`

---

### 2026-02-27 - Entry 2 - Post-implementation analysis note (no code change)

**Observation**

- Analytics `Pruner` display logic currently hides pruner when `enable_pruning` is false.
- Results page displays pruner text regardless of `enable_pruning`.
- This can show `Pruner: -` in Analytics while Results shows `median` for the same study.

**Status**

- Identified and explained to user.
- Fix postponed by user ("later, not now").
- No code changes were made for this item in this session.

---

### 2026-02-28 - Entry 3 - Remove blue highlight from profit metric cards (Results + Analytics)

**Target**

- Remove the light-blue highlighted background/border from the profit metric card so it visually matches other metric cards:
- white background
- gray border
- same card style as non-highlight metrics

**Implemented**

- Removed `highlight` class usage from profit cards in all relevant render paths:
- Analytics focused cards: `NET PROFIT`
- Analytics portfolio empty-state cards: `Portfolio Profit`
- Analytics portfolio populated cards: `Portfolio Profit`
- Results summary cards: `NET PROFIT`
- Kept CSS `.summary-card.highlight` rule unchanged for future optional use elsewhere.

**Why this approach**

- Targeted and safe: only the specific profit cards changed.
- Avoids global CSS side effects.
- Preserves ability to use `highlight` for other UI elements in future updates.

**Problems solved**

- Profit card visual inconsistency with the rest of metric cards on both pages.
- Removes unintended emphasis styling where neutral card style is required.

**Reference checks and tests**

- JS syntax checks:
- `node --check src/ui/static/js/analytics.js` -> OK
- `node --check src/ui/static/js/results-tables.js` -> OK
- Regression tests:
- `py -3 -m pytest tests/test_server.py` -> `39 passed`

**Errors encountered**

- None during implementation of this fix.

**Files modified**

- `src/ui/static/js/analytics.js`
- `src/ui/static/js/results-tables.js`

---

### 2026-02-28 - Entry 4 - Analytics focused-study chart now shows WFA window markers

**Target**

- Add WFA window boundary markers (`W1`, `W2`, ...) to Analytics stitched equity chart **only** in focused-study mode.
- Keep aggregated/multi-study views unchanged (no markers in portfolio or set-aggregated modes).
- Match Results-page marker semantics while keeping Analytics architecture lightweight and race-safe.

**Implemented**

- Added backend endpoint:
- `GET /api/analytics/studies/<study_id>/window-boundaries`
- Returns ordered window boundaries for WFA study from `wfa_windows`, with safe fallback boundary time priority:
- `oos_start_ts` -> `oos_start_date` -> `is_end_ts` -> `is_end_date`
- Non-WFA studies are rejected with `400`, missing studies return `404`.

- Added frontend API helper:
- `fetchAnalyticsStudyWindowBoundariesRequest(studyId, signal)` in `api.js`.

- Extended Analytics page state and flow:
- Added focused-boundary cache by `study_id`.
- Added AbortController + request-token guards for boundary fetches.
- Added normalization of boundary payload (`time`, `window_number`, `label`) before use.
- Focused-study chart now requests/caches boundaries and renders markers.
- Non-focused modes explicitly render without markers.

- Extended Analytics chart renderer:
- `analytics-equity.js` now accepts optional chart options with `windowBoundaries`.
- Draws vertical dashed boundary lines and W-labels on the chart using timestamp alignment.
- Preserves existing behavior when boundaries are not provided.

**Why this approach**

- Keeps marker logic scoped to focused single-study mode as requested.
- Avoids heavy study-detail payloads by using a dedicated lightweight endpoint.
- Prevents race conditions when changing focused rows quickly.
- Future-proof: marker data retrieval is explicit and reusable.

**Problems solved**

- Analytics focused-study chart lacked WFA window boundaries compared to Results.
- Inconsistent single-study diagnostic visibility between Results and Analytics pages.
- Potential stale async UI updates prevented via request-token + abort guards.

**Reference checks and tests**

- JS syntax checks:
- `node --check src/ui/static/js/api.js` -> OK
- `node --check src/ui/static/js/analytics.js` -> OK
- `node --check src/ui/static/js/analytics-equity.js` -> OK

- Backend regression:
- `py -3 -m pytest tests/test_server.py` -> `42 passed`
- `py -3 -m pytest tests/test_analytics.py` -> `8 passed`

- New tests added for the new endpoint:
- success payload ordering + fallback boundary-time selection
- reject non-WFA study (`400`)
- missing study (`404`)

**Errors encountered**

- None during this fix implementation.

**Files modified**

- `src/ui/server_routes_analytics.py`
- `src/ui/static/js/api.js`
- `src/ui/static/js/analytics.js`
- `src/ui/static/js/analytics-equity.js`
- `tests/test_server.py`

---

### 2026-02-28 - Entry 5 - Fix WFA Fixed-mode Results header showing `OOS days = 0`

**Target**

- Eliminate incorrect `0d` display in Results WFA window headers for Fixed-mode studies.
- Preserve adaptive-mode suffix behavior (`(Xd)` + trigger badge) where adaptive metadata exists.

**Implemented**

- Updated `wfa-results-ui.js` header rendering logic for window rows:
- Added strict nullable/empty guard before numeric conversion of `oos_actual_days`.
- Prevented JavaScript coercion path where `Number(null) === 0` incorrectly produced `0d`.
- Added adaptive-context gating:
- Show adaptive suffix only when study adaptive mode is `true`.
- Backward-compatible fallback: if adaptive mode is unknown (`null`) and adaptive metadata exists, still show suffix.

**Why this approach**

- Fixes the direct root cause with minimal surface area (UI-only change).
- Avoids changing backend WFA storage/serialization semantics.
- Keeps adaptive metadata visible for legacy/partial payloads while ensuring fixed mode stays clean.

**Problems solved**

- Fixed-mode WFA headers no longer display false `0d` OOS duration.
- Adaptive suffix remains correctly scoped to adaptive window metadata.

**Reference checks and tests**

- JS syntax check:
- `node --check src/ui/static/js/wfa-results-ui.js` -> OK
- Backend contract regression:
- `py -3 -m pytest tests/test_server.py::test_get_wfa_window_details` -> passed
- Added assertion coverage to ensure fixed-mode window payload preserves:
- `oos_actual_days is None`
- `trigger_type is None`

**Errors encountered**

- None during this fix implementation.

**Files modified**

- `src/ui/static/js/wfa-results-ui.js`
- `tests/test_server.py`

---

### 2026-02-28 - Entry 6 - Analytics Study Sets duplicate-name auto-resolution (`(1)`, `(2)`, ...)

**Target**

- Preserve current lightweight Save Set flow while resolving duplicate set names automatically.
- Match Merlin standard duplicate-name behavior:
- first duplicate -> `Name (1)`
- next duplicate -> `Name (2)`
- and so on.
- Avoid prompt re-open loops and avoid extra modal/UX complexity.

**Implemented**

- Updated backend Study Set creation logic in `create_study_set`:
- when insert hits unique-name constraint (`LOWER(name)`), retries with suffixed name candidates.
- suffix sequence is deterministic and incremental: `base`, `base (1)`, `base (2)`, ...
- includes length-safe suffixing (keeps generated names within 120-char policy).
- added bounded retry guard (`max_attempts = 1000`) to prevent unbounded loops.

**Why this approach**

- Robustness: server-side solution guarantees consistent behavior for all clients, not only current Analytics UI.
- Simplicity: no need for extra modal state or prompt-loop logic in frontend.
- Race-safe: uniqueness remains enforced by DB index; retries handle contention correctly.

**Problems solved**

- Saving a set with an already existing name no longer fails with a duplicate-name error.
- User flow stays uninterrupted with current prompt-based UI.

**Reference checks and tests**

- Added API-level regression test:
- `test_analytics_sets_create_auto_suffixes_duplicate_names`
- validates `Duplicate Set`, `Duplicate Set (1)`, `Duplicate Set (2)` creation order and names.

- Test runs:
- `py -3 -m pytest tests/test_server.py` -> `43 passed`
- `py -3 -m pytest tests/test_analytics.py` -> `8 passed`

**Errors encountered**

- Isolated single-test run hit existing DB teardown issue in this environment:
- `ValueError: Database 'tests_session.db' not found`
- Full module run (`tests/test_server.py`) completed successfully and includes the new test passing.

**Files modified**

- `src/core/storage.py`
- `tests/test_server.py`
