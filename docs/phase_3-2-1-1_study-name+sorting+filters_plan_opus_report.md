# Phase 3-2-1-1 Study Name + Sorting + Filters - Implementation Report

## 1) Scope Implemented
This update implements the requested Layer 2 extension from:

- `docs/phase_3-2-1-1_study-name+sorting+filters_plan_opus.md`

Implemented features:
- Study Name column (replacing Symbol + TF in table view).
- Column sorting with 3-click cycle.
- Multi-select filters (Strategy, Symbol, TF, WFA, IS/OOS).
- Active filters strip with per-filter clear and global clear.
- Auto-select mode (filters drive selection when enabled).
- Deterministic date-added metadata in API for robust default sorting.

Explicitly excluded (per confirmed scope):
- Label filter and PASS/MAYBE/FAIL logic.
- Select PASS Only button behavior.
- Portfolio equity aggregation changes (chart remains selected-study stitched curve).

## 2) Backend Changes
### File
- `src/ui/server_routes_analytics.py`

### Changes
`GET /api/analytics/summary` was extended to include study identity/time metadata required by frontend sorting and naming logic:

- Added selected columns:
  - `study_name`
  - `created_at`
  - `completed_at`
  - `created_at_epoch` (`strftime('%s', created_at)`)
  - `completed_at_epoch` (`strftime('%s', completed_at)`)

- Added response fields per study:
  - `study_name`
  - `created_at`
  - `completed_at`
  - `created_at_epoch`
  - `completed_at_epoch`

This enables deterministic frontend default order:
1. `created_at` (preferred),
2. fallback `completed_at`,
3. final stable fallback `study_id`.

No endpoint additions were required.
No DB schema changes were required.

## 3) Frontend Template Changes
### File
- `src/ui/templates/analytics.html`

### Changes
- Added Study Name header and removed Symbol/TF visible columns.
- Added sortable header markup (data-sort-key + arrow placeholders) for:
  - Study Name, Profit%, MaxDD%, Trades, WFE%, OOS Wins, OOS P(med), OOS WR(med)
- Updated subtitle default text:
  - `Sorted by date added (newest first)`
- Added Auto-select checkbox near selection buttons.
- Added filters section:
  - `#analyticsFiltersBar`
  - `#analyticsActiveFilters`
- Included new script:
  - `/static/js/analytics-filters.js`

## 4) Frontend Logic Changes
### 4.1 New Filters Module
#### File
- `src/ui/static/js/analytics-filters.js`

#### Implemented behavior
- 5 dropdown filters:
  - Strategy, Symbol, TF, WFA, IS/OOS
- Value sources auto-populated from loaded studies.
- Supports:
  - normal multi-select,
  - Ctrl+Click exclusive mode,
  - "cannot leave empty" safety (reverts to All),
  - All checkbox auto-sync.
- Dropdown button shows active selected count (`Name (N)`).
- Active filters strip:
  - one tag per active filter,
  - per-tag clear,
  - global Clear All.
- TF options sorted by natural timeframe order.
- WFA options sorted by semantic order (`Fixed`, `Adaptive`, `Unknown`).

### 4.2 Table Module Refactor
#### File
- `src/ui/static/js/analytics-table.js`

#### Core additions
- Study Name display builder with robust staged transformation:
  - handles counter suffix `(... )`,
  - removes `_WFA` / `_OPT`,
  - removes date range suffix,
  - strips `S##_` prefix when present,
  - normalizes numeric TF tokens,
  - falls back to `symbol + tf` if needed.

- Deterministic default sort model:
  - rows default: `created_at` desc -> `completed_at` desc -> `study_id` asc
  - groups default: by newest member row using same default comparator.

- Active column sort model:
  - sort only within groups,
  - group order remains default newest-group-first.

- 3-click sort cycle implemented:
  - click 1: best direction,
  - click 2: reverse,
  - click 3: reset to default date-added sort.

- Visible-only selection hierarchy logic:
  - header checkbox applies to visible rows only,
  - group checkbox applies to visible rows in group only,
  - hidden rows unaffected by header/group toggles.

- Filtered visibility behavior:
  - non-matching study rows hidden (`display:none`),
  - group row hidden if all child rows hidden.

- Row numbering:
  - renumbered for visible rows only.

- Auto-select integration:
  - when enabled: selection becomes exactly visible rows on each filter/table render.
  - when disabled: filter changes do not mutate selection.

### 4.3 Page Controller Integration
#### File
- `src/ui/static/js/analytics.js`

#### Changes
- Added state for:
  - filters,
  - autoSelect,
  - sortState.
- Integrated new modules:
  - `AnalyticsFilters` for filter state/UI.
  - `AnalyticsTable` options for sort/filter/auto-select.
- Subtitle now reflects sort state dynamically:
  - default: date-added message,
  - active: `Sorted by <Column> ▲/▼`.
- Preserved chart behavior exactly as required:
  - selected-study stitched equity (no portfolio-aggregation logic added).

## 5) Styling Changes
### File
- `src/ui/static/css/style.css`

### Added styles
- Auto-select control layout/styling.
- Filters bar and dropdown menus.
- Active filter tags and clear controls.
- Sortable header active/hover arrow behavior.
- Selection row layout updates for controls + auto-select.

## 6) Problem Cases Addressed
1. API lacked fields needed for robust "date added" sorting and study-name rendering.
2. Previous table default order was profit/date based, not insertion chronology.
3. Filter interactions were previously absent.
4. Checkbox hierarchy needed explicit visible-only behavior under filtering.
5. Needed deterministic tie behavior for future-proof sorting correctness.

## 7) Test Updates
### File
- `tests/test_server.py`

### Added/updated
- Analytics insert helper made flexible for timestamp fields.
- New API test:
  - `test_analytics_summary_includes_study_name_and_timestamps`
  - validates:
    - `study_name` presence,
    - `created_at`/`completed_at` pass-through,
    - epoch fields,
    - null-created fallback shape.

## 8) Validation Results
### Command 1
```powershell
C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests/test_server.py -q
```
Result:
- `27 passed`

### Command 2
```powershell
C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q
```
Result:
- `191 passed`
- `3 warnings` (Optuna experimental warnings only; no failures)

## 9) Errors Encountered During Implementation
One test initially failed because SQLite auto-defaulted `created_at` for rows where it was omitted.  
Resolution: explicitly set `created_at = NULL` in that targeted test row to verify null fallback behavior.

No remaining test failures.

## 10) Future-Proofing Notes
This update keeps analytics logic modular and deterministic for upcoming phases:
- sorting fallback chain is explicit and stable,
- study-name rendering has staged parsing + fallback,
- filter state is isolated in a dedicated module,
- table rendering cleanly separates ordering and visibility logic.

Deferred by design to later phases:
- Label/PASS filtering and selection actions,
- portfolio-equity aggregation chart behavior.

