import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import IO, Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from backtesting import _stats
from indicators.ma import (
    VALID_MA_TYPES,
    alma,
    dema,
    ema,
    get_ma,
    hma,
    kama,
    sma,
    t3,
    tma,
    vwap,
    vwma,
    wma,
)
from indicators.volatility import atr

from . import metrics

DEFAULT_ATR_PERIOD = 14


CSVSource = Union[str, Path, IO[str], IO[bytes]]


@dataclass
class TradeRecord:
    direction: Optional[str] = None
    entry_time: Optional[pd.Timestamp] = None
    exit_time: Optional[pd.Timestamp] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    size: float = 0.0
    net_pnl: float = 0.0
    profit_pct: Optional[float] = None
    side: Optional[str] = None


@dataclass
class StrategyResult:
    """
    Complete result of a strategy backtest.

    Stores both raw curves and calculated metrics to keep orchestration and
    calculation concerns separate.
    """

    trades: List[TradeRecord]
    equity_curve: List[float]
    balance_curve: List[float]
    timestamps: List[pd.Timestamp]

    net_profit: float = 0.0
    net_profit_pct: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    romad: Optional[float] = None  # Return Over Maximum Drawdown
    ulcer_index: Optional[float] = None
    recovery_factor: Optional[float] = None
    consistency_score: Optional[float] = None  # % of profitable months

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "net_profit": self.net_profit,
            "net_profit_pct": self.net_profit_pct,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "equity_curve": self.equity_curve,
            "balance_curve": self.balance_curve,
            "timestamps": [ts.isoformat() if hasattr(ts, "isoformat") else ts for ts in self.timestamps],
        }

        optional_metrics = {
            "sharpe_ratio": self.sharpe_ratio,
            "profit_factor": self.profit_factor,
            "romad": self.romad,
            "ulcer_index": self.ulcer_index,
            "recovery_factor": self.recovery_factor,
            "consistency_score": self.consistency_score,
        }

        for key, value in optional_metrics.items():
            if value is not None:
                data[key] = value

        return data


