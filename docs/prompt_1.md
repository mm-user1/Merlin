# Phase 1: Core Extraction to src/core/

**Migration Phase:** 1 of 9
**Complexity:** 🟢 LOW
**Risk:** 🟢 LOW
**Estimated Effort:** 2-3 hours
**Priority:** 🟢 SAFE - PURE REORGANIZATION

---

## Context and Background

### Project Overview

You are working on **S01 Trailing MA v26 - TrailingMA Ultralight**, a cryptocurrency/forex trading strategy backtesting and optimization platform. The project provides both a web interface (Flask SPA) and CLI tools to run single backtests or optimize across thousands of parameter combinations using Bayesian optimization (Optuna).

### Current State

The project has successfully completed:
- ✅ **Phase -1: Test Infrastructure Setup** - pytest configured, 21 tests passing
- ✅ **Phase 0: Regression Baseline for S01** - Comprehensive baseline established with 93 trades

All **21 tests are passing** (9 sanity tests + 12 regression tests), and the regression baseline exactly matches the production UI results:
- Net Profit: 230.75%
- Max Drawdown: 20.03%
- Total Trades: 93

### Current Directory Structure

```
src/
├── server.py                    # Flask HTTP API
├── index.html                   # Monolithic SPA (192KB)
├── backtest_engine.py          # Main backtest engine (NOT in core/)
├── optuna_engine.py            # Optuna optimizer (NOT in core/)
├── walkforward_engine.py       # WFA engine (NOT in core/)
├── optimizer_engine.py         # Grid Search (to be removed in Phase 3)
├── run_backtest.py             # CLI wrapper
└── strategies/
    ├── base.py
    └── s01_trailing_ma/
        ├── strategy.py
        └── config.json
```

**Problem:** The three main engines (backtest, optuna, walkforward) are currently scattered in the root `src/` directory alongside UI and CLI files. This makes the architecture unclear and violates separation of concerns.

### Target Architecture (After Phase 1)

```
src/
├── core/                        # NEW: Core engines directory
│   ├── __init__.py             # NEW: Core package init
│   ├── backtest_engine.py      # MOVED from src/
│   ├── optuna_engine.py        # MOVED from src/
│   └── walkforward_engine.py   # MOVED from src/
├── ui/                          # (Phase 8 - not yet)
├── strategies/
│   ├── base.py
│   └── s01_trailing_ma/
│       ├── strategy.py
│       └── config.json
├── server.py                    # Will update imports
├── run_backtest.py              # Will update imports
├── optimizer_engine.py          # Keep for now (Phase 3 will remove)
└── index.html                   # Keep for now (Phase 8 will move)
```

---

## Objective

**Goal:** Create explicit `src/core/` directory and move all engines there WITHOUT changing their internal logic. This is a pure physical reorganization that will:

1. Make the architecture explicit and clear
2. Separate core business logic from interface layers
3. Prepare for subsequent phases (metrics, indicators, export)
4. Maintain 100% behavioral compatibility

**Critical Constraint:** This is a **zero-behavior-change** refactoring. All 21 tests MUST pass after completion. The regression baseline MUST remain identical.

---

## Architecture Principles (Reference)

### Data Structure Ownership

Following the principle **"structures live where they're populated"**:

- **TradeRecord, StrategyResult** → `backtest_engine.py` (populated during simulation)
- **BasicMetrics, AdvancedMetrics** → `metrics.py` (future Phase 4)
- **OptimizationResult, OptunaConfig** → `optuna_engine.py` (created during optimization)
- **WFAMetrics** → `metrics.py` (future Phase 4)
- **StrategyParams** → `strategies/<strategy_name>/strategy.py` (each strategy owns params)

**Note:** In Phase 1, we're just moving files. Data structure locations remain unchanged.

### No Separate types.py

Structures are imported directly from their "home" modules. For Phase 1, this means:
- `TradeRecord` and `StrategyResult` will move with `backtest_engine.py` to `core/`
- Import paths will update from `from backtest_engine import ...` to `from core.backtest_engine import ...`

---

## Detailed Step-by-Step Instructions

### Step 1: Create Core Directory Structure (5 minutes)

**Action:** Create the `src/core/` directory and initialize it as a Python package.

```bash
# Navigate to project root
cd /path/to/S_01_v26-TrailingMA-Ultralight

# Create core directory
mkdir -p src/core

# Create __init__.py to make it a package
touch src/core/__init__.py
```

