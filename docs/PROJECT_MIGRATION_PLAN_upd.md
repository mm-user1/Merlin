# Migration Plan - Updated
## From Legacy S_01-Centric Architecture to Clean Core Architecture

**Version:** 2.0
**Date:** 2025-11-27
**Status:** Final - Ready for Execution
**Scope:** Step-by-step migration from current legacy architecture to target structure with 3 engines, metrics, export, and separated UI.

---

## Executive Summary

This updated plan incorporates feedback from two audit reports (claude_MIGRATION_AUDIT_REPORT_2.md and codex_migration_plan_audit_report.md) and addresses the following key adjustments:

### Key Changes from v1.4:

1. **Frontend phase moved to end** - UI separation now happens AFTER legacy cleanup (more logical flow)
2. **StrategyParams lives inside strategy.py** - Each strategy owns its parameter structure
3. **metrics.py only calculates** - Other modules consume the metrics, metrics.py doesn't orchestrate
4. **Data structures co-located with creators** - Structures live next to modules that populate them
5. **Phase reordering** - Export moved earlier (low risk), Metrics before Indicators (easier validation)
6. **Phase splitting** - Phase 2 split into 2.A (move) and 2.B (Grid removal) for risk management

### Architecture Principles:

- **Iterative migration** - Small, verifiable phases with regression tests
- **Behavior preservation** - S01 results must remain identical (bit-exact where possible)
- **Legacy co-existence** - Old code stays until new code is validated
- **Test-driven** - Every high-risk change validated by automated tests
- **Data structure ownership** - Each module owns the structures it creates and populates

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
- Priority: **preserve S01 behavior** (and later, simple strategy)
- Important changes accompanied by regression and basic unit tests
- Legacy code deleted **only after** successful validation of new implementation
- Git tags at each phase completion: `phase-X-complete`

---

## Phase -1: Test Infrastructure Setup

**Complexity:** 🟢 LOW
**Risk:** 🟢 LOW
**Estimated Effort:** 2-4 hours
**Priority:** 🔴 CRITICAL - MUST DO FIRST

### Goal

Prepare minimal but usable test infrastructure before starting serious changes.

### Steps

1. Create `tests/` folder in project root
2. Configure test execution via `pytest`:
   - Simple `pytest.ini` or config in `pyproject.toml`
   - Set test discovery patterns
   - Configure output verbosity
3. Add at least one "sanity" test to verify infrastructure works:
   - `tests/test_sanity.py` with simple assertions
   - Test basic imports: `from backtest_engine import StrategyResult`
4. Establish habit:
   - Run `pytest` before/after major migration phases
   - Use it as quick "did we break everything?" indicator

### Deliverables

- [ ] `tests/` directory created
- [ ] `pytest.ini` or `pyproject.toml` test config
- [ ] `tests/test_sanity.py` passing
- [ ] `pytest -v` command working
- [ ] CI-ready: can run tests in pipeline later

### Success Criteria

- Running `pytest -v` shows green results
- All team members (just you!) can run tests locally
- Foundation ready for regression tests

---

## Phase 0: Regression Baseline for S01

**Complexity:** 🟡 MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 4-6 hours
**Priority:** 🔴 CRITICAL - FOUNDATION FOR ALL VALIDATION

### Goal

Lock in current S01 behavior before any core changes. This becomes the "golden baseline" for all future validation.

### Steps

