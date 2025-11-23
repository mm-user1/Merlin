# Migration Prompt 7: Update Walk-Forward Analysis Engine

## Objective

Update `walkforward_engine.py` to use the new modular strategy system. Replace all calls to `run_strategy()` with `strategy_class.run()` and adapt the WFA workflow to work with any strategy.

## Prerequisites

Complete **migration_prompt_6.md** before starting this stage.

## Background: Walk-Forward Analysis (WFA)

WFA is a time-series cross-validation technique:

1. **Split data into windows:** Each window has:
   - IS period (In-Sample, 80%): For optimization
   - OOS period (Out-of-Sample, 20%): For validation
   - Windows slide forward by 70% each time (30% overlap)

2. **Per window:**
   - Optimize parameters on IS period (Grid or Optuna)
   - Select top-K performers by IS score
   - Validate those K params on OOS period
   - Record OOS metrics

3. **Forward test:**
   - Use best params from all windows
   - Test on unseen Forward period (after all windows)

4. **Output:**
   - CSV with all window results
   - Optional: ZIP archive with trade history for top-K params

**Current Implementation:**
- `walkforward_engine.py` imports `run_strategy()` from `backtest_engine.py`
- Calls `run_strategy()` 5 times:
  - Lines 324, 367, 433: During WFA workflow
  - Lines 902, 920: During trade export
- Creates `StrategyParams` objects using `StrategyParams.from_dict()`

**After Migration:**
- `run_strategy()` will be removed from `backtest_engine.py`
- Need to use `strategy_class.run()` instead
- Need to pass `warmup_bars` explicitly instead of calculating from `StrategyParams`

---

## Tasks

### Task 7.1: Update Imports

**File:** `src/walkforward_engine.py`

**Find the import statement (line 16):**
```python
from backtest_engine import StrategyParams, run_strategy, TradeRecord
```

**Replace with:**
```python
from backtest_engine import TradeRecord, prepare_dataset_with_warmup
# Note: StrategyParams and run_strategy are removed
```

### Task 7.2: Add Strategy Support to WFConfig

**Find the `WFConfig` dataclass (around line 62):**
```python
@dataclass
class WFConfig:
    """Walk-forward analysis configuration."""

    optimization_config: OptimizationConfig
    top_k: int = 5
    # ... other fields ...
```

**Add new fields:**
```python
@dataclass
class WFConfig:
    """Walk-forward analysis configuration."""

    optimization_config: OptimizationConfig
    top_k: int = 5
    is_pct: float = 0.8
    wf_pct: float = 0.7
    forward_pct: float = 0.2
    optuna_config: Optional[OptunaConfig] = None

    # NEW: Add these fields
    strategy_id: str = "s01_trailing_ma"  # Strategy to use
    warmup_bars: int = 1000  # User-controlled warmup
```

### Task 7.3: Update WalkForwardEngine Class - Add Strategy Loading

**Find the `WalkForwardEngine.__init__()` method (around line 140):**

**Add strategy loading at the end of `__init__`:**
```python
class WalkForwardEngine:
    def __init__(self, config: WFConfig):
        self.config = config
        self.opt_config = config.optimization_config
        self.top_k = config.top_k
        self.is_pct = config.is_pct
        self.wf_pct = config.wf_pct
        self.forward_pct = config.forward_pct
        self.optuna_config = config.optuna_config

        # NEW: Load strategy
        from strategies import get_strategy
        try:
            self.strategy_class = get_strategy(config.strategy_id)
        except ValueError as e:
            raise ValueError(f"Failed to load strategy '{config.strategy_id}': {e}")
```

### Task 7.4: Update run_window() Method - Replace run_strategy Calls

**Find the `run_window()` method (around line 260).** This method contains 3 calls to `run_strategy()`:
1. IS period (line ~324)
2. OOS period (line ~367)
3. Forward period (line ~433)

