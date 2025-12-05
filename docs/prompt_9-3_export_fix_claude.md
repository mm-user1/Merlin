# Enhancement Plan: Strategy-Agnostic CSV Export System

**Date:** 2025-12-05
**Depends On:** commit c3d42dd + 3-line enhancement (dynamic attribute storage)
**Priority:** MEDIUM (optimization works, CSV is reporting feature)
**Status:** 📋 Planned

---

## EXECUTIVE SUMMARY

**Goal:** Make CSV export work for all strategies (S01, S04, S05, etc.) with strategy-specific parameter columns

**Current State:**
- S01: CSV export works (hardcoded columns)
- S04: CSV export only shows metrics, not parameters

**Target State:**
- S01: CSV export unchanged (backward compatible)
- S04: CSV shows rsiLen, stochLen, obLevel, etc. columns
- Future strategies: Automatically generate correct columns

**Approach:** Dynamic column generation based on strategy config.json

**Files to Modify:**
1. `src/core/export.py` - Add dynamic column generation
2. `src/server.py` - Pass strategy_id to export function
3. `src/core/optuna_engine.py` - Ensure dynamic attributes stored (prerequisite)

---

## PROBLEM STATEMENT

### Current CSV Export for S01 (Works)

**Code:** `src/core/export.py` lines 19-54

```python
CSV_COLUMN_SPECS = [
    # Tuple format: (label, frontend_name, internal_name, formatter)
    ("Trend MA", "maType", "ma_type", None),
    ("MA Length", "maLength", "ma_length", None),
    ("Close Count Long", "closeCountLong", "close_count_long", None),
    ("Close Count Short", "closeCountShort", "close_count_short", None),
    # ... 15 more S01 parameters ...
    ("Net Profit%", None, "net_profit_pct", "percent"),
    ("Max DD%", None, "max_drawdown_pct", "percent"),
    ("Trades", None, "total_trades", None),
    ("Score", None, "score", "float"),
    # ... metrics ...
]
```

**Generated CSV:**
```csv
Trend MA,MA Length,Close Count Long,...,Net Profit%,Max DD%,Trades,Score
EMA,175,7,...,25.0,5.0,50,8.5
SMA,200,5,...,22.0,6.0,45,7.8
```

✅ Works perfectly for S01

---

### Current CSV Export for S04 (Broken)

**Problem:** Uses same `CSV_COLUMN_SPECS`, but S04 has different parameters

**S04 Parameters:**
- rsiLen, stochLen, kLen, dLen, obLevel, osLevel, extLookback, confirmBars

**OptimizationResult for S04:**
```python
opt_result.ma_type = ""           # Empty (not used by S04)
opt_result.ma_length = 0          # Empty
opt_result.rsiLen = 24            # S04 param (if dynamic storage added)
opt_result.stochLen = 16          # S04 param
opt_result.net_profit_pct = 25.0  # Metric
```

**Current CSV Output:**
```csv
Trend MA,MA Length,Close Count Long,...,Net Profit%,Max DD%,Trades,Score
,0,0,...,25.0,5.0,50,8.5
,0,0,...,22.0,6.0,45,7.8
```

❌ S01 columns are empty, S04 params not shown!

---

### Expected CSV Export for S04

**Goal:**
```csv
RSI Length,Stoch Length,OB Level,OS Level,Extremum Lookback,Confirm Bars,Net Profit%,Max DD%,Trades,Score
4,4,75.0,15.0,23,14,25.0,5.0,50,8.5
6,6,80.0,20.0,30,20,27.0,6.0,55,9.0
8,8,75.0,15.0,25,16,22.0,7.0,48,7.5
```

✅ Shows S04 parameters with human-readable labels
✅ Includes standard metrics (net profit, trades, etc.)
✅ Sortable and filterable by parameter values

---

## SOLUTION ARCHITECTURE

### Design Principles

