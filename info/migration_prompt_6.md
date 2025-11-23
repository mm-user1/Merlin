# Migration Prompt 6: Update Optimization Engines (Grid & Optuna)

## Objective

Update `optimizer_engine.py` and `optuna_engine.py` to use the new modular strategy system instead of hardcoded S01 logic. This stage removes caching for MVP simplicity and makes both optimizers strategy-agnostic.

## Prerequisites

Complete **migration_prompt_5.md** before starting this stage.

## Background: Current Architecture

The current optimization engines contain **hardcoded S01 strategy logic**:

**optimizer_engine.py:**
- `_init_worker()` (lines ~269-340): Pre-computes MA/ATR caches for performance
- `_simulate_combination()` (lines ~342-700): Contains full S01 bar-by-bar trading logic (350+ lines of duplicated code)
- Uses global caches: `_ma_cache`, `_atr_values`, `_lowest_cache`, `_highest_cache`

**optuna_engine.py:**
- Imports and reuses `_simulate_combination` from `optimizer_engine.py`
- Also relies on the caching system

**Problem:** These functions are tightly coupled to S01 parameters and logic. After extracting S01 to `strategies/s01_trailing_ma/strategy.py`, the optimizer engines will break.

**Solution:** Replace hardcoded simulation with `strategy_class.run()` calls. Remove caching for MVP (can be re-added later as optimization).

---

## ⚠️ Why Remove Caching? Understanding Separation of Concerns

The current `_simulate_combination()` function contains **350+ lines of hardcoded S01 trading logic**. This violates the separation of concerns principle:

### **Current Problem:**
```python
def _simulate_combination(params_dict):
    # Optimizer knows about:
    ma_type = params_dict["ma_type"]           # ❌ Strategy detail!
    trail_ma_long_type = params_dict["..."]    # ❌ Strategy detail!
    stop_long_atr = params_dict["..."]         # ❌ Strategy detail!

    # Optimizer implements:
    if c > ma_value:                            # ❌ S01 entry logic!
        counter_close_trend_long += 1
    if counter_close_trend_long >= close_count_long:  # ❌ S01 logic!
        open_long_position()

    # 350+ more lines of S01-specific code...
```

**This makes the optimizer S01-only!** Can't use it for RSI strategy, MACD strategy, etc.

### **Correct Separation:**

**Optimizer should handle:**
✅ Parameter combinations generation
✅ Multiprocessing orchestration
✅ Result collection and scoring
✅ Progress tracking

**Strategy should handle:**
✅ Trading logic (entry/exit rules)
✅ Indicator calculations (MA, ATR, RSI, etc.)
✅ Metrics computation (profit, drawdown, sharpe)

### **Solution: Replace with Strategy Call**
```python
def _run_single_combination(args):
    params_dict, df, trade_start_idx, strategy_class = args

    # Optimizer just calls strategy - doesn't know HOW it works!
    result = strategy_class.run(df, params_dict, trade_start_idx)

    # Convert to OptimizationResult
    return OptimizationResult(
        params=params_dict,
        net_profit_pct=result.net_profit_pct,
        ...
    )
```

**Now optimizer works with ANY strategy!** 🎉

### **Caching Trade-off:**

**With caching (current):**
- ✅ Fast: ~200-500 combos/second
- ❌ S01-only: hardcoded MA types, stop logic
- ❌ Can't add new strategies

**Without caching (MVP):**
- ✅ Strategy-agnostic: works with any strategy
- ✅ Simple and maintainable
- ❌ Slower: ~50-100 combos/second (3× slower)

**Future (post-MVP):**
- Re-implement caching at strategy level
- Each strategy defines `calculate_indicators()` for caching
- Platform caches common indicators (MA, ATR) generically
- Best of both worlds!

**For MVP: Correctness > Speed.** Get it working first, optimize later.

---

## Tasks

### Task 6.1: Add Strategy Support to OptimizationConfig

**File:** `src/optimizer_engine.py`

**Find the `OptimizationConfig` dataclass (around line 46):**
```python
@dataclass
class OptimizationConfig:
    """Configuration received from the optimizer form."""

    csv_file: IO[Any]
    # ... existing fields ...
```

**Add new fields at the end:**
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

    # NEW: Add these fields
    strategy_id: str = "s01_trailing_ma"  # Default to S01
    warmup_bars: int = 1000  # User-controlled warmup
