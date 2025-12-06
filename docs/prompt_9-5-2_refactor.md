# Phase 9-5-2: Server Layer Cleanup - Remove S01-Specific Defaults & Dual Naming

**Target Agent**: GPT 5.1 Codex
**Project**: S_01 Trailing MA Backtesting Platform
**Task**: Phase 9-5-2 - Server Layer Refactoring
**Complexity**: High (Backend architectural refactoring)
**Priority**: Critical (Continuation of Phase 9-5 refactoring)
**Prerequisite**: Phase 9-5-1 must be completed first

---

## Executive Summary

This is **Phase 9-5-2**, the second phase in the comprehensive refactoring series to eliminate S01/S04 architecture inconsistencies.

**Phase 9-5-1 (Completed)** standardized:
- Parameter naming to camelCase throughout
- OptimizationResult to generic dict-based structure
- CSV export system to be config-driven

**Phase 9-5-2 (This Phase)** focuses on **server layer cleanup**:
- Remove S01-specific defaults from DEFAULT_PRESET
- Eliminate dual naming fallbacks (camelCase vs snake_case)
- Implement generic parameter type loading from config.json
- Remove all hardcoded S01 parameter handling

**Success Metric**: After Phase 9-5-2, server.py contains zero hardcoded S01 parameter names and loads all parameter metadata from strategy config.json files.

**Next Phases**:
- Phase 9-5-3 will handle frontend UI refactoring
- Phase 9-5-4 will update tests and documentation

---

## Table of Contents