1. **Backward Compatibility:** S01 CSV export must remain unchanged
2. **Strategy-Agnostic:** Works for any strategy with config.json
3. **Single Source of Truth:** Parameter definitions come from config.json
4. **Minimal Code Changes:** Reuse existing export logic where possible
5. **Maintainable:** Clear separation between S01 (legacy) and dynamic (new)

---

### High-Level Flow

```
┌─────────────────────────────────────────────────────────┐
│ 1. Optimization Completes                               │
│    - S04 ran 100 trials                                 │
│    - Results list contains 100 OptimizationResult objs  │
│    - Each result has dynamic attrs: rsiLen, obLevel...  │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│ 2. server.py calls export_optuna_results()             │
│    - Passes results list                                │
│    - Passes fixed_params dict                           │
│    - Passes strategy_id="s04_stochrsi"  ← NEW           │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│ 3. export.py detects strategy type                     │
│    - if strategy_id == "s01_trailing_ma":               │
│        Use hardcoded CSV_COLUMN_SPECS                   │
│    - else:                                              │
│        Build column specs dynamically                   │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│ 4. Dynamic Column Building                              │
│    - get_strategy_config(strategy_id)                   │
│    - Read parameters from config.json                   │
│    - Build specs: [(label, frontend, internal, fmt)]   │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│ 5. CSV Generation (existing logic)                     │
│    - Filter columns (remove fixed params)               │
│    - Write header row                                   │
│    - Write data rows with getattr(result, attr, "")    │
└─────────────────────────────────────────────────────────┘
                     ↓
                   CSV File
```

---

## IMPLEMENTATION PLAN

### Prerequisite: Ensure Dynamic Attribute Storage

**Status:** ⚠️ NOT YET IN CODEBASE (see prompt_9-2_fix_codex_audit.md)

**Required Change:** Add 3 lines to `src/core/optuna_engine.py` line 298

```python
# Store S04 params as dynamic attributes
for key, value in params_dict.items():
    if not hasattr(opt_result, key):
        setattr(opt_result, key, value)
```

**Why Needed:** CSV export can't show parameters that aren't in the result object

**Test:**
```python
opt_result = _run_single_combination(args)
assert hasattr(opt_result, 'rsiLen')  # Must exist
assert opt_result.rsiLen == 24        # Must have value
```

Without this, the CSV export enhancement won't work!

---

### Step 1: Add Dynamic Column Builder to export.py

**File:** `src/core/export.py`
**Location:** After line 96 (after `_format_csv_value` function)

**Add Function:**

```python
def _build_column_specs_for_strategy(
    strategy_id: str,
) -> List[Tuple[str, Optional[str], str, Optional[str]]]:
    """
    Build CSV column specifications dynamically from strategy config.

    For S01: Returns hardcoded CSV_COLUMN_SPECS (backward compatible)
    For other strategies: Generates specs from config.json

    Args:
        strategy_id: Strategy identifier (e.g., 's04_stochrsi')

    Returns:
        List of tuples: (label, frontend_name, internal_name, formatter)

        Example:
        [
            ("RSI Length", "rsiLen", "rsiLen", None),
            ("OB Level", "obLevel", "obLevel", "float1"),
            ("Net Profit%", None, "net_profit_pct", "percent"),
            ...
        ]
    """
    from strategies import get_strategy_config

    # S01: Use existing hardcoded specs (backward compatible)
    if strategy_id == "s01_trailing_ma":
        return CSV_COLUMN_SPECS

    # Other strategies: Build specs dynamically
    try:
        config = get_strategy_config(strategy_id)
    except (ValueError, KeyError):
        # Strategy not found, use hardcoded specs as fallback
        return CSV_COLUMN_SPECS

    parameters = config.get("parameters", {})
    if not isinstance(parameters, dict):
        return CSV_COLUMN_SPECS

    specs: List[Tuple[str, Optional[str], str, Optional[str]]] = []

    # Add parameter columns (same order as config.json)
    for frontend_name, param_spec in parameters.items():
        if not isinstance(param_spec, dict):
            continue

        param_type = param_spec.get("type", "float")
        label = param_spec.get("label", frontend_name)  # Human-readable label

        # Use camelCase name as internal name (matches dynamic storage)
        # S04 stores as "rsiLen", not "rsi_len"
        internal_name = frontend_name

        # Determine formatter based on parameter type
        if param_type == "int":
            formatter = None  # No decimals for integers
        elif param_type == "float":
            formatter = "float1"  # 1 decimal place
        elif param_type == "select":
            formatter = None  # String values (e.g., "EMA")
        else:
            formatter = None  # Default: no formatting

        # Tuple: (label, frontend_name, internal_name, formatter)
        # frontend_name is used to check if param is in fixed_params (filtering)
        # internal_name is used to access attribute on result object
        specs.append((label, frontend_name, internal_name, formatter))

    # Add standard metric columns (same for all strategies)
    metric_specs = [
        ("Net Profit%", None, "net_profit_pct", "percent"),
        ("Max DD%", None, "max_drawdown_pct", "percent"),
        ("Trades", None, "total_trades", None),
        ("Score", None, "score", "float"),
        ("RoMaD", None, "romad", "optional_float"),
        ("Sharpe", None, "sharpe_ratio", "optional_float"),
        ("PF", None, "profit_factor", "optional_float"),
        ("Ulcer", None, "ulcer_index", "optional_float"),
        ("Recover", None, "recovery_factor", "optional_float"),
        ("Consist", None, "consistency_score", "optional_float"),
    ]

    specs.extend(metric_specs)

    return specs
```

