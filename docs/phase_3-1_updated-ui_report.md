# Phase 3-1 UI Updates — Session Changelog

Date: 2026-01-18
Scope: Results page UI + API support

This report lists all changes in the exact order they were applied during this session. Each step includes the problem, the solution, and modified files.

---

1) **Results table period labels (Variant 1)**
- **Problem:** Needed to show the active module period (Optuna IS / DSR / FT / Stress / Manual) in the results table header.
- **Solution:** Added date formatting and period label logic in results JS, appended period to table title, with `Period: N/A` fallback.
- **Files:**
  - `src/ui/static/js/results.js`

2) **Table header separator**
- **Problem:** Title and period ran together in header.
- **Solution:** Added a middle dot separator (`·`) between title and period.
- **Files:**
  - `src/ui/static/js/results.js`

3) **Study run date in page header**
- **Problem:** Needed to show study run date next to study name (e.g., `... · 2026.01.18`).
- **Solution:** Added `studyCreatedAt` to state, used `completed_at` (fallback `created_at`) and formatted date; appended to H2 header with `·`.
- **Files:**
  - `src/ui/static/js/results.js`

4) **Optimization Time persistence + display**
- **Problem:** Optimization time existed only in runtime summary; not persisted for future study loads; needed in Optuna Settings (left panel) under Workers.
- **Solution:**
  - Added `optimization_time_seconds` column to DB schema (studies table) and ensured migrations add it.
  - Stored optimization duration in `save_optuna_study_to_db` using Optuna summary or `start_time` fallback.
  - Added `Optimization Time` line in Results UI (Optuna Settings) and formatted seconds in JS.
  - For WFA mode, display `-`.
- **Files:**
  - `src/core/storage.py`
  - `src/ui/templates/results.html`
  - `src/ui/static/js/results.js`

5) **Equity chart time axis (Variant A)**
- **Problem:** Needed horizontal time labels on equity chart for non-WFA modes.
- **Solution:**
  - Backtest response already contains `timestamps`; updated JS to pass timestamps to chart renderer.
  - Rendered 5 evenly-spaced ticks and labels (initially `YYYY.MM.DD` vs `YYYY.MM` based on >90 days).
  - No WFA timestamps used.
- **Files:**
  - `src/ui/static/js/results.js`

6) **Move axis out of chart to avoid overlap with comparison line (Variant 1)**
- **Problem:** Comparison line overlapped axis labels inside SVG.
- **Solution:**
  - Added dedicated axis row below chart (`#equityAxis`) and moved axis labels/ticks out of SVG into HTML.
  - Restructured chart markup to include `chart-canvas` + `chart-axis` row.
  - Adjusted CSS layout/height.
- **Files:**
  - `src/ui/templates/results.html`
  - `src/ui/static/css/style.css`
  - `src/ui/static/js/results.js`

7) **Axis label sizing & tick collisions**
- **Problem:** Axis labels too small and ticks overlapped text.
- **Solution:**
  - Increased axis font size to 11px, then 12px; increased axis height; moved tick position upward.
- **Files:**
  - `src/ui/static/css/style.css`

8) **Change ticks to full-height vertical gridlines**
- **Problem:** Vertical tick marks still clashed with labels.
- **Solution:**
  - Removed tick marks and drew faint full-height gridlines in SVG at tick positions.
- **Files:**
  - `src/ui/static/js/results.js`
  - `src/ui/static/css/style.css` (removed tick class)

9) **Parameter table font weight (non-bold)**
- **Problem:** Parameters block values and names were bold.
- **Solution:** Set both name/value font-weight to 400.
- **Files:**
  - `src/ui/static/css/style.css`

10) **Attempted parameter ordering fixes (investigation)**
- **Problem:** Parameters still alphabetical despite ordering logic.
- **Solution (investigation steps):**
  - Added and then reverted a temporary re-render attempt; later found real cause: Flask JSON key sorting.
- **Files:**
  - `src/ui/static/js/results.js` (temporary changes, later removed)

11) **Root cause fix: preserve config order via API**
- **Problem:** Flask sorted JSON keys alphabetically (`JSON_SORT_KEYS`), losing original `config.json` order.
- **Solution:** Added `parameter_order` and `group_order` arrays in strategy config API response, preserving file order.
- **Files:**
  - `src/ui/server.py`

12) **Parameters block redesigned into grouped tiles**
- **Problem:** Wanted grouping (Entry / Stops / Trail / Risk), two-column layout, less gap between name/value, fixed params in grey, and copy-on-click.
- **Solution:**
  - Replaced table with grid layout and group cards.
  - Used `parameter_order` and `group_order` to render groups and preserve order.
  - Rendered labels from `config.json` `label` field; fallback to formatted name.
  - Fixed params (optimize.enabled !== true) styled as grey.
  - Added copy-to-clipboard on name/value click.
- **Files:**
  - `src/ui/templates/results.html`
  - `src/ui/static/css/style.css`
  - `src/ui/static/js/results.js`

13) **Copy highlight (local row flash)**
- **Problem:** Wanted visual feedback on copy without toast.
- **Solution:** Added 800ms highlight on the clicked parameter row; used pale blue hover color from table (`#e8f4ff`).
- **Files:**
  - `src/ui/static/css/style.css`
  - `src/ui/static/js/results.js`

14) **Temporary 3-column grid test and revert**
- **Problem:** Considered three columns for parameter groups.
- **Solution:** Briefly switched to 3 columns, then reverted to 2 columns per request.
- **Files:**
  - `src/ui/static/css/style.css`

15) **Axis labels format update (remove year)**
- **Problem:** Wanted month.day labels only, no year, and removed the 3‑month logic.
- **Solution:** Always label ticks as `MM.DD`.
- **Files:**
  - `src/ui/static/js/results.js`

---

## Summary of files changed
- `src/ui/static/js/results.js`
- `src/ui/static/css/style.css`
- `src/ui/templates/results.html`
- `src/ui/server.py`
- `src/core/storage.py`

## Notes
- WFA axis time labels are still intentionally omitted (no timestamps saved for stitched WFA curve).
- Optimization time persists only for **new** studies created after adding `optimization_time_seconds`.

---

End of report.
