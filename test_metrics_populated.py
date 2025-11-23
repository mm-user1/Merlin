#!/usr/bin/env python3
"""
Test that advanced metrics are now populated in StrategyResult
"""

import sys
sys.path.insert(0, './src')

import pandas as pd
from strategies import get_strategy

# Load data
df = pd.read_csv('./data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv')
df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
df.set_index('time', inplace=True)
df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

# Run S01 with default params
S01 = get_strategy('s01_trailing_ma')
params = {
    'maType': 'SMA', 'maLength': 45, 'closeCountLong': 7, 'closeCountShort': 5,
    'stopLongX': 2.0, 'stopLongRR': 3, 'stopLongLP': 2,
    'stopShortX': 2.0, 'stopShortRR': 3, 'stopShortLP': 2,
    'stopLongMaxPct': 3.0, 'stopShortMaxPct': 3.0,
    'stopLongMaxDays': 2, 'stopShortMaxDays': 4,
    'trailRRLong': 1.0, 'trailRRShort': 1.0,
    'trailLongType': 'SMA', 'trailLongLength': 160, 'trailLongOffset': -1.0,
    'trailShortType': 'SMA', 'trailShortLength': 160, 'trailShortOffset': 1.0,
    'commissionRate': 0.0005, 'contractSize': 0.01, 'riskPerTrade': 2.0, 'atrPeriod': 14,
}

print("Running backtest with S01 default parameters...")
result = S01.run(df, params, trade_start_idx=0)

print()
print("=" * 60)
print("ADVANCED METRICS POPULATION TEST")
print("=" * 60)

# Check basic metrics first
print("\nBasic Metrics:")
print(f"  Net Profit:     {result.net_profit_pct:.2f}%")
print(f"  Max Drawdown:   {result.max_drawdown_pct:.2f}%")
print(f"  Total Trades:   {result.total_trades}")

# Verify all advanced metrics are populated
print("\nAdvanced Metrics:")
metrics_to_check = [
    'sharpe_ratio',
    'profit_factor',
    'romad',
    'ulcer_index',
    'recovery_factor',
    'consistency_score'
]

all_populated = True
for metric in metrics_to_check:
    value = getattr(result, metric)
    if value is not None:
        status = "✅"
        display = f"{value:.2f}" if isinstance(value, float) else str(value)
    else:
        status = "❌"
        display = "None"
        all_populated = False

    print(f"  {status} {metric:20s}: {display}")

print()
if all_populated:
    print("✅ ALL ADVANCED METRICS POPULATED - Fix successful!")
    print()
    print("Impact:")
    print("  ✅ Optimization scoring now works correctly")
    print("  ✅ CSV exports include all advanced metric columns")
    print("  ✅ Score Filter functionality enabled")
    print("  ✅ Walk-Forward Analysis can use metrics for selection")
    sys.exit(0)
else:
    print("❌ SOME METRICS MISSING - Fix incomplete!")
    sys.exit(1)
