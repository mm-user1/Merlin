# Merlin — Sanitization Behavior (Phase 4.2, v1.0.19_4-2)

This document describes **exactly** how *objective sanitization* works in Merlin after the “Sanitize if Total Trades <= …” update (Phase 4.2).

It covers:
- UI settings and defaults
- How settings flow from UI → API → engine → storage
- All sanitization decision branches (single-objective vs multi-objective, constraints on/off, PF edge cases, sanitization disabled)
- The exact “trial outcome” semantics (COMPLETE vs FAIL) and why that matters for Optuna

> Scope note: “Sanitization” here only refers to the Phase 4.2 feature that **replaces non-finite objective values with 0.0 under a trades threshold**. It does **not** modify your underlying strategy simulation; it only affects what is returned to Optuna as objective values.

---

## 1) Terminology and key concepts

### 1.1 Objective vs metric vs constraint
- **Metric**: any value computed by Merlin’s backtest (e.g., `net_profit_pct`, `profit_factor`, `sharpe_ratio`, `total_trades`).
- **Objective**: a metric selected in “Optimization Objectives” that Merlin returns to Optuna for optimization (single value or tuple).
- **Constraint metric**: a metric referenced by an enabled constraint rule. Constraints are evaluated *separately* from objectives.

### 1.2 “Non-finite” values
Merlin treats these as **non-finite**:
- `None`
- `NaN`
- `+inf`
- `-inf`
- values that cannot be converted to `float`

Merlin implements this by using `math.isfinite(float(x))` (non-finite if that returns `False`) plus `None` checks. (See “Sources” for Python docs.)

### 1.3 What “FAIL” means in Optuna
Merlin fails a trial by returning `NaN` as the objective value(s). Optuna treats this as a **failed trial** (state `FAIL`) but does not abort the study. Failed trials are ignored by built-in samplers when sampling new parameters.  
This is an important reason sanitization exists: sanitizing can keep some edge-case trials “successful” instead of failing.

(See Optuna citations in “Sources”.)

---

## 2) UI settings (Optuna Settings → index page)

### 2.1 Controls
Merlin provides:

- **Checkbox**: “Sanitize if Total Trades <=”
- **Integer input**: threshold `N`

### 2.2 Defaults
- `sanitize_enabled = true` (checkbox checked)
- `sanitize_trades_threshold = 0`

Meaning: sanitization only triggers when `total_trades <= 0` (in practice, `total_trades == 0`).

### 2.3 Placement and help text
The sanitize controls appear:
- Under **Optimization Objectives**
- Above **Optimization budget**

A small hint line is shown under the input:
- `Sanitizes: Sharpe, Sortino, SQN, Profit Factor`

---

## 3) Settings flow (UI → API → engine → storage)

### 3.1 Request payload
When starting optimization, the UI sends:

```json
{
  "sanitize_enabled": true,
  "sanitize_trades_threshold": 0
}
```

### 3.2 Server parsing and validation
On the backend:
- Missing fields default to:
  - `sanitize_enabled = True`
  - `sanitize_trades_threshold = 0`
- `sanitize_trades_threshold` must be an integer `>= 0` (negative values are rejected).

### 3.3 Engine config
These fields are stored in `OptunaConfig`:
- `sanitize_enabled: bool`
- `sanitize_trades_threshold: int`

### 3.4 Persistence (study storage)
Merlin stores the sanitize settings with the study record:
- `sanitize_enabled`
- `sanitize_trades_threshold`

This supports reproducibility: you can always see what sanitization settings were used for a completed study.

---

## 4) What exactly gets sanitized

### 4.1 Sanitization whitelist
Merlin only sanitizes objectives for this explicit whitelist:

- `sharpe_ratio`
- `sortino_ratio`
- `sqn`
- `profit_factor`

If you select any other objective (e.g., `romad`, `ulcer_index`, `net_profit_pct`) and it becomes non-finite, Merlin does **not** sanitize it, and the trial will fail.

### 4.2 Sanitization applies to objectives only
Sanitization changes **only the objective values returned to Optuna**.

It does **not** mutate the `all_metrics` dict that is used to evaluate constraints.
So constraints always see the “raw” metric values computed by the backtest, not the sanitized objective values.

---

## 5) The objective evaluation pipeline (per trial)

For each Optuna trial, Merlin’s objective function roughly does:

1. Run strategy/backtest for trial parameters → compute `result`
2. Collect `all_metrics` from `result` (includes `total_trades`)
3. Extract objective values (floats) in the same order as selected objectives
4. Apply sanitization rules (Phase 4.2)
5. If trial should fail → return NaN objective(s) immediately
6. Otherwise evaluate constraints (if any enabled)
7. Store objective/constraint values on result and on trial attrs
8. Return objective value(s) to Optuna

