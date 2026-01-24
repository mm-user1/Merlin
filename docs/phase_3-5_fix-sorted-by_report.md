# Results Subtitle Update Report

Date: 2026-01-24

## Summary
Updated the Results page subtitle logic to display concrete sorting criteria (including primary objectives and selected post-process sort metrics) and to standardize OOS/Manual Test subtitles to show only the source. Removed the legacy "Compared against" line for manual tests to keep the subtitle line consistent with OOS Test.

## Details
- Optuna IS subtitle now resolves the actual objective used for sorting:
  - Single objective: "Sorted by Objective: <Objective>"
  - Multi-objective: "Sorted by Primary Objective: <Objective>"
  - Fallbacks remain safe when config data is missing.
- Forward Test and Stress Test subtitles now reflect the selected sort metric using a robust label formatter that gracefully handles future metrics.
- OOS Test and Manual Test subtitles now show only "Source: <Friendly Name>" (no sorting text).
- Manual Test "Compared against" line is hidden/cleared.

## New or Modified Functions
- `formatTitleToken(token)`: Converts tokens to friendly labels with acronym handling (FT/IS/OOS/RoMaD/etc.).
- `formatTitleFromKey(key)`: Humanizes snake_case/space/hyphen keys into title-like labels.
- `formatSortMetricLabel(metric)`: Maps known sort metrics and falls back to humanized formatting for future metrics.
- `formatSourceLabel(source)`: Maps known source keys to friendly labels and falls back to humanized formatting.
- `getOptunaSortSubtitle()`: Centralized, consistent Optuna subtitle builder with multi-objective handling.

## Files Changed
- `src/ui/static/js/results.js`

---

# OOS Trades Download Fix

Date: 2026-01-24

## Summary
Added an OOS Test trades export endpoint and routed the Results page download button to it when the OOS Test tab is active. This ensures OOS Test downloads use the OOS date range rather than the IS range.

## Details
- New endpoint `/api/studies/<study_id>/trials/<trial_number>/oos-trades` mirrors the Forward Test export flow but uses `oos_test_start_date` / `oos_test_end_date` from the study.
- Frontend now routes Downloads in the OOS Test tab to the new endpoint.
- Existing IS/DSR/Stress/Forward/Manual/WFA exports are unchanged.

## New or Modified Functions
- `download_oos_test_trades(...)` in `src/ui/server.py`.

## Files Changed
- `src/ui/server.py`
- `src/ui/static/js/results.js`

## Notes
- No tests were run (endpoint mirrors existing FT export logic).
- Validate by opening `/results`, selecting OOS Test, selecting a trial, and downloading trades. The output should match the OOS test period.
