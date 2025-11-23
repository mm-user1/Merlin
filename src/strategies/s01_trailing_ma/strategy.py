"""
S01 Trailing MA Strategy - v26 Ultralight
Moving Average crossover with trailing stops and ATR-based position sizing
"""

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from backtest_engine import (
    StrategyResult,
    TradeRecord,
    atr,
    compute_max_drawdown,
    get_ma,
)
from strategies.base import BaseStrategy


class S01TrailingMA(BaseStrategy):
    """
    S01 Trailing MA Strategy Implementation

    Entry Logic:
    - Long: Close crosses above MA for N consecutive bars (closeCountLong)
    - Short: Close crosses below MA for N consecutive bars (closeCountShort)

    Exit Logic:
    - ATR-based stops
    - Risk/Reward targets
    - Trailing MA exits
    - Max % loss stops
    - Max days in trade stops
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
        trade_start_idx: int = 0
    ) -> StrategyResult:
        """
        Execute S01 Trailing MA strategy.

        IMPORTANT: This is a direct copy of the logic from backtest_engine.run_strategy()
        adapted to work with Dict[str, Any] params instead of StrategyParams dataclass.
        """

        ma_type = str(params.get("maType", "EMA")).upper()
        ma_length = max(int(params.get("maLength", 45)), 0)
        close_count_long = max(int(params.get("closeCountLong", 7)), 0)
        close_count_short = max(int(params.get("closeCountShort", 5)), 0)

        stop_long_atr = float(params.get("stopLongX", 2.0))
        stop_long_rr = float(params.get("stopLongRR", 3.0))
        stop_long_lp = max(int(params.get("stopLongLP", 2)), 1)
        stop_short_atr = float(params.get("stopShortX", 2.0))
        stop_short_rr = float(params.get("stopShortRR", 3.0))
        stop_short_lp = max(int(params.get("stopShortLP", 2)), 1)

        stop_long_max_pct = max(float(params.get("stopLongMaxPct", 3.0)), 0.0)
        stop_short_max_pct = max(float(params.get("stopShortMaxPct", 3.0)), 0.0)
        stop_long_max_days = max(int(params.get("stopLongMaxDays", 2)), 0)
        stop_short_max_days = max(int(params.get("stopShortMaxDays", 4)), 0)

        trail_rr_long = float(params.get("trailRRLong", 1.0))
        trail_rr_short = float(params.get("trailRRShort", 1.0))
        trail_ma_long_type = str(params.get("trailLongType", "SMA")).upper()
        trail_ma_long_length = max(int(params.get("trailLongLength", 160)), 0)
        trail_ma_long_offset = float(params.get("trailLongOffset", -1.0))
        trail_ma_short_type = str(params.get("trailShortType", "SMA")).upper()
        trail_ma_short_length = max(int(params.get("trailShortLength", 160)), 0)
        trail_ma_short_offset = float(params.get("trailShortOffset", 1.0))

        risk_per_trade_pct = max(float(params.get("riskPerTrade", 2.0)), 0.0)
        contract_size = max(float(params.get("contractSize", 0.01)), 0.0)
        commission_rate = max(float(params.get("commissionRate", 0.0005)), 0.0)
        atr_period = max(int(params.get("atrPeriod", 14)), 1)

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]
        times = df.index

        ma_series = get_ma(close, ma_type, ma_length, volume, high, low)
        atr_series = atr(high, low, close, atr_period)
        lowest_long = low.rolling(stop_long_lp, min_periods=1).min()
        highest_short = high.rolling(stop_short_lp, min_periods=1).max()

        trail_ma_long = get_ma(close, trail_ma_long_type, trail_ma_long_length, volume, high, low)
        trail_ma_short = get_ma(close, trail_ma_short_type, trail_ma_short_length, volume, high, low)
        if trail_ma_long_length > 0:
            trail_ma_long = trail_ma_long * (1 + trail_ma_long_offset / 100.0)
        if trail_ma_short_length > 0:
            trail_ma_short = trail_ma_short * (1 + trail_ma_short_offset / 100.0)

        time_in_range = np.zeros(len(times), dtype=bool)
        time_in_range[trade_start_idx:] = True

        equity = 100.0
        realized_equity = equity
        position = 0
        prev_position = 0
        position_size = 0.0
        entry_price = math.nan
        stop_price = math.nan
        target_price = math.nan
        trail_price_long = math.nan
        trail_price_short = math.nan
        trail_activated_long = False
        trail_activated_short = False
        entry_time_long: Optional[pd.Timestamp] = None
        entry_time_short: Optional[pd.Timestamp] = None
        entry_commission = 0.0

        counter_close_trend_long = 0
        counter_close_trend_short = 0
        counter_trade_long = 0
        counter_trade_short = 0

        trades: List[TradeRecord] = []
        realized_curve: List[float] = []

        for i in range(len(df)):
            time = times[i]
            c = close.iat[i]
            h = high.iat[i]
            l = low.iat[i]
            ma_value = ma_series.iat[i]
            atr_value = atr_series.iat[i]
            lowest_value = lowest_long.iat[i]
            highest_value = highest_short.iat[i]
            trail_long_value = trail_ma_long.iat[i]
            trail_short_value = trail_ma_short.iat[i]

            if not np.isnan(ma_value):
                if c > ma_value:
                    counter_close_trend_long += 1
                    counter_close_trend_short = 0
                elif c < ma_value:
                    counter_close_trend_short += 1
                    counter_close_trend_long = 0
                else:
                    counter_close_trend_long = 0
                    counter_close_trend_short = 0

            if position > 0:
                counter_trade_long = 1
                counter_trade_short = 0
            elif position < 0:
                counter_trade_long = 0
                counter_trade_short = 1

            exit_price: Optional[float] = None
            if position > 0:
                if (
                    not trail_activated_long
                    and not math.isnan(entry_price)
                    and not math.isnan(stop_price)
                ):
                    activation_price = entry_price + (entry_price - stop_price) * trail_rr_long
                    if l <= activation_price:
                        trail_activated_long = True
                        if math.isnan(trail_price_long):
                            trail_price_long = stop_price
                if not math.isnan(trail_price_long) and not np.isnan(trail_long_value):
                    if np.isnan(trail_price_long) or trail_long_value < trail_price_long:
                        trail_price_long = trail_long_value
                if trail_activated_long:
                    if not math.isnan(trail_price_long) and l <= trail_price_long:
                        exit_price = h if trail_price_long > h else trail_price_long
                else:
                    if l <= stop_price:
                        exit_price = stop_price
                    elif h >= target_price:
                        exit_price = target_price
                if exit_price is None and entry_time_long is not None and stop_long_max_days > 0:
                    days_in_trade = int(math.floor((time - entry_time_long).total_seconds() / 86400))
                    if days_in_trade >= stop_long_max_days:
                        exit_price = c
                if exit_price is not None:
                    gross_pnl = (exit_price - entry_price) * position_size
                    exit_commission = exit_price * position_size * commission_rate
                    net_pnl = gross_pnl - exit_commission - entry_commission
                    realized_equity += gross_pnl - exit_commission
                    entry_value = entry_price * position_size
                    profit_pct = (net_pnl / entry_value * 100.0) if entry_value else None
                    trades.append(
                        TradeRecord(
                            direction="long",
                            side="LONG",
                            entry_time=entry_time_long,
                            exit_time=time,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            size=position_size,
                            net_pnl=net_pnl,
                            profit_pct=profit_pct,
                        )
                    )
                    position = 0
                    position_size = 0.0
                    entry_price = math.nan
                    stop_price = math.nan
                    target_price = math.nan
                    trail_price_long = math.nan
                    trail_activated_long = False
                    entry_time_long = None
                    entry_commission = 0.0

            elif position < 0:
                if (
                    not trail_activated_short
                    and not math.isnan(entry_price)
                    and not math.isnan(stop_price)
                ):
                    activation_price = entry_price - (stop_price - entry_price) * trail_rr_short
                    if h >= activation_price:
                        trail_activated_short = True
                        if math.isnan(trail_price_short):
                            trail_price_short = stop_price
                if not math.isnan(trail_price_short) and not np.isnan(trail_short_value):
                    if np.isnan(trail_price_short) or trail_short_value < trail_price_short:
                        trail_price_short = trail_short_value
                if trail_activated_short:
                    if not math.isnan(trail_price_short) and h >= trail_price_short:
                        exit_price = l if trail_price_short < l else trail_price_short
                else:
                    if h >= stop_price:
                        exit_price = stop_price
                    elif l <= target_price:
                        exit_price = target_price
                if exit_price is None and entry_time_short is not None and stop_short_max_days > 0:
                    days_in_trade = int(math.floor((time - entry_time_short).total_seconds() / 86400))
                    if days_in_trade >= stop_short_max_days:
                        exit_price = c
                if exit_price is not None:
                    gross_pnl = (entry_price - exit_price) * position_size
                    exit_commission = exit_price * position_size * commission_rate
                    net_pnl = gross_pnl - exit_commission - entry_commission
                    realized_equity += gross_pnl - exit_commission
                    entry_value = entry_price * position_size
                    profit_pct = (net_pnl / entry_value * 100.0) if entry_value else None
                    trades.append(
                        TradeRecord(
                            direction="short",
                            side="SHORT",
                            entry_time=entry_time_short,
                            exit_time=time,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            size=position_size,
                            net_pnl=net_pnl,
                            profit_pct=profit_pct,
                        )
                    )
                    position = 0
                    position_size = 0.0
                    entry_price = math.nan
                    stop_price = math.nan
                    target_price = math.nan
                    trail_price_short = math.nan
                    trail_activated_short = False
                    entry_time_short = None
                    entry_commission = 0.0

            up_trend = counter_close_trend_long >= close_count_long and counter_trade_long == 0
            down_trend = counter_close_trend_short >= close_count_short and counter_trade_short == 0

            can_open_long = (
                up_trend
                and position == 0
                and prev_position == 0
                and time_in_range[i]
                and not np.isnan(atr_value)
                and not np.isnan(lowest_value)
            )
            can_open_short = (
                down_trend
                and position == 0
                and prev_position == 0
                and time_in_range[i]
                and not np.isnan(atr_value)
                and not np.isnan(highest_value)
            )

            if can_open_long:
                stop_size = atr_value * stop_long_atr
                long_stop_price = lowest_value - stop_size
                long_stop_distance = c - long_stop_price
                if long_stop_distance > 0:
                    long_stop_pct = (long_stop_distance / c) * 100
                    if long_stop_pct <= stop_long_max_pct or stop_long_max_pct <= 0:
                        risk_cash = realized_equity * (risk_per_trade_pct / 100)
                        qty = risk_cash / long_stop_distance if long_stop_distance != 0 else 0
                        if contract_size > 0:
                            qty = math.floor((qty / contract_size)) * contract_size
                        if qty > 0:
                            position = 1
                            position_size = qty
                            entry_price = c
                            stop_price = long_stop_price
                            target_price = c + long_stop_distance * stop_long_rr
                            trail_price_long = long_stop_price
                            trail_activated_long = False
                            entry_time_long = time
                            entry_commission = entry_price * position_size * commission_rate
                            realized_equity -= entry_commission

            if can_open_short and position == 0:
                stop_size = atr_value * stop_short_atr
                short_stop_price = highest_value + stop_size
                short_stop_distance = short_stop_price - c
                if short_stop_distance > 0:
                    short_stop_pct = (short_stop_distance / c) * 100
                    if short_stop_pct <= stop_short_max_pct or stop_short_max_pct <= 0:
                        risk_cash = realized_equity * (risk_per_trade_pct / 100)
                        qty = risk_cash / short_stop_distance if short_stop_distance != 0 else 0
                        if contract_size > 0:
                            qty = math.floor((qty / contract_size)) * contract_size
                        if qty > 0:
                            position = -1
                            position_size = qty
                            entry_price = c
                            stop_price = short_stop_price
                            target_price = c - short_stop_distance * stop_short_rr
                            trail_price_short = short_stop_price
                            trail_activated_short = False
                            entry_time_short = time
                            entry_commission = entry_price * position_size * commission_rate
                            realized_equity -= entry_commission

            mark_to_market = realized_equity
            if position > 0 and not math.isnan(entry_price):
                mark_to_market += (c - entry_price) * position_size
            elif position < 0 and not math.isnan(entry_price):
                mark_to_market += (entry_price - c) * position_size
            realized_curve.append(realized_equity)
            prev_position = position

        equity_series = pd.Series(realized_curve, index=df.index[: len(realized_curve)])
        net_profit_pct = ((realized_equity - equity) / equity) * 100
        max_drawdown_pct = compute_max_drawdown(equity_series)
        total_trades = len(trades)

        from backtest_engine import calculate_advanced_metrics

        advanced_metrics = calculate_advanced_metrics(
            equity_curve=realized_curve,
            time_index=df.index[: len(realized_curve)],
            trades=trades,
            net_profit_pct=net_profit_pct,
            max_drawdown_pct=max_drawdown_pct,
        )

        return StrategyResult(
            net_profit_pct=net_profit_pct,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            trades=trades,
            sharpe_ratio=advanced_metrics["sharpe_ratio"],
            profit_factor=advanced_metrics["profit_factor"],
            romad=advanced_metrics["romad"],
            ulcer_index=advanced_metrics["ulcer_index"],
            recovery_factor=advanced_metrics["recovery_factor"],
            consistency_score=advanced_metrics["consistency_score"],
        )
