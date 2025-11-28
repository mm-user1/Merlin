# Phase 3: Grid Search Removal

**Migration Phase:** 3 of 9
**Complexity:** 🟡 MEDIUM
**Risk:** 🟡 MEDIUM
**Estimated Effort:** 6-8 hours
**Priority:** ⚠️ REQUIRES CAREFUL EXECUTION

---

## Context and Background

### Project Overview

You are working on **S01 Trailing MA v26 - TrailingMA Ultralight**, a cryptocurrency/forex trading strategy backtesting and optimization platform. This phase focuses on removing Grid Search optimization completely and consolidating all optimization logic in Optuna.

### Previous Phases Completed

- ✅ **Phase -1: Test Infrastructure Setup** - pytest configured, comprehensive test suite
- ✅ **Phase 0: Regression Baseline for S01** - Comprehensive baseline established
- ✅ **Phase 1: Core Extraction** - Engines moved to `src/core/`
- ✅ **Phase 2: Export Extraction** - Export logic centralized in `src/core/export.py`

### Current State After Phase 2

```
src/
├── core/                           # ✅ Created in Phase 1
│   ├── __init__.py
│   ├── backtest_engine.py         # ✅ Moved in Phase 1
│   ├── optuna_engine.py           # ✅ Moved in Phase 1
│   ├── walkforward_engine.py      # ✅ Moved in Phase 1
│   └── export.py                  # ✅ Created in Phase 2
├── strategies/
│   ├── base.py
│   └── s01_trailing_ma/
│       ├── strategy.py
│       └── config.json
├── server.py                       # ✅ Imports updated
├── run_backtest.py                 # ✅ Imports updated
├── optimizer_engine.py             # ⚠️ Grid Search - TO BE REMOVED
└── index.html                      # ⚠️ Has Grid Search UI - TO BE UPDATED
```

**All tests passing.** Regression baseline maintained (Net Profit: 230.75%, Trades: 93).

---

## The Problem: Grid Search Legacy Code

Currently, `optimizer_engine.py` contains **two distinct systems**:

### 1. **Grid Search Implementation** (to be deleted)
- `generate_parameter_grid()` - Cartesian product of parameter ranges
- `run_grid_optimization()` - Grid search execution with multiprocessing
- Worker pool management and caching logic

### 2. **Shared Core Logic** (to be moved to optuna_engine.py)
- `OptimizationResult` dataclass - Result structure used by both optimizers
- `DEFAULT_SCORE_CONFIG` - Scoring configuration
- `PARAMETER_MAP` - Parameter name mapping
- `_generate_numeric_sequence()` - Numeric parameter generation
- `_parse_timestamp()` - Timestamp parsing utility
- `_run_single_combination()` - **CORE SIMULATOR** - Runs backtest for single parameter set
- `calculate_score()` - Composite score calculation from metrics

### Current Coupling

**optuna_engine.py imports from optimizer_engine.py:**

```python
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

This creates a dependency on Grid Search code even though Optuna doesn't use Grid Search itself.

---

## Objective

**Goal:** Remove Grid Search completely and make Optuna the sole optimizer by:

1. **Moving shared code** from `optimizer_engine.py` to `optuna_engine.py`
2. **Removing Grid Search** from server.py API endpoints
3. **Removing Grid Search** from UI (index.html)
4. **Deleting optimizer_engine.py** completely
5. **Updating documentation** to reflect Optuna-only architecture

**Critical Constraints:**
- All Optuna functionality must work identically after migration
- Optimization scores must remain unchanged (bit-exact)
- All tests must pass (regression baseline maintained)
- No performance degradation

---

## Architecture Principles

### Why Remove Grid Search?

**Rationale:**
1. **Simplicity** - One optimizer is easier to maintain than two
2. **Optuna superiority** - Bayesian optimization is more efficient than brute-force grid search
3. **No use cases** - Grid Search doesn't provide any functionality Optuna can't handle
4. **Code bloat** - Maintaining two optimizers with shared code creates complexity
5. **Migration blocker** - Grid Search couples with old architecture patterns

### Data Structure Ownership After Phase 3

Following the principle **"structures live where they're populated"**:

- **OptimizationResult** → `optuna_engine.py` (created during Optuna trials)
- **OptunaConfig** → `optuna_engine.py` (already there)
- **TradeRecord, StrategyResult** → `backtest_engine.py` (unchanged)
- **StrategyParams** → `strategies/<strategy_name>/strategy.py` (unchanged)

**No more optimizer_engine.py** - all optimization logic consolidated in `optuna_engine.py`.

---

## Detailed Code Analysis

### What Lives in optimizer_engine.py (Current State)

#### 1. Data Structures

```python
@dataclass
class OptimizationConfig:
    """Configuration received from the optimizer form."""
    csv_file: IO[Any]
    worker_processes: int
    contract_size: float
    commission_rate: float
    risk_per_trade_pct: float
    atr_period: int
    enabled_params: Dict[str, bool]
    param_ranges: Dict[str, Tuple[float, float, float]]
    ma_types_trend: List[str]
    ma_types_trail_long: List[str]
    ma_types_trail_short: List[str]
    lock_trail_types: bool
    fixed_params: Dict[str, Any]
    score_config: Optional[Dict[str, Any]] = None
    strategy_id: str = "s01_trailing_ma"
    warmup_bars: int = 1000
    filter_min_profit: bool = False
    min_profit_threshold: float = 0.0
    optimization_mode: str = "grid"

@dataclass
class OptimizationResult:
    """Represents a single optimization result row."""
    ma_type: str
    ma_length: int
    close_count_long: int
    close_count_short: int
    stop_long_atr: float
    stop_long_rr: float
    stop_long_lp: int
    stop_short_atr: float
    stop_short_rr: float
    stop_short_lp: int
    stop_long_max_pct: float
    stop_short_max_pct: float
    stop_long_max_days: int
    stop_short_max_days: int
    trail_rr_long: float
    trail_rr_short: float
    trail_ma_long_type: str
    trail_ma_long_length: int
    trail_ma_long_offset: float
    trail_ma_short_type: str
    trail_ma_short_length: int
    trail_ma_short_offset: float
    net_profit_pct: float
    max_drawdown_pct: float
    total_trades: int
    romad: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    ulcer_index: Optional[float] = None
    recovery_factor: Optional[float] = None
    consistency_score: Optional[float] = None
    score: float = 0.0
```

**Decision:** `OptimizationResult` moves to `optuna_engine.py`. `OptimizationConfig` is Grid-specific and will be deleted.

#### 2. Constants

```python
SCORE_METRIC_ATTRS: Dict[str, str] = {
    "romad": "romad",
    "sharpe": "sharpe_ratio",
    "pf": "profit_factor",
    "ulcer": "ulcer_index",
    "recovery": "recovery_factor",
    "consistency": "consistency_score",
}

DEFAULT_SCORE_CONFIG: Dict[str, Any] = {
    "weights": {},
    "enabled_metrics": {},
    "invert_metrics": {},
    "normalization_method": "percentile",
    "filter_enabled": False,
    "min_score_threshold": 0.0,
}