1. **Select baseline dataset:**
   - Choose small representative dataset (or subset of real data)
   - Example: 1-2 months of `OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
   - Should be quick to run but cover key scenarios (trends, ranges, volatility)

2. **Create baseline generation tool:**
   - Script: `tools/generate_baseline_s01.py`
   - Runs current (legacy) S01 with **fixed parameters** (document these!)
   - Saves:
     - Basic metrics (Net Profit %, Max DD %, Total Trades, etc.) → `data/baseline/s01_metrics.json`
     - All trades → `data/baseline/s01_trades.csv`
     - Equity curve → `data/baseline/s01_equity.csv` (optional but useful)

3. **Create regression test:**
   - Test: `tests/test_regression_s01.py`
   - Loads baseline from `data/baseline/`
   - Runs current S01 with same parameters
   - Compares results with tolerances:
     - Net Profit %: ±0.01% (floating point tolerance)
     - Max DD %: ±0.01%
     - Total Trades: exact match (±0)
     - Trade entry/exit times: exact match
     - Trade PnL: ±0.0001 (floating point tolerance)

4. **Document baseline parameters:**
   - Create `data/baseline/README.md` with:
     - Exact parameters used
     - Dataset details (symbol, timeframe, date range)
     - Expected metrics values
     - Tolerance levels and reasoning

### Tolerance Recommendations

```python
# tests/test_regression_s01.py
TOLERANCE_CONFIG = {
    "net_profit_pct": 0.01,      # ±0.01%
    "max_drawdown_pct": 0.01,    # ±0.01%
    "total_trades": 0,            # exact match
    "trade_pnl": 0.0001,          # floating point epsilon
    "sharpe_ratio": 0.001,        # ±0.001
}
```

### Deliverables

- [ ] `tools/generate_baseline_s01.py` script
- [ ] `data/baseline/` directory with stored results:
  - `s01_metrics.json`
  - `s01_trades.csv`
  - `s01_equity.csv` (optional)
  - `README.md` with documentation
- [ ] `tests/test_regression_s01.py` comparing against baseline
- [ ] Baseline parameters documented
- [ ] Test passing with current codebase

### Success Criteria

- Regression test passes consistently (run 3+ times to verify)
- Baseline captures enough detail to catch behavioral changes
- Documentation allows reproducing baseline in future

---

## Phase 1: Core Extraction to src/core/

**Complexity:** 🟢 LOW
**Risk:** 🟢 LOW
**Estimated Effort:** 2-3 hours
**Priority:** 🟢 SAFE - PURE REORGANIZATION

### Goal

Create explicit `src/core/` directory and move all engines there WITHOUT changing imports or logic yet. This is a pure physical reorganization.

### Steps

1. **Create core directory:**
   ```bash
   mkdir src/core
   touch src/core/__init__.py
   ```

2. **Move engines (no logic changes):**
   ```bash
   mv src/backtest_engine.py src/core/
   mv src/optuna_engine.py src/core/
   mv src/walkforward_engine.py src/core/
   ```

3. **Update imports everywhere:**
   - `server.py`: `from backtest_engine import ...` → `from core.backtest_engine import ...`
   - `run_backtest.py`: same
   - `optuna_engine.py`: update internal imports
   - `walkforward_engine.py`: update internal imports
   - `strategies/s01_trailing_ma/strategy.py`: update imports

4. **Test everything:**
   - Run `pytest` (all tests should pass)
   - Run manual smoke test:
     - Start server: `python src/ui/server.py` (will update path in next phase)
     - Test single backtest via UI
     - Test Optuna optimization (small number of trials)

### Deliverables

- [ ] `src/core/` directory created
- [ ] Three engines moved to `core/`
- [ ] All imports updated across codebase
- [ ] `pytest` passing
- [ ] Manual smoke test passed
- [ ] Git commit: "Phase 1: Move engines to core/"

### Success Criteria

- No behavioral changes (regression test passes)
- Code runs exactly as before
- Cleaner directory structure

---

## Phase 2: Export Extraction to export.py

**Complexity:** 🟡 MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 4-6 hours
**Priority:** 🟢 MOVED UP - LOW RISK, HIGH VALUE

### Goal

Centralize all export logic in a single module. This provides useful utilities for later phases and is low risk since export is "write-only" (doesn't affect calculations).

### Rationale for Moving Up

Originally Phase 5, moved earlier because:
- Lower risk than Grid removal or metrics extraction
- Provides useful utilities immediately
- Helps decouple optimizer_engine from CSV formatting
- Makes later phases cleaner (metrics/indicators can use export right away)

### Steps

1. **Create export module:**
   ```python
   # src/core/export.py
   from typing import List, Dict, Any
   from pathlib import Path

   def export_trades_tv(trades: List[TradeRecord], path: str) -> None:
       """Export trades in TradingView Trading Report Generator format"""
       pass

   def export_optuna_results(
       results: List[OptimizationResult],
       path: str,
       fixed_params: Dict[str, Any]
   ) -> None:
       """Export Optuna results with parameter block header + results table"""
       pass

   def export_wfa_summary(
       wfa_results: "WFAResults",  # forward reference
       path: str
   ) -> None:
       """Export Walk-Forward Analysis summary CSV"""
       pass
   ```

2. **Extract CSV export logic from optimizer_engine.py:**
   - Move `CSV_COLUMN_SPECS` (lines 552-585) → `export.py`
   - Move `export_to_csv()` (lines 610-698) → `export.py` as `export_optuna_results()`
   - Keep same column filtering logic (fixed params exclusion)
   - Keep same formatters (percent, float, float1, optional_float)

3. **Update optimizer_engine.py:**
   - Import: `from core.export import export_optuna_results`
   - Replace `export_to_csv()` calls with `export_optuna_results()`

4. **Update optuna_engine.py:**
   - Import and use `export_optuna_results()` for saving results

5. **Implement three export functions:**
   - `export_optuna_results()` - CSV export after Optuna optimization
   - `export_wfa_summary()` - CSV export after WFA (Optuna + Walk-Forward)
   - `export_trades()` - CSV + ZIP with trade history (when Export Trades checkbox enabled)

6. **Test exports:**
   - Run Optuna optimization and verify CSV output format unchanged
   - Manually inspect CSV structure matches original
   - Verify parameter block and results table both present
   - Test with various fixed_params configurations

### Deliverables

- [ ] `src/core/export.py` created
- [ ] Export functions implemented and tested
- [ ] `optimizer_engine.py` updated to use export module
- [ ] `optuna_engine.py` updated to use export module
- [ ] CSV output format verified unchanged
- [ ] Manual test with sample optimization results
- [ ] Git commit: "Phase 2: Extract export logic to export.py"

### Success Criteria

- Exported CSV files match original format exactly
- All engines use centralized export
- Regression tests still pass

---

## Phase 3: Grid Search Removal

**Complexity:** 🟡 MEDIUM
**Risk:** 🟡 MEDIUM
**Estimated Effort:** 6-8 hours
**Priority:** ⚠️ REQUIRES CAREFUL EXECUTION

### Goal

Remove Grid Search completely and merge all shared code directly into `optuna_engine.py`. Since Optuna is the sole optimizer, there's no need for a separate utilities module.

### Current coupling:
```python
# optuna_engine.py imports from optimizer_engine:
from optimizer_engine import (
    OptimizationResult,           # dataclass
    DEFAULT_SCORE_CONFIG,          # dict constant
    PARAMETER_MAP,                 # dict constant
    _generate_numeric_sequence,    # utility function
    _parse_timestamp,              # utility function
    _run_single_combination,       # CORE SIMULATOR
    calculate_score,               # scoring logic
)
```

### Steps

#### Step 1: Copy Shared Code to optuna_engine.py (3-4 hours)

1. **Move structures and constants to optuna_engine.py:**
   ```python
   # src/core/optuna_engine.py
   from dataclasses import dataclass
   from typing import Dict, List, Any

   @dataclass
   class OptimizationResult:
       """Result structure for Optuna optimization trials"""
       # ... copy from optimizer_engine

   DEFAULT_SCORE_CONFIG = {
       # ... move from optimizer_engine
   }

   PARAMETER_MAP = {
       # ... copy from optimizer_engine
   }

   def calculate_score(...) -> float:
       """Calculate composite score from metrics for Optuna trials"""
       # ... copy from optimizer_engine

   def _generate_numeric_sequence(...) -> List:
       """Generate numeric parameter sequence for Optuna sampling"""
       # ... copy from optimizer_engine

   def _parse_timestamp(...):
       """Parse timestamp from various formats"""
       # ... copy from optimizer_engine (or move to general utils if used elsewhere)

   def _run_single_combination(...):
       """Run backtest for single parameter combination"""
       # ... copy from optimizer_engine
   ```

2. **Update optuna_engine.py imports:**
   - Remove ALL imports from `optimizer_engine`
   - Update code to use local definitions (defined above)
   - Verify all Optuna functionality works

3. **Test Optuna optimization:**
   - Run end-to-end Optuna optimization
   - Verify scores match previous runs
   - Test all optimization targets (score, net_profit, romad, sharpe, max_drawdown)
   - Test all budget modes (n_trials, timeout, patience)

#### Step 2: Remove Grid Search Completely (3-4 hours)

1. **Update server.py:**
   - Find Grid Search mode selection in API endpoints
   - Remove Grid Search configuration options
   - Remove Grid Search execution paths
   - Keep only:
     - Optuna optimization endpoints
     - WFA endpoints
     - Single backtest endpoints

2. **Update UI:**
   - Remove Grid Search option from optimization mode dropdown
   - Remove Grid-specific parameter inputs
   - Update help text/documentation

3. **Delete optimizer_engine.py:**
   - Delete `src/optimizer_engine.py` completely
   - No legacy archive needed (Grid Search not coming back)

4. **Update documentation:**
   - Update `CLAUDE.md` to remove Grid Search references
   - Update `PROJECT_TARGET_ARCHITECTURE.md` if needed
   - Add migration note in `changelog.md`

5. **Clean imports:**
   - Search codebase for `from optimizer_engine import`
   - Should find NOTHING (all moved to optuna_engine.py)
   - Remove any unused imports

6. **Final testing:**
   - Run Optuna optimization end-to-end
   - Verify CSV export still works
   - Run regression test
   - Test with large parameter spaces (1000+ trials)

### Deliverables

- [ ] All shared code moved to `optuna_engine.py`
- [ ] `optuna_engine.py` self-contained (no optimizer_engine imports)
- [ ] Grid Search removed from server.py
- [ ] Grid Search removed from UI
- [ ] `optimizer_engine.py` deleted
- [ ] All imports cleaned up
- [ ] Documentation updated
- [ ] Optuna end-to-end test passing
- [ ] Regression test passing
- [ ] Git commit: "Phase 3: Remove Grid Search, Optuna-only"

### Success Criteria

- Optuna is sole optimization engine
- All optimization use cases covered
- Performance maintained or improved
- Codebase simpler (one less file, no optimization_utils.py)
- No dependencies on deleted optimizer_engine.py

---

## Phase 4: Metrics Extraction to metrics.py

**Complexity:** 🔴 HIGH
**Risk:** 🔴 HIGH
**Estimated Effort:** 8-12 hours
**Priority:** 🚨 HIGH-RISK PHASE #1

### Goal

Centralize all metrics calculation in `metrics.py`. Any formula change can break result comparability, so this requires careful OLD vs NEW comparison.

### Rationale for Before Indicators

Metrics are self-contained (operate on StrategyResult) while indicators are scattered throughout backtest_engine. Easier to validate metrics independently first.

### Current State

**Metrics currently in backtest_engine.py:**
- Basic metrics: net_profit_pct, max_drawdown_pct, total_trades (lines 999-1001)
- Advanced metrics: sharpe, profit_factor, romad, ulcer, recovery, consistency (lines 671-723)
- Helper functions: `calculate_monthly_returns`, `calculate_sharpe_ratio`, etc.

### Steps

1. **Create metrics module structure:**
   ```python
   # src/core/metrics.py
   from dataclasses import dataclass
   from typing import List, Optional
   from core.backtest_engine import StrategyResult, TradeRecord

   @dataclass
   class BasicMetrics:
       """Basic performance metrics calculated from strategy results"""
       net_profit: float
       net_profit_pct: float
       gross_profit: float
       gross_loss: float
       max_drawdown: float
       max_drawdown_pct: float
       total_trades: int
       winning_trades: int
       losing_trades: int
       win_rate: float
       avg_win: float
       avg_loss: float
       avg_trade: float

   @dataclass
   class AdvancedMetrics:
       """Advanced risk-adjusted metrics for optimization"""
       sharpe_ratio: Optional[float] = None
       sortino_ratio: Optional[float] = None
       profit_factor: Optional[float] = None
       romad: Optional[float] = None
       recovery_factor: Optional[float] = None
       ulcer_index: Optional[float] = None
       consistency_score: Optional[float] = None

   @dataclass
   class WFAMetrics:
       """Walk-Forward Analysis aggregate metrics"""
       avg_net_profit_pct: float
       avg_max_drawdown_pct: float
       successful_windows: int
       total_windows: int
       success_rate: float
       # ... more WFA-specific metrics

   def calculate_basic(result: StrategyResult) -> BasicMetrics:
       """Calculate basic metrics from strategy result"""
       pass

   def calculate_advanced(result: StrategyResult) -> AdvancedMetrics:
       """Calculate advanced metrics from strategy result"""
       pass

   def calculate_for_wfa(wfa_results: List) -> WFAMetrics:
       """Calculate aggregate WFA metrics"""
       pass
   ```

2. **Extract calculation functions:**
   - Move `calculate_monthly_returns()` → `metrics.py`
   - Move `calculate_sharpe_ratio()` → `metrics.py`
   - Move `calculate_profit_factor()` → `metrics.py`
   - Move `calculate_ulcer_index()` → `metrics.py`
   - Move `calculate_consistency_score()` → `metrics.py`
   - Implement `calculate_basic()` using extracted logic
   - Implement `calculate_advanced()` using extracted functions

3. **Parallel implementation strategy (CRITICAL):**
   ```python
   # In backtest_engine.py, keep OLD code temporarily:
   def run_strategy_OLD(...) -> StrategyResult:
       # ... existing implementation
       result.net_profit_pct = ...  # OLD way
       return result

   # In backtest_engine.py, add NEW integration:
   def run_strategy(...) -> StrategyResult:
       # ... simulation logic
       basic = metrics.calculate_basic(result)
       advanced = metrics.calculate_advanced(result)

       # Copy to result for backward compatibility
       result.net_profit_pct = basic.net_profit_pct
       result.sharpe_ratio = advanced.sharpe_ratio
       # ...
       return result
   ```

4. **Create parity test:**
   ```python
   # tests/test_metrics.py
   def test_metrics_parity():
       """Verify OLD and NEW implementations produce identical results"""
       # Load baseline result
       baseline_result = load_baseline_strategy_result()

       # OLD way (current backtest_engine)
       old_net_profit = baseline_result.net_profit_pct
       old_sharpe = baseline_result.sharpe_ratio

       # NEW way (metrics.py)
       new_basic = calculate_basic(baseline_result)
       new_advanced = calculate_advanced(baseline_result)

       # Assert bit-exact match
       assert old_net_profit == new_basic.net_profit_pct
       assert old_sharpe == new_advanced.sharpe_ratio
       # ... all metrics
   ```

5. **Test edge cases:**
   ```python
   def test_metrics_edge_cases():
       """Test metrics with unusual inputs"""
       # Zero trades
       result_no_trades = StrategyResult(trades=[], ...)
       basic = calculate_basic(result_no_trades)
       assert basic.total_trades == 0
       assert basic.win_rate == 0.0

       # All losing trades
       result_all_losses = ...
       basic = calculate_basic(result_all_losses)
       assert basic.winning_trades == 0

       # All winning trades
       # Single trade
       # Very short equity curve
   ```

6. **Update engines to use metrics.py:**
   - `backtest_engine.py`: Call `metrics.calculate_*` in `run_strategy()`
   - `optuna_engine.py`: Use metrics for objective function
   - `walkforward_engine.py`: Use metrics for window results

7. **Remove OLD calculation code:**
   - After validation passes, delete OLD metric functions from `backtest_engine.py`
   - Keep only simulation logic in `backtest_engine`

### Edge Cases to Test

- Zero trades (division by zero)
- All losing trades
- All winning trades
- Single trade
- Very short equity curve (<30 bars)
- Constant equity (no trades executed)
- Negative equity (drawdown > 100%)

### Validation Checklist

- [ ] Parity test passes (OLD vs NEW identical)
- [ ] Edge case tests pass
- [ ] Regression test passes (S01 behavior unchanged)
- [ ] Optuna trials produce same scores as before
- [ ] Manual inspection: compare metrics for known strategy run

### Deliverables

- [ ] `src/core/metrics.py` created
- [ ] All metric structures defined (BasicMetrics, AdvancedMetrics, WFAMetrics)
- [ ] Calculation functions implemented
- [ ] `tests/test_metrics.py` with edge cases
- [ ] Parity test: OLD vs NEW (passing)
- [ ] backtest_engine uses metrics.py
- [ ] optuna_engine uses metrics.py
- [ ] walkforward_engine uses metrics.py
- [ ] OLD metric code deleted from backtest_engine
- [ ] Regression test passing
- [ ] Git commit: "Phase 4: Extract metrics to metrics.py"

### Success Criteria

- Bit-exact match between OLD and NEW implementations
- All edge cases handled gracefully
- No changes to optimization scores
- S01 regression test passes

---

## Phase 5: Indicators Package Extraction

**Complexity:** 🔴 HIGH
**Risk:** 🔴 HIGH
**Estimated Effort:** 10-14 hours
**Priority:** 🚨 HIGH-RISK PHASE #2

### Goal

Extract all indicators from `backtest_engine.py` into separate `indicators/` package while preserving exact calculation behavior.

### Why This Is High Risk

- Indicators currently embedded in backtest_engine.py (~150 lines)
- S01 relies on 11 MA types + ATR + trail calculations
- Any tiny change in indicator calculation = different trades = broken S01
- Floating point operations sensitive to order: `(a+b)+c ≠ a+(b+c)`

### Current Indicators (backtest_engine.py lines 222-379)

**11 MA types:** SMA, EMA, WMA, HMA, VWMA, VWAP, ALMA, DEMA, KAMA, TMA, T3
**Volatility:** ATR
**Helper:** get_ma() (facade for all MA types)

### Incremental Extraction Strategy

**DO NOT extract all at once!** Extract one indicator at a time, test after each.

### Steps

1. **Create indicators package:**
   ```bash
   mkdir src/indicators
   touch src/indicators/__init__.py
   ```

2. **Extract in safe order (LOW to HIGH risk):**

   **Phase 5.1: Utilities (LOW RISK - 1 hour)**
   ```python
   # src/indicators/misc.py
   def _parse_timestamp(...):
       """Utility for timestamp parsing"""
       # Move from backtest_engine if present
   ```
   - Run regression test ✓

   **Phase 5.2: Basic MAs (MEDIUM RISK - 2-3 hours)**
   ```python
   # src/indicators/ma.py
   def sma(series: pd.Series, length: int) -> pd.Series:
       """Simple Moving Average"""
       # Move from backtest_engine lines 226-227

   def ema(series: pd.Series, length: int) -> pd.Series:
       """Exponential Moving Average"""
       # Move from backtest_engine lines 222-223

   def wma(series: pd.Series, length: int) -> pd.Series:
       """Weighted Moving Average"""
       # Move from backtest_engine lines 230-234
   ```
   - Test each MA individually
   - Run regression test after EACH extraction ✓

   **Phase 5.3: Volume-Weighted MAs (MEDIUM RISK - 2 hours)**
   ```python
   # src/indicators/ma.py (continued)
   def vwma(close: pd.Series, volume: pd.Series, length: int) -> pd.Series:
       """Volume-Weighted Moving Average"""
       # Move from backtest_engine lines 245-248
       # Note: This is a moving average, not a pure volume indicator

   def vwap(df: pd.DataFrame, length: int) -> pd.Series:
       """Volume-Weighted Average Price"""
       # Move from backtest_engine lines 318-323
       # Note: This is a moving average, not a pure volume indicator
   ```
   - Test: Run S01 with VWMA/VWAP parameters
   - Run regression test ✓

   **Phase 5.4: Volatility Indicators (MEDIUM RISK - 2 hours)**
   ```python
   # src/indicators/volatility.py
   def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
       """Average True Range"""
       # Move from backtest_engine lines 368-378

   def natr(df: pd.DataFrame, period: int = 14) -> pd.Series:
       """Normalized ATR"""
       # If implemented
   ```
   - Test: Run S01 with ATR-based stops
   - Create specific ATR test:
     ```python
     def test_atr_parity():
         df = load_test_data()
         old_atr = backtest_engine_OLD.atr(df, 14)
         new_atr = volatility.atr(df, 14)
         assert np.allclose(old_atr, new_atr, rtol=1e-10)
     ```
   - Run regression test ✓

   **Phase 5.5: Advanced MAs (HIGH RISK - 4-5 hours)**
   ```python
   # src/indicators/ma.py (continued)
   def hma(series: pd.Series, length: int) -> pd.Series:
       """Hull Moving Average"""
       # Move from backtest_engine lines 237-242

   def alma(series: pd.Series, length: int, offset: float = 0.85, sigma: float = 6) -> pd.Series:
       """Arnaud Legoux Moving Average"""
       # Move from backtest_engine lines 251-262

   def kama(series: pd.Series, length: int, fast: int = 2, slow: int = 30) -> pd.Series:
       """Kaufman Adaptive Moving Average"""
       # Move from backtest_engine lines 271-296

   def dema(series: pd.Series, length: int) -> pd.Series:
       """Double EMA"""
       # Move from backtest_engine lines 265-268

   def tma(series: pd.Series, length: int) -> pd.Series:
       """Triangular Moving Average"""
       # Move from backtest_engine lines 299-303

   def t3(series: pd.Series, length: int, factor: float = 0.7) -> pd.Series:
       """T3 Moving Average"""
       # Move from backtest_engine lines 312-315 + gd() helper
   ```
   - Test EACH MA type individually
   - Create comparison tests for each
   - Run regression test after each ✓

   **Phase 5.6: MA Facade (MEDIUM RISK - 1 hour)**
   ```python
   # src/indicators/ma.py
   def get_ma(series: pd.Series, ma_type: str, length: int, **kwargs) -> pd.Series:
       """Unified interface for all MA types"""
       # Move from backtest_engine lines 326-365
       VALID_MA_TYPES = {"SMA", "EMA", "HMA", ...}

       if ma_type == "SMA":
           return sma(series, length)
       elif ma_type == "EMA":
           return ema(series, length)
       # ... etc
   ```
   - Test with all 11 MA types
   - Run regression test ✓

3. **Implement BaseStrategy fallback mechanism:**
   ```python
   # src/strategies/base.py
   class BaseStrategy:
       # Custom indicators per strategy (optional)
       custom_indicators = {}

       @classmethod
       def get_indicator(cls, name: str, *args, **kwargs):
           """Fallback mechanism for indicator lookup"""
           # 1. Check if strategy has indicator_<name> method
           method_name = f"indicator_{name}"
           if hasattr(cls, method_name):
               return getattr(cls, method_name)(*args, **kwargs)

           # 2. Check custom_indicators dict
           if name in cls.custom_indicators:
               return cls.custom_indicators[name](*args, **kwargs)

           # 3. Look up in indicators package
           from indicators import ma, volatility, trend, oscillators

           # Try each module
           for module in [ma, volatility, trend, oscillators]:
               if hasattr(module, name.lower()):
                   return getattr(module, name.lower())(*args, **kwargs)

           raise ValueError(f"Indicator '{name}' not found")
   ```

4. **Update backtest_engine.py to use indicators:**
   ```python
   # src/core/backtest_engine.py
   from indicators.ma import get_ma, sma, ema, vwma, vwap
   from indicators.volatility import atr

   def run_strategy(...):
       # Replace inline calculations with imports
       ma_values = get_ma(df['Close'], params.ma_type, params.ma_length)
       atr_values = atr(df, params.atr_period)
       # Note: VWMA and VWAP are in ma.py, not volume.py
       # ...
   ```

5. **Create comprehensive indicator tests:**
   ```python
   # tests/test_indicators.py
   def test_sma_basic():
       """Test SMA with known values"""
       series = pd.Series([1, 2, 3, 4, 5])
       result = sma(series, 3)
       expected = pd.Series([nan, nan, 2.0, 3.0, 4.0])
       assert np.allclose(result, expected, equal_nan=True)

   def test_ema_decay():
       """Test EMA decay factor"""
       # ...

   def test_all_ma_types():
       """Ensure all 11 MA types work"""
       data = load_test_data()
       for ma_type in VALID_MA_TYPES:
           result = get_ma(data['Close'], ma_type, 20)
           assert result is not None
           assert len(result) == len(data)
   ```

6. **Validation after each extraction:**
   ```python
   # After extracting each indicator
   pytest tests/test_indicators.py::test_<indicator>_parity
   pytest tests/test_regression_s01.py
   ```

### Critical Warnings

🚨 **Floating point sensitivity:**
- Even refactoring can change results
- MUST compare outputs, not just logic
- Use `np.allclose(rtol=1e-10)` for comparisons

🚨 **Array indexing:**
- Watch for off-by-one errors
- Verify warmup period handling
- Check NaN propagation at start of series

🚨 **Dependency order:**
- Some MAs depend on others (HMA uses WMA, DEMA uses EMA)
- Extract dependencies first

### Deliverables

- [ ] `src/indicators/` package created
- [ ] `indicators/__init__.py` with exports
- [ ] `indicators/ma.py` (all 11 MA types including VWMA and VWAP)
- [ ] `indicators/volatility.py` (ATR, NATR)
- [ ] `indicators/trend.py`, `oscillators.py`, `misc.py` (as needed, if implemented)
- [ ] `tests/test_indicators.py` with parity tests
- [ ] BaseStrategy fallback mechanism implemented
- [ ] backtest_engine.py updated to use indicators package
- [ ] OLD indicator code deleted from backtest_engine
- [ ] Regression test passing after EVERY extraction
- [ ] Git commits after each sub-phase

**Note:** No `volume.py` file - VWMA and VWAP are moving averages and belong in `ma.py`

### Success Criteria

- BIT-EXACT results (no tolerance for differences)
- All 11 MA types produce identical output
- ATR calculations match exactly
- S01 regression test passes
- No degradation in performance

---

## Phase 6: Simple Strategy Testing

**Complexity:** 🟡 MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 8-12 hours
**Priority:** ✅ EXCELLENT VALIDATION APPROACH

### Goal

Test new architecture on dead-simple strategy BEFORE migrating complex S01. Much easier to debug issues without S01 complexity.

### Why This Is Smart

- Validates entire pipeline end-to-end
- Tests all three engines (backtest, optuna, WFA)
- Tests metrics, indicators, export
- Much simpler to debug than S01
- Proves architecture works before high-risk S01 migration

### Simple MA Strategy Design

```python
# src/strategies/simple_ma/strategy.py
from dataclasses import dataclass
from typing import Dict, Any
import pandas as pd
from strategies.base import BaseStrategy
from core.backtest_engine import StrategyResult, TradeRecord

