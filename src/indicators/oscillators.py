"""
Oscillator indicators for the strategy suite.

Implements TradingView-compatible RSI and Stochastic RSI using
Wilder's smoothing for reliability with the migrated architecture.
"""

import numpy as np
import pandas as pd


def rsi(series: pd.Series, length: int) -> pd.Series:
    """
    Relative Strength Index (RSI).

    Matches TradingView's ``ta.rsi`` using Wilder's smoothing where the
    smoothing factor is ``alpha = 1 / length``.

    Args:
        series: Input price series (typically Close).
        length: RSI period.

    Returns:
        RSI values as a ``pd.Series`` in the range ``[0, 100]``.
    """

    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

    rs = avg_gain / avg_loss
    rsi_values = 100.0 - (100.0 / (1.0 + rs))

    return rsi_values


def stoch_rsi(close: pd.Series, rsi_len: int, stoch_len: int) -> pd.Series:
    """
    Stochastic RSI.

    Applies the stochastic oscillator to RSI values to measure momentum.

    Args:
        close: Close price series.
        rsi_len: RSI lookback period.
        stoch_len: Stochastic lookback period.

    Returns:
        StochRSI values as a ``pd.Series`` scaled to ``[0, 100]``.
    """

    rsi_values = rsi(close, rsi_len)
    rsi_min = rsi_values.rolling(window=stoch_len, min_periods=1).min()
    rsi_max = rsi_values.rolling(window=stoch_len, min_periods=1).max()

    denominator = rsi_max - rsi_min
    stoch_rsi_values = pd.Series(0.0, index=close.index)

    valid_mask = denominator.notna() & (denominator != 0)
    stoch_rsi_values.loc[valid_mask] = (
        (rsi_values.loc[valid_mask] - rsi_min.loc[valid_mask])
        / denominator.loc[valid_mask]
        * 100.0
    )

    return stoch_rsi_values


__all__ = ["rsi", "stoch_rsi"]
