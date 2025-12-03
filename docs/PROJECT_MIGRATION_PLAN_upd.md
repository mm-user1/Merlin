# Migration Plan - Updated v2.1
## From Legacy S_01-Centric Architecture to Clean Core Architecture

**Version:** 2.1
**Date:** 2025-12-03
**Status:** Final - Ready for Phase 7 Execution
**Scope:** Updated plan incorporating Phase 6 completion and addressing UI hardcoding issues.

---

## Executive Summary

This updated plan reflects the completion of Phases -1 through 6 and addresses critical findings from the Phase 6 audit. The main changes from v2.0:

### Key Updates in v2.1:

1. **Phase 7 remains unchanged** - S01 migration via duplicate strategy approach
2. **NEW Phase 8: Dynamic Optimizer + CSS Extraction** - Fix hardcoded S01 parameters in UI
3. **NEW Phase 9: Legacy Code Cleanup** - Delete all S01-specific hardcoded blocks
4. **Phase 10: Frontend Separation** (was Phase 8) - Full UI modularization
5. **Phase 11: Documentation** (was Phase 9) - No logging (deferred to post-migration)

### Rationale for Changes:

**Phase 6 Audit Finding:** The optimizer UI has hardcoded S01 parameters that don't load for S04 strategy. This blocks production use of S04 and will complicate S01 migration.

**Solution:** Insert new phases to fix UI dynamically BEFORE deleting legacy code, ensuring UI remains functional throughout migration.

### Architecture Principles (Unchanged):

- **Iterative migration** - Small, verifiable phases with regression tests
- **Behavior preservation** - S01 results must remain identical
- **Legacy co-existence** - Old code stays until new code is validated
- **Test-driven** - Every high-risk change validated by automated tests
- **Data structure ownership** - Each module owns the structures it creates

---

## 0. General Principles

### Data Structure Location Strategy

Following the principle "structures live where they're populated":

- **TradeRecord, StrategyResult** → `backtest_engine.py` (populated during simulation)
- **BasicMetrics, AdvancedMetrics** → `metrics.py` (calculated from StrategyResult)
- **OptimizationResult, OptunaConfig** → `optuna_engine.py` (created during optimization)
- **WFAMetrics** → `metrics.py` (aggregated metrics calculation)
- **StrategyParams** → `strategies/<strategy_name>/strategy.py` (each strategy owns its params)

### Migration Safeguards

On each phase:
- Priority: **preserve S01 behavior** (and S04)
- Important changes accompanied by regression and basic unit tests
- Legacy code deleted **only after** successful validation of new implementation
- Git tags at each phase completion: `phase-X-complete`

---

## Phase -1: Test Infrastructure Setup ✅ COMPLETE

**Status:** COMPLETE (2025-11-28)
**Duration:** ~2 hours
**Tests:** 9/9 sanity tests passing

[Content unchanged - phase already completed]

---

## Phase 0: Regression Baseline for S01 ✅ COMPLETE

**Status:** COMPLETE (2025-11-28)
**Duration:** ~3 hours
**Tests:** 12/12 regression tests passing

[Content unchanged - phase already completed]

---

## Phase 1: Core Extraction to src/core/ ✅ COMPLETE

**Status:** COMPLETE (2025-11-28)
**Duration:** ~2 hours
**Tests:** 21/21 passing

[Content unchanged - phase already completed]

---

## Phase 2: Export Extraction to export.py ✅ COMPLETE

**Status:** COMPLETE (2025-11-28)
**Duration:** ~4 hours
**Tests:** 28/28 passing

[Content unchanged - phase already completed]

---

## Phase 3: Grid Search Removal ✅ COMPLETE

**Status:** COMPLETE (2025-11-29)
**Complexity:** 🔴 HIGH
**Risk:** 🟡 MEDIUM

[Content unchanged - phase already completed]

---

## Phase 4: Metrics Extraction to metrics.py ✅ COMPLETE

**Status:** COMPLETE (2025-11-29)
**Complexity:** 🔴 HIGH
**Risk:** 🔴 HIGH

[Content unchanged - phase already completed]

---

## Phase 5: Indicators Package Extraction ✅ COMPLETE

**Status:** COMPLETE (2025-11-29)
**Complexity:** 🔴 HIGH
**Risk:** 🔴 HIGH

[Content unchanged - phase already completed]

---

## Phase 6: Simple Strategy Testing ✅ COMPLETE

**Status:** COMPLETE (2025-12-03)
**Complexity:** 🟡 MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 8-12 hours
**Actual Effort:** ~10 hours

### Goal

Test new architecture end-to-end with S04 StochRSI strategy BEFORE migrating complex S01.

### What Was Delivered

✅ S04 StochRSI strategy implemented in new architecture
✅ RSI and StochRSI indicators added to `oscillators.py`
✅ Performance matched reference within ±5% tolerance
✅ All 58 tests passing (4 new S04 tests + 54 existing)
✅ Architecture validated for Phase 7

### Critical Finding

⚠️ **UI Integration NOT Tested**: Optimizer parameters are hardcoded for S01 in the frontend. When S04 is selected, optimizer still shows S01 parameters instead of S04 parameters.

**Impact:** Blocks production use of S04 and will complicate future strategy additions.

**Resolution:** Addressed in NEW Phase 8 (Dynamic Optimizer + CSS Extraction).

---

## Phase 7: S01 Migration via Duplicate

**Complexity:** 🔴 VERY HIGH
**Risk:** 🔴 VERY HIGH
**Estimated Effort:** 16-24 hours
**Priority:** 🚨 HIGHEST RISK PHASE

### Goal

Migrate S01 strategy to new architecture while:
- Legacy S01 remains available for testing and comparison
- Creating migrated S01 in separate folder
- After validation, migrated version becomes production

### Why This Is Highest Risk

- S01 is complex: 11 MA types, trailing stops, ATR sizing, close counts
- Current S01 calls `run_strategy()` from backtest_engine (~300 lines of S01-specific logic)
- Must reimplement complex logic in strategy class
- Any difference in results is unacceptable

### Current S01 Architecture

```python
# strategies/s01_trailing_ma/strategy.py (current - 45 lines)
class S01TrailingMA(BaseStrategy):
    @staticmethod
    def run(df, params, trade_start_idx):
        parsed_params = StrategyParams.from_dict(params)
        return run_strategy(df, parsed_params, trade_start_idx)  # ← delegates to engine!

# backtest_engine.py (current - line 726)
def run_strategy(df, params, trade_start_idx):  # ← 300+ lines of S01-specific logic
    # - Calculate MAs, ATR, trailing MAs
    # - Bar-by-bar simulation
    # - Entry/exit logic with close counts
    # - Position sizing (qty or % of equity)
    # - Stop management (ATR-based, max %, max days)
    # - Trail management (long/short trails with different MA types)
```

### Dual-Track Strategy

