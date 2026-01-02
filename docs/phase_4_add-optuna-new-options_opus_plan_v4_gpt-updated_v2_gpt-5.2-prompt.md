# GPT-5.2 Codex Implementation Prompt — Merlin Phase 4 Optuna Enhancements (Plan v4)

You are an agent coder working inside the Merlin codebase. Implement **Phase 4: Optuna Enhancement Plan v4** exactly as specified in:
- `phase_4_add-optuna-new-options_opus_plan_v4_gpt-updated_v2.md` (the authoritative spec)

## Goal

Upgrade Merlin’s Optuna optimization module to support:

1) **Multi-objective optimization** (1–6 objectives, Pareto front handling, primary objective for sorting)  
2) **Soft constraints** (metrics-based feasibility, deprioritize infeasible trials; do not hard-prune based on constraints)  
3) **Extended samplers** (Random, TPE, NSGA-II, NSGA-III + configurable NSGA settings)  
4) UI support for all of the above + results rendering with Pareto + constraint indicators  
5) Storage update for a **fresh DB schema** (no migration/back-compat required)

## Non‑negotiable engineering constraints

### A) Do NOT change Merlin’s concurrency model
Merlin already uses a multi-process architecture (separate worker processes + shared Optuna storage). **Do not replace this with `study.optimize(..., n_jobs=...)`** and do not switch to thread-based parallelism.

Keep existing:
- Worker process spawning and its communication pattern.
- Shared Optuna storage mechanism (e.g., JournalStorage / file backend, or whatever the current module uses).
- Total trial budget coordination via existing callback/limits.

Your changes must integrate into the existing engine, not rewrite the execution approach.

### B) Pruning behavior in multi-objective
Optuna’s `trial.should_prune()` is **not supported** for multi-objective optimization. Therefore:
- If `len(objectives) > 1`: disable pruning end-to-end (UI should hide/disable pruner, backend must not call `trial.should_prune()`).
- If `len(objectives) == 1`: keep existing pruning behavior as-is.

### C) Fresh DB
There is **no migration**. Update schema creation and assume the DB will be recreated from scratch. Remove any migration scaffolding.

### D) Multi-objective correctness
- Use `optuna.create_study(direction=...)` when 1 objective.
- Use `optuna.create_study(directions=[...])` when 2+ objectives.
- Multi-objective objective function must return a tuple of floats in the same order as `objectives`.
- Call `study.set_metric_names([...])` when multi-objective.

### E) Constraints semantics
- Constraint violations are represented as floats:
  - `<= 0` means **feasible**
  - `> 0` means **violated**
- Missing/NaN constraint metric values are treated as **violated**.
- Constraints are **soft**: infeasible trials must still be stored, but should be **deprioritized** in results.

### F) Sorting contract (default UI ordering)
- 1 objective: sort by objective value (direction-aware).
- 2+ objectives: sort by Pareto membership first, then by **primary objective** (direction-aware), then by trial_number as tie-breaker.
- **If constraints are enabled:** compute Pareto membership only among feasible trials, and sort:
  1) feasible + Pareto
  2) feasible + non-Pareto
  3) infeasible
  Within each group: by primary objective, then trial_number.

Do not rely on any incidental ordering of `study.best_trials`; explicitly implement a deterministic ordering.

---

## Required file changes (high level)

Backend (Python):
- `src/core/optuna_engine.py` (core logic for objectives, constraints, sampler config, study creation, sorting, best trial selection)
- `src/core/storage.py` (fresh DB schema + persistence changes for studies/trials)
- `src/ui/server.py` (server-side validation + payload parsing + passing config into engine)

Frontend:
- `src/ui/templates/index.html` (new objectives + constraints + NSGA settings UI)
- `src/ui/templates/results.html` (Pareto + constraint indicators + new settings summary)
- `src/ui/static/js/ui-handlers.js` (integration glue only)
- `src/ui/static/js/results.js` (integration glue only)
- **NEW:** `src/ui/static/js/optuna-ui.js`
- **NEW:** `src/ui/static/js/optuna-results-ui.js`
- `src/ui/static/css/style.css` (styling additions for new UI blocks and badges)

Docs:
- `CLAUDE.md` (or project docs file referenced by plan)

---

## Implementation checklist (follow the plan sections)

### 1) Multi-objective core (backend)

Implement the constants exactly as in the plan:
- `OBJECTIVE_DIRECTIONS`
- `OBJECTIVE_DISPLAY_NAMES`

Add:
- `MultiObjectiveConfig` dataclass with:
  - `objectives: List[str]`
  - `primary_objective: Optional[str]`
  - `is_multi_objective()`
  - `get_directions()`
  - `get_single_direction()`
  - `get_metric_names()`