**Key changes:**
1. Remove `StrategyParams.from_dict()` calls
2. Replace `run_strategy()` with `self.strategy_class.run()`
3. Update `prepare_dataset_with_warmup()` to use `warmup_bars` instead of `strategy_params`

**Find the IS period section (around line 309-324):**

**Current code:**
```python
for params in top_params:
    from backtest_engine import prepare_dataset_with_warmup

    # Create params object for warmup calculation
    strategy_params = StrategyParams.from_dict(params)

    # Prepare dataset with warmup for IS period
    is_df_prepared, trade_start_idx = prepare_dataset_with_warmup(
        df, is_start_time, is_end_time, strategy_params
    )

    # Run strategy with trade_start_idx
    strategy_params.use_date_filter = True
    result = run_strategy(is_df_prepared, strategy_params, trade_start_idx)
```

**Replace with:**
```python
for params in top_params:
    # Prepare dataset with warmup for IS period
    is_df_prepared, trade_start_idx = prepare_dataset_with_warmup(
        df, is_start_time, is_end_time, self.config.warmup_bars
    )

    # Prepare params dict with date filter enabled
    params_copy = params.copy()
    params_copy['dateFilter'] = True
    params_copy['start'] = is_start_time
    params_copy['end'] = is_end_time

    # Run strategy with trade_start_idx
    result = self.strategy_class.run(is_df_prepared, params_copy, trade_start_idx)
```

**Find the OOS period section (around line 351-367):**

**Current code:**
```python
for params in top_params:
    from backtest_engine import prepare_dataset_with_warmup

    # Create params object for warmup calculation
    strategy_params = StrategyParams.from_dict(params)

    # IMPORTANT: For OOS validation, we use prepare_dataset_with_warmup to:
    # 1. Add warmup period before oos_start for proper MA calculation
    # 2. Set trade_start_idx to oos_start, ensuring trades open only in OOS
    oos_df_prepared, trade_start_idx = prepare_dataset_with_warmup(
        df, oos_start_time, oos_end_time, strategy_params
    )

    # Run strategy with trade_start_idx
    strategy_params.use_date_filter = True
    result = run_strategy(oos_df_prepared, strategy_params, trade_start_idx)
```

**Replace with:**
```python
for params in top_params:
    # IMPORTANT: For OOS validation, we use prepare_dataset_with_warmup to:
    # 1. Add warmup period before oos_start for proper MA calculation
    # 2. Set trade_start_idx to oos_start, ensuring trades open only in OOS
    oos_df_prepared, trade_start_idx = prepare_dataset_with_warmup(
        df, oos_start_time, oos_end_time, self.config.warmup_bars
    )

    # Prepare params dict with date filter enabled
    params_copy = params.copy()
    params_copy['dateFilter'] = True
    params_copy['start'] = oos_start_time
    params_copy['end'] = oos_end_time

    # Run strategy with trade_start_idx
    result = self.strategy_class.run(oos_df_prepared, params_copy, trade_start_idx)
```

**Find the Forward period section (around line 408-433):**

**Current code:**
```python
from backtest_engine import prepare_dataset_with_warmup

forward_start_time = df.index[fwd_start]
forward_end_time = df.index[fwd_end - 1]
print(f"Forward test period: {forward_start_time.date()} to {forward_end_time.date()}")

for agg in aggregated:
    params = agg.params
    strategy_params = StrategyParams.from_dict(params)

    # Use prepare_dataset_with_warmup for forward test
    # This adds warmup period before forward_start to properly warm up MAs
    forward_df_prepared, trade_start_idx = prepare_dataset_with_warmup(
        df, forward_start_time, forward_end_time, strategy_params
    )

    if not forward_df_prepared.empty:
        # Run strategy with trade_start_idx
        strategy_params.use_date_filter = True
        result = run_strategy(forward_df_prepared, strategy_params, trade_start_idx)
```

