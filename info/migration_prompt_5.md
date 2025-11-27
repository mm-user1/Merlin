# Migration Prompt 5: API Integration & Final Testing

## Objective

Complete the migration by integrating the new strategy system with all API endpoints (backtest, optimize, walkforward) and perform comprehensive end-to-end testing.

## Prerequisites

Complete **migration_prompt_4.md** before starting this stage.

## Tasks

### Task 5.1: Update /api/backtest Endpoint

Modify the `/api/backtest` endpoint in `src/server.py` to use the strategy system:

**Find the endpoint (around line 923):**
```python
@app.post("/api/backtest")
def run_backtest() -> object:
```

**Update it to:**
```python
@app.post("/api/backtest")
def run_backtest() -> object:
    """Run single backtest with selected strategy"""

    # Get strategy ID from form (default to S01)
    strategy_id = request.form.get("strategy", "s01_trailing_ma")

    # Get warmup bars
    warmup_bars_raw = request.form.get("warmupBars", "1000")
    try:
        warmup_bars = int(warmup_bars_raw)
        warmup_bars = max(100, min(5000, warmup_bars))
    except (TypeError, ValueError):
        warmup_bars = 1000

    # Load CSV data (existing code)
    csv_file = request.files.get("file")
    csv_path_raw = (request.form.get("csvPath") or "").strip()
    # ... (keep existing CSV loading logic)

    # Parse payload
    payload_raw = request.form.get("payload", "{}")
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        return ("Invalid payload JSON.", HTTPStatus.BAD_REQUEST)

    # Load strategy
    from strategies import get_strategy
    try:
        strategy_class = get_strategy(strategy_id)
    except ValueError as e:
        return (str(e), HTTPStatus.BAD_REQUEST)

    # Load data
    try:
        df = load_data(data_source)
    except ValueError as exc:
        if opened_file:
            opened_file.close()
        return (str(exc), HTTPStatus.BAD_REQUEST)

    # Prepare dataset with warmup
    trade_start_idx = 0
    use_date_filter = payload.get('dateFilter', False)
    start = payload.get('start')
    end = payload.get('end')

    if use_date_filter and (start is not None or end is not None):
        # Parse dates
        if isinstance(start, str):
            start = pd.Timestamp(start, tz='UTC')
        if isinstance(end, str):
            end = pd.Timestamp(end, tz='UTC')

        # Apply warmup
        try:
            df, trade_start_idx = prepare_dataset_with_warmup(
                df, start, end, warmup_bars
            )
        except Exception as exc:
            if opened_file:
                opened_file.close()
            app.logger.exception("Failed to prepare dataset with warmup")
            return ("Failed to prepare dataset.", HTTPStatus.INTERNAL_SERVER_ERROR)

    # Run strategy
    try:
        result = strategy_class.run(df, payload, trade_start_idx)
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:
        app.logger.exception("Backtest execution failed")
        return ("Backtest execution failed.", HTTPStatus.INTERNAL_SERVER_ERROR)

    return jsonify({
        "metrics": result.to_dict(),
        "parameters": payload,
    })
```

### Task 5.2: Note on Optimization Engines

**IMPORTANT:** `/api/optimize` and `/api/walkforward` endpoints will be updated in **migration_prompt_6.md** and **migration_prompt_7.md** respectively.

At this stage (Stage 5), we are **only** updating the `/api/backtest` endpoint. The optimization engines (`optimizer_engine.py`, `optuna_engine.py`) and WFA engine (`walkforward_engine.py`) contain hardcoded S01 logic that requires extensive refactoring.

**What works after Stage 5:**
- ✅ Single backtest via UI
- ✅ Strategy selector
- ✅ Dynamic forms
- ✅ Warmup bars input
- ❌ Grid optimization (broken - will fix in Stage 6)
- ❌ Optuna optimization (broken - will fix in Stage 6)
- ❌ Walk-Forward Analysis (broken - will fix in Stage 7)

**Next steps:**
- Stage 6: Update Grid and Optuna optimizers
- Stage 7: Update WFA engine

### Task 5.3: Update UI JavaScript (Backtest Function)

Update the existing `runBacktest()` function in `index.html` to include strategy ID and warmup bars:

