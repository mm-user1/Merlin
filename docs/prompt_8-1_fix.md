# Phase 8.1: Critical Bug Fixes - Post Phase 8 Issues

**Phase:** 8.1 (Hotfix after Phase 8 completion)
**Complexity:** 🟢 LOW-MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 3-5 hours
**Priority:** 🔴 CRITICAL - PRODUCTION BLOCKERS
**Status:** Ready for Execution

---

## Table of Contents

1. [Context and Background](#context-and-background)
2. [Issues Summary](#issues-summary)
3. [Issue 1: Error Popup When Loading Strategy](#issue-1-error-popup-when-loading-strategy)
4. [Issue 2: Missing MA Type Checkboxes](#issue-2-missing-ma-type-checkboxes)
5. [Issue 3: S04 Optimization Producing Identical Results](#issue-3-s04-optimization-producing-identical-results)
6. [Implementation Guide](#implementation-guide)
7. [Testing Requirements](#testing-requirements)
8. [Success Criteria](#success-criteria)

---

## Context and Background

### Project State

This is a cryptocurrency/forex trading strategy backtesting and optimization platform. **Phase 8** was recently completed, which:

- ✅ Extracted all CSS from `index.html` to `src/static/css/style.css`
- ✅ Replaced hardcoded optimizer HTML with dynamic generation from strategy `config.json`
- ✅ Made optimizer parameters load dynamically for any strategy
- ✅ 76 tests passing

### Current Branch

```
Branch: codex/implement-phase-8-of-project-update
Status: Phase 8 complete, but 3 critical issues discovered during testing
```

### Available Strategies

1. **s01_trailing_ma** - Legacy S01 (will be removed in Phase 9)
2. **s01_trailing_ma_migrated** - Migrated S01 (production-ready)
3. **s04_stochrsi** - StochRSI strategy (working in backtest, broken in optimizer)

### Documentation References

- **Full Migration Plan**: `docs/PROJECT_MIGRATION_PLAN_upd.md`
- **Phase 8 Prompt**: `docs/prompt_8.md`
- **Phase 8 Report**: `docs/prompt_8_report.md`
- **Phase 8 Audit**: `docs/prompt_8_audit.md`
- **Project Architecture**: `docs/PROJECT_TARGET_ARCHITECTURE.md`
- **Project Structure**: `docs/PROJECT_STRUCTURE.md`

---

## Issues Summary

After Phase 8 completion, three critical issues were discovered:

### Issue 1: Error Popup When Loading Strategy Configuration

**Severity**: 🟡 MEDIUM (UX issue, not functional blocker)
**Impact**: Users see "Error loading strategy configuration" popup, but strategy actually loads
**Location**: `src/index.html` - `loadStrategyConfig()` function (line ~860)

### Issue 2: Missing MA Type Checkboxes

**Severity**: 🔴 HIGH (Functional blocker for S01 strategies)
**Impact**: S01 strategies cannot vary MA types during optimization
**Location**: `src/index.html` - MA type selector UI (lines 254-520)
**Reason**: MA type selectors were removed with the hardcoded optimizer section in Phase 8

### Issue 3: S04 Optimization Producing Identical Results

**Severity**: 🔴 CRITICAL (Complete failure of S04 optimization)
**Impact**: S04 optimizer doesn't work - produces S01 results with all zeros
**Evidence**: `docs/OKX_LINKUSDT.P, 15 2025.06.15-2025.11.15_Optuna (3).csv`
**Root Cause**: Backend uses S01 parameters and MA types instead of S04 parameters

---

## Issue 1: Error Popup When Loading Strategy

### Problem Description

When a user selects a strategy from the dropdown, they see an alert popup:

```
"Error loading strategy configuration"
```

However, the strategy **does load successfully** - the popup is a false alarm. After clicking "OK", the strategy parameters populate correctly in both backtest and optimizer forms.

### Root Cause Analysis

**Location**: `src/index.html` line ~860-874

```javascript
async function loadStrategyConfig(strategyId) {
  try {
    const response = await fetch(`/api/strategies/${strategyId}/config`);
    currentStrategyConfig = await response.json();

    updateStrategyInfo(currentStrategyConfig);
    generateBacktestForm(currentStrategyConfig);
    generateOptimizerForm(currentStrategyConfig);

    console.log(`Loaded strategy: ${currentStrategyConfig.name}`);
  } catch (error) {
    console.error('Failed to load strategy config:', error);
    alert('Error loading strategy configuration');  // ← FALSE ALARM
  }
}
```

**Analysis**:

The `catch` block is being triggered even though the fetch succeeds. This suggests one of the following:

1. **Response parsing error**: `response.json()` may be failing due to malformed JSON
2. **Synchronous exception**: One of the form generation functions throws an error
3. **Network issue**: Fetch succeeds but response is not OK (status 4xx/5xx)

**Most Likely Cause**: One of the UI generation functions (`updateStrategyInfo`, `generateBacktestForm`, or `generateOptimizerForm`) is throwing an error, but the forms still render because subsequent code continues execution.

### Why It's Not Breaking Functionality

JavaScript's `try-catch` only catches the first error. If `generateBacktestForm()` succeeds but `generateOptimizerForm()` throws a non-critical error (like trying to access a missing DOM element), the catch block triggers but the forms are already populated.

### Fix Strategy

**Option A: Add Response Validation** (Recommended)

```javascript
async function loadStrategyConfig(strategyId) {
  try {
    const response = await fetch(`/api/strategies/${strategyId}/config`);

    // VALIDATE RESPONSE
    if (!response.ok) {
      throw new Error(`Server returned ${response.status}: ${response.statusText}`);
    }

    const config = await response.json();

    // VALIDATE CONFIG
    if (!config || typeof config !== 'object') {
      throw new Error('Invalid config format');
    }

    if (!config.parameters || typeof config.parameters !== 'object') {
      throw new Error('Missing parameters in config');
    }

    currentStrategyConfig = config;

    // WRAP EACH STEP SEPARATELY
    try {
      updateStrategyInfo(config);
    } catch (err) {
      console.warn('Failed to update strategy info:', err);
      // Non-critical, continue
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
    alert(`Error loading strategy configuration: ${error.message}\n\nPlease check browser console for details.`);
  }
}
```

**Option B: Silent Errors** (If errors are expected and non-critical)

```javascript
async function loadStrategyConfig(strategyId) {
  try {
    const response = await fetch(`/api/strategies/${strategyId}/config`);

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}: ${response.statusText}`);
    }

    currentStrategyConfig = await response.json();

    updateStrategyInfo(currentStrategyConfig);
    generateBacktestForm(currentStrategyConfig);
    generateOptimizerForm(currentStrategyConfig);

    console.log(`✓ Loaded strategy: ${currentStrategyConfig.name}`);
  } catch (error) {
    // ONLY SHOW ALERT FOR CRITICAL ERRORS
    console.error('Failed to load strategy config:', error);

    // If we have a strategy config despite the error, don't alert
    if (!currentStrategyConfig || !currentStrategyConfig.parameters) {
      alert('Error loading strategy configuration. Please refresh and try again.');
    } else {
      console.warn('Non-critical error during strategy load, but forms populated successfully');
    }
  }
}
```

### Testing

**Test 1: Normal Load**
1. Select S01 from dropdown
2. Verify NO error popup
3. Verify strategy loads correctly
4. Check console for any warnings

**Test 2: Network Error**
1. Disconnect network or use DevTools to simulate offline
2. Select strategy
3. Verify appropriate error message
4. Reconnect and try again

**Test 3: Invalid Strategy**
1. Manually call `loadStrategyConfig('nonexistent_strategy')`
2. Verify appropriate error message

---

## Issue 2: Missing MA Type Checkboxes

### Problem Description

In Phase 8, the hardcoded optimizer HTML was removed (lines 1455-1829). This section contained:

1. **Optimizer parameter inputs** (maLength, closeCountLong, etc.) - ✅ Successfully replaced with dynamic generation
2. **MA type checkbox selectors** (Trend MA, Trail Long MA, Trail Short MA) - ❌ **REMOVED BY MISTAKE**

**Impact**:

- S01 strategies **require** the ability to vary MA types during optimization
- S01 has 3 MA type parameters:
  - `maType` - Trend MA type (SMA, EMA, HMA, ALMA, KAMA, WMA, TMA, T3, DEMA, VWMA, VWAP)
  - `trailLongType` - Trail Long MA type (same options)
  - `trailShortType` - Trail Short MA type (same options)
- Currently, MA type checkboxes exist in the **backtest form** but NOT in the **optimizer form**
- Without these checkboxes, S01 optimization can only test one MA type combination

### Current State

**Backtest Form** (lines 254-520):

```html
<!-- WORKING: MA type selectors in backtest form -->
<div class="ma-type-section">
  <h4>Trend MA Types</h4>
  <div class="checkbox-grid">
    <label><input type="checkbox" id="trend-sma" data-group="trend" data-type="SMA" /> SMA</label>
    <label><input type="checkbox" id="trend-ema" data-group="trend" data-type="EMA" /> EMA</label>
    <label><input type="checkbox" id="trend-hma" data-group="trend" data-type="HMA" /> HMA</label>
    <!-- ... 8 more MA types ... -->
  </div>
</div>

<div class="ma-type-section">
  <h4>Trail Long MA Types</h4>
  <!-- ... similar structure ... -->
</div>

<div class="ma-type-section">
  <h4>Trail Short MA Types</h4>
  <!-- ... similar structure ... -->
</div>
```

**Optimizer Form** (After Phase 8):

```html
<!-- MISSING: MA type selectors NOT in optimizer form -->
<div id="optimizerParamsContainer">
  <!-- Only shows dynamic parameters from config.json -->
  <!-- maType, trailLongType, trailShortType are NOT in config.json -->
</div>
```

### Why MA Types Are Not in config.json

**S01 config.json** does NOT include `maType`, `trailLongType`, `trailShortType` because:

1. These are **list parameters** (user selects multiple values to test)
2. `config.json` format only supports single-value parameters with ranges
3. MA types are handled specially in the backend via `ma_types_trend`, `ma_types_trail_long`, `ma_types_trail_short` arrays

**Backend expectation** (`src/server.py` lines 1203-1213):

```python
ma_types_trend = payload.get("ma_types_trend") or payload.get("maTypesTrend") or []
ma_types_trail_long = payload.get("ma_types_trail_long") or payload.get("maTypesTrailLong") or []
ma_types_trail_short = payload.get("ma_types_trail_short") or payload.get("maTypesTrailShort") or []
```

The backend **expects** these arrays in the optimization payload.

### Evidence from CSV Output

Looking at `docs/OKX_LINKUSDT.P, 15 2025.06.15-2025.11.15_Optuna (3).csv`:

```
MA Type,Tr L Type,Tr S Type,Net Profit%,Max DD%,Trades,Score,...
WMA,TMA,VWMA,94.82%,23.05%,66,15.00,...
HMA,SMA,HMA,94.82%,23.05%,66,15.00,...
```

The CSV shows **MA types being varied** in the results. But this is actually from S04 running with S01's backend logic (see Issue 3). For S01, we need these MA type selectors to work correctly.

### Architecture Decision

**Should MA types be added to config.json?**

**NO.** MA types are fundamentally different from numeric parameters:

- Numeric parameters: Single value, range with min/max/step
- MA types: Multi-select from fixed list of 11 options

**Solution**: MA type selectors should be **strategy-specific UI** that exists separately from the dynamic parameter form.

### Fix Strategy

**Step 1**: Add MA Type Selector Section to Optimizer

The MA type selectors should appear in the optimizer form **only for S01 strategies** (both `s01_trailing_ma` and `s01_trailing_ma_migrated`).

**Location**: After the dynamic `optimizerParamsContainer` div

```html
<!-- AFTER dynamic parameters -->
<div id="optimizerParamsContainer">
  <!-- Dynamic parameters here -->
</div>

<!-- ADD THIS: MA Type Selectors (conditionally shown for S01) -->
<div id="maTypeSelectorContainer" style="display: none; margin-top: 30px;">
  <div class="section" style="background-color: #f9f9f9; padding: 20px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #4a90e2;">MA Type Selection (for Optimization)</h3>
    <p style="font-size: 13px; color: #666; margin-bottom: 20px;">
      Select which Moving Average types to test during optimization. The optimizer will create combinations of these types.
    </p>

    <!-- Trend MA Types -->
    <div class="ma-type-section">
      <h4 style="color: #4a90e2; font-size: 14px; margin-bottom: 10px;">Trend MA Types</h4>
      <div class="checkbox-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 8px;">
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="SMA" /> SMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="EMA" /> EMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="HMA" checked /> HMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="ALMA" /> ALMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="KAMA" /> KAMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="WMA" /> WMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="TMA" /> TMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="T3" /> T3
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="DEMA" /> DEMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="VWMA" /> VWMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trend" data-type="VWAP" /> VWAP
        </label>
      </div>
    </div>

    <!-- Trail Long MA Types -->
    <div class="ma-type-section" style="margin-top: 20px;">
      <h4 style="color: #4a90e2; font-size: 14px; margin-bottom: 10px;">Trail Long MA Types</h4>
      <div class="checkbox-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 8px;">
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="SMA" /> SMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="EMA" /> EMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="HMA" checked /> HMA
        </label>
        <!-- ... repeat for all 11 MA types ... -->
      </div>
    </div>

    <!-- Trail Short MA Types -->
    <div class="ma-type-section" style="margin-top: 20px;">
      <h4 style="color: #4a90e2; font-size: 14px; margin-bottom: 10px;">Trail Short MA Types</h4>
      <div class="checkbox-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 8px;">
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="SMA" /> SMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="EMA" /> EMA
        </label>
        <label style="display: flex; align-items: center; font-size: 13px;">
          <input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="HMA" checked /> HMA
        </label>
        <!-- ... repeat for all 11 MA types ... -->
      </div>
    </div>

    <!-- Trail Lock Option -->
    <div style="margin-top: 20px; padding: 15px; background-color: white; border-radius: 5px;">
      <label style="display: flex; align-items: center; font-size: 14px;">
        <input type="checkbox" id="opt-lockTrailTypes" style="margin-right: 10px;" />
        <span>Lock Trail MA Types (use same types for Long and Short)</span>
      </label>
      <p style="font-size: 12px; color: #666; margin: 5px 0 0 25px;">
        When enabled, Trail Short types will match Trail Long types during optimization.
      </p>
    </div>
  </div>
</div>
```

**Step 2**: Show/Hide MA Type Selectors Based on Strategy

Modify `generateOptimizerForm()` to detect S01 strategies:

```javascript
function generateOptimizerForm(config) {
  const container = document.getElementById('optimizerParamsContainer');
  if (!container) {
    console.error('Optimizer container not found');
    return;
  }

  // Clear and generate dynamic parameters
  container.innerHTML = '';
  const params = config.parameters || {};
  const groups = {};

  // ... existing parameter generation code ...

  // Show/hide MA type selectors based on strategy
  const maTypeContainer = document.getElementById('maTypeSelectorContainer');
  if (maTypeContainer) {
    // Check if this is an S01 strategy
    const isS01 = currentStrategyId && currentStrategyId.includes('s01');

    if (isS01) {
      maTypeContainer.style.display = 'block';
      console.log('MA type selectors enabled for S01 strategy');
    } else {
      maTypeContainer.style.display = 'none';
      console.log('MA type selectors hidden for non-S01 strategy');
    }
  }

  // Rebind event listeners
  bindOptimizerInputs();
}
```

**Step 3**: Collect MA Types in Optimization Payload

Modify the optimization submission function to include MA types:

```javascript
function collectOptimizerMATypes() {
  const maTypes = {
    trend: [],
    trailLong: [],
    trailShort: []
  };

  // Only collect if MA type container is visible
  const container = document.getElementById('maTypeSelectorContainer');
  if (!container || container.style.display === 'none') {
    return null; // Not applicable for this strategy
  }

  // Collect checked MA types
  const checkboxes = document.querySelectorAll('.opt-ma-type:checked');
  checkboxes.forEach(cb => {
    const group = cb.dataset.group;
    const type = cb.dataset.type;
    if (group && type) {
      if (group === 'trend') {
        maTypes.trend.push(type);
      } else if (group === 'trailLong') {
        maTypes.trailLong.push(type);
      } else if (group === 'trailShort') {
        maTypes.trailShort.push(type);
      }
    }
  });

  // Get lock setting
  const lockCheckbox = document.getElementById('opt-lockTrailTypes');
  const lockTrailTypes = lockCheckbox ? lockCheckbox.checked : false;

  return {
    maTypesTrend: maTypes.trend,
    maTypesTrailLong: maTypes.trailLong,
    maTypesTrailShort: maTypes.trailShort,
    lockTrailTypes: lockTrailTypes
  };
}

// Update optimization payload assembly
function buildOptimizationPayload() {
  const payload = {
    // ... existing fields ...
    param_ranges: collectOptimizerParams(),
    // ... other fields ...
  };

  // Add MA types if applicable
  const maTypes = collectOptimizerMATypes();
  if (maTypes) {
    payload.ma_types_trend = maTypes.maTypesTrend;
    payload.ma_types_trail_long = maTypes.maTypesTrailLong;
    payload.ma_types_trail_short = maTypes.maTypesTrailShort;
    payload.lock_trail_types = maTypes.lockTrailTypes;
  }

  return payload;
}
```

### Testing

**Test 1: S01 Strategy**
1. Select S01 from dropdown
2. Navigate to Optimizer tab
3. Verify MA type selectors are **visible**
4. Check some MA types (e.g., HMA, EMA, SMA for each group)
5. Enable 2-3 numeric parameters
6. Run small optimization (10 trials)
7. Verify CSV shows different MA type combinations

**Test 2: S04 Strategy**
1. Select S04 from dropdown
2. Navigate to Optimizer tab
3. Verify MA type selectors are **hidden**
4. Enable 3 numeric parameters
5. Run small optimization (10 trials)
6. Verify results use S04 parameters (not S01 MA types)

**Test 3: Trail Lock Feature**
1. Select S01
2. Check "Lock Trail MA Types"
3. Select different Trail Long types
4. Run optimization
5. Verify Trail Short types match Trail Long types in results

---

## Issue 3: S04 Optimization Producing Identical Results

### Problem Description

When running optimization for S04 StochRSI strategy:

1. User selects S04 from dropdown ✓
2. User enables S04 parameters in optimizer ✓
3. User runs optimization (50 trials)
4. **Results show S01 parameters with all zeros**:
   - `maLength=0`, `closeCountLong=0`, `stopLongX=0.0`, etc.
   - Only MA types are varied (which S04 doesn't use)
   - All 50 trials produce **identical metrics**: Net Profit 94.82%, Max DD 23.05%, 66 trades

**Evidence**: `docs/OKX_LINKUSDT.P, 15 2025.06.15-2025.11.15_Optuna (3).csv`

```csv
Fixed Parameters
Parameter Name,Value
maLength,0              ← S01 parameter!
closeCountLong,0        ← S01 parameter!
closeCountShort,0       ← S01 parameter!
...

MA Type,Tr L Type,Tr S Type,Net Profit%,Max DD%,Trades,...
WMA,TMA,VWMA,94.82%,23.05%,66,15.00,...  ← All identical!
HMA,SMA,HMA,94.82%,23.05%,66,15.00,...   ← Same results!
```

### Root Cause Analysis

**Location**: `src/server.py` lines 1203-1220

The backend's `_build_optimization_config()` function has **hardcoded S01 logic**:

```python
# Lines 1203-1213: HARDCODED S01 MA TYPES
ma_types_trend = payload.get("ma_types_trend") or payload.get("maTypesTrend") or []
ma_types_trail_long = payload.get("ma_types_trail_long") or payload.get("maTypesTrailLong") or []
ma_types_trail_short = payload.get("ma_types_trail_short") or payload.get("maTypesTrailShort") or []

# Lines 1215-1220: HARDCODED S01 TRAIL LOCK
lock_trail_types_raw = payload.get("lock_trail_types") or payload.get("lockTrailTypes") or payload.get("trailLock")
lock_trail_types = _parse_bool(lock_trail_types_raw, False)
```

This code **always** looks for MA types, regardless of strategy. Then it passes these to the optimization engine, which creates combinations of MA types instead of S04 parameters.

**Problem**: The optimization engine sees:
- Strategy: `s04_stochrsi`
- MA types: `['HMA', 'SMA', 'EMA', ...]`
- S04 param ranges: `{'rsiLen': [10, 20, 2], 'stochLen': [10, 20, 2], ...}`

The engine is confused - it's trying to optimize S04 with S01's MA type logic.

### Expected Behavior

**S04 should optimize:**
- `rsiLen`: [10, 20, step 2]
- `stochLen`: [10, 20, step 2]
- `obLevel`: [60, 90, step 1]
- `osLevel`: [5, 30, step 1]
- `extLookback`: [5, 60, step 1]
- `confirmBars`: [2, 40, step 1]

**S04 should NOT use:**
- MA types (S04 doesn't use MAs)
- S01 parameters (maLength, closeCountLong, etc.)

### Why All Results Are Identical

The optimization engine is varying **only MA types**, but S04 strategy ignores MA types. So every trial runs with the same S04 parameters (defaults), producing identical results.

### Fix Strategy

**Step 1**: Make MA Type Handling Strategy-Specific

Modify `_build_optimization_config()` to only include MA types for S01 strategies:

```python
def _build_optimization_config(
    csv_file,
    payload: dict,
    worker_processes=None,
    strategy_id=None,
    warmup_bars: Optional[int] = None,
) -> OptimizationConfig:
    # ... existing code ...

    if strategy_id is None:
        strategy_id = "s01_trailing_ma"

    # CHANGE: Only handle MA types for S01 strategies
    ma_types_trend = []
    ma_types_trail_long = []
    ma_types_trail_short = []
    lock_trail_types = False

    # Check if this is an S01 strategy (includes both legacy and migrated)
    is_s01_strategy = strategy_id and ('s01' in strategy_id.lower())

    if is_s01_strategy:
        # Only extract MA types for S01 strategies
        ma_types_trend = payload.get("ma_types_trend") or payload.get("maTypesTrend") or []
        ma_types_trail_long = (
            payload.get("ma_types_trail_long")
            or payload.get("maTypesTrailLong")
            or []
        )
        ma_types_trail_short = (
            payload.get("ma_types_trail_short")
            or payload.get("maTypesTrailShort")
            or []
        )

        lock_trail_types_raw = (
            payload.get("lock_trail_types")
            or payload.get("lockTrailTypes")
            or payload.get("trailLock")
        )
        lock_trail_types = _parse_bool(lock_trail_types_raw, False)

        # Log for debugging
        print(f"S01 Strategy detected: using MA types")
        print(f"  Trend: {len(ma_types_trend)} types")
        print(f"  Trail Long: {len(ma_types_trail_long)} types")
        print(f"  Trail Short: {len(ma_types_trail_short)} types")
        print(f"  Lock: {lock_trail_types}")
    else:
        # Non-S01 strategies: ignore MA types
        print(f"Non-S01 Strategy ({strategy_id}): skipping MA types")

    # ... rest of function continues unchanged ...
```

**Step 2**: Validate S04 Parameters Are Used

Ensure the optimization engine uses S04's parameter ranges:

The `OptimizationConfig` should have:
```python
OptimizationConfig(
    strategy_id='s04_stochrsi',
    param_ranges={
        'rsiLen': (10.0, 20.0, 2.0),
        'stochLen': (10.0, 20.0, 2.0),
        'obLevel': (60.0, 90.0, 1.0),
        'osLevel': (5.0, 30.0, 1.0),
        'extLookback': (5.0, 60.0, 1.0),
        'confirmBars': (2.0, 40.0, 1.0)
    },
    ma_types_trend=[],  # Empty for S04
    ma_types_trail_long=[],  # Empty for S04
    ma_types_trail_short=[],  # Empty for S04
    ...
)
```

**Step 3**: Fix Optuna Engine MA Type Handling

Check `src/core/optuna_engine.py` to ensure it doesn't require MA types:

```python
def run_optimization(config: OptimizationConfig) -> List[OptimizationResult]:
    # ... existing code ...

    def objective(trial):
        params = {}

        # Sample regular parameters
        for param_name, (min_val, max_val, step) in config.param_ranges.items():
            # ... existing sampling code ...

        # ONLY sample MA types if they exist
        if config.ma_types_trend:
            params['maType'] = trial.suggest_categorical('maType', config.ma_types_trend)

        if config.ma_types_trail_long:
            params['trailLongType'] = trial.suggest_categorical('trailLongType', config.ma_types_trail_long)

        if config.ma_types_trail_short:
            if config.lock_trail_types:
                params['trailShortType'] = params.get('trailLongType', config.ma_types_trail_short[0])
            else:
                params['trailShortType'] = trial.suggest_categorical('trailShortType', config.ma_types_trail_short)

        # Run strategy
        result = run_backtest(config.df, params, config.strategy_id, ...)

        # ... rest of objective ...
```

**Key Change**: Don't sample MA types if the lists are empty.

### Testing

**Test 1: S04 Optimization (Main Fix)**
1. Select S04 from dropdown
2. Enable 3 parameters: rsiLen, stochLen, obLevel
3. Set ranges:
   - rsiLen: [12, 18, step 2]
   - stochLen: [12, 18, step 2]
   - obLevel: [70, 80, step 5]
4. Run 10 trials
5. **Verify CSV shows**:
   - S04 parameters being varied (rsiLen, stochLen, obLevel)
   - NO S01 parameters (maLength, closeCountLong, etc.)
   - NO MA Type columns
   - Results should differ between trials

**Test 2: S01 Optimization (No Regression)**
1. Select S01 from dropdown
2. Enable 2 numeric parameters + MA types
3. Run 10 trials
4. Verify CSV shows:
   - S01 parameters being varied
   - MA Type columns present
   - Results vary as expected

**Test 3: Mixed Optimization**
1. Run S04 optimization
2. Switch to S01 and run optimization
3. Verify both produce correct results

---

## Implementation Guide

### Step-by-Step Implementation

#### Part 1: Fix Issue 1 (Error Popup)

**File**: `src/index.html`

**Line**: ~860-874

**Action**: Replace `loadStrategyConfig()` function

```javascript
async function loadStrategyConfig(strategyId) {
  try {
    const response = await fetch(`/api/strategies/${strategyId}/config`);

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}: ${response.statusText}`);
    }

    const config = await response.json();

    if (!config || typeof config !== 'object' || !config.parameters) {
      throw new Error('Invalid config format');
    }

    currentStrategyConfig = config;

    // Try each step independently
    try {
      updateStrategyInfo(config);
    } catch (err) {
      console.warn('Non-critical: Failed to update strategy info:', err);
    }

    try {
      generateBacktestForm(config);
    } catch (err) {
      console.error('Failed to generate backtest form:', err);
      alert('Error generating backtest form. Please refresh.');
      return;
    }

    try {
      generateOptimizerForm(config);
    } catch (err) {
      console.error('Failed to generate optimizer form:', err);
      alert('Error generating optimizer form. Please refresh.');
      return;
    }

    console.log(`✓ Loaded strategy: ${config.name}`);
  } catch (error) {
    console.error('Failed to load strategy config:', error);

    // Only alert if config truly failed to load
    if (!currentStrategyConfig || !currentStrategyConfig.parameters) {
      alert(`Error loading strategy: ${error.message}\n\nCheck browser console for details.`);
    }
  }
}
```

**Test**: Select strategies, verify no false alarms

---

#### Part 2: Fix Issue 2 (MA Type Checkboxes)

**File**: `src/index.html`

**Location**: After line that contains `<div id="optimizerParamsContainer">`

**Action 1**: Add MA type selector container

Find this line:
```html
<div id="optimizerParamsContainer" class="optimizer-params-container">
  <!-- Parameters will be generated dynamically here -->
</div>
```

**Add AFTER it**:

```html
<!-- MA Type Selectors (S01 only) -->
<div id="maTypeSelectorContainer" style="display: none; margin-top: 30px;">
  <div class="section" style="background-color: #f9f9f9; padding: 20px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #4a90e2;">🎯 MA Type Selection</h3>
    <p style="font-size: 13px; color: #666; margin-bottom: 20px;">
      Select which Moving Average types to test during optimization. Each combination will be tested.
    </p>

    <!-- Trend MA Types -->
    <div class="ma-type-section" style="margin-bottom: 20px;">
      <h4 style="color: #4a90e2; font-size: 14px; margin: 0 0 10px 0;">Trend MA Types</h4>
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 8px;">
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="SMA" /> SMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="EMA" /> EMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="HMA" checked /> HMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="ALMA" /> ALMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="KAMA" /> KAMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="WMA" /> WMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="TMA" /> TMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="T3" /> T3</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="DEMA" /> DEMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="VWMA" /> VWMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trend" data-type="VWAP" /> VWAP</label>
      </div>
    </div>

    <!-- Trail Long MA Types -->
    <div class="ma-type-section" style="margin-bottom: 20px;">
      <h4 style="color: #4a90e2; font-size: 14px; margin: 0 0 10px 0;">Trail Long MA Types</h4>
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 8px;">
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="SMA" /> SMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="EMA" /> EMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="HMA" checked /> HMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="ALMA" /> ALMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="KAMA" /> KAMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="WMA" /> WMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="TMA" /> TMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="T3" /> T3</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="DEMA" /> DEMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="VWMA" /> VWMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailLong" data-type="VWAP" /> VWAP</label>
      </div>
    </div>

    <!-- Trail Short MA Types -->
    <div class="ma-type-section" style="margin-bottom: 20px;">
      <h4 style="color: #4a90e2; font-size: 14px; margin: 0 0 10px 0;">Trail Short MA Types</h4>
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 8px;">
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="SMA" /> SMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="EMA" /> EMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="HMA" checked /> HMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="ALMA" /> ALMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="KAMA" /> KAMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="WMA" /> WMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="TMA" /> TMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="T3" /> T3</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="DEMA" /> DEMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="VWMA" /> VWMA</label>
        <label style="display: flex; align-items: center; font-size: 13px;"><input type="checkbox" class="opt-ma-type" data-group="trailShort" data-type="VWAP" /> VWAP</label>
      </div>
    </div>

    <!-- Lock Trail Types -->
    <div style="padding: 15px; background-color: white; border-radius: 5px;">
      <label style="display: flex; align-items: center; font-size: 14px; cursor: pointer;">
        <input type="checkbox" id="opt-lockTrailTypes" style="margin-right: 10px;" />
        <span><strong>Lock Trail MA Types</strong> (use same for Long & Short)</span>
      </label>
      <p style="font-size: 12px; color: #666; margin: 5px 0 0 25px;">
        When enabled, Trail Short types will automatically match Trail Long types.
      </p>
    </div>
  </div>
</div>
```

**Action 2**: Update `generateOptimizerForm()` function

Find the `generateOptimizerForm()` function and add this code at the END (before `bindOptimizerInputs()`):

```javascript
function generateOptimizerForm(config) {
  const container = document.getElementById('optimizerParamsContainer');
  // ... existing parameter generation code ...

  // ====== ADD THIS BLOCK ======
  // Show/hide MA type selectors based on strategy
  const maTypeContainer = document.getElementById('maTypeSelectorContainer');
  if (maTypeContainer) {
    const isS01 = currentStrategyId && currentStrategyId.toLowerCase().includes('s01');

    if (isS01) {
      maTypeContainer.style.display = 'block';
      console.log('✓ MA type selectors enabled for S01 strategy');
    } else {
      maTypeContainer.style.display = 'none';
      console.log('✓ MA type selectors hidden for non-S01 strategy');
    }
  } else {
    console.warn('MA type selector container not found in DOM');
  }
  // ====== END BLOCK ======

  bindOptimizerInputs();
  console.log(`Generated optimizer form with ${totalParams} parameters`);
}
```

**Action 3**: Add MA type collection function

Find where optimization payload is built (search for the function that handles optimization submission). Add this helper function near the top:

```javascript
/**
 * Collect selected MA types for S01 optimization.
 * Returns null if MA type container is not visible (non-S01 strategy).
 */
function collectOptimizerMATypes() {
  const container = document.getElementById('maTypeSelectorContainer');

  // If container hidden or not found, return null (not applicable)
  if (!container || container.style.display === 'none') {
    return null;
  }

  const maTypes = {
    trend: [],
    trailLong: [],
    trailShort: []
  };

  // Collect checked MA types
  const checkboxes = document.querySelectorAll('.opt-ma-type:checked');
  checkboxes.forEach(cb => {
    const group = cb.dataset.group;
    const type = cb.dataset.type;

    if (group && type) {
      if (group === 'trend') {
        maTypes.trend.push(type);
      } else if (group === 'trailLong') {
        maTypes.trailLong.push(type);
      } else if (group === 'trailShort') {
        maTypes.trailShort.push(type);
      }
    }
  });

  // Validate at least one type selected in each group
  if (maTypes.trend.length === 0) {
    console.warn('No Trend MA types selected, defaulting to HMA');
    maTypes.trend.push('HMA');
  }
  if (maTypes.trailLong.length === 0) {
    console.warn('No Trail Long MA types selected, defaulting to HMA');
    maTypes.trailLong.push('HMA');
  }
  if (maTypes.trailShort.length === 0) {
    console.warn('No Trail Short MA types selected, defaulting to HMA');
    maTypes.trailShort.push('HMA');
  }

  // Get lock setting
  const lockCheckbox = document.getElementById('opt-lockTrailTypes');
  const lockTrailTypes = lockCheckbox ? lockCheckbox.checked : false;

  console.log('Collected MA types:', {
    trend: maTypes.trend,
    trailLong: maTypes.trailLong,
    trailShort: maTypes.trailShort,
    lock: lockTrailTypes
  });

  return {
    maTypesTrend: maTypes.trend,
    maTypesTrailLong: maTypes.trailLong,
    maTypesTrailShort: maTypes.trailShort,
    lockTrailTypes: lockTrailTypes
  };
}
```

**Action 4**: Update optimization payload assembly

Find the function that builds the optimization payload (likely in the optimization submission handler). Update it to include MA types:

```javascript
// In the optimization submission function, find where payload is built:
const payload = {
  strategy: currentStrategyId,
  param_ranges: collectOptimizerParams(),
  fixed_params: collectFixedParams(),
  enabled_params: collectEnabledParams(),
  // ... other existing fields ...
};

// ====== ADD THIS ======
// Add MA types if applicable (S01 only)
const maTypes = collectOptimizerMATypes();
if (maTypes) {
  payload.ma_types_trend = maTypes.maTypesTrend;
  payload.ma_types_trail_long = maTypes.maTypesTrailLong;
  payload.ma_types_trail_short = maTypes.maTypesTrailShort;
  payload.lock_trail_types = maTypes.lockTrailTypes;

  console.log('Added MA types to optimization payload');
} else {
  console.log('MA types not applicable for this strategy');
}
// ====== END ======
```

**Test**: Select S01, verify MA type checkboxes appear. Select S04, verify they're hidden.

---

#### Part 3: Fix Issue 3 (S04 Optimization)

**File**: `src/server.py`

**Location**: Find `def _build_optimization_config(` (around line 1076)

**Action**: Update MA type handling to be strategy-specific

Find these lines (around 1203-1220):

```python
# OLD CODE (lines 1203-1220):
ma_types_trend = payload.get("ma_types_trend") or payload.get("maTypesTrend") or []
ma_types_trail_long = (
    payload.get("ma_types_trail_long")
    or payload.get("maTypesTrailLong")
    or []
)
ma_types_trail_short = (
    payload.get("ma_types_trail_short")
    or payload.get("maTypesTrailShort")
    or []
)

lock_trail_types_raw = (
    payload.get("lock_trail_types")
    or payload.get("lockTrailTypes")
    or payload.get("trailLock")
)
lock_trail_types = _parse_bool(lock_trail_types_raw, False)
```

**REPLACE WITH**:

```python
# NEW CODE: Strategy-specific MA type handling
ma_types_trend = []
ma_types_trail_long = []
ma_types_trail_short = []
lock_trail_types = False

# Only extract MA types for S01 strategies
is_s01_strategy = strategy_id and ('s01' in strategy_id.lower())

if is_s01_strategy:
    # S01 uses MA types for trend and trail logic
    ma_types_trend = payload.get("ma_types_trend") or payload.get("maTypesTrend") or []
    ma_types_trail_long = (
        payload.get("ma_types_trail_long")
        or payload.get("maTypesTrailLong")
        or []
    )
    ma_types_trail_short = (
        payload.get("ma_types_trail_short")
        or payload.get("maTypesTrailShort")
        or []
    )

    lock_trail_types_raw = (
        payload.get("lock_trail_types")
        or payload.get("lockTrailTypes")
        or payload.get("trailLock")
    )
    lock_trail_types = _parse_bool(lock_trail_types_raw, False)

    # Log for debugging
    app.logger.info(f"S01 strategy ({strategy_id}): using MA types")
    app.logger.info(f"  Trend types: {len(ma_types_trend)} ({ma_types_trend})")
    app.logger.info(f"  Trail Long types: {len(ma_types_trail_long)} ({ma_types_trail_long})")
    app.logger.info(f"  Trail Short types: {len(ma_types_trail_short)} ({ma_types_trail_short})")
    app.logger.info(f"  Lock trail types: {lock_trail_types}")
else:
    # Non-S01 strategies don't use MA types
    app.logger.info(f"Non-S01 strategy ({strategy_id}): ignoring MA types from payload")
    # All MA type lists remain empty
```

**Test**: Run S04 optimization, verify it uses S04 parameters (not MA types).

---

### Validation Steps

After implementing all fixes:

1. **Restart server**
   ```bash
   cd src
   python server.py
   ```

2. **Test Issue 1 Fix**
   - Select S01 → no error popup
   - Select S04 → no error popup
   - Switch between strategies → no error popups

3. **Test Issue 2 Fix**
   - Select S01 → MA type checkboxes visible in optimizer
   - Select S04 → MA type checkboxes hidden
   - Check some MA types for S01 → verify they're collected in payload

4. **Test Issue 3 Fix**
   - Select S04
   - Enable 3 parameters: rsiLen [12-18-2], stochLen [12-18-2], obLevel [70-80-5]
   - Run 10 trials
   - **Verify CSV**:
     - Shows rsiLen, stochLen, obLevel being varied
     - NO maLength, closeCountLong columns
     - NO "MA Type" columns
     - Results should differ between trials

5. **Regression Test S01**
   - Select S01
   - Enable 2 params + MA types
   - Run 10 trials
   - Verify CSV shows S01 parameters + MA type combinations

---

## Testing Requirements

### Manual Testing Checklist

#### Issue 1: Error Popup
- [ ] Select S01 → no error popup, strategy loads
- [ ] Select S04 → no error popup, strategy loads
- [ ] Select S01 migrated → no error popup
- [ ] Rapid strategy switching → no errors
- [ ] Check browser console for warnings (should be minimal)

#### Issue 2: MA Type Checkboxes
- [ ] Select S01 → MA type section visible in optimizer
- [ ] MA type checkboxes functional (check/uncheck)
- [ ] Default HMA checked for all 3 groups
- [ ] Trail lock checkbox functional
- [ ] Select S04 → MA type section hidden
- [ ] Switch S01→S04→S01 → MA types show/hide correctly

#### Issue 3: S04 Optimization
- [ ] S04 optimizer shows 6 parameters (rsiLen, stochLen, obLevel, osLevel, extLookback, confirmBars)
- [ ] Enable 3 params, run 10 trials
- [ ] CSV has S04 param columns (not S01 params)
- [ ] CSV has NO "MA Type" columns
- [ ] Results vary between trials
- [ ] Metrics make sense for S04 strategy

#### Regression: S01 Optimization
- [ ] S01 optimizer shows ~19 parameters + MA types
- [ ] Enable 2 params + MA types
- [ ] Run 10 trials
- [ ] CSV has S01 param columns
- [ ] CSV has "MA Type", "Tr L Type", "Tr S Type" columns
- [ ] Results vary between trials
- [ ] Matches previous S01 optimization results

### Automated Testing

Run existing test suite to ensure no regressions:

```bash
cd src
pytest tests/ -v
```

Expected: **76 tests passing** (same as before)

---

## Success Criteria

Phase 8.1 is successful when:

### Issue 1: Fixed
- ✅ No error popup when loading strategies
- ✅ Strategies load correctly
- ✅ Browser console shows minimal warnings

### Issue 2: Fixed
- ✅ S01 strategies show MA type checkboxes in optimizer
- ✅ S04 strategies hide MA type checkboxes
- ✅ MA types collected correctly in optimization payload
- ✅ Trail lock feature works

### Issue 3: Fixed
- ✅ S04 optimization uses S04 parameters
- ✅ S04 optimization does NOT use MA types
- ✅ S04 results vary between trials
- ✅ S04 CSV shows correct columns

### No Regressions
- ✅ S01 optimization still works correctly
- ✅ All 76 tests still passing
- ✅ No new bugs introduced

### Code Quality
- ✅ Code is clean and well-commented
- ✅ Console logs are helpful for debugging
- ✅ Error messages are user-friendly

---

## Deliverables

After completing Phase 8.1:

- [ ] `src/index.html` updated with fixes
- [ ] `src/server.py` updated with strategy-specific logic
- [ ] All 3 issues resolved
- [ ] Manual testing completed
- [ ] Automated tests passing (76/76)
- [ ] Git commit: "Phase 8.1: Fix error popup, MA type checkboxes, and S04 optimization"
- [ ] Documentation updated if needed

---

## Summary

Phase 8.1 fixes three critical issues discovered after Phase 8:

1. **Error Popup** - False alarm removed by improving error handling
2. **MA Type Checkboxes** - Restored for S01 strategies, hidden for others
3. **S04 Optimization** - Fixed to use S04 parameters instead of S01 MA types

These fixes ensure:
- ✅ Better UX (no false error popups)
- ✅ S01 strategies can vary MA types during optimization
- ✅ S04 optimization works correctly with its own parameters
- ✅ Architecture remains clean and strategy-agnostic

After Phase 8.1, the system will be ready for Phase 9 (Legacy Code Cleanup).

---

**End of Phase 8.1 Fix Prompt**

**Version**: 1.0
**Date**: 2025-12-04
**Author**: Migration Analysis Team
**Status**: Ready for GPT 5.1 Codex Implementation
