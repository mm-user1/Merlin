# Phase 10: Full Frontend Separation

## Agent Instructions for GPT 5.1 Codex

**Date:** 2025-12-11
**Phase:** 10 - Full Frontend Separation
**Complexity:** MEDIUM
**Risk:** LOW
**Estimated Effort:** 6-8 hours

---

## Executive Summary

This phase completes the frontend separation by moving all HTML, CSS, and JavaScript into a proper modular structure. The goal is to transform a monolithic 3166-line `index.html` file into a clean, maintainable architecture with separated concerns.

**CRITICAL:** This is a refactoring task. The UI must look and behave EXACTLY the same after completion. No functional changes, no new features - only structural reorganization.

---

## Current State Analysis

### File Locations (BEFORE)

```
src/
├── server.py                    # Flask app (1811 lines)
├── index.html                   # Monolithic file (3166 lines)
│                                # - HTML: lines 1-525
│                                # - JavaScript: lines 526-3164 (~2638 lines)
└── static/
    └── css/
        └── style.css            # Already extracted (778 lines)
```

### Target Structure (AFTER)

```
src/
├── core/                        # Unchanged
├── indicators/                  # Unchanged
├── strategies/                  # Unchanged
├── Presets/                     # Unchanged
├── run_backtest.py              # Unchanged
└── ui/
    ├── __init__.py              # NEW
    ├── server.py                # MOVED from src/server.py
    ├── templates/
    │   └── index.html           # Clean HTML only (~550 lines)
    └── static/
        ├── css/
        │   └── style.css        # MOVED from src/static/css/
        └── js/
            ├── main.js          # App initialization (~150 lines)
            ├── api.js           # API communication (~200 lines)
            ├── strategy-config.js  # Form generation (~350 lines)
            ├── ui-handlers.js   # Event handlers (~400 lines)
            ├── presets.js       # Preset management (~450 lines)
            └── utils.js         # Utility functions (~200 lines)
```

---

## Implementation Steps

### Step 1: Create Directory Structure

**Files to create:**
```bash
mkdir -p src/ui/templates
mkdir -p src/ui/static/css
mkdir -p src/ui/static/js
touch src/ui/__init__.py
```

**`src/ui/__init__.py` content:**
```python
"""UI module for Flask web application."""
```

---

### Step 2: Move Static CSS

**Action:** Move `src/static/css/style.css` to `src/ui/static/css/style.css`

```bash
mv src/static/css/style.css src/ui/static/css/style.css
rmdir src/static/css
rmdir src/static
```

**Verification:** File content should be unchanged (778 lines).

---

### Step 3: Move and Update server.py

**Action:** Move `src/server.py` to `src/ui/server.py`

**Required modifications:**

1. **Update Flask app initialization (line 18):**

```python
# BEFORE:
app = Flask(__name__, static_folder="static", static_url_path="/static")

# AFTER:
import sys
from pathlib import Path

# Add parent directory to path for core imports
sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
    static_url_path="/static"
)
```

2. **Update index route to use template:**

```python
# BEFORE (find the route that serves index.html):
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# AFTER:
from flask import render_template

@app.route("/")
def index():
    return render_template("index.html")
```

3. **Update PRESETS_DIR path (around line 93):**

```python
# BEFORE:
PRESETS_DIR = Path(__file__).resolve().parent / "Presets"

# AFTER:
PRESETS_DIR = Path(__file__).resolve().parent.parent / "Presets"
```

4. **Remove old static route if it exists:**
The `@app.route("/static/<path:path>")` route should be removed since Flask will handle static files automatically with the new configuration.

---

### Step 4: Extract JavaScript into Modules

This is the most complex step. Extract all JavaScript from `src/index.html` (lines 526-3164) into separate module files.

#### 4.1: Create `src/ui/static/js/utils.js`

**Content:** Utility functions that don't depend on other modules.

```javascript
/**
 * Utility functions for the Strategy Backtester & Optimizer UI.
 * No dependencies on other modules.
 */

/**
 * Deep clone an object using JSON serialization.
 * @param {Object} data - Object to clone
 * @returns {Object} Cloned object
 */
function clonePreset(data) {
  try {
    return JSON.parse(JSON.stringify(data || {}));
  } catch (error) {
    return {};
  }
}

/**
 * Parse a value to number with fallback.
 * @param {*} value - Value to parse
 * @param {number} fallback - Fallback value
 * @returns {number}
 */
function parseNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/**
 * Format a metric value for display.
 * @param {*} value - Value to format
 * @param {number} digits - Decimal places
 * @returns {string}
 */
function formatMetric(value, digits = 2) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toFixed(digits);
  }
  if (value === undefined || value === null) {
    return 'N/A';
  }
  return value;
}

/**
 * Format a backtest result block for display.
 * @param {number} index - Result index
 * @param {number} total - Total results
 * @param {Object} payload - Request payload
 * @param {Object} data - Response data
 * @returns {string}
 */
function formatResultBlock(index, total, payload, data) {
  const metrics = data.metrics || {};
  return [
    `#${index}/${total}`,
    `Net Profit %: ${formatMetric(metrics.net_profit_pct)}`,
    `Max Drawdown %: ${formatMetric(metrics.max_drawdown_pct)}`,
    `Total Trades: ${metrics.total_trades ?? 'N/A'}`
  ].join('\n');
}

