# Phase 9-5-3: Frontend & UI Refactoring - Generic Parameter Rendering System

**Target Agent**: GPT 5.1 Codex
**Project**: S_01 Trailing MA Backtesting Platform
**Task**: Phase 9-5-3 - Frontend UI Refactoring
**Complexity**: High (Frontend architectural refactoring)
**Priority**: Critical (Continuation of Phase 9-5 refactoring)
**Prerequisites**: Phases 9-5-1 and 9-5-2 must be completed first

---

## Executive Summary

This is **Phase 9-5-3**, the third phase in the comprehensive refactoring series to eliminate S01/S04 architecture inconsistencies.

**Phase 9-5-1 (Completed)** standardized:
- Parameter naming to camelCase throughout Python codebase
- OptimizationResult to generic dict-based structure
- CSV export system to be config-driven

**Phase 9-5-2 (Completed)** cleaned up:
- Removed S01-specific defaults from server layer
- Eliminated dual naming fallbacks
- Implemented generic parameter type loading from config.json

**Phase 9-5-3 (This Phase)** focuses on **frontend UI refactoring**:
- Remove `requires_ma_selection` feature flag from strategy configs
- Implement generic parameter rendering based on parameter type
- Build parameter forms dynamically from config.json
- Remove all hardcoded parameter names from frontend JavaScript

**Success Metric**: After Phase 9-5-3, the frontend can render any strategy's parameters without code changes, using only the strategy's config.json.

**Next Phase**:
- Phase 9-5-4 will update tests and documentation

---

## Table of Contents