```

### Task 6.2: Replace _simulate_combination with Strategy Call

**This is the critical change.** We're replacing 350+ lines of hardcoded S01 logic with a simple strategy call.

**Find and DELETE:**
1. The entire `_init_worker()` function (lines ~269-340)
2. The entire `_simulate_combination()` function (lines ~342-700+)

**Add new worker function at the same location:**
```python
def _run_single_combination(args: Tuple[Dict[str, Any], pd.DataFrame, int, Any]) -> OptimizationResult:
    """
    Worker function to run a single parameter combination using strategy.run().

    Args:
        args: Tuple of (params_dict, df, trade_start_idx, strategy_class)

    Returns:
        OptimizationResult with metrics for this combination
    """
    params_dict, df, trade_start_idx, strategy_class = args

    try:
        # Call strategy.run() instead of hardcoded logic
        result = strategy_class.run(df, params_dict, trade_start_idx)

        # Convert StrategyResult to OptimizationResult
        opt_result = OptimizationResult(
            params=params_dict,
            net_profit_pct=result.net_profit_pct,
            max_drawdown_pct=result.max_drawdown_pct,
            trades_count=result.total_trades,
            sharpe_ratio=result.sharpe_ratio,
            profit_factor=result.profit_factor,
            romad=result.romad,
            ulcer_index=result.ulcer_index,
            recovery_factor=result.recovery_factor,
            consistency_score=result.consistency_score,
        )
        return opt_result

    except Exception as e:
        # Return failed result with zero metrics
        return OptimizationResult(
            params=params_dict,
            net_profit_pct=0.0,
            max_drawdown_pct=0.0,
            trades_count=0,
            sharpe_ratio=None,
            profit_factor=None,
            romad=None,
            ulcer_index=None,
            recovery_factor=None,
            consistency_score=None,
        )
```

### Task 6.3: Update run_grid_optimization Function

**Find the `run_grid_optimization()` function (around line 844).**

**Replace the entire function with:**
```python
def run_grid_optimization(config: OptimizationConfig) -> List[OptimizationResult]:
    """Execute the grid search optimization using modular strategy system."""

    # Load strategy
    from strategies import get_strategy
    try:
        strategy_class = get_strategy(config.strategy_id)
    except ValueError as e:
        raise ValueError(f"Failed to load strategy '{config.strategy_id}': {e}")

    # Load data
    df = load_data(config.csv_file)

    # Generate parameter combinations
    combinations = generate_parameter_grid(config)
    total = len(combinations)
    if total == 0:
        raise ValueError("No parameter combinations generated for optimization.")

    # Prepare dataset with warmup
    use_date_filter = bool(config.fixed_params.get("dateFilter", False))
    start = _parse_timestamp(config.fixed_params.get("start"))
    end = _parse_timestamp(config.fixed_params.get("end"))

    trade_start_idx = 0
    if use_date_filter and (start is not None or end is not None):
        from backtest_engine import prepare_dataset_with_warmup

        try:
            df, trade_start_idx = prepare_dataset_with_warmup(
                df, start, end, config.warmup_bars
            )
        except Exception as exc:
            raise ValueError(f"Failed to prepare dataset with warmup: {exc}")

    # Create worker arguments
    # Each worker gets: (params_dict, df, trade_start_idx, strategy_class)
    worker_args = [
        (combo, df, trade_start_idx, strategy_class)
        for combo in combinations
    ]

    # Run optimization with multiprocessing
    results: List[OptimizationResult] = []
    processes = min(32, max(1, int(config.worker_processes)))

    # Note: No initializer needed - each task is self-contained
    with mp.Pool(processes=processes) as pool:
        progress_iter = tqdm(
            pool.imap_unordered(_run_single_combination, worker_args, chunksize=CHUNK_SIZE),
            desc="Optimizing",
            total=total,
            unit="combo",
        )
        for result in progress_iter:
            results.append(result)

    return results
```

**Key changes:**
1. Loads strategy using `get_strategy(config.strategy_id)`
2. Uses `config.warmup_bars` instead of calculating from parameters
3. Calls `_run_single_combination()` which internally uses `strategy_class.run()`
4. No caching - each combination re-runs the strategy (MVP simplicity)
5. Uses `imap_unordered` for better progress tracking

### Task 6.4: Update Optuna Engine

**File:** `src/optuna_engine.py`

**Find the import section (around line 17):**
```python
from optimizer_engine import (
    CHUNK_SIZE,
    OptimizationConfig,
    OptimizationResult,
    _init_worker,
    _simulate_combination,
    generate_parameter_grid,
)
```

**Replace with:**
```python
from optimizer_engine import (
    CHUNK_SIZE,
    OptimizationConfig,
    OptimizationResult,
    _run_single_combination,  # Changed from _simulate_combination
    _parse_timestamp,  # Add this helper function
    generate_parameter_grid,
)
# Note: _init_worker is removed (no longer needed)
```

**Find the `_setup_worker_pool()` method in OptunaOptimizer class (around line 180):**

Current code looks like:
```python
def _setup_worker_pool(self) -> None:
    """Initialise the worker pool with pre-computed caches."""

    from backtest_engine import prepare_dataset_with_warmup, StrategyParams

    # ... lots of code to prepare caches ...

    pool_args = (
        df,
        # ... many cache-related args ...
    )
    self.pool = mp.Pool(
        processes=processes,
        initializer=_init_worker,
        initargs=pool_args,
    )
