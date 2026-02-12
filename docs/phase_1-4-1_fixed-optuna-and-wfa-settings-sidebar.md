# Phase 1-4-1 Report: Fixed Optuna/WFA Settings Sidebar State in Results

## Scope
This report documents the latest fix for incorrect values shown in the `Optuna Settings` and `WFA Settings` sidebars on the `Results` page.

The update targets one core issue:
- stale sidebar values leaking from the previously opened study into the currently opened study, especially visible in `WFA` mode.

It also includes finalized follow-up UI/storage refinements for `Results`:
- `WFA Settings` expanded by default.
- Adaptive-only rows hidden for fixed WFA.
- New `WFA Run Time` row in `WFA Settings`, backed by persisted runtime.

No DB backfill/migration was introduced for historical rows.

---

## Problem Summary

### User-visible symptoms
- `Optuna Settings` looked correct in many `OPT` studies, but not consistently for `WFA`.
- In `WFA` studies, sidebar values could show data from a previously opened study.
- Missing values in older studies were not shown as missing (`-`); instead, old values persisted in UI memory.

### Why this was dangerous
- Incorrect context while reviewing a study.
- Risk of making analytical decisions on wrong settings.
- Confusing behavior when switching between studies and modes.

---

## Root Causes

### 1) State carry-over in frontend payload application
In `results-controller.js`, `applyStudyPayload(...)` used fallbacks to previous `ResultsState` values for multiple sidebar fields.

This meant:
- if current study did not have a field, UI reused previous study’s value.
- stale values propagated across studies.

### 2) Incomplete WFA metadata persistence for new records
When saving WFA studies, important optimization metadata was not written into `studies` columns (many fields were inserted as `None`), which increased chances of missing values during load/render.

### 3) Adaptive mode rendering did not support explicit “unknown”
`wfa-adaptive-mode` used boolean conversion directly, which forced `null`/missing into `Off` instead of showing missing state.

---

## Design Goals for the Fix
- Stop stale value propagation completely.
- Preserve behavior for already existing DBs.
- Improve metadata persistence for new WFA studies.
- Keep code minimal, readable, and localized.
- Avoid schema migration and avoid backfill (as requested).

---

## What Was Changed

## 1) Frontend: remove stale fallbacks when opening a study
File:
- `src/ui/static/js/results-controller.js`

### Main logic change
`ResultsState.wfa` and `ResultsState.optuna` are now rebuilt from the current study payload/config only.

### Key details
- Removed fallback patterns like:
  - `... ?? ResultsState.wfa.<field> ?? ...`
  - `... || ResultsState.optuna.<field>`
- Replaced with:
  - current study fields, current `config_json` fields, or `null`/safe defaults.

### Result
- Opening a study now shows only that study’s data.
- If field is missing in DB/config, UI sees it as missing, not inherited from prior study.

---

## 2) Frontend: adaptive mode can now show missing (`-`)
File:
- `src/ui/static/js/results-tables.js`

### Main logic change
- Replaced forced boolean rendering:
  - old behavior: `Boolean(value)` => `On/Off`
- New behavior:
  - `null/undefined` => `-`
  - truthy => `On`
  - falsy => `Off`

### Result
- Sidebar no longer reports fake `Off` when adaptive mode data is absent.

---

## 3) WFA run config persistence: include `optuna_config` in saved config JSON
File:
- `src/ui/server_routes_run.py`

### Main logic change
- Added:
  - `base_template["optuna_config"] = ...`
- This ensures WFA study `config_json` contains full optimization metadata used to generate the study.

### Result
- New WFA studies have richer self-contained config payload.
- Sidebar can reliably resolve Optuna settings from the same study record.

---

## 4) Storage: persist WFA study metadata into `studies` columns
File:
- `src/core/storage.py` (`save_wfa_study_to_db`)

### Main logic changes
- Added extraction of:
  - `optuna_config` and `wfa` sections from incoming config.
- Persisted previously missing fields into `studies` row for WFA:
  - `is_period_days`
  - `sampler_type`
  - `population_size`
  - `crossover_prob`
  - `mutation_prob`
  - `swapping_prob`
  - `budget_mode`
  - `n_trials`
  - `time_limit`
  - `convergence_patience`
- Kept existing adaptive/WFA trigger fields persistence:
  - `adaptive_mode`, `max_oos_period_days`, `min_oos_trades`, `check_interval_trades`,
  - `cusum_threshold`, `dd_threshold_multiplier`, `inactivity_multiplier`.