**How It Works:**

1. **S01 Path:** Returns `CSV_COLUMN_SPECS` immediately → no changes to S01 export
2. **S04 Path:**
   - Reads S04's config.json
   - Extracts parameters with labels ("RSI Length", "Stoch Length", etc.)
   - Determines formatter based on type (int → no decimals, float → 1 decimal)
   - Uses camelCase names as internal names ("rsiLen", not "rsi_len")
   - Appends standard metrics (same for all strategies)
   - Returns combined list

**Key Design Decision:**
```python
internal_name = frontend_name  # Uses "rsiLen" for both
```

This matches how dynamic attributes are stored in OptimizationResult. No conversion needed!

---

### Step 2: Update export_optuna_results() Signature

**File:** `src/core/export.py`
**Location:** Line 98

**Change:**

```python
# OLD:
def export_optuna_results(
    results: List[OptimizationResult],
    fixed_params: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]],
    *,
    filter_min_profit: bool = False,
    min_profit_threshold: float = 0.0,
    optimization_metadata: Optional[Dict[str, Any]] = None,
) -> str:

# NEW (add strategy_id parameter):
def export_optuna_results(
    results: List[OptimizationResult],
    fixed_params: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]],
    *,
    filter_min_profit: bool = False,
    min_profit_threshold: float = 0.0,
    optimization_metadata: Optional[Dict[str, Any]] = None,
    strategy_id: str = "s01_trailing_ma",  # NEW
) -> str:
```

**Purpose:** Pass strategy_id to determine which column specs to use

**Default:** `"s01_trailing_ma"` for backward compatibility with existing calls

---

### Step 3: Use Dynamic Column Specs in Export Logic

**File:** `src/core/export.py`
**Location:** Line 158 (in `export_optuna_results` function)

**Change:**

```python
# OLD (line 158):
filtered_columns = [
    spec for spec in CSV_COLUMN_SPECS if spec[1] is None or spec[1] not in fixed_lookup
]

# NEW:
column_specs = _build_column_specs_for_strategy(strategy_id)
filtered_columns = [
    spec for spec in column_specs if spec[1] is None or spec[1] not in fixed_lookup
]
```

**How It Works:**

1. Calls `_build_column_specs_for_strategy(strategy_id)` to get appropriate specs
2. For S01: Returns hardcoded `CSV_COLUMN_SPECS`
3. For S04: Returns dynamically generated specs
4. Filters out columns for parameters in `fixed_params` (same logic as before)

**Example for S04:**