```

**Replace the entire `_setup_worker_pool()` method with:**
```python
def _setup_worker_pool(self) -> None:
    """Initialize the worker pool for Optuna optimization."""

    # Load strategy
    from strategies import get_strategy
    try:
        strategy_class = get_strategy(self.base_config.strategy_id)
    except ValueError as e:
        raise ValueError(f"Failed to load strategy '{self.base_config.strategy_id}': {e}")

    # Load and prepare data
    from backtest_engine import load_data, prepare_dataset_with_warmup

    df = load_data(self.base_config.csv_file)

    use_date_filter = bool(self.base_config.fixed_params.get("dateFilter", False))
    start = self._parse_timestamp(self.base_config.fixed_params.get("start"))
    end = self._parse_timestamp(self.base_config.fixed_params.get("end"))

    trade_start_idx = 0
    if use_date_filter and (start is not None or end is not None):
        try:
            df, trade_start_idx = prepare_dataset_with_warmup(
                df, start, end, self.base_config.warmup_bars
            )
        except Exception as exc:
            raise ValueError(f"Failed to prepare dataset with warmup: {exc}")

    # Store for later use
    self.df = df
    self.trade_start_idx = trade_start_idx
    self.strategy_class = strategy_class

    # Create simple pool without initializer
    processes = min(32, max(1, int(self.base_config.worker_processes)))
    self.pool = mp.Pool(processes=processes)
```

**Find the `_evaluate_params()` method (around line 290):**

Current code:
```python
def _evaluate_params(self, params_dict: Dict[str, Any]) -> OptimizationResult:
    """Evaluate a single parameter set using the worker pool."""
    if self.pool is None:
        raise RuntimeError("Worker pool not initialized")

    return self.pool.apply(_simulate_combination, (params_dict,))
```

**Replace with:**
```python
def _evaluate_params(self, params_dict: Dict[str, Any]) -> OptimizationResult:
    """Evaluate a single parameter set using the worker pool."""
    if self.pool is None:
        raise RuntimeError("Worker pool not initialized")

    # Prepare args for _run_single_combination
    args = (params_dict, self.df, self.trade_start_idx, self.strategy_class)

    return self.pool.apply(_run_single_combination, (args,))
```

**Note:** The `_parse_timestamp()` helper function is used in `_setup_worker_pool()` and has already been imported in Task 6.4 above.

### Task 6.5: Update Server Endpoint to Pass Strategy Info

**File:** `src/server.py`

**Find the `_build_optimization_config()` function (around line 550):**

**Update the function signature to accept strategy parameters:**
```python
def _build_optimization_config(
    csv_file,
    payload: dict,
    worker_processes=None,
    strategy_id=None,
    warmup_bars=None
) -> OptimizationConfig:
    """Build optimization config from request payload."""

    if strategy_id is None:
        strategy_id = "s01_trailing_ma"
    if warmup_bars is None:
        warmup_bars = 1000

    # ... existing code to parse payload ...

    # At the end, when creating OptimizationConfig:
    return OptimizationConfig(
        csv_file=csv_file,
        worker_processes=worker_processes or 6,
        # ... all existing fields ...
        score_config=score_config,

        # NEW: Add these
        strategy_id=strategy_id,
        warmup_bars=warmup_bars,
    )
```

**Find the `/api/optimize` endpoint (around line 923):**

**Update to extract and pass strategy parameters:**
```python
@app.post("/api/optimize")
def run_optimization_endpoint() -> object:
    """Run grid or optuna optimization with selected strategy."""

    # Get strategy ID and warmup bars
    strategy_id = request.form.get("strategy", "s01_trailing_ma")
    warmup_bars_raw = request.form.get("warmupBars", "1000")
    try:
        warmup_bars = int(warmup_bars_raw)
        warmup_bars = max(100, min(5000, warmup_bars))
    except (TypeError, ValueError):
        warmup_bars = 1000

    # ... existing code to get worker_processes, CSV files, etc. ...

    # Build optimization config with strategy info
    optimization_config = _build_optimization_config(
        data_source,
        config_payload,
        worker_processes,
        strategy_id,      # NEW
        warmup_bars       # NEW
    )

    # ... rest of existing code (unchanged) ...
