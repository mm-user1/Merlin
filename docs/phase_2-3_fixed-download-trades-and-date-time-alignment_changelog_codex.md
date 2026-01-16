# Phase 2-3 Report: Fixed Download Trades + Date/Time Alignment

Date: 2026-01-16
Scope: Merlin codebase at `+Merlin/+Merlin-GH/`

## Summary
This session focused on two core areas:
1) **Trade export reliability** (Download Trades for Optuna, WFA, FT, Manual Test).
2) **Consistent date-only alignment** across all modules (to prevent end-day truncation).

The work was carried out in multiple steps. Below is a comprehensive, ordered changelog with motivations, exact functions touched, and the reasoning behind each change.

---

## 1) UI text adjustments (Post Process panel)
**Files**
- `src/ui/templates/index.html`
- `src/ui/static/js/post-process-ui.js`

**Changes**
- Renamed label text:
  - “Top Candidates for DSR:” > “Top Candidates:”
  - “Forward Test Period (days):” > “Test Period (days):”
- Removed Stress Test note text: “Test parameter robustness by applying small perturbations (sensitivity analysis).”
- Fixed DSR input alignment by ensuring `#dsrSettings` uses flex layout when shown.

**Why**
- Requested UI text cleanup and consistency.
- DSR input had a different gap because the settings container was toggled to `display: block`, overriding the `.form-group` flex styling. Switching to `display: flex` preserves consistent spacing.

**Functions/sections edited**
- Inline labels in `index.html`.
- `syncPostProcessUI()` in `post-process-ui.js`:
  - `dsrSettings.style.display = ...` changed to `flex` when visible.

---

## 2) Added FT/Manual trade download endpoints + UI routing
**Files**
- `src/ui/server.py`
- `src/ui/static/js/results.js`

**Changes**
- **New endpoints**:
  - `POST /api/studies/<study_id>/trials/<trial_number>/ft-trades`
  - `POST /api/studies/<study_id>/tests/<test_id>/trials/<trial_number>/mt-trades`
- **Updated Download Trades button routing**:
  - WFA > `/wfa/trades` (unchanged)
  - Forward Test tab > `/ft-trades`
  - Manual Tests tab > `/mt-trades`
  - DSR/Stress/Optuna tabs > Optuna `/trials/<trial>/trades`

**Why**
- Previously Download Trades only worked for Optuna and WFA.
- FT and Manual Test had no endpoints and no UI routing.
- Required for robust, consistent export across all result tabs.

**Functions/sections edited**
- `download_trial_trades()` updated to use new helper export flow.
- Added:
  - `download_forward_test_trades()`
  - `download_manual_test_trades()`
- `results.js` download button handler updated to route by active tab.

---

## 3) Centralized trade export flow for consistency
**File**
- `src/ui/server.py`

**Changes**
Added helpers to keep all export paths consistent and concise:
- `_run_trade_export(...)`:
  - Loads strategy and data.
  - Applies date filter + warmup.
  - Executes strategy and returns trades.
- `_send_trades_csv(...)`:
  - Builds symbol from CSV filename.
  - Uses `export_trades_csv` and returns `send_file` response.

**Why**
- Avoid code duplication for Optuna/FT/Manual export endpoints.
- Ensure same alignment + warmup behavior across all export paths.

**Functions added**
- `_run_trade_export`
- `_send_trades_csv`

---

## 4) Manual Test export validation
**File**
- `src/ui/server.py`

**Changes**
- In `download_manual_test_trades()`, added validation that the requested `trial_number` exists in `manual_tests.trials_tested_csv`.

**Why**
- Prevent exporting trades for trials that were not part of the manual test results table.

**Functions edited**
- `download_manual_test_trades()`

---

## 5) Fix symbol in export for uploaded CSV paths
**File**
- `src/ui/server.py`

**Problem observed**
- When a CSV path is a temp upload (`merlin_uploads/upload_...`), the symbol in CSV export became `upload:...`.

**Fix**
- `_send_trades_csv(...)` now:
  - If the path is a temp upload, uses the study’s original CSV filename for symbol extraction.
  - Otherwise uses the actual CSV path basename.

**Why**
- Restore correct symbol format (e.g., `OKX:LINKUSDT.P`).

