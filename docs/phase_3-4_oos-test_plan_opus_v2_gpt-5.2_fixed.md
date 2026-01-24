# Phase 3-4: Out-of-Sample Test Module (v2 — GPT-5.2 fixed)

## Changelog (v2 → GPT-5.2 fixed)

- **Fixed date boundary semantics (inclusive ends, zero overlap):** Replaced the “exclusive internal ends” design with Merlin’s current **inclusive end** slicing model and computed boundaries so **IS ends the day before FT starts**, and **FT ends the day before OOS starts**. This eliminates leakage without refactoring the backtest slicers.
- **Fixed `_set_optimization_state` usage:** Updated server integration examples to match the repo’s real `_set_optimization_state(payload_dict)` signature.
- **Fixed candidate selection field/type mismatches:** Updated candidate selection to use real dataclasses/fields (`StressTestResult.status`, etc.), and clarified DB vs in-memory selection paths.
- **Fixed multi-objective fallback:** Replaced “sort by primary objective” fallback with a multi-objective-safe selection method that mirrors Merlin’s existing DB ordering (Pareto/constraints + primary objective tie-break).
- **Fixed schema consistency:** Removed OOS “change” columns from the DB schema (UI computes deltas like FT). Kept only OOS raw metrics + degradation ratio + rank + source tracking (consistent with existing FT persistence).
- **Fixed naming collision with WFA:** Renamed all new study/trial columns from `oos_*` to `oos_test_*` to avoid confusion with existing WFA `wfa_windows.oos_*` columns.

---

## Overview

Add a new **Out-of-Sample (OOS) Test** feature that performs final validation of optimization results on a reserved portion of the dataset. This provides a true holdout test after all Post Process filtering stages (DSR, Forward Test, Stress Test) have been completed.

### Key Differences from Existing Features

| Feature | Purpose | When Executed | Data Source |
|---------|---------|---------------|-------------|
| **Forward Test** | Filter candidates during optimization | After Optuna, before final ranking | FT period (cut from end of remaining data) |
| **Manual Test** | Ad-hoc testing from Results page | User-triggered | User-selected period |
| **OOS Test (NEW)** | Final validation of filtered winners | After all Post Process stages | **Final holdout period at dataset end** |
| **Walk-Forward** | Rolling IS/OOS optimization | Instead of Optuna | Multiple rolling windows |

---

## Architecture

### Data Period Splitting (inclusive ends, no overlap)

When both Forward Test and OOS Test are enabled, periods are cut in this order:

1) Cut **OOS Test** period from the very end of the dataset (holdout test)  
2) Cut **Forward Test** period from what remains (validation)  
3) Remaining front segment is **In-Sample (IS)** optimization window (training)

**IMPORTANT: Merlin’s current slicing behavior is end-inclusive.** To prevent leakage without refactoring slicers, we enforce **non-overlap** by placing boundaries on different days:

- `is_end = ft_start - 1 day`  
- `ft_end = oos_start - 1 day`  
- `oos_end = user_end` (last bar/day of the selected dataset range)

Example (calendar-day illustration):

```
Full Dataset: 2025-05-01 → 2025-11-20  (inclusive end)
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Cut OOS Test period from END (e.g., 30 days)            │
│ OOS Period: 2025-10-22 → 2025-11-20 (inclusive)                 │
│ Remaining End becomes: 2025-10-21                               │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Cut FT period from REMAINING (e.g., 15 days)            │
│ FT Period: 2025-10-07 → 2025-10-21 (inclusive)                  │
│ Remaining End becomes: 2025-10-06                               │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Remaining = IS Period for optimization                  │
│ IS Period: 2025-05-01 → 2025-10-06 (inclusive)                  │
└─────────────────────────────────────────────────────────────────┘
```

**Non-overlapping guarantee (inclusive ranges):**
- IS: `[is_start, is_end]`
- FT: `[ft_start, ft_end]`
- OOS: `[oos_start, oos_end]`

No bar/day is included in more than one period because each boundary day belongs to exactly one period.

### Candidate Source Logic

OOS Test takes top-K candidates from the **last active Post Process module that has results**.

Rules:
1. Check that results actually exist, not just that the module flag is enabled.
2. If sourcing from Stress Test, filter out candidates with `status != "ok"`.
3. When sourcing from Stress Test, **rehydrate `params`** from the DB (`trials.params_json`) because `StressTestResult` does not store params.

