"""
Post Process module for optimization validation.

Phase 1: Forward Test (FT) implementation
- Auto FT after Optuna optimization (TRUE HOLDOUT)
- Manual testing from Results page
- WFA integration
"""
from __future__ import annotations

import logging
import multiprocessing as mp
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# Configuration Dataclasses
# ============================================================


@dataclass
class PostProcessConfig:
    """Configuration for Post Process forward test."""

    enabled: bool = False
    ft_period_days: int = 30
    top_k: int = 20
    sort_metric: str = "profit_degradation"  # or "ft_romad"
    warmup_bars: int = 1000


@dataclass
class FTResult:
    """Forward test result for a single trial."""

    trial_number: int
    optuna_rank: int
    params: dict

    is_net_profit_pct: float
    is_max_drawdown_pct: float
    is_total_trades: int
    is_win_rate: float
    is_sharpe_ratio: Optional[float]
    is_romad: Optional[float]
    is_profit_factor: Optional[float]

    ft_net_profit_pct: float
    ft_max_drawdown_pct: float
    ft_total_trades: int
    ft_win_rate: float
    ft_sharpe_ratio: Optional[float]
    ft_sortino_ratio: Optional[float]
    ft_romad: Optional[float]
    ft_profit_factor: Optional[float]
    ft_ulcer_index: Optional[float]
    ft_sqn: Optional[float]
    ft_consistency_score: Optional[float]

    profit_degradation: float
    max_dd_change: float
    romad_change: float
    sharpe_change: float
    pf_change: float

    ft_rank: Optional[int] = None
    rank_change: Optional[int] = None


# ============================================================
# Timestamp Handling (Timezone-Aware)
# ============================================================


def _parse_timestamp(value: Any) -> Optional[pd.Timestamp]:
    """
    Parse timestamp to tz-aware UTC.

    Uses same pattern as optuna_engine._parse_timestamp() to ensure
    consistency with Merlin's tz-aware DataFrame index.
    """
    if value in (None, ""):
        return None
    try:
        ts = pd.Timestamp(value)
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts


# ============================================================
# Worker Function (module-level for multiprocessing)
# ============================================================


def _ft_worker_entry(
    csv_path: str,
    strategy_id: str,
    task_dict: Dict[str, Any],
    ft_start_date: str,
    ft_end_date: str,
    warmup_bars: int,
    is_period_days: int,
    ft_period_days: int,
) -> Optional[Dict[str, Any]]:
    """
    Entry point for FT worker process.

    Follows optuna_engine pattern: load data and strategy inside worker.
    """
    from .backtest_engine import load_data
    from . import metrics
    from strategies import get_strategy

    worker_logger = logging.getLogger(__name__)
    trial_number = task_dict["trial_number"]

    try:
        df = load_data(csv_path)
        strategy_class = get_strategy(strategy_id)

        ft_start = _parse_timestamp(ft_start_date)
        ft_end = _parse_timestamp(ft_end_date)

        if ft_start is None or ft_end is None:
            raise ValueError(f"Invalid FT dates: start={ft_start_date}, end={ft_end_date}")

        ft_start_idx = df.index.get_indexer([ft_start], method="bfill")[0]
        if ft_start_idx < 0 or ft_start_idx >= len(df):
            raise ValueError(
                f"FT start date {ft_start_date} not found in data range "
                f"{df.index.min()} to {df.index.max()}"
            )

        warmup_start_idx = max(0, ft_start_idx - warmup_bars)
        df_ft_with_warmup = df.iloc[warmup_start_idx:]
        df_ft_with_warmup = df_ft_with_warmup[df_ft_with_warmup.index <= ft_end]

        if len(df_ft_with_warmup) == 0:
            raise ValueError(f"No data in FT period {ft_start_date} to {ft_end_date}")

        trade_start_idx = ft_start_idx - warmup_start_idx

        params = task_dict["params"]
        result = strategy_class.run(df_ft_with_warmup, params, trade_start_idx)

        basic = metrics.calculate_basic(result, 100.0)
        advanced = metrics.calculate_advanced(result, 100.0)

        ft_metrics = {
            "net_profit_pct": basic.net_profit_pct,
            "max_drawdown_pct": basic.max_drawdown_pct,
            "total_trades": basic.total_trades,
            "win_rate": basic.win_rate,
            "sharpe_ratio": advanced.sharpe_ratio,
            "sortino_ratio": advanced.sortino_ratio,
            "romad": advanced.romad,
            "profit_factor": advanced.profit_factor,
            "ulcer_index": advanced.ulcer_index,
            "sqn": advanced.sqn,
            "consistency_score": advanced.consistency_score,
        }

        is_metrics = task_dict["is_metrics"]
        comparison = calculate_comparison_metrics(
            is_metrics, ft_metrics, is_period_days, ft_period_days
        )

        return {
            "trial_number": trial_number,
            "optuna_rank": task_dict["optuna_rank"],
            "params": params,
            "is_metrics": is_metrics,
            "ft_metrics": ft_metrics,
            "comparison": comparison,
        }

    except Exception as exc:
        worker_logger.warning("FT failed for trial %s: %s", trial_number, exc)
        return None