```
strategies/s01_trailing_ma/          ← KEEP unchanged (legacy)
strategies/s01_trailing_ma_migrated/ ← NEW implementation
```

### Steps

#### 7.1: Create Migrated Strategy Structure (2 hours)

1. **Create new folder:**
   ```bash
   mkdir src/strategies/s01_trailing_ma_migrated
   touch src/strategies/s01_trailing_ma_migrated/__init__.py
   ```

2. **Copy and update config.json:**
   ```bash
   cp src/strategies/s01_trailing_ma/config.json \
      src/strategies/s01_trailing_ma_migrated/
   ```
   - Update `strategy_id` to `"s01_trailing_ma_migrated"`
   - Keep all parameters identical

3. **Create strategy.py with S01Params:**
   ```python
   # src/strategies/s01_trailing_ma_migrated/strategy.py
   from dataclasses import dataclass
   from typing import Dict, Any, Optional
   import pandas as pd

   @dataclass
   class S01Params:
       """
       S01 strategy parameters - lives INSIDE the strategy module.
       This is the target architecture: each strategy owns its params.
       """
       # Main MA
       ma_type: str = "HMA"
       ma_length: int = 50

       # Trailing MAs
       trail_long_type: str = "HMA"
       trail_long_length: int = 30
       trail_short_type: str = "HMA"
       trail_short_length: int = 30

       # Entry logic
       close_count_long: int = 3
       close_count_short: int = 3

       # Position sizing
       qty: float = 1.0
       qty_mode: str = "fixed"  # "fixed" or "percent_equity"

       # Stops (ATR-based, max %, max days)
       enable_atr_stop: bool = True
       atr_multiplier_long: float = 1.5
       atr_multiplier_short: float = 1.5
       atr_period: int = 14

       stop_long_max_pct: float = 5.0
       stop_short_max_pct: float = 5.0

       stop_long_max_days: int = 30
       stop_short_max_days: int = 30

       # Trailing exits
       trail_rr_long: float = 1.0
       trail_rr_short: float = 1.0
       trail_long_offset: float = 0.0
       trail_short_offset: float = 0.0

       # ... more params as needed

       @staticmethod
       def from_dict(d: Dict[str, Any]) -> "S01Params":
           """Parse from frontend/API payload"""
           return S01Params(
               ma_type=d.get('maType', 'HMA'),
               ma_length=int(d.get('maLength', 50)),
               # ... all params with camelCase mapping
           )
   ```

#### 7.2: Incremental Logic Migration (10-15 hours)

**Strategy:** Copy run_strategy() logic in chunks, test each chunk.

1. **Step 1: Copy run_strategy() to S01TrailingMAMigrated.run()** (2 hours)
   - Create exact copy of run_strategy() inside strategy class
   - Run comparison test (legacy vs migrated)
   - Should be IDENTICAL since it's exact copy

2. **Step 2: Replace inline calculations with indicators.* calls** (4-6 hours)
   ```python
   # BEFORE (inline in run_strategy):
   ma_values = df['Close'].rolling(window=params.ma_length).mean()

   # AFTER (using indicators package):
   from indicators.ma import get_ma
   ma_values = get_ma(df['Close'], p.ma_type, p.ma_length)
   ```
   - Replace EACH indicator calculation one at a time
   - Run comparison after EACH replacement
   - Expected: EXACT match (if indicator extraction was correct in Phase 5)

3. **Step 3: Refactor internal structure (optional)** (2-3 hours)
   - Extract methods: `_calculate_indicators()`, `_process_bar()`, etc.
   - This is OPTIONAL - only do if it improves clarity
   - Test after each refactor

4. **Step 4: Final validation** (2-4 hours)
   - Run extensive comparison tests
   - Test with multiple parameter combinations
   - Test edge cases (long/short trails, different MA types)

#### 7.3: Comprehensive Comparison Testing (4-6 hours)

**Critical comparison function:**

```python
# tests/test_s01_migration.py
def test_s01_legacy_vs_migrated():
    """Compare legacy and migrated S01 - MUST be bit-exact"""
    df = load_baseline_data()
    params = load_baseline_params()

    # Run legacy
    legacy_result = S01TrailingMA.run(df, params, trade_start_idx=0)

    # Run migrated
    migrated_result = S01TrailingMAMigrated.run(df, params, trade_start_idx=0)

    # MUST be bit-exact
    assert legacy_result.net_profit_pct == migrated_result.net_profit_pct
    assert legacy_result.max_drawdown_pct == migrated_result.max_drawdown_pct
    assert legacy_result.total_trades == migrated_result.total_trades

    # Compare trades one-by-one
    for t1, t2 in zip(legacy_result.trades, migrated_result.trades):
        assert t1.entry_time == t2.entry_time
        assert t1.exit_time == t2.exit_time
        assert abs(t1.net_pnl - t2.net_pnl) < 1e-6
```

### Validation Checklist

- [ ] Migrated strategy runs without errors
- [ ] Legacy vs migrated comparison: EXACT match (tolerance < 1e-6)
- [ ] All 11 MA types tested
- [ ] All stop types tested (ATR, max DD, max days)
- [ ] Both position sizing modes tested (fixed, percent)
- [ ] Multiple parameter combinations tested
- [ ] Baseline regression test passes with migrated version
- [ ] Optuna optimization produces similar scores
- [ ] Performance acceptable (not degraded)

### Deliverables

- [ ] `strategies/s01_trailing_ma_migrated/` created
- [ ] S01Params dataclass in strategy.py
- [ ] Logic migrated from run_strategy()
- [ ] Uses indicators.* instead of inline calculations
- [ ] `tests/test_s01_migration.py` with comprehensive tests
- [ ] Regression test: legacy vs migrated (exact match)
- [ ] All Optuna trials produce similar scores
- [ ] Git commit: "Phase 7: S01 migration to new architecture"

### Success Criteria

- Bit-exact match between legacy and migrated (tolerance < 1e-6)
- All baseline tests pass
- S01 fully functional in new architecture
- Legacy S01 kept for reference (not deleted yet)
- Performance maintained or improved

### Notes

⚠️ **Do NOT delete legacy code in this phase.** Legacy cleanup happens in Phase 9 after UI is fixed in Phase 8.

---

## Phase 8: Dynamic Optimizer + CSS Extraction (NEW)

**Complexity:** 🟡 MEDIUM
**Risk:** 🟡 MEDIUM
**Estimated Effort:** 8-12 hours
**Priority:** 🔴 CRITICAL - FIXES PRODUCTION BLOCKER

### Goal

Fix the hardcoded S01 parameters in the optimizer UI and make parameter loading fully dynamic for ANY strategy. Also extract CSS as preparatory work for Phase 10.

### Why This Phase Was Added

