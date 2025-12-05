"""Test S01 with all 11 MA types to ensure indicators work."""

from pathlib import Path

import pandas as pd

# Add src to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.backtest_engine import load_data, prepare_dataset_with_warmup
from indicators.ma import VALID_MA_TYPES
from strategies.s01_trailing_ma.strategy import S01Params, S01TrailingMA


def main() -> None:
    data_path = Path(__file__).parent.parent / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
    df = load_data(str(data_path))

    start_ts = pd.Timestamp("2025-05-01", tz="UTC")
    end_ts = pd.Timestamp("2025-11-20", tz="UTC")
    df_prepared, trade_start_idx = prepare_dataset_with_warmup(df, start_ts, end_ts, 1000)

    print(f"Testing S01 with all {len(VALID_MA_TYPES)} MA types...")

    results = {}
    for ma_type in sorted(VALID_MA_TYPES):
        print(f"\nTesting {ma_type}...", end=" ")
        payload = {
            "backtester": True,
            "dateFilter": True,
            "start": start_ts,
            "end": end_ts,
            "maType": ma_type,
            "maLength": 50,
            "closeCountLong": 7,
            "closeCountShort": 5,
            "trailLongType": ma_type,
            "trailLongLength": 160,
            "trailLongOffset": -1.0,
            "trailShortType": ma_type,
            "trailShortLength": 160,
            "trailShortOffset": 1.0,
            "stopLongX": 2.0,
            "stopLongRR": 3.0,
            "stopLongLP": 2,
            "stopShortX": 2.0,
            "stopShortRR": 3.0,
            "stopShortLP": 2,
            "stopLongMaxPct": 3.0,
            "stopShortMaxPct": 3.0,
            "stopLongMaxDays": 2,
            "stopShortMaxDays": 4,
            "trailRRLong": 1.0,
            "trailRRShort": 1.0,
            "riskPerTrade": 2.0,
            "contractSize": 0.01,
            "commissionRate": 0.0005,
            "atrPeriod": 14,
        }

        params = S01Params.from_dict(payload)
        try:
            result = S01TrailingMA.run(df_prepared, params.to_dict(), trade_start_idx)
            results[ma_type] = {
                "net_profit_pct": result.net_profit_pct,
                "max_dd_pct": result.max_drawdown_pct,
                "total_trades": result.total_trades,
            }
            print(f"✅ Profit: {result.net_profit_pct:.2f}%, Trades: {result.total_trades}")
        except Exception as e:  # pragma: no cover - debugging aid
            print(f"❌ FAILED: {e}")
            results[ma_type] = {"error": str(e)}

    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)

    for ma_type, res in sorted(results.items()):
        if "error" in res:
            print(f"{ma_type:8} - ERROR: {res['error']}")
        else:
            print(
                f"{ma_type:8} - Profit: {res['net_profit_pct']:8.2f}% | "
                f"DD: {res['max_dd_pct']:7.2f}% | Trades: {res['total_trades']:3d}"
            )

    all_passed = all("error" not in res for res in results.values())
    if all_passed:
        print("\n✅ All 11 MA types working correctly!")
    else:
        print("\n❌ Some MA types failed!")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