/**
 * Compose datetime string from date and time parts.
 * @param {string} datePart - Date string
 * @param {string} timePart - Time string
 * @returns {string}
 */
function composeDateTime(datePart, timePart) {
  const date = (datePart || '').trim();
  const time = (timePart || '').trim();
  if (!date) {
    return '';
  }
  const normalizedTime = time || '00:00';
  return `${date}T${normalizedTime}`;
}

/**
 * Set checkbox value by element ID.
 * @param {string} id - Element ID
 * @param {boolean} checked - Checked state
 */
function setCheckboxValue(id, checked) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }
  element.checked = Boolean(checked);
}

/**
 * Set input value by element ID.
 * @param {string} id - Element ID
 * @param {*} value - Value to set
 */
function setInputValue(id, value) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }
  if (value === undefined || value === null) {
    element.value = '';
  } else {
    element.value = value;
  }
}

/**
 * Show error message in error element.
 * @param {string} message - Error message
 */
function showErrorMessage(message) {
  const errorEl = document.getElementById('error');
  if (!errorEl) {
    return;
  }
  errorEl.textContent = message;
  errorEl.style.display = message ? 'block' : 'none';
}

/**
 * Clear error message.
 */
function clearErrorMessage() {
  showErrorMessage('');
}

/**
 * Show results message.
 * @param {string} message - Message to show
 */
function showResultsMessage(message) {
  const resultsEl = document.getElementById('results');
  if (!resultsEl) {
    return;
  }
  resultsEl.textContent = message;
  resultsEl.classList.remove('loading');
  if (message) {
    resultsEl.classList.add('ready');
  } else {
    resultsEl.classList.remove('ready');
  }
}

/**
 * Render selected files list.
 * @param {Array} files - Array of File objects
 */
function renderSelectedFiles(files) {
  const selectedFilesWrapper = document.getElementById('selectedFilesWrapper');
  const selectedFilesList = document.getElementById('selectedFilesList');

  if (!selectedFilesWrapper || !selectedFilesList) {
    return;
  }

  const entries = [];
  if (files && files.length) {
    files.forEach((file) => {
      entries.push(file.name);
    });
  } else if (window.selectedCsvPath) {
    entries.push(window.selectedCsvPath);
  }

  selectedFilesList.innerHTML = '';
  if (!entries.length) {
    selectedFilesWrapper.style.display = 'none';
    return;
  }

  const fragment = document.createDocumentFragment();
  entries.forEach((label) => {
    const item = document.createElement('li');
    item.textContent = label;
    fragment.appendChild(item);
  });

  selectedFilesList.appendChild(fragment);
  selectedFilesWrapper.style.display = 'block';
}
```

---

#### 4.2: Create `src/ui/static/js/api.js`

**Content:** All API communication functions.

```javascript
/**
 * API communication functions for Strategy Backtester & Optimizer.
 * Dependencies: utils.js
 */

/**
 * Fetch list of available strategies.
 * @returns {Promise<Object>} Response with strategies array
 */
async function fetchStrategies() {
  const response = await fetch('/api/strategies');
  if (!response.ok) {
    throw new Error(`Failed to fetch strategies: ${response.status}`);
  }
  return response.json();
}

/**
 * Fetch strategy configuration.
 * @param {string} strategyId - Strategy identifier
 * @returns {Promise<Object>} Strategy configuration
 */
async function fetchStrategyConfig(strategyId) {
  const response = await fetch(`/api/strategy/${strategyId}/config`);
  if (!response.ok) {
    throw new Error(`Server returned ${response.status}: ${response.statusText}`);
  }
  const config = await response.json();

  if (!config || typeof config !== 'object') {
    throw new Error('Invalid config format');
  }

  if (!config.parameters || typeof config.parameters !== 'object') {
    throw new Error('Missing parameters in config');
  }

  return config;
}

/**
 * Run a single backtest.
 * @param {FormData} formData - Form data with backtest parameters
 * @returns {Promise<Object>} Backtest results
 */
async function runBacktestRequest(formData) {
  const response = await fetch('/api/backtest', {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Backtest request failed');
  }

  return response.json();
}

/**
 * Run optimization.
 * @param {FormData} formData - Form data with optimization config
 * @returns {Promise<Blob>} CSV blob with results
 */
async function runOptimizationRequest(formData) {
  const response = await fetch('/api/optimize', {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Optimization request failed');
  }

  return {
    blob: await response.blob(),
    headers: response.headers
  };
}

/**
 * Run walk-forward analysis.
 * @param {FormData} formData - Form data with WFA config
 * @returns {Promise<Object>} WFA results
 */
async function runWalkForwardRequest(formData) {
  const response = await fetch('/api/walkforward', {
    method: 'POST',
    body: formData
  });

  const data = await response.json();

  if (!response.ok || data.status !== 'success') {
    const message = data && data.error ? data.error : 'Walk-Forward request failed.';
    throw new Error(message);
  }

  return data;
}

/**
 * Fetch presets list.
 * @returns {Promise<Object>} Response with presets array
 */
async function fetchPresetsList() {
  const response = await fetch('/api/presets');
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to fetch presets');
  }
  return response.json();
}

/**
 * Load a preset by name.
 * @param {string} name - Preset name
 * @returns {Promise<Object>} Preset data
 */
async function loadPresetRequest(name) {
  const response = await fetch(`/api/presets/${encodeURIComponent(name)}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to load preset');
  }
  return response.json();
}

/**
 * Save a new preset.
 * @param {string} name - Preset name
 * @param {Object} values - Preset values
 * @returns {Promise<Object>} Response
 */
async function savePresetRequest(name, values) {
  const response = await fetch('/api/presets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, values })
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to save preset');
  }
  return response.json();
}

/**
 * Overwrite existing preset.
 * @param {string} name - Preset name
 * @param {Object} values - New values
 * @returns {Promise<Object>} Response
 */
async function overwritePresetRequest(name, values) {
  const response = await fetch(`/api/presets/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values })
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to overwrite preset');
  }
  return response.json();
}

