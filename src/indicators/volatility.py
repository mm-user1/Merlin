"""
Volatility indicators for S01 Trailing MA v26.

Contains Average True Range (ATR) and related volatility metrics.
All functions are pure and compatible with legacy implementations.
"""

import pandas as pd


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """
    Average True Range (ATR).

    Measures market volatility using true range smoothed by EMA.

    Args:
        high: High price series
        low: Low price series
        close: Close price series
        period: ATR period (default 14)

    Returns:
        ATR values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 386).
        Must remain bit-exact compatible with original implementation.
    """
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()