@dataclass
class StrategyParams:
    use_backtester: bool
    use_date_filter: bool
    start: Optional[pd.Timestamp]
    end: Optional[pd.Timestamp]
    ma_type: str
    ma_length: int
    close_count_long: int
    close_count_short: int
    stop_long_atr: float
    stop_long_rr: float
    stop_long_lp: int
    stop_short_atr: float
    stop_short_rr: float
    stop_short_lp: int
    stop_long_max_pct: float
    stop_short_max_pct: float
    stop_long_max_days: int
    stop_short_max_days: int
    trail_rr_long: float
    trail_rr_short: float
    trail_ma_long_type: str
    trail_ma_long_length: int
    trail_ma_long_offset: float
    trail_ma_short_type: str
    trail_ma_short_length: int
    trail_ma_short_offset: float
    risk_per_trade_pct: float
    contract_size: float
    commission_rate: float = 0.0005
    atr_period: int = DEFAULT_ATR_PERIOD

    @staticmethod
    def _parse_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        value_str = str(value).strip().lower()
        if value_str in {"true", "1", "yes", "y", "on"}:
            return True
        if value_str in {"false", "0", "no", "n", "off"}:
            return False
        return default

    @staticmethod
    def _parse_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_int(value: Any, default: int) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[pd.Timestamp]:
        if value in (None, ""):
            return None
        try:
            ts = pd.Timestamp(value)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            else:
                ts = ts.tz_convert("UTC")
            return ts
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "StrategyParams":
        payload = payload or {}

        ma_type = str(payload.get("maType", "EMA")).upper()
        if ma_type not in VALID_MA_TYPES:
            raise ValueError(f"Unsupported MA type: {ma_type}")
        trail_ma_long_type = str(payload.get("trailLongType", "SMA")).upper()
        if trail_ma_long_type not in VALID_MA_TYPES:
            raise ValueError(f"Unsupported trail MA long type: {trail_ma_long_type}")
        trail_ma_short_type = str(payload.get("trailShortType", "SMA")).upper()
        if trail_ma_short_type not in VALID_MA_TYPES:
            raise ValueError(f"Unsupported trail MA short type: {trail_ma_short_type}")

        return cls(
            use_backtester=cls._parse_bool(payload.get("backtester", True), True),
            use_date_filter=cls._parse_bool(payload.get("dateFilter", True), True),
            start=cls._parse_timestamp(payload.get("start")),
            end=cls._parse_timestamp(payload.get("end")),
            ma_type=ma_type,
            ma_length=max(cls._parse_int(payload.get("maLength", 45), 0), 0),
            close_count_long=max(cls._parse_int(payload.get("closeCountLong", 7), 0), 0),
            close_count_short=max(cls._parse_int(payload.get("closeCountShort", 5), 0), 0),
            stop_long_atr=cls._parse_float(payload.get("stopLongX", 2.0), 2.0),
            stop_long_rr=cls._parse_float(payload.get("stopLongRR", 3.0), 3.0),
            stop_long_lp=max(cls._parse_int(payload.get("stopLongLP", 2), 0), 1),
            stop_short_atr=cls._parse_float(payload.get("stopShortX", 2.0), 2.0),
            stop_short_rr=cls._parse_float(payload.get("stopShortRR", 3.0), 3.0),
            stop_short_lp=max(cls._parse_int(payload.get("stopShortLP", 2), 0), 1),
            stop_long_max_pct=max(cls._parse_float(payload.get("stopLongMaxPct", 3.0), 3.0), 0.0),
            stop_short_max_pct=max(cls._parse_float(payload.get("stopShortMaxPct", 3.0), 3.0), 0.0),
            stop_long_max_days=max(cls._parse_int(payload.get("stopLongMaxDays", 2), 0), 0),
            stop_short_max_days=max(cls._parse_int(payload.get("stopShortMaxDays", 4), 0), 0),
            trail_rr_long=max(cls._parse_float(payload.get("trailRRLong", 1.0), 1.0), 0.0),
            trail_rr_short=max(cls._parse_float(payload.get("trailRRShort", 1.0), 1.0), 0.0),
            trail_ma_long_type=trail_ma_long_type,
            trail_ma_long_length=max(cls._parse_int(payload.get("trailLongLength", 160), 0), 0),
            trail_ma_long_offset=cls._parse_float(payload.get("trailLongOffset", -1.0), -1.0),
            trail_ma_short_type=trail_ma_short_type,
            trail_ma_short_length=max(cls._parse_int(payload.get("trailShortLength", 160), 0), 0),
            trail_ma_short_offset=cls._parse_float(payload.get("trailShortOffset", 1.0), 1.0),
            risk_per_trade_pct=max(cls._parse_float(payload.get("riskPerTrade", 2.0), 2.0), 0.0),
            contract_size=max(cls._parse_float(payload.get("contractSize", 0.01), 0.01), 0.0),
            commission_rate=max(cls._parse_float(payload.get("commissionRate", 0.0005), 0.0005), 0.0),
            atr_period=max(cls._parse_int(payload.get("atrPeriod", DEFAULT_ATR_PERIOD), DEFAULT_ATR_PERIOD), 1),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["start"] = self.start.isoformat() if self.start is not None else None
        data["end"] = self.end.isoformat() if self.end is not None else None
        return data


def load_data(csv_source: CSVSource) -> pd.DataFrame:
    df = pd.read_csv(csv_source)
    if "time" not in df.columns:
        raise ValueError("CSV must include a 'time' column with timestamps in seconds")
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True, errors="coerce")
    if df["time"].isna().all():
        raise ValueError("Failed to parse timestamps from 'time' column")
    df = df.set_index("time").sort_index()
    expected_cols = {"open", "high", "low", "close", "Volume", "volume"}
    available_cols = set(df.columns)
    price_cols = {"open", "high", "low", "close"}
    if not price_cols.issubset({col.lower() for col in available_cols}):
        raise ValueError("CSV must include open, high, low, close columns")
    volume_col = None
    for col in ("Volume", "volume", "VOL", "vol"):
        if col in df.columns:
            volume_col = col
            break
    if volume_col is None:
        raise ValueError("CSV must include a volume column")
    renamed = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        volume_col: "Volume",
    }
    normalized_cols = {col: renamed.get(col.lower(), col) for col in df.columns}
    df = df.rename(columns=normalized_cols)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def compute_max_drawdown(equity_curve: pd.Series) -> float:
    equity_curve = equity_curve.ffill()
    drawdown = 1 - equity_curve / equity_curve.cummax()
    _, peak_dd = _stats.compute_drawdown_duration_peaks(drawdown)
    if peak_dd.isna().all():
        return 0.0
    return peak_dd.max() * 100


