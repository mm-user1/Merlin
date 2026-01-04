# Phase 4.1: Critical Fixes - Implementation Prompt for GPT 5.2 Codex

## Project Context

**Merlin** is a cryptocurrency trading strategy backtesting and Optuna optimization platform with a Flask SPA frontend. After Phase 4 (commit 33b1ce9), which added new Optuna features and upgraded to Optuna 4.6.0, three issues have been identified that require immediate fixes.

### Project Architecture
- **Core Module**: `src/core/optuna_engine.py` - Handles Bayesian optimization using Optuna
- **Multi-Objective Optimization**: Supports multiple optimization targets (score, net_profit, romad, sharpe, max_drawdown)
- **Constraints System**: Implements constraint-based optimization (e.g., max_drawdown_pct ≤ 25%)
- **Database Persistence**: All optimization results saved to SQLite, browsable through web UI

### Technology Stack
- Python 3.x
- Optuna 4.6.0 (upgraded in Phase 4)
- SQLite with WAL mode
- Flask backend

---

## Three Critical Issues to Fix

### Issue 1: Penalty Values Are Not the Correct Approach (HIGH PRIORITY)
### Issue 2: Infeasible Trial Sorting Problem (MEDIUM PRIORITY)
### Issue 3: Dead Code Function Should Be Removed (LOW PRIORITY)

---

## Issue 1: Penalty Values Violate Optuna Best Practices

### Status: 🔴 CRITICAL - Must be fixed

### Problem Analysis

**Current Implementation (INCORRECT):**

When a trial has missing or NaN objective values in multi-objective optimization, the code assigns penalty values (-1e12 or 1e12) and marks the trial as COMPLETE:

**File**: `src/core/optuna_engine.py`

**Location 1** (lines 1393-1406):
```python
objective_missing = False
try:
    objective_values = self._extract_objective_values(all_metrics)
except optuna.TrialPruned as exc:
    if self.mo_config.is_multi_objective():
        # ❌ WRONG: Assigns penalty values
        objective_values = self._build_penalty_objectives(all_metrics)
        objective_missing = True
        logger.warning(
            "Objective missing for trial %s; applying penalty values and marking invalid (multi-objective). Reason: %s",
            trial.number,
            exc,
        )
    else:
        raise
```

**Location 2** (lines 1469-1482):
```python
objective_missing = False
try:
    objective_values = self._extract_objective_values(all_metrics)
except optuna.TrialPruned as exc:
    if self.mo_config.is_multi_objective():
        # ❌ WRONG: Assigns penalty values
        objective_values = self._build_penalty_objectives(all_metrics)
        objective_missing = True
        logger.warning(
            "Objective missing for trial %s; applying penalty values and marking invalid (multi-objective). Reason: %s",
            trial.number,
            exc,
        )
    else:
        raise
```

**Helper Function** (lines 1356-1366):
```python
def _build_penalty_objectives(self, all_metrics: Dict[str, Any]) -> List[float]:
    objective_values: List[float] = []
    for obj in self.mo_config.objectives:
        value = all_metrics.get(obj)
        if value is None or _is_nan(value):
            direction = OBJECTIVE_DIRECTIONS.get(obj, "maximize")
            penalty = -1e12 if direction == "maximize" else 1e12
            objective_values.append(penalty)
        else:
            objective_values.append(float(value))
    return objective_values
```

**Post-Processing Filter** (line 1736 in `_finalize_results`):
```python
self.trial_results = [r for r in self.trial_results if not r.objective_missing]
```

**Storage Filter** (`src/core/storage.py` line 333):
```python
filtered_results = [
    r for r in list(trial_results or []) if not getattr(r, "objective_missing", False)
]
```

### Why This Is Wrong

This pattern exists only because Merlin currently marks “invalid objective” trials as **COMPLETE** (by returning penalty values) and then tries to hide them later with `objective_missing` filters.

This is problematic because:
1. The sampler treats COMPLETE trials as real data → fake penalty objectives pollute sampling.
2. The UI/DB trial counts diverge from Optuna’s real trial states.
3. Filtering is duplicated in multiple layers (engine + storage), which is brittle.

**Correct Optuna-aligned behavior:**
- If an objective is truly missing/non-finite (bug/undefined), return `float('nan')` (or a tuple of NaNs).
  Optuna marks the trial as FAIL and **it will not abort the study**.
- Remove `objective_missing` and all post-processing filters.
- When building “results lists” for UI/DB, only include trials with Optuna TrialState.COMPLETE.

Optuna FAQ (stable) explicitly states:
- Trials that return NaN are treated as failures but do not abort studies.
- Exceptions (other than TrialPruned) will abort studies unless you use `catch=`.