### Result
- New WFA study rows are significantly more complete.
- Sidebar data resolution becomes deterministic and less dependent on optional fallbacks.

---

## 5) Tests: added coverage for new WFA metadata persistence
File:
- `tests/test_storage.py`

### Added test
- `test_save_wfa_study_persists_optuna_and_wfa_metadata`

### What it validates
- WFA `studies` row stores all newly persisted fields.
- `config_json` still contains expected nested blocks (`optuna_config`, `wfa`).

### Result
- Prevents silent regression for future storage changes.

---

## 6) UI behavior: `WFA Settings` is expanded by default
File:
- `src/ui/templates/results.html`

### Main logic change
- The `WFA Settings` collapsible now includes `open` by default.

### Result
- The section is immediately visible when a WFA study is opened, matching the intended UX.

---

## 7) UI behavior: hide adaptive-only rows for fixed WFA
Files:
- `src/ui/templates/results.html`
- `src/ui/static/js/results-tables.js`

### Main logic change
- Adaptive-only rows now have dedicated row IDs:
  - `wfa-max-oos-row`
  - `wfa-min-trades-row`
  - `wfa-check-interval-row`
  - `wfa-cusum-row`
  - `wfa-dd-mult-row`
  - `wfa-inactivity-row`
- Added helper visibility logic in sidebar rendering:
  - show rows only when `Adaptive = On`
  - hide rows when `Adaptive = Off` (fixed WFA)

### Result
- Fixed WFA no longer shows parameters that belong only to adaptive mode.
- Sidebar content is cleaner and semantically correct.

---

## 8) New sidebar metric: `WFA Run Time`
Files:
- `src/core/storage.py`
- `src/ui/static/js/results-controller.js`
- `src/ui/static/js/results-tables.js`
- `src/ui/templates/results.html`
- `tests/test_storage.py`

### Main logic change
- Added runtime calculation for WFA save path (`save_wfa_study_to_db`) using existing `start_time`.
- Persisted this value into existing `studies.optimization_time_seconds` for WFA rows.
- Added `runTimeSeconds` into `ResultsState.wfa`.
- Added new row in `WFA Settings`:
  - label: `WFA Run Time`
  - value: formatted duration from `runTimeSeconds`, or `-` if unavailable.

### Result
- Sidebar now shows meaningful end-to-end WFA runtime without schema migration.
- Old studies remain valid and show `-` when runtime is missing.

---

## Behavior: Before vs After

### Before
- Sidebar fields could survive from prior study if current study missed some values.
- WFA sidebar could look inconsistent and misleading.
- Adaptive mode could incorrectly show `Off` when value was actually unknown/missing.
- WFA records had incomplete metadata in DB columns.

### After
- Sidebar strictly reflects currently opened study.
- Missing values are shown as missing (`-`) instead of stale inherited data.
- Adaptive mode uses explicit tri-state display (`On` / `Off` / `-`).
- New WFA studies persist richer metadata; loading/rendering is stable.
- `WFA Settings` is open by default.
- Adaptive-only rows are shown only for adaptive WFA.
- `WFA Run Time` is available for newly saved WFA studies.

---

## Compatibility and Migration

### Existing DBs
- Fully compatible.
- No schema change, no migration, no backfill.

### Old study rows
- If a field does not exist in old data, UI now shows `-` or safe default.
- This is intentional and correct (better than displaying stale foreign values).
- For `WFA Run Time`, legacy rows without persisted runtime show `-`.

### New study rows
- Gain richer metadata persistence automatically from this version onward.
- Persist `WFA Run Time` into `optimization_time_seconds`.

---

## Validation Performed
- Test command:
  - `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests/test_storage.py tests/test_server.py tests/test_walkforward.py -q`
- Result:
  - `34 passed`

This confirms no regressions in covered storage/server/walkforward flows and validates new persistence behavior.

---

## Why This Solution Is Reliable
- Removes the direct mechanism that caused stale values (state fallback to previous study).
- Improves source-of-truth completeness for newly created WFA records.
- Keeps old data readable without unsafe assumptions.
- Adds automated regression protection in storage tests.

---

## Final Outcome
The `Results` sidebars (`Optuna Settings`, `WFA Settings`) now behave consistently and predictably:
- no cross-study leakage,
- no hidden stale values,
- correct missing-data representation,
- improved WFA metadata persistence for all newly saved studies,
- clearer WFA UX for fixed vs adaptive parameters,
- explicit end-to-end `WFA Run Time` visibility in sidebar.
