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
    StrategyParams,
    DEFAULT_ATR_PERIOD,
    load_data,
    prepare_dataset_with_warmup,
    prepare_dataset_with_warmup_legacy,
    run_strategy,
)

from .optuna_engine import (
    OptunaConfig,
    run_optuna_optimization,
)

from .walkforward_engine import (
    WFConfig,
    WFResult,
    WalkForwardEngine,
    export_wfa_trades_history,
    export_wf_results_csv,
    generate_wfa_output_filename,
    _extract_symbol_from_csv_filename,
)

from .export import (
    CSV_COLUMN_SPECS,
    export_optuna_results,
    export_trades_csv,
    export_trades_zip,
    export_wfa_summary,
)

__all__ = [
    # backtest_engine exports
    "CSVSource",
    "TradeRecord",
    "StrategyResult",
    "StrategyParams",
    "DEFAULT_ATR_PERIOD",
    "load_data",
    "prepare_dataset_with_warmup",
    "prepare_dataset_with_warmup_legacy",
    "run_strategy",

    # optuna_engine exports
    "OptunaConfig",
    "run_optuna_optimization",

    # walkforward_engine exports
    "WFConfig",
    "WFResult",
    "WalkForwardEngine",
    "export_wfa_trades_history",
    "export_wf_results_csv",
    "generate_wfa_output_filename",
    "_extract_symbol_from_csv_filename",

    # export
    "CSV_COLUMN_SPECS",
    "export_optuna_results",
    "export_trades_csv",
    "export_trades_zip",
    "export_wfa_summary",
]