Pseudo-code (uses real field names / dataclasses):

```python
from typing import List, Optional, Tuple, Dict, Any
from core.post_process import DSRResult, FTResult, StressTestResult
from core.storage import get_study_trial, load_study_from_db

@dataclass
class OOSTestCandidate:
    trial_number: int
    params: Dict[str, Any]
    source_module: str        # "stress_test" | "forward_test" | "dsr" | "optuna"
    source_rank: int          # rank within the source module
    is_metrics: Dict[str, Any]  # IS metrics for comparison (from DB or source result)

def get_oos_test_candidates(
    study_id: str,
    top_k: int,
    dsr_results: Optional[List[DSRResult]],
    ft_results: Optional[List[FTResult]],
    st_results: Optional[List[StressTestResult]],
) -> Tuple[List[OOSTestCandidate], str]:

    if st_results:
        valid = [r for r in st_results if getattr(r, "status", None) == "ok"]
        valid = valid[:top_k]
        candidates = []
        for idx, r in enumerate(valid, 1):
            trial = get_study_trial(study_id, int(r.trial_number))
            if not trial or not trial.get("params"):
                # Skip if params missing; mirror Stress Test skipping behavior
                continue
            candidates.append(OOSTestCandidate(
                trial_number=int(r.trial_number),
                params=dict(trial["params"]),
                source_module="stress_test",
                source_rank=int(getattr(r, "st_rank", None) or idx),
                is_metrics={
                    "net_profit_pct": trial.get("net_profit_pct", 0.0),
                    "max_drawdown_pct": trial.get("max_drawdown_pct", 0.0),
                    "total_trades": trial.get("total_trades", 0),
                    "win_rate": trial.get("win_rate", 0.0),
                    "max_consecutive_losses": trial.get("max_consecutive_losses", 0),
                    "sharpe_ratio": trial.get("sharpe_ratio"),
                    "romad": trial.get("romad"),
                    "profit_factor": trial.get("profit_factor"),
                },
            ))
        return candidates, "stress_test"

    if ft_results:
        chosen = ft_results[:top_k]
        return [
            OOSTestCandidate(
                trial_number=int(r.trial_number),
                params=dict(r.params),
                source_module="forward_test",
                source_rank=int(r.ft_rank or r.source_rank),
                is_metrics={
                    "net_profit_pct": r.is_net_profit_pct,
                    "max_drawdown_pct": r.is_max_drawdown_pct,
                    "total_trades": r.is_total_trades,
                    "win_rate": r.is_win_rate,
                    "max_consecutive_losses": r.is_max_consecutive_losses,
                    "sharpe_ratio": r.is_sharpe_ratio,
                    "romad": r.is_romad,
                    "profit_factor": r.is_profit_factor,
                },
            )
            for r in chosen
        ], "forward_test"

    if dsr_results:
        chosen = dsr_results[:top_k]
        return [
            OOSTestCandidate(
                trial_number=int(r.trial_number),
                params=dict(r.params),
                source_module="dsr",
                source_rank=int(r.dsr_rank or r.optuna_rank),
                is_metrics={},  # Load from DB if needed for consistency
            )
            for r in chosen
        ], "dsr"

    # Fallback: use Merlin’s DB ordering (single OR multi-objective safe)
    study_data = load_study_from_db(study_id) or {}
    trials = list(study_data.get("trials") or [])[:top_k]
    return [
        OOSTestCandidate(
            trial_number=int(t["trial_number"]),
            params=dict(t.get("params") or {}),
            source_module="optuna",
            source_rank=i + 1,
            is_metrics={
                "net_profit_pct": t.get("net_profit_pct", 0.0),
                "max_drawdown_pct": t.get("max_drawdown_pct", 0.0),
                "total_trades": t.get("total_trades", 0),
                "win_rate": t.get("win_rate", 0.0),
                "max_consecutive_losses": t.get("max_consecutive_losses", 0),
                "sharpe_ratio": t.get("sharpe_ratio"),
                "romad": t.get("romad"),
                "profit_factor": t.get("profit_factor"),
            },
        )
        for i, t in enumerate(trials)
    ], "optuna"
```

### Execution Workflow