### Multi-Objective Pruning vs Failing - Important Distinction

**Rule 1 (multi-objective):** Do not use pruning at all.
- Optuna explicitly states `trial.should_prune()` does **not support multi-objective optimization**.
- Merlin already disables pruning UI/backend when objectives > 1. Keep it that way.

**Rule 2 (single-objective):** Keep genuine pruning semantics.
- If the pruner decides to prune, let `optuna.TrialPruned` propagate as a PRUNED trial.
- Do **not** catch-and-convert `TrialPruned` into FAIL.

**Rule 3 (objective missing / non-finite):** Do not raise exceptions; return NaN to mark FAIL.
- Optuna treats `float('nan')` return values as TrialState.FAIL and it does not abort the study.
- This is the cleanest way to drop “invalid objective” trials without polluting the sampler with fake COMPLETE values.

**Important nuance (constraints learning):**
- Optuna’s `constraints_func` is evaluated only after **successful** (COMPLETE) trials, and won’t be called for FAILED/PRUNED trials.
- Therefore, use FAIL (NaN) only for truly missing/buggy objective values.
- For “domain infeasible but still computable” regions (e.g., too few trades), prefer expressing infeasibility via constraints (e.g., `total_trades >= 30`) while keeping objective values finite.

### The Correct Fix

**Step 1**: Replace penalty value handling with proper exception handling

**File**: `src/core/optuna_engine.py`

**Change Location 1** (lines 1393-1406):

```python
# BEFORE (WRONG):
objective_missing = False
try:
    objective_values = self._extract_objective_values(all_metrics)
except optuna.TrialPruned as exc:
    if self.mo_config.is_multi_objective():
        objective_values = self._build_penalty_objectives(all_metrics)
        objective_missing = True
        logger.warning(
            "Objective missing for trial %s; applying penalty values and marking invalid (multi-objective). Reason: %s",
            trial.number,
            exc,
        )
    else:
        raise

# AFTER (CORRECT):
# 1) Do NOT use TrialPruned to signal “objective missing”.
# 2) Keep pruning semantics ONLY for genuine pruning (single-objective only).
# 3) If an objective value is missing / non-finite, FAIL the trial by returning NaN.
#    Optuna treats NaN returns as TrialState.FAIL and it will NOT abort the study.

objective_values = self._extract_objective_values(all_metrics)

# Optional: sanitize “numerical” non-finite values (see Nuance section below).
objective_values, sanitized = self._sanitize_objective_values(objective_values)
if sanitized:
    trial.set_user_attr("merlin.sanitized_metrics", sanitized)

if self.mo_config.is_multi_objective():
    if any(v is None or (isinstance(v, float) and not math.isfinite(v)) for v in objective_values):
        trial.set_user_attr("merlin.objective_missing", True)
        return tuple([float("nan")] * len(self.mo_config.objectives))
else:
    # single-objective: objective_values may be a float or a 1-item list; handle both
    v = objective_values[0] if isinstance(objective_values, (list, tuple)) else objective_values
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        trial.set_user_attr("merlin.objective_missing", True)
        return float("nan")
```

**Change Location 2** (lines 1469-1482):

```python
# BEFORE (WRONG):
objective_missing = False
try:
    objective_values = self._extract_objective_values(all_metrics)
except optuna.TrialPruned as exc:
    if self.mo_config.is_multi_objective():
        objective_values = self._build_penalty_objectives(all_metrics)
        objective_missing = True
        logger.warning(
            "Objective missing for trial %s; applying penalty values and marking invalid (multi-objective). Reason: %s",
            trial.number,
            exc,
        )
    else:
        raise

# AFTER (CORRECT):
# 1) Do NOT use TrialPruned to signal “objective missing”.
# 2) Keep pruning semantics ONLY for genuine pruning (single-objective only).
# 3) If an objective value is missing / non-finite, FAIL the trial by returning NaN.
#    Optuna treats NaN returns as TrialState.FAIL and it will NOT abort the study.

objective_values = self._extract_objective_values(all_metrics)

# Optional: sanitize “numerical” non-finite values (see Nuance section below).
objective_values, sanitized = self._sanitize_objective_values(objective_values)
if sanitized:
    trial.set_user_attr("merlin.sanitized_metrics", sanitized)

if self.mo_config.is_multi_objective():
    if any(v is None or (isinstance(v, float) and not math.isfinite(v)) for v in objective_values):
        trial.set_user_attr("merlin.objective_missing", True)
        return tuple([float("nan")] * len(self.mo_config.objectives))
else:
    # single-objective: objective_values may be a float or a 1-item list; handle both
    v = objective_values[0] if isinstance(objective_values, (list, tuple)) else objective_values
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        trial.set_user_attr("merlin.objective_missing", True)
        return float("nan")
```