**Replace with:**
```python
forward_start_time = df.index[fwd_start]
forward_end_time = df.index[fwd_end - 1]
print(f"Forward test period: {forward_start_time.date()} to {forward_end_time.date()}")

for agg in aggregated:
    params = agg.params

    # Use prepare_dataset_with_warmup for forward test
    # This adds warmup period before forward_start to properly warm up MAs
    forward_df_prepared, trade_start_idx = prepare_dataset_with_warmup(
        df, forward_start_time, forward_end_time, self.config.warmup_bars
    )

    if not forward_df_prepared.empty:
        # Prepare params dict with date filter enabled
        params_copy = params.copy()
        params_copy['dateFilter'] = True
        params_copy['start'] = forward_start_time
        params_copy['end'] = forward_end_time

        # Run strategy with trade_start_idx
        result = self.strategy_class.run(forward_df_prepared, params_copy, trade_start_idx)
```

### Task 7.5: Update export_wfa_trades_history() Function

**Find the `export_wfa_trades_history()` function (around line 848).**

This function exports trade history for top-K params. It contains 2 calls to `run_strategy()`:
- Line ~902: IS period
- Line ~920: OOS period

**Find the function signature and update imports inside:**

**Current code (around line 876):**
```python
from backtest_engine import StrategyParams, run_strategy, prepare_dataset_with_warmup
```

**Replace with:**
```python
from backtest_engine import prepare_dataset_with_warmup
from strategies import get_strategy
```

**Add strategy loading at the beginning of the function (after imports):**
```python
def export_wfa_trades_history(
    wf_result: WFResult,
    df: pd.DataFrame,
    csv_filename: str,
    top_k: int = 10,
    output_dir: str = "./wfa_trades",
) -> List[str]:
    """
    Export detailed trade history for top K parameter sets from WFA.

    ... docstring ...
    """
    from pathlib import Path
    from backtest_engine import prepare_dataset_with_warmup
    from strategies import get_strategy

    # NEW: Load strategy (get from WFResult if available, else default to S01)
    strategy_id = getattr(wf_result, 'strategy_id', 's01_trailing_ma')
    try:
        strategy_class = get_strategy(strategy_id)
    except ValueError as e:
        raise ValueError(f"Failed to load strategy '{strategy_id}': {e}")

    # Get warmup_bars (from WFResult if available, else default)
    warmup_bars = getattr(wf_result, 'warmup_bars', 1000)

    # ... rest of existing code ...
```

**Find the IS period run (around line 892-902):**

**Current code:**
```python
# Exact WFA replication: prepare_dataset_with_warmup + run_strategy
is_df_prepared, trade_start_idx = prepare_dataset_with_warmup(
    df, is_start_time, is_end_time, params
)

params.use_date_filter = True
is_result = run_strategy(is_df_prepared, params, trade_start_idx)
```

**Replace with:**
```python
# Exact WFA replication: prepare_dataset_with_warmup + strategy.run()
is_df_prepared, trade_start_idx = prepare_dataset_with_warmup(
    df, is_start_time, is_end_time, warmup_bars
)

# Prepare params dict
params_dict = agg.params.copy()
params_dict['dateFilter'] = True
params_dict['start'] = is_start_time
params_dict['end'] = is_end_time

is_result = strategy_class.run(is_df_prepared, params_dict, trade_start_idx)
```

**Find the OOS period run (around line 915-920):**

**Current code:**
```python
oos_df_prepared, trade_start_idx = prepare_dataset_with_warmup(
    df, oos_start_time, oos_end_time, params
)

params.use_date_filter = True
oos_result = run_strategy(oos_df_prepared, params, trade_start_idx)
```

**Replace with:**
```python
oos_df_prepared, trade_start_idx = prepare_dataset_with_warmup(
    df, oos_start_time, oos_end_time, warmup_bars
)

# Prepare params dict
params_dict = agg.params.copy()
params_dict['dateFilter'] = True
params_dict['start'] = oos_start_time
params_dict['end'] = oos_end_time

oos_result = strategy_class.run(oos_df_prepared, params_dict, trade_start_idx)
```