def prepare_dataset_with_warmup(
    df: pd.DataFrame,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
    warmup_bars: int,
) -> tuple[pd.DataFrame, int]:
    """
    Trim dataset with warmup period for MA calculations.

    Args:
        df: Full OHLCV DataFrame with datetime index
        start: Start date for trading (None = use all data)
        end: End date for trading (None = use all data)
        warmup_bars: Number of bars to include before the start date

    Returns:
        Tuple of (trimmed_df, trade_start_idx)
        - trimmed_df: DataFrame with warmup + trading period
        - trade_start_idx: Index where trading should begin (warmup ends)
    """
    try:
        normalized_warmup = int(warmup_bars)
    except (TypeError, ValueError):
        normalized_warmup = 0

    normalized_warmup = max(0, normalized_warmup)

    # If no date filtering, use entire dataset
    if start is None and end is None:
        return df.copy(), 0

    # Find indices for start and end dates
    times = df.index

    # Determine start index
    if start is not None:
        # Find first index >= start
        start_mask = times >= start
        if not start_mask.any():
            # Start date is after all data
            print(f"Warning: Start date {start} is after all available data")
            return df.iloc[0:0].copy(), 0  # Return empty df
        start_idx = int(start_mask.argmax())
    else:
        start_idx = 0

    # Determine end index
    if end is not None:
        # Find last index <= end
        end_mask = times <= end
        if not end_mask.any():
            # End date is before all data
            print(f"Warning: End date {end} is before all available data")
            return df.iloc[0:0].copy(), 0  # Return empty df
        # Get the last True value
        end_idx = len(end_mask) - 1 - int(end_mask[::-1].argmax())
        end_idx += 1  # Include the end bar
    else:
        end_idx = len(df)

    # Calculate warmup start (go back from start_idx)
    warmup_start_idx = max(0, start_idx - normalized_warmup)

    # Check if we have enough data
    actual_warmup = start_idx - warmup_start_idx
    if actual_warmup < normalized_warmup:
        print(f"Warning: Insufficient warmup data. Need {normalized_warmup} bars, "
              f"only have {actual_warmup} bars available")

    # Trim the dataframe
    trimmed_df = df.iloc[warmup_start_idx:end_idx].copy()

    # Trade start index is where actual trading begins (after warmup)
    trade_start_idx = start_idx - warmup_start_idx

    return trimmed_df, trade_start_idx


def prepare_dataset_with_warmup_legacy(
    df: pd.DataFrame,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
    params: StrategyParams,
) -> tuple[pd.DataFrame, int]:
    """
    Backward-compatible wrapper that calculates warmup from StrategyParams.

    This preserves existing behaviour for callers that rely on StrategyParams
    to determine the warmup period.
    """

    max_ma_length = max(
        params.ma_length,
        params.trail_ma_long_length,
        params.trail_ma_short_length,
    )
    required_warmup = max(500, int(max_ma_length * 1.5))
    return prepare_dataset_with_warmup(df, start, end, required_warmup)