**Verify:**
```bash
ls -la src/core/
# Should show:
# - __init__.py
```

**Populate `src/core/__init__.py`:**

```python
"""
Core engines for the S01 TrailingMA backtesting and optimization platform.

This package contains the three main engines:
- backtest_engine: Single backtest execution
- optuna_engine: Bayesian optimization using Optuna
- walkforward_engine: Walk-Forward Analysis orchestrator

These engines are the heart of the platform and should be imported
by interface layers (UI, CLI) but should not depend on them.
"""

__version__ = "2.0.0"  # Architecture migration version

# Expose main engines at package level for convenience
from .backtest_engine import (
    TradeRecord,
    StrategyResult,
    StrategyParams,
    run_strategy,
    load_data,
    prepare_dataset_with_warmup,
)

from .optuna_engine import (
    run_optuna_optimization,
    OptimizationResult,
)

from .walkforward_engine import (
    run_walkforward,
)

__all__ = [
    # backtest_engine exports
    "TradeRecord",
    "StrategyResult",
    "StrategyParams",
    "run_strategy",
    "load_data",
    "prepare_dataset_with_warmup",

    # optuna_engine exports
    "run_optuna_optimization",
    "OptimizationResult",

    # walkforward_engine exports
    "run_walkforward",
]
```

**Rationale:** The `__init__.py` file:
1. Makes `core/` a proper Python package
2. Documents the purpose of the core layer
3. Exposes commonly-used functions/classes at package level
4. Allows both `from core.backtest_engine import ...` and `from core import ...` imports

---

### Step 2: Move Engine Files (10 minutes)

**Action:** Move the three main engine files to `src/core/` directory.

```bash
# Move engines to core/
mv src/backtest_engine.py src/core/
mv src/optuna_engine.py src/core/
mv src/walkforward_engine.py src/core/
```

**Verify:**
```bash
ls -la src/core/
# Should show:
# - __init__.py
# - backtest_engine.py
# - optuna_engine.py
# - walkforward_engine.py

ls -la src/*.py
# Should NOT show the three engines anymore
# Should still show:
# - server.py
# - run_backtest.py
# - optimizer_engine.py (Grid Search - will be removed in Phase 3)
```

**Important:** Do NOT modify the content of the engine files yet. This is purely a file move operation.

---

### Step 3: Update Imports in Engine Files (30-45 minutes)

**Action:** Update internal imports within the three engine files to reflect their new location.

#### 3.1: Update `src/core/backtest_engine.py`

**Current imports (no changes needed):**
```python
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import IO, Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from backtesting import _stats
```

**Status:** ✅ No changes needed - `backtest_engine.py` doesn't import the other engines

#### 3.2: Update `src/core/optuna_engine.py`

**Search for imports from other engines:**

```bash
grep -n "from backtest_engine import" src/core/optuna_engine.py
grep -n "from optimizer_engine import" src/core/optuna_engine.py
grep -n "import backtest_engine" src/core/optuna_engine.py
```

**Expected findings:**
- Imports from `backtest_engine` (needs update to `core.backtest_engine`)
- Imports from `optimizer_engine` (needs update to `../optimizer_engine` or absolute import)

**Update pattern:**

**BEFORE:**
```python
from backtest_engine import (
    TradeRecord,
    StrategyResult,
    StrategyParams,
    run_strategy,
    load_data,
)
```

**AFTER:**
```python
from core.backtest_engine import (
    TradeRecord,
    StrategyResult,
    StrategyParams,
    run_strategy,
    load_data,
)
```

**For optimizer_engine imports:**

**BEFORE:**
```python
from optimizer_engine import (
    OptimizationResult,
    DEFAULT_SCORE_CONFIG,
    PARAMETER_MAP,
    calculate_score,
)
```

**AFTER (Option 1 - Absolute import):**
```python
from optimizer_engine import (
    OptimizationResult,
    DEFAULT_SCORE_CONFIG,
    PARAMETER_MAP,
    calculate_score,
)
```

