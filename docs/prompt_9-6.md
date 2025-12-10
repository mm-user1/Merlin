# Phase 9-6: Remove Hardcoded S01 Dependencies — Make Core Generic & Config-Driven

## 🎯 Mission

You are tasked with **removing all hardcoded S01-specific parameter references** from the core modules (`server.py`, `walkforward_engine.py`, `backtest_engine.py`) and making the codebase **fully config-driven and strategy-agnostic**.

This is **Phase 9-6** of a cryptocurrency trading strategy backtesting and optimization platform that uses:
- **Typed strategy modules** with camelCase parameters (Pine Script → Python)
- **Generic config-driven core** (Optuna-only optimizer, Flask SPA frontend)
- **Auto-discovery strategy system** via `config.json` + `strategy.py`

Your changes must ensure that **any new strategy** (S04, S05, etc.) can be added without modifying core modules.

---

## 📋 Issues to Fix

### Issue 1: CSV Import Hardcodes MA Fields
**Location:** `src/server.py:300-317` (`_parse_csv_parameter_block`)

**Problem:**
The CSV import function explicitly checks for `maType`, `trailLongType`, and `trailShortType` and uppercases them into array fields. This breaks CSV import for non-S01 strategies (e.g., S04 StochRSI, which has no MA parameters).

**Current Code (Lines 300-317):**
```python
if name == "maType":
    value = str(raw_value or "").strip().upper()
    if value:
        updates["trendMATypes"] = [value]
        applied.append("trendMATypes")
    continue
if name == "trailLongType":
    value = str(raw_value or "").strip().upper()
    if value:
        updates["trailLongTypes"] = [value]
        applied.append("trailLongTypes")
    continue
if name == "trailShortType":
    value = str(raw_value or "").strip().upper()
    if value:
        updates["trailShortTypes"] = [value]
        applied.append("trailShortTypes")
    continue
```

**Required Fix:**
1. **Remove all hardcoded `maType`, `trailLongType`, `trailShortType` handling**
2. Make CSV import **generic and config-driven**:
   - Accept `strategy` parameter from form data
   - Load parameter types from `strategies.get_strategy_config(strategy_id)["parameters"]`
   - For each CSV row, look up the parameter type in the config
   - If type is `"select"` or `"options"`, uppercase the value (generic handling)
   - Otherwise, use `_convert_import_value(name, raw_value)` as-is
3. Add fallback: if `strategy` not provided, use first available strategy from `list_strategies()`
4. **Preserve existing special-case handling** for `start`/`end` (date splitting) and internal fields (`dateFilter`, `nTrials`, etc.)

**Example Logic:**
```python
# Resolve strategy_id from request
strategy_id = request.form.get("strategy") or request.get_json(silent=True).get("strategy")
if not strategy_id:
    available = list_strategies()
    strategy_id = available[0]["id"] if available else None

# Load parameter types
param_types = {}
if strategy_id:
    try:
        config = get_strategy_config(strategy_id)
        for param_name, param_spec in config.get("parameters", {}).items():
            param_types[param_name] = param_spec.get("type", "float")
    except Exception:
        pass  # Fall back to generic handling

# Process each CSV parameter
for name, raw_value in parameters.items():
    if name == "start":
        # ... existing date handling
        continue
    if name == "end":
        # ... existing date handling
        continue

    # Generic select/options handling
    param_type = param_types.get(name, "").lower()
    if param_type in {"select", "options"}:
        value = str(raw_value or "").strip().upper()
        if value:
            updates[name] = value
            applied.append(name)
        continue

    # Default conversion
    converted = _convert_import_value(name, raw_value)
    updates[name] = converted
    applied.append(name)
```

---

### Issue 2: Walk-Forward Reporting Locks to S01 Fields
**Location:** `src/core/walkforward_engine.py:583, 1045-1072`

**Problem:**
Two functions hardcode S01 parameter names:
1. **`_create_param_id` (line 583)** — builds param IDs using `params.get("maType")` and `params.get("maLength")`
2. **`export_wf_results_csv` (lines 1045-1072)** — writes a fixed list of S01 parameters to the CSV

This prevents WFA from working with S04 or any future strategies.

