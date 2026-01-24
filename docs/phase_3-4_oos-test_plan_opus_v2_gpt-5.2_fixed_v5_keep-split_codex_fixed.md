# Phase 3-4: Out-of-Sample Test (OOS Test) (v5 — keep current split semantics)

## Changelog (v2 — GPT-5.2 fixed → v3)

1. **OOS Test is NOT a Post Process module:** Updated wording and architecture so OOS Test is a **separate “Test” section** (as in UI) and is implemented as an **automated Manual Test** run on a reserved holdout period (same metrics + comparison behavior).
2. **No OOS reranking:** Removed OOS “rank by degradation” behavior and removed the `oos_test_rank` column. OOS results are displayed and stored **in the same order as the source list**.
3. **Source selection = last finished module (strict precedence):** Clarified selection rules to exactly match the pipeline:
   - Optuna only → source = Optuna
   - +DSR → source = DSR
   - +Forward Test → source = Forward Test
   - +Stress Test → source = Stress Test
4. **Schema + UI updated accordingly:** DB stores `oos_test_source` + `oos_test_source_rank` (source ordering) and OOS raw metrics + degradation ratio; UI defaults to sorting by source order.
5. **Added prerequisite:** Manual Test is updated to support `sourceTab='stress_test'` so testing from the Stress Test tab uses Stress Test ordering (and OOS can reuse the same engine).

(Other fixes from v2 — GPT-5.2 fixed remain in effect: inclusive, non-overlapping date boundaries; correct `_set_optimization_state` signature; multi-objective-safe Optuna fallback; schema “change” metrics not stored.)
- **Kept existing boundary overlap semantics:** Removed the “day-before” non-overlap rule and matched Merlin’s current Forward Test split (`is_end = ft_start`). Adjacent periods share the boundary bar by design.

---

## Overview

Add an **Out-of-Sample Test (OOS Test)** feature that runs a final evaluation on a reserved holdout period at the end of the selected dataset window.

**Critical UX/behavior point:** OOS Test is **not** a Post Process module. It is a separate “Test” feature (like Manual Test) that is **automatically executed** during “Run Optimization” when enabled.

### Relationship to existing Manual Test

OOS Test should reuse the **same computation path** as Manual Test:

- same backtest run path
- same metric set (basic + advanced as currently shown)
- same comparison logic (`profit_degradation` ratio, etc.)

The difference is only:
- Manual Test is user-triggered, user-chosen dates & trials.
- OOS Test is optimizer-triggered, auto-chosen OOS dates & auto-chosen trials (from the latest finished module).

### Why this is correct for time series

For time series evaluation, the holdout test set must be **chronologically after** training/validation data to avoid leakage. This is exactly what OOS Test enforces by cutting the holdout window from the end. (See scikit-learn’s TimeSeriesSplit docs for the general principle of avoiding training on future data.)

---

## Data Period Splitting (inclusive ends, 1-bar overlap — matches current FT)

Merlin’s existing **Forward Test** split sets `is_end = ft_start` (same timestamp). Because dataset trimming is **end-inclusive**, that creates a **single shared boundary bar** between IS and FT (the boundary bar is included in both periods).

You said you are fine with this 1-bar overlap, so OOS Test should **keep the same semantics** (no “day-before” exclusions).

### Boundary rules (same style as `calculate_ft_dates`)

Let `user_start`, `user_end` be the user-selected window.

**OOS-only (FT disabled):**
- `oos_start = user_end - oos_period_days`
- `oos_end = user_end`
- `is_end = oos_start`

**FT + OOS enabled (cut OOS first, then FT from remaining):**
- `oos_start = user_end - oos_period_days`
- `oos_end = user_end`
- `ft_end = oos_start`
- `ft_start = ft_end - ft_period_days`
- `is_end = ft_start`

This yields a shared boundary bar between adjacent segments:
- IS/FT share the `ft_start` bar
- FT/OOS share the `oos_start` bar
- If FT is disabled, IS/OOS share the `oos_start` bar

### Example

```
Full Dataset: 2025-05-01 → 2025-11-20 (inclusive)

OOS (30 days): 2025-10-21 → 2025-11-20
FT  (15 days): 2025-10-06 → 2025-10-21
IS:            2025-05-01 → 2025-10-06
```

In this example, `2025-10-06` is shared by IS+FT and `2025-10-21` is shared by FT+OOS.

**Note on “days” semantics:** This mirrors Merlin’s current FT behavior where `start = end - period_days`. With inclusive slicing, a “30 days” setting can correspond to `period_days + 1` calendar days if your data is daily bars. This is existing behavior and is kept for consistency.