```javascript
async function runBacktest() {
    const formData = new FormData();

    // Add strategy ID
    formData.append('strategy', currentStrategyId);

    // Add warmup bars
    const warmupBars = document.getElementById('warmupBars').value;
    formData.append('warmupBars', warmupBars);

    // Collect all backtest parameters
    const backtestContainer = document.getElementById('backtestParamsContent');
    const inputs = backtestContainer.querySelectorAll('input, select');

    const params = {};
    inputs.forEach(input => {
        if (input.type === 'checkbox') {
            params[input.name] = input.checked;
        } else if (input.type === 'number') {
            params[input.name] = parseFloat(input.value);
        } else {
            params[input.name] = input.value;
        }
    });

    // Add date filter
    params.dateFilter = document.getElementById('dateFilter').checked;
    if (params.dateFilter) {
        params.start = document.getElementById('startDate').value + ' ' +
                      document.getElementById('startTime').value;
        params.end = document.getElementById('endDate').value + ' ' +
                    document.getElementById('endTime').value;
    }

    formData.append('payload', JSON.stringify(params));

    // Add CSV file
    const csvFile = document.getElementById('csvFile').files[0];
    if (csvFile) {
        formData.append('file', csvFile);
    }

    try {
        const response = await fetch('/api/backtest', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        displayBacktestResults(data);
    } catch (error) {
        console.error('Backtest error:', error);
        alert('Error running backtest');
    }
}

async function runOptimization() {
    const formData = new FormData();

    // Add strategy ID
    formData.append('strategy', currentStrategyId);

    // Add warmup bars
    const warmupBars = document.getElementById('warmupBars').value;
    formData.append('warmupBars', warmupBars);

    // Collect enabled parameters and ranges
    const enabledParams = {};
    const paramRanges = {};
    const fixedParams = {};

    const optimizerContainer = document.getElementById('optimizerParamsContent');
    const checkboxes = optimizerContainer.querySelectorAll('[id^="opt_"]');

    checkboxes.forEach(checkbox => {
        const paramName = checkbox.id.replace('opt_', '');
        const isEnabled = checkbox.checked;

        enabledParams[paramName] = isEnabled;

        if (isEnabled) {
            // Get ranges
            const minInput = document.getElementById(`${paramName}_min`);
            const maxInput = document.getElementById(`${paramName}_max`);
            const stepInput = document.getElementById(`${paramName}_step`);

            if (minInput && maxInput && stepInput) {
                paramRanges[paramName] = [
                    parseFloat(minInput.value),
                    parseFloat(maxInput.value),
                    parseFloat(stepInput.value)
                ];
            }
        } else {
            // Use default value from backtest form
            const backtestInput = document.querySelector(`[name="${paramName}"]`);
            if (backtestInput) {
                fixedParams[paramName] = backtestInput.value;
            }
        }
    });

    // Add date filter to fixed params
    fixedParams.dateFilter = document.getElementById('dateFilter').checked;
    if (fixedParams.dateFilter) {
        fixedParams.start = document.getElementById('startDate').value + ' ' +
                           document.getElementById('startTime').value;
        fixedParams.end = document.getElementById('endDate').value + ' ' +
                         document.getElementById('endTime').value;
    }

    const config = {
        enabled_params: enabledParams,
        param_ranges: paramRanges,
        fixed_params: fixedParams
    };

    formData.append('config', JSON.stringify(config));

    // Add CSV
    const csvFile = document.getElementById('csvFile').files[0];
    if (csvFile) {
        formData.append('file', csvFile);
    }

    try {
        const response = await fetch('/api/optimize', {
            method: 'POST',
            body: formData
        });

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'optimization_results.csv';
        a.click();
    } catch (error) {
        console.error('Optimization error:', error);
        alert('Error running optimization');
    }
}
```

## Testing

### Test 5.1: Reference Test (Complete E2E)

**CRITICAL:** This is the definitive test to verify the migration is successful.

1. Start the server:
```bash
cd src
python server.py
```

2. Open browser: `http://localhost:8000`