def run_strategy(df: pd.DataFrame, params: StrategyParams, trade_start_idx: int = 0) -> StrategyResult:
    if params.use_backtester is False:
        raise ValueError("Backtester is disabled in the provided parameters")

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    ma_series = get_ma(close, params.ma_type, params.ma_length, volume, high, low)
    atr_series = atr(high, low, close, params.atr_period)
    lowest_long = low.rolling(params.stop_long_lp, min_periods=1).min()
    highest_short = high.rolling(params.stop_short_lp, min_periods=1).max()

    trail_ma_long = get_ma(close, params.trail_ma_long_type, params.trail_ma_long_length, volume, high, low)
    trail_ma_short = get_ma(close, params.trail_ma_short_type, params.trail_ma_short_length, volume, high, low)
    if params.trail_ma_long_length > 0:
        trail_ma_long = trail_ma_long * (1 + params.trail_ma_long_offset / 100.0)
    if params.trail_ma_short_length > 0:
        trail_ma_short = trail_ma_short * (1 + params.trail_ma_short_offset / 100.0)

    times = df.index
    if params.use_date_filter:
        # Use trade_start_idx to define trading zone
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
    mtm_curve: List[float] = []  # Mark-to-market equity (includes unrealized PnL)

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
                activation_price = entry_price + (entry_price - stop_price) * params.trail_rr_long
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
            if exit_price is None and entry_time_long is not None and params.stop_long_max_days > 0:
                days_in_trade = int(math.floor((time - entry_time_long).total_seconds() / 86400))
                if days_in_trade >= params.stop_long_max_days:
                    exit_price = c
            if exit_price is not None:
                gross_pnl = (exit_price - entry_price) * position_size
                exit_commission = exit_price * position_size * params.commission_rate
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
                activation_price = entry_price - (stop_price - entry_price) * params.trail_rr_short
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
            if exit_price is None and entry_time_short is not None and params.stop_short_max_days > 0:
                days_in_trade = int(math.floor((time - entry_time_short).total_seconds() / 86400))
                if days_in_trade >= params.stop_short_max_days:
                    exit_price = c
            if exit_price is not None:
                gross_pnl = (entry_price - exit_price) * position_size
                exit_commission = exit_price * position_size * params.commission_rate
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

        up_trend = counter_close_trend_long >= params.close_count_long and counter_trade_long == 0
        down_trend = counter_close_trend_short >= params.close_count_short and counter_trade_short == 0

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
            stop_size = atr_value * params.stop_long_atr
            long_stop_price = lowest_value - stop_size
            long_stop_distance = c - long_stop_price
            if long_stop_distance > 0:
                long_stop_pct = (long_stop_distance / c) * 100
                if long_stop_pct <= params.stop_long_max_pct or params.stop_long_max_pct <= 0:
                    risk_cash = realized_equity * (params.risk_per_trade_pct / 100)
                    qty = risk_cash / long_stop_distance if long_stop_distance != 0 else 0
                    if params.contract_size > 0:
                        qty = math.floor((qty / params.contract_size)) * params.contract_size
                    if qty > 0:
                        position = 1
                        position_size = qty
                        entry_price = c
                        stop_price = long_stop_price
                        target_price = c + long_stop_distance * params.stop_long_rr
                        trail_price_long = long_stop_price
                        trail_activated_long = False
                        entry_time_long = time
                        entry_commission = entry_price * position_size * params.commission_rate
                        realized_equity -= entry_commission

        if can_open_short and position == 0:
            stop_size = atr_value * params.stop_short_atr
            short_stop_price = highest_value + stop_size
            short_stop_distance = short_stop_price - c
            if short_stop_distance > 0:
                short_stop_pct = (short_stop_distance / c) * 100
                if short_stop_pct <= params.stop_short_max_pct or params.stop_short_max_pct <= 0:
                    risk_cash = realized_equity * (params.risk_per_trade_pct / 100)
                    qty = risk_cash / short_stop_distance if short_stop_distance != 0 else 0
                    if params.contract_size > 0:
                        qty = math.floor((qty / params.contract_size)) * params.contract_size
                    if qty > 0:
                        position = -1
                        position_size = qty
                        entry_price = c
                        stop_price = short_stop_price
                        target_price = c - short_stop_distance * params.stop_short_rr
                        trail_price_short = short_stop_price
                        trail_activated_short = False
                        entry_time_short = time
                        entry_commission = entry_price * position_size * params.commission_rate
                        realized_equity -= entry_commission

        mark_to_market = realized_equity
        if position > 0 and not math.isnan(entry_price):
            mark_to_market += (c - entry_price) * position_size
        elif position < 0 and not math.isnan(entry_price):
            mark_to_market += (entry_price - c) * position_size
        realized_curve.append(realized_equity)
        mtm_curve.append(mark_to_market)  # Save MTM equity for Ulcer Index calculation
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