### Task 7.6: Update WFResult to Store Strategy Info

**Find the `WFResult` dataclass (around line 118):**

**Add new fields:**
```python
@dataclass
class WFResult:
    """Complete walk-forward analysis result."""

    windows: List[WindowResult]
    aggregated: List[AggregatedResult]
    forward_profit_pct: Optional[float] = None
    forward_max_dd_pct: Optional[float] = None
    forward_trades: int = 0
    total_runtime_seconds: float = 0.0

    # NEW: Add strategy metadata
    strategy_id: str = "s01_trailing_ma"
    warmup_bars: int = 1000
```

**Find where `WFResult` is created (in `WalkForwardEngine.run()` method, around line 450):**

**Update the creation:**
```python
return WFResult(
    windows=window_results,
    aggregated=aggregated,
    forward_profit_pct=forward_profit,
    forward_max_dd_pct=forward_dd,
    forward_trades=forward_trades,
    total_runtime_seconds=total_runtime,

    # NEW: Add strategy metadata
    strategy_id=self.config.strategy_id,
    warmup_bars=self.config.warmup_bars,
)
```

### Task 7.7: Update Server Endpoint

**File:** `src/server.py`

**Find the `/api/walkforward` endpoint (search for `@app.post("/api/walkforward")`):**

**Update to extract strategy info:**
```python
@app.post("/api/walkforward")
def run_walkforward_optimization() -> object:
    """Run Walk-Forward Analysis with selected strategy."""

    # Get strategy ID and warmup bars
    strategy_id = request.form.get("strategy", "s01_trailing_ma")
    warmup_bars_raw = request.form.get("warmupBars", "1000")
    try:
        warmup_bars = int(warmup_bars_raw)
        warmup_bars = max(100, min(5000, warmup_bars))
    except (TypeError, ValueError):
        warmup_bars = 1000

    # ... existing code to parse request ...

    # Build optimization config (same as /api/optimize)
    optimization_config = _build_optimization_config(
        data_source,
        config_payload,
        worker_processes,
        strategy_id,      # NEW
        warmup_bars       # NEW
    )

    # ... existing code to get top_k, optuna settings, etc. ...

    # Create WFConfig
    from walkforward_engine import WFConfig

    wf_config = WFConfig(
        optimization_config=optimization_config,
        top_k=top_k,
        is_pct=is_pct,
        wf_pct=wf_pct,
        forward_pct=forward_pct,
        optuna_config=optuna_config,  # Can be None

        # NEW: Add strategy info
        strategy_id=strategy_id,
        warmup_bars=warmup_bars,
    )

    # ... rest of existing code (unchanged) ...
```

### Task 7.8: Update JavaScript (Already Done?)

**Check if JavaScript for WFA already sends strategy_id and warmup_bars.**

**If not, find the WFA submit function and add:**
```javascript
async function submitWalkForward() {
    const formData = new FormData();

    // Add strategy ID
    formData.append('strategy', currentStrategyId);

    // Add warmup bars
    const warmupBars = document.getElementById('warmupBars').value;
    formData.append('warmupBars', warmupBars);

    // ... rest of existing code ...
}
```

---

## Testing

### Test 7.1: Basic WFA (Single Window)

**Prerequisites:** Stages 1-6 completed and tested.

