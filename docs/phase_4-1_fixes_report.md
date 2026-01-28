# Phase 4-1 Fixes Report

Date: 2026-01-28
Scope: Fixes implemented after the Phase 4 WFA refactor was committed (session starting from the tri-state constraints badge issue).

## Step-by-step Changelog

### 1) Tri-state constraints badge rendered as "fail" when NULL
- Issue: In Optuna results UI, constraints_satisfied = null was treated as false, showing a red dot.
- Files/functions:
  - `src/ui/static/js/optuna-results-ui.js` - `renderTrialRow()` constraint badge handling.
- Change:
  - Treat null the same as undefined for constraints rendering (blank/unknown).
- Why:
  - Preserve tri-state semantics from storage (NULL = unknown, not failed).

### 2) Stitched OOS timestamps ignored in WFA chart
- Issue: Stitched equity reconstruction omitted timestamps, so chart axis stayed index-based.
- Files/functions:
  - `src/ui/static/js/results.js` - stitched reconstruction output now includes timestamps.
  - `src/ui/static/js/wfa-results-ui.js` - `displayStitchedEquity()` passes timestamps to `renderEquityChart()`.
- Change:
  - Carry stitched timestamps through reconstruction and into chart rendering.
- Why:
  - Use real dates on the axis (aligns with Optuna charts and stored per-window timestamps).

### 3) NULL module ranks sorted first in WFA window trials
- Issue: module_rank NULL values could appear before ranked rows in WFA module tables.
- Files/functions:
  - `src/core/storage.py` - `load_wfa_window_trials()` ORDER BY clause.
- Change:
  - Sort by `(module_rank IS NULL) ASC, module_rank ASC` so NULLs appear last.
- Why:
  - Maintain expected ordering and avoid NULLs floating to the top.

### 4) WFA Stress Test base metrics mismatched (should mirror Optuna IS)
- Issue: Stress Test rows in WFA used partial base metrics; some fields were missing or inconsistent with Optuna IS.
- Files/functions:
  - `src/core/walkforward_engine.py` - `_convert_st_results_for_storage()`.
- Change:
  - Pull all base metrics from `optuna_result` (net profit, max DD, win rate, trades, max CL, PF, Ulcer, SQN, Consistency, Sharpe, RoMaD), with fallback only if Optuna data is unavailable.
- Why:
  - Stress Test has no separate test period; base metrics should match Optuna IS for the same trial.
- Notes:
  - Affects newly generated WFA studies. Existing stored rows are not retroactively updated.

### 5) WFA expanded tables lacked Optuna-style rank change arrows
- Issue: WFA module tables showed only base rank numbers; no deltas vs source ranking.
- Files/functions:
  - `src/ui/static/js/wfa-results-ui.js` - `renderModuleTrialsTable()`.
- Change:
  - Added rank-delta rendering using `source_rank - module_rank` to match Optuna mode.
- Why:
  - Match Optuna mode's rank-change visualization for DSR / Forward Test / Stress Test tables.

### 6) Optuna IS tab in WFA should not show rank deltas
- Issue: WFA Optuna IS table showed rank changes even though it is not a re-ranked view.
- Files/functions:
  - `src/ui/static/js/wfa-results-ui.js` - `renderModuleTrialsTable()` and `formatWfaRankCell()`.
- Change:
  - Show rank deltas only for re-ranking modules (`dsr`, `forward_test`, `stress_test`).
  - Treat null/undefined source ranks as "no delta" (avoid Number(null) -> 0 causing false deltas).
- Why:
  - Keep WFA Optuna IS consistent with Optuna mode behavior (no rank change in base Optuna IS list).

### 7) Report housekeeping
- Issue: An addendum was appended to the committed Phase 4 report.
- Files:
  - `docs/phase_4_wfa-refactor_plan_opus_v1_gpt-5.2_fixed_v2_report.md`.
- Change:
  - Removed that addendum and moved all post-commit fixes into this new report.
- Why:
  - Keep the committed Phase 4 report unchanged and centralize fixes here.