**Phase 6 Audit Finding:** The optimizer UI has hardcoded S01 parameters:
- Hardcoded HTML controls (lines 1455-1829 in index.html, ~374 lines)
- Hardcoded JavaScript array `OPTIMIZATION_PARAMETERS` (lines 2668-2840, ~172 lines)

**Impact:**
- When S04 is selected, optimizer shows S01 parameters instead of S04 parameters
- Blocks production use of S04
- Will block any future strategy additions
- Must be fixed BEFORE deleting legacy code in Phase 9

**Solution:** Make optimizer dynamically load parameters from strategy config.json, just like the backtest form already does.

### Current vs Target Architecture

**Current (Broken):**
```
User selects S04 → Backtest form loads S04 params ✅
                 → Optimizer form shows S01 params ❌ (hardcoded HTML)
```

**Target (Fixed):**
```
User selects S04 → Backtest form loads S04 params ✅
                 → Optimizer form loads S04 params ✅ (dynamic from config.json)
```

### Audit of Hardcoded S01 References

#### Backend (server.py) - 19 S01-specific blocks:
- `DEFAULT_PRESET` dict (lines 75-130) - S01 parameters as defaults
- `MA_TYPES` tuple (lines 25-37) - shared, but referenced by S01 logic
- Default strategy ID: `"s01_trailing_ma"` (lines 596, 962, 1163, 1503)
- S01-specific parameter handling (lines 678-693, 1198-1215, 1341-1347)

#### Frontend (index.html) - Major hardcoded sections:
- Optimizer HTML controls (lines 1455-1829, ~374 lines)
- `OPTIMIZATION_PARAMETERS` array (lines 2668-2840, 19 parameters, ~172 lines)
- MA type checkboxes (hardcoded for S01 trend/trail MA selection)

**Total:** ~550 lines of S01-specific hardcoded UI code

### Steps

#### 8.1: Extract CSS to Separate File (2-3 hours)

This is preparatory work for Phase 10, but doing it now makes the next steps easier.

1. **Create CSS directory:**
   ```bash
   mkdir -p src/static/css
   ```

2. **Extract all `<style>` blocks from index.html:**
   - Find all style blocks in index.html
   - Move to `src/static/css/style.css`
   - Keep CSS exactly as is (no refactoring yet)

3. **Update index.html:**
   ```html
   <head>
       <link rel="stylesheet" href="/static/css/style.css">
   </head>
   ```

4. **Update Flask static serving:**
   ```python
   # src/server.py
   app = Flask(__name__, static_folder='static', static_url_path='/static')
   ```

5. **Test:**
   - Start server: `python src/server.py`
   - Verify page loads and looks identical
   - Check browser DevTools for CSS loading correctly

#### 8.2: Create Dynamic Optimizer Form Generator (4-6 hours)

**Goal:** Replace hardcoded optimizer HTML with dynamic generation from config.json.

1. **Replace hardcoded optimizer HTML with container:**

Find this section in index.html (lines ~1454-1829):
```html
<!-- OLD: Hardcoded S01 parameters -->
<div class="opt-row">
  <input id="opt-maLength" type="checkbox" checked />
  <label class="opt-label" for="opt-maLength">T MA Length</label>
  ...
</div>
```

Replace with:
```html
<!-- NEW: Dynamic container -->
<div id="optimizerParamsContainer">
  <!-- Parameters will be generated dynamically here -->
</div>
```

2. **Create `generateOptimizerForm()` function:**

```javascript
/**
 * Generate optimizer parameters form from strategy config
 * Only shows parameters where optimize.enabled === true
 */
function generateOptimizerForm(config) {
  const container = document.getElementById('optimizerParamsContainer');
  if (!container) {
    console.error('Optimizer container not found');
    return;
  }

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
}

/**
 * Create a single optimizer parameter row
 */
function createOptimizerRow(paramName, paramDef) {
  const row = document.createElement('div');
  row.className = 'opt-row';

  // Checkbox
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.id = `opt-${paramName}`;
  checkbox.checked = paramDef.optimize.enabled || false;

  const label = document.createElement('label');
  label.className = 'opt-label';
  label.htmlFor = `opt-${paramName}`;
  label.textContent = paramDef.label || paramName;

  // Controls div (from, to, step)
  const controlsDiv = document.createElement('div');
  controlsDiv.className = 'opt-controls';

  // From input
  const fromLabel = document.createElement('label');
  fromLabel.textContent = 'From:';
  const fromInput = document.createElement('input');
  fromInput.className = 'tiny-input';
  fromInput.id = `opt-${paramName}-from`;
  fromInput.type = 'number';
  fromInput.value = paramDef.optimize.min !== undefined ? paramDef.optimize.min : paramDef.min;
  fromInput.step = paramDef.optimize.step || paramDef.step || (paramDef.type === 'int' ? '1' : '0.1');

  // To input
  const toLabel = document.createElement('label');
  toLabel.textContent = 'To:';
  const toInput = document.createElement('input');
  toInput.className = 'tiny-input';
  toInput.id = `opt-${paramName}-to`;
  toInput.type = 'number';
  toInput.value = paramDef.optimize.max !== undefined ? paramDef.optimize.max : paramDef.max;
  toInput.step = paramDef.optimize.step || paramDef.step || (paramDef.type === 'int' ? '1' : '0.1');

  // Step input
  const stepLabel = document.createElement('label');
  stepLabel.textContent = 'Step:';
  const stepInput = document.createElement('input');
  stepInput.className = 'tiny-input';
  stepInput.id = `opt-${paramName}-step`;
  stepInput.type = 'number';
  stepInput.value = paramDef.optimize.step || paramDef.step || (paramDef.type === 'int' ? '1' : '0.1');
  stepInput.step = paramDef.type === 'int' ? '1' : '0.01';
  stepInput.min = paramDef.type === 'int' ? '1' : '0.01';

  controlsDiv.appendChild(fromLabel);
  controlsDiv.appendChild(fromInput);
  controlsDiv.appendChild(toLabel);
  controlsDiv.appendChild(toInput);
  controlsDiv.appendChild(stepLabel);
  controlsDiv.appendChild(stepInput);

  row.appendChild(checkbox);
  row.appendChild(label);
  row.appendChild(controlsDiv);

  return row;
}
```

3. **Update `loadStrategyConfig()` to call generator:**

```javascript
async function loadStrategyConfig(strategyId) {
  try {
    const response = await fetch(`/api/strategies/${strategyId}/config`);
    currentStrategyConfig = await response.json();

    updateStrategyInfo(currentStrategyConfig);
    generateBacktestForm(currentStrategyConfig);
    generateOptimizerForm(currentStrategyConfig);  // ← ADD THIS LINE

    console.log(`Loaded strategy: ${currentStrategyConfig.name}`);
  } catch (error) {
    console.error('Failed to load strategy config:', error);
    alert('Error loading strategy configuration');
  }
}
```

4. **Delete hardcoded `OPTIMIZATION_PARAMETERS` array:**