@dataclass
class SimpleMAParams:
    """Parameters for Simple MA strategy - lives WITH the strategy"""
    fast_length: int = 10
    slow_length: int = 20
    stop_loss_pct: float = 2.0  # %

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SimpleMAParams":
        return SimpleMAParams(
            fast_length=int(d.get('fastLength', 10)),
            slow_length=int(d.get('slowLength', 20)),
            stop_loss_pct=float(d.get('stopLossPct', 2.0)),
        )

class SimpleMA(BaseStrategy):
    """
    Ultra-simple MA crossover strategy:
    - Long when fast MA > slow MA
    - Exit when fast MA < slow MA OR stop loss hit
    - No trailing, no ATR, no complex logic
    """

    STRATEGY_ID = "simple_ma"
    STRATEGY_NAME = "Simple MA Crossover"
    STRATEGY_VERSION = "v1"

    @staticmethod
    def run(df: pd.DataFrame, params: Dict[str, Any], trade_start_idx: int = 0) -> StrategyResult:
        """Dead simple strategy implementation"""
        # Parse params
        p = SimpleMAParams.from_dict(params)

        # Calculate indicators
        from indicators.ma import sma
        fast_ma = sma(df['Close'], p.fast_length)
        slow_ma = sma(df['Close'], p.slow_length)

        # Simple bar-by-bar logic
        trades = []
        position = None

        for i in range(trade_start_idx, len(df)):
            # Entry logic
            if position is None and fast_ma.iloc[i] > slow_ma.iloc[i]:
                position = {
                    'entry_time': df.index[i],
                    'entry_price': df['Close'].iloc[i],
                    'direction': 'Long'
                }

            # Exit logic
            elif position is not None:
                should_exit = False

                # Exit on crossover down
                if fast_ma.iloc[i] < slow_ma.iloc[i]:
                    should_exit = True

                # Exit on stop loss
                pnl_pct = (df['Close'].iloc[i] - position['entry_price']) / position['entry_price'] * 100
                if pnl_pct < -p.stop_loss_pct:
                    should_exit = True

                if should_exit:
                    trades.append(TradeRecord(
                        direction=position['direction'],
                        entry_time=position['entry_time'],
                        exit_time=df.index[i],
                        entry_price=position['entry_price'],
                        exit_price=df['Close'].iloc[i],
                        size=1.0,
                        net_pnl=(df['Close'].iloc[i] - position['entry_price']),
                    ))
                    position = None

        # Build result
        return StrategyResult(
            trades=trades,
            equity_curve=None,  # Calculate if needed
            # Metrics calculated by metrics.py
        )