**AFTER (Option 2 - Relative import from parent):**
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from optimizer_engine import (
    OptimizationResult,
    DEFAULT_SCORE_CONFIG,
    PARAMETER_MAP,
    calculate_score,
)
```

**Recommended:** Use **Option 1** (absolute import). Since `optimizer_engine.py` is still in `src/` and `src/` is in the Python path, absolute imports will work. This will be cleaned up in Phase 3 when Grid Search is removed.

#### 3.3: Update `src/core/walkforward_engine.py`

**Search for imports:**

```bash
grep -n "from backtest_engine import" src/core/walkforward_engine.py
grep -n "from optuna_engine import" src/core/walkforward_engine.py
grep -n "from optimizer_engine import" src/core/walkforward_engine.py
```

**Update pattern:**

**BEFORE:**
```python
from backtest_engine import load_data, prepare_dataset_with_warmup, StrategyParams
from optuna_engine import run_optuna_optimization
from optimizer_engine import OptimizationResult
```

**AFTER:**
```python
from core.backtest_engine import load_data, prepare_dataset_with_warmup, StrategyParams
from core.optuna_engine import run_optuna_optimization
from optimizer_engine import OptimizationResult  # Grid Search - will be removed in Phase 3
```

**Alternatively (using relative imports within core/):**
```python
from .backtest_engine import load_data, prepare_dataset_with_warmup, StrategyParams
from .optuna_engine import run_optuna_optimization
from optimizer_engine import OptimizationResult  # Grid Search
```

**Recommended:** Use **relative imports** (`.backtest_engine`) for intra-core imports. This makes it clear these modules are part of the same package.

---

### Step 4: Update Imports in Interface Layer Files (45-60 minutes)

**Action:** Update all files that import from the engines to use the new `core.` prefix.

#### 4.1: Update `src/server.py`

**Search for engine imports:**

```bash
grep -n "from backtest_engine import" src/server.py
grep -n "from optuna_engine import" src/server.py
grep -n "from walkforward_engine import" src/server.py
```

**Update pattern:**

**BEFORE:**
```python
from backtest_engine import (
    load_data,
    prepare_dataset_with_warmup,
    StrategyParams,
    run_strategy,
    TradeRecord,
)
from optuna_engine import run_optuna_optimization
from walkforward_engine import run_walkforward
```

**AFTER:**
```python
from core.backtest_engine import (
    load_data,
    prepare_dataset_with_warmup,
    StrategyParams,
    run_strategy,
    TradeRecord,
)
from core.optuna_engine import run_optuna_optimization
from core.walkforward_engine import run_walkforward
```

**Alternatively (using package-level imports):**
```python
from core import (
    TradeRecord,
    StrategyResult,
    StrategyParams,
    run_strategy,
    load_data,
    prepare_dataset_with_warmup,
    run_optuna_optimization,
    run_walkforward,
)
```

**Recommended:** Use explicit module imports (`from core.backtest_engine import ...`) for clarity.

#### 4.2: Update `src/run_backtest.py`

**Search and update:**

```bash
grep -n "from backtest_engine import" src/run_backtest.py
```

**Update pattern:**

**BEFORE:**
```python
from backtest_engine import (
    load_data,
    prepare_dataset_with_warmup,
    StrategyParams,
    run_strategy,
)
```

**AFTER:**
```python
from core.backtest_engine import (
    load_data,
    prepare_dataset_with_warmup,
    StrategyParams,
    run_strategy,
)
```

#### 4.3: Update Strategy Files

**Check if strategies import engines:**

```bash
grep -r "from backtest_engine import" src/strategies/
grep -r "from optuna_engine import" src/strategies/
```

**Update pattern (if found):**

**BEFORE:**
```python
from backtest_engine import StrategyResult, TradeRecord
```

**AFTER:**
```python
from core.backtest_engine import StrategyResult, TradeRecord
```

**Note:** S01 strategy typically imports these through relative imports or from base strategy. Verify each case.

#### 4.4: Update Test Files

**Critical:** Test files MUST be updated to use new import paths.

**Update `tools/generate_baseline_s01.py`:**

```bash
grep -n "from backtest_engine import" tools/generate_baseline_s01.py
```

**BEFORE:**
```python
from backtest_engine import (
    StrategyParams,
    run_strategy,
    load_data,
    prepare_dataset_with_warmup,
)
```

**AFTER:**
```python
from core.backtest_engine import (
    StrategyParams,
    run_strategy,
    load_data,
    prepare_dataset_with_warmup,
)
```

**Update `tests/test_regression_s01.py`:**

```bash
grep -n "from backtest_engine import" tests/test_regression_s01.py
```

**BEFORE:**
```python
from backtest_engine import (
    StrategyParams,
    run_strategy,
    TradeRecord,
    load_data,
    prepare_dataset_with_warmup,
)
```

**AFTER:**
```python
from core.backtest_engine import (
    StrategyParams,
    run_strategy,
    TradeRecord,
    load_data,
    prepare_dataset_with_warmup,
)
```

**Update `tests/test_sanity.py`:**

```bash
grep -n "from backtest_engine import" tests/test_sanity.py
```

**BEFORE:**
```python
from backtest_engine import StrategyResult
```

**AFTER:**
```python
from core.backtest_engine import StrategyResult
```

---

### Step 5: Update sys.path or PYTHONPATH (if needed)

**Check current Python path setup:**

Most projects add `src/` to the Python path. Verify this is configured:

**Option 1: pytest.ini configuration**

Check `pytest.ini` for `pythonpath` setting:
```ini
[pytest]
pythonpath = src
```

**Option 2: Environment variable**

Check if `PYTHONPATH` is set:
```bash
echo $PYTHONPATH
```

**Option 3: Programmatic path modification**

Some scripts may add to `sys.path`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
```

