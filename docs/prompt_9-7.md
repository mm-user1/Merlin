# Phase 9-7: Fix Audit Issues

## Context

You are working on a cryptocurrency trading strategy backtesting platform. The codebase has undergone a major migration to a hybrid architecture (typed strategy modules + generic config-driven core). A comprehensive audit was completed in Phase 9-6.

**Key Architecture Files:**
- `docs/PROJECT_TARGET_ARCHITECTURE.md` - Target architecture description
- `docs/PROJECT_STRUCTURE.md` - Project structure
- `docs/ADDING_NEW_STRATEGY.md` - Strategy import guide
- `docs/prompt_9-6_audit_FINAL.md` - Detailed audit report

**Test Command:** `python -m pytest tests/ -v`

## Issues to Fix

There are **3 issues** identified in the audit that need to be fixed. Fix them in order.

---

## Issue #1: Broken Indicator Parity Tests (HIGH PRIORITY)

### Problem

The file `tests/test_indicators.py` contains parity tests that compare "old" implementations in `core.backtest_engine` with "new" implementations in `indicators/ma.py`. However, the MA functions (`sma`, `ema`, `wma`, `hma`, `dema`, `alma`, `kama`, `tma`, `t3`, `get_ma`) have been fully migrated to `indicators/ma.py` and removed from `backtest_engine.py`.

The tests fail with `AttributeError: module 'core.backtest_engine' has no attribute 'sma'` (and similar for other functions).

### Root Cause

During Phase 5 migration, MA functions were moved to `indicators/ma.py`. The parity tests served their purpose (verifying migration correctness) but now reference non-existent functions.

Note: The `atr` parity test passes because `atr` is still imported into `backtest_engine.py` from `indicators.volatility` (see line 6 of `src/core/backtest_engine.py`).

### Solution

**Remove the outdated parity tests** from `tests/test_indicators.py`. The parity tests have served their purpose. Keep the following test classes that test actual functionality:
- `TestMAEdgeCases` - Tests edge cases for MA functions
- `TestVolatilityParity` - Can be kept (atr is imported into backtest_engine)
- `TestAllMATypes` - Tests that all MA types work via get_ma()

**Remove these test classes:**
- `TestMAsParity` - All 3 tests reference non-existent functions
- `TestAdvancedMAsPart1` - Both tests reference non-existent functions
- `TestAdvancedMAsPart2` - All 4 tests reference non-existent functions
- `TestGetMAFacade` - References non-existent get_ma in backtest_engine

### Expected Result After Fix

All tests in `test_indicators.py` should pass. The file should contain:
- `TestMAEdgeCases` (2 tests)
- `TestVolatilityParity` (1 test)
- `TestAllMATypes` (1 test)

Total: 4 tests remaining, all passing.

---

## Issue #2: Undefined `logger` in export.py (MEDIUM PRIORITY)

### Problem

The file `src/core/export.py` uses `logger.warning()` on lines 85, 87, and 91, but `logger` is never imported or defined in the module. This will cause a `NameError` if the exception paths are triggered.

### Code Locations

```python
# Line 84-86
except Exception as exc:  # pragma: no cover - defensive fallback
    logger.warning(f"Could not load config for {strategy_id}: {exc}")
    return _get_default_metric_columns()

# Line 89-91
if not isinstance(parameters, dict):
    logger.warning(f"Invalid parameters in config for {strategy_id}")
    return _get_default_metric_columns()
```

### Solution

Add logging import at the top of `src/core/export.py` (after the other imports) and create a module-level logger:

```python
import logging

logger = logging.getLogger(__name__)
```

Add after line 22 (after `from .optuna_engine import OptimizationResult`).

### Expected Result After Fix

- The file should import logging and define logger
- No NameError when exception paths are triggered
- Existing tests should still pass

---

## Issue #3: Dead Code - export_wfa_summary() stub (LOW PRIORITY)

### Problem

The file `src/core/export.py` contains a stub function `export_wfa_summary()` at lines 224-232 that raises `NotImplementedError`. This is dead code because:

1. WFA export functionality already exists in `core/walkforward_engine.py`:
   - `export_wf_results_csv()` - Full implementation
   - `export_wfa_trades_history()` - Full implementation

2. The stub is exported in `core/__init__.py` and `__all__` in export.py but never used

### Solution

**Option A (Recommended):** Remove the stub entirely:

1. Remove `export_wfa_summary` from `src/core/export.py`:
   - Remove from `__all__` list (line 29)
   - Remove the function definition (lines 224-232)

2. Remove `export_wfa_summary` from `src/core/__init__.py`:
   - Remove from import statement (line 44)
   - Remove from `__all__` list (line 79)

### Expected Result After Fix

- `export_wfa_summary` no longer exists in codebase
- No tests should reference it (none currently do)
- Cleaner codebase with no dead stubs

---

## Verification Steps

After making all fixes, run:

```bash
cd src
python -m pytest ../tests/ -v
```

**Expected result:** All 83+ tests pass (was 83/93, should be ~83/83 after removing broken tests).

Also verify no import errors:

```bash
cd src
python -c "from core import export; from core import walkforward_engine; from indicators import ma"
```

---

## Important Guidelines

1. **Do not modify** any working functionality
2. **Do not add** new features - only fix the identified issues
3. **Do not change** parameter naming conventions (must stay camelCase)
4. **Preserve** all passing tests
5. **Run tests** after each fix to verify no regressions

## Files to Modify

1. `tests/test_indicators.py` - Remove outdated parity test classes
2. `src/core/export.py` - Add logging import, remove dead stub
3. `src/core/__init__.py` - Remove export_wfa_summary from exports

## Success Criteria

- All tests pass (`python -m pytest tests/ -v`)
- No NameError on `logger` in export.py
- No dead `export_wfa_summary` stub
- Clean imports with no errors