```

### Config JSON

```json
{
  "strategy_id": "simple_ma",
  "strategy_name": "Simple MA Crossover",
  "version": "v1",
  "description": "Dead simple MA crossover for testing architecture",
  "parameters": {
    "fastLength": {
      "type": "int",
      "label": "Fast MA Length",
      "default": 10,
      "min": 5,
      "max": 50,
      "step": 1,
      "optimize": {
        "enabled": true,
        "min": 5,
        "max": 30,
        "step": 5
      }
    },
    "slowLength": {
      "type": "int",
      "label": "Slow MA Length",
      "default": 20,
      "min": 10,
      "max": 100,
      "step": 1,
      "optimize": {
        "enabled": true,
        "min": 15,
        "max": 50,
        "step": 5
      }
    },
    "stopLossPct": {
      "type": "float",
      "label": "Stop Loss %",
      "default": 2.0,
      "min": 0.5,
      "max": 10.0,
      "step": 0.5,
      "optimize": {
        "enabled": false
      }
    }
  }
}
```

### Steps

1. **Create strategy files:**
   ```bash
   mkdir src/strategies/simple_ma
   touch src/strategies/simple_ma/__init__.py
   touch src/strategies/simple_ma/strategy.py
   touch src/strategies/simple_ma/config.json
   ```

2. **Implement strategy** (as shown above)

3. **Create matching TradingView version:**
   ```pine
   //@version=5
   strategy("Simple MA Test", overlay=true)

   fastLen = input.int(10, "Fast MA")
   slowLen = input.int(20, "Slow MA")
   stopPct = input.float(2.0, "Stop Loss %")

   fastMA = ta.sma(close, fastLen)
   slowMA = ta.sma(close, slowLen)

   if (fastMA > slowMA)
       strategy.entry("Long", strategy.long)

   if (fastMA < slowMA)
       strategy.close("Long")

   strategy.exit("Stop", "Long", loss=close * stopPct / 100)
   ```

4. **Test progression:**
   ```
   Step 1: Single backtest
   ├─ Run simple_ma via CLI
   ├─ Verify trades make sense
   └─ Export trades to CSV

   Step 2: Compare with TradingView
   ├─ Export TradingView trades
   ├─ Compare entry/exit times
   └─ Compare PnL (allow small tolerance for commission differences)

   Step 3: Optuna optimization
   ├─ Run 50-100 trials
   ├─ Verify score improves over trials
   ├─ Verify best params are reasonable
   └─ Export results CSV

   Step 4: WFA (if implemented)
   ├─ Run 3-5 windows
   ├─ Verify IS optimization works
   ├─ Verify OOS testing works
   └─ Export WFA summary

   Step 5: UI integration
   ├─ Select simple_ma in UI
   ├─ Run backtest via web interface
   ├─ Run optimization via web interface
   └─ View/download results
   ```

5. **Create tests:**
   ```python
   # tests/test_simple_ma.py
   def test_simple_ma_basic():
       """Test simple_ma produces trades"""
       df = load_test_data()
       params = {'fastLength': 10, 'slowLength': 20, 'stopLossPct': 2.0}
       result = SimpleMA.run(df, params)

       assert result.total_trades > 0
       assert len(result.trades) == result.total_trades

   def test_simple_ma_optuna():
       """Test Optuna optimization with simple_ma"""
       config = OptunaConfig(
           strategy_id="simple_ma",
           n_trials=10,
           # ...
       )
       results = run_optuna_optimization(config)

       assert len(results) == 10
       assert max(r.score for r in results) > min(r.score for r in results)
   ```

### Indicators to Use

- **Only SMA** (simplest MA type)
- Avoid VWMA/VWAP (need volume logic)
- No ATR dependencies (too complex for this test)
- No trailing stops (test that in S01)

### Validation Checklist

- [ ] Strategy runs without errors
- [ ] Produces trades (not empty result)
- [ ] TradingView comparison matches (±1% tolerance)
- [ ] Optuna optimization improves score over trials
- [ ] CSV export formats correct
- [ ] UI integration works
- [ ] All three engines tested (backtest, optuna, WFA)
- [ ] Metrics calculated correctly
- [ ] No regression in existing tests

### Deliverables

- [ ] `src/strategies/simple_ma/` created
- [ ] `config.json` with simple parameters
- [ ] `strategy.py` with simple logic
- [ ] SimpleMAParams dataclass in strategy.py
- [ ] Matching TradingView PineScript version
- [ ] TradingView comparison completed
- [ ] `tests/test_simple_ma.py` passing
- [ ] All three engines tested and working
- [ ] UI integration verified
- [ ] Git commit: "Phase 6: Add simple_ma test strategy"

### Success Criteria

- Simple strategy validates entire architecture
- All components working together (engines, metrics, indicators, export)
- Confidence to proceed with S01 migration
- No major issues discovered

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
- Current S01 just calls `run_strategy()` from backtest_engine (line 726)
- Must reimplement ~300 lines of complex logic in strategy class
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
   - Remove any legacy fields if present

3. **Create strategy.py with StrategyParams:**
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
       close_count: int = 3

       # Position sizing
       qty: float = 1.0
       qty_mode: str = "fixed"  # "fixed" or "percent_equity"

       # Stops
       enable_atr_stop: bool = True
       atr_multiplier: float = 1.5
       atr_period: int = 14
       enable_max_dd_stop: bool = False
       max_dd_pct: float = 5.0
       enable_max_days_stop: bool = False
       max_days: int = 30

       # ... more params

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
   ```python
   class S01TrailingMAMigrated(BaseStrategy):
       STRATEGY_ID = "s01_trailing_ma_migrated"
       STRATEGY_NAME = "S01 Trailing MA (Migrated)"
       STRATEGY_VERSION = "v26"

       @staticmethod
       def run(df: pd.DataFrame, params: Dict[str, Any], trade_start_idx: int = 0) -> StrategyResult:
           # Parse params
           p = S01Params.from_dict(params)

           # COPY entire run_strategy() logic here initially
           # This creates duplication temporarily - that's OK!
           # ... (300+ lines)
   ```
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
   - Expected: EXACT match (if indicator extraction was correct)

3. **Step 3: Refactor internal structure (optional)** (2-3 hours)
   ```python
   class S01TrailingMAMigrated(BaseStrategy):
       @staticmethod
       def _calculate_indicators(df, p):
           """Extract indicator calculation to separate method"""
           pass

       @staticmethod
       def _process_bar(i, df, p, state):
           """Extract bar processing logic"""
           pass

       @staticmethod
       def run(df, params, trade_start_idx):
           p = S01Params.from_dict(params)
           indicators = S01TrailingMAMigrated._calculate_indicators(df, p)
           # ... main loop using _process_bar
   ```
   - This is OPTIONAL refactoring
   - Only do if it makes code clearer
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
    assert len(legacy_result.trades) == len(migrated_result.trades)

    # Compare trades one-by-one
    for t1, t2 in zip(legacy_result.trades, migrated_result.trades):
        assert t1.entry_time == t2.entry_time
        assert t1.exit_time == t2.exit_time
        assert t1.entry_price == t2.entry_price
        assert t1.exit_price == t2.exit_price
        assert abs(t1.net_pnl - t2.net_pnl) < 1e-6  # floating point tolerance

def test_s01_migrated_with_all_ma_types():
    """Test migrated S01 with all 11 MA types"""
    df = load_test_data()
    base_params = load_baseline_params()

    for ma_type in VALID_MA_TYPES:
        params = {**base_params, 'maType': ma_type}

        legacy_result = S01TrailingMA.run(df, params)
        migrated_result = S01TrailingMAMigrated.run(df, params)

        # Results should match
        assert abs(legacy_result.net_profit_pct - migrated_result.net_profit_pct) < 0.01

def test_s01_migrated_edge_cases():
    """Test edge cases specific to S01"""
    test_cases = [
        {'closeCount': 1},   # Immediate entry
        {'closeCount': 10},  # Many consecutive closes required
        {'qtyMode': 'fixed', 'qty': 1.0},
        {'qtyMode': 'percent_equity', 'qty': 10.0},
        {'enableAtrStop': True, 'atrMultiplier': 1.0},
        {'enableAtrStop': True, 'atrMultiplier': 3.0},
        # ... more edge cases
    ]

    for test_case in test_cases:
        # Test doesn't crash and produces reasonable results
        pass
```

