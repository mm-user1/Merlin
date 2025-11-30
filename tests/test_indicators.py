"""Parity tests for extracted indicators (Phase 5)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core import backtest_engine
from indicators import ma, volatility


DATA_PATH = Path(__file__).parent.parent / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"


# Fixtures
@pytest.fixture(scope="module")
def test_df():
    if not DATA_PATH.exists():
        pytest.skip(f"Test data not found: {DATA_PATH}")
    return backtest_engine.load_data(str(DATA_PATH))


@pytest.fixture(scope="module")
def test_series(test_df):
    return test_df["Close"]


@pytest.fixture(scope="module")
def test_volume(test_df):
    return test_df["Volume"]


@pytest.fixture(scope="module")
def test_ohlcv(test_df):
    return test_df[["High", "Low", "Close", "Volume"]]


class TestMAsParity:
    """Test parity between OLD and NEW MA implementations."""

    def test_sma_parity(self, test_series):
        length = 20
        old_sma = backtest_engine.sma(test_series, length)
        new_sma = ma.sma(test_series, length)
        pd.testing.assert_series_equal(old_sma, new_sma)

    def test_ema_parity(self, test_series):
        length = 20
        old_ema = backtest_engine.ema(test_series, length)
        new_ema = ma.ema(test_series, length)
        pd.testing.assert_series_equal(old_ema, new_ema)

    def test_wma_parity(self, test_series):
        length = 20
        old_wma = backtest_engine.wma(test_series, length)
        new_wma = ma.wma(test_series, length)
        pd.testing.assert_series_equal(old_wma, new_wma)


class TestMAEdgeCases:
    """Test MA functions with edge cases."""

    def test_sma_zero_length(self, test_series):
        result = ma.sma(test_series, 0)
        assert result.isna().all()

    def test_ema_single_value(self):
        series = pd.Series([100.0])
        result = ma.ema(series, 1)
        assert not result.isna().any()
        assert result.iloc[0] == 100.0


class TestVolatilityParity:
    """Test parity for volatility indicators."""

    def test_atr_parity(self, test_ohlcv):
        period = 14
        old_atr = backtest_engine.atr(
            test_ohlcv["High"],
            test_ohlcv["Low"],
            test_ohlcv["Close"],
            period,
        )
        new_atr = volatility.atr(
            test_ohlcv["High"],
            test_ohlcv["Low"],
            test_ohlcv["Close"],
            period,
        )
        pd.testing.assert_series_equal(old_atr, new_atr)


class TestAdvancedMAsPart1:
    """Test parity for advanced MAs (HMA, DEMA)."""

    def test_hma_parity(self, test_series):
        length = 20
        old_hma = backtest_engine.hma(test_series, length)
        new_hma = ma.hma(test_series, length)
        pd.testing.assert_series_equal(old_hma, new_hma)

    def test_dema_parity(self, test_series):
        length = 20
        old_dema = backtest_engine.dema(test_series, length)
        new_dema = ma.dema(test_series, length)
        pd.testing.assert_series_equal(old_dema, new_dema)


class TestAdvancedMAsPart2:
    """Test parity for complex advanced MAs."""

    def test_alma_parity(self, test_series):
        length = 20
        old_alma = backtest_engine.alma(test_series, length)
        new_alma = ma.alma(test_series, length)
        pd.testing.assert_series_equal(old_alma, new_alma)

    def test_kama_parity(self, test_series):
        length = 20
        old_kama = backtest_engine.kama(test_series, length)
        new_kama = ma.kama(test_series, length)
        pd.testing.assert_series_equal(old_kama, new_kama, rtol=1e-10)

    def test_tma_parity(self, test_series):
        length = 20
        old_tma = backtest_engine.tma(test_series, length)
        new_tma = ma.tma(test_series, length)
        pd.testing.assert_series_equal(old_tma, new_tma)

    def test_t3_parity(self, test_series):
        length = 20
        old_t3 = backtest_engine.t3(test_series, length)
        new_t3 = ma.t3(test_series, length)
        pd.testing.assert_series_equal(old_t3, new_t3)


class TestAllMATypes:
    """Test all MA types work via get_ma()."""

    def test_all_ma_types_work(self, test_series, test_volume, test_ohlcv):
        length = 20
        for ma_type in ma.VALID_MA_TYPES:
            if ma_type == "VWMA":
                result = ma.get_ma(test_series, ma_type, length, volume=test_volume)
            elif ma_type == "VWAP":
                result = ma.get_ma(
                    test_ohlcv["Close"],
                    ma_type,
                    length,
                    volume=test_ohlcv["Volume"],
                    high=test_ohlcv["High"],
                    low=test_ohlcv["Low"],
                )
            else:
                result = ma.get_ma(test_series, ma_type, length)

            assert result is not None
            assert len(result) == len(test_series)


class TestGetMAFacade:
    """Test get_ma() unified interface."""

    def test_get_ma_parity_all_types(self, test_series, test_volume, test_ohlcv):
        length = 20

        for ma_type in ma.VALID_MA_TYPES:
            if ma_type == "VWMA":
                old_result = backtest_engine.get_ma(
                    test_series, ma_type, length, volume=test_volume
                )
                new_result = ma.get_ma(test_series, ma_type, length, volume=test_volume)
            elif ma_type == "VWAP":
                old_result = backtest_engine.get_ma(
                    test_ohlcv["Close"],
                    ma_type,
                    length,
                    volume=test_ohlcv["Volume"],
                    high=test_ohlcv["High"],
                    low=test_ohlcv["Low"],
                )
                new_result = ma.get_ma(
                    test_ohlcv["Close"],
                    ma_type,
                    length,
                    volume=test_ohlcv["Volume"],
                    high=test_ohlcv["High"],
                    low=test_ohlcv["Low"],
                )
            else:
                old_result = backtest_engine.get_ma(test_series, ma_type, length)
                new_result = ma.get_ma(test_series, ma_type, length)

            pd.testing.assert_series_equal(old_result, new_result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
