# Phase 1: Post Process Forward Test - Implementation Plan v4

**Date:** 2026-01-10
**Author:** Claude Opus 4.5
**Based on:** phase_1_plan_opus_v3.md + GPT 5.2 audit + additional audit fixes

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Naming Convention](#naming-convention)
3. [Database Schema](#database-schema)
4. [Module Structure](#module-structure)
5. [Implementation Details](#implementation-details)
6. [UI Changes](#ui-changes)
7. [API Endpoints](#api-endpoints)
8. [Integration Points](#integration-points)
9. [File Change Summary](#file-change-summary)
10. [Implementation Order](#implementation-order)
11. [Testing Checklist](#testing-checklist)

---

## Executive Summary

### What We're Building

**Phase 1 adds Forward Test (FT) validation to Merlin:**

1. **Auto Post Process FT** - Automatically validate top-K Optuna candidates on reserved (holdout) data after optimization
2. **Manual Test** - Test any study's params on new data from Results page (pop-up modal)
3. **WFA Integration** - Use FT internally to select better params per WFA window (no display)

### Key Design Decisions

| Decision | Choice |
|----------|--------|
| Storage approach | Extend `trials` table with `ft_` columns |
| FT sort metric | User-selectable dropdown (Profit Degradation, FT ROMAD) |
| Degradation calculation | Annualized for Profit only, raw comparison for ROMAD |
| Manual Test comparison | Context-aware: compares vs source tab (Optuna or FT metrics) |
| WFA + FT display | Use internally only, don't display FT details |
| Parallel execution | Use worker count from Main page input, follow optuna_engine pattern |
| Results page tabs | "Top Parameter Sets" → "Forward Test" → "Test Results" |
| Naming convention | "Post Process" for section, "Forward Test" for tab/feature |
| New JS file | `post-process-ui.js` (single file for both pages) |
| **Data holdout** | **TRUE HOLDOUT via date filter: shorten `fixed_params.end` so Optuna sees IS-only** |
| **FT date range** | **FT split within USER-SELECTED range (not full CSV)** |
| **Timezone handling** | **All timestamps are tz-aware UTC** |

### What's NOT in Phase 1

- Robustness score formula (skip)
- Minimum OOS trades threshold (skip)
- Regime consideration warnings (skip)
- Progress tracking for FT (skip)
- DSR, perturbation, bootstrap (Phase 2+)

### Fixes Applied (v4)

| Issue | Source | Fix |
|-------|--------|-----|
| Data leakage | GPT 5.2 1.1 | TRUE HOLDOUT via date filter: shorten `fixed_params.end`, Optuna never sees FT data |
| Timezone bug | GPT 5.2 1.2 | All timestamps use `tz="UTC"` or Merlin's `_parse_timestamp()` |
| API format mismatch | GPT 5.2 1.4 | `postProcess` config embedded in existing `config` JSON blob |
| Date range ambiguity | GPT 5.2 2.1 | Store `is_end_date` in `config_json.fixed_params.end`, add separate `ft_start_date`/`ft_end_date` |
| ROMAD sort ambiguity | GPT 5.2 2.2 | Sort by `ft_romad` (absolute), not change |
| JSON casing | GPT 5.2 2.3 | Manual test `results_json` uses snake_case (matches DB pattern) |
| FT equity curves | GPT 5.2 3.1 | On-demand via `/api/backtest` with `ft_start_date`/`ft_end_date` |
| WFA + FT algorithm | GPT 5.2 3.2 | Detailed algorithm specified |
| ProcessPoolExecutor | v3 1 | Keep ProcessPoolExecutor (compatible with Merlin) |
| FTResult missing params | v3 2 | `params: dict` field included |
| Manual tests JSON | v3 3 | Summary fields for quick display |
| FT tab no data | v3 4 | Check for actual FT results before showing tab |
| top_k > trials | v3 5 | Clamp to available trials |
| Naming conflict | v3 6 | Strategy params = camelCase, system/FT fields = snake_case |
| Manual test warmup | v3 7 | Warmup pulled from BEFORE test start date |
| Index guard | v3 8 | Validate index >= 0, raise clear error if date not found |
| IS period days | Additional | Calculate from stored `config_json.fixed_params` |
| Tab naming | Additional | "Forward Test" tab (not "Post Process") |
| Optuna API mismatch | v4 audit | Do NOT pass df_is; shorten `fixed_params.end` so Optuna loads IS-only via date filter |
| FT split range | v4 audit | Split FT within USER-SELECTED range (apply date filter first, then split) |
| Manual test context | v4 feature | Context-aware comparison: source_tab determines baseline metrics |

---

## Naming Convention

**Merlin's documented rule: "camelCase end-to-end" applies to STRATEGY PARAMETERS.**

Strategy parameters (from config.json, passed to strategy.run()) use camelCase everywhere:
- `maType`, `closeCountLong`, `rsiLen`, `stopLongMaxPct`

**System/infrastructure fields follow existing Merlin patterns:**

Looking at existing code (storage.py, optuna_engine.py), system fields use snake_case in Python/DB:
- `net_profit_pct`, `max_drawdown_pct`, `warmup_bars`, `is_period_days`

**Post Process fields follow this existing system pattern:**

| Layer | Convention | Example |
|-------|------------|---------|
| HTML form inputs | camelCase | `ftPeriodDays`, `topK`, `sortMetric` |
| JavaScript | camelCase | `ftPeriodDays`, `topK`, `sortMetric` |
| API request body | camelCase | `{ "ftPeriodDays": 30, "topK": 20 }` |
| Python variables | snake_case | `ft_period_days`, `top_k`, `sort_metric` |
| Database columns | snake_case | `ft_period_days`, `ft_net_profit_pct` |
| API response | snake_case (from DB) | `{ "ft_period_days": 30 }` |
| Manual test results_json | snake_case | `{ "net_profit_pct": 85.3 }` |

**Key distinction:**
- **Strategy params** (passed to strategy.run()): camelCase everywhere per Merlin docs
- **System/FT config fields**: snake_case in Python/DB (matches existing `warmup_bars`, `net_profit_pct`)
- **API responses**: Return DB data directly without case conversion (existing pattern)
- **Manual test results_json**: snake_case (matches DB pattern, avoids frontend mapping)

---

## Database Schema

### Schema (Fresh DB - No Migration Needed)

```sql
-- ============================================================
-- TRIALS TABLE EXTENSIONS (for Auto Post Process FT)
-- ============================================================

-- FT metrics (NULL for trials not in top-K)
ft_net_profit_pct REAL,
ft_max_drawdown_pct REAL,
ft_total_trades INTEGER,
ft_win_rate REAL,
ft_sharpe_ratio REAL,
ft_sortino_ratio REAL,
ft_romad REAL,
ft_profit_factor REAL,
ft_ulcer_index REAL,
ft_sqn REAL,
ft_consistency_score REAL,

-- Degradation metric (annualized ratio for profit)
profit_degradation REAL,

-- FT ranking (1 = best, NULL for non-tested trials)
ft_rank INTEGER,


-- ============================================================
-- STUDIES TABLE EXTENSIONS (FT configuration)
-- ============================================================

ft_enabled INTEGER DEFAULT 0,
ft_period_days INTEGER,
ft_top_k INTEGER,
ft_sort_metric TEXT,

-- Actual dates used (calculated from user input)
ft_start_date TEXT,
ft_end_date TEXT,

-- IS period info (for degradation calculation)
is_period_days INTEGER,


-- ============================================================
-- NEW TABLE: MANUAL TESTS
-- ============================================================

CREATE TABLE IF NOT EXISTS manual_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),

    -- Test configuration
    test_name TEXT,
    data_source TEXT NOT NULL,  -- 'original_csv' or 'new_csv'
    csv_path TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,

    -- Source context for comparison baseline
    source_tab TEXT NOT NULL,  -- 'optuna' or 'forward_test' - determines which metrics to compare against

    -- Summary fields for quick display (avoid JSON parsing)
    trials_count INTEGER NOT NULL,
    trials_tested_csv TEXT NOT NULL,  -- CSV string: "7,3,1"
    best_profit_degradation REAL,
    worst_profit_degradation REAL,

    -- Full results (JSON array) - uses snake_case keys
    results_json TEXT NOT NULL,

    FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_manual_tests_study ON manual_tests(study_id);
CREATE INDEX IF NOT EXISTS idx_manual_tests_created ON manual_tests(created_at DESC);
```

### Results JSON Structure (Manual Tests)

**Note on key casing:** Manual test `results_json` uses **snake_case** keys to match
existing Merlin DB/API patterns. This avoids frontend mapping complexity.

```json
{
  "config": {
    "data_source": "original_csv",
    "csv_path": "/path/to/file.csv",
    "start_date": "2025-12-01",
    "end_date": "2025-12-31",
    "period_days": 31
  },
  "results": [
    {
      "trial_number": 7,
      "original_metrics": {
        "net_profit_pct": 85.3,
        "max_drawdown_pct": 5.2,
        "total_trades": 142,
        "win_rate": 58.4,
        "sharpe_ratio": 1.52,
        "romad": 16.4,
        "profit_factor": 1.85
      },
      "test_metrics": {
        "net_profit_pct": 12.3,
        "max_drawdown_pct": 4.1,
        "total_trades": 23,
        "win_rate": 52.1,
        "sharpe_ratio": 0.92,
        "romad": 3.0,
        "profit_factor": 1.42
      },
      "comparison": {
        "rank_change": 5,
        "profit_degradation": 0.73,
        "max_dd_change": -1.1,
        "romad_change": -13.4,
        "sharpe_change": -0.60,
        "pf_change": -0.43
      }
    }
  ]
}
```

---

## Module Structure

### New File: `src/core/post_process.py`

```python
"""
Post Process module for optimization validation.

Phase 1: Forward Test (FT) implementation
- Auto FT after Optuna optimization (TRUE HOLDOUT)
- Manual testing from Results page
- WFA integration

CRITICAL: FT is a TRUE HOLDOUT test. The FT period data is NEVER
seen by Optuna during optimization. This prevents data leakage.

Future phases may add:
- Deflated Sharpe Ratio (DSR)
- Parameter perturbation
- Bootstrap confidence intervals
"""
from __future__ import annotations

import logging
import multiprocessing as mp
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from .backtest_engine import StrategyResult

logger = logging.getLogger(__name__)


# ============================================================
# Configuration Dataclasses
# ============================================================

@dataclass
class PostProcessConfig:
    """Configuration for Post Process forward test."""
    enabled: bool = False
    ft_period_days: int = 30
    top_k: int = 20
    sort_metric: str = "profit_degradation"  # or "ft_romad"
    warmup_bars: int = 1000


@dataclass
class FTResult:
    """Forward test result for a single trial."""
    trial_number: int
    optuna_rank: int
    params: dict  # Trial parameters (for WFA integration)

    # IS metrics (optimization period) - for comparison only
    is_net_profit_pct: float
    is_max_drawdown_pct: float
    is_total_trades: int
    is_win_rate: float
    is_sharpe_ratio: Optional[float]
    is_romad: Optional[float]
    is_profit_factor: Optional[float]

    # FT metrics (forward test period) - displayed in table
    ft_net_profit_pct: float
    ft_max_drawdown_pct: float
    ft_total_trades: int
    ft_win_rate: float
    ft_sharpe_ratio: Optional[float]
    ft_sortino_ratio: Optional[float]
    ft_romad: Optional[float]
    ft_profit_factor: Optional[float]
    ft_ulcer_index: Optional[float]
    ft_sqn: Optional[float]
    ft_consistency_score: Optional[float]

    # Comparison metrics (for equity chart display)
    profit_degradation: float  # annualized ratio
    max_dd_change: float
    romad_change: float
    sharpe_change: float
    pf_change: float

    # Ranking
    ft_rank: Optional[int] = None
    rank_change: Optional[int] = None  # optuna_rank - ft_rank


@dataclass
class ManualTestConfig:
    """Configuration for manual test from Results page."""
    study_id: str
    data_source: str  # 'original_csv' or 'new_csv'
    csv_path: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    trial_numbers: Optional[List[int]] = None


# ============================================================
# Timestamp Handling (Timezone-Aware)
# ============================================================

def _parse_timestamp(value: Any) -> Optional[pd.Timestamp]:
    """
    Parse timestamp to tz-aware UTC.

    Uses same pattern as optuna_engine._parse_timestamp() to ensure
    consistency with Merlin's tz-aware DataFrame index.
    """
    if value in (None, ""):
        return None
    try:
        ts = pd.Timestamp(value)
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts


# ============================================================
# Worker Function (module-level for multiprocessing)
# ============================================================

def _ft_worker_entry(
    csv_path: str,
    strategy_id: str,
    task_dict: Dict[str, Any],
    ft_start_date: str,
    ft_end_date: str,
    warmup_bars: int,
    is_period_days: int,
    ft_period_days: int,
) -> Optional[Dict[str, Any]]:
    """
    Entry point for FT worker process.

    Follows optuna_engine pattern: load data and strategy inside worker.
    """
    from .backtest_engine import load_data
    from . import metrics
    from strategies import get_strategy

    worker_logger = logging.getLogger(__name__)
    trial_number = task_dict["trial_number"]

    try:
        # Load data inside worker (avoid pickling large DataFrames)
        df = load_data(csv_path)
        strategy_class = get_strategy(strategy_id)

        # Parse timestamps as tz-aware UTC (critical for Merlin's tz-aware index)
        ft_start = _parse_timestamp(ft_start_date)
        ft_end = _parse_timestamp(ft_end_date)

        if ft_start is None or ft_end is None:
            raise ValueError(f"Invalid FT dates: start={ft_start_date}, end={ft_end_date}")

        # Get index for FT start date using tz-aware comparison
        ft_start_idx = df.index.get_indexer([ft_start], method='bfill')[0]

        # Guard against invalid index (-1 means date not found/after last index)
        if ft_start_idx < 0 or ft_start_idx >= len(df):
            raise ValueError(
                f"FT start date {ft_start_date} not found in data range "
                f"{df.index.min()} to {df.index.max()}"
            )

        # Get warmup bars before FT start
        warmup_start_idx = max(0, ft_start_idx - warmup_bars)

        df_ft_with_warmup = df.iloc[warmup_start_idx:]
        df_ft_with_warmup = df_ft_with_warmup[df_ft_with_warmup.index <= ft_end]

        # Validate we have data
        if len(df_ft_with_warmup) == 0:
            raise ValueError(f"No data in FT period {ft_start_date} to {ft_end_date}")

        # trade_start_idx skips warmup
        trade_start_idx = ft_start_idx - warmup_start_idx

        # Run strategy
        params = task_dict["params"]
        result = strategy_class.run(df_ft_with_warmup, params, trade_start_idx)

        # Calculate metrics
        basic = metrics.calculate_basic(result, 100.0)
        advanced = metrics.calculate_advanced(result, 100.0)

        ft_metrics = {
            "net_profit_pct": basic.net_profit_pct,
            "max_drawdown_pct": basic.max_drawdown_pct,
            "total_trades": basic.total_trades,
            "win_rate": basic.win_rate,
            "sharpe_ratio": advanced.sharpe_ratio,
            "sortino_ratio": advanced.sortino_ratio,
            "romad": advanced.romad,
            "profit_factor": advanced.profit_factor,
            "ulcer_index": advanced.ulcer_index,
            "sqn": advanced.sqn,
            "consistency_score": advanced.consistency_score,
        }

        # Calculate comparison metrics
        is_metrics = task_dict["is_metrics"]
        comparison = calculate_comparison_metrics(
            is_metrics, ft_metrics, is_period_days, ft_period_days
        )

        return {
            "trial_number": trial_number,
            "optuna_rank": task_dict["optuna_rank"],
            "params": params,
            "is_metrics": is_metrics,
            "ft_metrics": ft_metrics,
            "comparison": comparison,
        }

    except Exception as exc:
        worker_logger.warning(f"FT failed for trial {trial_number}: {exc}")
        return None


# ============================================================
# Core Functions
# ============================================================

def calculate_ft_dates(
    user_start: pd.Timestamp,
    user_end: pd.Timestamp,
    ft_period_days: int,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, int, int]:
    """
    Calculate IS/FT date boundaries within USER-SELECTED range.

    CRITICAL: FT is split from the END of the user-selected date range,
    NOT from the full CSV. This ensures the user's date filter is respected.

    Args:
        user_start: User-selected start date (tz-aware UTC)
        user_end: User-selected end date (tz-aware UTC)
        ft_period_days: Days to reserve for forward test

    Returns:
        (is_end, ft_start, ft_end, is_days, ft_days)

    Example:
        User selects: 2025-05-01 to 2025-09-01 (123 days)
        FT period: 30 days
        Result:
            is_end = 2025-08-02
            ft_start = 2025-08-02
            ft_end = 2025-09-01
            is_days = 93
            ft_days = 30
    """
    total_days = (user_end - user_start).days

    if ft_period_days >= total_days:
        raise ValueError(
            f"FT period ({ft_period_days} days) must be less than "
            f"user-selected range ({total_days} days). "
            f"User range: {user_start.date()} to {user_end.date()}"
        )

    # FT starts ft_period_days before user_end
    ft_start = user_end - pd.Timedelta(days=ft_period_days)

    # IS ends where FT begins
    is_end = ft_start

    is_days = (is_end - user_start).days
    ft_days = ft_period_days

    return is_end, ft_start, user_end, is_days, ft_days


def calculate_profit_degradation(
    is_profit: float,
    ft_profit: float,
    is_period_days: int,
    ft_period_days: int,
) -> float:
    """
    Calculate annualized profit degradation ratio.

    Returns ratio where 1.0 = no degradation, <1.0 = worse in FT
    """
    if is_period_days <= 0 or ft_period_days <= 0:
        return 0.0

    # Annualize both values
    is_annual = is_profit * (365 / is_period_days)
    ft_annual = ft_profit * (365 / ft_period_days)

    if is_annual <= 0:
        return 0.0

    return ft_annual / is_annual


def calculate_comparison_metrics(
    is_metrics: Dict[str, Any],
    ft_metrics: Dict[str, Any],
    is_period_days: int,
    ft_period_days: int,
) -> Dict[str, Any]:
    """
    Calculate comparison between IS and FT metrics.

    Returns dict with:
    - profit_degradation (annualized)
    - max_dd_change (raw difference)
    - romad_change (raw difference)
    - sharpe_change (raw difference)
    - pf_change (raw difference)
    """
    profit_deg = calculate_profit_degradation(
        is_metrics.get("net_profit_pct", 0),
        ft_metrics.get("net_profit_pct", 0),
        is_period_days,
        ft_period_days,
    )

    return {
        "profit_degradation": profit_deg,
        "max_dd_change": (ft_metrics.get("max_drawdown_pct") or 0) -
                         (is_metrics.get("max_drawdown_pct") or 0),
        "romad_change": (ft_metrics.get("romad") or 0) -
                        (is_metrics.get("romad") or 0),
        "sharpe_change": (ft_metrics.get("sharpe_ratio") or 0) -
                         (is_metrics.get("sharpe_ratio") or 0),
        "pf_change": (ft_metrics.get("profit_factor") or 0) -
                     (is_metrics.get("profit_factor") or 0),
    }


def run_forward_test(
    csv_path: str,
    strategy_id: str,
    optuna_results: List,
    config: PostProcessConfig,
    is_period_days: int,
    ft_period_days: int,
    ft_start_date: str,
    ft_end_date: str,
    n_workers: int = 6,
) -> List[FTResult]:
    """
    Run forward test on top-K Optuna candidates.

    Uses multiprocessing pattern from optuna_engine:
    - Pass paths/configs to workers (not DataFrames)
    - Each worker loads data independently

    Args:
        csv_path: Path to CSV file
        strategy_id: Strategy ID
        optuna_results: Sorted Optuna results (best first)
        config: FT configuration
        is_period_days: Days in IS period
        ft_period_days: Days in FT period
        ft_start_date: FT period start date (YYYY-MM-DD)
        ft_end_date: FT period end date (YYYY-MM-DD)
        n_workers: Number of parallel workers

    Returns:
        List of FTResult, sorted by sort_metric (best first)
    """
    # Clamp top_k to available trials
    top_k = min(config.top_k, len(optuna_results))
    candidates = optuna_results[:top_k]

    # Prepare tasks
    tasks = []
    for idx, candidate in enumerate(candidates):
        tasks.append({
            "trial_number": candidate.optuna_trial_number,
            "optuna_rank": idx + 1,
            "params": candidate.params,
            "is_metrics": {
                "net_profit_pct": candidate.net_profit_pct,
                "max_drawdown_pct": candidate.max_drawdown_pct,
                "total_trades": candidate.total_trades,
                "win_rate": candidate.win_rate,
                "sharpe_ratio": candidate.sharpe_ratio,
                "romad": candidate.romad,
                "profit_factor": candidate.profit_factor,
            }
        })

    # Execute in parallel using ProcessPoolExecutor
    ft_results = []

    if n_workers <= 1:
        # Single process
        for task in tasks:
            result = _ft_worker_entry(
                csv_path, strategy_id, task,
                ft_start_date, ft_end_date, config.warmup_bars,
                is_period_days, ft_period_days,
            )
            if result:
                ft_results.append(_build_ft_result(result))
    else:
        # Multi-process
        from concurrent.futures import ProcessPoolExecutor, as_completed

        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {}
            for task in tasks:
                future = executor.submit(
                    _ft_worker_entry,
                    csv_path, strategy_id, task,
                    ft_start_date, ft_end_date, config.warmup_bars,
                    is_period_days, ft_period_days,
                )
                futures[future] = task["trial_number"]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        ft_results.append(_build_ft_result(result))
                except Exception as e:
                    trial_num = futures[future]
                    logger.warning(f"FT failed for trial {trial_num}: {e}")

    # Sort and assign ranks
    ft_results = apply_ft_ranking(ft_results, config.sort_metric)

    return ft_results


def _build_ft_result(result_dict: Dict[str, Any]) -> FTResult:
    """Build FTResult from worker result dict."""
    is_m = result_dict["is_metrics"]
    ft_m = result_dict["ft_metrics"]
    comp = result_dict["comparison"]

    return FTResult(
        trial_number=result_dict["trial_number"],
        optuna_rank=result_dict["optuna_rank"],
        params=result_dict["params"],
        is_net_profit_pct=is_m.get("net_profit_pct", 0),
        is_max_drawdown_pct=is_m.get("max_drawdown_pct", 0),
        is_total_trades=is_m.get("total_trades", 0),
        is_win_rate=is_m.get("win_rate", 0),
        is_sharpe_ratio=is_m.get("sharpe_ratio"),
        is_romad=is_m.get("romad"),
        is_profit_factor=is_m.get("profit_factor"),
        ft_net_profit_pct=ft_m.get("net_profit_pct", 0),
        ft_max_drawdown_pct=ft_m.get("max_drawdown_pct", 0),
        ft_total_trades=ft_m.get("total_trades", 0),
        ft_win_rate=ft_m.get("win_rate", 0),
        ft_sharpe_ratio=ft_m.get("sharpe_ratio"),
        ft_sortino_ratio=ft_m.get("sortino_ratio"),
        ft_romad=ft_m.get("romad"),
        ft_profit_factor=ft_m.get("profit_factor"),
        ft_ulcer_index=ft_m.get("ulcer_index"),
        ft_sqn=ft_m.get("sqn"),
        ft_consistency_score=ft_m.get("consistency_score"),
        profit_degradation=comp.get("profit_degradation", 0),
        max_dd_change=comp.get("max_dd_change", 0),
        romad_change=comp.get("romad_change", 0),
        sharpe_change=comp.get("sharpe_change", 0),
        pf_change=comp.get("pf_change", 0),
    )


def apply_ft_ranking(
    ft_results: List[FTResult],
    sort_metric: str,
) -> List[FTResult]:
    """
    Sort FT results and assign ft_rank.

    sort_metric:
    - 'profit_degradation': Higher = better (less degradation)
    - 'ft_romad': Higher absolute FT ROMAD = better
    """
    if sort_metric == "profit_degradation":
        # Higher degradation ratio = better (less degradation)
        ft_results.sort(key=lambda x: x.profit_degradation, reverse=True)
    elif sort_metric == "ft_romad":
        # Higher absolute FT ROMAD = better
        ft_results.sort(key=lambda x: x.ft_romad or 0, reverse=True)

    # Assign ranks and calculate rank change
    for rank, result in enumerate(ft_results, start=1):
        result.ft_rank = rank
        result.rank_change = result.optuna_rank - rank  # positive = improved

    return ft_results


# ============================================================
# Manual Test Functions
# ============================================================

def run_manual_test(
    config: ManualTestConfig,
    trials: List[Dict],
    csv_path: str,
    strategy_id: str,
    warmup_bars: int,
    original_period_days: int,
    n_workers: int = 6,  # NOTE: Unused in Phase 1, kept for future parallelization
) -> Dict[str, Any]:
    """
    Run manual test on specified trials with new data.

    Warmup bars are pulled from BEFORE the test start date (same as FT logic).

    Note: n_workers parameter is unused in Phase 1 (single-process execution).
    Kept in signature for potential Phase 2 parallelization.

    Returns results dict ready for storage (snake_case keys).
    """
    from .backtest_engine import load_data
    from . import metrics
    from strategies import get_strategy

    # Load FULL data first (we need bars before test start for warmup)
    df_full = load_data(csv_path)
    strategy_class = get_strategy(strategy_id)

    # Determine test period boundaries (tz-aware)
    if config.start_date and config.end_date:
        test_start = _parse_timestamp(config.start_date)
        test_end = _parse_timestamp(config.end_date)
    else:
        # If no dates specified, use full dataset
        test_start = df_full.index.min()
        test_end = df_full.index.max()

    if test_start is None or test_end is None:
        raise ValueError(f"Invalid test dates: start={config.start_date}, end={config.end_date}")

    # Find test start index in full data
    test_start_idx = df_full.index.get_indexer([test_start], method='bfill')[0]

    # Guard against invalid index
    if test_start_idx < 0 or test_start_idx >= len(df_full):
        raise ValueError(
            f"Test start date {config.start_date} not found in data range "
            f"{df_full.index.min()} to {df_full.index.max()}"
        )

    # Get warmup bars BEFORE test start (from full data)
    warmup_start_idx = max(0, test_start_idx - warmup_bars)

    # Create test dataset: warmup + test period
    df_test = df_full.iloc[warmup_start_idx:]
    df_test = df_test[df_test.index <= test_end]

    if len(df_test) == 0:
        raise ValueError(f"No data in test period {config.start_date} to {config.end_date}")

    # trade_start_idx skips the warmup bars
    trade_start_idx = test_start_idx - warmup_start_idx

    # Calculate actual test period days (excluding warmup)
    df_test_only = df_test.iloc[trade_start_idx:]
    test_period_days = (df_test_only.index.max() - df_test_only.index.min()).days

    results = []
    for trial in trials:
        params = trial.get("params") or {}
        trial_number = trial.get("trial_number")

        try:
            # Run backtest (warmup already included in df_test)
            result = strategy_class.run(df_test, params, trade_start_idx)

            basic = metrics.calculate_basic(result, 100.0)
            advanced = metrics.calculate_advanced(result, 100.0)

            # Use snake_case for JSON storage (matches DB pattern)
            test_metrics = {
                "net_profit_pct": basic.net_profit_pct,
                "max_drawdown_pct": basic.max_drawdown_pct,
                "total_trades": basic.total_trades,
                "win_rate": basic.win_rate,
                "sharpe_ratio": advanced.sharpe_ratio,
                "romad": advanced.romad,
                "profit_factor": advanced.profit_factor,
            }

            original_metrics = {
                "net_profit_pct": trial.get("net_profit_pct", 0),
                "max_drawdown_pct": trial.get("max_drawdown_pct", 0),
                "total_trades": trial.get("total_trades", 0),
                "win_rate": trial.get("win_rate", 0),
                "sharpe_ratio": trial.get("sharpe_ratio"),
                "romad": trial.get("romad"),
                "profit_factor": trial.get("profit_factor"),
            }

            profit_deg = calculate_profit_degradation(
                original_metrics["net_profit_pct"],
                test_metrics["net_profit_pct"],
                original_period_days,
                test_period_days,
            )

            comparison = {
                "profit_degradation": profit_deg,
                "max_dd_change": (test_metrics["max_drawdown_pct"] or 0) -
                               (original_metrics["max_drawdown_pct"] or 0),
                "romad_change": (test_metrics["romad"] or 0) -
                               (original_metrics["romad"] or 0),
                "sharpe_change": (test_metrics["sharpe_ratio"] or 0) -
                                (original_metrics["sharpe_ratio"] or 0),
                "pf_change": (test_metrics["profit_factor"] or 0) -
                            (original_metrics["profit_factor"] or 0),
            }

            results.append({
                "trial_number": trial_number,
                "original_metrics": original_metrics,
                "test_metrics": test_metrics,
                "comparison": comparison,
            })

        except Exception as e:
            logger.warning(f"Manual test failed for trial {trial_number}: {e}")

    # Calculate summary
    if results:
        degradations = [r["comparison"]["profit_degradation"] for r in results]
        best_deg = max(degradations)
        worst_deg = min(degradations)
    else:
        best_deg = None
        worst_deg = None

    return {
        "config": {
            "data_source": config.data_source,
            "csv_path": config.csv_path,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "period_days": test_period_days,
        },
        "results": results,
        "summary": {
            "trials_count": len(results),
            "trials_tested_csv": ",".join(str(r["trial_number"]) for r in results),
            "best_profit_degradation": best_deg,
            "worst_profit_degradation": worst_deg,
        }
    }


def calculate_is_period_days(config_json: Dict[str, Any]) -> int:
    """
    Calculate IS period days from stored config.

    Used by manual test to determine original_period_days for
    degradation calculation.
    """
    fixed_params = config_json.get("fixed_params", {})
    start_str = fixed_params.get("start")
    end_str = fixed_params.get("end")

    if not start_str or not end_str:
        return 0

    start_ts = _parse_timestamp(start_str)
    end_ts = _parse_timestamp(end_str)

    if start_ts is None or end_ts is None:
        return 0

    return (end_ts - start_ts).days
```

---

## UI Changes

### Main Page: Post Process Section

**Location:** Right panel (Optimizer Run), ABOVE Walk-Forward Analysis section

**Layout:** Compact, WFA-style (parameter + input on same line, expand when checked)

```
┌─────────────────────────────────────────────────────────┐
│ Optimizer Run                                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ☐ Post Process                                          │  ← Collapsed
│                                                         │
│ ☑ Post Process                                          │  ← Expanded
│   ┌─────────────────────────────────────────────────┐   │
│   │ Forward Test Period (days): [30    ]            │   │
│   │ Top Candidates:             [20    ]            │   │
│   │ Sort FT Results By:         [▼ Profit Degradation]│ │
│   └─────────────────────────────────────────────────┘   │
│                                                         │
│ ☐ Walk-Forward Analysis                                 │
│   ...                                                   │
└─────────────────────────────────────────────────────────┘
```

**Sort FT Results By dropdown options:**
- Profit Degradation (default)
- FT ROMAD

### Results Page: Tab Structure

```
[Top Parameter Sets] [Forward Test] [Test Results]
```

**Tab visibility logic:**
- "Top Parameter Sets" - always visible
- "Forward Test" - visible if `study.ft_enabled == 1 AND any trial has ft_rank != null`
- "Test Results" - visible if manual tests exist for study

### Tab 2: Forward Test

**Table columns (same as Optuna, showing FT period metrics):**

| Param ID | Pareto | Constraints | Net Profit % | Max DD % | Trades | Score | RoMaD | Sharpe | PF | Ulcer | SQN | Consist |

**Equity Chart Panel - Comparison Line:**

At bottom of equity chart, one line with comparison metrics:

```
Rank: +5 | Profit Deg: 0.73 | Max DD: -1.1% | ROMAD: -13.4 | Sharpe: -0.60 | PF: -0.43
```

**Equity Chart Generation:**

FT equity curves are generated on-demand via `/api/backtest` with:
- Same strategy params as selected trial
- `dateFilter=true`
- `start=ft_start_date`, `end=ft_end_date` (from study)
- `warmupBars=study.warmup_bars`
- `csvPath=study.csv_file_path`

### Tab 3: Test Results

Same table structure as Forward Test.

**Context-aware comparison:**

The comparison baseline depends on which tab the Manual Test was launched from:
- **Launched from "Top Parameter Sets" tab**: Compare vs Optuna IS metrics
- **Launched from "Forward Test" tab**: Compare vs FT metrics

This is stored in `source_tab` field and displayed in Test Results:
- Header shows: "Compared against: Optuna Results" or "Compared against: Forward Test Results"
- Comparison line shows degradation vs the appropriate baseline metrics

This provides intuitive, consistent behavior: users always compare Manual Test results
against the metrics they were looking at when they clicked the button.

### Manual Test Modal

**Button name:** "Manual Test"

**Button location:** Top-right of Results page, before "Download Trades"

**Note:** The button is visible on both "Top Parameter Sets" and "Forward Test" tabs.
The current active tab is automatically recorded as `source_tab` for comparison context.

```
┌─────────────────────────────────────────────────────────────┐
│ Test Parameters on New Data                             [X] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Data Source                                                 │
│ ○ Original CSV                                              │
│ ● New CSV: [Choose File] filename.csv                       │
│                                                             │
│ Date Range                                                  │
│ Start: [2025-12-01]    End: [2025-12-31]                    │
│                                                             │
│ ─────────────────────────────────────────────────────────── │
│                                                             │
│ Trials to Test                                              │
│ ○ Top Rank: [10]                                            │
│ ○ Use Selected (Trial #7)                                   │
│                                                             │
│                                [Cancel]  [Run Test]         │
└─────────────────────────────────────────────────────────────┘
```

**Ranking is context-aware based on source tab:**
- From "Top Parameter Sets" tab: "Top Rank" uses Optuna ranking
- From "Forward Test" tab: "Top Rank" uses FT ranking

This keeps the UI simple while maintaining consistent behavior with the comparison baseline.

---

## API Endpoints

### Modified Endpoints

#### `POST /api/optimize`

**Request format:** Multipart form data (existing pattern)

- `config` field contains JSON string with new `postProcess` key:

```json
{
  "enabled_params": {...},
  "param_ranges": {...},
  "fixed_params": {...},
  "objectives": [...],
  "postProcess": {
    "enabled": true,
    "ftPeriodDays": 30,
    "topK": 20,
    "sortMetric": "profit_degradation"
  }
}
```

**Server-side behavior when FT enabled:**

1. Parse `postProcess` config (camelCase → snake_case)
2. Get user-selected date range from `fixed_params.start` and `fixed_params.end`
3. Call `calculate_ft_dates()` to compute IS/FT boundaries within user range
4. **CRITICAL**: Update `fixed_params["end"]` to IS end date (shortening the range)
5. Call `run_optimization()` normally - it loads CSV and respects `fixed_params` dates
6. After optimization completes, call `run_forward_test()` on FT period
7. Store FT results in trials table
8. Store `ft_start_date`, `ft_end_date`, `is_period_days` in studies table

**Key insight**: We do NOT pass a pre-sliced DataFrame to Optuna. Instead, we shorten
`fixed_params.end` so that when Optuna loads the CSV and applies date filtering,
it automatically sees only the IS period. This is compatible with existing Optuna API.

#### `POST /api/walkforward`

**Request body additions (in config JSON):**

```json
{
  "postProcess": {
    "enabled": true,
    "ftPeriodDays": 15,
    "topK": 5,
    "sortMetric": "profit_degradation"
  }
}
```

**WFA + FT Integration Algorithm:**

When FT enabled for WFA:
1. For each window:
   a. Split IS period: `[is_start, is_end - ft_period_days]` = training, rest = FT holdout
   b. Run Optuna on training portion only
   c. Run FT on holdout portion
   d. Select best params by FT ranking (not IS ranking)
   e. Use selected params for OOS evaluation
2. No FT details stored/displayed (internal use only)
3. If window too small for FT, skip FT and use IS-best params

#### `GET /api/studies/<study_id>`

**Response additions:**

```json
{
  "study": {
    "ft_enabled": 1,
    "ft_period_days": 30,
    "ft_top_k": 20,
    "ft_sort_metric": "profit_degradation",
    "ft_start_date": "2025-10-24",
    "ft_end_date": "2025-11-22",
    "is_period_days": 175
  },
  "trials": [
    {
      "ft_net_profit_pct": 62.1,
      "ft_max_drawdown_pct": 6.8,
      "ft_total_trades": 23,
      "profit_degradation": 0.73,
      "ft_rank": 1
    }
  ],
  "manual_tests": [
    {
      "id": 1,
      "created_at": "2025-12-15T10:30:00Z",
      "data_source": "original_csv",
      "start_date": "2025-12-01",
      "end_date": "2025-12-31",
      "source_tab": "optuna",
      "trials_count": 3,
      "trials_tested_csv": "7,3,1",
      "best_profit_degradation": 0.73,
      "worst_profit_degradation": 0.48
    }
  ]
}
```

### New Endpoints

#### `POST /api/studies/<study_id>/test`

Run manual test.

**Request body:**
```json
{
  "dataSource": "original_csv",
  "csvPath": null,
  "startDate": "2025-12-01",
  "endDate": "2025-12-31",
  "trialNumbers": [7, 3, 1],
  "sourceTab": "optuna"
}
```

The `sourceTab` field is required and must be either `"optuna"` or `"forward_test"`.
It determines which baseline metrics to use for comparison:
- `"optuna"`: Compare against Optuna IS metrics (net_profit_pct, romad, etc.)
- `"forward_test"`: Compare against FT metrics (ft_net_profit_pct, ft_romad, etc.)

**Response:**
```json
{
  "status": "success",
  "test_id": 1,
  "summary": {
    "trials_count": 3,
    "best_profit_degradation": 0.73,
    "worst_profit_degradation": 0.48
  }
}
```

#### `GET /api/studies/<study_id>/tests`

List manual tests for study.

#### `GET /api/studies/<study_id>/tests/<test_id>`

Get full manual test results (with results_json).

#### `DELETE /api/studies/<study_id>/tests/<test_id>`

Delete a manual test.

---

## Integration Points

### 1. Optuna Engine Integration

**File:** `src/core/optuna_engine.py`

**Changes:**
- **No changes required to optuna_engine.py**
- FT integration happens in server.py by modifying `fixed_params.end` BEFORE calling `run_optimization()`
- This works because `run_optimization()` already loads the CSV and respects `fixed_params.start/end` date filtering
- We do NOT pass a pre-sliced DataFrame; we simply shorten the date range

### 2. Server Integration (Main FT Logic)

**File:** `src/ui/server.py`

**Changes to `/api/optimize`:**

```python
# Parse postProcess config
post_process_config = config_payload.get("postProcess", {})
ft_enabled = post_process_config.get("enabled", False)

# Store original user dates for reference
original_user_start = config_payload["fixed_params"].get("start")
original_user_end = config_payload["fixed_params"].get("end")

if ft_enabled:
    from core.post_process import (
        PostProcessConfig, calculate_ft_dates, run_forward_test, _parse_timestamp
    )

    # Get user-selected date range (NOT full CSV range)
    user_start = _parse_timestamp(original_user_start)
    user_end = _parse_timestamp(original_user_end)

    if user_start is None or user_end is None:
        # If no date filter, use full CSV range
        df_temp = load_data(data_source)
        user_start = df_temp.index.min()
        user_end = df_temp.index.max()

    # Calculate IS/FT boundaries within user-selected range
    ft_period_days = int(post_process_config.get("ftPeriodDays", 30))
    is_end, ft_start, ft_end, is_days, ft_days = calculate_ft_dates(
        user_start, user_end, ft_period_days
    )

    # CRITICAL: Shorten fixed_params.end to IS end date BEFORE building OptimizationConfig
    # This ensures Optuna sees ONLY the IS period when it loads the CSV
    config_payload["fixed_params"]["end"] = is_end.isoformat()

# Build OptimizationConfig from (possibly modified) config_payload
# Uses existing helper function pattern from server.py
optimization_config = _build_optimization_config(config_payload, data_source, ...)
optuna_config = _build_optuna_config(config_payload, ...)

# Run optimization - uses OptimizationConfig which now has shortened end date
results, study_id = run_optuna_optimization(optimization_config, optuna_config)

if ft_enabled:
    # After optimization completes, run FT on the holdout period
    pp_config = PostProcessConfig(
        enabled=True,
        ft_period_days=ft_days,
        top_k=int(post_process_config.get("topK", 20)),
        sort_metric=post_process_config.get("sortMetric", "profit_degradation"),
        warmup_bars=warmup_bars,
    )

    ft_results = run_forward_test(
        csv_path=data_path,
        strategy_id=strategy_id,
        optuna_results=results,
        config=pp_config,
        is_period_days=is_days,
        ft_period_days=ft_days,
        ft_start_date=ft_start.strftime("%Y-%m-%d"),
        ft_end_date=ft_end.strftime("%Y-%m-%d"),
        n_workers=worker_processes,
    )

    # Update trials with FT data
    # ... (save FT results to DB)
```

**Key point:** The `fixed_params["end"]` mutation happens BEFORE `_build_optimization_config()`
is called, so the resulting `OptimizationConfig` instance contains the shortened IS end date.

### 3. WFA Engine Integration

**File:** `src/core/walkforward_engine.py`

**Changes:**
- Accept `PostProcessConfig` in WFA config
- Per window: split IS into training + FT holdout
- Run Optuna on training portion
- Run FT on holdout portion
- Select params by FT ranking (use `ft_results[0].params`)
- No FT display in results

### 4. Storage Integration

**File:** `src/core/storage.py`

**Changes:**
- Add new columns to schema (as specified in Database Schema section)
- Update `save_optuna_study_to_db()` to save FT config and results
- Add `save_manual_test_to_db()` with summary fields
- Update `load_study_from_db()` to load manual_tests (without results_json for list view)
- Add `load_manual_test_results()` for full results

---

## File Change Summary

| File | Changes |
|------|---------|
| `src/core/post_process.py` | **NEW FILE** |
| `src/core/storage.py` | Schema + save/load functions |
| `src/core/optuna_engine.py` | No changes (FT handled in server.py) |
| `src/core/walkforward_engine.py` | FT per window, use params field |
| `src/ui/server.py` | Parse config, TRUE HOLDOUT split, new endpoints |
| `src/ui/templates/index.html` | Post Process section |
| `src/ui/templates/results.html` | Tabs, modal |
| `src/ui/static/js/post-process-ui.js` | **NEW FILE** |
| `src/ui/static/js/main.js` | Import post-process-ui |
| `src/ui/static/js/results.js` | Tab switching, FT display logic, on-demand equity |
| `src/ui/static/js/api.js` | Manual test API calls |
| `src/ui/static/css/style.css` | Tabs, modal, comparison line styles |

---

## Implementation Order

### Step 1: Database Schema
1. Add new columns and table to `storage.py` `_create_schema()`
2. Delete old studies.db (fresh start)
3. Test schema creation

### Step 2: Core Module
1. Create `src/core/post_process.py`
2. Implement all functions with:
   - tz-aware timestamp handling
   - TRUE HOLDOUT split
   - worker pattern
3. Unit tests

### Step 3: Storage Integration
1. Save/load functions for FT and manual tests
2. Test round-trip

### Step 4: Server Integration (Optuna + FT)
1. Parse `postProcess` config from existing `config` JSON blob
2. Implement TRUE HOLDOUT: split data, run Optuna on IS-only
3. Call post_process after optimization
4. Store `is_period_days` for degradation calculation
5. Test Optuna + FT flow

### Step 5: Main Page UI
1. Post Process section (WFA-style)
2. `post-process-ui.js`
3. Test form submission

### Step 6: Results Page - Forward Test Tab
1. Tab structure with visibility check (tab name: "Forward Test")
2. FT table display
3. On-demand equity chart via `/api/backtest`
4. Comparison line on equity chart

### Step 7: Manual Test Feature
1. Modal UI
2. API endpoints
3. Test Results tab
4. `calculate_is_period_days()` for degradation

### Step 8: WFA Integration
1. FT per window (training/holdout split within IS)
2. Use FT-best params for OOS
3. Handle small windows gracefully
4. Test WFA + FT

### Step 9: Final Testing

---

## Testing Checklist

### Unit Tests

- [ ] `calculate_ft_dates()` - correct IS/FT boundary calculation within user range
- [ ] `calculate_ft_dates()` - error when FT period >= user range
- [ ] `_parse_timestamp()` - handles all input formats, returns tz-aware UTC
- [ ] `calculate_profit_degradation()` - correct annualized ratio
- [ ] `calculate_comparison_metrics()` - correct raw differences
- [ ] `_ft_worker_entry()` - loads data, handles tz-aware dates, runs backtest
- [ ] `run_forward_test()` - parallel execution, clamps top_k
- [ ] `calculate_is_period_days()` - extracts days from config_json
- [ ] Storage round-trip for FT data
- [ ] Storage round-trip for manual tests with summary fields and source_tab

### Integration Tests

- [ ] Optuna + FT enabled (TRUE HOLDOUT verified)
- [ ] Optuna + FT disabled (unchanged behavior)
- [ ] WFA + FT enabled (uses FT-best params)
- [ ] WFA + FT disabled (unchanged behavior)
- [ ] Manual test with original CSV
- [ ] Manual test with new CSV
- [ ] Manual test with selected trial only
- [ ] On-demand FT equity chart generation

### Edge Cases

- [ ] FT period longer than user-selected range (error with clear message)
- [ ] FT period longer than full CSV when no date filter (error)
- [ ] No trades in FT period (handle gracefully)
- [ ] All FT candidates fail (no tab shown, study saved)
- [ ] top_k > available trials (clamped)
- [ ] Manual test with no trials selected (error)
- [ ] FT start date after data end (clear error, not silent bad results)
- [ ] Manual test start date before CSV start (uses available warmup)
- [ ] Manual test warmup correctly pulled from before test start
- [ ] WFA window too small for FT (skip FT, use IS-best)
- [ ] Tz-naive input dates (correctly converted to UTC)
- [ ] No user date filter (FT split uses full CSV range as fallback)
- [ ] Manual test from Forward Test tab uses FT metrics as baseline
- [ ] Manual test from Optuna tab uses IS metrics as baseline

### UI Tests

- [ ] Post Process section collapse/expand
- [ ] Tab visibility based on ft_rank presence
- [ ] Tab named "Forward Test" (not "Post Process")
- [ ] Comparison line on equity chart
- [ ] "Manual Test" button visible on both tabs
- [ ] Manual Test modal opens with correct source_tab context
- [ ] Test Results tab displays correct comparison baseline header
- [ ] Test Results comparison uses correct metrics based on source_tab

### Data Leakage Verification

- [ ] **CRITICAL**: Verify Optuna never sees FT period data
- [ ] `fixed_params.end` is shortened to IS end BEFORE calling `run_optimization()`
- [ ] FT split happens within user-selected range (not full CSV)
- [ ] `config_json.fixed_params.end` stores IS end date (not original user end)
- [ ] FT period dates stored separately in `ft_start_date`/`ft_end_date`
- [ ] Original user end date is recoverable from `ft_end_date` field

---

**End of Implementation Plan v4**
