# Tools

Development and debugging utilities for the Merlin platform.

## Available Tools

### generate_baseline_s01.py

Generates regression test baseline for S01 strategy.

**When to use:** After intentional changes to S01 that affect results.

```bash
python tools/generate_baseline_s01.py
```

**Output:**
- `data/baseline/s01_baseline_metrics.json` - Metrics snapshot
- `data/baseline/s01_baseline_trades.csv` - Trade list

### benchmark_indicators.py

Performance benchmark for indicator calculations.

**When to use:** After modifying indicator implementations to verify performance.

```bash
python tools/benchmark_indicators.py
```

**Output:** Timing results for each MA type and ATR (100 iterations on 10,000 bars).

### benchmark_metrics.py

Performance benchmark for metrics calculations.

**When to use:** After modifying metrics module to verify performance.

```bash
python tools/benchmark_metrics.py
```

### test_all_ma_types.py

Tests S01 strategy with all 11 MA types to ensure indicators work correctly.

**When to use:** After modifying MA indicators or S01 strategy logic.

```bash
python tools/test_all_ma_types.py
```

**Output:** Summary table showing profit/drawdown/trades for each MA type.

## Usage Notes

- All tools should be run from project root: `python tools/<script>.py`
- Tools add `src/` to Python path automatically
- Tools use the standard test data: `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