```
1. Calculate period dates (IS, FT, OOS) - BEFORE optimization
         ↓
2. Optuna optimization on IS period
         ↓
3. DSR Analysis (if enabled)
         ↓
4. Forward Test on FT period (if enabled)
         ↓
5. Stress Test (if enabled)
         ↓
6. OOS Test on OOS period (if enabled)  ← NEW STAGE
         ↓
7. Save results to database
         ↓
8. Display in Results page "OOS Test" tab
```

**CRITICAL:** Period splitting must happen if **OOS Test OR Forward Test** is enabled (not only FT).

### Mutual Exclusion with WFA

OOS Test and Walk-Forward Analysis (WFA) are mutually exclusive:
- When OOS Test checkbox is enabled → WFA checkbox is disabled
- When WFA checkbox is enabled → OOS Test checkbox is disabled

---

## Database Schema Changes

### Table: `studies`

Add columns (use `oos_test_*` prefix to avoid WFA `oos_*` collisions):

```sql
oos_test_enabled INTEGER DEFAULT 0,
oos_test_period_days INTEGER,
oos_test_top_k INTEGER,
oos_test_start_date TEXT,
oos_test_end_date TEXT,
oos_test_source_module TEXT  -- "optuna" | "dsr" | "forward_test" | "stress_test"
```

### Table: `trials`

Add columns (match FT persistence pattern: store raw metrics + degradation ratio + rank; UI computes deltas):

```sql
-- OOS Test metrics (parallel to FT columns)
oos_test_net_profit_pct REAL,
oos_test_max_drawdown_pct REAL,
oos_test_total_trades INTEGER,
oos_test_win_rate REAL,
oos_test_max_consecutive_losses INTEGER,
oos_test_sharpe_ratio REAL,
oos_test_sortino_ratio REAL,
oos_test_romad REAL,
oos_test_profit_factor REAL,
oos_test_ulcer_index REAL,
oos_test_sqn REAL,
oos_test_consistency_score REAL,

-- Comparison metric (same convention as FT: annualized ratio)
oos_test_profit_degradation REAL,

-- Ranking and source tracking
oos_test_rank INTEGER,
oos_test_source TEXT,         -- which module provided this candidate
oos_test_source_rank INTEGER   -- rank within that module
```

**Note:** OOS “change” metrics (max_dd_change, romad_change, etc.) are **not stored** (consistent with FT). They are computed in the UI from IS vs OOS columns.

---

## Data Structures

### Configuration

```python
@dataclass
class OOSTestConfig:
    enabled: bool
    period_days: int   # Test Period (days)
    top_k: int         # Top Candidates
```

### Results

```python
@dataclass
class OOSTestResult:
    trial_number: int

    source_module: str  # "optuna" | "dsr" | "forward_test" | "stress_test"
    source_rank: int

    # OOS raw metrics
    oos_test_net_profit_pct: float
    oos_test_max_drawdown_pct: float
    oos_test_total_trades: int
    oos_test_win_rate: float
    oos_test_max_consecutive_losses: int
    oos_test_sharpe_ratio: Optional[float]
    oos_test_sortino_ratio: Optional[float]
    oos_test_romad: Optional[float]
    oos_test_profit_factor: Optional[float]
    oos_test_ulcer_index: Optional[float]
    oos_test_sqn: Optional[float]
    oos_test_consistency_score: Optional[float]

    # Comparison metric (ratio)
    oos_test_profit_degradation: float

    # Rank (default: by degradation descending)
    oos_test_rank: int
```

### PeriodDates

```python
@dataclass
class PeriodDates:
    """Calculated period boundaries (all inclusive)."""
    is_start: str              # Inclusive
    is_end: str                # Inclusive (last bar/day of IS)
    ft_start: Optional[str]    # Inclusive (None if FT disabled)
    ft_end: Optional[str]      # Inclusive (None if FT disabled)
    oos_start: Optional[str]   # Inclusive (None if OOS disabled)
    oos_end: Optional[str]     # Inclusive (None if OOS disabled)
    is_days: int
    ft_days: int
    oos_days: int
```

---

## Implementation Plan

### Phase 3-4-1: Database Schema Update

**Files:** `src/core/storage.py`

