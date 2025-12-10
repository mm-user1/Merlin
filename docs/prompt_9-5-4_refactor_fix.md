# Phase 9-5-4 Refactor Fix - Complete Implementation Guide

**Version:** 1.0
**Date:** 2025-12-10
**Target:** GPT 5.1 Codex
**Scope:** Fix all remaining issues after Phase 9-5-4 migration to achieve fully generic, config-driven architecture

---

## Executive Summary

This document provides comprehensive instructions to fix all remaining hardcoded S01-specific code after Phase 9-5-4. The goal is to achieve a fully generic, config-driven optimizer that works seamlessly with any strategy (S01, S04, and future strategies) without special-casing.

**Current State:**
- ✅ Backend API endpoints are mostly generic
- ✅ Backtest form is fully config-driven
- ✅ Basic parameter handling uses camelCase consistently
- ❌ Optimizer still contains S01-specific MA selection logic
- ❌ Feature flag scaffolding remains (dead code)
- ❌ OptimizationConfig has S01-only fields
- ❌ Frontend has inline CSS and lacks validation
- ❌ No frontend tests exist

**Target State:**
- ✅ Optimizer fully config-driven (works with any strategy)
- ✅ No S01-specific code in core layers
- ✅ All CSS externalized
- ✅ Frontend validation for optimizer ranges
- ✅ Frontend tests cover critical UI logic
- ✅ Improved regression test reporting

---

## Issues to Fix (Verified)

Based on `docs/need-to-fix-after-9-5-4_nw.md`, the following issues have been verified in the codebase:

### 1. Legacy Feature Flag Scaffold (Backend)
**Location:** `src/server.py` lines ~41-74, 1085-1143, 1307-1336
**Issue:** `_get_strategy_features()` function still exists and checks for `features` in config.json, but no strategies use it anymore
**Impact:** Dead code that executes but does nothing; clutters codebase

### 2. S01-Specific MA Handling in Server
**Location:** `src/server.py` lines ~1451-1453, 1317-1335
**Issue:** Optimizer payload uppercases MA types and expects `ma_types_trend/trail_*` fields
**Impact:** Blocks non-S01 strategies from using select-type parameters in optimizer

### 3. S01-Only Fields in OptimizationConfig
**Location:** `src/core/optuna_engine.py` lines ~40-44
**Issue:** Dataclass has `ma_types_trend`, `ma_types_trail_long`, `ma_types_trail_short`, `lock_trail_types`, `atr_period` hardcoded
**Impact:** Breaks optimizer for strategies without these exact fields

### 4. Hardcoded MA Logic in Optuna Engine
**Location:** `src/core/optuna_engine.py` lines ~360-410, 420-421, 565-568
**Issue:** Special-cases MA selection instead of using generic select parameter handling
**Impact:** Prevents other strategies from using select-type optimization

### 5. Walkforward Engine Assumes S01 Params
**Location:** `src/core/walkforward_engine.py` lines ~447-449, 585-594, 1050
**Issue:** References `ma_types_trend/trail_*` when building optimization configs
**Impact:** WFA only works with S01-shaped strategies

### 6. Optimizer UI Still Hardcoded to S01
**Location:** `src/index.html` lines ~419-537 (MA selectors), 2930-2947 (payload building)
**Issue:** Backtest form is config-driven, but optimizer form has hardcoded S01 MA selectors
**Impact:** UI doesn't adapt to different strategies; S04 optimizer shows wrong controls

### 7. Missing Client-Side Validation
**Location:** `src/index.html` (optimizer form submission)
**Issue:** No validation for `from < to`, positive step, or config min/max bounds
**Impact:** Users can submit invalid ranges, causing backend errors

### 8. Inline CSS Remains
**Location:** `src/index.html` lines ~8-48
**Issue:** Some CSS still inline in `<style>` tag despite `style.css` existing
**Impact:** Blocks full frontend separation (Phase 10 prep)

### 9. Frontend Tests Absent
**Location:** No test files for UI logic
**Issue:** No automated tests for `createFormField`, `generateOptimizerForm`, validation
**Impact:** Regressions go unnoticed during refactors

### 10. Regression Test Report Too Thin
**Location:** `tests/REGRESSION_TEST_REPORT.md`
**Issue:** Only 7 lines; lacks suite breakdown, timing, dataset details
**Impact:** Difficult to audit test coverage and track performance over time

**Note:** Issue #15 (Frontend remains monolithic) is excluded per user request - will be fixed in Phase 10.

---

## Architecture Context

### Current Architecture (Phase 9-5-4)

```
Core Principles:
- Parameter naming: camelCase end-to-end (Pine → config.json → Python → CSV)
- Hybrid model: Strategies own typed params; core uses Dict[str, Any]
- Config-driven: Backend/frontend derive schemas from config.json
- Strategy-agnostic core: No hardcoded strategy logic

Directory Structure:
src/
├── core/
│   ├── backtest_engine.py    # Defines TradeRecord, StrategyResult
│   ├── optuna_engine.py       # ⚠️ Has S01-specific fields
│   ├── walkforward_engine.py  # ⚠️ References S01 params
│   ├── metrics.py
│   └── export.py
├── strategies/
│   ├── s01_trailing_ma/       # S01 strategy (11 MA types, complex logic)
│   │   ├── config.json        # ✅ No features field
│   │   └── strategy.py        # S01Params dataclass
│   └── s04_stochrsi/          # S04 strategy (simpler)
│       ├── config.json        # ✅ No features field
│       └── strategy.py        # S04Params dataclass
├── server.py                  # ⚠️ Has feature flag scaffold + MA handling
└── index.html                 # ⚠️ Has S01 MA selectors, inline CSS
```

### Target Architecture (After This Fix)

```
Changes:
- ✅ OptimizationConfig: Generic fields only (param_types, param_ranges, fixed_params)
- ✅ Optuna engine: Generate search space from param_types (no MA special-casing)
- ✅ Server: Remove _get_strategy_features(), handle select params generically
- ✅ Frontend: Optimizer form generated from config (like backtest form)
- ✅ CSS: Fully externalized to style.css
- ✅ Validation: Client-side range/step validation before submit
- ✅ Tests: Frontend tests + improved regression report
```

---

## Implementation Plan

### Phase A: Backend Core Cleanup (High Priority)

#### A1. Remove Feature Flag Scaffold from Server
**Estimated Time:** 30 minutes
**Files:** `src/server.py`

