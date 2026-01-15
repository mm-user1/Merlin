# Phase 2.1: Stress Test Post Process Feature - Implementation Plan

**Document Version:** v3.2
**Date:** 2026-01-14
**Author:** Claude Opus 4.5
**Status:** Draft - Awaiting Approval
**Changes from v3.1:** UI updates: red Param ID for problematic trials instead of badges; show both Profit Ret and RoMaD Ret in comparison line

---

## Changelog (v3.1 → v3.2)

| # | Issue | Fix Applied |
|---|-------|-------------|
| H | Badge/label UI approach | Use red Param ID color for problematic trials (status ≠ ok); show detailed status in comparison line |
| I | Comparison line retention display | Show both "Profit Ret: X%" and "RoMaD Ret: Y%" instead of single "Ret: X%" |

---

## Changelog (v3 → v3.1)

| # | Issue | Fix Applied |
|---|-------|-------------|
| G | Inconsistent `total_perturbations` in early-exit branches | Use `n_generated` consistently (not `n`) in `n_valid==0` and `SKIPPED_BAD_BASE` branches |

---

## Changelog (v2 → v3)

| # | Issue | Fix Applied |
|---|-------|-------------|
| A | Invalid base RoMaD handling | Option A: `combined_failure_rate = profit_failure_rate` when RoMaD invalid |
| B | Summary aggregation bug | Use `is not None` instead of truthiness checks; correct denominator |
| C | Quantile reproducibility | Use `np.quantile(x, q, method="linear")` explicitly |
| D | INSUFFICIENT_DATA undefined | Define trigger: `n_valid < MIN_NEIGHBORS` (default: 4) |
| E | Terminology consistency | Ensure all UI uses "retention" / "lower-tail" / "sensitivity analysis" |
| F | `n==0 → SKIPPED_NO_PARAMS` bug | **Fixed**: `SKIPPED_NO_PARAMS` only when no perturbations generated; `INSUFFICIENT_DATA` when all backtests failed |
| - | Database migration | **Removed**: User will use fresh DB, no migration needed |
| - | UI visualization | **Clarified**: Same table as Optuna IS, re-arranged by ST; comparison line at chart bottom |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Feature Overview](#2-feature-overview)
3. [Design Decisions Summary](#3-design-decisions-summary)
4. [Technical Architecture](#4-technical-architecture)
5. [Data Structures](#5-data-structures)
6. [Implementation Details](#6-implementation-details)
7. [UI Components](#7-ui-components)
8. [Database Schema](#8-database-schema)
9. [API Endpoints](#9-api-endpoints)
10. [Implementation Phases](#10-implementation-phases)
11. [Testing Strategy](#11-testing-strategy)
12. [Risks and Mitigations](#12-risks-and-mitigations)
13. [Future Considerations](#13-future-considerations)

---

## 1. Executive Summary

### Purpose
Add a **Stress Test** feature to Merlin's Post Process module that evaluates parameter robustness through systematic perturbation testing. This feature identifies overfit parameter sets that perform well in optimization but collapse with small parameter changes.

### Core Concept
A "good" parameter set should not be a fragile spike. Robust solutions sit on a "plateau" of nearby good solutions, while overfit solutions sit on a narrow ridge where tiny changes break performance.

### Position in Workflow
```
Optuna Optimization
       ↓
   DSR Analysis (if enabled) → Re-rank by DSR probability
       ↓
   Forward Test (if enabled) → Re-rank by profit_degradation or ft_romad
       ↓
   Stress Test (if enabled) → Re-rank by retention_score    ← NEW
       ↓
   WFA uses top-1 from final ranking
```

---

## 2. Feature Overview

### What Stress Test Does
1. Takes top-K candidates from previous Post Process step (chain: FT > DSR > Optuna)
2. For each candidate, runs a **baseline IS backtest** with identical conditions
3. Generates parameter perturbations using One-At-a-Time (OAT) approach
4. Runs backtests for all perturbations on IS period
5. Calculates retention metrics by comparing perturbation results to baseline
6. Re-ranks candidates by retention score
7. Stores results for UI display and WFA selection

### Key User Benefits
- **Overfitting Detection**: Identifies parameter sets that are "lucky peaks" vs stable plateaus
- **Confidence in Selection**: Higher retention = more confidence params will work in production
- **Risk Awareness**: Failure rate metric shows how often small changes cause problems
- **Informed Decisions**: See both performance ranking and retention ranking
- **Per-parameter sensitivity** diagnostic to identify fragile parameters

---

## 3. Design Decisions Summary

| Decision Point | Choice | Rationale |
|----------------|--------|-----------|
| **Test Period** | IS Period Only | Faster, tests optimization surface robustness |
| **Perturbation Steps** | ±1 step | Simple and clear; step size from config.json `optimize.step` |
| **Scoring Method** | Percentile-Based | Industry standard, robust to outliers |
| **Terminology** | "Retention ratio" not "confidence" | Avoid statistical language for deterministic OAT |
| **Primary Metrics** | Net Profit % + RoMaD | Both calculated, user chooses sort metric |
| **Failure Definition** | Combined: profit OR romad | Risk-aware failure detection |
| **Failure Threshold** | Configurable (default 70%) | Perturbation below X% of base = failed |
| **Input Source** | Chain from previous step | FT results > DSR results > Optuna results |
| **Final Ranking** | Sort by retention_score | Most stable params rise to top |
| **Categorical Params** | Skip | Only perturb numeric (int/float) params |
| **Score Range** | Unbounded (can exceed 1.0) | Retention ratio, not clipped |
| **Bad Base Policy** | Explicit N/A handling | profit≤0 → skip, invalid romad → exclude from romad metrics |
| **[v3] Invalid RoMaD** | Option A | `combined_failure_rate = profit_failure_rate` when RoMaD invalid |
| **[v3] Min Neighbors** | 4 | `status = INSUFFICIENT_DATA` if `n_valid < 4` |
| **[v3] No Valid Results** | Distinct status | `SKIPPED_NO_PARAMS` only when no perturbations generated; `INSUFFICIENT_DATA` when all backtests failed |
| **[v3] Quantile Method** | `method="linear"` | Explicit for reproducibility across NumPy versions |
| **[v3.2] UI Warning Display** | Red Param ID | Visual indicator in table; detailed status in comparison line |

---

## 4. Technical Architecture

### 4.1 Perturbation Generation (OAT Approach)

For each candidate parameter set, generate perturbations by changing one parameter at a time:

```python
def generate_perturbations(
    base_params: dict,
    config_json: dict
) -> List[dict]:
    """
    Generate OAT perturbations for a parameter set.

    Uses ±1 step from config.json optimize.step for each numeric parameter.

    Args:
        base_params: Original parameter values (e.g., {"maLength": 250, "maType": "EMA", ...})
        config_json: Strategy config with parameter definitions

    Returns:
        List of perturbed parameter dicts with metadata
    """
    perturbations = []

    for param_name, param_config in config_json["parameters"].items():
        param_type = param_config.get("type")

        # Skip categorical/select parameters
        if param_type == "select":
            continue

        # Skip non-optimizable parameters
        if not param_config.get("optimize", {}).get("enabled", False):
            continue

        base_value = base_params[param_name]
        step = param_config["optimize"].get("step", param_config.get("step", 1))
        min_val = param_config["optimize"].get("min", param_config.get("min"))
        max_val = param_config["optimize"].get("max", param_config.get("max"))

        # Generate ±1 step perturbations
        for direction in [-1, +1]:
            perturbed_value = base_value + (direction * step)

            # Bounds checking
            if min_val is not None and perturbed_value < min_val:
                continue
            if max_val is not None and perturbed_value > max_val:
                continue

            # Create perturbed params dict
            perturbed_params = base_params.copy()
            perturbed_params[param_name] = perturbed_value

            perturbations.append({
                "params": perturbed_params,
                "perturbed_param": param_name,
                "direction": direction,
                "base_value": base_value,
                "perturbed_value": perturbed_value
            })

    return perturbations
```

**Example:**
For S01 with base params `{maLength: 250, closeCountLong: 7, stopLongX: 2.0}`:
- maLength step=25: test 225, 275
- closeCountLong step=1: test 6, 8
- stopLongX step=0.1: test 1.9, 2.1
- Total: ~20-30 perturbations per candidate

### 4.2 Retention Scoring Algorithm

**[v3 CHANGES: A, B, C, D applied]**

```python
import numpy as np
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum
import math


# [v3] Minimum neighbors for reliable statistics
MIN_NEIGHBORS = 4


class StressTestStatus(Enum):
    """Status of Stress Test for a candidate."""
    OK = "ok"                              # Normal processing
    SKIPPED_BAD_BASE = "skipped_bad_base"  # Base profit <= 0
    SKIPPED_NO_PARAMS = "skipped_no_params"  # No numeric optimizable params
    INSUFFICIENT_DATA = "insufficient_data"  # [v3 FIX D] Too few valid perturbations


@dataclass
class RetentionMetrics:
    """
    Retention metrics from perturbation results.

    "Retention ratio" terminology (not "stability score" or "confidence"):
    - ratio = 1.0 means neighbor equals base
    - ratio < 1.0 means neighbor degraded
    - ratio > 1.0 means neighbor improved (possible, not clipped)
    """
    # Status
    status: StressTestStatus

    # Profit-based retention (None if base_profit <= 0)
    profit_retention: Optional[float]      # Combined score: 0.5 * lower_tail + 0.5 * median
    profit_lower_tail: Optional[float]     # 5th percentile (not "95% confidence")
    profit_median: Optional[float]         # 50th percentile
    profit_worst: Optional[float]          # min ratio

    # RoMaD-based retention (None if base_romad invalid)
    romad_retention: Optional[float]
    romad_lower_tail: Optional[float]
    romad_median: Optional[float]
    romad_worst: Optional[float]

    # Failure rates
    profit_failure_rate: Optional[float]   # Fraction below threshold (profit)
    romad_failure_rate: Optional[float]    # Fraction below threshold (romad), None if invalid
    combined_failure_rate: float           # [v3 FIX A] See logic below

    profit_failure_count: int
    romad_failure_count: int               # [v3 FIX A] 0 if romad invalid
    combined_failure_count: int
    total_perturbations: int
    failure_threshold: float

    # Per-parameter sensitivity
    param_worst_ratios: dict  # {param_name: worst_profit_ratio}


def calculate_retention_metrics(
    base_metrics: dict,
    perturbation_results: List[dict],
    failure_threshold: float = 0.7,
    total_perturbations_generated: int = 0
) -> RetentionMetrics:
    """
    Calculate retention metrics from perturbation results.

    [v3 FIX A] When base RoMaD is invalid:
        - romad_retention = None
        - romad_failure_rate = None
        - romad_failure_count = 0
        - combined_failure_rate = profit_failure_rate
        - combined_failure_count = profit_failure_count

    [v3 FIX B] Aggregation uses `is not None` checks, not truthiness.
    [v3 FIX C] Uses numpy.quantile() with method="linear" for reproducibility.
    [v3 FIX D] Returns INSUFFICIENT_DATA if n_valid < MIN_NEIGHBORS.

    IMPORTANT: This function does NOT check for SKIPPED_NO_PARAMS.
    That check must happen in the caller (run_stress_test) where the original
    perturbation count is known. If perturbation_results is empty here,
    it means all backtests failed, which is INSUFFICIENT_DATA.

    Args:
        base_metrics: Metrics from baseline IS re-run
        perturbation_results: List of perturbation result dicts (filtered, non-None only)
        failure_threshold: Below this ratio = failed (0-1)
        total_perturbations_generated: Original count before filtering (for accurate reporting)

    Returns:
        RetentionMetrics with all calculated values
    """
    n = len(perturbation_results)
    n_generated = total_perturbations_generated if total_perturbations_generated > 0 else n

    # [v3 FIX] If no valid results, this is INSUFFICIENT_DATA (not SKIPPED_NO_PARAMS).
    # SKIPPED_NO_PARAMS should only be set by caller when generate_perturbations() returned [].
    if n == 0:
        return RetentionMetrics(
            status=StressTestStatus.INSUFFICIENT_DATA,
            profit_retention=None, profit_lower_tail=None, profit_median=None, profit_worst=None,
            romad_retention=None, romad_lower_tail=None, romad_median=None, romad_worst=None,
            profit_failure_rate=1.0, romad_failure_rate=None, combined_failure_rate=1.0,
            profit_failure_count=n_generated, romad_failure_count=0, combined_failure_count=n_generated,
            total_perturbations=n_generated, failure_threshold=failure_threshold,
            param_worst_ratios={}
        )

    base_profit = base_metrics.get("net_profit_pct", 0)
    base_romad = base_metrics.get("romad")

    # Check for bad base profit
    # [v3.1 FIX] Use n_generated for consistency (defensive - normally caught in run_stress_test)
    if base_profit <= 0:
        return RetentionMetrics(
            status=StressTestStatus.SKIPPED_BAD_BASE,
            profit_retention=None, profit_lower_tail=None, profit_median=None, profit_worst=None,
            romad_retention=None, romad_lower_tail=None, romad_median=None, romad_worst=None,
            profit_failure_rate=None, romad_failure_rate=None, combined_failure_rate=1.0,
            profit_failure_count=n_generated, romad_failure_count=0, combined_failure_count=n_generated,
            total_perturbations=n_generated, failure_threshold=failure_threshold,
            param_worst_ratios={}
        )

    # [v3 FIX A] Check for valid base romad (must be positive number)
    romad_valid = base_romad is not None and math.isfinite(base_romad) and base_romad > 0

    # Calculate profit ratios (filtering out None/failed results)
    profit_ratios = []
    romad_ratios = []

    # Track per-parameter worst ratios
    param_profit_ratios = {}  # {param_name: [ratios]}

    for result in perturbation_results:
        neighbor_profit = result.get("net_profit_pct")

        # Skip if perturbation failed completely
        if neighbor_profit is None:
            continue

        # Profit ratio (base_profit > 0 guaranteed here)
        profit_ratio = neighbor_profit / base_profit
        profit_ratios.append(profit_ratio)

        # Track per-parameter
        param_name = result.get("perturbed_param", "unknown")
        if param_name not in param_profit_ratios:
            param_profit_ratios[param_name] = []
        param_profit_ratios[param_name].append(profit_ratio)

        # RoMaD ratio (only if base valid)
        if romad_valid:
            neighbor_romad = result.get("romad")
            if neighbor_romad is not None and math.isfinite(neighbor_romad):
                romad_ratio = neighbor_romad / base_romad
            else:
                romad_ratio = 0.0  # Treat None/invalid as complete failure
            romad_ratios.append(romad_ratio)

    n_valid = len(profit_ratios)

    # [v3 FIX D] Check for insufficient data
    if n_valid < MIN_NEIGHBORS:
        # Still compute what we can, but mark as insufficient
        status = StressTestStatus.INSUFFICIENT_DATA
    else:
        status = StressTestStatus.OK

    # If no valid results at all (all had net_profit_pct=None after worker returned)
    # [v3.1 FIX] Use n_generated for consistency with n==0 branch
    if n_valid == 0:
        return RetentionMetrics(
            status=StressTestStatus.INSUFFICIENT_DATA,
            profit_retention=None, profit_lower_tail=None, profit_median=None, profit_worst=None,
            romad_retention=None, romad_lower_tail=None, romad_median=None, romad_worst=None,
            profit_failure_rate=1.0, romad_failure_rate=None, combined_failure_rate=1.0,
            profit_failure_count=n_generated, romad_failure_count=0, combined_failure_count=n_generated,
            total_perturbations=n_generated, failure_threshold=failure_threshold,
            param_worst_ratios={}
        )

    profit_ratios = np.array(profit_ratios)

    # [v3 FIX C] Use numpy.quantile with explicit method="linear" for reproducibility
    profit_lower_tail = float(np.quantile(profit_ratios, 0.05, method="linear"))
    profit_median = float(np.quantile(profit_ratios, 0.50, method="linear"))
    profit_worst = float(np.min(profit_ratios))

    # No clipping - retention can exceed 1.0
    profit_retention = 0.5 * profit_lower_tail + 0.5 * profit_median

    # RoMaD retention (if valid)
    if romad_valid and len(romad_ratios) > 0:
        romad_ratios = np.array(romad_ratios)
        romad_lower_tail = float(np.quantile(romad_ratios, 0.05, method="linear"))
        romad_median = float(np.quantile(romad_ratios, 0.50, method="linear"))
        romad_worst = float(np.min(romad_ratios))
        romad_retention = 0.5 * romad_lower_tail + 0.5 * romad_median
    else:
        # [v3 FIX A] Invalid base romad - set to None
        romad_lower_tail = None
        romad_median = None
        romad_worst = None
        romad_retention = None

    # Calculate failure rates
    profit_failures = int(np.sum(profit_ratios < failure_threshold))
    profit_failure_rate = profit_failures / n_valid

    # [v3 FIX A] RoMaD failure handling when invalid
    if romad_valid and len(romad_ratios) > 0:
        romad_failures = int(np.sum(np.array(romad_ratios) < failure_threshold))
        romad_failure_rate = romad_failures / len(romad_ratios)

        # Combined failure: perturbation failed if EITHER metric failed
        combined_failures = 0
        for i in range(min(len(profit_ratios), len(romad_ratios))):
            profit_failed = profit_ratios[i] < failure_threshold
            romad_failed = romad_ratios[i] < failure_threshold
            if profit_failed or romad_failed:
                combined_failures += 1
        # Add any extra profit-only results
        combined_failures += sum(1 for i in range(len(romad_ratios), len(profit_ratios))
                                  if profit_ratios[i] < failure_threshold)
        combined_failure_rate = combined_failures / n_valid
    else:
        # [v3 FIX A] When RoMaD is invalid: combined = profit only
        romad_failures = 0
        romad_failure_rate = None
        combined_failures = profit_failures
        combined_failure_rate = profit_failure_rate

    # Per-parameter worst ratios
    param_worst_ratios = {
        param: float(min(ratios))
        for param, ratios in param_profit_ratios.items()
        if len(ratios) > 0
    }

    return RetentionMetrics(
        status=status,
        profit_retention=round(profit_retention, 4),
        profit_lower_tail=round(profit_lower_tail, 4),
        profit_median=round(profit_median, 4),
        profit_worst=round(profit_worst, 4),
        romad_retention=round(romad_retention, 4) if romad_retention is not None else None,
        romad_lower_tail=round(romad_lower_tail, 4) if romad_lower_tail is not None else None,
        romad_median=round(romad_median, 4) if romad_median is not None else None,
        romad_worst=round(romad_worst, 4) if romad_worst is not None else None,
        profit_failure_rate=round(profit_failure_rate, 4),
        romad_failure_rate=round(romad_failure_rate, 4) if romad_failure_rate is not None else None,
        combined_failure_rate=round(combined_failure_rate, 4),
        profit_failure_count=profit_failures,
        romad_failure_count=romad_failures,
        combined_failure_count=combined_failures,
        total_perturbations=n,
        failure_threshold=failure_threshold,
        param_worst_ratios=param_worst_ratios
    )
```

### 4.3 Post Process Workflow Integration

```python
def run_post_process(optuna_results, config):
    """
    Post Process workflow with Stress Test integration.
    """
    current_results = optuna_results

    # Step 1: DSR Analysis
    if config.dsr_enabled:
        dsr_results = run_dsr_analysis(current_results[:config.dsr_top_k], ...)
        # Re-rank by DSR probability
        dsr_results.sort(key=lambda x: x.dsr_probability, reverse=True)
        current_results = dsr_results

    # Step 2: Forward Test
    if config.ft_enabled:
        ft_results = run_forward_test(current_results[:config.ft_top_k], ...)
        # Re-rank by FT metric
        if config.ft_sort_metric == "ft_romad":
            ft_results.sort(key=lambda x: x.ft_romad or -inf, reverse=True)
        else:
            ft_results.sort(key=lambda x: x.profit_degradation, reverse=True)
        current_results = ft_results

    # Step 3: Stress Test (NEW)
    if config.stress_test_enabled:
        st_results = run_stress_test(current_results[:config.st_top_k], ...)
        # Re-rank by retention score
        # Handle None retention scores (bad base) - sort to bottom
        if config.st_sort_metric == "romad_retention":
            st_results.sort(
                key=lambda r: (r.romad_retention is not None, r.romad_retention or 0),
                reverse=True
            )
        else:  # Default: profit_retention
            st_results.sort(
                key=lambda r: (r.profit_retention is not None, r.profit_retention or 0),
                reverse=True
            )
        current_results = st_results

    return current_results  # WFA uses top-1 from this
```

---

## 5. Data Structures

### 5.1 Configuration Dataclass

**File:** `src/core/post_process.py`

```python
@dataclass
class StressTestConfig:
    """Stress Test configuration."""
    enabled: bool = False
    top_k: int = 5                          # Top candidates to test
    failure_threshold: float = 0.7          # Below this ratio = failed (0-1)
    sort_metric: str = "profit_retention"   # or "romad_retention"
    warmup_bars: int = 1000
```

### 5.2 Result Dataclass

**File:** `src/core/post_process.py`

```python
@dataclass
class StressTestResult:
    """
    Result of Stress Test for a single candidate.

    Uses "retention" terminology instead of "stability".
    Retention values can exceed 1.0 (no clipping).
    Includes status field for bad base handling.
    """
    # Identity
    trial_number: int
    source_rank: int              # Rank from input source (Optuna/DSR/FT)

    # Status for bad base handling
    status: str                   # "ok", "skipped_bad_base", "skipped_no_params", "insufficient_data"

    # Base metrics from IS re-run (not stored results)
    base_net_profit_pct: float
    base_max_drawdown_pct: float
    base_romad: Optional[float]
    base_sharpe_ratio: Optional[float]

    # Retention scores (can exceed 1.0, None if bad base)
    profit_retention: Optional[float]    # Combined: 0.5 * lower_tail + 0.5 * median
    romad_retention: Optional[float]

    # Detailed profit-based metrics
    profit_worst: Optional[float]        # min(perturbed) / base
    profit_lower_tail: Optional[float]   # 5th percentile
    profit_median: Optional[float]       # median ratio

    # Detailed RoMaD-based metrics (None if base_romad invalid)
    romad_worst: Optional[float]
    romad_lower_tail: Optional[float]
    romad_median: Optional[float]

    # Failure analysis
    profit_failure_rate: Optional[float]
    romad_failure_rate: Optional[float]  # [v3] None if romad invalid
    combined_failure_rate: float         # [v3] = profit_failure_rate if romad invalid
    profit_failure_count: int
    romad_failure_count: int             # [v3] = 0 if romad invalid
    combined_failure_count: int
    total_perturbations: int
    failure_threshold: float

    # Per-parameter sensitivity
    param_worst_ratios: dict             # {param_name: worst_profit_ratio}
    most_sensitive_param: Optional[str]  # Param with lowest worst ratio

    # Ranking
    st_rank: Optional[int] = None  # Rank after ST sorting
    rank_change: Optional[int] = None  # source_rank - st_rank
```

### 5.3 Per-Perturbation Result (internal use)

```python
@dataclass
class PerturbationResult:
    """Result of a single perturbation backtest."""
    perturbed_param: str           # Which param was changed
    direction: int                 # -1 or +1
    base_value: float              # Original value
    perturbed_value: float         # New value

    # Metrics from backtest
    net_profit_pct: float
    max_drawdown_pct: float
    romad: Optional[float]
    sharpe_ratio: Optional[float]
    total_trades: int
```

---

## 6. Implementation Details

### 6.1 Main Stress Test Function

**File:** `src/core/post_process.py`

```python
def run_stress_test(
    csv_path: str,
    strategy_id: str,
    source_results: List[Any],      # From Optuna/DSR/FT
    config: StressTestConfig,
    is_start_date: str,
    is_end_date: str,
    fixed_params: dict,
    config_json: dict,
    n_workers: int = 6
) -> Tuple[List[StressTestResult], dict]:
    """
    Run Stress Test on top-K candidates from source results.

    For each candidate, first runs a baseline IS backtest with
    identical conditions (same IS range, warmup, data prep) before running
    perturbation backtests. This ensures apple-to-apple comparison.

    Args:
        csv_path: Path to price data CSV
        strategy_id: Strategy identifier
        source_results: Results from previous PP step (sorted by their ranking)
        config: StressTestConfig with settings
        is_start_date: IS period start
        is_end_date: IS period end
        fixed_params: Non-optimizable params
        config_json: Strategy config with param definitions
        n_workers: Parallel workers for backtests

    Returns:
        Tuple of (List[StressTestResult], summary_dict)
    """
    top_k = min(config.top_k, len(source_results))
    candidates = source_results[:top_k]

    results = []

    for source_rank, candidate in enumerate(candidates, 1):
        # Extract params from candidate (format depends on source type)
        params = extract_params_from_candidate(candidate)

        # Run baseline IS backtest with SAME conditions as perturbations
        base_metrics = run_baseline_backtest(
            csv_path=csv_path,
            strategy_id=strategy_id,
            params=params,
            is_start_date=is_start_date,
            is_end_date=is_end_date,
            fixed_params=fixed_params,
            warmup_bars=config.warmup_bars
        )

        # Check for bad base - skip if profit <= 0
        if base_metrics is None or base_metrics.get("net_profit_pct", 0) <= 0:
            result = StressTestResult(
                trial_number=get_trial_number(candidate),
                source_rank=source_rank,
                status="skipped_bad_base",
                base_net_profit_pct=base_metrics.get("net_profit_pct", 0) if base_metrics else 0,
                base_max_drawdown_pct=base_metrics.get("max_drawdown_pct", 0) if base_metrics else 0,
                base_romad=base_metrics.get("romad") if base_metrics else None,
                base_sharpe_ratio=base_metrics.get("sharpe_ratio") if base_metrics else None,
                profit_retention=None,
                romad_retention=None,
                profit_worst=None, profit_lower_tail=None, profit_median=None,
                romad_worst=None, romad_lower_tail=None, romad_median=None,
                profit_failure_rate=None, romad_failure_rate=None,
                combined_failure_rate=1.0,
                profit_failure_count=0, romad_failure_count=0, combined_failure_count=0,
                total_perturbations=0,
                failure_threshold=config.failure_threshold,
                param_worst_ratios={},
                most_sensitive_param=None
            )
            results.append(result)
            continue

        # Generate perturbations (±1 step from config.json)
        perturbations = generate_perturbations(params, config_json)

        if len(perturbations) == 0:
            # No numeric optimizable params - skip
            result = StressTestResult(
                trial_number=get_trial_number(candidate),
                source_rank=source_rank,
                status="skipped_no_params",
                base_net_profit_pct=base_metrics["net_profit_pct"],
                base_max_drawdown_pct=base_metrics["max_drawdown_pct"],
                base_romad=base_metrics.get("romad"),
                base_sharpe_ratio=base_metrics.get("sharpe_ratio"),
                profit_retention=None,
                romad_retention=None,
                profit_worst=None, profit_lower_tail=None, profit_median=None,
                romad_worst=None, romad_lower_tail=None, romad_median=None,
                profit_failure_rate=None, romad_failure_rate=None,
                combined_failure_rate=1.0,
                profit_failure_count=0, romad_failure_count=0, combined_failure_count=0,
                total_perturbations=0,
                failure_threshold=config.failure_threshold,
                param_worst_ratios={},
                most_sensitive_param=None
            )
            results.append(result)
            continue

        # Run perturbation backtests in parallel
        perturbation_results = run_perturbations_parallel(
            csv_path=csv_path,
            strategy_id=strategy_id,
            perturbations=perturbations,
            is_start_date=is_start_date,
            is_end_date=is_end_date,
            fixed_params=fixed_params,
            warmup_bars=config.warmup_bars,
            n_workers=n_workers
        )

        # Calculate retention metrics
        # Pass original perturbation count for accurate reporting when some/all fail
        metrics = calculate_retention_metrics(
            base_metrics=base_metrics,
            perturbation_results=perturbation_results,
            failure_threshold=config.failure_threshold,
            total_perturbations_generated=len(perturbations)
        )

        # Find most sensitive parameter
        most_sensitive = None
        if metrics.param_worst_ratios:
            most_sensitive = min(metrics.param_worst_ratios, key=metrics.param_worst_ratios.get)

        # Create result object
        result = StressTestResult(
            trial_number=get_trial_number(candidate),
            source_rank=source_rank,
            status=metrics.status.value,
            base_net_profit_pct=base_metrics["net_profit_pct"],
            base_max_drawdown_pct=base_metrics["max_drawdown_pct"],
            base_romad=base_metrics.get("romad"),
            base_sharpe_ratio=base_metrics.get("sharpe_ratio"),
            profit_retention=metrics.profit_retention,
            romad_retention=metrics.romad_retention,
            profit_worst=metrics.profit_worst,
            profit_lower_tail=metrics.profit_lower_tail,
            profit_median=metrics.profit_median,
            romad_worst=metrics.romad_worst,
            romad_lower_tail=metrics.romad_lower_tail,
            romad_median=metrics.romad_median,
            profit_failure_rate=metrics.profit_failure_rate,
            romad_failure_rate=metrics.romad_failure_rate,
            combined_failure_rate=metrics.combined_failure_rate,
            profit_failure_count=metrics.profit_failure_count,
            romad_failure_count=metrics.romad_failure_count,
            combined_failure_count=metrics.combined_failure_count,
            total_perturbations=metrics.total_perturbations,
            failure_threshold=metrics.failure_threshold,
            param_worst_ratios=metrics.param_worst_ratios,
            most_sensitive_param=most_sensitive
        )
        results.append(result)

    # Sort by selected metric
    # Handle None retention scores - sort to bottom
    if config.sort_metric == "romad_retention":
        results.sort(
            key=lambda r: (r.romad_retention is not None, r.romad_retention or 0),
            reverse=True
        )
    else:
        results.sort(
            key=lambda r: (r.profit_retention is not None, r.profit_retention or 0),
            reverse=True
        )

    # Assign ST ranks and calculate rank change
    for idx, result in enumerate(results, 1):
        result.st_rank = idx
        result.rank_change = result.source_rank - idx

    # [v3 FIX B] Summary statistics using is not None checks
    valid_results = [r for r in results if r.status == "ok"]

    # Profit retention average
    profit_retention_vals = [r.profit_retention for r in valid_results
                            if r.profit_retention is not None]
    avg_profit_retention = (sum(profit_retention_vals) / len(profit_retention_vals)
                           if profit_retention_vals else None)

    # RoMaD retention average
    romad_retention_vals = [r.romad_retention for r in valid_results
                           if r.romad_retention is not None]
    avg_romad_retention = (sum(romad_retention_vals) / len(romad_retention_vals)
                          if romad_retention_vals else None)

    # Combined failure rate average
    combined_fr_vals = [r.combined_failure_rate for r in valid_results]
    avg_combined_failure_rate = (sum(combined_fr_vals) / len(combined_fr_vals)
                                 if combined_fr_vals else None)

    summary = {
        "candidates_tested": len(results),
        "candidates_valid": len(valid_results),
        "candidates_skipped_bad_base": sum(1 for r in results if r.status == "skipped_bad_base"),
        "candidates_skipped_no_params": sum(1 for r in results if r.status == "skipped_no_params"),
        "candidates_insufficient_data": sum(1 for r in results if r.status == "insufficient_data"),
        "total_perturbations_run": sum(r.total_perturbations for r in results),
        "avg_profit_retention": round(avg_profit_retention, 4) if avg_profit_retention is not None else None,
        "avg_romad_retention": round(avg_romad_retention, 4) if avg_romad_retention is not None else None,
        "avg_combined_failure_rate": round(avg_combined_failure_rate, 4) if avg_combined_failure_rate is not None else None,
        "failure_threshold": config.failure_threshold
    }

    return results, summary
```

### 6.2 Parallel Perturbation Execution

```python
def run_perturbations_parallel(
    csv_path: str,
    strategy_id: str,
    perturbations: List[dict],
    is_start_date: str,
    is_end_date: str,
    fixed_params: dict,
    warmup_bars: int,
    n_workers: int
) -> List[dict]:
    """
    Run perturbation backtests in parallel.

    Uses same multiprocessing pattern as Forward Test.
    Returns list of dicts with metrics + perturbation metadata.
    """
    import multiprocessing as mp

    # Prepare worker arguments
    worker_args = [
        (csv_path, strategy_id, p["params"], is_start_date, is_end_date,
         fixed_params, warmup_bars, p["perturbed_param"], p["direction"],
         p["base_value"], p["perturbed_value"])
        for p in perturbations
    ]

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=n_workers) as pool:
        results = pool.starmap(_perturbation_worker, worker_args)

    return [r for r in results if r is not None]


def _perturbation_worker(
    csv_path: str,
    strategy_id: str,
    params: dict,
    start_date: str,
    end_date: str,
    fixed_params: dict,
    warmup_bars: int,
    perturbed_param: str,
    direction: int,
    base_value: float,
    perturbed_value: float
) -> Optional[dict]:
    """
    Worker function for single perturbation backtest.
    Returns dict with metrics + perturbation metadata for aggregation.
    """
    try:
        from strategies import get_strategy_class
        from core.backtest_engine import load_data, prepare_dataset_with_warmup
        from core import metrics

        strategy_class = get_strategy_class(strategy_id)
        df = load_data(csv_path)
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            df, start_date, end_date, warmup_bars
        )

        full_params = {**fixed_params, **params}
        params_obj = strategy_class.PARAMS_CLASS(**full_params)

        result = strategy_class.run(df_prepared, params_obj, trade_start_idx)

        basic = metrics.calculate_basic(result, initial_capital=100.0)
        advanced = metrics.calculate_advanced(result)

        return {
            "perturbed_param": perturbed_param,
            "direction": direction,
            "base_value": base_value,
            "perturbed_value": perturbed_value,
            "net_profit_pct": basic.net_profit_pct,
            "max_drawdown_pct": basic.max_drawdown_pct,
            "romad": advanced.romad,
            "sharpe_ratio": advanced.sharpe_ratio,
            "total_trades": basic.total_trades
        }

    except Exception as e:
        print(f"Perturbation worker error: {e}")
        return None
```

---

## 7. UI Components

### 7.1 Results Page - Stress Test Tab (Primary Visualization)

**[v3 CLARIFIED]** The Stress Test tab displays:
1. **Same table as Optuna IS metrics** - identical columns (Net Profit %, Max DD %, Trades, Score, RoMaD, Sharpe, PF, Ulcer, SQN, Consist)
2. **Re-arranged by ST results** - sorted by retention score instead of Optuna rank
3. **Rank column shows ST rank** (not Optuna rank)
4. **[v3.2] Red Param ID** - Problematic trials (status ≠ "ok") displayed with red parameter identifier
5. **Comparison line at chart bottom** - shows ST-specific metrics when row clicked

This follows the same pattern as DSR tab.

**File:** `src/ui/templates/results.html`

Add new tab button:
```html
<button class="tab-btn" data-tab="stress_test" style="display: none;">Stress Test</button>
```

### 7.2 JavaScript - Results Page State

**File:** `src/ui/static/js/results.js`

Add to ResultsState:
```javascript
stressTest: {
  enabled: false,
  topK: null,
  trials: [],                    // StressTestResult objects (trials with st_rank)
  sortMetric: 'profit_retention',
  failureThreshold: 0.7,
  avgProfitRetention: null,
  avgRomadRetention: null,
  avgCombinedFailureRate: null,
  candidatesSkippedBadBase: 0,
  candidatesSkippedNoParams: 0,
  candidatesInsufficientData: 0
}
```

### 7.3 Data Loading - Study Load Handler

```javascript
// In loadStudyData() function, after loading trials:
const stTrials = (data.trials || []).filter((trial) =>
  trial.st_rank !== null && trial.st_rank !== undefined
);
stTrials.sort((a, b) => (a.st_rank || 0) - (b.st_rank || 0));

ResultsState.stressTest = {
  enabled: Boolean(study.st_enabled),
  topK: study.st_top_k ?? null,
  trials: stTrials,
  sortMetric: study.st_sort_metric ?? 'profit_retention',
  failureThreshold: study.st_failure_threshold ?? 0.7,
  avgProfitRetention: study.st_avg_profit_retention ?? null,
  avgRomadRetention: study.st_avg_romad_retention ?? null,
  avgCombinedFailureRate: study.st_avg_combined_failure_rate ?? null,
  candidatesSkippedBadBase: study.st_candidates_skipped_bad_base ?? 0,
  candidatesSkippedNoParams: study.st_candidates_skipped_no_params ?? 0,
  candidatesInsufficientData: study.st_candidates_insufficient_data ?? 0
};
```

### 7.4 Tab Visibility Logic

```javascript
function updateTabsVisibility() {
  // ... existing code for DSR, FT tabs ...

  const hasST = ResultsState.stressTest.enabled && ResultsState.stressTest.trials.length > 0;
  const stTab = document.querySelector('[data-tab="stress_test"]');
  if (stTab) stTab.style.display = hasST ? 'inline-flex' : 'none';

  // Fallback if active tab is hidden
  if (!hasST && ResultsState.activeTab === 'stress_test') {
    ResultsState.activeTab = 'optuna';
  }
}
```

### 7.5 Stress Test Table Rendering

**[v3.2 UPDATE]** Uses same columns as Optuna table, with red Param ID for problematic trials:

```javascript
function renderStressTestTable(trials) {
  // Use same table structure as Optuna/DSR
  const columns = OptunaResultsUI.buildTrialTableHeaders();

  const tbody = document.querySelector('#resultsTable tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  // Build Optuna rank map for comparison line
  const optunaRankMap = {};
  (ResultsState.results || []).forEach((t, i) => {
    optunaRankMap[t.trial_number] = i + 1;
  });

  trials.forEach((trial, index) => {
    const row = document.createElement('tr');
    const trialNumber = trial.trial_number;
    const stRank = trial.st_rank || index + 1;

    // Use ST rank in first column
    row.innerHTML = OptunaResultsUI.buildTrialRowHtml(trial, stRank);

    // [v3.2] Apply red color to Param ID cell for problematic trials
    const isProblematic = trial.st_status && trial.st_status !== 'ok';
    if (isProblematic) {
      const paramIdCell = row.querySelector('.param-id-cell');
      if (paramIdCell) {
        paramIdCell.style.color = '#d9534f';  // Bootstrap danger red
        paramIdCell.style.fontWeight = '500';
      }
    }

    row.classList.toggle('selected', ResultsState.selectedRowId === trialNumber);

    row.addEventListener('click', async () => {
      selectTableRow(index, trialNumber);
      showParameterDetails(trial);

      // [v3.2] Build comparison line with ST-specific metrics
      const optunaRank = optunaRankMap[trialNumber];
      const rankDelta = optunaRank ? (optunaRank - stRank) : null;

      // Handle problematic statuses with detailed messages
      if (trial.st_status === 'skipped_bad_base') {
        const baseProfit = trial.base_net_profit_pct ?? 0;
        const line = `Status: Bad Base (profit ≤ 0%) | Base Profit: ${baseProfit.toFixed(1)}%`;
        setComparisonLine(line);
      } else if (trial.st_status === 'insufficient_data') {
        const validNeighbors = trial.total_perturbations - trial.combined_failure_count;
        const line = `Status: Insufficient Data (${validNeighbors} valid neighbors, minimum 4 required) | Profit Ret: N/A | RoMaD Ret: N/A`;
        setComparisonLine(line);
      } else if (trial.st_status === 'skipped_no_params') {
        const line = `Status: No Testable Parameters (strategy has only categorical params)`;
        setComparisonLine(line);
      } else {
        // Normal status = "ok"
        const rankLine = rankDelta !== null ? `Rank: ${formatSigned(rankDelta, 0)}` : null;

        // [v3.2 UPDATE] Show both Profit Ret and RoMaD Ret
        const profitRet = trial.profit_retention;
        const profitRetLabel = profitRet !== null && profitRet !== undefined
          ? `${(profitRet * 100).toFixed(1)}%`
          : 'N/A';

        const romadRet = trial.romad_retention;
        const romadRetLabel = romadRet !== null && romadRet !== undefined
          ? `${(romadRet * 100).toFixed(1)}%`
          : 'N/A';

        // Format failure rate
        const failRate = trial.combined_failure_rate;
        const failRateLabel = failRate !== null && failRate !== undefined
          ? `${(failRate * 100).toFixed(1)}%`
          : 'N/A';

        // Label clarifies when romad is unavailable
        const romadValid = trial.romad_failure_rate !== null;
        const failRateType = romadValid ? 'Fail' : 'Fail (profit)';

        // Most sensitive param
        const sensParam = trial.most_sensitive_param || null;
        const sensLine = sensParam ? `Sens: ${sensParam}` : null;

        const line = [
          rankLine,
          `Profit Ret: ${profitRetLabel}`,
          `RoMaD Ret: ${romadRetLabel}`,
          `${failRateType}: ${failRateLabel}`,
          sensLine
        ].filter(Boolean).join(' | ');
        setComparisonLine(line);
      }

      // Fetch and render equity curve
      const equity = await fetchEquityCurve(trial);
      if (equity && equity.length) {
        renderEquityChart(equity);
      }
    });

    tbody.appendChild(row);
  });
}
```

### 7.6 Comparison Line Format

**[v3.2 UPDATE]** When a Stress Test trial row is clicked, the comparison line shows:

**For normal trials (status = "ok"):**
```
Rank: +3 | Profit Ret: 87.5% | RoMaD Ret: 82.3% | Fail: 10.0% | Sens: maLength
```

**For problematic trials:**
```
Status: Bad Base (profit ≤ 0%) | Base Profit: -5.3%
```
or
```
Status: Insufficient Data (2 valid neighbors, minimum 4 required) | Profit Ret: N/A | RoMaD Ret: N/A
```
or
```
Status: No Testable Parameters (strategy has only categorical params)
```

**Legend:**
- **Rank**: `Optuna Rank - ST Rank` (positive = moved up, better)
- **Profit Ret**: Profit retention percentage (can exceed 100%)
- **RoMaD Ret**: RoMaD retention percentage (can exceed 100%, or N/A if base RoMaD invalid)
- **Fail**: Combined failure rate (or "Fail (profit)" if RoMaD unavailable)
- **Sens**: Most sensitive parameter (if any)

### 7.7 Start Page - Stress Test Section

**File:** `src/ui/templates/index.html`

Location: Below Forward Test section, inside Post Process container.

```html
<!-- Stress Test Section -->
<div class="post-process-subsection" id="stressTestSection">
  <label class="checkbox-label">
    <input type="checkbox" id="enableStressTest" />
    <strong>Enable Parameters Stress Test</strong>
  </label>
  <p class="help-text">
    Test parameter robustness by applying small perturbations (sensitivity analysis).
  </p>

  <div id="stressTestSettings" style="display: none;">
    <div class="form-row">
      <label for="stTopK">Top Candidates:</label>
      <input type="number" id="stTopK" value="5" min="1" max="100" />
      <span class="help-text">Number of candidates to stress test</span>
    </div>

    <div class="form-row">
      <label for="stFailureThreshold">Failure Threshold (%):</label>
      <input type="number" id="stFailureThreshold" value="70" min="0" max="100" step="5" />
      <span class="help-text">Perturbations below this % of base (profit OR RoMaD) = failed</span>
    </div>

    <div class="form-row">
      <label for="stSortMetric">Sort Results By:</label>
      <select id="stSortMetric">
        <option value="profit_retention" selected>Profit Retention</option>
        <option value="romad_retention">RoMaD Retention</option>
      </select>
    </div>
  </div>
</div>
```

### 7.8 JavaScript - Start Page

**File:** `src/ui/static/js/post-process-ui.js`

```javascript
// Add to PostProcessUI object

initStressTest: function() {
  const enableCheckbox = document.getElementById('enableStressTest');
  const settingsDiv = document.getElementById('stressTestSettings');

  if (enableCheckbox && settingsDiv) {
    enableCheckbox.addEventListener('change', function() {
      settingsDiv.style.display = this.checked ? 'block' : 'none';
    });
  }
},

collectStressTestConfig: function() {
  const enabled = document.getElementById('enableStressTest')?.checked || false;

  return {
    enabled: enabled,
    topK: parseInt(document.getElementById('stTopK')?.value || '5', 10),
    failureThreshold: parseInt(document.getElementById('stFailureThreshold')?.value || '70', 10) / 100,
    sortMetric: document.getElementById('stSortMetric')?.value || 'profit_retention'
  };
}
```

---

## 8. Database Schema

**[v3] No migration needed - user will use fresh database.**

### 8.1 Studies Table Additions

**File:** `src/core/storage.py`

Add to CREATE TABLE studies statement:

```sql
st_enabled INTEGER DEFAULT 0,
st_top_k INTEGER,
st_failure_threshold REAL,
st_sort_metric TEXT,
st_avg_profit_retention REAL,
st_avg_romad_retention REAL,
st_avg_combined_failure_rate REAL,
st_total_perturbations INTEGER,
st_candidates_skipped_bad_base INTEGER,
st_candidates_skipped_no_params INTEGER,
st_candidates_insufficient_data INTEGER
```

### 8.2 Trials Table Additions

Add to CREATE TABLE trials statement:

```sql
st_rank INTEGER,
st_status TEXT,
profit_retention REAL,
romad_retention REAL,
profit_worst REAL,
profit_lower_tail REAL,
profit_median REAL,
romad_worst REAL,
romad_lower_tail REAL,
romad_median REAL,
profit_failure_rate REAL,
romad_failure_rate REAL,
combined_failure_rate REAL,
profit_failure_count INTEGER,
romad_failure_count INTEGER,
combined_failure_count INTEGER,
total_perturbations INTEGER,
st_failure_threshold REAL,
param_worst_ratios TEXT,         -- JSON: {param_name: worst_ratio}
most_sensitive_param TEXT
```

### 8.3 Save Function

```python
def save_stress_test_results(
    study_id: str,
    st_results: List[StressTestResult],
    st_summary: dict,
    config: StressTestConfig
) -> None:
    """
    Save Stress Test results to database.
    Updates both studies table (metadata) and trials table (per-trial results).
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Update studies table with ST metadata
        cursor.execute("""
            UPDATE studies SET
                st_enabled = 1,
                st_top_k = ?,
                st_failure_threshold = ?,
                st_sort_metric = ?,
                st_avg_profit_retention = ?,
                st_avg_romad_retention = ?,
                st_avg_combined_failure_rate = ?,
                st_total_perturbations = ?,
                st_candidates_skipped_bad_base = ?,
                st_candidates_skipped_no_params = ?,
                st_candidates_insufficient_data = ?
            WHERE study_id = ?
        """, (
            config.top_k,
            config.failure_threshold,
            config.sort_metric,
            st_summary.get("avg_profit_retention"),
            st_summary.get("avg_romad_retention"),
            st_summary.get("avg_combined_failure_rate"),
            st_summary.get("total_perturbations_run"),
            st_summary.get("candidates_skipped_bad_base", 0),
            st_summary.get("candidates_skipped_no_params", 0),
            st_summary.get("candidates_insufficient_data", 0),
            study_id
        ))

        # Batch update trials with ST results
        update_data = []
        for result in st_results:
            param_worst_json = json.dumps(result.param_worst_ratios) if result.param_worst_ratios else None

            update_data.append((
                result.st_rank,
                result.status,
                result.profit_retention,
                result.romad_retention,
                result.profit_worst,
                result.profit_lower_tail,
                result.profit_median,
                result.romad_worst,
                result.romad_lower_tail,
                result.romad_median,
                result.profit_failure_rate,
                result.romad_failure_rate,
                result.combined_failure_rate,
                result.profit_failure_count,
                result.romad_failure_count,
                result.combined_failure_count,
                result.total_perturbations,
                result.failure_threshold,
                param_worst_json,
                result.most_sensitive_param,
                study_id,
                result.trial_number
            ))

        cursor.executemany("""
            UPDATE trials SET
                st_rank = ?,
                st_status = ?,
                profit_retention = ?,
                romad_retention = ?,
                profit_worst = ?,
                profit_lower_tail = ?,
                profit_median = ?,
                romad_worst = ?,
                romad_lower_tail = ?,
                romad_median = ?,
                profit_failure_rate = ?,
                romad_failure_rate = ?,
                combined_failure_rate = ?,
                profit_failure_count = ?,
                romad_failure_count = ?,
                combined_failure_count = ?,
                total_perturbations = ?,
                st_failure_threshold = ?,
                param_worst_ratios = ?,
                most_sensitive_param = ?
            WHERE study_id = ? AND trial_number = ?
        """, update_data)

        conn.commit()

    finally:
        conn.close()
```

---

## 9. API Endpoints

### 9.1 Optimization Endpoint Updates

**File:** `src/ui/server.py`

Update `/api/optimize` to handle Stress Test:

```python
@app.route('/api/optimize', methods=['POST'])
def run_optimization_endpoint():
    # ... existing code ...

    # Extract Stress Test config
    st_config = post_process_payload.get("stressTest", {})
    stress_test_config = StressTestConfig(
        enabled=st_config.get("enabled", False),
        top_k=st_config.get("topK", 5),
        failure_threshold=st_config.get("failureThreshold", 0.7),
        sort_metric=st_config.get("sortMetric", "profit_retention")
    )

    # ... run Optuna, DSR, FT as before ...

    # Run Stress Test if enabled
    if stress_test_config.enabled:
        # Determine source results
        if ft_enabled and ft_results:
            source_results = ft_results
            source_type = "forward_test"
        elif dsr_enabled and dsr_results:
            source_results = dsr_results
            source_type = "dsr"
        else:
            source_results = optuna_results
            source_type = "optuna"

        st_results, st_summary = run_stress_test(
            csv_path=csv_path,
            strategy_id=strategy_id,
            source_results=source_results,
            config=stress_test_config,
            is_start_date=is_start,
            is_end_date=is_end,
            fixed_params=fixed_params,
            config_json=config_json
        )

        # Save to database
        save_stress_test_results(study_id, st_results, st_summary, stress_test_config)
```

### 9.2 Study Loading Updates

Update `/api/studies/<study_id>` - trials already include ST fields, just needs proper parsing in load function.

---

## 10. Implementation Phases

### Phase 1: Core Backend (Priority: High)

**Estimated scope:** ~450 lines of Python

1. **Data structures** (`post_process.py`)
   - Add `StressTestConfig` dataclass
   - Add `StressTestResult` dataclass with v3 fields
   - Add `RetentionMetrics` dataclass with v3 fields
   - Add `StressTestStatus` enum with `INSUFFICIENT_DATA`
   - Define `MIN_NEIGHBORS = 4` constant

2. **Baseline backtest** (`post_process.py`)
   - Implement `run_baseline_backtest()` function
   - Ensure identical IS period/warmup as perturbations

3. **Perturbation generation** (`post_process.py`)
   - Implement `generate_perturbations()` function
   - Handle int/float params, skip select/categorical
   - Respect bounds from config.json
   - Use ±1 step from config.json `optimize.step`

4. **Parallel execution** (`post_process.py`)
   - Implement `run_perturbations_parallel()`
   - Implement `_perturbation_worker()`
   - Follow existing FT multiprocessing pattern

5. **Retention calculation** (`post_process.py`)
   - Implement `calculate_retention_metrics()`
   - [v3 FIX C] Use `numpy.quantile(x, q, method="linear")`
   - [v3 FIX A] Handle invalid RoMaD with Option A logic
   - [v3 FIX D] Return `INSUFFICIENT_DATA` if `n_valid < MIN_NEIGHBORS`

6. **Main function** (`post_process.py`)
   - Implement `run_stress_test()`
   - Baseline IS re-run before perturbations
   - Status handling for skipped candidates
   - [v3 FIX B] Summary aggregation with `is not None` checks
   - Per-parameter sensitivity tracking
   - Source selection logic (FT > DSR > Optuna)
   - Ranking and summary generation

### Phase 2: Database Layer (Priority: High)

**Estimated scope:** ~150 lines of Python

1. **Schema** (`storage.py`)
   - Add ST columns to studies table CREATE statement
   - Add ST columns to trials table CREATE statement
   - (No migration needed - fresh DB)

2. **Save functions** (`storage.py`)
   - Implement `save_stress_test_results()`
   - Handle JSON serialization for `param_worst_ratios`
   - Update `save_study_to_db()` for ST metadata

3. **Load functions** (`storage.py`)
   - Update `load_study_from_db()` to include ST fields
   - Handle JSON deserialization for `param_worst_ratios`

### Phase 3: API Integration (Priority: High)

**Estimated scope:** ~100 lines of Python

1. **Optimize endpoint** (`server.py`)
   - Extract ST config from payload
   - Call `run_stress_test()` after FT
   - Save results to database

2. **Study endpoint** (`server.py`)
   - Ensure ST fields included in response
   - Include ST summary stats

### Phase 4: Frontend - Start Page (Priority: Medium)

**Estimated scope:** ~80 lines of HTML/JS

1. **HTML section** (`index.html`)
   - Add Stress Test checkbox and settings
   - Clear label about failure definition
   - Position below Forward Test

2. **JavaScript** (`post-process-ui.js`)
   - Add ST initialization
   - Add config collection function

3. **Form submission** (`ui-handlers.js`)
   - Include ST config in payload

### Phase 5: Frontend - Results Page (Priority: Medium)

**Estimated scope:** ~200 lines of JS

1. **Tab management** (`results.js`)
   - Add Stress Test tab button visibility logic
   - Add ST state to ResultsState
   - Parse ST trials from study data

2. **Table rendering** (`results.js`)
   - Implement `renderStressTestTable()` using DSR pattern
   - Same columns as Optuna, re-ranked by ST
   - Use `st_rank` in rank column
   - [v3.2] Apply red color to Param ID cell for problematic trials

3. **Comparison line** (`results.js`)
   - Build comparison line with ST metrics
   - [v3.2] Show both Profit Ret and RoMaD Ret
   - [v3.2] Show detailed status messages for problematic trials
   - Show rank change, failure rate, most sensitive param

4. **View refresh** (`results.js`)
   - Add `stress_test` case to tab switch logic
   - Update table header: "Stress Test", "Sorted by retention"

### Phase 6: Testing (Priority: High)

1. **Unit tests**
   - Test perturbation generation
   - [v3 FIX C] Test quantile calculations with `method="linear"`
   - [v3 FIX A] Test invalid RoMaD handling (Option A)
   - [v3 FIX D] Test `INSUFFICIENT_DATA` status
   - [v3 FIX B] Test summary aggregation with 0.0 values
   - Test edge cases

2. **Integration tests**
   - Test full workflow: Optuna → DSR → FT → ST
   - Test database save/load
   - Test API endpoints

---

## 11. Testing Strategy

### 11.1 Unit Tests

**File:** `tests/test_stress_test.py`

```python
import numpy as np
import math
from core.post_process import (
    generate_perturbations,
    calculate_retention_metrics,
    StressTestStatus,
    MIN_NEIGHBORS
)


def test_generate_perturbations_basic():
    """Test OAT perturbation generation."""
    base_params = {"maLength": 250, "maType": "EMA", "stopLongX": 2.0}
    config_json = {
        "parameters": {
            "maLength": {"type": "int", "optimize": {"enabled": True, "step": 25, "min": 25, "max": 500}},
            "maType": {"type": "select", "optimize": {"enabled": True}},
            "stopLongX": {"type": "float", "optimize": {"enabled": True, "step": 0.1, "min": 1.0, "max": 3.0}}
        }
    }

    perturbations = generate_perturbations(base_params, config_json)

    # Should skip maType (select), generate ±1 for maLength and stopLongX
    assert len(perturbations) == 4  # 2 params × 2 directions

    # Check maLength perturbations
    ma_perturbations = [p for p in perturbations if p["perturbed_param"] == "maLength"]
    assert len(ma_perturbations) == 2
    assert any(p["perturbed_value"] == 225 for p in ma_perturbations)
    assert any(p["perturbed_value"] == 275 for p in ma_perturbations)


def test_retention_calculation_with_quantile_method():
    """[v3 FIX C] Test percentile calculation uses method='linear'."""
    base_metrics = {"net_profit_pct": 50.0, "romad": 2.0}
    perturbation_results = [
        {"net_profit_pct": 48.0, "romad": 1.9, "perturbed_param": "maLength"},
        {"net_profit_pct": 45.0, "romad": 1.8, "perturbed_param": "maLength"},
        {"net_profit_pct": 52.0, "romad": 2.1, "perturbed_param": "stopLongX"},
        {"net_profit_pct": 30.0, "romad": 1.2, "perturbed_param": "stopLongX"},
        {"net_profit_pct": 51.0, "romad": 2.0, "perturbed_param": "closeCount"},
    ]

    metrics = calculate_retention_metrics(base_metrics, perturbation_results, failure_threshold=0.7)

    assert metrics.status == StressTestStatus.OK
    assert metrics.total_perturbations == 5

    # Verify quantile calculation with method="linear"
    expected_ratios = np.array([48/50, 45/50, 52/50, 30/50, 51/50])
    expected_5pct = np.quantile(expected_ratios, 0.05, method="linear")
    expected_median = np.quantile(expected_ratios, 0.50, method="linear")

    assert abs(metrics.profit_lower_tail - expected_5pct) < 0.001
    assert abs(metrics.profit_median - expected_median) < 0.001


def test_invalid_romad_option_a():
    """[v3 FIX A] Test that invalid base RoMaD uses Option A logic."""
    base_metrics = {"net_profit_pct": 50.0, "romad": None}  # Invalid romad
    perturbation_results = [
        {"net_profit_pct": 45.0, "romad": 1.5, "perturbed_param": "p1"},
        {"net_profit_pct": 48.0, "romad": 1.8, "perturbed_param": "p2"},
        {"net_profit_pct": 40.0, "romad": 1.2, "perturbed_param": "p3"},
        {"net_profit_pct": 52.0, "romad": 2.0, "perturbed_param": "p4"},
    ]

    metrics = calculate_retention_metrics(base_metrics, perturbation_results, failure_threshold=0.7)

    assert metrics.status == StressTestStatus.OK
    assert metrics.profit_retention is not None  # Profit still calculated

    # [v3 FIX A] Option A: RoMaD metrics are None
    assert metrics.romad_retention is None
    assert metrics.romad_failure_rate is None
    assert metrics.romad_failure_count == 0

    # [v3 FIX A] Combined = profit only
    assert metrics.combined_failure_rate == metrics.profit_failure_rate
    assert metrics.combined_failure_count == metrics.profit_failure_count


def test_insufficient_data_status():
    """[v3 FIX D] Test INSUFFICIENT_DATA when n_valid < MIN_NEIGHBORS."""
    base_metrics = {"net_profit_pct": 50.0, "romad": 2.0}
    # Only 2 valid results, less than MIN_NEIGHBORS (4)
    perturbation_results = [
        {"net_profit_pct": 48.0, "romad": 1.9, "perturbed_param": "p1"},
        {"net_profit_pct": 45.0, "romad": 1.8, "perturbed_param": "p2"},
    ]

    metrics = calculate_retention_metrics(base_metrics, perturbation_results)

    assert metrics.status == StressTestStatus.INSUFFICIENT_DATA
    # Metrics still computed, just flagged
    assert metrics.profit_retention is not None
    assert metrics.total_perturbations == 2


def test_aggregation_with_zero_values():
    """[v3 FIX B] Test that 0.0 values are not filtered out."""
    # This tests the summary aggregation logic
    # A retention of 0.0 should not be treated as falsy/missing

    base_metrics = {"net_profit_pct": 50.0, "romad": 2.0}
    # Create results where all neighbors are much worse
    perturbation_results = [
        {"net_profit_pct": 0.5, "romad": 0.1, "perturbed_param": "p1"},  # ratio = 0.01
        {"net_profit_pct": 0.5, "romad": 0.1, "perturbed_param": "p2"},
        {"net_profit_pct": 0.5, "romad": 0.1, "perturbed_param": "p3"},
        {"net_profit_pct": 0.5, "romad": 0.1, "perturbed_param": "p4"},
    ]

    metrics = calculate_retention_metrics(base_metrics, perturbation_results)

    # profit_retention should be very low but NOT None
    assert metrics.profit_retention is not None
    assert metrics.profit_retention < 0.1  # Should be very low


def test_retention_can_exceed_one():
    """Test that retention ratio can exceed 1.0 (no clipping)."""
    base_metrics = {"net_profit_pct": 50.0, "romad": 2.0}
    perturbation_results = [
        {"net_profit_pct": 60.0, "romad": 2.5, "perturbed_param": "p1"},
        {"net_profit_pct": 55.0, "romad": 2.2, "perturbed_param": "p2"},
        {"net_profit_pct": 58.0, "romad": 2.3, "perturbed_param": "p3"},
        {"net_profit_pct": 62.0, "romad": 2.6, "perturbed_param": "p4"},
    ]

    metrics = calculate_retention_metrics(base_metrics, perturbation_results)

    # All ratios > 1.0, retention should be > 1.0 (not clipped)
    assert metrics.profit_worst > 1.0
    assert metrics.profit_median > 1.0
    assert metrics.profit_retention > 1.0


def test_bad_base_profit():
    """Test handling of base profit <= 0."""
    base_metrics = {"net_profit_pct": -10.0, "romad": -0.5}
    perturbation_results = [
        {"net_profit_pct": 5.0, "romad": 0.2, "perturbed_param": "p1"},
    ]

    metrics = calculate_retention_metrics(base_metrics, perturbation_results)

    assert metrics.status == StressTestStatus.SKIPPED_BAD_BASE
    assert metrics.profit_retention is None
    assert metrics.romad_retention is None
    assert metrics.combined_failure_rate == 1.0


def test_all_perturbations_failed_is_insufficient_data():
    """
    [v3 FIX] Test that when all perturbation backtests fail (return None),
    status is INSUFFICIENT_DATA, NOT SKIPPED_NO_PARAMS.

    SKIPPED_NO_PARAMS should only be used when generate_perturbations() returns []
    (no eligible parameters). If perturbations were generated but all workers
    failed, that's a different failure mode.
    """
    base_metrics = {"net_profit_pct": 50.0, "romad": 2.0}

    # Simulate: 10 perturbations were generated, but all workers failed
    # run_perturbations_parallel filtered out all None results → empty list
    perturbation_results = []
    total_generated = 10  # We know 10 were generated

    metrics = calculate_retention_metrics(
        base_metrics,
        perturbation_results,
        failure_threshold=0.7,
        total_perturbations_generated=total_generated
    )

    # Should be INSUFFICIENT_DATA, NOT SKIPPED_NO_PARAMS
    assert metrics.status == StressTestStatus.INSUFFICIENT_DATA
    assert metrics.status != StressTestStatus.SKIPPED_NO_PARAMS

    # Should report the original count, not 0
    assert metrics.total_perturbations == 10
    assert metrics.profit_failure_count == 10  # All failed
    assert metrics.combined_failure_rate == 1.0


def test_n_valid_zero_uses_n_generated():
    """
    [v3.1 FIX G] Test that when workers return results but all have
    net_profit_pct=None (second-stage filtering), we still report
    n_generated counts, not the filtered count n.

    Scenario:
    - 20 perturbations generated
    - 15 workers return results (5 returned None, filtered by run_perturbations_parallel)
    - All 15 results have net_profit_pct=None (filtered by calculate_retention_metrics)
    - n=15, n_valid=0, n_generated=20
    - Should report total_perturbations=20, not 15
    """
    base_metrics = {"net_profit_pct": 50.0, "romad": 2.0}

    # Workers returned 15 results, but all have net_profit_pct=None
    perturbation_results = [
        {"net_profit_pct": None, "romad": 1.5, "perturbed_param": f"p{i}"}
        for i in range(15)
    ]
    total_generated = 20  # Original count was 20

    metrics = calculate_retention_metrics(
        base_metrics,
        perturbation_results,
        failure_threshold=0.7,
        total_perturbations_generated=total_generated
    )

    assert metrics.status == StressTestStatus.INSUFFICIENT_DATA
    # Should use n_generated (20), not n (15)
    assert metrics.total_perturbations == 20
    assert metrics.profit_failure_count == 20
    assert metrics.combined_failure_count == 20


def test_bounds_checking():
    """Test that perturbations respect parameter bounds."""
    base_params = {"maLength": 25}  # At minimum
    config_json = {
        "parameters": {
            "maLength": {"type": "int", "optimize": {"enabled": True, "step": 25, "min": 25, "max": 500}}
        }
    }

    perturbations = generate_perturbations(base_params, config_json)

    # Should only generate +1 step (50), not -1 step (would be 0, below min)
    assert len(perturbations) == 1
    assert perturbations[0]["perturbed_value"] == 50


def test_percentile_not_always_min():
    """[v3 FIX C] Verify 5th percentile is NOT always the minimum."""
    # With n=20 and linear interpolation, 5th percentile should interpolate
    ratios = [0.1] + [0.9] * 19  # One outlier at 0.1

    p5 = np.quantile(ratios, 0.05, method="linear")

    # 5th percentile should NOT equal min (0.1) for this distribution
    assert p5 > 0.1, f"5th percentile ({p5}) should not equal min (0.1)"
```

### 11.2 Integration Tests

```python
def test_stress_test_workflow():
    """Test full ST workflow with baseline re-run."""
    # Create mock Optuna results
    mock_results = [
        MockTrial(trial_number=1, params={"maLength": 250}, net_profit_pct=50.0),
        MockTrial(trial_number=2, params={"maLength": 200}, net_profit_pct=45.0),
    ]

    config = StressTestConfig(enabled=True, top_k=2, failure_threshold=0.7)

    results, summary = run_stress_test(
        csv_path="test_data.csv",
        strategy_id="s01_trailing_ma",
        source_results=mock_results,
        config=config,
        # ... other params
    )

    assert len(results) == 2
    assert all(r.st_rank is not None for r in results)

    # Verify baseline was re-run (base metrics populated)
    for r in results:
        if r.status == "ok":
            assert r.base_net_profit_pct is not None

    # Sorted by retention
    valid_results = [r for r in results if r.profit_retention is not None]
    if len(valid_results) >= 2:
        assert valid_results[0].profit_retention >= valid_results[1].profit_retention


def test_database_save_load():
    """Test ST results save and load from database."""
    # Save
    save_stress_test_results(study_id, st_results, st_summary, config)

    # Load
    data = load_study_from_db(study_id)

    assert data["study"]["st_enabled"] == 1
    st_trials = [t for t in data["trials"] if t.get("st_rank") is not None]
    assert len(st_trials) == len(st_results)
    assert st_trials[0]["st_rank"] == 1

    # Check v3 fields
    trial = st_trials[0]
    assert "st_status" in trial
    assert "profit_retention" in trial
    assert "combined_failure_rate" in trial
    assert "most_sensitive_param" in trial
```

---

## 12. Risks and Mitigations

### Risk 1: Computational Cost

**Risk:** Stress Test adds significant backtest runs (top-K × ~20-30 perturbations + 1 baseline per candidate).

**Mitigation:**
- Default top_k = 5 (not 20 like DSR/FT)
- Run perturbations in parallel with existing worker pool
- Consider progress indicator in UI for long-running tests
- Baseline can be parallelized with first perturbation batch

### Risk 2: Edge Cases with Few Perturbations

**Risk:** If strategy has only 1-2 numeric params, percentile calculations may be unreliable.

**Mitigation:**
- [v3 FIX D] `INSUFFICIENT_DATA` status when `n_valid < MIN_NEIGHBORS`
- [v3 FIX C] Use `numpy.quantile` with `method="linear"` for small n
- [v3.2] Red Param ID visual indicator for insufficient data
- [v3.2] Detailed status in comparison line
- Document minimum perturbation count for reliable results

### Risk 3: Bad Base Cases

**Risk:** Base profit ≤ 0 or invalid RoMaD causes misleading ratios.

**Mitigation:**
- Base profit ≤ 0: Mark as `SKIPPED_BAD_BASE`, exclude from retention ranking
- [v3 FIX A] Invalid RoMaD: Use Option A (`combined = profit only`)
- [v3.2] Red Param ID for skipped candidates
- [v3.2] Detailed status message in comparison line

### Risk 4: Aggregation Errors

**[v3 FIX B] Addressed**

**Risk:** Truthiness checks filter out valid 0.0 or negative values.

**Mitigation:**
- Use `is not None` checks instead of truthiness
- Divide by count of included items, not total valid results
- Unit test with edge case values (0.0, negative)

### Risk 5: Quantile Reproducibility

**[v3 FIX C] Addressed**

**Risk:** Different NumPy versions may use different default interpolation methods.

**Mitigation:**
- Explicitly use `np.quantile(x, q, method="linear")`
- Document the interpolation method in code comments
- Unit test verifies correct behavior

### Risk 6: Source Result Type Variations

**Risk:** Different source types (Optuna/DSR/FT) have different data structures.

**Mitigation:**
- Implement `extract_params_from_candidate()` helper with type checking
- Document expected fields from each source type
- Unit test with each source type

---

## 13. Future Considerations

### 13.1 Phase 2 Enhancements

- **Monte Carlo random perturbations**: In addition to OAT, add option for N random perturbations
- **Multi-step perturbations**: Option for ±2 steps instead of just ±1
- **Visualization**: Heatmap showing retention across parameter space
- **Enhanced per-parameter sensitivity**: histogram of ratios per param

### 13.2 Advanced Retention Metrics

- **Plateau width**: How far can each param move before performance drops 20%?
- **Gradient estimation**: Numerical derivatives of profit surface
- **Cross-parameter sensitivity**: Test pairs of parameters together

### 13.3 Integration with WFA

- **Window-level retention**: Run ST on each WFA window's best params
- **Retention-weighted WFE**: Weight WFE by retention score

### 13.4 Performance Optimizations

- **Caching**: Cache data loading across perturbations and baseline
- **Incremental ST**: Only re-run ST for new/changed candidates
- **GPU acceleration**: For strategies with heavy indicator calculations

---

## Appendix A: API Payload Format

### Start Page → Backend

```json
{
  "postProcess": {
    "dsrEnabled": true,
    "dsrTopK": 20,
    "enabled": true,
    "ftPeriodDays": 30,
    "topK": 20,
    "sortMetric": "profit_degradation",
    "stressTest": {
      "enabled": true,
      "topK": 5,
      "failureThreshold": 0.7,
      "sortMetric": "profit_retention"
    }
  }
}
```

### Backend → Results Page

```json
{
  "study": {
    "st_enabled": 1,
    "st_top_k": 5,
    "st_failure_threshold": 0.7,
    "st_sort_metric": "profit_retention",
    "st_avg_profit_retention": 0.82,
    "st_avg_romad_retention": 0.78,
    "st_avg_combined_failure_rate": 0.12,
    "st_total_perturbations": 150,
    "st_candidates_skipped_bad_base": 1,
    "st_candidates_skipped_no_params": 0,
    "st_candidates_insufficient_data": 0
  },
  "trials": [
    {
      "trial_number": 5,
      "st_rank": 1,
      "st_status": "ok",
      "profit_retention": 0.91,
      "romad_retention": 0.88,
      "combined_failure_rate": 0.05,
      "most_sensitive_param": "maLength",
      "param_worst_ratios": "{\"maLength\": 0.72, \"stopLongX\": 0.85}"
    }
  ]
}
```

---

## Appendix B: File Change Summary

| File | Changes |
|------|---------|
| `src/core/post_process.py` | Add dataclasses, main functions, baseline re-run (~450 lines) |
| `src/core/storage.py` | Add ST columns in schema, save/load functions (~150 lines) |
| `src/ui/server.py` | Update optimize endpoint (~100 lines) |
| `src/ui/templates/index.html` | Add ST section (~30 lines) |
| `src/ui/static/js/post-process-ui.js` | Add ST functions (~50 lines) |
| `src/ui/static/js/ui-handlers.js` | Add ST to payload (~10 lines) |
| `src/ui/static/js/results.js` | Add ST tab, table rendering, comparison line (~220 lines) |
| `src/ui/templates/results.html` | Add ST tab button (~5 lines) |
| `tests/test_stress_test.py` | New test file (~200 lines) |

**Total estimated new code:** ~1,220 lines

---

## Appendix C: Glossary

| Term | Definition |
|------|------------|
| **OAT** | One-At-a-Time perturbation approach |
| **Retention Score** | Metric measuring robustness (can exceed 1.0 if neighbors outperform base) |
| **Worst Ratio** | min(perturbed) / base - worst case performance retention |
| **Lower-Tail Ratio** | 5th percentile of neighbor ratios (not "95% confidence") |
| **Combined Failure Rate** | [v3] Fraction where profit OR romad failed; equals profit_failure_rate if romad invalid |
| **Source Rank** | Rank from input source (Optuna/DSR/FT) |
| **ST Rank** | Rank after Stress Test sorting |
| **Rank Change** | source_rank - st_rank (positive = improvement) |
| **Most Sensitive Param** | Parameter with lowest worst ratio |
| **MIN_NEIGHBORS** | [v3] Minimum valid perturbations for reliable statistics (default: 4) |
| **Param ID** | [v3.2] Parameter identifier displayed in table (shown in red for problematic trials) |

---

## Appendix D: Changes Summary

### v3.2 Fixes

| Fix | Change |
|-----|--------|
| **H** | UI warning display: red Param ID color instead of badges/labels; detailed status in comparison line |
| **I** | Comparison line shows both "Profit Ret: X%" and "RoMaD Ret: Y%" (not just one "Ret") |

### v3.1 Fix

| Fix | Change |
|-----|--------|
| **G** | In `n_valid==0` and `SKIPPED_BAD_BASE` branches, use `n_generated` (not `n`) for `total_perturbations` and failure counts |

### v3: From Remaining Clarifications Document

| Fix | Change |
|-----|--------|
| **A** | Invalid base RoMaD: `combined_failure_rate = profit_failure_rate`, `romad_*` fields = None/0 |
| **B** | Use `is not None` checks in aggregation, not truthiness; correct denominators |
| **C** | Use `np.quantile(x, q, method="linear")` explicitly for reproducibility |
| **D** | Define `INSUFFICIENT_DATA` status trigger when `n_valid < MIN_NEIGHBORS` (4) |
| **E** | Terminology consistency (already applied in v2) |
| **F** | `SKIPPED_NO_PARAMS` only when `len(perturbations)==0`; `INSUFFICIENT_DATA` when all backtests fail |

### User-Requested Changes

| Change | Applied |
|--------|---------|
| **No migration** | Removed all migration code; schema defined in CREATE statements |
| **UI visualization** | Clarified: Same table as Optuna IS, re-ranked by ST; comparison line at chart bottom (like DSR) |

### From v1 → v2 (Retained)

1. Baseline metrics from IS re-run, not stored results
2. "Retention ratio" / "lower-tail" terminology
3. Use `numpy.quantile()` for percentile calculation
4. Retention can exceed 1.0 (no clipping)
5. Both profit and romad failure rates + combined failure
6. Explicit bad base policy
7. Per-parameter sensitivity diagnostic

---

## References

- [Build Alpha - Robustness Testing Guide](https://www.buildalpha.com/robustness-testing-guide/)
- [StrategyQuant - Robustness Tests and Analysis](https://strategyquant.com/blog/robustness-tests-and-analysis/)
- [StrategyQuant - Monte Carlo Methods](https://strategyquant.com/blog/new-robustness-tests-on-the-strategyquant-codebase-5-monte-carlo-methods-to-bulletproof-your-trading-strategies/)
- [Adaptrade - Stress Testing for Trading Strategy Robustness](http://www.adaptrade.com/Newsletter/NL-StressTesting.htm)
- [John Ehlers - A Procedure to Evaluate Trading Strategy Robustness](https://www.mesasoftware.com/papers/ROBUSTNESS.pdf)
- [The Robust Trader - Parameter Stability](https://therobusttrader.com/parameter-stability/)

---

**End of Document**