#### Fix 2.1: Make `_create_param_id` Generic

**Current Code (Lines 577-589):**
```python
def _create_param_id(self, params: Dict[str, Any]) -> str:
    """
    Create unique ID for param set
    Format: "MA_TYPE MA_LENGTH_hash"
    Example: "EMA 45_6d4ad0df"
    """
    ma_type = params.get("maType", "UNKNOWN")
    ma_length = params.get("maLength", 0)

    param_str = json.dumps(params, sort_keys=True)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]

    return f"{ma_type} {ma_length}_{param_hash}"
```

**Required Fix:**
1. Load `config.json` parameters for the strategy (`self.config.strategy_id`)
2. Find the **first two optimizable parameters** (where `optimize.enabled == true`)
3. Use those parameter values for the label (fallback to hash if < 2 params)
4. Format: `"{param1_value} {param2_value}_{hash}"` or `"{hash}"` if no optimizable params

**Example Implementation:**
```python
def _create_param_id(self, params: Dict[str, Any]) -> str:
    """
    Create unique ID for param set using first 2 optimizable parameters.
    Format: "VALUE1 VALUE2_hash" or "hash" if no optimizable params found.
    Examples:
      S01: "EMA 45_6d4ad0df"
      S04: "16 75.0_a3b5c7e9"
    """
    from strategies import get_strategy_config

    try:
        config = get_strategy_config(self.config.strategy_id)
        parameters = config.get("parameters", {})

        # Find first 2 optimizable parameters (in definition order)
        optimizable = []
        for param_name, param_spec in parameters.items():
            optimize_cfg = param_spec.get("optimize", {})
            if optimize_cfg.get("enabled", False):
                optimizable.append(param_name)
            if len(optimizable) == 2:
                break

        # Build label from first 2 optimizable param values
        label_parts = []
        for param_name in optimizable:
            value = params.get(param_name, "?")
            label_parts.append(str(value))

        # Generate hash
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]

        if label_parts:
            label = " ".join(label_parts)
            return f"{label}_{param_hash}"
        else:
            return param_hash

    except Exception:
        # Fallback: use hash only
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
        return param_hash
```

#### Fix 2.2: Make CSV Export Generic

**Current Code (Lines 1038-1095):**
```python
writer.writerow(["=== DETAILED PARAMETERS FOR TOP 10 ==="])
writer.writerow([])

for rank, agg in enumerate(result.aggregated[:10], 1):
    writer.writerow([f"--- Rank #{rank}: {agg.param_id} ---"])
    params = agg.params
    writer.writerow(["Parameter", "Value"])
    writer.writerow(["MA Type", params.get("maType", "N/A")])
    writer.writerow(["MA Length", params.get("maLength", "N/A")])
    writer.writerow(["Close Count Long", params.get("closeCountLong", "N/A")])
    # ... 20+ hardcoded S01 parameters ...
```

**Required Fix:**
1. Load `config.json` for `result.strategy_id`
2. Iterate over **all parameters** in definition order (preserve `config.json` order)
3. For each parameter, write: `[label, params.get(param_name, "N/A")]`
4. Use the `label` field from config, fallback to `param_name` if missing

**Example Implementation:**
```python
writer.writerow(["=== DETAILED PARAMETERS FOR TOP 10 ==="])
writer.writerow([])

# Load strategy config to get parameter definitions
from strategies import get_strategy_config

try:
    config = get_strategy_config(result.strategy_id)
    param_definitions = config.get("parameters", {})
except Exception:
    param_definitions = {}

for rank, agg in enumerate(result.aggregated[:10], 1):
    writer.writerow([f"--- Rank #{rank}: {agg.param_id} ---"])
    params = agg.params
    writer.writerow(["Parameter", "Value"])

    # Iterate over parameters in config order
    for param_name, param_spec in param_definitions.items():
        label = param_spec.get("label", param_name)
        value = params.get(param_name, "N/A")
        writer.writerow([label, value])

    # Performance Metrics section (unchanged)
    writer.writerow([])
    writer.writerow(["Performance Metrics", ""])
    writer.writerow(["Appearance", agg.appearances])
    # ... rest of metrics ...
```

---

