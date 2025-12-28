import hashlib
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.walkforward_engine import (
    OOSStitchedResult,
    WFConfig,
    WFResult,
    WalkForwardEngine,
    WindowResult,
)
from core.export import export_wfa_trades_history
from core.backtest_engine import StrategyResult, TradeRecord, load_data
from strategies import get_strategy_config


def _build_params_from_config(strategy_id: str):
    config = get_strategy_config(strategy_id)
    parameters = config.get("parameters", {}) if isinstance(config, dict) else {}
    params = {}
    for name, spec in parameters.items():
        if not isinstance(spec, dict):
            continue
        default_value = spec.get("default")
        params[name] = default_value if default_value is not None else 0
    return params


def _build_wf_result(strategy_id: str):
    wf_config = WFConfig(strategy_id=strategy_id, is_period_days=180, oos_period_days=60)
    params = _build_params_from_config(strategy_id)
    engine = WalkForwardEngine(wf_config, {}, {})
    param_id = engine._create_param_id(params)

    window_result = WindowResult(
        window_id=1,
        is_start=pd.Timestamp("2025-01-01", tz="UTC"),
        is_end=pd.Timestamp("2025-06-29", tz="UTC"),
        oos_start=pd.Timestamp("2025-06-30", tz="UTC"),
        oos_end=pd.Timestamp("2025-08-28", tz="UTC"),
        best_params=params,
        param_id=param_id,
        is_net_profit_pct=1.0,
        is_max_drawdown_pct=0.5,
        is_total_trades=5,
        oos_net_profit_pct=2.0,
        oos_max_drawdown_pct=1.0,
        oos_total_trades=4,
        oos_equity_curve=[100.0, 102.0],
        oos_timestamps=[
            pd.Timestamp("2025-06-30", tz="UTC"),
            pd.Timestamp("2025-08-28", tz="UTC"),
        ],
    )

    stitched = OOSStitchedResult(
        final_net_profit_pct=2.0,
        max_drawdown_pct=1.0,
        total_trades=4,
        wfe=100.0,
        oos_win_rate=100.0,
        equity_curve=[100.0, 102.0],
        timestamps=[pd.Timestamp("2025-06-30", tz="UTC"), pd.Timestamp("2025-08-28", tz="UTC")],
        window_ids=[1, 1],
    )

    result = WFResult(
        config=wf_config,
        windows=[window_result],
        stitched_oos=stitched,
        strategy_id=strategy_id,
        total_windows=1,
        trading_start_date=window_result.is_start,
        trading_end_date=window_result.oos_end,
        warmup_bars=wf_config.warmup_bars,
    )

    return result, params, param_id


def test_param_id_generation_s01():
    engine = WalkForwardEngine(WFConfig(strategy_id="s01_trailing_ma"), {}, {})
    params = {"maType": "EMA", "maLength": 45, "closeCountLong": 7}

    expected_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]
    assert engine._create_param_id(params) == f"EMA 45_{expected_hash}"


def test_param_id_generation_s04():
    engine = WalkForwardEngine(WFConfig(strategy_id="s04_stochrsi"), {}, {})
    params = {"rsiLen": 16, "stochLen": 20, "kLen": 3}

    expected_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]
    assert engine._create_param_id(params) == f"16 20_{expected_hash}"


def test_param_id_falls_back_and_logs_warning(monkeypatch, caplog):
    """
    Ensure _create_param_id logs and falls back to hash when strategy config cannot be read.
    """

    engine = WalkForwardEngine(WFConfig(strategy_id="s01_trailing_ma"), {}, {})
    params = {"maType": "EMA", "maLength": 45, "closeCountLong": 7}
    expected_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]

    def raise_value_error(strategy_id):  # noqa: ARG001
        raise ValueError("boom")

    monkeypatch.setattr("strategies.get_strategy_config", raise_value_error)

    with caplog.at_level(logging.WARNING, logger="core.walkforward_engine"):
        param_id = engine._create_param_id(params)

    assert param_id == expected_hash
    assert any("Falling back to hash-only param_id" in record.message for record in caplog.records)


def test_split_data_rolls_forward():
    index = pd.date_range("2025-01-01", periods=40, freq="D", tz="UTC")
    base_row = {"Open": 1.0, "High": 1.1, "Low": 0.9, "Close": 1.0, "Volume": 100}
    df = pd.DataFrame([base_row for _ in range(len(index))], index=index)

    wf_config = WFConfig(strategy_id="s01_trailing_ma", is_period_days=10, oos_period_days=5)
    engine = WalkForwardEngine(wf_config, {}, {})

    windows = engine.split_data(df, df.index[0], df.index[-1])

    assert len(windows) >= 2
    assert windows[0].oos_start == windows[0].is_end + pd.Timedelta(days=1)
    assert windows[1].is_start == windows[0].is_start + pd.Timedelta(days=5)