```python
# User enabled rsiLen and obLevel for optimization
# stochLen is fixed at 16

column_specs = [
    ("RSI Length", "rsiLen", "rsiLen", None),         # Will be included
    ("Stoch Length", "stochLen", "stochLen", None),   # Will be FILTERED OUT (fixed)
    ("OB Level", "obLevel", "obLevel", "float1"),     # Will be included
    ("Net Profit%", None, "net_profit_pct", "percent"),  # Will be included (no frontend_name)
    ...
]

fixed_lookup = {"stochLen": 16}

filtered_columns = [
    ("RSI Length", "rsiLen", "rsiLen", None),
    ("OB Level", "obLevel", "obLevel", "float1"),
    ("Net Profit%", None, "net_profit_pct", "percent"),
    ...
]
```

Result: CSV includes rsiLen and obLevel columns, but NOT stochLen (fixed param shown in header block)

---

### Step 4: Handle Missing Attributes Gracefully

**File:** `src/core/export.py`
**Location:** Line 175 (data row writing loop)

**Current Code (works but can be improved):**

```python
for item in filtered_results:
    row_values = []
    for _, frontend_name, attr_name, formatter in filtered_columns:
        value = getattr(item, attr_name)  # May raise AttributeError
        row_values.append(_format_csv_value(value, formatter))
    output.write(",".join(row_values) + "\n")
```

**Enhanced Code (safer):**

```python
for item in filtered_results:
    row_values = []
    for _, frontend_name, attr_name, formatter in filtered_columns:
        # Use getattr with default to handle missing attributes
        value = getattr(item, attr_name, "")  # Returns "" if attribute missing
        row_values.append(_format_csv_value(value, formatter))
    output.write(",".join(row_values) + "\n")
```

**Why:**
- If dynamic attribute storage fails for some reason, CSV export won't crash
- Missing values show as empty cells instead of raising AttributeError
- Defensive programming

---

### Step 5: Update server.py to Pass strategy_id

**File:** `src/server.py`
**Location:** Line 1729 (in `/api/optimize` endpoint)

**Change:**

```python
# OLD (line 1729):
csv_content = export_optuna_results(
    results,
    fixed_parameters,
    filter_min_profit=optimization_config.filter_min_profit,
    min_profit_threshold=optimization_config.min_profit_threshold,
    optimization_metadata=optimization_metadata,
)

# NEW (add strategy_id parameter):
csv_content = export_optuna_results(
    results,
    fixed_parameters,
    filter_min_profit=optimization_config.filter_min_profit,
    min_profit_threshold=optimization_config.min_profit_threshold,
    optimization_metadata=optimization_metadata,
    strategy_id=optimization_config.strategy_id,  # NEW
)
```

**Purpose:** Pass strategy_id from optimization config to export function

**Requirement:** `optimization_config` must have `strategy_id` attribute (already exists after commit c3d42dd)

---

## TESTING REQUIREMENTS

### Test 1: S01 CSV Export Unchanged (CRITICAL)

**Objective:** Verify S01 CSV export is byte-for-byte identical to before enhancement

**Test Case:**
```bash
Strategy: S01 Trailing MA
Parameters: maLength (25-500, step 25), closeCountLong (2-10, step 1)
Trials: 50
```

**Expected CSV Header:**
```csv
Trend MA,MA Length,Close Count Long,Close Count Short,...,Net Profit%,Max DD%,Trades,Score,...
```

**Pass Criteria:**
- ✅ All S01 parameter columns present
- ✅ Column order identical to before
- ✅ Data rows have correct values
- ✅ No regressions in formatting

**Verification:**
```bash
# Export S01 results before and after enhancement
diff old_s01_export.csv new_s01_export.csv
# Should show no differences (or only data value differences, not structure)
```

---

### Test 2: S04 CSV Includes Parameters (PRIMARY GOAL)

**Objective:** Verify S04 CSV export includes parameter columns