### Issue 3: Unused Imports and Dead Helper in backtest_engine.py
**Location:** `src/core/backtest_engine.py:7-21`

**Problem:**
1. **Lines 7-21:** Unused MA function imports (`alma`, `dema`, `ema`, etc.)
2. **Lines 135-141:** Dead code — `compute_max_drawdown` function not called anywhere

**Required Fix:**
1. **Remove all unused MA imports** (lines 7-21):
   ```python
   from indicators.ma import (
       VALID_MA_TYPES,
       alma, dema, ema, get_ma, hma, kama, sma, t3, tma, vwap, vwma, wma,
   )
   ```
   **Keep only:** `VALID_MA_TYPES, get_ma` (if referenced elsewhere, otherwise remove all)

2. **Remove dead helper function** `compute_max_drawdown` (lines 135-141):
   ```python
   def compute_max_drawdown(equity_curve: pd.Series) -> float:
       equity_curve = equity_curve.ffill()
       drawdown = 1 - equity_curve / equity_curve.cummax()
       _, peak_dd = _stats.compute_drawdown_duration_peaks(drawdown)
       if peak_dd.isna().all():
           return 0.0
       return peak_dd.max() * 100
   ```

3. **Verify no references exist** by searching the codebase:
   - Search for `compute_max_drawdown` (should find only the definition)
   - Search for individual MA function calls (`alma(`, `dema(`, etc.) in `backtest_engine.py`

**Expected Cleanup:**
- Reduced module load time
- Cleaner imports
- No functional changes (these were unused)

---

## 🧪 Testing Requirements

### 1. CSV Import Tests
**File:** `tests/test_server.py` (create if missing)

```python
def test_csv_import_s01_parameters():
    """CSV import should handle S01 MA parameters via config lookup."""
    # Upload CSV with: maType,EMA / maLength,45
    # Verify: updates["maType"] == "EMA" (uppercased select type)

def test_csv_import_s04_parameters():
    """CSV import should handle S04 parameters via config lookup."""
    # Upload CSV with: rsiLen,16 / stochLen,20
    # Verify: updates["rsiLen"] == 16, updates["stochLen"] == 20

def test_csv_import_without_strategy_uses_first_available():
    """CSV import without strategy param should use first from list_strategies()."""
    # Send request without "strategy" field
    # Verify it uses list_strategies()[0]["id"]
```

### 2. Walk-Forward Tests
**File:** `tests/test_walkforward.py` (create if missing)

```python
def test_param_id_generation_s01():
    """Param ID should use first 2 optimizable params for S01."""
    # Strategy: s01_trailing_ma
    # Params: maType=EMA, maLength=45, closeCountLong=7
    # Expected: "EMA 45_{hash}"

def test_param_id_generation_s04():
    """Param ID should use first 2 optimizable params for S04."""
    # Strategy: s04_stochrsi
    # Params: rsiLen=16, stochLen=20, kLen=3
    # Expected: "16 20_{hash}"

def test_wf_csv_export_includes_all_s01_params():
    """WF CSV export should list all S01 parameters from config."""
    # Run WFA with S01, export CSV
    # Verify "Detailed Parameters" section includes all config.json params

def test_wf_csv_export_includes_all_s04_params():
    """WF CSV export should list all S04 parameters from config."""
    # Run WFA with S04, export CSV
    # Verify "Detailed Parameters" section includes rsiLen, stochLen, etc.
```

### 3. Naming Consistency Tests
**File:** `tests/test_naming_consistency.py` (already exists)

Run existing tests to ensure:
- No snake_case parameters introduced
- `config.json` and dataclass alignment maintained
- No hardcoded S01 fields in core modules

### 4. Regression Tests
**Files:** `tests/test_regression_s01.py`, `tests/test_s01_migration.py`

Run full regression suite to ensure:
- S01 backtest results unchanged
- S01 optimization results unchanged
- Walk-Forward results unchanged (format may change, but logic identical)

---

## 🏗️ Architecture Context

### Strategy Discovery System
Strategies are auto-loaded from `src/strategies/*/` if they contain:
1. **`config.json`** — Parameter schema, metadata
2. **`strategy.py`** — Strategy class with `STRATEGY_ID`, `STRATEGY_NAME`, `run()` method

