# Phase 9-5-2: Application Layer Refactoring - Server, UI & Testing

**Target Agent**: GPT 5.1 Codex
**Project**: S_01 Trailing MA Backtesting Platform
**Task**: Phase 9-5-2 - Refactor Server/UI Layer & Complete Testing
**Complexity**: High (Multi-phase architectural refactoring)
**Priority**: Critical (Completion of Phase 9-5 refactoring)
**Prerequisite**: Phase 9-5-1 must be completed first

---

## Executive Summary

This is **Phase 9-5-2**, the second and final part of the comprehensive refactoring to eliminate S01/S04 architecture inconsistencies.

**Phase 9-5-1 (Completed)** standardized:
- Parameter naming to camelCase throughout
- OptimizationResult to generic dict-based structure
- CSV export system to be config-driven

**Phase 9-5-2 (This Phase)** will complete the refactoring by:
1. Cleaning up server defaults and removing dual naming support
2. Implementing generic parameter type system for UI rendering
3. Updating all tests and documentation

**Success Metric**: After Phase 9-5-2, adding a new strategy requires only `config.json` + `strategy.py` with no changes to core modules, server, or frontend.

---

## Table of Contents

1. [Project Context](#project-context)
2. [Phase 9-5-1 Recap](#phase-9-5-1-recap)
3. [Implementation Plan - 3 Phases](#implementation-plan)
   - [Phase 4: Clean Up Server Defaults](#phase-4-clean-up-server-defaults)
   - [Phase 5: Generic Parameter Type System](#phase-5-generic-parameter-type-system--ui-rendering)
   - [Phase 6: Tests & Documentation](#phase-6-update-tests-and-documentation)
4. [Testing Requirements](#testing-requirements)
5. [Code Quality Standards](#code-quality-standards)
6. [File Reference Guide](#file-reference-guide)

---

## Project Context

### What This Project Does

This is a **backtesting and optimization platform** for trading strategies:

- **Strategies**: S01 (Trailing MA), S04 (StochRSI), future strategies
- **Core Engines**:
  - `backtest_engine.py` - Single backtest execution
  - `optuna_engine.py` - Bayesian parameter optimization (Optuna-based)
  - `walkforward_engine.py` - Walk-forward analysis orchestrator
- **Interface**: Flask web server + HTML/JS frontend, optional CLI
- **Data Flow**: OHLCV CSV → Strategy simulation → Metrics → CSV export

### Key Architecture Principles (Must Preserve)

1. **Performance Critical**: Multiprocessing with pre-computed caches for indicators
2. **Data Structure Ownership**: "Structures live where they're populated"
3. **No separate `types.py`**: Import data structures from their home modules
4. **Hybrid approach**:
   - **Strategies**: Typed dataclasses for type safety (e.g., `S01Params`, `S04Params`)
   - **Core modules**: Generic dicts `Dict[str, Any]` for strategy-agnostic operation

---

## Phase 9-5-1 Recap

Phase 9-5-1 completed the following:

### ✓ Phase 1: Standardized to camelCase
- Converted S01Params dataclass to camelCase
- Simplified S01Params.from_dict() (direct mapping, no conversion)
- Deleted S01Params.to_dict() method
- Updated all S01 strategy logic to use camelCase
- Verified S04Params consistency

### ✓ Phase 2: Made OptimizationResult Generic
- Replaced 21 S01-specific fields with `params: Dict[str, Any]`
- Deleted hardcoded PARAMETER_MAP and INTERNAL_TO_FRONTEND_MAP
- Updated _objective function to store params as dict
- Removed dynamic setattr() workaround
- Built search space dynamically from config.json

### ✓ Phase 3: Created Generic CSV Export System
- Deleted hardcoded CSV_COLUMN_SPECS
- Added _get_formatter() helper
- Enhanced _build_column_specs_for_strategy() to build from config.json
- Updated export_optuna_results() to read from result.params dict
- Removed S01-specific error handling

**Result**: Parameters now flow unchanged through the system (camelCase throughout), core data structures are generic, and CSV export is config-driven.

---

## Implementation Plan

You will complete 3 phases sequentially. Each phase must be fully tested before proceeding to the next.

---

## Phase 4: Clean Up Server Defaults

**Goal**: Remove S01-specific defaults and dual naming support.

### 4.1 Simplify DEFAULT_PRESET

**File**: `src/server.py` (lines 156-211, approximate)

**Current**:
```python
DEFAULT_PRESET = {
    "name": "Default",
    "maType": "EMA",
    "maLength": 45,
    "closeCountLong": 7,
    "closeCountShort": 5,
    # ... 20+ more S01-specific parameters
    "filterByProfit": False,
    "minProfitThreshold": 0.0,
    # ... optimization settings
}
```

**Target**:
```python
DEFAULT_PRESET = {
    "name": "Default",

    # Universal settings (not strategy-specific)
    "dateFilter": True,
    "start": None,
    "end": None,

    # Optimization settings
    "optimizationMode": "optuna",
    "nTrials": 100,
    "timeout": None,
    "patience": None,
    "workerProcesses": 6,

    # Scoring configuration
    "scoreConfig": {
        "weights": {
            "romad": 0.25,
            "sharpe": 0.20,
            "pf": 0.20,
            "ulcer": 0.15,
            "recovery": 0.10,
            "consistency": 0.10,
        },
        "normalization_method": "percentile",
    },

    # Filtering
    "filterByProfit": False,
    "minProfitThreshold": 0.0,
}
```

**Rationale**: Strategy-specific defaults come from config.json, not server defaults.

**Action Items**:
1. Remove all S01-specific parameter defaults
2. Keep only universal settings (dates, optimization, scoring, filtering)
3. Document that strategy defaults loaded from config.json

### 4.2 Remove Dual Naming Fallbacks

**File**: `src/server.py` (lines 1182-1514, approximate)

**Current**:
```python
# Dual naming support
ma_type = params.get("maType") or params.get("ma_type", "EMA")
ma_length = params.get("maLength") or params.get("ma_length", 45)
close_count_long = params.get("closeCountLong") or params.get("close_count_long", 7)
# ... many more dual fallbacks
```

**Target**:
```python
# camelCase only (no fallbacks)
ma_type = params.get("maType", "EMA")
ma_length = params.get("maLength", 45)
close_count_long = params.get("closeCountLong", 7)
# ... clean camelCase access
```

**Action Items**:
1. Find all `params.get("camelCase") or params.get("snake_case")` patterns
2. Remove snake_case fallback
3. Keep only camelCase access

### 4.3 Remove S01-Specific Parameter Handling

**File**: `src/server.py` (lines 1340-1350, approximate)

**Current**:
```python
# Special handling for MA types
if "maType" in params:
    params["maType"] = MA_TYPE_MAPPINGS.get(params["maType"], params["maType"])
if "trailLongType" in params:
    params["trailLongType"] = MA_TYPE_MAPPINGS.get(params["trailLongType"], params["trailLongType"])
# ... more S01-specific logic
```

**Target**: **DELETE** - All parameters handled generically.

### 4.4 Simplify _sanitize_score_config()

**File**: `src/server.py` (lines 1207-1273, approximate)

**Current**:
```python
def _sanitize_score_config(score_config: Dict[str, Any]) -> Dict[str, Any]:
    # ... dual naming fallbacks
    weights = score_config.get("weights") or score_config.get("score_weights", {})
    # ... more snake_case fallbacks
```

**Target**:
```python
def _sanitize_score_config(score_config: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize score configuration - camelCase only."""
    weights = score_config.get("weights", {})
    enabled_metrics = score_config.get("enabledMetrics", {})
    invert_metrics = score_config.get("invertMetrics", {})
    normalization_method = score_config.get("normalizationMethod", "percentile")
    filter_enabled = score_config.get("filterEnabled", False)
    min_score_threshold = score_config.get("minScoreThreshold", 0.0)

    return {
        "weights": weights,
        "enabled_metrics": enabled_metrics,
        "invert_metrics": invert_metrics,
        "normalization_method": normalization_method,
        "filter_enabled": filter_enabled,
        "min_score_threshold": min_score_threshold,
    }
```

**Action Items**:
1. Remove all snake_case fallbacks
2. Use camelCase parameter names only
3. Provide sensible defaults

### 4.5 Remove strategy_param_types Extraction

**File**: `src/server.py` (lines 1318-1333, approximate)

**Current**:
```python
# Extract parameter types (S01-specific hardcoded)
strategy_param_types = {
    "maLength": "int",
    "closeCountLong": "int",
    # ... hardcoded types
}
```

**Target**: Load from strategy's config.json:

```python
def _get_parameter_types(strategy_id: str) -> Dict[str, str]:
    """Load parameter types from strategy config."""
    from strategies import get_strategy_config

    config = get_strategy_config(strategy_id)
    parameters = config.get("parameters", {})

    param_types = {}
    for param_name, param_spec in parameters.items():
        param_types[param_name] = param_spec.get("type", "float")

    return param_types
```

**Action Items**:
1. Delete hardcoded strategy_param_types
2. Load parameter types from config.json
3. Use in validation and type conversions

### 4.6 Update _build_optimization_config()

**File**: `src/server.py` (function that builds OptimizationConfig)

**Action Items**:
1. Load parameter metadata from strategy's config.json
2. No hardcoded parameter knowledge
3. Build config generically based on strategy ID

### Phase 4 Verification

**Test Checklist**:
- [ ] DEFAULT_PRESET contains only universal settings
- [ ] No S01-specific parameters in DEFAULT_PRESET
- [ ] All dual naming fallbacks removed
- [ ] S01-specific parameter handling deleted
- [ ] _sanitize_score_config() uses camelCase only
- [ ] Parameter types loaded from config.json
- [ ] Start server - verify default preset loads correctly
- [ ] Test backtest endpoint with S01
- [ ] Test backtest endpoint with S04
- [ ] Test optimize endpoint with S01
- [ ] Test optimize endpoint with S04

**Test Command**:
```bash
cd src
python server.py

# In another terminal
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{"strategy": "s01_trailing_ma", "params": {...}}'
```

---

## Phase 5: Generic Parameter Type System & UI Rendering

**Goal**: Make frontend render parameters based on type from config.json, remove hardcoded MA selection.

### 5.1 Remove requires_ma_selection Feature Flag

**File**: `src/strategies/s01_trailing_ma/config.json` (lines 7-10)

**Current**:
```json
{
  "features": {
    "requires_ma_selection": true,
    "ma_groups": ["trend", "trail_long", "trail_short"]
  }
}
```

**Target**: **DELETE** features section entirely.

**Rationale**: Generic parameter type system renders dropdowns automatically for any `type: "select"` parameter.

### 5.2 Verify Parameter Types in S01 Config

**File**: `src/strategies/s01_trailing_ma/config.json`

**Verify**:
- All MA type parameters use `"type": "select"`
- All length parameters use `"type": "int"`
- All float parameters use `"type": "float"`

**Example**:
```json
{
  "parameters": {
    "maType": {
      "type": "select",
      "label": "Trend MA Type",
      "default": "EMA",
      "options": ["EMA", "SMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"]
    },
    "maLength": {
      "type": "int",
      "label": "MA Length",
      "default": 45,
      "min": 0,
      "max": 500
    },
    "trailLongType": {
      "type": "select",
      "label": "Trail MA Long Type",
      "default": "SMA",
      "options": ["EMA", "SMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"]
    }
  }
}
```

### 5.3 Update Frontend Parameter Rendering

**File**: `index.html` (or `src/ui/static/js/main.js` if separated)

**Current** (hardcoded):
```javascript
if (config.features && config.features.requires_ma_selection) {
    // Hardcoded parameter names
    renderMATypeDropdown("maType", config.parameters.maType);
    renderMATypeDropdown("trailLongType", config.parameters.trailLongType);
    renderMATypeDropdown("trailShortType", config.parameters.trailShortType);
}
```

**Target** (generic):
```javascript
function renderParameters(config) {
    const parametersContainer = document.getElementById("parameters");
    parametersContainer.innerHTML = "";  // Clear

    const parameters = config.parameters || {};

    // Generic rendering based on parameter type
    for (const [paramName, paramConfig] of Object.entries(parameters)) {
        const paramElement = renderParameter(paramName, paramConfig);
        parametersContainer.appendChild(paramElement);
    }
}

function renderParameter(paramName, paramConfig) {
    const container = document.createElement("div");
    container.className = "parameter-row";

    const label = document.createElement("label");
    label.textContent = paramConfig.label || paramName;
    label.htmlFor = `param-${paramName}`;
    container.appendChild(label);

    let input;

    switch (paramConfig.type) {
        case "int":
        case "float":
            input = renderNumberInput(paramName, paramConfig);
            break;
        case "select":
        case "options":  // Support both names
            input = renderDropdown(paramName, paramConfig);
            break;
        case "bool":
            input = renderCheckbox(paramName, paramConfig);
            break;
        default:
            console.warn(`Unknown parameter type: ${paramConfig.type}`);
            input = renderNumberInput(paramName, paramConfig);  // Fallback
    }

    container.appendChild(input);
    return container;
}

function renderNumberInput(paramName, paramConfig) {
    const input = document.createElement("input");
    input.type = "number";
    input.id = `param-${paramName}`;
    input.name = paramName;
    input.value = paramConfig.default || 0;
    input.min = paramConfig.min || 0;
    input.max = paramConfig.max || 1000;
    input.step = paramConfig.step || (paramConfig.type === "int" ? 1 : 0.1);
    return input;
}

function renderDropdown(paramName, paramConfig) {
    const select = document.createElement("select");
    select.id = `param-${paramName}`;
    select.name = paramName;

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

function renderCheckbox(paramName, paramConfig) {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = `param-${paramName}`;
    input.name = paramName;
    input.checked = paramConfig.default || false;
    return input;
}
```

**Action Items**:
1. Remove hardcoded parameter names (`maType`, `trailLongType`, `trailShortType`)
2. Remove `requires_ma_selection` feature flag check
3. Loop through config.parameters and render generically
4. Render dropdowns for **any** `type: "select"` parameter
5. Support `type: "int"`, `"float"`, `"select"`, `"bool"`

### 5.4 Update Server Validation

**File**: `src/server.py` (validation logic)

**Add Generic Validation**:
```python
def _validate_strategy_params(strategy_id: str, params: Dict[str, Any]) -> None:
    """Generic parameter validation based on config.json."""
    from strategies import get_strategy_config

    config = get_strategy_config(strategy_id)
    parameters = config.get("parameters", {})

    for param_name, param_config in parameters.items():
        value = params.get(param_name)
        if value is None:
            continue  # Use default

        param_type = param_config.get("type", "float")

        # Type validation
        if param_type == "int":
            if not isinstance(value, int):
                try:
                    params[param_name] = int(value)
                except (ValueError, TypeError):
                    raise ValueError(f"{param_name} must be an integer")

        elif param_type == "float":
            if not isinstance(value, (int, float)):
                try:
                    params[param_name] = float(value)
                except (ValueError, TypeError):
                    raise ValueError(f"{param_name} must be a number")

        elif param_type in ["select", "options"]:
            options = param_config.get("options", [])
            if value not in options:
                raise ValueError(f"{param_name} must be one of {options}, got {value}")

        elif param_type == "bool":
            if not isinstance(value, bool):
                params[param_name] = bool(value)

        # Range validation
        if param_type in ["int", "float"]:
            min_val = param_config.get("min")
            max_val = param_config.get("max")
            if min_val is not None and value < min_val:
                raise ValueError(f"{param_name} must be >= {min_val}")
            if max_val is not None and value > max_val:
                raise ValueError(f"{param_name} must be <= {max_val}")
```

**Action Items**:
1. Remove hardcoded MA type validation
2. Add generic type validation for int/float/select/bool
3. Add generic range validation
4. Load validation rules from config.json

### 5.5 Verify S04 Config Types

**File**: `src/strategies/s04_stochrsi/config.json`

**Verify**:
```json
{
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
  }
}
```

**Action Items**:
1. Verify all parameter types are correct
2. Ensure consistency with S01 pattern
3. No feature flags needed

### Phase 5 Verification

**Test Checklist**:
- [ ] `requires_ma_selection` feature flag removed from S01 config.json
- [ ] S01 config.json uses `type: "select"` for MA type parameters
- [ ] Frontend renders parameters generically based on type
- [ ] MA type dropdowns render correctly for S01
- [ ] Number inputs render correctly for S04
- [ ] Server validation works generically for both strategies
- [ ] Load S01 in frontend - verify all parameters render correctly
- [ ] Load S04 in frontend - verify all parameters render correctly
- [ ] Submit backtest request - verify parameters validated correctly

**Test Command**:
```bash
# Start server
cd src
python server.py

# Open browser: http://localhost:8000
# Select S01 strategy - verify maType, trailLongType, trailShortType show as dropdowns
# Select S04 strategy - verify rsiLen, stochLen show as number inputs
```

---

## Phase 6: Update Tests and Documentation

**Goal**: Ensure all tests pass and documentation reflects new architecture.

### 6.1 Update Test Fixtures

**Files**: All test files in `tests/`

**Action Items**:
1. Find all test data with parameters
2. Convert snake_case parameter names to camelCase
3. Update expected outputs

**Example**:
```python
# OLD
test_params = {
    "ma_type": "EMA",
    "ma_length": 45,
    "close_count_long": 7,
}

# NEW
test_params = {
    "maType": "EMA",
    "maLength": 45,
    "closeCountLong": 7,
}
```

### 6.2 Update Regression Tests

**File**: `tests/test_regression_s01.py`

**Action Items**:
1. Update parameter dictionaries to use camelCase
2. Verify baseline comparisons still pass
3. Update any hardcoded parameter references

### 6.3 Update Unit Tests

**Files**:
- `tests/test_optuna_engine.py`
- `tests/test_export.py`

**Action Items**:
1. Update tests for generic OptimizationResult (params as dict)
2. Update tests for dynamic CSV column building
3. Add tests for parameter type system

### 6.4 Add Naming Consistency Tests

**File**: `tests/test_naming_consistency.py` (NEW)

**Create**:
```python
"""Test naming consistency across the codebase."""
import pytest
from dataclasses import fields
from strategies.s01_trailing_ma.strategy import S01Params, S01Strategy
from strategies.s04_stochrsi.strategy import S04Params, S04Strategy
from strategies import get_strategy_config


def test_s01_params_use_camelCase():
    """Verify all S01Params fields use camelCase."""
    for field in fields(S01Params):
        # Skip internal control parameters
        if field.name in ["use_backtester", "use_date_filter", "start", "end"]:
            continue

        # Check no underscores (camelCase has no underscores)
        assert "_" not in field.name, f"S01Params field {field.name} uses snake_case"


def test_s04_params_use_camelCase():
    """Verify all S04Params fields use camelCase."""
    for field in fields(S04Params):
        # Skip internal control parameters
        if field.name in ["use_backtester", "use_date_filter", "start", "end"]:
            continue

        assert "_" not in field.name, f"S04Params field {field.name} uses snake_case"


def test_config_matches_params_s01():
    """Verify S01 config.json parameter names match Params dataclass."""
    config = get_strategy_config("s01_trailing_ma")
    config_params = set(config["parameters"].keys())

    dataclass_params = {
        f.name for f in fields(S01Params)
        if f.name not in ["use_backtester", "use_date_filter", "start", "end"]
    }

    # All config params should exist in dataclass
    for param_name in config_params:
        assert param_name in dataclass_params, \
            f"Config param {param_name} not in S01Params dataclass"


def test_config_matches_params_s04():
    """Verify S04 config.json parameter names match Params dataclass."""
    config = get_strategy_config("s04_stochrsi")
    config_params = set(config["parameters"].keys())

    dataclass_params = {
        f.name for f in fields(S04Params)
        if f.name not in ["use_backtester", "use_date_filter", "start", "end"]
    }

    for param_name in config_params:
        assert param_name in dataclass_params, \
            f"Config param {param_name} not in S04Params dataclass"


def test_no_conversion_code():
    """Verify no snake_case ↔ camelCase conversion exists."""
    import inspect

    # Check S01Params.from_dict has no conversion
    source = inspect.getsource(S01Params.from_dict)
    assert "ma_type" not in source, "S01Params.from_dict still has snake_case conversion"
    assert "ma_length" not in source, "S01Params.from_dict still has snake_case conversion"

    # Check S01Params has no to_dict method
    assert not hasattr(S01Params, "to_dict"), "S01Params.to_dict should be deleted"


def test_parameter_types_valid():
    """Verify all strategies use valid parameter types."""
    valid_types = {"int", "float", "select", "options", "bool"}

    for strategy_id in ["s01_trailing_ma", "s04_stochrsi"]:
        config = get_strategy_config(strategy_id)
        parameters = config.get("parameters", {})

        for param_name, param_spec in parameters.items():
            param_type = param_spec.get("type")
            assert param_type in valid_types, \
                f"{strategy_id} param {param_name} has invalid type {param_type}"
```

### 6.5 Update CLAUDE.md

**File**: `CLAUDE.md`

**Add Section**:
```markdown
## Naming Convention: camelCase Throughout

**Critical Rule**: All parameters MUST use camelCase matching Pine Script conventions.

### Parameter Flow (No Conversions)

Pine Script (camelCase) → config.json (camelCase) → Python (camelCase) → CSV (camelCase)

Example:
- Pine Script: `input.int(16, "RSI Length")` → variable `rsiLen`
- config.json: `"rsiLen": {"type": "int", "default": 16}`
- Python Params: `rsiLen: int = 16`
- CSV export: column `rsiLen`

### Parameter Type System

Match Pine Script input types:

| Pine Script | config.json | Frontend | Python |
|-------------|-------------|----------|--------|
| `input.int()` | `"type": "int"` | Number input | `int` |
| `input.float()` | `"type": "float"` | Number input | `float` |
| `input.string(options=[...])` | `"type": "select"` | Dropdown | `str` |
| `input.bool()` | `"type": "bool"` | Checkbox | `bool` |

### Adding New Strategies

1. **Parameter names**: Use camelCase (e.g., `rsiLen`, not `rsi_len`)
2. **Params dataclass**: Typed fields with camelCase names
3. **from_dict()**: Direct mapping, no conversion
4. **No to_dict()**: Use `asdict(params)` from dataclasses module
5. **config.json**: Use correct parameter types (int/float/select/bool)

### Hybrid Architecture Pattern

**Strategy Level** (Type Safety):
```python
@dataclass
class S05Params:
    rsiLen: int = 16  # ← camelCase, typed
```

**Core Modules** (Generic):
```python
def optimize(params: Dict[str, Any]):  # ← Generic dict
    result.params = params  # ← Store as-is
```

### Performance Note

The multiprocessing cache architecture MUST be preserved. When modifying optimization logic, respect the caching pattern in `_init_worker()`.
```

### 6.6 Update PROJECT_TARGET_ARCHITECTURE.md

**File**: `docs/PROJECT_TARGET_ARCHITECTURE.md`

**Add Section**:
```markdown
## Naming Convention and Parameter Flow

### camelCase Throughout

All parameters use camelCase matching Pine Script conventions. No conversion layers exist.

**Parameter Flow**:
```
Pine Script (rsiLen) → config.json (rsiLen) → Python (rsiLen) → CSV (rsiLen)
```

**Benefits**:
- No conversion code needed
- Parameter names identical across entire pipeline
- Easier debugging (same name everywhere)
- Matches Pine Script source

### Hybrid Architecture: Typed Strategies + Generic Core

**Strategy Level** (Type Safety):
- Strategies define typed Params dataclasses
- Fields use camelCase matching config.json
- IDE autocomplete and type hints work
- Example: `S04Params.rsiLen: int = 16`

**Core Level** (Generic):
- Core modules work with `Dict[str, Any]`
- No hardcoded parameter knowledge
- Strategy-agnostic operation
- Example: `OptimizationResult.params: Dict[str, Any]`

**Conversion**:
- Happens once inside strategy: `self.params = S04Params.from_dict(params_dict)`
- Core modules pass dicts, strategies convert to typed dataclasses
```

### 6.7 Create Strategy Development Guide

**File**: `docs/ADDING_NEW_STRATEGY.md` (NEW)

**Create**:
```markdown
# Adding a New Strategy

## Step 1: Create Strategy Directory

```bash
mkdir -p src/strategies/s05_mystrategy
touch src/strategies/s05_mystrategy/__init__.py
touch src/strategies/s05_mystrategy/strategy.py
touch src/strategies/s05_mystrategy/config.json
```

## Step 2: Define config.json

Use camelCase parameter names matching your Pine Script source.

```json
{
  "id": "s05_mystrategy",
  "name": "S05 My Strategy",
  "version": "v01",
  "description": "Brief description",
  "parameters": {
    "rsiLen": {
      "type": "int",
      "label": "RSI Length",
      "default": 14,
      "min": 2,
      "max": 100,
      "step": 1,
      "group": "Indicators",
      "optimize": {
        "enabled": true,
        "min": 5,
        "max": 50,
        "step": 1
      }
    },
    "maType": {
      "type": "select",
      "label": "MA Type",
      "default": "EMA",
      "options": ["SMA", "EMA", "HMA"],
      "group": "Indicators",
      "optimize": {
        "enabled": false
      }
    },
    "threshold": {
      "type": "float",
      "label": "Entry Threshold",
      "default": 0.5,
      "min": 0.0,
      "max": 1.0,
      "step": 0.1,
      "group": "Entry",
      "optimize": {
        "enabled": true,
        "min": 0.1,
        "max": 0.9,
        "step": 0.1
      }
    }
  }
}
```

**Parameter Type Reference**:
- `"int"` - Integer values (Pine: `input.int()`)
- `"float"` - Decimal values (Pine: `input.float()`)
- `"select"` - Dropdown options (Pine: `input.string(options=[...])`)
- `"bool"` - True/False (Pine: `input.bool()`)

## Step 3: Define Params Dataclass

Use camelCase field names matching config.json.

```python
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class S05Params:
    """S05 strategy parameters - camelCase matching Pine Script."""
    rsiLen: int = 14
    maType: str = "EMA"
    threshold: float = 0.5

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "S05Params":
        """Direct mapping - no conversion."""
        return cls(
            rsiLen=int(d.get("rsiLen", 14)),
            maType=str(d.get("maType", "EMA")),
            threshold=float(d.get("threshold", 0.5)),
        )
```

**Rules**:
- ✅ Use camelCase (e.g., `rsiLen`, `maType`)
- ❌ Do NOT use snake_case (e.g., `rsi_len`, `ma_type`)
- ✅ Direct mapping in from_dict() (no conversion)
- ❌ Do NOT create to_dict() method (use `asdict()` instead)

## Step 4: Implement Strategy

```python
from core.backtest_engine import StrategyResult, TradeRecord
from strategies.base import BaseStrategy

class S05Strategy(BaseStrategy):
    def __init__(self, params_dict: Dict[str, Any]):
        # Hybrid: convert dict to typed dataclass
        self.params = S05Params.from_dict(params_dict)

    def run(self, df: pd.DataFrame, warmup_bars: int = 0) -> StrategyResult:
        """Execute strategy and return results."""
        p = self.params

        # Calculate indicators (use camelCase params)
        rsi = calculate_rsi(df["close"], p.rsiLen)
        ma = get_ma(df["close"], p.maType, p.rsiLen)

        # Trading logic
        trades = []
        position = None

        for i in range(warmup_bars, len(df)):
            # Entry logic
            if position is None and rsi[i] < 30:
                position = {
                    "entry_idx": i,
                    "entry_price": df["close"].iloc[i],
                    "direction": "long",
                }

            # Exit logic
            elif position is not None and rsi[i] > 70:
                trade = TradeRecord(
                    entry_time=df.index[position["entry_idx"]],
                    exit_time=df.index[i],
                    entry_price=position["entry_price"],
                    exit_price=df["close"].iloc[i],
                    size=1.0,
                    direction=position["direction"],
                    pnl=(df["close"].iloc[i] - position["entry_price"]) * 1.0,
                    commission=0.0,
                )
                trades.append(trade)
                position = None

        return StrategyResult(trades=trades)
```

## Step 5: Register Strategy

Add to `src/strategies/__init__.py`:

```python
from .s05_mystrategy.strategy import S05Strategy

STRATEGY_REGISTRY = {
    "s01_trailing_ma": S01Strategy,
    "s04_stochrsi": S04Strategy,
    "s05_mystrategy": S05Strategy,  # ← Add here
}
```

## Step 6: Test

```bash
cd src
python run_backtest.py --strategy s05_mystrategy --csv ../data/sample.csv
```

## Common Mistakes to Avoid

1. ❌ Using snake_case parameter names
2. ❌ Creating conversion code in from_dict()
3. ❌ Hardcoding strategy logic in core modules
4. ❌ Using invalid parameter types in config.json
5. ❌ Forgetting to add strategy to STRATEGY_REGISTRY

## Architecture Guarantees

After following this guide:
- ✅ Frontend renders your parameters automatically based on type
- ✅ Optimization works without core module changes
- ✅ CSV export includes your parameters automatically
- ✅ Parameter validation works generically
- ✅ Your strategy is treated identically to S01 and S04
```

### Phase 6 Verification

**Test Checklist**:
- [ ] All test fixtures use camelCase parameters
- [ ] Regression tests pass with camelCase
- [ ] Unit tests updated for generic OptimizationResult
- [ ] Naming consistency tests added and passing
- [ ] CLAUDE.md documents camelCase convention
- [ ] PROJECT_TARGET_ARCHITECTURE.md documents Hybrid approach
- [ ] ADDING_NEW_STRATEGY.md created with clear guide
- [ ] All existing tests pass
- [ ] New tests pass

**Test Command**:
```bash
cd tests
pytest -v
pytest test_naming_consistency.py -v
```

---

## Testing Requirements

### Integration Testing

After ALL phases complete:

1. **End-to-End S01 Test**:
   - Load S01 in frontend
   - Verify all parameters render correctly
   - Submit backtest request
   - Verify results displayed
   - Submit optimization request
   - Verify CSV export correct

2. **End-to-End S04 Test**:
   - Repeat above for S04 strategy

3. **Cross-Strategy Test**:
   - Switch between S01 and S04 in frontend
   - Verify parameter forms update correctly
   - Verify no parameter name conflicts

### Performance Testing

Verify no performance regression:

1. **Benchmark Optimization Speed**:
   - Run 100-trial optimization before refactoring
   - Run 100-trial optimization after refactoring
   - Verify throughput within 5% (caching architecture preserved)

2. **Memory Usage**:
   - Monitor memory during optimization
   - Verify no memory leaks or excessive growth

---

## Code Quality Standards

### Style Guidelines

1. **Type Hints**: Use type hints for all function signatures
2. **Docstrings**: Document all public functions with Google-style docstrings
3. **Naming**: Follow PEP 8 for function/variable names (snake_case), camelCase for parameters matching Pine Script
4. **Line Length**: Max 100 characters (relaxed from PEP 8's 79 for readability)

### Error Handling

1. **Validation**: Validate all inputs at API boundaries
2. **Logging**: Use logging module, not print statements
3. **Exceptions**: Raise specific exceptions with clear messages
4. **Graceful Degradation**: Fallback to sensible defaults when possible

### Comments

1. **WHY not WHAT**: Explain rationale, not obvious operations
2. **TODOs**: Include author and date for any TODO comments
3. **Complex Logic**: Document non-obvious algorithms or edge cases

### Git Commits

1. **Atomic Commits**: One logical change per commit
2. **Commit Messages**:
   - Format: `[Phase 9-5-2.X] Brief description`
   - Example: `[Phase 9-5-2.1] Remove S01-specific server defaults`
3. **Testing**: Ensure tests pass before committing

---

## File Reference Guide

### Server

**Server**:
- `src/server.py` - Flask API server (~1600 lines)
  - Lines 156-211: DEFAULT_PRESET (REFACTOR)
  - Lines 1182-1514: Dual naming fallbacks (REFACTOR)
  - Lines 1207-1273: _sanitize_score_config (REFACTOR)
  - Lines 1318-1333: strategy_param_types extraction (DELETE)
  - Lines 1340-1350: S01-specific parameter handling (DELETE)

### Frontend

**UI**:
- `index.html` - Main HTML page (~1200 lines)
  - Hardcoded MA type selection (REFACTOR to generic)
  - Parameter rendering (REFACTOR)

### Tests

**Test Files**:
- `tests/test_regression_s01.py` - S01 regression tests (UPDATE)
- `tests/test_optuna_engine.py` - Optuna engine unit tests (UPDATE)
- `tests/test_export.py` - Export utilities unit tests (UPDATE)
- `tests/test_naming_consistency.py` - Naming consistency tests (NEW)

### Documentation

- `CLAUDE.md` - Project guidelines for Claude Code (UPDATE)
- `docs/PROJECT_TARGET_ARCHITECTURE.md` - Target architecture (UPDATE)
- `docs/PROJECT_STRUCTURE.md` - Directory structure
- `docs/ADDING_NEW_STRATEGY.md` - Strategy development guide (NEW)

---

## Success Criteria (Phase 9-5-2 & Overall Checklist)

After completing all 3 phases of 9-5-2, verify:

- [ ] **No hardcoded parameter names** in server.py
- [ ] **DEFAULT_PRESET contains only universal settings**
- [ ] **All dual naming fallbacks removed**
- [ ] **S01-specific parameter handling deleted**
- [ ] **Parameter types loaded from config.json**
- [ ] **Frontend renders parameters generically** based on type
- [ ] **requires_ma_selection feature flag removed**
- [ ] **MA type dropdowns work** for S01 (via generic "select" type rendering)
- [ ] **Generic parameter validation** in server
- [ ] **All tests updated** to use camelCase
- [ ] **Naming consistency tests pass**
- [ ] **Documentation updated** (CLAUDE.md, architecture docs, new guide)

### Overall Phase 9-5 Success (Both 9-5-1 and 9-5-2)

- [ ] **No hardcoded parameter names** in core modules (optuna_engine, export, server)
- [ ] **Single naming convention** (camelCase) throughout entire system
- [ ] **No strategy-specific conditionals** (`if strategy_id == "s01"`) in core modules
- [ ] **No conversion code** between naming conventions (snake_case ↔ camelCase)
- [ ] **S01 and S04 treated identically** by core system
- [ ] **Adding new strategy requires only** config.json + strategy.py (no core changes)
- [ ] **All existing tests pass** (regression, unit, integration)
- [ ] **CSV export works correctly** for both S01 and S04
- [ ] **Optimization completes** without errors for both strategies
- [ ] **Performance preserved** (no regression in optimization speed)
- [ ] **Parameter flow verified**: Pine → JSON → Python → CSV (same names throughout)

---

## Critical Preservation

**DO NOT MODIFY**:
1. Multiprocessing cache architecture (`_init_worker()` in optuna_engine.py)
2. Performance-critical indicator calculations
3. Metrics calculation logic (unless fixing bugs)
4. Trade simulation core logic in backtest_engine.py

---

## Breaking Changes

This refactoring includes **breaking changes**:
- Existing CSV exports with snake_case headers become invalid
- Saved presets with snake_case parameters won't load
- API clients must update to camelCase parameters

**Mitigation**: Provide migration script or one-time conversion logic if needed.

---

## Future-Proofing

After this refactoring:
- Adding S05, S06, ... strategies is trivial (config.json + strategy.py)
- Parameter types can be extended (e.g., add "string" type)
- Frontend automatically adapts to new strategies
- No core module maintenance needed for new strategies

---

## Questions or Issues

If you encounter ambiguity or issues:
1. **Preserve existing behavior** - Refactoring should not change functionality
2. **Ask for clarification** - Don't guess on critical decisions
3. **Document assumptions** - Add comments explaining non-obvious choices
4. **Test incrementally** - Verify each change before moving to next

---

**END OF PHASE 9-5-2 PROMPT**

This completes the Phase 9-5 refactoring. After successful completion of both Phase 9-5-1 and Phase 9-5-2, the codebase will have a clean, generic architecture where S01 and S04 (and future strategies) are treated identically by the core system.
