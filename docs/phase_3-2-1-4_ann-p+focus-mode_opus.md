# Phase 3-2-1-4: Annualized Profit Column + Study Focus Mode

> Specification for two new features on the Analytics page:
> 1. Annualized Profit (Ann.P%) column in the Summary Table
> 2. Study Focus Mode for inspecting individual study details
>
> This update diverges from the original Phase 2 plan in `phase_3-2_wfa-analytics-layer-2_plan_opus_v4.md`.
> It cherry-picks Ann.P% from Phase 2 and adds a new Focus Mode concept not present in the original plan.

---

## Table of Contents

- [1. Annualized Profit Column](#1-annualized-profit-column)
- [2. Study Focus Mode](#2-study-focus-mode)
- [3. Sidebar: Optuna Settings and WFA Settings](#3-sidebar-optuna-settings-and-wfa-settings)
- [4. Chart and Metrics Cards Behavior](#4-chart-and-metrics-cards-behavior)
- [5. Backend Changes](#5-backend-changes)
- [6. Frontend Changes](#6-frontend-changes)
- [7. Interaction Summary](#7-interaction-summary)
- [8. Edge Cases](#8-edge-cases)
- [9. Implementation Steps](#9-implementation-steps)

---

## 1. Annualized Profit Column

### 1.1 Purpose

Enables comparison of studies with different data periods. A study earning +42% over 174 OOS days and another earning +72% over 324 OOS days cannot be compared directly — annualization normalizes them to a common time basis.

### 1.2 Formula

```
ann_profit_pct = ((1 + profit_pct / 100) ^ (365 / oos_span_days) - 1) * 100
```

Where `oos_span_days` is computed from equity curve timestamps (OOS-only timeline), NOT from `dataset_start_date` / `dataset_end_date` (which include the IS warmup period).

### 1.3 Computation Location

**Entirely in JavaScript (frontend).** The equity curve timestamps are already included in the summary API response for each study. No backend changes needed.

```javascript
const firstTs = study.equity_timestamps?.[0];
const lastTs = study.equity_timestamps?.[study.equity_timestamps.length - 1];
const oosSpanDays = (Date.parse(lastTs) - Date.parse(firstTs)) / 86400000;

if (oosSpanDays <= 0) return null; // show "N/A"
const annProfitPct = (Math.pow(1 + profitPct / 100, 365 / oosSpanDays) - 1) * 100;
```

### 1.4 Column Placement

The column is placed **before Profit%** to preserve the existing sequence Profit% → MaxDD% → Trades (consistent with Results page column order).

Updated column order (14 columns):

```
☑ │ # │ Strategy │ Study Name │ WFA │ IS/OOS │ Ann.P% │ Profit% │ MaxDD% │ Trades │ WFE% │ OOS Wins │ OOS P(med) │ OOS WR(med)
```

### 1.5 Display Format

| Value | Format | Example |
|-------|--------|---------|
| Positive | `+X.X%` | `+107.5%` |
| Negative | `-X.X%` | `-20.8%` |
| Zero | `0.0%` | `0.0%` |
| No data | `N/A` | (oos_span_days = 0 or missing timestamps) |

Same text coloring as Profit%: green for positive, red for negative.

### 1.6 Short Period Warning

| OOS Span | Behavior |
|----------|----------|
| >= 90 days | Normal display |
| 30-89 days | Show value with `*` suffix and tooltip: "Short OOS period (N days) — annualized value may be misleading" |
| < 30 days | Show `N/A` with tooltip: "OOS period too short for meaningful annualization (N days)" |

Rationale: +20% in 30 days annualizes to +791%, which is noise.

### 1.7 Sorting

Ann.P% is sortable. Add to `SORT_META`:

```javascript
ann_profit_pct: { label: 'Ann.P%', bestDirection: 'desc' }
```

The sort value is the computed annualized profit. Studies with `N/A` sort to the bottom.

### 1.8 Derived Field

Add `_ann_profit_pct` and `_oos_span_days` to the `withDerivedFields()` function in `analytics-table.js` so they are computed once per render and available for both display and sorting.

### 1.9 Examples

| Profit% | OOS Span Days | Ann.P% |
|---------|---------------|--------|
| +72.8 | 324 | +83.7 |
| +42.3 | 174 | +108.2 |
| -15.2 | 264 | -20.8 |
| +20.0 | 30 | N/A |
| +58.2 | 0 | N/A |

---

## 2. Study Focus Mode

### 2.1 Concept

Focus Mode is a new interaction layer **independent of checkbox selection**. It allows the user to inspect a single study's details (equity curve, metrics, optimization settings) without affecting the portfolio checkbox state.

Two independent selection concepts:

| Concept | Trigger | Purpose | Visual |
|---------|---------|---------|--------|
| **Checkbox selection** | Click / Shift+click / Ctrl+click | Portfolio aggregation (multi-select) | Checkbox state |
| **Study focus** | Alt+click | Inspect one study's details | Left blue border on row |

These are fully independent: focusing does not change checkboxes, and checking does not change focus.

### 2.2 Entering Focus Mode

**Trigger:** Alt+click on any study row in the Summary Table.

**Behavior:**
- `AnalyticsState.focusedStudyId` is set to the clicked study's `study_id`
- The focused row gets a visual indicator (3px solid left border, `#3498db`)
- Sidebar shows Optuna Settings and WFA Settings sections for this study
- Chart switches to the focused study's Stitched OOS equity curve
- Metric cards switch to the focused study's individual metrics
- Chart title updates: `Stitched OOS Equity — #N SYMBOL, TF` with a `[×]` dismiss button

**Alt+click on a different row** while already focused: switches focus to the new study.

### 2.3 Exiting Focus Mode

Two ways to exit:

| Method | Description |
|--------|-------------|
| **Esc key** | Press Escape anywhere on the page. Most natural keyboard shortcut for "dismiss/cancel". Works regardless of scroll position. |
| **Alt+click on focused row** | Alt+click on the already-focused row toggles focus off. |

On exit:
- `AnalyticsState.focusedStudyId` is set to `null`
- Focus row highlight is removed
- Sidebar Optuna/WFA Settings sections are hidden
- Chart reverts to the first checked study's equity (current Phase 1 behavior)
- Metric cards revert to aggregated values for checked studies
- Chart title reverts to default format

**No auto-exit on checkbox change.** Focus is sticky — it persists through checkbox toggles. The user must explicitly exit via Esc or Alt+click.

### 2.4 Focused Row Visual

The focused row has a 3px solid left border in `#3498db` (primary blue). No background color change (to avoid confusion with hover and striping).

```css
#analyticsSummaryTable tbody tr.analytics-study-row.analytics-focused {
  border-left: 3px solid #3498db;
}
```

Only one row can be focused at a time. The focus highlight is independent of checkbox state — a row can be both checked and focused, or unchecked and focused.

### 2.5 Chart Title in Focus Mode

```
Default (no focus):
  Stitched OOS Equity

Focused on study #3:
  Stitched OOS Equity — #3 LINKUSDT.P, 4h   [×]
```

The `[×]` is a small clickable button/link that exits focus mode (same as pressing Esc). It provides a visible, discoverable exit path.

Implementation: add a `<span>` element next to the chart title `<h3>`, visible only when `focusedStudyId` is set.

---

## 3. Sidebar: Optuna Settings and WFA Settings

### 3.1 Data Source

The `config_json` column in the `studies` table stores all optimization and WFA configuration for every study (both old and new). This data is parsed server-side and included in the summary API response as `optuna_settings` and `wfa_settings` objects per study.

### 3.2 Sidebar Sections

Two new collapsible sections appear in the sidebar **only when a study is focused**. They are hidden in aggregate mode (no focus).

Both sections start **expanded** when focus is first activated (consistent with Results page behavior).

```
┌─ Sidebar ─────────────────────────┐
│ ▼ Database                        │
│   my_research.db  ◄ active        │
│                                   │
│ ▼ Research Info                   │
│   Studies: 18 total (18 WFA)      │
│   Strategies: S01 v26             │
│   ...                             │
│                                   │
│ ▼ Optuna Settings                 │  ← visible only in focus mode
│   Objectives   Net Profit %       │
│   Primary      Net Profit %       │
│   Constraints  Trades >= 30       │
│   Budget       500 trials         │
│   Sampler      TPE                │
│   Pruner       -                  │
│   Workers      4                  │
│                                   │
│ ▼ WFA Settings                    │  ← visible only in focus mode
│   IS (days)    90                 │
│   OOS (days)   30                 │
│   Adaptive     Off                │
│                                   │
└───────────────────────────────────┘
```

### 3.3 Optuna Settings Fields

| Field | Source (from config_json) | Format |
|-------|--------------------------|--------|
| Objectives | `objectives` array | Comma-separated labels (using same label map as Results page) |
| Primary | `primary_objective` | Single objective label |
| Constraints | `constraints` array | "Metric >= N" format or "None" |
| Budget | `optuna_config.budget_mode` + params | "N trials" / "N min" / "No improvement N trials" |
| Sampler | `optuna_config.sampler_config.sampler_type` | UPPERCASE |
| Pruner | `optuna_config.pruner` or `optuna_config.enable_pruning` | String or "-" |
| Workers | `worker_processes` | Integer or "-" |

### 3.4 WFA Settings Fields

| Field | Source (from config_json) | Format |
|-------|--------------------------|--------|
| IS (days) | `wfa.is_period_days` or `is_period_days` (study column) | Integer |
| OOS (days) | `wfa.oos_period_days` | Integer |
| Adaptive | `wfa.adaptive_mode` or `adaptive_mode` (study column) | "On" / "Off" |
| Max OOS (days) | `wfa.max_oos_period_days` | Integer (only if adaptive) |
| Min OOS Trades | `wfa.min_oos_trades` | Integer (only if adaptive) |
| CUSUM Threshold | `wfa.cusum_threshold` | 2 decimal places (only if adaptive) |
| DD Multiplier | `wfa.dd_threshold_multiplier` | 2 decimal places (only if adaptive) |
| Inactivity Mult. | `wfa.inactivity_multiplier` | 2 decimal places (only if adaptive) |

Adaptive-only fields are hidden when adaptive mode is "Off" (same behavior as Results page).

### 3.5 HTML Structure

Add two new collapsible sections to `analytics.html` sidebar, after the Research Info section. Both start with `style="display: none;"` and are shown/hidden by JavaScript based on focus state.

```html
<div class="collapsible open" id="analytics-optuna-section" style="display: none;">
  <div class="collapsible-header">
    <span class="collapsible-icon">&#9660;</span>
    <span class="collapsible-title">Optuna Settings</span>
  </div>
  <div class="collapsible-content">
    <div class="settings-list" id="analyticsOptunaSettings"></div>
  </div>
</div>

<div class="collapsible open" id="analytics-wfa-section" style="display: none;">
  <div class="collapsible-header">
    <span class="collapsible-icon">&#9660;</span>
    <span class="collapsible-title">WFA Settings</span>
  </div>
  <div class="collapsible-content">
    <div class="settings-list" id="analyticsWfaSettings"></div>
  </div>
</div>
```

---

## 4. Chart and Metrics Cards Behavior

### 4.1 Two Modes

| Mode | Chart shows | Cards show | Card labels |
|------|-------------|------------|-------------|
| **Aggregate** (no focus) | First checked study's stitched OOS equity | Aggregated metrics for all checked studies | Portfolio Profit, Portfolio MaxDD, Total Trades, Profitable, Avg OOS Wins, Avg WFE, Avg OOS P(med) |
| **Focus** (study focused) | Focused study's stitched OOS equity | Focused study's individual metrics | NET PROFIT, MAX DRAWDOWN, TOTAL TRADES, WFE, OOS WINS, OOS PROFIT (MED), OOS WIN RATE (MED) |

### 4.2 Focus Mode Card Labels and Values

When a study is focused, the 7 cards match the Results page WFA card format exactly:

| # | Label | Value Source | Format |
|---|-------|-------------|--------|
| 1 | NET PROFIT | `profit_pct` | +XX.X% (green/red) |
| 2 | MAX DRAWDOWN | `max_dd_pct` | -XX.X% (red) |
| 3 | TOTAL TRADES | `winning_trades` / `total_trades` | "W/T" (e.g., "52/89") |
| 4 | WFE | `wfe_pct` | XX.X% |
| 5 | OOS WINS | `profitable_windows` / `total_windows` (%) | "N/M (X%)" |
| 6 | OOS PROFIT (MED) | `median_window_profit` | +XX.X% (green/red) |
| 7 | OOS WIN RATE (MED) | `median_window_wr` | XX.X% |

### 4.3 Aggregate Mode Card Labels and Values (unchanged)

Same as current implementation:

| # | Label | Formula |
|---|-------|---------|
| 1 | Portfolio Profit | SUM(profit_pct) for checked |
| 2 | Portfolio MaxDD | MAX(max_dd_pct) for checked (worst) |
| 3 | Total Trades | SUM(total_trades) for checked |
| 4 | Profitable | Count profit > 0 / total checked (%) |
| 5 | Avg OOS Wins | AVG(profitable_windows_pct) for checked |
| 6 | Avg WFE | AVG(wfe_pct) for checked |
| 7 | Avg OOS P(med) | AVG(median_window_profit) for checked |

### 4.4 Transition Between Modes

When entering focus mode:
- Cards re-render with focus labels and single-study values
- Chart re-renders with focused study's equity curve
- Chart title updates with study info and [×] button

When exiting focus mode:
- Cards re-render with aggregate labels and aggregated values
- Chart re-renders with first checked study's equity (or empty if none checked)
- Chart title reverts to default

---

## 5. Backend Changes

### 5.1 Summary Endpoint Update

Modify `GET /api/analytics/summary` to include parsed `config_json` fields for each study.

Add to the study object in the response:

```python
# Parse config_json for sidebar display
config = _parse_json_dict(row_dict.get("config_json"))
optuna_config = config.get("optuna_config") or {}
wfa_config = config.get("wfa") or {}

studies.append({
    # ... existing fields ...

    # NEW: parsed settings for Focus Mode sidebar
    "optuna_settings": {
        "objectives": list(config.get("objectives") or []),
        "primary_objective": config.get("primary_objective"),
        "constraints": list(config.get("constraints") or []),
        "budget_mode": optuna_config.get("budget_mode"),
        "n_trials": _safe_int(optuna_config.get("n_trials")),
        "time_limit": _safe_int(optuna_config.get("time_limit")),
        "convergence_patience": _safe_int(optuna_config.get("convergence_patience")),
        "sampler_type": (optuna_config.get("sampler_config") or {}).get("sampler_type"),
        "enable_pruning": optuna_config.get("enable_pruning"),
        "pruner": optuna_config.get("pruner"),
        "workers": _safe_int(config.get("worker_processes")),
        "sanitize_enabled": optuna_config.get("sanitize_enabled"),
        "sanitize_trades_threshold": _safe_int(optuna_config.get("sanitize_trades_threshold")),
        "filter_min_profit": config.get("filter_min_profit"),
        "min_profit_threshold": _safe_float(config.get("min_profit_threshold")),
    },
    "wfa_settings": {
        "is_period_days": _safe_int(row_dict.get("is_period_days"))
                          or _safe_int(wfa_config.get("is_period_days")),
        "oos_period_days": _safe_int(wfa_config.get("oos_period_days"))
                           or _safe_int(oos_period_days),
        "adaptive_mode": bool(_safe_int(row_dict.get("adaptive_mode"))),
        "max_oos_period_days": _safe_int(wfa_config.get("max_oos_period_days")),
        "min_oos_trades": _safe_int(wfa_config.get("min_oos_trades")),
        "cusum_threshold": _safe_float(wfa_config.get("cusum_threshold")),
        "dd_threshold_multiplier": _safe_float(wfa_config.get("dd_threshold_multiplier")),
        "inactivity_multiplier": _safe_float(wfa_config.get("inactivity_multiplier")),
    },
})
```

This works for **all existing studies** (old and new) because `config_json` has been stored since the project's inception. Every WFA study in the database already contains this data.

### 5.2 No New Endpoints

No separate API call is needed. The parsed settings are included in the existing summary response. The additional payload is ~200-500 bytes per study, negligible for 18-50 studies.

---

## 6. Frontend Changes

### 6.1 State Changes

Add to `AnalyticsState`:

```javascript
focusedStudyId: null,  // string study_id or null
```

### 6.2 New Functions in analytics.js

| Function | Purpose |
|----------|---------|
| `setFocus(studyId)` | Set focusedStudyId, update sidebar/chart/cards, highlight row |
| `clearFocus()` | Reset focusedStudyId to null, revert to aggregate mode |
| `renderFocusedSidebar(study)` | Populate Optuna Settings and WFA Settings sections |
| `hideFocusSidebar()` | Hide Optuna/WFA sections |
| `renderFocusedCards(study)` | Render 7 cards with single-study values and Results-page labels |

### 6.3 Event Handling in analytics-table.js

Add Alt+click detection to the existing click handler:

```javascript
// In the table click handler, before other row-click handling:
if (event.altKey && row) {
  event.preventDefault();
  const studyId = decodeStudyId(rowCheckbox.dataset.studyId);
  // Toggle: if already focused on this study, clear focus; otherwise set focus
  if (AnalyticsState.focusedStudyId === studyId) {
    clearFocus();
  } else {
    setFocus(studyId);
  }
  return; // Do not toggle checkbox
}
```

Add Esc key handler (global):

```javascript
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && AnalyticsState.focusedStudyId) {
    clearFocus();
  }
});
```

### 6.4 Chart Title [×] Button

When focus is active, the chart title area shows a dismiss button:

```javascript
// In renderSelectedStudyChart() or a new renderFocusedChart():
titleEl.innerHTML = `Stitched OOS Equity — #${rowNumber} ${symbol} ${tf}
  <span class="focus-dismiss" id="analyticsFocusDismiss" title="Exit focus mode">&times;</span>`;
```

Bind click on `#analyticsFocusDismiss` to `clearFocus()`.

### 6.5 Ann.P% Column in analytics-table.js

Add to `withDerivedFields()`:

```javascript
function computeAnnProfitPct(study) {
  const timestamps = study.equity_timestamps;
  if (!Array.isArray(timestamps) || timestamps.length < 2) return { annProfitPct: null, oosSpanDays: null };

  const firstMs = Date.parse(timestamps[0]);
  const lastMs = Date.parse(timestamps[timestamps.length - 1]);
  if (!Number.isFinite(firstMs) || !Number.isFinite(lastMs)) return { annProfitPct: null, oosSpanDays: null };

  const oosSpanDays = (lastMs - firstMs) / 86400000;
  if (oosSpanDays < 30) return { annProfitPct: null, oosSpanDays };

  const profitPct = toFiniteNumber(study.profit_pct);
  if (profitPct === null) return { annProfitPct: null, oosSpanDays };

  const annProfitPct = (Math.pow(1 + profitPct / 100, 365 / oosSpanDays) - 1) * 100;
  return { annProfitPct, oosSpanDays };
}
```

Add `_ann_profit_pct` and `_oos_span_days` to the derived fields object.

Add Ann.P% column to the table header in `analytics.html`:

```html
<th class="analytics-sortable" data-sort-key="ann_profit_pct">
  <span class="sort-label">Ann.P%</span><span class="sort-arrow"></span>
</th>
```

Add the cell rendering in `renderTableBody()` between IS/OOS and Profit%.

### 6.6 Sidebar Rendering

Reuse the same `.setting-item` markup pattern used by Research Info and by the Results page:

```javascript
function renderFocusedSidebar(study) {
  const optunaSection = document.getElementById('analytics-optuna-section');
  const wfaSection = document.getElementById('analytics-wfa-section');
  const optunaContainer = document.getElementById('analyticsOptunaSettings');
  const wfaContainer = document.getElementById('analyticsWfaSettings');

  if (!optunaSection || !wfaSection) return;

  const os = study.optuna_settings || {};
  const ws = study.wfa_settings || {};

  // Optuna Settings
  optunaContainer.innerHTML = '';
  const optunaRows = [
    { key: 'Objectives', val: formatObjectivesList(os.objectives) },
    { key: 'Primary', val: formatObjectiveLabel(os.primary_objective) },
    { key: 'Constraints', val: formatConstraintsSummary(os.constraints) },
    { key: 'Budget', val: formatBudget(os) },
    { key: 'Sampler', val: (os.sampler_type || '').toUpperCase() || '-' },
    { key: 'Pruner', val: os.enable_pruning ? (os.pruner || 'On') : '-' },
    { key: 'Workers', val: os.workers != null ? String(os.workers) : '-' },
  ];
  renderSettingsList(optunaContainer, optunaRows);
  optunaSection.style.display = '';

  // WFA Settings
  wfaContainer.innerHTML = '';
  const wfaRows = [
    { key: 'IS (days)', val: ws.is_period_days != null ? String(ws.is_period_days) : '-' },
    { key: 'OOS (days)', val: ws.oos_period_days != null ? String(ws.oos_period_days) : '-' },
    { key: 'Adaptive', val: ws.adaptive_mode ? 'On' : 'Off' },
  ];
  if (ws.adaptive_mode) {
    wfaRows.push(
      { key: 'Max OOS (days)', val: ws.max_oos_period_days != null ? String(ws.max_oos_period_days) : '-' },
      { key: 'Min OOS Trades', val: ws.min_oos_trades != null ? String(ws.min_oos_trades) : '-' },
      { key: 'CUSUM Threshold', val: ws.cusum_threshold != null ? Number(ws.cusum_threshold).toFixed(2) : '-' },
      { key: 'DD Multiplier', val: ws.dd_threshold_multiplier != null ? Number(ws.dd_threshold_multiplier).toFixed(2) : '-' },
      { key: 'Inactivity Mult.', val: ws.inactivity_multiplier != null ? Number(ws.inactivity_multiplier).toFixed(2) : '-' },
    );
  }
  renderSettingsList(wfaContainer, wfaRows);
  wfaSection.style.display = '';
}
```

Helper functions (`formatObjectivesList`, `formatObjectiveLabel`, `formatConstraintsSummary`, `formatBudget`) should mirror the logic from `results-format.js`. They can either be shared via `utils.js` or duplicated minimally in the analytics module.

---

## 7. Interaction Summary

```
ACTION                              RESULT
────────────────────────────────    ──────────────────────────────────────
Click on row                        Toggle checkbox (existing, unchanged)
Shift+click on row                  Range select (existing, unchanged)
Ctrl+click on row                   Toggle all visible (existing, unchanged)
Alt+click on row                    Focus this study → sidebar, chart, cards update
Alt+click on already-focused row    Exit focus → revert to aggregate mode
Esc key                             Exit focus → revert to aggregate mode
Click [×] next to chart title       Exit focus → revert to aggregate mode
Alt+click on different row          Switch focus to new study
```

Focus and checkbox selection are fully independent. A row can be:
- Checked and focused (checkbox ON, blue left border)
- Checked and not focused (checkbox ON, no border)
- Unchecked and focused (checkbox OFF, blue left border)
- Unchecked and not focused (checkbox OFF, no border)

---

## 8. Edge Cases

| Scenario | Behavior |
|----------|----------|
| Alt+click when no studies loaded | No-op |
| Focus a study with no equity curve | Chart shows "No stitched OOS equity data" placeholder; cards still show available metrics |
| Focus a study then switch database | Focus is cleared on DB switch (existing reset logic) |
| Focus a study then apply filter that hides it | Focus is cleared (focused study no longer visible) |
| Ann.P% with `oos_span_days = 0` | Show "N/A" |
| Ann.P% with `oos_span_days < 30` | Show "N/A" with tooltip |
| Ann.P% with `oos_span_days` 30-89 | Show value with `*` suffix and tooltip |
| Ann.P% with `profit_pct = 0` | Ann.P% = 0.0% |
| Sort by Ann.P% with N/A values | N/A sorts to bottom regardless of direction |
| `config_json` is null or empty | Sidebar sections show "-" for all fields |
| Study missing `optuna_settings` | Sidebar shows fields with "-" values |

---

## 9. Implementation Steps

### Step 1: Backend — Parse config_json in summary endpoint

- Modify `server_routes_analytics.py` → `analytics_summary()`
- Parse `config_json` for each WFA study
- Add `optuna_settings` and `wfa_settings` objects to each study in the response
- No new endpoints needed

### Step 2: Frontend — Ann.P% column

- Add `computeAnnProfitPct()` function and derived fields to `analytics-table.js`
- Add `ann_profit_pct` to `SORT_META`
- Add column header to `analytics.html` (before Profit%)
- Add cell rendering in `renderTableBody()`
- Add short-period warning display logic
- Update `colspan` values in group rows (13 → 14)

### Step 3: Frontend — Focus Mode state and events

- Add `focusedStudyId` to `AnalyticsState`
- Add Alt+click handler in table click event (in `analytics-table.js`)
- Add Esc key handler (in `analytics.js`)
- Add `setFocus()` and `clearFocus()` functions
- Add `.analytics-focused` CSS class for row highlight

### Step 4: Frontend — Sidebar sections

- Add Optuna Settings and WFA Settings HTML sections to `analytics.html`
- Implement `renderFocusedSidebar()` and `hideFocusSidebar()` in `analytics.js`
- Add helper functions for formatting objectives, constraints, budget
- Show/hide sections based on focus state

### Step 5: Frontend — Chart and cards in focus mode

- Modify `renderSelectedStudyChart()` to check for focused study first
- Add chart title [×] dismiss button
- Modify `renderSummaryCards()` to render differently based on focus state
- Add focus mode card rendering with Results-page labels

### Step 6: CSS updates

- Add `.analytics-focused` row style (3px left border)
- Add `.focus-dismiss` button style (small [×] near chart title)
- Ensure focus highlight doesn't conflict with hover, stripe, or checkbox states

---

*Document version: v1 | Created: 2026-02-23 | For: Merlin Phase 3-2-1-4*