Remove lines 2668-2840 entirely. This array is no longer needed.

5. **Update `bindOptimizerInputs()` function:**

Make it work with dynamically generated IDs:

```javascript
function bindOptimizerInputs() {
  // Get all optimizer checkboxes dynamically
  const checkboxes = document.querySelectorAll('[id^="opt-"]:not([id$="-from"]):not([id$="-to"]):not([id$="-step"])');

  checkboxes.forEach(checkbox => {
    checkbox.addEventListener('change', function() {
      const paramName = this.id.replace('opt-', '');
      const fromInput = document.getElementById(`opt-${paramName}-from`);
      const toInput = document.getElementById(`opt-${paramName}-to`);
      const stepInput = document.getElementById(`opt-${paramName}-step`);

      if (fromInput && toInput && stepInput) {
        const disabled = !this.checked;
        fromInput.disabled = disabled;
        toInput.disabled = disabled;
        stepInput.disabled = disabled;
      }
    });
  });
}
```

6. **Update optimization payload collection:**

Modify the function that collects optimizer parameters to work dynamically:

```javascript
function collectOptimizerParams() {
  const params = {};
  const ranges = {};

  // Get all optimizer checkboxes
  const checkboxes = document.querySelectorAll('[id^="opt-"]:not([id$="-from"]):not([id$="-to"]):not([id$="-step"])');

  checkboxes.forEach(checkbox => {
    if (checkbox.checked) {
      const paramName = checkbox.id.replace('opt-', '');
      const fromValue = parseFloat(document.getElementById(`opt-${paramName}-from`).value);
      const toValue = parseFloat(document.getElementById(`opt-${paramName}-to`).value);
      const stepValue = parseFloat(document.getElementById(`opt-${paramName}-step`).value);

      ranges[paramName] = [fromValue, toValue, stepValue];
    }
  });

  return ranges;
}
```

#### 8.3: Testing (2-3 hours)

1. **Test with S01:**
   - Select S01 from dropdown
   - Verify optimizer shows S01 parameters
   - Verify checkboxes, from/to/step inputs work
   - Run small Optuna optimization (10 trials)
   - Verify results

2. **Test with S04:**
   - Select S04 from dropdown
   - Verify optimizer shows S04 parameters (6 optimizable params)
   - Verify only enabled parameters shown
   - Run small Optuna optimization (10 trials)
   - Verify results

3. **Test edge cases:**
   - Switch between strategies multiple times
   - Verify no JavaScript errors in console
   - Test with missing optimize config (should handle gracefully)

### Deliverables

- [ ] CSS extracted to `src/static/css/style.css`
- [ ] Flask static serving configured
- [ ] Hardcoded optimizer HTML removed
- [ ] Dynamic container added
- [ ] `generateOptimizerForm()` function implemented
- [ ] `createOptimizerRow()` helper function implemented
- [ ] `loadStrategyConfig()` updated to generate optimizer form
- [ ] `OPTIMIZATION_PARAMETERS` array deleted
- [ ] `bindOptimizerInputs()` updated for dynamic IDs
- [ ] Optimizer payload collection updated
- [ ] Manual testing completed for S01 and S04
- [ ] Optimizer works with both strategies
- [ ] Git commit: "Phase 8: Dynamic optimizer + CSS extraction"

### Success Criteria

- ✅ S01 optimizer shows S01 parameters
- ✅ S04 optimizer shows S04 parameters (rsiLen, stochLen, obLevel, osLevel, extLookback, confirmBars)
- ✅ Switching strategies updates optimizer form correctly
- ✅ Optuna optimization works with both strategies
- ✅ CSS extracted successfully, page looks identical
- ✅ No JavaScript errors in browser console

### UI Status After This Phase

- ✅ Backtest form: Dynamic, works for all strategies
- ✅ Optimizer form: Dynamic, works for all strategies
- ❌ UI structure: Still monolithic (4746-line index.html)
- ⚠️ Legacy code: Still present in backend and frontend

**Note:** UI will be fully functional for S01 and S04. Legacy code cleanup happens in Phase 9.

---

## Phase 9: Legacy Code Cleanup (NEW)

**Complexity:** 🟡 MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 4-6 hours
**Priority:** ✅ SAFE - UI IS ALREADY DYNAMIC

### Goal

Delete all hardcoded S01-specific blocks from backend and frontend now that UI is fully dynamic. Leave a clean codebase for Phase 10 (Frontend Separation).

### Why This Phase Was Added

After Phase 8, the UI is fully dynamic and no longer depends on hardcoded S01 parameters. Now it's safe to delete all legacy S01-specific code without breaking functionality.

### What Gets Deleted

#### Backend (server.py):

1. **DEFAULT_PRESET dict** (lines 75-130)
   - Replace with empty dict or minimal generic defaults
   - Or load from default preset file

2. **Default strategy ID hardcoding:**
   - Line 596: `strategy_id = request.form.get("strategy", "s01_trailing_ma")`
   - Line 962: `strategy_id = request.form.get("strategy", "s01_trailing_ma")`
   - Line 1163: `strategy_id = "s01_trailing_ma"`
   - Line 1503: `strategy_id = request.form.get("strategy", "s01_trailing_ma")`

   Replace with:
   ```python
   strategy_id = request.form.get("strategy")
   if not strategy_id:
       return jsonify({"error": "No strategy specified"}), 400
   ```

3. **S01-specific parameter handling:**
   - Lines 678-693: Hardcoded ma_length, trail_length checks for warmup calculation
   - Lines 1198-1215: Hardcoded MA type mappings (ma_types_trend, ma_types_trail_long, etc.)
   - Lines 1341-1347: Hardcoded trail type locking logic

   **Decision:** Keep if generic enough, delete if S01-specific. Evaluate case-by-case.

4. **MA_TYPES tuple** (lines 25-37):
   - **Keep:** This is shared across strategies, not S01-specific
   - Could be moved to a constants file later

5. **BOOL_FIELDS, INT_FIELDS, FLOAT_FIELDS, LIST_FIELDS:**
   - Lines 131-161: S01-specific field definitions for preset system
   - **Decision:** Keep for now (presets deferred to later cleanup)

#### Frontend (index.html):

1. **Already deleted in Phase 8:**
   - Hardcoded optimizer HTML (was lines 1455-1829)
   - `OPTIMIZATION_PARAMETERS` array (was lines 2668-2840)

2. **Additional cleanup:**
   - Search for any remaining S01-specific comments
   - Search for hardcoded parameter references
   - Clean up unused JavaScript functions

### Steps

#### 9.1: Backend Cleanup (2-3 hours)

1. **Update default strategy handling:**