def test_stitched_equity_skips_duplicate_points():
    wf_config = WFConfig(strategy_id="s01_trailing_ma", is_period_days=180, oos_period_days=60)
    engine = WalkForwardEngine(wf_config, {}, {})

    windows = [
        WindowResult(
            window_id=1,
            is_start=pd.Timestamp("2025-01-01", tz="UTC"),
            is_end=pd.Timestamp("2025-06-29", tz="UTC"),
            oos_start=pd.Timestamp("2025-06-30", tz="UTC"),
            oos_end=pd.Timestamp("2025-08-28", tz="UTC"),
            best_params={},
            param_id="p1",
            is_net_profit_pct=10.0,
            is_max_drawdown_pct=2.0,
            is_total_trades=5,
            oos_net_profit_pct=5.0,
            oos_max_drawdown_pct=1.0,
            oos_total_trades=3,
            oos_equity_curve=[100.0, 110.0, 120.0],
            oos_timestamps=[
                pd.Timestamp("2025-06-30", tz="UTC"),
                pd.Timestamp("2025-07-30", tz="UTC"),
                pd.Timestamp("2025-08-28", tz="UTC"),
            ],
        ),
        WindowResult(
            window_id=2,
            is_start=pd.Timestamp("2025-06-30", tz="UTC"),
            is_end=pd.Timestamp("2025-12-28", tz="UTC"),
            oos_start=pd.Timestamp("2025-12-29", tz="UTC"),
            oos_end=pd.Timestamp("2026-02-26", tz="UTC"),
            best_params={},
            param_id="p2",
            is_net_profit_pct=8.0,
            is_max_drawdown_pct=2.5,
            is_total_trades=4,
            oos_net_profit_pct=7.0,
            oos_max_drawdown_pct=1.2,
            oos_total_trades=2,
            oos_equity_curve=[100.0, 110.0, 130.0],
            oos_timestamps=[
                pd.Timestamp("2025-12-29", tz="UTC"),
                pd.Timestamp("2026-01-29", tz="UTC"),
                pd.Timestamp("2026-02-26", tz="UTC"),
            ],
        ),
    ]

    stitched = engine._build_stitched_oos_equity(windows)

    assert stitched.equity_curve == pytest.approx([100.0, 110.0, 120.0, 132.0, 156.0])
    assert pytest.approx(stitched.final_net_profit_pct, rel=1e-4) == 56.0


def test_wfe_is_annualized():
    wf_config = WFConfig(strategy_id="s01_trailing_ma", is_period_days=180, oos_period_days=60)
    engine = WalkForwardEngine(wf_config, {}, {})

    windows = [
        WindowResult(
            window_id=1,
            is_start=pd.Timestamp("2025-01-01", tz="UTC"),
            is_end=pd.Timestamp("2025-06-29", tz="UTC"),
            oos_start=pd.Timestamp("2025-06-30", tz="UTC"),
            oos_end=pd.Timestamp("2025-08-28", tz="UTC"),
            best_params={},
            param_id="p1",
            is_net_profit_pct=50.0,
            is_max_drawdown_pct=2.0,
            is_total_trades=5,
            oos_net_profit_pct=20.0,
            oos_max_drawdown_pct=1.0,
            oos_total_trades=3,
            oos_equity_curve=[100.0, 120.0],
            oos_timestamps=[pd.Timestamp("2025-06-30", tz="UTC"), pd.Timestamp("2025-08-28", tz="UTC")],
        ),
        WindowResult(
            window_id=2,
            is_start=pd.Timestamp("2025-06-30", tz="UTC"),
            is_end=pd.Timestamp("2025-12-28", tz="UTC"),
            oos_start=pd.Timestamp("2025-12-29", tz="UTC"),
            oos_end=pd.Timestamp("2026-02-26", tz="UTC"),
            best_params={},
            param_id="p2",
            is_net_profit_pct=50.0,
            is_max_drawdown_pct=2.0,
            is_total_trades=5,
            oos_net_profit_pct=20.0,
            oos_max_drawdown_pct=1.0,
            oos_total_trades=3,
            oos_equity_curve=[100.0, 120.0],
            oos_timestamps=[pd.Timestamp("2025-12-29", tz="UTC"), pd.Timestamp("2026-02-26", tz="UTC")],
        ),
    ]

    stitched = engine._build_stitched_oos_equity(windows)

    assert pytest.approx(stitched.wfe, rel=1e-3) == 120.0