PARAMETER_MAP: Dict[str, Tuple[str, bool]] = {
    "maType": ("ma_type", True),
    "maLength": ("ma_length", False),
    "closeCountLong": ("close_count_long", False),
    "closeCountShort": ("close_count_short", False),
    "stopLongX": ("stop_long_atr", False),
    "stopLongRR": ("stop_long_rr", False),
    "stopLongLP": ("stop_long_lp", False),
    "stopShortX": ("stop_short_atr", False),
    "stopShortRR": ("stop_short_rr", False),
    "stopShortLP": ("stop_short_lp", False),
    "stopLongMaxPct": ("stop_long_max_pct", False),
    "stopShortMaxPct": ("stop_short_max_pct", False),
    "stopLongMaxDays": ("stop_long_max_days", False),
    "stopShortMaxDays": ("stop_short_max_days", False),
    "trailRRLong": ("trail_rr_long", False),
    "trailRRShort": ("trail_rr_short", False),
    "trailLongType": ("trail_ma_long_type", True),
    "trailLongLength": ("trail_ma_long_length", False),
    "trailLongOffset": ("trail_ma_long_offset", False),
    "trailShortType": ("trail_ma_short_type", True),
    "trailShortLength": ("trail_ma_short_length", False),
    "trailShortOffset": ("trail_ma_short_offset", False),
}
```

**Decision:** All three constants move to `optuna_engine.py`.

#### 3. Utility Functions

```python
def _generate_numeric_sequence(
    start: float,
    stop: float,
    step: float,
    *,
    include_endpoint: bool = True,
) -> List[Union[int, float]]:
    """
    Generate numeric sequence with proper handling of floating-point arithmetic.
    Returns integers if step is 1.0, otherwise floats.
    """
    # ... implementation
```

```python
def _parse_timestamp(value: Any) -> Optional[pd.Timestamp]:
    """Parse timestamp from various formats."""
    # ... implementation
```

**Decision:** Both utility functions move to `optuna_engine.py`.

#### 4. Core Simulation Function

```python
def _run_single_combination(args: Tuple[Dict[str, Any], pd.DataFrame, int, Any]) -> OptimizationResult:
    """
    Run backtest for a single parameter combination.

    This is the CORE SIMULATION FUNCTION used by both Grid Search and Optuna.
    It:
    1. Unpacks parameters and data
    2. Calls backtest_engine.run_strategy()
    3. Calculates metrics
    4. Returns OptimizationResult

    Args:
        args: Tuple of (params_dict, dataframe, trade_start_idx, score_config)

    Returns:
        OptimizationResult with all metrics populated
    """
    params_dict, df, trade_start_idx, score_config = args

    # Convert frontend params to StrategyParams
    from core.backtest_engine import StrategyParams, run_strategy

    strategy_params = StrategyParams(
        ma_type=params_dict["ma_type"],
        ma_length=params_dict["ma_length"],
        # ... all parameters
    )

    # Run backtest
    result = run_strategy(df, strategy_params, trade_start_idx)

    # Extract metrics
    net_profit_pct = result.net_profit_pct
    max_drawdown_pct = result.max_drawdown_pct
    total_trades = result.total_trades

    # Calculate advanced metrics (Sharpe, RoMaD, etc.)
    # ... metric calculation logic

    # Calculate composite score
    score = calculate_score(result, score_config)

    # Build OptimizationResult
    return OptimizationResult(
        ma_type=params_dict["ma_type"],
        ma_length=params_dict["ma_length"],
        # ... all parameters
        net_profit_pct=net_profit_pct,
        max_drawdown_pct=max_drawdown_pct,
        total_trades=total_trades,
        score=score,
        # ... all metrics
    )
