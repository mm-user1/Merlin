from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.post_process import (
    calculate_comparison_metrics,
    calculate_ft_dates,
    calculate_profit_degradation,
)


def test_calculate_ft_dates_basic():
    start = pd.Timestamp("2025-05-01", tz="UTC")
    end = pd.Timestamp("2025-09-01", tz="UTC")
    is_end, ft_start, ft_end, is_days, ft_days = calculate_ft_dates(start, end, 30)
    assert ft_end == end
    assert ft_start == end - pd.Timedelta(days=30)
    assert is_end == ft_start
    assert is_days == (is_end - start).days
    assert ft_days == 30


def test_calculate_ft_dates_invalid():
    start = pd.Timestamp("2025-05-01", tz="UTC")
    end = pd.Timestamp("2025-05-10", tz="UTC")
    try:
        calculate_ft_dates(start, end, 10)
    except ValueError as exc:
        assert "FT period" in str(exc)
    else:
        raise AssertionError("Expected ValueError for FT period >= range")


def test_calculate_profit_degradation_annualized():
    is_profit = 10.0
    ft_profit = 5.0
    ratio = calculate_profit_degradation(is_profit, ft_profit, 100, 50)
    assert abs(ratio - 1.0) < 1e-6


def test_calculate_comparison_metrics():
    is_metrics = {
        "net_profit_pct": 20.0,
        "max_drawdown_pct": 5.0,
        "romad": 4.0,
        "sharpe_ratio": 1.5,
        "profit_factor": 1.8,
    }
    ft_metrics = {
        "net_profit_pct": 10.0,
        "max_drawdown_pct": 7.0,
        "romad": 2.0,
        "sharpe_ratio": 1.0,
        "profit_factor": 1.2,
    }
    comparison = calculate_comparison_metrics(is_metrics, ft_metrics, 100, 50)
    assert comparison["max_dd_change"] == 2.0
    assert comparison["romad_change"] == -2.0
    assert comparison["sharpe_change"] == -0.5
    assert comparison["pf_change"] == pytest.approx(-0.6)
