"""
Generate baseline results for S01 Trailing MA strategy.

This script runs the current S01 strategy with fixed parameters
and saves the results for regression testing purposes.

The baseline includes:
- Basic metrics (Net Profit %, Max DD %, Total Trades, etc.)
- All trade records with entry/exit times and PnL
- Equity curve (optional but useful for debugging)

Usage:
    python tools/generate_baseline_s01.py
"""

import sys
import json
from dataclasses import asdict
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from core.backtest_engine import load_data, prepare_dataset_with_warmup
from strategies.s01_trailing_ma.strategy import S01Params, S01TrailingMA


# Fixed parameters for baseline (from user requirements)
BASELINE_PARAMS = {
    "maType": "SMA",
    "maLength": 300,
    "closeCountLong": 9,
    "closeCountShort": 5,
    "stopLongX": 2.0,
    "stopLongRR": 3,
    "stopLongLP": 2,
    "stopShortX": 2.0,
    "stopShortRR": 3,
    "stopShortLP": 2,
    "stopLongMaxPct": 7.0,
    "stopShortMaxPct": 10.0,
    "stopLongMaxDays": 5,
    "stopShortMaxDays": 2,
    "trailRRLong": 1,
    "trailRRShort": 1,
    "trailMaType": "EMA",
    "trailLongLength": 90,
    "trailLongOffset": -0.5,
    "trailShortLength": 190,
    "trailShortOffset": 2.0,
    "backtester": True,
    "dateFilter": True,
    "start": "2025-06-15 00:00:00",
    "end": "2025-11-15 00:00:00",
    "riskPerTrade": 2.0,
    "contractSize": 0.01,
    "commissionRate": 0.0005,
}

# Dataset details
CSV_FILE = "data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
WARMUP_BARS = 1000

# Output directory
OUTPUT_DIR = Path("data/baseline")


def load_csv_data(csv_path: str) -> pd.DataFrame:
    """Load OHLCV data using the official load_data function."""
    print(f"Loading data from {csv_path}...")
    df = load_data(csv_path)
    print(f"Loaded {len(df)} bars")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    return df


