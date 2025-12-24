import hashlib
import logging
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.walkforward_engine import (
    AggregatedResult,
    WFConfig,
    WFResult,
    WalkForwardEngine,
    WindowResult,
    WindowSplit,
)
from core.export import (
    export_wfa_trades_history,
    export_wf_results_csv,
)
from core.backtest_engine import StrategyResult, TradeRecord
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
    wf_config = WFConfig(strategy_id=strategy_id)
    params = _build_params_from_config(strategy_id)
    engine = WalkForwardEngine(wf_config, {}, {})
    param_id = engine._create_param_id(params)

    windows = [
        WindowSplit(
            window_id=1,
            is_start=0,
            is_end=10,
            gap_start=10,
            gap_end=12,
            oos_start=12,
            oos_end=15,
        )
    ]
    window_results = [
        WindowResult(
            window_id=1,
            top_params=[params],
            is_profits=[1.0],
            oos_profits=[2.0],
            oos_drawdowns=[0.0],
            oos_trades=[5],
        )
    ]
    aggregated = [
        AggregatedResult(
            param_id=param_id,
            params=params,
            window_ids=[1],
            avg_oos_profit=2.0,
            avg_is_profit=1.0,
            oos_win_rate=1.0,
            oos_profits=[2.0],
            is_profits=[1.0],
        )
    ]
    result = WFResult(
        config=wf_config,
        windows=windows,
        window_results=window_results,
        aggregated=aggregated,
        forward_profits=[3.0],
        forward_params=[params],
        wf_zone_start=0,
        wf_zone_end=10,
        forward_start=10,
        forward_end=15,
        strategy_id=strategy_id,
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


def test_wf_csv_export_includes_all_s01_params():
    result, _, param_id = _build_wf_result("s01_trailing_ma")

    csv_content = export_wf_results_csv(result)
    config = get_strategy_config("s01_trailing_ma")
    parameter_labels = [
        spec.get("label", name) if isinstance(spec, dict) else name
        for name, spec in config.get("parameters", {}).items()
    ]

    assert param_id in csv_content
    for label in parameter_labels:
        assert label in csv_content


def test_wf_csv_export_includes_all_s04_params():
    result, _, param_id = _build_wf_result("s04_stochrsi")

    csv_content = export_wf_results_csv(result)
    config = get_strategy_config("s04_stochrsi")
    parameter_labels = [
        spec.get("label", name) if isinstance(spec, dict) else name
        for name, spec in config.get("parameters", {}).items()
    ]

    assert param_id in csv_content
    for label in parameter_labels:
        assert label in csv_content


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
    windows = [
        WindowSplit(window_id=1, is_start=0, is_end=5, gap_start=5, gap_end=6, oos_start=6, oos_end=8)
    ]
    window_results = [
        WindowResult(
            window_id=1,
            top_params=[{}],
            is_profits=[1.0],
            oos_profits=[1.0],
            oos_drawdowns=[0.0],
            oos_trades=[1],
        )
    ]
    aggregated = [
        AggregatedResult(
            param_id="p1",
            params={},
            window_ids=[1],
            avg_oos_profit=1.0,
            avg_is_profit=1.0,
            oos_win_rate=1.0,
            oos_profits=[1.0],
            is_profits=[1.0],
        )
    ]

    wf_result = WFResult(
        config=wf_config,
        windows=windows,
        window_results=window_results,
        aggregated=aggregated,
        forward_profits=[1.0],
        forward_params=[{}],
        wf_zone_start=0,
        wf_zone_end=5,
        forward_start=8,
        forward_end=10,
        strategy_id="",  # Force fallback path
        warmup_bars=wf_config.warmup_bars,
    )

    files = export_wfa_trades_history(wf_result, df, "OKX:TEST", top_k=1, output_dir=tmp_path)

    assert len(files) == 1
    assert (tmp_path / files[0]).exists()
