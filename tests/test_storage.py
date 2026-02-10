import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.storage import (
    get_db_connection,
    load_study_from_db,
    load_wfa_window_trials,
    save_wfa_study_to_db,
)
from core.walkforward_engine import OOSStitchedResult, WFConfig, WFResult, WindowResult


def _build_dummy_wfa_result():
    wf_config = WFConfig(strategy_id="s01_trailing_ma", is_period_days=10, oos_period_days=5)
    params = {"maType": "EMA", "maLength": 50, "closeCountLong": 7}

    window = WindowResult(
        window_id=1,
        is_start=pd.Timestamp("2025-01-01", tz="UTC"),
        is_end=pd.Timestamp("2025-01-10", tz="UTC"),
        oos_start=pd.Timestamp("2025-01-11", tz="UTC"),
        oos_end=pd.Timestamp("2025-01-15", tz="UTC"),
        best_params=params,
        param_id="EMA 50_test",
        is_net_profit_pct=1.0,
        is_max_drawdown_pct=0.5,
        is_total_trades=1,
        oos_net_profit_pct=2.0,
        oos_max_drawdown_pct=0.7,
        oos_total_trades=2,
        oos_equity_curve=[100.0, 102.0],
        oos_timestamps=[
            pd.Timestamp("2025-01-11", tz="UTC"),
            pd.Timestamp("2025-01-15", tz="UTC"),
        ],
        is_best_trial_number=1,
        is_equity_curve=[100.0, 101.0],
        is_timestamps=[
            pd.Timestamp("2025-01-01", tz="UTC"),
            pd.Timestamp("2025-01-10", tz="UTC"),
        ],
        best_params_source="optuna_is",
        available_modules=["optuna_is"],
        is_pareto_optimal=True,
        constraints_satisfied=False,
        is_win_rate=50.0,
        oos_win_rate=60.0,
        optuna_is_trials=[
            {
                "trial_number": 1,
                "params": params,
                "param_id": "EMA 50_test",
                "net_profit_pct": 1.0,
                "max_drawdown_pct": 0.5,
                "total_trades": 1,
                "win_rate": 50.0,
                "is_selected": True,
            }
        ],
    )

    stitched = OOSStitchedResult(
        final_net_profit_pct=2.0,
        max_drawdown_pct=0.7,
        total_trades=2,
        wfe=100.0,
        oos_win_rate=60.0,
        equity_curve=[100.0, 102.0],
        timestamps=[
            pd.Timestamp("2025-01-11", tz="UTC"),
            pd.Timestamp("2025-01-15", tz="UTC"),
        ],
        window_ids=[1, 1],
    )

    wf_result = WFResult(
        config=wf_config,
        windows=[window],
        stitched_oos=stitched,
        strategy_id="s01_trailing_ma",
        total_windows=1,
        trading_start_date=window.is_start,
        trading_end_date=window.oos_end,
        warmup_bars=wf_config.warmup_bars,
    )
    return wf_result


def test_wfa_window_trials_table_created():
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='wfa_window_trials'"
        )
        assert cursor.fetchone() is not None


def test_wfa_window_new_columns():
    with get_db_connection() as conn:
        cursor = conn.execute("PRAGMA table_info(wfa_windows)")
        columns = {row["name"] for row in cursor.fetchall()}
    assert "best_params_source" in columns
    assert "available_modules" in columns
    assert "optimization_start_date" in columns
    assert "ft_start_date" in columns
    assert "is_pareto_optimal" in columns
    assert "constraints_satisfied" in columns
    assert "trigger_type" in columns
    assert "cusum_final" in columns
    assert "cusum_threshold" in columns
    assert "dd_threshold" in columns
    assert "oos_actual_days" in columns


def test_studies_stitched_columns():
    with get_db_connection() as conn:
        cursor = conn.execute("PRAGMA table_info(studies)")
        columns = {row["name"] for row in cursor.fetchall()}
    assert "stitched_oos_equity_curve" in columns
    assert "stitched_oos_timestamps_json" in columns
    assert "stitched_oos_window_ids_json" in columns
    assert "stitched_oos_net_profit_pct" in columns
    assert "stitched_oos_max_drawdown_pct" in columns
    assert "stitched_oos_total_trades" in columns
    assert "stitched_oos_win_rate" in columns
    assert "adaptive_mode" in columns
    assert "max_oos_period_days" in columns
    assert "min_oos_trades" in columns
    assert "check_interval_trades" in columns
    assert "cusum_threshold" in columns
    assert "dd_threshold_multiplier" in columns
    assert "inactivity_multiplier" in columns


def test_save_wfa_study_with_trials():
    wf_result = _build_dummy_wfa_result()
    study_id = save_wfa_study_to_db(
        wf_result=wf_result,
        config={},
        csv_file_path="",
        start_time=0.0,
        score_config=None,
    )

    study_data = load_study_from_db(study_id)
    assert study_data is not None
    assert study_data["study"]["optimization_mode"] == "wfa"
    assert study_data["windows"]

    window = study_data["windows"][0]
    assert window.get("best_params_source") == "optuna_is"
    assert window.get("is_pareto_optimal") is True
    assert window.get("constraints_satisfied") is False


def test_load_wfa_window_trials():
    wf_result = _build_dummy_wfa_result()
    study_id = save_wfa_study_to_db(
        wf_result=wf_result,
        config={},
        csv_file_path="",
        start_time=0.0,
        score_config=None,
    )
    window_id = f"{study_id}_w1"
    modules = load_wfa_window_trials(window_id)
    assert "optuna_is" in modules
    assert modules["optuna_is"]
    assert modules["optuna_is"][0]["trial_number"] == 1