**Step 1a (Nuance / robustness)**: Add objective-value sanitization to avoid “false invalid” FAIL trials

**Why**:
- Returning NaN is the correct way to mark a trial as FAIL **when the objective is truly missing/buggy**.
- But some objectives can become NaN/inf or missing in benign “domain edge cases” (e.g., no trades, divide-by-zero in ratios).
- In those cases, it’s better to normalize to a finite, conservative value and let **constraints** (e.g., `total_trades >= 30`) do the heavy lifting.

**Implement**:
Add a small helper in `src/core/optuna_engine.py` that:
1. Takes the extracted objective value(s) and the `all_metrics` dict.
2. Uses `total_trades` (if present) and basic numeric checks to normalize:
   - If `total_trades == 0` (or very small) and an objective metric is missing/None/NaN/inf, set it to a neutral finite value (recommended: `0.0`) and record the metric name in `sanitized_metrics`.
   - If an objective metric is missing/None/NaN/inf **and** you cannot confidently classify it as an “edge case” (e.g., `total_trades` missing), keep it as missing → the objective function should return NaN and FAIL the trial.
3. Returns `(normalized_objective_values, sanitized_metrics)`.

**Important**:
- This helper MUST NOT introduce huge penalty constants (e.g., ±1e12). If you normalize, normalize to small, conservative finite values and make it transparent via `trial.set_user_attr("merlin.sanitized_metrics", ...)`.

**Step 2**: Remove the `_build_penalty_objectives()` method entirely

**Delete** (lines 1356-1366):
```python
def _build_penalty_objectives(self, all_metrics: Dict[str, Any]) -> List[float]:
    # DELETE THIS ENTIRE METHOD - no longer needed
    ...
```

**Step 3**: Remove `objective_missing` flag from `OptimizationResult` dataclass

**File**: `src/core/optuna_engine.py` (around line 99)

```python
# BEFORE:
@dataclass
class OptimizationResult(StrategyResult):
    ...
    objective_missing: bool = False

# AFTER:
@dataclass
class OptimizationResult(StrategyResult):
    ...
    # objective_missing field removed - no longer needed
```

**Step 4**: Remove `objective_missing` parameter from `_trial_set_result_attrs()`

**File**: `src/core/optuna_engine.py` (around line 677)

```python
# BEFORE:
def _trial_set_result_attrs(
    trial: optuna.Trial,
    result: OptimizationResult,
    objective_values: List[float],
    all_metrics: Dict[str, Any],
    constraint_values: List[float],
    constraints_satisfied: bool,
    objective_missing: bool,  # REMOVE THIS PARAMETER
):
    ...
    trial.set_user_attr("merlin.objective_missing", bool(objective_missing))  # REMOVE THIS LINE

# AFTER:
def _trial_set_result_attrs(
    trial: optuna.Trial,
    result: OptimizationResult,
    objective_values: List[float],
    all_metrics: Dict[str, Any],
    constraint_values: List[float],
    constraints_satisfied: bool,
):
    # Remove objective_missing handling
    ...
```

**Step 5**: Remove calls to `objective_missing` in trial attribute setting

**File**: `src/core/optuna_engine.py` (lines 1416, 1425):

```python
# BEFORE:
result.objective_missing = objective_missing
...
_trial_set_result_attrs(
    trial=trial,
    result=result,
    objective_values=objective_values,
    all_metrics=all_metrics,
    constraint_values=constraint_values,
    constraints_satisfied=constraints_satisfied,
    objective_missing=objective_missing,  # REMOVE THIS
)

# AFTER:
# Remove result.objective_missing assignment
...
_trial_set_result_attrs(
    trial=trial,
    result=result,
    objective_values=objective_values,
    all_metrics=all_metrics,
    constraint_values=constraint_values,
    constraints_satisfied=constraints_satisfied,
)
```

**Step 6**: Remove post-processing filter in `_finalize_results()`

**File**: `src/core/optuna_engine.py` (line 1736)

```python
# BEFORE:
def _finalize_results(self) -> List[OptimizationResult]:
    ...
    self.trial_results = calculate_score(self.trial_results, score_config)
    self.trial_results = [r for r in self.trial_results if not r.objective_missing]  # REMOVE THIS LINE
    ...

# AFTER:
def _finalize_results(self) -> List[OptimizationResult]:
    ...
    self.trial_results = calculate_score(self.trial_results, score_config)
    # No filtering needed - failed trials never enter trial_results
    ...
```

**Step 7**: Remove filter in storage.py

