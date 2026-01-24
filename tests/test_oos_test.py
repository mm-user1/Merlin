from pathlib import Path
import json
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.post_process import (
    OOSTestCandidate,
    OOSTestConfig,
    OOSTestResult,
    StressTestResult,
    calculate_period_dates,
    get_oos_test_candidates,
    run_oos_test,
)
from core.storage import (
    generate_study_id,
    get_db_connection,
    load_study_from_db,
    save_oos_test_results,
)


def _seed_study_with_trials(trials):
    study_id = generate_study_id()
    study_name = f"OOS_{study_id[:8]}"
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO studies (study_id, study_name, strategy_id, optimization_mode)
            VALUES (?, ?, ?, ?)
            """,
            (study_id, study_name, "s01_trailing_ma", "optuna"),
        )
        for trial_number, params in trials:
            conn.execute(
                """
                INSERT INTO trials (
                    study_id, trial_number, params_json,
                    net_profit_pct, max_drawdown_pct, total_trades, win_rate,
                    max_consecutive_losses, sharpe_ratio, romad, profit_factor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    study_id,
                    trial_number,
                    json.dumps(params),
                    10.0 + trial_number,
                    5.0,
                    100 + trial_number,
                    50.0,
                    3,
                    1.2,
                    2.0,
                    1.5,
                ),
            )
        conn.commit()
    return study_id


def _make_stress_result(trial_number, status="ok", st_rank=None, source_rank=1):
    return StressTestResult(
        trial_number=trial_number,
        source_rank=source_rank,
        status=status,
        base_net_profit_pct=10.0,
        base_max_drawdown_pct=5.0,
        base_romad=2.0,
        base_sharpe_ratio=1.0,
        profit_retention=1.0,
        romad_retention=1.0,
        profit_worst=1.0,
        profit_lower_tail=1.0,
        profit_median=1.0,
        romad_worst=1.0,
        romad_lower_tail=1.0,
        romad_median=1.0,
        profit_failure_rate=0.0,
        romad_failure_rate=0.0,
        combined_failure_rate=0.0,
        profit_failure_count=0,
        romad_failure_count=0,
        combined_failure_count=0,
        total_perturbations=0,
        failure_threshold=0.7,
        param_worst_ratios={},
        most_sensitive_param=None,
        st_rank=st_rank,
        rank_change=0,
    )


def test_calculate_period_dates_oos_only():
    start = pd.Timestamp("2025-05-01", tz="UTC")
    end = pd.Timestamp("2025-11-20", tz="UTC")
    periods = calculate_period_dates(start, end, ft_period_days=0, oos_period_days=30)
    assert periods.oos_start == "2025-10-22"
    assert periods.oos_end == "2025-11-20"
    assert periods.is_end == "2025-10-21"
    assert periods.ft_start is None
    assert periods.ft_end is None
    assert periods.oos_days == 30


def test_calculate_period_dates_ft_only():
    start = pd.Timestamp("2025-05-01", tz="UTC")
    end = pd.Timestamp("2025-11-20", tz="UTC")
    periods = calculate_period_dates(start, end, ft_period_days=15, oos_period_days=0)
    assert periods.ft_start == "2025-11-06"
    assert periods.ft_end == "2025-11-20"
    assert periods.is_end == "2025-11-05"
    assert periods.oos_start is None
    assert periods.oos_end is None


def test_calculate_period_dates_both():
    start = pd.Timestamp("2025-05-01", tz="UTC")
    end = pd.Timestamp("2025-11-20", tz="UTC")
    periods = calculate_period_dates(start, end, ft_period_days=15, oos_period_days=30)
    assert periods.oos_start == "2025-10-22"
    assert periods.oos_end == "2025-11-20"
    assert periods.ft_start == "2025-10-07"
    assert periods.ft_end == "2025-10-21"
    assert periods.is_end == "2025-10-06"


def test_calculate_period_dates_invalid():
    start = pd.Timestamp("2025-05-01", tz="UTC")
    end = pd.Timestamp("2025-05-10", tz="UTC")
    with pytest.raises(ValueError):
        calculate_period_dates(start, end, ft_period_days=5, oos_period_days=5)


def test_get_oos_candidates_stress_filters_and_rehydrates():
    study_id = _seed_study_with_trials([(1, {"maLength": 50}), (2, {"maLength": 60})])
    st_results = [
        _make_stress_result(1, status="ok", st_rank=1, source_rank=1),
        _make_stress_result(2, status="skipped_bad_base", st_rank=2, source_rank=2),
    ]

    candidates, source = get_oos_test_candidates(
        study_id=study_id,
        top_k=5,
        dsr_results=None,
        ft_results=None,
        st_results=st_results,
    )

    assert source == "stress_test"
    assert len(candidates) == 1
    assert candidates[0].trial_number == 1
    assert candidates[0].params.get("maLength") == 50


