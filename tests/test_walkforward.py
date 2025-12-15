import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.walkforward_engine import (
    AggregatedResult,
    WFConfig,
    WFResult,
    WalkForwardEngine,
    WindowResult,
    WindowSplit,
    export_wf_results_csv,
)
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
            appearances="1/1",
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
