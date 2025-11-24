"""
Base Strategy Class
All trading strategies must inherit from this base class.
"""

from typing import Any, Dict

import pandas as pd

from backtest_engine import StrategyResult


class BaseStrategy:
    """
    Abstract base class for all trading strategies.

    All strategy implementations must define:
    - STRATEGY_ID: unique identifier (e.g., "s01_trailing_ma")
    - STRATEGY_NAME: human-readable name (e.g., "S01 Trailing MA")
    - STRATEGY_VERSION: version string (e.g., "v26")
    - run(): main trading logic implementation

    Optionally can define:
    - calculate_indicators(): for caching optimization (not used in MVP)
    """

    STRATEGY_ID = "base"
    STRATEGY_NAME = "Base Strategy"
    STRATEGY_VERSION = "v0"

    @staticmethod
    def camelcase_to_snake_case(name: str) -> str:
        """
        Convert camelCase parameter names (UI/config.json) to snake_case.

        This helper keeps the optimizer engines strategy-agnostic by
        automatically deriving internal parameter names from a strategy's
        configuration file.

        Examples:
            maType -> ma_type
            closeCountLong -> close_count_long
            trailLongType -> trail_long_type

        Args:
            name: Parameter name in camelCase format.

        Returns:
            Parameter name converted to snake_case.
        """

        import re

        step_one = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
        with_acronyms = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step_one)
        return with_acronyms.lower()

    @classmethod
    def get_parameter_mapping(cls, config: Dict[str, Any]) -> Dict[str, str]:
        """
        Build a snake_case → camelCase mapping for strategy parameters.

        Args:
            config: Strategy configuration loaded from ``config.json``.

        Returns:
            Dictionary mapping optimizer/internal parameter names (snake_case)
            to the frontend names expected by ``StrategyParams`` (camelCase).
        """

        parameters = config.get("parameters", {}) if isinstance(config, dict) else {}
        mapping: Dict[str, str] = {}

        for frontend_name in parameters.keys():
            internal_name = cls.camelcase_to_snake_case(frontend_name)
            mapping[internal_name] = frontend_name

        return mapping

    @staticmethod
    def calculate_indicators(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, pd.Series]:
        """
        Calculate technical indicators for the strategy.

        This method is optional and used for caching in optimization.
        Not implemented in MVP version.

        Args:
            df: OHLCV DataFrame
            params: Strategy parameters

        Returns:
            Dictionary of indicator name -> pd.Series
            Example: {"rsi": pd.Series(...), "bb_upper": pd.Series(...)}
        """
        return {}

    @staticmethod
    def run(
        df: pd.DataFrame,
        params: Dict[str, Any],
        trade_start_idx: int = 0
    ) -> StrategyResult:
        """
        Execute the trading strategy.

        Args:
            df: OHLCV DataFrame with columns [Open, High, Low, Close, Volume]
            params: Dictionary of strategy parameters
            trade_start_idx: Index to start trading (after warmup period)

        Returns:
            StrategyResult object with metrics and trade history
        """
        raise NotImplementedError("Strategy must implement run() method")
