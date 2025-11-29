import pandas as pd

from strategies.base import BaseStrategy
from core.backtest_engine import StrategyResult


class S02Test(BaseStrategy):
    STRATEGY_ID = "s02_test"
    STRATEGY_NAME = "S02 Test"
    STRATEGY_VERSION = "v1"

    @staticmethod
    def run(df, params, trade_start_idx=0):
        return StrategyResult(
            trades=[],
            equity_curve=[0.0],
            balance_curve=[0.0],
            timestamps=[pd.Timestamp("1970-01-01", tz="UTC")],
        )
