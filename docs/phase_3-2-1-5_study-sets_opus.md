# Phase 3-2-1-5: Study Sets

> Specification for Study Sets on the Analytics page.
> Study Sets allow users to create named, persistent groups of studies for quick comparison,
> workspace switching, and aggregated metric analysis.
>
> This update diverges from the original Phase 2/3 plan in `phase_3-2_wfa-analytics-layer-2_plan_opus_v4.md`.
> It replaces the sidebar-based set list + separate Sets Comparison panel with a single unified
> panel-table in the main area.

---

## Table of Contents

- [1. Concept](#1-concept)
- [2. Sets Panel Layout](#2-sets-panel-layout)
- [3. View Modes and State Machine](#3-view-modes-and-state-machine)
- [4. Interaction Model](#4-interaction-model)
- [5. Set Operations (CRUD)](#5-set-operations-crud)
- [6. Move Set Mode](#6-move-set-mode)
- [7. Metrics in Sets Panel](#7-metrics-in-sets-panel)
- [8. Filters Behavior with Sets](#8-filters-behavior-with-sets)
- [9. Focus Mode Integration](#9-focus-mode-integration)
- [10. Esc Priority Chain](#10-esc-priority-chain)
- [11. Collapsible Behavior](#11-collapsible-behavior)
- [12. Expand Toggle and Scroll](#12-expand-toggle-and-scroll)
- [13. Database Schema](#13-database-schema)
- [14. API Endpoints](#14-api-endpoints)
- [15. Frontend Architecture](#15-frontend-architecture)
- [16. Backend Changes](#16-backend-changes)
- [17. Edge Cases](#17-edge-cases)
- [18. Implementation Steps](#18-implementation-steps)

---

## 1. Concept

### 1.1 Problem

Filters and sorting partially answer questions like "what is profit on 1h TF?" or "what if I exclude this ticker?". But typical research involves comparing studies that differ by a single parameter (WFA 90/30 vs 120/30, Adaptive vs Fixed, TPE vs NSGA-II, different objective sets, etc.). The parameter space is too large for dedicated filter dropdowns.

### 1.2 Solution

Manually curated, named groups of studies ("sets") stored in the database. Each set is a persistent collection of `study_id` references. Users can:

- Quickly switch between curated portfolios (workspace switching)
- Compare aggregated metrics across sets at a glance (side-by-side table)
- Work inside a set — filter, sort, check/uncheck, focus on individual studies
- Create sub-sets from filtered selections within a set
- Aggregate multiple sets for combined analysis (union with deduplication)

### 1.3 Design Principle: Unified Panel

Instead of the original plan's dual approach (sidebar list + separate comparison panel), Study Sets use a **single compact panel-table** in the main area. This panel serves both functions: set switching AND metric comparison.

**Placement:** Between Summary Cards and Filters Bar.

```
┌─ Main Area ─────────────────────────────────────────────────┐
│  Header: "Analytics my_research.db"                         │
│  Stitched OOS Equity Chart                                  │
│  Summary Cards (7 metric cards)                             │
│                                                             │
│  ┌─ Study Sets Panel ─────────────────────────────────────┐ │
│  │  ...compact table with sets and metrics...             │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Filters Bar                                                │
│  [Select All] [Deselect All] [Auto-select]                  │
│  Summary Table                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Sets Panel Layout

### 2.1 Panel Structure

```
▾ Study Sets                                                        [+ Save Set]
┌────────────────────────────────────────────────────────────────────────────────────┐
│       │ Set Name            │ Ann.P% │ Profit% │ MaxDD% │Profitable│ WFE% │OOS W  │
│───────┼─────────────────────┼────────┼─────────┼────────┼──────────┼──────┼───────│
│       │ All Studies          │ +96.2% │ +128.5% │ -41.2% │12/18(67%)│ 21.5%│ 62.4% │
│  ☐    │ Optuna 4 targets     │+107.2% │  +48.6% │ -19.8% │ 4/5 (80%)│ 28.1%│ 76.2% │
│  ☐    │ Optuna 6 targets     │+112.5% │  +52.1% │ -22.3% │ 3/5 (60%)│ 25.4%│ 72.1% │
│  ☐    │ Best 1h only         │+118.4% │  +54.2% │ -22.1% │ 3/4 (75%)│ 30.1%│ 83.3% │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Visual Elements

- **"All Studies" row:** Always first. No checkbox. Click = navigate to all-studies view.
- **Set rows:** Each has a checkbox. Click on row = toggle checkbox. Alt+click = focus on set.
- **Focused set indicator:** Blue vertical line on the left edge of the row (outside the checkbox column), matching the Summary Table focused-row pattern (`border-left: 3px solid #3498db`).
- **Checked set indicator:** Checkbox is checked. No additional visual beyond the checkbox.
- **Focused + checked:** Blue vertical line (focus) + checked checkbox, exactly like Summary Table.
- **No radio buttons.** Selection is indicated by the blue vertical line only.

### 2.3 Panel with Focus Active (buttons visible)

```
▾ Study Sets                                                        [+ Save Set]
┌────────────────────────────────────────────────────────────────────────────────────┐
│       │ All Studies          │ +96.2% │ +128.5% │ -41.2% │12/18(67%)│ 21.5%│ 62.4%│
│▌ ☑    │ Optuna 4 targets     │+107.2% │  +48.6% │ -19.8% │ 4/5 (80%)│ 28.1%│ 76.2%│  ← focused
│  ☐    │ Optuna 6 targets     │+112.5% │  +52.1% │ -22.3% │ 3/5 (60%)│ 25.4%│ 72.1%│
│  ☐    │ Best 1h only         │+118.4% │  +54.2% │ -22.1% │ 3/4 (75%)│ 30.1%│ 83.3%│
├────────────────────────────────────────────────────────────────────────────────────┤
│  [Move]  [Rename]  [Delete]  [Update "Optuna 4 targets"]                          │
└────────────────────────────────────────────────────────────────────────────────────┘
```

- Action buttons row is **only visible when a user-created set is focused** (not "All Studies").
- When no set is focused, the action row is hidden.

### 2.4 [+ Save Set] Button Visibility

- **Visible** only when there are checked checkboxes in Summary Table (at least one study selected).
- **Hidden** when no studies are checked.
- Located in the panel header row, right-aligned.

---

## 3. View Modes and State Machine

### 3.1 Three View Modes

The Analytics page has three mutually exclusive view modes that control **which studies are visible** in the Summary Table:

| Mode | Summary Table Visibility | Summary Table Checkboxes | Entry |
|------|--------------------------|--------------------------|-------|
| **All Studies** | All studies in the database | Not changed on entry | Default; click "All Studies" row |
| **Set Focus** | Only focused set's members | All members checked on entry | Alt+click on a set row |
| **Set Checkboxes** | Union of checked sets' members (deduplicated by `study_id`) | All union members checked on entry | Click on set row (toggle checkbox) |

### 3.2 State Transitions

```
┌──────────────┐   Alt+click set    ┌──────────────┐
│              │ ─────────────────► │              │
│  ALL STUDIES │                    │  SET FOCUS   │
│   (default)  │ ◄───────────────── │              │
│              │  click "All        └──────┬───────┘
└──────┬───────┘  Studies" row        Esc  │
       │                                   │
       │ toggle set                        │ (if checked sets exist)
       │ checkbox                          ▼
       │                           ┌──────────────┐
       └─────────────────────────► │    SET       │
                                   │  CHECKBOXES  │
       ┌─────────────────────────► │              │
       │ toggle set checkbox       └──────┬───────┘
       │ (from All Studies with            │
       │  checked sets already)            │ last checkbox
       │                                   │ unchecked
       │                                   ▼
       └──────────────────────── ALL STUDIES
```

### 3.3 Detailed Transition Table

| From | Action | To | Effect |
|------|--------|----|--------|
| **All Studies** | Alt+click set X | **Set Focus** on X | ST shows X's members, all checked |
| **All Studies** | Click set X row (check) | **Set Checkboxes** | ST shows X's members, all checked |
| **Set Focus** on X | Esc (no study focus) | **Set Checkboxes** if any sets checked; else **All Studies** | ST shows union or all; checkboxes updated accordingly |
| **Set Focus** on X | Click "All Studies" row | **All Studies** | ST shows all studies, checkboxes NOT changed |
| **Set Focus** on X | Click set Y row (toggle checkbox) | **Set Focus** on X (unchanged) | Y's checkbox toggles silently, view unchanged |
| **Set Focus** on X | Alt+click set X (same) | **All Studies** | Focus toggled off; fall back to checked sets or all |
| **Set Focus** on X | Alt+click set Y (different) | **Set Focus** on Y | ST shows Y's members, all checked |
| **Set Checkboxes** | Click set (last one unchecked) | **All Studies** | No sets checked; ST shows all, checkboxes unchanged |
| **Set Checkboxes** | Click "All Studies" row | **All Studies** | ST shows all studies, checkboxes NOT changed. Set checkboxes in panel remain. |
| **Set Checkboxes** | Alt+click set X | **Set Focus** on X | ST shows X's members, all checked |
| **All Studies** (with checked sets in panel) | Click another set checkbox | **Set Checkboxes** | Re-enter checkbox mode; ST shows union |

### 3.4 Deduplication

When multiple sets are checked, the union of their `study_id` lists is computed using a JavaScript `Set`, which guarantees uniqueness automatically. No additional deduplication logic is needed.

```javascript
const unionIds = new Set();
checkedSets.forEach(set => {
    set.study_ids.forEach(id => unionIds.add(id));
});
```

---

## 4. Interaction Model

### 4.1 Sets Panel Interactions

All interactions mirror the Summary Table patterns for consistency.

| Action | Effect |
|--------|--------|
| **Click on set row** | Toggle checkbox (like Summary Table row click) |
| **Alt+click on set row** | Toggle focus on that set |
| **Shift+click on set row** | Range select/deselect (using anchor, like Summary Table) |
| **Ctrl+click on set row** | Check/uncheck all sets (like Summary Table Ctrl+click) |
| **Click on "All Studies" row** | Navigate to All Studies mode (no checkbox change) |
| **Click checkbox directly** | Toggle that set's checkbox (native behavior) |

### 4.2 Summary Table Checkbox Synchronization

When set checkboxes or focus change in the sets panel, Summary Table checkboxes are updated:

- **Set Focus activated:** Check all focused set's members in Summary Table.
- **Set Checkboxes changed (no focus):** Check all union members in Summary Table.
- **"All Studies" clicked:** Do NOT change Summary Table checkboxes.

After automatic checkbox sync, the user can manually toggle individual checkboxes in Summary Table. This does not affect set membership or sets panel state — it only affects Summary Cards and Equity Chart (variant B behavior).

### 4.3 Summary Cards and Equity Chart

Summary Cards and Equity Chart **follow Summary Table checkboxes** (variant B):

- They react to whatever is checked in Summary Table.
- Sets panel controls which studies are visible and initially checked, but after that, manual checkbox changes in Summary Table drive the cards and chart.
- Study Focus Mode (Alt+click on a study row in Summary Table) takes priority as before.

---

## 5. Set Operations (CRUD)

### 5.1 Create Set

**Trigger:** `[+ Save Set]` button (visible only when Summary Table has checked studies).

**Workflow:**
1. User checks studies in Summary Table (manually or via filters + Select All).
2. Click `[+ Save Set]`.
3. Browser `prompt()` dialog asks for set name.
4. Set saved to database with currently checked `study_id` list.
5. Sets panel refreshes. New set appears in the list.

**Sub-set creation workflow:**
1. Focus on set "Optuna 4 targets" (Alt+click).
2. Summary Table shows 5 studies, all checked.
3. Apply filter TF = 1h (2 studies visible).
4. Click "Select All" (checks visible 2 studies).
5. Click `[+ Save Set]` → name it "Optuna 4 targets 1h".

### 5.2 Rename Set

**Trigger:** `[Rename]` button (visible only when a user-created set is focused).

**Workflow:**
1. Click `[Rename]`.
2. Browser `prompt()` with current name pre-filled.
3. New name saved via PUT endpoint.
4. Sets panel refreshes.

### 5.3 Delete Set

**Trigger:** `[Delete]` button (visible only when a user-created set is focused).

**Workflow:**
1. Click `[Delete]`.
2. Browser `confirm()` dialog.
3. Set deleted via DELETE endpoint (CASCADE removes members).
4. Sets panel refreshes. View mode falls back to All Studies.

### 5.4 Update Set

**Trigger:** `[Update "Set Name"]` button (contextual).

The button has two modes:

**When a set is focused:**
- Button text: `[Update "Optuna 4 targets"]` (shows focused set name).
- One click → `confirm()` dialog → updates focused set's members to currently checked Summary Table `study_id` list.

**When no set is focused (but sets exist):**
- Button text: `[Update Set ▾]` (dropdown).
- Click opens dropdown listing all user-created sets.
- Click on set name in dropdown → `confirm()` dialog → updates that set's members.

**Note:** Update Set button is only shown when a set is focused (it appears in the action buttons row). The dropdown variant would only be needed if we showed Update outside focus mode, but since the action row is only visible during focus, the contextual `[Update "name"]` variant is the primary one.

---

## 6. Move Set Mode

### 6.1 Activation

**Trigger:** `[Move]` button (visible only when a user-created set is focused).

### 6.2 Workflow

1. Click `[Move]`.
2. Focused set row gets a visual indicator (e.g., `↕` icon or highlighted background).
3. Keyboard controls become active:
   - **↑ / ↓** — move set up/down by 1 position.
   - **PgUp / PgDown** — move by 3 positions.
   - **Home / End** — move to first/last position.
4. **Enter** or **Esc** — exit move mode, save new `sort_order` to database.

### 6.3 Visual Feedback

```
│       │ All Studies          │ ...                                              │
│▌ ☑  ↕ │ Optuna 4 targets     │ ...  ← being moved (highlighted row)            │
│  ☐    │ Optuna 6 targets     │ ...                                              │
│  ☐    │ Best 1h only         │ ...                                              │
├────────────────────────────────────────────────────────────────────────────────────┤
│  [Enter to confirm / Esc to cancel]                                               │
└────────────────────────────────────────────────────────────────────────────────────┘
```

- The `↕` symbol or equivalent icon appears next to the set name.
- The action buttons row text changes to `[Enter to confirm / Esc to cancel]` during move mode.
- "All Studies" row is excluded from move operations (always stays at the top).

### 6.4 Persistence

After move mode ends (Enter or Esc), the new order is saved by updating `sort_order` for all affected sets via a single PUT request or batch update.

---

## 7. Metrics in Sets Panel

### 7.1 Column Order

Consistent with Summary Table and project-wide conventions (profit metrics → drawdown → trades-like → quality):

```
Set Name │ Ann.P% │ Profit% │ MaxDD% │ Profitable │ WFE% │ OOS Wins
```

6 metric columns + set name = 7 columns total.

### 7.2 Metric Formulas

All metrics are computed on the frontend from already-loaded study data. No backend computation needed.

| Column | Formula | Format | Notes |
|--------|---------|--------|-------|
| **Ann.P%** | `AVG(ann_profit_pct)` of members | `+X.X%` / `-X.X%` | Rough estimate; uses pre-computed per-study values. Studies with `ann_profit_pct = null` (OOS < 30 days) are excluded from average. |
| **Profit%** | `SUM(profit_pct)` of members | `+X.X%` / `-X.X%` | Sum of all member profits. |
| **MaxDD%** | `MAX(abs(max_dd_pct))` of members (worst) | `-X.X%` | Worst single-study drawdown in the set. |
| **Profitable** | `count(profit_pct > 0) / total` | `N/M (X%)` | How many studies are profitable out of total members. |
| **WFE%** | `AVG(wfe_pct)` of members | `X.X%` | Average Walk-Forward Efficiency. |
| **OOS Wins** | `AVG(profitable_windows_pct)` of members | `X.X%` | Average OOS window win rate. |

### 7.3 "All Studies" Row Metrics

Computed from **all studies in the database** (not filtered). This serves as a baseline for comparison. The formulas are the same as above, applied to all loaded studies.

### 7.4 Conditional Formatting

Matching Summary Table patterns:
- **Ann.P%, Profit%:** Green (`val-positive`) for positive, red (`val-negative`) for negative.
- **MaxDD%:** Red (`val-negative`) when `abs(value) > 40`.
- **Profitable:** No special coloring.
- **WFE%, OOS Wins:** No special coloring.

---

## 8. Filters Behavior with Sets

### 8.1 Contextual Filter Values

When a set is focused (Set Focus mode):
- Filter dropdown values are **recalculated** to show only values present in the focused set's members.
- Example: if set "Optuna 4 targets" contains only `1h` and `4h` studies, the TF filter shows only `1h` and `4h`, not `30m`.

When in Set Checkboxes mode (union of checked sets):
- Filter values reflect the union of all checked sets' members.

When in All Studies mode:
- Filter values reflect all studies (default behavior).

### 8.2 Filter Interaction

Filters work **within** the current view:
- In Set Focus mode, filters further narrow the visible studies within the set.
- In Set Checkboxes mode, filters narrow within the union.
- In All Studies mode, filters work on all studies (current behavior).

---

## 9. Focus Mode Integration

Study Focus Mode (Alt+click on a study row in Summary Table) and Set Focus are independent layers:

| State | Summary Table Shows | Cards/Chart Show |
|-------|---------------------|------------------|
| No set + no study focus | All studies (or union if set checkboxes) | Aggregate of checked studies |
| Set "4 targets" focused + no study focus | 5 set members, all checked | Aggregate of 5 members |
| Set "4 targets" focused + study #3 focused | 5 set members, all checked | Study #3 details |
| No set focus + study #3 focused | All studies (or union) | Study #3 details |

Study focus takes visual priority for cards, chart, and sidebar settings display.

---

## 10. Esc Priority Chain

```
Esc pressed:
  1. Is a study focused (in Summary Table)?
     → Yes: Clear study focus. Stop.
  2. Is move mode active (in Sets panel)?
     → Yes: Exit move mode (confirm position). Stop.
  3. Is a set focused?
     → Yes: Clear set focus.
       - If any sets are checked → enter Set Checkboxes mode
         (ST shows union, checkboxes set to union members)
       - Else → enter All Studies mode
         (ST shows all studies, checkboxes unchanged)
     Stop.
  4. Nothing focused → Esc does nothing.
```

---

## 11. Collapsible Behavior

### 11.1 Collapsed State

```
▸ Study Sets   Focused: Optuna 4 targets (5)                       [+ Save Set]
```

- Shows focused set name and member count when a set is focused.
- When no set is focused: `▸ Study Sets` with no additional text.
- `[+ Save Set]` remains visible in collapsed state (when Summary Table has checked studies).

### 11.2 Default State on Page Load

- **Collapsed** if no user-created sets exist (or only "All Studies" pseudo-set).
- **Expanded** if at least one user-created set exists.

### 11.3 Expand/Collapse

Click on the `▾ Study Sets` / `▸ Study Sets` header toggles the panel.

---

## 12. Expand Toggle and Scroll

### 12.1 Default View

By default, the sets table shows up to **5 set rows** (not counting "All Studies" row). If there are more than 5 sets, a scroll is enabled within the compact view.

### 12.2 Expand Toggle

An expand toggle button (matching the Results page Optuna table expand toggle style — `.table-expand-toggle`) appears below the table when there are more than 5 sets.

- **Collapsed (default):** 5 visible rows + scroll.
- **Expanded:** 10 visible rows + scroll.

The toggle is a small chevron button (▼ / ▲) centered below the table, using the existing `.table-expand` / `.table-expand-toggle` CSS classes.

### 12.3 Scroll

Scroll is available in both compact and expanded modes when the number of sets exceeds the visible row limit.

---

## 13. Database Schema

```sql
-- In the active research DB (same DB as studies table)

CREATE TABLE IF NOT EXISTS study_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS study_set_members (
    set_id INTEGER NOT NULL REFERENCES study_sets(id) ON DELETE CASCADE,
    study_id TEXT NOT NULL,
    UNIQUE(set_id, study_id)
);
```

- Sets are **per-database**. Switching the active database loads different sets.
- `sort_order` enables manual ordering (Move Set). Default: order of creation.
- `ON DELETE CASCADE` ensures members are cleaned up when a set is deleted.
- No `description` column — not needed for this implementation.

---

## 14. API Endpoints

### 14.1 List Sets

```
GET /api/analytics/sets
```

**Response:**
```json
{
  "sets": [
    {
      "id": 1,
      "name": "Optuna 4 targets",
      "sort_order": 0,
      "study_ids": ["uuid-1", "uuid-2", "uuid-3", "uuid-4", "uuid-5"],
      "created_at": "2026-02-25 14:30:00"
    }
  ]
}
```

Sets are returned ordered by `sort_order ASC, id ASC`.

### 14.2 Create Set

```
POST /api/analytics/sets
Content-Type: application/json

{
  "name": "Optuna 4 targets",
  "study_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

**Response:**
```json
{
  "id": 1,
  "name": "Optuna 4 targets",
  "sort_order": 0,
  "study_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "created_at": "2026-02-25 14:30:00"
}
```

`sort_order` is automatically assigned as `MAX(sort_order) + 1` (append to end).

### 14.3 Update Set

```
PUT /api/analytics/sets/<id>
Content-Type: application/json

{
  "name": "Optuna 4 targets (updated)",  // optional
  "study_ids": ["uuid-1", "uuid-2"],     // optional - replaces all members
  "sort_order": 2                         // optional
}
```

**Response:**
```json
{"ok": true}
```

When `study_ids` is provided, all existing members are deleted and replaced with the new list (DELETE + INSERT approach).

### 14.4 Delete Set

```
DELETE /api/analytics/sets/<id>
```

**Response:**
```json
{"ok": true}
```

CASCADE deletes members automatically.

### 14.5 Reorder Sets (Batch)

```
PUT /api/analytics/sets/reorder
Content-Type: application/json

{
  "order": [3, 1, 2]  // set IDs in desired order
}
```

**Response:**
```json
{"ok": true}
```

Updates `sort_order` for all listed sets in a single transaction. This is called once when Move Set mode ends (Enter/Esc).

---

## 15. Frontend Architecture

### 15.1 New File: `analytics-sets.js`

Responsible for:
- Rendering the sets panel table (including "All Studies" row).
- Set checkbox management (click, Shift+click, Ctrl+click, Alt+click).
- Focus indicator rendering (blue vertical line).
- Action buttons row (Move, Rename, Delete, Update).
- Move mode keyboard handler.
- Expand toggle and scroll management.
- Collapsed/expanded panel state.
- Metrics computation for each set.
- Set CRUD API calls.

**Exposed via `window.AnalyticsSets`:**
```javascript
window.AnalyticsSets = {
  init(options),           // Initialize with studies, callbacks
  updateStudies(studies),  // Refresh metrics when studies data changes
  loadSets(),              // Load sets from API
  getFocusedSetId(),       // Current focused set ID or null
  getCheckedSetIds(),      // Set of checked set IDs
  getVisibleStudyIds(),    // Union of study_ids for current view mode
  getViewMode(),           // 'allStudies' | 'setFocus' | 'setCheckboxes'
  setFocusedSetId(id),     // External focus control
  clearFocus(),            // Clear set focus
};
```

### 15.2 Modifications to `analytics.js`

New state fields:
```javascript
const AnalyticsState = {
  // ... existing fields ...
  sets: [],                    // Array of set objects from API
  focusedSetId: null,          // Currently focused set ID
  checkedSetIds: new Set(),    // Checked set IDs
  setViewMode: 'allStudies',   // 'allStudies' | 'setFocus' | 'setCheckboxes'
  setMoveMode: false,          // Whether move mode is active
};
```

Integration points:
- On set focus/checkbox change → compute `visibleStudyIds` → pass to `AnalyticsTable.renderTable()` as new option.
- On set focus change → update filter dropdown values contextually.
- On Esc → check Esc priority chain (study focus → move mode → set focus).
- On `loadSummary()` → also call `AnalyticsSets.loadSets()`.
- On DB switch → reset sets state, reload sets.

### 15.3 Modifications to `analytics-table.js`

New option in `renderTable()`:
```javascript
renderTable(studies, checkedStudyIds, onSelectionChange, {
  // ... existing options ...
  visibleStudyIds: null,  // Set<string> or null (null = show all)
});
```

When `visibleStudyIds` is provided:
- Only studies with `study_id` in the set are shown (others hidden via `display: none`).
- This replaces the current filter-based visibility as an additional layer.
- Filter visibility is applied on top of set visibility (both must pass).

### 15.4 Modifications to `analytics-filters.js`

New method or option for contextual filter values:
- When a set is focused or sets are checked, filter dropdowns recalculate their available values from the visible study subset only.
- When returning to All Studies, filter values are recalculated from all studies.

### 15.5 Modifications to `analytics.html`

New HTML block between Summary Cards and Filters:
```html
<div class="analytics-sets-section" id="analyticsSetsSection">
  <div class="collapsible open" id="analytics-sets-collapsible">
    <div class="collapsible-header analytics-sets-header">
      <span class="collapsible-icon">&#9660;</span>
      <span class="collapsible-title">Study Sets</span>
      <span class="analytics-sets-summary" id="analyticsSetsSummary"></span>
      <button class="sel-btn analytics-save-set-btn" id="analyticsSaveSetBtn"
              type="button" style="display:none;">+ Save Set</button>
    </div>
    <div class="collapsible-content">
      <div class="analytics-sets-table-wrap" id="analyticsSetsTableWrap">
        <!-- Sets table rendered by analytics-sets.js -->
      </div>
      <div class="analytics-sets-actions" id="analyticsSetsActions" style="display:none;">
        <!-- Action buttons rendered by analytics-sets.js -->
      </div>
    </div>
  </div>
</div>
```

New script include:
```html
<script src="/static/js/analytics-sets.js"></script>
```

Script order: `api.js` → `analytics-equity.js` → `analytics-filters.js` → `analytics-sets.js` → `analytics-table.js` → `analytics.js`.

### 15.6 Modifications to `style.css`

New styles needed:
- `.analytics-sets-section` — panel container.
- `.analytics-sets-header` — header with title, summary text, Save Set button.
- `.analytics-sets-table-wrap` — table container with max-height and overflow.
- `.analytics-sets-table` — compact data table for sets.
- `.analytics-set-row` — set row styling.
- `.analytics-set-row.analytics-set-focused > td:first-child` — blue left border for focused set.
- `.analytics-sets-actions` — action buttons row.
- `.analytics-sets-expand` — expand toggle container.
- `.analytics-set-moving` — visual indicator for move mode.
- Compact mode: `max-height` based on 5 rows. Expanded mode: `max-height` based on 10 rows.

---

## 16. Backend Changes

### 16.1 `storage.py`

New functions:
```python
def ensure_study_sets_tables(db_path=None):
    """Create study_sets and study_set_members tables if they don't exist."""

def list_study_sets(db_path=None):
    """Return all sets with their member study_ids, ordered by sort_order."""

def create_study_set(name, study_ids, db_path=None):
    """Create a new set. Returns the created set dict."""

def update_study_set(set_id, name=None, study_ids=None, sort_order=None, db_path=None):
    """Update set name, members, or sort_order."""

def delete_study_set(set_id, db_path=None):
    """Delete a set (CASCADE deletes members)."""

def reorder_study_sets(id_order, db_path=None):
    """Update sort_order for all sets based on provided ID order."""
```

### 16.2 `server_routes_analytics.py`

New endpoints registered:
- `GET /api/analytics/sets` → calls `list_study_sets()`
- `POST /api/analytics/sets` → calls `create_study_set()`
- `PUT /api/analytics/sets/<int:set_id>` → calls `update_study_set()`
- `DELETE /api/analytics/sets/<int:set_id>` → calls `delete_study_set()`
- `PUT /api/analytics/sets/reorder` → calls `reorder_study_sets()`

### 16.3 Table Initialization

`ensure_study_sets_tables()` is called during analytics summary load or on first sets API access. This ensures tables exist without requiring a migration for existing databases.

---

## 17. Edge Cases

### 17.1 Set Contains Deleted Studies

A set may reference `study_id` values that no longer exist in the `studies` table (study was deleted after set creation). These orphaned references should be silently excluded:
- When computing metrics, only matching studies are used.
- When displaying members in Summary Table, non-existent studies are skipped.
- Orphaned references are NOT automatically cleaned up (the user may re-import the study).

### 17.2 Empty Set

A set with 0 valid members (all studies deleted):
- Shows `0/0 (0%)` for Profitable, `N/A` for other metrics.
- Focusing on it shows an empty Summary Table.

### 17.3 Duplicate Set Name

The `name` column has a UNIQUE constraint. Creating a set with a duplicate name returns an error. The frontend shows an alert and prompts for a different name.

### 17.4 DB Switch

When the user switches the active database:
- All sets state is reset (`focusedSetId = null`, `checkedSetIds = empty`, `setViewMode = 'allStudies'`).
- Sets are reloaded from the new database.

### 17.5 New Study Added (Optimization Completed)

If the user runs an optimization while on the Analytics page:
- Sets are not automatically updated (they reference specific `study_id` values).
- The new study appears in "All Studies" but not in any existing set.
- The user can add it to a set via Update Set.

### 17.6 No Sets Exist

When no user-created sets exist:
- Sets panel shows only "All Studies" row with metrics.
- Panel is collapsed by default.
- No action buttons visible.
- `[+ Save Set]` is the only way to create the first set.

### 17.7 Move Mode Interruption

If the user clicks outside the sets panel or interacts with Summary Table during move mode:
- Move mode is cancelled (same as Esc).
- The set returns to its pre-move position? Or keeps current position?
- **Decision:** Keep current position (auto-save on any exit from move mode). This is simpler and less surprising — the user sees the set in the new position before confirming.

---

## 18. Implementation Steps

### Step 1: Database Schema

- Add `ensure_study_sets_tables()` to `storage.py`.
- Add CRUD functions for study sets.
- Add tests for storage functions.

### Step 2: Backend API

- Add endpoints to `server_routes_analytics.py`.
- Register routes in `server.py`.
- Add API tests.

### Step 3: Frontend — Sets Panel (Basic)

- Create `analytics-sets.js` with panel rendering.
- Add HTML structure to `analytics.html`.
- Add CSS styles to `style.css`.
- Implement "All Studies" row with metrics.
- Implement set rows with checkboxes and metrics.
- Wire up `[+ Save Set]`, `[Rename]`, `[Delete]`.

### Step 4: Frontend — View Mode State Machine

- Implement three-mode state machine in `analytics.js`.
- Wire set focus (Alt+click) and checkbox (click) to mode transitions.
- Connect `visibleStudyIds` to `analytics-table.js`.
- Implement Summary Table checkbox synchronization.
- Implement Esc priority chain.

### Step 5: Frontend — Contextual Filters

- Update `analytics-filters.js` to accept contextual study subset.
- Recalculate filter values on set focus/checkbox change.

### Step 6: Frontend — Update Set (Contextual Button)

- Implement contextual `[Update "name"]` button.
- Implement dropdown variant for non-focus mode (if needed).

### Step 7: Frontend — Move Set Mode

- Implement keyboard-driven move mode.
- Implement visual feedback.
- Wire to reorder API endpoint.

### Step 8: Frontend — Expand Toggle and Scroll

- Implement compact/expanded toggle.
- Add scroll behavior.
- Implement collapsible header with summary text.

### Step 9: Integration Testing

- Test all state transitions.
- Test edge cases (empty sets, deleted studies, DB switch).
- Test interaction between sets, filters, study focus, and Summary Table.
- Full regression suite.