#### 7.4: If Results Don't Match (Debugging Protocol)

```python
def debug_divergence():
    """Protocol for finding where legacy and migrated diverge"""
    # 1. Export equity curves to CSV
    legacy_equity = pd.DataFrame(legacy_result.equity_curve)
    migrated_equity = pd.DataFrame(migrated_result.equity_curve)

    # 2. Find FIRST bar where they diverge
    for i in range(len(legacy_equity)):
        if abs(legacy_equity.iloc[i] - migrated_equity.iloc[i]) > 0.01:
            print(f"Divergence at bar {i}")
            # 3. Debug that specific bar
            # - MA values at that bar
            # - ATR values at that bar
            # - Entry/exit signals
            # - Position sizes
            # - Trailing stop values
            break

    # 4. Fix root cause
    # 5. Re-run full comparison
```

**Common issues to check:**
- Indicator calculation order differs
- Floating point accumulation (different order = different results)
- Array indexing off-by-one errors
- Warmup handling (trade_start_idx interpretation)
- Position sizing rounding (floor vs round vs ceil)
- Stop loss logic (inclusive vs exclusive comparisons)

#### 7.5: Switch to Production (1-2 hours)

**After 100% validation passes:**

1. **Archive legacy:**
   ```bash
   mv src/strategies/s01_trailing_ma \
      src/strategies/s01_trailing_ma_legacy
   ```

2. **Promote migrated to production:**
   ```bash
   mv src/strategies/s01_trailing_ma_migrated \
      src/strategies/s01_trailing_ma
   ```

3. **Update strategy_id in config.json:**
   ```json
   {
     "strategy_id": "s01_trailing_ma",  // back to original ID
     "strategy_name": "S01 Trailing MA",
     // ...
   }
   ```

4. **Update strategy class:**
   ```python
   # Rename class back to S01TrailingMA
   class S01TrailingMA(BaseStrategy):  # was S01TrailingMAMigrated
       STRATEGY_ID = "s01_trailing_ma"
       # ...
   ```

5. **Delete run_strategy() from backtest_engine.py:**
   - This is the final step!
   - Removes ~300 lines of S01-specific logic from core
   - backtest_engine now truly generic

6. **Update tests:**
   ```python
   # tests/test_regression_s01.py
   # Now tests the migrated version (but it's the only version)
   ```

7. **Clean up:**
   - Remove legacy folder (or keep archived for reference)
   - Remove comparison tests (no longer needed)
   - Update documentation

### Validation Checklist

- [ ] Migrated strategy runs without errors
- [ ] Legacy vs migrated comparison: EXACT match
- [ ] All 11 MA types tested
- [ ] All stop types tested (ATR, max DD, max days)
- [ ] Both position sizing modes tested (fixed, percent)
- [ ] Multiple parameter combinations tested
- [ ] Baseline regression test passes with migrated version
- [ ] Optuna optimization produces similar scores
- [ ] UI tested with migrated S01
- [ ] Performance acceptable (not degraded)

### Deliverables

- [ ] `strategies/s01_trailing_ma_migrated/` created
- [ ] S01Params dataclass in strategy.py
- [ ] Logic migrated from run_strategy()
- [ ] Uses indicators.* instead of inline calculations
- [ ] `tests/test_s01_migration.py` with comprehensive tests
- [ ] Regression test: legacy vs migrated (exact match)
- [ ] Baseline comparison (exact match)
- [ ] All Optuna trials produce similar scores
- [ ] UI tested with migrated S01
- [ ] Legacy archived, migrated promoted to production
- [ ] run_strategy() deleted from backtest_engine.py
- [ ] Git commits throughout migration
- [ ] Final commit: "Phase 7: S01 migration complete"

### Success Criteria

- Bit-exact match between legacy and migrated (tolerance < 1e-6)
- All baseline tests pass
- S01 fully functional in new architecture
- backtest_engine.py is now generic (no S01-specific logic)
- Performance maintained or improved

---