**File**: `src/core/storage.py` (line 333)

```python
# BEFORE:
filtered_results = [
    r for r in list(trial_results or []) if not getattr(r, "objective_missing", False)
]

# AFTER:
filtered_results = list(trial_results or [])
# No need to filter - failed trials are never saved
```

**Step 8**: Remove `objective_missing` from `_trial_from_optuna()`

**File**: `src/core/optuna_engine.py` (around lines 699, 724)

```python
# BEFORE:
def _trial_from_optuna(...):
    ...
    objective_missing = attrs.get("merlin.objective_missing")
    ...
    return OptimizationResult(
        ...
        objective_missing=bool(objective_missing) if objective_missing is not None else False,
    )

# AFTER:
def _trial_from_optuna(...):
    ...
    # Remove objective_missing handling
    ...
    return OptimizationResult(
        ...
        # objective_missing removed
    )
```

### Why This Fix Works

1. ✅ **Single-objective**: Already working correctly (raises exception → FAILED)
2. ✅ **Multi-objective**: Exception → FAILED → Ignored by samplers (correct behavior)
3. ✅ **No TPE crash**: FAILED trials have defined state, unlike PRUNED trials
4. ✅ **Cleaner code**: No special cases, no filtering, standard Optuna behavior
5. ✅ **Performance**: Faster sampling (fewer trials for samplers to process)
6. ✅ **Documentation**: Aligns with Optuna's documented best practices

### Testing Requirements for Issue 1

After implementing the fix, verify:

1. **Multi-objective study completes without crashes**
   - Run optimization with 2+ objectives
   - Ensure no TypeError from TPE sampler

2. **Failed trials don't appear in results**
   - Check `study.trials` - failed trials should have `state=FAIL`
   - Check `trial_results` - failed trials should NOT appear

3. **No penalty values in objective_values**
   - Inspect saved trials - no -1e12 or 1e12 values

4. **Pareto front is clean**
   - No need for post-filtering
   - Only valid trials appear

5. **All samplers work correctly**
   - Test with TPESampler
   - Test with NSGAIISampler
   - Test with NSGAIIISampler
   - Test with RandomSampler

---

## Issue 2: Infeasible Trial Sorting Problem

### Status: ⚠️ MEDIUM PRIORITY - Should be fixed

### Problem Analysis

**Current Implementation:**

**File**: `src/core/optuna_engine.py` (lines 497-518)

```python
def group_rank(item: OptimizationResult) -> int:
    if constraints_enabled:
        if not item.constraints_satisfied:
            return 2  # ❌ All infeasible trials get same rank
        return 0 if item.is_pareto_optimal else 1
    return 0 if item.is_pareto_optimal else 1

def primary_sort_value(item: OptimizationResult) -> float:
    value = 0.0
    if item.objective_values and len(item.objective_values) > primary_idx:
        value = float(item.objective_values[primary_idx])
    if primary_direction == "maximize":
        return -value
    return value

def tie_breaker(item: OptimizationResult) -> int:
    return int(item.optuna_trial_number or 0)

return sorted(
    results,
    key=lambda item: (group_rank(item), primary_sort_value(item), tie_breaker(item)),
    # ❌ Infeasible trials sorted by primary objective, not violation magnitude
)
```

**Current sorting hierarchy:**
1. Feasible Pareto-optimal trials (rank=0)
2. Feasible non-Pareto trials (rank=1)
3. ALL infeasible trials (rank=2) → Then sorted by primary objective value

### Why This Is Problematic

**Scenario**: Strict constraint (max_drawdown_pct ≤ 25%)

**Current behavior:**
- Trial #47: +150% profit, Max DD = 45% (constraint violated by 20%) → Shows FIRST
- Trial #23: +50% profit, Max DD = 26% (constraint violated by 1%) → Shows LATER

**User sees**: "Highest profit infeasible trial" first (misleading - massively violates constraints)

**Better approach**: Show "least infeasible trial" first

**User should see**: Trial #23 first (only slightly over limit, more realistic to fix)

### What Optuna Does

According to **Optuna documentation** (https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.NSGAIISampler.html):

> "Trial x constrained-dominates trial y if:
> 1. trial x is feasible and trial y is not, OR
> 2. both trials are infeasible but trial x has a smaller overall violation, OR
> 3. both are feasible and trial x dominates trial y."

**Optuna's NSGAIISampler and TPESampler** calculate infeasible trial scores by summing violation values of infeasible dimensions (values > 0), then sort trials using this score.

**Verdict**: Optuna's own samplers sort infeasible trials by total violation magnitude. The implementation should do the same for consistency.

### The Correct Fix

**Step 1**: Add violation magnitude calculation helper