**Tasks:**
1. Delete function `_get_strategy_features()` (lines 40-73)
2. Delete function `_normalize_ma_group_name()` (lines 20-37)
3. Find all calls to `_get_strategy_features()` and remove:
   - Line ~1085: `strategy_features = _get_strategy_features(strategy_id)`
   - Line ~1307: `strategy_features = _get_strategy_features(strategy_id)`
4. Remove any MA group validation branches that used `strategy_features`
   - Lines ~1331-1335: MA group validation for trend/trail

**Verification:**
```bash
# Should return no results:
grep -n "_get_strategy_features\|_normalize_ma_group_name\|strategy_features" src/server.py
```

#### A2. Genericize OptimizationConfig
**Estimated Time:** 1 hour
**Files:** `src/core/optuna_engine.py`, `src/server.py`, `src/core/walkforward_engine.py`

**Current Definition (lines 29-53 in optuna_engine.py):**
```python
@dataclass
class OptimizationConfig:
    csv_file: Any
    worker_processes: int
    contract_size: float
    commission_rate: float
    risk_per_trade_pct: float
    atr_period: int  # ⚠️ S01-specific
    enabled_params: Dict[str, bool]
    param_ranges: Dict[str, Tuple[float, float, float]]
    ma_types_trend: List[str]  # ⚠️ S01-specific
    ma_types_trail_long: List[str]  # ⚠️ S01-specific
    ma_types_trail_short: List[str]  # ⚠️ S01-specific
    lock_trail_types: bool  # ⚠️ S01-specific
    fixed_params: Dict[str, Any]
    param_types: Optional[Dict[str, str]] = None
    score_config: Optional[Dict[str, Any]] = None
    strategy_id: str = ""
    warmup_bars: int = 1000
    filter_min_profit: bool = False
    min_profit_threshold: float = 0.0
    optimization_mode: str = "optuna"
```

**Target Definition:**
```python
@dataclass
class OptimizationConfig:
    """Generic optimization configuration for any strategy."""

    # Required fields
    csv_file: Any
    strategy_id: str
    enabled_params: Dict[str, bool]  # {paramName: True/False}
    param_ranges: Dict[str, Tuple[float, float, float]]  # {paramName: (min, max, step)}
    param_types: Dict[str, str]  # {paramName: "int"|"float"|"select"|etc}
    fixed_params: Dict[str, Any]  # {paramName: value}

    # Execution settings
    worker_processes: int = 1
    warmup_bars: int = 1000

    # Strategy-specific settings (values come from fixed_params)
    contract_size: float = 1.0
    commission_rate: float = 0.0005
    risk_per_trade_pct: float = 1.0

    # Optimization control
    filter_min_profit: bool = False
    min_profit_threshold: float = 0.0
    score_config: Optional[Dict[str, Any]] = None
    optimization_mode: str = "optuna"

    # REMOVED: atr_period, ma_types_*, lock_trail_types
    # These are now in fixed_params or derived from param_types
```

**Tasks:**
1. Update `OptimizationConfig` dataclass in `optuna_engine.py`
2. Update all instantiations in `server.py` (lines ~1451-1453)
   - Remove: `ma_types_trend`, `ma_types_trail_long`, `ma_types_trail_short`, `lock_trail_types`, `atr_period`
   - Ensure `param_types` is populated from `_get_parameter_types(strategy_id)`
3. Update all instantiations in `walkforward_engine.py` (lines ~442-462)
4. Update response serialization in `server.py` (lines ~825-827)

**Example Server.py Change (lines 1317-1453):**

**BEFORE:**
```python
ma_types_trend: List[str] = []
ma_types_trail_long: List[str] = []
ma_types_trail_short: List[str] = []

# ... MA selection logic ...

optimization_config = OptimizationConfig(
    # ... other fields ...
    ma_types_trend=[str(ma).upper() for ma in ma_types_trend],
    ma_types_trail_long=[str(ma).upper() for ma in ma_types_trail_long],
    ma_types_trail_short=[str(ma).upper() for ma in ma_types_trail_short],
    lock_trail_types=bool(payload.get("lock_trail_types", False)),
    atr_period=int(payload.get("atr_period", 14)),
    # ...
)
```

**AFTER:**
```python
# No MA-specific handling - all select params handled generically
param_types = _get_parameter_types(strategy_id)

optimization_config = OptimizationConfig(
    # ... other fields ...
    param_types=param_types,
    # MA selections and atr_period now in fixed_params or param_ranges
    # ...
)
```

**Verification:**
```bash
# Should return no results in core modules:
grep -n "ma_types_trend\|ma_types_trail\|lock_trail_types\|atr_period" src/core/optuna_engine.py
grep -n "ma_types_trend\|ma_types_trail\|lock_trail_types" src/core/walkforward_engine.py
```

#### A3. Remove MA Special-Casing from Optuna Engine
**Estimated Time:** 2 hours
**Files:** `src/core/optuna_engine.py`

**Current Issue (lines ~357-410):**
```python
ma_trend_options = [ma.upper() for ma in self.base_config.ma_types_trend]
trail_long_options = [ma.upper() for ma in self.base_config.ma_types_trail_long]
trail_short_options = [ma.upper() for ma in self.base_config.ma_types_trail_short]

for param_name, param_spec in parameters.items():
    # ... numeric handling ...

    # ⚠️ Hardcoded MA logic:
    if param_name == "maType":
        space[param_name] = {"type": "categorical", "choices": ma_trend_options}
    elif param_name == "trailLongType":
        space[param_name] = {"type": "categorical", "choices": trail_long_options}
    # etc...
```

**Target Implementation:**
```python
# Generic select parameter handling
for param_name, param_spec in parameters.items():
    if not isinstance(param_spec, dict):
        continue

    param_type = param_spec.get("type", "float")

    if param_type in ("int", "float"):
        # Numeric parameter
        if param_name in enabled_params and enabled_params[param_name]:
            if param_name in param_ranges:
                min_val, max_val, step_val = param_ranges[param_name]
                space[param_name] = {
                    "type": param_type,
                    "min": min_val,
                    "max": max_val,
                    "step": step_val,
                }
                self.param_type_map[param_name] = param_type

    elif param_type in ("select", "options"):
        # Select parameter (generic - works for MA, RSI mode, etc.)
        options = param_spec.get("options", [])
        if not options:
            continue

        if param_name in enabled_params and enabled_params[param_name]:
            # Get selected options from fixed_params or default to all
            selected_options = fixed_params.get(f"{param_name}_options", options)
            if selected_options:
                space[param_name] = {
                    "type": "categorical",
                    "choices": selected_options,
                }
                self.param_type_map[param_name] = "select"
        else:
            # Not being optimized - use default value
            pass

    elif param_type in ("bool", "boolean"):
        # Boolean parameter
        if param_name in enabled_params and enabled_params[param_name]:
            space[param_name] = {
                "type": "categorical",
                "choices": [True, False],
            }
            self.param_type_map[param_name] = "bool"
```

