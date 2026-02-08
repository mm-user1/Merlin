# Phase 1-2: Studies Manager Filter

## Overview

Add a text filter to the Studies Manager section on the Results page. A new "Filter" button between Select and Delete toggles a text input field. Typing in the input filters the studies list in real time (case-insensitive substring match on study name). The filter persists across database switches.

## Current State

### HTML (results.html:25-33)
```html
<div class="collapsible-content studies-manager">
  <div class="studies-list"></div>
  <div class="manager-buttons">
    <button class="manager-btn" id="studySelectBtn">Select</button>
    <button class="manager-btn delete-btn" id="studyDeleteBtn">Delete</button>
  </div>
</div>
```

### Button Styling (style.css:1434-1472)
- Normal: `background: #e0e0e0; border: 1px solid #b8b8b8`
- Hover: `background: #d8d8d8; border-color: #a8a8a8`
- Active: `background: #c8c8c8; border-color: #989898`

### State (results-state.js:70-71)
```js
multiSelect: false,
selectedStudies: []
```

### Key Functions (results-controller.js)
- `renderStudiesList(studies)` (line 123) - renders study items into `.studies-list`
- `loadStudiesList()` (line 165) - fetches from API, calls `renderStudiesList()`
- `bindStudiesManager()` (line 883) - wires Select/Delete button events
- `resetForDbSwitch()` (line 177) - resets state on DB change (must NOT reset filter)

## Design

### Layout
```
  study-item-1
  study-item-2
  study-item-3
[ Select ]  [ Filter ]  [ Delete ]
[_______________________________ ]    <-- appears when Filter is active
```

The text input appears as a full-width row below the three buttons, inside `manager-buttons` or as a sibling div. Hidden by default, shown when filter is active. Plain empty input field, no icons, no placeholder.

### Behavior

| Action | Result |
|--------|--------|
| Click Filter (off -> on) | Button gets `active` class, input row appears, input is auto-focused |
| Type text | Studies list filters in real time (case-insensitive substring match on study name), non-matching items get `display: none` |
| Click Filter (on -> off) | Button loses `active` class, input row hides, filter text cleared, all studies visible |
| DB switch while filter active | Filter stays enabled, `resetForDbSwitch()` does NOT touch filter state, `renderStudiesList()` re-applies filter after loading new studies |
| Select mode + Filter | Both work together: filter narrows visible list, multi-select operates on visible items |
| Delete while filtered | Deletes selected/current study as normal (filter has no effect on delete logic) |
| Empty filter text while active | All studies visible (empty string matches everything) |

## Files to Change

### 1. `src/ui/static/js/results-state.js`

Add two new fields to `ResultsState` (after line 71):

```js
filterActive: false,
filterText: ''
```

### 2. `src/ui/templates/results.html`

Add Filter button between Select and Delete. Add hidden filter input row below the buttons.

**Before (lines 29-32):**
```html
<div class="manager-buttons">
  <button class="manager-btn" id="studySelectBtn">Select</button>
  <button class="manager-btn delete-btn" id="studyDeleteBtn">Delete</button>
</div>
```

**After:**
```html
<div class="manager-buttons">
  <button class="manager-btn" id="studySelectBtn">Select</button>
  <button class="manager-btn" id="studyFilterBtn">Filter</button>
  <button class="manager-btn delete-btn" id="studyDeleteBtn">Delete</button>
</div>
<div class="manager-filter-row" id="studyFilterRow" style="display:none;">
  <input type="text" id="studyFilterInput" class="manager-filter-input" />
</div>
```

### 3. `src/ui/static/css/style.css`

Add styles after the existing `.manager-btn` block (~line 1473):

```css
.manager-filter-row {
  padding: 0 10px 5px;
}

.manager-filter-input {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid #b8b8b8;
  border-radius: 3px;
  font-size: 12px;
  color: #2a2a2a;
  background: #fff;
  box-sizing: border-box;
  outline: none;
}

.manager-filter-input:focus {
  border-color: #a8a8a8;
}
```

### 4. `src/ui/static/js/results-controller.js`

#### 4a. Update `renderStudiesList()` (~line 123)

After appending each study item to the list, apply the filter. Add at the end of the function (after the `forEach` loop):

```js
applyStudiesFilter();
```

#### 4b. Add `applyStudiesFilter()` function

New function near `renderStudiesList()`:

```js
function applyStudiesFilter() {
  const filterText = ResultsState.filterText.toLowerCase();
  const items = document.querySelectorAll('.studies-list .study-item');
  items.forEach(item => {
    const name = item.querySelector('.study-name');
    if (!name) return;
    const match = !filterText || name.textContent.toLowerCase().includes(filterText);
    item.style.display = match ? '' : 'none';
  });
}
```

#### 4c. Update `bindStudiesManager()` (~line 883)

Add Filter button wiring after the existing Select/Delete handlers:

```js
const filterBtn = document.getElementById('studyFilterBtn');
const filterRow = document.getElementById('studyFilterRow');
const filterInput = document.getElementById('studyFilterInput');

if (filterBtn && filterRow && filterInput) {
  // Restore active state on page load
  filterBtn.classList.toggle('active', ResultsState.filterActive);
  filterRow.style.display = ResultsState.filterActive ? '' : 'none';
  filterInput.value = ResultsState.filterText;

  filterBtn.addEventListener('click', () => {
    ResultsState.filterActive = !ResultsState.filterActive;
    filterBtn.classList.toggle('active', ResultsState.filterActive);
    filterRow.style.display = ResultsState.filterActive ? '' : 'none';

    if (ResultsState.filterActive) {
      filterInput.focus();
    } else {
      ResultsState.filterText = '';
      filterInput.value = '';
      applyStudiesFilter();
    }
  });

  filterInput.addEventListener('input', () => {
    ResultsState.filterText = filterInput.value;
    applyStudiesFilter();
  });
}
```

#### 4d. Confirm `resetForDbSwitch()` (~line 177)

Verify that `resetForDbSwitch()` does NOT reset `filterActive` or `filterText`. Current code does not touch these fields (they don't exist yet), so no changes needed here -- just do not add them to the reset function.

## What NOT to Change

- No backend changes (pure client-side filtering)
- No changes to `api.js`
- No changes to `resetForDbSwitch()` (filter intentionally persists)
- No icons or placeholder text in the filter input
- No new dependencies

## Testing Checklist

- [ ] Filter button appears between Select and Delete
- [ ] Clicking Filter shows empty input field below buttons
- [ ] Typing filters studies list in real time (case-insensitive)
- [ ] Clicking Filter again hides input, clears filter, shows all studies
- [ ] Filter active state (grey button) is visually distinct
- [ ] Switching database keeps filter active and applied to new studies list
- [ ] Select (multi-select) mode works alongside active filter
- [ ] Delete works on filtered/unfiltered studies
- [ ] Empty filter text shows all studies
- [ ] Page reload resets filter (no persistence to storage needed)