**Available Strategies:**
- `s01_trailing_ma` — MA crossover with trailing stops (26 params)
- `s04_stochrsi` — StochRSI swing strategy (12 params)

### Parameter Naming Convention
✅ **camelCase** end-to-end (Pine → config → Python → CSV)
- `maType`, `closeCountLong`, `rsiLen`, `stochLen`

❌ **No snake_case**
- `ma_type`, `close_count_long`, `rsi_len`

### Config.json Structure
Each parameter has:
```json
{
  "paramName": {
    "type": "int" | "float" | "select" | "options" | "bool",
    "label": "Human-Readable Name",
    "default": 45,
    "min": 0,
    "max": 500,
    "options": ["EMA", "SMA", "HMA"],  // Required for select types
    "group": "Entry",
    "optimize": {
      "enabled": true,
      "min": 25,
      "max": 200,
      "step": 25
    }
  }
}
```

### Core Module Guarantees
**Core modules must remain strategy-agnostic:**
1. `backtest_engine.py` — Defines `TradeRecord`, `StrategyResult`, data loading
2. `optuna_engine.py` — `OptimizationResult.params: Dict[str, Any]` (generic dict)
3. `walkforward_engine.py` — Consumes strategy via `config.strategy_id`
4. `export.py` — Iterates `config.json` parameters for CSV headers
5. `server.py` — Resolves strategy from request, loads config dynamically

**Strategy modules own their logic:**
- `strategies/s01_trailing_ma/strategy.py` — S01Params dataclass, entry/exit logic
- `strategies/s04_stochrsi/strategy.py` — S04Params dataclass, StochRSI logic

---

## 📚 Key Files Reference

### 1. `src/server.py`
**Function:** `_parse_csv_parameter_block(file_storage) -> Tuple[Dict[str, Any], List[str]]`
- **Line 253-323:** CSV import with hardcoded MA handling
- **Fix:** Load `strategy_id` from request, use `get_strategy_config()` for type lookup

**Dependencies:**
- `strategies.get_strategy_config(strategy_id)` → Returns `config.json` dict
- `strategies.list_strategies()` → Returns list of available strategies

### 2. `src/core/walkforward_engine.py`
**Class:** `WalkForwardEngine`
- **Line 583-589:** `_create_param_id()` hardcodes `maType`, `maLength`
- **Fix:** Iterate `config["parameters"]` to find first 2 optimizable params

**Function:** `export_wf_results_csv(result, df)`
- **Lines 1045-1072:** Hardcoded S01 parameter rows
- **Fix:** Load `result.strategy_id` config, iterate all parameters

**Dependencies:**
- `strategies.get_strategy_config(strategy_id)` → Returns config dict
- `result.strategy_id` → Strategy identifier from `WFResult` dataclass

### 3. `src/core/backtest_engine.py`
**Imports Section:**
- **Lines 7-21:** Unused MA imports
- **Fix:** Remove unused imports, keep only `VALID_MA_TYPES`, `get_ma` (if needed)

**Dead Code:**
- **Lines 135-141:** `compute_max_drawdown()` function
- **Fix:** Delete function (not called anywhere)

### 4. Strategy Config Examples

**S01 Config (`src/strategies/s01_trailing_ma/config.json`):**
```json
{
  "id": "s01_trailing_ma",
  "name": "S01 Trailing MA",
  "parameters": {
    "maType": { "type": "select", "options": ["EMA", "SMA", "HMA", ...], "optimize": {"enabled": true} },
    "maLength": { "type": "int", "default": 45, "optimize": {"enabled": true, "min": 25, "max": 500} },
    "closeCountLong": { "type": "int", "default": 7, "optimize": {"enabled": true} },
    "trailLongType": { "type": "select", "options": [...], "optimize": {"enabled": true} },
    ...
  }
}
```

**S04 Config (`src/strategies/s04_stochrsi/config.json`):**
```json
{
  "id": "s04_stochrsi",
  "name": "S04 StochRSI",
  "parameters": {
    "rsiLen": { "type": "int", "default": 16, "optimize": {"enabled": true} },
    "stochLen": { "type": "int", "default": 16, "optimize": {"enabled": true} },
    "kLen": { "type": "int", "default": 3, "optimize": {"enabled": true} },
    "obLevel": { "type": "float", "default": 75.0, "optimize": {"enabled": true} },
    ...
  }
}
```