**Tasks:**
1. Replace lines ~360-410 with generic parameter handling
2. Remove all references to `ma_types_trend`, `ma_types_trail_*`, `lock_trail_types`
3. Update trial suggestion logic (lines ~420-421, 565-568) to use `param_type_map`
4. Handle select parameters via `fixed_params["{paramName}_options"]` pattern

**Lock Trail Logic:**
If S01 needs "lock trail types" functionality, implement it as:
```python
# In fixed_params:
fixed_params["lockTrailTypes"] = True  # User sets this

# In trial suggestion:
if "trailLongType" in space and fixed_params.get("lockTrailTypes"):
    long_type = trial.suggest_categorical("trailLongType", space["trailLongType"]["choices"])
    trial.set_user_attr("trailShortType", long_type)  # Lock short to same
```

**Verification:**
```bash
pytest tests/test_optuna_engine.py -v
# Should pass all tests without MA hardcoding
```

#### A4. Fix Walkforward Engine
**Estimated Time:** 30 minutes
**Files:** `src/core/walkforward_engine.py`

**Current Issue (lines 447-449):**
```python
ma_types_trend=list(self.base_config_template["ma_types_trend"]),
ma_types_trail_long=list(self.base_config_template["ma_types_trail_long"]),
ma_types_trail_short=list(self.base_config_template["ma_types_trail_short"]),
```

**Tasks:**
1. Remove these three lines
2. Ensure `param_types` is passed from base config template
3. Update lines ~585-594 and ~1050 that format parameter names

**Verification:**
```bash
grep -n "ma_types_trend\|ma_types_trail" src/core/walkforward_engine.py
# Should return no results
```

---

### Phase B: Frontend Optimizer Generalization (High Priority)

#### B1. Remove Hardcoded S01 MA Selectors
**Estimated Time:** 2 hours
**Files:** `src/index.html`

**Current State:**
- Lines ~419-537: Hardcoded MA checkbox selectors for `trailLong` and `trailShort`
- Similar hardcoded selectors exist for Trend MA (earlier in file)
- Backtest form already has generic `createFormField()` that handles select parameters

**Target State:**
- Optimizer form uses same `createFormField()` logic as backtest form
- Select parameters render as multi-select checkboxes or dropdowns
- No S01-specific HTML

**Implementation:**

1. **Identify hardcoded MA selector blocks:**
   ```bash
   grep -n "ma-selector\|data-group=\"trail" src/index.html
   ```

2. **Replace with dynamic generation:**
   - Optimizer form already has `generateOptimizerForm()` function (line 1019)
   - Update it to handle select-type parameters like backtest form does
   - Reuse `createFormField()` or create `createOptimizerField()` variant

3. **Example approach:**
   ```javascript
   function generateOptimizerForm(config) {
     const container = document.getElementById('optimizerParamsContainer');
     container.innerHTML = '';

     const params = config.parameters || {};

     // Group optimizable parameters
     const groups = {};
     for (const [paramName, paramDef] of Object.entries(params)) {
       if (!paramDef.optimize || !paramDef.optimize.enabled) {
         continue;
       }

       const group = paramDef.group || 'Other';
       if (!groups[group]) groups[group] = [];
       groups[group].push({ name: paramName, def: paramDef });
     }

     // Render each group
     for (const [groupName, groupParams] of Object.entries(groups)) {
       const groupDiv = createOptimizerGroup(groupName);

       groupParams.forEach(({ name, def }) => {
         const row = createOptimizerRow(name, def);
         groupDiv.appendChild(row);
       });

       container.appendChild(groupDiv);
     }
   }

   function createOptimizerRow(paramName, paramDef) {
     const row = document.createElement('div');
     row.className = 'opt-row';

     // Checkbox to enable optimization
     const checkbox = document.createElement('input');
     checkbox.type = 'checkbox';
     checkbox.id = `opt-${paramName}`;
     checkbox.checked = paramDef.optimize.enabled;

     const label = document.createElement('label');
     label.textContent = paramDef.label || paramName;
     label.htmlFor = checkbox.id;

     row.appendChild(checkbox);
     row.appendChild(label);

     // Type-specific controls
     const paramType = paramDef.type;

     if (paramType === 'int' || paramType === 'float') {
       // Numeric: from, to, step
       const controls = createNumericOptimizerControls(paramName, paramDef);
       row.appendChild(controls);
     } else if (paramType === 'select' || paramType === 'options') {
       // Select: multi-choice checkboxes
       const controls = createSelectOptimizerControls(paramName, paramDef);
       row.appendChild(controls);
     }

     return row;
   }

   function createSelectOptimizerControls(paramName, paramDef) {
     const container = document.createElement('div');
     container.className = 'opt-select-controls';

     const options = paramDef.options || [];

     // "ALL" checkbox
     const allCheckbox = document.createElement('input');
     allCheckbox.type = 'checkbox';
     allCheckbox.id = `opt-${paramName}-all`;
     allCheckbox.dataset.paramName = paramName;

     const allLabel = document.createElement('label');
     allLabel.textContent = 'ALL';
     allLabel.htmlFor = allCheckbox.id;

     container.appendChild(allCheckbox);
     container.appendChild(allLabel);

     // Individual option checkboxes
     options.forEach(option => {
       const cb = document.createElement('input');
       cb.type = 'checkbox';
       cb.id = `opt-${paramName}-${option}`;
       cb.dataset.paramName = paramName;
       cb.dataset.option = option;
       cb.checked = true;  // Default all selected

       const lbl = document.createElement('label');
       lbl.textContent = option;
       lbl.htmlFor = cb.id;

       container.appendChild(cb);
       container.appendChild(lbl);
     });

     // Bind ALL checkbox logic
     allCheckbox.addEventListener('change', () => {
       const allChecked = allCheckbox.checked;
       options.forEach(option => {
         const cb = document.getElementById(`opt-${paramName}-${option}`);
         if (cb) cb.checked = allChecked;
       });
     });

     return container;
   }
   ```