Implement `create_optimization_study(...)`:
- if multi-objective: use `directions=...` + `set_metric_names`
- else: use `direction=...`

Update objective function creation:
- Run a single backtest per trial.
- Compute metrics dict including: objectives + constraints metrics + total_trades (and all metrics listed in plan).
- For each selected objective:
  - if value is None/NaN: raise `optuna.TrialPruned(...)` (per plan).
- ALWAYS set:
  - `trial.set_user_attr("merlin.constraint_values", constraint_values)` (even if empty list)
  - `trial.set_user_attr("merlin.all_metrics", all_metrics)` (or whatever minimal set is needed for persistence/debug)
- Return:
  - single float (1 objective)
  - tuple(...) (2+ objectives)

### 2) Soft constraints (backend)

Implement:
- `CONSTRAINT_OPERATORS`
- `ConstraintSpec` dataclass (metric, threshold, enabled, operator property)

Implement:
- `evaluate_constraints(all_metrics, constraints_specs)`:
  - Only include enabled constraints
  - Missing/NaN => append `1.0`
  - For gte: `threshold - value`
  - For lte: `value - threshold`
  - Return list in the same order as enabled constraints

Implement:
- `create_constraints_func(constraints_specs)`:
  - if no enabled constraints: return None
  - else return function that:
    - reads `trial.user_attrs["merlin.constraint_values"]`
    - if missing or wrong length: return `[1.0] * n_enabled`

IMPORTANT: pass `constraints_func` into **both** TPESampler and NSGA samplers when constraints are enabled.

### 3) Samplers (backend)

Implement `SamplerConfig` and `create_sampler(config, constraints_func)` exactly per plan, supporting:
- `tpe`
- `nsga2`
- `nsga3`
- `random`

For NSGA samplers, implement conditional settings:
- `population_size`
- `crossover_prob`
- `mutation_prob`
- `swapping_prob`

### 4) Results sorting + “best trial” selection (backend)

Implement `sort_optimization_results(...)` per Sorting Contract above.
- Must be deterministic.
- Must handle constraints-enabled mode (feasible grouping + feasible-only Pareto).
- Must be direction-aware for primary objective (maximize/minimize).

Implement `get_best_trial_info(...)`:
- Single objective: use `study.best_trial`, `study.best_value`, `study.best_params`.
- Multi-objective: choose a “best” among Pareto trials by sorting Pareto trials using primary objective (direction-aware), with tie-breaker by trial_number.

### 5) Server-side validation (server.py)

Implement validation functions exactly per plan:
- `validate_objectives_config(objectives, primary_objective)`
  - 1–6 objectives
  - primary required if >1 and must be in objectives
  - objectives must be known keys
- `validate_constraints_config(constraints_payload)`
  - validate enabled constraints only
  - metric must be known
  - threshold must be float-parsable
- `validate_sampler_config(...)`
  - sampler in allowed set
  - nsga fields in valid ranges

Update `/api/optimize` payload parsing:
- New request fields (match the plan and update UI accordingly):
  - `objectives: string[]`
  - `primary_objective?: string`
  - `constraints: [{metric, threshold, enabled}]`
  - sampler + nsga params + n_startup_trials (tpe)
- Keep legacy keys only if plan explicitly requires backward compatibility (it does not).

### 6) Storage (fresh DB schema, no migration)

Update `storage.py`:
- Implement the `studies` and `trials` schema as specified in plan section 6.
- Persist:
  - objectives_json, directions_json, primary_objective
  - constraints_json
  - sampler settings
  - objective_values_json per trial
  - constraint_values_json and constraints_satisfied per trial
  - is_pareto_optimal per trial
  - best_values_json for multi-objective studies (and best_value for single-objective if needed by UI)

Since DB is fresh:
- You may remove old “legacy” fields only if nothing else uses them.
- If legacy fields still used in other parts of UI, keep them but ensure new fields are populated.

### 7) Frontend UI (index.html)

Replace old single-target dropdown with:
- **OPTIMIZATION OBJECTIVES** section:
  - 10 checkboxes (from plan), with ↑/↓ indicators and direction labels
  - enforce 1–6 selection in UI (disable extra checks when 6 selected)
  - show **Primary Objective** dropdown only when 2+ checked, values must be the checked objectives

Add **OPTIMIZATION CONSTRAINTS** section (collapsible):
- per plan list + defaults
- show note “Trials violating constraints are deprioritized (not pruned)”

Add **NSGA SAMPLER SETTINGS** section:
- only visible when sampler is NSGA-II or NSGA-III