```python
# OLD (lines 596, 962, 1163, 1503):
strategy_id = request.form.get("strategy", "s01_trailing_ma")

# NEW:
strategy_id = request.form.get("strategy")
if not strategy_id:
    available_strategies = list_strategies()
    if available_strategies:
        strategy_id = available_strategies[0]['id']  # Use first available
    else:
        return jsonify({"error": "No strategies available"}), 500
```

2. **Simplify DEFAULT_PRESET:**

```python
# OLD (lines 75-130): Hardcoded S01 parameters

# NEW: Minimal generic defaults
DEFAULT_PRESET: Dict[str, Any] = {
    "dateFilter": True,
    "backtester": True,
    "startDate": "2025-04-01",
    "startTime": "00:00",
    "endDate": "2025-09-01",
    "endTime": "00:00",
}
```

3. **Clean up S01-specific warmup calculation:**

Lines 678-693 have hardcoded parameter names:
```python
# OLD:
if "maLength" in param_ranges:
    max_ma_length = max(max_ma_length, int(param_ranges["maLength"][1]))
if "trailLongLength" in param_ranges:
    max_ma_length = max(max_ma_length, int(param_ranges["trailLongLength"][1]))
```

**Decision:**
- Option A: Delete entirely (let each strategy handle warmup)
- Option B: Make generic (scan all int parameters for "length" in name)
- **Recommended:** Option A - delete, revisit warmup handling in future

4. **Clean up MA type handling:**

Lines 1198-1215 have S01-specific MA type mappings:
```python
ma_types_trend = payload.get("ma_types_trend") or payload.get("maTypesTrend") or []
ma_types_trail_long = payload.get("ma_types_trail_long") or ...
```

**Decision:** Keep if generic enough for other strategies, delete if S01-specific.

5. **Search for remaining S01 references:**

```bash
grep -n "s01\|S01\|S_01" src/server.py
```

Delete or genericize any remaining hardcoded references.

#### 9.2: Frontend Cleanup (1-2 hours)

1. **Verify all hardcoded HTML is gone:**

```bash
grep -n "opt-maLength\|opt-closeCount\|opt-stop\|opt-trail" src/index.html
```

Should return NO results (deleted in Phase 8).

2. **Search for S01-specific comments:**

```bash
grep -i "s01\|trailing.*ma\|legacy" src/index.html
```

Remove any legacy comments or references.

3. **Clean up unused JavaScript:**

Search for functions that reference deleted elements:
- Old optimizer binding code
- Hardcoded parameter lists

#### 9.3: Delete Legacy S01 Implementation (1 hour)

Now that S01 is migrated (Phase 7), delete the legacy version:

```bash
# Promote migrated to production
mv src/strategies/s01_trailing_ma src/strategies/s01_trailing_ma_legacy_backup
mv src/strategies/s01_trailing_ma_migrated src/strategies/s01_trailing_ma

# Update strategy_id in config.json back to "s01_trailing_ma"
# Update STRATEGY_ID in strategy.py back to "s01_trailing_ma"
```

**Important:** Keep `s01_trailing_ma_legacy_backup` for one more phase, just in case. Delete in Phase 11 documentation phase.

#### 9.4: Delete run_strategy() from backtest_engine.py (30 min)

This is the final step - removing S01-specific logic from core:

```python
# src/core/backtest_engine.py

# DELETE: The ~300 line run_strategy() function
# This function is S01-specific and no longer needed
```

After deletion:
- backtest_engine.py is truly generic
- No strategy-specific logic in core
- Clean separation of concerns achieved

#### 9.5: Testing (1 hour)

1. **Run full test suite:**
   ```bash
   pytest tests/ -v
   ```

   Should show 70+ tests passing (including S01 migrated and S04).

2. **Manual UI testing:**
   - Start server
   - Test S01 (migrated version)
   - Test S04
   - Test preset save/load
   - Test Optuna optimization for both strategies

3. **Verify no hardcoded references remain:**
   ```bash
   grep -r "s01_trailing_ma" src/ --include="*.py" --include="*.html" --include="*.js"
   ```

   Should only find:
   - Strategy folder name
   - References in generic code (list_strategies, etc.)
   - No hardcoded defaults

### Deliverables

- [ ] Backend default strategy handling genericized
- [ ] DEFAULT_PRESET simplified
- [ ] S01-specific warmup code removed
- [ ] MA type handling cleaned up
- [ ] All S01 references removed from server.py
- [ ] Frontend verified clean (no hardcoded HTML)
- [ ] Unused JavaScript removed
- [ ] Legacy S01 renamed to backup
- [ ] Migrated S01 promoted to production
- [ ] run_strategy() deleted from backtest_engine.py
- [ ] All tests passing
- [ ] Manual UI testing completed
- [ ] Git commit: "Phase 9: Delete all legacy S01 code"

### Success Criteria

- ✅ No S01-specific hardcoded references in backend
- ✅ No S01-specific hardcoded references in frontend
- ✅ backtest_engine.py is truly generic (no run_strategy())
- ✅ Both S01 and S04 work correctly in UI
- ✅ All tests passing
- ✅ Codebase clean and maintainable

### Code Status After This Phase

- ✅ S01: Fully migrated to new architecture
- ✅ S04: Working in new architecture
- ✅ Backend: Clean, no hardcoded S01 blocks
- ✅ Frontend: Dynamic, no hardcoded parameters
- ❌ UI structure: Still monolithic (need Phase 10)

---

## Phase 10: Full Frontend Separation

**Complexity:** 🟡 MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 6-8 hours
**Priority:** ✅ CLEAN ARCHITECTURE

### Goal

Complete the frontend separation by moving all HTML, CSS, and JavaScript into proper module structure as defined in PROJECT_STRUCTURE.md.

### Why Now

After Phase 9, all legacy code is gone and UI is fully dynamic. Now it's safe to restructure the frontend without worrying about breaking hardcoded dependencies.

### Target Structure

```
src/ui/
├── server.py                    # Flask app (already in src/)
├── templates/
│   └── index.html               # Clean HTML only (~500 lines)
└── static/
    ├── css/
    │   └── style.css            # Already extracted in Phase 8
    └── js/
        ├── main.js              # App initialization
        ├── api.js               # API calls
        ├── ui-handlers.js       # Event handlers
        └── strategy-config.js   # Strategy loading and form generation
```

### Steps

#### 10.1: Create UI Directory Structure (30 min)

```bash
mkdir -p src/ui/templates
mkdir -p src/ui/static/js
# Note: src/static/css already exists from Phase 8
mv src/static src/ui/static
```

#### 10.2: Move and Clean HTML (2-3 hours)

1. **Extract JavaScript from index.html:**
   - Find all `<script>` blocks
   - Split into logical modules:
     - `main.js` - Initialization, global variables
     - `api.js` - Fetch calls to backend
     - `ui-handlers.js` - Event listeners, button clicks
     - `strategy-config.js` - loadStrategyConfig, generateBacktestForm, generateOptimizerForm