4. **Update payload collection (lines 2930-2947):**
   ```javascript
   // BEFORE (hardcoded):
   const maTypesTrend = [];
   const maTypesTrailLong = [];
   const maTypesTrailShort = [];

   // AFTER (generic):
   // Collect selected options for each select-type parameter
   Object.entries(paramsDef).forEach(([name, def]) => {
     if (def.type === 'select' || def.type === 'options') {
       const checkbox = document.getElementById(`opt-${name}`);
       if (checkbox && checkbox.checked) {
         // Get selected options
         const options = def.options || [];
         const selectedOptions = [];
         options.forEach(option => {
           const optCb = document.getElementById(`opt-${name}-${option}`);
           if (optCb && optCb.checked) {
             selectedOptions.push(option);
           }
         });

         if (selectedOptions.length > 0) {
           // Store in fixed_params as "{paramName}_options"
           fixedParams[`${name}_options`] = selectedOptions;
         }
       } else {
         // Not optimizing - use current backtest value
         fixedParams[name] = getBacktestParamValue(name, def, dynamicParams);
       }
     }
   });
   ```

**Verification:**
1. Start server: `python src/server.py`
2. Open browser: `http://localhost:8000`
3. Select S01 strategy → Optimizer tab should show all S01 parameters dynamically
4. Select S04 strategy → Optimizer tab should show S04 parameters (no MA selectors)
5. Check browser console for errors

#### B2. Add Client-Side Validation
**Estimated Time:** 1 hour
**Files:** `src/index.html`

**Current Issue:**
No validation before submitting optimizer form. Users can enter:
- `from >= to` (invalid range)
- Negative step
- Values outside config min/max

**Implementation:**

1. **Add validation function:**
   ```javascript
   function validateOptimizerForm(config) {
     const errors = [];
     const params = config.parameters || {};

     Object.entries(params).forEach(([paramName, paramDef]) => {
       if (!paramDef.optimize || !paramDef.optimize.enabled) {
         return;
       }

       const checkbox = document.getElementById(`opt-${paramName}`);
       if (!checkbox || !checkbox.checked) {
         return;
       }

       if (paramDef.type === 'int' || paramDef.type === 'float') {
         const fromInput = document.getElementById(`opt-${paramName}-from`);
         const toInput = document.getElementById(`opt-${paramName}-to`);
         const stepInput = document.getElementById(`opt-${paramName}-step`);

         if (fromInput && toInput && stepInput) {
           const fromVal = Number(fromInput.value);
           const toVal = Number(toInput.value);
           const stepVal = Number(stepInput.value);

           // Check finite
           if (!Number.isFinite(fromVal) || !Number.isFinite(toVal) || !Number.isFinite(stepVal)) {
             errors.push(`${paramDef.label || paramName}: All values must be numbers`);
             return;
           }

           // Check from < to
           if (fromVal >= toVal) {
             errors.push(`${paramDef.label || paramName}: From must be less than To`);
           }

           // Check positive step
           if (stepVal <= 0) {
             errors.push(`${paramDef.label || paramName}: Step must be positive`);
           }

           // Check config bounds
           const configMin = paramDef.optimize.min !== undefined ? paramDef.optimize.min : paramDef.min;
           const configMax = paramDef.optimize.max !== undefined ? paramDef.optimize.max : paramDef.max;

           if (configMin !== undefined && fromVal < configMin) {
             errors.push(`${paramDef.label || paramName}: From (${fromVal}) below config minimum (${configMin})`);
           }
           if (configMax !== undefined && toVal > configMax) {
             errors.push(`${paramDef.label || paramName}: To (${toVal}) above config maximum (${configMax})`);
           }
         }
       } else if (paramDef.type === 'select' || paramDef.type === 'options') {
         // Check at least one option selected
         const options = paramDef.options || [];
         const hasSelection = options.some(option => {
           const cb = document.getElementById(`opt-${paramName}-${option}`);
           return cb && cb.checked;
         });

         if (!hasSelection) {
           errors.push(`${paramDef.label || paramName}: At least one option must be selected`);
         }
       }
     });

     return errors;
   }
   ```

2. **Call validation before submit:**
   ```javascript
   // In optimization submit handler
   async function handleOptimizationSubmit() {
     const errors = validateOptimizerForm(currentStrategyConfig);

     if (errors.length > 0) {
       alert('Validation errors:\n\n' + errors.join('\n'));
       return;
     }

     // Proceed with optimization...
   }
   ```

**Verification:**
1. Try to submit optimizer with `from=50, to=10` → Should show error
2. Try to submit with `step=-1` → Should show error
3. Try to submit with all MA options unchecked → Should show error

#### B3. Extract Remaining Inline CSS
**Estimated Time:** 30 minutes
**Files:** `src/index.html`, `src/static/css/style.css`

**Current State:**
- Line 7: `<link rel="stylesheet" href="/static/css/style.css" />`
- Line 8: `<style>` tag with inline CSS

**Tasks:**
1. Copy all CSS from `<style>` tag (lines ~8-48) to `style.css`
2. Delete `<style>` tag from `index.html`
3. Verify no style regressions

**Verification:**
```bash
grep -n "<style>" src/index.html
# Should return no results
```

---

### Phase C: Testing & Documentation (Medium Priority)

#### C1. Add Frontend Tests
**Estimated Time:** 3 hours
**Files:** `tests/frontend/` (new), `package.json`, `.github/workflows/test.yml`

**Rationale:**
No frontend tests exist. UI logic is complex and prone to regressions during refactors.

**Technology Choice:**
- **Option 1:** Jest + jsdom (Node-based, fast)
- **Option 2:** Playwright (browser-based, slower but more realistic)
- **Recommended:** Jest for unit tests, Playwright for E2E

**Setup (Jest):**

1. **Install dependencies:**
   ```bash
   npm init -y  # If no package.json exists
   npm install --save-dev jest jsdom
   ```

2. **Create test structure:**
   ```
   tests/
   ├── frontend/
   │   ├── test_form_generation.js
   │   ├── test_validation.js
   │   └── test_optimizer.js
   └── ...
   ```

