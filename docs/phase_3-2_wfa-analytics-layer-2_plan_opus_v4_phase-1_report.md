# Phase 3.2 Layer 2 Analytics (Phase 1) Implementation Report

## 1) Scope and Target
This update implements **Layer 2 Analytics - Phase 1 only** for Merlin, based on:

- `docs/phase_3-1_wfa-analytics_concept_opus_v6_ENG.md`
- `docs/phase_3-2_wfa-analytics-layer-2_plan_opus_v4.md`
- `docs/layer-2_mockup_v2_opus.html`
- `docs/layer-2_mockup_v2_opus_phase-1.html`

Implemented scope:
- New Analytics page and navigation.
- Backend summary API for WFA studies.
- Phase 1 table, selection logic, summary cards, and stitched equity chart display.
- Phase 1 robustness/test coverage.

Out of scope (kept for later phases):
- Portfolio-equity aggregation formula.
- New DB records for analytics outputs.
- Legacy-data backfill migration.

## 2) Confirmed Phase 1 Constraints Applied
The implementation follows the agreed decisions:

1. Phase 1 simplified portfolio card formulas are kept as-is.
2. Group duration uses plan formula `(end - start).days` (no +1).
3. Equity in Phase 1 uses **stitched equity from WFA results**.
4. No legacy backfill in this phase.
5. Routes are placed according to current architecture, with analytics isolated in `server_routes_analytics.py`.
6. `adaptive_mode` mapping includes fallback to `"Unknown"` for non-0/1 values.
7. CSV filename parsing remains strict (no fallback parser).
8. Equity chart behavior matches WFA Results style, without WFA window marks and without percent axis labels.

## 3) Backend Implementation
### 3.1 New routes
Added to `src/ui/server_routes_analytics.py`:

- `GET /analytics` -> renders `analytics.html`
- `GET /api/analytics/summary` -> returns Layer 2 Phase 1 summary payload

### 3.2 Summary API payload
`/api/analytics/summary` returns:

- `db_name`
- `studies[]` (WFA studies only)
- `research_info`

Study-level fields include:
- identity/context: `study_id`, `strategy`, `strategy_id`, `strategy_version`, `symbol`, `tf`, `wfa_mode`, `is_oos`
- metrics: `profit_pct`, `max_dd_pct`, `total_trades`, `winning_trades`, `wfe_pct`, `total_windows`, `profitable_windows`, `profitable_windows_pct`, `median_window_profit`, `median_window_wr`
- stitched equity: `has_equity_curve`, `equity_curve`, `equity_timestamps`

### 3.3 Backend parsing and normalization logic
Implemented robust helper logic:
- Flexible date parsing (`YYYY-MM-DD` and `YYYY.MM.DD`)
- Period-days calculation with Phase 1 formula
- Safe numeric parsing for int/float and NaN/inf handling
- JSON dict/list parsing with null/invalid guards
- Strict symbol/TF parser from `csv_file_name`
- Strategy label normalization (`s01_*` -> `S01`, plus version)
- `adaptive_mode`: `0=Fixed`, `1=Adaptive`, else `Unknown`
- OOS period display from `is_period_days` and `config_json.wfa.oos_period_days`

### 3.4 Sorting and grouping behavior
- WFA rows are sorted by:
  1. dataset start date
  2. dataset end date
  3. profit descending within period
  4. `study_id` (stable tiebreak)
- `research_info.data_periods` grouped by `(dataset_start_date, dataset_end_date)` with counts and period days.

### 3.5 Additional robustness hardening
- WFA filter made case-insensitive:
  - `LOWER(COALESCE(optimization_mode, '')) = 'wfa'`
  - This safely includes legacy/variant casing like `WFA`.

### 3.6 Route architecture refactor
To keep future Phase 2/3 and Layer 3 work maintainable, analytics routes were extracted from the large data-routes module:

- New dedicated module: `src/ui/server_routes_analytics.py`
- Existing module kept focused: `src/ui/server_routes_data.py` (analytics block removed)
- App registration updated: `src/ui/server.py` now registers
  - `register_data_routes(app)`
  - `register_analytics_routes(app)`
  - `register_run_routes(app)`