2. **Move HTML to templates:**
   ```bash
   mv src/index.html src/ui/templates/index.html
   ```

3. **Clean HTML:**
   - Remove all `<style>` blocks (already in style.css)
   - Remove all `<script>` blocks (moved to JS files)
   - Add script tags:
   ```html
   <script src="/static/js/api.js"></script>
   <script src="/static/js/strategy-config.js"></script>
   <script src="/static/js/ui-handlers.js"></script>
   <script src="/static/js/main.js"></script>
   ```

#### 10.3: Move Server.py (30 min)

```bash
mv src/server.py src/ui/server.py
```

Update Flask configuration:
```python
# src/ui/server.py
app = Flask(__name__,
            static_folder='static',
            template_folder='templates')
```

Update imports:
```python
# OLD:
from core.backtest_engine import ...

# NEW:
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.backtest_engine import ...
```

Or use proper package structure with `__init__.py`.

#### 10.4: Modularize JavaScript (3-4 hours)

**api.js:**
```javascript
// All fetch calls to backend
async function fetchStrategies() { ... }
async function fetchStrategyConfig(strategyId) { ... }
async function runBacktest(payload) { ... }
async function runOptimization(payload) { ... }
```

**strategy-config.js:**
```javascript
// Strategy configuration and form generation
let currentStrategyConfig = null;
let currentStrategyId = null;

async function loadStrategyConfig(strategyId) { ... }
function generateBacktestForm(config) { ... }
function generateOptimizerForm(config) { ... }
function createFormField(paramName, paramDef, prefix) { ... }
function createOptimizerRow(paramName, paramDef) { ... }
```

**ui-handlers.js:**
```javascript
// Event listeners and UI interactions
function bindOptimizerInputs() { ... }
function handleStrategyChange() { ... }
function handleBacktestSubmit() { ... }
function handleOptimizationSubmit() { ... }
```

**main.js:**
```javascript
// Initialization and global setup
document.addEventListener('DOMContentLoaded', async () => {
    await loadStrategies();
    // ... other initialization
});
```

#### 10.5: Update Import Paths (1 hour)

All Python imports need to be updated:
```python
# In tests, run_backtest.py, etc.
# OLD:
from core.backtest_engine import ...

# NEW:
from ui.server import ...
```

Or restructure project to use proper package imports.

#### 10.6: Testing (1-2 hours)

1. **Start server from new location:**
   ```bash
   cd src
   python ui/server.py
   # OR
   cd src/ui
   python server.py
   ```

2. **Test all UI functionality:**
   - [ ] Page loads correctly
   - [ ] CSS applied correctly
   - [ ] JavaScript loads without errors
   - [ ] Strategy selection works
   - [ ] Backtest form generation works
   - [ ] Optimizer form generation works
   - [ ] Single backtest execution works
   - [ ] Optimization execution works
   - [ ] Results display correctly
   - [ ] Preset save/load works

3. **Browser DevTools checks:**
   - No console errors
   - All assets load (CSS, JS)
   - Network tab shows successful API calls

### Deliverables

- [ ] `src/ui/` directory structure created
- [ ] HTML moved to `templates/index.html` and cleaned
- [ ] CSS already in `static/css/style.css` (from Phase 8)
- [ ] JavaScript modularized into `static/js/*.js`
- [ ] `server.py` moved to `ui/server.py`
- [ ] Flask configuration updated
- [ ] All imports updated
- [ ] Full UI smoke test completed
- [ ] No console errors in browser
- [ ] Git commit: "Phase 10: Full frontend separation"

### Success Criteria

- ✅ UI looks and behaves exactly as before
- ✅ No functional regressions
- ✅ Clean separation of concerns (HTML/CSS/JS/Python)
- ✅ Follows PROJECT_STRUCTURE.md
- ✅ Easy to maintain and modify
- ✅ All tests passing

### Architecture Achievement

After this phase:
- ✅ Clean core architecture
- ✅ Strategies in separate modules
- ✅ Indicators extracted
- ✅ Metrics centralized
- ✅ Export unified
- ✅ UI fully separated
- ✅ No legacy code

**Migration complete!** Only documentation remains (Phase 11).

---

## Phase 11: Documentation

**Complexity:** 🟢 LOW
**Risk:** 🟢 LOW
**Estimated Effort:** 4-6 hours
**Priority:** ✅ FINALIZATION

### Goal

Update all documentation to reflect the final migrated state. NO logging implementation (deferred to post-migration).

### Why No Logging

Logging is a nice-to-have feature, not critical for architecture migration completion. Adding it now would:
- Extend migration timeline
- Add complexity
- Distract from documentation focus

**Decision:** Defer logging to post-migration updates. Focus on completing migration first.

### Steps

#### 11.1: Update Architecture Documentation (2 hours)

1. **PROJECT_TARGET_ARCHITECTURE.md:**
   ```markdown
   # Target Architecture Overview

   **Status:** ✅ CURRENT IMPLEMENTATION (as of 2025-12-03)

   This document describes the CURRENT architecture after migration completion.

   ## Changes from Legacy:
   - [x] Core engines separated into src/core/
   - [x] Metrics centralized in metrics.py
   - [x] Indicators extracted to indicators/ package
   - [x] Export centralized in export.py
   - [x] S01 migrated to new architecture
   - [x] S04 implemented in new architecture
   - [x] Grid Search removed (Optuna only)
   - [x] Frontend fully separated (HTML/CSS/JS modules)
   - [x] All legacy code removed
   ```

2. **PROJECT_STRUCTURE.md:**
   - Update directory tree to reflect actual structure
   - Document all file locations
   - Update component descriptions

3. **CLAUDE.md:**
   ```markdown
   ## Architecture (Updated 2025-12-03)

   ### Completed Migration ✅

   The project has completed its architecture migration from legacy
   S01-centric design to clean modular architecture.

   **Key Changes:**
   - Core engines in `src/core/`
   - Strategies in `src/strategies/` (S01, S04)
   - Indicators in `src/indicators/`
   - Metrics in `src/core/metrics.py`
   - Export in `src/core/export.py`
   - UI in `src/ui/` (fully separated)

   **Grid Search Removed:** Use Optuna for all optimization.
   ```

#### 11.2: Update Migration Documentation (1-2 hours)

1. **This document (PROJECT_MIGRATION_PLAN_upd.md):**
   - Mark all phases as COMPLETE
   - Add "Migration Complete" banner at top
   - Update status from "Ready for Execution" to "Completed"

2. **MIGRATION_PROGRESS.md:**
   - Mark all phases complete with dates
   - Update overall progress to 100%
   - Add final summary section