3. **Example test file (`tests/frontend/test_form_generation.js`):**
   ```javascript
   /**
    * @jest-environment jsdom
    */

   const fs = require('fs');
   const path = require('path');

   // Load HTML
   const html = fs.readFileSync(
     path.resolve(__dirname, '../../src/index.html'),
     'utf8'
   );

   describe('Form Generation', () => {
     beforeEach(() => {
       document.documentElement.innerHTML = html;

       // Mock window.currentStrategyConfig
       window.currentStrategyConfig = {
         id: 's04_stochrsi',
         name: 'S04 StochRSI',
         parameters: {
           rsiLen: {
             type: 'int',
             label: 'RSI Length',
             default: 14,
             min: 2,
             max: 100,
             optimize: { enabled: true, min: 10, max: 30, step: 2 }
           },
           obLevel: {
             type: 'float',
             label: 'Overbought Level',
             default: 80.0,
             min: 50.0,
             max: 100.0,
             optimize: { enabled: true, min: 70, max: 90, step: 5 }
           }
         }
       };
     });

     test('createFormField renders int parameter correctly', () => {
       const paramDef = window.currentStrategyConfig.parameters.rsiLen;
       const field = createFormField('rsiLen', paramDef, 'backtest');

       expect(field).toBeTruthy();
       expect(field.querySelector('label').textContent).toBe('RSI Length');

       const input = field.querySelector('input[type="number"]');
       expect(input).toBeTruthy();
       expect(input.min).toBe('2');
       expect(input.max).toBe('100');
       expect(input.value).toBe('14');
     });

     test('generateOptimizerForm creates optimizer controls', () => {
       generateOptimizerForm(window.currentStrategyConfig);

       const container = document.getElementById('optimizerParamsContainer');
       expect(container.children.length).toBeGreaterThan(0);

       // Check for rsiLen optimizer controls
       const rsiCheckbox = document.getElementById('opt-rsiLen');
       expect(rsiCheckbox).toBeTruthy();
       expect(rsiCheckbox.type).toBe('checkbox');

       const rsiFrom = document.getElementById('opt-rsiLen-from');
       expect(rsiFrom).toBeTruthy();
       expect(rsiFrom.value).toBe('10');  // optimize.min
     });

     test('validation catches from >= to', () => {
       generateOptimizerForm(window.currentStrategyConfig);

       // Set invalid range
       document.getElementById('opt-rsiLen').checked = true;
       document.getElementById('opt-rsiLen-from').value = '50';
       document.getElementById('opt-rsiLen-to').value = '10';

       const errors = validateOptimizerForm(window.currentStrategyConfig);
       expect(errors.length).toBeGreaterThan(0);
       expect(errors[0]).toContain('From must be less than To');
     });

     test('validation catches negative step', () => {
       generateOptimizerForm(window.currentStrategyConfig);

       document.getElementById('opt-rsiLen').checked = true;
       document.getElementById('opt-rsiLen-step').value = '-1';

       const errors = validateOptimizerForm(window.currentStrategyConfig);
       expect(errors.some(e => e.includes('Step must be positive'))).toBe(true);
     });

     test('select parameter renders with options', () => {
       window.currentStrategyConfig.parameters.maType = {
         type: 'select',
         label: 'MA Type',
         default: 'EMA',
         options: ['EMA', 'SMA', 'HMA'],
         optimize: { enabled: true }
       };

       generateOptimizerForm(window.currentStrategyConfig);

       // Check for option checkboxes
       expect(document.getElementById('opt-maType-EMA')).toBeTruthy();
       expect(document.getElementById('opt-maType-SMA')).toBeTruthy();
       expect(document.getElementById('opt-maType-HMA')).toBeTruthy();
     });
   });
   ```

4. **Update `package.json`:**
   ```json
   {
     "scripts": {
       "test": "jest",
       "test:watch": "jest --watch"
     }
   }
   ```

5. **Run tests:**
   ```bash
   npm test
   ```

**Coverage Goals:**
- ✅ `createFormField()` for int, float, select, bool
- ✅ `generateOptimizerForm()` creates correct controls
- ✅ Validation catches invalid ranges
- ✅ Validation checks config bounds
- ✅ Select parameter "ALL" checkbox logic
- ✅ Payload collection from optimizer form

**Verification:**
```bash
npm test
# Should show 15+ tests passing
```

#### C2. Improve Regression Test Report
**Estimated Time:** 30 minutes
**Files:** `tests/REGRESSION_TEST_REPORT.md`, `pytest.ini`, `.github/workflows/test.yml`

**Current Report (7 lines):**
```markdown
# Regression Test Report (Phase 9-5-4)

- **Command:** `pytest -v`
- **Dataset:** `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
- **Result:** All tests passed (86 total).
- **Notes:** Naming consistency suite enforces camelCase parameters and config/dataclass alignment for S01 and S04.
```

**Target Report Structure:**
```markdown
# Regression Test Report

**Date:** 2025-12-10
**Phase:** 9-5-4 Post-Fix
**Command:** `pytest -v --durations=10`
**Dataset:** `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
**Total Tests:** 92
**Result:** ✅ All Passed

---

## Test Suite Breakdown

| Suite | Tests | Duration | Status |
|-------|-------|----------|--------|
| test_sanity.py | 9 | 0.12s | ✅ PASS |
| test_regression_s01.py | 12 | 3.45s | ✅ PASS |
| test_s01_migration.py | 8 | 2.89s | ✅ PASS |
| test_s04_stochrsi.py | 6 | 1.23s | ✅ PASS |
| test_backtest_engine.py | 15 | 1.67s | ✅ PASS |
| test_optuna_engine.py | 18 | 4.12s | ✅ PASS |
| test_walkforward_engine.py | 7 | 2.34s | ✅ PASS |
| test_indicators.py | 11 | 0.89s | ✅ PASS |
| test_naming_consistency.py | 6 | 0.05s | ✅ PASS |
| **Total** | **92** | **16.76s** | **✅** |

---

## Critical Tests

### S01 Regression Baseline
- ✅ `test_s01_matches_baseline_metrics` - Net profit, drawdown, trades match
- ✅ `test_s01_equity_curve_matches` - Equity curve within 0.01% tolerance
- ✅ `test_s01_trade_entries_exits_match` - Trade timing exact match

### S04 Validation
- ✅ `test_s04_basic_backtest` - Strategy runs without errors
- ✅ `test_s04_optimization` - Optuna optimization completes
- ✅ `test_s04_metrics_reasonable` - Metrics within expected ranges

### Naming Consistency
- ✅ `test_s01_params_use_camelCase` - All S01 params are camelCase
- ✅ `test_s04_params_use_camelCase` - All S04 params are camelCase
- ✅ `test_no_feature_flags` - No strategies use deprecated features field

---

## Dataset Details

**File:** `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
**Timeframe:** 15-minute OHLCV
**Date Range:** 2025-05-01 to 2025-11-20
**Total Bars:** 18,432
**Warmup Bars:** 1000
**Tradeable Bars:** 17,432

---

## Performance Comparison

| Phase | Total Tests | Duration | Avg per Test |
|-------|-------------|----------|--------------|
| 9-5-3 | 86 | 15.23s | 0.177s |
| 9-5-4 | 92 | 16.76s | 0.182s |
| 9-5-4 Post-Fix | 92 | 16.45s | 0.179s |