### 8) DSR trial_number mapping treated 0 as missing (inflated rank deltas)
- Issue: In DSR, `trial_number = optuna_trial_number or idx` treated `optuna_trial_number = 0` as falsy and replaced it with the loop index. This attached DSR metrics to the wrong trial row and produced huge rank deltas (for example, a Top-K=20 run showing +43).
- Investigation results (order and source of DSR candidates):
  - Optuna mode: `run_optimization()` returns results after `sort_optimization_results()`; `src/ui/server.py` passes that sorted list directly into `run_dsr_analysis()`.
  - WFA mode: `WalkForwardEngine._run_optuna_on_window()` returns `optimization_results` already sorted; those are passed into `run_dsr_analysis()`.
  - Conclusion: DSR candidates come from the exact same ordered list as the Optuna IS table. The large delta was not caused by candidate ordering.
- How the +43 appeared (example):
  - The trial with `optuna_trial_number = 0` was selected by DSR and ranked (say `dsr_rank = 4`).
  - The mapping logic stored that DSR result under `trial_number = idx` (e.g., 47).
  - The UI then attached `dsr_rank = 4` to the row whose base rank was around 47, so the delta looked like `47 - 4 = +43`.
- Files/functions:
  - `src/core/post_process.py` - `run_dsr_analysis()` trial_number assignment.
- Change:
  - Use an explicit `None` check so trial 0 is preserved.
- Code diff:
  ```diff
  -        trial_number = getattr(optuna_result, "optuna_trial_number", None) or idx
  +        trial_number = getattr(optuna_result, "optuna_trial_number", None)
  +        if trial_number is None:
  +            trial_number = idx
  ```
- Why:
  - Keeps DSR results bound to the correct Optuna trial numbers in both Optuna and WFA modes, preventing inflated rank deltas.

### 9) WFA comparison line parity for post-process modules
- Issue: WFA module tables (Optuna IS / DSR / Forward Test / Stress Test within each window) did not update the comparison line. Optuna mode shows a comparison line for every post-process module, but WFA was silent.
- Files/functions:
  - `src/ui/static/js/wfa-results-ui.js` - module row click handling and comparison line generation.
  - `src/core/walkforward_engine.py` - Stress Test module metrics storage.
- Change:
  - Added WFA comparison line rendering for module tables to mirror Optuna mode.
  - Extended WFA Stress Test `module_metrics` to include `combined_failure_count`, `total_perturbations`, and `most_sensitive_param` so the WFA line can match Optuna's "Insufficient Data" and "Sens" details.
- Why:
  - Enables full post-process parity (DSR/FT/ST) between Optuna and WFA results views.

### 10) WFA Stress Test used full IS window instead of truncated Optuna IS period
- Issue: When Forward Test (FT) was enabled, WFA truncated the Optuna IS optimization window (optimization_end = IS end minus FT days). Stress Test should use this same truncated Optuna IS period, but WFA ran Stress Test against the full IS window instead. That made WFA Stress Test behavior differ from Optuna mode.
- Files/functions:
  - `src/core/walkforward_engine.py` - Stress Test window date selection.
- Change:
  - Stress Test now uses `optimization_start`/`optimization_end` (the Optuna IS period actually used for optimization), not the full window IS.
- Why:
  - Aligns WFA Stress Test execution logic with Optuna mode: Stress Test should evaluate the same IS period that generated the Optuna IS results.

### 11) WFA results table header parity (module name, dates, sort type)
- Issue: WFA results table header stayed generic and did not update based on selected module/tab. It also did not show the stitched OOS period on load.
- Files/functions:
  - `src/ui/static/js/results.js` - default WFA header initialization; stitched OOS period label.
  - `src/ui/static/js/wfa-results-ui.js` - header updates on WFA module tab selection and stitched row click.
- Change:
  - On WFA load: header now shows `Stitched OOS · <min oos start>-<max oos end>` with empty subtitle.
  - On module tab click: header shows module name, correct working dates, and the same sort subtitle logic as Optuna (Primary Objective / DSR / FT sort metric / Stress Test sort metric).
  - Header does not change on window header / IS / OOS row clicks (per spec).
