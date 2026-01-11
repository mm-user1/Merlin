"""
Core engines for the S01 TrailingMA backtesting and optimization platform.

This package contains the three main engines:
- backtest_engine: Single backtest execution
- optuna_engine: Bayesian optimization using Optuna
- walkforward_engine: Walk-Forward Analysis orchestrator

These engines are the heart of the platform and should be imported
by interface layers (UI, CLI) but should not depend on them.
"""

__version__ = "2.0.0"  # Architecture migration version

# Expose main engines at package level for convenience
from .backtest_engine import (
    CSVSource,
    TradeRecord,
    StrategyResult,
    load_data,
    prepare_dataset_with_warmup,
)

from .optuna_engine import (
    OptunaConfig,
    OptimizationResult,
    run_optuna_optimization,
)

from .walkforward_engine import (
    WFConfig,
    WFResult,
    WalkForwardEngine,
)

from .export import (
    export_trades_csv,
    _extract_symbol_from_csv_filename,
)

from .metrics import (
    BasicMetrics,
    AdvancedMetrics,
    WFAMetrics,
    calculate_basic,
    calculate_advanced,
    calculate_for_wfa,
    enrich_strategy_result,
)

__all__ = [
    # backtest_engine exports
    "CSVSource",
    "TradeRecord",
    "StrategyResult",
    "load_data",
    "prepare_dataset_with_warmup",

    # optuna_engine exports
    "OptunaConfig",
    "OptimizationResult",
    "run_optuna_optimization",

    # walkforward_engine exports
    "WFConfig",
    "WFResult",
    "WalkForwardEngine",

    # export
    "export_trades_csv",
    "_extract_symbol_from_csv_filename",

    # metrics
    "BasicMetrics",
    "AdvancedMetrics",
    "WFAMetrics",
    "calculate_basic",
    "calculate_advanced",
    "calculate_for_wfa",
    "enrich_strategy_result",
]