**File**: `src/core/optuna_engine.py`

**Insert BEFORE** `sort_optimization_results()` function (around line 470):

```python
def _calculate_total_violation(
    constraint_values: Optional[List[float]],
    constraints_satisfied: Optional[bool],
) -> float:
    """
    Calculate total constraint violation magnitude.

    For Optuna constraints:
    - constraint_value > 0 means constraint is VIOLATED
    - constraint_value ≤ 0 means constraint is SATISFIED

    Returns sum of positive violations (lower is better, closer to feasible).

    Args:
        constraint_values: List of constraint violation values
        constraints_satisfied: Whether the trial is feasible (True/False) if known

    Returns:
        Total violation magnitude.
        - 0.0 for feasible trials
        - +inf for infeasible trials with missing constraint values (defensive)
    """
    if not constraint_values:
        if constraints_satisfied is False:
            return float("inf")
        return 0.00
    return sum(max(0.0, float(v)) for v in constraint_values)
```

**Step 2**: Update `sort_optimization_results()` sorting key

**File**: `src/core/optuna_engine.py` (lines 515-518)

```python
# BEFORE:
return sorted(
    results,
    key=lambda item: (group_rank(item), primary_sort_value(item), tie_breaker(item)),
)

# AFTER:
return sorted(
    results,
    key=lambda item: (
        group_rank(item),                                             # 0=feas+Pareto, 1=feas+non-Pareto, 2=infeas
        _calculate_total_violation(item.constraint_values, item.constraints_satisfied),  # Sort infeasible by total violation (lower=better)
        primary_sort_value(item),                                     # Then by primary objective
        tie_breaker(item)                                             # Finally by trial number
    ),
)
```

### New Sorting Hierarchy (After Fix)

**Constraints enabled:**
1. Feasible Pareto-optimal trials (rank=0, violation=0)
2. Feasible non-Pareto trials (rank=1, violation=0)
3. Infeasible trials (rank=2), sorted by:
   - **Total violation magnitude** (lower = closer to feasible = better)
   - Then primary objective value
   - Then trial number

**Constraints disabled:**
1. Pareto-optimal trials (rank=0)
2. Non-Pareto trials (rank=1)

### Why This Fix Works

1. ✅ **Aligns with Optuna's approach**: NSGAIISampler and TPESampler use violation magnitude
2. ✅ **More useful for users**: Shows "almost feasible" trials first
3. ✅ **Better parameter tuning**: Users can see which parameters get them close to feasibility
4. ✅ **Preserves existing behavior**: Feasible trials still sorted correctly
5. ✅ **Minimal code change**: Only adds one function and one sort key

### Testing Requirements for Issue 2

After implementing the fix, verify:

1. **Strict constraints scenario**
   - Set constraint: `max_drawdown_pct ≤ 20%`
   - Run optimization where most/all trials are infeasible
   - Verify trials with DD=21% appear before DD=40%

2. **Feasible trials unaffected**
   - Pareto-optimal trials still appear first
   - Feasible non-Pareto trials still appear second
   - Primary objective sorting preserved for feasible trials

3. **No constraints scenario**
   - Behavior unchanged from current implementation
   - Only Pareto/non-Pareto sorting applies

4. **UI display**
   - Check Results page (`/results`)
   - Infeasible trials should show in order of "closest to feasible"

---

## Issue 3: Dead Code Function Should Be Removed

### Status: ✅ LOW PRIORITY - Optional cleanup

### Problem Analysis

**Function Never Called:**

**File**: `src/core/optuna_engine.py` (lines 521-556)

```python
def get_best_trial_info(
    study: optuna.Study,
    mo_config: MultiObjectiveConfig,
) -> Optional[Dict[str, Any]]:
    """Get best trial info based on optimization mode."""
    if not mo_config.is_multi_objective():
        best = study.best_trial
        if best is None:
            return None
        return {
            "trial_number": best.number,
            "value": study.best_value,
            "params": best.params,
        }

    pareto_trials = study.best_trials
    if not pareto_trials:
        return None

    primary_idx = mo_config.objectives.index(mo_config.primary_objective)
    primary_direction = OBJECTIVE_DIRECTIONS[mo_config.primary_objective]
    reverse = primary_direction == "maximize"

    sorted_pareto = sorted(
        pareto_trials,
        key=lambda t: t.values[primary_idx],
        reverse=reverse,
    )

    best = sorted_pareto[0]
    return {
        "trial_number": best.number,
        "values": dict(zip(mo_config.objectives, best.values)),
        "params": best.params,
        "pareto_size": len(pareto_trials),
    }
```

**Verification**: Grep search shows this function is ONLY defined, never called:

```bash
$ grep -r "get_best_trial_info" src/
src/core/optuna_engine.py:521:def get_best_trial_info(  # Only definition, no calls
```

**Actual best trial selection** happens in `_finalize_results()` (line 1752):

```python
def _finalize_results(self) -> List[OptimizationResult]:
    ...
    constraints_enabled = any(spec.enabled for spec in self.constraints)
    self.trial_results = sort_optimization_results(
        self.trial_results, self.study, self.mo_config, constraints_enabled
    )

    best_result = self.trial_results[0]  # ✅ Uses sorted results (correct)
    ...
```

### Why This Is Not Actually A Problem

**If the function WERE used, would it be correct?**

According to **Optuna's source code** (https://github.com/optuna/optuna/blob/master/optuna/study/study.py):

```python
@property
def best_trials(self) -> list[FrozenTrial]:
    """Return trials located at the Pareto front in the study."""
    trials = self.get_trials(deepcopy=False)
    is_constrained = any((_CONSTRAINTS_KEY in trial.system_attrs) for trial in trials)

    return _get_pareto_front_trials(self, consider_constraint=is_constrained)
```

✅ **Optuna's `study.best_trials` DOES consider constraints** when calculating Pareto front.

So even if `get_best_trial_info()` were called:
- It uses `study.best_trials` (line 536)
- `study.best_trials` is constraint-aware per Optuna's implementation
- It would filter to feasible Pareto trials automatically
- **The function would work correctly**

### Verdict

**Not a real issue because:**
1. ❌ Function is never called (dead code)
2. ✅ Actual best trial selection uses correct logic (`trial_results[0]` after constraint-aware sorting)
3. ✅ If function were used, Optuna's `study.best_trials` would handle constraints correctly anyway

### The Fix (Optional Cleanup)

**Option 1**: Delete the dead code entirely

**File**: `src/core/optuna_engine.py`

```python
# DELETE lines 521-556
# def get_best_trial_info(...):
#     ...
```

**Option 2**: Keep it with a documentation comment (for potential future use)

```python
def get_best_trial_info(
    study: optuna.Study,
    mo_config: MultiObjectiveConfig,
) -> Optional[Dict[str, Any]]:
    """
    Get best trial info based on optimization mode.

    NOTE: Currently unused. Kept for potential future use.
    Actual best trial selection happens in _finalize_results() using
    sorted trial_results. This function would work correctly if called,
    as study.best_trials is constraint-aware in Optuna.
    """
    # ... existing implementation ...
```

**Recommendation**: **Option 1 (delete)** is preferred for cleaner codebase. If there's potential future use, **Option 2** is acceptable.

### Testing Requirements for Issue 3

No testing required - this is dead code removal.

If keeping the function (Option 2):
- No changes to behavior
- No testing needed

---

## Summary of Changes

### Files to Modify

| File | Changes | Lines Affected |
|------|---------|----------------|
| `src/core/optuna_engine.py` | Issue 1: Remove penalty value logic | ~1356-1366, 1393-1406, 1416, 1425, 1469-1482, 1736 |
| `src/core/optuna_engine.py` | Issue 1: Remove `objective_missing` field/parameter | ~99, 677, 687, 699, 724 |
| `src/core/optuna_engine.py` | Issue 2: Add violation sorting | ~470 (new function), 515-518 |
| `src/core/optuna_engine.py` | Issue 3: Remove dead code | 521-556 |
| `src/core/storage.py` | Issue 1: Remove filter | 333 |

### Code Quality Requirements

**CRITICAL**: These fixes must be:
1. ✅ **Robust**: Handle edge cases (empty constraint_values, None values, etc.)
2. ✅ **Future-proof**: Work with future Optuna versions (using documented APIs only)
3. ✅ **Reliable**: No crashes, no silent failures
4. ✅ **Consistent**: Follow existing code style and naming conventions
5. ✅ **Concise**: Remove all unnecessary code
6. ✅ **Clear**: Add comments explaining Optuna-specific behavior

### Comprehensive Testing Checklist

After implementing all fixes, run these tests:

#### Basic Functionality
- [ ] Single-objective optimization works (no regression)
- [ ] Multi-objective optimization works (no crashes)
- [ ] Constraints work correctly (feasible/infeasible detection)
- [ ] All samplers work: TPESampler, NSGAIISampler, NSGAIIISampler, RandomSampler

#### Issue 1 Verification (Penalty Values → Failed Trials)
- [ ] Trials with missing objectives marked as FAILED (not COMPLETE)
- [ ] Failed trials don't appear in `study.trials` with `state=COMPLETE`
- [ ] Failed trials don't appear in `trial_results`
- [ ] No penalty values (-1e12, 1e12) in saved trials
- [ ] No filtering needed in `_finalize_results()` or `storage.py`
- [ ] TPESampler doesn't crash with multi-objective + missing objectives
- [ ] Database saves clean trials only (no `objective_missing` attribute)

