"""
S01 Trailing MA Strategy - v26 Ultralight
Moving Average crossover with trailing stops and ATR-based position sizing
"""

from typing import Any, Dict

import pandas as pd

from backtest_engine import StrategyParams, StrategyResult, run_strategy
from strategies.base import BaseStrategy


class S01TrailingMA(BaseStrategy):
    """
    S01 Trailing MA Strategy Implementation
    """

    STRATEGY_ID = "s01_trailing_ma"
    STRATEGY_NAME = "S01 Trailing MA"
    STRATEGY_VERSION = "v26"

    @staticmethod
    def calculate_indicators(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, pd.Series]:
        """
        Calculate all indicators needed for the strategy.

        Note: This method is not used in MVP (no caching optimization).
        Kept for future compatibility.
        """
        return {}

    @staticmethod
    def run(
        df: pd.DataFrame,
        params: Dict[str, Any],
        trade_start_idx: int = 0,
    ) -> StrategyResult:
        """
        Execute S01 Trailing MA strategy via the legacy backtest engine implementation.
        """

        parsed_params = StrategyParams.from_dict(params)
        return run_strategy(df, parsed_params, trade_start_idx)