*Note: Duration variance <5% is expected due to system load.*

---

## Test Coverage Notes

- **Core engines:** All public methods covered
- **Strategies:** S01 and S04 have full coverage (backtest, optimize, metrics)
- **Indicators:** All 11 MA types + RSI + StochRSI tested
- **Frontend:** Basic Jest tests added (form generation, validation)
- **Edge cases:** Empty data, missing params, invalid ranges

---

## CI/CD Integration

Tests run automatically on:
- ✅ Every commit to `main` branch
- ✅ All pull requests
- ✅ Nightly builds (full suite + performance benchmarks)

**GitHub Actions:** `.github/workflows/test.yml`

---

## Next Steps

- [ ] Add performance benchmarks (track optimization speed over time)
- [ ] Add frontend E2E tests with Playwright
- [ ] Expand S04 coverage (add edge cases)
- [ ] Add WFA integration tests
```

**Implementation:**

1. **Generate detailed report:**
   ```bash
   pytest -v --durations=10 --tb=short > test_output.txt 2>&1
   ```

2. **Parse output and update report:**
   - Count tests per file
   - Extract durations
   - Add dataset details
   - Include comparison table

3. **Automate in CI:**
   ```yaml
   # .github/workflows/test.yml
   - name: Run Tests with Coverage
     run: |
       pytest -v --durations=10 --cov=src --cov-report=term-missing > test_output.txt

   - name: Generate Report
     run: |
       python tools/generate_test_report.py > tests/REGRESSION_TEST_REPORT.md
   ```

**Verification:**
```bash
cat tests/REGRESSION_TEST_REPORT.md
# Should show expanded report with all sections
```

---

### Phase D: Integration & Validation (Critical)

#### D1. End-to-End Testing
**Estimated Time:** 2 hours

**Test Cases:**

1. **S01 Strategy (Full Flow):**
   ```bash
   # 1. Start server
   cd src && python server.py

   # 2. Open browser: http://localhost:8000

   # 3. Select S01 strategy
   - Verify backtest form loads S01 parameters
   - Verify optimizer form loads S01 parameters (no hardcoded HTML)
   - Check for: maType, maLength, trailLongType, trailShortType, etc.

   # 4. Run backtest
   - Set parameters
   - Submit
   - Verify results display

   # 5. Run optimization
   - Enable optimizer for: maLength, closeCountLong, stopLongX
   - Set ranges: maLength (30-70, step 10)
   - Submit
   - Verify optimization runs
   - Verify CSV export includes results

   # 6. Check browser console
   - Should have no errors
   ```

2. **S04 Strategy (Full Flow):**
   ```bash
   # Same steps but with S04
   # Optimizer should show: rsiLen, stochLen, obLevel, osLevel, confirmBars
   # Should NOT show any MA selectors (S01-specific)
   ```

3. **Strategy Switching:**
   ```bash
   # 1. Load S01 → Optimizer shows S01 params
   # 2. Switch to S04 → Optimizer updates to S04 params
   # 3. Switch back to S01 → Optimizer shows S01 params again
   # 4. No console errors during switching
   ```

4. **Validation Edge Cases:**
   ```bash
   # Try to submit optimizer with:
   - from >= to → Should show error
   - step = 0 → Should show error
   - step < 0 → Should show error
   - from below config min → Should show error
   - to above config max → Should show error
   - All select options unchecked → Should show error
   ```

5. **Backend API Testing:**
   ```bash
   # Test /api/optimize endpoint directly
   curl -X POST http://localhost:8000/api/optimize \
     -H "Content-Type: application/json" \
     -d '{
       "strategy": "s04_stochrsi",
       "enabled_params": {"rsiLen": true},
       "param_ranges": {"rsiLen": [10, 30, 5]},
       "param_types": {"rsiLen": "int"},
       "fixed_params": {"stochLen": 14, "obLevel": 80.0},
       "optuna_n_trials": 10,
       "optuna_target": "score"
     }'

   # Should return optimization results without errors
   ```

**Acceptance Criteria:**
- ✅ S01 optimizer works with all parameters
- ✅ S04 optimizer works with all parameters
- ✅ No S01-specific UI elements appear for S04
- ✅ Validation prevents invalid submissions
- ✅ No browser console errors
- ✅ No backend errors in logs
- ✅ CSV exports contain correct parameters

#### D2. Regression Test Suite
**Estimated Time:** 1 hour

**Run Full Test Suite:**
```bash
# Backend tests
pytest -v --durations=10

# Frontend tests (if implemented)
npm test

# Integration tests
pytest tests/integration/ -v
```

**Expected Results:**
- ✅ All 92+ backend tests pass
- ✅ All 15+ frontend tests pass (if implemented)
- ✅ No test failures or warnings
- ✅ Performance within 5% of baseline

**Regression Checks:**
```python
# tests/test_regression_s01.py
def test_s01_optimizer_still_works():
    """Verify S01 optimizer works after removing hardcoded logic."""
    config = OptimizationConfig(
        csv_file=load_test_csv(),
        strategy_id="s01_trailing_ma",
        enabled_params={"maLength": True, "closeCountLong": True},
        param_ranges={
            "maLength": (30, 70, 10),
            "closeCountLong": (1, 5, 1),
        },
        param_types={"maLength": "int", "closeCountLong": "int"},
        fixed_params={
            "maType": "HMA",
            "trailLongType": "EMA",
            # ... other params
        },
        worker_processes=1,
        warmup_bars=1000,
    )

    results = run_optimization(config)

    assert len(results) > 0
    assert all(r.total_trades > 0 for r in results)
    assert all(r.net_profit_pct != 0 for r in results)

def test_s04_optimizer_works():
    """Verify S04 optimizer works with generic implementation."""
    config = OptimizationConfig(
        csv_file=load_test_csv(),
        strategy_id="s04_stochrsi",
        enabled_params={"rsiLen": True},
        param_ranges={"rsiLen": (10, 30, 5)},
        param_types={"rsiLen": "int"},
        fixed_params={"stochLen": 14, "obLevel": 80.0, "osLevel": 20.0},
        worker_processes=1,
        warmup_bars=1000,
    )

    results = run_optimization(config)

    assert len(results) > 0