**Steps:**
1. Start server: `cd src && python server.py`
2. Open browser: `http://localhost:8000`
3. Select strategy: "S01 Trailing MA v26"
4. Load CSV: `data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
5. Set warmup bars: 1000
6. Configure WFA:
   - IS%: 80
   - WF%: 70
   - Forward%: 20
   - Top K: 3
   - Optimization Method: Grid Search
   - Enable 1-2 parameters (e.g., MA Length: 200-400 step 100)
7. Click "Run Walk-Forward"

**Expected Results:**
- WFA starts without errors
- Progress logs show:
  ```
  Window 1/N: [date1] to [date2]
  Optimizing IS period...
  Top 3 params selected
  Validating on OOS...
  ```
- CSV downloads with structure:
  ```
  # WINDOW 1
  # IS: 2025-06-01 to 2025-09-15
  # OOS: 2025-09-16 to 2025-10-15
  rank,ma_length,is_profit%,is_dd%,oos_profit%,oos_dd%,...
  1,300,25.5,12.3,18.2,15.1,...
  ...

  # AGGREGATE RESULTS
  rank,ma_length,avg_is_profit,avg_oos_profit,consistency,...
  ...

  # FORWARD TEST
  ma_length,forward_profit%,forward_dd%,...
  ```

**Validate:**
- All windows completed
- OOS metrics are present and non-zero
- Forward test ran successfully
- No Python exceptions in server log

### Test 7.2: WFA with Trade Export

**Steps:**
1. Same setup as Test 7.1
2. Enable "Export Trades" checkbox
3. Set "Top: 5" (or less than total combinations)
4. Run WFA

**Expected Results:**
- WFA completes successfully
- ZIP file downloads containing:
  ```
  wfa_trades_SYMBOL_TIMESTAMP/
    wfa_trades_rank_1_maLength_300.csv
    wfa_trades_rank_2_maLength_350.csv
    ...
  ```
- Each CSV file contains:
  ```
  # Parameters: maLength=300, closeCountLong=9, ...
  # Strategy: S01 Trailing MA v26

  # === WINDOW 1: IS Period ===
  # IS: 2025-06-01 to 2025-09-15
  entry_time,exit_time,side,entry_price,exit_price,pnl%,...
  2025-06-05 10:00,2025-06-07 14:30,LONG,1.234,1.245,0.89,...
  ...

  # === WINDOW 1: OOS Period ===
  # OOS: 2025-09-16 to 2025-10-15
  entry_time,exit_time,side,...
  ...
  ```

**Validate:**
- ZIP contains correct number of files (top_k)
- Each file has trades from all windows (IS + OOS)
- Trade timestamps match window periods
- No duplicate trades

### Test 7.3: WFA with Optuna

**Steps:**
1. Same setup as Test 7.1
2. Configure WFA:
   - Optimization Method: Optuna
   - Target: Composite Score
   - Budget: 50 trials
   - Enable 2-3 parameters with wide ranges
3. Run WFA

**Expected Results:**
- Each window runs Optuna optimization (50 trials per window)
- Progress shows:
  ```
  Window 1/N: Optuna optimization
  Trial 1/50 | Best: 45.2
  Trial 2/50 | Best: 47.8
  ...
  Trial 50/50 | Best: 52.3
  Top 3 params selected by IS score
  ```
- Results CSV shows top-K params selected by Optuna
- OOS validation runs on those top-K
- Forward test uses best overall params

**Performance:**
- Optuna WFA is much slower than Grid (50 trials × N windows)
- Should still complete without errors

### Test 7.4: Multi-File WFA

**Steps:**
1. Select 2-3 CSV files (different symbols)
2. Run WFA with Grid search
3. Enable trade export

**Expected Results:**
- Results CSV contains sections for each file:
  ```
  # FILE: BTCUSDT.csv
  # WINDOW 1
  ...
  # AGGREGATE RESULTS
  ...
  # FORWARD TEST
  ...

  # FILE: ETHUSDT.csv
  # WINDOW 1
  ...
  ```
- ZIP file contains subdirectories:
  ```
  wfa_trades_BTCUSDT_TIMESTAMP/
    wfa_trades_rank_1_...csv
  wfa_trades_ETHUSDT_TIMESTAMP/
    wfa_trades_rank_1_...csv
  ```

### Test 7.5: WFA Edge Cases

**Test 7.5.1: Small dataset (insufficient data for windows)**
- Use CSV with only 30 days of data
- Expected: Error message "Insufficient data for walk-forward analysis"

**Test 7.5.2: Top-K larger than combinations**
- Enable only 1 parameter with 3 values (3 combos)
- Set Top-K = 10
- Expected: WFA uses all 3 combos (not fail)

**Test 7.5.3: Forward period has no data**
- Set Forward% = 0
- Expected: WFA completes, but forward_profit_pct = None in results

---

## Final End-to-End Test (Reference Test)

**This is the comprehensive test from migration_prompt_5.md, now including WFA:**

### E2E Test 1: Full Backtest

**CSV:** `data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
**Strategy:** S01 Trailing MA v26
**Date Range:** 2025-06-15 to 2025-11-15
**Warmup Bars:** 1000

