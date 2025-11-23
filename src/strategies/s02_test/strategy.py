from strategies.base import BaseStrategy
from backtest_engine import StrategyResult


class S02Test(BaseStrategy):
    STRATEGY_ID = "s02_test"
    STRATEGY_NAME = "S02 Test"
    STRATEGY_VERSION = "v1"

    @staticmethod
    def run(df, params, trade_start_idx=0):
        return StrategyResult(
            net_profit_pct=0.0,
            max_drawdown_pct=0.0,
            total_trades=0,
            trades=[],
        )