1. Add `oos_test_*` columns to `studies` table schema in `_create_schema()`
2. Add `oos_test_*` columns to `trials` table schema in `_create_schema()`
3. Add `oos_test_*` columns to `_ensure_columns()` for robustness
4. Add `save_oos_test_results()` function (parallel to `save_forward_test_results()`)
5. Add `load_oos_test_results()` function (parallel to `load_forward_test_results()` patterns, if needed)
6. Update `load_study_from_db()` to include OOS Test fields in returned JSON

**Testing:**
- Verify new columns are created correctly
- Test save/load round-trip for OOS Test results

### Phase 3-4-2: Period Calculation Logic

**Files:** `src/core/post_process.py`

1. Create new `calculate_period_dates()` function (do not modify existing `calculate_ft_dates()`)
2. Implement **inclusive end** boundaries matching current slicers
3. Ensure non-overlap by subtracting one day between period endpoints
4. Validate minimum IS length (reject if IS becomes empty/negative)
5. Return `PeriodDates` dataclass with all boundaries

**New function:**
```python
def calculate_period_dates(
    user_start: pd.Timestamp,
    user_end: pd.Timestamp,
    ft_period_days: int = 0,
    oos_period_days: int = 0,
) -> PeriodDates:
    """
    Calculate IS, FT, and OOS period boundaries.

    Cutting order: OOS from end first, then FT from remaining.
    All periods are inclusive-ended in keeping with Merlin's slicing.
    Non-overlap is achieved by setting:
      is_end = ft_start - 1 day
      ft_end = oos_start - 1 day
    """
```
**Implementation detail:** Define “days” using the **date component** (calendar days) for consistent UI semantics, even when timestamps include times.

**Testing:**
- Only OOS enabled (no FT)
- Only FT enabled (no OOS)
- Both enabled
- Edge cases: OOS+FT too large, IS too small

### Phase 3-4-3: Core OOS Test Logic

**Files:** `src/core/post_process.py`

1. Add `OOSTestConfig`, `OOSTestCandidate`, `OOSTestResult` dataclasses
2. Implement `get_oos_test_candidates()` using real object fields/types (see above)
3. Implement `_oos_test_worker_entry()` worker function (mirror FT worker pattern)
4. Implement `run_oos_test()` main function (mirror `run_forward_test()` structure)
5. Reuse `calculate_profit_degradation()` for annualized degradation ratio using IS vs OOS

**Key implementation details:**
- Use multiprocessing pool like FT
- Reuse warmup and dataset preparation logic
- Reuse metrics calculation from `metrics.py`
- Rank by `oos_test_profit_degradation` descending by default (configurable later if desired)

**Testing:**
- Source module coverage: optuna/dsr/ft/stress_test
- Params rehydration for Stress Test candidates
- Stress Test filtering: `status == "ok"` only
- Edge cases: no trades in OOS

### Phase 3-4-4: Server Integration

**Files:** `src/ui/server.py`

1. Parse OOS Test config from request payload (`oosTest`)
2. **CRITICAL:** Trigger period split if **FT OR OOS Test** enabled
3. Call `calculate_period_dates()` before optimization starts
4. Run Optuna on `[is_start, is_end]` (inclusive)
5. Run FT on `[ft_start, ft_end]` (inclusive) if enabled
6. Run Stress Test if enabled
7. Run OOS Test on `[oos_start, oos_end]` (inclusive) after Stress Test
8. Persist OOS Test results to DB
9. Persist study-level `oos_test_*` metadata to `studies` table

**Progress reporting (correct signature):**
```python
_set_optimization_state({
    "status": "running",
    "mode": "optuna",
    "study_id": study_id,
    "stage": "oos_test",
    "message": "Running OOS Test...",
})
```

### Phase 3-4-5: Start Page UI

**Files:**
- `src/ui/templates/index.html`
- `src/ui/static/js/post-process-ui.js` (collect OOS config)
- `src/ui/static/js/ui-handlers.js` (inject into payload)

1. Add "Out-of-Sample Test" section:
   - Position: between Post Process and Walk-Forward Analysis
   - Checkbox: Enable Out-of-Sample Test
   - Input: Test Period (days) — default 30
   - Input: Top Candidates — default 10
2. Mutual exclusion with WFA (disable/enable behavior)

### Phase 3-4-6: Results Page UI