Add new script tags:
- Load `optuna-ui.js` on index page before `ui-handlers.js` (so ui-handlers can call its functions)

### 8) Frontend Results (results.html)

Add:
- Pareto badge display
- constraint feasibility indicator (✓/✗)
- dynamic objective columns when multi-objective
- settings summary should display objectives list + primary + constraints summary

Add new script tags:
- Load `optuna-results-ui.js` on results page before `results.js`

### 9) New JS files (Option B)

Create: `src/ui/static/js/optuna-ui.js`
Must export (via `window.OptunaUI = {...}` or equivalent pattern used in project):
- `updateObjectiveSelection()`
- `toggleNsgaSettings()`
- `collectObjectives()` -> `{ objectives: [...], primary_objective: ... }`
- `collectConstraints()` -> array of constraint specs

Create: `src/ui/static/js/optuna-results-ui.js`
Must export:
- `buildTrialTableHeaders(objectives, hasConstraints)` -> header DOM or HTML string
- `renderTrialRow(trial, objectives, flags)` -> row DOM/HTML including Pareto badge + feasible indicator

Modify `ui-handlers.js` minimally:
- Initialize Optuna UI by calling functions in `OptunaUI`
- On optimize submit: merge `collectObjectives()` + `collectConstraints()` output into request payload

Modify `results.js` minimally:
- Call helpers to build headers and render rows using response data

### 10) CSS updates

Add styles for:
- objective checkbox list layout
- primary objective dropdown
- constraint rows + collapsible panel
- badges: Pareto, feasible/infeasible

---

## API / data shape expectations (align UI and backend)

Request payload to `/api/optimize` must include at least:
```json
{
  "objectives": ["net_profit_pct", "max_drawdown_pct"],
  "primary_objective": "net_profit_pct",
  "constraints": [
    {"metric":"total_trades","threshold":30,"enabled":true},
    {"metric":"max_drawdown_pct","threshold":25.0,"enabled":true}
  ],
  "sampler": "nsga2",
  "population_size": 50,
  "crossover_prob": 0.9,
  "mutation_prob": null,
  "swapping_prob": 0.5,
  "n_startup_trials": 20
}
```

Response used by results UI must include per-trial:
- `trial_number`
- `params`
- `objective_values` (array aligned with objectives) OR map `{metric:value}` (choose one, but keep consistent)
- `is_pareto_optimal`
- `constraints_satisfied` (boolean)
- `constraint_values` (array) (optional in UI but must be stored)

Also return study-level fields:
- `objectives`, `directions`, `primary_objective`
- `pareto_front_size`
- `best_trial_info` (single-objective or derived in multi-objective)

---

## Acceptance criteria (must pass)

1) Single objective runs behave exactly as before (best_trial, best_value, best_params, pruning works).
2) Multi-objective runs:
   - Objective returns tuple
   - `study.best_trials` produces Pareto set
   - UI shows Pareto badge and objective columns
   - Default table ordering matches sorting contract (Pareto-first, then primary objective)
3) Constraints enabled:
   - constraint_values recorded for every successful trial
   - feasibility computed correctly (`<=0` all constraints)
   - feasible trials appear before infeasible in UI
   - Pareto computed among feasible trials (ignore infeasible) and labeled accordingly
4) Sampler selection works:
   - TPE / Random work in single & multi-objective (as supported by Optuna)
   - NSGA-II and NSGA-III work in multi-objective and accept NSGA settings
   - constraints_func passed where applicable
5) Fresh DB schema creates and app runs from empty DB without migrations.

---

## Reference links (Optuna) — for coder only (URLs are in a code block)

```text
create_study (direction vs directions):
https://optuna.readthedocs.io/en/stable/reference/generated/optuna.create_study.html

Study.best_trials (Pareto front set for multi-objective):
https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.Study.html

Trial.should_prune limitation (multi-objective unsupported):
https://optuna.readthedocs.io/en/stable/reference/generated/optuna.trial.Trial.html

TPESampler (constraints_func supported; evaluated after successful trials only):
https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.TPESampler.html

NSGAIISampler (multi-objective sampler; constraints_func supported):
https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.NSGAIISampler.html
```

---

## Output

Implement the update fully. Commit-style discipline:
- Keep changes scoped to the plan.
- Avoid large refactors unrelated to Phase 4.
- Keep `ui-handlers.js` and `results.js` changes minimal; move Optuna-specific logic into the two new JS files.

If any plan detail conflicts with current code reality, follow this priority:
1) This prompt
2) Plan v4 document
3) Existing code
and document the decision in a short comment in the relevant file.