## Phase 8: Frontend Separation

**Complexity:** 🟡 MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 6-10 hours
**Priority:** ✅ MOVED TO END - LOGICAL PLACEMENT

### Goal

Make UI readable and maintainable by separating HTML/CSS/JS into proper files, WITHOUT changing behavior. This is pure UI refactoring with no impact on backend.

### Rationale for Moving to End

Originally Phase 1, moved to end because:
- Frontend changes don't affect backend logic
- Can do this after all core functionality is migrated
- More logical to clean up UI once core is stable
- Allows focus on high-risk backend phases first
- UI testing easier when core is already solid

### Current State

**index.html is MASSIVE: 192KB monolithic file**
- Likely thousands of lines of inline JS and CSS
- High chance of hidden dependencies and coupling
- But: isolated from backend logic

### Steps

1. **Create UI directory structure:**
   ```bash
   mkdir -p src/ui/templates
   mkdir -p src/ui/static/css
   mkdir -p src/ui/static/js
   ```

2. **Move server.py:**
   ```bash
   mv src/server.py src/ui/server.py
   ```
   - Update import paths to `from core.backtest_engine import ...`

3. **Extract CSS (2-3 hours):**
   - Find all `<style>` blocks in index.html
   - Move to `src/ui/static/css/style.css`
   - Keep CSS exactly as is (no refactoring yet)
   - Optional: split into multiple files if very large:
     - `layout.css` - grid, flexbox, positioning
     - `components.css` - buttons, forms, tables
     - `theme.css` - colors, fonts, spacing

4. **Extract JavaScript (3-5 hours):**
   - Find all `<script>` blocks in index.html
   - Move to `src/ui/static/js/main.js`
   - Keep JavaScript exactly as is (no refactoring yet)
   - Watch for:
     - Inline event handlers (`onclick="..."`) - might need to move to JS
     - Script execution order dependencies
     - DOM ready checks
   - Optional: split into logical modules if very large:
     - `api.js` - AJAX calls to backend
     - `ui-handlers.js` - event handlers
     - `charts.js` - visualization code (if exists)
     - `utils.js` - helper functions

5. **Update index.html:**
   ```html
   <!DOCTYPE html>
   <html>
   <head>
       <meta charset="UTF-8">
       <title>S01 TrailingMA Backtester</title>
       <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
   </head>
   <body>
       <!-- Clean HTML markup only -->

       <script src="{{ url_for('static', filename='js/main.js') }}"></script>
   </body>
   </html>
   ```

6. **Update Flask static file serving:**
   ```python
   # src/ui/server.py
   from flask import Flask, send_from_directory

   app = Flask(__name__,
               static_folder='static',
               template_folder='templates')

   @app.route('/')
   def index():
       return render_template('index.html')

   # Explicit static routes if needed
   @app.route('/static/<path:path>')
   def send_static(path):
       return send_from_directory('static', path)
   ```

7. **Test EVERY UI feature manually:**
   - Start server: `python src/ui/server.py`
   - Test all features:
     - [ ] Strategy selection dropdown
     - [ ] Parameter inputs (all fields)
     - [ ] Date range selection
     - [ ] Single backtest execution
     - [ ] Optuna optimization execution
     - [ ] WFA execution (if implemented)
     - [ ] Results table display
     - [ ] CSV export download
     - [ ] Preset save/load
     - [ ] CSV import for presets
     - [ ] All buttons and controls
     - [ ] Error handling and messages

8. **Watch out for:**
   - Inline event handlers that need moving to JS
   - Dynamic CSS (JS-generated styles)
   - Script execution order dependencies
   - AJAX endpoint paths (might need `/api/` prefix)
   - CORS issues (unlikely in same-origin setup)
   - Asset loading paths (relative vs absolute)

### Suggested File Structure

```
src/ui/
├── server.py                    # Flask app
├── templates/
│   └── index.html               # Clean HTML only
└── static/
    ├── css/
    │   ├── style.css            # Main styles
    │   ├── components.css       # Optional: component styles
    │   └── layout.css           # Optional: layout styles
    └── js/
        ├── main.js              # App initialization
        ├── api.js               # API calls
        ├── ui-handlers.js       # Event handlers
        └── charts.js            # Optional: visualization
```

### Testing Checklist

Create manual testing checklist:
```markdown
## UI Smoke Test Checklist

### Page Load
- [ ] Page loads without errors
- [ ] All CSS applied correctly
- [ ] No console errors in browser DevTools

### Strategy Selection
- [ ] Strategy dropdown shows all strategies
- [ ] Selecting strategy loads correct parameters
- [ ] Parameter defaults match config.json

### Single Backtest
- [ ] Can input all parameters
- [ ] Can select date range
- [ ] Execute backtest button works
- [ ] Results display correctly
- [ ] Can download results CSV

### Optimization
- [ ] Optuna mode selected
- [ ] Can set number of trials
- [ ] Can enable/disable parameters for optimization
- [ ] Execute optimization button works
- [ ] Progress updates during optimization
- [ ] Results table populates
- [ ] Can sort/filter results
- [ ] Can download optimization CSV

### Presets
- [ ] Can save current parameters as preset
- [ ] Can load saved preset
- [ ] Can delete preset
- [ ] Can import preset from CSV

### Edge Cases
- [ ] Invalid parameter values show error
- [ ] Network errors handled gracefully
- [ ] Long-running operations don't freeze UI
- [ ] Multiple operations don't conflict
```

### Deliverables

- [ ] `src/ui/` directory structure created
- [ ] `server.py` moved to `ui/`
- [ ] `index.html` cleaned (HTML only) in `templates/`
- [ ] `static/css/style.css` with all styles
- [ ] `static/js/main.js` with all JavaScript
- [ ] Flask static serving configured
- [ ] Manual smoke test checklist completed
- [ ] All UI features working
- [ ] No behavior changes verified
- [ ] Browser DevTools shows no errors
- [ ] Git commit: "Phase 8: Separate frontend HTML/CSS/JS"

### Success Criteria

- UI looks and behaves exactly as before
- No functional regressions
- Code more maintainable (separate concerns)
- Easier to modify CSS/JS in future

---

## Phase 9: Logging, Cleanup, Documentation

**Complexity:** 🟡 MEDIUM
**Risk:** 🟢 LOW
**Estimated Effort:** 6-10 hours
**Priority:** ✅ POLISH PHASE

### Goal

Bring project to clean final state with proper logging, removed legacy code, and updated documentation.

### Steps

#### 9.1: Logging Setup (2-3 hours)

1. **Create logging configuration:**
   ```python
   # src/core/logging_config.py
   import logging
   import sys
   from pathlib import Path

   def setup_logging(level=logging.INFO, debug=False, log_file=None):
       """
       Configure logging for the project

       Args:
           level: Default logging level
           debug: If True, set level to DEBUG
           log_file: Optional path to log file
       """
       if debug:
           level = logging.DEBUG

       handlers = [logging.StreamHandler(sys.stdout)]

       if log_file:
           log_file = Path(log_file)
           log_file.parent.mkdir(parents=True, exist_ok=True)
           handlers.append(logging.FileHandler(log_file))

       logging.basicConfig(
           level=level,
           format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
           datefmt='%Y-%m-%d %H:%M:%S',
           handlers=handlers
       )

       # Suppress noisy libraries
       logging.getLogger('matplotlib').setLevel(logging.WARNING)
       logging.getLogger('optuna').setLevel(logging.INFO)
   ```

2. **Add logging to engines:**
   ```python
   # src/core/backtest_engine.py
   import logging
   logger = logging.getLogger(__name__)

   def run_backtest(...):
       logger.info(f"Starting backtest: strategy={strategy_id}, "
                   f"date_range={date_range}, warmup={warmup_bars}")
       # ...
       logger.debug(f"Prepared dataset: {len(df)} bars, "
                    f"trade_start_idx={trade_start_idx}")
       # ...
       logger.info(f"Backtest complete: {result.total_trades} trades, "
                   f"PnL={result.net_profit_pct:.2f}%")
       return result
   ```

   ```python
   # src/core/optuna_engine.py
   import logging
   logger = logging.getLogger(__name__)

   def run_optuna_optimization(...):
       logger.info(f"Starting Optuna optimization: {n_trials} trials, "
                   f"target={target}, budget_mode={budget_mode}")

       def objective(trial):
           logger.debug(f"Trial {trial.number}: params={trial.params}")
           # ...
           logger.debug(f"Trial {trial.number}: score={score:.4f}")
           return score

       # ...
       logger.info(f"Optimization complete: best_score={study.best_value:.4f}, "
                   f"best_params={study.best_params}")
   ```

   ```python
   # src/core/walkforward_engine.py
   import logging
   logger = logging.getLogger(__name__)

   def run_walkforward(...):
       logger.info(f"Starting WFA: {n_windows} windows, "
                   f"IS_length={is_length}, OOS_length={oos_length}")

       for i, window in enumerate(windows):
           logger.info(f"Window {i+1}/{n_windows}: "
                       f"IS={window.is_start}..{window.is_end}, "
                       f"OOS={window.oos_start}..{window.oos_end}")
           # ...

       logger.info(f"WFA complete: avg_pnl={avg_pnl:.2f}%, "
                   f"successful_windows={success_count}/{n_windows}")
   ```