```

**Decision:** This function moves to `optuna_engine.py`. It's the core simulation wrapper used by Optuna trials.

#### 5. Scoring Function

```python
def calculate_score(
    result: Any,  # StrategyResult or dict with metrics
    score_config: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Calculate composite score from multiple metrics.

    Supports:
    - Weighted combination of metrics (RoMaD, Sharpe, Profit Factor, etc.)
    - Normalization (percentile-based or min-max)
    - Metric inversion (for metrics where lower is better)
    - Filtering by minimum thresholds

    Args:
        result: StrategyResult or dict with metric values
        score_config: Configuration for scoring (weights, enabled metrics, etc.)

    Returns:
        Composite score (higher is better)
    """
    # ... implementation with weighted scoring, normalization, etc.
```

**Decision:** This function moves to `optuna_engine.py`.

#### 6. Grid Search Functions (TO BE DELETED)

```python
def generate_parameter_grid(config: OptimizationConfig) -> List[Dict[str, Any]]:
    """Generate Cartesian product of all parameter combinations."""
    # ... Grid Search specific logic

def run_grid_optimization(config: OptimizationConfig) -> List[OptimizationResult]:
    """Execute Grid Search optimization with multiprocessing."""
    # ... Grid Search specific logic with worker pools

def run_optimization(config: OptimizationConfig) -> List[OptimizationResult]:
    """Main entry point - delegates to Grid Search."""
    # ... wrapper that calls run_grid_optimization()
```

**Decision:** All Grid Search functions are **DELETED**. They are not used by Optuna.

---

## Detailed Step-by-Step Instructions

### Step 1: Copy Shared Code to optuna_engine.py (2-3 hours)

**Action:** Move all shared structures, constants, and functions from `optimizer_engine.py` to `optuna_engine.py`.

#### 1.1: Add Data Structures

**At the top of `src/core/optuna_engine.py` (after imports, before OptunaConfig):**

```python
"""Optuna-based Bayesian optimization engine for S_01 TrailingMA."""
from __future__ import annotations

import logging
import multiprocessing as mp
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
from decimal import Decimal

import optuna
from optuna.pruners import MedianPruner, PercentilePruner, PatientPruner
from optuna.samplers import RandomSampler, TPESampler
from optuna.trial import TrialState
import pandas as pd
import numpy as np

from .backtest_engine import (
    DEFAULT_ATR_PERIOD,
    load_data,
    StrategyParams,
    run_strategy,
    StrategyResult,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class OptimizationResult:
    """
    Represents a single optimization result (one trial/combination).

    This structure is populated by _run_single_combination() and contains:
    - All strategy parameters tested
    - Performance metrics (net profit, drawdown, trades)
    - Advanced metrics (Sharpe, RoMaD, Profit Factor, etc.)
    - Composite score

    Used by both Optuna optimization and results export.
    """
    ma_type: str
    ma_length: int
    close_count_long: int
    close_count_short: int
    stop_long_atr: float
    stop_long_rr: float
    stop_long_lp: int
    stop_short_atr: float
    stop_short_rr: float
    stop_short_lp: int
    stop_long_max_pct: float
    stop_short_max_pct: float
    stop_long_max_days: int
    stop_short_max_days: int
    trail_rr_long: float
    trail_rr_short: float
    trail_ma_long_type: str
    trail_ma_long_length: int
    trail_ma_long_offset: float
    trail_ma_short_type: str
    trail_ma_short_length: int
    trail_ma_short_offset: float
    net_profit_pct: float
    max_drawdown_pct: float
    total_trades: int
    romad: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    ulcer_index: Optional[float] = None
    recovery_factor: Optional[float] = None
    consistency_score: Optional[float] = None
    score: float = 0.0


# ============================================================================
# Constants
# ============================================================================

SCORE_METRIC_ATTRS: Dict[str, str] = {
    "romad": "romad",
    "sharpe": "sharpe_ratio",
    "pf": "profit_factor",
    "ulcer": "ulcer_index",
    "recovery": "recovery_factor",
    "consistency": "consistency_score",
}

DEFAULT_SCORE_CONFIG: Dict[str, Any] = {
    "weights": {},
    "enabled_metrics": {},
    "invert_metrics": {},
    "normalization_method": "percentile",
    "filter_enabled": False,
    "min_score_threshold": 0.0,
}

PARAMETER_MAP: Dict[str, Tuple[str, bool]] = {
    # Format: "frontendKey": ("result_attribute", is_categorical)
    "maType": ("ma_type", True),
    "maLength": ("ma_length", False),
    "closeCountLong": ("close_count_long", False),
    "closeCountShort": ("close_count_short", False),
    "stopLongX": ("stop_long_atr", False),
    "stopLongRR": ("stop_long_rr", False),
    "stopLongLP": ("stop_long_lp", False),
    "stopShortX": ("stop_short_atr", False),
    "stopShortRR": ("stop_short_rr", False),
    "stopShortLP": ("stop_short_lp", False),
    "stopLongMaxPct": ("stop_long_max_pct", False),
    "stopShortMaxPct": ("stop_short_max_pct", False),
    "stopLongMaxDays": ("stop_long_max_days", False),
    "stopShortMaxDays": ("stop_short_max_days", False),
    "trailRRLong": ("trail_rr_long", False),
    "trailRRShort": ("trail_rr_short", False),
    "trailLongType": ("trail_ma_long_type", True),
    "trailLongLength": ("trail_ma_long_length", False),
    "trailLongOffset": ("trail_ma_long_offset", False),
    "trailShortType": ("trail_ma_short_type", True),
    "trailShortLength": ("trail_ma_short_length", False),
    "trailShortOffset": ("trail_ma_short_offset", False),
}


# ============================================================================
# Utility Functions
# ============================================================================

def _generate_numeric_sequence(
    start: float,
    stop: float,
    step: float,
    *,
    include_endpoint: bool = True,
) -> List[Union[int, float]]:
    """
    Generate numeric sequence with proper handling of floating-point arithmetic.

    Uses Decimal for precise step calculations to avoid floating-point errors.
    Returns integers if step is 1.0 and all values are whole numbers.

    Args:
        start: Starting value
        stop: Ending value
        step: Step size
        include_endpoint: If True, include stop value if it aligns with steps

    Returns:
        List of numeric values (int or float)

    Examples:
        >>> _generate_numeric_sequence(1.0, 3.0, 1.0)
        [1, 2, 3]
        >>> _generate_numeric_sequence(0.5, 2.0, 0.5)
        [0.5, 1.0, 1.5, 2.0]
    """
    # Use Decimal for precise calculations
    d_start = Decimal(str(start))
    d_stop = Decimal(str(stop))
    d_step = Decimal(str(step))

    if d_step == 0:
        raise ValueError("Step cannot be zero")

    # Generate sequence
    sequence = []
    current = d_start

    if include_endpoint:
        while current <= d_stop:
            sequence.append(float(current))
            current += d_step
    else:
        while current < d_stop:
            sequence.append(float(current))
            current += d_step

    # Convert to integers if appropriate
    if d_step == Decimal('1') and all(Decimal(str(v)) % 1 == 0 for v in sequence):
        return [int(v) for v in sequence]

    return sequence


def _parse_timestamp(value: Any) -> Optional[pd.Timestamp]:
    """
    Parse timestamp from various formats.

    Handles:
    - pd.Timestamp objects (passthrough)
    - datetime objects
    - ISO format strings
    - Unix timestamps (int/float)

    Args:
        value: Timestamp in various formats

    Returns:
        pd.Timestamp or None if parsing fails
    """
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        return value

    if isinstance(value, str):
        try:
            return pd.Timestamp(value)
        except Exception:
            return None

    if isinstance(value, (int, float)):
        try:
            return pd.Timestamp.fromtimestamp(value)
        except Exception:
            return None

    try:
        return pd.Timestamp(value)
    except Exception:
        return None


# ============================================================================
# Core Simulation Function
# ============================================================================

def _run_single_combination(
    args: Tuple[Dict[str, Any], pd.DataFrame, int, Any]
) -> OptimizationResult:
    """
    Run backtest for a single parameter combination.

    This is the CORE SIMULATION FUNCTION used by Optuna trials.
    It wraps backtest_engine.run_strategy() and formats results.

    Process:
    1. Unpack arguments (params, data, trade_start_idx, score_config)
    2. Convert parameter dict to StrategyParams
    3. Call backtest_engine.run_strategy()
    4. Extract basic metrics (net profit, drawdown, trades)
    5. Calculate advanced metrics (Sharpe, RoMaD, Profit Factor, etc.)
    6. Calculate composite score
    7. Build and return OptimizationResult

    Args:
        args: Tuple of (params_dict, dataframe, trade_start_idx, score_config)
            - params_dict: Dict with all strategy parameters
            - dataframe: Market data (OHLCV)
            - trade_start_idx: Bar index to start trading (after warmup)
            - score_config: Scoring configuration (weights, enabled metrics)

    Returns:
        OptimizationResult with all parameters and metrics populated

    Note:
        This function must remain bit-exact compatible with the original
        implementation to maintain regression baseline.
    """
    params_dict, df, trade_start_idx, score_config = args

    # Convert parameter dict to StrategyParams
    strategy_params = StrategyParams(
        ma_type=params_dict["ma_type"],
        ma_length=params_dict["ma_length"],
        close_count_long=params_dict["close_count_long"],
        close_count_short=params_dict["close_count_short"],
        stop_long_atr=params_dict["stop_long_atr"],
        stop_long_rr=params_dict["stop_long_rr"],
        stop_long_lp=params_dict["stop_long_lp"],
        stop_short_atr=params_dict["stop_short_atr"],
        stop_short_rr=params_dict["stop_short_rr"],
        stop_short_lp=params_dict["stop_short_lp"],
        stop_long_max_pct=params_dict["stop_long_max_pct"],
        stop_short_max_pct=params_dict["stop_short_max_pct"],
        stop_long_max_days=params_dict["stop_long_max_days"],
        stop_short_max_days=params_dict["stop_short_max_days"],
        trail_rr_long=params_dict["trail_rr_long"],
        trail_rr_short=params_dict["trail_rr_short"],
        trail_ma_long_type=params_dict["trail_ma_long_type"],
        trail_ma_long_length=params_dict["trail_ma_long_length"],
        trail_ma_long_offset=params_dict["trail_ma_long_offset"],
        trail_ma_short_type=params_dict["trail_ma_short_type"],
        trail_ma_short_length=params_dict["trail_ma_short_length"],
        trail_ma_short_offset=params_dict["trail_ma_short_offset"],
    )

    # Run backtest
    result = run_strategy(df, strategy_params, trade_start_idx)

    # Extract basic metrics
    net_profit_pct = result.net_profit_pct
    max_drawdown_pct = result.max_drawdown_pct
    total_trades = result.total_trades

    # Extract advanced metrics (already calculated by backtest_engine)
    sharpe_ratio = getattr(result, 'sharpe_ratio', None)
    profit_factor = getattr(result, 'profit_factor', None)
    romad = getattr(result, 'romad', None)
    ulcer_index = getattr(result, 'ulcer_index', None)
    recovery_factor = getattr(result, 'recovery_factor', None)
    consistency_score = getattr(result, 'consistency_score', None)

    # Calculate composite score
    score = calculate_score(result, score_config)

    # Build OptimizationResult
    return OptimizationResult(
        ma_type=params_dict["ma_type"],
        ma_length=params_dict["ma_length"],
        close_count_long=params_dict["close_count_long"],
        close_count_short=params_dict["close_count_short"],
        stop_long_atr=params_dict["stop_long_atr"],
        stop_long_rr=params_dict["stop_long_rr"],
        stop_long_lp=params_dict["stop_long_lp"],
        stop_short_atr=params_dict["stop_short_atr"],
        stop_short_rr=params_dict["stop_short_rr"],
        stop_short_lp=params_dict["stop_short_lp"],
        stop_long_max_pct=params_dict["stop_long_max_pct"],
        stop_short_max_pct=params_dict["stop_short_max_pct"],
        stop_long_max_days=params_dict["stop_long_max_days"],
        stop_short_max_days=params_dict["stop_short_max_days"],
        trail_rr_long=params_dict["trail_rr_long"],
        trail_rr_short=params_dict["trail_rr_short"],
        trail_ma_long_type=params_dict["trail_ma_long_type"],
        trail_ma_long_length=params_dict["trail_ma_long_length"],
        trail_ma_long_offset=params_dict["trail_ma_long_offset"],
        trail_ma_short_type=params_dict["trail_ma_short_type"],
        trail_ma_short_length=params_dict["trail_ma_short_length"],
        trail_ma_short_offset=params_dict["trail_ma_short_offset"],
        net_profit_pct=net_profit_pct,
        max_drawdown_pct=max_drawdown_pct,
        total_trades=total_trades,
        sharpe_ratio=sharpe_ratio,
        profit_factor=profit_factor,
        romad=romad,
        ulcer_index=ulcer_index,
        recovery_factor=recovery_factor,
        consistency_score=consistency_score,
        score=score,
    )


# ============================================================================
# Scoring Function
# ============================================================================

def calculate_score(
    result: Union[StrategyResult, Dict[str, Any]],
    score_config: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Calculate composite score from multiple metrics.

    Supports:
    - Weighted combination of metrics (RoMaD, Sharpe, Profit Factor, etc.)
    - Normalization (percentile-based or min-max)
    - Metric inversion (for metrics where lower is better, e.g., Ulcer Index)
    - Filtering by minimum thresholds

    The score is calculated as a weighted sum of normalized metrics:
        score = Σ(weight_i × normalized_metric_i)

    Args:
        result: StrategyResult object or dict with metric values
        score_config: Configuration dict with:
            - weights: Dict[str, float] - Metric weights
            - enabled_metrics: Dict[str, bool] - Which metrics to include
            - invert_metrics: Dict[str, bool] - Which metrics to invert
            - normalization_method: str - "percentile" or "minmax"

    Returns:
        Composite score (higher is better)

    Example:
        >>> config = {
        ...     "weights": {"romad": 0.4, "sharpe": 0.3, "pf": 0.3},
        ...     "enabled_metrics": {"romad": True, "sharpe": True, "pf": True},
        ... }
        >>> calculate_score(result, config)
        11.52
    """
    if score_config is None:
        score_config = DEFAULT_SCORE_CONFIG

    # Extract metric values from result
    if isinstance(result, dict):
        metrics = result
    else:
        metrics = {
            "romad": getattr(result, "romad", None),
            "sharpe_ratio": getattr(result, "sharpe_ratio", None),
            "profit_factor": getattr(result, "profit_factor", None),
            "ulcer_index": getattr(result, "ulcer_index", None),
            "recovery_factor": getattr(result, "recovery_factor", None),
            "consistency_score": getattr(result, "consistency_score", None),
        }

    # Get configuration
    weights = score_config.get("weights", {})
    enabled_metrics = score_config.get("enabled_metrics", {})
    invert_metrics = score_config.get("invert_metrics", {})

    # If no weights specified, use equal weights
    if not weights:
        weights = {
            "romad": 0.25,
            "sharpe": 0.20,
            "pf": 0.20,
            "ulcer": 0.15,
            "recovery": 0.10,
            "consistency": 0.10,
        }

    # Calculate weighted score
    total_score = 0.0
    total_weight = 0.0

    for metric_key, weight in weights.items():
        # Skip if metric disabled
        if enabled_metrics and not enabled_metrics.get(metric_key, True):
            continue

        # Get metric attribute name
        attr_name = SCORE_METRIC_ATTRS.get(metric_key, metric_key)
        value = metrics.get(attr_name)

        # Skip if metric not available
        if value is None:
            continue

        # Invert if needed (e.g., Ulcer Index - lower is better)
        if invert_metrics.get(metric_key, False):
            # Invert by taking reciprocal (avoid division by zero)
            if value != 0:
                value = 1.0 / value
            else:
                value = 0.0

        # Add weighted contribution
        total_score += weight * value
        total_weight += weight

    # Normalize by total weight
    if total_weight > 0:
        return total_score / total_weight

    # Fallback: use RoMaD or net profit
    if metrics.get("romad"):
        return float(metrics["romad"])

    # Ultimate fallback
    return 0.0


# ============================================================================
# OptunaConfig (already exists - keep unchanged)
# ============================================================================

# @dataclass
# class OptunaConfig:
#     ... (already defined in optuna_engine.py)
```

**Checkpoint:** All shared code now exists in `optuna_engine.py`.

#### 1.2: Remove Old Imports

**In `src/core/optuna_engine.py`, remove the import from optimizer_engine:**

**BEFORE:**
```python
from optimizer_engine import (
    DEFAULT_SCORE_CONFIG,
    OptimizationResult,
    PARAMETER_MAP,
    _generate_numeric_sequence,
    _parse_timestamp,
    _run_single_combination,
    calculate_score,
)
```

**AFTER:**
```python
# All imports now local - no dependency on optimizer_engine
```

**Verify:** Search for any remaining references:
```bash
grep -n "optimizer_engine" src/core/optuna_engine.py
# Should return NOTHING
```

---

### Step 2: Update Core Package Exports (15 minutes)

**Action:** Export `OptimizationResult` from core package.

**In `src/core/__init__.py`, add:**

```python
# Optuna engine exports
from .optuna_engine import (
    OptimizationResult,      # NEW: Moved from optimizer_engine
    OptunaConfig,            # Already there
    OptunaOptimizer,         # Already there (if exported)
    # ... other optuna exports
)

__all__ = [
    # ... existing exports ...

    # Optuna engine exports
    "OptimizationResult",
    "OptunaConfig",
    "OptunaOptimizer",
]
```

---

### Step 3: Update Export Module (10 minutes)

**Action:** Update `src/core/export.py` to import `OptimizationResult` from `optuna_engine`.

**In `src/core/export.py`:**

**BEFORE:**
```python
# Temporary import from optimizer_engine (Phase 2)
from optimizer_engine import OptimizationResult
```

**AFTER:**
```python
# Import from optuna_engine (proper location after Phase 3)
from .optuna_engine import OptimizationResult
```

**Update function signature if needed:**
```python
def export_optuna_results(
    results: List[OptimizationResult],  # Now properly typed
    fixed_params: Union[Mapping[str, Any], Iterable[Tuple[str, Any]]],
    # ...
) -> str:
    # ... implementation unchanged
```

---

### Step 4: Remove Grid Search from server.py (60-90 minutes)

**Action:** Remove all Grid Search related code from Flask API.

#### 4.1: Find Grid Search References

```bash
grep -n "grid" src/server.py -i
grep -n "optimizer_engine" src/server.py
grep -n "optimization_mode" src/server.py
```

#### 4.2: Remove Grid Search Imports

**BEFORE:**
```python
from optimizer_engine import (
    OptimizationConfig,
    run_optimization,  # Grid Search entry point
)
from core.optuna_engine import OptunaOptimizer, OptunaConfig
```

**AFTER:**
```python
# Only Optuna imports needed
from core.optuna_engine import (
    OptunaOptimizer,
    OptunaConfig,
    OptimizationResult,
)
```

#### 4.3: Update Optimization Endpoint

**Find the `/api/optimize` endpoint:**

**BEFORE (supports both Grid and Optuna):**
```python
@app.route('/api/optimize', methods=['POST'])
def optimize():
    """Run optimization (Grid Search or Optuna)."""
    data = request.json

    # Get optimization mode
    optimization_mode = data.get('optimizationMode', 'grid')

    if optimization_mode == 'grid':
        # Grid Search path
        config = OptimizationConfig(
            csv_file=...,
            optimization_mode='grid',
            # ... Grid-specific config
        )
        results = run_optimization(config)
    elif optimization_mode == 'optuna':
        # Optuna path
        optuna_config = OptunaConfig(
            target=data.get('target', 'score'),
            # ... Optuna-specific config
        )
        optimizer = OptunaOptimizer(base_config, optuna_config)
        results = optimizer.optimize()
    else:
        return jsonify({"error": f"Unknown mode: {optimization_mode}"}), 400

    # Export results
    csv_content = export_optuna_results(results, fixed_params)
    return send_file(csv_content, ...)
```

**AFTER (Optuna only):**
```python
@app.route('/api/optimize', methods=['POST'])
def optimize():
    """Run Optuna optimization."""
    data = request.json

    # Build Optuna configuration
    optuna_config = OptunaConfig(
        target=data.get('target', 'score'),
        budget_mode=data.get('budgetMode', 'trials'),
        n_trials=data.get('nTrials', 100),
        time_limit=data.get('timeLimit', 3600),
        convergence_patience=data.get('convergencePatience', 50),
        enable_pruning=data.get('enablePruning', True),
        sampler=data.get('sampler', 'tpe'),
        pruner=data.get('pruner', 'median'),
        warmup_trials=data.get('warmupTrials', 20),
    )

    # Build base configuration (data, parameters, etc.)
    base_config = {
        'csv_file': ...,
        'enabled_params': data.get('enabledParams', {}),
        'param_ranges': data.get('paramRanges', {}),
        'fixed_params': data.get('fixedParams', {}),
        'score_config': data.get('scoreConfig', {}),
        # ... other settings
    }

    # Run Optuna optimization
    optimizer = OptunaOptimizer(base_config, optuna_config)
    results = optimizer.optimize()

    # Prepare metadata for export
    metadata = {
        'method': 'Optuna',
        'target': optuna_config.target,
        'total_trials': len(results),
        'completed_trials': len([r for r in results if r is not None]),
        # ... other Optuna metadata
    }

    # Export results to CSV
    from core.export import export_optuna_results
    csv_content = export_optuna_results(
        results,
        fixed_params=base_config['fixed_params'],
        optimization_metadata=metadata,
    )

    # Return as downloadable file
    return send_file(
        BytesIO(csv_content.encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='optimization_results.csv'
    )
```

#### 4.4: Remove Grid-Specific Configuration Handling

**Search for:**
- `optimization_mode` parameter handling
- Grid-specific parameter parsing
- Grid-specific error handling

**Delete all Grid Search code paths.**

---

### Step 5: Remove Grid Search from UI (60-90 minutes)

**Action:** Update `src/index.html` to remove Grid Search option from UI.

#### 5.1: Find Grid Search UI Elements

```bash
grep -n "grid" src/index.html -i | head -30
grep -n "optimization.*mode" src/index.html -i
```

#### 5.2: Remove Optimization Mode Selector

**BEFORE (has Grid/Optuna dropdown):**
```html
<div class="form-group">
    <label for="optimizationMode">Optimization Mode:</label>
    <select id="optimizationMode" class="form-control">
        <option value="grid">Grid Search</option>
        <option value="optuna" selected>Optuna (Bayesian)</option>
    </select>
</div>
```

**AFTER (Optuna only, no selector needed):**
```html
<!-- Optimization Mode is now always Optuna -->
<input type="hidden" id="optimizationMode" value="optuna">
```

**Or simply remove the field entirely and hardcode `"optuna"` in JavaScript.**

#### 5.3: Remove Grid-Specific UI Controls

**Look for:**
- Grid search step size controls
- Grid combination count displays
- Grid-specific help text

**Example (REMOVE):**
```html
<div id="gridSearchOptions" class="grid-options">
    <h4>Grid Search Settings</h4>
    <div class="form-group">
        <label>Step Size:</label>
        <input type="number" id="gridStepSize" value="1.0">
    </div>
    <div class="form-group">
        <label>Total Combinations:</label>
        <span id="totalCombinations">0</span>
    </div>
</div>
```

#### 5.4: Update JavaScript

**Find JavaScript that handles optimization mode switching:**

**BEFORE:**
```javascript
document.getElementById('optimizationMode').addEventListener('change', function() {
    const mode = this.value;

    if (mode === 'grid') {
        document.getElementById('gridSearchOptions').style.display = 'block';
        document.getElementById('optunaOptions').style.display = 'none';
    } else if (mode === 'optuna') {
        document.getElementById('gridSearchOptions').style.display = 'none';
        document.getElementById('optunaOptions').style.display = 'block';
    }
});
```

**AFTER:**
```javascript
// Always use Optuna (no mode selection needed)
// Show only Optuna options
document.getElementById('optunaOptions').style.display = 'block';
```

**Update optimization request:**

**BEFORE:**
```javascript
function runOptimization() {
    const mode = document.getElementById('optimizationMode').value;

    const data = {
        optimizationMode: mode,
        // ... mode-specific parameters
    };

    // ... send request
}
```

**AFTER:**
```javascript
function runOptimization() {
    // Always Optuna
    const data = {
        target: document.getElementById('optimizationTarget').value,
        budgetMode: document.getElementById('budgetMode').value,
        nTrials: parseInt(document.getElementById('nTrials').value),
        // ... only Optuna parameters
    };

    fetch('/api/optimize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(response => response.blob())
    .then(blob => {
        // Download CSV
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'optimization_results.csv';
        a.click();
    });
}
```

---

### Step 6: Delete optimizer_engine.py (5 minutes)

**Action:** Remove the Grid Search file completely.

```bash
# Delete optimizer_engine.py
rm src/optimizer_engine.py
```

**Verify deletion:**
```bash
ls -la src/*.py
# Should NOT show optimizer_engine.py
```

---

### Step 7: Search for Remaining References (15 minutes)

**Action:** Ensure no code still imports from `optimizer_engine`.

```bash
# Search entire codebase
grep -r "optimizer_engine" src/
grep -r "from optimizer_engine import" src/
grep -r "import optimizer_engine" src/

# Search tests
grep -r "optimizer_engine" tests/

# Search tools
grep -r "optimizer_engine" tools/
```

**Expected:** Should find NOTHING (all references removed).

**If found:** Update those files to import from `core.optuna_engine` instead.

---

### Step 8: Update Documentation (30 minutes)

#### 8.1: Update CLAUDE.md

**In `/home/user/S_01_v26-TrailingMA-Ultralight/CLAUDE.md`:**

**BEFORE:**
```markdown
### 2. Optimization Modes

The system supports two distinct optimization approaches:

**Grid Search** (`optimizer_engine.py`):
- Cartesian product of all enabled parameter ranges
- Uses multiprocessing with pre-computed caches for performance
- Best for small-to-medium search spaces (<10,000 combinations)

**Bayesian Optimization** (`optuna_engine.py`):
- Optuna-based smart search that learns from previous trials
- ...
```

**AFTER:**
```markdown
### 2. Optimization Engine

The system uses **Optuna** for Bayesian optimization:

**Optuna Engine** (`core/optuna_engine.py`):
- Smart search that learns from previous trials
- 5 optimization targets: score, net_profit, romad, sharpe, max_drawdown
- 3 budget modes: n_trials, timeout, or patience (convergence)
- Includes pruning to eliminate unpromising trials early
- Significantly more efficient than brute-force grid search

**Grid Search has been removed** (as of Phase 3 - 2025-11-28):
- Optuna covers all optimization use cases
- Simpler codebase with single optimizer
- Better performance and smarter parameter exploration
```

#### 8.2: Update PROJECT_TARGET_ARCHITECTURE.md

**In `docs/PROJECT_TARGET_ARCHITECTURE.md`:**

**Update section 2.2:**

**BEFORE:**
```markdown
### 2.2. `optuna_engine.py` — Optimization Engine

**Purpose:**
The only optimizer in the project, using Optuna.
```

**AFTER:**
```markdown
### 2.2. `optuna_engine.py` — Optimization Engine

**Purpose:**
The sole optimization engine in the project, using Optuna for Bayesian optimization.

**Status:** As of Phase 3 (2025-11-28), Grid Search has been completely removed.
All optimization now uses Optuna exclusively.

**Data structures owned by this module:**
- `OptimizationResult` - Single trial result (moved from optimizer_engine in Phase 3)
- `OptunaConfig` - Optimization configuration
```

#### 8.3: Update docs/MIGRATION_PROGRESS.md (or create changelog entry)

**Add Phase 3 completion:**

```markdown
## Phase 3: Grid Search Removal ✅

**Completed:** 2025-11-28
**Duration:** ~7 hours
**Complexity:** 🟡 MEDIUM
**Risk:** 🟡 MEDIUM

### Changes

**Moved to optuna_engine.py:**
- `OptimizationResult` dataclass
- `DEFAULT_SCORE_CONFIG` constant
- `PARAMETER_MAP` constant
- `_generate_numeric_sequence()` utility
- `_parse_timestamp()` utility
- `_run_single_combination()` core simulator
- `calculate_score()` scoring function

**Removed completely:**
- `src/optimizer_engine.py` (deleted)
- Grid Search implementation (`generate_parameter_grid`, `run_grid_optimization`)
- Grid Search UI controls (optimization mode selector)
- Grid Search API endpoints

**Updated:**
- `src/server.py` - Removed Grid mode, Optuna-only
- `src/index.html` - Removed Grid UI elements
- `src/core/export.py` - Imports OptimizationResult from optuna_engine
- `src/core/__init__.py` - Exports OptimizationResult from optuna_engine
- Documentation (CLAUDE.md, PROJECT_TARGET_ARCHITECTURE.md)

### Results

- ✅ All tests passing (21/21)
- ✅ Regression baseline maintained (230.75% profit, 93 trades)
- ✅ Optuna optimization works identically
- ✅ No performance degradation
- ✅ Codebase simplified (~500 lines removed)
```

---

### Step 9: Testing (90-120 minutes)

**Critical:** This phase must maintain bit-exact compatibility with Optuna optimization.

#### 9.1: Run Test Suite

```bash
pytest tests/ -v
```

**Expected:** All tests passing

**Watch for:**
- Import errors (`No module named 'optimizer_engine'`)
- Missing attribute errors (`'module' object has no attribute 'OptimizationResult'`)

#### 9.2: Test Optuna Optimization (CLI/Script)

**Create test script `tools/test_optuna_phase3.py`:**

```python
"""Test Optuna optimization after Phase 3 changes."""

from pathlib import Path
from core.optuna_engine import OptunaOptimizer, OptunaConfig, OptimizationResult
from core.backtest_engine import load_data

# Load data
data_path = Path(__file__).parent.parent / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
df = load_data(str(data_path))

print(f"Loaded {len(df)} bars")

# Configure Optuna
optuna_config = OptunaConfig(
    target="score",
    budget_mode="trials",
    n_trials=10,  # Small number for quick test
    enable_pruning=True,
    sampler="tpe",
)

# Base configuration
base_config = {
    'csv_file': None,  # Already loaded
    'dataframe': df,
    'warmup_bars': 100,
    'enabled_params': {
        'closeCountLong': True,
        'closeCountShort': True,
    },
    'param_ranges': {
        'closeCountLong': (5, 15, 1),
        'closeCountShort': (3, 10, 1),
    },
    'fixed_params': {
        'maType': 'HMA',
        'maLength': 50,
        # ... other fixed params
    },
    'score_config': {
        'weights': {'romad': 0.4, 'sharpe': 0.3, 'pf': 0.3},
    },
}

# Run optimization
print("Starting Optuna optimization (10 trials)...")
optimizer = OptunaOptimizer(base_config, optuna_config)
results = optimizer.optimize()

print(f"\nCompleted {len(results)} trials")

# Show best result
best_result = max(results, key=lambda r: r.score)
print(f"\nBest trial:")
print(f"  Score: {best_result.score:.2f}")
print(f"  Net Profit: {best_result.net_profit_pct:.2f}%")
print(f"  Max Drawdown: {best_result.max_drawdown_pct:.2f}%")
print(f"  Total Trades: {best_result.total_trades}")
print(f"  Close Count Long: {best_result.close_count_long}")
print(f"  Close Count Short: {best_result.close_count_short}")

# Test export
from core.export import export_optuna_results

metadata = {
    'method': 'Optuna',
    'total_trials': len(results),
    'completed_trials': len([r for r in results if r.score > 0]),
}

csv_content = export_optuna_results(
    results,
    fixed_params=base_config['fixed_params'],
    optimization_metadata=metadata,
)

# Save to file
output_path = Path(__file__).parent.parent / "test_optuna_phase3_results.csv"
with open(output_path, 'w') as f:
    f.write(csv_content)

print(f"\nResults exported to: {output_path}")
print("\n✅ Phase 3 Optuna test PASSED")
```

**Run test:**
```bash
python tools/test_optuna_phase3.py
```

**Expected output:**
```
Loaded 5000 bars
Starting Optuna optimization (10 trials)...
[Optuna progress bars...]
Completed 10 trials

Best trial:
  Score: 11.52
  Net Profit: 230.75%
  Max Drawdown: 20.03%
  Total Trades: 93
  Close Count Long: 9
  Close Count Short: 5

Results exported to: test_optuna_phase3_results.csv

✅ Phase 3 Optuna test PASSED
```

#### 9.3: Test via UI

**Start server:**
```bash
cd src
python server.py
```

**In browser:**
1. Navigate to `http://localhost:8000`
2. Select S01 strategy
3. **Verify:** No "Grid Search" option visible (only Optuna)
4. Configure Optuna optimization:
   - Target: Composite Score
   - Budget: 20 trials
   - Enable 2-3 parameters
5. Click "Optimize"

**Expected:**
- Optimization runs successfully
- Progress updates display
- Results download as CSV
- CSV format matches original (Optuna Metadata + Fixed Params + Results)

#### 9.4: Regression Test

```bash
pytest tests/test_regression_s01.py -v -m regression
```

**Expected:** 12/12 tests passing

**Critical validations:**
- ✅ Net profit: 230.75% (±0.01%)
- ✅ Max drawdown: 20.03% (±0.01%)
- ✅ Total trades: 93 (exact)

#### 9.5: Performance Check

**Run larger optimization:**

```python
# In test script, change:
n_trials=100  # Instead of 10

# Run and time it
import time
start = time.time()
results = optimizer.optimize()
duration = time.time() - start

print(f"Optimization took {duration:.1f}s for 100 trials")
print(f"Average: {duration/100:.2f}s per trial")
```

**Expected:** Similar or better performance than before Phase 3.

---

## Validation Checklist

Before considering Phase 3 complete, verify ALL of the following:

### Code Changes
- [ ] All shared code moved to `optuna_engine.py`
- [ ] `OptimizationResult` in `optuna_engine.py`
- [ ] `DEFAULT_SCORE_CONFIG` in `optuna_engine.py`
- [ ] `PARAMETER_MAP` in `optuna_engine.py`
- [ ] `_generate_numeric_sequence()` in `optuna_engine.py`
- [ ] `_parse_timestamp()` in `optuna_engine.py`
- [ ] `_run_single_combination()` in `optuna_engine.py`
- [ ] `calculate_score()` in `optuna_engine.py`
- [ ] No imports from `optimizer_engine` in `optuna_engine.py`

### File Operations
- [ ] `src/optimizer_engine.py` deleted
- [ ] `src/core/__init__.py` exports `OptimizationResult` from `optuna_engine`
- [ ] `src/core/export.py` imports `OptimizationResult` from `optuna_engine`

### Server Changes
- [ ] Grid Search mode removed from `/api/optimize`
- [ ] No `optimizer_engine` imports in `server.py`
- [ ] Optuna-only optimization endpoint working

### UI Changes
- [ ] Grid Search option removed from UI
- [ ] Optimization mode selector removed (or hidden)
- [ ] Only Optuna options visible
- [ ] JavaScript updated (no Grid mode handling)

### Testing
- [ ] All unit tests passing
- [ ] Regression tests passing: 12/12
- [ ] Optuna CLI test passing
- [ ] Optuna UI test passing
- [ ] Performance acceptable (no degradation)

### Code Quality
- [ ] No references to `optimizer_engine` anywhere:
  ```bash
  grep -r "optimizer_engine" src/ tests/ tools/
  # Should return NOTHING
  ```
- [ ] No import errors
- [ ] No broken links in code

### Documentation
- [ ] `CLAUDE.md` updated
- [ ] `PROJECT_TARGET_ARCHITECTURE.md` updated
- [ ] Migration progress documented
- [ ] Phase 3 completion noted

### Behavioral Validation
- [ ] Optuna optimization produces identical scores
- [ ] CSV export format unchanged
- [ ] Net profit matches baseline: 230.75%
- [ ] Total trades matches baseline: 93
- [ ] No regression in any metrics

---

## Git Workflow

```bash
# Stage all changes
git add src/core/optuna_engine.py
git add src/core/export.py
git add src/core/__init__.py
git add src/server.py
git add src/index.html
git add CLAUDE.md
git add docs/PROJECT_TARGET_ARCHITECTURE.md
git add docs/MIGRATION_PROGRESS.md
git add tools/test_optuna_phase3.py

# Note: optimizer_engine.py deletion is automatically staged
git status  # Verify optimizer_engine.py shows as deleted

# Commit
git commit -m "Phase 3: Remove Grid Search, Optuna-only

- Moved shared code from optimizer_engine.py to optuna_engine.py:
  - OptimizationResult dataclass
  - DEFAULT_SCORE_CONFIG, PARAMETER_MAP constants
  - _generate_numeric_sequence(), _parse_timestamp() utilities
  - _run_single_combination() core simulator
  - calculate_score() scoring function
- Deleted src/optimizer_engine.py completely
- Updated optuna_engine.py: self-contained, no optimizer_engine dependency
- Updated server.py: removed Grid Search mode, Optuna-only API
- Updated index.html: removed Grid Search UI elements
- Updated export.py: imports OptimizationResult from optuna_engine
- Updated core/__init__.py: exports OptimizationResult
- Updated documentation (CLAUDE.md, architecture docs)
- All tests passing (21/21)
- Regression baseline maintained (Net Profit 230.75%, Trades 93)
- Optuna optimization bit-exact compatible with previous version

This consolidation:
- Simplifies codebase (~500 lines removed)
- One optimizer instead of two
- Easier to maintain and understand
- No loss of functionality (Optuna superior to Grid Search)
- Prepares for metrics/indicators extraction (Phase 4-5)
"

# Tag
git tag phase-3-complete

# Verify
git log -1 --stat
git show phase-3-complete
```

---

## Common Issues and Troubleshooting

### Issue 1: Import Error - No module named 'optimizer_engine'

**Symptom:**
```
ModuleNotFoundError: No module named 'optimizer_engine'
```

**Cause:** Some file still imports from `optimizer_engine`

**Solution:**
```bash
# Find the culprit
grep -r "from optimizer_engine import" .

# Update to import from core.optuna_engine instead
# Example:
# BEFORE: from optimizer_engine import OptimizationResult
# AFTER:  from core.optuna_engine import OptimizationResult
```

### Issue 2: AttributeError - 'module' has no attribute 'OptimizationResult'

**Symptom:**
```
AttributeError: module 'core.optuna_engine' has no attribute 'OptimizationResult'
```

**Cause:** `OptimizationResult` not properly defined or exported

**Solution:**
1. Verify `OptimizationResult` is defined in `optuna_engine.py`
2. Verify it's a `@dataclass`
3. Check `core/__init__.py` exports it:
   ```python
   from .optuna_engine import OptimizationResult
   __all__ = [..., "OptimizationResult"]
   ```

### Issue 3: UI Shows "Grid Search" Option

**Symptom:** Grid Search still appears in optimization mode dropdown

**Cause:** HTML not updated or cached in browser

**Solution:**
1. Verify `index.html` changes saved
2. Hard refresh browser: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
3. Clear browser cache
4. Check for multiple `index.html` files (ensure editing correct one)

### Issue 4: Optimization Scores Changed

**Symptom:** Optuna produces different scores than before Phase 3

**Cause:** Bug in code migration (should NOT happen!)

**Solution:**
1. Compare `calculate_score()` implementation:
   ```bash
   # Extract old version from git
   git show HEAD~1:src/optimizer_engine.py > /tmp/old_optimizer.py

   # Compare calculate_score function
   grep -A 50 "def calculate_score" /tmp/old_optimizer.py
   grep -A 50 "def calculate_score" src/core/optuna_engine.py
   ```
2. Verify `_run_single_combination()` is identical
3. Check for typos in parameter names

### Issue 5: Tests Fail After Deletion

**Symptom:** Tests fail with import errors or assertion failures

**Cause:** Test files may import from `optimizer_engine`

**Solution:**
```bash
# Check test imports
grep -r "optimizer_engine" tests/

# Update to import from core.optuna_engine
# Example in tests/test_*.py:
# BEFORE: from optimizer_engine import OptimizationResult
# AFTER:  from core.optuna_engine import OptimizationResult
```

### Issue 6: Server Won't Start

**Symptom:**
```bash
python src/server.py
# ImportError or AttributeError
```

**Cause:** `server.py` still references Grid Search

**Solution:**
1. Check all imports at top of `server.py`
2. Search for `optimizer_engine` references:
   ```bash
   grep -n "optimizer_engine" src/server.py
   ```
3. Update to Optuna-only imports
4. Remove Grid mode handling in endpoints

---

## Performance Validation

Phase 3 should have **NO negative performance impact** - in fact, it may improve slightly by removing dead code.

### Benchmark Test

**Create `tools/benchmark_optuna.py`:**

```python
"""Benchmark Optuna performance after Phase 3."""

import time
from core.optuna_engine import OptunaOptimizer, OptunaConfig
from core.backtest_engine import load_data

# Load data
df = load_data("data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv")

# Configure
base_config = {
    'dataframe': df,
    'warmup_bars': 100,
    'enabled_params': {'closeCountLong': True, 'closeCountShort': True},
    'param_ranges': {'closeCountLong': (5, 15, 1), 'closeCountShort': (3, 10, 1)},
    'fixed_params': {'maType': 'HMA', 'maLength': 50},
}

optuna_config = OptunaConfig(n_trials=50, enable_pruning=True)

# Benchmark
print("Running 50 Optuna trials...")
start = time.time()
optimizer = OptunaOptimizer(base_config, optuna_config)
results = optimizer.optimize()
duration = time.time() - start

print(f"\nResults:")
print(f"  Total time: {duration:.1f}s")
print(f"  Per trial: {duration/50:.2f}s")
print(f"  Trials/sec: {50/duration:.2f}")
print(f"  Completed: {len(results)}/50")

# Compare with baseline (if available)
# Expected: ~1-3 seconds per trial depending on hardware
```

**Run:**
```bash
python tools/benchmark_optuna.py
```

**Expected:** Similar performance to before Phase 3 (±5%).

---

## Success Criteria Summary

Phase 3 is complete when:

1. ✅ **All shared code moved** - `optuna_engine.py` is self-contained
2. ✅ **optimizer_engine.py deleted** - File no longer exists
3. ✅ **Grid Search removed from server** - Optuna-only API
4. ✅ **Grid Search removed from UI** - Optuna-only interface
5. ✅ **All imports updated** - No `optimizer_engine` references
6. ✅ **All tests passing** - 21/21 tests green
7. ✅ **Regression baseline maintained** - Bit-exact compatibility
8. ✅ **Documentation updated** - Architecture docs reflect changes
9. ✅ **Clean git commit** - With tag `phase-3-complete`

---

## Next Steps After Phase 3

Once Phase 3 is complete and validated, proceed to:

**Phase 4: Metrics Extraction to metrics.py**
- Complexity: 🔴 HIGH
- Risk: 🔴 HIGH
- Estimated Effort: 8-12 hours

Phase 4 will centralize all metrics calculation in `src/core/metrics.py`, extracting from `backtest_engine.py`. This is high-risk because any formula change can break result comparability.

---

## Quick Reference Commands

```bash
# ============================================================================
# Code Migration
# ============================================================================

# Copy shared code to optuna_engine.py (manual - see Step 1)

# Delete optimizer_engine.py
rm src/optimizer_engine.py

# ============================================================================
# Verification
# ============================================================================

# Search for remaining references (should be empty)
grep -r "optimizer_engine" src/ tests/ tools/
grep -r "from optimizer_engine import" src/

# Verify optuna_engine imports
grep -n "^from" src/core/optuna_engine.py | grep -v "^from \.backtest"

# ============================================================================
# Testing
# ============================================================================

# Run full test suite
pytest tests/ -v                           # All tests
pytest tests/test_regression_s01.py -v     # Regression only

# Test Optuna optimization
python tools/test_optuna_phase3.py

# Benchmark performance
python tools/benchmark_optuna.py

# ============================================================================
# Server Testing
# ============================================================================

# Start server
cd src && python server.py

# Test optimization via UI
# Navigate to http://localhost:8000
# Verify no Grid Search option
# Run small Optuna optimization (10-20 trials)

# ============================================================================
# Git
# ============================================================================

# Check status (optimizer_engine.py should show as deleted)
git status

# Commit all changes
git add -A
git commit -m "Phase 3: Remove Grid Search, Optuna-only"
git tag phase-3-complete

# Verify
git log -1 --stat
git show phase-3-complete
```

---

## Migration Safety Nets

### Rollback Plan

If Phase 3 encounters critical issues:

**Option 1: Git rollback**
```bash
# Rollback to Phase 2
git reset --hard phase-2-complete

# Verify
pytest tests/ -v
```

**Option 2: Keep backup**
```bash
# Before starting Phase 3
cp src/optimizer_engine.py src/optimizer_engine.py.backup

# If needed, restore
mv src/optimizer_engine.py.backup src/optimizer_engine.py
```

### Critical Files Backup

Before Phase 3, backup:
- `src/optimizer_engine.py`
- `src/core/optuna_engine.py`
- `src/server.py`
- `src/index.html`

```bash
mkdir -p backups/phase3
cp src/optimizer_engine.py backups/phase3/
cp src/core/optuna_engine.py backups/phase3/
cp src/server.py backups/phase3/
cp src/index.html backups/phase3/
```

---

## Detailed CSV Export Compatibility

### CSV Format Must Remain Identical

**Structure:**
```csv
Optuna Metadata
Method,Optuna
Target,Composite Score
Total Trials,100
Completed Trials,100
Pruned Trials,5
Best Trial Number,42
Best Value,11.52
Optimization Time,125.3s

Fixed Parameters
Parameter Name,Value
maType,HMA
maLength,50

CC L,CC S,St L X,St L RR,St L LP,St S X,St S RR,St S LP,...,Net Profit%,Max DD%,Trades,Score
9,5,2.0,0.5,0,1.5,0.3,0,...,230.75%,20.03%,93,11.52
10,4,1.8,0.4,0,1.6,0.4,0,...,215.30%,18.22%,87,10.85
...
```

**Critical:**
- Optuna Metadata section unchanged
- Fixed Parameters section unchanged
- Column headers unchanged (order matters!)
- Value formatting unchanged (percentages, decimals)

**Verification:**
```python
# Compare old vs new export
from optimizer_engine import export_to_csv as old_export  # Before deletion
from core.export import export_optuna_results as new_export

# Create identical test data
# Run both exports
# Compare strings character-by-character
assert old_csv == new_csv, "Export format changed!"
```

---

**End of Phase 3 Prompt**

**Total Length:** ~29.5 KB
**Target Audience:** GPT 5.1 Codex
**Expected Execution Time:** 6-8 hours
**Risk Level:** 🟡 MEDIUM (careful execution required)

**Key Success Metric:** Optuna optimization produces bit-exact identical scores to before Phase 3, with Grid Search completely removed and codebase simplified by ~500 lines.