- Why:
  - Matches Optuna header behavior while respecting WFA-specific periods (including truncated Optuna IS when FT is enabled).

### 12) WFA Optuna IS subtitle ignored primary objective
- Issue: WFA studies stored no `primary_objective` in the `studies` row, and the UI only read `study.primary_objective` or `config.optuna_config.primary_objective`. Result: WFA Optuna IS subtitle defaulted to the first objective (e.g., Net Profit %) instead of the selected primary objective (e.g., Sharpe Ratio).
- Files/functions:
  - `src/core/storage.py` - `save_wfa_study_to_db()` study insert.
  - `src/ui/static/js/results.js` - `applyStudyPayload()` primary objective resolution.
- Change:
  - Persist WFA `primary_objective` from `config_json`.
  - UI now falls back to `config.primary_objective` when `study.primary_objective` is missing (supports existing WFA studies).
- Why:
  - Keeps WFA Optuna IS subtitle consistent with the actual primary objective selected in the run configuration.

### 13) WFA equity chart boundary markers (stitched windows + IS/OOS split)
- Issue: WFA stitched OOS chart had no visually distinct window separators, and the combined IS+OOS window chart lacked a clear IS/OOS boundary marker.
- Files/functions:
  - `src/ui/static/js/results.js` - `renderEquityChart()` boundary line styling and label behavior.
  - `src/ui/static/js/wfa-results-ui.js` - window equity rendering for `period="both"`.
- Change:
  - Boundary lines now render as light-blue dotted vertical markers.
  - Stitched OOS chart continues to show per-window separators (with W1/W2 labels).
  - Combined IS+OOS window chart now draws a single IS→OOS boundary marker based on timestamps and `oos_start_date` (fallback `is_end_date`).
- Why:
  - Improves readability and aligns chart visuals with window transitions and IS/OOS split points.

### 14) WFA chart boundary line visibility
- Issue: Boundary markers were too thin to see clearly on the equity chart.
- Files/functions:
  - `src/ui/static/js/results.js` - `renderEquityChart()` boundary line stroke width.
- Change:
  - Increased boundary line stroke width to improve visibility.
- Why:
  - Makes IS/OOS and window boundaries easier to see without affecting chart data.

### 15) WFA chart boundary dash length
- Issue: Boundary markers needed longer dashes for better visibility.
- Files/functions:
  - `src/ui/static/js/results.js` - `renderEquityChart()` boundary dash pattern.
- Change:
  - Increased dash length by setting `stroke-dasharray` to `6 4`.
- Why:
  - Improves visual clarity without altering data or layout.

### 16) Replace deprecated `datetime.utcnow()` with timezone-aware UTC timestamps
- Issue: Python 3.12+ deprecates `datetime.utcnow()` because it returns naive UTC datetimes.
- Files/functions:
  - `src/core/storage.py` - study insert timestamps.
  - `src/ui/server.py` - `_set_optimization_state()` `updated_at`.
- Change:
  - Added `_utc_now_iso()` helper and replaced `datetime.utcnow().isoformat() + "Z"` calls with `datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")`.
- Why:
  - Removes deprecation warning while preserving the exact timestamp format and behavior (UTC with trailing `Z`).

## Files Changed (Summary)
- `src/ui/static/js/optuna-results-ui.js`
- `src/ui/static/js/results.js`
- `src/ui/static/js/wfa-results-ui.js`
- `src/core/storage.py`
- `src/core/walkforward_engine.py`
- `src/core/post_process.py`
- `src/ui/server.py`
- `docs/phase_4_wfa-refactor_plan_opus_v1_gpt-5.2_fixed_v2_report.md`
- `docs/phase_4-1_fixes_report.md` (this file)

## Tests Executed
Command (per AGENTS.md):
`C:\\Users\\mt\\Desktop\\Strategy\\S_Python\\.venv\\Scripts\\python.exe -m pytest tests/ -v`

Results:
- 151 passed
- 3 warnings
  - Optuna ExperimentalWarning: multivariate sampler.
