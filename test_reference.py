#!/usr/bin/env python3
"""
Reference Test from Migration Prompt 5
Expected: ~230.75% profit, ~20.03% max DD, 93 trades
"""

import sys
sys.path.insert(0, './src')

import pandas as pd
from strategies import get_strategy

# Load CSV data
df = pd.read_csv('./data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv')
df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
df.set_index('time', inplace=True)
df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

# Apply date filter: 2025-06-15 to 2025-11-15
start = pd.Timestamp('2025-06-15 00:00', tz='UTC')
end = pd.Timestamp('2025-11-15 00:00', tz='UTC')

# Calculate warmup
warmup_bars = 1000
mask = (df.index >= start) & (df.index <= end)
trade_zone = df[mask]

if len(trade_zone) == 0:
    print("ERROR: No data in trade zone!")
    sys.exit(1)

# Get warmup data
first_trade_time = trade_zone.index[0]
warmup_df = df[df.index < first_trade_time].tail(warmup_bars)

# Concatenate warmup + trade zone
full_df = pd.concat([warmup_df, trade_zone])
trade_start_idx = len(warmup_df)

print(f"Data prepared:")
print(f"  Total bars: {len(full_df)}")
print(f"  Warmup bars: {trade_start_idx}")
print(f"  Trade zone bars: {len(trade_zone)}")
print(f"  Trade start: {full_df.index[trade_start_idx]}")
print()

# Load S01 strategy
S01 = get_strategy('s01_trailing_ma')

# Reference parameters from migration_prompt_5.md
params = {
    'maType': 'SMA',
    'maLength': 300,
    'closeCountLong': 9,
    'closeCountShort': 5,
    'stopLongX': 2.0,
    'stopLongRR': 3,
    'stopLongLP': 2,
    'stopShortX': 2.0,
    'stopShortRR': 3,
    'stopShortLP': 2,
    'stopLongMaxPct': 7.0,
    'stopShortMaxPct': 10.0,
    'stopLongMaxDays': 5,
    'stopShortMaxDays': 2,
    'trailRRLong': 1,
    'trailRRShort': 1,
    'trailLongType': 'EMA',
    'trailLongLength': 90,
    'trailLongOffset': -0.5,
    'trailShortType': 'EMA',
    'trailShortLength': 190,
    'trailShortOffset': 2.0,
    'commissionRate': 0.0005,
    'contractSize': 0.01,
    'riskPerTrade': 2.0,
    'atrPeriod': 14,
}

# Run backtest
print("Running backtest...")
result = S01.run(full_df, params, trade_start_idx)

print()
print("=" * 60)
print("REFERENCE TEST RESULTS")
print("=" * 60)
print(f"Net Profit:     {result.net_profit_pct:>10.2f}%")
print(f"Max Drawdown:   {result.max_drawdown_pct:>10.2f}%")
print(f"Total Trades:   {result.total_trades:>10}")
print()
print("EXPECTED (from migration_prompt_5.md):")
print(f"Net Profit:     {'230.75':>10}% (±0.5% tolerance)")
print(f"Max Drawdown:   {'20.03':>10}% (±0.5% tolerance)")
print(f"Total Trades:   {'93':>10} (±2 tolerance)")
print()

# Check tolerance
profit_ok = abs(result.net_profit_pct - 230.75) <= 0.5
dd_ok = abs(result.max_drawdown_pct - 20.03) <= 0.5
trades_ok = abs(result.total_trades - 93) <= 2

if profit_ok and dd_ok and trades_ok:
    print("✅ TEST PASSED - Results within tolerance!")
else:
    print("❌ TEST FAILED - Results outside tolerance:")
    if not profit_ok:
        print(f"   Profit diff: {result.net_profit_pct - 230.75:.2f}%")
    if not dd_ok:
        print(f"   DD diff: {result.max_drawdown_pct - 20.03:.2f}%")
    if not trades_ok:
        print(f"   Trades diff: {result.total_trades - 93}")
    sys.exit(1)