**Parameters:**
- MA Type: SMA
- MA Length: 300
- Close Count Long: 9
- Close Count Short: 5
- Stop Long ATR: 2.0, RR: 3, LP: 2
- Stop Short ATR: 2.0, RR: 3, LP: 2
- Stop Long Max %: 7.0
- Stop Short Max %: 10.0
- Stop Long Max Days: 5
- Stop Short Max Days: 2
- Trail RR Long: 1
- Trail RR Short: 1
- Trail MA Long: EMA, Length: 90, Offset: -0.5
- Trail MA Short: EMA, Length: 190, Offset: 2.0

**Expected Results:**
```
Net Profit: 230.75%
Max Drawdown: 20.03%
Total Trades: 93
```

**Tolerance:** ±0.5% on profit/DD, ±2 trades

### E2E Test 2: Grid Optimization

Same CSV and date range, optimize:
- MA Length: 200 to 400, step 100 (3 values)
- Close Count Long: 5 to 9, step 2 (3 values)
- Total: 9 combinations

**Expected:**
- 9 rows in CSV
- Best combo should have score > 50
- All combos have valid metrics

### E2E Test 3: Optuna Optimization

Same CSV and date range, optimize with Optuna:
- 50 trials
- 3-4 parameters enabled

**Expected:**
- 50 trials complete
- Best trial has higher score than random trials
- CSV has 50 rows

### E2E Test 4: Walk-Forward Analysis

Same CSV, WFA configuration:
- IS: 80%, WF: 70%, Forward: 20%
- Top-K: 5
- Grid search with 2 parameters (9-25 combos)

**Expected:**
- 2-3 windows generated (depends on data)
- Each window: IS optimization → OOS validation
- Forward test on final period
- CSV with window results + aggregated + forward

### E2E Test 5: WFA with Trade Export

Same as E2E Test 4, but enable trade export (Top 3).

**Expected:**
- ZIP file with 3 CSV files
- Each file has trades from all windows (IS + OOS)
- Trade count matches reported metrics

**If all E2E tests pass → Migration is complete! ✅**

---

## Completion Checklist

- [ ] Imports updated (removed `StrategyParams`, `run_strategy`)
- [ ] `WFConfig` updated with `strategy_id` and `warmup_bars` fields
- [ ] `WalkForwardEngine.__init__()` loads strategy
- [ ] `run_window()` method: IS period updated (3 changes)
- [ ] `run_window()` method: OOS period updated (3 changes)
- [ ] `run_window()` method: Forward period updated (3 changes)
- [ ] `export_wfa_trades_history()` function updated (2 changes)
- [ ] `WFResult` dataclass updated with strategy metadata
- [ ] `WFResult` creation updated to pass metadata
- [ ] `/api/walkforward` endpoint updated
- [ ] JavaScript updated (if needed)
- [ ] Test 7.1 passed (Basic WFA)
- [ ] Test 7.2 passed (WFA with trade export)
- [ ] Test 7.3 passed (WFA with Optuna)
- [ ] Test 7.4 passed (Multi-file WFA)
- [ ] Test 7.5 passed (Edge cases)
- [ ] E2E Test 1 passed (Full backtest)
- [ ] E2E Test 2 passed (Grid optimization)
- [ ] E2E Test 3 passed (Optuna optimization)
- [ ] E2E Test 4 passed (WFA)
- [ ] E2E Test 5 passed (WFA with trade export)
- [ ] Git commit: "Migration Stage 7: Update Walk-Forward Analysis for modular strategies"

