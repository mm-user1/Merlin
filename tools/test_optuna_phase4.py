"""Test Optuna optimization after Phase 4 (metrics extraction)."""
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.backtest_engine import load_data  # noqa: E402
from core.optuna_engine import (  # noqa: E402
    OptunaConfig,
    OptimizationConfig,
    run_optuna_optimization,
)


def main() -> None:
    data_path = Path(__file__).parent.parent / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
    df = load_data(str(data_path))
    print(f"Loaded {len(df)} bars for optimization")

    base_config = OptimizationConfig(
        csv_file=str(data_path),
        worker_processes=1,
        contract_size=0.01,
        commission_rate=0.0005,
        risk_per_trade_pct=2.0,
        atr_period=14,
        enabled_params={
            "closeCountLong": True,
            "closeCountShort": True,
        },
        param_ranges={
            "closeCountLong": (5, 15, 5),
            "closeCountShort": (3, 9, 3),
        },
        ma_types_trend=["HMA"],
        ma_types_trail_long=["HMA"],
        ma_types_trail_short=["HMA"],
        lock_trail_types=False,
        fixed_params={
            "maType": "HMA",
            "maLength": 50,
            "dateFilter": True,
            "start": "2025-06-15 00:00:00",
            "end": "2025-11-15 00:00:00",
            "backtester": True,
        },
        score_config=None,
    )

    optuna_config = OptunaConfig(
        target="score",
        budget_mode="trials",
        n_trials=2,
        time_limit=60,
        enable_pruning=False,
        sampler="tpe",
    )

    optimizer_results = run_optuna_optimization(base_config, optuna_config)
    print(f"Completed {len(optimizer_results)} trials")

    if optimizer_results:
        best_result = max(optimizer_results, key=lambda r: float(r.score))
        print("Best trial summary:")
        print(f"  Score: {best_result.score:.4f}")
        print(f"  Net Profit %: {best_result.net_profit_pct:.2f}%")
        if best_result.sharpe_ratio is not None:
            print(f"  Sharpe: {best_result.sharpe_ratio:.4f}")
        if best_result.romad is not None:
            print(f"  RoMaD: {best_result.romad:.4f}")


if __name__ == "__main__":
    main()