**Action:** Ensure `src/` remains in the Python path. The new `core/` package structure should work automatically once `src/` is in the path.

**Verify:**
```bash
cd /path/to/project
python3 -c "from core.backtest_engine import TradeRecord; print('SUCCESS')"
# Should print: SUCCESS
```

---

### Step 6: Comprehensive Testing (30-45 minutes)

**Critical:** This is a zero-behavior-change refactoring. ALL tests must pass.

#### 6.1: Run Sanity Tests

```bash
pytest tests/test_sanity.py -v
```

**Expected result:** 9/9 tests passing

**Watch for:**
- Import errors (most common issue)
- Module not found errors
- Circular import issues

#### 6.2: Run Regression Tests

```bash
pytest tests/test_regression_s01.py -v -m regression
```

**Expected result:** 12/12 tests passing

**Critical validations:**
- ✅ Net profit matches baseline (230.75% ± 0.01%)
- ✅ Max drawdown matches baseline (20.03% ± 0.01%)
- ✅ Total trades matches baseline (93 exact)
- ✅ All trade entry/exit times match exactly
- ✅ All trade PnL values match (±0.0001 tolerance)

#### 6.3: Run Full Test Suite

```bash
pytest tests/ -v
```

**Expected result:** 21/21 tests passing

#### 6.4: Manual Smoke Test - CLI

**Test the CLI tool:**

```bash
cd src
python run_backtest.py --csv ../data/raw/OKX_LINKUSDT.P,\ 15\ 2025.05.01-2025.11.20.csv
```

**Expected:** No import errors, backtest runs successfully

#### 6.5: Manual Smoke Test - UI

**Start the server:**

```bash
cd src
python server.py
```

**Expected:** Server starts without import errors

**Test in browser:**
1. Navigate to `http://localhost:8000` (or configured port)
2. Select S01 strategy
3. Click "Run Backtest"
4. Verify results display correctly

**Expected results (should match baseline):**
- Net Profit: ~230.75%
- Max Drawdown: ~20.03%
- Total Trades: 93

#### 6.6: Test Optuna Optimization

**Via UI:**
1. Select Optuna optimization mode
2. Set n_trials = 10 (small for quick test)
3. Enable 2-3 parameters for optimization
4. Click "Optimize"

**Expected:** Optimization completes without errors

**Via CLI (if supported):**
```bash
# Create test script
python -c "
from core.optuna_engine import run_optuna_optimization
from core.backtest_engine import load_data
# ... test optimization
"
```

---

### Step 7: Verify No Broken Imports (Code Quality Check)

**Action:** Search for any remaining old-style imports that weren't caught.

#### 7.1: Search for old import patterns

```bash
# Search entire src/ directory
grep -r "from backtest_engine import" src/
grep -r "from optuna_engine import" src/
grep -r "from walkforward_engine import" src/

# Should return NOTHING (or only from core/ itself)
```

#### 7.2: Search tests and tools

```bash
grep -r "from backtest_engine import" tests/
grep -r "from backtest_engine import" tools/

# Should return NOTHING
```

#### 7.3: Check for implicit imports