---

## Source selection (last finished module)

OOS Test must test candidates from the **last finished stage in the pipeline**, with strict precedence:

1. If Stress Test ran and produced results → source = Stress Test
2. Else if Forward Test ran and produced results → source = Forward Test
3. Else if DSR ran and produced results → source = DSR
4. Else → source = Optuna (raw trials ordering as shown in Results)

This exactly matches the user-visible pipeline and avoids “mixing” sources.

### Candidate ordering (must be preserved)

OOS Test **must not rerank**. It uses the source ordering as-is:

- Optuna source order = the order shown in Optuna results table
- DSR source order = `dsr_rank` order
- FT source order = `ft_rank` order
- Stress Test source order = `st_rank` order **after filtering failures**

OOS results are stored and rendered in this same order, with `oos_test_source_rank` reflecting the original source rank (or sequential order if the source rank is missing).

---

## OOS Test execution = automated Manual Test

### Prerequisite: fix Manual Test when launched from Stress Test tab

Today, the Manual Test UI sends `sourceTab` values only for `optuna`, `forward_test`, and `dsr`. When launched from the **Stress Test** tab, it still sends `sourceTab='optuna'`, so the backend computes `rank_change` against the wrong baseline ordering.

Fix this first (so OOS can reuse the same logic cleanly):

- **Frontend (`src/ui/static/js/results.js`)**: when `ResultsState.activeTab === 'stress_test'`, send `sourceTab = 'stress_test'`.
- **Backend (`src/ui/server.py`)**: accept `sourceTab='stress_test'` and use `st_rank` for `baseline_rank_map`.
- Keep Manual Test *metric baseline* unchanged (Stress Test doesn’t define a separate backtest period like FT): comparisons remain against IS metrics (same as `optuna`/`dsr`).

### Core idea

Implement OOS Test by reusing the Manual Test “batch test” logic with:
- `startDate = oos_start`
- `endDate = oos_end`
- `trialNumbers = [trial numbers in source order]`
- `sourceTab = <source module>` (now includes `stress_test` after the prerequisite fix)

### Recommended factoring (avoid duplication)

Extract the “run tests for N trials on a period” logic into a reusable core helper so both Manual Test and OOS Test call the same implementation:

- Create: `src/core/testing.py::run_period_test_for_trials(...)`
- Manual Test endpoint becomes a thin wrapper (validate payload → load df → call helper → persist).
- OOS Test stage calls the same helper directly from the optimizer flow (no HTTP hop).

Either way: OOS Test results format should match Manual Test output (per-trial `original_metrics`, `test_metrics`, `comparison`).

### Comparison metric

Continue using the existing “annualized ratio” approach for `profit_degradation` (consistent with FT and Manual Test), computed via Merlin’s existing comparison function.


Continue using the existing “annualized ratio” approach for `profit_degradation` (consistent with FT and Manual Test), computed via Merlin’s existing comparison function.

---

## Database Schema

### `studies` table (metadata)

```sql
oos_test_enabled INTEGER DEFAULT 0,
oos_test_period_days INTEGER,
oos_test_top_k INTEGER,
oos_test_start_date TEXT,
oos_test_end_date TEXT,
oos_test_source_module TEXT  -- "optuna" | "dsr" | "forward_test" | "stress_test"
```

### `trials` table (results)

Store only raw OOS metrics + degradation ratio + source ordering info.

```sql
-- OOS Test metrics (parallel to FT)
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

-- Comparison metric (same as FT/Manual Test convention)
oos_test_profit_degradation REAL,

-- Source tracking (order preservation)
oos_test_source TEXT,         -- which module provided this trial list
oos_test_source_rank INTEGER  -- rank/order in that source list
```

**Removed:** `oos_test_rank` (OOS does not rerank).

---

## Implementation Plan

### Phase 3-4-0: Manual Test support for Stress Test tab (required first)

**Goal:** When users run Manual Test while viewing the **Stress Test** tab, the test should treat the baseline ordering as Stress Test ordering (use `st_rank`) and store `source_tab='stress_test'` in manual test records.

**Files:**
- `src/ui/static/js/results.js`
- `src/ui/server.py`

**Frontend changes (`results.js`):**
- In the Manual Test modal submission logic, map `ResultsState.activeTab === 'stress_test'` → `sourceTab = 'stress_test'`.

