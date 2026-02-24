# Phase 3-2-1-4 Report: Ann.P% + Study Focus Mode

Date: 2026-02-24  
Project: Merlin (`./+Merlin/+Merlin-GH/`)

## 1. Scope and Target

This update implemented two Analytics page features:

1. `Ann.P%` (Annualized Profit) column in the Summary Table.
2. Study Focus Mode with independent focus state (separate from checkbox selection), including:
   - focused-row indicator,
   - focused chart/cards behavior,
   - focus-specific Optuna/WFA sidebar settings.

The implementation also corrected plan-level issues found during audit (schema mismatches, unsafe rendering, state coupling, threshold contradictions, and lifecycle gaps).

## 2. What Was Implemented

## 2.1 Backend (`/api/analytics/summary`)

Updated `src/ui/server_routes_analytics.py`:

- Added robust parsing helpers and settings extraction for each WFA study:
  - `optuna_settings`
  - `wfa_settings`
- Added schema fallbacks from both:
  - `config_json` payload, and
  - normalized study columns.
- Implemented tri-state adaptive parsing:
  - `true` -> `On`
  - `false` -> `Off`
  - missing/unknown -> `null` (frontend renders `-`).
- Added safe/fallback extraction for:
  - objectives, primary objective, constraints,
  - budget mode and budget params,
  - sampler type,
  - pruning/sanitize/filter fields,
  - WFA adaptive and adaptive-only parameters.
- Normalized objectives/constraints via array-safe parsing to avoid malformed legacy payload coercion.
- Added adaptive-mode fallback for `wfa_mode` label itself, so legacy rows with missing column values are still classified from `config_json` when possible.

No new endpoint was added.

## 2.2 Frontend: Ann.P% Column

Updated:

- `src/ui/templates/analytics.html`
- `src/ui/static/js/analytics-table.js`
- `src/ui/static/js/analytics.js`

Implemented:

- New sortable `Ann.P%` column inserted before `Profit%`.
- Derived annualization metrics in `analytics-table.js`:
  - `ann_profit_pct` (sortable numeric value),
  - `_oos_span_days` (for tooltip/warning logic).
- Annualization formula applied on stitched OOS timestamps.
- Final threshold policy (as agreed):
  - `<= 30 days` -> `N/A`
  - `31-89 days` -> value + `*` + warning tooltip
  - `>= 90 days` -> normal display
- `N/A` naturally sorts to bottom through existing null-safe numeric sort.
- Updated table colspans for new column count.

## 2.3 Frontend: Focus Mode

Updated:

- `src/ui/static/js/analytics.js`
- `src/ui/static/js/analytics-table.js`
- `src/ui/templates/analytics.html`
- `src/ui/static/css/style.css`

Implemented:

- New `focusedStudyId` state in analytics page state.
- Callback-based module wiring (no cross-module global coupling):
  - table emits focus-toggle via callback,
  - page orchestrator owns focus state/actions.
- Alt+click on row toggles focus.
- Esc clears focus.
- Focus row visual marker via `.analytics-focused`.
- Focus behavior is independent of checkbox selection.
- Focus lifecycle robustness:
  - focus cleared automatically if focused row becomes hidden by filters,
  - focus reset on summary reload/database switch.
- Chart behavior:
  - focus mode prioritizes focused study chart,
  - safe title rendering (DOM/text nodes, no unsafe HTML interpolation),
  - dismiss button in title (`x`) exits focus.
- Cards behavior:
  - aggregate mode unchanged,
  - focus mode uses single-study WFA-style labels/values.
- Sidebar behavior:
  - added hidden Optuna/WFA sections in Analytics sidebar,
  - shown only when focus is active,
  - rendered from `optuna_settings` / `wfa_settings`,
  - adaptive-only WFA fields shown only when adaptive is `true`,
  - `adaptive_mode: null` rendered as `-`.
  - `0` values are preserved as visible values (not collapsed to missing placeholder).

## 3. Plan Issues Resolved

The implementation explicitly resolved the audited plan discrepancies:

1. Fixed cross-module focus coupling by using callback-based table/page contract.
2. Fixed sort-key consistency (`ann_profit_pct` is actual sortable field).
3. Removed unsafe `innerHTML` chart-title strategy and used safe DOM composition.
4. Fixed sampler source mismatch with current saved schema (`sampler`, `sampler_type`, optional sampler_config fallback).
5. Added focus lifecycle handling for hidden rows and DB reload paths.
6. Resolved annualization threshold contradiction with agreed boundary (`<=30` -> `N/A`).
7. Corrected table colspans for new column count.
8. Preserved tri-state adaptive semantics (`null` not coerced to `Off`).
9. Added robust fallbacks for sparse/legacy `config_json`.
10. Aligned focus card behavior and formatting with existing Results WFA card style.

## 4. Tests and Validation

Updated tests:

- `tests/test_server.py`
  - added `test_analytics_summary_includes_focus_settings_payload`
  - validates:
    - new payload keys,
    - config vs column fallback behavior,
    - tri-state adaptive (`None` preserved),
    - key Optuna/WFA field mapping correctness.

Executed reference tests:

- Command:
  - `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests/test_server.py -q`
- Result:
  - `28 passed`

Full regression suite:

- Command:
  - `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests -q`
- Result:
  - `192 passed`
  - `3 warnings` (existing Optuna experimental warning for `multivariate`; no failures)

Notes:

- A narrow `-k` subset run can hit a pre-existing test harness quirk around restoring `tests_session.db` when no prior DB is created in-session; full `tests/test_server.py` run passes cleanly.

## 5. Files Changed

- `src/ui/server_routes_analytics.py`
- `src/ui/templates/analytics.html`
- `src/ui/static/js/analytics-table.js`
- `src/ui/static/js/analytics.js`
- `src/ui/static/css/style.css`
- `tests/test_server.py`
- `docs/phase_3-2-1-4_ann-p+focus-mode_opus_report.md`

## 6. Outcome

The update now fully implements Ann.P% and Focus Mode with robust backend/frontend contracts, safer rendering, correct state ownership, and regression-covered API behavior.