**Files:**
- `src/ui/templates/results.html`
- `src/ui/static/js/results.js`
- `src/ui/static/js/post-process-ui.js`

1. Add “OOS Test” tab button (visible when OOS Test data exists)
2. Render OOS Test table using existing FT patterns:
   - Display `oos_test_profit_degradation` as ratio
   - Compute deltas (OOS - IS) in UI (do not store in DB)
   - Show `oos_test_source` + `oos_test_source_rank` columns

### Phase 3-4-7: Documentation & Testing

1. Update `CLAUDE.md` with OOS Test documentation
2. Add unit tests for `calculate_period_dates()` (no overlap, inclusive semantics)
3. Add unit tests for candidate selection:
   - Stress Test filtering (`status=="ok"`)
   - Params rehydration
   - Multi-objective fallback ordering (mirror `load_study_from_db` ordering)
4. Add integration test for full OOS Test flow

---

## File Change Summary

| File | Type | Changes |
|------|------|---------|
| `src/core/storage.py` | Modify | Schema update (+ _ensure_columns), save/load functions for OOS Test |
| `src/core/post_process.py` | Modify | Period calculation, OOS Test functions |
| `src/ui/server.py` | Modify | Period split logic (OOS OR FT), integration, progress state updates |
| `src/ui/templates/index.html` | Modify | OOS Test UI section |
| `src/ui/static/js/post-process-ui.js` | Modify | OOS config collection + results rendering |
| `src/ui/static/js/ui-handlers.js` | Modify | Inject OOS config into payload |
| `src/ui/templates/results.html` | Modify | OOS Test tab |
| `src/ui/static/js/results.js` | Modify | OOS tab logic |
| `CLAUDE.md` | Modify | Documentation update |
| `tests/test_oos_test.py` | Create | Unit tests |

---

## API Changes

### Request Payload Extension

```json
{
  "oosTest": {
    "enabled": true,
    "periodDays": 30,
    "topK": 10
  }
}
```

### Response / Study Data Extension

Study metadata (fields stored in `studies`):

```json
{
  "study": {
    "oos_test_enabled": 1,
    "oos_test_period_days": 30,
    "oos_test_top_k": 10,
    "oos_test_start_date": "2025-10-22",
    "oos_test_end_date": "2025-11-20",
    "oos_test_source_module": "forward_test"
  }
}
```

Trial rows (fields stored in `trials`):

```json
{
  "trial_number": 1,
  "oos_test_net_profit_pct": 12.5,
  "oos_test_romad": 0.85,
  "oos_test_profit_degradation": 0.87,
  "oos_test_rank": 1,
  "oos_test_source": "forward_test",
  "oos_test_source_rank": 3
}
```

---

## Risk Considerations

1. **Data Period Validation:** Ensure IS period doesn't become too short when both FT and OOS Test are enabled.
2. **Empty Results:** Handle cases where OOS period has no trades gracefully.
3. **Source Module Availability:** If source module has fewer candidates than `top_k`, use all available candidates.
4. **Performance:** OOS Test adds another multiprocess stage.
5. **Boundary correctness:** Inclusive ends require “day-before” boundaries to avoid overlap; enforce via tests.
6. **Params rehydration:** Stress Test candidates require DB lookup for params.

---

## Success Criteria

1. OOS Test section appears correctly on Start page
2. Mutual exclusion with WFA works
3. Period dates are calculated correctly (OOS cut first, then FT)
4. **No data leakage:** IS/FT/OOS are non-overlapping using inclusive ranges
5. **OOS-only mode works:** Period split happens even when FT disabled
6. Candidates are sourced from correct Post Process module with params
7. Stress Test candidates with bad status are filtered out
8. OOS Test results are saved to database
9. OOS Test tab displays on Results page with correct data
10. `oos_test_profit_degradation` displays as ratio (consistent with FT/Manual Test)
11. All existing functionality remains working

---

## References (for implementation semantics)

1. Optuna `Study.best_trial` / `Study.best_trials` (single vs multi-objective):  
   https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.Study.html

2. pandas time-series label slicing includes endpoints (label-based slicing is inclusive of stop bound):  
   https://pandas.pydata.org/docs/user_guide/timeseries.html

3. Time-series data splitting should be chronological to prevent leakage (train → validate → test in time order):  
   https://dzone.com/articles/data-splits-machine-learning-training-validation-test