# ============================================================
# Core Functions
# ============================================================


def calculate_ft_dates(
    user_start: pd.Timestamp,
    user_end: pd.Timestamp,
    ft_period_days: int,
) -> Tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, int, int]:
    """
    Calculate IS/FT date boundaries within USER-SELECTED range.

    Returns:
        (is_end, ft_start, ft_end, is_days, ft_days)
    """
    total_days = (user_end - user_start).days

    if ft_period_days >= total_days:
        raise ValueError(
            f"FT period ({ft_period_days} days) must be less than "
            f"user-selected range ({total_days} days). "
            f"User range: {user_start.date()} to {user_end.date()}"
        )

    ft_start = user_end - pd.Timedelta(days=ft_period_days)
    is_end = ft_start
    is_days = (is_end - user_start).days
    ft_days = ft_period_days

    return is_end, ft_start, user_end, is_days, ft_days


def calculate_profit_degradation(
    is_profit: float,
    ft_profit: float,
    is_period_days: int,
    ft_period_days: int,
) -> float:
    """
    Calculate annualized profit degradation ratio.

    Returns ratio where 1.0 = no degradation, <1.0 = worse in FT.
    """
    if is_period_days <= 0 or ft_period_days <= 0:
        return 0.0

    is_annual = is_profit * (365 / is_period_days)
    ft_annual = ft_profit * (365 / ft_period_days)

    if is_annual <= 0:
        return 0.0

    return ft_annual / is_annual


def calculate_comparison_metrics(
    is_metrics: Dict[str, Any],
    ft_metrics: Dict[str, Any],
    is_period_days: int,
    ft_period_days: int,
) -> Dict[str, Any]:
    """
    Calculate comparison between IS and FT metrics.
    """
    profit_deg = calculate_profit_degradation(
        is_metrics.get("net_profit_pct", 0),
        ft_metrics.get("net_profit_pct", 0),
        is_period_days,
        ft_period_days,
    )

    return {
        "profit_degradation": profit_deg,
        "max_dd_change": (ft_metrics.get("max_drawdown_pct") or 0)
        - (is_metrics.get("max_drawdown_pct") or 0),
        "romad_change": (ft_metrics.get("romad") or 0) - (is_metrics.get("romad") or 0),
        "sharpe_change": (ft_metrics.get("sharpe_ratio") or 0)
        - (is_metrics.get("sharpe_ratio") or 0),
        "pf_change": (ft_metrics.get("profit_factor") or 0)
        - (is_metrics.get("profit_factor") or 0),
    }


def calculate_is_period_days(config_json: Dict[str, Any]) -> Optional[int]:
    """Calculate IS period days from stored config_json.fixed_params."""
    if not isinstance(config_json, dict):
        return None
    fixed = config_json.get("fixed_params") or {}
    start = _parse_timestamp(fixed.get("start"))
    end = _parse_timestamp(fixed.get("end"))
    if start is None or end is None:
        return None
    return max(0, (end - start).days)


def _build_is_metrics(result: Any) -> Dict[str, Any]:
    return {
        "net_profit_pct": getattr(result, "net_profit_pct", 0.0),
        "max_drawdown_pct": getattr(result, "max_drawdown_pct", 0.0),
        "total_trades": getattr(result, "total_trades", 0),
        "win_rate": getattr(result, "win_rate", 0.0),
        "sharpe_ratio": getattr(result, "sharpe_ratio", None),
        "romad": getattr(result, "romad", None),
        "profit_factor": getattr(result, "profit_factor", None),
    }