**Backend changes (`server.py`):**
1. Extend validation: allow `sourceTab` in `{"optuna","forward_test","dsr","stress_test"}`.
2. Extend baseline rank map logic:
   - `optuna` → enumerate trial list order
   - `forward_test` → `ft_rank`
   - `dsr` → `dsr_rank`
   - `stress_test` → `st_rank`
3. Keep baseline period days logic unchanged (Stress Test has no separate “period days” like FT; compare against IS period days).
4. Persist manual test row with `source_tab='stress_test'` (already stored generically).

**Acceptance tests:**
- Open a study with Stress Test results, switch to Stress Test tab, run Manual Test with “Top K”.
- Confirm the request payload contains `sourceTab='stress_test'`.
- Confirm the saved manual test record shows `source_tab='stress_test'` and the backend does not reject it.
- Confirm per-row `comparison.rank_change` is computed relative to `st_rank` baseline order.

### Phase 3-4-1: Storage changes
 Storage changes

**File:** `src/core/storage.py`

- Add columns above in `_create_schema()` and `_ensure_columns()`
- Add `save_oos_test_results(study_id, results)` that writes:
  - OOS metrics + `oos_test_profit_degradation`
  - `oos_test_source`, `oos_test_source_rank`

### Phase 3-4-2: Period date calculation

**File:** `src/core/post_process.py`

- Keep `calculate_period_dates()` aligned with current end-inclusive splitting (no ?day-before? gap). Accept 1-bar boundary overlap.
- Ensure period split triggers if **OOS Test OR Forward Test** enabled.
- Validate IS remains non-empty.

### Phase 3-4-3: Shared “period test” engine (Manual Test reuse)

**Recommended refactor:** Extract the core logic currently used by Manual Test into a reusable helper so OOS Test can call it.

Create (example):
- `src/core/testing.py::run_period_test_for_trials(df, strategy_id, warmup_bars, fixed_params, start_ts, end_ts, trials, baseline_metrics_resolver, baseline_period_days, test_period_days)`

Manual Test endpoint becomes a thin wrapper: validate payload → load df → call helper → save manual test record.

OOS Test stage becomes: build trial list → call helper → persist results to `trials` OOS columns.

### Phase 3-4-4: Server integration (optimizer run)

**File:** `src/ui/server.py`

- Parse `oosTest` config from `/api/optimize` payload
- Compute period dates (IS/FT/OOS) before Optuna if OOS/FT enabled
- After optimization and any selected Post Process modules:
  1) Determine **source module** using “last finished module” precedence  
  2) Extract top-K trial numbers **in source order**  
  3) Run OOS test via the shared Manual Test engine  
  4) Save OOS metrics into `trials` and metadata into `studies`

Progress reporting uses the correct signature:
```python
_set_optimization_state({
    "status": "running",
    "mode": "optuna",
    "study_id": study_id,
    "stage": "oos_test",
    "message": "Running OOS Test...",
})
```

### Phase 3-4-5: UI (Start page)

No change to layout: OOS Test remains a separate section between Post Process and WFA (as in the UI screenshot).

### Phase 3-4-6: UI (Results page)

- Add “OOS Test” tab when OOS fields exist
- Default ordering: **sort by `oos_test_source_rank` ascending**
- Show `oos_test_source` and `oos_test_source_rank`
- Do not auto-sort by degradation (user can still sort interactively if you provide that UI behavior)

### Phase 3-4-7: Tests

Add tests to cover:
- Period splitting correctness (inclusive, boundary-bar overlap matches current FT)
- Source selection precedence rules
- Order preservation:
  - given a source ordered list of trial_numbers, OOS results remain in that order in storage + UI rendering
- Multi-objective Optuna fallback uses Merlin’s existing trial ordering (not `best_trial`), consistent with Optuna’s docs for multi-objective (`best_trials`).

---

## Success Criteria

1. OOS Test is clearly separate from Post Process in UI and docs.
2. Period splitting happens when OOS enabled (even if FT disabled).
3. Period split semantics match existing Forward Test: adjacent periods share the boundary bar (by design).
4. OOS candidate source matches “last finished module” precedence.
5. OOS results preserve source order; no OOS reranking occurs.
6. OOS uses the same metrics + comparison semantics as Manual Test.
7. Multi-objective studies behave correctly (no `best_trial` misuse).

---

## References

- scikit-learn `TimeSeriesSplit` (time-ordered splits to avoid training on future data):  
  https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- Optuna Study docs (`best_trial` single-objective only; multi-objective uses `best_trials`):  
  https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.Study.html
