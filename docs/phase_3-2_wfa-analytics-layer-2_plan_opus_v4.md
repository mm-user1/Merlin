# Phase 3-2: WFA Analytics Layer 2 — Implementation Plan v4

> Definitive specification for the Analytics page in Merlin.
> A developer should be able to implement Layer 2 from this document alone.
> Features are split into 3 implementation phases. Each section is tagged with its phase.

---

## Changelog

| Version | Changes |
|---------|---------|
| v2 → v3 | 7 audit fixes (analytics columns migration, DB selector reuse, dual TF/date parsers, OOS span for Ann.P%, forward-fill equity, adaptive_mode type) |
| v3 → v4 | Renamed "Research Analytics" → "Analytics". Split into 3 implementation phases. Replaced "N Selected" card with "Profitable Studies". Phase 1 simplified equity (single study curve) and metrics (SUM profit, worst MaxDD). Header checkbox added. |

---

## Table of Contents

- [1. Executive Summary](#1-executive-summary)
- [2. Page Overview](#2-page-overview)
- [3. Sidebar Sections](#3-sidebar-sections)
- [4. Main Area Components](#4-main-area-components)
- [5. Auto-Label Logic](#5-auto-label-logic)
- [6. Study Sets](#6-study-sets)
- [7. Portfolio Equity Aggregation](#7-portfolio-equity-aggregation)
- [8. Annualized Profit](#8-annualized-profit)
- [9. Column Sorting](#9-column-sorting)
- [10. Time Period Groups](#10-time-period-groups)
- [11. Conditional Formatting](#11-conditional-formatting)
- [12. Heatmaps](#12-heatmaps)
- [13. Backend API](#13-backend-api)
- [14. Frontend Architecture](#14-frontend-architecture)
- [15. Database Changes](#15-database-changes)
- [16. Export to Global DB (Layer 3 Preview)](#16-export-to-global-db-layer-3-preview)
- [17. Error Handling and Edge Cases](#17-error-handling-and-edge-cases)
- [18. Performance Considerations](#18-performance-considerations)
- [19. Testing Plan](#19-testing-plan)
- [20. Implementation Phases](#20-implementation-phases)
- [21. Open Questions](#21-open-questions)
- [22. Metric Dictionary](#22-metric-dictionary)

---

## Implementation Phase Summary

### Phase 1 — Foundation: Data Pipeline + Table + Simple Equity

| Component | What's Included |
|-----------|----------------|
| **Backend** | `/analytics` route, `GET /api/analytics/summary`, `parse_csv_filename()`, `parse_date_flexible()`, `adaptive_mode` conversion |
| **Sidebar** | DB selector (click-to-switch only), Research Info |
| **Main area** | Header ("Analytics" + DB name), Stitched OOS equity chart (single study, same style as Results page), 7 metric cards, Select All / Deselect All buttons, Header checkbox |
| **Table** | 13 columns (no Ann.P%, no Label, no Note), time period group rows with group checkboxes, row checkboxes, default sort Profit% desc (no sorting UI) |
| **Not included** | Labels, notes, sets, filters, sorting UI, conditional formatting, AVG footer, heatmaps, Ann.P%, export, Selection Summary sidebar, Sets Comparison |

### Phase 2 — Interactive Analysis: Equity Aggregation + Filters + Labels + Heatmaps

| Component | What's Included |
|-----------|----------------|
| **Backend** | `POST /api/analytics/equity` (forward-fill aggregation), `POST /api/analytics/label`, `POST /api/analytics/labels/batch`, `_ensure_analytics_columns()` migration, `oos_span_days` computation |
| **Sidebar** | Selection Summary |
| **Main area** | Aggregated portfolio equity chart (replaces single-study), upgraded metric cards (from aggregated curve), filters bar (6 dropdowns + Select PASS Only), column sorting (3-click cycle), conditional formatting, AVG footer row, heatmaps, conditional formatting legend, Export CSV |
| **Table** | +3 columns: Ann.P%, Label, Note (total 16) |

### Phase 3 — Sets + Global Export

| Component | What's Included |
|-----------|----------------|
| **Backend** | Sets CRUD (`GET/POST/DELETE/PUT /api/analytics/sets`), `study_sets`/`study_set_members` tables, `POST /api/analytics/export-global`, Global DB schema |
| **Sidebar** | Study Sets section |
| **Main area** | Sets Comparison panel (collapsible), Export Selected to Global DB button |

---

## 1. Executive Summary

**Layer 2 (Analytics)** is a new page in Merlin that shows a summary table of ALL Walk-Forward Analysis (WFA) studies in the currently active research database. It answers the question: **"Which combinations work? What if I traded only the selected ones?"**

### What Layer 2 Adds (All Phases Combined)

- Summary table of all WFA studies with 16 columns and conditional formatting
- Time period group rows (studies grouped by data date range)
- Column sorting (3-click cycle: best-first → worst-first → reset)
- Annualized profit column for cross-period comparison
- Filters (Strategy, Symbol, TF, WFA mode, IS/OOS, Label)
- Portfolio equity curve for checked studies (aggregated)
- Portfolio metrics cards (7 cards)
- Named Study Sets (persistent, saved in DB)
- Sets Comparison panel (side-by-side set metrics)
- Auto-labeling (PASS / MAYBE / FAIL)
- Heatmaps (Profit% and WFE% by Symbol × TF)
- Export to Global DB (for Layer 3)
- Save Labels (persist analytics_label and analytics_note)

### Three-Layer Architecture Context

```
Layer 1 (done)  → Single study: 7 metric cards for one WFA study
Layer 2 (this)  → Research summary: all studies in one .db
Layer 3 (later) → Global analytics: all research across all .db files
```

**Architectural invariant:** Layer 3 = Layer 2 + `research` column + insights journal. The same UI component is built once for Layer 2 and reused for Layer 3 with a different data source.

---

## 2. Page Overview

### 2.1 Purpose and Questions Answered

**Combination evaluation:**

| # | Question | Answer via | Phase |
|---|----------|-----------|-------|
| 1 | Which ticker × TF combinations are profitable? | Summary table + conditional formatting | 1 (table) + 2 (formatting) |
| 2 | Which are unprofitable? | Filter profit < 0, label = FAIL | 2 |
| 3 | Which strategy is better? | Filter by strategy | 2 |
| 4 | Fixed vs Adaptive? | Filter by WFA mode | 2 |
| 5 | Which IS/OOS is optimal? | Filter by IS/OOS | 2 |

**Portfolio questions:**

| # | Question | Answer via | Phase |
|---|----------|-----------|-------|
| 6 | What if trading ALL? | Select All → portfolio equity + metrics | 1 (simplified) → 2 (full) |
| 7 | What if only PASS? | Select PASS → recalculate | 2 |
| 8 | What if only 1h? | Filter TF=1h → checkboxes → recalculate | 2 |
| 9 | What if S01 LINK/ETH 1h? | Manual selection → recalculate | 1 |
| 10 | Combined profit/DD/trades? | Portfolio metrics for checked items | 1 |
| 11 | Compare two portfolios? | Named sets + Sets Comparison panel | 3 |

**Data quality:**

| # | Question | Answer via | Phase |
|---|----------|-----------|-------|
| 12 | Are all studies valid? | Status + window count in table | 1 |
| 13 | Anomalies? | 0 trades, DD > 50%, WFE > 100% | 1 (visible) + 2 (formatting) |
| 14 | What to redo? | Label + note | 2 |

### 2.2 Entry Point and Navigation

- **Top nav tab:** Start | Results | **Analytics**
- **URL:** `/analytics` (separate route)
- **How to get there:** Click "Analytics" tab in top nav

### 2.3 Page Layout

**Phase 1 layout:**

```
┌─ Top Nav (40px) ─────────────────────────────────────────────────────────────┐
│  Start │ Results │ Analytics (active)                                        │
├─ Sidebar (368px) ──┬─ Main Area (flex: 1) ──────────────────────────────────┤
│                    │                                                         │
│  [Database]        │  Header: "Analytics" + db name                         │
│  [Research Info]   │  Stitched OOS Equity Chart (single study)              │
│                    │  Portfolio Metrics Cards (7)                            │
│                    │  [Select All] [Deselect All]                            │
│                    │  Summary Table (group rows, 13 cols)                    │
│                    │                                                         │
└────────────────────┴─────────────────────────────────────────────────────────┘
```

**Full layout (after Phase 3):**

```
┌─ Top Nav (40px) ─────────────────────────────────────────────────────────────┐
│  Start │ Results │ Analytics (active)                                        │
├─ Sidebar (368px) ──┬─ Main Area (flex: 1) ──────────────────────────────────┤
│                    │                                                         │
│  [Database]        │  Header: "Analytics" + db name                         │
│  [Research Info]   │  Portfolio Equity Chart (aggregated)                    │
│  [Selection]       │  Portfolio Metrics Cards (7)                            │
│  [Study Sets]      │  Sets Comparison Panel (collapsible)                    │
│  [Auto-Label]      │  Filters Bar                                            │
│                    │  Summary Table (group rows, sortable, 16 cols)          │
│                    │  Conditional Formatting Legend                           │
│                    │  Heatmaps (collapsible)                                 │
│                    │  Actions Bar                                            │
│                    │                                                         │
└────────────────────┴─────────────────────────────────────────────────────────┘
```

---

## 3. Sidebar Sections

### 3.1 Database Selector `[Phase 1]`

Lists all `.db` files in `src/storage/` (excluding `global/` subdirectory). Click to switch active database and reload all data. Simplified version of the Results page DB selector — no Delete, Filter, or Select buttons.

```
┌─ Database ─────────────────────────────┐
│  S01_all_tickers_feb2026.db  ◄ active  │
│  S01_optimal_TF.db                     │
│  S01_vs_S03.db                         │
└────────────────────────────────────────┘
```

**API:** Reuses existing endpoints:
- `GET /api/databases` — list available DB files
- `POST /api/databases/active` — switch active DB

No dedicated `GET /api/analytics/databases` endpoint. The analytics page uses the same DB switching mechanism as the Results page. The active DB is shared application-wide.

**Behavior:**
- Selected DB highlighted with blue left border
- Switching DB: calls `POST /api/databases/active` then reloads all analytics data
- Active DB name shown in main area header
- Click-only interaction (no delete, filter, or other management functions)

### 3.2 Research Info `[Phase 1]`

Auto-populated from the loaded studies data. No manual input needed.

| Field | Source | Example |
|-------|--------|---------|
| Studies | Count of WFA studies in DB | "18 total (18 WFA)" |
| Strategies | Distinct strategy_id + version | "S01 v26" |
| Symbols | Count + list of distinct symbols | "6 tickers" |
| Timeframes | Distinct TFs | "30m, 1h, 4h" |
| WFA Mode | Distinct adaptive_mode values | "Fixed" or "Fixed, Adaptive" |
| IS / OOS | Distinct is_period/oos configs | "90 / 30" |
| Data Periods | Count of distinct (start, end) | "2 periods" |

### 3.3 Selection Summary `[Phase 2]`

Updates dynamically when checkboxes change.

| Field | Example |
|-------|---------|
| Selected | "5 / 18 studies" |
| Active Set | "WFA F 90/30 high vol" (or "—" if no set active) |
| Labels | "8 PASS, 7 MAYBE, 3 FAIL" |

### 3.4 Study Sets `[Phase 3]`

Persistent named groups of studies. See [Section 6](#6-study-sets) for full specification.

```
┌─ Study Sets ───────────────────────────┐
│  ● WFA F 90/30 high vol   5 studies ◄  │  ← active (blue highlight)
│  ● 1h PASS only           4 studies    │
│  ● All PASS + MAYBE      11 studies    │
│                                        │
│  [Save Selection as Set] [Delete Set]  │
└────────────────────────────────────────┘
```

### 3.5 Auto-Label Thresholds `[Phase 2]`

Collapsed by default. Shows current PASS/FAIL criteria. Read-only in MVP (configurable in future).

---

## 4. Main Area Components

### 4.1 Header `[Phase 1]`

```
Analytics  S01_all_tickers_feb2026.db
```

### 4.2 Equity Chart

#### Phase 1: Single Study Stitched OOS Equity

Displays the Stitched OOS equity curve from one selected study. Same chart style as the Results page equity chart:
- Same chart size and proportions
- Same date format on X-axis
- Same zero-equity reference line
- No percent axis (equity values, not %)
- **No WFA window markers** (unlike Results page)

**Selection behavior:**
- When 1 study is checked → show that study's stitched OOS equity curve
- When multiple studies are checked → show the **first checked** study's curve (by table order / Profit% desc)
- When 0 studies checked → empty chart placeholder
- Chart title: "Stitched OOS Equity — LINKUSDT.P 1h" (symbol + TF of displayed study)

**Data source:** Equity curve loaded from `equity_curve` and `equity_timestamps` JSON arrays in the WFA study record (same data used by Results page).

#### Phase 2: Aggregated Portfolio Equity

Replaces the single-study chart with an aggregated portfolio equity curve:
- Shows the combined equity curve for ALL checked studies
- Aggregation method: forward-fill alignment + equal-weight averaging (see [Section 7](#7-portfolio-equity-aggregation))
- Title updates dynamically: "Portfolio Equity Curve (5 selected)"
- Updates when checkbox state changes (debounced, 300ms)

### 4.3 Portfolio Metrics Cards

7 summary cards in a responsive grid (`grid-template-columns: repeat(auto-fit, minmax(130px, 1fr))`).

#### Phase 1 formulas (simplified)

When 1 study is checked, cards show that study's metrics. When multiple studies are checked, cards show aggregated values using simplified formulas:

| # | Card Label | Phase 1 Formula | Format | Color |
|---|-----------|----------------|--------|-------|
| 1 | Portfolio Profit | `SUM(profit_pct_i)` for checked studies | +XX.X% | Green if > 0, red if < 0 |
| 2 | Portfolio MaxDD | `MAX(max_dd_pct_i)` for checked studies (worst) | -XX.X% | Always red |
| 3 | Total Trades | `SUM(total_trades_i)` for checked studies | Integer | Neutral |
| 4 | Profitable | Count of checked studies with profit > 0 / total checked (%) | "10/20 (50%)" | Neutral |
| 5 | Avg OOS Wins | `AVG(profitable_windows_pct_i)` for checked studies | XX.X% | Neutral |
| 6 | Avg WFE | `AVG(wfe_i)` for checked studies | XX.X% | Neutral |
| 7 | Avg OOS P(med) | `AVG(median_window_profit_i)` for checked studies | +XX.X% | Green/red |

When 0 studies checked, all cards show "—".

#### Phase 2 upgrade

Cards 1 and 2 upgrade to use the aggregated equity curve:

| # | Card Label | Phase 2 Formula |
|---|-----------|----------------|
| 1 | Portfolio Profit | `(portfolio_curve[-1] / 100 - 1) * 100` from aggregated curve |
| 2 | Portfolio MaxDD | Peak-to-trough on aggregated equity curve |

Cards 3–7 remain unchanged.

**CRITICAL (Phase 2+):** Portfolio Profit and MaxDD are computed FROM the aggregated equity curve, NOT as SUM/AVG of individual study values.

### 4.4 Sets Comparison Panel `[Phase 3]`

Collapsible panel between metrics cards and filters bar. Starts collapsed.

```
┌─ Sets Comparison ──────────────────────────────────────────────────────────┐
│  Set Name              │ N │ Port.P% │ Port.DD% │ Trades │ Avg WFE │ OOS W │
│  ● WFA F 90/30 high vol│ 5 │ +48.6   │ -19.8    │ 310    │  28.1   │ 76.2% │
│  ● 1h PASS only        │ 4 │ +54.2   │ -22.1    │ 228    │  30.1   │ 83.3% │
│  ● All PASS + MAYBE    │11 │ +28.7   │ -26.8    │ 589    │  21.5   │ 62.4% │
│                                                                             │
│  [Compare Equity Curves]                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Columns:**

| Column | Formula |
|--------|---------|
| Set Name | Stored name + colored dot |
| N | Count of set members |
| Port.P% | From aggregated equity curve of set members |
| Port.DD% | From aggregated equity curve of set members |
| Trades | SUM(total_trades_i) for set members |
| Avg WFE | AVG(wfe_i) for set members |
| Avg OOS Wins | AVG(profitable_windows_pct_i) for set members |

**Behavior:**
- Click row → loads that set (checks its studies in main table, updates equity and metrics)
- Active set row highlighted
- [Compare Equity Curves] → overlays all set equity curves on the main chart in different colors
- Metrics computed on-demand when panel opens (not stored)
- Panel is collapsible with header click

### 4.5 Filters Bar `[Phase 2]`

**Dropdown filters:**

| Filter | Values | Source |
|--------|--------|--------|
| Strategy | All, S01 v26, S03 v10, ... | Distinct from studies |
| Symbol | All, LINKUSDT.P, ... | Distinct from studies |
| TF | All, 30m, 1h, 4h, ... | Distinct from studies |
| WFA | All, Fixed, Adaptive | Distinct from studies |
| IS/OOS | All, 90/30, 120/30, ... | Distinct from studies |
| Label | All, PASS, MAYBE, FAIL | Fixed values |

**Selection buttons:**

| Button | Phase | Behavior |
|--------|-------|----------|
| Select All | 1 | Checks all studies |
| Deselect All | 1 | Unchecks all |
| Select PASS Only | 2 | Checks only PASS-labeled visible studies |

**Filter behavior (Phase 2):**
- Filters HIDE rows that don't match (CSS `display:none`), not just uncheck
- Checkbox state persists when filters change (a hidden checked study stays checked)
- Portfolio metrics and equity include ALL checked studies (not just visible ones)
- Filter dropdowns auto-populate from actual data in the loaded studies
- Group header rows are hidden if all their children are hidden

### 4.6 Summary Table

#### 4.6.1 Column Schema

**Phase 1 columns (13):**

| # | Column | Width | Source | Description |
|---|--------|-------|--------|-------------|
| — | ☑ | 36px | UI state | Checkbox for portfolio selection |
| 1 | # | 30px | Row number | Sequential number |
| 2 | Strategy | auto | `strategy_id` + `strategy_version` | "S01 v26" |
| 3 | Symbol | auto | Parsed from `csv_file_name` | "LINKUSDT.P" |
| 4 | TF | 40px | Parsed from `csv_file_name` | "1h" |
| 5 | WFA | 50px | `adaptive_mode` | "Fixed" / "Adaptive" |
| 6 | IS/OOS | 55px | `is_period_days` + OOS config | "90/30" |
| 7 | Profit% | 70px | `stitched_oos_net_profit_pct` | Stitched OOS net profit |
| 8 | MaxDD% | 65px | `stitched_oos_max_drawdown_pct` | Stitched OOS max drawdown |
| 9 | Trades | 55px | `stitched_oos_total_trades` | Total trade count |
| 10 | WFE% | 55px | `best_value` | Walk-Forward Efficiency |
| 11 | OOS Wins | 90px | `profitable_windows`/`total_windows` | "10/12 (83%)" |
| 12 | OOS P(med) | 80px | `median_window_profit` | Median window profit |
| 13 | OOS WR(med) | 80px | `median_window_wr` | Median window win rate |

No sorting UI in Phase 1. Table is always sorted by Profit% descending within each time period group.

**Phase 2 adds 3 columns (total 16):**

| # | Column | Width | Source | Sortable | Description |
|---|--------|-------|--------|----------|-------------|
| 14 | Ann.P% | 65px | Computed: see [Section 8](#8-annualized-profit) | Yes | Annualized profit |
| 15 | Label | 60px | `analytics_label` | No | PASS / MAYBE / FAIL badge |
| 16 | Note | 120px | `analytics_note` | No | Truncated text, tooltip on hover |

Phase 2 also makes columns 7–13 sortable with the 3-click cycle.

#### 4.6.2 Header Checkbox `[Phase 1]`

The table header row includes a master checkbox in the ☑ column. It acts as a top-level toggle for all study rows:

| Header checkbox state | Meaning |
|---|---|
| ☑ Checked | All studies are checked |
| ☐ Unchecked | No studies are checked |
| ▣ Indeterminate (dash) | Some studies are checked, some not |

**Interaction:**
- Click when unchecked or indeterminate → checks ALL studies (same as Select All button)
- Click when checked → unchecks ALL studies (same as Deselect All button)

**Three-level checkbox hierarchy:**

```
☑ Header checkbox          ← controls ALL rows
  ☑ Group "2025-01-01 — 2025-11-20"  ← controls rows in this group
    ☑ Study row 1
    ☑ Study row 2
  ▣ Group "2025-05-01 — 2025-11-20"  ← indeterminate (mixed)
    ☑ Study row 3
    ☐ Study row 4
```

State changes propagate:
- **Downward:** checking/unchecking a parent checks/unchecks all children
- **Upward:** child state changes update parent to checked/unchecked/indeterminate

#### 4.6.3 AVG Footer Row `[Phase 2]`

- Shows averages for all visible (filtered) studies (not just checked)
- Styled distinctly: `#f0f0f0` background, bold, 2px top border
- Columns with averages: Profit%, MaxDD%, Trades (avg), WFE%, OOS P(med), OOS WR(med), Ann.P%
- OOS Wins shows average percentage format
- Always stays at the bottom of the table

### 4.7 Conditional Formatting Legend `[Phase 2]`

Compact grid showing color meanings. See [Section 11](#11-conditional-formatting).

### 4.8 Heatmaps `[Phase 2]`

Collapsible section with two heatmaps side by side. See [Section 12](#12-heatmaps).

### 4.9 Actions Bar

| Button | Phase | Behavior |
|--------|-------|----------|
| Export Selected to Global DB | 3 | Exports checked studies to `analytics.db` (Layer 3). See [Section 16](#16-export-to-global-db-layer-3-preview). |
| Save Labels | 2 | Saves `analytics_label` and `analytics_note` for all modified studies back to the research DB |
| Export CSV | 2 | Downloads the summary table as a CSV file |

---

## 5. Auto-Label Logic `[Phase 2]`

### 5.1 Rules

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

### 5.2 Evaluation Order

FAIL is checked first (any single FAIL condition triggers FAIL), then PASS (all conditions must be met), then MAYBE is the fallback.

### 5.3 Behavior

- Auto-label computed in Python when the summary endpoint is called
- Applied to studies that don't have a manual label override (`analytics_label IS NULL`)
- Manual labels take priority over auto-labels
- Clicking the label badge opens a dropdown: PASS / MAYBE / FAIL / Auto (reset to auto)
- [Save Labels] persists changes to `studies.analytics_label` and `studies.analytics_note`
- Thresholds are hardcoded in MVP; configurable through UI in a future phase

---

## 6. Study Sets `[Phase 3]`

### 6.1 Concept

A "Set" is a named, persistent group of study_ids. It enables:
- Quick switching between curated portfolios
- Side-by-side comparison of different portfolio compositions
- Persistent bookmarks that survive page reloads

### 6.2 Database Schema

```sql
-- In the research DB (same DB as studies table)
CREATE TABLE IF NOT EXISTS study_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS study_set_members (
    set_id INTEGER NOT NULL REFERENCES study_sets(id) ON DELETE CASCADE,
    study_id TEXT NOT NULL,
    UNIQUE(set_id, study_id)
);
```

### 6.3 Sidebar UI

```
┌─ Study Sets ───────────────────────────┐
│  ● WFA F 90/30 high vol   5 studies ◄  │  ← active (blue highlight)
│  ● 1h PASS only           4 studies    │
│  ● All PASS + MAYBE      11 studies    │
│                                        │
│  [Save Selection as Set] [Delete Set]  │
└────────────────────────────────────────┘
```

- Each set shows: colored dot, name, member count
- Click a set → check its member studies in the table, update equity and metrics
- Active set highlighted; name shown in Selection summary
- [Save Selection as Set] → prompt for name → saves currently checked study_ids
- [Delete Set] → confirm → removes set and its members

### 6.4 Interaction with Main Table

When a set is loaded:
1. All checkboxes reset (unchecked)
2. Set member study_ids are checked
3. Equity curve and portfolio metrics update
4. Chart title shows set name: "Portfolio Equity Curve (5 selected — WFA F 90/30 high vol)"
5. Profitable card shows set context

When user manually changes checkboxes after loading a set:
- Active set indicator remains (user can see which set they started from)
- But modifications are not auto-saved to the set
- User can [Save Selection as Set] to create a new set with current selection

### 6.5 API Endpoints

| Endpoint | Method | Request Body | Response |
|----------|--------|-------------|----------|
| `GET /api/analytics/sets` | GET | — | `{sets: [{id, name, description, study_ids, count}]}` |
| `POST /api/analytics/sets` | POST | `{name, study_ids: [...]}` | `{id, name, count}` |
| `DELETE /api/analytics/sets/<id>` | DELETE | — | `{ok: true}` |
| `PUT /api/analytics/sets/<id>` | PUT | `{name?, study_ids?}` | `{ok: true}` |

---

## 7. Portfolio Equity Aggregation `[Phase 2]`

### 7.1 Data Source

Each WFA study has a stitched OOS equity curve stored as JSON arrays:
- `equity_curve`: `[100.0, 102.5, 101.8, ...]` (values starting from 100)
- `equity_timestamps`: `["2025-01-15T00:00:00", "2025-01-16T00:00:00", ...]`

In Phase 1, these are loaded directly for the single-study chart display.
In Phase 2, they are used for aggregation.

### 7.2 Algorithm

Uses forward-fill (last-observation-carried-forward / LOCF) instead of linear interpolation. Linear interpolation creates phantom intermediate values that distort MaxDD calculations. Forward-fill preserves the step-like nature of equity curves (values only change at actual trade events).

```python
def aggregate_equity_curves(selected_studies):
    """
    Aggregate multiple equity curves into a single portfolio curve.
    Uses equal-weight averaging over the common time intersection.
    Alignment via forward-fill (LOCF), NOT linear interpolation.
    """
    if len(selected_studies) == 0:
        return None  # empty state

    if len(selected_studies) == 1:
        return selected_studies[0]  # single study, no aggregation

    # 1. Find common time range (intersection)
    t_start = max(study.timestamps[0] for study in selected_studies)
    t_end = min(study.timestamps[-1] for study in selected_studies)

    if t_start >= t_end:
        return None  # no overlap — show warning

    # 2. Build common timestamp grid
    #    Use the finest-grained timestamp set within [t_start, t_end]
    #    Or: generate uniform grid at 1-day intervals
    common_ts = generate_daily_grid(t_start, t_end)

    # 3. For each study, align equity at common timestamps using FORWARD-FILL
    #    For each common timestamp, use the LAST KNOWN equity value at or before
    #    that timestamp. This preserves step-like equity behavior and avoids
    #    phantom values that linear interpolation would create.
    #    Normalize: each curve starts at 100.0 at t_start
    aligned_curves = []
    for study in selected_studies:
        curve = forward_fill(study.timestamps, study.equity_curve, common_ts)
        # Normalize to 100 at t_start
        start_val = curve[0]
        normalized = [v / start_val * 100.0 for v in curve]
        aligned_curves.append(normalized)

    # 4. Compute portfolio: equal-weight average
    portfolio = []
    for i in range(len(common_ts)):
        avg = sum(curve[i] for curve in aligned_curves) / len(aligned_curves)
        portfolio.append(avg)

    # 5. Compute portfolio metrics
    portfolio_profit = (portfolio[-1] / 100.0 - 1) * 100
    portfolio_maxdd = compute_max_drawdown(portfolio)

    return {
        'curve': portfolio,
        'timestamps': common_ts,
        'profit_pct': portfolio_profit,
        'max_drawdown_pct': portfolio_maxdd
    }


def forward_fill(src_timestamps, src_values, target_timestamps):
    """
    Align src_values to target_timestamps using forward-fill (LOCF).
    For each target timestamp, returns the last src value at or before it.
    """
    result = []
    j = 0  # pointer into src_timestamps
    last_val = src_values[0]
    for t in target_timestamps:
        while j < len(src_timestamps) and src_timestamps[j] <= t:
            last_val = src_values[j]
            j += 1
        result.append(last_val)
    return result
```

### 7.3 Max Drawdown Computation

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

### 7.4 Time Range Rule

**MVP: intersection only.**

Only the common period present in ALL selected studies is used. Studies must have overlapping OOS periods for aggregation to work.

| Scenario | Behavior |
|----------|----------|
| All studies overlap fully | Full aggregation |
| Partial overlap | Only overlapping portion used |
| No overlap | Warning: "No common time range" |
| Short overlap (< 30 days) | Warning icon on chart |

### 7.5 Computation Location

- **Backend** (`POST /api/analytics/equity`): accepts `study_ids`, returns aggregated curve + metrics
- Why backend: equity curves can be large; Python has proper forward-fill logic; avoids sending all raw curves to frontend
- Frontend sends checked study_ids, receives ready-to-plot result

---

## 8. Annualized Profit `[Phase 2]`

### 8.1 Purpose

Enables comparison of studies with different data periods. A study earning +42% over 204 OOS days annualizes differently than +72% over 324 OOS days.

### 8.2 Formula

```
ann_profit_pct = ((1 + profit_pct / 100) ^ (365 / oos_span_days) - 1) * 100
```

`oos_span_days` is the OOS time span, NOT the full dataset span.

- `dataset_start_date` / `dataset_end_date` in the `studies` table represent the FULL data range (including IS warmup period), which is larger than the actual OOS trading period.
- The correct span for annualization is from the **first OOS window start** to the **last OOS window end**.

**How `oos_span_days` is derived:**

The equity curve timestamps already represent the OOS-only timeline (they are stitched from OOS windows only). Therefore:

```python
oos_span_days = (equity_timestamps[-1] - equity_timestamps[0]).days
```

This is computed by the backend in the summary endpoint (Phase 2 only) and returned as a field per study.

### 8.3 Examples

| Profit% | OOS Span Days | Ann.P% | Calculation |
|---------|--------------|--------|-------------|
| +72.8 | 264 | +107.5 | `((1.728)^(365/264) - 1) * 100` |
| +42.3 | 174 | +108.2 | `((1.423)^(365/174) - 1) * 100` |
| -15.2 | 264 | -20.8 | `((0.848)^(365/264) - 1) * 100` |
| -12.8 | 174 | -25.5 | `((0.872)^(365/174) - 1) * 100` |

*Note: OOS span days are shorter than dataset days because IS warmup is excluded.*

### 8.4 Implementation

- `oos_span_days` is computed in **Python** by the summary endpoint from `equity_timestamps`
- Ann.P% is computed in **JavaScript** on the frontend using the `oos_span_days` field (not stored in DB)
- Same conditional formatting as Profit% column

Do NOT use `dataset_start_date` / `dataset_end_date` for annualization. These include the IS period and would understate the annualized return.

### 8.5 Short Period Warning

If `oos_span_days < 90`:
- Show ⚠ icon next to the annualized value
- Tooltip: "Short OOS period (N days) — annualized value may be misleading"
- Reason: +20% in 30 days annualizes to +791%, which is not meaningful

### 8.6 Edge Cases

| Scenario | Behavior |
|----------|----------|
| oos_span_days = 0 | Show "N/A" |
| oos_span_days = 365 | Ann.P% = Profit% (no change) |
| profit_pct = 0 | Ann.P% = 0 |
| Very short OOS period (< 30 days) | Show value with ⚠⚠ double warning |
| No equity_timestamps available | Show "N/A", log warning |

---

## 9. Column Sorting `[Phase 2]`

### 9.1 Sortable Columns

Profit%, MaxDD%, Trades, WFE%, OOS Wins, OOS P(med), OOS WR(med), Ann.P%

Non-sortable: checkbox, #, Strategy, Symbol, TF, WFA, IS/OOS, Label, Note

### 9.2 Three-Click Cycle

| Click | Action | Arrow |
|-------|--------|-------|
| 1st | Sort "best first" | ▼ for most columns, ▲ for MaxDD |
| 2nd | Sort "worst first" | Reversed |
| 3rd | Reset to default (Profit% desc) | — |

**"Best first" direction:**

| Column | Best First = | Arrow |
|--------|-------------|-------|
| Profit% | Descending (highest first) | ▼ |
| MaxDD% | Ascending (lowest first) | ▲ |
| Trades | Descending (most first) | ▼ |
| WFE% | Descending (highest first) | ▼ |
| OOS Wins | Descending (highest % first) | ▼ |
| OOS P(med) | Descending (highest first) | ▼ |
| OOS WR(med) | Descending (highest first) | ▼ |
| Ann.P% | Descending (highest first) | ▼ |

### 9.3 Visual Indicator

- Active sort column header has a visible arrow (▲ or ▼) and a highlight color
- Inactive sortable columns show a dimmed arrow on hover only
- Default sort (on page load): Profit% descending

### 9.4 Sort Within Groups

**Sorting happens WITHIN each time-period group, not across groups.** Rows do not move between groups. Group order is always by start_date ascending.

The AVG footer row always stays at the very bottom.

### 9.5 Sort Key Extraction

For OOS Wins column (`"10/12 (83%)"`), sort by the percentage value (83).

---

## 10. Time Period Groups `[Phase 1]`

### 10.1 Concept

Studies are grouped by their data date range (`dataset_start_date`, `dataset_end_date`). Each group has a separator row in the table.

### 10.2 Group Row Format

```
☑ │ 2025-01-01 — 2025-11-20 (324 days) │                           12 studies
```

- Spans all columns (using colspan)
- Checkbox toggles all studies in the group
- Shows start date, end date, duration in days, study count
- Background: `#e8e8e8` with 2px top border

### 10.3 Grouping Logic

```python
# Group key: (dataset_start_date, dataset_end_date)
groups = {}
for study in studies:
    key = (study.dataset_start_date, study.dataset_end_date)
    groups.setdefault(key, []).append(study)

# Sort groups by start_date ascending, then end_date ascending
sorted_groups = sorted(groups.items(), key=lambda x: (x[0][0], x[0][1]))
```

### 10.4 Duration Calculation

The `_format_date()` function in `storage.py` uses `strftime("%Y-%m-%d")` with hyphens. The date parser must handle both hyphen and dot formats for robustness.

```python
from datetime import datetime

def parse_date_flexible(date_str):
    """Parse date string in either '%Y-%m-%d' (hyphen) or '%Y.%m.%d' (dot) format."""
    for fmt in ("%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str!r} (expected YYYY-MM-DD or YYYY.MM.DD)")

def period_days(start_str, end_str):
    """Calculate days between two date strings."""
    start = parse_date_flexible(start_str)
    end = parse_date_flexible(end_str)
    return (end - start).days
```

**Display format:** Group rows display dates using the format stored in the DB (typically `YYYY-MM-DD` from `_format_date()`).

### 10.5 Group Checkbox Behavior

| Action | Result |
|--------|--------|
| Check group checkbox | All studies in group become checked |
| Uncheck group checkbox | All studies in group become unchecked |
| Check/uncheck individual study | Group checkbox shows indeterminate (—) if mixed, checked if all, unchecked if none |

### 10.6 Single Period Optimization

If ALL studies in the DB share the same date range, there is only one group. The group row is still shown (for consistency and to display the date range), but visually it's less prominent.

---

## 11. Conditional Formatting `[Phase 2]`

### 11.1 Cell Background Colors

| Metric | Strong Green `#c6efce` | Light Green `#e2f0d9` | Yellow `#fff9e6` | Light Red `#fce4ec` | Strong Red `#f8d7da` |
|--------|----------------------|---------------------|-----------------|-------------------|---------------------|
| Profit% | > +30 | 0 .. +30 | — | — | < 0 |
| Ann.P% | > +30 | 0 .. +30 | — | — | < 0 |
| MaxDD% | < 20 | — | 20 — 35 | — | > 35 |
| WFE% | > 20 | — | 10 — 20 | — | < 10 |
| OOS Wins % | > 70% | — | 40% — 70% | — | < 40% |
| OOS P(med) | > +5 | 0 .. +5 | — | — | < 0 |

### 11.2 Text Colors

| Condition | Color | Hex |
|-----------|-------|-----|
| Positive values (profit, OOS P) | Green | `#27ae60` |
| Negative values | Red | `#e74c3c` |
| Warning range (MaxDD 20-35) | Orange | `#e67e22` |
| Neutral | Default text | `#2a2a2a` |

### 11.3 Label Badges

| Label | Background | Text | Border |
|-------|-----------|------|--------|
| PASS | `#d4edda` | `#155724` | `#8fd19e` |
| MAYBE | `#fff3cd` | `#856404` | `#ffc107` |
| FAIL | `#f8d7da` | `#721c24` | `#f1aeb5` |

---

## 12. Heatmaps `[Phase 2]`

### 12.1 Types

| Heatmap | Rows | Columns | Cell Value |
|---------|------|---------|------------|
| Profit% by Symbol × TF | Symbols | Timeframes | `stitched_oos_net_profit_pct` |
| WFE% by Symbol × TF | Symbols | Timeframes | `best_value` (WFE) |

### 12.2 Cell Colors (Threshold-Based)

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

### 12.3 AVG Rows and Columns

- Last row: AVG per TF (across all symbols)
- Last column: AVG per Symbol (across all TFs)
- Cells with no data show "—"

### 12.4 Multiple Studies Per Cell

If multiple studies map to the same Symbol × TF (e.g., from different time periods or different IS/OOS settings), show AVG in the cell.

### 12.5 Filter Interaction

Heatmaps respect active filters (except Symbol and TF filters which define the axes). If the user filters to WFA=Fixed only, the heatmap shows only Fixed studies.

### 12.6 Collapsible

Section starts expanded. Click header to collapse/expand.

---

## 13. Backend API

### 13.1 Endpoints by Phase

**Existing endpoints reused (no new code):**
- `GET /api/databases` — list available DB files
- `POST /api/databases/active` — switch active DB

**Phase 1:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /analytics` | GET | Serve Analytics page |
| `GET /api/analytics/summary` | GET | Summary data (studies + research_info, no labels/oos_span_days) |

**Phase 2:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/analytics/equity` | POST | Compute aggregated portfolio equity |
| `POST /api/analytics/label` | POST | Save label + note for one study |
| `POST /api/analytics/labels/batch` | POST | Save labels for multiple studies |

Phase 2 also upgrades `GET /api/analytics/summary` to include `auto_label`, `analytics_label`, `analytics_note`, and `oos_span_days` fields.

**Phase 3:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/analytics/export-global` | POST | Export selected studies to analytics.db |
| `GET /api/analytics/sets` | GET | List all sets |
| `POST /api/analytics/sets` | POST | Create set |
| `DELETE /api/analytics/sets/<id>` | DELETE | Delete set |
| `PUT /api/analytics/sets/<id>` | PUT | Update set |

### 13.2 GET /api/analytics/summary

Returns all data needed to render the analytics page. Uses the currently active DB (no `?db=` parameter).

**Phase 1 response:**

```json
{
  "db_name": "S01_all_tickers_feb2026.db",
  "studies": [
    {
      "study_id": "uuid-...",
      "strategy": "S01 v26",
      "symbol": "LINKUSDT.P",
      "tf": "1h",
      "wfa_mode": "Fixed",
      "is_oos": "90/30",
      "dataset_start_date": "2025-01-01",
      "dataset_end_date": "2025-11-20",
      "profit_pct": 72.8,
      "max_dd_pct": 22.3,
      "total_trades": 89,
      "winning_trades": 52,
      "wfe_pct": 32.1,
      "total_windows": 12,
      "profitable_windows": 10,
      "profitable_windows_pct": 83.3,
      "median_window_profit": 14.2,
      "median_window_wr": 64.8,
      "has_equity_curve": true
    }
  ],
  "research_info": {
    "total_studies": 18,
    "wfa_studies": 18,
    "strategies": ["S01 v26"],
    "symbols": ["LINKUSDT.P", "ETHUSDT.P", "..."],
    "timeframes": ["30m", "1h", "4h"],
    "wfa_modes": ["Fixed"],
    "is_oos_periods": ["90/30"],
    "data_periods": [
      {"start": "2025-01-01", "end": "2025-11-20", "days": 324, "count": 12},
      {"start": "2025-05-01", "end": "2025-11-20", "days": 204, "count": 6}
    ]
  }
}
```

**Phase 2 additions to each study object:**

```json
{
  "oos_span_days": 264,
  "auto_label": "PASS",
  "analytics_label": null,
  "analytics_note": "Best overall"
}
```

**Phase 3 additions to response:**

```json
{
  "sets": [
    {"id": 1, "name": "WFA F 90/30 high vol", "study_ids": ["uuid-1", "..."], "count": 5}
  ]
}
```

**Key field conversions:**

| Field | Source | Notes |
|-------|--------|-------|
| `wfa_mode` | `adaptive_mode` column (INTEGER) | Converted in Python: `"Fixed" if row.adaptive_mode == 0 else "Adaptive"` |
| `oos_span_days` | `equity_timestamps` JSON array (Phase 2) | `(timestamps[-1] - timestamps[0]).days`. NOT from `dataset_start_date`/`dataset_end_date` |
| `dataset_start_date` | `studies.dataset_start_date` | Full dataset start (includes IS). Used for time period grouping only, NOT for annualization |
| `dataset_end_date` | `studies.dataset_end_date` | Full dataset end. Used for time period grouping only, NOT for annualization |

**Note on equity curves:** The summary endpoint does NOT include equity curves inline (they can be large). In Phase 1, equity curves are loaded individually for the selected study. In Phase 2, they are loaded via `POST /api/analytics/equity`.

### 13.3 Phase 1: Single Study Equity Loading

For the Phase 1 single-study chart, the equity curve data needs to be loaded for the checked study. Two options:

**Option A (recommended):** Include `equity_curve` and `equity_timestamps` in the summary response only for studies that have them (`has_equity_curve: true`). For typical research DBs with < 50 WFA studies, this is feasible.

**Option B:** Add a lightweight endpoint `GET /api/analytics/study/<study_id>/equity` that returns just one study's curve. More work but cleaner separation.

Recommendation: Option A for Phase 1 simplicity. The data is already in the DB and study count is typically small. Phase 2 replaces this with the aggregated equity endpoint.

### 13.4 POST /api/analytics/equity `[Phase 2]`

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
  "total_trades": 310,
  "avg_oos_wins": 76.2,
  "avg_wfe": 28.1,
  "avg_oos_profit_med": 11.5,
  "overlap_days": 280,
  "warning": null
}
```

If no overlap exists, `warning` contains a message string and `curve` is null.

### 13.5 POST /api/analytics/label `[Phase 2]`

**Request:**
```json
{
  "study_id": "uuid-1",
  "label": "PASS",
  "note": "Best overall performer"
}
```

Saves to `studies.analytics_label` and `studies.analytics_note` in the research DB.

### 13.6 POST /api/analytics/labels/batch `[Phase 2]`

**Request:**
```json
{
  "labels": [
    {"study_id": "uuid-1", "label": "PASS", "note": "Best overall"},
    {"study_id": "uuid-2", "label": "MAYBE", "note": null}
  ]
}
```

### 13.7 Symbol and TF Parsing `[Phase 1]`

Symbol and TF are parsed from `csv_file_name`. The Merlin convention:

```
OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv
     ^symbol^   ^TF^
```

- Symbol: between first `_` and `,`
- TF: number after `, ` — convert minutes to human-readable:
  - 1 → "1m", 5 → "5m", 15 → "15m", 30 → "30m"
  - 60 → "1h", 120 → "2h", 240 → "4h"
  - 1440 → "1D"

The parser also handles human-readable TF strings (e.g., `1h`, `4h`) that may appear in some CSV filenames, matching the existing JS `parseTimeframeToMinutes()` in `results-controller.js` (lines 28-41).

```python
import re

def parse_csv_filename(csv_file_name):
    """Extract symbol and timeframe from Merlin CSV filename.

    Handles both numeric TF (e.g., '15' for 15m) and
    human-readable TF (e.g., '1h', '4h') formats.
    """
    if not csv_file_name:
        return None, None

    # Try numeric TF first: "OKX_LINKUSDT.P, 15 2025.05.01-..."
    m = re.match(r'^[^_]*_([^,]+),\s*(\d+)\s', csv_file_name)
    if m:
        symbol = m.group(1).strip()
        tf_minutes = int(m.group(2))
        tf_map = {1: "1m", 5: "5m", 15: "15m", 30: "30m",
                  60: "1h", 120: "2h", 240: "4h", 1440: "1D"}
        tf = tf_map.get(tf_minutes, f"{tf_minutes}m")
        return symbol, tf

    # Try human-readable TF: "OKX_LINKUSDT.P, 1h 2025.05.01-..."
    m = re.match(r'^[^_]*_([^,]+),\s*(\d+[mhdwMHDW])\s', csv_file_name)
    if m:
        symbol = m.group(1).strip()
        tf_raw = m.group(2).lower()
        # Normalize: "60m" → "1h", "240m" → "4h", etc.
        tf = _normalize_tf(tf_raw)
        return symbol, tf

    return None, None


def _normalize_tf(tf_str):
    """Normalize timeframe string to canonical form."""
    # Already in h/d/w format
    if tf_str[-1] in ('h', 'd', 'w'):
        return tf_str

    # Minutes — convert to higher unit if applicable
    if tf_str[-1] == 'm':
        minutes = int(tf_str[:-1])
        if minutes >= 1440 and minutes % 1440 == 0:
            return f"{minutes // 1440}D"
        if minutes >= 60 and minutes % 60 == 0:
            return f"{minutes // 60}h"
        return tf_str

    return tf_str
```

Date strings in `csv_file_name` use dot format (`2025.05.01`) while `_format_date()` in `storage.py` writes hyphen format (`2025-05-01`). Both formats are handled by `parse_date_flexible()` (see [Section 10.4](#104-duration-calculation)).

---

## 14. Frontend Architecture

### 14.1 New Files

| File | Phase | Purpose |
|------|-------|---------|
| `templates/analytics.html` | 1 | HTML template for the analytics page |
| `static/js/analytics.js` | 1 | Main controller: init, load data, event binding |
| `static/js/analytics-table.js` | 1 | Table rendering, group rows, checkboxes |
| `static/js/analytics-equity.js` | 1 | Equity chart rendering (single study in P1, aggregated in P2) |
| `static/js/analytics-filters.js` | 2 | Filter dropdowns, Select PASS Only |
| `static/js/analytics-heatmap.js` | 2 | Heatmap rendering |
| `static/js/analytics-sets.js` | 3 | Sets management (create, delete, load, compare) |

### 14.2 State Management

```javascript
const AnalyticsState = {
  // Data
  dbName: '',
  studies: [],               // all studies from summary API
  researchInfo: null,        // research metadata

  // UI state — Phase 1
  checkedStudyIds: new Set(), // currently checked study_ids

  // Sort state — Phase 1 (fixed), Phase 2 (interactive)
  sortColumn: 'profit_pct',  // current sort column key
  sortDirection: 'desc',      // 'asc' | 'desc'
  sortClicks: 1,              // Phase 2: 1, 2, or 3 (for 3-click cycle)

  // Phase 2 additions
  filteredStudies: [],        // after applying dropdown filters
  filters: {
    strategy: 'All',
    symbol: 'All',
    tf: 'All',
    wfa: 'All',
    isOos: 'All',
    label: 'All'
  },
  portfolioResult: null,      // aggregated equity result from API

  // Phase 3 additions
  sets: [],                   // saved sets
  activeSetId: null,          // currently loaded set id (or null)
  setMetrics: {}              // cached set metrics by set_id
};
```

### 14.3 Event Flow

**Phase 1:**

```
Page Load
  → GET /api/analytics/summary
  → Populate AnalyticsState (studies, researchInfo)
  → Render sidebar (DB list, research info)
  → Render table (group rows, data rows, sorted by Profit% desc)
  → Default: no studies checked, empty chart

User checks study (individual / group / header checkbox)
  → Update AnalyticsState.checkedStudyIds
  → Update checkbox hierarchy (propagate up/down)
  → If 1+ studies checked: show first checked study's equity curve
  → Compute simplified portfolio metrics cards
  → If 0 checked: clear chart, show "—" on all cards

User clicks Select All / Deselect All
  → Check/uncheck all studies
  → Same update flow as above

User clicks DB in sidebar
  → POST /api/databases/active
  → GET /api/analytics/summary
  → Reset all state, re-render
```

**Phase 2 adds:**

```
User clicks filter dropdown
  → Update AnalyticsState.filters
  → Recompute filteredStudies (hide/show rows)
  → Update AVG footer row
  → Group rows hidden if all children hidden

User clicks column header
  → Update sort state (3-click cycle)
  → Re-sort rows within each group
  → Re-render table body

User checks studies (upgraded)
  → POST /api/analytics/equity with checked study_ids
  → Render aggregated equity chart + upgraded metrics cards

User clicks Save Labels
  → Collect all modified labels/notes
  → POST /api/analytics/labels/batch
  → Show success notification
```

**Phase 3 adds:**

```
User clicks set in sidebar
  → Load set: check member studies, update equity + metrics
  → Update activeSetId
```

### 14.4 HTML Template

Separate template at `templates/analytics.html`. Shares the same CSS file (`style.css`) with the other pages, plus analytics-specific styles.

The top nav renders all three tabs. The active tab is determined by the current URL.

---

## 15. Database Changes

### 15.1 New Tables in Research DB `[Phase 3]`

```sql
CREATE TABLE IF NOT EXISTS study_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS study_set_members (
    set_id INTEGER NOT NULL REFERENCES study_sets(id) ON DELETE CASCADE,
    study_id TEXT NOT NULL,
    UNIQUE(set_id, study_id)
);
```

Added via the idempotent migration pattern already used in `storage.py` (create table IF NOT EXISTS).

### 15.2 New Columns in `studies` Table `[Phase 2]`

The columns `analytics_label` and `analytics_note` do NOT currently exist in the `studies` table schema. They must be added via an `ensure()` migration in `storage.py`.

```python
# In storage.py — add to the ensure() migration section
# (follows the existing pattern of ALTER TABLE ... ADD COLUMN)

def _ensure_analytics_columns(conn):
    """Add analytics columns to studies table if missing."""
    cursor = conn.execute("PRAGMA table_info(studies)")
    existing = {row[1] for row in cursor.fetchall()}

    if "analytics_label" not in existing:
        conn.execute("ALTER TABLE studies ADD COLUMN analytics_label TEXT")

    if "analytics_note" not in existing:
        conn.execute("ALTER TABLE studies ADD COLUMN analytics_note TEXT")
```

This function should be called from the existing `ensure()` entry point so that it runs automatically when the DB is first opened.

### 15.3 Existing Columns Used (Already Present from Layer 1) `[Phase 1]`

| Column | Type | Used For |
|--------|------|----------|
| `stitched_oos_net_profit_pct` | REAL | Profit% |
| `stitched_oos_max_drawdown_pct` | REAL | MaxDD% |
| `stitched_oos_total_trades` | INTEGER | Trades |
| `stitched_oos_winning_trades` | INTEGER | Winning trades (not shown in table but available) |
| `best_value` | REAL | WFE% |
| `profitable_windows` | INTEGER | OOS Wins numerator |
| `total_windows` | INTEGER | OOS Wins denominator |
| `stitched_oos_win_rate` | REAL | OOS Wins % |
| `median_window_profit` | REAL | OOS P(med) |
| `median_window_wr` | REAL | OOS WR(med) |
| `worst_window_profit` | REAL | Filtering (not shown) |
| `worst_window_dd` | REAL | Filtering (not shown) |
| `dataset_start_date` | TEXT | Time period grouping (NOT for annualization) |
| `dataset_end_date` | TEXT | Time period grouping (NOT for annualization) |
| `csv_file_name` | TEXT | Symbol + TF parsing |
| `strategy_id` | TEXT | Strategy column |
| `strategy_version` | TEXT | Strategy column |
| `is_period_days` | INTEGER | IS/OOS column |
| `adaptive_mode` | **INTEGER DEFAULT 0** | WFA column. Convert in API: `"Fixed" if row.adaptive_mode == 0 else "Adaptive"` |

### 15.4 Global DB (for Layer 3 export) `[Phase 3]`

Location: `src/storage/global/analytics.db`

Setup on first export:
```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
conn.execute("PRAGMA foreign_keys=ON")
```

Schema: see [Section 16.3](#163-analyticsdb-schema).

---

## 16. Export to Global DB (Layer 3 Preview) `[Phase 3]`

### 16.1 What Layer 3 Is

Layer 3 (Global Analytics) is a future feature that accumulates data across ALL research databases. It uses the **same UI component** as Layer 2 with additions:

| Feature | Layer 2 | Layer 3 |
|---------|---------|---------|
| Data source | Current research DB | `analytics.db` (global) |
| `research` column | No | Yes |
| Filter by research | No | Yes |
| Insights journal | No | Yes |
| Export button | Export to Global DB | No (final destination) |

**Invariant:** Layer 3 = Layer 2 + research column + insights journal. One UI component, two data sources.

### 16.2 Export Mechanism

When user clicks [Export Selected to Global DB]:

1. Collect checked study_ids
2. For each study: read all fields from research DB + equity curve
3. Parse symbol, TF from csv_file_name
4. Compute auto-label at export time
5. UPSERT into `analytics.db` `runs` table
6. Show success: "Exported N studies to Global Analytics"

**UPSERT logic:** `INSERT ... ON CONFLICT(study_id) DO UPDATE`. This preserves manual labels in the global DB on re-export (only auto-computed fields are updated).

### 16.3 analytics.db Schema

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

### 16.4 Research Name

Derived from the DB filename by default:
- `S01_all_tickers_feb2026.db` → `S01_all_tickers_feb2026`

In the export dialog, the user can override this name.

---

## 17. Error Handling and Edge Cases

| Scenario | Behavior | Phase |
|----------|----------|-------|
| DB has 0 WFA studies | Empty state: "No WFA studies found in this database" | 1 |
| DB has only Optuna studies | Message: "Analytics requires WFA studies. This database contains only Optuna studies." | 1 |
| Study missing equity curve data | Phase 1: skip chart for that study. Phase 2: exclude from aggregation, show ⚠ icon | 1, 2 |
| No overlapping time range for selected studies | Warning banner above chart: "Selected studies have no overlapping time period" | 2 |
| Very short overlap (< 30 days) | ⚠ icon on chart with tooltip | 2 |
| oos_span_days < 90 for Ann.P% | ⚠ icon on Ann.P% value | 2 |
| oos_span_days = 0 or no equity_timestamps | Ann.P% shows "N/A" | 2 |
| CSV file missing | Study still shown (metrics stored in DB), file indicator dimmed | 1 |
| Empty set (all members deleted from DB) | Auto-delete set or show empty marker | 3 |
| Duplicate set name | Reject with error: "A set with this name already exists" | 3 |
| WFE > 100% or < 0% | Show with ⚠ icon (anomaly indicator) | 1 (visible) + 2 (formatted) |
| Total trades = 0 | Show "0" in Trades, mark as anomaly | 1 |
| No sets exist | "Study Sets" section shows "No sets saved" + [Save Selection as Set] button only | 3 |
| All studies have same date range | Single group row shown | 1 |
| Heatmap cell with no study | Show "—" with neutral background | 2 |
| Date format mismatch | `parse_date_flexible()` handles both `YYYY-MM-DD` and `YYYY.MM.DD` | 1 |

---

## 18. Performance Considerations

| Concern | Approach | Phase |
|---------|----------|-------|
| Summary query speed | Single SQL query, no joins to wfa_windows needed | 1 |
| Equity curve loading (Phase 1) | Included in summary for single-study display; typically < 50 studies | 1 |
| Equity curve loading (Phase 2) | Loaded on-demand via separate equity endpoint | 2 |
| Portfolio aggregation | Done in Python backend; forward-fill is O(N × T) | 2 |
| Many studies (> 100) | Table renders fine up to ~500 rows | 1 |
| Sort performance | Client-side JS `Array.sort()` — fast for < 1000 studies | 2 |
| Heatmap computation | O(studies) — trivial | 2 |
| Set comparison metrics | Requires one equity aggregation per set; compute sequentially | 3 |
| Debounced equity updates | 300ms debounce on checkbox changes | 2 |
| `oos_span_days` computation | Parse only first/last timestamps (not full array) | 2 |

---

## 19. Testing Plan

### 19.1 Phase 1 Tests

**Backend:**

| Test | What to Verify |
|------|----------------|
| `test_analytics_summary` | Returns correct WFA studies with all fields |
| `test_analytics_summary_empty_db` | Returns empty array, no error |
| `test_analytics_summary_optuna_only` | Returns empty array with message |
| `test_symbol_tf_parsing_numeric` | Correct extraction from `OKX_LINKUSDT.P, 15 ...` |
| `test_symbol_tf_parsing_human` | Correct extraction from `OKX_LINKUSDT.P, 1h ...` |
| `test_period_days_calculation` | Correct duration from date strings (both formats) |
| `test_date_parser_hyphen` | `parse_date_flexible("2025-01-01")` works |
| `test_date_parser_dot` | `parse_date_flexible("2025.01.01")` works |
| `test_adaptive_mode_conversion` | INTEGER 0 → "Fixed", 1 → "Adaptive" |

**Frontend (manual):**

| Test | What to Verify |
|------|----------------|
| Page loads with data | Table populated, research info correct |
| Table group rows | Groups visible, correct dates and study counts |
| Checkbox hierarchy | Header ↔ group ↔ individual propagation |
| Select All / Deselect All | All checkboxes toggle |
| Single study equity chart | Chart displays selected study's stitched OOS curve |
| Multiple studies → first study chart | Chart shows first checked study |
| Metric cards (1 study) | Shows that study's metrics |
| Metric cards (multiple) | SUM profit, worst MaxDD, SUM trades, profitable count |
| DB switching | Reloads data correctly |
| Default sort | Studies sorted by Profit% desc within groups |

### 19.2 Phase 2 Tests

**Backend:**

| Test | What to Verify |
|------|----------------|
| `test_auto_label_pass` | Study with good metrics gets PASS |
| `test_auto_label_fail` | Study with negative profit gets FAIL |
| `test_auto_label_maybe` | Borderline study gets MAYBE |
| `test_auto_label_manual_override` | Manual label preserved |
| `test_equity_aggregation_two_studies` | Correct portfolio curve |
| `test_equity_aggregation_no_overlap` | Returns warning |
| `test_equity_aggregation_single_study` | Returns study's own curve |
| `test_equity_forward_fill` | Forward-fill produces correct step-aligned values |
| `test_label_save` | analytics_label and analytics_note persisted |
| `test_label_columns_migration` | `_ensure_analytics_columns()` adds columns to legacy DBs |
| `test_oos_span_days` | Computed from equity_timestamps, not dataset dates |

**Frontend (manual):**

| Test | What to Verify |
|------|----------------|
| Aggregated equity chart | Multiple studies → proper aggregated curve |
| Upgraded metric cards | Profit and MaxDD from aggregated curve |
| Column sorting | 3-click cycle works, sorts within groups |
| Filter dropdowns | Hide/show rows correctly, AVG updates |
| Select PASS Only | Checks only PASS-labeled visible studies |
| Ann.P% values | Correct annualized values using OOS span, ⚠ for short periods |
| Conditional formatting | Correct colors for all threshold ranges |
| Heatmaps | Correct values and colors |
| Label editing | Click badge → dropdown, save persists |

### 19.3 Phase 3 Tests

**Backend:**

| Test | What to Verify |
|------|----------------|
| `test_set_crud` | Create, read, delete sets |
| `test_set_duplicate_name` | Rejects duplicate name |
| `test_export_global_upsert` | New study inserted, existing updated |
| `test_export_global_preserves_label` | Manual label in global DB not overwritten |

**Frontend (manual):**

| Test | What to Verify |
|------|----------------|
| Set save | Creates set with current selection |
| Set load | Click set → correct studies checked |
| Set delete | Removes set |
| Sets comparison panel | Shows per-set metrics, click loads set |
| Compare Equity Curves | Overlays all set curves |
| Export to Global DB | Studies exported to analytics.db |

---

## 20. Implementation Phases

### Phase 1 — Foundation: Data Pipeline + Table + Simple Equity

| Step | Scope | Details |
|------|-------|---------|
| 1.1 | Backend route + template | `/analytics` route in server.py, `analytics.html` template with sidebar + main area structure |
| 1.2 | Summary endpoint | `GET /api/analytics/summary` — query studies table, parse symbol/TF, convert adaptive_mode, build research_info, include equity curves |
| 1.3 | Frontend controller | `analytics.js` — page init, API call, state management, event binding |
| 1.4 | Table rendering | `analytics-table.js` — 13 columns, group rows with duration, row checkboxes, group checkboxes, header checkbox, default sort Profit% desc |
| 1.5 | Equity chart | `analytics-equity.js` — single study stitched OOS curve, same style as Results page |
| 1.6 | Metric cards | 7 cards with Phase 1 formulas (SUM profit, worst MaxDD, profitable count) |
| 1.7 | Sidebar | DB selector (click-only), Research Info section |
| 1.8 | Selection buttons | Select All, Deselect All |

**Verifiable outcome:** Page loads, shows all WFA studies in table with group rows. Clicking a study shows its equity curve. Selecting multiple shows first study's curve + aggregated card metrics. DB switching works.

### Phase 2 — Interactive Analysis: Equity Aggregation + Filters + Labels + Heatmaps

| Step | Scope | Details |
|------|-------|---------|
| 2.1 | DB migration | `_ensure_analytics_columns()` for analytics_label, analytics_note |
| 2.2 | Equity aggregation | `POST /api/analytics/equity` with forward-fill + equal-weight averaging |
| 2.3 | Aggregated chart | Replace single-study chart with aggregated portfolio curve |
| 2.4 | Upgraded metric cards | Cards 1-2 use aggregated curve metrics |
| 2.5 | oos_span_days | Compute from equity_timestamps in summary endpoint |
| 2.6 | Ann.P% column | Add column 14 to table, JS computation |
| 2.7 | Auto-labels | Backend computation, Label column (15), label badges |
| 2.8 | Note column | Column 16, editable text |
| 2.9 | Label endpoints | `POST /api/analytics/label`, `POST /api/analytics/labels/batch` |
| 2.10 | Save Labels button | Actions bar |
| 2.11 | Filters bar | `analytics-filters.js` — 6 dropdowns, Select PASS Only |
| 2.12 | Column sorting | 3-click cycle on columns 7–14 |
| 2.13 | Conditional formatting | Cell backgrounds + text colors for all metric columns |
| 2.14 | AVG footer row | Averages for visible studies |
| 2.15 | Heatmaps | `analytics-heatmap.js` — Profit% and WFE% by Symbol × TF |
| 2.16 | Formatting legend | Compact grid showing color meanings |
| 2.17 | Selection Summary | Sidebar section with selected count + label breakdown |
| 2.18 | Export CSV | Download summary table as CSV |

**Verifiable outcome:** Full interactive analysis. Checking studies shows aggregated equity. Filters narrow the view. Labels are editable and persistent. Heatmaps visualize cross-symbol/TF patterns.

### Phase 3 — Sets + Global Export

| Step | Scope | Details |
|------|-------|---------|
| 3.1 | Sets DB tables | `study_sets`, `study_set_members` creation |
| 3.2 | Sets CRUD endpoints | `GET/POST/DELETE/PUT /api/analytics/sets` |
| 3.3 | Sets sidebar UI | `analytics-sets.js` — list, save, delete, load sets |
| 3.4 | Set loading | Click set → check members, update chart + cards |
| 3.5 | Sets Comparison panel | Collapsible panel with per-set metrics |
| 3.6 | Compare Equity Curves | Overlay multiple set curves on chart |
| 3.7 | Global DB schema | `src/storage/global/analytics.db` setup |
| 3.8 | Export endpoint | `POST /api/analytics/export-global` with UPSERT |
| 3.9 | Export UI | Button + research name dialog |

**Verifiable outcome:** Named portfolio sets can be saved, loaded, and compared. Studies can be exported to the global analytics DB for Layer 3.

---

## 21. Open Questions

1. **Analytics as separate page vs view mode?** → Decision: separate `/analytics` route with own template. The Results page is already complex. Shared CSS via `style.css`.

2. **Equity curve loading strategy (Phase 1)** — Include curves in summary response for Phase 1 simplicity. Phase 2 replaces with on-demand aggregated endpoint.

3. **Set metrics caching** — Recompute every time the panel opens (simpler, no stale risk). Cache only if performance becomes an issue.

4. **Heatmap multiple studies per cell** — AVG for MVP. Could add dropdown to switch between AVG/MAX/MIN later.

5. **Ann.P% warning threshold** — 90 OOS days hardcoded. Configurable in future if needed.

6. **Filter persistence** — Should filter state persist across page reloads (localStorage)? → Recommendation: yes, use localStorage for filter state and last active DB.

7. **Set colors** — How are set dot colors assigned? → Auto-assign from a fixed palette of 8 colors, cycling if more sets.

---

## 22. Metric Dictionary

Exact formulas and null-handling for all values displayed on the Analytics page.

### 22.1 Table Columns

| Column | Formula | Null / Edge Case | Format | Phase |
|--------|---------|-------------------|--------|-------|
| Profit% | `stitched_oos_net_profit_pct` (from DB) | 0.0 if null | 1 decimal, +/− sign | 1 |
| MaxDD% | `stitched_oos_max_drawdown_pct` (from DB, positive) | 0.0 if null | 1 decimal, positive | 1 |
| Trades | `stitched_oos_total_trades` (from DB) | 0 if null | Integer | 1 |
| WFE% | `best_value` (from DB) | "N/A" if null | 1 decimal | 1 |
| OOS Wins | `profitable_windows / total_windows` (from DB) | "0/0 (0%)" if null | "N/M (X%)" | 1 |
| OOS P(med) | `median_window_profit` (from DB) | "N/A" if null | 1 decimal, +/− sign | 1 |
| OOS WR(med) | `median_window_wr` (from DB) | "N/A" if null | 1 decimal | 1 |
| Ann.P% | `((1 + profit/100)^(365/oos_span_days) - 1) * 100` | "N/A" if oos_span_days=0 or missing | 1 decimal, +/− sign | 2 |

Ann.P% uses `oos_span_days` (from equity_timestamps), NOT `period_days` (from dataset dates).

### 22.2 Portfolio Metrics Cards

| # | Card | Phase 1 Formula | Phase 2 Formula | Null Handling |
|---|------|----------------|----------------|---------------|
| 1 | Portfolio Profit | `SUM(profit_pct_i)` | `(portfolio_curve[-1] / 100 - 1) * 100` | "—" if 0 checked |
| 2 | Portfolio MaxDD | `MAX(max_dd_pct_i)` (worst) | `max(peak_to_trough)` on aggregated curve | "—" if 0 checked |
| 3 | Total Trades | `SUM(total_trades_i)` | Same | 0 |
| 4 | Profitable | Profitable count / total checked (%) | Same | "0/0 (0%)" |
| 5 | Avg OOS Wins | `AVG(profitable_windows_pct_i)` | Same | "—" if 0 |
| 6 | Avg WFE | `AVG(wfe_i)` | Same | "—" if 0 |
| 7 | Avg OOS P(med) | `AVG(median_window_profit_i)` | Same | "—" if 0 |

### 22.3 Sets Comparison `[Phase 3]`

Same formulas as portfolio metrics (Phase 2 version) but computed per-set from each set's member studies.

### 22.4 AVG Footer Row `[Phase 2]`

All averages computed over VISIBLE (filtered) studies, not just checked:
- `AVG(profit_pct)`, `AVG(max_dd_pct)`, `AVG(total_trades)`, `AVG(wfe_pct)`
- `AVG(median_window_profit)`, `AVG(median_window_wr)`, `AVG(ann_profit_pct)`
- OOS Wins: `AVG(profitable_windows_pct)`

---

*Document version: v4 | Created: 2026-02-21 | For: Merlin Phase 3-2*
*v3 audit fixes preserved. 3-phase implementation split added.*
