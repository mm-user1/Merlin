# TODO: Refactor Parameter Mapping to Support Multiple Strategies

## Priority: HIGH (before adding 2nd strategy)

## Problem Statement

**Current Issue:**
The optimizer engines (`optimizer_engine.py` and `optuna_engine.py`) currently have **hardcoded parameter mappings** that are specific to the S01 Trailing MA strategy. This violates the modular strategy architecture and creates technical debt.

### Hardcoded Mappings (Lines 165-181 in optimizer_engine.py):
```python
INTERNAL_TO_FRONTEND_MAP.update({
    # Strategy-specific parameters (S01 only!)
    "ma_type": "maType",
    "trail_ma_long_type": "trailLongType",
    "trail_ma_short_type": "trailShortType",

    # Global parameters (more universal but still hardcoded)
    "risk_per_trade_pct": "riskPerTrade",
    "contract_size": "contractSize",
    "commission_rate": "commissionRate",
    "atr_period": "atrPeriod",
})
```

### Why This Is a Problem:

1. **Breaks Modularity:**
   - `optimizer_engine.py` is tightly coupled to S01 strategy parameters
   - MA types (`ma_type`, `trail_ma_long_type`, `trail_ma_short_type`) are S01-specific
   - Other strategies may not use MA at all (e.g., RSI-based, Bollinger Band strategies)

2. **Violates Open/Closed Principle:**
   - Adding a new strategy requires **modifying** core optimizer code
   - Should be: open for extension, closed for modification

3. **No Single Source of Truth:**
   - Parameters defined in strategy's `config.json`
   - Mapping duplicated in `optimizer_engine.py`
   - Changes require updates in multiple places

4. **Scalability Issues:**
   - With 10 strategies × 20 parameters each = 200 hardcoded mappings
   - Unmaintainable and error-prone

## Proposed Solution: Auto-Generation from config.json

### Core Concept:
**Each strategy automatically generates its parameter mapping from its config.json**, eliminating all hardcoded mappings in the optimizer.

### Architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│ Strategy config.json                                             │
│ {                                                                │
│   "parameters": {                                                │
│     "maType": {...},        ← Frontend names (camelCase)        │
│     "maLength": {...},                                           │
│     "trailLongType": {...}                                       │
│   }                                                              │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Auto-generate mapping
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ Strategy class provides mapping:                                 │
│                                                                  │
│ get_parameter_mapping() → {                                      │
│   "ma_type": "maType",          ← Internal → Frontend           │
│   "ma_length": "maLength",                                       │
│   "trail_ma_long_type": "trailLongType"                         │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Optimizer uses this
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ _run_single_combination()                                        │
│                                                                  │
│ mapping = strategy_class.get_parameter_mapping()                │
│ strategy_payload = {mapping.get(k, k): v for k, v in ...}      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Add Helper Function (strategies/base.py)

Create a utility to convert camelCase → snake_case:

```python
def camelcase_to_snake_case(name: str) -> str:
    """
    Convert camelCase to snake_case.

    Examples:
        maType → ma_type
        closeCountLong → close_count_long
        trailLongType → trail_ma_long_type  (if needed)

    Args:
        name: Parameter name in camelCase

    Returns:
        Parameter name in snake_case
    """
    import re

    # Insert underscore before uppercase letters
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    # Handle sequences of uppercase letters
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()
```

**Test cases:**
```python
assert camelcase_to_snake_case("maType") == "ma_type"
assert camelcase_to_snake_case("maLength") == "ma_length"
assert camelcase_to_snake_case("closeCountLong") == "close_count_long"
assert camelcase_to_snake_case("trailLongType") == "trail_long_type"
assert camelcase_to_snake_case("stopLongX") == "stop_long_x"
assert camelcase_to_snake_case("atrPeriod") == "atr_period"
```

### Phase 2: Add Method to BaseStrategy (strategies/base.py)

```python
class BaseStrategy:
    """Base class for all trading strategies."""

    STRATEGY_ID = "base"
    STRATEGY_NAME = "Base Strategy"
    STRATEGY_VERSION = "v0"

    @classmethod
    def get_parameter_mapping(cls) -> Dict[str, str]:
        """
        Auto-generate internal→frontend parameter mapping from config.json.

        This method reads the strategy's config.json and creates a mapping
        from internal parameter names (snake_case) to frontend names (camelCase).

        The optimizer uses this mapping to convert parameters before passing
        them to the strategy's run() method.

        Returns:
            Dictionary mapping internal_name → frontend_name
            Example: {"ma_type": "maType", "ma_length": "maLength"}
        """
        from strategies import get_strategy_config

        try:
            config = get_strategy_config(cls.STRATEGY_ID)
        except ValueError:
            # Strategy not registered or config not found
            # Return empty mapping (strategy will handle parameters itself)
            return {}

        mapping: Dict[str, str] = {}
        parameters = config.get("parameters", {})

        for frontend_name in parameters.keys():
            internal_name = camelcase_to_snake_case(frontend_name)
            mapping[internal_name] = frontend_name

        return mapping

    @staticmethod
    def calculate_indicators(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, pd.Series]:
        """Calculate technical indicators (optional, for caching)."""
        return {}

    @staticmethod
    def run(
        df: pd.DataFrame,
        params: Dict[str, Any],
        trade_start_idx: int = 0
    ) -> StrategyResult:
        """Execute the trading strategy."""
        raise NotImplementedError("Strategy must implement run() method")
```

### Phase 3: Update Optimizer Engine (optimizer_engine.py)

**3A. Add Global Parameters Mapping**

Separate truly global parameters from strategy-specific ones:

```python
# Global configuration parameters (universal across all strategies)
# These are passed from OptimizationConfig and not defined in strategy config.json
GLOBAL_CONFIG_PARAMS: Dict[str, str] = {
    "risk_per_trade_pct": "riskPerTrade",
    "contract_size": "contractSize",
    "commission_rate": "commissionRate",
    "atr_period": "atrPeriod",
}
```

**3B. Update INTERNAL_TO_FRONTEND_MAP Construction**

Remove hardcoded strategy-specific mappings:

```python
# Reverse mapping: internal_name -> frontend_name
# Used to convert optimizer's internal parameter names to strategy's expected frontend names
INTERNAL_TO_FRONTEND_MAP: Dict[str, str] = {
    internal: frontend for frontend, (internal, _) in PARAMETER_MAP.items()
}

# Add global configuration parameters (universal, not strategy-specific)
INTERNAL_TO_FRONTEND_MAP.update(GLOBAL_CONFIG_PARAMS)

# NOTE: Strategy-specific parameters (like ma_type, trail_ma_long_type) are now
# obtained dynamically from each strategy's get_parameter_mapping() method.
# This eliminates hardcoded strategy dependencies in the optimizer.
```

**3C. Update _run_single_combination() Function**

Modify the conversion logic to use strategy's mapping:

```python
def _run_single_combination(args: Tuple[Dict[str, Any], pd.DataFrame, int, Any]) -> OptimizationResult:
    """
    Worker function to run a single parameter combination using strategy.run().

    Args:
        args: Tuple of (params_dict, df, trade_start_idx, strategy_class)

    Returns:
        OptimizationResult with metrics for this combination
    """

    params_dict, df, trade_start_idx, strategy_class = args

    # ... (keep existing _as_int, _as_float, _base_result functions) ...

    try:
        # Build complete parameter mapping:
        # 1. Base mapping from PARAMETER_MAP (optimizer params)
        # 2. Global config params (risk, commission, etc.)
        # 3. Strategy-specific params (from strategy's config.json)
        base_mapping = {internal: frontend for frontend, (internal, _) in PARAMETER_MAP.items()}
        complete_mapping = {**base_mapping, **GLOBAL_CONFIG_PARAMS}

        # Get strategy-specific parameter mapping
        strategy_mapping = strategy_class.get_parameter_mapping()
        complete_mapping.update(strategy_mapping)

        # Convert internal parameter names (snake_case) to frontend names (camelCase)
        strategy_payload = {
            complete_mapping.get(key, key): value
            for key, value in params_dict.items()
        }

        result = strategy_class.run(df, strategy_payload, trade_start_idx)
        opt_result = _base_result()
        opt_result.net_profit_pct = result.net_profit_pct
        opt_result.max_drawdown_pct = result.max_drawdown_pct
        opt_result.total_trades = result.total_trades
        opt_result.sharpe_ratio = result.sharpe_ratio
        opt_result.profit_factor = result.profit_factor
        opt_result.romad = result.romad
        opt_result.ulcer_index = result.ulcer_index
        opt_result.recovery_factor = result.recovery_factor
        opt_result.consistency_score = result.consistency_score
        return opt_result
    except Exception:
        return _base_result()
```

### Phase 4: Verify No Breaking Changes

**Critical:** The refactoring should be **100% backward compatible** with S01 strategy.

**Test checklist:**
1. ✓ S01 strategy still works with Grid optimizer
2. ✓ S01 strategy still works with Optuna optimizer
3. ✓ Parameter conversion produces identical results to before
4. ✓ All 26 parameters correctly mapped (verify with test)

---

## Testing Strategy

### Test 1: Verify camelcase_to_snake_case()

Create `test_parameter_mapping.py`:

```python
#!/usr/bin/env python3
"""Test parameter mapping auto-generation."""

import sys
sys.path.insert(0, './src')

from strategies.base import camelcase_to_snake_case

def test_conversion():
    """Test camelCase to snake_case conversion."""
    test_cases = [
        ("maType", "ma_type"),
        ("maLength", "ma_length"),
        ("closeCountLong", "close_count_long"),
        ("closeCountShort", "close_count_short"),
        ("stopLongX", "stop_long_x"),
        ("stopLongRR", "stop_long_rr"),
        ("stopLongLP", "stop_long_lp"),
        ("trailLongType", "trail_long_type"),
        ("trailLongLength", "trail_long_length"),
        ("trailLongOffset", "trail_long_offset"),
        ("riskPerTrade", "risk_per_trade"),
        ("contractSize", "contract_size"),
        ("commissionRate", "commission_rate"),
        ("atrPeriod", "atr_period"),
    ]

    print("Testing camelCase → snake_case conversion:")
    print("=" * 60)

    for camel, expected_snake in test_cases:
        result = camelcase_to_snake_case(camel)
        status = "✓" if result == expected_snake else "✗"
        print(f"{status} {camel:20s} → {result:25s} (expected: {expected_snake})")
        assert result == expected_snake, f"Failed: {camel} → {result}, expected {expected_snake}"

    print("=" * 60)
    print("✅ All conversion tests passed!")

if __name__ == "__main__":
    test_conversion()
```

### Test 2: Verify S01 Strategy Mapping

```python
def test_s01_mapping():
    """Test that S01 strategy generates correct mapping."""
    from strategies import get_strategy

    strategy_class = get_strategy("s01_trailing_ma")
    mapping = strategy_class.get_parameter_mapping()

    # Expected mappings from S01 config.json
    expected = {
        "ma_type": "maType",
        "ma_length": "maLength",
        "close_count_long": "closeCountLong",
        "close_count_short": "closeCountShort",
        "stop_long_x": "stopLongX",
        "trail_long_type": "trailLongType",
        "trail_long_length": "trailLongLength",
        "trail_long_offset": "trailLongOffset",
        # ... add all parameters from config.json
    }

    print("\nTesting S01 strategy mapping:")
    print("=" * 60)

    for internal, frontend in expected.items():
        if internal in mapping:
            actual = mapping[internal]
            status = "✓" if actual == frontend else "✗"
            print(f"{status} {internal:25s} → {actual}")
            assert actual == frontend
        else:
            print(f"✗ Missing mapping for {internal}")
            assert False, f"Missing mapping for {internal}"

    print("=" * 60)
    print(f"✅ S01 strategy mapping correct ({len(mapping)} parameters)")
```

### Test 3: Integration Test with Optimizer

```python
def test_optimizer_integration():
    """Test that optimizer correctly uses strategy mapping."""
    # This should be run as part of existing optimization tests
    # Verify that:
    # 1. Parameters are correctly converted
    # 2. Strategy receives expected parameter names
    # 3. Results are identical to pre-refactor version
    pass
```

---

## Migration Checklist

### Pre-Implementation:
- [ ] Read and understand current parameter flow (optimizer → strategy)
- [ ] Review S01 strategy's config.json (all 26+ parameters)
- [ ] Understand PARAMETER_MAP and its usage

### Implementation:
- [ ] Add `camelcase_to_snake_case()` to `strategies/base.py`
- [ ] Add `get_parameter_mapping()` to `BaseStrategy` class
- [ ] Create `GLOBAL_CONFIG_PARAMS` in `optimizer_engine.py`
- [ ] Remove hardcoded MA type mappings from `INTERNAL_TO_FRONTEND_MAP`
- [ ] Update `_run_single_combination()` to use strategy mapping
- [ ] Add comprehensive docstrings explaining the new approach

### Testing:
- [ ] Run `test_parameter_mapping.py` (all conversions pass)
- [ ] Run `test_s01_mapping.py` (S01 mapping correct)
- [ ] Test Grid optimizer with S01 (results identical to before)
- [ ] Test Optuna optimizer with S01 (results identical to before)
- [ ] Verify all 26 parameters correctly converted

### Verification:
- [ ] No hardcoded strategy-specific parameters in optimizer_engine.py
- [ ] Code passes Python syntax check (`py_compile`)
- [ ] All existing tests still pass
- [ ] Documentation updated (comments explaining new architecture)

### Cleanup:
- [ ] Remove old TODO comments about hardcoded mappings
- [ ] Update OPTUNA_FIX_SUMMARY.md to mention this refactor
- [ ] Add note about strategy-agnostic architecture

---

## Expected Benefits

### After Refactoring:

1. **✅ Full Modularity:**
   - Optimizer has zero knowledge of specific strategy parameters
   - Adding new strategy = zero changes to optimizer code

2. **✅ Single Source of Truth:**
   - config.json is the only place defining parameters
   - Mapping auto-generated from config.json

3. **✅ Maintainability:**
   - No duplicated parameter definitions
   - Changes to strategy parameters require no optimizer changes

4. **✅ Scalability:**
   - Support unlimited strategies without code changes
   - Each strategy manages its own parameter contract

5. **✅ Testability:**
   - Easy to verify mapping correctness per strategy
   - Clear separation of concerns

---

## Edge Cases to Handle

### 1. Special Parameter Names

Some parameters might have irregular naming:
- `stopLongX` → `stop_long_x` (not `stop_long_xatr`)
- `stopLongRR` → `stop_long_rr` (not `stop_long_rrisk`)

**Solution:** Test conversion function with all actual parameter names from S01.

### 2. Parameters Not in config.json

Global parameters like `riskPerTrade` are in `OptimizationConfig` but not in strategy's config.json.

**Solution:** Keep `GLOBAL_CONFIG_PARAMS` separate for these universal parameters.

### 3. Backward Compatibility

Existing code might rely on hardcoded mappings.

**Solution:**
- Verify that `strategy_class.get_parameter_mapping()` returns exact same mappings as before
- Run comparison tests: old approach vs new approach (results must be identical)

### 4. Strategy Without config.json

What if a strategy doesn't have config.json?

**Solution:** `get_parameter_mapping()` returns empty dict, falls back to key passthrough.

---

## Success Criteria

The refactoring is complete when:

1. ✅ No strategy-specific parameter names in `optimizer_engine.py`
2. ✅ S01 strategy optimization produces identical results to before
3. ✅ New strategies can be added without modifying optimizer code
4. ✅ All tests pass
5. ✅ Code is well-documented with clear architecture explanations

---

## Estimated Effort

- **Implementation:** 2-3 hours
- **Testing:** 1-2 hours
- **Documentation:** 30 minutes
- **Total:** 3.5-5.5 hours

---

## References

- Current implementation: `src/optimizer_engine.py` lines 165-181
- Strategy config example: `src/strategies/s01_trailing_ma/config.json`
- Strategy registry: `src/strategies/__init__.py`
- Base strategy class: `src/strategies/base.py`

---

## Notes for Implementation

- **Preserve all existing functionality** - this is a pure refactor
- **Test thoroughly** - parameter conversion is critical for correct results
- **Document well** - explain the auto-generation approach for future developers
- **Keep it simple** - avoid over-engineering, the solution should be straightforward

---

**Priority:** Implement this **before** adding a second strategy to avoid accumulating more technical debt.

**Assigned to:** Future agent/developer
**Created:** 2025-11-24
**Status:** TODO (pending)
