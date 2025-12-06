# Phase 9-5-4: Testing & Documentation - Finalize Refactoring

**Target Agent**: GPT 5.1 Codex
**Project**: S_01 Trailing MA Backtesting Platform
**Task**: Phase 9-5-4 - Testing & Documentation
**Complexity**: High (Comprehensive testing and documentation)
**Priority**: Critical (Final phase of Phase 9-5 refactoring)
**Prerequisites**: Phases 9-5-1, 9-5-2, and 9-5-3 must be completed first

---

## Executive Summary

This is **Phase 9-5-4**, the final phase in the comprehensive refactoring series to eliminate S01/S04 architecture inconsistencies.

**Phases 9-5-1 through 9-5-3 (Completed)**:
- Standardized all parameters to camelCase throughout the system
- Made core data structures generic (OptimizationResult, CSV export)
- Cleaned up server layer (removed S01-specific defaults, dual naming)
- Refactored frontend UI (generic parameter rendering from config.json)

**Phase 9-5-4 (This Phase)** focuses on **testing and documentation**:
- Update all test fixtures to use camelCase parameters
- Create comprehensive naming consistency tests
- Update CLAUDE.md with new naming conventions
- Update PROJECT_TARGET_ARCHITECTURE.md
- Create ADDING_NEW_STRATEGY.md developer guide
- Run full regression test suite
- Verify end-to-end functionality

**Success Metric**: After Phase 9-5-4, all tests pass, documentation is current, and the system is fully verified to work with both S01 and S04 strategies using the new architecture.

---

## Table of Contents