**Test Case:**
```bash
Strategy: S04 StochRSI
Parameters to vary:
  - rsiLen: 4 to 50, step 2
  - obLevel: 60 to 90, step 1
Fixed parameters:
  - stochLen: 16
Trials: 20
```

**Expected CSV Header:**
```csv
RSI Length,OB Level,Net Profit%,Max DD%,Trades,Score,RoMaD,Sharpe,PF,Ulcer,Recover,Consist
```

**Expected Data Row (example):**
```csv
24,75.0,25.0,5.0,50,8.5,5.0,1.5,2.0,3.2,5.0,0.8
```

**Pass Criteria:**
- ✅ CSV includes "RSI Length" column with varied values (4, 6, 8, 10...)
- ✅ CSV includes "OB Level" column with varied values (60.0, 61.0, 62.0...)
- ✅ CSV does NOT include "Stoch Length" column (fixed param)
- ✅ Fixed parameters shown in header block
- ✅ Metrics columns present (Net Profit%, Max DD%, etc.)
- ✅ All values formatted correctly

**Fixed Param Block (top of CSV):**
```
# Fixed Parameters:
# Stoch Length = 16
# %K Smoothing = 3
# %D Smoothing = 3
# ...
```

---

### Test 3: Multi-Parameter S04 Export

**Objective:** Verify all optimized S04 parameters appear in CSV

**Test Case:**
```bash
Strategy: S04 StochRSI
Parameters to vary:
  - rsiLen: 4 to 50, step 2
  - stochLen: 4 to 50, step 2
  - obLevel: 60 to 90, step 1
  - osLevel: 5 to 30, step 1
  - extLookback: 5 to 60, step 1
  - confirmBars: 2 to 40, step 1
Trials: 100
```

**Expected CSV Header:**
```csv
RSI Length,Stoch Length,Overbought Level,Oversold Level,Extremum Lookback,Confirm Bars,Net Profit%,Max DD%,...
```

**Pass Criteria:**
- ✅ All 6 parameter columns present
- ✅ Human-readable labels from config.json
- ✅ All values correct (match OptimizationResult attributes)
- ✅ Sortable by any parameter column
- ✅ No empty or missing values

---

### Test 4: Column Filtering (Fixed Parameters)

**Objective:** Verify fixed parameters don't appear as columns

**Test Case:**
```bash
Strategy: S04 StochRSI
Enabled: rsiLen, obLevel
Fixed: stochLen=16, osLevel=15, extLookback=23, confirmBars=14
```

**Expected CSV Header:**
```csv
RSI Length,Overbought Level,Net Profit%,Max DD%,...
```

**NOT Expected:**
```csv
RSI Length,Stoch Length,Overbought Level,Oversold Level,...  ← stochLen, osLevel shouldn't be here
```

**Pass Criteria:**
- ✅ Only varied parameters appear as columns
- ✅ Fixed parameters in header block
- ✅ Correct filtering logic

---

### Test 5: Parameter Labels from config.json

**Objective:** Verify labels match config.json, not parameter names

**S04 config.json:**
```json
{
  "rsiLen": {
    "label": "RSI Length",  ← Use this
    ...
  },
  "obLevel": {
    "label": "Overbought Level",  ← Use this
    ...
  }
}
```

**Expected CSV Header:**
```csv
RSI Length,Overbought Level,...  ← Labels, not "rsiLen", "obLevel"
```

**Pass Criteria:**
- ✅ Column headers use labels from config.json
- ✅ Human-readable (e.g., "RSI Length" not "rsiLen")
- ✅ Consistent with config.json definitions

---

### Test 6: Formatter Correctness

**Objective:** Verify numeric formatting is correct

**Parameter Types:**
- `rsiLen` (int) → No decimals: `24`, not `24.0`
- `obLevel` (float) → 1 decimal: `75.0`, not `75` or `75.00`
- `net_profit_pct` (float, percent) → `25.0%`

**Pass Criteria:**
- ✅ Integers have no decimals
- ✅ Floats have 1 decimal place
- ✅ Percents formatted with % sign
- ✅ Optional values (Sharpe, RoMaD) handle None gracefully