Two internal helpers implement the key logic:
- `_sanitize_objective_values(...)`
- `_prepare_objective_values(...)` (checks “force fail” and remaining non-finite values)

---

## 6) Sanitization decision logic (ALL CASES)

Let:
- `enabled = sanitize_enabled`
- `N = sanitize_trades_threshold`
- `T = total_trades` from `all_metrics`

### 6.1 Gate condition: when sanitization is allowed to run
Sanitization is applied only if **all** are true:

1) `enabled == True`  
2) `T` is **finite** (not None/NaN/inf and convertible to float)  
3) `float(T) <= N`

If any of these are false, sanitization does not run.

### 6.2 Profit Factor special rule (PF “infinite” handling)
**Before** the gate condition is even considered:

- If `profit_factor` is among selected objectives **and** its extracted objective value is `+inf` or `-inf`, Merlin sets `force_fail = True`.

This is independent of:
- `sanitize_enabled` on/off
- `sanitize_trades_threshold`
- constraints on/off

**Important nuance**: this PF “infinite fail” rule only triggers if `profit_factor` is a selected **objective**. If PF is not an objective, PF being infinite does not automatically fail the trial.

### 6.3 Sanitization rules for each metric (when gate is open)

When the gate condition is true (`enabled && T<=N`), Merlin walks the objective list and applies:

#### A) Sharpe / Sortino / SQN
If objective metric is one of:
- `sharpe_ratio`
- `sortino_ratio`
- `sqn`

and the extracted objective value is non-finite (`None`, NaN, +inf, -inf):
- replace it with `0.0`

#### B) Profit Factor (PF)
If objective metric is `profit_factor` and:
- value is non-finite **but not** infinite (i.e., `None`/NaN):
  - replace it with `0.0`

If PF value is `+inf`/`-inf`:
- **never sanitized**
- already handled by the earlier “force_fail” rule (trial fails)

### 6.4 Final strictness check (after sanitization)
After sanitization runs (or is skipped), Merlin checks objective_values:

- If `force_fail == True` **OR** any objective value remains non-finite:
  - trial is marked to fail
  - Merlin returns NaN objective(s)

---

## 7) Outcomes by scenario

### 7.1 Single-objective vs multi-objective return shapes
- **Single-objective**: Merlin returns a single float.
  - Failure return: `float("nan")`
- **Multi-objective**: Merlin returns a tuple of floats with length = number of objectives.
  - Failure return: `(nan, nan, ..., nan)` (same length as objectives)

### 7.2 Constraints enabled vs disabled
- If **constraints are disabled**: Merlin simply returns objectives (or fails) and does not compute constraint violations.
- If **constraints are enabled**:
  - Merlin computes a violations vector.
  - Missing/non-finite constraint metrics are treated as violated (violation `1.0`).
  - Constraints evaluation is **skipped** if the trial fails early (because Merlin returns NaN objective(s) immediately).

> This is aligned with Optuna’s documented behavior: `constraints_func` is evaluated only after successful trials and is not called when trials fail or are pruned. (See “Sources”.)

---

## 8) Comprehensive case matrix

This matrix assumes “objective value becomes non-finite” during metric computation.

### 8.1 Sanitization disabled (`sanitize_enabled = False`)
| Condition | Outcome |
|---|---|
| Any selected objective value is non-finite | Trial FAIL (Merlin returns NaN objective(s)) |
| PF is an objective and PF is ±inf | Trial FAIL (via “force_fail”) |
| PF is not an objective and PF is ±inf | No automatic failure (unless some selected objective is non-finite). If PF is a **constraint**, it becomes violated (see below). |

### 8.2 Sanitization enabled but gate closed
Gate closes when:
- `total_trades` is non-finite / missing, or
- `total_trades > N`

| Condition | Outcome |
|---|---|
| Any selected objective value is non-finite | Trial FAIL (NaN objective(s)) |
| PF is an objective and PF is ±inf | Trial FAIL (via “force_fail”) |

### 8.3 Sanitization enabled and gate open (`total_trades <= N`)
| Objective metric | Non-finite type | Result |
|---|---|---|
| Sharpe / Sortino / SQN | None/NaN/±inf | Sanitized to `0.0` |
| Profit Factor | None/NaN | Sanitized to `0.0` |
| Profit Factor | ±inf | Trial FAIL (via “force_fail”, regardless of gate) |
| Any other objective | None/NaN/±inf | Not sanitized → Trial FAIL |

### 8.4 Constraints-specific behavior (independent of sanitization)
Constraints are computed only if the trial is not failed early.

