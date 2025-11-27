# Migration Prompt 3: Update Server with Strategy Endpoints

## Objective

Add new API endpoints to server.py for strategy management while maintaining backward compatibility with existing functionality.

## Prerequisites

Complete **migration_prompt_2.md** before starting this stage.

## Context

The server currently handles backtesting and optimization with hardcoded S01 strategy. We need to add endpoints that allow the UI to discover strategies and load their configurations dynamically.

## Tasks

### Task 3.1: Add Strategy Management Endpoints

Add the following endpoints to `src/server.py` (append at the end, before `if __name__ == "__main__":`):

```python
# ============================================
# STRATEGY MANAGEMENT ENDPOINTS
# ============================================

@app.get("/api/strategies")
def list_strategies_endpoint() -> object:
    """
    List all available strategies.

    Returns:
        JSON: {
            "strategies": [
                {
                    "id": "s01_trailing_ma",
                    "name": "S01 Trailing MA",
                    "version": "v26",
                    "description": "...",
                    "author": "..."
                }
            ]
        }
    """
    from strategies import list_strategies
    strategies = list_strategies()
    return jsonify({"strategies": strategies})


@app.get("/api/strategies/<string:strategy_id>/config")
def get_strategy_config_endpoint(strategy_id: str) -> object:
    """
    Get strategy configuration (from config.json).

    Args:
        strategy_id: Strategy identifier (e.g., 's01_trailing_ma')

    Returns:
        JSON: Full config.json content including parameters

    Errors:
        404: Strategy not found
    """
    from strategies import get_strategy_config

    try:
        config = get_strategy_config(strategy_id)
        return jsonify(config)
    except ValueError as e:
        return (str(e), HTTPStatus.NOT_FOUND)


@app.get("/api/strategies/<string:strategy_id>")
def get_strategy_metadata_endpoint(strategy_id: str) -> object:
    """
    Get strategy metadata (lightweight version without full parameters).

    Args:
        strategy_id: Strategy identifier

    Returns:
        JSON: {
            "id": "s01_trailing_ma",
            "name": "S01 Trailing MA",
            "version": "v26",
            "description": "...",
            "parameter_count": 25
        }

    Errors:
        404: Strategy not found
    """
    from strategies import get_strategy_config

    try:
        config = get_strategy_config(strategy_id)
        return jsonify({
            "id": config.get('id'),
            "name": config.get('name'),
            "version": config.get('version'),
            "description": config.get('description'),
            "author": config.get('author', ''),
            "parameter_count": len(config.get('parameters', {}))
        })
    except ValueError as e:
        return (str(e), HTTPStatus.NOT_FOUND)
```

### Task 3.2: Update prepare_dataset_with_warmup Function

Modify the `prepare_dataset_with_warmup()` function in `backtest_engine.py` to accept warmup_bars as a parameter instead of calculating it from params:

**Find this function (around line 340):**
```python
def prepare_dataset_with_warmup(
    df: pd.DataFrame,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
    params: StrategyParams
) -> Tuple[pd.DataFrame, int]:
```

**Replace the signature with:**
```python
def prepare_dataset_with_warmup(
    df: pd.DataFrame,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
    warmup_bars: int = 1000
) -> Tuple[pd.DataFrame, int]:
    """
    Prepare dataset with warmup period for indicator calculation.

    Args:
        df: Full OHLCV DataFrame
        start: Trading start date (optional)
        end: Trading end date (optional)
        warmup_bars: Number of bars before start for indicator warmup

    Returns:
        Tuple of (filtered_df, trade_start_idx)
    """
```

**Update the warmup calculation inside the function:**

Replace the dynamic calculation:
```python
# OLD CODE (remove this):
max_ma_length = max(
    params.ma_length,
    params.trail_ma_long_length,
    params.trail_ma_short_length
)
warmup_bars = max(500, int(max_ma_length * 1.5))
```

With the simple parameter:
```python
# NEW CODE:
# warmup_bars is now passed as parameter
# Default is 1000 bars
```

### Task 3.3: Add Backward Compatibility Wrapper

Add this wrapper function to `backtest_engine.py` (append at the end):