/**
 * Save defaults preset.
 * @param {Object} values - Default values
 * @returns {Promise<Object>} Response
 */
async function saveDefaultsRequest(values) {
  const response = await fetch('/api/presets/defaults', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values })
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to save defaults');
  }
  return response.json();
}

/**
 * Delete a preset.
 * @param {string} name - Preset name
 * @returns {Promise<void>}
 */
async function deletePresetRequest(name) {
  const response = await fetch(`/api/presets/${encodeURIComponent(name)}`, {
    method: 'DELETE'
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to delete preset');
  }
}

/**
 * Import preset from CSV file.
 * @param {File} file - CSV file
 * @returns {Promise<Object>} Imported preset data
 */
async function importPresetFromCsvRequest(file) {
  const formData = new FormData();
  formData.append('file', file, file.name);

  const response = await fetch('/api/presets/import-csv', {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to import settings from CSV');
  }

  return response.json();
}
```

---

#### 4.3: Create `src/ui/static/js/strategy-config.js`

**Content:** Strategy loading and form generation functions.

```javascript
/**
 * Strategy configuration and form generation.
 * Dependencies: utils.js, api.js
 */

// Global state for current strategy
window.currentStrategyId = null;
window.currentStrategyConfig = null;

/**
 * Load list of available strategies on page load.
 */
async function loadStrategiesList() {
  try {
    const data = await fetchStrategies();

    const select = document.getElementById('strategySelect');
    if (!select) {
      return;
    }

    select.innerHTML = '';

    if (!data.strategies || data.strategies.length === 0) {
      select.innerHTML = '<option value="">No strategies found</option>';
      console.error('No strategies discovered');
      return;
    }

    data.strategies.forEach((strategy) => {
      const option = document.createElement('option');
      option.value = strategy.id;
      option.textContent = `${strategy.name} ${strategy.version}`;
      select.appendChild(option);
    });

    if (data.strategies.length > 0) {
      window.currentStrategyId = data.strategies[0].id;
      select.value = window.currentStrategyId;
      await loadStrategyConfig(window.currentStrategyId);
    }
  } catch (error) {
    console.error('Failed to load strategies:', error);
    alert('Error loading strategies. Check console for details.');
  }
}

/**
 * Handle strategy selection change.
 */
async function handleStrategyChange() {
  const select = document.getElementById('strategySelect');
  window.currentStrategyId = select?.value || null;

  if (!window.currentStrategyId) {
    return;
  }

  await loadStrategyConfig(window.currentStrategyId);
}

/**
 * Load strategy configuration and generate forms.
 * @param {string} strategyId - Strategy identifier
 */
async function loadStrategyConfig(strategyId) {
  try {
    const config = await fetchStrategyConfig(strategyId);
    window.currentStrategyConfig = config;

    try {
      updateStrategyInfo(config);
    } catch (err) {
      console.warn('Failed to update strategy info:', err);
    }

    try {
      generateBacktestForm(config);
    } catch (err) {
      console.error('Failed to generate backtest form:', err);
      alert('Error generating backtest form. Please refresh the page.');
      return;
    }

    try {
      generateOptimizerForm(config);
    } catch (err) {
      console.error('Failed to generate optimizer form:', err);
      alert('Error generating optimizer form. Please refresh the page.');
      return;
    }

    console.log(`✓ Loaded strategy: ${config.name}`);
  } catch (error) {
    console.error('Failed to load strategy config:', error);
    if (!window.currentStrategyConfig || !window.currentStrategyConfig.parameters) {
      alert(`Error loading strategy configuration: ${error.message}\n\nPlease check browser console for details.`);
    } else {
      console.warn('Non-critical error during strategy load, but forms populated successfully');
    }
  }
}

/**
 * Update strategy info panel.
 * @param {Object} config - Strategy configuration
 */
function updateStrategyInfo(config) {
  const info = document.getElementById('strategyInfo');
  if (!info) {
    return;
  }

  document.getElementById('strategyName').textContent = config.name || '';
  document.getElementById('strategyVersion').textContent = config.version || '';
  document.getElementById('strategyDescription').textContent = config.description || 'N/A';
  document.getElementById('strategyParamCount').textContent = Object.keys(config.parameters || {}).length;
  info.style.display = 'block';
}

/**
 * Generate backtest parameters form from config.
 * @param {Object} config - Strategy configuration
 */
function generateBacktestForm(config) {
  const container = document.getElementById('backtestParamsContent');
  if (!container) {
    return;
  }

  container.innerHTML = '';

  const params = config.parameters || {};
  const groups = {};

  for (const [paramName, paramDef] of Object.entries(params)) {
    const group = paramDef.group || 'Other';
    if (!groups[group]) {
      groups[group] = [];
    }
    groups[group].push({ name: paramName, def: paramDef });
  }

  for (const [groupName, groupParams] of Object.entries(groups)) {
    const groupDiv = document.createElement('div');
    groupDiv.className = 'param-group';
    groupDiv.style.marginBottom = '25px';
    groupDiv.style.flexDirection = 'column';
    groupDiv.style.alignItems = 'flex-start';

    const groupTitle = document.createElement('h4');
    groupTitle.textContent = groupName;
    groupTitle.style.color = '#4a90e2';
    groupTitle.style.marginBottom = '15px';
    groupDiv.appendChild(groupTitle);

    groupParams.forEach(({ name, def }) => {
      const formGroup = createFormField(name, def, 'backtest');
      groupDiv.appendChild(formGroup);
    });

    container.appendChild(groupDiv);
  }
}

/**
 * Generate optimizer parameters form from strategy config.
 * Only shows parameters where optimize.enabled === true.
 * @param {Object} config - Strategy configuration
 */
function generateOptimizerForm(config) {
  const container = document.getElementById('optimizerParamsContainer');
  if (!container) {
    console.error('Optimizer container not found (#optimizerParamsContainer)');
    return;
  }

  container.innerHTML = '';

  const params = config.parameters || {};
  const groups = {};

  for (const [paramName, paramDef] of Object.entries(params)) {
    if (paramDef.optimize && paramDef.optimize.enabled) {
      const group = paramDef.group || 'Other';
      if (!groups[group]) {
        groups[group] = [];
      }
      groups[group].push({ name: paramName, def: paramDef });
    }
  }

  const totalParams = Object.values(groups).reduce((sum, g) => sum + g.length, 0);
  if (totalParams === 0) {
    container.innerHTML = '<p class="warning">No optimizable parameters defined for this strategy.</p>';
    bindOptimizerInputs();
    return;
  }

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

  bindOptimizerInputs();
  console.log(`Generated optimizer form with ${totalParams} parameters`);
}

/**
 * Create a single optimizer parameter row.
 * @param {string} paramName - Parameter name
 * @param {Object} paramDef - Parameter definition
 * @returns {HTMLElement}
 */
function createOptimizerRow(paramName, paramDef) {
  const row = document.createElement('div');
  row.className = 'opt-row';

  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.id = `opt-${paramName}`;
  checkbox.checked = Boolean(paramDef.optimize && paramDef.optimize.enabled);
  checkbox.dataset.paramName = paramName;
  checkbox.classList.add('opt-param-toggle');

  const label = document.createElement('label');
  label.className = 'opt-label';
  label.htmlFor = `opt-${paramName}`;
  label.textContent = paramDef.label || paramName;

  const controlsDiv = document.createElement('div');
  controlsDiv.className = 'opt-controls';

  const paramType = paramDef.type || 'float';

  if (paramType === 'select' || paramType === 'options') {
    const optionsContainer = createSelectOptions(paramName, paramDef);
    controlsDiv.appendChild(optionsContainer);
  } else {
    const isInt = paramType === 'int' || paramType === 'integer';
    const defaultStep = isInt ? 1 : 0.1;
    const minStep = isInt ? 1 : 0.01;

    const fromLabel = document.createElement('label');
    fromLabel.textContent = 'From:';
    const fromInput = document.createElement('input');
    fromInput.className = 'tiny-input';
    fromInput.id = `opt-${paramName}-from`;
    fromInput.type = 'number';
    fromInput.value = paramDef.optimize?.min ?? paramDef.min ?? 0;
    fromInput.step = paramDef.optimize?.step || paramDef.step || defaultStep;
    fromInput.dataset.paramName = paramName;

    const toLabel = document.createElement('label');
    toLabel.textContent = 'To:';
    const toInput = document.createElement('input');
    toInput.className = 'tiny-input';
    toInput.id = `opt-${paramName}-to`;
    toInput.type = 'number';
    toInput.value = paramDef.optimize?.max ?? paramDef.max ?? 100;
    toInput.step = paramDef.optimize?.step || paramDef.step || defaultStep;
    toInput.dataset.paramName = paramName;

    const stepLabel = document.createElement('label');
    stepLabel.textContent = 'Step:';
    const stepInput = document.createElement('input');
    stepInput.className = 'tiny-input';
    stepInput.id = `opt-${paramName}-step`;
    stepInput.type = 'number';
    stepInput.value = paramDef.optimize?.step || paramDef.step || defaultStep;
    stepInput.step = minStep;
    stepInput.min = minStep;
    stepInput.dataset.paramName = paramName;

    controlsDiv.appendChild(fromLabel);
    controlsDiv.appendChild(fromInput);
    controlsDiv.appendChild(toLabel);
    controlsDiv.appendChild(toInput);
    controlsDiv.appendChild(stepLabel);
    controlsDiv.appendChild(stepInput);
  }

  row.appendChild(checkbox);
  row.appendChild(label);
  row.appendChild(controlsDiv);

  return row;
}

/**
 * Create multi-select checkbox UI for select/dropdown parameters.
 * @param {string} paramName - Parameter name
 * @param {Object} paramDef - Parameter definition
 * @returns {HTMLElement}
 */
function createSelectOptions(paramName, paramDef) {
  const container = document.createElement('div');
  container.className = 'select-options-container';
  container.dataset.paramName = paramName;

  const options = paramDef.options || [];

  if (options.length === 0) {
    const warning = document.createElement('span');
    warning.className = 'warning-text';
    warning.textContent = 'No options defined for this parameter';
    container.appendChild(warning);
    return container;
  }

  // "All" checkbox
  const allCheckboxWrapper = document.createElement('label');
  allCheckboxWrapper.className = 'select-option-label all-option';
  allCheckboxWrapper.style.fontWeight = 'bold';

  const allCheckbox = document.createElement('input');
  allCheckbox.type = 'checkbox';
  allCheckbox.className = 'select-option-checkbox';
  allCheckbox.dataset.paramName = paramName;
  allCheckbox.dataset.optionValue = '__ALL__';
  allCheckbox.id = `opt-${paramName}-all`;

  const allLabel = document.createElement('span');
  allLabel.textContent = 'All';

  allCheckboxWrapper.appendChild(allCheckbox);
  allCheckboxWrapper.appendChild(allLabel);
  container.appendChild(allCheckboxWrapper);

  // Individual option checkboxes
  options.forEach((optionValue) => {
    const optionWrapper = document.createElement('label');
    optionWrapper.className = 'select-option-label';

    const optionCheckbox = document.createElement('input');
    optionCheckbox.type = 'checkbox';
    optionCheckbox.className = 'select-option-checkbox';
    optionCheckbox.dataset.paramName = paramName;
    optionCheckbox.dataset.optionValue = optionValue;
    optionCheckbox.id = `opt-${paramName}-${optionValue}`;

    if (optionValue === paramDef.default) {
      optionCheckbox.checked = true;
    }

    const optionLabel = document.createElement('span');
    optionLabel.textContent = optionValue;

    optionWrapper.appendChild(optionCheckbox);
    optionWrapper.appendChild(optionLabel);
    container.appendChild(optionWrapper);
  });

  // "All" checkbox behavior
  allCheckbox.addEventListener('change', () => {
    const individualCheckboxes = container.querySelectorAll(
      `input.select-option-checkbox[data-param-name="${paramName}"]:not([data-option-value="__ALL__"])`
    );
    individualCheckboxes.forEach((cb) => {
      cb.checked = allCheckbox.checked;
    });
  });

  // Sync "All" checkbox state
  const individualCheckboxes = container.querySelectorAll(
    `input.select-option-checkbox[data-param-name="${paramName}"]:not([data-option-value="__ALL__"])`
  );
  individualCheckboxes.forEach((cb) => {
    cb.addEventListener('change', () => {
      const allChecked = Array.from(individualCheckboxes).every((checkbox) => checkbox.checked);
      allCheckbox.checked = allChecked;
    });
  });

  return container;
}

/**
 * Create a form field based on parameter definition.
 * @param {string} paramName - Parameter name
 * @param {Object} paramDef - Parameter definition
 * @param {string} prefix - ID prefix
 * @returns {HTMLElement}
 */
function createFormField(paramName, paramDef, prefix) {
  const formGroup = document.createElement('div');
  formGroup.className = 'form-group';
  formGroup.style.marginBottom = '15px';

  const label = document.createElement('label');
  label.textContent = paramDef.label || paramName;
  label.style.display = 'inline-block';
  label.style.width = '200px';
  formGroup.appendChild(label);

  let input;

  if (paramDef.type === 'select') {
    input = document.createElement('select');
    input.id = `${prefix}_${paramName}`;
    input.name = paramName;
    input.style.padding = '5px';
    input.style.minWidth = '150px';

    (paramDef.options || []).forEach((option) => {
      const opt = document.createElement('option');
      opt.value = option;
      opt.textContent = option;
      if (option === paramDef.default) {
        opt.selected = true;
      }
      input.appendChild(opt);
    });
  } else if (paramDef.type === 'int' || paramDef.type === 'float') {
    input = document.createElement('input');
    input.type = 'number';
    input.id = `${prefix}_${paramName}`;
    input.name = paramName;
    input.value = paramDef.default ?? 0;
    input.min = paramDef.min !== undefined ? paramDef.min : '';
    input.max = paramDef.max !== undefined ? paramDef.max : '';
    input.step = paramDef.step || (paramDef.type === 'int' ? 1 : 0.1);
    input.style.padding = '5px';
    input.style.width = '120px';
  } else if (paramDef.type === 'bool') {
    input = document.createElement('input');
    input.type = 'checkbox';
    input.id = `${prefix}_${paramName}`;
    input.name = paramName;
    input.checked = paramDef.default || false;
  }

  if (input) {
    formGroup.appendChild(input);
  }

  return formGroup;
}

/**
 * Get optimizer parameter elements.
 * @returns {Array}
 */
function getOptimizerParamElements() {
  const params = window.currentStrategyConfig?.parameters || {};
  const checkboxes = document.querySelectorAll('.opt-param-toggle');

  return Array.from(checkboxes).map((checkbox) => {
    const paramName = checkbox.dataset.paramName || checkbox.id.replace(/^opt-/, '');
    return {
      name: paramName,
      checkbox,
      fromInput: document.getElementById(`opt-${paramName}-from`),
      toInput: document.getElementById(`opt-${paramName}-to`),
      stepInput: document.getElementById(`opt-${paramName}-step`),
      def: params[paramName] || {}
    };
  });
}
```

---

#### 4.4: Create `src/ui/static/js/presets.js`

**Content:** All preset management functions.

```javascript
/**
 * Preset management functions.
 * Dependencies: utils.js, api.js
 */

// Preset constants
const DEFAULT_PRESET_KEY = 'defaults';
const PRESET_NAME_PATTERN = /^[A-Za-z0-9 _-]{1,64}$/;
const PRESET_LABELS = {
  dateFilter: 'Date Filter',
  backtester: 'Backtester',
  startDate: 'Start Date',
  startTime: 'Start Time',
  endDate: 'End Date',
  endTime: 'End Time',
  csvPath: 'CSV Path',
  workerProcesses: 'Worker Processes',
  minProfitFilter: 'Net Profit Filter',
  minProfitThreshold: 'Net Profit Min %',
  scoreFilterEnabled: 'Score Filter',
  scoreThreshold: 'Score Min Score',
  scoreWeights: 'Score Weights',
  scoreEnabledMetrics: 'Score Enabled Metrics',
  scoreInvertMetrics: 'Score Invert Metrics'
};

// Global preset state
window.knownPresets = [];
window.selectedCsvPath = '';
window.defaults = {
  dateFilter: true,
  backtester: true,
  startDate: '',
  startTime: '',
  endDate: '',
  endTime: '',
  csvPath: '',
  workerProcesses: 6,
  minProfitFilter: false,
  minProfitThreshold: 0,
  scoreFilterEnabled: false,
  scoreThreshold: 60,
  scoreWeights: { romad: 0.25, sharpe: 0.20, pf: 0.20, ulcer: 0.15, recovery: 0.10, consistency: 0.10 },
  scoreEnabledMetrics: { romad: true, sharpe: true, pf: true, ulcer: true, recovery: true, consistency: true },
  scoreInvertMetrics: { ulcer: true }
};

/**
 * Format preset label.
 * @param {string} key - Preset key
 * @returns {string}
 */
function formatPresetLabel(key) {
  return PRESET_LABELS[key] || key;
}

/**
 * Apply preset values to form.
 * @param {Object} values - Preset values
 * @param {Object} options - Options
 */
function applyPresetValues(values, { clearResults = false } = {}) {
  if (!values || typeof values !== 'object') {
    return;
  }

  if (Object.prototype.hasOwnProperty.call(values, 'csvPath')) {
    const csvPathValue = typeof values.csvPath === 'string' ? values.csvPath.trim() : '';
    window.selectedCsvPath = csvPathValue;
  } else {
    window.selectedCsvPath = '';
  }

  if (Object.prototype.hasOwnProperty.call(values, 'dateFilter')) {
    setCheckboxValue('dateFilter', values.dateFilter);
  }
  if (Object.prototype.hasOwnProperty.call(values, 'backtester')) {
    setCheckboxValue('backtester', values.backtester);
  }
  if (Object.prototype.hasOwnProperty.call(values, 'startDate')) {
    setInputValue('startDate', values.startDate);
  }
  if (Object.prototype.hasOwnProperty.call(values, 'startTime')) {
    setInputValue('startTime', values.startTime);
  }
  if (Object.prototype.hasOwnProperty.call(values, 'endDate')) {
    setInputValue('endDate', values.endDate);
  }
  if (Object.prototype.hasOwnProperty.call(values, 'endTime')) {
    setInputValue('endTime', values.endTime);
  }

  if (Object.prototype.hasOwnProperty.call(values, 'workerProcesses')) {
    const workerInput = document.getElementById('workerProcesses');
    if (workerInput) {
      workerInput.value = values.workerProcesses;
    }
  }

  const minProfitCheckbox = document.getElementById('minProfitFilter');
  const minProfitInput = document.getElementById('minProfitThreshold');
  if (minProfitCheckbox && Object.prototype.hasOwnProperty.call(values, 'minProfitFilter')) {
    minProfitCheckbox.checked = Boolean(values.minProfitFilter);
  }
  if (minProfitInput && Object.prototype.hasOwnProperty.call(values, 'minProfitThreshold')) {
    setInputValue('minProfitThreshold', values.minProfitThreshold);
  }

  const scoreSettings = {
    scoreFilterEnabled: Object.prototype.hasOwnProperty.call(values, 'scoreFilterEnabled')
      ? values.scoreFilterEnabled
      : window.defaults.scoreFilterEnabled,
    scoreThreshold: Object.prototype.hasOwnProperty.call(values, 'scoreThreshold')
      ? values.scoreThreshold
      : window.defaults.scoreThreshold,
    scoreWeights: clonePreset(
      Object.prototype.hasOwnProperty.call(values, 'scoreWeights')
        ? values.scoreWeights
        : window.defaults.scoreWeights
    ),
    scoreEnabledMetrics: clonePreset(
      Object.prototype.hasOwnProperty.call(values, 'scoreEnabledMetrics')
        ? values.scoreEnabledMetrics
        : window.defaults.scoreEnabledMetrics
    ),
    scoreInvertMetrics: clonePreset(
      Object.prototype.hasOwnProperty.call(values, 'scoreInvertMetrics')
        ? values.scoreInvertMetrics
        : window.defaults.scoreInvertMetrics
    )
  };
  applyScoreSettings(scoreSettings);

  // Apply dynamic strategy parameters
  applyDynamicBacktestParams(values);

  if (clearResults) {
    const csvFileInputEl = document.getElementById('csvFile');
    if (csvFileInputEl) {
      csvFileInputEl.value = '';
    }
    const resultsEl = document.getElementById('results');
    if (resultsEl) {
      resultsEl.textContent = 'Нажмите «Run» для запуска бэктеста…';
      resultsEl.classList.remove('ready', 'loading');
    }
    clearErrorMessage();
    const optimizerResultsEl = document.getElementById('optimizerResults');
    if (optimizerResultsEl) {
      optimizerResultsEl.style.display = 'none';
      optimizerResultsEl.textContent = '';
      optimizerResultsEl.classList.remove('ready', 'loading');
    }
    const progressContainer = document.getElementById('optimizerProgress');
    if (progressContainer) {
      progressContainer.style.display = 'none';
    }
  }

  const csvFileInputEl = document.getElementById('csvFile');
  const currentFiles = csvFileInputEl ? Array.from(csvFileInputEl.files || []) : [];
  renderSelectedFiles(currentFiles);
  syncMinProfitFilterUI();
  syncScoreFilterUI();
  updateScoreFormulaPreview();
}

/**
 * Update defaults.
 * @param {Object} values - New default values
 */
function updateDefaults(values) {
  const merged = { ...window.defaults, ...clonePreset(values) };
  window.defaults = merged;
}

/**
 * Apply defaults to form.
 * @param {Object} options - Options
 */
function applyDefaults(options = {}) {
  const clearResults =
    options && Object.prototype.hasOwnProperty.call(options, 'clearResults')
      ? Boolean(options.clearResults)
      : true;
  applyPresetValues(window.defaults, { clearResults });
}

/**
 * Collect current preset values from form.
 * @returns {Object}
 */
function collectPresetValues() {
  const minProfitCheckbox = document.getElementById('minProfitFilter');
  const minProfitInput = document.getElementById('minProfitThreshold');
  const workerInput = document.getElementById('workerProcesses');
  const csvPathValue = typeof window.selectedCsvPath === 'string' ? window.selectedCsvPath.trim() : '';
  const scoreState = readScoreUIState();

  const dynamicParams = collectDynamicBacktestParams();

  return {
    dateFilter: document.getElementById('dateFilter').checked,
    backtester: document.getElementById('backtester').checked,
    startDate: document.getElementById('startDate').value.trim(),
    startTime: document.getElementById('startTime').value.trim(),
    endDate: document.getElementById('endDate').value.trim(),
    endTime: document.getElementById('endTime').value.trim(),
    csvPath: csvPathValue,
    workerProcesses: workerInput
      ? parseNumber(workerInput.value, window.defaults.workerProcesses)
      : window.defaults.workerProcesses,
    minProfitFilter: Boolean(minProfitCheckbox && minProfitCheckbox.checked),
    minProfitThreshold: minProfitInput
      ? parseNumber(minProfitInput.value, window.defaults.minProfitThreshold)
      : window.defaults.minProfitThreshold,
    scoreFilterEnabled: Boolean(scoreState.scoreFilterEnabled),
    scoreThreshold: scoreState.scoreThreshold,
    scoreWeights: { ...scoreState.scoreWeights },
    scoreEnabledMetrics: { ...scoreState.scoreEnabledMetrics },
    scoreInvertMetrics: { ...scoreState.scoreInvertMetrics },
    ...dynamicParams
  };
}

/**
 * Load preset by name.
 * @param {string} name - Preset name
 * @param {Object} options - Options
 * @returns {Promise<Object>}
 */
async function loadPreset(name, { clearResults = false } = {}) {
  const data = await loadPresetRequest(name);
  const values = data?.values || {};
  if (name.toLowerCase() === DEFAULT_PRESET_KEY) {
    updateDefaults(values);
    applyDefaults({ clearResults });
  } else {
    applyPresetValues(values, { clearResults });
  }
  return values;
}

/**
 * Render preset list in dropdown.
 */
function renderPresetList() {
  const presetListEl = document.getElementById('presetList');
  const presetEmptyEl = document.getElementById('presetEmpty');

  if (!presetListEl || !presetEmptyEl) {
    return;
  }

  presetListEl.innerHTML = '';
  const userPresets = window.knownPresets.filter((item) => !item.is_default);
  if (!userPresets.length) {
    presetEmptyEl.style.display = 'block';
    return;
  }

  presetEmptyEl.style.display = 'none';
  const fragment = document.createDocumentFragment();
  userPresets.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'preset-item';

    const applyButton = document.createElement('button');
    applyButton.type = 'button';
    applyButton.className = 'preset-entry';
    applyButton.textContent = item.name;
    applyButton.addEventListener('click', (event) => {
      event.stopPropagation();
      handlePresetSelection(item.name);
    });

    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'preset-actions';

    const overwriteButton = document.createElement('button');
    overwriteButton.type = 'button';
    overwriteButton.className = 'preset-action-btn preset-overwrite';
    overwriteButton.setAttribute('aria-label', `Overwrite preset ${item.name}`);
    overwriteButton.title = 'Overwrite preset';
    overwriteButton.textContent = '⟳';
    overwriteButton.addEventListener('click', (event) => {
      event.stopPropagation();
      handlePresetOverwrite(item.name);
    });

    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'preset-action-btn preset-delete';
    deleteButton.setAttribute('aria-label', `Delete preset ${item.name}`);
    deleteButton.title = 'Delete preset';
    deleteButton.textContent = '✕';
    deleteButton.addEventListener('click', (event) => {
      event.stopPropagation();
      handlePresetDelete(item.name);
    });

    actionsContainer.appendChild(overwriteButton);
    actionsContainer.appendChild(deleteButton);
    row.appendChild(applyButton);
    row.appendChild(actionsContainer);
    fragment.appendChild(row);
  });

  presetListEl.appendChild(fragment);
}