3. **Create MIGRATION_SUMMARY.md:**
   ```markdown
   # Migration Summary

   **Started:** 2025-11-28
   **Completed:** 2025-12-0X
   **Duration:** X weeks
   **Total Phases:** 11

   ## What Was Achieved

   - ✅ Clean architecture with separated concerns
   - ✅ 2 strategies working (S01, S04)
   - ✅ All legacy code removed
   - ✅ UI fully dynamic and modular
   - ✅ 70+ tests passing
   - ✅ Performance maintained

   ## Breaking Changes

   - Grid Search removed (use Optuna)
   - Import paths changed (use core.*)
   - UI structure changed (now in src/ui/)

   ## Migration to Future Versions

   See docs/ADDING_NEW_STRATEGY.md for how to add strategies.
   ```

#### 11.3: Create Strategy Development Guide (2 hours)

1. **docs/ADDING_NEW_STRATEGY.md:**
   ```markdown
   # Adding a New Strategy

   ## Overview

   After migration, adding new strategies is straightforward:
   1. Create strategy directory
   2. Define parameters dataclass
   3. Implement strategy logic
   4. Create config.json
   5. Test

   ## Step-by-Step Guide

   ### 1. Create Directory Structure

   ```bash
   mkdir src/strategies/my_strategy
   touch src/strategies/my_strategy/__init__.py
   touch src/strategies/my_strategy/strategy.py
   touch src/strategies/my_strategy/config.json
   ```

   ### 2. Define Parameters

   ```python
   # src/strategies/my_strategy/strategy.py
   from dataclasses import dataclass
   from typing import Dict, Any

   @dataclass
   class MyStrategyParams:
       param1: int = 10
       param2: float = 1.5

       @classmethod
       def from_dict(cls, d: Dict[str, Any]) -> "MyStrategyParams":
           return cls(
               param1=int(d.get('param1', 10)),
               param2=float(d.get('param2', 1.5)),
           )

       def to_dict(self) -> Dict[str, Any]:
           return {
               'param1': self.param1,
               'param2': self.param2,
           }
   ```

   ### 3. Implement Strategy

   ```python
   from strategies.base import BaseStrategy
   from core.backtest_engine import StrategyResult, TradeRecord

   class MyStrategy(BaseStrategy):
       STRATEGY_ID = "my_strategy"
       STRATEGY_NAME = "My Strategy"
       STRATEGY_VERSION = "v1"

       @staticmethod
       def run(df: pd.DataFrame, params: Dict[str, Any],
               trade_start_idx: int = 0) -> StrategyResult:
           p = MyStrategyParams.from_dict(params)

           # Calculate indicators
           from indicators.ma import sma
           ma = sma(df['Close'], p.param1)

           # Bar-by-bar simulation
           trades = []
           for i in range(trade_start_idx, len(df)):
               # Your logic here
               pass

           # Build result
           result = StrategyResult(
               trades=trades,
               equity_curve=[],
               balance_curve=[],
               timestamps=[],
           )

           # Calculate metrics
           from core import metrics
           basic = metrics.calculate_basic(result, initial_balance=100.0)
           advanced = metrics.calculate_advanced(result)

           result.net_profit_pct = basic.net_profit_pct
           result.max_drawdown_pct = basic.max_drawdown_pct
           result.total_trades = basic.total_trades
           result.sharpe_ratio = advanced.sharpe_ratio

           return result
   ```

   ### 4. Create config.json

   ```json
   {
     "id": "my_strategy",
     "name": "My Strategy",
     "version": "v1",
     "description": "Description here",
     "parameters": {
       "param1": {
         "type": "int",
         "label": "Parameter 1",
         "default": 10,
         "min": 1,
         "max": 100,
         "step": 1,
         "group": "Main",
         "optimize": {
           "enabled": true,
           "min": 5,
           "max": 50,
           "step": 5
         }
       },
       "param2": {
         "type": "float",
         "label": "Parameter 2",
         "default": 1.5,
         "min": 0.0,
         "max": 10.0,
         "step": 0.1,
         "group": "Main",
         "optimize": {
           "enabled": false
         }
       }
     }
   }
   ```

   ### 5. Test

   ```python
   # tests/test_my_strategy.py
   def test_my_strategy_basic():
       df = load_test_data()
       params = {'param1': 10, 'param2': 1.5}
       result = MyStrategy.run(df, params)

       assert result is not None
       assert len(result.trades) >= 0
   ```

   ### 6. Use in UI

   The strategy will automatically appear in the UI dropdown after restart.
   No UI changes needed - parameters load dynamically from config.json!
   ```

2. **docs/CONFIG_JSON_FORMAT.md:**
   - Document complete config.json specification
   - Include all parameter types
   - Document optimization section
   - Provide examples

#### 11.4: Update Changelog (30 min)

```markdown
# Changelog

## [2.0.0] - 2025-12-0X - Architecture Migration Complete

### Major Changes

- **Architecture Migration:** Completed 11-phase migration from legacy to clean architecture
- **Strategies:** S01 migrated, S04 added (StochRSI)
- **Optimizer:** Grid Search removed, Optuna-only
- **UI:** Fully dynamic parameter loading, separated frontend
- **Core:** Metrics centralized, indicators extracted, export unified
- **Legacy:** All hardcoded S01 code removed

### Breaking Changes

- Grid Search no longer available
- optimizer_engine.py removed
- Import paths changed (use `core.*`, not root imports)
- UI moved to `src/ui/`
- StrategyParams now lives in each strategy module
- Frontend structure changed (HTML/CSS/JS separated)

### New Features

- Dynamic optimizer form generation (works with any strategy)
- Strategy auto-discovery system
- Comprehensive test suite (70+ tests)
- S04 StochRSI strategy
- RSI and StochRSI indicators

### Bug Fixes

- Fixed optimizer showing wrong parameters for different strategies
- Fixed baseline mismatch (UTC timezone issue)
- Fixed various Phase 6 audit issues

### Migration Notes

- See docs/PROJECT_MIGRATION_PLAN_upd.md for full migration details
- All functionality preserved, just reorganized
- Performance maintained or improved
- No data loss or behavioral changes for S01

### Documentation

- Updated all architecture docs
- Added strategy development guide
- Added config.json format specification
- Created migration summary

### Future Work (Deferred)

- Logging system (post-migration)
- WFA optimization
- Preset system overhaul
- Additional strategies
```

#### 11.5: Clean Up Temporary Files (30 min)

Delete backup and temporary files:
```bash
# Delete legacy S01 backup (kept through Phase 10 for safety)
rm -rf src/strategies/s01_trailing_ma_legacy_backup

# Delete any .bak files
find . -name "*.bak" -delete

# Delete any temporary test files
find . -name "*_old.py" -delete
find . -name "*_tmp.py" -delete
```

### Deliverables

