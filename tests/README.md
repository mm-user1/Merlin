# Tests

Pytest test suite for the Merlin backtesting platform.

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_regression_s01.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Test Files

| File | Purpose |
|------|---------|
| `test_sanity.py` | Infrastructure sanity checks (imports, directories, Python version) |
| `test_regression_s01.py` | S01 baseline regression - validates results match saved baseline |
| `test_s01_migration.py` | S01 migration validation - ensures migrated strategy works correctly |
| `test_s04_stochrsi.py` | S04 StochRSI strategy tests |
| `test_metrics.py` | Metrics calculation tests (BasicMetrics, AdvancedMetrics) |
| `test_export.py` | CSV export functionality tests |
| `test_indicators.py` | Technical indicator tests (MA types, ATR, RSI) |
| `test_naming_consistency.py` | camelCase naming guardrails - prevents snake_case parameters |
| `test_walkforward.py` | Walk-forward analysis tests |
| `test_server.py` | HTTP API endpoint tests |

## Test Categories

### Sanity Tests
Quick infrastructure checks. Run first to verify environment:
```bash
pytest tests/test_sanity.py -v
```

### Regression Tests
Validate strategy results against saved baselines:
```bash
pytest tests/test_regression_s01.py -v
```

If regression tests fail after intentional changes, regenerate baseline:
```bash
python tools/generate_baseline_s01.py
```

### Strategy Tests
Test individual strategy implementations:
```bash
pytest tests/test_s01_migration.py tests/test_s04_stochrsi.py -v
```

### Naming Guardrails
Ensure camelCase convention is maintained:
```bash
pytest tests/test_naming_consistency.py -v
```

## Baseline Data

Regression baselines stored in `data/baseline/`:
- `s01_baseline_metrics.json` - Expected S01 metrics
- `s01_baseline_trades.csv` - Expected S01 trade list

## Adding Tests for New Strategies

1. Create `tests/test_<strategy_id>.py`
2. Include tests for:
   - Basic execution (strategy runs without error)
   - Expected results validation (against PineScript reference)
   - Edge cases (empty data, extreme parameters)
3. Run with: `pytest tests/test_<strategy_id>.py -v`