```

---

## Implementation Checklist

Use this checklist to track progress:

### Phase A: Backend Core Cleanup
- [ ] A1. Remove `_get_strategy_features()` from server.py
- [ ] A1. Remove `_normalize_ma_group_name()` from server.py
- [ ] A1. Remove all `strategy_features` usage
- [ ] A2. Update `OptimizationConfig` dataclass
- [ ] A2. Remove S01-specific fields
- [ ] A2. Update server.py instantiations
- [ ] A2. Update walkforward_engine.py instantiations
- [ ] A3. Genericize parameter space generation in optuna_engine.py
- [ ] A3. Remove MA special-casing
- [ ] A3. Update trial suggestion logic
- [ ] A4. Remove MA references from walkforward_engine.py
- [ ] A4. Verify all backend changes with grep

### Phase B: Frontend Optimizer Generalization
- [ ] B1. Remove hardcoded MA selector HTML
- [ ] B1. Update `generateOptimizerForm()` to handle all param types
- [ ] B1. Create `createSelectOptimizerControls()` function
- [ ] B1. Update payload collection to handle select params generically
- [ ] B1. Remove hardcoded `maTypesTrend`, `maTypesTrailLong`, etc.
- [ ] B2. Add `validateOptimizerForm()` function
- [ ] B2. Check from < to
- [ ] B2. Check positive step
- [ ] B2. Check config bounds
- [ ] B2. Hook validation into submit handler
- [ ] B3. Move remaining inline CSS to style.css
- [ ] B3. Delete `<style>` tag from index.html
- [ ] B3. Verify no style regressions

### Phase C: Testing & Documentation
- [ ] C1. Set up Jest + jsdom
- [ ] C1. Create `tests/frontend/` directory
- [ ] C1. Write tests for `createFormField()`
- [ ] C1. Write tests for `generateOptimizerForm()`
- [ ] C1. Write tests for validation logic
- [ ] C1. Write tests for select parameter rendering
- [ ] C1. Run `npm test` and verify 15+ tests pass
- [ ] C2. Generate detailed test breakdown
- [ ] C2. Add dataset details to report
- [ ] C2. Add performance comparison table
- [ ] C2. Update `REGRESSION_TEST_REPORT.md`

### Phase D: Integration & Validation
- [ ] D1. Test S01 full flow (backtest + optimize)
- [ ] D1. Test S04 full flow (backtest + optimize)
- [ ] D1. Test strategy switching
- [ ] D1. Test validation edge cases
- [ ] D1. Test backend API directly with curl
- [ ] D2. Run full backend test suite (`pytest -v`)
- [ ] D2. Run frontend tests (`npm test`)
- [ ] D2. Add S01/S04 optimizer regression tests
- [ ] D2. Verify all tests pass

---

## Testing Strategy

### Unit Tests (Backend)
```bash
# Test individual modules
pytest tests/test_optuna_engine.py -v
pytest tests/test_walkforward_engine.py -v
pytest tests/test_server.py -v  # If exists

# Expected:
# - OptimizationConfig instantiation works without MA fields
# - Parameter space generation handles int/float/select/bool generically
# - Trial suggestion works for all param types
```

### Unit Tests (Frontend)
```bash
npm test

# Expected:
# - Form generation creates correct controls for each param type
# - Validation catches all invalid cases
# - Select parameter "ALL" logic works
# - Payload collection includes all param types
```

### Integration Tests
```bash
# Test end-to-end flows
pytest tests/test_integration_optimizer.py -v

# Expected:
# - S01 optimization completes successfully
# - S04 optimization completes successfully
# - CSV exports contain correct columns
# - No hardcoded assumptions break non-S01 strategies
```

### Manual Testing
1. **Browser Console Audit:**
   - Open DevTools → Console
   - Load S01 → Check for errors
   - Load S04 → Check for errors
   - Submit optimizer → Check for errors

2. **Network Tab Audit:**
   - Watch API requests
   - Verify payload structure matches expectations
   - Check response status codes

3. **Visual Regression:**
   - Compare S01 UI before/after
   - Verify all controls still visible
   - Verify styling unchanged

---

## Common Pitfalls & Solutions

### Pitfall 1: Select Parameters Not Rendering
**Symptom:** MA types or other select params don't show in optimizer
**Cause:** Missing `options` array in config.json or incorrect type
**Solution:**
```json
{
  "maType": {
    "type": "select",  // Must be "select" or "options"
    "options": ["EMA", "SMA", "HMA"],  // Must be non-empty array
    "optimize": {
      "enabled": true
    }
  }
}
```

### Pitfall 2: Validation Not Triggering
**Symptom:** Invalid ranges submitted without error
**Cause:** Validation function not called before submit
**Solution:**
```javascript
// In submit handler, BEFORE building payload:
const errors = validateOptimizerForm(currentStrategyConfig);
if (errors.length > 0) {
  alert('Validation errors:\n\n' + errors.join('\n'));
  return;  // Stop submission
}
```

### Pitfall 3: Optimizer Payload Missing Select Options
**Symptom:** Backend receives empty lists for select params
**Cause:** Frontend not collecting selected options
**Solution:**
```javascript
// When collecting optimizer payload:
if (paramDef.type === 'select') {
  const selectedOptions = [];
  paramDef.options.forEach(option => {
    const cb = document.getElementById(`opt-${paramName}-${option}`);
    if (cb && cb.checked) {
      selectedOptions.push(option);
    }
  });

  if (selectedOptions.length > 0) {
    fixedParams[`${paramName}_options`] = selectedOptions;
  }
}
```

### Pitfall 4: OptimizationConfig Instantiation Fails
**Symptom:** `TypeError: __init__() got unexpected keyword argument 'ma_types_trend'`
**Cause:** Old code still passing removed fields
**Solution:**
```python
# BEFORE:
config = OptimizationConfig(
    ma_types_trend=["EMA", "SMA"],  # ❌ Field removed
    # ...
)

# AFTER:
config = OptimizationConfig(
    param_types={"maType": "select"},  # ✅ Generic
    fixed_params={"maType_options": ["EMA", "SMA"]},  # ✅ Options in fixed_params
    # ...
)
```

### Pitfall 5: Tests Fail After Changes
**Symptom:** Tests that passed before now fail
**Cause:** Test fixtures still use old OptimizationConfig fields
**Solution:**
```python
# Update all test fixtures in tests/conftest.py or individual test files
@pytest.fixture
def optimization_config():
    return OptimizationConfig(
        csv_file=io.BytesIO(b"..."),
        strategy_id="s01_trailing_ma",
        enabled_params={"maLength": True},
        param_ranges={"maLength": (30, 70, 10)},
        param_types={"maLength": "int"},  # ✅ Required now
        fixed_params={"maType": "HMA"},  # ✅ Non-optimized params
        # ❌ Remove: ma_types_trend, ma_types_trail_*, lock_trail_types, atr_period
    )