def test_get_oos_candidates_fallback_uses_db_order(monkeypatch):
    trials = [
        {"trial_number": 5, "params": {"a": 1}, "net_profit_pct": 10.0, "max_drawdown_pct": 5.0},
        {"trial_number": 2, "params": {"a": 2}, "net_profit_pct": 9.0, "max_drawdown_pct": 6.0},
    ]

    def fake_load_study(_study_id):
        return {"trials": trials}

    import core.storage as storage

    monkeypatch.setattr(storage, "load_study_from_db", fake_load_study)

    candidates, source = get_oos_test_candidates(
        study_id="study",
        top_k=2,
        dsr_results=None,
        ft_results=None,
        st_results=None,
    )

    assert source == "optuna"
    assert [c.trial_number for c in candidates] == [5, 2]


def test_run_oos_test_flow(monkeypatch):
    import core.post_process as pp

    candidates = [
        OOSTestCandidate(
            trial_number=1,
            params={"p": 1},
            source_module="optuna",
            source_rank=1,
            is_metrics={"net_profit_pct": 10.0},
        ),
        OOSTestCandidate(
            trial_number=2,
            params={"p": 2},
            source_module="optuna",
            source_rank=2,
            is_metrics={"net_profit_pct": 10.0},
        ),
    ]

    def fake_worker(
        csv_path,
        strategy_id,
        task_dict,
        oos_start_date,
        oos_end_date,
        warmup_bars,
        is_period_days,
        oos_period_days,
    ):
        profit_deg = 1.1 if task_dict["trial_number"] == 1 else 0.5
        return {
            "trial_number": task_dict["trial_number"],
            "source_rank": task_dict["source_rank"],
            "source_module": task_dict["source_module"],
            "oos_metrics": {
                "net_profit_pct": 5.0,
                "max_drawdown_pct": 2.0,
                "total_trades": 10,
                "win_rate": 50.0,
                "max_consecutive_losses": 2,
                "sharpe_ratio": 1.0,
                "sortino_ratio": 1.2,
                "romad": 2.0,
                "profit_factor": 1.5,
                "ulcer_index": 4.0,
                "sqn": 1.1,
                "consistency_score": 60.0,
            },
            "profit_degradation": profit_deg,
        }

    class DummyPool:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starmap(self, func, args_list):
            return [func(*args) for args in args_list]

    class DummyContext:
        def Pool(self, processes=None):
            return DummyPool()

    monkeypatch.setattr(pp, "_oos_test_worker_entry", fake_worker)
    monkeypatch.setattr(pp.mp, "get_context", lambda *_: DummyContext())

    config = OOSTestConfig(enabled=True, period_days=30, top_k=2)
    results = run_oos_test(
        csv_path="dummy.csv",
        strategy_id="s01_trailing_ma",
        candidates=candidates,
        config=config,
        is_period_days=100,
        oos_period_days=30,
        oos_start_date="2025-10-22",
        oos_end_date="2025-11-20",
        n_workers=1,
    )

    assert results[0].trial_number == 1
    assert results[0].oos_test_rank == 1
    assert results[1].trial_number == 2


def test_save_oos_test_results_roundtrip():
    study_id = _seed_study_with_trials([(1, {"maLength": 50})])
    oos_results = [
        OOSTestResult(
            trial_number=1,
            source_module="forward_test",
            source_rank=3,
            oos_test_net_profit_pct=12.5,
            oos_test_max_drawdown_pct=4.0,
            oos_test_total_trades=50,
            oos_test_win_rate=55.0,
            oos_test_max_consecutive_losses=3,
            oos_test_sharpe_ratio=1.1,
            oos_test_sortino_ratio=1.2,
            oos_test_romad=2.5,
            oos_test_profit_factor=1.6,
            oos_test_ulcer_index=3.0,
            oos_test_sqn=1.4,
            oos_test_consistency_score=65.0,
            oos_test_profit_degradation=0.85,
            oos_test_rank=1,
        )
    ]

    save_oos_test_results(
        study_id,
        oos_results,
        oos_test_enabled=True,
        oos_test_period_days=30,
        oos_test_top_k=10,
        oos_test_start_date="2025-10-22",
        oos_test_end_date="2025-11-20",
        oos_test_source_module="forward_test",
    )

    data = load_study_from_db(study_id)
    assert data["study"]["oos_test_enabled"] == 1
    oos_trials = [t for t in data["trials"] if t.get("oos_test_rank") is not None]
    assert len(oos_trials) == 1
    assert oos_trials[0]["oos_test_rank"] == 1
    assert oos_trials[0]["oos_test_source"] == "forward_test"