---

## 6) Default dates in Manual Test modal
**File**
- `src/ui/templates/results.html`

**Changes**
- Set default values:
  - Start: `2025-06-15`
  - End: `2025-11-15`

**Why**
- Requested fixed defaults for quicker manual test setup.

---

## 7) Root cause: end-day truncation for date-only ranges
**Observed issue**
- FT downloads sometimes had more trades than UI counts.
- Cause: date-only end values (e.g., `2025-09-15`) were parsed as midnight (`00:00:00`), excluding the rest of the end day.

**Conclusion**
- This behavior existed across multiple modules, not just FT/MT.
- WFA export already aligned date-only ends to last bar of the day. FT/MT did not.

---

## 8) Global fix: unified date-only alignment across Merlin
**Core change**
A unified alignment helper was added and adopted across core + server logic:

**New helper**
- `align_date_bounds(index, start_raw, end_raw)` in `src/core/backtest_engine.py`:
  - Parses timestamps in UTC.
  - If date-only, aligns:
    - start > first bar on/after date
    - end > last bar on date

**Why**
- This makes date-only ranges behave consistently everywhere and removes the long-standing “last day trimmed” bug.

**Modules updated to use align_date_bounds**
1. `src/core/optuna_engine.py`
   - `_prepare_data_and_strategy()` now aligns date-only bounds before trimming.

2. `src/core/post_process.py`
   - FT worker (`_ft_worker_entry`) aligns start/end against df index.
   - DSR re-run uses aligned bounds.
   - Stress Test IS backtest uses aligned bounds.

3. `src/core/walkforward_engine.py`
   - WFA overall trading range now aligns to bar boundaries for date-only values.

4. `src/ui/server.py`
   - Backtest endpoint (`/api/backtest`) uses aligned bounds.
   - Manual Test endpoint aligns bounds after loading CSV.
   - WFA data filtering (server-side) uses aligned bounds.
   - Trade export helpers use aligned bounds.

**Why this is correct**
- Aligns with WFA export behavior.
- Prevents end-day data loss for all date-only ranges.
- Keeps exact timestamps unchanged if time component is provided.

---

## 9) Behavioral changes & compatibility
**What changes for users**
- Date-only end dates now include the full end day in all modules.
- Old studies computed before this fix may show mismatches vs new exports.

**Compatibility note**
- Stored metrics in DB (Optuna/FT/DSR/Stress/Manual/WFA) remain unchanged for existing studies.
- To fully sync UI metrics with new exports, those studies/tests should be re-run.

---

## Files Modified (complete list)
- `src/ui/templates/index.html`
- `src/ui/static/js/post-process-ui.js`
- `src/ui/templates/results.html`
- `src/ui/static/js/results.js`
- `src/ui/server.py`
- `src/core/backtest_engine.py`
- `src/core/optuna_engine.py`
- `src/core/post_process.py`
- `src/core/walkforward_engine.py`

---

## Key Functions Added / Updated
**Added**
- `align_date_bounds(index, start_raw, end_raw)` in `backtest_engine.py`.

**Updated**
- `OptimizationEngine._prepare_data_and_strategy()` (date alignment)
- `post_process._ft_worker_entry()` (FT alignment)
- `run_dsr_analysis()` (DSR alignment)
- `_run_is_backtest()` (Stress Test alignment)
- `WalkForwardEngine.run_wf_optimization()` (WFA alignment)
- `run_backtest()` endpoint alignment
- `run_manual_test_endpoint()` alignment
- Trade export endpoints for FT/MT

---

## Why this resolves the old alignment bug
Previously, any date-only **end** was interpreted as the start of that day, which effectively removed the entire last day of data. The new logic aligns **date-only** end bounds to the **last available bar** of that day in the dataset. This behavior is now consistent across Optuna, WFA, FT, DSR, Stress Test, Manual Test, and trade export.

---

## Remaining considerations
- Existing stored results still use old trimming. For consistency, re-run FT/Manual tests or full studies.
- If you want strict filtering of trades within aligned start/end (like WFA export does), we can add an explicit post-filter step in exports, but current `prepare_dataset_with_warmup()` already enforces inclusive bounds.

---

End of report.