def run_baseline():
    """Run baseline backtest and save results."""
    print("=" * 80)
    print("S01 Trailing MA v26 - Baseline Generation")
    print("=" * 80)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    project_root = Path(__file__).parent.parent
    csv_path = project_root / CSV_FILE
    df = load_csv_data(str(csv_path))

    # Parse parameters
    print("\nParsing strategy parameters...")
    params = S01Params.from_dict(BASELINE_PARAMS)
    print(f"MA Type: {params.maType}")
    print(f"MA Length: {params.maLength}")
    print(f"Close Count Long: {params.closeCountLong}")
    print(f"Close Count Short: {params.closeCountShort}")

    # Prepare dataset with warmup (using official function)
    print("\nPreparing dataset with warmup...")
    start_ts = pd.Timestamp(BASELINE_PARAMS["start"], tz="UTC")
    end_ts = pd.Timestamp(BASELINE_PARAMS["end"], tz="UTC")

    df_prepared, trade_start_idx = prepare_dataset_with_warmup(
        df, start_ts, end_ts, WARMUP_BARS
    )

    print(f"Prepared dataset: {len(df_prepared)} bars")
    print(f"Trade start index: {trade_start_idx}")
    print(f"Trading period: {len(df_prepared) - trade_start_idx} bars")

    # Run strategy
    print("\nRunning backtest...")
    result = S01TrailingMA.run(df_prepared, asdict(params), trade_start_idx)

    # Display results
    print("\n" + "=" * 80)
    print("BASELINE RESULTS")
    print("=" * 80)
    print(f"Net Profit: {result.net_profit_pct:.2f}%")
    print(f"Max Drawdown: {result.max_drawdown_pct:.2f}%")
    print(f"Total Trades: {result.total_trades}")

    if result.sharpe_ratio is not None:
        print(f"Sharpe Ratio: {result.sharpe_ratio:.4f}")
    if result.profit_factor is not None:
        print(f"Profit Factor: {result.profit_factor:.4f}")
    if result.romad is not None:
        print(f"RoMaD: {result.romad:.4f}")
    if result.sqn is not None:
        print(f"SQN: {result.sqn:.4f}")

    # Save metrics to JSON
    metrics_file = OUTPUT_DIR / "s01_metrics.json"
    metrics = {
        "net_profit_pct": float(result.net_profit_pct),
        "max_drawdown_pct": float(result.max_drawdown_pct),
        "total_trades": int(result.total_trades),
        "sharpe_ratio": float(result.sharpe_ratio) if result.sharpe_ratio is not None else None,
        "profit_factor": float(result.profit_factor) if result.profit_factor is not None else None,
        "romad": float(result.romad) if result.romad is not None else None,
        "ulcer_index": float(result.ulcer_index) if result.ulcer_index is not None else None,
        "sqn": float(result.sqn) if result.sqn is not None else None,
        "consistency_score": float(result.consistency_score) if result.consistency_score is not None else None,
        "generated_at": datetime.now().isoformat(),
        "parameters": BASELINE_PARAMS,
        "dataset": CSV_FILE,
        "warmup_bars": WARMUP_BARS,
    }

    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved to: {metrics_file}")

    # Save trades to CSV
    if result.trades:
        trades_file = OUTPUT_DIR / "s01_trades.csv"
        trades_data = []
        for trade in result.trades:
            trades_data.append({
                "direction": trade.direction,
                "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
                "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
                "entry_price": float(trade.entry_price),
                "exit_price": float(trade.exit_price),
                "size": float(trade.size),
                "net_pnl": float(trade.net_pnl),
                "profit_pct": float(trade.profit_pct) if trade.profit_pct is not None else None,
            })

        trades_df = pd.DataFrame(trades_data)
        trades_df.to_csv(trades_file, index=False)
        print(f"Trades saved to: {trades_file}")
        print(f"Total trades exported: {len(trades_data)}")

    # Save README with documentation
    readme_file = OUTPUT_DIR / "README.md"
    readme_content = f"""# S01 Trailing MA v26 - Baseline Data

## Overview

This directory contains baseline results for the S01 Trailing MA strategy.
These results serve as the "golden standard" for regression testing during migration.

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Dataset

- **File:** `{CSV_FILE}`
- **Symbol:** OKX_LINKUSDT.P
- **Timeframe:** 15 minutes
- **Full Range:** 2025-05-01 to 2025-11-20

## Backtest Configuration

### Date Range
- **Start:** {BASELINE_PARAMS['start']}
- **End:** {BASELINE_PARAMS['end']}
- **Warmup Bars:** {WARMUP_BARS}

### Strategy Parameters

**Main MA:**
- Type: {BASELINE_PARAMS['maType']}
- Length: {BASELINE_PARAMS['maLength']}

**Entry Logic:**
- Close Count Long: {BASELINE_PARAMS['closeCountLong']}
- Close Count Short: {BASELINE_PARAMS['closeCountShort']}

**Stop Loss (Long):**
- ATR Multiplier: {BASELINE_PARAMS['stopLongX']}
- Risk/Reward: {BASELINE_PARAMS['stopLongRR']}
- Lookback Period: {BASELINE_PARAMS['stopLongLP']}
- Max %: {BASELINE_PARAMS['stopLongMaxPct']}%
- Max Days: {BASELINE_PARAMS['stopLongMaxDays']}

**Stop Loss (Short):**
- ATR Multiplier: {BASELINE_PARAMS['stopShortX']}
- Risk/Reward: {BASELINE_PARAMS['stopShortRR']}
- Lookback Period: {BASELINE_PARAMS['stopShortLP']}
- Max %: {BASELINE_PARAMS['stopShortMaxPct']}%
- Max Days: {BASELINE_PARAMS['stopShortMaxDays']}

**Trailing Stops:**
- Long Trail RR: {BASELINE_PARAMS['trailRRLong']}
- Trail MA Type: {BASELINE_PARAMS['trailMaType']}
- Long Trail Length: {BASELINE_PARAMS['trailLongLength']}
- Long Trail Offset: {BASELINE_PARAMS['trailLongOffset']}%
- Short Trail RR: {BASELINE_PARAMS['trailRRShort']}
- Short Trail Length: {BASELINE_PARAMS['trailShortLength']}
- Short Trail Offset: {BASELINE_PARAMS['trailShortOffset']}%

## Expected Results

Based on user requirements, the baseline should produce:

- **Net Profit:** {metrics['net_profit_pct']:.2f}% (Expected: ~230.75% ±0.5%)
- **Max Drawdown:** {metrics['max_drawdown_pct']:.2f}% (Expected: ~20.03% ±0.5%)
- **Total Trades:** {metrics['total_trades']} (Expected: ~93 ±2)

## Tolerance Levels for Regression Tests

The following tolerances are used for regression validation:

- **net_profit_pct:** ±0.01% (floating point tolerance)
- **max_drawdown_pct:** ±0.01%
- **total_trades:** exact match (±0)
- **trade entry/exit times:** exact match
- **trade PnL:** ±0.0001 (floating point epsilon)

## Files

- `s01_metrics.json` - Basic and advanced metrics
- `s01_trades.csv` - All trade records
- `README.md` - This file

## Usage

The regression test (`tests/test_regression_s01.py`) loads these baseline results
and compares them against the current implementation to ensure no behavioral changes
during migration.
"""

    with open(readme_file, "w") as f:
        f.write(readme_content)
    print(f"Documentation saved to: {readme_file}")

    print("\n" + "=" * 80)
    print("BASELINE GENERATION COMPLETE")
    print("=" * 80)
    print(f"\nBaseline files created in: {OUTPUT_DIR}")
    print("\nYou can now run regression tests with:")
    print("  pytest tests/test_regression_s01.py -v")


if __name__ == "__main__":
    run_baseline()