This refactor preserves all endpoint contracts and minimizes future merge/conflict risk for analytics growth.

## 4) Frontend Implementation
### 4.1 New page/template
Added `src/ui/templates/analytics.html`:
- Top navigation with Analytics tab.
- Sidebar sections: Database and Research Info.
- Main area with:
  - DB title
  - message banner
  - stitched equity chart block
  - summary cards row
  - Select All / Deselect All controls
  - summary table with header/group/row checkboxes

### 4.2 New JS modules
Added:
- `src/ui/static/js/analytics.js` (page controller/state)
- `src/ui/static/js/analytics-table.js` (grouped table + selection hierarchy)
- `src/ui/static/js/analytics-equity.js` (stitched equity chart rendering)

Implemented behaviors:
- Database switching and summary reload.
- Research info rendering.
- Grouped summary table by period.
- Tri-state checkbox logic (header/group/row).
- Selection-driven cards and chart updates.
- Chart displays selected study stitched equity.
- Empty-state handling for all UI blocks.

### 4.3 Styling updates
Updated `src/ui/static/css/style.css` with analytics-specific classes:
- DB label, message banner, selection buttons
- analytics group row styles
- analytics table scroll/empty states
- analytics row hover and striping adjustments
- analytics table-height specificity fix via `.table-scroll.analytics-table-scroll`

### 4.4 Navigation updates
Analytics tab added to:
- `src/ui/templates/index.html`
- `src/ui/templates/results.html`

## 5) Security and Reliability Improvements
During implementation, additional robustness fixes were applied:

1. Fixed mojibake placeholder rendering in analytics UI and standardized missing-value display.
2. Hardened research-info rendering via DOM `textContent` (instead of raw interpolation).
3. Escaped user/data-derived table text in `analytics-table.js`.
4. Encoded row `study_id` values in checkbox attributes and decoded on readback to avoid unsafe attribute injection edge cases.

## 6) Test Coverage Added
Updated `tests/test_server.py`:

### 6.1 Helpers
- Temporary active DB context helper for deterministic isolation.
- Study insert helper for analytics-specific fixtures.

### 6.2 New tests
1. `test_analytics_page_renders`
2. `test_analytics_summary_empty_db_returns_expected_message`
3. `test_analytics_summary_optuna_only_returns_expected_message`
4. `test_analytics_summary_wfa_phase1_contract`

Covered assertions include:
- Empty DB behavior/message.
- Optuna-only DB behavior/message.
- WFA row extraction and ordering.
- Strategy/symbol/TF parsing.
- `wfa_mode` and `is_oos` conversion rules.
- stitched equity contract (`has_equity_curve` with length check).
- research info aggregates (`strategies`, `symbols`, `timeframes`, `wfa_modes`, `is_oos_periods`, `data_periods`).

## 7) Reference Test Execution
Command used (required interpreter):

```powershell
C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests/test_server.py -q
```

Result:
- `26 passed`
- No failing tests.

Additional regression validation:

```powershell
C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q
```

Result:
- `190 passed`
- `3 warnings` (Optuna experimental warnings only, no test failures)

## 8) Problems Solved by This Update
This Phase 1 implementation now provides:
- A complete Layer 2 Analytics entry point and UI.
- A stable backend summary contract for WFA-only analytics data.
- Phase 1 summary/table/chart behavior aligned to agreed formulas and constraints.
- Deterministic test coverage for key analytics API scenarios.

## 9) Errors Encountered
No blocking implementation/runtime errors remained after fixes.

Non-blocking issues found and resolved during implementation:
- Corrupted placeholder text rendering in analytics UI.
- Unsafe interpolation surfaces in table/research info rendering.

## 10) Remaining Phase 2+ Work (Explicitly Deferred)
Not part of this phase and intentionally deferred:
- Portfolio-level stitched equity aggregation logic.
- Phase 2 formula upgrades.
- Legacy DB null backfill/migration strategy.
- Additional analytics layers beyond Phase 1 scope.