def run_forward_test(
    *,
    csv_path: str,
    strategy_id: str,
    optuna_results: Sequence[Any],
    config: PostProcessConfig,
    is_period_days: int,
    ft_period_days: int,
    ft_start_date: str,
    ft_end_date: str,
    n_workers: int,
) -> List[FTResult]:
    """
    Run forward test for top-K optuna results.
    """
    if not config.enabled:
        return []

    candidates = list(optuna_results or [])
    if not candidates:
        return []

    top_k = max(1, int(config.top_k or 1))
    top_k = min(top_k, len(candidates))

    tasks: List[Dict[str, Any]] = []
    for idx, result in enumerate(candidates[:top_k], 1):
        trial_number = getattr(result, "optuna_trial_number", None) or idx
        tasks.append(
            {
                "trial_number": int(trial_number),
                "optuna_rank": idx,
                "params": dict(getattr(result, "params", {}) or {}),
                "is_metrics": _build_is_metrics(result),
            }
        )

    max_workers = max(1, min(int(n_workers or 1), len(tasks)))
    ctx = mp.get_context("spawn")
    results: List[FTResult] = []

    with ctx.Pool(processes=max_workers) as pool:
        worker_args = [
            (
                csv_path,
                strategy_id,
                task,
                ft_start_date,
                ft_end_date,
                int(config.warmup_bars),
                int(is_period_days),
                int(ft_period_days),
            )
            for task in tasks
        ]
        for payload in pool.starmap(_ft_worker_entry, worker_args):
            if not payload:
                continue
            is_metrics = payload["is_metrics"]
            ft_metrics = payload["ft_metrics"]
            comparison = payload["comparison"]
            results.append(
                FTResult(
                    trial_number=int(payload["trial_number"]),
                    optuna_rank=int(payload["optuna_rank"]),
                    params=payload["params"],
                    is_net_profit_pct=is_metrics.get("net_profit_pct", 0.0),
                    is_max_drawdown_pct=is_metrics.get("max_drawdown_pct", 0.0),
                    is_total_trades=is_metrics.get("total_trades", 0),
                    is_win_rate=is_metrics.get("win_rate", 0.0),
                    is_sharpe_ratio=is_metrics.get("sharpe_ratio"),
                    is_romad=is_metrics.get("romad"),
                    is_profit_factor=is_metrics.get("profit_factor"),
                    ft_net_profit_pct=ft_metrics.get("net_profit_pct", 0.0),
                    ft_max_drawdown_pct=ft_metrics.get("max_drawdown_pct", 0.0),
                    ft_total_trades=ft_metrics.get("total_trades", 0),
                    ft_win_rate=ft_metrics.get("win_rate", 0.0),
                    ft_sharpe_ratio=ft_metrics.get("sharpe_ratio"),
                    ft_sortino_ratio=ft_metrics.get("sortino_ratio"),
                    ft_romad=ft_metrics.get("romad"),
                    ft_profit_factor=ft_metrics.get("profit_factor"),
                    ft_ulcer_index=ft_metrics.get("ulcer_index"),
                    ft_sqn=ft_metrics.get("sqn"),
                    ft_consistency_score=ft_metrics.get("consistency_score"),
                    profit_degradation=comparison.get("profit_degradation", 0.0),
                    max_dd_change=comparison.get("max_dd_change", 0.0),
                    romad_change=comparison.get("romad_change", 0.0),
                    sharpe_change=comparison.get("sharpe_change", 0.0),
                    pf_change=comparison.get("pf_change", 0.0),
                )
            )

    if not results:
        return []

    sort_metric = (config.sort_metric or "profit_degradation").strip().lower()
    if sort_metric == "ft_romad":
        results.sort(
            key=lambda r: float(r.ft_romad) if r.ft_romad is not None else float("-inf"),
            reverse=True,
        )
    else:
        results.sort(key=lambda r: float(r.profit_degradation), reverse=True)

    for idx, result in enumerate(results, 1):
        result.ft_rank = idx
        result.rank_change = result.optuna_rank - idx

    return results