#### Issue 2 Verification (Infeasible Sorting)
- [ ] Feasible Pareto trials appear first
- [ ] Feasible non-Pareto trials appear second
- [ ] Infeasible trials sorted by violation magnitude (lower = better)
- [ ] Within same violation level, sorted by primary objective
- [ ] UI displays trials in correct order
- [ ] Works with no constraints (backward compatibility)

#### Issue 3 Verification (Dead Code Removal)
- [ ] `get_best_trial_info()` removed (or documented as unused)
- [ ] No calls to removed function exist in codebase
- [ ] Best trial selection still works via `trial_results[0]`

#### Edge Cases
- [ ] Empty trial results (no trials completed)
- [ ] All trials failed (no COMPLETE trials)
- [ ] All trials infeasible (no feasible trials)
- [ ] Mixed state: some feasible, some infeasible, some failed
- [ ] Constraint values is None or empty list
- [ ] Objective values is None or empty list

#### Performance
- [ ] No performance regression (optimization speed unchanged)
- [ ] Memory usage stable (no memory leaks from failed trials)
- [ ] Database queries efficient (no extra filtering overhead)

#### Integration
- [ ] Web UI shows correct results
- [ ] Database persistence works correctly
- [ ] Trade export works for all saved trials
- [ ] Preset loading/saving works
- [ ] Walk-forward analysis unaffected

---

## Implementation Instructions for GPT 5.2 Codex

### Step-by-Step Implementation Order

**Phase 1: Issue 1 (Penalty Values) - MUST BE FIRST**
1. Update exception handling in two locations (lines 1393-1406, 1469-1482)
2. Remove `_build_penalty_objectives()` method (lines 1356-1366)
3. Remove `objective_missing` from `OptimizationResult` dataclass (line 99)
4. Remove `objective_missing` from `_trial_set_result_attrs()` signature and body
5. Remove `objective_missing` assignments and calls
6. Remove filtering in `_finalize_results()` (line 1736)
7. Remove filtering in `storage.py` (line 333)
8. Remove `objective_missing` from `_trial_from_optuna()` (lines 699, 724)

**Phase 2: Issue 2 (Infeasible Sorting)**
1. Add `_calculate_total_violation()` helper function
2. Update `sort_optimization_results()` sorting key

**Phase 3: Issue 3 (Dead Code)**
1. Delete `get_best_trial_info()` function (or add "unused" comment)

### Code Style Guidelines

**Follow existing patterns:**
- Use type hints for all function parameters and return values
- Use docstrings for new functions (Google style)
- Preserve existing logging statements (update if needed)
- Match existing indentation (4 spaces)
- Keep line length ≤ 100 characters where reasonable

**Error handling:**
- Preserve exception chain with `raise ... from exc`
- Log warnings for important state changes
- Don't catch exceptions unless you can handle them

**Comments:**
- Explain WHY, not WHAT
- Reference Optuna documentation URLs where relevant
- Mark changes with clear comments for future maintainers

### Common Pitfalls to Avoid

