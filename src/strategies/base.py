"""
Base Strategy Class
All trading strategies must inherit from this base class.
"""

from typing import Any, Dict

import pandas as pd

from core.backtest_engine import StrategyResult


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