---

## Common Issues & Troubleshooting

### Issue 1: "StrategyParams not found"

**Cause:** Forgot to remove `StrategyParams.from_dict()` call.

**Fix:** Search for all occurrences of `StrategyParams` in `walkforward_engine.py`:
```bash
grep -n "StrategyParams" src/walkforward_engine.py
```
Should return 0 results (except in comments).

### Issue 2: "prepare_dataset_with_warmup() takes 3 arguments, 4 given"

**Cause:** Old signature expected `StrategyParams`, new signature expects `warmup_bars`.

**Fix:** Verify `backtest_engine.py` has updated signature:
```python
def prepare_dataset_with_warmup(
    df: pd.DataFrame,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
    warmup_bars: int  # Changed from StrategyParams
) -> Tuple[pd.DataFrame, int]:
```

### Issue 3: WFA completes but OOS profits are all zero

**Cause:** `params_copy` not properly setting `dateFilter` and date range.

**Debug:**
1. Add print statement before `strategy_class.run()`:
   ```python
   print(f"Running strategy with params: {params_copy}")
   ```
2. Verify output shows:
   ```
   {'dateFilter': True, 'start': Timestamp(...), 'end': Timestamp(...), ...}
   ```

**Fix:** Ensure `params_copy` includes all required fields.

### Issue 4: Trade export missing trades

**Cause:** Window index calculation incorrect.

**Debug:**
1. Check window splits in `_split_windows()` method
2. Verify `window.is_start`, `window.is_end`, `window.oos_start`, `window.oos_end` are correct
3. Add logging:
   ```python
   print(f"IS period: {is_start_time} to {is_end_time}")
   print(f"IS trades: {len(is_trades)}")
   ```

**Fix:** Ensure trade filtering by `entry_time` matches window boundaries.

### Issue 5: ZIP file empty or corrupt

**Cause:** File path issues in `export_wfa_trades_history()`.

**Debug:**
1. Check `output_dir` exists
2. Verify CSV files created before ZIP
3. Add logging:
   ```python
   print(f"Created trade file: {trade_file}")
   ```

**Fix:** Ensure `Path(output_dir).mkdir(parents=True, exist_ok=True)` is called.

---

## Performance Considerations

**WFA Performance without Caching:**

- **Original (cached):** ~5-10 minutes for typical WFA (3 windows, 100 combos each)
- **MVP (no cache):** ~15-30 minutes (3× slower)

**Why acceptable:**
- WFA is typically run overnight or during extended sessions
- Correctness > speed for MVP
- Users can reduce search space (fewer parameters, larger steps)

**Future optimization:**
- Re-implement caching at strategy level
- Use distributed processing (multiple machines)
- Implement incremental WFA (resume from checkpoint)

**For now:** Document expected runtime in UI ("Estimated time: 20-30 min for 300 combos")

---

## Migration Complete! 🎉

If all tests pass, the migration is complete. The system now supports:

✅ **Modular strategies:** Easy to add new strategies
✅ **Dynamic UI:** Forms generated from strategy configs
✅ **All optimizers work:** Grid, Optuna, WFA
✅ **All features work:** Backtest, optimization, trade export
✅ **Backward compatible:** S01 produces identical results
✅ **Extensible:** Future strategies can be added without modifying core

**Next Steps:**
1. Create documentation for adding new strategies (see ARCHITECTURE.md)
2. Add preset management for new strategies
3. (Optional) Re-implement caching for performance
4. (Future) Add Pine Script → Python translation agent

**Congratulations on completing the migration!**
