# Phase 9: Legacy Code Cleanup - Task Prompt

**Phase:** 9 of 11
**Complexity:** 🟡 MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 4-6 hours
**Priority:** ✅ SAFE - UI IS ALREADY DYNAMIC
**Status:** Ready for Execution

---

## Table of Contents

1. [Project Context](#project-context)
2. [Phase 9 Objective](#phase-9-objective)
3. [Why This Phase Is Safe](#why-this-phase-is-safe)
4. [What Gets Deleted/Changed](#what-gets-deletedchanged)
5. [Detailed Implementation Guide](#detailed-implementation-guide)
6. [Testing Strategy](#testing-strategy)
7. [Validation Checklist](#validation-checklist)
8. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
9. [Success Criteria](#success-criteria)

---

## Project Context

You are working on a cryptocurrency/forex trading strategy backtesting platform that has successfully completed 8 phases of architecture migration. The system now has a fully dynamic UI that loads parameters from strategy `config.json` files, making it safe to remove all legacy S01-specific hardcoded code.

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
- ✅ **Phase 8**: Dynamic Optimizer + CSS Extraction
- ✅ **Phase 8.1**: Fix error popup, MA type checkboxes, and S04 optimization

### Current System State

**Strategies Available**:
- `s01_trailing_ma` - Legacy S01 (WILL BE REMOVED in this phase)
- `s01_trailing_ma_migrated` - Migrated S01 (WILL BECOME production)
- `s04_stochrsi` - StochRSI strategy (working)

**UI State**:
- ✅ Backtest form: Dynamic, works for all strategies
- ✅ Optimizer form: Dynamic, works for all strategies
- ✅ MA type selectors: Show only for S01 strategies
- ✅ CSS: Extracted to external file

**Test Suite**: 76 tests passing

---

## Phase 9 Objective

**Goal**: Delete all hardcoded S01-specific blocks from backend and frontend now that UI is fully dynamic. Leave a clean codebase for Phase 10 (Frontend Separation).

**Four Main Tasks**:
1. **Promote Migrated S01** (30 min): Rename `s01_trailing_ma_migrated` → `s01_trailing_ma`
2. **Backend Cleanup** (2-3 hours): Remove S01 hardcoding from `server.py` and core modules
3. **Frontend Cleanup** (1-2 hours): Remove S01-specific JavaScript logic
4. **Delete Legacy Code** (30 min): Remove `run_strategy()` from `backtest_engine.py`

**Success Criteria**:
1. ✅ No S01-specific hardcoded references in backend
2. ✅ No S01-specific hardcoded references in frontend
3. ✅ `backtest_engine.py` is truly generic (no `run_strategy()`)
4. ✅ Both S01 and S04 work correctly in UI
5. ✅ All 76 tests still passing
6. ✅ Codebase clean and maintainable

---

## Why This Phase Is Safe

### Phase 8 Made It Safe

Phase 8 transformed the UI from hardcoded to dynamic:

**Before Phase 8 (Dangerous)**:
```
Delete S01 code → UI breaks → Production down ❌
```

**After Phase 8 (Safe)**:
```
Delete S01 code → UI works (reads from config.json) → Production works ✅
```

### What Changed in Phase 8

1. **Optimizer form**: Now generated dynamically from `config.json`
2. **MA type selectors**: Now conditionally shown based on `isS01Strategy()` check
3. **Parameter collection**: Now reads from dynamic DOM elements
4. **CSS**: Extracted to external file

### Why Deleting Legacy Code Won't Break Anything

1. **Migrated S01 is self-contained**: All logic is in `s01_trailing_ma_migrated/strategy.py`
2. **UI is config-driven**: Reads parameters from strategy `config.json`
3. **Backend routes are generic**: Use strategy registry, not hardcoded IDs
4. **Tests validate behavior**: 76 tests catch any regressions

---

## What Gets Deleted/Changed

### Summary of Changes

| Location | Type | Action | Lines Affected |
|----------|------|--------|----------------|
| `src/strategies/s01_trailing_ma/` | Directory | DELETE | ~200 lines |
| `src/strategies/s01_trailing_ma_migrated/` | Directory | RENAME → `s01_trailing_ma/` | 0 (rename only) |
| `src/core/backtest_engine.py` | Function | DELETE `run_strategy()` | ~300 lines |
| `src/server.py` | Code blocks | MODIFY | ~50 lines |
| `src/core/optuna_engine.py` | Default value | MODIFY | ~5 lines |
| `src/core/walkforward_engine.py` | Default values | MODIFY | ~10 lines |
| `src/index.html` | JavaScript | MODIFY | ~30 lines |

### Detailed Audit of Legacy Code

#### 1. Server.py (Backend) - 11 S01-specific blocks

**Hardcoded Default Strategy IDs** (4 locations):
```python
# Line 601
strategy_id = request.form.get("strategy", "s01_trailing_ma")

# Line 966-967
strategy_id = request.form.get("strategy", "s01_trailing_ma")

# Line 1168
strategy_id = "s01_trailing_ma"

# Line 1515
strategy_id = request.form.get("strategy", "s01_trailing_ma")
```

**S01-Specific Conditional Logic** (Lines 1203-1227):
```python
is_s01_strategy = bool(strategy_id) and "s01" in str(strategy_id).lower()
ma_types_trend: List[str] = []
ma_types_trail_long: List[str] = []
ma_types_trail_short: List[str] = []
lock_trail_types = False

if is_s01_strategy:
    ma_types_trend = payload.get("ma_types_trend") or ...
    ma_types_trail_long = payload.get("ma_types_trail_long") or ...
    ma_types_trail_short = payload.get("ma_types_trail_short") or ...
    lock_trail_types_raw = payload.get("lock_trail_types") or ...
    lock_trail_types = _parse_bool(lock_trail_types_raw, False)
```

**Note**: This S01-specific logic is CORRECT and should be KEPT. It's a legitimate strategy-specific feature, not hardcoding. The key is that it detects S01 dynamically rather than assuming all strategies are S01.

#### 2. Core Modules - Default Values

**optuna_engine.py** (Line 48):
```python
strategy_id: str = "s01_trailing_ma"  # ← Change to empty or first available
```

**walkforward_engine.py** (Lines 35, 92, 813):
```python
strategy_id: str = "s01_trailing_ma"  # ← Change to empty or first available
```

#### 3. backtest_engine.py - Legacy Function

**`run_strategy()` function** (Lines 381-687, ~307 lines):
```python
def run_strategy(df: pd.DataFrame, params: StrategyParams, trade_start_idx: int = 0) -> StrategyResult:
    """
    This is the LEGACY S01-specific implementation.
    After Phase 7, this is only used by the legacy s01_trailing_ma wrapper.
    The migrated version has its own implementation in strategy.py.

    DELETE THIS ENTIRE FUNCTION.
    """
    # ... 307 lines of S01-specific logic ...
```

**Also delete**:
- `StrategyParams` class (legacy, now in migrated strategy)
- Any helper functions used only by `run_strategy()`

#### 4. Index.html (Frontend) - JavaScript

**`isS01Strategy()` function usage** (12+ locations):
```javascript
// Line 1218: Show/hide MA type selectors
if (isS01Strategy()) {
    maTypeContainer.style.display = 'block';
} else {
    maTypeContainer.style.display = 'none';
}

// Lines 2616, 2932, 3062-3065, 3412: Conditional MA type handling
const isS01 = isS01Strategy();
if (isS01 && isMaSelectorVisible()) {
    // ... MA type logic ...
}
```

**Note**: This logic is CORRECT and should be KEPT. It properly detects S01 strategies dynamically.

**Hardcoded fallback strategy IDs** (3 locations):
```javascript
// Line 3263
formData.append('strategy', currentStrategyId || 's01_trailing_ma');

// Line 3509
formData.append('strategy', currentStrategyId || 's01_trailing_ma');

// Line 3841
formData.append('strategy', currentStrategyId || 's01_trailing_ma');
```

**Page Title** (Line 6):
```html
<title>S_01 TrailingMA — Backtester и Optimizer</title>
```

---

## Detailed Implementation Guide

### Step 1: Promote Migrated S01 to Production (30 min)

**Goal**: Rename `s01_trailing_ma_migrated` to `s01_trailing_ma`, making the migrated version the production version.

#### 1.1: Backup Legacy S01 (Just in Case)

```bash
# Create backup of legacy implementation
mv src/strategies/s01_trailing_ma src/strategies/s01_trailing_ma_legacy_backup
```

**Note**: This backup will be deleted at the end of Phase 9 after validation.

#### 1.2: Rename Migrated to Production

```bash
# Rename migrated to production
mv src/strategies/s01_trailing_ma_migrated src/strategies/s01_trailing_ma
```

#### 1.3: Update Strategy ID in config.json

**File**: `src/strategies/s01_trailing_ma/config.json`

```json
{
  "id": "s01_trailing_ma",
  "name": "S01 Trailing MA",
  "version": "v26",
  ...
}
```

**Change**: Update `id` from `"s01_trailing_ma_migrated"` to `"s01_trailing_ma"`.

#### 1.4: Update Strategy ID in strategy.py

**File**: `src/strategies/s01_trailing_ma/strategy.py`

Find and update:
```python
class S01TrailingMAMigrated(BaseStrategy):
    STRATEGY_ID = "s01_trailing_ma_migrated"  # ← OLD
    STRATEGY_NAME = "S01 Trailing MA Migrated"
```

Change to:
```python
class S01TrailingMA(BaseStrategy):
    STRATEGY_ID = "s01_trailing_ma"  # ← NEW
    STRATEGY_NAME = "S01 Trailing MA"
```

**Also rename the class**: `S01TrailingMAMigrated` → `S01TrailingMA`

#### 1.5: Update __init__.py

**File**: `src/strategies/s01_trailing_ma/__init__.py`

If it imports `S01TrailingMAMigrated`, update to `S01TrailingMA`:

```python
from .strategy import S01TrailingMA
```

#### 1.6: Test Strategy Registration

```bash
cd src
python -c "from strategies import list_strategies; print([s['id'] for s in list_strategies()])"
```

**Expected output**:
```
['s01_trailing_ma', 's04_stochrsi']
```

**Note**: Should show `s01_trailing_ma` (not `s01_trailing_ma_migrated`).

---

### Step 2: Backend Cleanup - Remove Default Strategy IDs (1 hour)

**Goal**: Replace hardcoded `"s01_trailing_ma"` defaults with dynamic strategy selection.

#### 2.1: Fix server.py Default Strategy Handling

**File**: `src/server.py`

Find all 4 occurrences of hardcoded default:

```python
# OLD (4 locations):
strategy_id = request.form.get("strategy", "s01_trailing_ma")
```

Replace with dynamic selection:

```python
# NEW: Get strategy ID from request, require it explicitly
strategy_id = request.form.get("strategy") or request.json.get("strategy") if request.is_json else request.form.get("strategy")
if not strategy_id:
    # Return error - strategy must be specified
    return jsonify({"error": "No strategy specified. Please select a strategy."}), 400
```

**Alternative approach** (if backward compatibility needed):

```python
# NEW: Get first available strategy as default
from strategies import list_strategies

strategy_id = request.form.get("strategy")
if not strategy_id:
    available = list_strategies()
    if available:
        strategy_id = available[0]['id']
    else:
        return jsonify({"error": "No strategies available"}), 500
```

**Locations to update**:
- Line ~601 (backtest endpoint)
- Line ~966 (optimize endpoint)
- Line ~1168 (preset import)
- Line ~1515 (walkforward endpoint)

#### 2.2: Fix optuna_engine.py Default

**File**: `src/core/optuna_engine.py`

Find the `OptimizationConfig` dataclass:

```python
@dataclass
class OptimizationConfig:
    # ... other fields ...
    strategy_id: str = "s01_trailing_ma"  # ← OLD
```

Change to:

```python
@dataclass
class OptimizationConfig:
    # ... other fields ...
    strategy_id: str = ""  # ← NEW: No default, must be specified
```

**Or use empty string and validate**:

```python
def run_optimization(config: OptimizationConfig) -> List[OptimizationResult]:
    if not config.strategy_id:
        raise ValueError("strategy_id must be specified in OptimizationConfig")
    # ... rest of function ...
```

#### 2.3: Fix walkforward_engine.py Defaults

**File**: `src/core/walkforward_engine.py`

Find and update these dataclasses:

```python
# Line ~35: WFConfig
@dataclass
class WFConfig:
    strategy_id: str = "s01_trailing_ma"  # ← OLD
    # ... other fields ...

# Line ~92: WFResult
@dataclass
class WFResult:
    strategy_id: str = "s01_trailing_ma"  # ← OLD
    # ... other fields ...
```

Change to:

```python
@dataclass
class WFConfig:
    strategy_id: str = ""  # ← NEW: Must be specified
    # ... other fields ...

@dataclass
class WFResult:
    strategy_id: str = ""  # ← NEW: Populated from WFConfig
    # ... other fields ...
```

**Also fix Line ~813**:

```python
# OLD:
strategy_id = getattr(wf_result, 'strategy_id', 's01_trailing_ma')

# NEW:
strategy_id = getattr(wf_result, 'strategy_id', '')
if not strategy_id:
    strategy_id = getattr(wf_config, 'strategy_id', '')
```

---

### Step 3: Delete run_strategy() from backtest_engine.py (1 hour)

**Goal**: Remove the legacy S01-specific implementation from the core engine.

#### 3.1: Identify Code to Delete

**File**: `src/core/backtest_engine.py`

**DELETE** the following:

1. **`run_strategy()` function** (Lines ~381-687, ~307 lines):
```python
def run_strategy(df: pd.DataFrame, params: StrategyParams, trade_start_idx: int = 0) -> StrategyResult:
    """
    DELETE THIS ENTIRE FUNCTION.
    Legacy S01-specific implementation.
    Migrated version is in src/strategies/s01_trailing_ma/strategy.py
    """
    # ... 307 lines ...
```

2. **`StrategyParams` class** (if it exists in backtest_engine.py):
```python
@dataclass
class StrategyParams:
    """
    DELETE THIS CLASS.
    Now lives in src/strategies/s01_trailing_ma/strategy.py as S01Params
    """
    # ... parameters ...
```

3. **Helper functions used only by `run_strategy()`**:
   - Check if any helper functions are ONLY used by `run_strategy()`
   - If so, delete them too
   - If they're used elsewhere, keep them

#### 3.2: Keep These Functions

**DO NOT DELETE** these functions in `backtest_engine.py`:

- `load_data()` - Used by all strategies
- `prepare_dataset_with_warmup()` - Used by all strategies
- `StrategyResult` dataclass - Used by all strategies
- `TradeRecord` dataclass - Used by all strategies
- Any utility functions used by multiple strategies

#### 3.3: Verify No Import Errors

After deletion, check for import errors:

```bash
cd src
python -c "from core.backtest_engine import load_data, prepare_dataset_with_warmup, StrategyResult, TradeRecord; print('OK')"
```

**Expected output**: `OK`

Check that strategies still import correctly:

```bash
python -c "from strategies.s01_trailing_ma.strategy import S01TrailingMA; print('OK')"
python -c "from strategies.s04_stochrsi.strategy import S04StochRSI; print('OK')"
```

---

### Step 4: Frontend Cleanup - JavaScript (1 hour)

**Goal**: Remove hardcoded S01 fallbacks while keeping legitimate S01-detection logic.

#### 4.1: Identify What to Keep vs Delete

**KEEP** (legitimate S01 detection):
```javascript
// This is CORRECT - detects S01 dynamically
function isS01Strategy(strategyId = currentStrategyId) {
    return typeof strategyId === 'string' && strategyId.toLowerCase().includes('s01');
}

// This is CORRECT - conditionally shows MA types for S01
if (isS01Strategy()) {
    maTypeContainer.style.display = 'block';
}
```

**DELETE** (hardcoded fallbacks):
```javascript
// This is WRONG - hardcoded fallback
formData.append('strategy', currentStrategyId || 's01_trailing_ma');
```

#### 4.2: Fix Hardcoded Strategy Fallbacks

**File**: `src/index.html`

Find these 3 locations with hardcoded fallbacks:

```javascript
// Line ~3263 (in optimization submit)
formData.append('strategy', currentStrategyId || 's01_trailing_ma');

// Line ~3509 (in backtest submit)
formData.append('strategy', currentStrategyId || 's01_trailing_ma');

// Line ~3841 (in walkforward submit)
formData.append('strategy', currentStrategyId || 's01_trailing_ma');
```

**Replace with**:

```javascript
// NEW: Require strategy selection, show error if not selected
if (!currentStrategyId) {
    alert('Please select a strategy before running.');
    return;
}
formData.append('strategy', currentStrategyId);
```

**Alternative** (auto-select first strategy):

```javascript
// NEW: Use first strategy if none selected
const strategyId = currentStrategyId || (strategies.length > 0 ? strategies[0].id : null);
if (!strategyId) {
    alert('No strategies available. Please check configuration.');
    return;
}
formData.append('strategy', strategyId);
```

#### 4.3: Update Page Title

**File**: `src/index.html`

Find line ~6:
```html
<title>S_01 TrailingMA — Backtester и Optimizer</title>
```

Change to:
```html
<title>Strategy Backtester & Optimizer</title>
```

Or make it dynamic (optional enhancement):
```html
<title id="pageTitle">Strategy Backtester & Optimizer</title>
```

```javascript
// In loadStrategyConfig():
document.getElementById('pageTitle').textContent = `${config.name} — Backtester & Optimizer`;
```

#### 4.4: Verify isS01Strategy() Logic is Correct

The `isS01Strategy()` function should work correctly after renaming:

```javascript
function isS01Strategy(strategyId = currentStrategyId) {
    return typeof strategyId === 'string' && strategyId.toLowerCase().includes('s01');
}
```

**Test cases**:
- `isS01Strategy('s01_trailing_ma')` → `true` ✅
- `isS01Strategy('s04_stochrsi')` → `false` ✅
- `isS01Strategy(null)` → `false` ✅
- `isS01Strategy(undefined)` → `false` ✅

---

### Step 5: Delete Legacy Backup (15 min)

**Goal**: Remove the legacy S01 backup after validation.

#### 5.1: Verify Everything Works

Before deleting the backup:

1. Run full test suite
2. Manual UI testing
3. Verify S01 optimization works
4. Verify S04 optimization works

#### 5.2: Delete Legacy Backup

```bash
# Only after validation passes
rm -rf src/strategies/s01_trailing_ma_legacy_backup
```

#### 5.3: Verify No References Remain

```bash
# Search for any remaining references to legacy/migrated
grep -r "s01_trailing_ma_migrated" src/ --include="*.py" --include="*.html" --include="*.json"
grep -r "s01_trailing_ma_legacy" src/ --include="*.py" --include="*.html" --include="*.json"
```

**Expected output**: No matches found.

---

### Step 6: Update Tests (30 min)

**Goal**: Update test files to use the renamed strategy.

#### 6.1: Update test_s01_migration.py

**File**: `tests/test_s01_migration.py`

Find and replace imports:
```python
# OLD:
from strategies.s01_trailing_ma.strategy import S01TrailingMA  # Legacy
from strategies.s01_trailing_ma_migrated.strategy import S01TrailingMAMigrated  # Migrated

# NEW:
from strategies.s01_trailing_ma.strategy import S01TrailingMA  # Now the migrated version
```

**Update test class names if needed**:
```python
# OLD:
class TestS01Migration:
    def test_legacy_vs_migrated_exact_match(self, ...):
        legacy_result = S01TrailingMA.run(...)  # Legacy
        migrated_result = S01TrailingMAMigrated.run(...)  # Migrated

# NEW:
class TestS01Strategy:
    def test_baseline_match(self, ...):
        result = S01TrailingMA.run(...)  # Now the migrated version
```

**Note**: The legacy vs migrated comparison tests can be simplified to just baseline tests since there's only one version now.

#### 6.2: Update test_regression_s01.py

**File**: `tests/test_regression_s01.py`

Verify imports use the correct path:
```python
from strategies.s01_trailing_ma.strategy import S01TrailingMA
```

#### 6.3: Run Test Suite

```bash
cd src
pytest tests/ -v
```

**Expected**: All 76 tests passing (some may need adjustment for renamed classes).

---

## Testing Strategy

### Test Checklist

#### Automated Tests

```bash
# Run full test suite
cd src
pytest tests/ -v

# Expected: 76 tests passing
```

#### Manual UI Testing

1. **Start server**:
   ```bash
   cd src
   python server.py
   ```

2. **Test S01 Strategy**:
   - [ ] Select S01 from dropdown
   - [ ] Verify parameters load correctly
   - [ ] Verify MA type checkboxes appear
   - [ ] Run single backtest
   - [ ] Run small optimization (10 trials)
   - [ ] Verify results match expected

3. **Test S04 Strategy**:
   - [ ] Select S04 from dropdown
   - [ ] Verify parameters load correctly
   - [ ] Verify MA type checkboxes are HIDDEN
   - [ ] Run single backtest
   - [ ] Run small optimization (10 trials)
   - [ ] Verify results are correct (not S01 results)

4. **Test Strategy Switching**:
   - [ ] Switch S01 → S04 → S01
   - [ ] Verify forms update correctly
   - [ ] Verify no JavaScript errors in console

5. **Test Edge Cases**:
   - [ ] Refresh page, verify first strategy auto-selected
   - [ ] Browser console has no errors
   - [ ] Network tab shows successful API calls

### Verification Commands

```bash
# Check strategy registration
cd src
python -c "from strategies import list_strategies; print([s['id'] for s in list_strategies()])"
# Expected: ['s01_trailing_ma', 's04_stochrsi']

# Check no legacy references
grep -r "s01_trailing_ma_migrated" src/
# Expected: No matches

grep -r "s01_trailing_ma_legacy" src/
# Expected: No matches

# Check run_strategy is deleted
grep -n "def run_strategy" src/core/backtest_engine.py
# Expected: No matches

# Check StrategyParams is deleted (if it was in backtest_engine)
grep -n "class StrategyParams" src/core/backtest_engine.py
# Expected: No matches
```

---

## Validation Checklist

### Phase 9.1: Promote Migrated S01

- [ ] Backed up legacy S01 to `s01_trailing_ma_legacy_backup`
- [ ] Renamed `s01_trailing_ma_migrated` to `s01_trailing_ma`
- [ ] Updated `config.json` with ID `"s01_trailing_ma"`
- [ ] Updated `strategy.py` class name to `S01TrailingMA`
- [ ] Updated `strategy.py` STRATEGY_ID to `"s01_trailing_ma"`
- [ ] Updated `__init__.py` import
- [ ] Verified strategy appears in registry

### Phase 9.2: Backend Cleanup

- [ ] Removed hardcoded `"s01_trailing_ma"` from server.py (4 locations)
- [ ] Added proper strategy validation (require strategy ID)
- [ ] Updated `optuna_engine.py` default strategy_id
- [ ] Updated `walkforward_engine.py` default strategy_id (3 locations)
- [ ] No import errors after changes

### Phase 9.3: Delete run_strategy()

- [ ] Deleted `run_strategy()` function from `backtest_engine.py`
- [ ] Deleted `StrategyParams` class if present
- [ ] Deleted any orphaned helper functions
- [ ] Kept `load_data()`, `prepare_dataset_with_warmup()`, `StrategyResult`, `TradeRecord`
- [ ] No import errors after deletion

### Phase 9.4: Frontend Cleanup

- [ ] Removed hardcoded fallback `|| 's01_trailing_ma'` (3 locations)
- [ ] Added proper validation before submit
- [ ] Updated page title
- [ ] Kept `isS01Strategy()` function (legitimate detection)
- [ ] No JavaScript errors in console

### Phase 9.5: Cleanup and Testing

- [ ] All 76 tests passing
- [ ] Manual UI testing completed for S01
- [ ] Manual UI testing completed for S04
- [ ] Strategy switching works correctly
- [ ] No legacy references remain in codebase
- [ ] Deleted `s01_trailing_ma_legacy_backup`

### Phase 9.6: Git Commit

- [ ] Committed changes: "Phase 9: Delete all legacy S01 code"
- [ ] Tagged commit: `git tag phase-9-complete`
- [ ] Pushed to remote

---

## Common Pitfalls and Solutions

### Pitfall 1: Import Errors After Deletion

**Problem**: After deleting `run_strategy()`, some modules fail to import.

**Cause**: Other modules may import `run_strategy` or `StrategyParams` from `backtest_engine`.

**Solution**:
```bash
# Find all imports
grep -r "from core.backtest_engine import" src/ tests/
grep -r "from backtest_engine import" src/ tests/
```

Update any imports that reference deleted items:
```python
# OLD:
from core.backtest_engine import run_strategy, StrategyParams

# NEW: Remove these imports, they're no longer needed
from core.backtest_engine import StrategyResult, TradeRecord
```

### Pitfall 2: Legacy S01 Still Used by Tests

**Problem**: Tests import from `s01_trailing_ma` but expect the legacy version.

**Solution**: Update test imports:
```python
# OLD (tests may have):
from strategies.s01_trailing_ma.strategy import S01TrailingMA
from strategies.s01_trailing_ma_migrated.strategy import S01TrailingMAMigrated

# After migration comparison tests use:
legacy_result = S01TrailingMA.run(...)  # Was legacy
migrated_result = S01TrailingMAMigrated.run(...)  # Was migrated

# NEW (after Phase 9):
from strategies.s01_trailing_ma.strategy import S01TrailingMA
# Only one version now - the migrated one
result = S01TrailingMA.run(...)
```

**Update test logic**:
- Remove legacy vs migrated comparison tests (no legacy anymore)
- Keep baseline validation tests (verify correct behavior)

### Pitfall 3: Strategy Registration Fails

**Problem**: After renaming, strategy doesn't appear in dropdown.

**Cause**: Strategy registry caches results or `__init__.py` has wrong import.

**Solution**:
```python
# Check __init__.py
# src/strategies/s01_trailing_ma/__init__.py should have:
from .strategy import S01TrailingMA

# Verify registration
cd src
python -c "
from strategies import list_strategies, _REGISTRY
print('Registry:', list(_REGISTRY.keys()))
print('List:', [s['id'] for s in list_strategies()])
"
```

If caching issue, restart Python process completely.

### Pitfall 4: Frontend Still Shows "s01_trailing_ma_migrated"

**Problem**: Strategy dropdown shows old migrated name.

**Cause**: Browser cache or strategy list fetched before rename.

**Solution**:
1. Clear browser cache (Ctrl+Shift+Delete)
2. Hard refresh (Ctrl+Shift+R)
3. Check API response:
   ```
   curl http://localhost:8000/api/strategies
   ```
   Should show `s01_trailing_ma` (not migrated)

### Pitfall 5: MA Type Selectors Not Working

**Problem**: MA type selectors don't appear for S01 after rename.

**Cause**: `isS01Strategy()` checks for 's01' in strategy ID.

**Verification**:
```javascript
// In browser console:
console.log(currentStrategyId);  // Should be "s01_trailing_ma"
console.log(isS01Strategy());    // Should be true
```

**Solution**: Ensure strategy ID contains "s01":
- Correct: `"s01_trailing_ma"` ✅
- Wrong: `"s1_trailing_ma"` ❌ (missing 0)

### Pitfall 6: Tests Fail with "Module Not Found"

**Problem**: Tests fail because they import from deleted paths.

**Solution**: Update test imports:
```python
# Check for old imports
grep -r "s01_trailing_ma_migrated" tests/
grep -r "run_strategy" tests/

# Update to new paths
```

### Pitfall 7: Optimization Fails Without Strategy ID

**Problem**: After removing default, optimization fails with "No strategy specified".

**Cause**: Frontend not sending strategy ID in payload.

**Solution**: Check frontend payload:
```javascript
console.log('Payload:', JSON.stringify(payload));
// Should include: "strategy": "s01_trailing_ma"
```

If missing, ensure `currentStrategyId` is set when strategy is selected.

### Pitfall 8: Baseline Test Fails

**Problem**: Baseline regression test fails after changes.

**Cause**: Baseline was generated with legacy version, now running against migrated.

**Analysis**:
- If Phase 7 passed, migrated is bit-exact with legacy
- Baseline should still match
- If it doesn't, something went wrong in Phase 7

**Solution**:
1. Verify migrated strategy is correct
2. Re-run Phase 7 validation tests
3. If needed, regenerate baseline with migrated version

---

## Success Criteria

Phase 9 is successful when ALL of these criteria are met:

### 1. No Legacy S01 References

```bash
# Run these checks:
grep -r "s01_trailing_ma_migrated" src/
# Expected: No matches

grep -r "s01_trailing_ma_legacy" src/
# Expected: No matches

grep -n "def run_strategy" src/core/backtest_engine.py
# Expected: No matches
```

### 2. Strategy Registration Correct

```bash
cd src
python -c "from strategies import list_strategies; print([s['id'] for s in list_strategies()])"
# Expected: ['s01_trailing_ma', 's04_stochrsi']
```

### 3. All Tests Pass

```bash
pytest tests/ -v
# Expected: 76 tests passing
```

### 4. S01 Baseline Matches

```python
# Run baseline test
pytest tests/test_regression_s01.py -v

# Expected:
# Net Profit: 230.75%
# Max Drawdown: 20.03%
# Total Trades: 93
```

### 5. Manual UI Verification

**S01 Strategy**:
- [ ] Parameters load correctly
- [ ] MA type selectors appear
- [ ] Backtest produces correct results
- [ ] Optimization produces varied results

**S04 Strategy**:
- [ ] Parameters load correctly
- [ ] MA type selectors hidden
- [ ] Backtest produces correct results
- [ ] Optimization uses S04 parameters (not S01)

### 6. No JavaScript Errors

Open browser DevTools (F12), check Console tab:
- [ ] No red errors
- [ ] No 404 for API calls
- [ ] Strategy switching works smoothly

### 7. Code Quality

- [ ] No hardcoded `"s01_trailing_ma"` defaults in backend
- [ ] No hardcoded fallbacks in frontend
- [ ] `backtest_engine.py` is strategy-agnostic
- [ ] Clean imports (no unused imports)

---

## Next Steps After Phase 9

After Phase 9 is complete and validated:

**Phase 10** (Next): Full Frontend Separation
- Modularize JavaScript into separate files
- Move HTML to `templates/`
- Move server.py to `ui/`
- Clean up imports

**Phase 11**: Documentation
- Update all documentation to reflect migration completion
- Create strategy development guide
- Create migration summary
- Mark migration as complete

---

## Project Files Reference

### Files You'll Modify

**Directories**:
- `src/strategies/s01_trailing_ma/` - Rename from migrated, update IDs
- `src/strategies/s01_trailing_ma_legacy_backup/` - DELETE after validation

**Backend**:
- `src/core/backtest_engine.py` - DELETE `run_strategy()` and related code
- `src/server.py` - Remove hardcoded default strategy IDs
- `src/core/optuna_engine.py` - Update default strategy_id
- `src/core/walkforward_engine.py` - Update default strategy_id

**Frontend**:
- `src/index.html` - Remove hardcoded fallbacks, update title

**Tests**:
- `tests/test_s01_migration.py` - Update imports and test logic
- `tests/test_regression_s01.py` - Verify imports

### Files You'll Read

- `src/strategies/s01_trailing_ma_migrated/strategy.py` - Current migrated implementation
- `src/strategies/s01_trailing_ma_migrated/config.json` - Strategy configuration
- `docs/PROJECT_MIGRATION_PLAN_upd.md` - Phase 9 requirements

---

## Implementation Checklist

### Preparation

- [ ] Read this entire prompt
- [ ] Understand current codebase state
- [ ] Review Phase 8.1 completion status
- [ ] Ensure all 76 tests passing before starting

### Step 1: Promote Migrated S01 (30 min)

- [ ] Backup legacy to `s01_trailing_ma_legacy_backup`
- [ ] Rename `s01_trailing_ma_migrated` → `s01_trailing_ma`
- [ ] Update `config.json` ID
- [ ] Update `strategy.py` class name and ID
- [ ] Update `__init__.py` import
- [ ] Verify strategy registration

### Step 2: Backend Cleanup (2-3 hours)

- [ ] Update server.py (4 locations)
- [ ] Update optuna_engine.py (1 location)
- [ ] Update walkforward_engine.py (3 locations)
- [ ] Verify no import errors

### Step 3: Delete run_strategy() (1 hour)

- [ ] Delete `run_strategy()` function
- [ ] Delete `StrategyParams` class if present
- [ ] Delete orphaned helper functions
- [ ] Verify imports still work

### Step 4: Frontend Cleanup (1 hour)

- [ ] Remove hardcoded fallbacks (3 locations)
- [ ] Add validation before submit
- [ ] Update page title
- [ ] Verify no JavaScript errors

### Step 5: Testing (1 hour)

- [ ] Update test imports
- [ ] Run full test suite
- [ ] Manual UI testing for S01
- [ ] Manual UI testing for S04
- [ ] Test strategy switching

### Step 6: Cleanup (15 min)

- [ ] Delete `s01_trailing_ma_legacy_backup`
- [ ] Verify no legacy references remain
- [ ] Commit changes
- [ ] Tag: `phase-9-complete`
- [ ] Push to remote

---

## Debugging Guide

### If Tests Fail After Renaming

```bash
# Check what's imported
python -c "
from strategies.s01_trailing_ma.strategy import S01TrailingMA
print('Class name:', S01TrailingMA.__name__)
print('Strategy ID:', S01TrailingMA.STRATEGY_ID)
"
```

**Expected**:
```
Class name: S01TrailingMA
Strategy ID: s01_trailing_ma
```

### If Strategy Not Found in UI

```bash
# Check API response
curl http://localhost:8000/api/strategies

# Check registry directly
python -c "
from strategies import _REGISTRY
print('Registered:', list(_REGISTRY.keys()))
"
```

### If Optimization Produces Wrong Results

```bash
# Check which strategy is being used
# Add logging in server.py:
print(f"Running optimization for strategy: {strategy_id}")
```

### If Import Errors Occur

```bash
# Find all imports of deleted items
grep -rn "from core.backtest_engine import" src/ tests/
grep -rn "run_strategy" src/ tests/
grep -rn "StrategyParams" src/ tests/
```

---

## Conclusion

Phase 9 is a cleanup phase that removes all legacy S01-specific code now that the UI is fully dynamic. This phase is LOW RISK because:

1. ✅ Migrated S01 is validated (Phase 7)
2. ✅ UI is dynamic (Phase 8)
3. ✅ All tests pass

The main work is:
1. Renaming directories and updating IDs
2. Removing hardcoded defaults
3. Deleting legacy code
4. Updating tests

After this phase, the codebase will be clean and ready for Phase 10 (Frontend Separation).

**Key Success Factors**:
- ✅ Careful attention to renaming (IDs must match)
- ✅ Thorough testing after each change
- ✅ Verification that no legacy references remain
- ✅ Manual UI testing for both strategies

**Good luck! This phase cleans up technical debt and prepares for the final migration steps.**

---

**Project Repository**: Current working directory
**Key Files**: `src/strategies/`, `src/core/backtest_engine.py`, `src/server.py`, `src/index.html`

**Key Commands**:
```bash
# Start server
cd src
python server.py

# Run tests
pytest tests/ -v

# Check strategy registration
python -c "from strategies import list_strategies; print([s['id'] for s in list_strategies()])"

# Search for legacy references
grep -r "s01_trailing_ma_migrated" src/
grep -r "run_strategy" src/core/backtest_engine.py
```

**Report Issues**: If you encounter problems not covered in this prompt, document them clearly with:
1. What you tried
2. What you expected
3. What actually happened
4. Relevant error messages
5. Browser console output (if UI-related)

---

**End of Phase 9 Prompt**

**Version**: 1.0
**Date**: 2025-12-04
**Author**: Migration Team
**Status**: Ready for Execution
