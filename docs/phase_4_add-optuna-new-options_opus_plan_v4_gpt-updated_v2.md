# Phase 4: Optuna Enhancement Plan v4

**Version:** 4.0 (Final)
**Date:** 2025-12-30
**Status:** Ready for Implementation
**Author:** Claude Opus 4.5

---

## Executive Summary

This document outlines the implementation plan for enhancing Merlin's Optuna optimization module with:

1. **Multi-Objective Optimization** - Optimize multiple metrics simultaneously
2. **Soft Constraints** - Enforce minimum/maximum requirements on metrics
3. **Extended Samplers** - NSGA-II, NSGA-III support with configuration options

**Database:** Fresh database will be created (no migration needed).

---

## Table of Contents

1. [Requirements Summary](#1-requirements-summary)
2. [Multi-Objective Optimization](#2-multi-objective-optimization)
3. [Soft Constraints](#3-soft-constraints)
4. [Sampler Configuration](#4-sampler-configuration)
5. [Server-Side Validation](#5-server-side-validation)
6. [Database Schema](#6-database-schema)
7. [UI Changes](#7-ui-changes)
8. [Implementation Phases](#8-implementation-phases)

---

## 1. Requirements Summary

### 1.1 Key Decisions

| Topic | Decision |
|-------|----------|
| Multi-objective UI | Checkboxes for all metrics, hardcoded min/max direction with arrow indicator |
| Primary objective | Dropdown to select primary (for sorting Pareto trials) |
| Results sorting | 1 objective = by value, 2+ objectives = Pareto first, then by primary objective |
| Constraints | Soft constraints only (deprioritize, don't prune) |
| Constraint metrics | All Merlin metrics + Total Trades |
| Sampler selection | Dropdown with explicit user selection |
| Database | Fresh database (reset existing) |

### 1.2 Implementation Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Study creation | `direction=` for 1 objective, `directions=` for 2+ | Keeps single-objective clean with `best_trial` access |
| Optuna directions | Use native directions, not negation | Clearer, works with Optuna tooling |
| Missing objective values | Trial fails (pruned) | Prevents misleading Pareto fronts |
| Missing constraint values | Always set; default = violated | Conservative, robust behavior |
| NSGA-III reference points | Use Optuna defaults | Simplest approach |

---

## 2. Multi-Objective Optimization

### 2.1 Available Objectives

| Metric | Display Name | Direction | Arrow |
|--------|--------------|-----------|-------|
| `net_profit_pct` | Net Profit % | maximize | ↑ |
| `max_drawdown_pct` | Max Drawdown % | minimize | ↓ |
| `sharpe_ratio` | Sharpe Ratio | maximize | ↑ |
| `sortino_ratio` | Sortino Ratio | maximize | ↑ |
| `romad` | RoMaD | maximize | ↑ |
| `profit_factor` | Profit Factor | maximize | ↑ |
| `win_rate` | Win Rate % | maximize | ↑ |
| `sqn` | SQN | maximize | ↑ |
| `ulcer_index` | Ulcer Index | minimize | ↓ |
| `consistency_score` | Consistency % | maximize | ↑ |

### 2.2 Primary Objective

When 2+ objectives selected, user must choose a **primary objective** from the selected objectives.

**Purpose:**
- Provides clear sorting within Pareto front
- Answers "which trial should I pick?"

**Sorting rule:**
1. Pareto-optimal trials first
2. Within each group: sort by primary objective value

### 2.3 UI Design

```
┌─────────────────────────────────────────────────────────────┐
│ OPTIMIZATION OBJECTIVES                                      │
├─────────────────────────────────────────────────────────────┤
│ Select 1-6 objectives:                                      │
│                                                             │
│ ☑ Net Profit %        ↑ maximize                           │
│ ☑ Max Drawdown %      ↓ minimize                           │
│ ☐ Sharpe Ratio        ↑ maximize                           │
│ ☐ Sortino Ratio       ↑ maximize                           │
│ ☐ RoMaD               ↑ maximize                           │
│ ☐ Profit Factor       ↑ maximize                           │
│ ☐ Win Rate %          ↑ maximize                           │
│ ☐ SQN                 ↑ maximize                           │
│ ☐ Ulcer Index         ↓ minimize                           │
│ ☐ Consistency %       ↑ maximize                           │
│                                                             │
│ Primary Objective: [▼ Net Profit %    ]  (for sorting)     │
│                    ↳ Only visible when 2+ objectives        │
└─────────────────────────────────────────────────────────────┘
```

### 2.4 Implementation

**Constants:**
```python
OBJECTIVE_DIRECTIONS: Dict[str, str] = {
    "net_profit_pct": "maximize",
    "max_drawdown_pct": "minimize",
    "sharpe_ratio": "maximize",
    "sortino_ratio": "maximize",
    "romad": "maximize",
    "profit_factor": "maximize",
    "win_rate": "maximize",
    "sqn": "maximize",
    "ulcer_index": "minimize",
    "consistency_score": "maximize",
}

OBJECTIVE_DISPLAY_NAMES: Dict[str, str] = {
    "net_profit_pct": "Net Profit %",
    "max_drawdown_pct": "Max Drawdown %",
    "sharpe_ratio": "Sharpe Ratio",
    "sortino_ratio": "Sortino Ratio",
    "romad": "RoMaD",
    "profit_factor": "Profit Factor",
    "win_rate": "Win Rate %",
    "sqn": "SQN",
    "ulcer_index": "Ulcer Index",
    "consistency_score": "Consistency %",
}
```

**Configuration:**
```python
@dataclass
class MultiObjectiveConfig:
    """Configuration for optimization objectives."""
    objectives: List[str]
    primary_objective: Optional[str] = None  # Required if len(objectives) > 1

    def is_multi_objective(self) -> bool:
        return len(self.objectives) > 1

    def get_directions(self) -> List[str]:
        """Get Optuna directions for all objectives."""
        return [OBJECTIVE_DIRECTIONS[obj] for obj in self.objectives]

    def get_single_direction(self) -> str:
        """Get single direction for single-objective mode."""
        assert len(self.objectives) == 1
        return OBJECTIVE_DIRECTIONS[self.objectives[0]]

    def get_metric_names(self) -> List[str]:
        """Get display names for set_metric_names()."""
        return [OBJECTIVE_DISPLAY_NAMES[obj] for obj in self.objectives]
```

**Study Creation (Single vs Multi-objective):**
```python
def create_optimization_study(
    mo_config: MultiObjectiveConfig,
    sampler: optuna.samplers.BaseSampler,
    study_name: str = None,
    storage = None,
) -> optuna.Study:
    """
    Create Optuna study with proper single/multi-objective handling.

    - 1 objective: uses direction= (single-objective mode)
    - 2+ objectives: uses directions= (multi-objective mode)
    """

    if mo_config.is_multi_objective():
        # Multi-objective: use directions=
        study = optuna.create_study(
            study_name=study_name,
            directions=mo_config.get_directions(),
            sampler=sampler,
            storage=storage,
        )
        # Set metric names for clarity
        study.set_metric_names(mo_config.get_metric_names())
    else:
        # Single-objective: use direction=
        study = optuna.create_study(
            study_name=study_name,
            direction=mo_config.get_single_direction(),
            sampler=sampler,
            storage=storage,
        )

    return study
```

**Objective Function:**
```python
def create_objective_function(
    mo_config: MultiObjectiveConfig,
    constraint_specs: List[ConstraintSpec],
    strategy_class,
    df: pd.DataFrame,
    trade_start_idx: int,
    fixed_params: Dict[str, Any],
):
    """Create objective function for Optuna optimization."""

    def objective(trial: optuna.Trial):
        params = prepare_trial_parameters(trial, fixed_params)
        result = strategy_class.run(df, params, trade_start_idx)

        basic = calculate_basic(result)
        advanced = calculate_advanced(result)

        # Collect all metrics
        all_metrics = {
            "net_profit_pct": basic.net_profit_pct,
            "max_drawdown_pct": basic.max_drawdown_pct,
            "sharpe_ratio": advanced.sharpe_ratio,
            "sortino_ratio": advanced.sortino_ratio,
            "romad": advanced.romad,
            "profit_factor": advanced.profit_factor,
            "win_rate": basic.win_rate,
            "sqn": advanced.sqn,
            "ulcer_index": advanced.ulcer_index,
            "consistency_score": advanced.consistency_score,
            "total_trades": basic.total_trades,
        }

        # Check for missing/NaN objective values - FAIL if any missing
        objective_values = []
        for obj in mo_config.objectives:
            value = all_metrics.get(obj)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                raise optuna.TrialPruned(f"Missing or NaN value for objective: {obj}")
            objective_values.append(float(value))

        # ALWAYS set constraint values (even if empty)
        constraint_values = evaluate_constraints(all_metrics, constraint_specs)
        trial.set_user_attr("merlin.constraint_values", constraint_values)
        trial.set_user_attr("merlin.all_metrics", all_metrics)

        # Return single value or tuple based on mode
        if mo_config.is_multi_objective():
            return tuple(objective_values)
        else:
            return objective_values[0]

    return objective
```

**Results Sorting:**

**If constraints are enabled:**
- Determine trial feasibility using `merlin.constraint_values` (trial is feasible if all constraint values `<= 0.0`).
- Compute Pareto membership **only among feasible trials** (ignore infeasible trials when building the Pareto front).
- Sort order:
  1) feasible + Pareto
  2) feasible + non-Pareto
  3) infeasible
  Within each group, sort by the primary objective (direction-aware), then by `trial_number` as a stable tie-breaker.

```python
def sort_optimization_results(
    results: List[OptimizationResult],
    study: optuna.Study,
    mo_config: MultiObjectiveConfig,
) -> List[OptimizationResult]:
    """Sort results based on optimization mode."""

    if not mo_config.is_multi_objective():
        # Single-objective: sort by objective value
        direction = mo_config.get_single_direction()
        reverse = (direction == "maximize")
        return sorted(
            results,
            key=lambda r: r.objective_values[0],
            reverse=reverse
        )

    # Multi-objective: Pareto first, then by primary objective
    pareto_trials = study.best_trials
    pareto_numbers = {t.number for t in pareto_trials}

    primary_idx = mo_config.objectives.index(mo_config.primary_objective)
    primary_direction = OBJECTIVE_DIRECTIONS[mo_config.primary_objective]

    def sort_key(r: OptimizationResult):
        is_pareto = 1 if r.trial_number in pareto_numbers else 0
        primary_value = r.objective_values[primary_idx]
        if primary_direction == "minimize":
            primary_value = -primary_value
        return (is_pareto, primary_value)

    return sorted(results, key=sort_key, reverse=True)
```

**Accessing Best Trial:**
```python
def get_best_trial_info(
    study: optuna.Study,
    mo_config: MultiObjectiveConfig,
) -> Dict[str, Any]:
    """Get best trial info based on optimization mode."""

    if not mo_config.is_multi_objective():
        # Single-objective: use best_trial directly
        best = study.best_trial
        return {
            "trial_number": best.number,
            "value": study.best_value,
            "params": study.best_params,
        }

    # Multi-objective: sort Pareto by primary objective
    pareto_trials = study.best_trials
    if not pareto_trials:
        return None

    primary_idx = mo_config.objectives.index(mo_config.primary_objective)
    primary_direction = OBJECTIVE_DIRECTIONS[mo_config.primary_objective]
    reverse = (primary_direction == "maximize")

    sorted_pareto = sorted(
        pareto_trials,
        key=lambda t: t.values[primary_idx],
        reverse=reverse
    )

    best = sorted_pareto[0]
    return {
        "trial_number": best.number,
        "values": dict(zip(mo_config.objectives, best.values)),
        "params": best.params,
        "pareto_size": len(pareto_trials),
    }
```

---

## 3. Soft Constraints

### 3.1 Constraint Metrics

| Metric | Display Name | Operator | Default |
|--------|--------------|----------|---------|
| `total_trades` | Total Trades | ≥ | 30 |
| `net_profit_pct` | Net Profit % | ≥ | 0.0 |
| `max_drawdown_pct` | Max Drawdown % | ≤ | 30.0 |
| `sharpe_ratio` | Sharpe Ratio | ≥ | 0.0 |
| `romad` | RoMaD | ≥ | 0.0 |
| `profit_factor` | Profit Factor | ≥ | 1.0 |
| `win_rate` | Win Rate % | ≥ | 0.0 |
| `sqn` | SQN | ≥ | 0.0 |
| `ulcer_index` | Ulcer Index | ≤ | 20.0 |
| `consistency_score` | Consistency % | ≥ | 0.0 |
| `sortino_ratio` | Sortino Ratio | ≥ | 0.0 |

### 3.2 UI Design

```
┌─────────────────────────────────────────────────────────────┐
│ OPTIMIZATION CONSTRAINTS                             [▼]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Trials violating constraints are deprioritized (not pruned) │
│                                                             │
│ ☑ Total Trades        ≥  [___30___]                        │
│ ☐ Net Profit %        ≥  [___0.0__]                        │
│ ☑ Max Drawdown %      ≤  [___25.0_]                        │
│ ☐ Sharpe Ratio        ≥  [___0.5__]                        │
│ ☐ RoMaD               ≥  [___1.0__]                        │
│ ☐ Profit Factor       ≥  [___1.2__]                        │
│ ☐ Win Rate %          ≥  [___40.0_]                        │
│ ☐ SQN                 ≥  [___1.0__]                        │
│ ☐ Ulcer Index         ≤  [___15.0_]                        │
│ ☐ Consistency %       ≥  [___50.0_]                        │
│ ☐ Sortino Ratio       ≥  [___0.5__]                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Implementation

**Constants:**
```python
CONSTRAINT_OPERATORS: Dict[str, str] = {
    "total_trades": "gte",
    "net_profit_pct": "gte",
    "max_drawdown_pct": "lte",
    "sharpe_ratio": "gte",
    "sortino_ratio": "gte",
    "romad": "gte",
    "profit_factor": "gte",
    "win_rate": "gte",
    "sqn": "gte",
    "ulcer_index": "lte",
    "consistency_score": "gte",
}
```

**Configuration:**
```python
@dataclass
class ConstraintSpec:
    """Specification for a single constraint."""
    metric: str
    threshold: float
    enabled: bool = False

    @property
    def operator(self) -> str:
        return CONSTRAINT_OPERATORS[self.metric]
```

**Evaluation (with robust handling):**
```python
def evaluate_constraints(
    all_metrics: Dict[str, Any],
    constraints: List[ConstraintSpec]
) -> List[float]:
    """
    Evaluate soft constraints.

    Returns list where:
        > 0: constraint violated
        <= 0: constraint satisfied

    Missing/NaN values are treated as VIOLATED.
    Always returns list of correct length for enabled constraints.
    """
    enabled_constraints = [c for c in constraints if c.enabled]

    if not enabled_constraints:
        return []

    violations = []

    for spec in enabled_constraints:
        value = all_metrics.get(spec.metric)

        # Missing or NaN = VIOLATED
        if value is None or (isinstance(value, float) and math.isnan(value)):
            violations.append(1.0)  # Positive = violated
            continue

        value = float(value)

        if spec.operator == "gte":
            violation = spec.threshold - value
        else:  # lte
            violation = value - spec.threshold

        violations.append(violation)

    return violations
```

**Constraints Function Factory:**
```python
def create_constraints_func(constraints: List[ConstraintSpec]):
    """
    Create constraints function for Optuna sampler.

    Returns function that retrieves stored constraint values,
    with fallback to violated vector of correct shape.
    """
    enabled_constraints = [c for c in constraints if c.enabled]
    n_constraints = len(enabled_constraints)

    if n_constraints == 0:
        return None

    def constraints_func(trial: optuna.Trial) -> List[float]:
        values = trial.user_attrs.get("merlin.constraint_values")

        # Fallback: if somehow missing, return violated vector
        if values is None:
            return [1.0] * n_constraints

        # Ensure correct shape
        if len(values) != n_constraints:
            return [1.0] * n_constraints

        return values

    return constraints_func
```

---

## 4. Sampler Configuration

### 4.1 Available Samplers

| Sampler | Display Name | Description |
|---------|--------------|-------------|
| `tpe` | TPE (Bayesian) | Tree-structured Parzen Estimator |
| `nsga2` | NSGA-II | Genetic algorithm for 2-4 objectives |
| `nsga3` | NSGA-III | Many-objective optimization (5+) |
| `random` | Random | Baseline random search |

### 4.2 NSGA Settings (Conditional)

Shown only when NSGA-II or NSGA-III selected:

```
┌─────────────────────────────────────────────────────────────┐
│ NSGA SAMPLER SETTINGS                                       │
├─────────────────────────────────────────────────────────────┤
│ Population Size:       [___100__]  (default: 50)           │
│ Crossover Probability: [___0.9__]  (default: 0.9)          │
│ Mutation Probability:  [________]  (empty = auto)          │
│ Swapping Probability:  [___0.5__]  (default: 0.5)          │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Implementation

```python
@dataclass
class SamplerConfig:
    """Configuration for Optuna sampler."""
    sampler_type: str = "tpe"
    population_size: int = 50
    crossover_prob: float = 0.9
    mutation_prob: Optional[float] = None
    swapping_prob: float = 0.5
    n_startup_trials: int = 20


def create_sampler(
    config: SamplerConfig,
    constraints_func = None
) -> optuna.samplers.BaseSampler:
    """Create Optuna sampler based on configuration."""

    if config.sampler_type == "tpe":
        return optuna.samplers.TPESampler(
            n_startup_trials=config.n_startup_trials,
            multivariate=True,
            constraints_func=constraints_func,
        )

    elif config.sampler_type == "nsga2":
        return optuna.samplers.NSGAIISampler(
            population_size=config.population_size,
            crossover_prob=config.crossover_prob,
            mutation_prob=config.mutation_prob,
            swapping_prob=config.swapping_prob,
            constraints_func=constraints_func,
        )

    elif config.sampler_type == "nsga3":
        return optuna.samplers.NSGAIIISampler(
            population_size=config.population_size,
            crossover_prob=config.crossover_prob,
            mutation_prob=config.mutation_prob,
            swapping_prob=config.swapping_prob,
            constraints_func=constraints_func,
        )

    elif config.sampler_type == "random":
        return optuna.samplers.RandomSampler()

    else:
        raise ValueError(f"Unknown sampler type: {config.sampler_type}")
```

---

## 5. Server-Side Validation

### 5.1 Objective Validation

```python
def validate_objectives_config(
    objectives: List[str],
    primary_objective: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """
    Validate objectives configuration.

    Returns:
        (is_valid, error_message)
    """
    # Rule 1: At least 1 objective required
    if not objectives or len(objectives) < 1:
        return False, "At least 1 objective is required."

    # Rule 2: Maximum 6 objectives
    if len(objectives) > 6:
        return False, "Maximum 6 objectives allowed."

    # Rule 3: All objectives must be valid
    for obj in objectives:
        if obj not in OBJECTIVE_DIRECTIONS:
            return False, f"Unknown objective: {obj}"

    # Rule 4: If multi-objective, primary is required
    if len(objectives) > 1:
        if not primary_objective:
            return False, "Primary objective required for multi-objective optimization."

        # Rule 5: Primary must be in selected objectives
        if primary_objective not in objectives:
            return False, "Primary objective must be one of the selected objectives."

    return True, None
```

### 5.2 Constraint Validation

```python
def validate_constraints_config(
    constraints: List[Dict[str, Any]]
) -> Tuple[bool, Optional[str]]:
    """
    Validate constraints configuration.

    Returns:
        (is_valid, error_message)
    """
    for i, spec in enumerate(constraints):
        metric = spec.get("metric")
        threshold = spec.get("threshold")
        enabled = spec.get("enabled", False)

        if not enabled:
            continue

        # Rule 1: Metric must be valid
        if metric not in CONSTRAINT_OPERATORS:
            return False, f"Constraint {i+1}: Unknown metric '{metric}'"

        # Rule 2: Threshold must be a valid number
        if threshold is None:
            return False, f"Constraint {i+1}: Threshold is required"

        try:
            float(threshold)
        except (TypeError, ValueError):
            return False, f"Constraint {i+1}: Threshold must be a number"

    return True, None
```

### 5.3 Sampler Validation

```python
def validate_sampler_config(
    sampler_type: str,
    population_size: Optional[int],
    crossover_prob: Optional[float],
) -> Tuple[bool, Optional[str]]:
    """
    Validate sampler configuration.

    Returns:
        (is_valid, error_message)
    """
    valid_samplers = {"tpe", "nsga2", "nsga3", "random"}

    if sampler_type not in valid_samplers:
        return False, f"Unknown sampler: {sampler_type}"

    if sampler_type in ("nsga2", "nsga3"):
        if population_size is not None:
            if population_size < 2:
                return False, "Population size must be at least 2"
            if population_size > 1000:
                return False, "Population size must be at most 1000"

        if crossover_prob is not None:
            if not (0.0 <= crossover_prob <= 1.0):
                return False, "Crossover probability must be between 0 and 1"

    return True, None
```

### 5.4 Integration in server.py

```python
@app.post("/api/optimize")
def run_optimization_endpoint():
    # ... existing code ...

    # Validate objectives
    objectives = config_payload.get("objectives", [])
    primary_objective = config_payload.get("primary_objective")

    valid, error = validate_objectives_config(objectives, primary_objective)
    if not valid:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    # Validate constraints
    constraints = config_payload.get("constraints", [])

    valid, error = validate_constraints_config(constraints)
    if not valid:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    # Validate sampler
    sampler_type = config_payload.get("sampler", "tpe")
    population_size = config_payload.get("population_size")
    crossover_prob = config_payload.get("crossover_prob")

    valid, error = validate_sampler_config(sampler_type, population_size, crossover_prob)
    if not valid:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    # ... continue with optimization ...
```

---

## 6. Database Schema

**Note:** Fresh database will be created. No migration needed.

### 6.1 Studies Table

```sql
CREATE TABLE studies (
    study_id TEXT PRIMARY KEY,
    study_name TEXT UNIQUE NOT NULL,

    -- Strategy info
    strategy_id TEXT NOT NULL,
    strategy_version TEXT,

    -- Mode
    optimization_mode TEXT NOT NULL,

    -- Multi-objective configuration
    objectives_json TEXT,
    n_objectives INTEGER DEFAULT 1,
    directions_json TEXT,
    primary_objective TEXT,

    -- Constraints configuration
    constraints_json TEXT,

    -- Sampler configuration
    sampler_type TEXT DEFAULT 'tpe',
    population_size INTEGER,
    crossover_prob REAL,
    mutation_prob REAL,
    swapping_prob REAL,

    -- Budget configuration
    budget_mode TEXT,
    n_trials INTEGER,
    time_limit INTEGER,
    convergence_patience INTEGER,

    -- Results summary
    total_trials INTEGER DEFAULT 0,
    completed_trials INTEGER DEFAULT 0,
    pruned_trials INTEGER DEFAULT 0,
    pareto_front_size INTEGER,

    -- Best values
    best_value REAL,
    best_values_json TEXT,

    -- Score config
    score_config_json TEXT,

    -- Configuration snapshot
    config_json TEXT,

    -- File references
    csv_file_path TEXT,
    csv_file_name TEXT,

    -- Dataset info
    dataset_start_date TEXT,
    dataset_end_date TEXT,
    warmup_bars INTEGER,

    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,

    -- Filters
    filter_min_profit INTEGER DEFAULT 0,
    min_profit_threshold REAL DEFAULT 0.0
);
```

### 6.2 Trials Table

```sql
CREATE TABLE trials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL,
    trial_number INTEGER NOT NULL,

    -- Parameters
    params_json TEXT NOT NULL,

    -- Objective values
    objective_values_json TEXT,

    -- Pareto info
    is_pareto_optimal INTEGER DEFAULT 0,
    dominance_rank INTEGER,

    -- Constraint satisfaction
    constraints_satisfied INTEGER DEFAULT 1,
    constraint_values_json TEXT,

    -- All metrics
    net_profit_pct REAL,
    max_drawdown_pct REAL,
    total_trades INTEGER,
    win_rate REAL,
    avg_win REAL,
    avg_loss REAL,
    gross_profit REAL,
    gross_loss REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    romad REAL,
    profit_factor REAL,
    sqn REAL,
    ulcer_index REAL,
    consistency_score REAL,

    -- Legacy
    composite_score REAL,

    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(study_id, trial_number),
    FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE
);

CREATE INDEX idx_trials_pareto ON trials(study_id, is_pareto_optimal);
CREATE INDEX idx_trials_constraints ON trials(study_id, constraints_satisfied);
```

---

## 7. UI Changes

### 7.1 Start Page (index.html)

**New Sections:**
1. **OPTIMIZATION OBJECTIVES** - 10 checkboxes with ↑/↓ arrows, primary dropdown
2. **OPTIMIZATION CONSTRAINTS** - 11 checkboxes with threshold inputs (collapsible)
3. **NSGA SAMPLER SETTINGS** - Population/crossover settings (conditional)

**Modified:**
1. Sampler dropdown - add NSGA-II, NSGA-III
2. Remove old single target dropdown

### 7.2 Results Page (results.html)

**New:**
1. Pareto badge for Pareto-optimal trials
2. Multi-objective columns in trial table
3. Constraint satisfaction indicator (✓/✗)

### 7.3 JavaScript Summary

**New JavaScript Files (Option B):**
- `optuna-ui.js` *(new)* - Optuna settings UI logic (objectives, primary objective, constraints, NSGA settings). Loaded on `index.html`.
- `optuna-results-ui.js` *(new)* - Optuna results UI helpers (dynamic table headers/rows, Pareto badge, constraint indicator). Loaded on `results.html`.

**optuna-ui.js:**
- `updateObjectiveSelection()` - Handle checkboxes, update primary dropdown
- `toggleNsgaSettings()` - Show/hide NSGA settings
- `collectObjectives()` - Gather for form submission
- `collectConstraints()` - Gather enabled constraints

**optuna-results-ui.js:**
- `renderTrialRow()` - Add Pareto badge, constraint indicator
- `buildTrialTableHeaders()` - Dynamic columns

**ui-handlers.js:**
- Integration glue: initialize Optuna controls, call `optuna-ui.js` collectors, and attach returned data to the `/api/optimize` request payload.

**results.js:**
- Integration glue: use `optuna-results-ui.js` helpers to render the trials table and summary blocks.



---

## 8. Implementation Phases

### Phase 4.1: Multi-Objective Core
**Files:** `optuna_engine.py`, `storage.py`

- [ ] Add `OBJECTIVE_DIRECTIONS`, `OBJECTIVE_DISPLAY_NAMES` constants
- [ ] Implement `MultiObjectiveConfig` dataclass
- [ ] Implement `create_optimization_study()` with single/multi handling
- [ ] Implement objective function with NaN handling
- [ ] Implement `sort_optimization_results()`
- [ ] Implement `get_best_trial_info()`
- [ ] Update database schema (fresh DB)
- [ ] Update save/load functions in storage.py

### Phase 4.2: Multi-Objective UI
**Files:** `index.html`, `results.html`, `optuna-ui.js`, `optuna-results-ui.js`, `ui-handlers.js`, `results.js`

- [ ] Add objectives checkboxes section
- [ ] Add primary objective dropdown
- [ ] Implement JS handlers for objective selection
- [ ] Update form submission
- [ ] Add Pareto badge to results
- [ ] Update trial table for multiple objectives

### Phase 4.3: Soft Constraints
**Files:** `optuna_engine.py`, `index.html`, `optuna-ui.js`, `optuna-results-ui.js`, `ui-handlers.js`, `results.js`

- [ ] Add `CONSTRAINT_OPERATORS` constant
- [ ] Implement `ConstraintSpec` dataclass
- [ ] Implement `evaluate_constraints()` with robust handling
- [ ] Implement `create_constraints_func()` with shape fallback
- [ ] Add constraints UI section
- [ ] Display constraint indicators in results

### Phase 4.4: Extended Samplers
**Files:** `optuna_engine.py`, `index.html`, `optuna-ui.js`, `ui-handlers.js`

- [ ] Implement `SamplerConfig` dataclass
- [ ] Implement `create_sampler()` with all types
- [ ] Add NSGA-II, NSGA-III to dropdown
- [ ] Add NSGA settings panel
- [ ] Implement conditional visibility

### Phase 4.5: Validation & Integration
**Files:** `server.py`, `CLAUDE.md`

- [ ] Add `validate_objectives_config()`
- [ ] Add `validate_constraints_config()`
- [ ] Add `validate_sampler_config()`
- [ ] Integrate validation in `/api/optimize`
- [ ] End-to-end testing
- [ ] Update documentation

---

## Appendix: Technical References

- [optuna.create_study](https://optuna.readthedocs.io/en/stable/reference/generated/optuna.create_study.html) - `direction` vs `directions`
- [Study.best_trials](https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.Study.html) - Multi-objective Pareto front
- [TPESampler.constraints_func](https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.TPESampler.html) - Soft constraints
- [NSGAIISampler](https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.NSGAIISampler.html)
- [NSGAIIISampler](https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.NSGAIIISampler.html)

---

*Document v4 (Final) - Ready for Implementation*