```bash
# Search for 'import backtest_engine' (without from)
grep -r "import backtest_engine" src/
grep -r "import optuna_engine" src/
grep -r "import walkforward_engine" src/

# If found, update to:
# import core.backtest_engine as backtest_engine
```

---

## Validation Checklist

Before considering Phase 1 complete, verify ALL of the following:

### File Structure
- [ ] `src/core/` directory exists
- [ ] `src/core/__init__.py` exists and is properly populated
- [ ] `src/core/backtest_engine.py` exists (moved from src/)
- [ ] `src/core/optuna_engine.py` exists (moved from src/)
- [ ] `src/core/walkforward_engine.py` exists (moved from src/)
- [ ] `src/backtest_engine.py` does NOT exist (moved to core/)
- [ ] `src/optuna_engine.py` does NOT exist (moved to core/)
- [ ] `src/walkforward_engine.py` does NOT exist (moved to core/)

### Import Updates
- [ ] `src/core/backtest_engine.py` imports updated (if needed)
- [ ] `src/core/optuna_engine.py` imports updated to `core.backtest_engine`
- [ ] `src/core/walkforward_engine.py` imports updated to `core.` or relative imports
- [ ] `src/server.py` imports updated to `core.backtest_engine`, etc.
- [ ] `src/run_backtest.py` imports updated to `core.`
- [ ] `src/strategies/**/*.py` imports updated (if they import engines)
- [ ] `tools/generate_baseline_s01.py` imports updated to `core.`
- [ ] `tests/test_regression_s01.py` imports updated to `core.`
- [ ] `tests/test_sanity.py` imports updated to `core.`

### Testing
- [ ] Sanity tests passing: 9/9
- [ ] Regression tests passing: 12/12
- [ ] Full test suite passing: 21/21
- [ ] CLI smoke test passed (backtest runs)
- [ ] UI smoke test passed (server starts, backtest works)
- [ ] Optuna optimization tested (works via UI)

### Code Quality
- [ ] No old import patterns remain (`grep` searches return nothing)
- [ ] No import errors in any file
- [ ] No circular import issues
- [ ] Python path configured correctly

### Behavioral Validation
- [ ] Net profit matches baseline: 230.75% (±0.01%)
- [ ] Max drawdown matches baseline: 20.03% (±0.01%)
- [ ] Total trades matches baseline: 93 (exact)
- [ ] Trade-by-trade comparison matches baseline

### Documentation
- [ ] `src/core/__init__.py` has descriptive docstring
- [ ] Git commit message is descriptive

---

## Git Workflow

### Commit Strategy

```bash
# Stage changes
git add src/core/
git add src/server.py
git add src/run_backtest.py
git add src/strategies/
git add tests/
git add tools/

# Commit with descriptive message
git commit -m "Phase 1: Move engines to core/

- Created src/core/ directory structure
- Moved backtest_engine.py to core/
- Moved optuna_engine.py to core/
- Moved walkforward_engine.py to core/
- Updated all imports across codebase:
  - server.py
  - run_backtest.py
  - strategies/
  - tests/
  - tools/
- All 21 tests passing
- Regression baseline maintained (Net Profit 230.75%, Total Trades 93)

This is a pure reorganization with zero behavior changes.
Prepares for subsequent migration phases (export, metrics, indicators).
"

# Tag the phase completion
git tag phase-1-complete

# Verify commit
git log -1 --stat
git show phase-1-complete
```

---

## Common Issues and Troubleshooting

### Issue 1: ImportError: No module named 'core'

**Symptom:**
```
ImportError: No module named 'core'
```

**Cause:** Python path doesn't include `src/`

**Solution:**

**Option A - pytest.ini:**
```ini
[pytest]
pythonpath = src
```

**Option B - Environment variable:**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