3. **Add CLI logging flag:**
   ```python
   # src/cli/run_backtest.py
   import argparse
   from core.logging_config import setup_logging

   parser = argparse.ArgumentParser()
   parser.add_argument('--log-level',
                      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                      default='INFO',
                      help='Logging level')
   parser.add_argument('--debug',
                      action='store_true',
                      help='Enable debug logging (same as --log-level DEBUG)')
   parser.add_argument('--log-file',
                      help='Optional log file path')

   args = parser.parse_args()

   setup_logging(
       level=getattr(logging, args.log_level),
       debug=args.debug,
       log_file=args.log_file
   )
   ```

#### 9.2: Final Cleanup (2-3 hours)

1. **Delete legacy code:**
   ```bash
   # Remove archived legacy S01 (if confident)
   rm -rf src/strategies/s01_trailing_ma_legacy

   # Remove optimizer_engine.py (Grid Search)
   # (should be done in Phase 3, but double-check)

   # Remove any backup files
   find . -name "*.bak" -delete
   find . -name "*_old.py" -delete
   ```

2. **Remove unused imports:**
   ```bash
   # Use a tool like autoflake or manually search
   grep -r "import.*optimizer_engine" src/
   # Should return nothing
   ```

3. **Clean up temporary comments:**
   - Remove `# TODO: migrate` comments
   - Remove `# LEGACY:` markers
   - Remove comparison code that's no longer needed

4. **Verify no S01-specific code in backtest_engine:**
   ```bash
   grep -n "run_strategy" src/core/backtest_engine.py
   # Should not find the old 300-line function
   ```

5. **Check for hardcoded paths:**
   ```bash
   grep -r "C:\\\\Users" src/
   grep -r "/Users/someone" src/
   # Fix any hardcoded absolute paths
   ```

#### 9.3: Documentation Updates (2-4 hours)

1. **Update PROJECT_TARGET_ARCHITECTURE.md:**
   ```markdown
   # Target Architecture Overview

   **Status:** ✅ CURRENT IMPLEMENTATION (as of 2025-11-27)

   This document describes the CURRENT architecture after migration completion.

   ## Changes from Legacy:
   - [x] Core engines separated into src/core/
   - [x] Metrics centralized in metrics.py
   - [x] Indicators extracted to indicators/ package
   - [x] Export centralized in export.py
   - [x] S01 migrated to new architecture
   - [x] Grid Search removed (Optuna only)
   - [x] Frontend separated (HTML/CSS/JS)
   ```

2. **Update PROJECT_STRUCTURE.md:**
   - Reflect actual directory structure
   - Update all paths
   - Remove references to deleted files

3. **Update CLAUDE.md:**
   ```markdown
   ## Architecture (Updated 2025-11-27)

   - **Core engines** in `src/core/`:
     - `backtest_engine.py` - generic backtest simulator
     - `optuna_engine.py` - Optuna optimization (Grid Search removed)
     - `walkforward_engine.py` - WFA orchestrator

   - **Utilities** in `src/core/`:
     - `metrics.py` - all metrics calculation
     - `export.py` - CSV export functions
     - `optimization_utils.py` - shared optimization code

   - **Domain layers**:
     - `indicators/` - MA types, ATR, and other indicators
     - `strategies/` - strategy implementations with own params

   - **Interface layer**:
     - `ui/` - Flask server + HTML/CSS/JS frontend
     - `cli/` - command-line tools
   ```

4. **Create strategy development guide:**
   ```markdown
   # docs/ADDING_NEW_STRATEGY.md

   ## How to Add a New Strategy

   ### 1. Create Strategy Directory
   ```bash
   mkdir src/strategies/my_strategy
   touch src/strategies/my_strategy/__init__.py
   touch src/strategies/my_strategy/strategy.py
   touch src/strategies/my_strategy/config.json
   ```

   ### 2. Define Strategy Parameters
   ```python
   # strategy.py
   from dataclasses import dataclass

   @dataclass
   class MyStrategyParams:
       param1: int = 10
       param2: float = 1.5

       @staticmethod
       def from_dict(d: Dict[str, Any]) -> "MyStrategyParams":
           return MyStrategyParams(
               param1=int(d.get('param1', 10)),
               param2=float(d.get('param2', 1.5)),
           )
   ```

   ### 3. Implement Strategy Class
   ```python
   class MyStrategy(BaseStrategy):
       STRATEGY_ID = "my_strategy"
       STRATEGY_NAME = "My Strategy"
       STRATEGY_VERSION = "v1"

       @staticmethod
       def run(df: pd.DataFrame, params: Dict[str, Any],
               trade_start_idx: int = 0) -> StrategyResult:
           p = MyStrategyParams.from_dict(params)
           # ... strategy logic
           return StrategyResult(...)
   ```

   ### 4. Create config.json
   See config_json_format.md for full specification.

   ### 5. Test Strategy
   - Create tests/test_my_strategy.py
   - Test single backtest
   - Test optimization
   - Compare with TradingView if possible
   ```

5. **Create config.json format documentation:**
   ```markdown
   # docs/CONFIG_JSON_FORMAT.md

   ## Strategy Configuration Format

   Every strategy must have a `config.json` file describing its parameters.

   ### Basic Structure
   ```json
   {
     "strategy_id": "my_strategy",
     "strategy_name": "My Strategy",
     "version": "v1",
     "description": "Strategy description",
     "parameters": {
       "param1": {
         "type": "int",
         "label": "Parameter 1",
         "description": "What this parameter does",
         "default": 10,
         "min": 1,
         "max": 100,
         "step": 1,
         "group": "Entry",
         "optimize": {
           "enabled": true,
           "min": 5,
           "max": 50,
           "step": 5
         }
       }
     }
   }
   ```

   ### Parameter Types
   - `int` - Integer parameter
   - `float` - Floating point parameter
   - `bool` - Boolean parameter
   - `select` - Dropdown selection (add `options` array)
   - `string` - Text input

   ### Optimization Section
   If `optimize.enabled = true`, parameter can be optimized by Optuna.
   Optimization ranges can differ from UI input ranges.
   ```

6. **Update changelog.md:**
   ```markdown
   # Changelog

   ## [2.0.0] - 2025-11-27 - Architecture Migration Complete

   ### Major Changes
   - Migrated to clean architecture with separate core/indicators/strategies
   - Removed Grid Search optimizer (Optuna only)
   - Centralized metrics calculation in metrics.py
   - Extracted indicators to indicators/ package
   - Migrated S01 strategy to new architecture
   - Separated frontend (HTML/CSS/JS)
   - Added comprehensive test suite
   - Added logging throughout

   ### Breaking Changes
   - Grid Search no longer available
   - optimizer_engine.py removed
   - Import paths changed (use core.*)
   - StrategyParams now lives in each strategy module

   ### Migration Notes
   - See PROJECT_MIGRATION_PLAN_upd.md for full migration details
   - All functionality preserved, just reorganized
   - Performance maintained or improved
   ```

#### 9.4: Final Verification (1-2 hours)

1. **Run full test suite:**
   ```bash
   pytest -v
   # All tests should pass
   ```

2. **Run complete workflow:**
   - Single backtest via CLI
   - Single backtest via UI
   - Optuna optimization via CLI
   - Optuna optimization via UI
   - WFA (if implemented)
   - CSV exports
   - Preset save/load

3. **Performance check:**
   - Run S01 optimization with 100 trials
   - Should complete in reasonable time
   - Compare with pre-migration benchmarks (if available)

4. **Code quality check:**
   ```bash
   # Check for common issues
   grep -r "TODO" src/
   grep -r "FIXME" src/
   grep -r "import.*optimizer_engine" src/
   ```

### Deliverables

- [ ] `src/core/logging_config.py` created
- [ ] All engines use logging
- [ ] CLI --debug and --log-level flags working
- [ ] Legacy code deleted
- [ ] Unused imports removed
- [ ] Documentation updated:
  - [ ] PROJECT_TARGET_ARCHITECTURE.md
  - [ ] PROJECT_STRUCTURE.md
  - [ ] CLAUDE.md
  - [ ] docs/ADDING_NEW_STRATEGY.md
  - [ ] docs/CONFIG_JSON_FORMAT.md
  - [ ] changelog.md
- [ ] Full test suite passing
- [ ] Complete workflow tested
- [ ] Git commit: "Phase 9: Add logging, cleanup, update docs"

### Success Criteria

- Clean codebase with no legacy artifacts
- Comprehensive logging for debugging
- Documentation reflects current state
- Easy for new contributors (or future you!) to understand
- All tests passing
- All features working

---

## Summary of Phase Order Changes

### Original Order (v1.4)
-1, 0, 1, 2, 3, 4, 5, 6, 7, 8

### Updated Order (v2.0)
-1, 0, 1, 2 (Export), 3 (Grid removal), 4 (Metrics), 5 (Indicators), 6 (Simple), 7 (S01), 8 (Frontend), 9 (Polish)

### Key Reordering Rationale

1. **Frontend moved from #1 to #8:**
   - More logical to clean up UI AFTER core is stable
   - Allows focus on high-risk backend first
   - UI changes don't affect backend migration