```

---

## Verification Commands

After completing all phases, run these commands to verify success:

### 1. Code Audit
```bash
# Should return NO results (S01-specific code removed):
grep -r "ma_types_trend\|ma_types_trail\|lock_trail_types" src/core/
grep -r "_get_strategy_features\|_normalize_ma_group_name" src/server.py
grep -r "atr_period" src/core/optuna_engine.py | grep -v "fixed_params"

# Should return NO results (inline styles removed):
grep -n "<style>" src/index.html

# Should return results ONLY in test files (feature flags tested as absent):
grep -r "features.*ma_groups\|requires_ma_selection" src/
```

### 2. Test Suite
```bash
# All backend tests should pass:
pytest -v --tb=short
# Expected: 92+ tests, 0 failures

# All frontend tests should pass:
npm test
# Expected: 15+ tests, 0 failures
```

### 3. Manual Browser Test
```bash
# 1. Start server
cd src && python server.py

# 2. Open http://localhost:8000

# 3. Test S01
- Select "S01 Trailing MA"
- Go to Optimizer tab
- Verify all S01 parameters appear (maType, trailLongType, etc.)
- Enable optimization for maLength
- Set range 30-70, step 10
- Submit
- Verify optimization runs

# 4. Test S04
- Select "S04 StochRSI"
- Go to Optimizer tab
- Verify S04 parameters appear (rsiLen, stochLen, etc.)
- Verify NO MA selectors appear
- Enable optimization for rsiLen
- Set range 10-30, step 5
- Submit
- Verify optimization runs

# 5. Check console
- Open DevTools
- Should have ZERO errors
```

### 4. API Test
```bash
# Test optimizer endpoint with S04 (non-S01 strategy)
curl -X POST http://localhost:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "s04_stochrsi",
    "csv_path": "data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv",
    "enabled_params": {"rsiLen": true},
    "param_ranges": {"rsiLen": [10, 30, 5]},
    "param_types": {"rsiLen": "int"},
    "fixed_params": {
      "stochLen": 14,
      "obLevel": 80.0,
      "osLevel": 20.0,
      "extLookback": 3,
      "confirmBars": 1
    },
    "optuna_n_trials": 5,
    "optuna_target": "score"
  }'

# Expected: HTTP 200, JSON response with 5 optimization results
```

---

## Success Criteria

All of the following must be true:

### Backend
- ✅ `grep` commands return no S01-specific code in core modules
- ✅ `OptimizationConfig` has no MA-specific fields
- ✅ `optuna_engine.py` generates search space generically
- ✅ `walkforward_engine.py` has no MA references
- ✅ `server.py` has no `_get_strategy_features()`

### Frontend
- ✅ Optimizer form generated dynamically for S01 and S04
- ✅ No hardcoded MA selector HTML
- ✅ Validation prevents invalid submissions
- ✅ No inline CSS in `index.html`
- ✅ Browser console has zero errors

### Testing
- ✅ All 92+ backend tests pass
- ✅ All 15+ frontend tests pass
- ✅ S01 optimizer works end-to-end
- ✅ S04 optimizer works end-to-end
- ✅ Regression test report expanded (20+ lines)

### Documentation
- ✅ `REGRESSION_TEST_REPORT.md` updated with detailed breakdown
- ✅ All code changes documented in commit messages
- ✅ No TODO comments left in code

---

## Rollback Plan

If issues arise during implementation:

1. **Commit after each phase:**
   ```bash
   git add -A
   git commit -m "Phase A1: Remove feature flag scaffold"
   git tag phase-a1-complete
   ```

2. **If phase fails, rollback:**
   ```bash
   git reset --hard phase-a1-complete
   ```

3. **Keep old code commented during migration:**
   ```python
   # OLD (S01-specific):
   # ma_types_trend = [ma.upper() for ma in config.ma_types_trend]

   # NEW (generic):
   if param_type == "select":
       options = param_def.get("options", [])
   ```

4. **Run tests after each change:**
   ```bash
   pytest tests/test_optuna_engine.py -v
   # Verify tests still pass before proceeding
   ```

---

## Estimated Timeline

| Phase | Tasks | Time | Complexity |
|-------|-------|------|------------|
| **A1** | Remove feature flags | 0.5h | 🟢 Low |
| **A2** | Genericize OptimizationConfig | 1.0h | 🟡 Medium |
| **A3** | Remove MA special-casing | 2.0h | 🔴 High |
| **A4** | Fix walkforward engine | 0.5h | 🟢 Low |
| **B1** | Generalize optimizer UI | 2.0h | 🔴 High |
| **B2** | Add validation | 1.0h | 🟡 Medium |
| **B3** | Extract CSS | 0.5h | 🟢 Low |
| **C1** | Frontend tests | 3.0h | 🔴 High |
| **C2** | Improve regression report | 0.5h | 🟢 Low |
| **D1** | End-to-end testing | 2.0h | 🟡 Medium |
| **D2** | Regression suite | 1.0h | 🟡 Medium |
| **Total** | | **14.0h** | |

**Optimistic:** 12 hours (experienced developer, no blockers)
**Realistic:** 14 hours (includes debugging and test fixes)
**Pessimistic:** 18 hours (includes unforeseen issues and refactoring)

---

## Final Notes

### Architecture Philosophy
This refactor completes the migration to a fully config-driven architecture. After this fix:
- **Core modules** are strategy-agnostic and work with `Dict[str, Any]`
- **Strategies** own their typed params and config.json
- **UI** renders dynamically from config.json
- **No hardcoded assumptions** about specific strategies

### Future-Proofing
Adding a new strategy (e.g., S05 Bollinger Bands) should require:
1. Create `src/strategies/s05_bollinger/`
2. Add `config.json` with parameters
3. Implement `strategy.py` with `S05Params` dataclass
4. **Zero changes to core, server, or UI**

The optimizer, backtest form, CSV export, and metrics calculation should "just work" because they derive everything from config.json.

### Maintenance
After this fix, the codebase is significantly easier to maintain:
- Fewer lines of code (remove ~300 lines of S01-specific logic)
- Clearer separation of concerns
- Better testability (generic code is easier to test)
- Easier to onboard new developers (less cognitive load)

---

## Contact & Support

If you encounter issues during implementation:

1. **Check this document** for pitfalls and solutions
2. **Run verification commands** to diagnose the problem
3. **Check test output** for specific error messages
4. **Review git history** to see what changed

**Document Version:** 1.0
**Last Updated:** 2025-12-10
**Prepared for:** GPT 5.1 Codex
**Review Status:** Ready for Implementation

---

END OF DOCUMENT