/**
 * Refresh preset list from server.
 * @param {boolean} silent - Suppress errors
 */
async function refreshPresetList(silent = false) {
  try {
    const data = await fetchPresetsList();
    window.knownPresets = Array.isArray(data?.presets) ? data.presets : [];
  } catch (error) {
    window.knownPresets = [];
    if (!silent) {
      showErrorMessage(error.message || 'Failed to fetch presets');
    }
    console.error(error);
  }
  renderPresetList();
}

// Preset menu handlers
function openPresetMenu() {
  const presetDropdownEl = document.getElementById('presetDropdown');
  const presetToggleEl = document.getElementById('presetToggle');
  const presetMenuEl = document.getElementById('presetMenu');

  if (!presetDropdownEl) return;

  presetDropdownEl.classList.add('open');
  if (presetToggleEl) presetToggleEl.setAttribute('aria-expanded', 'true');
  if (presetMenuEl) presetMenuEl.setAttribute('aria-hidden', 'false');
}

function closePresetMenu() {
  const presetDropdownEl = document.getElementById('presetDropdown');
  const presetToggleEl = document.getElementById('presetToggle');
  const presetMenuEl = document.getElementById('presetMenu');

  if (!presetDropdownEl) return;

  presetDropdownEl.classList.remove('open');
  if (presetToggleEl) presetToggleEl.setAttribute('aria-expanded', 'false');
  if (presetMenuEl) presetMenuEl.setAttribute('aria-hidden', 'true');
}