---

## 🚨 Critical Constraints

### ❌ What NOT to Change
1. **Do NOT modify parameter naming** (must stay camelCase)
2. **Do NOT add snake_case fallbacks or converters**
3. **Do NOT add `to_dict()` methods to dataclasses** (use `dataclasses.asdict`)
4. **Do NOT modify strategy modules** (`s01_trailing_ma/strategy.py`, `s04_stochrsi/strategy.py`)
5. **Do NOT change CSV export format** for existing fields (dates, metrics)
6. **Do NOT modify Optuna engine** (already generic via `OptimizationResult.params`)

### ✅ What TO Change
1. **Make CSV import generic** (load parameter types from config)
2. **Make WF param ID generic** (find first 2 optimizable params)
3. **Make WF CSV export generic** (iterate config parameters)
4. **Remove unused MA imports** from `backtest_engine.py`
5. **Remove dead `compute_max_drawdown` function**

### ⚠️ Preserve Existing Behavior
1. **CSV import date handling** (`start`/`end` splitting) must stay unchanged
2. **CSV import uppercase handling** for select types (now config-driven)
3. **WF CSV format** (sections, headers) must stay identical (content generic)
4. **Parameter ID hash format** must stay `{label}_{hash}` (label now dynamic)

---

## 🔍 Validation Steps

### Step 1: Code Review
- [ ] `server.py`: No hardcoded `maType`, `trailLongType`, `trailShortType`
- [ ] `walkforward_engine.py`: `_create_param_id()` loads config dynamically
- [ ] `walkforward_engine.py`: `export_wf_results_csv()` iterates config params
- [ ] `backtest_engine.py`: No unused MA imports
- [ ] `backtest_engine.py`: No `compute_max_drawdown` function

### Step 2: Run Tests
```bash
cd src
pytest tests/test_naming_consistency.py -v  # Must pass
pytest tests/test_regression_s01.py -v      # Baselines must match
pytest tests/test_server.py -v -k csv       # CSV import tests
pytest tests/test_walkforward.py -v          # WF tests (create file)
```

### Step 3: Manual Validation
1. **CSV Import Test:**
   - Upload S01 CSV with `maType,EMA` → Verify `maType = "EMA"` (uppercase)
   - Upload S04 CSV with `rsiLen,16` → Verify `rsiLen = 16` (int)

2. **Walk-Forward Test:**
   - Run WFA with S01 → Verify param IDs like `"EMA 45_abc123"`
   - Run WFA with S04 → Verify param IDs like `"16 16_xyz789"`
   - Export WF CSV → Verify parameter section lists all strategy params

3. **Unused Code Test:**
   - Search codebase for `compute_max_drawdown` → Should find 0 references
   - Search for `from indicators.ma import alma` → Should find 0 references

---

## 📝 Expected Deliverables

1. **Modified Files:**
   - `src/server.py` (CSV import made generic)
   - `src/core/walkforward_engine.py` (param ID + CSV export made generic)
   - `src/core/backtest_engine.py` (unused imports removed)

2. **New Test File (optional but recommended):**
   - `tests/test_walkforward.py` (param ID tests, CSV export tests)

3. **Passing Test Suite:**
   - All existing tests pass (naming, regression, migration)
   - New tests for CSV import strategy detection
   - New tests for WF param ID generation

4. **Documentation Update:**
   - Add comment in `server.py:_parse_csv_parameter_block` explaining config-driven approach
   - Add comment in `walkforward_engine.py:_create_param_id` explaining dynamic label logic

---

## 🎓 Success Criteria

✅ **Generic Core:**
- No S01-specific parameter names in `server.py`, `walkforward_engine.py`, `backtest_engine.py`
- CSV import works for S01, S04, and future strategies without code changes

✅ **Config-Driven Export:**
- WF CSV "Detailed Parameters" section lists all strategy params from `config.json`
- Param IDs use first 2 optimizable params (dynamic, not hardcoded)