❌ **Don't**:
- Change behavior of feasible trial sorting
- Modify constraint evaluation logic (it's correct)
- Change database schema
- Remove logging that's already present
- Add unnecessary abstraction layers
- Use deprecated Optuna APIs

✅ **Do**:
- Preserve all existing functionality for feasible trials
- Keep changes minimal and focused
- Add comments explaining Optuna-specific behavior
- Test edge cases (None, empty lists, etc.)
- Follow existing code patterns

### Validation Steps

After making changes:

1. **Syntax check**: Ensure no Python syntax errors
2. **Import check**: Verify all imports are present
3. **Type check**: Run mypy/pyright if available
4. **Logic review**: Trace through code paths manually
5. **Edge case review**: Check None/empty handling
6. **Documentation review**: Ensure comments are clear

---

## References and Documentation

### Official Optuna Documentation

**Core Concepts:**
- Trial states: https://optuna.readthedocs.io/en/stable/faq.html
- Multi-objective: https://optuna.readthedocs.io/en/stable/tutorial/20_recipes/002_multi_objective.html
- Constraints: https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.TPESampler.html

**Samplers:**
- TPESampler: https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.TPESampler.html
- NSGAIISampler: https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.NSGAIISampler.html
- NSGAIIISampler: https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.NSGAIIISampler.html

**GitHub Issues:**
- TPE + Multi-objective + Pruning: https://github.com/optuna/optuna/issues/5260
- Failed vs Pruned trials: https://github.com/optuna/optuna/issues/1647
- Constraint violation discussion: https://github.com/optuna/optuna/discussions/5259

### Merlin Project Documentation

- Project overview: `docs/PROJECT_OVERVIEW.md`
- AI assistant guidance: `CLAUDE.md`
- Issue documentation:
  - `docs/phase_4-1_fixes_PENALTY-ISSUE_sonnet.md`
  - `docs/phase_4-1_fixes_SORTING-ISSUE+DEAD-CODE_sonnet.md`

---

## Expected Outcomes

### After Implementing All Fixes

**Code Quality:**
- ✅ Cleaner codebase (removed ~100+ lines of unnecessary code)
- ✅ Follows Optuna best practices
- ✅ More maintainable (less special-case logic)
- ✅ Better documented (clear comments on Optuna behavior)

**Functionality:**
- ✅ Multi-objective optimization works correctly
- ✅ No TPE crashes with missing objectives
- ✅ Failed trials properly ignored by samplers
- ✅ Infeasible trials sorted logically
- ✅ No dead code confusion

**User Experience:**
- ✅ More useful trial ordering (least-violated infeasible trials first)
- ✅ Cleaner results display (no fake penalty trials)
- ✅ Faster optimization (samplers ignore failed trials)
- ✅ More intuitive UI (violations clearly indicated)

**Performance:**
- ✅ Faster sampling (fewer trials to process)
- ✅ Less memory usage (failed trials not stored)
- ✅ Cleaner database (no filtering overhead)

---

## Final Notes for GPT 5.2 Codex

### Priority Order
1. **Issue 1** (CRITICAL) - Must fix first, enables cleaner code
2. **Issue 2** (MEDIUM) - Improves UX, aligns with Optuna
3. **Issue 3** (LOW) - Optional cleanup

### Success Criteria

**The implementation is successful if:**
1. All tests pass (basic functionality + issue-specific + edge cases)
2. No regressions in existing features
3. Code is cleaner and more maintainable than before
4. Follows Optuna documented best practices
5. All three issues are properly addressed

### Questions/Clarifications

If any ambiguity arises during implementation:
1. **Check Optuna docs first** - Official documentation is authoritative
2. **Preserve existing behavior** - For feasible trials, constraints, etc.
3. **Minimal changes** - Don't over-engineer or add unnecessary features
4. **Ask for clarification** - If truly unclear, document assumptions

---

## Appendix: Complete Code Context

### Relevant Type Definitions

**From `src/core/optuna_engine.py`:**

```python
@dataclass
class OptimizationResult(StrategyResult):
    """Result from a single optimization trial."""
    # ... existing StrategyResult fields ...

    optuna_trial_number: Optional[int] = None
    objective_values: List[float] = field(default_factory=list)
    constraint_values: List[float] = field(default_factory=list)
    constraints_satisfied: Optional[bool] = None
    is_pareto_optimal: Optional[bool] = None
    dominance_rank: Optional[int] = None
    objective_missing: bool = False  # TO BE REMOVED in Issue 1
```

### Helper Functions

```python
def _is_nan(value: Any) -> bool:
    """Check if value is NaN."""
    return isinstance(value, float) and math.isnan(value)

def evaluate_constraints(
    all_metrics: Dict[str, Any],
    constraints: List[ConstraintSpec],
) -> List[float]:
    """
    Evaluate constraint violations.

    Returns list of violation values:
    - value > 0: constraint is VIOLATED
    - value ≤ 0: constraint is SATISFIED
    """
    violations: List[float] = []
    for spec in constraints:
        if not spec.enabled:
            continue
        value = all_metrics.get(spec.metric)
        if value is None or _is_nan(value):
            violations.append(1.0)  # Treat missing as violated
            continue

        value = float(value)
        if spec.operator == "gte":
            violations.append(spec.threshold - value)  # violation if value < threshold
        elif spec.operator == "lte":
            violations.append(value - spec.threshold)  # violation if value > threshold
        else:
            violations.append(0.0)

    return violations
```

### Constants

```python
OBJECTIVE_DIRECTIONS = {
    "score": "maximize",
    "net_profit": "maximize",
    "net_profit_pct": "maximize",
    "romad": "maximize",
    "sharpe_ratio": "maximize",
    "max_drawdown_pct": "minimize",
    "profit_factor": "maximize",
    "sqn": "maximize",
    "ulcer_index": "minimize",
}
```

---

**End of Implementation Prompt**

This prompt provides comprehensive, clear instructions for fixing all three issues with robust, future-proof, reliable, consistent, concise, and clear code following Optuna best practices.