function togglePresetMenu() {
  const presetDropdownEl = document.getElementById('presetDropdown');
  if (!presetDropdownEl) return;

  if (presetDropdownEl.classList.contains('open')) {
    closePresetMenu();
  } else {
    openPresetMenu();
  }
}

async function handleApplyDefaults() {
  closePresetMenu();
  try {
    await loadPreset(DEFAULT_PRESET_KEY, { clearResults: true });
    clearErrorMessage();
  } catch (error) {
    showErrorMessage(error.message || 'Failed to load defaults');
  }
}

async function handlePresetSelection(name) {
  closePresetMenu();
  try {
    await loadPreset(name, { clearResults: false });
    clearErrorMessage();
  } catch (error) {
    showErrorMessage(error.message || 'Failed to load preset');
  }
}

async function handleSaveAsPreset() {
  closePresetMenu();
  const values = collectPresetValues();
  let presetName = '';

  while (true) {
    const input = window.prompt('Enter preset name:', '');
    if (input === null) return;

    const trimmed = input.trim();
    if (!trimmed) {
      window.alert('Preset name cannot be empty.');
      continue;
    }
    if (trimmed.toLowerCase() === DEFAULT_PRESET_KEY) {
      window.alert('Cannot use name "defaults".');
      continue;
    }
    if (!PRESET_NAME_PATTERN.test(trimmed)) {
      window.alert('Name can only contain letters, numbers, spaces, hyphens and underscores.');
      continue;
    }
    if (window.knownPresets.some((item) => item.name.toLowerCase() === trimmed.toLowerCase())) {
      window.alert('Preset with this name already exists.');
      continue;
    }
    presetName = trimmed;
    break;
  }

  try {
    await savePresetRequest(presetName, values);
    await refreshPresetList(false);
    window.alert(`Preset "${presetName}" saved.`);
  } catch (error) {
    showErrorMessage(error.message || 'Failed to save preset');
  }
}

