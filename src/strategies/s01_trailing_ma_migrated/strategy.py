"""
Migrated S01 Trailing MA Strategy - v26
Self-contained implementation that mirrors the legacy engine logic for
bit-exact validation during Phase 7 migration.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from core import metrics
from core.backtest_engine import StrategyResult, TradeRecord
from indicators.ma import get_ma
from indicators.volatility import atr
from strategies.base import BaseStrategy


@dataclass
class S01Params:
    use_backtester: bool = True
    use_date_filter: bool = True
    start: Optional[pd.Timestamp] = None
    end: Optional[pd.Timestamp] = None
    ma_type: str = "EMA"
    ma_length: int = 45
    close_count_long: int = 7
    close_count_short: int = 5
    stop_long_atr: float = 2.0
    stop_long_rr: float = 3.0
    stop_long_lp: int = 2
    stop_short_atr: float = 2.0
    stop_short_rr: float = 3.0
    stop_short_lp: int = 2
    stop_long_max_pct: float = 3.0
    stop_short_max_pct: float = 3.0
    stop_long_max_days: int = 2
    stop_short_max_days: int = 4
    trail_rr_long: float = 1.0
    trail_rr_short: float = 1.0
    trail_ma_long_type: str = "SMA"
    trail_ma_long_length: int = 160
    trail_ma_long_offset: float = -1.0
    trail_ma_short_type: str = "SMA"
    trail_ma_short_length: int = 160
    trail_ma_short_offset: float = 1.0
    risk_per_trade_pct: float = 2.0
    contract_size: float = 0.01
    commission_rate: float = 0.0005
    atr_period: int = 14

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "S01Params":
        """
        Parse S01 parameters from frontend/API payload.
        Maps camelCase (frontend) to snake_case (Python).

        This method directly parses the input dictionary without using
        legacy StrategyParams, ensuring the strategy owns its parameters.

        Args:
            payload: Dictionary with camelCase parameter names from frontend

        Returns:
            S01Params instance with all parameters parsed
        """
        d = payload or {}

        # Date handling (convert string to Timestamp if needed)
        start = d.get("start")
        end = d.get("end")
        if isinstance(start, str):
            start = pd.Timestamp(start, tz="UTC")
        if isinstance(end, str):
            end = pd.Timestamp(end, tz="UTC")

        return cls(
            # Backtester flags
            use_backtester=bool(d.get("backtester", True)),
            use_date_filter=bool(d.get("dateFilter", True)),
            start=start,
            end=end,

            # Main MA parameters
            ma_type=str(d.get("maType", "EMA")),
            ma_length=int(d.get("maLength", 45)),

            # Entry logic
            close_count_long=int(d.get("closeCountLong", 7)),
            close_count_short=int(d.get("closeCountShort", 5)),

            # Stop parameters (ATR-based)
            stop_long_atr=float(d.get("stopLongX", 2.0)),
            stop_long_rr=float(d.get("stopLongRR", 3.0)),
            stop_long_lp=int(d.get("stopLongLP", 2)),
            stop_short_atr=float(d.get("stopShortX", 2.0)),
            stop_short_rr=float(d.get("stopShortRR", 3.0)),
            stop_short_lp=int(d.get("stopShortLP", 2)),

            # Stop parameters (max % and max days)
            stop_long_max_pct=float(d.get("stopLongMaxPct", 3.0)),
            stop_short_max_pct=float(d.get("stopShortMaxPct", 3.0)),
            stop_long_max_days=int(d.get("stopLongMaxDays", 2)),
            stop_short_max_days=int(d.get("stopShortMaxDays", 4)),

            # Trail parameters
            trail_rr_long=float(d.get("trailRRLong", 1.0)),
            trail_rr_short=float(d.get("trailRRShort", 1.0)),
            trail_ma_long_type=str(d.get("trailLongType", "SMA")),
            trail_ma_long_length=int(d.get("trailLongLength", 160)),
            trail_ma_long_offset=float(d.get("trailLongOffset", -1.0)),
            trail_ma_short_type=str(d.get("trailShortType", "SMA")),
            trail_ma_short_length=int(d.get("trailShortLength", 160)),
            trail_ma_short_offset=float(d.get("trailShortOffset", 1.0)),

            # Risk parameters
            risk_per_trade_pct=float(d.get("riskPerTrade", 2.0)),
            contract_size=float(d.get("contractSize", 0.01)),
            commission_rate=float(d.get("commissionRate", 0.0005)),
            atr_period=int(d.get("atrPeriod", 14)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "maType": self.ma_type,
            "maLength": self.ma_length,
            "closeCountLong": self.close_count_long,
            "closeCountShort": self.close_count_short,
            "stopLongX": self.stop_long_atr,
            "stopLongRR": self.stop_long_rr,
            "stopLongLP": self.stop_long_lp,
            "stopShortX": self.stop_short_atr,
            "stopShortRR": self.stop_short_rr,
            "stopShortLP": self.stop_short_lp,
            "stopLongMaxPct": self.stop_long_max_pct,
            "stopShortMaxPct": self.stop_short_max_pct,
            "stopLongMaxDays": self.stop_long_max_days,
            "stopShortMaxDays": self.stop_short_max_days,
            "trailRRLong": self.trail_rr_long,
            "trailRRShort": self.trail_rr_short,
            "trailLongType": self.trail_ma_long_type,
            "trailLongLength": self.trail_ma_long_length,
            "trailLongOffset": self.trail_ma_long_offset,
            "trailShortType": self.trail_ma_short_type,
            "trailShortLength": self.trail_ma_short_length,
            "trailShortOffset": self.trail_ma_short_offset,
            "riskPerTrade": self.risk_per_trade_pct,
            "contractSize": self.contract_size,
            "commissionRate": self.commission_rate,
            "atrPeriod": self.atr_period,
            "backtester": self.use_backtester,
            "dateFilter": self.use_date_filter,
            "start": self.start.isoformat() if self.start is not None else None,
            "end": self.end.isoformat() if self.end is not None else None,
        }


class S01TrailingMAMigrated(BaseStrategy):
    STRATEGY_ID = "s01_trailing_ma_migrated"
    STRATEGY_NAME = "S01 Trailing MA Migrated"
    STRATEGY_VERSION = "v26"

    @staticmethod
    def run(df: pd.DataFrame, params: Dict[str, Any], trade_start_idx: int = 0) -> StrategyResult:
        p = S01Params.from_dict(params)

        if p.use_backtester is False:
            raise ValueError("Backtester is disabled in the provided parameters")

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        ma_series = get_ma(close, p.ma_type, p.ma_length, volume, high, low)
        atr_series = atr(high, low, close, p.atr_period)
        lowest_long = low.rolling(p.stop_long_lp, min_periods=1).min()
        highest_short = high.rolling(p.stop_short_lp, min_periods=1).max()

        trail_ma_long = get_ma(close, p.trail_ma_long_type, p.trail_ma_long_length, volume, high, low)
        trail_ma_short = get_ma(close, p.trail_ma_short_type, p.trail_ma_short_length, volume, high, low)
        if p.trail_ma_long_length > 0:
            trail_ma_long = trail_ma_long * (1 + p.trail_ma_long_offset / 100.0)
        if p.trail_ma_short_length > 0:
            trail_ma_short = trail_ma_short * (1 + p.trail_ma_short_offset / 100.0)

        times = df.index
        if p.use_date_filter:
            time_in_range = np.zeros(len(times), dtype=bool)
            time_in_range[trade_start_idx:] = True
        else:
            time_in_range = np.ones(len(times), dtype=bool)

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
        mtm_curve: List[float] = []

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
                if not trail_activated_long and not math.isnan(entry_price) and not math.isnan(stop_price):
                    activation_price = entry_price + (entry_price - stop_price) * p.trail_rr_long
                    if h >= activation_price:
                        trail_activated_long = True
                        if math.isnan(trail_price_long):
                            trail_price_long = stop_price
                if not math.isnan(trail_price_long) and not np.isnan(trail_long_value):
                    if np.isnan(trail_price_long) or trail_long_value > trail_price_long:
                        trail_price_long = trail_long_value
                if trail_activated_long:
                    if not math.isnan(trail_price_long) and l <= trail_price_long:
                        exit_price = h if trail_price_long > h else trail_price_long
                else:
                    if l <= stop_price:
                        exit_price = stop_price
                    elif h >= target_price:
                        exit_price = target_price
                if exit_price is None and entry_time_long is not None and p.stop_long_max_days > 0:
                    days_in_trade = int(math.floor((time - entry_time_long).total_seconds() / 86400))
                    if days_in_trade >= p.stop_long_max_days:
                        exit_price = c
                if exit_price is not None:
                    gross_pnl = (exit_price - entry_price) * position_size
                    exit_commission = exit_price * position_size * p.commission_rate
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
                if not trail_activated_short and not math.isnan(entry_price) and not math.isnan(stop_price):
                    activation_price = entry_price - (stop_price - entry_price) * p.trail_rr_short
                    if l <= activation_price:
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
                if exit_price is None and entry_time_short is not None and p.stop_short_max_days > 0:
                    days_in_trade = int(math.floor((time - entry_time_short).total_seconds() / 86400))
                    if days_in_trade >= p.stop_short_max_days:
                        exit_price = c
                if exit_price is not None:
                    gross_pnl = (entry_price - exit_price) * position_size
                    exit_commission = exit_price * position_size * p.commission_rate
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

            up_trend = counter_close_trend_long >= p.close_count_long and counter_trade_long == 0
            down_trend = counter_close_trend_short >= p.close_count_short and counter_trade_short == 0

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
                stop_size = atr_value * p.stop_long_atr
                long_stop_price = lowest_value - stop_size
                long_stop_distance = c - long_stop_price
                if long_stop_distance > 0:
                    long_stop_pct = (long_stop_distance / c) * 100
                    if long_stop_pct <= p.stop_long_max_pct or p.stop_long_max_pct <= 0:
                        risk_cash = realized_equity * (p.risk_per_trade_pct / 100)
                        qty = risk_cash / long_stop_distance if long_stop_distance != 0 else 0
                        if p.contract_size > 0:
                            qty = math.floor((qty / p.contract_size)) * p.contract_size
                        if qty > 0:
                            position = 1
                            position_size = qty
                            entry_price = c
                            stop_price = long_stop_price
                            target_price = c + long_stop_distance * p.stop_long_rr
                            trail_price_long = long_stop_price
                            trail_activated_long = False
                            entry_time_long = time
                            entry_commission = entry_price * position_size * p.commission_rate
                            realized_equity -= entry_commission

            if can_open_short and position == 0:
                stop_size = atr_value * p.stop_short_atr
                short_stop_price = highest_value + stop_size
                short_stop_distance = short_stop_price - c
                if short_stop_distance > 0:
                    short_stop_pct = (short_stop_distance / c) * 100
                    if short_stop_pct <= p.stop_short_max_pct or p.stop_short_max_pct <= 0:
                        risk_cash = realized_equity * (p.risk_per_trade_pct / 100)
                        qty = risk_cash / short_stop_distance if short_stop_distance != 0 else 0
                        if p.contract_size > 0:
                            qty = math.floor((qty / p.contract_size)) * p.contract_size
                        if qty > 0:
                            position = -1
                            position_size = qty
                            entry_price = c
                            stop_price = short_stop_price
                            target_price = c - short_stop_distance * p.stop_short_rr
                            trail_price_short = short_stop_price
                            trail_activated_short = False
                            entry_time_short = time
                            entry_commission = entry_price * position_size * p.commission_rate
                            realized_equity -= entry_commission

            mark_to_market = realized_equity
            if position > 0 and not math.isnan(entry_price):
                mark_to_market += (c - entry_price) * position_size
            elif position < 0 and not math.isnan(entry_price):
                mark_to_market += (entry_price - c) * position_size
            realized_curve.append(realized_equity)
            mtm_curve.append(mark_to_market)
            prev_position = position

        timestamps = list(df.index[: len(mtm_curve)])

        result = StrategyResult(
            trades=trades,
            equity_curve=mtm_curve,
            balance_curve=realized_curve,
            timestamps=timestamps,
        )

        basic_metrics = metrics.calculate_basic(result, initial_balance=equity)

        result.net_profit = basic_metrics.net_profit
        result.net_profit_pct = basic_metrics.net_profit_pct
        result.gross_profit = basic_metrics.gross_profit
        result.gross_loss = basic_metrics.gross_loss
        result.max_drawdown = basic_metrics.max_drawdown
        result.max_drawdown_pct = basic_metrics.max_drawdown_pct
        result.total_trades = basic_metrics.total_trades
        result.winning_trades = basic_metrics.winning_trades
        result.losing_trades = basic_metrics.losing_trades

        advanced_metrics = metrics.calculate_advanced(
            result,
            initial_balance=equity,
            risk_free_rate=0.02,
        )

        result.sharpe_ratio = advanced_metrics.sharpe_ratio
        result.profit_factor = advanced_metrics.profit_factor
        result.romad = advanced_metrics.romad
        result.ulcer_index = advanced_metrics.ulcer_index
        result.recovery_factor = advanced_metrics.recovery_factor
        result.consistency_score = advanced_metrics.consistency_score

        return result