2. **Export moved from #5 to #2:**
   - Lower risk than Grid removal
   - Provides useful utilities early
   - Helps decouple optimizer_engine
   - Makes later phases cleaner

3. **Metrics before Indicators (#4 → #3, #3 → #4):**
   - Metrics are self-contained (operate on StrategyResult)
   - Easier to validate independently
   - Indicators are scattered and riskier
   - Build confidence with metrics first

4. **Phase 2 split into 3.A and 3.B:**
   - Original "Core move + Grid removal" was too large
   - Now: Phase 1 (move to core), Phase 3 (Grid removal split)
   - Better risk management

---

## Cross-Cutting Concerns

### Testing Strategy

**Test Coverage Goals:**
- ❌ NOT aiming for 100% coverage (pet project)
- ✅ CRITICAL: Regression tests for S01 behavior
- ✅ CRITICAL: Parity tests for extracted code (indicators, metrics)
- ✅ GOOD: Edge case tests (zero trades, single trade, etc.)
- ⚠️ OPTIONAL: Unit tests for utilities

**Test Types:**
- **Regression tests:** Ensure S01 behavior unchanged
- **Parity tests:** Old vs new implementation matches
- **Edge case tests:** Unusual inputs handled gracefully
- **Integration tests:** End-to-end workflows work

### Performance Considerations

**Current Performance Features:**
- Multiprocessing with worker pools (6 default)
- Pre-computed indicator caches (in optimizer_engine _init_worker)
- Vectorized numpy/pandas operations

**Migration Risks:**
1. ⚠️ Indicator extraction might break caching
   - Current: _ma_cache, _lowest_cache, _highest_cache in workers
   - After migration: Must preserve this pattern
   - **RECOMMENDATION:** Keep caching in backtest_engine or create cache manager

2. 💡 Profile before/after migration:
   - Simple strategy should run 10x faster than S01
   - Optuna should handle 1000+ trials/hour for simple strategy
   - Use `python -m cProfile` if issues detected

### Git Strategy

```bash
# Main development branch
git checkout -b migration-v2

# Each phase gets a tag
git tag phase-1-complete
git tag phase-2-export-complete
git tag phase-3-grid-removal-complete
# ... etc

# High-risk phases get extra branches
git checkout -b phase-5-indicators-sma
git checkout -b phase-5-indicators-ema
# ... merge incrementally
```

### Validation Checkpoints

After each high-risk phase:
```
Phase X → Validation Checkpoint → Phase X+1
         ↓
   - Run full regression suite
   - Manual UI smoke test
   - Performance benchmark
   - Git tag: "phase-X-complete"
   - Update MIGRATION_PROGRESS.md
```

---

## Risk Matrix

| Phase | Complexity | Risk | Failure Impact | Mitigation |
|-------|-----------|------|----------------|------------|
| Phase -1 | 🟢 LOW | 🟢 LOW | 🟢 Low - just delays start | Do first, invest time upfront |
| Phase 0 | 🟡 MED | 🟢 LOW | 🔴 Critical - no safety net | Must complete before Phase 2+ |
| Phase 1 | 🟢 LOW | 🟢 LOW | 🟢 Low - just reorganization | Simple move, test imports |
| Phase 2 | 🟡 MED | 🟢 LOW | 🟢 Low - export only | Verify CSV formats |
| Phase 3 | 🔴 HIGH | 🟡 MED | 🟡 Medium - optimizer breaks | Split into 3.A and 3.B |
| Phase 4 | 🔴 HIGH | 🔴 HIGH | 🔴 Critical - scoring breaks | Parity tests, OLD/NEW comparison |
| Phase 5 | 🔴 HIGH | 🔴 HIGH | 🔴 Critical - S01 breaks | Extract one indicator at a time |
| Phase 6 | 🟡 MED | 🟢 LOW | 🟡 Medium - delays Phase 7 | TradingView validation |
| Phase 7 | 🔴 VERY HIGH | 🔴 VERY HIGH | 🔴 Critical - S01 unusable | Dual-track, incremental, bit-exact validation |
| Phase 8 | 🟡 MED | 🟢 LOW | 🟢 Low - UI only | Manual testing, no backend impact |
| Phase 9 | 🟡 MED | 🟢 LOW | 🟢 Low - polish only | Standard cleanup |

---

## Timeline Estimates

**Optimistic Scenario (experienced developer, no major issues):**
- Total: 70-90 hours = 9-12 workdays = **2 weeks full-time** or **4-6 weeks part-time**

**Realistic Scenario (some bugs, learning curve):**
- Total: 90-120 hours = 12-15 workdays = **3 weeks full-time** or **6-8 weeks part-time**

**Pessimistic Scenario (significant issues, multiple iterations):**
- Total: 120-160+ hours = 15-20+ workdays = **3-4 weeks full-time** or **2-3 months part-time**

**Recommendation:** Plan for realistic scenario, hope for optimistic, prepare for pessimistic.

---

## Migration Tracking

Use this to track your progress:

```markdown
## MIGRATION_PROGRESS.md

- [x] Phase -1: Test Infrastructure (Started: YYYY-MM-DD, Completed: YYYY-MM-DD)
- [x] Phase 0: Regression Baseline
- [x] Phase 1: Core Extraction
- [ ] Phase 2: Export Extraction
- [ ] Phase 3: Grid Search Removal
  - [ ] 3.A: Extract shared code
  - [ ] 3.B: Remove Grid Search
- [ ] Phase 4: Metrics Extraction
- [ ] Phase 5: Indicators Extraction
  - [ ] 5.1: Utilities
  - [ ] 5.2: Volume indicators
  - [ ] 5.3: Volatility indicators
  - [ ] 5.4: Basic MAs
  - [ ] 5.5: Advanced MAs
  - [ ] 5.6: MA facade
- [ ] Phase 6: Simple Strategy Testing
- [ ] Phase 7: S01 Migration
  - [ ] 7.1: Create structure
  - [ ] 7.2: Incremental migration
  - [ ] 7.3: Comprehensive testing
  - [ ] 7.4: Production switch
- [ ] Phase 8: Frontend Separation
- [ ] Phase 9: Logging, Cleanup, Documentation

## Notes
- Add notes about challenges, decisions, workarounds
- Document any deviations from plan
- Track time spent per phase
```

---

## Critical Success Factors

### ✅ Must Have
1. **Regression baseline BEFORE any changes** (Phase 0)
2. **Test infrastructure** (Phase -1)
3. **Bit-exact validation** for Phases 4, 5, 7
4. **Incremental approach** - one change at a time
5. **Legacy preservation** during migration (dual-track)

### ⚠️ Should Have
1. **TradingView validation** for strategies
2. **Performance profiling** before/after
3. **Documentation as you go** (not all at end)
4. **Git tags** at each phase completion

### 💡 Nice to Have
1. **Parallel development** (multiple branches)
2. **Rollback plan** (git tags enable this)
3. **CI/CD pipeline** (GitHub Actions)
4. **Automated performance benchmarks**

---

## Final Notes

### When to Stop and Ask for Help

🚨 **STOP migration if:**
1. Phase 0 baseline cannot be reproduced consistently
2. Regression tests fail after Phase 4 or 5 and you can't fix quickly
3. Performance degrades >50% after migration
4. S01 migrated version differs from legacy by >0.1%

### Tips for Success

1. **Take your time with Phases 4, 5, and 7** - these are high-risk
2. **Run regression test frequently** - after every significant change
3. **Commit early, commit often** - easy to rollback if needed
4. **Test in small increments** - don't batch multiple changes
5. **Document decisions** - future you will thank present you
6. **Celebrate milestones** - each phase completion is an achievement!

### Questions During Migration

If you encounter:
- **Unexpected test failures:** Debug before proceeding
- **Performance issues:** Profile and investigate
- **Design questions:** Refer back to PROJECT_TARGET_ARCHITECTURE.md
- **Scope creep:** Stay focused on migration, defer improvements

---

## Appendix: Key Architecture Decisions

### Data Structure Ownership
**Decision:** Structures live where they're populated
**Rationale:** Clear ownership, easier to understand data flow
**Impact:** No separate types.py needed

### StrategyParams Location
**Decision:** Inside each strategy's strategy.py
**Rationale:** Each strategy owns its parameters, no shared StrategyParams
**Impact:** Better encapsulation, easier to add new strategies

### Frontend Timing
**Decision:** Separate frontend AFTER core migration
**Rationale:** UI doesn't affect backend, logical to clean up last
**Impact:** Focus on high-risk backend first

### Export Early
**Decision:** Extract export before Grid removal
**Rationale:** Low risk, provides utilities immediately
**Impact:** Cleaner later phases, useful for debugging

### Metrics Before Indicators
**Decision:** Extract metrics before indicators
**Rationale:** Metrics self-contained, easier to validate
**Impact:** Build confidence before riskier indicator extraction

---

**END OF MIGRATION PLAN**

**Version:** 2.0
**Status:** Ready for Execution
**Last Updated:** 2025-11-27
**Author:** Migration Team
**Next Step:** Begin Phase -1 (Test Infrastructure Setup)