async function handleSaveDefaults() {
  closePresetMenu();
  const values = collectPresetValues();
  try {
    const response = await saveDefaultsRequest(values);
    updateDefaults(response?.values || values);
    window.alert('Current settings saved as defaults.');
  } catch (error) {
    showErrorMessage(error.message || 'Failed to save defaults');
  }
}

async function handlePresetDelete(name) {
  const confirmed = window.confirm(`Delete preset "${name}"?`);
  if (!confirmed) return;

  closePresetMenu();
  try {
    await deletePresetRequest(name);
    await refreshPresetList(false);
  } catch (error) {
    showErrorMessage(error.message || 'Failed to delete preset');
  }
}

async function handlePresetOverwrite(name) {
  const confirmed = window.confirm(`Overwrite preset "${name}" with current settings?`);
  if (!confirmed) return;

  closePresetMenu();
  const values = collectPresetValues();
  try {
    await overwritePresetRequest(name, values);
    await refreshPresetList(false);
    window.alert(`Preset "${name}" overwritten.`);
  } catch (error) {
    showErrorMessage(error.message || 'Failed to overwrite preset');
  }
}

/**
 * Initialize presets on page load.
 */
async function initializePresets() {
  try {
    await loadPreset(DEFAULT_PRESET_KEY, { clearResults: true });
    clearErrorMessage();
  } catch (error) {
    console.error(error);
    applyDefaults({ clearResults: true });
  }
  await refreshPresetList(true);
}
```

**Note:** The presets.js file is large. Continue the remaining functions in Part 2 of the prompt...

---

**FILE SIZE LIMIT REACHED - Continue in prompt_10-2.md**

This prompt is getting large. Please continue with Part 2 (`prompt_10-2.md`) which contains:
- `ui-handlers.js` - Event handlers and form submission
- `main.js` - App initialization
- Step 5: Clean HTML template
- Step 6: Testing procedures
- Validation checklist
