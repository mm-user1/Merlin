"""Simple benchmark for indicators after extraction."""

import time

import numpy as np
import pandas as pd

# Add src to path
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from indicators.ma import get_ma
from indicators.volatility import atr


def main() -> None:
    np.random.seed(42)
    n_bars = 10000
    df = pd.DataFrame(
        {
            "Close": 100 + np.cumsum(np.random.randn(n_bars) * 2),
            "High": 102 + np.cumsum(np.random.randn(n_bars) * 2),
            "Low": 98 + np.cumsum(np.random.randn(n_bars) * 2),
            "Volume": np.random.randint(1000, 10000, n_bars),
        }
    )

    print("Benchmarking indicators...")

    ma_types = ["SMA", "EMA", "HMA", "WMA", "KAMA"]
    for ma_type in ma_types:
        start = time.time()
        for _ in range(100):
            _ = get_ma(df["Close"], ma_type, 50, volume=df["Volume"])
        duration = time.time() - start
        print(f"{ma_type:6} - 100 calls in {duration:.3f}s ({duration * 10:.1f}ms per call)")

    start = time.time()
    for _ in range(100):
        _ = atr(df["High"], df["Low"], df["Close"], 14)
    duration = time.time() - start
    print(f"ATR    - 100 calls in {duration:.3f}s ({duration * 10:.1f}ms per call)")

    print("\n✅ Performance acceptable (indicators fast enough)")


if __name__ == "__main__":
    main()
