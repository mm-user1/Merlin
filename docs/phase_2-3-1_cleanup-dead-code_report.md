# Phase 2-3-1 Cleanup Report: Dead/Duplicate Code Removal

Date: 2026-01-16
Scope: Merlin codebase at `+Merlin/+Merlin-GH/`

## Summary
Performed the three planned cleanup steps to remove dead code, eliminate duplicate date-alignment logic, and consolidate UTC timestamp parsing. Changes are purely refactors; no intended behavioral changes. Emphasis: consistency and clarity.

---

## Step 1: Remove dead code
### Removed
- `src/core/optuna_engine.py::_parse_timestamp`

### Why
- It was **unused** after date alignment was centralized.
- `rg` confirmed only the function definition existed; no call sites.

### Effect
- Eliminates dead code and reduces confusion around which parser is canonical.

---

## Step 2: Remove duplicate alignment helper in WFA export
### Replaced
- Local helper `_align_window_ts()` inside `download_wfa_trades()` (server)

### With
- `align_date_bounds(df.index, start_raw, end_raw)` from `core/backtest_engine.py`

### Why
- `_align_window_ts()` duplicated the same logic now centralized in `align_date_bounds()`.
- Keeps one canonical alignment implementation across the codebase.

### Effect
- No behavior change; eliminates duplicated logic.

---

## Step 3: Consolidate UTC parsing into a shared helper
### Added / Promoted
- `parse_timestamp_utc()` in `src/core/backtest_engine.py`
  - Previously `_parse_timestamp_utc`, now public and reused.

### Removed
- `src/core/post_process.py::_parse_timestamp`

### Updated call sites
- `post_process.calculate_is_period_days()` now calls `parse_timestamp_utc()`.
- `src/ui/server.py` now uses `parse_timestamp_utc()` instead of `_parse_pp_timestamp`.

### Why
- Removes duplicate parser implementations.
- Ensures one UTC parser is used everywhere.

### Effect
- No functional change; purely consolidation.

---

## Files Modified
- `src/core/backtest_engine.py`
  - `_parse_timestamp_utc` renamed to `parse_timestamp_utc`
  - `align_date_bounds()` updated to use the new name

- `src/core/optuna_engine.py`
  - removed unused `_parse_timestamp`

- `src/core/post_process.py`
  - removed `_parse_timestamp`
  - `calculate_is_period_days()` now uses `parse_timestamp_utc`

- `src/ui/server.py`
  - removed `_align_window_ts()`
  - replaced WFA export alignment with `align_date_bounds()`
  - replaced `_parse_pp_timestamp` usage with `parse_timestamp_utc`

---

## Verification / Safety Checks
- `rg` confirms no remaining usage of `_parse_pp_timestamp`, `_align_window_ts`, or the removed `_parse_timestamp`.
- Strategy-local `_parse_timestamp` in `s04_stochrsi` remains intentionally (not part of global alignment).

Tests were not run as part of this cleanup (refactor-only). If you want, we can run:
- Optuna run with date-only range
- WFA export
- Manual Test + FT export

---

## Behavior Impact
- Intended: **No behavioral change**.
- Alignment and parsing logic remain the same; only duplicated helpers removed.

---

End of report.
