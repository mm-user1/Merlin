# Phase 3-2: WFA Analytics Layer 2 — Implementation Plan v5

> Remaining specification for the Analytics page in Merlin.
> This plan lists only features NOT YET implemented as of 2026-02-26.
> Phase structure removed — items are listed as independent work units.

---

## Changelog

| Version | Changes |
|---------|---------|
| v2 → v3 | 7 audit fixes (analytics columns migration, DB selector reuse, dual TF/date parsers, OOS span for Ann.P%, forward-fill equity, adaptive_mode type) |
| v3 → v4 | Renamed "Research Analytics" → "Analytics". Split into 3 implementation phases. Replaced "N Selected" card with "Profitable Studies". Phase 1 simplified equity (single study curve) and metrics (SUM profit, worst MaxDD). Header checkbox added. |
| v4 → v5 | Removed all implemented features. Removed phase structure. Aligned with current architecture (Study Name column, 14-column table, focus mode, study sets with comparison metrics, multi-select filters, auto-select, row interaction shortcuts). |

---

## Table of Contents

- [1. What Is Already Implemented](#1-what-is-already-implemented)
- [2. Remaining Features Overview](#2-remaining-features-overview)
- [3. Portfolio Equity Aggregation](#3-portfolio-equity-aggregation)
- [4. Auto-Labels](#4-auto-labels)
- [5. Notes Column](#5-notes-column)
- [6. Label and Note Persistence](#6-label-and-note-persistence)
- [7. Conditional Formatting](#7-conditional-formatting)
- [8. AVG Footer Row](#8-avg-footer-row)
- [9. Heatmaps](#9-heatmaps)
- [10. Selection Summary Sidebar](#10-selection-summary-sidebar)
- [11. Compare Set Equity Curves](#11-compare-set-equity-curves)
- [12. Export CSV](#12-export-csv)
- [13. Export to Global DB (Layer 3 Preview)](#13-export-to-global-db-layer-3-preview)
- [14. Backend API (New Endpoints)](#14-backend-api-new-endpoints)
- [15. Database Changes](#15-database-changes)
- [16. Error Handling and Edge Cases](#16-error-handling-and-edge-cases)
- [17. Performance Considerations](#17-performance-considerations)
- [18. Testing Plan](#18-testing-plan)
- [19. Open Questions](#19-open-questions)

---

## 1. What Is Already Implemented

The following features are fully implemented and should NOT be re-implemented:

### Page Structure
- Analytics page route (`GET /analytics`), template, and top nav tab
- Three-page navigation (Start | Results | Analytics)
- Sidebar with Database selector (click-to-switch) and Research Info section
- Main area with header showing "Analytics [db_name]"
- Message area for errors/info

### Backend
- `GET /api/analytics/summary` — returns all WFA studies with full field set
- Symbol/TF parsing from `csv_file_name` with numeric and human-readable TF formats
- `adaptive_mode` conversion (0→Fixed, 1→Adaptive)
- `parse_date_flexible()` for both YYYY-MM-DD and YYYY.MM.DD formats
- Per-study `optuna_settings` and `wfa_settings` nested objects
- `study_name`, `created_at`, `completed_at`, epoch timestamps
- Study Sets CRUD API: `GET/POST/PUT/DELETE /api/analytics/sets`, `PUT /api/analytics/sets/reorder`

### Summary Table (14 columns)
| # | Column | Sortable | Notes |
|---|--------|----------|-------|
| — | ☑ Checkbox | — | Tri-state (header/group/row hierarchy) |
| 1 | # | — | Renumbered for visible rows only |
| 2 | Strategy | — | "S01 v26" format |
| 3 | Study Name | Yes | Parsed display name (strips _WFA, date range, S##_ prefix; normalizes TF) |
| 4 | WFA | — | Fixed / Adaptive |
| 5 | IS/OOS | — | "90/30" format |
| 6 | Ann.P% | Yes | Annualized profit with ⚠ for short periods (≤30d → "N/A", 31-89d → `*` suffix) |
| 7 | Profit% | Yes | Signed percent with +/− |
| 8 | MaxDD% | Yes | Negative format, red text if abs > 40% |
| 9 | Trades | Yes | Integer |
| 10 | WFE% | Yes | 1 decimal, "N/A" if missing |
| 11 | OOS Wins | Yes | "X/Y (Z%)" format |
| 12 | OOS P(med) | Yes | Signed percent, 1 decimal |
| 13 | OOS WR(med) | Yes | Unsigned percent, 1 decimal |

### Table Features
- Time period group rows with duration, study count, and group checkboxes
- Column sorting with 3-click cycle (best → worst → reset)
- Sort within groups (group order = newest first by created_at)
- Row click toggle, Shift+click range selection, Ctrl+click visible-only bulk select/deselect
- Row numbering renumbered for visible rows only

### Filters
- 5 multi-select filter dropdowns: Strategy, Symbol, TF, WFA, IS/OOS
- Ctrl+click for exclusive mode (isolate)
- Active filter tags strip with per-filter clear and Clear All
- Auto-select mode (filters drive selection)

### Equity Chart
- Single study stitched OOS equity curve (SVG polyline)
- Time-scaled X-axis with date ticks
- Baseline at 100.0
- Chart title with study number + symbol + TF
- Empty state handling

### Metric Cards (7 cards)
- Portfolio mode (multiple studies checked): SUM profit, MAX(maxDD) worst, SUM trades, profitable count/total, AVG OOS Wins %, AVG WFE, AVG OOS P(med)
- Focus mode (single study focused): individual study metrics with WFA-style labels
- Empty state: dashes

### Focus Mode
- Alt+click toggles focus on a study row
- Escape exits focus
- Focused row gets visual marker (CSS class)
- Chart shows focused study's equity curve
- Sidebar shows Optuna/WFA settings for focused study
- Focus cleared on filter hide, DB switch, summary reload

### Study Sets
- Persistent named sets (SQLite: `study_sets` + `study_set_members` tables)
- "All Studies" baseline row
- 3 view modes: allStudies, setFocus, setCheckboxes
- Sets table with per-set metrics: Ann.P%, Profit%, MaxDD%, Profitable, WFE%, OOS Wins
- Set CRUD: Save Set, Update Set (focused or dropdown), Rename, Delete
- Move mode (keyboard-driven reorder)
- Expand/collapse for >5 sets
- Set checkbox selection (click/shift/ctrl)
- Set focus (Alt+click) with study visibility filtering

### Selection
- Select All / Deselect All buttons
- Auto-select checkbox
- Header checkbox (tri-state)

---

## 2. Remaining Features Overview

| # | Feature | Scope | Dependencies |
|---|---------|-------|-------------|
| 1 | Portfolio equity aggregation | Backend + frontend | New endpoint |
| 2 | Auto-labels (PASS / MAYBE / FAIL) | Backend + frontend | DB migration |
| 3 | Notes column | Frontend + backend | DB migration |
| 4 | Label and note persistence | Backend + frontend | DB migration, auto-labels |
| 5 | Conditional formatting | Frontend | — |
| 6 | AVG footer row | Frontend | — |
| 7 | Heatmaps | Frontend | — |
| 8 | Selection Summary sidebar | Frontend | Auto-labels |
| 9 | Compare set equity curves | Frontend + backend | Portfolio equity aggregation |
| 10 | Export CSV | Frontend | — |
| 11 | Export to Global DB | Backend + frontend | DB schema, new endpoint |

---

## 3. Portfolio Equity Aggregation

### 3.1 Purpose

Replace the current single-study equity chart with an aggregated portfolio equity curve when multiple studies are checked. The current chart shows only the first checked (or focused) study's stitched OOS curve.

### 3.2 Algorithm

Uses forward-fill (last-observation-carried-forward / LOCF) instead of linear interpolation. Linear interpolation creates phantom intermediate values that distort MaxDD calculations.

```python
def aggregate_equity_curves(selected_studies):
    """
    Aggregate multiple equity curves into a single portfolio curve.
    Uses equal-weight averaging over the common time intersection.
    Alignment via forward-fill (LOCF), NOT linear interpolation.
    """
    if len(selected_studies) == 0:
        return None

    if len(selected_studies) == 1:
        return selected_studies[0]  # single study, no aggregation

    # 1. Find common time range (intersection)
    t_start = max(study.timestamps[0] for study in selected_studies)
    t_end = min(study.timestamps[-1] for study in selected_studies)

    if t_start >= t_end:
        return None  # no overlap — show warning

    # 2. Build common timestamp grid (daily intervals)
    common_ts = generate_daily_grid(t_start, t_end)

    # 3. Align each study using forward-fill, normalize to 100.0 at t_start
    aligned_curves = []
    for study in selected_studies:
        curve = forward_fill(study.timestamps, study.equity_curve, common_ts)
        start_val = curve[0]
        normalized = [v / start_val * 100.0 for v in curve]
        aligned_curves.append(normalized)

    # 4. Equal-weight average
    portfolio = []
    for i in range(len(common_ts)):
        avg = sum(curve[i] for curve in aligned_curves) / len(aligned_curves)
        portfolio.append(avg)

    # 5. Compute portfolio metrics from aggregated curve
    portfolio_profit = (portfolio[-1] / 100.0 - 1) * 100
    portfolio_maxdd = compute_max_drawdown(portfolio)

    return {
        'curve': portfolio,
        'timestamps': common_ts,
        'profit_pct': portfolio_profit,
        'max_drawdown_pct': portfolio_maxdd
    }
```

### 3.3 Max Drawdown Computation

```python
def compute_max_drawdown(equity_curve):
    """Peak-to-trough drawdown on equity array."""
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100.0
        if dd > max_dd:
            max_dd = dd
    return max_dd
```

### 3.4 Time Range Rule

**MVP: intersection only.**

| Scenario | Behavior |
|----------|----------|
| All studies overlap fully | Full aggregation |
| Partial overlap | Only overlapping portion used |
| No overlap | Warning: "No common time range" |
| Short overlap (< 30 days) | Warning icon on chart |

### 3.5 Chart Behavior Change

- When 0 studies checked → empty chart placeholder (current behavior)
- When 1 study checked → show that study's stitched OOS curve (current behavior)
- When 2+ studies checked → show aggregated portfolio equity curve (NEW)
- Focus mode → show focused study's curve (current behavior, takes priority)
- Chart title updates: "Portfolio Equity Curve (N selected)" when showing aggregated curve

### 3.6 Metric Cards Upgrade

When showing aggregated portfolio curve, cards 1 and 2 upgrade:

| # | Card | Current (Phase 1) Formula | Upgraded Formula |
|---|------|--------------------------|-----------------|
| 1 | Portfolio Profit | `SUM(profit_pct_i)` | `(portfolio_curve[-1] / 100 - 1) * 100` from aggregated curve |
| 2 | Portfolio MaxDD | `MAX(max_dd_pct_i)` worst | Peak-to-trough on aggregated equity curve |

Cards 3–7 remain unchanged.

**CRITICAL:** Portfolio Profit and MaxDD are computed FROM the aggregated equity curve, NOT as SUM/AVG of individual study values.

### 3.7 Computation Location

- **Backend** (`POST /api/analytics/equity`): accepts `study_ids`, returns aggregated curve + metrics
- Frontend sends checked study_ids (debounced 300ms after checkbox changes), receives ready-to-plot result
- When 1 study checked, skip API call and use existing client-side curve display

### 3.8 Interaction with Focus Mode

Focus mode overrides portfolio aggregation:
- Focus active → show focused study's individual curve (current behavior)
- Focus cleared with 2+ studies checked → trigger portfolio aggregation

---

## 4. Auto-Labels

### 4.1 Rules

```
PASS:  profit > 0  AND  maxDD < 35  AND  profitable_windows_pct > 60  AND  total_trades >= 30
FAIL:  profit <= 0  OR  maxDD > 50  OR  profitable_windows_pct < 30
MAYBE: everything else
```

Where:
- `profit` = `stitched_oos_net_profit_pct`
- `maxDD` = `stitched_oos_max_drawdown_pct` (stored as positive number)
- `profitable_windows_pct` = `(profitable_windows / total_windows) * 100`
- `total_trades` = `stitched_oos_total_trades`

### 4.2 Evaluation Order

FAIL is checked first (any single FAIL condition triggers FAIL), then PASS (all conditions must be met), then MAYBE is the fallback.

### 4.3 Behavior

- Auto-label computed in Python when the summary endpoint is called
- Applied to studies that don't have a manual label override (`analytics_label IS NULL`)
- Manual labels take priority over auto-labels
- Thresholds are hardcoded in MVP; configurable through UI in a future phase

### 4.4 Label Column in Table

Add a new column **Label** after OOS WR(med) (column 14 in current table, becoming column 15 with the label addition):

| Column | Width | Source | Sortable | Description |
|--------|-------|--------|----------|-------------|
| Label | 60px | `analytics_label` or auto-computed | No | PASS / MAYBE / FAIL badge |

Clicking the label badge opens a dropdown: PASS / MAYBE / FAIL / Auto (reset to auto).

### 4.5 Label Badges

| Label | Background | Text | Border |
|-------|-----------|------|--------|
| PASS | `#d4edda` | `#155724` | `#8fd19e` |
| MAYBE | `#fff3cd` | `#856404` | `#ffc107` |
| FAIL | `#f8d7da` | `#721c24` | `#f1aeb5` |

### 4.6 Label Filter

Add a **Label** dropdown to the existing filters bar (6th filter, after IS/OOS):

| Filter | Values | Source |
|--------|--------|--------|
| Label | All, PASS, MAYBE, FAIL | Fixed values |

Also add a **Select PASS Only** button near the existing Select All / Deselect All buttons. It checks only PASS-labeled visible studies.

### 4.7 Auto-Label Thresholds Sidebar

Collapsed sidebar section below Study Sets. Shows current PASS/FAIL criteria. Read-only in MVP.

```
┌─ Auto-Label Thresholds ───────────────┐
│  PASS: P>0, DD<35, OOS W>60%, T≥30   │
│  FAIL: P≤0 | DD>50 | OOS W<30%       │
│  MAYBE: everything else               │
└────────────────────────────────────────┘
```

---

## 5. Notes Column

Add a new column **Note** after Label (becoming column 16):

| Column | Width | Source | Sortable | Description |
|--------|-------|--------|----------|-------------|
| Note | 120px | `analytics_note` | No | Truncated text, tooltip on hover |

- Click cell to edit (inline input or small textarea)
- Truncated display with full text in `title` tooltip
- Changes tracked locally until Save Labels is clicked

---

## 6. Label and Note Persistence

### 6.1 Database Migration

The columns `analytics_label` and `analytics_note` do NOT currently exist in the `studies` table. They must be added via idempotent migration:

```python
def _ensure_analytics_columns(conn):
    """Add analytics columns to studies table if missing."""
    cursor = conn.execute("PRAGMA table_info(studies)")
    existing = {row[1] for row in cursor.fetchall()}

    if "analytics_label" not in existing:
        conn.execute("ALTER TABLE studies ADD COLUMN analytics_label TEXT")

    if "analytics_note" not in existing:
        conn.execute("ALTER TABLE studies ADD COLUMN analytics_note TEXT")
```

Call from the existing `ensure()` entry point in `storage.py`.

### 6.2 Save Labels Button

Add a **Save Labels** button in the actions area (near Select All / Deselect All). Behavior:
- Collects all modified labels and notes
- Sends `POST /api/analytics/labels/batch`
- Shows success notification
- Resets dirty tracking

### 6.3 Summary Endpoint Upgrade

`GET /api/analytics/summary` response per study gains these fields:
```json
{
  "auto_label": "PASS",
  "analytics_label": null,
  "analytics_note": "Best overall"
}
```

---

## 7. Conditional Formatting

### 7.1 Cell Background Colors

Currently only MaxDD% > 40% gets red text styling. Full conditional formatting adds background colors:

| Metric | Strong Green `#c6efce` | Light Green `#e2f0d9` | Yellow `#fff9e6` | Strong Red `#f8d7da` |
|--------|----------------------|---------------------|-----------------|---------------------|
| Profit% | > +30 | 0 .. +30 | — | < 0 |
| Ann.P% | > +30 | 0 .. +30 | — | < 0 |
| MaxDD% | < 20 | — | 20 — 35 | > 35 |
| WFE% | > 20 | — | 10 — 20 | < 10 |
| OOS Wins % | > 70% | — | 40% — 70% | < 40% |
| OOS P(med) | > +5 | 0 .. +5 | — | < 0 |

### 7.2 Text Colors

| Condition | Color | Hex |
|-----------|-------|-----|
| Positive values (profit, OOS P) | Green | `#27ae60` |
| Negative values | Red | `#e74c3c` |
| Warning range (MaxDD 20-35) | Orange | `#e67e22` |
| Neutral | Default text | `#2a2a2a` |

### 7.3 Conditional Formatting Legend

Compact grid below the table showing color meanings. Collapsible.

---

## 8. AVG Footer Row

- Sticky footer row at the bottom of the summary table
- Shows averages for all **visible** (filtered) studies, not just checked
- Styled distinctly: `#f0f0f0` background, bold, 2px top border
- Columns with averages: Ann.P%, Profit%, MaxDD%, Trades (avg), WFE%, OOS P(med), OOS WR(med)
- OOS Wins shows average percentage format
- Always stays at the very bottom of the table

---

## 9. Heatmaps

### 9.1 Types

| Heatmap | Rows | Columns | Cell Value |
|---------|------|---------|------------|
| Profit% by Symbol × TF | Symbols | Timeframes | `stitched_oos_net_profit_pct` |
| WFE% by Symbol × TF | Symbols | Timeframes | `best_value` (WFE) |

### 9.2 Cell Colors (Threshold-Based)

| Range | Color | CSS Class |
|-------|-------|-----------|
| Strong positive | `#a9dfbf` | `hm-strong-green` |
| Light positive | `#d5f5e3` | `hm-light-green` |
| Neutral | `#fdebd0` | `hm-neutral` |
| Light negative | `#fadbd8` | `hm-light-red` |
| Strong negative | `#f1948a` | `hm-strong-red` |
| AVG cells | `#eaf2f8` | `hm-avg` |

For Profit%: strong green > +30, light green 0..+30, neutral = N/A, light red -15..0, strong red < -15

For WFE%: strong green > 20, neutral 10..20, light red 5..10, strong red < 5

### 9.3 AVG Rows and Columns

- Last row: AVG per TF (across all symbols)
- Last column: AVG per Symbol (across all TFs)
- Cells with no data show "—"

### 9.4 Multiple Studies Per Cell

If multiple studies map to the same Symbol × TF (e.g., from different time periods or different IS/OOS settings), show AVG in the cell.

### 9.5 Filter Interaction

Heatmaps respect active filters (except Symbol and TF filters which define the axes). If the user filters to WFA=Fixed only, the heatmap shows only Fixed studies.

### 9.6 Layout

Collapsible section below the summary table. Two heatmaps side by side. Section starts expanded. Click header to collapse/expand.

### 9.7 New File

Add `static/js/analytics-heatmap.js` for heatmap rendering.

---

## 10. Selection Summary Sidebar

New collapsible sidebar section below Research Info. Updates dynamically when checkboxes change.

| Field | Example |
|-------|---------|
| Selected | "5 / 18 studies" |
| Active Set | "WFA F 90/30 high vol" (or "—" if no set active) |
| Labels | "8 PASS, 7 MAYBE, 3 FAIL" |

**Note:** The "Active Set" field should reflect the current study sets state — focused set name when in setFocus mode, checked set names when in setCheckboxes mode.

---

## 11. Compare Set Equity Curves

### 11.1 Purpose

Allow overlaying aggregated equity curves from different study sets on the main chart for visual comparison.

### 11.2 Trigger

Add a **Compare Equity Curves** button in the Study Sets section (near the existing actions). Visible when 2+ sets have checked checkboxes.

### 11.3 Behavior

- Clicking the button loads aggregated equity curves for each checked set
- Each set's curve is rendered as a separate colored line on the main equity chart
- Colors auto-assigned from a fixed palette of 8 colors, cycling if more sets
- Chart title: "Sets Comparison (N sets)"
- Clicking a set in the legend highlights its line
- Exiting comparison mode (clicking the button again, or unchecking sets) returns to normal chart behavior

### 11.4 Data Source

Uses the same `POST /api/analytics/equity` endpoint, called once per set with that set's `study_ids`.

---

## 12. Export CSV

### 12.1 Purpose

Download the current summary table as a CSV file for external analysis.

### 12.2 Trigger

Add an **Export CSV** button in the actions area.

### 12.3 Behavior

- Exports all visible (filtered) rows
- Includes all table columns: Strategy, Study Name, WFA, IS/OOS, Ann.P%, Profit%, MaxDD%, Trades, WFE%, OOS Wins, OOS P(med), OOS WR(med), Label, Note
- Group header rows included as separator rows
- File name: `analytics_{db_name}_{date}.csv`
- Client-side generation (no backend endpoint needed)

---

## 13. Export to Global DB (Layer 3 Preview)

### 13.1 What Layer 3 Is

Layer 3 (Global Analytics) accumulates data across ALL research databases. It uses the **same UI component** as Layer 2 with additions:

| Feature | Layer 2 | Layer 3 |
|---------|---------|---------|
| Data source | Current research DB | `analytics.db` (global) |
| `research` column | No | Yes |
| Filter by research | No | Yes |
| Insights journal | No | Yes |

### 13.2 Export Mechanism

When user clicks **Export Selected to Global DB**:

1. Collect checked study_ids
2. For each study: read all fields from research DB + equity curve
3. Parse symbol, TF from csv_file_name
4. Compute auto-label at export time
5. UPSERT into `analytics.db` `runs` table
6. Show success: "Exported N studies to Global Analytics"

**UPSERT logic:** `INSERT ... ON CONFLICT(study_id) DO UPDATE`. Preserves manual labels in global DB on re-export.

### 13.3 analytics.db Schema

Location: `src/storage/global/analytics.db`

Setup on first export:
```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
conn.execute("PRAGMA foreign_keys=ON")
```

```sql
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source
    research TEXT NOT NULL,
    source_db TEXT,
    study_id TEXT UNIQUE NOT NULL,
    exported_at TEXT,

    -- Identification
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,

    -- Settings
    wfa_mode TEXT,
    is_oos TEXT,
    dataset_start_date TEXT,
    dataset_end_date TEXT,
    period_days INTEGER,

    -- Stitched OOS metrics
    profit_pct REAL,
    max_dd_pct REAL,
    total_trades INTEGER,
    winning_trades INTEGER,

    -- Study-level
    wfe_pct REAL,

    -- Window aggregates
    total_windows INTEGER,
    profitable_windows INTEGER,
    profitable_windows_pct REAL,
    worst_window_profit REAL,
    worst_window_dd REAL,
    median_window_profit REAL,
    median_window_wr REAL,

    -- Equity curve (JSON)
    equity_curve_json TEXT,
    equity_timestamps_json TEXT,

    -- Labels
    auto_label TEXT,
    label TEXT,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_research ON runs(research);
CREATE INDEX IF NOT EXISTS idx_runs_strategy ON runs(strategy);
CREATE INDEX IF NOT EXISTS idx_runs_symbol ON runs(symbol);
CREATE INDEX IF NOT EXISTS idx_runs_tf ON runs(tf);
CREATE INDEX IF NOT EXISTS idx_runs_label ON runs(label);

CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT (datetime('now')),
    research TEXT,
    scope TEXT NOT NULL,
    statement TEXT NOT NULL,
    evidence TEXT,
    action TEXT
);

CREATE INDEX IF NOT EXISTS idx_insights_scope ON insights(scope);
```

### 13.4 Research Name

Derived from the DB filename by default:
- `S01_all_tickers_feb2026.db` → `S01_all_tickers_feb2026`

In the export dialog, the user can override this name.

### 13.5 Export Button

Add **Export Selected to Global DB** button in the actions area. Disabled when no studies are checked.

---

## 14. Backend API (New Endpoints)

All existing endpoints remain unchanged. New endpoints to add:

| Endpoint | Method | Purpose | Dependencies |
|----------|--------|---------|-------------|
| `POST /api/analytics/equity` | POST | Compute aggregated portfolio equity | Section 3 |
| `POST /api/analytics/label` | POST | Save label + note for one study | Section 6 |
| `POST /api/analytics/labels/batch` | POST | Save labels for multiple studies | Section 6 |
| `POST /api/analytics/export-global` | POST | Export checked studies to analytics.db | Section 13 |

### 14.1 POST /api/analytics/equity

**Request:**
```json
{
  "study_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

**Response:**
```json
{
  "curve": [100.0, 101.2, 103.5, "..."],
  "timestamps": ["2025-01-15", "2025-01-16", "..."],
  "profit_pct": 48.6,
  "max_drawdown_pct": 19.8,
  "overlap_days": 280,
  "warning": null
}
```

If no overlap exists, `warning` contains a message string and `curve` is null.

### 14.2 POST /api/analytics/label

**Request:**
```json
{
  "study_id": "uuid-1",
  "label": "PASS",
  "note": "Best overall performer"
}
```

Saves to `studies.analytics_label` and `studies.analytics_note`.

### 14.3 POST /api/analytics/labels/batch

**Request:**
```json
{
  "labels": [
    {"study_id": "uuid-1", "label": "PASS", "note": "Best overall"},
    {"study_id": "uuid-2", "label": "MAYBE", "note": null}
  ]
}
```

### 14.4 GET /api/analytics/summary (Upgrade)

Add to each study object in the existing response:
```json
{
  "auto_label": "PASS",
  "analytics_label": null,
  "analytics_note": "Best overall"
}
```

---

## 15. Database Changes

### 15.1 New Columns in `studies` Table

```python
def _ensure_analytics_columns(conn):
    """Add analytics columns to studies table if missing."""
    cursor = conn.execute("PRAGMA table_info(studies)")
    existing = {row[1] for row in cursor.fetchall()}

    if "analytics_label" not in existing:
        conn.execute("ALTER TABLE studies ADD COLUMN analytics_label TEXT")

    if "analytics_note" not in existing:
        conn.execute("ALTER TABLE studies ADD COLUMN analytics_note TEXT")
```

Call from the existing `ensure()` entry point in `storage.py`.

### 15.2 Global DB Schema

Location: `src/storage/global/analytics.db` — see [Section 13.3](#133-analyticsdb-schema).

Add to `.gitignore`:
```
src/storage/global/
```

---

## 16. Error Handling and Edge Cases

| Scenario | Behavior | Feature |
|----------|----------|---------|
| No overlapping time range for selected studies | Warning banner above chart: "Selected studies have no overlapping time period" | Portfolio aggregation |
| Very short overlap (< 30 days) | ⚠ icon on chart with tooltip | Portfolio aggregation |
| Study missing equity curve data | Exclude from aggregation, show ⚠ icon | Portfolio aggregation |
| Empty set (all members deleted from DB) | Auto-delete set or show empty marker | Study sets |
| Heatmap cell with no study | Show "—" with neutral background | Heatmaps |
| WFE > 100% or < 0% | Show with ⚠ icon (anomaly indicator) | Conditional formatting |
| Duplicate set name | Already handled: reject with error | Study sets |
| No sets exist for comparison | Hide "Compare Equity Curves" button | Set comparison |
| Export with 0 checked studies | Disable export buttons | Export |
| Global DB does not exist yet | Create on first export | Global export |

---

## 17. Performance Considerations

| Concern | Approach |
|---------|----------|
| Portfolio aggregation | Done in Python backend; forward-fill is O(N × T) |
| Debounced equity updates | 300ms debounce on checkbox changes before calling equity endpoint |
| Heatmap computation | O(studies) — trivial |
| Set comparison metrics | Already computed in sets table; equity overlay requires one API call per set |
| Sort performance | Client-side JS `Array.sort()` — fast for < 1000 studies |
| Conditional formatting | CSS classes applied during render — no performance impact |
| Export CSV | Client-side Blob generation — no backend roundtrip |

---

## 18. Testing Plan

### Backend Tests

| Test | What to Verify |
|------|----------------|
| `test_auto_label_pass` | Study with good metrics gets PASS |
| `test_auto_label_fail` | Study with negative profit gets FAIL |
| `test_auto_label_maybe` | Borderline study gets MAYBE |
| `test_auto_label_manual_override` | Manual label preserved over auto-label |
| `test_equity_aggregation_two_studies` | Correct portfolio curve |
| `test_equity_aggregation_no_overlap` | Returns warning |
| `test_equity_aggregation_single_study` | Returns study's own curve |
| `test_equity_forward_fill` | Forward-fill produces correct step-aligned values |
| `test_label_save` | analytics_label and analytics_note persisted |
| `test_label_columns_migration` | `_ensure_analytics_columns()` adds columns to legacy DBs |
| `test_export_global_upsert` | New study inserted, existing updated |
| `test_export_global_preserves_label` | Manual label in global DB not overwritten |

### Frontend Tests (Manual)

| Test | What to Verify |
|------|----------------|
| Aggregated equity chart | Multiple studies → proper aggregated curve |
| Upgraded metric cards | Profit and MaxDD from aggregated curve when 2+ studies |
| Conditional formatting | Correct background colors for all threshold ranges |
| AVG footer row | Averages for visible studies, stays at bottom |
| Heatmaps | Correct values and colors in Symbol × TF grids |
| Label editing | Click badge → dropdown, save persists |
| Note editing | Click cell → inline edit, save persists |
| Select PASS Only | Checks only PASS-labeled visible studies |
| Label filter | Shows/hides studies by label |
| Export CSV | Downloaded file has correct columns and data |
| Compare set equity curves | Overlay multiple colored curves on chart |
| Selection Summary sidebar | Updates on checkbox change, shows label breakdown |

---

## 19. Open Questions

1. **Set metrics caching** — Recompute every time the panel opens (simpler, no stale risk). Cache only if performance becomes an issue.

2. **Heatmap multiple studies per cell** — AVG for MVP. Could add dropdown to switch between AVG/MAX/MIN later.

3. **Filter persistence** — Should filter state persist across page reloads (localStorage)? Recommendation: yes, use localStorage for filter state and last active DB.

4. **Set colors for equity comparison** — Auto-assign from a fixed palette of 8 colors, cycling if more sets.

5. **Note editing UX** — Inline input on click vs modal dialog. Recommendation: inline input.

6. **Conditional formatting toggle** — Should the user be able to disable formatting? Recommendation: not in MVP.

---

*Document version: v5 | Created: 2026-02-26 | For: Merlin Phase 3-2*
*Removed all implemented features. Removed phase structure. Aligned with current 14-column table, focus mode, study sets, multi-select filters.*