If a constraint metric is missing/non-finite:
- Merlin treats it as violated (adds `1.0` violation)

So:
- PF is ±inf and PF is used as a **constraint** (but not objective) → PF constraint is violated (violation 1.0), trial still completes if objectives are finite.
- PF is ±inf and PF is used as **objective** → trial fails before constraints are computed.

---

## 9) Trial metadata side-effects

If sanitization occurs (i.e., at least one objective value was replaced with 0.0), Merlin records:

- `trial.set_user_attr("merlin.sanitized_metrics", ["metric1", "metric2", ...])`

This is an Optuna trial user attribute stored in Optuna’s study storage (not in Merlin’s separate “studies” DB table, unless you later export or sync it explicitly).

---

## 10) Practical examples

### Example A — default settings (enabled, N=0), objective = Sharpe
- `total_trades == 0`
- `sharpe_ratio == NaN`

Gate open (`0 <= 0`), Sharpe is in whitelist → objective sanitized:
- Sharpe objective returned as `0.0`
- Trial is successful (COMPLETE), not FAIL.

### Example B — default settings, objective = Sharpe, trades=5
- `total_trades == 5`
- `sharpe_ratio == NaN`

Gate closed (`5 > 0`) → no sanitization.
Non-finite objective remains → trial FAIL (returns NaN).

### Example C — PF is objective, PF is +inf
- Regardless of sanitize on/off, threshold, constraints:
  - PF objective is ±inf → force_fail → trial FAIL (NaN objective(s))

### Example D — PF is NOT objective, PF is constraint, PF is +inf
- Objectives are finite (e.g., `net_profit_pct` is finite)
- Constraints enabled and include PF
- PF is non-finite → PF constraint violation `1.0`
- Trial still completes (COMPLETE), but is marked infeasible by constraints.

---

## 11) Where to look in code

(These are “current Merlin state after Phase 4.2” locations.)

- `src/core/optuna_engine.py`
  - `SANITIZE_METRICS`
  - `_is_non_finite`, `_is_inf`
  - `_sanitize_objective_values`
  - `_prepare_objective_values`
  - Objective function `_objective` (and worker variant if applicable)
  - `evaluate_constraints`

- `src/ui/templates/index.html` (sanitize controls)
- `src/ui/static/js/optuna-ui.js` (collectSanitizeConfig + initSanitizeControls)
- `src/ui/static/js/ui-handlers.js` (payload builder)
- `src/ui/server.py` (request parsing + validation)
- `src/core/storage.py` (study persistence columns)

---

## 12) Sources (external behavior references)

Optuna docs and Python docs are included here because they define the meaning of “trial FAIL” and the behavior of samplers/constraints.

```text
Optuna FAQ: NaNs are treated as failures but do not abort studies
https://optuna.readthedocs.io/en/latest/faq.html
(Section: “How are NaNs returned by trials handled?”)

Optuna samplers (TPE): failed trials are ignored by built-in samplers
https://optuna.readthedocs.io/en/v4.5.0/reference/samplers/generated/optuna.samplers.TPESampler.html
(Note: “failed trials are ignored … regarded as deleted”)

Optuna constraints_func: evaluated after each successful trial; not called for failed/pruned trials
https://optuna.readthedocs.io/en/v4.5.0/reference/samplers/generated/optuna.samplers.TPESampler.html
(Section: constraints_func)

Python: math.isfinite(x) returns False for NaN and infinities
https://docs.python.org/3/library/math.html#math.isfinite
```

---

## 13) Summary (one paragraph)

Merlin’s Phase 4.2 sanitization is a **threshold-gated, whitelist-only** transformation applied **only to Optuna objective return values**.

When `sanitize_enabled` is ON and `total_trades <= sanitize_trades_threshold`:
- `sharpe_ratio`, `sortino_ratio`, `sqn`: any non-finite objective value (`None`, `NaN`, `+inf`, `-inf`, or non-parsable) is replaced with `0.0`.
- `profit_factor`: `None`/`NaN` is replaced with `0.0` (but `+inf`/`-inf` is never replaced).

Profit Factor objective values of `+inf` or `-inf` cause the trial to FAIL **only when `profit_factor` is selected as an objective**, via a `NaN` objective return.

If the sanitize gate is closed (e.g., `total_trades > threshold` or `total_trades` is missing/non-finite) or sanitization is OFF, Merlin runs in strict mode: any non-finite selected objective value causes the trial to FAIL via `NaN` objective return(s).

Constraints are evaluated only for trials that do not fail early, and missing/non-finite constraint metrics are treated as violated. Sanitization does not change the raw metrics used for constraints evaluation.