- [ ] PROJECT_TARGET_ARCHITECTURE.md updated
- [ ] PROJECT_STRUCTURE.md updated
- [ ] CLAUDE.md updated
- [ ] PROJECT_MIGRATION_PLAN_upd.md marked complete
- [ ] MIGRATION_PROGRESS.md marked complete
- [ ] MIGRATION_SUMMARY.md created
- [ ] docs/ADDING_NEW_STRATEGY.md created
- [ ] docs/CONFIG_JSON_FORMAT.md created
- [ ] Changelog.md updated
- [ ] Temporary files cleaned up
- [ ] Git commit: "Phase 11: Documentation complete - Migration finished"
- [ ] Git tag: `migration-v2-complete`

### Success Criteria

- ✅ All documentation reflects current state
- ✅ Easy for new contributors to understand
- ✅ Clear guide for adding new strategies
- ✅ Migration history documented
- ✅ No outdated references to legacy architecture
- ✅ Clean repository (no temporary files)

---

## Summary of Phase Order (v2.1)

### Updated Phase Sequence:

- ✅ Phase -1: Test Infrastructure
- ✅ Phase 0: Regression Baseline
- ✅ Phase 1: Core Extraction
- ✅ Phase 2: Export Extraction
- ✅ Phase 3: Grid Search Removal
- ✅ Phase 4: Metrics Extraction
- ✅ Phase 5: Indicators Extraction
- ✅ Phase 6: S04 Strategy Testing
- ⏳ Phase 7: S01 Migration
- 🆕 Phase 8: Dynamic Optimizer + CSS (NEW)
- 🆕 Phase 9: Legacy Code Cleanup (NEW)
- ⏳ Phase 10: Frontend Separation (was Phase 8)
- ⏳ Phase 11: Documentation (was Phase 9, no logging)

### Key Differences from v2.0:

1. **Phase 8 (NEW):** Fix hardcoded optimizer parameters + extract CSS
2. **Phase 9 (NEW):** Delete all legacy S01 code safely
3. **Phase 10:** Frontend separation moved later (was Phase 8)
4. **Phase 11:** Documentation only, no logging

### Rationale:

The v2.1 plan fixes the **critical UI issue** discovered in Phase 6 audit by:
1. Making UI dynamic BEFORE deleting legacy (Phase 8)
2. Deleting legacy AFTER UI is fixed (Phase 9)
3. Restructuring frontend AFTER legacy is gone (Phase 10)

This ensures UI remains functional throughout and cleanup is safe.

---

## Timeline Estimates

**Optimistic Scenario:**
- Phases 7-11: 38-52 hours = 5-7 workdays = **1-1.5 weeks full-time**

**Realistic Scenario:**
- Phases 7-11: 52-68 hours = 7-9 workdays = **1.5-2 weeks full-time**

**Total Migration (Phases -1 through 11):**
- Optimistic: 90-110 hours = **2-2.5 weeks full-time**
- Realistic: 110-140 hours = **2.5-3.5 weeks full-time**

---

## Risk Matrix (Updated)

| Phase | Complexity | Risk | Failure Impact | Status |
|-------|-----------|------|----------------|--------|
| Phase -1 | 🟢 LOW | 🟢 LOW | 🟢 Low | ✅ COMPLETE |
| Phase 0 | 🟡 MED | 🟢 LOW | 🔴 Critical | ✅ COMPLETE |
| Phase 1 | 🟢 LOW | 🟢 LOW | 🟢 Low | ✅ COMPLETE |
| Phase 2 | 🟡 MED | 🟢 LOW | 🟢 Low | ✅ COMPLETE |
| Phase 3 | 🔴 HIGH | 🟡 MED | 🟡 Medium | ✅ COMPLETE |
| Phase 4 | 🔴 HIGH | 🔴 HIGH | 🔴 Critical | ✅ COMPLETE |
| Phase 5 | 🔴 HIGH | 🔴 HIGH | 🔴 Critical | ✅ COMPLETE |
| Phase 6 | 🟡 MED | 🟢 LOW | 🟡 Medium | ✅ COMPLETE |
| Phase 7 | 🔴 VERY HIGH | 🔴 VERY HIGH | 🔴 Critical | ⏳ PENDING |
| Phase 8 (NEW) | 🟡 MED | 🟡 MED | 🟡 Medium | ⏳ PENDING |
| Phase 9 (NEW) | 🟡 MED | 🟢 LOW | 🟢 Low | ⏳ PENDING |
| Phase 10 | 🟡 MED | 🟢 LOW | 🟢 Low | ⏳ PENDING |
| Phase 11 | 🟢 LOW | 🟢 LOW | 🟢 Low | ⏳ PENDING |

---

## Critical Success Factors

### ✅ Must Have

1. **Regression baseline BEFORE any changes** (Phase 0) ✅ DONE
2. **Test infrastructure** (Phase -1) ✅ DONE
3. **Bit-exact validation** for Phases 4, 5, 7
4. **Incremental approach** - one change at a time
5. **Dynamic UI** before legacy cleanup (Phase 8 → Phase 9 order)

### ⚠️ Should Have

1. **TradingView validation** for strategies ✅ DONE for S04
2. **Performance profiling** before/after
3. **Documentation as you go**
4. **Git tags** at each phase completion

### 💡 Nice to Have

1. **Parallel development** (multiple branches)
2. **Rollback plan** (git tags enable this)
3. **CI/CD pipeline** (GitHub Actions)
4. **Automated performance benchmarks**

---

## Questions During Migration

If you encounter:
- **Unexpected test failures:** Debug before proceeding
- **Performance issues:** Profile and investigate
- **Design questions:** Refer back to PROJECT_TARGET_ARCHITECTURE.md
- **Scope creep:** Stay focused on migration, defer improvements
- **UI issues:** Phase 8 should fix them, don't bypass

---

**END OF MIGRATION PLAN v2.1**

**Version:** 2.1
**Status:** Ready for Phase 7 Execution
**Last Updated:** 2025-12-03
**Author:** Migration Team
**Next Step:** Begin Phase 7 (S01 Migration via Duplicate)

---

## Appendix: Hardcoded S01 References Audit

### Backend (server.py)

**Lines with S01 hardcoding:**
- 75-130: DEFAULT_PRESET with S01 parameters
- 596: Default strategy_id = "s01_trailing_ma"
- 962: Default strategy_id = "s01_trailing_ma"
- 1163: Hardcoded strategy_id = "s01_trailing_ma"
- 1503: Default strategy_id = "s01_trailing_ma"
- 678-693: S01 parameter names for warmup calculation
- 1198-1215: S01 MA type mappings
- 1341-1347: S01 trail type handling

**Total:** ~160 lines of S01-specific backend code

### Frontend (index.html)

**Before Phase 8:**
- 1455-1829: Hardcoded optimizer HTML (~374 lines)
- 2668-2840: OPTIMIZATION_PARAMETERS array (~172 lines)

**Total:** ~546 lines of S01-specific frontend code

**After Phase 8:** All deleted ✅

### Grand Total

**~700 lines of S01-specific hardcoded code** identified and tracked for cleanup in Phase 9.
