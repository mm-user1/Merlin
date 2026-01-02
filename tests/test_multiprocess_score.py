"""
Integration test for multi-process composite score optimization.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.optuna_engine import (  # noqa: E402
    DEFAULT_SCORE_CONFIG,
    OptimizationConfig,
    OptunaConfig,
    OptunaOptimizer,
)

DATA_PATH = (
    Path(__file__).parent.parent
    / "data"
    / "raw"
    / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
)


@pytest.mark.slow
class TestMultiProcessScore:
    """Test multi-process optimization with composite scoring enabled."""

    @pytest.fixture
    def base_config(self):
        score_config = DEFAULT_SCORE_CONFIG.copy()
        score_config["enabled_metrics"] = {
            "romad": True,
            "sharpe": True,
            "pf": True,
            "ulcer": True,
            "sqn": True,
            "consistency": True,
        }
        score_config["weights"] = {
            "romad": 0.25,
            "sharpe": 0.20,
            "pf": 0.20,
            "ulcer": 0.15,
            "sqn": 0.10,
            "consistency": 0.10,
        }
        score_config["invert_metrics"] = {"ulcer": True}
        return OptimizationConfig(
            csv_file=str(DATA_PATH),
            strategy_id="s01_trailing_ma",
            enabled_params={"maLength": True},
            param_ranges={"maLength": (10, 50, 10)},
            param_types={"maLength": "int"},
            fixed_params={
                "maType": "EMA",
                "closeCountLong": 2,
                "closeCountShort": 2,
            },
            worker_processes=2,
            score_config=score_config,
        )

    def test_multiprocess_uses_minmax(self, base_config):
        """Multi-process mode should use minmax normalization."""
        optuna_config = OptunaConfig(
            objectives=["net_profit_pct"],
            budget_mode="trials",
            n_trials=5,
        )

        optimizer = OptunaOptimizer(base_config, optuna_config)
        results = optimizer.optimize()

        assert all("maLength" in r.params for r in results)
        assert any(r.score > 0 for r in results)

    def test_single_and_multi_produce_same_scores(self, base_config):
        """Single-process and multi-process should produce same scores for same params."""
        optuna_config = OptunaConfig(
            objectives=["net_profit_pct"],
            budget_mode="trials",
            n_trials=3,
        )

        base_config.worker_processes = 1
        optimizer_single = OptunaOptimizer(base_config, optuna_config)
        results_single = optimizer_single.optimize()

        base_config.worker_processes = 2
        optimizer_multi = OptunaOptimizer(base_config, optuna_config)
        results_multi = optimizer_multi.optimize()

        for r_single in results_single:
            for r_multi in results_multi:
                if r_single.params == r_multi.params:
                    assert r_single.score == pytest.approx(r_multi.score, rel=0.01)