✅ **Clean Codebase:**
- No unused imports in `backtest_engine.py`
- No dead code (`compute_max_drawdown` removed)

✅ **Test Coverage:**
- All existing tests pass (naming, regression, S01 migration)
- New tests validate CSV import strategy detection
- New tests validate WF param ID generation for S01/S04

✅ **Backward Compatibility:**
- S01 CSV imports produce identical results (values may differ due to uppercase handling)
- S01 WF results produce same metrics (param ID format may differ)
- No breaking changes to API or file formats

---

## 🛠️ Implementation Order

1. **Start with Issue 3** (easiest, no dependencies):
   - Remove unused MA imports from `backtest_engine.py:7-21`
   - Remove `compute_max_drawdown` from `backtest_engine.py:135-141`
   - Verify no references in codebase

2. **Fix Issue 1** (CSV import):
   - Modify `server.py:_parse_csv_parameter_block`
   - Add strategy resolution logic
   - Load config and apply type-based conversion
   - Test with S01 and S04 CSV uploads

3. **Fix Issue 2.1** (WF param ID):
   - Modify `walkforward_engine.py:_create_param_id`
   - Load config, find first 2 optimizable params
   - Build label dynamically
   - Test with S01 and S04 WF runs

4. **Fix Issue 2.2** (WF CSV export):
   - Modify `walkforward_engine.py:export_wf_results_csv` lines 1038-1095
   - Replace hardcoded parameter rows with config iteration
   - Test CSV output for S01 and S04

5. **Add Tests:**
   - Create `tests/test_walkforward.py`
   - Add CSV import tests to `tests/test_server.py`
   - Run full test suite

6. **Validate:**
   - Manual CSV upload (S01, S04)
   - Manual WF run (S01, S04)
   - Compare outputs to baseline

---

## 🔗 Related Documentation

- `CLAUDE.md` — Project overview, architecture, parameter naming rules
- `docs/ADDING_NEW_STRATEGY.md` — Strategy onboarding guide
- `tests/test_naming_consistency.py` — Naming convention tests
- `src/strategies/s01_trailing_ma/config.json` — S01 parameter schema
- `src/strategies/s04_stochrsi/config.json` — S04 parameter schema

---

## 💡 Key Insights

### Why This Matters
1. **Scalability:** Adding S05, S06, S07 should require ZERO core changes
2. **Maintainability:** Parameter changes happen in `config.json`, not scattered across 5 files
3. **Testability:** New strategies inherit full test coverage (CSV import, WF, export)
4. **Correctness:** No risk of typos in hardcoded parameter names

### Design Philosophy
- **Strategy modules own behavior** (entry/exit logic, parameter dataclasses)
- **Core modules own orchestration** (optimization loops, WF window splitting, CSV formatting)
- **Config files bridge the two** (parameter schemas, types, labels, optimize ranges)

### Future-Proofing
This refactor enables:
- **Strategy marketplace:** Users upload `config.json` + `strategy.py` → instant integration
- **Parameter evolution:** Change S01 params without touching core
- **Multi-strategy portfolios:** Run WFA across multiple strategies simultaneously

---

## ⚡ Quick Reference

### Get Strategy Config
```python
from strategies import get_strategy_config

config = get_strategy_config("s01_trailing_ma")
parameters = config["parameters"]  # Dict[str, Dict[str, Any]]
```

### Iterate Parameters in Order
```python
for param_name, param_spec in parameters.items():
    param_type = param_spec.get("type")  # "int", "float", "select", etc.
    label = param_spec.get("label", param_name)
    default = param_spec.get("default")
    optimize_cfg = param_spec.get("optimize", {})
    is_optimizable = optimize_cfg.get("enabled", False)
```

### Check If Parameter Is Select Type
```python
param_type = param_spec.get("type", "").lower()
if param_type in {"select", "options"}:
    # Uppercase the value
    value = str(raw_value).strip().upper()
```

### Find First N Optimizable Params
```python
optimizable = []
for param_name, param_spec in parameters.items():
    optimize_cfg = param_spec.get("optimize", {})
    if optimize_cfg.get("enabled", False):
        optimizable.append(param_name)
    if len(optimizable) == 2:
        break
```

---

**End of Prompt — Good luck! 🚀**