1. [Project Context](#project-context)
2. [Previous Phases Recap](#previous-phases-recap)
3. [Current Problems in Frontend](#current-problems-in-frontend)
4. [Implementation Plan](#implementation-plan)
5. [Testing Requirements](#testing-requirements)
6. [Code Quality Standards](#code-quality-standards)
7. [File Reference Guide](#file-reference-guide)

---

## Project Context

### What This Project Does

This is a **backtesting and optimization platform** for trading strategies:

- **Strategies**: S01 (Trailing MA), S04 (StochRSI), future strategies
- **Core Engines**: Backtest, Optuna optimization, Walk-forward analysis
- **Interface**: Flask web server + HTML/JS Single Page Application (SPA)
- **Data Flow**: User selects strategy → Frontend loads config.json → Renders parameter form → Submits to backend

### Key Architecture Principles

1. **Config-Driven UI**: Frontend renders based on strategy's config.json
2. **Generic Parameter System**: Support int, float, select (dropdown), bool types
3. **No Hardcoded Strategy Knowledge**: Frontend shouldn't know about "maType" or "rsiLen"
4. **Parameter Type Mapping**: Match Pine Script input types to HTML widgets

### Pine Script to Frontend Mapping

| Pine Script Input | config.json Type | Frontend Widget | HTML Element |
|-------------------|------------------|-----------------|--------------|
| `input.int()` | `"type": "int"` | Number input (integer) | `<input type="number" step="1">` |
| `input.float()` | `"type": "float"` | Number input (decimal) | `<input type="number" step="0.1">` |
| `input.string(options=[...])` | `"type": "select"` | Dropdown | `<select>` |
| `input.bool()` | `"type": "bool"` | Checkbox | `<input type="checkbox">` |

---

## Previous Phases Recap

### ✓ Phase 9-5-1: Foundation Refactoring
- Converted all Python parameters to camelCase
- Made OptimizationResult generic with `params: Dict[str, Any]`
- Created dynamic CSV export from config.json

### ✓ Phase 9-5-2: Server Layer Cleanup
- Removed S01-specific defaults from DEFAULT_PRESET
- Eliminated all dual naming fallbacks (camelCase vs snake_case)
- Implemented `_get_parameter_types()` to load from config.json
- Added generic parameter validation

**Result**: Backend is now fully generic and config-driven.

---

## Current Problems in Frontend

### Problem 1: requires_ma_selection Feature Flag

**File**: `src/strategies/s01_trailing_ma/config.json`

**Current**:
```json
{
  "id": "s01_trailing_ma",
  "name": "S01 Trailing MA",
  "features": {
    "requires_ma_selection": true,
    "ma_groups": ["trend", "trail_long", "trail_short"]
  },
  "parameters": {
    "maType": {"type": "select", "options": ["EMA", "SMA", ...]},
    // ...
  }
}
```

**Issue**: `requires_ma_selection` is a **hardcoded feature flag** that triggers special MA dropdown rendering. This violates the generic architecture.

**Why it's wrong**:
- Frontend checks `if (config.features.requires_ma_selection)` → S01-specific logic
- S04 doesn't have this flag, so different rendering paths
- Any strategy with dropdown parameters needs this flag
- Should render dropdowns based on `"type": "select"`, not feature flags

### Problem 2: Hardcoded Parameter Rendering

**File**: `index.html` or `src/static/js/main.js` (depending on structure)

**Current**:
```javascript
if (config.features && config.features.requires_ma_selection) {
    // Hardcoded parameter names
    renderMATypeDropdown("maType", config.parameters.maType);
    renderMATypeDropdown("trailLongType", config.parameters.trailLongType);
    renderMATypeDropdown("trailShortType", config.parameters.trailShortType);
}

// Then render other parameters differently
for (const [paramName, paramConfig] of Object.entries(config.parameters)) {
    if (paramName === "maType" || paramName === "trailLongType" || paramName === "trailShortType") {
        continue;  // Skip, already rendered above
    }
    renderParameter(paramName, paramConfig);
}
```

**Why it's wrong**:
- Hardcoded parameter names (`maType`, `trailLongType`, `trailShortType`)
- Special-case logic for S01
- S04's parameters render through different code path
- Adding a new strategy with dropdowns requires frontend code changes

### Problem 3: Non-Generic Parameter Rendering

**Current approach**:
- Some parameters rendered by type (`renderParameter()`)
- Other parameters rendered by name (`renderMATypeDropdown()`)
- Inconsistent rendering logic
- No single source of truth

**Should be**:
- **All** parameters rendered by type from config.json
- Single `renderParameter()` function handles all types
- No parameter name checking

---

## Implementation Plan

You will complete **3 major tasks** sequentially. Each task must be tested before proceeding.

---

## Task 1: Remove requires_ma_selection Feature Flag

**Goal**: Delete feature flags from strategy configs, use parameter types instead.

### 1.1 Update S01 Config

**File**: `src/strategies/s01_trailing_ma/config.json`

**Find and DELETE** the `features` section:

```json
{
  "id": "s01_trailing_ma",
  "name": "S01 Trailing MA",
  "version": "v01",
  "description": "Trailing Moving Average strategy",

  "features": {                          // ← DELETE THIS ENTIRE SECTION
    "requires_ma_selection": true,
    "ma_groups": ["trend", "trail_long", "trail_short"]
  },

  "parameters": {
    // ... keep all parameters
  }
}
```

**After deletion**:
```json
{
  "id": "s01_trailing_ma",
  "name": "S01 Trailing MA",
  "version": "v01",
  "description": "Trailing Moving Average strategy with crossover signals and trailing exits",

  "parameters": {
    "maType": {
      "type": "select",           // ← This is sufficient for dropdown rendering
      "label": "Trend MA Type",
      "default": "EMA",
      "options": ["EMA", "SMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"],
      "group": "Trend Detection"
    },
    // ... rest of parameters
  }
}
```

### 1.2 Verify S01 Parameter Types

**File**: `src/strategies/s01_trailing_ma/config.json`

Verify these parameters have correct types:

**MA Type Parameters** (should be `"type": "select"`):
- `maType` - Trend MA Type
- `trailLongType` - Trail Long MA Type
- `trailShortType` - Trail Short MA Type

**Integer Parameters** (should be `"type": "int"`):
- `maLength`, `closeCountLong`, `closeCountShort`
- `stopLongLP`, `stopShortLP`
- `stopLongMaxDays`, `stopShortMaxDays`
- `trailLongLength`, `trailShortLength`
- `atrPeriod`

**Float Parameters** (should be `"type": "float"`):
- `stopLongX`, `stopLongRR`, `stopShortX`, `stopShortRR`
- `stopLongMaxPct`, `stopShortMaxPct`
- `trailRRLong`, `trailRRShort`
- `trailLongOffset`, `trailShortOffset`
- `riskPerTrade`, `contractSize`, `commissionRate`

### 1.3 Verify S04 Config Consistency

**File**: `src/strategies/s04_stochrsi/config.json`

Verify S04 config does **not** have `features` section and uses proper types:

```json
{
  "id": "s04_stochrsi",
  "name": "S04 StochRSI",
  "version": "v01",
  "description": "StochRSI-based oscillator strategy",

  "parameters": {
    "rsiLen": {
      "type": "int",
      "label": "RSI Length",
      "default": 16,
      "min": 1,
      "max": 200
    },
    "obLevel": {
      "type": "float",
      "label": "Overbought Level",
      "default": 75.0,
      "min": 0.0,
      "max": 100.0
    }
    // ... other parameters
  }
}
```

### Task 1 Verification

**Checklist**:
- [ ] `features` section deleted from S01 config.json
- [ ] `features` section not present in S04 config.json
- [ ] All S01 MA type parameters use `"type": "select"`
- [ ] All S01 integer parameters use `"type": "int"`
- [ ] All S01 float parameters use `"type": "float"`
- [ ] All S04 parameters have correct types
- [ ] Config files are valid JSON (no syntax errors)

**Test Command**:
```bash
# Validate JSON syntax
python -m json.tool src/strategies/s01_trailing_ma/config.json > /dev/null
python -m json.tool src/strategies/s04_stochrsi/config.json > /dev/null

# Should output nothing if valid, error if syntax issue
```

---

## Task 2: Implement Generic Parameter Rendering

**Goal**: Build parameter forms dynamically from config.json based on type.

### 2.1 Locate Frontend JavaScript

**Files to modify**:
- `index.html` - If JavaScript is inline in `<script>` tags
- `src/static/js/main.js` - If JavaScript is separated (check if this file exists)

**Search for**:
- `requires_ma_selection` - Feature flag check
- `renderMATypeDropdown` - Hardcoded MA dropdown rendering
- `renderParameter` - Current parameter rendering logic

### 2.2 Create Generic renderParameter Function

**Find or create** the main parameter rendering function.

**DELETE old hardcoded approach**:
```javascript
if (config.features && config.features.requires_ma_selection) {
    renderMATypeDropdown("maType", config.parameters.maType);
    renderMATypeDropdown("trailLongType", config.parameters.trailLongType);
    renderMATypeDropdown("trailShortType", config.parameters.trailShortType);
}
```

**REPLACE with generic approach**:

```javascript
/**
 * Render all strategy parameters dynamically based on config.json
 * @param {Object} config - Strategy configuration object
 */
function renderStrategyParameters(config) {
    const parametersContainer = document.getElementById("parameters-container");
    if (!parametersContainer) {
        console.error("Parameters container not found");
        return;
    }

    // Clear existing parameters
    parametersContainer.innerHTML = "";

    const parameters = config.parameters || {};

    // Group parameters if groups defined
    const grouped = groupParametersByCategory(parameters);

    // Render each group
    for (const [groupName, groupParams] of Object.entries(grouped)) {
        if (groupName !== "ungrouped") {
            const groupHeader = document.createElement("h3");
            groupHeader.className = "parameter-group-header";
            groupHeader.textContent = groupName;
            parametersContainer.appendChild(groupHeader);
        }

        // Render parameters in this group
        for (const [paramName, paramConfig] of Object.entries(groupParams)) {
            const paramElement = renderParameter(paramName, paramConfig);
            parametersContainer.appendChild(paramElement);
        }
    }
}

/**
 * Group parameters by their 'group' field
 * @param {Object} parameters - Parameters object from config.json
 * @returns {Object} - Grouped parameters
 */
function groupParametersByCategory(parameters) {
    const groups = { ungrouped: {} };

    for (const [paramName, paramConfig] of Object.entries(parameters)) {
        const groupName = paramConfig.group || "ungrouped";
        if (!groups[groupName]) {
            groups[groupName] = {};
        }
        groups[groupName][paramName] = paramConfig;
    }

    return groups;
}

/**
 * Render a single parameter based on its type
 * @param {string} paramName - Parameter name (camelCase)
 * @param {Object} paramConfig - Parameter configuration from config.json
 * @returns {HTMLElement} - Parameter row element
 */
function renderParameter(paramName, paramConfig) {
    const row = document.createElement("div");
    row.className = "parameter-row";
    row.dataset.paramName = paramName;

    // Label
    const label = document.createElement("label");
    label.textContent = paramConfig.label || paramName;
    label.htmlFor = `param-${paramName}`;
    row.appendChild(label);

    // Input widget based on type
    let input;
    const paramType = paramConfig.type || "float";

    switch (paramType) {
        case "int":
        case "float":
            input = renderNumberInput(paramName, paramConfig);
            break;

        case "select":
        case "options":  // Support both naming conventions
            input = renderSelectDropdown(paramName, paramConfig);
            break;

        case "bool":
        case "boolean":
            input = renderCheckbox(paramName, paramConfig);
            break;

        default:
            console.warn(`Unknown parameter type: ${paramType} for ${paramName}`);
            input = renderNumberInput(paramName, paramConfig);  // Fallback
    }

    row.appendChild(input);

    // Optional: Add description/help text
    if (paramConfig.description) {
        const helpText = document.createElement("span");
        helpText.className = "parameter-help";
        helpText.textContent = paramConfig.description;
        row.appendChild(helpText);
    }

    return row;
}

/**
 * Render number input (int or float)
 */
function renderNumberInput(paramName, paramConfig) {
    const input = document.createElement("input");
    input.type = "number";
    input.id = `param-${paramName}`;
    input.name = paramName;
    input.className = "parameter-input number-input";

    // Set value
    input.value = paramConfig.default !== undefined ? paramConfig.default : 0;

    // Set constraints
    if (paramConfig.min !== undefined) input.min = paramConfig.min;
    if (paramConfig.max !== undefined) input.max = paramConfig.max;

    // Set step based on type
    if (paramConfig.step !== undefined) {
        input.step = paramConfig.step;
    } else if (paramConfig.type === "int") {
        input.step = 1;
    } else {
        input.step = 0.1;
    }

    return input;
}

/**
 * Render dropdown/select input
 */
function renderSelectDropdown(paramName, paramConfig) {
    const select = document.createElement("select");
    select.id = `param-${paramName}`;
    select.name = paramName;
    select.className = "parameter-input select-input";

    const options = paramConfig.options || [];

    options.forEach(optionValue => {
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = optionValue;

        if (optionValue === paramConfig.default) {
            option.selected = true;
        }

        select.appendChild(option);
    });

    return select;
}

/**
 * Render checkbox input
 */
function renderCheckbox(paramName, paramConfig) {
    const container = document.createElement("div");
    container.className = "checkbox-container";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = `param-${paramName}`;
    input.name = paramName;
    input.className = "parameter-input checkbox-input";
    input.checked = paramConfig.default !== undefined ? paramConfig.default : false;

    container.appendChild(input);
    return container;
}
```

### 2.3 Update Strategy Selection Handler

**Find the code** that handles strategy selection change (e.g., dropdown change event).

**Current** (approximate):
```javascript
strategySelect.addEventListener("change", function() {
    const strategyId = this.value;
    loadStrategyConfig(strategyId).then(config => {
        // Old hardcoded rendering
        if (config.features && config.features.requires_ma_selection) {
            // ... hardcoded MA dropdowns
        }
    });
});
```

**Target**:
```javascript
strategySelect.addEventListener("change", function() {
    const strategyId = this.value;

    // Load strategy config from server
    fetch(`/api/strategy/${strategyId}/config`)
        .then(response => response.json())
        .then(config => {
            // Store config globally for form submission
            window.currentStrategyConfig = config;

            // Render parameters generically
            renderStrategyParameters(config);
        })
        .catch(error => {
            console.error("Failed to load strategy config:", error);
        });
});
```

### 2.4 Implement Parameter Value Collection

**Add function** to collect parameter values from rendered form:

```javascript
/**
 * Collect parameter values from the rendered form
 * @returns {Object} - Parameter name-value pairs (camelCase keys)
 */
function collectParameterValues() {
    const params = {};
    const config = window.currentStrategyConfig;

    if (!config || !config.parameters) {
        return params;
    }

    // Iterate through each parameter in config
    for (const [paramName, paramConfig] of Object.entries(config.parameters)) {
        const input = document.getElementById(`param-${paramName}`);
        if (!input) continue;

        const paramType = paramConfig.type || "float";

        // Extract value based on type
        switch (paramType) {
            case "int":
                params[paramName] = parseInt(input.value, 10);
                break;

            case "float":
                params[paramName] = parseFloat(input.value);
                break;

            case "select":
            case "options":
                params[paramName] = input.value;
                break;

            case "bool":
            case "boolean":
                params[paramName] = input.checked;
                break;

            default:
                params[paramName] = input.value;
        }
    }

    return params;
}
```

### 2.5 Update Form Submission

**Find backtest/optimize submission handlers**.

**Update to use** `collectParameterValues()`:

```javascript
// Backtest submission
backtestButton.addEventListener("click", function() {
    const strategyId = strategySelect.value;
    const params = collectParameterValues();  // ← Generic collection

    const payload = {
        strategy: strategyId,
        params: params,
        csvFile: csvFileInput.value,
    };

    fetch("/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
    .then(response => response.json())
    .then(result => {
        displayBacktestResults(result);
    })
    .catch(error => {
        console.error("Backtest failed:", error);
    });
});

// Optimization submission (similar pattern)
optimizeButton.addEventListener("click", function() {
    const strategyId = strategySelect.value;
    const params = collectParameterValues();  // ← Same generic collection

    const payload = {
        strategy: strategyId,
        params: params,
        nTrials: parseInt(nTrialsInput.value, 10),
        // ... other optimization settings
    };

    fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
    .then(/* ... */);
});
```

### Task 2 Verification

**Checklist**:
- [ ] `renderStrategyParameters()` function implemented
- [ ] `renderParameter()` handles all types (int, float, select, bool)
- [ ] `renderNumberInput()` creates number inputs with correct step
- [ ] `renderSelectDropdown()` creates dropdowns with options
- [ ] `renderCheckbox()` creates checkboxes
- [ ] `collectParameterValues()` extracts values by type
- [ ] Feature flag checks deleted
- [ ] Hardcoded parameter names removed
- [ ] Form submission uses generic collection

**Test Steps**:
1. Open browser to http://localhost:8000
2. Select S01 strategy
3. Verify all parameters render:
   - MA type dropdowns (maType, trailLongType, trailShortType)
   - Integer inputs (maLength, closeCountLong, etc.)
   - Float inputs (stopLongX, trailRRLong, etc.)
4. Select S04 strategy
5. Verify all S04 parameters render:
   - Integer inputs (rsiLen, stochLen, kLen, dLen)
   - Float inputs (obLevel, osLevel)
6. Submit backtest for S01 - verify success
7. Submit backtest for S04 - verify success

---

## Task 3: Add Strategy Config API Endpoint

**Goal**: Provide endpoint for frontend to fetch strategy config.json.

### 3.1 Add Endpoint in server.py

**File**: `src/server.py`

**Add this route**:

```python
@app.route("/api/strategy/<strategy_id>/config", methods=["GET"])
def get_strategy_config_endpoint(strategy_id: str):
    """Return strategy configuration for frontend rendering.

    Args:
        strategy_id: Strategy identifier (e.g., "s01_trailing_ma")

    Returns:
        JSON response with strategy configuration
    """
    try:
        from strategies import get_strategy_config

        config = get_strategy_config(strategy_id)

        # Return config with appropriate headers
        return jsonify(config), HTTPStatus.OK

    except FileNotFoundError:
        return (
            jsonify({"error": f"Strategy '{strategy_id}' not found"}),
            HTTPStatus.NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Failed to load config for {strategy_id}")
        return (
            jsonify({"error": f"Failed to load strategy config: {str(e)}"}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
```

### 3.2 Add Strategy List Endpoint (Optional)

**Add this route** to list available strategies:

```python
@app.route("/api/strategies", methods=["GET"])
def list_strategies_endpoint():
    """Return list of available strategies.

    Returns:
        JSON response with strategy list
    """
    try:
        from strategies import list_strategies

        strategies = list_strategies()

        # Return list with basic info
        strategy_list = []
        for strategy_id in strategies:
            try:
                config = get_strategy_config(strategy_id)
                strategy_list.append({
                    "id": strategy_id,
                    "name": config.get("name", strategy_id),
                    "version": config.get("version", "unknown"),
                    "description": config.get("description", ""),
                })
            except Exception:
                # Skip if config can't be loaded
                continue

        return jsonify({"strategies": strategy_list}), HTTPStatus.OK

    except Exception as e:
        logger.exception("Failed to list strategies")
        return (
            jsonify({"error": f"Failed to list strategies: {str(e)}"}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
```

### 3.3 Update Frontend to Use Endpoint

**In JavaScript**, update strategy config loading:

```javascript
/**
 * Load strategy configuration from server
 * @param {string} strategyId - Strategy identifier
 * @returns {Promise<Object>} - Strategy config object
 */
async function loadStrategyConfig(strategyId) {
    const response = await fetch(`/api/strategy/${strategyId}/config`);

    if (!response.ok) {
        throw new Error(`Failed to load config for ${strategyId}: ${response.statusText}`);
    }

    const config = await response.json();
    return config;
}

// Usage in strategy selection handler
strategySelect.addEventListener("change", async function() {
    const strategyId = this.value;

    try {
        const config = await loadStrategyConfig(strategyId);
        window.currentStrategyConfig = config;
        renderStrategyParameters(config);
    } catch (error) {
        console.error("Failed to load strategy config:", error);
        alert(`Error loading strategy: ${error.message}`);
    }
});
```

### 3.4 Handle Strategy Dropdown Population

**Update strategy dropdown** to populate from API (optional but recommended):

```javascript
/**
 * Populate strategy dropdown from server
 */
async function populateStrategyDropdown() {
    try {
        const response = await fetch("/api/strategies");
        const data = await response.json();

        const strategySelect = document.getElementById("strategy-select");
        strategySelect.innerHTML = "";  // Clear existing options

        data.strategies.forEach(strategy => {
            const option = document.createElement("option");
            option.value = strategy.id;
            option.textContent = `${strategy.name} (${strategy.version})`;
            strategySelect.appendChild(option);
        });

        // Load first strategy by default
        if (data.strategies.length > 0) {
            const firstStrategyId = data.strategies[0].id;
            const config = await loadStrategyConfig(firstStrategyId);
            window.currentStrategyConfig = config;
            renderStrategyParameters(config);
        }

    } catch (error) {
        console.error("Failed to populate strategies:", error);
    }
}

// Call on page load
document.addEventListener("DOMContentLoaded", function() {
    populateStrategyDropdown();
});
```

### Task 3 Verification

**Checklist**:
- [ ] `/api/strategy/<strategy_id>/config` endpoint added
- [ ] `/api/strategies` endpoint added (optional)
- [ ] Endpoint returns correct JSON for S01
- [ ] Endpoint returns correct JSON for S04
- [ ] Frontend uses endpoint to load config
- [ ] Strategy dropdown populates from API
- [ ] Error handling for missing strategies

**Test Commands**:
```bash
# Test config endpoint
curl http://localhost:8000/api/strategy/s01_trailing_ma/config
curl http://localhost:8000/api/strategy/s04_stochrsi/config

# Test strategies list endpoint
curl http://localhost:8000/api/strategies

# Should return valid JSON for each
```

---

## Testing Requirements

### Browser Testing

After completing all tasks, perform comprehensive browser tests:

1. **Strategy Selection**:
   - Open http://localhost:8000
   - Select S01 strategy
   - Verify all parameters render correctly
   - Check MA type dropdowns show all options
   - Check integer inputs have step=1
   - Check float inputs have step=0.1

2. **Parameter Interaction**:
   - Change maType dropdown - verify value updates
   - Change maLength input - verify value updates
   - Switch to S04 strategy
   - Verify parameters change to S04 parameters
   - Switch back to S01
   - Verify parameters revert to S01

3. **Form Submission**:
   - Fill in S01 parameters
   - Submit backtest
   - Verify parameters sent correctly (check browser DevTools Network tab)
   - Verify backtest completes
   - Repeat for S04

4. **Optimization Workflow**:
   - Select S01 strategy
   - Configure optimization settings
   - Submit optimization
   - Verify parameters collected correctly
   - Check CSV export includes correct parameter columns

### Cross-Browser Testing

Test in multiple browsers:
- Chrome/Edge (Chromium)
- Firefox
- Safari (if available)

Verify:
- Dropdowns render correctly
- Number inputs work
- Form submission succeeds
- No JavaScript errors in console

### Regression Testing

**S01 Functionality**:
- All MA type dropdowns work
- All parameter inputs accept values
- Backtest produces correct results
- Optimization completes successfully
- CSV export includes all parameters

**S04 Functionality**:
- All parameter inputs work
- Backtest produces correct results
- Optimization completes successfully
- CSV export includes all parameters

---

## Code Quality Standards

### JavaScript Style

1. **Use modern JavaScript** (ES6+)
   - `const` and `let` instead of `var`
   - Arrow functions where appropriate
   - Async/await for promises
   - Template literals for string interpolation

2. **Naming Conventions**:
   - camelCase for variables and functions
   - PascalCase for classes (if any)
   - UPPER_CASE for constants

3. **Comments**:
   - JSDoc comments for functions
   - Inline comments for complex logic

4. **Error Handling**:
   - Try-catch for async operations
   - User-friendly error messages
   - Console logging for debugging

### HTML/CSS

1. **Semantic HTML**:
   - Use appropriate elements (`<label>`, `<select>`, `<input>`)
   - Accessible form elements (proper `for` attributes)

2. **CSS Classes**:
   - Descriptive class names
   - Consistent naming convention (e.g., BEM)

3. **Responsive Design**:
   - Ensure parameter forms work on different screen sizes
   - Test with browser zoom

### Git Commits

1. **Atomic Commits**: One logical change per commit
2. **Commit Messages**:
   - Format: `[Phase 9-5-3] Brief description`
   - Examples:
     - `[Phase 9-5-3] Remove requires_ma_selection feature flag`
     - `[Phase 9-5-3] Implement generic parameter rendering`
     - `[Phase 9-5-3] Add strategy config API endpoint`

---

## File Reference Guide

### Frontend Files

**Primary Files**:
- `index.html` - Main HTML page with embedded JavaScript
  - Search for: `<script>` tags
  - Parameter rendering logic
  - Form submission handlers

**Alternative Structure** (if JavaScript is separated):
- `src/static/js/main.js` - Main JavaScript file
- `src/static/css/style.css` - Stylesheet

### Strategy Config Files

**S01**:
- `src/strategies/s01_trailing_ma/config.json` - S01 parameter definitions

**S04**:
- `src/strategies/s04_stochrsi/config.json` - S04 parameter definitions

### Server File

**Backend**:
- `src/server.py` - Flask server (add API endpoints here)

---

## Success Criteria

After completing Phase 9-5-3, verify:

- [ ] **`features` section deleted** from S01 config.json
- [ ] **All parameters have correct types** in config.json
- [ ] **`renderStrategyParameters()` implemented**
- [ ] **Generic `renderParameter()` handles all types**
- [ ] **No hardcoded parameter names** in JavaScript
- [ ] **No feature flag checks** in JavaScript
- [ ] **`collectParameterValues()` works generically**
- [ ] **Strategy config API endpoint added**
- [ ] **Strategy list API endpoint added** (optional)
- [ ] **Frontend loads config from API**
- [ ] **S01 parameters render correctly** in browser
- [ ] **S04 parameters render correctly** in browser
- [ ] **MA type dropdowns work** for S01
- [ ] **Parameter submission works** for both strategies
- [ ] **Backtest works** for S01 and S04
- [ ] **Optimization works** for S01 and S04
- [ ] **No JavaScript errors** in browser console

---

## Critical Preservation

**DO NOT MODIFY**:
1. Backend Python code (except adding API endpoints)
2. Strategy implementation logic
3. Core optimization/backtest engines

**ONLY MODIFY**:
- `index.html` (or `src/static/js/main.js`)
- `src/strategies/s01_trailing_ma/config.json`
- `src/strategies/s04_stochrsi/config.json`
- `src/server.py` (only to add API endpoints)

---

## Next Steps

After completing Phase 9-5-3:

1. **Commit all changes** with clear commit messages
2. **Test in browser** thoroughly
3. **Document any issues** encountered
4. **Proceed to Phase 9-5-4** which will:
   - Update all test fixtures to use camelCase
   - Create naming consistency tests
   - Update CLAUDE.md with naming conventions
   - Create ADDING_NEW_STRATEGY.md guide

---

## Questions or Issues

If you encounter ambiguity or issues:

1. **Preserve existing behavior** - Refactoring should not change functionality
2. **Ask for clarification** - Don't guess on critical decisions
3. **Test in browser** - Verify each change visually
4. **Check browser console** - Look for JavaScript errors

---

**END OF PHASE 9-5-3 PROMPT**