def test_export_trades_falls_back_to_config_strategy(monkeypatch, tmp_path):
    """Ensure export_wfa_trades_history uses wf_result.config when strategy_id is missing."""

    class FakeStrategy:
        @staticmethod
        def run(df_slice, params, trade_start_idx):  # noqa: ARG003
            start = df_slice.index[0]
            end = df_slice.index[-1]
            trade = TradeRecord(
                direction="long",
                entry_time=start,
                exit_time=end,
                entry_price=1.0,
                exit_price=1.1,
                size=1.0,
                net_pnl=0.1,
            )
            return StrategyResult(
                trades=[trade],
                equity_curve=[100.0, 110.0],
                balance_curve=[100.0, 110.0],
                timestamps=[start, end],
            )

    def fake_prepare(df_slice, start_time, end_time, warmup_bars):  # noqa: ARG001
        return df_slice, 0

    monkeypatch.setattr("strategies.get_strategy", lambda strategy_id: FakeStrategy)
    monkeypatch.setattr("core.walkforward_engine.prepare_dataset_with_warmup", fake_prepare)
    monkeypatch.setattr("core.backtest_engine.prepare_dataset_with_warmup", fake_prepare)

    index = pd.date_range("2025-01-01", periods=20, freq="h", tz="UTC")
    base_row = {"Open": 1.0, "High": 1.1, "Low": 0.9, "Close": 1.0, "Volume": 100}
    df = pd.DataFrame([base_row for _ in range(len(index))], index=index)

    wf_config = WFConfig(strategy_id="s01_trailing_ma")
    window_result = WindowResult(
        window_id=1,
        is_start=index[0],
        is_end=index[5],
        oos_start=index[6],
        oos_end=index[8],
        best_params={},
        param_id="p1",
        is_net_profit_pct=1.0,
        is_max_drawdown_pct=0.0,
        is_total_trades=1,
        oos_net_profit_pct=1.0,
        oos_max_drawdown_pct=0.0,
        oos_total_trades=1,
        oos_equity_curve=[100.0, 101.0],
        oos_timestamps=[index[6], index[8]],
    )

    stitched = OOSStitchedResult(
        final_net_profit_pct=1.0,
        max_drawdown_pct=0.0,
        total_trades=1,
        wfe=100.0,
        oos_win_rate=100.0,
        equity_curve=[100.0, 101.0],
        timestamps=[index[6], index[8]],
        window_ids=[1, 1],
    )

    wf_result = WFResult(
        config=wf_config,
        windows=[window_result],
        stitched_oos=stitched,
        strategy_id="",  # Force fallback path
        total_windows=1,
        trading_start_date=index[0],
        trading_end_date=index[8],
        warmup_bars=wf_config.warmup_bars,
    )

    files = export_wfa_trades_history(wf_result, df, "OKX:TEST", output_dir=tmp_path)

    assert len(files) == 1
    assert (tmp_path / files[0]).exists()


def test_walkforward_integration_with_sample_data(monkeypatch):
    data_path = Path(__file__).parent.parent / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
    if not data_path.exists():
        pytest.skip("Sample data file not available for integration test.")

    df = load_data(str(data_path))

    strategy_id = "s01_trailing_ma"
    default_params = _build_params_from_config(strategy_id)

    class FakeResult:
        def __init__(self, params):
            self.params = params

    def fake_optuna(self, df_slice, start_time, end_time):  # noqa: ARG001
        return [FakeResult(default_params)]

    monkeypatch.setattr(WalkForwardEngine, "_run_optuna_on_window", fake_optuna)

    wf_config = WFConfig(
        strategy_id=strategy_id,
        is_period_days=60,
        oos_period_days=30,
        warmup_bars=200,
    )
    base_template = {
        "fixed_params": {"dateFilter": False},
        "risk_per_trade_pct": 2.0,
        "contract_size": 0.01,
        "commission_rate": 0.0005,
    }
    engine = WalkForwardEngine(wf_config, base_template, {})

    result, _study_id = engine.run_wf_optimization(df)

    assert result.total_windows >= 2
    assert result.stitched_oos is not None
    assert result.windows
