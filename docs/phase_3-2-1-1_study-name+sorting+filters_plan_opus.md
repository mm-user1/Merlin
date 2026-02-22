# Phase 3-2-1: Study Name + Sorting + Filters — Implementation Plan

> Specification for three features on the Analytics page: Study Name column, column sorting, and multi-select filter dropdowns.
> This document is the authoritative reference for the coding agent implementing these features.
> Phase 1 of the Layer 2 plan is already implemented. This work extends it.

---

## Table of Contents

- [1. Study Name Column](#1-study-name-column)
- [2. Column Sorting](#2-column-sorting)
- [3. Filters](#3-filters)
- [4. Interaction Between Features](#4-interaction-between-features)
- [5. Backend Changes Summary](#5-backend-changes-summary)
- [6. Frontend Changes Summary](#6-frontend-changes-summary)

---

## 1. Study Name Column

### 1.1 Problem

The current Analytics table has separate columns for Strategy, Symbol, and TF. There is no way to identify which specific study record in the database a row corresponds to. For example, a study named `S01_OKX_JUPUSDT.P, 1h 2024.10.02-2026.02.01_WFA (19)` in the DB cannot be located in the Analytics table — there is no study name, no counter, and no way to cross-reference with the Studies Manager on the Results page.

### 1.2 Solution

Replace the three columns **Strategy + Symbol + TF** with two columns: **Strategy + Study Name**.

The Study Name column displays a shortened version of the `study_name` field from the `studies` table, with redundant parts removed.

### 1.3 Transformation Rule

The `study_name` in the database follows this format:
```
{StrategyPrefix}_{Exchange}_{Symbol}, {TF} {StartDate}-{EndDate}_{Mode} ({Counter})
```

The displayed Study Name removes:
1. The strategy prefix and underscore (e.g., `S01_`) — already shown in the Strategy column
2. The date range (e.g., ` 2024.10.02-2026.02.01`) — already shown in the group row
3. The mode suffix (e.g., `_WFA`) — always WFA on this page, and there is a WFA column

What remains:
```
{Exchange}_{Symbol}, {TF}                    — if no counter
{Exchange}_{Symbol}, {TF} ({Counter})        — if counter exists
```

### 1.4 Transformation Examples

| study_name in DB | Displayed Study Name |
|---|---|
| `S01_OKX_JUPUSDT.P, 1h 2024.10.02-2026.02.01_WFA (19)` | `OKX_JUPUSDT.P, 1h (19)` |
| `S01_OKX_ETHUSDT.P, 15 2025.05.01-2025.11.20_WFA` | `OKX_ETHUSDT.P, 15m` |
| `S03_OKX_LINKUSDT.P, 240 2025.01.01-2025.11.20_WFA (2)` | `OKX_LINKUSDT.P, 4h (2)` |
| `S01_OKX_BTCUSDT.P, 1h 2025.01.01-2025.11.20_WFA` | `OKX_BTCUSDT.P, 1h` |

Notes:
- When the counter is absent (first run with these parameters), no parentheses are shown.
- The TF in the study name may be numeric (e.g., `15` for 15m, `240` for 4h). The transformation should normalize it to human-readable form (same logic as the existing `_parse_csv_filename` / `_normalize_tf` in `server_routes_analytics.py`). However, the simplest approach is to just strip the known parts via regex and leave the rest as-is, since the study_name already contains the TF in whatever form it was generated.

### 1.5 Regex Approach for Transformation

The transformation can be implemented as a single regex substitution on the `study_name` string:

1. Remove the strategy prefix: everything up to and including the first `_` that follows the `S##` pattern
2. Remove the date range: the pattern ` YYYY.MM.DD-YYYY.MM.DD` (space + date-date)
3. Remove the mode suffix: `_WFA` or `_OPT`

The order matters. The result is the Study Name for display.

Edge case: if `study_name` is null or doesn't match the expected pattern, fall back to showing whatever is available (e.g., the raw symbol + TF from the existing parsed fields).

### 1.6 Updated Table Column Layout

**Before (13 data columns + checkbox):**
```
☑ | # | Strategy | Symbol | TF | WFA | IS/OOS | Profit% | MaxDD% | Trades | WFE% | OOS Wins | OOS P(med) | OOS WR(med)
```

**After (12 data columns + checkbox):**
```
☑ | # | Strategy | Study Name | WFA | IS/OOS | Profit% | MaxDD% | Trades | WFE% | OOS Wins | OOS P(med) | OOS WR(med)
```

Symbol and TF columns are removed from the visible table. They remain in the API response as separate fields (needed for filters — see Section 3).

### 1.7 Table Visualization

```
┌──┬──┬────────┬──────────────────────────┬─────┬──────┬───────┬──────┬──────┬─────┬──────────┬──────────┬──────────┐
│☑ │# │Strategy│ Study Name               │ WFA │IS/OOS│Profit%│MaxDD%│Trades│WFE% │ OOS Wins │OOS P(med)│OOS WR(md)│
├──┼──┼────────┼──────────────────────────┼─────┼──────┼───────┼──────┼──────┼─────┼──────────┼──────────┼──────────┤
│☑ │1 │S01 v26 │OKX_JUPUSDT.P, 1h (19)   │Fixed│ 90/30│ +72.8 │ 22.3 │  89  │ 32.1│10/12(83%)│  +14.2   │   64.8   │
│☑ │2 │S01 v26 │OKX_ETHUSDT.P, 1h        │Fixed│ 90/30│ +58.2 │ 16.8 │  76  │ 28.9│ 9/12(75%)│  +11.8   │   61.2   │
│☐ │3 │S03 v10 │OKX_LINKUSDT.P, 4h (2)   │Fixed│ 90/30│ +31.5 │ 19.8 │  54  │ 21.4│ 8/12(67%)│   +7.3   │   58.5   │
│☐ │4 │S01 v26 │OKX_SUIUSDT.P, 30m       │Fixed│ 90/30│ -15.2 │ 32.1 │  42  │  8.5│ 3/12(25%)│   -4.8   │   48.1   │
└──┴──┴────────┴──────────────────────────┴─────┴──────┴───────┴──────┴──────┴─────┴──────────┴──────────┴──────────┘
```

### 1.8 Backend Requirement

The `GET /api/analytics/summary` endpoint currently does NOT return `study_name` or `created_at`. Both must be added:

- `study_name` — needed for the Study Name column display
- `created_at` — needed for the default sort order (see Section 2)

Add these two fields to the SQL SELECT query and include them in each study object in the response.

The study_name-to-display-name transformation should be done in **JavaScript** on the frontend, not in Python. Reason: the raw `study_name` is useful metadata to keep available in the frontend state (e.g., for tooltips or future cross-referencing), and the transformation is purely presentational.

### 1.9 HTML Template Changes

In `analytics.html`, update the `<thead>` to replace the Symbol and TF headers with a single Study Name header:

**Before:**
```
<th>Strategy</th>
<th>Symbol</th>
<th>TF</th>
```

**After:**
```
<th>Strategy</th>
<th>Study Name</th>
```

Also update the group row `colspan` from 13 to 12 (one fewer column).

---

## 2. Column Sorting

### 2.1 Default Sort: Newest-Added First

On page load and after any sort reset, the table uses "addition order" sorting:

1. **Group order:** Groups are sorted by the newest `created_at` timestamp among their studies — the group containing the most recently added study appears first (descending).
2. **Within each group:** Studies are sorted by `created_at` descending — the most recently added study appears first.

This matches the mental model of the Studies Manager on the Results page, where the most recent study appears at the top.

### 2.2 Default Sort Visualization

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ☑ │ 2025-05-01 — 2026-02-01 (276 days)                          6 studies │  ← group with the
│───┼──────────────────────────────────────────────────────────────────────── │     newest study
│ ☑ │1 │S01 v26│OKX_JUPUSDT.P, 1h (19) │Fixed│90/30│ +72.8│...             │  ← most recently added
│ ☑ │2 │S01 v26│OKX_JUPUSDT.P, 1h (18) │Fixed│90/30│ +68.1│...             │
│ ☐ │3 │S01 v26│OKX_ETHUSDT.P, 1h      │Fixed│90/30│ +58.2│...             │
│ ☐ │4 │S01 v26│OKX_LINKUSDT.P, 4h     │Fixed│90/30│ +31.5│...             │
│ ☐ │5 │S01 v26│OKX_SUIUSDT.P, 1h      │Fixed│90/30│ +38.9│...             │
│ ☐ │6 │S01 v26│OKX_ETHUSDT.P, 30m     │Fixed│90/30│ -15.2│...             │
│───┼──────────────────────────────────────────────────────────────────────── │
│ ☑ │ 2025-01-01 — 2025-11-20 (324 days)                         12 studies │  ← second group
│───┼──────────────────────────────────────────────────────────────────────── │
│ ☐ │7 │S01 v26│OKX_LINKUSDT.P, 1h (5) │Fixed│90/30│ +65.1│...             │
│ ☐ │8 │S03 v10│OKX_LINKUSDT.P, 1h     │Fixed│90/30│ +42.3│...             │
│   │...                                                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Sorting Happens Within Groups

When the user clicks a sortable column header, rows are re-sorted **within** each group. Rows never move between groups. The group order itself remains unchanged (always newest-group-first based on `created_at`).

### 2.4 Three-Click Cycle

Each sortable column header has a 3-click cycle:

| Click | Action | Visual |
|-------|--------|--------|
| 1st click | Sort "best first" within each group | ▼ (or ▲ for MaxDD%) |
| 2nd click | Sort "worst first" within each group | Arrow reversed |
| 3rd click | Reset to default sort (by `created_at` desc) | No arrow |

Only one column can be actively sorted at a time. Clicking a different column resets the previous column and starts the cycle on the new one.

### 2.5 "Best First" Direction Per Column

| Column | Best First | Direction | Arrow |
|--------|-----------|-----------|-------|
| Study Name | Alphabetical A → Z | Ascending | ▼ |
| Profit% | Highest profit first | Descending | ▼ |
| MaxDD% | Lowest drawdown first | Ascending | ▲ |
| Trades | Most trades first | Descending | ▼ |
| WFE% | Highest WFE first | Descending | ▼ |
| OOS Wins | Highest % first | Descending | ▼ |
| OOS P(med) | Highest first | Descending | ▼ |
| OOS WR(med) | Highest first | Descending | ▼ |

**Non-sortable columns:** ☑ (checkbox), # (row number), Strategy, WFA, IS/OOS.

### 2.6 Sort Key for OOS Wins

The OOS Wins column displays as `"10/12 (83%)"`. The sort key is the percentage value (83), extracted from `profitable_windows_pct` in the study data. Do not parse the display string — use the numeric field directly.

### 2.7 Sort Key for Study Name

Sort alphabetically using `String.localeCompare()` with `{ numeric: true, sensitivity: 'base' }` on the displayed study name string. This ensures that `(2)` sorts before `(19)` numerically.

### 2.8 Row Renumbering

The `#` column always shows sequential numbers 1, 2, 3... from top to bottom, regardless of sort order. After any sort change, rows are renumbered.

### 2.9 Visual Indicators

**Sortable column headers** should show:
- **Inactive state:** No arrow visible. On hover, a dimmed arrow appears (subtle indication that the column is sortable).
- **Active state (1st click):** Arrow visible (▼ or ▲), column header text slightly highlighted (e.g., bold or a subtle background color).
- **Active state (2nd click):** Arrow reversed.
- **After 3rd click:** Returns to inactive state.

### 2.10 Table Subtitle Update

The subtitle below "Summary Table" should reflect the current sort state:
- Default: `"Sorted by date added (newest first)"`
- Active sort: `"Sorted by Profit% ▼"` or `"Sorted by MaxDD% ▲"`

### 2.11 State Management

Add to the `AnalyticsState` or table state:

- `sortColumn`: string or null — currently active sort column key (e.g., `'profit_pct'`, `'study_name'`, null for default)
- `sortDirection`: `'asc'` | `'desc'` — current direction
- `sortClickCount`: 1 | 2 | 3 — tracks position in the 3-click cycle

On 3rd click, all three reset: `sortColumn = null`, `sortDirection = null`, `sortClickCount = 0`.

### 2.12 Sorting Example

Starting from default sort (by `created_at` desc within groups):

```
Group "2025-05-01 — 2026-02-01"                    Group "2025-05-01 — 2026-02-01"
│1│OKX_JUPUSDT.P, 1h (19)  │ +72.8│    Click 1    │1│OKX_JUPUSDT.P, 1h (19)  │ +72.8│
│2│OKX_JUPUSDT.P, 1h (18)  │ +68.1│   Profit%▼    │2│OKX_JUPUSDT.P, 1h (18)  │ +68.1│
│3│OKX_ETHUSDT.P, 1h       │ +58.2│   ────────►   │3│OKX_ETHUSDT.P, 1h       │ +58.2│
│4│OKX_LINKUSDT.P, 4h      │ +31.5│               │4│OKX_SUIUSDT.P, 1h       │ +38.9│ ← swapped
│5│OKX_SUIUSDT.P, 1h       │ +38.9│               │5│OKX_LINKUSDT.P, 4h      │ +31.5│ ← swapped
│6│OKX_ETHUSDT.P, 30m      │ -15.2│               │6│OKX_ETHUSDT.P, 30m      │ -15.2│

Group "2025-01-01 — 2025-11-20"  stays in its own group, sorted independently
```

---

## 3. Filters

### 3.1 Overview

Six multi-select dropdown filters that allow narrowing the visible table rows. Each dropdown contains checkboxes for selecting one or more values. Filters hide non-matching rows (CSS `display:none`), they do not remove data.

### 3.2 Filter Bar Layout

The filter bar sits between the selection buttons and the summary table.

**When no filters are active (all dropdowns show "All"):**

```
┌─── Filters ────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  ┌──────────┐ ┌─────────────┐ ┌──────┐ ┌──────┐ ┌─────────┐ ┌──────────┐     │
│  │Strategy ▾│ │Symbol     ▾│ │TF  ▾│ │WFA ▾│ │IS/OOS ▾│ │Label   ▾│     │
│  └──────────┘ └─────────────┘ └──────┘ └──────┘ └─────────┘ └──────────┘     │
│                                                                                 │
│  [Select All]  [Deselect All]  [Select PASS Only]      ☐ Auto-select          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**When filters are active:**

```
┌─── Filters ────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  ┌──────────┐ ┌─────────────┐ ┌──────┐ ┌──────┐ ┌─────────┐ ┌──────────┐     │
│  │Strategy ▾│ │ Symbol (2) ▾│ │TF(2)▾│ │WFA ▾│ │IS/OOS ▾│ │Label   ▾│     │
│  └──────────┘ └─────────────┘ └──────┘ └──────┘ └─────────┘ └──────────┘     │
│                                                                                 │
│  Active: [TF: 30m, 1h ×]  [Symbol: JUPUSDT.P, ETHUSDT.P ×]    [Clear All]   │
│                                                                                 │
│  [Select All]  [Deselect All]  [Select PASS Only]      ☐ Auto-select          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

Note: The Label filter dropdown values (PASS / MAYBE / FAIL) come from the auto-label system, which is Phase 2 of the Layer 2 plan. If labels are not yet implemented, the Label dropdown should either be hidden or disabled with a "(Phase 2)" note. The other 5 filters work with data already available in Phase 1.

### 3.3 Filter Dropdown List

The six filter categories and their value sources:

| Filter | Values Populated From | Example Values |
|--------|----------------------|----------------|
| Strategy | Distinct `strategy` values from studies | `S01 v26`, `S03 v10` |
| Symbol | Distinct `symbol` values from studies | `JUPUSDT.P`, `ETHUSDT.P`, `LINKUSDT.P` |
| TF | Distinct `tf` values from studies | `30m`, `1h`, `4h` |
| WFA | Distinct `wfa_mode` values from studies | `Fixed`, `Adaptive` |
| IS/OOS | Distinct `is_oos` values from studies | `90/30`, `120/30` |
| Label | Fixed: `PASS`, `MAYBE`, `FAIL` | (Phase 2 — when auto-labels are implemented) |

Values are auto-populated from the loaded studies data. Each dropdown only shows values that actually exist in the current database.

### 3.4 Dropdown Internal Structure

When a dropdown is opened, it shows:

```
┌─ Symbol ──────────────────────────┐
│  ☑  All                           │  ← always first position
│──────────────────────────────────│
│  ☑  JUPUSDT.P                     │
│  ☑  ETHUSDT.P                     │
│  ☑  LINKUSDT.P                    │
│  ☐  SUIUSDT.P                     │
│  ☐  BTCUSDT.P                     │
│  ☐  SOLUSDT.P                     │
└───────────────────────────────────┘
```

- **`All` checkbox** is always the first item, separated by a thin divider line.
- Below: one checkbox per distinct value, sorted alphabetically (or by natural order for TF: 1m < 5m < 15m < 30m < 1h < 4h < 1D).

### 3.5 Click Interaction Rules

**Normal click on a value checkbox:**

Toggle that checkbox on/off. Standard multi-select behavior.

| Starting State | Normal Click On | Result |
|---|---|---|
| All selected (All ☑) | Click `SUIUSDT.P` | Uncheck `SUIUSDT.P`. `All` becomes unchecked. Filter is now active. |
| Some selected | Click unchecked `BTCUSDT.P` | Check `BTCUSDT.P`. If all values are now checked → `All` auto-checks. |
| Only one selected | Click that one (uncheck it) | **Cannot leave empty** — reverts to All (all values checked). |

**Ctrl+Click on a value:**

"Only this" mode. Selects exclusively the clicked value, deselects everything else.

| Starting State | Ctrl+Click On | Result |
|---|---|---|
| All selected | Ctrl+Click `1h` | Only `1h` checked. `All` unchecked. Filter active. |
| Multiple selected | Ctrl+Click `4h` (unchecked) | Only `4h` checked. Everything else unchecked. |
| Only `1h` selected | Ctrl+Click `4h` | Only `4h` checked. `1h` unchecked. Quick switch. |
| Only `1h` selected | Ctrl+Click `1h` (already the only one) | **Reverts to All** (cannot leave empty after deselecting the only item). |

**Click on `All`:**

| Starting State | Click All | Result |
|---|---|---|
| Some values selected | Click `All` | All values become checked. Filter becomes inactive. |
| All values already selected | Click `All` | No change (already All). |

### 3.6 "Cannot Leave Empty" Rule

A filter can never have zero values selected. If the last remaining checked value would be unchecked (by normal click or Ctrl+Click on itself), the filter reverts to All (all values checked, filter inactive).

This prevents the confusing state of "filter active but nothing matches → empty table."

### 3.7 All Checkbox Auto-Sync

The `All` checkbox reflects the current state:
- **Checked (☑)** when all individual values are checked → filter is inactive
- **Unchecked (☐)** when any individual value is unchecked → filter is active

`All` is never indeterminate. It's a binary indicator.

### 3.8 Dropdown Button Label

When filter is inactive (All selected): show the filter name only.
```
[TF ▾]
```

When filter is active (some values selected): show the filter name and count of selected values.
```
[TF (2) ▾]
```

This provides a quick visual indication that a filter is active, even when the dropdown is closed.

### 3.9 Active Filter Strip

A row of tags that appears **only when at least one filter is active** (not All). It sits between the dropdown row and the selection buttons row.

```
Active: [TF: 30m, 1h ×]  [Symbol: JUPUSDT.P, ETHUSDT.P ×]    [Clear All]
```

**Tag format:** `{FilterName}: {value1}, {value2} ×`

**When more than 3 values are selected in one filter:**
```
[Symbol: JUPUSDT.P, ETHUSDT.P, +2 more ×]
```
This prevents the tag strip from becoming too wide.

**Tag interactions:**

| Action | Result |
|---|---|
| Click `×` on a tag | That filter resets to All. Tag disappears. |
| Click `[Clear All]` | All filters reset to All. Entire Active strip hides. |

**When no filters are active:** the entire Active strip row is hidden (not shown at all, not shown empty).

### 3.10 Auto-select Checkbox

A checkbox labeled **"Auto-select"** positioned to the right of the selection buttons (Select All / Deselect All / Select PASS Only).

```
[Select All]  [Deselect All]  [Select PASS Only]      ☐ Auto-select
```

**Behavior when Auto-select is ON (☑):**

1. Immediately: all currently visible (not hidden by filters) study rows get their checkboxes checked. Hidden rows get unchecked.
2. On any filter change: the checked set is recalculated — visible rows checked, hidden rows unchecked.
3. Portfolio equity curve and metric cards update accordingly.

**Behavior when Auto-select is OFF (☐):**

1. Filter changes only hide/show rows. Checkboxes are not touched.
2. A hidden (filtered-out) row retains its checkbox state.
3. Portfolio metrics include ALL checked studies, even hidden ones.

**Turning Auto-select OFF:**

When the user unchecks Auto-select, the current checkbox state is preserved as-is. No checkboxes change. Future filter changes stop auto-updating checkboxes.

**Manual checkbox changes while Auto-select is ON:**

Manual checkbox clicks still work normally. However, the next filter change will override manual selections (auto-select recalculates from scratch based on visibility). This is expected behavior — Auto-select means "filters drive selection."

### 3.11 How Filters Affect the Table

| Aspect | Behavior |
|---|---|
| Non-matching rows | Hidden via CSS `display:none` |
| Group header rows | Hidden if ALL their child study rows are hidden |
| Checkbox state of hidden rows | Preserved when Auto-select is OFF; cleared when Auto-select is ON |
| Portfolio metrics / equity | Based on ALL checked rows (includes hidden checked rows when Auto-select is OFF) |
| Row numbers (#) | Renumbered based on visible rows only (1, 2, 3... among visible) |
| Sort order | Maintained. Sorting operates on all studies; visibility is independent of sort. |

### 3.12 Filter State in AnalyticsState

Each filter is an object tracking which values are selected:

```
filters: {
  strategy: null,    // null = All, Set(['S01 v26']) = active filter
  symbol: null,
  tf: null,
  wfa: null,
  isOos: null,
  label: null
}
autoSelect: false    // Auto-select checkbox state
```

`null` means "All" (no filter active). A `Set` of selected values means the filter is active. This makes the "is filter active?" check simple: `filter !== null`.

### 3.13 Filter Matching Logic

A study row is visible if it matches ALL active filters (AND logic across filters). Within each filter, the study must match ANY of the selected values (OR logic within a filter).

```
visible = (strategy filter matches OR strategy filter is All)
      AND (symbol filter matches OR symbol filter is All)
      AND (tf filter matches OR tf filter is All)
      AND (wfa filter matches OR wfa filter is All)
      AND (isOos filter matches OR isOos filter is All)
      AND (label filter matches OR label filter is All)
```

### 3.14 Full Workflow Example

```
Initial state:
  - 18 studies in DB
  - All visible, nothing checked
  - All filters: All
  - Auto-select: OFF

Step 1: User opens TF dropdown, Ctrl+Click on "1h"
  → TF filter = {1h} (only 1h selected)
  → All non-1h rows are hidden
  → Active strip appears: [TF: 1h ×]
  → Table shows 6 visible rows out of 18
  → Group rows with no visible children are hidden

Step 2: User wants to compare — Ctrl+Click on "4h" in TF dropdown
  → TF filter = {4h} (only 4h now — Ctrl+Click replaced 1h)
  → All non-4h rows hidden
  → Active strip: [TF: 4h ×]
  → Quick single-click switch!

Step 3: User wants to see both — normal click on "1h" in TF dropdown
  → TF filter = {4h, 1h} (added 1h to existing 4h)
  → Rows with 1h or 4h are visible
  → Active strip: [TF: 1h, 4h ×]

Step 4: User turns on Auto-select
  → All visible rows (1h + 4h studies) get checked
  → Hidden rows (30m etc.) get unchecked
  → Portfolio equity curve builds from checked studies
  → Metric cards update

Step 5: User adds Symbol filter: Ctrl+Click on "LINKUSDT.P"
  → Symbol filter = {LINKUSDT.P}
  → Only LINKUSDT.P with 1h or 4h visible (2 rows)
  → Auto-select: these 2 rows checked, all others unchecked
  → Active strip: [TF: 1h, 4h ×]  [Symbol: LINKUSDT.P ×]
  → Portfolio recalculated for 2 studies

Step 6: User clicks [Clear All]
  → All filters reset to All (null)
  → All 18 rows visible
  → Auto-select: all 18 rows checked
  → Active strip disappears
  → Portfolio shows all 18 studies
```

---

## 4. Interaction Between Features

### 4.1 Sort + Filters

Sorting and filtering are independent. Sorting defines the order of rows. Filtering defines which rows are visible. When both are active:

- Hidden rows maintain their sort position (if they become visible again, they appear in the correct sorted order)
- Renumbering (#) counts only visible rows

### 4.2 Sort + Groups

Sorting always operates within groups. Group order is always newest-group-first (by `created_at`). When sort is active, each group's rows are independently sorted by the active column. When sort is reset (3rd click), each group's rows return to `created_at` desc order.

### 4.3 Filters + Groups

If all children of a group are hidden by filters, the group header row is also hidden. If at least one child is visible, the group header is visible. The group checkbox only considers visible children for its checked/indeterminate state.

### 4.4 Auto-select + Filters + Portfolio

When Auto-select is ON:
- Portfolio metrics = metrics of visible (filtered) studies
- Changing any filter immediately updates checked set → portfolio updates

When Auto-select is OFF:
- Portfolio metrics = metrics of all checked studies (visible + hidden)
- Changing filters does not change checked set → portfolio does not change from filter changes alone

### 4.5 Select All / Deselect All + Filters

- **Select All**: checks ALL studies (visible + hidden), regardless of filter state
- **Deselect All**: unchecks ALL studies (visible + hidden)
- **Select PASS Only**: checks only PASS-labeled visible studies (Phase 2 — when labels exist)

These buttons operate independently of Auto-select. If Auto-select is ON and user clicks Select All, then changes a filter, Auto-select will recalculate (overriding the Select All).

---

## 5. Backend Changes Summary

The `GET /api/analytics/summary` endpoint needs two additional fields per study:

| New Field | Source Column | Purpose |
|---|---|---|
| `study_name` | `studies.study_name` | Study Name column display |
| `created_at` | `studies.created_at` | Default sort order |

Both fields already exist in the `studies` table and simply need to be added to the SQL SELECT and included in the response JSON.

No new endpoints are needed. No database schema changes are needed.

---

## 6. Frontend Changes Summary

### 6.1 Files to Modify

| File | Changes |
|---|---|
| `analytics.html` | Update `<thead>` columns (remove Symbol + TF, add Study Name). Update group row colspan. Add Filters section HTML structure between selection buttons and table. |
| `analytics-table.js` | Study Name column rendering. New sort logic (3-click cycle, within-group sorting, `created_at` default). Row renumbering. Update `groupStudies()` to sort groups by newest `created_at`. Filter visibility logic. |
| `analytics.js` | Add filter state to `AnalyticsState`. Handle Auto-select logic. Wire filter changes to table visibility updates and portfolio recalculation. Update subtitle text based on sort state. |

### 6.2 New File

| File | Purpose |
|---|---|
| `analytics-filters.js` | Multi-select dropdown rendering, click/Ctrl+Click handlers, Active Filter Strip rendering, filter state management, dropdown open/close behavior. |

### 6.3 CSS Additions

Styles needed for:
- Filter bar container
- Multi-select dropdown (open/closed states)
- Checkbox items inside dropdown (with hover state)
- Active filter tag strip (tags with × close buttons, Clear All button)
- Sort arrow indicators on column headers (active/hover states)
- Auto-select checkbox styling

These should be added to the existing `style.css` following the established analytics-specific class naming pattern (e.g., `analytics-filter-bar`, `analytics-dropdown`, `analytics-filter-tag`).

---

*Document version: v1 | Created: 2026-02-22 | For: Merlin Phase 3-2-1*
*Extends: phase_3-2_wfa-analytics-layer-2_plan_opus_v4.md (Phase 1 implemented)*