```

### Task 6.6: Update JavaScript to Send Strategy ID

**File:** `src/index.html`

**Find the `runOptimization()` or `submitOptimization()` function (search for `'/api/optimize'`):**

**Add strategy ID and warmup bars to FormData:**
```javascript
async function submitOptimization() {
    const formData = new FormData();

    // Add strategy ID
    formData.append('strategy', currentStrategyId);  // currentStrategyId set by strategy selector

    // Add warmup bars
    const warmupBars = document.getElementById('warmupBars').value;
    formData.append('warmupBars', warmupBars);

    // ... rest of existing code to collect parameters ...

    const response = await fetch('/api/optimize', {
        method: 'POST',
        body: formData
    });

    // ... rest of existing code ...
}
```

---

## Testing

### Test 6.1: Grid Search Single-File Optimization

**Prerequisites:** S01 strategy extracted and registered (from previous stages).

**Steps:**
1. Start server: `cd src && python server.py`
2. Open browser: `http://localhost:8000`
3. Select strategy: "S01 Trailing MA v26"
4. Load CSV: `data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
5. Enable date filter: 2025-06-15 to 2025-11-15
6. Set warmup bars: 1000
7. Configure optimizer:
   - Method: Grid Search
   - Enable "T MA Length": From 200, To 400, Step 100 (3 combinations)
   - Disable all other parameters
8. Click "Optimize"

**Expected Results:**
- Optimization starts without errors
- Progress bar shows "3 combos"
- Results CSV downloads with 3 rows
- Check CSV:
  - Parameter block shows `maLength: (fixed value)`
  - Results table has columns: `ma_length, net_profit_pct, max_drawdown_pct, trades, sharpe, score`
  - All 3 combinations completed (non-zero trades)

**If errors occur:**
- Check browser console for JS errors
- Check server logs for Python exceptions
- Verify `_run_single_combination` is called correctly
- Verify `strategy_class.run()` returns valid StrategyResult

### Test 6.2: Grid Search Multi-Parameter Optimization

**Steps:**
1. Same setup as Test 6.1
2. Enable multiple parameters:
   - T MA Length: 200 to 400, step 100 (3 values)
   - Close Count Long: 5 to 9, step 2 (3 values)
   - Stop Long ATR: 1.5 to 2.5, step 0.5 (3 values)
3. Total combinations: 3 × 3 × 3 = 27
4. Click "Optimize"

**Expected Results:**
- CSV downloads with 27 rows
- All combinations have valid metrics
- Progress shows completion in reasonable time (<30 seconds on modern hardware)

**Performance Note:**
- Without caching, each combination recalculates all indicators
- This is slower than cached version but acceptable for MVP
- Future optimization: re-implement caching as strategy-agnostic system

### Test 6.3: Optuna Optimization

**Steps:**
1. Same setup as Test 6.1
2. Configure optimizer:
   - Method: Optuna (smart search)
   - Target: Composite Score
   - Budget: Number of trials = 50
   - Enable parameters:
     - T MA Length: 100 to 500, step 10
     - Close Count Long: 3 to 15, step 1
     - Stop Long ATR: 1.0 to 3.0, step 0.1
3. Click "Optimize"

**Expected Results:**
- Optuna starts without errors
- Progress shows trials completing (1, 2, 3, ... 50)
- CSV downloads with 50 rows (one per trial)
- Best trial should have higher score than random trials
- Check logs: "Best trial: #X with score Y.YY"

**Common Issues:**
- Import error: Verify `_run_single_combination` is imported in `optuna_engine.py`
- Pool error: Verify `_setup_worker_pool()` stores `self.df`, `self.strategy_class`, `self.trade_start_idx`
- Evaluation error: Verify `_evaluate_params()` packs args correctly

### Test 6.4: Strategy Parameter Validation

**Test that optimizer respects strategy config:**

**Steps:**
1. Create a test config in `strategies/s01_trailing_ma/config.json`
2. Set a parameter's optimize range: `"maLength": {"optimize": {"min": 50, "max": 100}}`
3. In UI, enable "T MA Length" optimization but set different range (200-400)
4. Run optimization

**Expected Behavior:**
- Optimizer should use UI range (200-400), not config range (50-100)
- UI values override config defaults

**Why:** Optimizer uses `config.param_ranges` which comes from UI, not strategy config.

### Test 6.5: Multi-File Grid Search

**Steps:**
1. Select multiple CSV files (e.g., 3 different symbols)
2. Configure Grid search with 2-3 parameters (9-27 combinations)
3. Click "Optimize"

**Expected Results:**
- Results CSV contains sections for each file:
  ```
  # FILE: file1.csv
  # Parameter Block...
  ma_length,close_count_long,net_profit_pct,...
  200,5,15.2,...
  ...

  # FILE: file2.csv
  # Parameter Block...
  ...
  ```
- Each file's section has all combinations tested
- No errors during multi-file processing

---

## Completion Checklist

- [ ] `OptimizationConfig` updated with `strategy_id` and `warmup_bars` fields
- [ ] `_init_worker()` function deleted
- [ ] `_simulate_combination()` function deleted
- [ ] New `_run_single_combination()` function added
- [ ] `run_grid_optimization()` updated to use strategy system
- [ ] `optuna_engine.py` imports updated (removed `_init_worker`, added `_run_single_combination`)
- [ ] `OptunaOptimizer._setup_worker_pool()` updated
- [ ] `OptunaOptimizer._evaluate_params()` updated
- [ ] `_build_optimization_config()` updated with new parameters
- [ ] `/api/optimize` endpoint updated to pass strategy_id and warmup_bars
- [ ] JavaScript updated to send strategy_id and warmup_bars
- [ ] Test 6.1 passed (Grid single-file)
- [ ] Test 6.2 passed (Grid multi-parameter)
- [ ] Test 6.3 passed (Optuna)
- [ ] Test 6.4 passed (Parameter validation)
- [ ] Test 6.5 passed (Multi-file)
- [ ] No errors in server logs
- [ ] No errors in browser console
- [ ] Git commit: "Migration Stage 6: Update Grid & Optuna optimizers for modular strategies"

---

## Performance Notes

**Expected Performance Impact:**

Without caching, optimization will be **slower** than the original cached version:
- **Original (with cache):** ~200-500 combos/second (depending on hardware)
- **MVP (no cache):** ~50-100 combos/second

**Why is this acceptable for MVP:**
1. Code simplicity - easier to maintain and extend
2. Strategy-agnostic - works with any strategy, not just S01
3. Correctness over speed - ensures each combination is independent
4. Future optimization path - caching can be re-added later as a separate enhancement

**When to re-add caching:**
After confirming the modular system works correctly, caching can be re-implemented as:
1. Strategy-level caching: Each strategy defines what indicators to cache
2. Universal cache manager: Centralized cache for common indicators (MA, ATR, etc.)
3. Cache validation: Verify cached values match non-cached for correctness

**For now:** Focus on correctness and modularity. Performance optimization comes later.

---

## Common Issues & Troubleshooting

### Issue 1: "StrategyResult has no attribute 'romad'"

**Cause:** `strategy.run()` returns incomplete result object.

**Fix:** Verify `strategies/s01_trailing_ma/strategy.py` returns all required metrics:
```python
return StrategyResult(
    net_profit_pct=...,
    max_drawdown_pct=...,
    trades_count=...,
    sharpe_ratio=...,
    profit_factor=...,
    romad=...,            # Required
    ulcer_index=...,      # Required
    recovery_factor=...,  # Required
    consistency_score=...,# Required
    trades=[]
)
```

### Issue 2: "Pool worker crashed"

**Cause:** Exception in `_run_single_combination()` not caught.

**Fix:** Verify the try/except block in `_run_single_combination()` catches all exceptions and returns valid OptimizationResult with zero metrics.

### Issue 3: Slow optimization (>5 seconds for small grid)

**Cause:** DataFrame being pickled and sent to each worker.

**Mitigation:** This is expected without caching. For large optimizations (>1000 combos), consider:
1. Reducing search space
2. Using Optuna instead of Grid
3. Using fewer worker processes (paradoxically can be faster due to less overhead)

### Issue 4: "strategy_class not picklable"

**Cause:** Trying to send strategy class to workers via pool initializer.

**Fix:** Send strategy_id as string, let each worker call `get_strategy(strategy_id)` locally.

**Better approach (if issue persists):**
```python
# In _run_single_combination
def _run_single_combination(args):
    params_dict, df, trade_start_idx, strategy_id = args  # Pass ID, not class

    from strategies import get_strategy
    strategy_class = get_strategy(strategy_id)  # Load in worker

    result = strategy_class.run(df, params_dict, trade_start_idx)
    # ... rest of code
```

---

## Next Stage

Proceed to **migration_prompt_7.md** to update Walk-Forward Analysis engine and complete the migration.
