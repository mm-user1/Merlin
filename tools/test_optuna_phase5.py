"""Test Optuna optimization after Phase 5 (indicators extraction)."""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.optuna_engine import (  # noqa: E402
    OptunaConfig,
    OptunaOptimizer,
    OptimizationConfig,
)
from core.backtest_engine import load_data  # noqa: E402


def main() -> None:
    data_path = Path(__file__).parent.parent / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
    df = load_data(str(data_path))

    print(f"Loaded {len(df)} bars")

    optuna_config = OptunaConfig(
        target="score",
        budget_mode="trials",
        n_trials=10,
        enable_pruning=True,
        sampler="tpe",
    )

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
            "closeCountLong": (5, 15, 1),
            "closeCountShort": (3, 9, 1),
        },
        ma_types_trend=["SMA", "EMA", "HMA"],
        ma_types_trail_long=["SMA", "EMA", "HMA"],
        ma_types_trail_short=["SMA", "EMA", "HMA"],
        lock_trail_types=False,
        fixed_params={
            "maType": "EMA",
            "maLength": 50,
            "dateFilter": True,
            "start": "2025-06-15 00:00:00",
            "end": "2025-11-15 00:00:00",
            "backtester": True,
        },
        score_config=None,
    )

    print("Starting Optuna optimization (10 trials, 3 MA types)...")
    optimizer = OptunaOptimizer(base_config, optuna_config)
    results = optimizer.optimize()

    print(f"\nCompleted {len(results)} trials")

    if not results:
        print("\n❌ No optimization results returned")
        raise SystemExit(1)

    best_result = max(results, key=lambda r: r.score)
    print("\nBest trial:")
    print(f"  MA Type: {best_result.ma_type}")
    print(f"  Score: {best_result.score:.2f}")
    print(f"  Net Profit: {best_result.net_profit_pct:.2f}%")

    print("\n✅ Phase 5 Optuna test PASSED")


if __name__ == "__main__":
    main()
