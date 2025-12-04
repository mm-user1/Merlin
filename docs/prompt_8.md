# Phase 8: Dynamic Optimizer + CSS Extraction - Task Prompt

**Phase:** 8 of 11
**Complexity:** 🟡 MEDIUM
**Risk:** 🟡 MEDIUM
**Estimated Effort:** 8-12 hours
**Priority:** 🔴 CRITICAL - FIXES PRODUCTION BLOCKER
**Status:** Ready for Execution

---

## Table of Contents

1. [Project Context](#project-context)
2. [Phase 8 Objective](#phase-8-objective)
3. [Why This Phase Was Added](#why-this-phase-was-added)
4. [Current vs Target Architecture](#current-vs-target-architecture)
5. [Problem Analysis](#problem-analysis)
6. [Implementation Requirements](#implementation-requirements)
7. [Detailed Implementation Guide](#detailed-implementation-guide)
8. [Testing Strategy](#testing-strategy)
9. [Validation Checklist](#validation-checklist)
10. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
11. [Success Criteria](#success-criteria)

---

## Project Context

You are working on a cryptocurrency/forex trading strategy backtesting platform that has successfully completed 7 phases of architecture migration. Phase 6 audit revealed a critical issue: the optimizer UI has hardcoded S01 parameters that prevent other strategies from working correctly.

### Completed Phases

- ✅ **Phase -1**: Test Infrastructure Setup (9 tests passing)
- ✅ **Phase 0**: Regression Baseline for S01 (12 regression tests)
- ✅ **Phase 1**: Core Extraction to `src/core/`
- ✅ **Phase 2**: Export Extraction to `export.py`
- ✅ **Phase 3**: Grid Search Removal (Optuna-only)
- ✅ **Phase 4**: Metrics Extraction to `metrics.py`
- ✅ **Phase 5**: Indicators Package Extraction
- ✅ **Phase 6**: S04 StochRSI Strategy (architecture validation)
- ✅ **Phase 7**: S01 Migration (bit-exact compatibility achieved)

### Current System State

**Strategies Available**:
- `s01_trailing_ma` - Legacy S01 (will be removed in Phase 9)
- `s01_trailing_ma_migrated` - Migrated S01 (production-ready)
- `s04_stochrsi` - StochRSI strategy (working)

**UI State**:
- **Backtest form**: ✅ Dynamic, works for all strategies
- **Optimizer form**: ❌ Hardcoded S01 parameters (BROKEN)
- **File size**: 4746 lines (monolithic HTML)

**Test Suite**: 76 tests passing

---

## Phase 8 Objective

**Goal**: Fix the hardcoded S01 parameters in the optimizer UI and extract CSS as preparatory work for Phase 10 frontend separation.

**Two Main Tasks**:
1. **CSS Extraction** (2-3 hours): Move all `<style>` blocks to external CSS file
2. **Dynamic Optimizer** (6-9 hours): Replace hardcoded optimizer HTML with dynamic generation from `config.json`

**Success Criteria**:
1. ✅ CSS extracted to `src/static/css/style.css`, page looks identical
2. ✅ Optimizer form generated dynamically from strategy config
3. ✅ S01 optimizer shows S01 parameters correctly
4. ✅ S04 optimizer shows S04 parameters (6 optimizable params)
5. ✅ Switching strategies updates optimizer form correctly
6. ✅ Optuna optimization works with both strategies

---

## Why This Phase Was Added

### Phase 6 Audit Finding

During Phase 6 testing, a critical issue was discovered:

**Problem**: The optimizer UI has hardcoded S01 parameters in two places:
1. **Hardcoded HTML controls** (lines 1455-1829 in `index.html`, ~374 lines)
2. **Hardcoded JavaScript array** `OPTIMIZATION_PARAMETERS` (lines 2668-2840, ~172 lines)

**Impact**:
- When S04 is selected, optimizer still shows S01 parameters instead of S04 parameters
- Blocks production use of S04
- Will block ANY future strategy additions
- Creates confusion for users (wrong parameters displayed)
- Must be fixed BEFORE deleting legacy code in Phase 9

**Root Cause**: UI was built when only S01 existed. When dynamic backtest form was added, optimizer was forgotten.

### Why Fix Now

1. **Phase 9 Dependency**: Phase 9 will delete legacy S01 code. If UI still has S01 hardcoding, the system will break.
2. **Multi-Strategy Support**: With S01 migrated and S04 working, we need the UI to support multiple strategies properly.
3. **User Experience**: Current state is confusing and broken for non-S01 strategies.
4. **Architecture Completion**: Clean UI is part of the target architecture.

---

## Current vs Target Architecture

### Current Architecture (Broken)

**User Flow**:
```
User selects S04 → Backtest form loads S04 params ✅
                 → Optimizer form shows S01 params ❌ (hardcoded HTML)
```

**Code Structure**:
```javascript
// index.html lines 1455-1829: Hardcoded HTML
<div class="opt-row">
  <input id="opt-maLength" type="checkbox" checked />
  <label class="opt-label" for="opt-maLength">T MA Length</label>
  <div class="opt-controls">
    <label>From:</label>
    <input class="tiny-input" id="opt-maLength-from" type="number" value="30" step="5" />
    <label>To:</label>
    <input class="tiny-input" id="opt-maLength-to" type="number" value="100" step="5" />
    <label>Step:</label>
    <input class="tiny-input" id="opt-maLength-step" type="number" value="5" step="1" />
  </div>
</div>
<!-- ... repeated for 19 S01 parameters ... -->

// index.html lines 2668-2840: Hardcoded JavaScript
const OPTIMIZATION_PARAMETERS = [
  { name: 'maLength', label: 'T MA Length', from: 30, to: 100, step: 5 },
  { name: 'closeCountLong', label: 'Close Count Long', from: 3, to: 10, step: 1 },
  // ... 19 S01-specific parameters ...
];
```

**Problem**: When user selects S04 (which has 6 optimizable parameters), the UI still shows 19 S01 parameters.

### Target Architecture (Fixed)

**User Flow**:
```
User selects S04 → Backtest form loads S04 params ✅
                 → Optimizer form loads S04 params ✅ (dynamic from config.json)
```

**Code Structure**:
```html
<!-- index.html: Dynamic container -->
<div id="optimizerParamsContainer">
  <!-- Parameters generated dynamically by JavaScript -->
</div>
```

```javascript
// JavaScript: Dynamic generation
async function loadStrategyConfig(strategyId) {
  const response = await fetch(`/api/strategies/${strategyId}/config`);
  currentStrategyConfig = await response.json();

  updateStrategyInfo(currentStrategyConfig);
  generateBacktestForm(currentStrategyConfig);  // Already exists
  generateOptimizerForm(currentStrategyConfig); // NEW - to be implemented
}

function generateOptimizerForm(config) {
  const container = document.getElementById('optimizerParamsContainer');
  container.innerHTML = ''; // Clear existing

  // Only show parameters where optimize.enabled === true
  const optimizableParams = Object.entries(config.parameters)
    .filter(([name, def]) => def.optimize && def.optimize.enabled);

  // Generate HTML for each parameter
  optimizableParams.forEach(([name, def]) => {
    const row = createOptimizerRow(name, def);
    container.appendChild(row);
  });
}
```

**Benefits**:
- ✅ Works for ANY strategy automatically
- ✅ No hardcoding required
- ✅ Easy to add new strategies
- ✅ Consistent with backtest form approach

---

## Problem Analysis

### Hardcoded S01 References Audit

#### Backend (`server.py`) - 19 S01-specific blocks

**Lines with S01 hardcoding**:
- 75-130: `DEFAULT_PRESET` dict with S01 parameters as defaults
- 25-37: `MA_TYPES` tuple (shared, but referenced by S01 logic)
- 596, 962, 1163, 1503: Default strategy ID: `"s01_trailing_ma"`
- 678-693: S01-specific parameter handling for warmup calculation
- 1198-1215: S01-specific MA type mappings (`ma_types_trend`, `ma_types_trail_long`, etc.)
- 1341-1347: S01-specific trail type locking logic

**Total**: ~160 lines of S01-specific backend code (will be cleaned in Phase 9)

#### Frontend (`index.html`) - Major hardcoded sections

**Before Phase 8**:
- Lines 1455-1829: Hardcoded optimizer HTML (~374 lines)
- Lines 2668-2840: `OPTIMIZATION_PARAMETERS` array (19 parameters, ~172 lines)
- MA type checkboxes (hardcoded for S01 trend/trail MA selection)

**Total**: ~546 lines of S01-specific frontend code

**Grand Total**: ~700 lines of S01-specific hardcoded code

### What Gets Fixed in Phase 8

**Frontend Only** (Backend cleanup happens in Phase 9):
1. ❌ Delete hardcoded optimizer HTML (lines 1455-1829)
2. ✅ Add dynamic container `<div id="optimizerParamsContainer">`
3. ❌ Delete `OPTIMIZATION_PARAMETERS` array (lines 2668-2840)
4. ✅ Implement `generateOptimizerForm(config)` function
5. ✅ Implement `createOptimizerRow(paramName, paramDef)` helper
6. ✅ Update `bindOptimizerInputs()` to work with dynamic IDs
7. ✅ Update optimizer payload collection to work dynamically
8. ✅ Extract all CSS to external file

---

## Implementation Requirements

### 1. Directory Structure

Create static directory structure:

```bash
mkdir -p src/static/css
```

**Note**: `src/static/js/` will be created in Phase 10 (Frontend Separation).

### 2. Strategy Config Format

Each strategy's `config.json` defines which parameters are optimizable:

```json
{
  "id": "s04_stochrsi",
  "name": "S04 StochRSI",
  "parameters": {
    "rsiLen": {
      "type": "int",
      "label": "RSI Length",
      "default": 14,
      "min": 5,
      "max": 50,
      "step": 1,
      "group": "Indicators",
      "optimize": {
        "enabled": true,
        "min": 10,
        "max": 20,
        "step": 2
      }
    },
    "stochLen": {
      "type": "int",
      "label": "Stochastic Length",
      "default": 14,
      "min": 5,
      "max": 50,
      "step": 1,
      "group": "Indicators",
      "optimize": {
        "enabled": true,
        "min": 10,
        "max": 20,
        "step": 2
      }
    },
    // ... more parameters ...
  }
}
```

**Key Points**:
- `optimize.enabled: true` → Parameter appears in optimizer
- `optimize.enabled: false` → Parameter hidden from optimizer
- `optimize.min/max/step` → Ranges for optimization (can differ from UI ranges)

### 3. Flask Static Serving

Ensure Flask serves static files correctly:

```python
# src/server.py
app = Flask(__name__, static_folder='static', static_url_path='/static')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)
```

### 4. HTML Structure

**Current** (lines 1455-1829):
```html
<div class="opt-section">
  <div class="opt-section-title">Trend MA</div>
  <div class="opt-row">
    <input id="opt-maLength" type="checkbox" checked />
    <label class="opt-label" for="opt-maLength">T MA Length</label>
    <!-- ... controls ... -->
  </div>
  <!-- ... more rows ... -->
</div>
```

**Target** (dynamic):
```html
<div id="optimizerParamsContainer">
  <!-- Generated dynamically by JavaScript -->
</div>
```

---

## Detailed Implementation Guide

### Step 1: CSS Extraction (2-3 hours)

**Goal**: Move all `<style>` blocks from `index.html` to external CSS file.

#### 1.1: Identify All Style Blocks

Search for all `<style>` tags in `index.html`:

```bash
grep -n "<style>" src/index.html
```

Typical sections:
- Main styles
- Form styles
- Button styles
- Table styles
- Modal styles
- Optimizer styles

#### 1.2: Create CSS File

```bash
mkdir -p src/static/css
touch src/static/css/style.css
```

#### 1.3: Extract Styles

**Find all `<style>` blocks**:
```html
<!-- index.html -->
<style>
  body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
    background: #f5f5f5;
  }
  /* ... more styles ... */
</style>
```

**Copy to CSS file**:
```css
/* src/static/css/style.css */
body {
  font-family: Arial, sans-serif;
  margin: 0;
  padding: 20px;
  background: #f5f5f5;
}
/* ... more styles ... */
```

**Important**: Preserve ALL styles exactly as they are. No refactoring yet.

#### 1.4: Update HTML

**Remove all `<style>` blocks** from `index.html`.

**Add link in `<head>`**:
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>S01 Trailing MA - Backtester & Optimizer</title>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
  <!-- ... -->
</body>
</html>
```

#### 1.5: Update Flask Configuration

Ensure static serving is configured:

```python
# src/server.py (already exists, verify it's correct)
app = Flask(__name__, static_folder='static', static_url_path='/static')

# Optional: Explicit route for static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)
```

#### 1.6: Test CSS Extraction

**Start server**:
```bash
cd src
python server.py
```

**Open browser**: `http://localhost:8000` (or configured port)

**Verify**:
- [ ] Page loads without errors
- [ ] Page looks IDENTICAL to before
- [ ] No missing styles
- [ ] Browser DevTools shows CSS loading from `/static/css/style.css`

**Check for errors**:
```javascript
// Open browser console (F12)
// Should see NO 404 errors for style.css
// Network tab should show: style.css - Status 200 OK
```

---

### Step 2: Remove Hardcoded Optimizer HTML (30 min)

**Goal**: Replace hardcoded optimizer HTML with dynamic container.

#### 2.1: Locate Hardcoded Section

Find the optimizer parameters section in `index.html` (around lines 1455-1829):

```html
<!-- OLD: Hardcoded S01 parameters -->
<div class="opt-section">
  <div class="opt-section-title">Trend MA</div>
  <div class="opt-row">
    <input id="opt-maLength" type="checkbox" checked />
    <label class="opt-label" for="opt-maLength">T MA Length</label>
    <div class="opt-controls">
      <label>From:</label>
      <input class="tiny-input" id="opt-maLength-from" type="number" value="30" step="5" />
      <label>To:</label>
      <input class="tiny-input" id="opt-maLength-to" type="number" value="100" step="5" />
      <label>Step:</label>
      <input class="tiny-input" id="opt-maLength-step" type="number" value="5" step="1" />
    </div>
  </div>
  <!-- ... 18 more parameters ... -->
</div>

<div class="opt-section">
  <div class="opt-section-title">Close Counts</div>
  <!-- ... more hardcoded rows ... -->
</div>

<!-- ... more sections ... -->
```

#### 2.2: Replace with Dynamic Container

**Delete lines 1455-1829** (entire hardcoded section).

**Replace with**:
```html
<!-- NEW: Dynamic container -->
<div id="optimizerParamsContainer" class="optimizer-params-container">
  <!-- Parameters will be generated dynamically here -->
</div>
```

**Add CSS for container** (if not already in style.css):
```css
.optimizer-params-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
```

---

### Step 3: Implement Dynamic Optimizer Form Generator (4-6 hours)

**Goal**: Create JavaScript functions to generate optimizer form from `config.json`.

#### 3.1: Create `generateOptimizerForm()` Function

**Add to existing JavaScript** (find the section with other generator functions):

```javascript
/**
 * Generate optimizer parameters form from strategy config.
 * Only shows parameters where optimize.enabled === true.
 *
 * @param {Object} config - Strategy configuration object
 */
function generateOptimizerForm(config) {
  const container = document.getElementById('optimizerParamsContainer');
  if (!container) {
    console.error('Optimizer container not found (#optimizerParamsContainer)');
    return;
  }

  // Clear existing content
  container.innerHTML = '';

  const params = config.parameters || {};
  const groups = {};

  // Group parameters by their 'group' property
  for (const [paramName, paramDef] of Object.entries(params)) {
    // Only include parameters that are optimizable
    if (paramDef.optimize && paramDef.optimize.enabled) {
      const group = paramDef.group || 'Other';
      if (!groups[group]) {
        groups[group] = [];
      }
      groups[group].push({ name: paramName, def: paramDef });
    }
  }

  // Check if any optimizable parameters exist
  const totalParams = Object.values(groups).reduce((sum, g) => sum + g.length, 0);
  if (totalParams === 0) {
    container.innerHTML = '<p class="warning">No optimizable parameters defined for this strategy.</p>';
    return;
  }

  // Generate HTML for each group
  for (const [groupName, groupParams] of Object.entries(groups)) {
    const groupDiv = document.createElement('div');
    groupDiv.className = 'opt-section';

    const groupTitle = document.createElement('div');
    groupTitle.className = 'opt-section-title';
    groupTitle.textContent = groupName;
    groupDiv.appendChild(groupTitle);

    groupParams.forEach(({ name, def }) => {
      const row = createOptimizerRow(name, def);
      groupDiv.appendChild(row);
    });

    container.appendChild(groupDiv);
  }

  // Rebind event listeners after generating form
  bindOptimizerInputs();

  console.log(`Generated optimizer form with ${totalParams} parameters`);
}
```

#### 3.2: Create `createOptimizerRow()` Helper

**Add after `generateOptimizerForm()`**:

```javascript
/**
 * Create a single optimizer parameter row.
 *
 * @param {string} paramName - Parameter name (e.g., 'maLength')
 * @param {Object} paramDef - Parameter definition from config.json
 * @returns {HTMLElement} - The created row element
 */
function createOptimizerRow(paramName, paramDef) {
  const row = document.createElement('div');
  row.className = 'opt-row';

  // Checkbox to enable/disable optimization for this parameter
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.id = `opt-${paramName}`;
  checkbox.checked = paramDef.optimize.enabled || false;
  checkbox.dataset.paramName = paramName; // Store for later reference

  // Label
  const label = document.createElement('label');
  label.className = 'opt-label';
  label.htmlFor = `opt-${paramName}`;
  label.textContent = paramDef.label || paramName;

  // Controls div (from, to, step)
  const controlsDiv = document.createElement('div');
  controlsDiv.className = 'opt-controls';

  // Determine parameter type
  const isInt = paramDef.type === 'int' || paramDef.type === 'integer';

  // Determine default step
  const defaultStep = isInt ? 1 : 0.1;
  const minStep = isInt ? 1 : 0.01;

  // From input
  const fromLabel = document.createElement('label');
  fromLabel.textContent = 'From:';
  const fromInput = document.createElement('input');
  fromInput.className = 'tiny-input';
  fromInput.id = `opt-${paramName}-from`;
  fromInput.type = 'number';
  fromInput.value = paramDef.optimize.min !== undefined
    ? paramDef.optimize.min
    : (paramDef.min !== undefined ? paramDef.min : 0);
  fromInput.step = paramDef.optimize.step || paramDef.step || defaultStep;
  fromInput.dataset.paramName = paramName;

  // To input
  const toLabel = document.createElement('label');
  toLabel.textContent = 'To:';
  const toInput = document.createElement('input');
  toInput.className = 'tiny-input';
  toInput.id = `opt-${paramName}-to`;
  toInput.type = 'number';
  toInput.value = paramDef.optimize.max !== undefined
    ? paramDef.optimize.max
    : (paramDef.max !== undefined ? paramDef.max : 100);
  toInput.step = paramDef.optimize.step || paramDef.step || defaultStep;
  toInput.dataset.paramName = paramName;

  // Step input
  const stepLabel = document.createElement('label');
  stepLabel.textContent = 'Step:';
  const stepInput = document.createElement('input');
  stepInput.className = 'tiny-input';
  stepInput.id = `opt-${paramName}-step`;
  stepInput.type = 'number';
  stepInput.value = paramDef.optimize.step || paramDef.step || defaultStep;
  stepInput.step = minStep;
  stepInput.min = minStep;
  stepInput.dataset.paramName = paramName;

  // Assemble controls
  controlsDiv.appendChild(fromLabel);
  controlsDiv.appendChild(fromInput);
  controlsDiv.appendChild(toLabel);
  controlsDiv.appendChild(toInput);
  controlsDiv.appendChild(stepLabel);
  controlsDiv.appendChild(stepInput);

  // Assemble row
  row.appendChild(checkbox);
  row.appendChild(label);
  row.appendChild(controlsDiv);

  return row;
}
```

#### 3.3: Update `loadStrategyConfig()` to Call Generator

**Find the existing `loadStrategyConfig()` function** (should look like this):

```javascript
async function loadStrategyConfig(strategyId) {
  try {
    const response = await fetch(`/api/strategies/${strategyId}/config`);
    currentStrategyConfig = await response.json();

    updateStrategyInfo(currentStrategyConfig);
    generateBacktestForm(currentStrategyConfig);
    // ADD THIS LINE ↓
    generateOptimizerForm(currentStrategyConfig);

    console.log(`Loaded strategy: ${currentStrategyConfig.name}`);
  } catch (error) {
    console.error('Failed to load strategy config:', error);
    alert('Error loading strategy configuration');
  }
}
```

**Add the call to `generateOptimizerForm()`** after `generateBacktestForm()`.

#### 3.4: Delete Hardcoded `OPTIMIZATION_PARAMETERS` Array

**Find and DELETE** (around lines 2668-2840):

```javascript
// DELETE THIS ENTIRE ARRAY
const OPTIMIZATION_PARAMETERS = [
  { name: 'maLength', label: 'T MA Length', from: 30, to: 100, step: 5 },
  { name: 'closeCountLong', label: 'Close Count Long', from: 3, to: 10, step: 1 },
  // ... 17 more parameters ...
];
```

This array is no longer needed since parameters are loaded from `config.json`.

---

### Step 4: Update Event Binding (1-2 hours)

**Goal**: Make event listeners work with dynamically generated IDs.

#### 4.1: Update `bindOptimizerInputs()` Function

**Find the existing `bindOptimizerInputs()` function** and replace it:

```javascript
/**
 * Bind event listeners to optimizer inputs.
 * Must be called after dynamic form generation.
 */
function bindOptimizerInputs() {
  // Get all optimizer checkboxes (exclude from/to/step inputs)
  const checkboxes = document.querySelectorAll(
    '[id^="opt-"]:not([id$="-from"]):not([id$="-to"]):not([id$="-step"])'
  );

  checkboxes.forEach(checkbox => {
    // Remove existing listener if any (prevent duplicates)
    checkbox.removeEventListener('change', handleOptimizerCheckboxChange);

    // Add new listener
    checkbox.addEventListener('change', handleOptimizerCheckboxChange);

    // Initialize state (disable inputs if checkbox unchecked)
    handleOptimizerCheckboxChange.call(checkbox);
  });

  console.log(`Bound event listeners to ${checkboxes.length} optimizer checkboxes`);
}

/**
 * Handle optimizer checkbox change event.
 * Enables/disables corresponding from/to/step inputs.
 */
function handleOptimizerCheckboxChange() {
  const paramName = this.dataset.paramName || this.id.replace('opt-', '');
  const fromInput = document.getElementById(`opt-${paramName}-from`);
  const toInput = document.getElementById(`opt-${paramName}-to`);
  const stepInput = document.getElementById(`opt-${paramName}-step`);

  const disabled = !this.checked;

  if (fromInput) fromInput.disabled = disabled;
  if (toInput) toInput.disabled = disabled;
  if (stepInput) stepInput.disabled = disabled;

  // Optional: Visual feedback
  const row = this.closest('.opt-row');
  if (row) {
    if (disabled) {
      row.classList.add('disabled');
    } else {
      row.classList.remove('disabled');
    }
  }
}
```

**Add CSS for disabled state** (if not already in style.css):

```css
.opt-row.disabled {
  opacity: 0.5;
}

.opt-row.disabled .opt-controls input {
  background-color: #f0f0f0;
  cursor: not-allowed;
}
```

---

### Step 5: Update Optimization Payload Collection (1-2 hours)

**Goal**: Collect optimizer parameters dynamically instead of using hardcoded array.

#### 5.1: Update `collectOptimizerParams()` Function

**Find the function that collects optimizer parameters** (might be named differently, search for where optimizer payload is built):

```javascript
/**
 * Collect enabled optimizer parameters and their ranges.
 * Returns object with parameter names as keys and [from, to, step] as values.
 *
 * @returns {Object} - e.g., { 'maLength': [30, 100, 5], 'closeCountLong': [3, 10, 1] }
 */
function collectOptimizerParams() {
  const ranges = {};

  // Get all optimizer checkboxes
  const checkboxes = document.querySelectorAll(
    '[id^="opt-"]:not([id$="-from"]):not([id$="-to"]):not([id$="-step"])'
  );

  checkboxes.forEach(checkbox => {
    if (checkbox.checked) {
      const paramName = checkbox.dataset.paramName || checkbox.id.replace('opt-', '');

      const fromInput = document.getElementById(`opt-${paramName}-from`);
      const toInput = document.getElementById(`opt-${paramName}-to`);
      const stepInput = document.getElementById(`opt-${paramName}-step`);

      if (fromInput && toInput && stepInput) {
        const fromValue = parseFloat(fromInput.value);
        const toValue = parseFloat(toInput.value);
        const stepValue = parseFloat(stepInput.value);

        // Validate values
        if (isNaN(fromValue) || isNaN(toValue) || isNaN(stepValue)) {
          console.warn(`Invalid values for parameter ${paramName}, skipping`);
          return;
        }

        if (fromValue >= toValue) {
          console.warn(`From >= To for parameter ${paramName}, skipping`);
          return;
        }

        if (stepValue <= 0) {
          console.warn(`Invalid step for parameter ${paramName}, skipping`);
          return;
        }

        ranges[paramName] = [fromValue, toValue, stepValue];
      }
    }
  });

  return ranges;
}
```

#### 5.2: Update Optimization Request Handler

**Find the function that sends optimization request** (typically triggered by "Optimize" button):

```javascript
async function runOptimization() {
  // Collect optimizer parameters (uses new dynamic collection)
  const paramRanges = collectOptimizerParams();

  // Validate at least one parameter is enabled
  if (Object.keys(paramRanges).length === 0) {
    alert('Please enable at least one parameter to optimize');
    return;
  }

  // Collect other form data (CSV files, date range, Optuna settings, etc.)
  const csvFiles = getSelectedCSVFiles(); // Implement as needed
  const dateRange = getDateRange(); // Implement as needed
  const optunaConfig = getOptunaConfig(); // Implement as needed

  // Build request payload
  const payload = {
    strategy: currentStrategyId,
    csv_files: csvFiles,
    date_range: dateRange,
    param_ranges: paramRanges,
    optuna_config: optunaConfig,
    // ... other fields ...
  };

  console.log('Optimization payload:', payload);

  // Send request
  try {
    const response = await fetch('/api/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}: ${response.statusText}`);
    }

    // Handle response (download CSV, show results, etc.)
    const blob = await response.blob();
    downloadFile(blob, 'optimization_results.csv');

  } catch (error) {
    console.error('Optimization failed:', error);
    alert(`Optimization failed: ${error.message}`);
  }
}
```

---

### Step 6: Testing and Validation (2-3 hours)

**Goal**: Thoroughly test the dynamic optimizer with multiple strategies.

#### 6.1: Test CSS Extraction

**Checklist**:
- [ ] Start server: `python src/server.py`
- [ ] Open browser: `http://localhost:8000`
- [ ] Page loads without errors
- [ ] Page looks IDENTICAL to before extraction
- [ ] Browser DevTools → Network tab shows `style.css` loaded (Status 200)
- [ ] Browser DevTools → Console shows NO CSS errors
- [ ] All UI elements styled correctly (buttons, forms, tables)

#### 6.2: Test Optimizer with S01

**Steps**:
1. Select S01 from strategy dropdown
2. Navigate to Optimizer tab
3. Verify optimizer parameters displayed:
   - Should show ~19 S01 parameters grouped by category
   - Parameters: maLength, closeCountLong, closeCountShort, stops, trails, etc.
   - Default ranges loaded from `config.json`
4. Check/uncheck parameter checkboxes
   - Inputs should disable/enable correctly
5. Modify from/to/step values
6. Run small optimization (10 trials)
7. Verify results download correctly

**Expected S01 Parameters** (from `s01_trailing_ma/config.json`):
- Trend MA: maLength
- Close Counts: closeCountLong, closeCountShort
- Stops: stopLongX, stopLongRR, stopLongLP, stopShortX, stopShortRR, stopShortLP
- Stop Limits: stopLongMaxPct, stopShortMaxPct, stopLongMaxDays, stopShortMaxDays
- Trails: trailRRLong, trailRRShort, trailLongLength, trailShortLength, trailLongOffset, trailShortOffset

#### 6.3: Test Optimizer with S04

**Steps**:
1. Select S04 from strategy dropdown
2. Navigate to Optimizer tab
3. Verify optimizer parameters displayed:
   - Should show 6 S04 parameters
   - Parameters: rsiLen, stochLen, obLevel, osLevel, extLookback, confirmBars
   - No S01 parameters visible
4. Check/uncheck parameter checkboxes
5. Modify ranges
6. Run small optimization (10 trials)
7. Verify results download correctly

**Expected S04 Parameters** (from `s04_stochrsi/config.json`):
```json
{
  "rsiLen": { "optimize": { "enabled": true, "min": 10, "max": 20, "step": 2 } },
  "stochLen": { "optimize": { "enabled": true, "min": 10, "max": 20, "step": 2 } },
  "obLevel": { "optimize": { "enabled": true, "min": 70, "max": 85, "step": 5 } },
  "osLevel": { "optimize": { "enabled": true, "min": 15, "max": 30, "step": 5 } },
  "extLookback": { "optimize": { "enabled": true, "min": 5, "max": 20, "step": 5 } },
  "confirmBars": { "optimize": { "enabled": true, "min": 1, "max": 5, "step": 1 } }
}
```

#### 6.4: Test Strategy Switching

**Steps**:
1. Select S01 → Verify optimizer shows S01 params
2. Switch to S04 → Verify optimizer updates to S04 params
3. Switch back to S01 → Verify optimizer updates back to S01 params
4. Switch to S04 again → Verify optimizer updates to S04 params

**Verify**:
- [ ] No JavaScript errors in console
- [ ] Parameters update immediately on strategy change
- [ ] No leftover parameters from previous strategy
- [ ] Checkboxes reset to default state
- [ ] Ranges reset to defaults from config.json

#### 6.5: Test Edge Cases

**Test 1: Strategy with no optimizable parameters**

Create test scenario (or temporarily modify config):
```json
{
  "parameters": {
    "param1": {
      "optimize": { "enabled": false }
    }
  }
}
```

Expected: Show warning message "No optimizable parameters defined for this strategy."

**Test 2: Mixed enabled/disabled parameters**

Verify only `enabled: true` parameters appear in optimizer.

**Test 3: Parameter groups**

Verify parameters grouped correctly by `group` property.

**Test 4: Missing optimize config**

Test parameter without `optimize` property:
```json
{
  "param1": {
    "type": "int",
    "default": 10
    // NO "optimize" property
  }
}
```

Expected: Parameter NOT shown in optimizer (only backtest form).

#### 6.6: Test Full Optimization Workflow

**S01 Full Workflow**:
1. Select S01 strategy
2. Load CSV data
3. Set date range
4. Enable 3-5 parameters in optimizer
5. Set reasonable ranges (small search space for testing)
6. Configure Optuna: 20 trials, timeout 60s
7. Run optimization
8. Verify CSV downloads
9. Verify CSV has correct columns and data

**S04 Full Workflow**:
1. Select S04 strategy
2. Load CSV data
3. Set date range
4. Enable 3-4 parameters
5. Set ranges
6. Configure Optuna: 15 trials
7. Run optimization
8. Verify results

---

## Validation Checklist

### Phase 8.1: CSS Extraction

- [ ] Created `src/static/css/` directory
- [ ] Created `src/static/css/style.css`
- [ ] Extracted all `<style>` blocks to `style.css`
- [ ] Removed all `<style>` blocks from `index.html`
- [ ] Added `<link rel="stylesheet" href="/static/css/style.css">` to HTML
- [ ] Flask static serving configured correctly
- [ ] Server starts without errors
- [ ] Page loads and looks identical
- [ ] Browser DevTools shows CSS loading (Status 200)
- [ ] No console errors

### Phase 8.2: Dynamic Optimizer

- [ ] Removed hardcoded optimizer HTML (lines 1455-1829)
- [ ] Added `<div id="optimizerParamsContainer">` dynamic container
- [ ] Deleted `OPTIMIZATION_PARAMETERS` array (lines 2668-2840)
- [ ] Implemented `generateOptimizerForm(config)` function
- [ ] Implemented `createOptimizerRow(paramName, paramDef)` helper
- [ ] Updated `loadStrategyConfig()` to call `generateOptimizerForm()`
- [ ] Updated `bindOptimizerInputs()` for dynamic IDs
- [ ] Implemented `handleOptimizerCheckboxChange()` function
- [ ] Updated `collectOptimizerParams()` for dynamic collection
- [ ] Updated optimization request handler

### Phase 8.3: Testing

- [ ] Tested CSS extraction (page looks identical)
- [ ] Tested S01 optimizer (shows S01 parameters)
- [ ] Tested S04 optimizer (shows S04 parameters)
- [ ] Tested strategy switching (parameters update correctly)
- [ ] Tested checkbox enable/disable behavior
- [ ] Tested parameter range modification
- [ ] Tested S01 optimization (small run, 10 trials)
- [ ] Tested S04 optimization (small run, 10 trials)
- [ ] Tested edge cases (no params, mixed enabled/disabled)
- [ ] No JavaScript errors in console
- [ ] All UI interactions work smoothly

### Phase 8.4: Final Validation

- [ ] S01 shows 15-19 optimizable parameters
- [ ] S04 shows 6 optimizable parameters
- [ ] Switching strategies updates form immediately
- [ ] Optimization runs successfully for both strategies
- [ ] Results CSV downloads correctly
- [ ] No regressions in backtest form
- [ ] No regressions in other UI features

### Phase 8.5: Documentation

- [ ] Updated inline comments in JavaScript
- [ ] Documented any deviations or issues
- [ ] Created list of known issues (if any)

### Phase 8.6: Git Commit

- [ ] Committed changes: "Phase 8: Dynamic optimizer + CSS extraction"
- [ ] Tagged commit: `git tag phase-8-complete`
- [ ] Pushed to remote

---

## Common Pitfalls and Solutions

### Pitfall 1: CSS Not Loading

**Symptoms**: Page has no styling, looks broken.

**Causes**:
- Incorrect static folder path
- Flask not configured for static serving
- Typo in CSS filename or path

**Solutions**:
```python
# Verify Flask configuration
app = Flask(__name__, static_folder='static', static_url_path='/static')

# Add explicit route if needed
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)
```

**Debug**:
```bash
# Check file exists
ls -la src/static/css/style.css

# Check Flask routes
# In Python console:
from src.server import app
print(app.url_map)
```

**Browser DevTools**:
- Network tab: Check if `style.css` request returns 200 or 404
- Console: Check for CSS loading errors

### Pitfall 2: Optimizer Container Not Found

**Symptoms**: Console error "Optimizer container not found"

**Cause**: Container ID mismatch or HTML not loaded when JavaScript runs.

**Solution**:
```javascript
// Add defensive check
function generateOptimizerForm(config) {
  const container = document.getElementById('optimizerParamsContainer');
  if (!container) {
    console.error('Optimizer container not found. HTML may not be loaded yet.');
    return;
  }
  // ... rest of function
}
```

**Ensure DOM is loaded**:
```javascript
document.addEventListener('DOMContentLoaded', () => {
  // Initialize here
  loadStrategies();
});
```

### Pitfall 3: Parameters Not Showing

**Symptoms**: Optimizer form is empty when strategy selected.

**Causes**:
- `optimize.enabled` is `false` for all parameters
- `config.json` not loaded correctly
- `generateOptimizerForm()` not called

**Debug**:
```javascript
async function loadStrategyConfig(strategyId) {
  const response = await fetch(`/api/strategies/${strategyId}/config`);
  const config = await response.json();

  console.log('Loaded config:', config);
  console.log('Optimizable params:',
    Object.entries(config.parameters)
      .filter(([n, d]) => d.optimize && d.optimize.enabled)
      .map(([n, d]) => n)
  );

  generateOptimizerForm(config);
}
```

**Check config.json**:
```json
{
  "parameters": {
    "myParam": {
      "optimize": {
        "enabled": true  // ← Must be true
      }
    }
  }
}
```

### Pitfall 4: Event Listeners Not Working

**Symptoms**: Checkboxes don't enable/disable inputs.

**Causes**:
- Event listeners not bound after dynamic generation
- Multiple listeners bound (duplicates)

**Solution**:
```javascript
function generateOptimizerForm(config) {
  // ... generate HTML ...

  // MUST call after generation
  bindOptimizerInputs();
}

function bindOptimizerInputs() {
  const checkboxes = document.querySelectorAll('[id^="opt-"]...');

  checkboxes.forEach(checkbox => {
    // Remove existing listener (prevent duplicates)
    checkbox.removeEventListener('change', handleOptimizerCheckboxChange);

    // Add new listener
    checkbox.addEventListener('change', handleOptimizerCheckboxChange);

    // Initialize state
    handleOptimizerCheckboxChange.call(checkbox);
  });
}
```

### Pitfall 5: Parameter Name Mismatches

**Symptoms**: Optimizer sends wrong parameter names to backend.

**Causes**:
- Frontend uses camelCase, backend expects snake_case
- Parameter names don't match config.json

**Solution**: Use `dataset` attributes to store original parameter names:

```javascript
checkbox.dataset.paramName = paramName;
fromInput.dataset.paramName = paramName;
toInput.dataset.paramName = paramName;
stepInput.dataset.paramName = paramName;

// Later retrieval:
const paramName = checkbox.dataset.paramName || checkbox.id.replace('opt-', '');
```

**Backend mapping**: Should be handled by `StrategyParams.from_dict()`:

```python
# Backend handles camelCase → snake_case
@staticmethod
def from_dict(d: Dict[str, Any]) -> "S01Params":
    return S01Params(
        ma_length=int(d.get('maLength', 50)),  # camelCase input
        # ...
    )
```

### Pitfall 6: Validation Errors

**Symptoms**: Optimization fails with "Invalid parameter range"

**Cause**: From/To/Step values not validated.

**Solution**:
```javascript
function collectOptimizerParams() {
  const ranges = {};

  checkboxes.forEach(checkbox => {
    if (checkbox.checked) {
      const from = parseFloat(fromInput.value);
      const to = parseFloat(toInput.value);
      const step = parseFloat(stepInput.value);

      // VALIDATE
      if (isNaN(from) || isNaN(to) || isNaN(step)) {
        console.warn(`Invalid values for ${paramName}`);
        return; // Skip this parameter
      }

      if (from >= to) {
        console.warn(`From >= To for ${paramName}`);
        return;
      }

      if (step <= 0 || step > (to - from)) {
        console.warn(`Invalid step for ${paramName}`);
        return;
      }

      ranges[paramName] = [from, to, step];
    }
  });

  return ranges;
}
```

### Pitfall 7: Strategy Switch Doesn't Update Optimizer

**Symptoms**: Switching strategies doesn't update optimizer form.

**Cause**: `generateOptimizerForm()` not called on strategy change.

**Solution**:
```javascript
// In strategy dropdown change handler
strategySelect.addEventListener('change', async function() {
  const strategyId = this.value;
  await loadStrategyConfig(strategyId); // ← This should call generateOptimizerForm()
});

// Ensure loadStrategyConfig() includes:
async function loadStrategyConfig(strategyId) {
  const config = await fetchConfig(strategyId);
  currentStrategyConfig = config;
  currentStrategyId = strategyId;

  updateStrategyInfo(config);
  generateBacktestForm(config);
  generateOptimizerForm(config); // ← MUST be called here
}
```

### Pitfall 8: CSS Classes Missing

**Symptoms**: Optimizer form looks unstyled or broken.

**Cause**: CSS extraction missed some styles, or class names changed.

**Solution**: Verify all CSS classes used in dynamic generation exist in `style.css`:

```css
/* Required classes for optimizer */
.opt-section { /* ... */ }
.opt-section-title { /* ... */ }
.opt-row { /* ... */ }
.opt-label { /* ... */ }
.opt-controls { /* ... */ }
.tiny-input { /* ... */ }
.opt-row.disabled { /* ... */ }
```

**Debug**: Inspect element in browser DevTools, check computed styles.

### Pitfall 9: Backend API Changes

**Symptoms**: Optimization request fails with 400/500 errors.

**Cause**: Backend expects different payload format.

**Solution**: Check backend endpoint signature:

```python
# Backend: /api/optimize
@app.route('/api/optimize', methods=['POST'])
def optimize():
    payload = request.get_json()
    strategy_id = payload.get('strategy')
    param_ranges = payload.get('param_ranges')  # ← Format must match
    # ...
```

**Frontend must send**:
```javascript
const payload = {
  strategy: 's04_stochrsi',
  param_ranges: {
    'rsiLen': [10, 20, 2],
    'stochLen': [10, 20, 2]
  },
  // ... other fields
};
```

### Pitfall 10: Performance Issues

**Symptoms**: Form generation is slow with many parameters.

**Cause**: Creating many DOM elements can be slow.

**Solution**: Use document fragments:

```javascript
function generateOptimizerForm(config) {
  const container = document.getElementById('optimizerParamsContainer');
  container.innerHTML = '';

  const fragment = document.createDocumentFragment();

  for (const [groupName, groupParams] of Object.entries(groups)) {
    const groupDiv = document.createElement('div');
    // ... build group ...
    fragment.appendChild(groupDiv);
  }

  container.appendChild(fragment); // Single DOM update

  bindOptimizerInputs();
}
```

---

## Success Criteria

Phase 8 is successful when ALL of these criteria are met:

### 1. CSS Extraction Success

```bash
# File exists and has content
ls -lh src/static/css/style.css
# Should show file size > 10KB

# No <style> blocks in HTML
grep -c "<style>" src/index.html
# Should return 0

# Page looks identical
# Visual inspection: open browser, compare before/after screenshots
```

### 2. S01 Optimizer Works

**Test**:
```javascript
// Browser console
// 1. Select S01
// 2. Check console output:
console.log(document.querySelectorAll('.opt-row').length);
// Should show 15-19 (number of optimizable S01 parameters)
```

**Expected parameters**: maLength, closeCountLong, closeCountShort, stops, trails, etc.

**Run optimization**:
- Enable 3 parameters
- Set ranges: maLength [40-60, step 10], closeCountLong [5-8, step 1], stopLongX [1.5-2.5, step 0.5]
- Run 10 trials
- Should complete and download CSV

### 3. S04 Optimizer Works

**Test**:
```javascript
// Browser console
// 1. Select S04
// 2. Check console output:
console.log(document.querySelectorAll('.opt-row').length);
// Should show 6 (S04 optimizable parameters)
```

**Expected parameters**: rsiLen, stochLen, obLevel, osLevel, extLookback, confirmBars

**Run optimization**:
- Enable 3 parameters
- Set ranges
- Run 10 trials
- Should complete and download CSV

### 4. Strategy Switching Works

**Test**:
```javascript
// 1. Select S01 → optimizer shows S01 params
// 2. Select S04 → optimizer shows S04 params
// 3. Select S01 → optimizer shows S01 params again

// No errors in console
// Parameters update immediately
```

### 5. No JavaScript Errors

**Test**:
```bash
# Open browser DevTools console (F12)
# Perform all actions:
# - Load page
# - Select strategies
# - Check/uncheck parameters
# - Modify ranges
# - Run optimization

# Console should show:
# ✅ "Loaded strategy: S01..."
# ✅ "Generated optimizer form with X parameters"
# ✅ "Bound event listeners to X checkboxes"
# ❌ NO red errors
```

### 6. Full Optimization Workflow

**S01 Test**:
```bash
pytest tests/test_s01_migration.py -v
# Should still pass (no regressions)

# Manual test:
# 1. Select S01
# 2. Load test CSV
# 3. Enable maLength, closeCountLong
# 4. Run 10 trials
# 5. Verify CSV downloads
# 6. Open CSV, verify columns and data
```

**S04 Test**:
```bash
pytest tests/test_s04.py -v
# Should still pass (no regressions)

# Manual test:
# 1. Select S04
# 2. Load test CSV
# 3. Enable rsiLen, stochLen, obLevel
# 4. Run 10 trials
# 5. Verify CSV downloads
# 6. Open CSV, verify columns and data
```

### 7. UI Quality Checks

- [ ] CSS extracted, page looks identical
- [ ] Optimizer form generates correctly for all strategies
- [ ] Checkboxes enable/disable inputs correctly
- [ ] Parameter groups displayed clearly
- [ ] Form layout matches original design
- [ ] No visual regressions
- [ ] Mobile/responsive layout works (if applicable)

### 8. Code Quality

- [ ] Code is clean and well-documented
- [ ] Functions have clear names and docstrings
- [ ] No magic numbers or hardcoded values
- [ ] Consistent coding style
- [ ] No console.log spam (only useful logs)
- [ ] Error handling for edge cases

---

## Next Steps After Phase 8

After Phase 8 is complete and validated:

**Phase 9** (Next): Legacy Code Cleanup
- Delete legacy S01 implementation (`s01_trailing_ma/`)
- Promote migrated version to production (`s01_trailing_ma_migrated/` → `s01_trailing_ma/`)
- Delete `run_strategy()` from `backtest_engine.py`
- Clean up S01 hardcoding in backend (`server.py`)
- Remove default strategy ID hardcoding
- Clean up preset system hardcoding

**Phase 10**: Full Frontend Separation
- Modularize JavaScript into separate files
- Move HTML to `templates/`
- Move server.py to `ui/`
- Clean up imports

**Phase 11**: Documentation
- Update all documentation
- Create strategy development guide
- Create migration summary

---

## Project Files Reference

### Files You'll Modify

- **src/index.html** - Remove hardcoded HTML, add dynamic container
- **src/static/css/style.css** - NEW - All extracted CSS
- **src/server.py** - Verify static serving configuration (minor changes)

### Files You'll Read

- **src/strategies/s01_trailing_ma/config.json** - S01 parameter definitions
- **src/strategies/s04_stochrsi/config.json** - S04 parameter definitions
- **docs/PROJECT_MIGRATION_PLAN_upd.md** - Phase 8 requirements

### Test Files

No new test files needed. Manual testing is sufficient for UI changes.

---

## Implementation Checklist

### Preparation

- [ ] Read this entire prompt
- [ ] Understand current UI structure (index.html ~4746 lines)
- [ ] Review S01 and S04 config.json files
- [ ] Backup current index.html (just in case)

### Step 1: CSS Extraction (2-3 hours)

- [ ] Create `src/static/css/` directory
- [ ] Create `style.css` file
- [ ] Find all `<style>` blocks in index.html
- [ ] Copy styles to style.css (preserve exactly)
- [ ] Remove `<style>` blocks from index.html
- [ ] Add `<link>` tag in HTML `<head>`
- [ ] Verify Flask static serving
- [ ] Test: Page loads and looks identical
- [ ] Test: No CSS errors in console

### Step 2: Remove Hardcoded HTML (30 min)

- [ ] Locate optimizer HTML section (lines ~1455-1829)
- [ ] Delete entire hardcoded section
- [ ] Add `<div id="optimizerParamsContainer">`
- [ ] Locate `OPTIMIZATION_PARAMETERS` array (lines ~2668-2840)
- [ ] Delete entire array
- [ ] Test: Page still loads (optimizer empty for now)

### Step 3: Implement Dynamic Generation (4-6 hours)

- [ ] Implement `generateOptimizerForm(config)` function
- [ ] Implement `createOptimizerRow(paramName, paramDef)` helper
- [ ] Update `loadStrategyConfig()` to call generator
- [ ] Test: S01 optimizer shows parameters
- [ ] Test: S04 optimizer shows parameters

### Step 4: Update Event Binding (1-2 hours)

- [ ] Update `bindOptimizerInputs()` for dynamic IDs
- [ ] Implement `handleOptimizerCheckboxChange()` function
- [ ] Update `collectOptimizerParams()` for dynamic collection
- [ ] Test: Checkboxes enable/disable inputs
- [ ] Test: Parameter collection works

### Step 5: Testing (2-3 hours)

- [ ] Test CSS extraction (page identical)
- [ ] Test S01 optimizer (shows S01 params)
- [ ] Test S04 optimizer (shows S04 params)
- [ ] Test strategy switching (updates correctly)
- [ ] Test optimization workflow (S01)
- [ ] Test optimization workflow (S04)
- [ ] Test edge cases
- [ ] Verify no JavaScript errors

### Step 6: Final Validation

- [ ] All tests pass
- [ ] S01 and S04 both work correctly
- [ ] No regressions in other features
- [ ] Code is clean and documented
- [ ] Commit changes
- [ ] Tag: `phase-8-complete`
- [ ] Push to remote

---

## Debugging Guide

### If CSS Doesn't Load

**Step 1**: Check file exists
```bash
ls -la src/static/css/style.css
```

**Step 2**: Check Flask config
```python
# In Python console
from src.server import app
print(app.static_folder)  # Should show 'static'
print(app.static_url_path)  # Should show '/static'
```

**Step 3**: Test direct access
```
Open browser: http://localhost:8000/static/css/style.css
Should show CSS content, not 404
```

**Step 4**: Check HTML link
```html
<!-- Should be EXACTLY -->
<link rel="stylesheet" href="/static/css/style.css">
<!-- NOT -->
<link rel="stylesheet" href="static/css/style.css">  <!-- Missing leading / -->
<link rel="stylesheet" href="/css/style.css">  <!-- Missing /static -->
```

### If Optimizer Form Is Empty

**Step 1**: Check config loaded
```javascript
// Browser console
console.log(currentStrategyConfig);
// Should show full config object with parameters
```

**Step 2**: Check optimizable parameters
```javascript
const opts = Object.entries(currentStrategyConfig.parameters)
  .filter(([n, d]) => d.optimize && d.optimize.enabled);
console.log('Optimizable params:', opts);
// Should show list of parameters
```

**Step 3**: Check container exists
```javascript
const container = document.getElementById('optimizerParamsContainer');
console.log('Container:', container);
// Should show HTMLDivElement, not null
```

**Step 4**: Check generation was called
```javascript
// Add debug log in generateOptimizerForm()
function generateOptimizerForm(config) {
  console.log('generateOptimizerForm called with:', config);
  // ... rest of function
}
```

### If Parameters Wrong

**Step 1**: Check strategy ID
```javascript
console.log('Current strategy:', currentStrategyId);
// Should match selected dropdown value
```

**Step 2**: Check config.json
```bash
# For S04
cat src/strategies/s04_stochrsi/config.json | grep -A5 "optimize"
# Should show optimize blocks with enabled: true
```

**Step 3**: Reload config
```javascript
// Force reload
await loadStrategyConfig('s04_stochrsi');
console.log('Reloaded config');
```

### If Optimization Fails

**Step 1**: Check payload
```javascript
// In runOptimization()
const payload = buildPayload();
console.log('Sending payload:', JSON.stringify(payload, null, 2));
```

**Step 2**: Check backend logs
```bash
# Terminal running server should show request
# Look for errors or validation failures
```

**Step 3**: Test with minimal payload
```javascript
// Simplify payload to minimum
const payload = {
  strategy: 's04_stochrsi',
  param_ranges: {
    'rsiLen': [12, 16, 2]
  },
  n_trials: 5
};
```

---

## Conclusion

Phase 8 fixes a critical production blocker by making the optimizer UI fully dynamic. This phase is essential for:

1. **Multi-strategy support**: UI now works with ANY strategy
2. **Phase 9 preparation**: Enables safe cleanup of legacy code
3. **Architecture completion**: Moves toward clean, modular UI
4. **User experience**: No more confusion with wrong parameters

The implementation is straightforward but requires careful testing to ensure no regressions.

**Key Success Factors**:
- ✅ CSS extraction without visual changes
- ✅ Dynamic form generation from config.json
- ✅ Works for S01, S04, and future strategies
- ✅ Comprehensive testing
- ✅ No JavaScript errors

After Phase 8, the UI will be fully functional for all strategies, paving the way for Phase 9 legacy cleanup.

**Good luck! This phase fixes a critical issue and improves the architecture significantly.**

---

**Project Repository**: Current working directory
**Key Files**: `src/index.html`, `src/static/css/style.css`, `src/server.py`

**Key Commands**:
```bash
# Start server
cd src
python server.py

# Check CSS extraction
ls -la src/static/css/style.css

# Test in browser
# Open http://localhost:8000
# Select strategies, test optimizer

# Verify no errors
# Browser DevTools → Console (F12)
```

**Report Issues**: If you encounter problems not covered in this prompt, document them clearly with:
1. What you tried
2. What you expected
3. What actually happened
4. Browser console errors (if any)
5. Network tab responses (if relevant)

---

**End of Phase 8 Prompt**

**Version**: 1.0
**Date**: 2025-12-04
**Author**: Migration Team
**Status**: Ready for Execution
