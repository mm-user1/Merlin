"""Simple benchmark for metrics calculation overhead (Phase 4)."""
import time
from dataclasses import asdict
from pathlib import Path
import sys

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.backtest_engine import load_data, prepare_dataset_with_warmup  # noqa: E402
from core.metrics import calculate_basic, calculate_advanced  # noqa: E402
from strategies.s01_trailing_ma.strategy import S01Params, S01TrailingMA  # noqa: E402


def main() -> None:
    data_path = Path(__file__).parent.parent / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
    df = load_data(str(data_path))

    params = S01Params(ma_type="HMA", ma_length=50)
    start_ts = pd.Timestamp("2025-05-01", tz="UTC")
    end_ts = pd.Timestamp("2025-11-20", tz="UTC")
    df_prepared, trade_start_idx = prepare_dataset_with_warmup(df, start_ts, end_ts, 1000)

    runs = 3
    start = time.time()

    for _ in range(runs):
        result = S01TrailingMA.run(df_prepared, asdict(params), trade_start_idx)
        _ = calculate_basic(result)
        _ = calculate_advanced(result)

    duration = time.time() - start
    print(f"Ran {runs} backtests in {duration:.2f}s")
    print(f"Average: {duration / runs:.3f}s per backtest")


if __name__ == "__main__":
    main()