1. [Project Context](#project-context)
2. [Previous Phases Recap](#previous-phases-recap)
3. [Implementation Plan](#implementation-plan)
4. [Testing Requirements](#testing-requirements)
5. [Documentation Standards](#documentation-standards)
6. [File Reference Guide](#file-reference-guide)

---

## Project Context

### What This Project Does

This is a **backtesting and optimization platform** for trading strategies with a fully generic, config-driven architecture.

### Architecture After Refactoring

**Parameter Flow** (No Conversions):
```
Pine Script (camelCase) → config.json (camelCase) → Python (camelCase) → CSV (camelCase)
```

**Hybrid Architecture**:
- **Strategy Level**: Typed dataclasses with camelCase fields (e.g., `S01Params.maType`)
- **Core Level**: Generic dicts `Dict[str, Any]` (e.g., `OptimizationResult.params`)

**Config-Driven System**:
- Backend loads parameter types from config.json
- Frontend renders parameters from config.json
- CSV export builds columns from config.json
- No hardcoded parameter names in core modules

---

## Previous Phases Recap

### ✓ Phase 9-5-1: Foundation Refactoring
- Converted S01Params and S04Params to camelCase
- Made OptimizationResult generic with `params: Dict[str, Any]`
- Created dynamic CSV export from config.json
- Deleted `to_dict()` methods, using `asdict()` instead

### ✓ Phase 9-5-2: Server Layer Cleanup
- Removed S01-specific parameters from DEFAULT_PRESET
- Eliminated all dual naming fallbacks
- Implemented `_get_parameter_types()` to load from config.json
- Added generic parameter validation

### ✓ Phase 9-5-3: Frontend UI Refactoring
- Removed `requires_ma_selection` feature flag
- Implemented generic parameter rendering based on type
- Added strategy config API endpoint
- Frontend now renders any strategy's parameters without code changes

**Current State**: Architecture is fully generic and config-driven. Now we need to verify it works and document it properly.

---

## Implementation Plan

You will complete **4 major tasks** sequentially. Each task builds upon the previous.

---

## Task 1: Update Test Fixtures

**Goal**: Convert all test data to use camelCase parameters.

### 1.1 Locate Test Files

**Find all test files**:
```bash
find ./tests -name "*.py" -type f
```

Expected files:
- `tests/test_regression_s01.py`
- `tests/test_optuna_engine.py`
- `tests/test_export.py`
- `tests/test_backtest_engine.py`
- Others as needed

### 1.2 Update S01 Test Fixtures

**For each test file**, find parameter dictionaries and convert to camelCase.

**Example - Before**:
```python
def test_s01_backtest():
    params = {
        "ma_type": "EMA",
        "ma_length": 45,
        "close_count_long": 7,
        "close_count_short": 5,
        "stop_long_atr": 2.0,
        "stop_long_rr": 3.0,
        "stop_long_lp": 2,
        "trail_rr_long": 1.0,
        "trail_ma_long_type": "SMA",
        "trail_ma_long_length": 160,
        "trail_ma_long_offset": -1.0,
        "risk_per_trade_pct": 2.0,
        "contract_size": 0.01,
        "commission_rate": 0.0005,
        "atr_period": 14,
    }
```

**After**:
```python
def test_s01_backtest():
    params = {
        "maType": "EMA",
        "maLength": 45,
        "closeCountLong": 7,
        "closeCountShort": 5,
        "stopLongX": 2.0,
        "stopLongRR": 3.0,
        "stopLongLP": 2,
        "stopShortX": 2.0,
        "stopShortRR": 3.0,
        "stopShortLP": 2,
        "stopLongMaxPct": 3.0,
        "stopShortMaxPct": 3.0,
        "stopLongMaxDays": 2,
        "stopShortMaxDays": 4,
        "trailRRLong": 1.0,
        "trailRRShort": 1.0,
        "trailLongType": "SMA",
        "trailLongLength": 160,
        "trailLongOffset": -1.0,
        "trailShortType": "SMA",
        "trailShortLength": 160,
        "trailShortOffset": 1.0,
        "riskPerTrade": 2.0,
        "contractSize": 0.01,
        "commissionRate": 0.0005,
        "atrPeriod": 14,
    }
```

### 1.3 Update S04 Test Fixtures

**Verify S04 tests** already use camelCase (they should).

**Example**:
```python
def test_s04_backtest():
    params = {
        "rsiLen": 16,
        "stochLen": 16,
        "kLen": 3,
        "dLen": 3,
        "obLevel": 75.0,
        "osLevel": 15.0,
        "extLookback": 23,
        "confirmBars": 14,
        "riskPerTrade": 2.0,
        "contractSize": 0.01,
        "initialCapital": 100.0,
        "commissionPct": 0.05,
    }
```

### 1.4 Update Expected Outputs

**For regression tests**, update expected CSV column names.

**Before**:
```python
def test_csv_export():
    expected_columns = [
        "ma_type",
        "ma_length",
        "close_count_long",
        # ...
    ]
```

**After**:
```python
def test_csv_export():
    expected_columns = [
        "maType",
        "maLength",
        "closeCountLong",
        # ...
    ]
```

### 1.5 Update Mock Data

**For unit tests** that mock OptimizationResult:

**Before**:
```python
result = OptimizationResult(
    ma_type="EMA",
    ma_length=45,
    # ... 20+ S01-specific fields
    net_profit_pct=1234.56,
)
```

**After**:
```python
result = OptimizationResult(
    params={
        "maType": "EMA",
        "maLength": 45,
        "closeCountLong": 7,
        # ... all parameters as dict
    },
    net_profit_pct=1234.56,
    max_drawdown_pct=15.3,
    total_trades=42,
    # ... metrics only
)
```

### Task 1 Verification

**Checklist**:
- [ ] All test parameter dicts use camelCase
- [ ] S01 test fixtures updated (24 parameters)
- [ ] S04 test fixtures verified (already camelCase)
- [ ] Expected CSV column names updated
- [ ] OptimizationResult mocks use `params` dict
- [ ] No snake_case parameter names in tests

**Test Command**:
```bash
cd tests
pytest -v

# Run specific test files
pytest test_regression_s01.py -v
pytest test_export.py -v
pytest test_optuna_engine.py -v
```

---

## Task 2: Create Naming Consistency Tests

**Goal**: Add automated tests to prevent regression to snake_case.

### 2.1 Create test_naming_consistency.py

**File**: `tests/test_naming_consistency.py` (NEW)

**Create this file**:

```python
"""Test naming consistency across the codebase.

Ensures all parameters use camelCase throughout the system,
preventing regression to snake_case naming.
"""
import pytest
from dataclasses import fields
from typing import Dict, Any

from strategies.s01_trailing_ma.strategy import S01Params, S01Strategy
from strategies.s04_stochrsi.strategy import S04Params, S04Strategy
from strategies import get_strategy_config


class TestParameterNaming:
    """Test parameter naming conventions."""

    def test_s01_params_use_camelCase(self):
        """Verify all S01Params fields use camelCase (no underscores)."""
        internal_params = {"use_backtester", "use_date_filter", "start", "end"}

        for field in fields(S01Params):
            # Skip internal control parameters
            if field.name in internal_params:
                continue

            # Strategy parameters must use camelCase (no underscores)
            assert "_" not in field.name, (
                f"S01Params field '{field.name}' uses snake_case. "
                f"All strategy parameters must use camelCase."
            )

    def test_s04_params_use_camelCase(self):
        """Verify all S04Params fields use camelCase (no underscores)."""
        internal_params = {"use_backtester", "use_date_filter", "start", "end"}

        for field in fields(S04Params):
            # Skip internal control parameters
            if field.name in internal_params:
                continue

            # Strategy parameters must use camelCase
            assert "_" not in field.name, (
                f"S04Params field '{field.name}' uses snake_case. "
                f"All strategy parameters must use camelCase."
            )


class TestConfigParameterConsistency:
    """Test config.json matches Python Params dataclasses."""

    def test_s01_config_matches_params(self):
        """Verify S01 config.json parameter names match S01Params dataclass."""
        config = get_strategy_config("s01_trailing_ma")
        config_params = set(config["parameters"].keys())

        internal_params = {"use_backtester", "use_date_filter", "start", "end"}
        dataclass_params = {
            f.name for f in fields(S01Params)
            if f.name not in internal_params
        }

        # All config params should exist in dataclass
        for param_name in config_params:
            assert param_name in dataclass_params, (
                f"Config param '{param_name}' not found in S01Params dataclass"
            )

        # All dataclass params should exist in config
        for param_name in dataclass_params:
            assert param_name in config_params, (
                f"Dataclass param '{param_name}' not found in S01 config.json"
            )

    def test_s04_config_matches_params(self):
        """Verify S04 config.json parameter names match S04Params dataclass."""
        config = get_strategy_config("s04_stochrsi")
        config_params = set(config["parameters"].keys())

        internal_params = {"use_backtester", "use_date_filter", "start", "end"}
        dataclass_params = {
            f.name for f in fields(S04Params)
            if f.name not in internal_params
        }

        # All config params should exist in dataclass
        for param_name in config_params:
            assert param_name in dataclass_params, (
                f"Config param '{param_name}' not found in S04Params dataclass"
            )

        # All dataclass params should exist in config
        for param_name in dataclass_params:
            assert param_name in config_params, (
                f"Dataclass param '{param_name}' not found in S04 config.json"
            )


class TestNoConversionCode:
    """Test that no snake_case ↔ camelCase conversion exists."""

    def test_no_to_dict_method(self):
        """Verify Params dataclasses don't have to_dict() method."""
        assert not hasattr(S01Params, "to_dict"), (
            "S01Params should not have to_dict() method. Use asdict() instead."
        )
        assert not hasattr(S04Params, "to_dict"), (
            "S04Params should not have to_dict() method. Use asdict() instead."
        )

    def test_from_dict_no_conversion(self):
        """Verify from_dict() uses direct mapping (no conversion)."""
        import inspect

        # Check S01Params.from_dict
        s01_source = inspect.getsource(S01Params.from_dict)
        assert "ma_type" not in s01_source, (
            "S01Params.from_dict contains snake_case conversion for 'ma_type'"
        )
        assert "ma_length" not in s01_source, (
            "S01Params.from_dict contains snake_case conversion for 'ma_length'"
        )
        assert "close_count_long" not in s01_source, (
            "S01Params.from_dict contains snake_case conversion for 'close_count_long'"
        )

        # Check S04Params.from_dict
        s04_source = inspect.getsource(S04Params.from_dict)
        # S04 should already be clean, but verify no legacy snake_case
        assert "rsi_len" not in s04_source, (
            "S04Params.from_dict contains snake_case conversion"
        )


class TestParameterTypes:
    """Test parameter type definitions are valid."""

    VALID_TYPES = {"int", "float", "select", "options", "bool", "boolean"}

    def test_s01_parameter_types_valid(self):
        """Verify all S01 parameters use valid types."""
        config = get_strategy_config("s01_trailing_ma")
        parameters = config.get("parameters", {})

        for param_name, param_spec in parameters.items():
            param_type = param_spec.get("type")
            assert param_type in self.VALID_TYPES, (
                f"S01 param '{param_name}' has invalid type '{param_type}'. "
                f"Valid types: {self.VALID_TYPES}"
            )

    def test_s04_parameter_types_valid(self):
        """Verify all S04 parameters use valid types."""
        config = get_strategy_config("s04_stochrsi")
        parameters = config.get("parameters", {})

        for param_name, param_spec in parameters.items():
            param_type = param_spec.get("type")
            assert param_type in self.VALID_TYPES, (
                f"S04 param '{param_name}' has invalid type '{param_type}'. "
                f"Valid types: {self.VALID_TYPES}"
            )

    def test_select_types_have_options(self):
        """Verify 'select' type parameters have 'options' field."""
        for strategy_id in ["s01_trailing_ma", "s04_stochrsi"]:
            config = get_strategy_config(strategy_id)
            parameters = config.get("parameters", {})

            for param_name, param_spec in parameters.items():
                param_type = param_spec.get("type")
                if param_type in ["select", "options"]:
                    options = param_spec.get("options")
                    assert options is not None, (
                        f"{strategy_id} param '{param_name}' is type 'select' "
                        f"but has no 'options' field"
                    )
                    assert isinstance(options, list), (
                        f"{strategy_id} param '{param_name}' options must be a list"
                    )
                    assert len(options) > 0, (
                        f"{strategy_id} param '{param_name}' options list is empty"
                    )


class TestNoFeatureFlags:
    """Test that feature flags have been removed."""

    def test_s01_no_features_section(self):
        """Verify S01 config.json has no 'features' section."""
        config = get_strategy_config("s01_trailing_ma")
        assert "features" not in config, (
            "S01 config.json should not have 'features' section. "
            "Use parameter types instead (e.g., 'type': 'select')."
        )

    def test_s04_no_features_section(self):
        """Verify S04 config.json has no 'features' section."""
        config = get_strategy_config("s04_stochrsi")
        assert "features" not in config, (
            "S04 config.json should not have 'features' section."
        )


class TestOptimizationResultStructure:
    """Test OptimizationResult uses generic structure."""

    def test_optimization_result_has_params_dict(self):
        """Verify OptimizationResult has 'params' field."""
        from core.optuna_engine import OptimizationResult
        from dataclasses import fields as get_fields

        field_names = {f.name for f in get_fields(OptimizationResult)}

        assert "params" in field_names, (
            "OptimizationResult should have 'params' field (generic dict)"
        )

    def test_optimization_result_no_s01_fields(self):
        """Verify OptimizationResult has no S01-specific parameter fields."""
        from core.optuna_engine import OptimizationResult
        from dataclasses import fields as get_fields

        field_names = {f.name for f in get_fields(OptimizationResult)}

        # These should NOT exist (S01-specific)
        forbidden_fields = {
            "ma_type", "ma_length", "close_count_long", "close_count_short",
            "stop_long_atr", "trail_rr_long", "trail_ma_long_type",
        }

        for forbidden in forbidden_fields:
            assert forbidden not in field_names, (
                f"OptimizationResult should not have S01-specific field '{forbidden}'. "
                f"Use 'params' dict instead."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### 2.2 Run Naming Tests

**Execute tests**:
```bash
cd tests
pytest test_naming_consistency.py -v
```

**Expected output**:
```
test_naming_consistency.py::TestParameterNaming::test_s01_params_use_camelCase PASSED
test_naming_consistency.py::TestParameterNaming::test_s04_params_use_camelCase PASSED
test_naming_consistency.py::TestConfigParameterConsistency::test_s01_config_matches_params PASSED
test_naming_consistency.py::TestConfigParameterConsistency::test_s04_config_matches_params PASSED
test_naming_consistency.py::TestNoConversionCode::test_no_to_dict_method PASSED
test_naming_consistency.py::TestNoConversionCode::test_from_dict_no_conversion PASSED
test_naming_consistency.py::TestParameterTypes::test_s01_parameter_types_valid PASSED
test_naming_consistency.py::TestParameterTypes::test_s04_parameter_types_valid PASSED
test_naming_consistency.py::TestParameterTypes::test_select_types_have_options PASSED
test_naming_consistency.py::TestNoFeatureFlags::test_s01_no_features_section PASSED
test_naming_consistency.py::TestNoFeatureFlags::test_s04_no_features_section PASSED
test_naming_consistency.py::TestOptimizationResultStructure::test_optimization_result_has_params_dict PASSED
test_naming_consistency.py::TestOptimizationResultStructure::test_optimization_result_no_s01_fields PASSED
```

### Task 2 Verification

**Checklist**:
- [ ] test_naming_consistency.py created
- [ ] Tests for camelCase parameter naming
- [ ] Tests for config/dataclass consistency
- [ ] Tests for no conversion code
- [ ] Tests for valid parameter types
- [ ] Tests for no feature flags
- [ ] Tests for generic OptimizationResult
- [ ] All naming tests pass

---

## Task 3: Update Documentation

**Goal**: Update project documentation to reflect new architecture.

### 3.1 Update CLAUDE.md

**File**: `CLAUDE.md`

**Add new section** at the top (after Project Overview):

```markdown
## Naming Convention: camelCase Throughout

**Critical Rule**: All strategy parameters MUST use camelCase matching Pine Script conventions.

### Parameter Flow (No Conversions)

```
Pine Script (camelCase) → config.json (camelCase) → Python (camelCase) → CSV (camelCase)
```

**Example**:
- Pine Script: `input.int(16, "RSI Length")` → variable `rsiLen`
- config.json: `"rsiLen": {"type": "int", "default": 16}`
- Python Params: `rsiLen: int = 16`
- CSV export: column header `rsiLen`

### Parameter Type System

Match Pine Script input types to config.json types:

| Pine Script Input | config.json Type | Frontend Widget | Python Type | Formatter |
|-------------------|------------------|-----------------|-------------|-----------|
| `input.int()` | `"type": "int"` | Number input (step=1) | `int` | None |
| `input.float()` | `"type": "float"` | Number input (step=0.1) | `float` | "float1" |
| `input.string(options=[...])` | `"type": "select"` | Dropdown | `str` | None |
| `input.bool()` | `"type": "bool"` | Checkbox | `bool` | None |

### Hybrid Architecture Pattern

**Strategy Level** (Type Safety):
```python
@dataclass
class S05Params:
    rsiLen: int = 16  # ← camelCase, typed
    maType: str = "EMA"
    threshold: float = 0.5
```

**Core Modules** (Generic):
```python
def optimize(params: Dict[str, Any]):  # ← Generic dict
    result = OptimizationResult(
        params=params,  # ← Store as-is
        net_profit_pct=1234.56,
    )
```

### Adding New Strategies

1. **Parameter names**: Use camelCase (e.g., `rsiLen`, not `rsi_len`)
2. **Params dataclass**: Typed fields with camelCase names
3. **from_dict()**: Direct mapping, no conversion
4. **No to_dict()**: Use `asdict(params)` from dataclasses module
5. **config.json**: Use correct parameter types (int/float/select/bool)
6. **No feature flags**: Use parameter types for UI rendering

### Performance Note

The multiprocessing cache architecture MUST be preserved. When modifying optimization logic, respect the caching pattern in `_init_worker()`.
```

### 3.2 Update PROJECT_TARGET_ARCHITECTURE.md

**File**: `docs/PROJECT_TARGET_ARCHITECTURE.md`

**Add section**:

```markdown
## Naming Convention and Parameter Flow

### camelCase Throughout

All strategy parameters use **camelCase** matching Pine Script conventions. No conversion layers exist.

**Parameter Flow**:
```
Pine Script (rsiLen) → config.json (rsiLen) → Python (rsiLen) → CSV (rsiLen)
```

**Benefits**:
- No conversion code needed
- Parameter names identical across entire pipeline
- Easier debugging (same name everywhere)
- Matches Pine Script source
- IDE autocomplete works seamlessly

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
- Built-in `asdict()` converts back to dict when needed

### Config-Driven System

**Backend**:
- `_get_parameter_types()` loads from config.json
- `_validate_strategy_params()` validates based on config.json
- `_build_column_specs_for_strategy()` builds CSV columns from config.json

**Frontend**:
- `renderStrategyParameters()` renders from config.json
- `renderParameter()` chooses widget based on type
- No hardcoded parameter names

**Benefits**:
- Adding new strategy requires only config.json + strategy.py
- No core module changes
- No frontend changes
- Automatic UI rendering
- Automatic CSV export
```

### 3.3 Create ADDING_NEW_STRATEGY.md

**File**: `docs/ADDING_NEW_STRATEGY.md` (NEW)

**Create comprehensive guide** (see full template in original Phase 9-5-2 prompt, Task 6.7).

**Key sections**:
1. Step 1: Create Strategy Directory
2. Step 2: Define config.json (with examples)
3. Step 3: Define Params Dataclass (camelCase)
4. Step 4: Implement Strategy Class
5. Step 5: Register Strategy
6. Step 6: Test
7. Common Mistakes to Avoid
8. Architecture Guarantees

**Example snippet**:

```markdown
# Adding a New Strategy

## Quick Start

```bash
# 1. Create directory
mkdir -p src/strategies/s05_mystrategy

# 2. Create files
touch src/strategies/s05_mystrategy/__init__.py
touch src/strategies/s05_mystrategy/strategy.py
touch src/strategies/s05_mystrategy/config.json
```

## Define config.json

Use camelCase parameter names matching Pine Script:

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
      "group": "Indicators"
    },
    "threshold": {
      "type": "float",
      "label": "Entry Threshold",
      "default": 0.5,
      "min": 0.0,
      "max": 1.0
    }
  }
}
```

## Define Params Dataclass

```python
@dataclass
class S05Params:
    """S05 strategy parameters - camelCase matching Pine Script."""
    rsiLen: int = 14
    threshold: float = 0.5

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "S05Params":
        """Direct mapping - no conversion."""
        return cls(
            rsiLen=int(d.get("rsiLen", 14)),
            threshold=float(d.get("threshold", 0.5)),
        )
```

## Architecture Guarantees

After following this guide:
- ✅ Frontend renders your parameters automatically
- ✅ Optimization works without core module changes
- ✅ CSV export includes your parameters automatically
- ✅ Parameter validation works generically
- ✅ Your strategy treated identically to S01 and S04
```

### 3.4 Update README.md

**File**: `README.md` or top-level project README

**Add note** about naming conventions:

```markdown
## Development Notes

### Parameter Naming Convention

All strategy parameters use **camelCase** to match Pine Script conventions:
- ✅ `rsiLen`, `maType`, `closeCountLong`
- ❌ `rsi_len`, `ma_type`, `close_count_long`

See [ADDING_NEW_STRATEGY.md](docs/ADDING_NEW_STRATEGY.md) for details.
```

### Task 3 Verification

**Checklist**:
- [ ] CLAUDE.md updated with naming conventions
- [ ] CLAUDE.md documents hybrid architecture
- [ ] PROJECT_TARGET_ARCHITECTURE.md updated
- [ ] ADDING_NEW_STRATEGY.md created
- [ ] README.md updated with development notes
- [ ] All markdown files are valid (no syntax errors)
- [ ] Documentation is clear and comprehensive

---

## Task 4: Run Full Regression Test Suite

**Goal**: Verify entire system works end-to-end with both strategies.

### 4.1 Run Unit Tests

**Execute all unit tests**:
```bash
cd tests
pytest -v
```

**Verify**:
- All tests pass
- No warnings about deprecated code
- No errors about missing parameters

### 4.2 Run Integration Tests

**S01 End-to-End Test**:

```bash
# 1. Start server
cd src
python server.py &
SERVER_PID=$!

# 2. Test backtest endpoint
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "s01_trailing_ma",
    "params": {
      "maType": "EMA",
      "maLength": 45,
      "closeCountLong": 7,
      "closeCountShort": 5,
      "riskPerTrade": 2.0
    },
    "csvFile": "../data/OKX_LINKUSDT.P, 15...csv"
  }'

# 3. Test optimization endpoint
curl -X POST http://localhost:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "s01_trailing_ma",
    "nTrials": 10,
    "params": {...}
  }' > s01_optimization_results.csv

# 4. Verify CSV format
head -20 s01_optimization_results.csv

# 5. Stop server
kill $SERVER_PID
```

**S04 End-to-End Test**:

```bash
# Repeat similar tests for S04
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

### 4.3 Browser Testing

**Manual testing in browser**:

1. Open http://localhost:8000
2. Select S01 strategy
3. Verify all parameters render correctly
4. Change some parameter values
5. Submit backtest
6. Verify results displayed
7. Submit optimization (10 trials)
8. Verify CSV downloads
9. Switch to S04 strategy
10. Repeat steps 3-8
11. Verify no JavaScript errors in console

### 4.4 Performance Regression Test

**Benchmark optimization speed**:

```python
# benchmark_optimization.py
import time
from core.optuna_engine import run_optimization, OptimizationConfig

config = OptimizationConfig(
    strategy_id="s01_trailing_ma",
    n_trials=100,
    # ... full config
)

start = time.time()
results = run_optimization(config)
elapsed = time.time() - start

print(f"100 trials completed in {elapsed:.2f} seconds")
print(f"Throughput: {100/elapsed:.2f} trials/second")
```

**Verify**:
- Performance within 5% of baseline
- No memory leaks
- All trials complete successfully

### 4.5 Create Regression Test Report

**Create file**: `tests/REGRESSION_TEST_REPORT.md`

**Template**:

```markdown
# Phase 9-5 Regression Test Report

**Date**: YYYY-MM-DD
**Tester**: [Your Name]
**Phases Completed**: 9-5-1, 9-5-2, 9-5-3, 9-5-4

## Summary

- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ S01 backtest works
- ✅ S04 backtest works
- ✅ S01 optimization works
- ✅ S04 optimization works
- ✅ Frontend renders parameters correctly
- ✅ No performance regression

## Test Results

### Unit Tests

```
pytest -v
======================== test session starts ========================
collected 47 items

tests/test_naming_consistency.py::TestParameterNaming::test_s01_params_use_camelCase PASSED
...
======================== 47 passed in 12.3s ========================
```

### Integration Tests

**S01 Backtest**:
- Status: ✅ Pass
- Execution time: 2.3s
- Trades generated: 42
- Net profit: 1234.56%

**S04 Backtest**:
- Status: ✅ Pass
- Execution time: 1.8s
- Trades generated: 38
- Net profit: 987.65%

**S01 Optimization (100 trials)**:
- Status: ✅ Pass
- Execution time: 45.2s
- Throughput: 2.21 trials/sec
- Best score: 5.67

**S04 Optimization (100 trials)**:
- Status: ✅ Pass
- Execution time: 38.9s
- Throughput: 2.57 trials/sec
- Best score: 4.23

### Browser Testing

- ✅ S01 parameters render correctly
- ✅ S04 parameters render correctly
- ✅ MA type dropdowns work
- ✅ Number inputs work
- ✅ Form submission works
- ✅ No JavaScript errors

### Performance

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Optimization (100 trials) | 44.5s | 45.2s | +1.6% |
| Backtest latency | 2.1s | 2.3s | +9.5% |
| Memory usage | 850MB | 860MB | +1.2% |

**Conclusion**: Performance within acceptable range (< 10% change).

## Issues Found

None.

## Recommendations

- Consider adding more test coverage for edge cases
- Monitor performance over time
- Document any future parameter additions

## Sign-off

This system is verified to work correctly with the new generic, config-driven architecture.
```

### Task 4 Verification

**Checklist**:
- [ ] All unit tests pass (pytest)
- [ ] S01 backtest works via API
- [ ] S04 backtest works via API
- [ ] S01 optimization works (10+ trials)
- [ ] S04 optimization works (10+ trials)
- [ ] CSV exports have correct format
- [ ] Frontend renders S01 parameters
- [ ] Frontend renders S04 parameters
- [ ] Browser testing complete (no errors)
- [ ] Performance regression test complete (< 10% change)
- [ ] Regression test report created

---

## Testing Requirements

### Acceptance Criteria

**All of these must be true**:

1. **No hardcoded parameter names** in core modules (optuna_engine, export, server)
2. **Single naming convention** (camelCase) throughout entire system
3. **No strategy-specific conditionals** (`if strategy_id == "s01"`) in core
4. **No conversion code** between naming conventions
5. **S01 and S04 treated identically** by core system
6. **Adding new strategy requires only** config.json + strategy.py
7. **All tests pass** (unit, integration, browser)
8. **CSV export works correctly** for both strategies
9. **Optimization completes** without errors
10. **Performance preserved** (< 10% regression)
11. **Documentation updated** and accurate

### Manual Verification Checklist

- [ ] Server starts without warnings
- [ ] Default preset loads (no S01-specific params)
- [ ] S01 config has no feature flags
- [ ] S04 config has no feature flags
- [ ] S01 parameters render in browser
- [ ] S04 parameters render in browser
- [ ] S01 backtest completes successfully
- [ ] S04 backtest completes successfully
- [ ] S01 optimization completes (10 trials)
- [ ] S04 optimization completes (10 trials)
- [ ] CSV has correct column headers (camelCase)
- [ ] No JavaScript errors in browser console
- [ ] Parameter validation works (rejects invalid inputs)
- [ ] CLAUDE.md reflects new architecture
- [ ] ADDING_NEW_STRATEGY.md guide complete

---

## Documentation Standards

### Markdown Style

1. **Clear headings**: Use proper hierarchy (##, ###, ####)
2. **Code blocks**: Use triple backticks with language tags
3. **Tables**: Use for structured data
4. **Examples**: Include concrete examples
5. **Links**: Use relative paths for internal docs

### Code Examples

1. **Complete**: Show full context, not snippets
2. **Correct**: Verify examples actually work
3. **Commented**: Explain non-obvious parts
4. **Formatted**: Use consistent indentation

### Writing Style

1. **Imperative**: Use command voice ("Create...", "Update...")
2. **Clear**: Avoid jargon and ambiguity
3. **Concise**: Respect reader's time
4. **Accurate**: Test all instructions

---

## File Reference Guide

### Test Files

- `tests/test_naming_consistency.py` - NEW naming consistency tests
- `tests/test_regression_s01.py` - S01 regression tests (UPDATE)
- `tests/test_optuna_engine.py` - Optuna engine tests (UPDATE)
- `tests/test_export.py` - CSV export tests (UPDATE)
- `tests/REGRESSION_TEST_REPORT.md` - NEW test report

### Documentation Files

- `CLAUDE.md` - Project guidelines for Claude Code (UPDATE)
- `docs/PROJECT_TARGET_ARCHITECTURE.md` - Architecture docs (UPDATE)
- `docs/ADDING_NEW_STRATEGY.md` - NEW developer guide
- `README.md` - Project README (UPDATE)

### Strategy Config Files

- `src/strategies/s01_trailing_ma/config.json` - Verify no feature flags
- `src/strategies/s04_stochrsi/config.json` - Verify no feature flags

---

## Success Criteria

After completing Phase 9-5-4, verify:

- [ ] **All test fixtures use camelCase**
- [ ] **test_naming_consistency.py created and passing**
- [ ] **CLAUDE.md updated** with naming conventions
- [ ] **PROJECT_TARGET_ARCHITECTURE.md updated**
- [ ] **ADDING_NEW_STRATEGY.md created**
- [ ] **README.md updated**
- [ ] **All unit tests pass**
- [ ] **All integration tests pass**
- [ ] **S01 end-to-end workflow verified**
- [ ] **S04 end-to-end workflow verified**
- [ ] **Browser testing complete**
- [ ] **Performance regression test complete**
- [ ] **Regression test report created**
- [ ] **No warnings or errors** in any test

---

## Overall Phase 9-5 Success

After completing **all phases** (9-5-1, 9-5-2, 9-5-3, 9-5-4):

- [ ] **camelCase throughout**: Parameters flow unchanged Pine → JSON → Python → CSV
- [ ] **Generic core**: No hardcoded S01/S04 knowledge in core modules
- [ ] **Config-driven**: Backend and frontend render from config.json
- [ ] **Hybrid architecture**: Typed strategies + generic core
- [ ] **No conversions**: No snake_case ↔ camelCase translation layers
- [ ] **Extensible**: Adding S05 requires only config.json + strategy.py
- [ ] **Tested**: Comprehensive test coverage prevents regression
- [ ] **Documented**: Clear guides for maintenance and extension
- [ ] **Verified**: End-to-end testing confirms everything works

---

## Git Commits

**Commit strategy for Phase 9-5-4**:

```bash
# 1. Test updates
git add tests/
git commit -m "[Phase 9-5-4] Update test fixtures to use camelCase parameters"

# 2. New tests
git add tests/test_naming_consistency.py
git commit -m "[Phase 9-5-4] Add naming consistency tests"

# 3. Documentation
git add CLAUDE.md docs/PROJECT_TARGET_ARCHITECTURE.md docs/ADDING_NEW_STRATEGY.md
git commit -m "[Phase 9-5-4] Update documentation with new architecture"

# 4. Test report
git add tests/REGRESSION_TEST_REPORT.md
git commit -m "[Phase 9-5-4] Add regression test report"

# 5. Final verification
git add .
git commit -m "[Phase 9-5-4] Final Phase 9-5 refactoring complete"
```

---

## Questions or Issues

If you encounter ambiguity or issues:

1. **Run tests incrementally** - Verify each change
2. **Check console output** - Look for warnings/errors
3. **Compare with working baseline** - Use git diff
4. **Document findings** - Add to regression report

---

**END OF PHASE 9-5-4 PROMPT**

This completes the Phase 9-5 refactoring series. The system is now fully generic, config-driven, and ready for future strategy additions without core module changes.