1. [Project Context](#project-context)
2. [Phase 9-5-1 Recap](#phase-9-5-1-recap)
3. [Current Problems in Server Layer](#current-problems-in-server-layer)
4. [Implementation Plan](#implementation-plan)
5. [Testing Requirements](#testing-requirements)
6. [Code Quality Standards](#code-quality-standards)
7. [File Reference Guide](#file-reference-guide)

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

### Pine Script Connection

Strategies are originally written in **Pine Script** (TradingView's scripting language) and ported to Python. Parameter names in Pine Script use **camelCase** (e.g., `rsiLen`, `stochLen`, `maType`). The target architecture matches this convention throughout the entire pipeline.

---

## Phase 9-5-1 Recap

Phase 9-5-1 completed three major refactorings:

### ✓ Phase 1: Standardized to camelCase
- Converted S01Params dataclass to camelCase (24 parameters)
- Simplified S01Params.from_dict() (direct mapping, no conversion)
- Deleted S01Params.to_dict() method (now using `asdict()`)
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

## Current Problems in Server Layer

### Problem 1: S01-Specific DEFAULT_PRESET

**File**: `src/server.py` (lines 156-211, approximate)

**Issue**: DEFAULT_PRESET contains 20+ hardcoded S01-specific parameters:

```python
DEFAULT_PRESET = {
    "name": "Default",
    "maType": "EMA",              # ← S01-specific
    "maLength": 45,               # ← S01-specific
    "closeCountLong": 7,          # ← S01-specific
    "closeCountShort": 5,         # ← S01-specific
    # ... 20+ more S01 parameters
    "filterByProfit": False,
    "minProfitThreshold": 0.0,
}
```

**Why it's wrong**:
- Breaks when user selects S04 strategy (different parameters)
- Violates generic architecture principle
- Strategy defaults should come from config.json, not server

### Problem 2: Dual Naming Fallbacks

**File**: `src/server.py` (lines 1182-1514, approximate)

**Issue**: Code supports both camelCase and snake_case:

```python
# Dual naming support (legacy compatibility)
ma_type = params.get("maType") or params.get("ma_type", "EMA")
ma_length = params.get("maLength") or params.get("ma_length", 45)
close_count_long = params.get("closeCountLong") or params.get("close_count_long", 7)
# ... many more dual fallbacks
```

**Why it's wrong**:
- After Phase 9-5-1, only camelCase exists
- Fallback logic is dead code
- Confuses maintenance ("which format is correct?")

### Problem 3: S01-Specific Parameter Handling

**File**: `src/server.py` (lines 1340-1350, approximate)

**Issue**: Special handling for MA type mappings:

```python
# Special handling for MA types
MA_TYPE_MAPPINGS = {"ema": "EMA", "sma": "SMA", ...}
if "maType" in params:
    params["maType"] = MA_TYPE_MAPPINGS.get(params["maType"], params["maType"])
if "trailLongType" in params:
    params["trailLongType"] = MA_TYPE_MAPPINGS.get(params["trailLongType"], params["trailLongType"])
# ... more S01-specific logic
```

**Why it's wrong**:
- Hardcoded parameter names (`maType`, `trailLongType`)
- S04 doesn't have these parameters
- Validation should be generic based on config.json

### Problem 4: Hardcoded Parameter Types

**File**: `src/server.py` (lines 1318-1333, approximate)

**Issue**: Parameter types extracted via hardcoded dict:

```python
# Extract parameter types (S01-specific hardcoded)
strategy_param_types = {
    "maLength": "int",
    "closeCountLong": "int",
    "closeCountShort": "int",
    # ... hardcoded for S01 only
}
```

**Why it's wrong**:
- Should load from strategy's config.json
- Breaks for S04 and future strategies
- Violates generic architecture

---

## Implementation Plan

You will complete **4 major tasks** sequentially. Each task must be tested before proceeding.

---

## Task 1: Simplify DEFAULT_PRESET

**Goal**: Remove all S01-specific parameters, keep only universal settings.

### 1.1 Locate DEFAULT_PRESET

**File**: `src/server.py` (search for `DEFAULT_PRESET =`)

Find the current DEFAULT_PRESET definition. It should be around lines 156-211.

### 1.2 Replace with Generic Version

**Current** (approximate):
```python
DEFAULT_PRESET = {
    "name": "Default",

    # S01-specific parameters (DELETE ALL)
    "maType": "EMA",
    "maLength": 45,
    "closeCountLong": 7,
    "closeCountShort": 5,
    "stopLongX": 2.0,
    "stopLongRR": 3.0,
    # ... 18+ more S01 parameters

    # Universal settings
    "dateFilter": True,
    "start": None,
    "end": None,
    "optimizationMode": "optuna",
    "nTrials": 100,
    # ... optimization/scoring settings
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

**Rationale**: Strategy-specific defaults come from config.json when user selects a strategy.

### 1.3 Add Comment Documentation

Add docstring comment above DEFAULT_PRESET:

```python
# Default preset containing only universal settings (not strategy-specific).
# Strategy parameter defaults are loaded from each strategy's config.json.
DEFAULT_PRESET = {
    # ...
}
```

### Task 1 Verification

**Checklist**:
- [ ] DEFAULT_PRESET contains zero strategy-specific parameters
- [ ] Only universal settings remain (dates, optimization, scoring, filtering)
- [ ] Docstring comment added explaining design
- [ ] Server starts without errors
- [ ] Default preset can be loaded via API

**Test Command**:
```bash
cd src
python server.py

# In another terminal
curl http://localhost:8000/api/presets
# Verify "Default" preset exists and has no strategy params
```

---

## Task 2: Remove Dual Naming Fallbacks

**Goal**: Eliminate all `params.get("camelCase") or params.get("snake_case")` patterns.

### 2.1 Identify Dual Naming Patterns

**File**: `src/server.py`

Search for dual naming patterns:
```bash
grep -n "params.get.*or params.get" src/server.py
```

Typical pattern:
```python
ma_type = params.get("maType") or params.get("ma_type", "EMA")
```

### 2.2 Replace with camelCase Only

**Pattern to find**:
```python
<variable> = params.get("<camelCase>") or params.get("<snake_case>", <default>)
```

**Replace with**:
```python
<variable> = params.get("<camelCase>", <default>)
```

**Examples**:

**Before**:
```python
ma_type = params.get("maType") or params.get("ma_type", "EMA")
ma_length = params.get("maLength") or params.get("ma_length", 45)
close_count_long = params.get("closeCountLong") or params.get("close_count_long", 7)
close_count_short = params.get("closeCountShort") or params.get("close_count_short", 5)
stop_long_atr = params.get("stopLongX") or params.get("stop_long_atr", 2.0)
```

**After**:
```python
ma_type = params.get("maType", "EMA")
ma_length = params.get("maLength", 45)
close_count_long = params.get("closeCountLong", 7)
close_count_short = params.get("closeCountShort", 5)
stop_long_atr = params.get("stopLongX", 2.0)
```

### 2.3 Search/Replace Guide

Use your editor's search/replace with regex:

**Search pattern** (regex):
```
params\.get\("([^"]+)"\)\s+or\s+params\.get\("([^"]+)",\s*([^)]+)\)
```

**Replace pattern**:
```
params.get("$1", $3)
```

This removes the snake_case fallback and keeps only the camelCase version.

### 2.4 Check Score Config Dual Naming

**File**: `src/server.py` (function `_sanitize_score_config`)

**Before**:
```python
def _sanitize_score_config(score_config: Dict[str, Any]) -> Dict[str, Any]:
    # Dual naming fallbacks
    weights = score_config.get("weights") or score_config.get("score_weights", {})
    enabled_metrics = score_config.get("enabledMetrics") or score_config.get("enabled_metrics", {})
    invert_metrics = score_config.get("invertMetrics") or score_config.get("invert_metrics", {})
    normalization_method = score_config.get("normalizationMethod") or score_config.get("normalization_method", "percentile")
    filter_enabled = score_config.get("filterEnabled") or score_config.get("filter_enabled", False)
    min_score_threshold = score_config.get("minScoreThreshold") or score_config.get("min_score_threshold", 0.0)
```

**After**:
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

### Task 2 Verification

**Checklist**:
- [ ] All dual naming fallbacks removed
- [ ] Only camelCase `.get()` calls remain
- [ ] _sanitize_score_config() simplified
- [ ] No references to snake_case parameter names
- [ ] Server starts without errors
- [ ] API endpoints accept camelCase parameters

**Test Command**:
```bash
# Search for any remaining dual fallbacks
grep -n "or params.get" src/server.py
# Should return no results

# Test backtest endpoint
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{"strategy": "s01_trailing_ma", "params": {"maType": "EMA", "maLength": 45}}'
```

---

## Task 3: Remove S01-Specific Parameter Handling

**Goal**: Delete hardcoded MA type mappings and S01-specific validation.

### 3.1 Locate MA_TYPE_MAPPINGS

**File**: `src/server.py`

Search for `MA_TYPE_MAPPINGS` or similar constants:

```python
MA_TYPE_MAPPINGS = {
    "ema": "EMA",
    "sma": "SMA",
    "hma": "HMA",
    # ... more mappings
}
```

**Action**: **DELETE** this constant entirely.

### 3.2 Remove MA Type Normalization Logic

Search for code that uses MA_TYPE_MAPPINGS:

```python
if "maType" in params:
    params["maType"] = MA_TYPE_MAPPINGS.get(params["maType"], params["maType"])
if "trailLongType" in params:
    params["trailLongType"] = MA_TYPE_MAPPINGS.get(params["trailLongType"], params["trailLongType"])
if "trailShortType" in params:
    params["trailShortType"] = MA_TYPE_MAPPINGS.get(params["trailShortType"], params["trailShortType"])
```

**Action**: **DELETE** all of this code.

**Rationale**: Frontend sends correct values; server shouldn't normalize.

### 3.3 Remove Other S01-Specific Parameter Logic

Search for any other hardcoded parameter names in server.py:

```python
# Example patterns to search for
"maType"
"maLength"
"closeCountLong"
"closeCountShort"
"trailLongType"
"trailShortType"
```

For each occurrence:
- If it's **hardcoded parameter handling** → DELETE
- If it's **generic parameter passing** → KEEP (camelCase dict access is fine)

**Examples**:

**DELETE this** (hardcoded validation):
```python
if params.get("maType") not in MA_TYPES:
    raise ValueError("Invalid maType")
```

**KEEP this** (generic pass-through):
```python
strategy_params = {
    "maType": params.get("maType"),
    "maLength": params.get("maLength"),
    # ... generic dict building
}
```

### Task 3 Verification

**Checklist**:
- [ ] MA_TYPE_MAPPINGS constant deleted
- [ ] All MA type normalization code removed
- [ ] No hardcoded S01 parameter validation
- [ ] Generic parameter passing preserved
- [ ] Server starts without errors
- [ ] S01 backtest works with various MA types

**Test Command**:
```bash
# Search for hardcoded S01 parameter names
grep -n "maType\|trailLongType\|closeCountLong" src/server.py
# Review each result - should only be generic dict access

# Test S01 with different MA types
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{"strategy": "s01_trailing_ma", "params": {"maType": "HMA", "maLength": 50}}'
```

---

## Task 4: Implement Generic Parameter Type Loading

**Goal**: Load parameter types from config.json instead of hardcoded dicts.

### 4.1 Create Helper Function

**File**: `src/server.py`

**Add this function** (place near other helper functions):

```python
def _get_parameter_types(strategy_id: str) -> Dict[str, str]:
    """Load parameter types from strategy configuration.

    Args:
        strategy_id: Strategy identifier (e.g., "s01_trailing_ma")

    Returns:
        Dict mapping parameter name to type (e.g., {"maLength": "int", "obLevel": "float"})

    Raises:
        Exception if strategy config cannot be loaded
    """
    from strategies import get_strategy_config

    config = get_strategy_config(strategy_id)
    parameters = config.get("parameters", {})

    param_types = {}
    for param_name, param_spec in parameters.items():
        if not isinstance(param_spec, dict):
            continue
        param_types[param_name] = param_spec.get("type", "float")

    return param_types
```

### 4.2 Replace Hardcoded strategy_param_types

**Find code like this** (approximate location):

```python
# Extract parameter types (S01-specific hardcoded)
strategy_param_types = {
    "maLength": "int",
    "closeCountLong": "int",
    "closeCountShort": "int",
    "stopLongLP": "int",
    # ... 15+ more hardcoded entries
}
```

**Replace with**:

```python
# Load parameter types from strategy config
try:
    strategy_param_types = _get_parameter_types(strategy_id)
except Exception as e:
    logger.warning(f"Could not load parameter types for {strategy_id}: {e}")
    strategy_param_types = {}  # Fallback to empty dict
```

### 4.3 Update _build_optimization_config()

**Find function** that builds OptimizationConfig (might be inline in endpoint handler).

**Before** (hardcoded parameter knowledge):
```python
def _build_optimization_config(payload: Dict[str, Any]) -> OptimizationConfig:
    # Hardcoded parameter ranges
    config = OptimizationConfig(
        strategy_id=payload.get("strategy"),
        # ... hardcoded S01 knowledge
    )
```

**After** (generic, config-driven):
```python
def _build_optimization_config(payload: Dict[str, Any]) -> OptimizationConfig:
    """Build optimization config from request payload.

    Loads parameter metadata from strategy's config.json.
    """
    strategy_id = payload.get("strategy")

    # Load parameter types and metadata from strategy config
    param_types = _get_parameter_types(strategy_id)

    config = OptimizationConfig(
        strategy_id=strategy_id,
        # ... build generically using param_types
    )

    return config
```

### 4.4 Add Generic Parameter Validation

**Add this function** (optional but recommended):

```python
def _validate_strategy_params(strategy_id: str, params: Dict[str, Any]) -> None:
    """Generic parameter validation based on config.json.

    Args:
        strategy_id: Strategy identifier
        params: Parameter dictionary to validate

    Raises:
        ValueError: If parameter validation fails
    """
    from strategies import get_strategy_config

    try:
        config = get_strategy_config(strategy_id)
    except Exception:
        # If config unavailable, skip validation
        return

    parameters = config.get("parameters", {})

    for param_name, param_config in parameters.items():
        value = params.get(param_name)
        if value is None:
            continue  # Use default from config

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
            if options and value not in options:
                raise ValueError(f"{param_name} must be one of {options}, got {value}")

        elif param_type == "bool":
            if not isinstance(value, bool):
                params[param_name] = bool(value)

        # Range validation (for int/float)
        if param_type in ["int", "float"]:
            min_val = param_config.get("min")
            max_val = param_config.get("max")
            numeric_value = params[param_name]

            if min_val is not None and numeric_value < min_val:
                raise ValueError(f"{param_name} must be >= {min_val}")
            if max_val is not None and numeric_value > max_val:
                raise ValueError(f"{param_name} must be <= {max_val}")
```

**Usage** (in API endpoint handlers):

```python
@app.route("/api/backtest", methods=["POST"])
def backtest():
    payload = request.get_json()
    strategy_id = payload.get("strategy")
    params = payload.get("params", {})

    # Generic validation
    _validate_strategy_params(strategy_id, params)

    # ... rest of backtest logic
```

### Task 4 Verification

**Checklist**:
- [ ] _get_parameter_types() helper added
- [ ] Hardcoded strategy_param_types replaced with dynamic loading
- [ ] _build_optimization_config() uses generic loading
- [ ] _validate_strategy_params() added (optional)
- [ ] Validation works for both S01 and S04
- [ ] Server starts without errors
- [ ] Type validation catches invalid inputs

**Test Command**:
```bash
# Test S01 validation
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{"strategy": "s01_trailing_ma", "params": {"maLength": "invalid"}}'
# Should return validation error

# Test S04 validation
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{"strategy": "s04_stochrsi", "params": {"rsiLen": 16, "obLevel": 150.0}}'
# Should return validation error (obLevel > 100)
```

---

## Testing Requirements

### Regression Testing

After completing all tasks, run comprehensive tests:

1. **Server Startup**:
   - Server starts without errors
   - Default preset loads correctly
   - No warnings about missing parameters

2. **S01 Backtest**:
   - Submit backtest with camelCase parameters
   - Verify results returned
   - Check trade count and metrics

3. **S04 Backtest**:
   - Submit backtest with S04 parameters
   - Verify results returned
   - Verify different parameter set works

4. **Optimization**:
   - Run small optimization (10 trials) for S01
   - Run small optimization (10 trials) for S04
   - Verify both complete without errors
   - Check CSV export format

5. **Parameter Validation**:
   - Test invalid parameter types (string for int)
   - Test out-of-range values
   - Test invalid select options
   - Verify appropriate errors returned

### Integration Testing

**Test Workflow**:
```bash
# 1. Start server
cd src
python server.py

# 2. In another terminal, test endpoints

# Test default preset
curl http://localhost:8000/api/presets

# Test S01 backtest
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d @test_s01_backtest.json

# Test S04 backtest
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d @test_s04_backtest.json

# Test optimization
curl -X POST http://localhost:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d @test_s01_optimize.json
```

**Sample test_s01_backtest.json**:
```json
{
  "strategy": "s01_trailing_ma",
  "params": {
    "maType": "EMA",
    "maLength": 45,
    "closeCountLong": 7,
    "closeCountShort": 5,
    "riskPerTrade": 2.0
  },
  "csvFile": "../data/OKX_LINKUSDT.P, 15...csv"
}
```

**Sample test_s04_backtest.json**:
```json
{
  "strategy": "s04_stochrsi",
  "params": {
    "rsiLen": 16,
    "stochLen": 16,
    "kLen": 3,
    "dLen": 3,
    "obLevel": 75.0,
    "osLevel": 15.0
  },
  "csvFile": "../data/OKX_LINKUSDT.P, 15...csv"
}
```

### Performance Testing

Verify no performance regression:

1. **Benchmark Request Latency**:
   - Measure backtest API response time before refactoring
   - Measure backtest API response time after refactoring
   - Verify within 5% tolerance

2. **Optimization Throughput**:
   - Run 100-trial optimization before refactoring
   - Run 100-trial optimization after refactoring
   - Verify throughput preserved (trials/second)

---

## Code Quality Standards

### Style Guidelines

1. **Type Hints**: Use type hints for all function signatures
   ```python
   def _get_parameter_types(strategy_id: str) -> Dict[str, str]:
   ```

2. **Docstrings**: Document all public functions with Google-style docstrings
   ```python
   def _validate_strategy_params(strategy_id: str, params: Dict[str, Any]) -> None:
       """Generic parameter validation based on config.json.

       Args:
           strategy_id: Strategy identifier
           params: Parameter dictionary to validate

       Raises:
           ValueError: If parameter validation fails
       """
   ```

3. **Naming**: Follow PEP 8 for function/variable names (snake_case)
4. **Line Length**: Max 100 characters

### Error Handling

1. **Validation**: Validate all inputs at API boundaries
2. **Logging**: Use logging module, not print statements
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.warning(f"Could not load config for {strategy_id}: {e}")
   ```

3. **Exceptions**: Raise specific exceptions with clear messages
   ```python
   raise ValueError(f"{param_name} must be >= {min_val}")
   ```

4. **Graceful Degradation**: Fallback to sensible defaults when possible

### Comments

1. **WHY not WHAT**: Explain rationale, not obvious operations
   ```python
   # Load from config.json instead of hardcoded dict for strategy-agnostic operation
   param_types = _get_parameter_types(strategy_id)
   ```

2. **TODOs**: Include author and date
   ```python
   # TODO(codex, 2025-01-15): Consider caching parameter types for performance
   ```

3. **Complex Logic**: Document non-obvious algorithms

### Git Commits

1. **Atomic Commits**: One logical change per commit
2. **Commit Messages**:
   - Format: `[Phase 9-5-2] Brief description`
   - Examples:
     - `[Phase 9-5-2] Remove S01-specific defaults from DEFAULT_PRESET`
     - `[Phase 9-5-2] Eliminate dual naming fallbacks in server.py`
     - `[Phase 9-5-2] Implement generic parameter type loading`

3. **Testing**: Ensure tests pass before committing

---

## File Reference Guide

### Server File

**Primary File**:
- `src/server.py` - Flask API server (~1922 lines)

**Key Sections to Modify**:
- DEFAULT_PRESET definition (search for `DEFAULT_PRESET =`)
- Dual naming fallbacks (search for `params.get.*or params.get`)
- _sanitize_score_config function (search for `def _sanitize_score_config`)
- MA_TYPE_MAPPINGS (search for `MA_TYPE_MAPPINGS`)
- Hardcoded parameter types (search for `strategy_param_types`)
- Optimization config building (search for `OptimizationConfig`)

### Strategy Files (Reference Only)

**S01 Trailing MA**:
- `src/strategies/s01_trailing_ma/config.json` - Parameter definitions (412 lines)
- `src/strategies/s01_trailing_ma/strategy.py` - Strategy implementation (465 lines)

**S04 StochRSI**:
- `src/strategies/s04_stochrsi/config.json` - Parameter definitions (134 lines)
- `src/strategies/s04_stochrsi/strategy.py` - Strategy implementation

**Strategies Module**:
- `src/strategies/__init__.py` - Contains `get_strategy_config()` function

---

## Success Criteria

After completing Phase 9-5-2, verify:

- [ ] **DEFAULT_PRESET contains zero S01-specific parameters**
- [ ] **Only universal settings** in DEFAULT_PRESET (dates, optimization, scoring)
- [ ] **All dual naming fallbacks removed** from server.py
- [ ] **No snake_case parameter references** remain
- [ ] **MA_TYPE_MAPPINGS deleted**
- [ ] **S01-specific parameter handling deleted**
- [ ] **_get_parameter_types() function added**
- [ ] **Parameter types loaded from config.json**
- [ ] **Generic parameter validation implemented**
- [ ] **Server starts without errors**
- [ ] **S01 backtest works** via API
- [ ] **S04 backtest works** via API
- [ ] **Optimization works** for both strategies
- [ ] **Parameter validation works** for both strategies
- [ ] **No performance regression** (request latency within 5%)

---

## Critical Preservation

**DO NOT MODIFY**:
1. Multiprocessing cache architecture (not in server.py)
2. Performance-critical indicator calculations (not in server.py)
3. Metrics calculation logic (not in server.py)
4. Trade simulation core logic (not in server.py)

**ONLY MODIFY**:
- `src/server.py` (Flask API server)
- No other files should be changed in this phase

---

## Next Steps

After completing Phase 9-5-2:

1. **Commit all changes** with clear commit messages
2. **Run full test suite** to ensure no regressions
3. **Document any issues** encountered during implementation
4. **Proceed to Phase 9-5-3** which will:
   - Remove `requires_ma_selection` feature flag from config.json
   - Implement generic parameter rendering in frontend
   - Update UI to handle any strategy's parameters dynamically

---

## Questions or Issues

If you encounter ambiguity or issues:

1. **Preserve existing behavior** - Refactoring should not change functionality
2. **Ask for clarification** - Don't guess on critical decisions
3. **Document assumptions** - Add comments explaining non-obvious choices
4. **Test incrementally** - Verify each task before moving to next

---

**END OF PHASE 9-5-2 PROMPT**
