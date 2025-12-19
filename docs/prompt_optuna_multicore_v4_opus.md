# Implementation Task: True Multi-Process Optuna Optimization

## For: GPT 5.1 Codex Agent Coder

**Objective:** Implement real multi-core CPU parallelism for Optuna optimization by switching from a broken `pool.apply()` pattern to Optuna's official multi-process optimization using shared storage.

**Constraint:** All changes must be contained within `src/core/optuna_engine.py` - do NOT create new Python modules.

**Optuna Version:** 4.4.0 (pinned in `requirements.txt`)

---

## Table of Contents

1. [Problem Analysis](#1-problem-analysis)
2. [Technical Background](#2-technical-background)
3. [Solution Architecture](#3-solution-architecture)
4. [Acceptance Criteria](#4-acceptance-criteria)
5. [Implementation Steps](#5-implementation-steps)
6. [Complete Code Changes](#6-complete-code-changes)
7. [Testing & Verification](#7-testing--verification)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Problem Analysis

### Current Implementation Issues

**File:** `src/core/optuna_engine.py`

#### Issue 1: Synchronous Blocking Pool (Lines 505-510)

```python
def _evaluate_parameters(self, params_dict: Dict[str, Any]) -> OptimizationResult:
    if self.pool is None:
        raise RuntimeError("Worker pool is not initialised.")
    args = (params_dict, self.df, self.trade_start_idx, self.strategy_class)
    return self.pool.apply(_run_single_combination, (args,))  # BLOCKING!
```

**Problem:** `pool.apply()` is **synchronous** - it blocks until the worker returns. Even though a pool with 6 workers is created (line 500), only 1 worker executes at a time.

#### Issue 2: No Parallelization in study.optimize() (Lines 697-704)

```python
self.study.optimize(
    lambda trial: self._objective(trial, search_space),
    n_trials=n_trials,
    timeout=timeout,
    callbacks=callbacks or None,
    show_progress_bar=False,
)
```

**Problem:** No `n_jobs` parameter is used. Even if added, Optuna's `n_jobs` uses **multi-threading**, which cannot parallelize CPU-bound Python code due to the Global Interpreter Lock (GIL).

#### Issue 3: Score Target Uses Local Results (Lines 589-599)

```python
if self.optuna_config.target == "score":
    temp_results = self.trial_results + [result]
    scored_results = calculate_score(temp_results, score_config)
```

**Problem:** `self.trial_results` is a per-process list. In multi-process mode, each worker only sees its own partial results, making percentile-based scoring **incorrect**.

### Performance Impact

| Metric | Current | After Fix |
|--------|---------|-----------|
| CPU Usage | ~12-15% (1 core) | 75-95% (all cores) |
| 500 trials time | ~50 minutes | ~10 minutes |
| Speedup | 1x | 4-5x |

---

## 2. Technical Background

### Why Optuna's n_jobs Parameter Won't Help

From [Optuna FAQ](https://optuna.readthedocs.io/en/stable/faq.html):

> "The python code will not be faster due to GIL because `optuna.study.Study.optimize()` with `n_jobs!=1` uses multi-threading."

**Multi-threading limitations:**
- Python's GIL allows only one thread to execute Python bytecode at a time
- Threads share memory (good for I/O-bound, useless for CPU-bound)
- Our backtest loop is 100% CPU-bound Python code

### Correct Approach: Multi-Process with Shared Storage

From [Optuna Easy Parallelization](https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/004_distributed.html):

```python
# Main process creates study with shared storage
storage = JournalStorage(JournalFileBackend("study.log"))
study = optuna.create_study(storage=storage, study_name="my_study")

# Each worker process (separate OS process):
study = optuna.load_study(storage=storage, study_name="my_study")
study.optimize(objective, n_trials=None, n_jobs=1)  # n_jobs=1 per process!
```

**Why this works:**
- Each worker is a separate OS process with its own Python interpreter
- No GIL contention - true parallel execution
- Workers coordinate via shared storage (file-based or database)
- TPE sampler with `constant_liar=True` avoids duplicate exploration

### Storage Options for Multi-Process

| Storage | Multi-Process Safe | Notes |
|---------|-------------------|-------|
| In-memory | NO | Each process has isolated memory |
| SQLite | NO | Locking issues with concurrent writes |
| **JournalFileBackend** | **YES** | Append-only log, optimized for parallel writes |
| PostgreSQL/MySQL | YES | Requires database server |

**We will use JournalStorage with JournalFileBackend** - no external dependencies, optimized for concurrent access.

### MaxTrialsCallback for Global Trial Limiting

From [Optuna MaxTrialsCallback](https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.MaxTrialsCallback.html):

```python
from optuna.study import MaxTrialsCallback

# states=None counts ALL trials (COMPLETE, PRUNED, FAIL)
callback = MaxTrialsCallback(n_trials=100, states=None)
study.optimize(objective, n_trials=None, callbacks=[callback])
```

This ensures the **global** trial count across all processes doesn't exceed the budget.

---

## 3. Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│ Main Process (Flask server or CLI)                              │
│                                                                 │
│  1. Materialize CSV to temp file (if file-like object)         │
│  2. Create JournalStorage with unique file path                │
│  3. Create study with storage, sampler, pruner                 │
│  4. Spawn N worker processes via multiprocessing.Process       │
│  5. Wait for all workers to complete                           │
│  6. Reload study from storage                                  │
│  7. Reconstruct OptimizationResult list from trial.user_attrs  │
│  8. Calculate composite scores post-hoc                        │
│  9. Cleanup temp files                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
       ┌──────────┐    ┌──────────┐    ┌──────────┐
       │ Worker 1 │    │ Worker 2 │    │ Worker N │
       │          │    │          │    │          │
       │ - Load   │    │ - Load   │    │ - Load   │
       │   study  │    │   study  │    │   study  │
       │ - Load   │    │ - Load   │    │ - Load   │
       │   data   │    │   data   │    │   data   │
       │ - Run    │    │ - Run    │    │ - Run    │
       │   trials │    │   trials │    │   trials │
       └──────────┘    └──────────┘    └──────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                 ┌─────────────────────────┐
                 │ Shared JournalStorage   │
                 │ (*.journal.log file)    │
                 │                         │
                 │ - Trial parameters      │
                 │ - Trial objective values│
                 │ - Trial user_attrs      │
                 │   (all metrics stored)  │
                 └─────────────────────────┘
```

### Key Design Decisions

1. **Single file modification** - All changes in `optuna_engine.py`
2. **Module-level worker function** - Required for Windows `spawn` multiprocessing
3. **Proxy objective for "score" target** - Use `romad` as Optuna objective, calculate composite score post-hoc
4. **MaxTrialsCallback** - Global trial limiting across all processes
5. **Graceful convergence degradation** - Convergence mode not supported in multi-process (uses large trial cap)
6. **Metrics in user_attrs** - Each trial stores all metrics for post-hoc result reconstruction

---

## 4. Acceptance Criteria

### A. Performance / Parallelism

- [ ] With `worker_processes > 1`, optimization spawns multiple OS processes
- [ ] Task Manager shows multiple Python PIDs actively using CPU
- [ ] CPU usage reaches 75-95% on multi-core systems
- [ ] 4-5x speedup observed with 6 workers vs 1 worker

### B. Correctness

- [ ] Single-process mode (`worker_processes=1`) works exactly as before
- [ ] Multi-process mode produces comparable optimization quality
- [ ] All budget modes work: `trials`, `time`, `convergence` (degraded)
- [ ] Flask endpoint `/api/optimize` works with both file upload and csvPath
- [ ] Results are properly sorted by target metric

### C. Global Budget Enforcement

- [ ] Trial-based budget: Total trials across all processes ≈ `n_trials` (not `n_trials × n_workers`)
- [ ] Time-based budget: Workers stop after configured timeout
- [ ] Convergence mode: Warning logged, falls back to large trial cap

### D. Results Aggregation

- [ ] Parent process returns unified `List[OptimizationResult]`
- [ ] All metrics reconstructed from `trial.user_attrs`
- [ ] Composite score calculated post-hoc using full result set
- [ ] `optuna_summary` reflects actual totals from storage

### E. Windows Compatibility

- [ ] No "can't pickle" errors
- [ ] No import-time process spawning
- [ ] Worker function is module-level (not nested/lambda)

### F. Storage

- [ ] Multi-process uses JournalStorage (NOT SQLite)
- [ ] Single-process can optionally use SQLite for `save_study=True`
- [ ] Temp storage files cleaned up when `save_study=False`

---

## 5. Implementation Steps

### Step 1: Add Required Imports

**Location:** Top of `src/core/optuna_engine.py` (after line 10)

**Add these imports:**

```python
import tempfile
from dataclasses import asdict
from pathlib import Path
```

**Verify existing imports include:**

```python
import multiprocessing as mp  # Already present
from optuna.trial import TrialState  # Already present
```

---

### Step 2: Add Helper Functions (Module-Level)

**Location:** After `_run_single_combination()` function (after line 206)

These functions handle metrics persistence and result reconstruction.

```python
# ---------------------------------------------------------------------------
# Multi-process helpers (module-level for pickling)
# ---------------------------------------------------------------------------

def _trial_set_result_attrs(
    trial: optuna.Trial,
    result: OptimizationResult,
    objective_value: float,
    target: str,
) -> None:
    """
    Store optimization result metrics in trial user_attrs for multi-process retrieval.

    These attributes are persisted to shared storage and can be read by the parent
    process after workers complete.
    """
    trial.set_user_attr("merlin.net_profit_pct", float(result.net_profit_pct))
    trial.set_user_attr("merlin.max_drawdown_pct", float(result.max_drawdown_pct))
    trial.set_user_attr("merlin.total_trades", int(result.total_trades))
    trial.set_user_attr("merlin.objective_value", float(objective_value))
    trial.set_user_attr("merlin.target", str(target))

    if result.romad is not None:
        trial.set_user_attr("merlin.romad", float(result.romad))
    if result.sharpe_ratio is not None:
        trial.set_user_attr("merlin.sharpe_ratio", float(result.sharpe_ratio))
    if result.profit_factor is not None:
        trial.set_user_attr("merlin.profit_factor", float(result.profit_factor))
    if result.ulcer_index is not None:
        trial.set_user_attr("merlin.ulcer_index", float(result.ulcer_index))
    if result.recovery_factor is not None:
        trial.set_user_attr("merlin.recovery_factor", float(result.recovery_factor))
    if result.consistency_score is not None:
        trial.set_user_attr("merlin.consistency_score", float(result.consistency_score))


def _result_from_trial(trial: optuna.trial.FrozenTrial) -> OptimizationResult:
    """
    Reconstruct OptimizationResult from a completed trial's params and user_attrs.

    Used by parent process to aggregate results after workers finish.
    """
    attrs = trial.user_attrs

    result = OptimizationResult(
        params=dict(trial.params),
        net_profit_pct=float(attrs.get("merlin.net_profit_pct", 0.0)),
        max_drawdown_pct=float(attrs.get("merlin.max_drawdown_pct", 0.0)),
        total_trades=int(attrs.get("merlin.total_trades", 0)),
        romad=attrs.get("merlin.romad"),
        sharpe_ratio=attrs.get("merlin.sharpe_ratio"),
        profit_factor=attrs.get("merlin.profit_factor"),
        ulcer_index=attrs.get("merlin.ulcer_index"),
        recovery_factor=attrs.get("merlin.recovery_factor"),
        consistency_score=attrs.get("merlin.consistency_score"),
        score=0.0,  # Will be calculated post-hoc
    )

    # Attach trial metadata
    setattr(result, "optuna_trial_number", trial.number)
    setattr(result, "optuna_value", trial.value)

    return result


def _materialize_csv_to_temp(csv_source: Any) -> Tuple[str, bool]:
    """
    Ensure CSV source is a file path string suitable for multi-process workers.

    Args:
        csv_source: Either a file path string or a file-like object

    Returns:
        Tuple of (file_path_string, needs_cleanup)
        - needs_cleanup is True if a temp file was created
    """
    # Already a path string
    if isinstance(csv_source, (str, Path)):
        return str(csv_source), False

    # File-like object with a valid path
    if hasattr(csv_source, "name") and csv_source.name:
        path = Path(csv_source.name)
        if path.exists() and path.is_file():
            return str(path), False

    # Need to materialize to temp file
    if hasattr(csv_source, "read"):
        # Reset position if seekable
        if hasattr(csv_source, "seek"):
            try:
                csv_source.seek(0)
            except Exception:
                pass

        # Read content
        content = csv_source.read()
        if isinstance(content, str):
            content = content.encode("utf-8")

        # Write to temp file
        temp_dir = Path(tempfile.gettempdir()) / "merlin_optuna_csv"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / f"optimization_{int(time.time())}_{id(csv_source)}.csv"
        temp_path.write_bytes(content)

        logger.info(f"Materialized CSV to temp file: {temp_path}")
        return str(temp_path), True

    # Fallback: assume it's usable as-is
    return str(csv_source), False
```

---

### Step 3: Add Worker Process Entry Point (Module-Level)

**Location:** After the helper functions added in Step 2

This function is the entry point for each worker process. It must be at module level to be picklable on Windows.

```python
def _worker_process_entry(
    study_name: str,
    storage_path: str,
    base_config_dict: Dict[str, Any],
    optuna_config_dict: Dict[str, Any],
    n_trials: Optional[int],
    timeout: Optional[int],
    worker_id: int,
) -> None:
    """
    Worker process entry point for multi-process optimization.

    Each worker:
    1. Creates its own JournalStorage connection
    2. Loads the shared study
    3. Runs trials with MaxTrialsCallback for global limiting
    4. Results automatically saved to shared storage via user_attrs

    Args:
        study_name: Name of the Optuna study to load
        storage_path: Path to JournalStorage log file
        base_config_dict: Serialized OptimizationConfig (from dataclasses.asdict)
        optuna_config_dict: Serialized OptunaConfig (from dataclasses.asdict)
        n_trials: Global trial limit (used with MaxTrialsCallback)
        timeout: Time limit in seconds (None for trial-based budget)
        worker_id: Unique identifier for logging
    """
    from optuna.storages import JournalStorage
    from optuna.storages.journal import JournalFileBackend
    from optuna.study import MaxTrialsCallback

    worker_logger = logging.getLogger(__name__)
    worker_logger.info(
        f"Worker {worker_id} started (PID: {mp.current_process().pid})"
    )

    try:
        # Create storage connection (each process needs its own)
        storage = JournalStorage(JournalFileBackend(storage_path))

        # Load shared study
        study = optuna.load_study(study_name=study_name, storage=storage)

        # Reconstruct config objects from dictionaries
        base_config = OptimizationConfig(**base_config_dict)
        optuna_config = OptunaConfig(**optuna_config_dict)

        # Create optimizer instance for this worker
        optimizer = OptunaOptimizer(base_config, optuna_config)

        # Prepare data (each worker loads its own copy)
        optimizer._prepare_data_and_strategy()

        # Build search space
        search_space = optimizer._build_search_space()

        # Create objective function
        def worker_objective(trial: optuna.Trial) -> float:
            return optimizer._objective_for_worker(trial, search_space)

        # Build callbacks
        callbacks = []
        if n_trials is not None:
            # MaxTrialsCallback enforces global trial limit across all workers
            callbacks.append(MaxTrialsCallback(n_trials, states=None))

        worker_logger.info(
            f"Worker {worker_id} starting optimization "
            f"(n_trials={n_trials}, timeout={timeout})"
        )

        # Run trials
        # n_jobs=1: No threading within worker (already multi-process)
        # n_trials=None: Let MaxTrialsCallback handle global limit
        study.optimize(
            worker_objective,
            n_trials=None,  # Controlled by MaxTrialsCallback
            timeout=timeout,
            callbacks=callbacks or None,
            show_progress_bar=False,
            n_jobs=1,
        )

        worker_logger.info(f"Worker {worker_id} completed successfully")

    except Exception as exc:
        worker_logger.error(
            f"Worker {worker_id} failed: {exc}", exc_info=True
        )
        raise
```

---

### Step 4: Modify OptunaOptimizer.__init__

**Location:** Lines 328-339

**Changes:**
1. Remove `self.pool` (no longer using mp.Pool)
2. Add instance variables for data caching
3. Add `multiprocess_mode` flag

**Replace the `__init__` method:**

```python
def __init__(self, base_config, optuna_config: OptunaConfig) -> None:
    self.base_config = base_config
    self.optuna_config = optuna_config

    # Data cached for optimization (loaded once per process)
    self.df: Optional[pd.DataFrame] = None
    self.trade_start_idx: int = 0
    self.strategy_class: Optional[Any] = None

    # Trial tracking (used in single-process mode)
    self.trial_results: List[OptimizationResult] = []
    self.best_value: float = float("-inf")
    self.trials_without_improvement: int = 0
    self.start_time: Optional[float] = None
    self.pruned_trials: int = 0

    # Optuna objects
    self.study: Optional[optuna.Study] = None
    self.pruner: Optional[optuna.pruners.BasePruner] = None
    self.param_type_map: Dict[str, str] = {}

    # Multi-process mode flag (set during optimize())
    self._multiprocess_mode: bool = False
```

---

### Step 5: Rename and Simplify Data Loading

**Location:** Lines 466-500 (the `_setup_worker_pool` method)

**Rename to `_prepare_data_and_strategy` and remove pool creation:**

```python
def _prepare_data_and_strategy(self) -> None:
    """
    Load dataset and strategy class for optimization.

    This method:
    - Loads the CSV data into a DataFrame
    - Applies date filtering if configured
    - Loads the strategy class
    - Caches these objects for use during trial evaluation

    In multi-process mode, each worker calls this independently.
    """
    from strategies import get_strategy

    try:
        self.strategy_class = get_strategy(self.base_config.strategy_id)
    except ValueError as e:
        raise ValueError(
            f"Failed to load strategy '{self.base_config.strategy_id}': {e}"
        )

    from .backtest_engine import prepare_dataset_with_warmup

    self.df = load_data(self.base_config.csv_file)

    use_date_filter = bool(self.base_config.fixed_params.get("dateFilter", False))
    start_ts = _parse_timestamp(self.base_config.fixed_params.get("start"))
    end_ts = _parse_timestamp(self.base_config.fixed_params.get("end"))

    self.trade_start_idx = 0
    if use_date_filter and (start_ts is not None or end_ts is not None):
        try:
            self.df, self.trade_start_idx = prepare_dataset_with_warmup(
                self.df, start_ts, end_ts, self.base_config.warmup_bars
            )
        except Exception as exc:
            raise ValueError(f"Failed to prepare dataset with warmup: {exc}")

    logger.info(
        f"Data prepared: {len(self.df)} rows, trade_start_idx={self.trade_start_idx}"
    )
```

---

### Step 6: Simplify _evaluate_parameters

**Location:** Lines 505-510

**Remove pool dependency - direct function call:**

```python
def _evaluate_parameters(self, params_dict: Dict[str, Any]) -> OptimizationResult:
    """
    Evaluate a single parameter combination by running a backtest.

    Parallelization happens at the process level (multiple workers),
    not at the evaluation level.
    """
    if self.df is None or self.strategy_class is None:
        raise RuntimeError(
            "Data not prepared. Call _prepare_data_and_strategy() first."
        )

    args = (params_dict, self.df, self.trade_start_idx, self.strategy_class)
    return _run_single_combination(args)
```

---

### Step 7: Add Worker-Specific Objective Function

**Location:** After `_objective` method (around line 635)

This objective function is used by worker processes. It differs from the main `_objective` in how it handles the "score" target.

```python
def _objective_for_worker(
    self, trial: optuna.Trial, search_space: Dict[str, Dict[str, Any]]
) -> float:
    """
    Objective function for multi-process workers.

    Key difference from _objective():
    - Uses proxy objective (romad) for "score" target since percentile
      scoring requires all results, which workers don't have
    - Stores all metrics in trial.user_attrs for post-hoc reconstruction
    - Does not maintain local trial_results list
    """
    params_dict = self._prepare_trial_parameters(trial, search_space)
    result = self._evaluate_parameters(params_dict)

    # Check minimum profit filter
    if self.base_config.filter_min_profit and (
        result.net_profit_pct < float(self.base_config.min_profit_threshold)
    ):
        raise optuna.TrialPruned("Below minimum profit threshold")

    # Determine objective value
    # For "score" target: use romad as proxy (percentile scoring done post-hoc)
    target = self.optuna_config.target
    if target == "score":
        objective_value = float(result.romad or 0.0)
    elif target == "net_profit":
        objective_value = float(result.net_profit_pct)
    elif target == "romad":
        objective_value = float(result.romad or 0.0)
    elif target == "sharpe":
        objective_value = float(result.sharpe_ratio or 0.0)
    elif target == "max_drawdown":
        objective_value = -float(result.max_drawdown_pct)
    else:
        objective_value = float(result.romad or 0.0)

    # Store all metrics in user_attrs for post-hoc reconstruction
    _trial_set_result_attrs(trial, result, objective_value, target)

    # Pruning check
    if self.pruner is not None:
        trial.report(objective_value, step=0)
        if trial.should_prune():
            raise optuna.TrialPruned("Pruned by Optuna")

    return objective_value
```

---

### Step 8: Modify _objective to Store User Attributes

**Location:** Lines 574-634 (the existing `_objective` method)

**Add user_attrs storage for single-process mode compatibility:**

Find this section (around line 624-626):

```python
self.trial_results.append(result)
setattr(result, "optuna_trial_number", trial.number)
setattr(result, "optuna_value", objective_value)
```

**Replace with:**

```python
self.trial_results.append(result)
setattr(result, "optuna_trial_number", trial.number)
setattr(result, "optuna_value", objective_value)

# Store metrics in user_attrs (enables result reconstruction from storage)
_trial_set_result_attrs(trial, result, objective_value, self.optuna_config.target)
```

---

### Step 9: Refactor optimize() Method

**Location:** Lines 639-767 (the entire `optimize` method)

This is the largest change. Replace the entire method:

```python
def optimize(self) -> List[OptimizationResult]:
    """
    Execute Optuna optimization.

    Automatically selects single-process or multi-process mode based on
    worker_processes configuration.
    """
    n_workers = min(32, max(1, int(self.base_config.worker_processes)))

    if n_workers > 1:
        return self._optimize_multiprocess(n_workers)
    else:
        return self._optimize_single_process()


def _optimize_single_process(self) -> List[OptimizationResult]:
    """
    Single-process optimization (original behavior).

    Used when worker_processes=1 or for debugging.
    """
    logger.info(
        "Starting single-process Optuna optimization: target=%s, budget_mode=%s",
        self.optuna_config.target,
        self.optuna_config.budget_mode,
    )

    self._multiprocess_mode = False
    self.start_time = time.time()
    self.trial_results = []
    self.best_value = float("-inf")
    self.trials_without_improvement = 0
    self.pruned_trials = 0

    # Prepare data and strategy
    search_space = self._build_search_space()
    self._prepare_data_and_strategy()

    # Create sampler and pruner
    sampler = self._create_sampler()
    self.pruner = self._create_pruner()

    # Storage configuration (SQLite only for single-process save_study)
    storage = None
    if self.optuna_config.save_study:
        storage = optuna.storages.RDBStorage(
            url="sqlite:///optuna_study.db",
            engine_kwargs={"connect_args": {"timeout": 30}},
        )

    study_name = self.optuna_config.study_name or f"strategy_opt_{int(time.time())}"

    self.study = optuna.create_study(
        study_name=study_name,
        direction="maximize",
        sampler=sampler,
        pruner=self.pruner,
        storage=storage,
        load_if_exists=self.optuna_config.save_study,
    )

    # Budget configuration
    timeout = None
    n_trials = None
    callbacks = []

    if self.optuna_config.budget_mode == "time":
        timeout = max(60, int(self.optuna_config.time_limit))
    elif self.optuna_config.budget_mode == "trials":
        n_trials = max(1, int(self.optuna_config.n_trials))
    elif self.optuna_config.budget_mode == "convergence":
        n_trials = 10000

        def convergence_callback(study: optuna.Study, _trial: optuna.Trial) -> None:
            if self.trials_without_improvement >= int(self.optuna_config.convergence_patience):
                study.stop()
                logger.info(
                    "Stopping optimization due to convergence (patience=%s)",
                    self.optuna_config.convergence_patience,
                )

        callbacks.append(convergence_callback)

    # Run optimization
    try:
        self.study.optimize(
            lambda trial: self._objective(trial, search_space),
            n_trials=n_trials,
            timeout=timeout,
            callbacks=callbacks or None,
            show_progress_bar=False,
            n_jobs=1,
        )
    except KeyboardInterrupt:
        logger.info("Optimization interrupted by user")
    finally:
        self.pruner = None

    return self._finalize_results()


def _optimize_multiprocess(self, n_workers: int) -> List[OptimizationResult]:
    """
    Multi-process optimization using shared JournalStorage.

    Spawns N worker processes that coordinate via shared storage.
    """
    logger.info(
        "Starting multi-process Optuna optimization: "
        "target=%s, budget_mode=%s, workers=%d",
        self.optuna_config.target,
        self.optuna_config.budget_mode,
        n_workers,
    )

    self._multiprocess_mode = True
    self.start_time = time.time()
    self.trial_results = []

    # Build search space (needed for study creation)
    search_space = self._build_search_space()

    # Materialize CSV to temp file if needed (file-like objects can't be pickled)
    csv_path, csv_needs_cleanup = _materialize_csv_to_temp(self.base_config.csv_file)

    # Create JournalStorage for multi-process coordination
    from optuna.storages import JournalStorage
    from optuna.storages.journal import JournalFileBackend

    journal_dir = Path(tempfile.gettempdir()) / "merlin_optuna_journals"
    journal_dir.mkdir(exist_ok=True)

    timestamp = int(time.time())
    study_name = self.optuna_config.study_name or f"strategy_opt_{timestamp}"
    storage_path = str(journal_dir / f"{study_name}_{timestamp}.journal.log")

    storage = JournalStorage(JournalFileBackend(storage_path))
    logger.info(f"Multi-process storage: {storage_path}")

    # Create sampler and pruner
    sampler = self._create_sampler()
    self.pruner = self._create_pruner()

    # Create study
    self.study = optuna.create_study(
        study_name=study_name,
        direction="maximize",
        sampler=sampler,
        pruner=self.pruner,
        storage=storage,
        load_if_exists=True,
    )

    # Budget configuration
    n_trials: Optional[int] = None
    timeout: Optional[int] = None

    if self.optuna_config.budget_mode == "time":
        timeout = max(60, int(self.optuna_config.time_limit))
        logger.info(f"Time budget: {timeout}s per worker")
    elif self.optuna_config.budget_mode == "trials":
        n_trials = max(1, int(self.optuna_config.n_trials))
        logger.info(f"Trial budget: {n_trials} total (global limit via MaxTrialsCallback)")
    elif self.optuna_config.budget_mode == "convergence":
        # Convergence mode doesn't work well with multi-process
        # (per-process counters don't see global state)
        logger.warning(
            "Convergence mode is not fully supported in multi-process optimization. "
            "Using trial cap of 10000 instead. Consider using 'trials' budget mode."
        )
        n_trials = 10000

    # Serialize configs for workers (must be picklable dicts)
    base_config_dict = asdict(self.base_config)
    base_config_dict["csv_file"] = csv_path  # Use materialized path

    optuna_config_dict = asdict(self.optuna_config)

    # Spawn worker processes
    processes: List[mp.Process] = []

    try:
        for worker_id in range(n_workers):
            p = mp.Process(
                target=_worker_process_entry,
                args=(
                    study_name,
                    storage_path,
                    base_config_dict,
                    optuna_config_dict,
                    n_trials,
                    timeout,
                    worker_id,
                ),
                name=f"OptunaWorker-{worker_id}",
            )
            processes.append(p)
            p.start()
            logger.info(f"Started worker {worker_id} (PID: {p.pid})")

        # Wait for all workers
        logger.info(f"Waiting for {n_workers} workers to complete...")
        for worker_id, p in enumerate(processes):
            p.join()
            if p.exitcode == 0:
                logger.info(f"Worker {worker_id} finished successfully")
            else:
                logger.error(f"Worker {worker_id} exited with code {p.exitcode}")

        logger.info("All workers completed")

    except KeyboardInterrupt:
        logger.info("Optimization interrupted - terminating workers...")
        for p in processes:
            if p.is_alive():
                p.terminate()
        for p in processes:
            p.join(timeout=5)

    # Reload study to get all results from shared storage
    self.study = optuna.load_study(study_name=study_name, storage=storage)

    # Reconstruct results from trial user_attrs
    logger.info(f"Extracting results from {len(self.study.trials)} trials...")
    self.trial_results = []
    for trial in self.study.trials:
        if trial.state == TrialState.COMPLETE:
            try:
                result = _result_from_trial(trial)
                self.trial_results.append(result)
            except Exception as exc:
                logger.warning(f"Failed to reconstruct trial {trial.number}: {exc}")

    logger.info(f"Reconstructed {len(self.trial_results)} results")

    # Cleanup temp files
    if csv_needs_cleanup:
        try:
            Path(csv_path).unlink(missing_ok=True)
            logger.debug(f"Cleaned up temp CSV: {csv_path}")
        except Exception:
            pass

    if not self.optuna_config.save_study:
        try:
            Path(storage_path).unlink(missing_ok=True)
            logger.debug(f"Cleaned up storage: {storage_path}")
        except Exception:
            pass

    self.pruner = None

    return self._finalize_results()


def _finalize_results(self) -> List[OptimizationResult]:
    """
    Finalize optimization results: calculate scores, sort, and build summary.

    Called by both single-process and multi-process paths.
    """
    end_time = time.time()
    optimization_time = end_time - (self.start_time or end_time)

    logger.info(
        "Optimization completed: trials=%s, time=%.1fs",
        len(self.study.trials) if self.study else len(self.trial_results),
        optimization_time,
    )

    # Calculate composite scores using percentile ranking
    # This is done post-hoc with the FULL result set (critical for multi-process)
    score_config = self.base_config.score_config or DEFAULT_SCORE_CONFIG
    self.trial_results = calculate_score(self.trial_results, score_config)

    # Build summary
    if self.study:
        completed_trials = sum(
            1 for t in self.study.trials if t.state == TrialState.COMPLETE
        )
        pruned_trials = sum(
            1 for t in self.study.trials if t.state == TrialState.PRUNED
        )
        total_trials = len(self.study.trials)

        # For "score" target, best_value should be the best composite score
        # (not the proxy objective used during optimization)
        if self.optuna_config.target == "score" and self.trial_results:
            best_value = max(r.score for r in self.trial_results)
        elif self.study.best_trial:
            best_value = self.study.best_value
        else:
            best_value = None

        best_trial_number = (
            self.study.best_trial.number if self.study.best_trial else None
        )
    else:
        completed_trials = len(self.trial_results)
        pruned_trials = self.pruned_trials
        total_trials = completed_trials + pruned_trials
        best_trial_number = None
        best_value = None

    summary = {
        "method": "Optuna",
        "target": self.optuna_config.target,
        "budget_mode": self.optuna_config.budget_mode,
        "total_trials": total_trials,
        "completed_trials": completed_trials,
        "pruned_trials": pruned_trials,
        "best_trial_number": best_trial_number,
        "best_value": best_value,
        "optimization_time_seconds": optimization_time,
        "multiprocess_mode": self._multiprocess_mode,
    }
    setattr(self.base_config, "optuna_summary", summary)

    # Sort results by target metric
    if self.optuna_config.target == "max_drawdown":
        self.trial_results.sort(key=lambda r: float(r.max_drawdown_pct))
    elif self.optuna_config.target == "score":
        self.trial_results.sort(key=lambda r: float(r.score), reverse=True)
    elif self.optuna_config.target == "net_profit":
        self.trial_results.sort(key=lambda r: float(r.net_profit_pct), reverse=True)
    elif self.optuna_config.target == "romad":
        self.trial_results.sort(
            key=lambda r: float(r.romad or float("-inf")), reverse=True
        )
    elif self.optuna_config.target == "sharpe":
        self.trial_results.sort(
            key=lambda r: float(r.sharpe_ratio or float("-inf")), reverse=True
        )
    else:
        self.trial_results.sort(key=lambda r: float(r.score), reverse=True)

    return self.trial_results
```

---

### Step 10: Update run_optuna_optimization (No Changes Needed)

The existing `run_optuna_optimization` function at line 770 already calls `optimizer.optimize()`, which now handles both modes automatically.

---

## 6. Complete Code Changes

### Summary of All Modifications

| Location | Change Type | Description |
|----------|-------------|-------------|
| Line ~11 | ADD | Import `tempfile`, `asdict`, `Path` |
| After line 206 | ADD | `_trial_set_result_attrs()` helper |
| After line 206 | ADD | `_result_from_trial()` helper |
| After line 206 | ADD | `_materialize_csv_to_temp()` helper |
| After line 206 | ADD | `_worker_process_entry()` function |
| Lines 328-339 | REPLACE | `__init__` - remove pool, add data cache vars |
| Lines 466-500 | REPLACE | Rename to `_prepare_data_and_strategy()`, remove pool |
| Lines 505-510 | REPLACE | `_evaluate_parameters()` - direct call |
| After line 634 | ADD | `_objective_for_worker()` method |
| Lines 624-626 | MODIFY | Add `_trial_set_result_attrs()` call |
| Lines 639-767 | REPLACE | Split into `optimize()`, `_optimize_single_process()`, `_optimize_multiprocess()`, `_finalize_results()` |

### Files NOT Modified

- `src/ui/server.py` - No changes needed
- `src/core/backtest_engine.py` - No changes needed
- `src/strategies/*` - No changes needed

---

## 7. Testing & Verification

### Test 1: Single-Process Baseline (Regression Test)

**Purpose:** Verify single-process mode works exactly as before.

**Setup:**
```python
# Via API or direct call
config = {
    "worker_processes": 1,
    "optuna_budget_mode": "trials",
    "optuna_n_trials": 20,
    "optuna_target": "score",
    # ... other params
}
```

**Verify:**
- [ ] Completes without errors
- [ ] Returns expected number of results
- [ ] CPU usage: ~12-15% (1 core at 100%)
- [ ] Logs show "Starting single-process Optuna optimization"

---

### Test 2: Multi-Process Speedup

**Purpose:** Verify true multi-core parallelization.

**Setup:**
```python
config = {
    "worker_processes": 6,
    "optuna_budget_mode": "trials",
    "optuna_n_trials": 50,
    "optuna_target": "romad",
    # ... other params
}
```

**Verify:**
- [ ] Logs show "Starting multi-process Optuna optimization"
- [ ] Logs show "Started worker X (PID: XXXXX)" for 6 workers
- [ ] Task Manager shows 6 Python processes
- [ ] CPU usage: 75-95% (all cores active)
- [ ] Completes ~4-5x faster than single-process

---

### Test 3: Global Trial Budget Enforcement

**Purpose:** Verify MaxTrialsCallback limits total trials.

**Setup:**
```python
config = {
    "worker_processes": 4,
    "optuna_budget_mode": "trials",
    "optuna_n_trials": 40,
    # ...
}
```

**Verify:**
- [ ] `optuna_summary["total_trials"]` is approximately 40 (not 160)
- [ ] Logs show "Trial budget: 40 total (global limit via MaxTrialsCallback)"

---

### Test 4: Time Budget Mode

**Purpose:** Verify timeout works in multi-process mode.

**Setup:**
```python
config = {
    "worker_processes": 4,
    "optuna_budget_mode": "time",
    "optuna_time_limit": 60,  # 60 seconds
    # ...
}
```

**Verify:**
- [ ] Optimization completes in approximately 60 seconds
- [ ] All workers terminate after timeout
- [ ] Results are properly collected

---

### Test 5: Score Target with Multi-Process

**Purpose:** Verify composite score calculation works correctly.

**Setup:**
```python
config = {
    "worker_processes": 4,
    "optuna_target": "score",
    "optuna_n_trials": 50,
    # ...
}
```

**Verify:**
- [ ] Results have non-zero `score` values
- [ ] Results are sorted by score (descending)
- [ ] `optuna_summary["best_value"]` equals best `score` (not proxy objective)

---

### Test 6: Flask Endpoint Integration

**Purpose:** Verify `/api/optimize` works with multi-process.

**Test both:**
1. File upload (Flask `FileStorage` object)
2. `csvPath` parameter (file path string)

**Verify:**
- [ ] Both methods work without "can't pickle" errors
- [ ] Temp file cleanup works (check temp directory)
- [ ] Response contains correct results

---

### Test 7: Convergence Mode Degradation

**Purpose:** Verify convergence mode doesn't crash.

**Setup:**
```python
config = {
    "worker_processes": 4,
    "optuna_budget_mode": "convergence",
    "optuna_convergence": 50,
    # ...
}
```

**Verify:**
- [ ] Warning logged: "Convergence mode is not fully supported..."
- [ ] Optimization runs with 10000 trial cap
- [ ] Completes successfully (may hit MaxTrialsCallback first)

---

## 8. Troubleshooting

### Issue 1: "Can't pickle local object"

**Symptoms:**
```
AttributeError: Can't pickle local object 'OptunaOptimizer.optimize.<locals>.<lambda>'
```

**Cause:** Lambda or nested function passed to `mp.Process`.

**Fix:** Ensure `_worker_process_entry` is at module level (not inside a class or function). Verify you're not passing lambdas to workers.

---

### Issue 2: "No module named 'optuna.storages.journal'"

**Symptoms:**
```
ImportError: cannot import name 'JournalFileBackend' from 'optuna.storages.journal'
```

**Cause:** Optuna version < 4.0.0

**Fix:**
```bash
pip install --upgrade "optuna>=4.0.0"
python -c "import optuna; print(optuna.__version__)"  # Should be 4.4.0
```

---

### Issue 3: Only 1 Core Used in Multi-Process Mode

**Symptoms:**
- Logs show workers starting
- CPU usage stays at ~15%

**Debug Steps:**
1. Check for worker error logs
2. Verify `p.exitcode` for each worker (0 = success)
3. Check if workers are actually running trials (look for JournalStorage file growing)
4. On Windows, ensure no import-time code spawns processes

---

### Issue 4: JournalStorage Permission Error (Windows)

**Symptoms:**
```
PermissionError: [WinError 32] The process cannot access the file...
```

**Cause:** File locking conflict on Windows.

**Fix:** Use `JournalFileOpenLock`:

```python
from optuna.storages.journal import JournalFileBackend, JournalFileOpenLock

lock_obj = JournalFileOpenLock(storage_path)
storage = JournalStorage(JournalFileBackend(storage_path, lock_obj=lock_obj))
```

---

### Issue 5: Results Missing After Multi-Process

**Symptoms:**
- Workers complete successfully
- `trial_results` is empty or incomplete

**Debug:**
1. Check trial states in study:
   ```python
   print(f"Total: {len(study.trials)}")
   print(f"Complete: {sum(1 for t in study.trials if t.state == TrialState.COMPLETE)}")
   print(f"Pruned: {sum(1 for t in study.trials if t.state == TrialState.PRUNED)}")
   print(f"Failed: {sum(1 for t in study.trials if t.state == TrialState.FAIL)}")
   ```
2. Check user_attrs are being stored:
   ```python
   trial = study.trials[0]
   print(trial.user_attrs)  # Should have merlin.* keys
   ```
3. Verify `_trial_set_result_attrs` is called in `_objective_for_worker`

---

### Issue 6: Score Values All Zero

**Symptoms:**
- Results have `score=0.0`

**Cause:** `calculate_score()` not called or config missing.

**Fix:** Verify `_finalize_results()` calls `calculate_score(self.trial_results, score_config)` and that `score_config` has proper `enabled_metrics` and `weights`.

---

### Issue 7: Workers Hang Indefinitely

**Symptoms:**
- Workers start but never finish
- No logs after "Worker X starting optimization"

**Debug:**
1. Add verbose logging in `_objective_for_worker`
2. Check if data loading fails silently
3. Try single-process mode to isolate the issue
4. Check for deadlocks in backtest logic

**Quick test:**
```python
# Run one worker's logic directly
optimizer = OptunaOptimizer(base_config, optuna_config)
optimizer._prepare_data_and_strategy()
# If this hangs, the issue is in data loading
```

---

### Issue 8: Memory Usage Very High

**Symptoms:**
- System runs out of RAM
- OOM killer terminates processes

**Cause:** Each worker loads its own DataFrame copy.

**Expected memory:**
```
Memory = N_workers × DataFrame_size + overhead

Example (100MB CSV, 6 workers):
~650 MB total
```

**Mitigations:**
- Reduce `worker_processes` on low-memory systems
- Use smaller date range to reduce DataFrame size
- Close other applications

---

## Appendix A: Constant Liar TPE Sampler

The TPE sampler is configured with `constant_liar=True` (line 441 in current code). This is critical for multi-process optimization:

1. Worker A requests next trial parameters
2. TPE suggests `maLength=50`
3. Worker A starts evaluation (not yet complete)
4. Worker B requests next parameters
5. TPE assumes A's trial will return a "median" value (the "lie")
6. TPE suggests `maLength=75` to B (avoids duplicating 50)
7. Worker A completes, true result replaces the "lie"

This ensures workers explore different regions of parameter space without duplicating work.

---

## Appendix B: Why Not Use n_jobs?

```python
# This does NOT help for CPU-bound work:
study.optimize(objective, n_trials=100, n_jobs=6)
```

Optuna's `n_jobs` spawns threads, not processes. Due to Python's GIL:
- Only one thread executes Python bytecode at a time
- Threading helps I/O-bound work (network, disk)
- Threading does NOT help CPU-bound work (our backtest loop)

Multi-process with shared storage is the correct solution for CPU-bound objectives.

---

## Appendix C: API Reference (Optuna 4.4.0)

### JournalStorage

```python
from optuna.storages import JournalStorage
from optuna.storages.journal import JournalFileBackend

storage = JournalStorage(JournalFileBackend("/path/to/study.log"))
```

### MaxTrialsCallback

```python
from optuna.study import MaxTrialsCallback

# states=None counts ALL trial states (COMPLETE, PRUNED, FAIL)
callback = MaxTrialsCallback(n_trials=100, states=None)

study.optimize(objective, n_trials=None, callbacks=[callback])
```

### Key Documentation Links

- [Easy Parallelization](https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/004_distributed.html)
- [FAQ - Parallelization](https://optuna.readthedocs.io/en/stable/faq.html)
- [JournalStorage](https://optuna.readthedocs.io/en/stable/reference/generated/optuna.storages.JournalStorage.html)
- [MaxTrialsCallback](https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.MaxTrialsCallback.html)

---

## Final Checklist

Before submitting, verify:

- [ ] All imports added at top of file
- [ ] Helper functions are at module level (not inside class)
- [ ] `_worker_process_entry` is at module level
- [ ] `__init__` removes `self.pool`, adds data cache vars
- [ ] `_setup_worker_pool` renamed to `_prepare_data_and_strategy`
- [ ] `_evaluate_parameters` no longer uses pool
- [ ] `_objective_for_worker` added for workers
- [ ] `_objective` calls `_trial_set_result_attrs`
- [ ] `optimize()` branches on `worker_processes`
- [ ] `_optimize_multiprocess` uses JournalStorage + MaxTrialsCallback
- [ ] `_finalize_results` calculates scores post-hoc
- [ ] No lambdas passed to `mp.Process`
- [ ] Temp file cleanup implemented
- [ ] All 8 tests pass

---

**End of Implementation Prompt**
