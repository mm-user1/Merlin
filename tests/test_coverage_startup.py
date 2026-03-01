import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.optuna_engine import (  # noqa: E402
    OptimizationConfig,
    OptunaConfig,
    OptunaOptimizer,
    SamplerConfig,
    _analyze_coverage_requirements,
    _generate_coverage_trials,
    _latin_hypercube_points,
)


def _base_config() -> OptimizationConfig:
    return OptimizationConfig(
        csv_file="dummy.csv",
        strategy_id="s01_trailing_ma",
        enabled_params={},
        param_ranges={},
        param_types={},
        fixed_params={},
    )


def test_latin_hypercube_points_shape_range_and_intervals():
    points = _latin_hypercube_points(n_dims=3, n_samples=20, seed=42)
    assert len(points) == 20
    assert all(len(point) == 3 for point in points)
    assert all(0.0 <= value <= 1.0 for point in points for value in point)

    # Each interval [i/N, (i+1)/N) appears exactly once per dimension.
    for dim_idx in range(3):
        bins = [min(19, int(point[dim_idx] * 20)) for point in points]
        assert sorted(bins) == list(range(20))


def test_generate_coverage_trials_is_deterministic():
    search_space = {
        "maType": {"type": "categorical", "choices": ["EMA", "SMA", "HMA", "WMA"]},
        "trailType": {"type": "categorical", "choices": ["EMA", "SMA"]},
        "maLen": {"type": "int", "low": 10, "high": 50, "step": 5},
        "stopX": {"type": "float", "low": 0.5, "high": 2.0, "step": 0.1},
    }

    first = _generate_coverage_trials(search_space, 24)
    second = _generate_coverage_trials(search_space, 24)
    assert first == second


def test_generate_coverage_trials_balances_main_axis_and_respects_bounds():
    search_space = {
        "maType": {"type": "categorical", "choices": ["EMA", "SMA", "HMA", "WMA"]},
        "trailType": {"type": "categorical", "choices": ["EMA", "SMA"]},
        "maLen": {"type": "int", "low": 10, "high": 50, "step": 5},
        "stopX": {"type": "float", "low": 0.5, "high": 2.0, "step": 0.1},
    }

    trials = _generate_coverage_trials(search_space, 10)
    assert len(trials) == 10

    ma_counts = {}
    for trial in trials:
        for key in ("maType", "trailType", "maLen", "stopX"):
            assert key in trial
        ma_counts[trial["maType"]] = ma_counts.get(trial["maType"], 0) + 1
        assert trial["trailType"] in {"EMA", "SMA"}
        assert 10 <= int(trial["maLen"]) <= 50
        assert (int(trial["maLen"]) - 10) % 5 == 0
        assert 0.5 <= float(trial["stopX"]) <= 2.0

    assert max(ma_counts.values()) - min(ma_counts.values()) <= 1


def test_analyze_coverage_requirements_nsga_recommendation_uses_population():
    search_space = {
        "maType": {
            "type": "categorical",
            "choices": ["EMA", "SMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"],
        },
        "stopX": {"type": "float", "low": 0.5, "high": 5.0},
        "atrX": {"type": "float", "low": 0.5, "high": 5.0},
        "trailX": {"type": "float", "low": 0.5, "high": 5.0},
    }

    report_tpe = _analyze_coverage_requirements(search_space, sampler_type="tpe", population_size=50)
    report_nsga = _analyze_coverage_requirements(search_space, sampler_type="nsga2", population_size=50)

    assert report_tpe["n_min"] == 11
    assert report_tpe["n_rec"] == 23
    assert report_nsga["n_min"] == 11
    assert report_nsga["n_rec"] == 50


def test_optuna_optimizer_sets_tpe_startup_to_zero_in_coverage_mode():
    optuna_cfg = OptunaConfig(
        objectives=["net_profit_pct"],
        sampler_config=SamplerConfig(sampler_type="tpe", n_startup_trials=20),
        warmup_trials=20,
        coverage_mode=True,
    )
    optimizer = OptunaOptimizer(_base_config(), optuna_cfg)
    assert optimizer.sampler_config.n_startup_trials == 0


def test_optuna_summary_contains_coverage_warning_message():
    base_config = _base_config()
    optuna_cfg = OptunaConfig(
        objectives=["net_profit_pct"],
        sampler_config=SamplerConfig(sampler_type="tpe", n_startup_trials=20),
        warmup_trials=5,
        coverage_mode=True,
    )
    optimizer = OptunaOptimizer(base_config, optuna_cfg)
    optimizer.start_time = time.time() - 1
    optimizer.trial_results = []
    optimizer._coverage_report = {
        "n_min": 11,
        "n_rec": 44,
        "main_axis_name": "maType",
        "main_axis_options": 11,
    }

    optimizer._finalize_results()
    summary = getattr(base_config, "optuna_summary", {})
    assert summary.get("initial_search_mode") == "coverage"
    assert summary.get("initial_search_trials") == 5
    assert summary.get("coverage_warning") == "Need more initial trials (min: 11, recommended: 44)"