3. Configure backtest:
   - **Strategy:** S01 Trailing MA v26
   - **CSV File:** Upload `data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
   - **Date Range:**
     - Start: 2025-06-15 00:00
     - End: 2025-11-15 00:00
   - **Warmup Bars:** 1000
   - **Parameters:**
     - MA Type: SMA
     - MA Length: 300
     - Close Count Long: 9
     - Close Count Short: 5
     - Stop Long ATR: 2.0
     - Stop Long RR: 3
     - Stop Long LP: 2
     - Stop Short ATR: 2.0
     - Stop Short RR: 3
     - Stop Short LP: 2
     - Stop Long Max %: 7.0
     - Stop Short Max %: 10.0
     - Stop Long Max Days: 5
     - Stop Short Max Days: 2
     - Trail RR Long: 1
     - Trail RR Short: 1
     - Trail MA Long Type: EMA
     - Trail MA Long Length: 90
     - Trail MA Long Offset: -0.5
     - Trail MA Short Type: EMA
     - Trail MA Short Length: 190
     - Trail MA Short Offset: 2.0

4. Click "Run Backtest"

5. **Verify results:**
```
Expected:
├─ Net Profit:        230.75% (±0.5% tolerance)
├─ Max Drawdown:      20.03% (±0.5% tolerance)
├─ Total Trades:      93 (±2 tolerance)
```

**If results match:** ✅ Migration successful!

**If results differ:** ❌ Debug:
- Check strategy logic wasn't modified
- Verify parameter mapping
- Check warmup calculation
- Compare with old version

### Test 5.2: Optimization Test

1. Configure optimization:
   - Same CSV and dates as above
   - Enable optimization for 2-3 parameters (e.g., MA Length, Close Count Long)
   - Set small ranges (e.g., MA Length: 200-350 step 50)
   - Use Grid search mode

2. Run optimization

3. Verify:
   - CSV downloads successfully
   - Results table has expected combinations
   - No errors in console

### Test 5.3: Walk-Forward Test

1. Configure WFA:
   - Same CSV
   - Optuna mode
   - 3 windows
   - 100 trials per window
   - Top-K: 10

2. Run WFA

3. Verify:
   - WFA completes without errors
   - Results CSV downloads
   - Top 10 parameter sets are shown

### Test 5.4: Multi-Strategy Test (Future Proof)

To verify the system works for future strategies:

1. Create a dummy second strategy:
```bash
mkdir src/strategies/s02_test
```

2. Create minimal `config.json`:
```json
{
  "id": "s02_test",
  "name": "S02 Test Strategy",
  "version": "v1",
  "description": "Test strategy",
  "parameters": {
    "testParam": {
      "type": "int",
      "label": "Test Parameter",
      "default": 10,
      "min": 1,
      "max": 100
    }
  }
}
```

3. Create minimal `strategy.py`:
```python
from strategies.base import BaseStrategy
from backtest_engine import StrategyResult

class S02Test(BaseStrategy):
    STRATEGY_ID = "s02_test"
    STRATEGY_NAME = "S02 Test"
    STRATEGY_VERSION = "v1"

    @staticmethod
    def run(df, params, trade_start_idx=0):
        # Dummy strategy - always returns zero
        return StrategyResult(
            net_profit_pct=0.0,
            max_drawdown_pct=0.0,
            total_trades=0,
            trades=[]
        )
```

4. Refresh browser

5. Verify:
   - Strategy dropdown now shows both S01 and S02
   - Selecting S02 shows its parameters
   - Can switch between strategies

## Completion Checklist

- [ ] `/api/backtest` updated to use strategy system
- [ ] UI JavaScript `runBacktest()` updated to send strategy ID and warmup bars
- [ ] Reference test passes (230.75% profit, 20.03% DD, 93 trades)
- [ ] Multi-strategy backtest test passes
- [ ] No console errors in browser
- [ ] No Python errors in server logs
- [ ] Git commit: "Migration Stage 5: Integrate backtest endpoint with strategy system"

## Stage 5 Success Criteria

This stage is complete when:
- ✅ Strategy selector works
- ✅ Forms generate dynamically
- ✅ Single backtest produces correct results
- ✅ Reference test passes with ±0.5% tolerance
- ✅ Multiple strategies can be tested via backtest
- ❌ Optimization NOT working yet (will fix in Stage 6)
- ❌ WFA NOT working yet (will fix in Stage 7)

## Next Stage

**Proceed to migration_prompt_6.md** to update Grid and Optuna optimization engines.