---

### Test 7: Empty Results Handling

**Objective:** Verify export handles edge cases

**Test Case 1: No Results**
```python
results = []
csv = export_optuna_results(results, {}, strategy_id="s04_stochrsi")
```

**Expected:** CSV with header only, no data rows

**Test Case 2: Single Result**
```python
results = [opt_result]  # One result
csv = export_optuna_results(results, {}, strategy_id="s04_stochrsi")
```

**Expected:** CSV with header + 1 data row

**Test Case 3: Missing Attributes**
```python
# Result missing rsiLen attribute (dynamic storage failed)
opt_result.rsiLen  # AttributeError
csv = export_optuna_results([opt_result], {}, strategy_id="s04_stochrsi")
```

**Expected:** CSV with empty cell for rsiLen (not crash)

---

## EDGE CASES AND ERROR HANDLING

### Edge Case 1: Strategy Config Not Found

**Scenario:** `get_strategy_config()` raises ValueError (unknown strategy)

**Handling:**
```python
try:
    config = get_strategy_config(strategy_id)
except (ValueError, KeyError):
    return CSV_COLUMN_SPECS  # Fallback to S01 specs
```

**Result:** Defaults to S01 column specs (safe fallback)

---

### Edge Case 2: Malformed config.json

**Scenario:** `parameters` key missing or wrong type

**Handling:**
```python
parameters = config.get("parameters", {})
if not isinstance(parameters, dict):
    return CSV_COLUMN_SPECS
```

**Result:** Fallback to S01 specs

---

### Edge Case 3: Missing Parameter Labels

**Scenario:** Parameter has no `"label"` field in config.json

**Handling:**
```python
label = param_spec.get("label", frontend_name)  # Use param name as fallback
```

**Result:** Uses parameter name as label (e.g., "rsiLen" instead of "RSI Length")

---

### Edge Case 4: Dynamic Attribute Missing

**Scenario:** Result object doesn't have S04 parameter attributes

**Handling:**
```python
value = getattr(item, attr_name, "")  # Returns "" if missing
```

**Result:** Empty cell in CSV (not crash)

**Root Cause:** Dynamic attribute storage not implemented → Fix prerequisite first!

---

### Edge Case 5: Unknown Parameter Type

**Scenario:** Parameter type is neither "int", "float", nor "select"

**Handling:**
```python
if param_type == "int":
    formatter = None
elif param_type == "float":
    formatter = "float1"
else:
    formatter = None  # Default: no formatting
```

**Result:** No formatting applied (safe default)

---

### Edge Case 6: Mixed Strategy Results

**Scenario:** Results list contains both S01 and S04 results (should never happen, but...)

**Current Design:** Assumes all results are from same strategy

**Mitigation:** Optuna engine only runs one strategy per session

**If Needed:** Could detect strategy from result attributes, but adds complexity

---

## CODE STRUCTURE

### Summary of Changes

**File 1: `src/core/export.py`**
- **Add:** `_build_column_specs_for_strategy()` function (~80 lines)
- **Modify:** `export_optuna_results()` signature (1 line)
- **Modify:** Column spec selection (1 line at line 158)
- **Modify:** Attribute access safety (1 line at line 175)

**Total:** ~83 lines added/modified

**File 2: `src/server.py`**
- **Modify:** Export function call (1 line at line 1729)

**Total:** 1 line modified

**File 3: `src/core/optuna_engine.py` (prerequisite)**
- **Modify:** Dynamic attribute storage (3 lines at line 298)

**Total:** 3 lines added

**Grand Total:** ~87 lines across 3 files

---

### Complexity Assessment

**New Functions:** 1 (`_build_column_specs_for_strategy`)

**Cyclomatic Complexity:**
- `_build_column_specs_for_strategy`: Medium (branching on strategy_id, error handling)
- Rest: Low (single-line changes)

