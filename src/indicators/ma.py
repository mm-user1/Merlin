"""
Moving Average indicators for S01 Trailing MA v26.

This module implements 11 different moving average types:
- Simple: SMA, WMA
- Exponential: EMA, DEMA
- Adaptive: KAMA
- Low-lag: HMA, ALMA
- Advanced: TMA, T3
- Volume-weighted: VWMA, VWAP

All functions are pure and operate on pandas Series/DataFrames.

Critical: These implementations must remain bit-exact compatible with
the original backtest_engine.py implementations to maintain regression baseline.
"""
import math
from typing import Optional

import numpy as np
import pandas as pd

# Constants (copied from backtest_engine.py)
FACTOR_T3 = 0.7
FAST_KAMA = 2
SLOW_KAMA = 30

VALID_MA_TYPES = {
    "SMA",
    "EMA",
    "HMA",
    "WMA",
    "VWMA",
    "VWAP",
    "ALMA",
    "DEMA",
    "KAMA",
    "TMA",
    "T3",
}


# ============================================================================
# Basic Moving Averages
# ============================================================================

def sma(series: pd.Series, length: int) -> pd.Series:
    """
    Simple Moving Average.

    Calculates the arithmetic mean of the last 'length' values.

    Args:
        series: Input price series
        length: Period length

    Returns:
        SMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 244).
        Must remain bit-exact compatible with original implementation.
    """
    return series.rolling(length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    """
    Exponential Moving Average.

    Applies exponential weighting where recent values have more influence.

    Args:
        series: Input price series
        length: Period length (span)

    Returns:
        EMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 240).
        Must remain bit-exact compatible with original implementation.
    """
    return series.ewm(span=length, adjust=False).mean()


def wma(series: pd.Series, length: int) -> pd.Series:
    """
    Weighted Moving Average.

    Applies linear weighting where recent values have more influence.
    Weight formula: weights = [1, 2, 3, ..., length]

    Args:
        series: Input price series
        length: Period length

    Returns:
        WMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 248).
        Must remain bit-exact compatible with original implementation.
    """
    weights = np.arange(1, length + 1, dtype=float)
    return series.rolling(length, min_periods=length).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


# ============================================================================
# Volume-Weighted Moving Averages
# ============================================================================

def vwma(series: pd.Series, volume: pd.Series, length: int) -> pd.Series:
    """
    Volume-Weighted Moving Average.

    Calculates MA weighted by volume. Recent high-volume bars have more influence.

    Args:
        series: Input price series
        volume: Volume series
        length: Period length

    Returns:
        VWMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 263).
        Must remain bit-exact compatible with original implementation.
    """
    weighted = (series * volume).rolling(length, min_periods=length).sum()
    vol_sum = volume.rolling(length, min_periods=length).sum()
    return weighted / vol_sum


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Volume-Weighted Average Price.

    Cumulative typical price weighted by volume.

    Args:
        high: High price series
        low: Low price series
        close: Close price series
        volume: Volume series

    Returns:
        VWAP values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 336).
        Must remain bit-exact compatible with original implementation.
    """
    typical = (high + low + close) / 3
    tp_vol = typical * volume
    cumulative = tp_vol.cumsum()
    cumulative_vol = volume.cumsum()
    return cumulative / cumulative_vol


# ============================================================================
# Advanced Moving Averages Part 1 (with dependencies)
# ============================================================================

def hma(series: pd.Series, length: int) -> pd.Series:
    """
    Hull Moving Average.

    Fast, low-lag MA that reduces delay while improving smoothness.
    Formula: WMA(2*WMA(n/2) - WMA(n), sqrt(n))

    Args:
        series: Input price series
        length: Period length

    Returns:
        HMA values as pd.Series

    Dependencies:
        Requires wma() function

    Note:
        This is a COPY of the function from backtest_engine.py (line 255).
        Must remain bit-exact compatible with original implementation.
    """
    if length <= 0:
        return pd.Series(np.nan, index=series.index)
    half_length = max(1, length // 2)
    sqrt_length = max(1, int(math.sqrt(length)))
    return wma(2 * wma(series, half_length) - wma(series, length), sqrt_length)


def alma(series: pd.Series, length: int, offset: float = 0.85, sigma: float = 6) -> pd.Series:
    """
    Arnaud Legoux Moving Average.

    Uses Gaussian distribution to reduce lag while maintaining smoothness.

    Args:
        series: Input price series
        length: Period length
        offset: Gaussian offset (default 0.85)
        sigma: Gaussian sigma (default 6)

    Returns:
        ALMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 269).
        Must remain bit-exact compatible with original implementation.
    """
    if length <= 0:
        return pd.Series(np.nan, index=series.index)
    m = offset * (length - 1)
    s = length / sigma

    def _alma(values: np.ndarray) -> float:
        weights = np.exp(-((np.arange(len(values)) - m) ** 2) / (2 * s * s))
        weights /= weights.sum()
        return np.dot(weights, values)

    return series.rolling(length, min_periods=length).apply(_alma, raw=True)


def dema(series: pd.Series, length: int) -> pd.Series:
    """
    Double Exponential Moving Average.

    Reduces lag compared to single EMA.
    Formula: 2*EMA - EMA(EMA)

    Args:
        series: Input price series
        length: Period length

    Returns:
        DEMA values as pd.Series

    Dependencies:
        Requires ema() function

    Note:
        This is a COPY of the function from backtest_engine.py (line 283).
        Must remain bit-exact compatible with original implementation.
    """
    e1 = ema(series, length)
    e2 = ema(e1, length)
    return 2 * e1 - e2


def kama(series: pd.Series, length: int) -> pd.Series:
    """
    Kaufman Adaptive Moving Average.

    Adapts to market volatility - fast in trending markets, slow in ranging markets.
    Uses Efficiency Ratio (ER) to adjust smoothing constant.

    Args:
        series: Input price series
        length: Period length

    Returns:
        KAMA values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 289).
        Must remain bit-exact compatible with original implementation.

    Warning:
        This implementation uses iterative logic and is sensitive to
        floating-point order of operations. Must match EXACTLY.
    """
    if length <= 0:
        return pd.Series(np.nan, index=series.index)
    mom = series.diff(length).abs()
    volatility = series.diff().abs().rolling(length, min_periods=length).sum()
    er = pd.Series(np.where(volatility != 0, mom / volatility, 0), index=series.index)
    fast_alpha = 2 / (FAST_KAMA + 1)
    slow_alpha = 2 / (SLOW_KAMA + 1)
    alpha = (er * (fast_alpha - slow_alpha) + slow_alpha) ** 2
    kama_values = np.empty(len(series))
    kama_values[:] = np.nan
    for i in range(len(series)):
        price = series.iat[i]
        if np.isnan(price):
            continue
        a = alpha.iat[i]
        if np.isnan(a):
            kama_values[i] = price if i == 0 else kama_values[i - 1]
            continue
        prev = (
            kama_values[i - 1]
            if i > 0 and not np.isnan(kama_values[i - 1])
            else (series.iat[i - 1] if i > 0 else price)
        )
        kama_values[i] = a * price + (1 - a) * prev
    return pd.Series(kama_values, index=series.index)


def tma(series: pd.Series, length: int) -> pd.Series:
    """
    Triangular Moving Average.

    Double-smoothed SMA that reduces lag.
    Formula: SMA(SMA(n/2), n/2+1)

    Args:
        series: Input price series
        length: Period length

    Returns:
        TMA values as pd.Series

    Dependencies:
        Requires sma() function

    Note:
        This is a COPY of the function from backtest_engine.py (line 317).
        Must remain bit-exact compatible with original implementation.
    """
    if length <= 0:
        return pd.Series(np.nan, index=series.index)
    first = sma(series, math.ceil(length / 2))
    return sma(first, math.floor(length / 2) + 1)


def _gd(series: pd.Series, length: int) -> pd.Series:
    """
    Generalized DEMA helper for T3 calculation.

    Internal helper function - not exported.

    Args:
        series: Input price series
        length: Period length

    Returns:
        GD values as pd.Series

    Note:
        This is a COPY of the function from backtest_engine.py (line 324).
        Must remain bit-exact compatible with original implementation.
    """
    ema1 = ema(series, length)
    ema2 = ema(ema1, length)
    return ema1 * (1 + FACTOR_T3) - ema2 * FACTOR_T3


def t3(series: pd.Series, length: int) -> pd.Series:
    """
    T3 Moving Average.

    Triple exponential smoothing with volume factor.
    Applies _gd() helper three times for advanced smoothing.

    Args:
        series: Input price series
        length: Period length

    Returns:
        T3 values as pd.Series

    Dependencies:
        Requires _gd() helper function

    Note:
        This is a COPY of the function from backtest_engine.py (line 330).
        Must remain bit-exact compatible with original implementation.
    """
    if length <= 0:
        return pd.Series(np.nan, index=series.index)
    return _gd(_gd(_gd(series, length), length), length)


# ============================================================================
# Unified MA Interface
# ============================================================================

def get_ma(
    series: pd.Series,
    ma_type: str,
    length: int,
    volume: Optional[pd.Series] = None,
    high: Optional[pd.Series] = None,
    low: Optional[pd.Series] = None,
) -> pd.Series:
    """
    Unified interface for all MA types.

    Dispatches to the appropriate MA function based on ma_type.

    Args:
        series: Input price series (usually Close)
        ma_type: MA type name (case-insensitive)
        length: Period length
        volume: Volume series (required for VWMA, VWAP)
        high: High series (required for VWAP)
        low: Low series (required for VWAP)

    Returns:
        MA values as pd.Series

    Raises:
        ValueError: If ma_type is not supported or required data missing

    Note:
        This is a COPY of the function from backtest_engine.py (line 344).
        Must remain bit-exact compatible with original implementation.
    """
    ma_type = ma_type.upper()
    if ma_type not in VALID_MA_TYPES:
        raise ValueError(f"Unsupported MA type: {ma_type}")
    if ma_type != "VWAP" and length == 0:
        return pd.Series(np.nan, index=series.index)
    if ma_type == "SMA":
        return sma(series, length)
    if ma_type == "EMA":
        return ema(series, length)
    if ma_type == "HMA":
        return hma(series, length)
    if ma_type == "WMA":
        return wma(series, length)
    if ma_type == "VWMA":
        if volume is None:
            raise ValueError("Volume data required for VWMA")
        return vwma(series, volume, length)
    if ma_type == "VWAP":
        if any(v is None for v in (high, low, volume)):
            raise ValueError("High, Low, Volume required for VWAP")
        return vwap(high, low, series, volume)
    if ma_type == "ALMA":
        return alma(series, length)
    if ma_type == "DEMA":
        return dema(series, length)
    if ma_type == "KAMA":
        return kama(series, length)
    if ma_type == "TMA":
        return tma(series, length)
    if ma_type == "T3":
        return t3(series, length)
    return ema(series, length)