**Option C - Programmatic:**
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
```

### Issue 2: ImportError: cannot import name 'X' from 'core.backtest_engine'

**Symptom:**
```
ImportError: cannot import name 'TradeRecord' from 'core.backtest_engine'
```

**Cause:** Function/class name doesn't exist or is misspelled

**Solution:**
1. Check the exported names in `core/__init__.py`
2. Verify the name exists in the source module
3. Check for typos in import statement

### Issue 3: Circular import

**Symptom:**
```
ImportError: cannot import name 'X' from partially initialized module 'core'
```

**Cause:** Circular dependency between modules

**Solution:**
1. Use relative imports within `core/` package
2. Move import statements inside functions (lazy import)
3. Restructure to remove circular dependency

### Issue 4: Tests failing after import updates

**Symptom:**
```
AssertionError: 230.752991016333 != 230.75 within 0.01 tolerance
```

**Cause:** Behavioral change introduced (should not happen in Phase 1!)

**Solution:**
1. Double-check no logic changes were made to engine files
2. Verify no typos in import updates
3. Regenerate baseline if absolutely necessary (but this indicates a problem)

### Issue 5: Server won't start

**Symptom:**
```
python server.py
# ... import errors
```

**Cause:** Missing import updates in `server.py`

**Solution:**
1. Carefully review all imports in `server.py`
2. Update to `from core.backtest_engine import ...`
3. Test import before starting server:
   ```python
   python -c "from core.backtest_engine import TradeRecord"
   ```

---

## Performance Validation

Phase 1 should have **ZERO performance impact** since we're only reorganizing files, not changing logic.

### Benchmark Test

**Before Phase 1:**
```bash
time python src/run_backtest.py --csv data/...
# Record execution time
```

**After Phase 1:**
```bash
time python src/run_backtest.py --csv data/...
# Should be identical (±1%)
```

**Expected:** No performance degradation

---

## Success Criteria Summary

Phase 1 is complete when:

1. ✅ **All files moved** - Three engines in `src/core/`
2. ✅ **All imports updated** - No import errors anywhere
3. ✅ **All tests passing** - 21/21 tests green
4. ✅ **Regression baseline maintained** - Bit-exact match
5. ✅ **Manual tests passing** - CLI, UI, Optuna all work
6. ✅ **No behavior changes** - Results identical to before
7. ✅ **Clean git commit** - With tag `phase-1-complete`
8. ✅ **Documentation updated** - `core/__init__.py` documented

---

## Next Steps After Phase 1

Once Phase 1 is complete and validated, proceed to:

**Phase 2: Export Extraction to export.py**
- Complexity: 🟡 MEDIUM
- Risk: 🟢 LOW
- Estimated Effort: 4-6 hours

Phase 2 will centralize all export logic (CSV formatting, TradingView export, Optuna results) in a single `src/core/export.py` module.

---

## Reference: Import Pattern Examples

### Before Phase 1 (OLD - Don't use)

```python
# server.py
from backtest_engine import run_strategy, StrategyParams
from optuna_engine import run_optuna_optimization

# tests/test_regression_s01.py
from backtest_engine import TradeRecord, load_data
```

### After Phase 1 (NEW - Correct)

```python
# server.py
from core.backtest_engine import run_strategy, StrategyParams
from core.optuna_engine import run_optuna_optimization

# tests/test_regression_s01.py
from core.backtest_engine import TradeRecord, load_data
```

### Alternative (package-level import)

```python
# server.py
from core import run_strategy, StrategyParams, run_optuna_optimization

# tests/test_regression_s01.py
from core import TradeRecord, load_data
```

---

## Quick Reference Commands

```bash
# Create core directory
mkdir -p src/core && touch src/core/__init__.py

# Move engines
mv src/backtest_engine.py src/core/
mv src/optuna_engine.py src/core/
mv src/walkforward_engine.py src/core/

# Search for old imports (should return nothing after updates)
grep -r "from backtest_engine import" src/ tests/ tools/
grep -r "from optuna_engine import" src/ tests/ tools/

# Test imports
python3 -c "from core.backtest_engine import TradeRecord; print('OK')"

# Run tests
pytest tests/test_sanity.py -v           # 9 tests
pytest tests/test_regression_s01.py -v    # 12 tests
pytest tests/ -v                          # 21 tests

# Smoke test CLI
cd src && python run_backtest.py --csv ../data/raw/OKX_LINKUSDT.P,\ 15\ 2025.05.01-2025.11.20.csv

# Smoke test UI
cd src && python server.py
# Visit http://localhost:8000

# Commit
git add -A
git commit -m "Phase 1: Move engines to core/"
git tag phase-1-complete
```

---

**End of Phase 1 Prompt**
**Total Length:** ~15.3 KB
**Target Audience:** GPT 5.1 Codex
**Expected Execution Time:** 2-3 hours
**Risk Level:** 🟢 LOW (pure reorganization)
