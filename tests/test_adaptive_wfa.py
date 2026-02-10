import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.backtest_engine import StrategyResult, TradeRecord
from core.walkforward_engine import WFConfig, WalkForwardEngine, WindowResult


def _build_engine(**kwargs):
    config = WFConfig(strategy_id="s01_trailing_ma", **kwargs)
    return WalkForwardEngine(config, {"fixed_params": {"dateFilter": False}}, {})


def _trade(exit_time: str, profit_pct: float) -> TradeRecord:
    return TradeRecord(exit_time=pd.Timestamp(exit_time, tz="UTC"), profit_pct=profit_pct)


def _result(trades, balances, timestamps):
    return StrategyResult(
        trades=list(trades),
        equity_curve=list(balances),
        balance_curve=list(balances),
        timestamps=list(timestamps),
    )


def test_compute_is_baseline_zero_trades_disables_triggers():
    engine = _build_engine()
    is_result = _result([], [100.0, 102.0], [pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2025-01-02", tz="UTC")])

    baseline = engine._compute_is_baseline(is_result, is_period_days=90)

    assert baseline["cusum_enabled"] is False
    assert baseline["drawdown_enabled"] is False
    assert baseline["inactivity_enabled"] is False


def test_compute_is_baseline_one_trade_uses_inactivity_fallback():
    engine = _build_engine()
    is_result = _result(
        [_trade("2025-01-05 00:00:00", 1.2)],
        [100.0, 101.0],
        [pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2025-01-05", tz="UTC")],
    )

    baseline = engine._compute_is_baseline(is_result, is_period_days=90)

    assert baseline["drawdown_enabled"] is True
    assert baseline["cusum_enabled"] is False
    assert baseline["inactivity_enabled"] is True
    assert baseline["max_trade_interval"] == pytest.approx(45.0)


def test_scan_triggers_drawdown_precedes_cusum():
    engine = _build_engine(min_oos_trades=1, check_interval_trades=1)
    baseline = {
        "mu": 1.0,
        "sigma": 1.0,
        "h": 0.1,
        "dd_limit": 1.0,
        "cusum_enabled": True,
        "drawdown_enabled": True,
        "inactivity_enabled": False,
    }
    trades = [_trade("2025-02-01 00:00:00", -5.0)]
    balances = [100.0, 98.0]
    timestamps = [
        pd.Timestamp("2025-01-31 00:00:00", tz="UTC"),
        pd.Timestamp("2025-02-01 00:00:00", tz="UTC"),
    ]

    trigger = engine._scan_triggers(
        trades=trades,
        balance_curve=balances,
        timestamps=timestamps,
        baseline=baseline,
        oos_start=pd.Timestamp("2025-01-31 00:00:00", tz="UTC"),
        oos_max_end=pd.Timestamp("2025-02-05 00:00:00", tz="UTC"),
    )

    assert trigger.trigger_type == "drawdown"
    assert trigger.trigger_trade_idx == 0


def test_scan_triggers_uses_fractional_days_for_inactivity():
    engine = _build_engine()
    baseline = {
        "h": 5.0,
        "dd_limit": 0.0,
        "cusum_enabled": False,
        "drawdown_enabled": False,
        "inactivity_enabled": True,
        "max_trade_interval": 0.25,
    }

    oos_start = pd.Timestamp("2025-03-01 00:00:00", tz="UTC")
    oos_end = pd.Timestamp("2025-03-02 00:00:00", tz="UTC")
    trigger = engine._scan_triggers(
        trades=[],
        balance_curve=[],
        timestamps=[],
        baseline=baseline,
        oos_start=oos_start,
        oos_max_end=oos_end,
    )

    assert trigger.trigger_type == "inactivity"
    assert trigger.oos_actual_days == pytest.approx(0.25)


def test_scan_triggers_between_trade_inactivity_returns_previous_trade_index():
    engine = _build_engine()
    baseline = {
        "h": 5.0,
        "dd_limit": 0.0,
        "cusum_enabled": False,
        "drawdown_enabled": False,
        "inactivity_enabled": True,
        "max_trade_interval": 1.0,
    }

    trades = [
        _trade("2025-04-02 00:00:00", 1.0),
        _trade("2025-04-05 00:00:00", 1.0),
    ]
    trigger = engine._scan_triggers(
        trades=trades,
        balance_curve=[],
        timestamps=[],
        baseline=baseline,
        oos_start=pd.Timestamp("2025-04-01 00:00:00", tz="UTC"),
        oos_max_end=pd.Timestamp("2025-04-10 00:00:00", tz="UTC"),
    )

    assert trigger.trigger_type == "inactivity"
    assert trigger.trigger_trade_idx == 0
    assert trigger.oos_actual_trades == 1


def test_adaptive_wfe_is_duration_weighted():
    engine = _build_engine(adaptive_mode=True, is_period_days=90, oos_period_days=30)
    windows = [
        WindowResult(
            window_id=1,
            is_start=pd.Timestamp("2025-01-01", tz="UTC"),
            is_end=pd.Timestamp("2025-03-31", tz="UTC"),
            oos_start=pd.Timestamp("2025-03-31", tz="UTC"),
            oos_end=pd.Timestamp("2025-04-10", tz="UTC"),
            best_params={},
            param_id="w1",
            is_net_profit_pct=10.0,
            is_max_drawdown_pct=1.0,
            is_total_trades=10,
            oos_net_profit_pct=2.0,
            oos_max_drawdown_pct=1.0,
            oos_total_trades=3,
            oos_equity_curve=[100.0, 102.0],
            oos_timestamps=[
                pd.Timestamp("2025-03-31", tz="UTC"),
                pd.Timestamp("2025-04-10", tz="UTC"),
            ],
            oos_actual_days=10.0,
        ),
        WindowResult(
            window_id=2,
            is_start=pd.Timestamp("2025-02-01", tz="UTC"),
            is_end=pd.Timestamp("2025-05-02", tz="UTC"),
            oos_start=pd.Timestamp("2025-05-02", tz="UTC"),
            oos_end=pd.Timestamp("2025-07-31", tz="UTC"),
            best_params={},
            param_id="w2",
            is_net_profit_pct=10.0,
            is_max_drawdown_pct=1.0,
            is_total_trades=10,
            oos_net_profit_pct=6.0,
            oos_max_drawdown_pct=1.0,
            oos_total_trades=3,
            oos_equity_curve=[100.0, 106.0],
            oos_timestamps=[
                pd.Timestamp("2025-05-02", tz="UTC"),
                pd.Timestamp("2025-07-31", tz="UTC"),
            ],
            oos_actual_days=90.0,
        ),
    ]

    stitched = engine._build_stitched_oos_equity(windows)
    assert stitched.wfe == pytest.approx(72.0, rel=1e-3)
