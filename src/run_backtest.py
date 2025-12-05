import argparse
import pandas as pd

from core.backtest_engine import load_data, prepare_dataset_with_warmup
from strategies import get_strategy
from strategies.s01_trailing_ma import S01Params

DEFAULT_CSV_PATH = "data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
DEFAULT_WARMUP_BARS = 1000


def build_default_params() -> S01Params:
    return S01Params(
        use_backtester=True,
        use_date_filter=True,
        start=pd.Timestamp("2025-06-15", tz="UTC"),
        end=pd.Timestamp("2025-11-15", tz="UTC"),
        ma_type="SMA",
        ma_length=300,
        close_count_long=9,
        close_count_short=5,
        stop_long_atr=2.0,
        stop_long_rr=3.0,
        stop_long_lp=2,
        stop_short_atr=2.0,
        stop_short_rr=3.0,
        stop_short_lp=2,
        stop_long_max_pct=7.0,
        stop_short_max_pct=10.0,
        stop_long_max_days=5,
        stop_short_max_days=2,
        trail_rr_long=1.0,
        trail_rr_short=1.0,
        trail_ma_long_type="EMA",
        trail_ma_long_length=90,
        trail_ma_long_offset=-0.5,
        trail_ma_short_type="EMA",
        trail_ma_short_length=190,
        trail_ma_short_offset=2.0,
        risk_per_trade_pct=2.0,
        contract_size=0.01,
        commission_rate=0.0005,
        atr_period=14,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the S01 Trailing MA backtest")
    parser.add_argument(
        "--csv",
        type=str,
        default=DEFAULT_CSV_PATH,
        help="Path to the CSV file with OHLCV data",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP_BARS,
        help="Warmup bars to include before the start date",
    )
    args = parser.parse_args()

    df = load_data(args.csv)
    params = build_default_params()

    df_prepared, trade_start_idx = prepare_dataset_with_warmup(
        df, params.start, params.end, args.warmup
    )

    strategy_cls = get_strategy("s01_trailing_ma")
    result = strategy_cls.run(df_prepared, params.to_dict(), trade_start_idx)

    print(f"Net Profit %: {result.net_profit_pct:.2f}")
    print(f"Max Portfolio Drawdown %: {result.max_drawdown_pct:.2f}")
    print(f"Total Trades: {result.total_trades}")


if __name__ == "__main__":
    main()