**Risk Level:** Low-Medium
- S01 path completely unchanged (backward compatible)
- S04 path new code (needs testing)
- Error handling in place (fallbacks to S01 specs)

---

## BENEFITS

### Benefit 1: Complete S04 Support

**Before:** S04 optimization works, but CSV export incomplete
**After:** S04 optimization + CSV export both work

**User Impact:**
- Can analyze S04 optimization results
- Can sort/filter by parameter values
- Can import winning parameters

---

### Benefit 2: Future-Proof

**New Strategy (e.g., S05 Bollinger Bands):**
1. Create S05 config.json with parameters
2. **CSV export automatically works!**
3. No code changes needed

**How:** `_build_column_specs_for_strategy()` reads any strategy's config

---

### Benefit 3: Backward Compatible

**S01 users:** No changes
**S01 CSV format:** Identical to before
**S01 code path:** Uses hardcoded specs (unchanged)

**Zero risk of breaking existing S01 functionality.**

---

### Benefit 4: Maintainable

**Single Source of Truth:** config.json defines parameters + labels

**No Duplication:**
- Don't maintain separate label lists
- Don't hardcode column specs per strategy
- Config change automatically reflects in CSV

**Clear Code:**
- `if strategy_id == "s01": use old way`
- `else: use new way`
- Easy to understand

---

### Benefit 5: Human-Readable CSVs

**Before (if we used param names):**
```csv
rsiLen,stochLen,obLevel,...
24,16,75.0,...
```

**After (with labels from config):**
```csv
RSI Length,Stoch Length,Overbought Level,...
24,16,75.0,...
```

**Better UX:** Users understand column headers without documentation

---

## RISKS AND MITIGATION

### Risk 1: S01 CSV Format Changes

**Probability:** Low (explicit `if` check prevents this)

**Impact:** High (breaks existing workflows)

**Mitigation:**
- Hardcoded check: `if strategy_id == "s01_trailing_ma"`
- Comprehensive S01 regression tests
- Byte-for-byte CSV comparison before/after

**Fallback:** Can revert export.py changes without affecting optimization

---

### Risk 2: Missing Dynamic Attributes

**Probability:** High if prerequisite not done

**Impact:** High (CSV export shows empty parameter columns)

**Mitigation:**
- **MUST implement prerequisite first** (3-line addition to optuna_engine.py)
- Test that attributes exist: `assert hasattr(opt_result, 'rsiLen')`
- Graceful handling: `getattr(item, attr_name, "")` returns empty string

**Dependency:** This enhancement REQUIRES dynamic attribute storage

---

### Risk 3: Config.json Schema Changes

**Probability:** Low (config schema is stable)

**Impact:** Medium (CSV export breaks if schema changes)

**Mitigation:**
- Defensive coding: `config.get("parameters", {})`
- Error handling: try/except with fallback to S01 specs
- Type checks: `if isinstance(parameters, dict)`

**Robustness:** Code handles missing/malformed config gracefully

---

### Risk 4: Performance with Many Parameters

**Probability:** Low (strategies typically have <20 parameters)

**Impact:** Low (CSV generation is fast)

**Concern:** Iterating config.json parameters on every export

**Mitigation:**
- Config parsing is lightweight
- Only done once per optimization session (results exported once)
- Can cache column specs if needed (future optimization)

**Not a practical concern.**

---

## IMPLEMENTATION CHECKLIST

### Prerequisites
- [ ] Dynamic attribute storage implemented (3 lines in optuna_engine.py)
- [ ] Verified S04 results have `rsiLen`, `obLevel`, etc. attributes
- [ ] Tested: `hasattr(opt_result, 'rsiLen')` returns True

### Core Implementation
- [ ] Add `_build_column_specs_for_strategy()` to export.py
- [ ] Update `export_optuna_results()` signature
- [ ] Update column spec selection (line 158)
- [ ] Update attribute access (line 175)
- [ ] Update export call in server.py (line 1729)