```python
# ============================================
# BACKWARD COMPATIBILITY
# ============================================

def prepare_dataset_with_warmup_legacy(
    df: pd.DataFrame,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
    params: StrategyParams
) -> Tuple[pd.DataFrame, int]:
    """
    Legacy wrapper for prepare_dataset_with_warmup.
    Automatically calculates warmup_bars from params.

    This function maintains backward compatibility with existing code
    that passes StrategyParams instead of warmup_bars.
    """
    max_ma_length = max(
        params.ma_length,
        params.trail_ma_long_length,
        params.trail_ma_short_length
    )
    warmup_bars = max(500, int(max_ma_length * 1.5))

    return prepare_dataset_with_warmup(df, start, end, warmup_bars)
```

### Task 3.4: Update Existing Endpoints (Minimal Changes)

**IMPORTANT:** Do NOT modify the core logic of `/api/backtest`, `/api/optimize`, or `/api/walkforward` yet. Only add warmup_bars parameter handling.

In `/api/backtest` endpoint, locate the call to `prepare_dataset_with_warmup`:

**Find (around line 987):**
```python
df, trade_start_idx = prepare_dataset_with_warmup(df, params.start, params.end, params)
```

**Replace with:**
```python
# Get warmup_bars from form (default 1000)
warmup_bars_raw = request.form.get("warmupBars", "1000")
try:
    warmup_bars = int(warmup_bars_raw)
    warmup_bars = max(100, min(5000, warmup_bars))  # Clamp to reasonable range
except (TypeError, ValueError):
    warmup_bars = 1000

df, trade_start_idx = prepare_dataset_with_warmup(df, params.start, params.end, warmup_bars)
```

**Do the same for `/api/optimize` and `/api/walkforward` endpoints.**

## Testing

### Test 3.1: Strategy List Endpoint
```bash
# Start server
cd src
python server.py

# In another terminal:
curl http://localhost:8000/api/strategies

# Expected output:
# {
#   "strategies": [
#     {
#       "id": "s01_trailing_ma",
#       "name": "S01 Trailing MA",
#       "version": "v26",
#       ...
#     }
#   ]
# }
```

### Test 3.2: Strategy Config Endpoint
```bash
curl http://localhost:8000/api/strategies/s01_trailing_ma/config

# Expected: Full config.json content with all parameters
```

### Test 3.3: Strategy Metadata Endpoint
```bash
curl http://localhost:8000/api/strategies/s01_trailing_ma

# Expected:
# {
#   "id": "s01_trailing_ma",
#   "name": "S01 Trailing MA",
#   "version": "v26",
#   "parameter_count": 25
# }
```

### Test 3.4: Warmup Bars Parameter
Test that existing backtest endpoint still works:

```bash
# Create test request (use curl or Postman)
curl -X POST http://localhost:8000/api/backtest \
  -F "file=@../data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv" \
  -F "warmupBars=1500" \
  -F "payload={...}"  # JSON with strategy parameters

# Should return backtest results without errors
```

### Test 3.5: Backward Compatibility
Verify that old code using StrategyParams still works:

```python
from backtest_engine import (
    StrategyParams, load_data,
    prepare_dataset_with_warmup_legacy
)
import pandas as pd

df = load_data('data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv')

params = StrategyParams(
    use_date_filter=True,
    start=pd.Timestamp("2025-06-15", tz="UTC"),
    end=pd.Timestamp("2025-11-15", tz="UTC"),
    ma_type="SMA",
    ma_length=300,
    # ... other parameters
)

# Should work with legacy function
df_prepared, idx = prepare_dataset_with_warmup_legacy(df, params.start, params.end, params)

print(f"✓ Prepared {len(df_prepared)} bars, trade starts at index {idx}")
```

## Completion Checklist

- [ ] Strategy endpoints added to server.py
- [ ] `prepare_dataset_with_warmup()` signature updated
- [ ] Backward compatibility wrapper added
- [ ] Warmup bars parameter added to existing endpoints
- [ ] All endpoints tested and working
- [ ] Server starts without errors
- [ ] Git commit: "Migration Stage 3: Add strategy endpoints and warmup parameter"

## Next Stage

Proceed to **migration_prompt_4.md** to update the UI with dynamic form generation.