### Testing
- [ ] Test 1: S01 CSV export unchanged
- [ ] Test 2: S04 CSV includes parameter columns
- [ ] Test 3: Multi-parameter S04 export
- [ ] Test 4: Column filtering (fixed params)
- [ ] Test 5: Parameter labels from config.json
- [ ] Test 6: Formatter correctness
- [ ] Test 7: Edge cases (empty results, missing attributes)

### Documentation
- [ ] Update CLAUDE.md with CSV export enhancement
- [ ] Document column spec format
- [ ] Add examples for S04 CSV output

### Deployment
- [ ] Run full test suite (S01 + S04)
- [ ] Compare S01 CSVs before/after
- [ ] Verify S04 CSVs have correct structure
- [ ] Merge to main branch

---

## FUTURE ENHANCEMENTS

### Enhancement 1: Caching Column Specs

**Current:** Builds column specs on every export call

**Optimization:** Cache specs per strategy
```python
_COLUMN_SPEC_CACHE: Dict[str, List[...]] = {}

def _build_column_specs_for_strategy(strategy_id):
    if strategy_id in _COLUMN_SPEC_CACHE:
        return _COLUMN_SPEC_CACHE[strategy_id]

    specs = ...  # Build specs
    _COLUMN_SPEC_CACHE[strategy_id] = specs
    return specs
```

**Benefit:** Faster repeated exports (minor, not critical)

---

### Enhancement 2: Custom Column Order

**Current:** Column order matches config.json parameter order

**Enhancement:** Allow users to specify column order
```json
{
  "csv_export": {
    "column_order": ["rsiLen", "obLevel", "net_profit_pct", ...]
  }
}
```

**Benefit:** Users can customize CSV layout

---

### Enhancement 3: Conditional Columns

**Current:** All parameters included (except fixed ones)

**Enhancement:** Hide parameters with no variation
```python
# If all trials have same value, don't show as column
if len(set(result.rsiLen for result in results)) == 1:
    skip_column("rsiLen")
```

**Benefit:** Cleaner CSVs when many params are effectively fixed

---

### Enhancement 4: Export to Multiple Formats

**Current:** Only CSV export

**Enhancement:** Support JSON, Excel, Parquet
```python
export_format = "csv"  # or "json", "xlsx", "parquet"
```

**Benefit:** Better for large datasets, programmatic access

---

## CONCLUSION

### Summary

**Goal:** Strategy-agnostic CSV export system

**Approach:**
- Keep S01 path unchanged (backward compatible)
- Add dynamic column generation for other strategies
- Read parameter definitions from config.json
- Minimal code changes (~87 lines across 3 files)

**Dependencies:**
- Requires dynamic attribute storage (prerequisite)
- Requires strategy_id in optimization config (already exists)

**Benefits:**
- S04 CSV export works
- Future strategies work automatically
- Human-readable column headers
- Maintainable single source of truth

**Risks:**
- Low (S01 explicitly protected)
- Comprehensive testing required
- Prerequisite must be done first

**Recommendation:** ✅ Implement after prerequisite is complete

### Comparison with Hardcoding S04 Columns

| Aspect | Hardcoded S04 Specs | Dynamic Generation |
|--------|--------------------|--------------------|
| **Code Lines** | ~40 lines | ~80 lines |
| **S01 Safety** | ✅ Same | ✅ Same |
| **S04 Support** | ✅ Works | ✅ Works |
| **S05 Support** | ❌ Need more code | ✅ Automatic |
| **Maintainability** | ❌ Duplication | ✅ Single source |
| **Flexibility** | ❌ Manual per strategy | ✅ Adapts automatically |

**Winner:** Dynamic Generation (more code upfront, but future-proof)

### Final Verdict

**Status:** ✅ **Recommended for implementation**

**Priority:** MEDIUM (optimization works, this is reporting enhancement)

**Complexity:** Low-Medium

**Risk:** Low

**Timeline:** 1-2 days development + testing

**Impact:** Completes S04 support, enables future strategies

This enhancement completes the strategy-agnostic architecture and provides a solid foundation for all future strategies.
