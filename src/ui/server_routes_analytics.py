import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import jsonify, render_template

from core.storage import get_active_db_name, get_db_connection


def register_routes(app):
    def _parse_date_flexible(date_str: Any) -> Optional[datetime]:
        """Parse date in YYYY-MM-DD or YYYY.MM.DD format."""
        value = str(date_str or "").strip()
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def _period_days(start_date: Any, end_date: Any) -> Optional[int]:
        start = _parse_date_flexible(start_date)
        end = _parse_date_flexible(end_date)
        if start is None or end is None:
            return None
        return max(0, (end - start).days)

    def _date_sort_key(date_str: Any) -> Tuple[int, Any]:
        parsed = _parse_date_flexible(date_str)
        if parsed is not None:
            return (0, parsed)
        return (1, str(date_str or ""))

    def _safe_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(parsed):
            return None
        return parsed

    def _safe_int(value: Any) -> Optional[int]:
        parsed = _safe_float(value)
        if parsed is None:
            return None
        return int(round(parsed))

    def _parse_json_dict(raw_value: Any) -> Dict[str, Any]:
        if isinstance(raw_value, dict):
            return raw_value
        if not raw_value:
            return {}
        try:
            parsed = json.loads(raw_value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}

    def _parse_json_array(raw_value: Any) -> List[Any]:
        if isinstance(raw_value, list):
            return raw_value
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if isinstance(parsed, list):
            return parsed
        return []

    def _timeframe_to_minutes(value: Any) -> float:
        token = str(value or "").strip().lower()
        if not token:
            return float("inf")
        m = re.match(r"^(\d+)(m)?$", token)
        if m:
            return float(m.group(1))
        m = re.match(r"^(\d+)h$", token)
        if m:
            return float(int(m.group(1)) * 60)
        m = re.match(r"^(\d+)d$", token)
        if m:
            return float(int(m.group(1)) * 1440)
        m = re.match(r"^(\d+)w$", token)
        if m:
            return float(int(m.group(1)) * 10080)
        return float("inf")

    def _normalize_tf(tf_str: str) -> str:
        token = str(tf_str or "").strip()
        if not token:
            return ""
        lower = token.lower()
        if lower.endswith(("h", "d", "w")):
            if lower.endswith("d"):
                return lower[:-1] + "D"
            return lower
        if not lower.endswith("m"):
            return lower
        try:
            minutes = int(lower[:-1])
        except ValueError:
            return lower
        if minutes >= 1440 and minutes % 1440 == 0:
            return f"{minutes // 1440}D"
        if minutes >= 60 and minutes % 60 == 0:
            return f"{minutes // 60}h"
        return f"{minutes}m"

    def _parse_csv_filename(csv_file_name: Any) -> Tuple[Optional[str], Optional[str]]:
        """Strict Merlin parser for symbol/timeframe from csv_file_name."""
        value = str(csv_file_name or "").strip()
        if not value:
            return None, None
        name = Path(value).name

        # Numeric TF: "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
        match = re.match(r"^[^_]*_([^,]+),\s*(\d+)\s", name)
        if match:
            symbol = match.group(1).strip()
            tf_minutes = int(match.group(2))
            tf_map = {
                1: "1m",
                5: "5m",
                15: "15m",
                30: "30m",
                60: "1h",
                120: "2h",
                240: "4h",
                1440: "1D",
            }
            return symbol, tf_map.get(tf_minutes, f"{tf_minutes}m")

        # Human TF: "OKX_LINKUSDT.P, 1h 2025.05.01-2025.11.20.csv"
        match = re.match(r"^[^_]*_([^,]+),\s*(\d+[mhdwMHDW])\s", name)
        if match:
            symbol = match.group(1).strip()
            tf = _normalize_tf(match.group(2))
            return symbol, tf

        return None, None

    def _format_strategy_label(strategy_id: Any, strategy_version: Any) -> str:
        strategy_raw = str(strategy_id or "").strip()
        version_raw = str(strategy_version or "").strip()
        if not strategy_raw:
            return "Unknown"
        match = re.match(r"^s(\d+)_", strategy_raw, re.IGNORECASE)
        if match:
            strategy_label = f"S{int(match.group(1)):02d}"
        else:
            strategy_label = strategy_raw
        if version_raw:
            version_label = version_raw if version_raw.lower().startswith("v") else f"v{version_raw}"
            return f"{strategy_label} {version_label}"
        return strategy_label

    def _format_wfa_mode(adaptive_mode: Any) -> str:
        adaptive_int = _safe_int(adaptive_mode)
        if adaptive_int == 0:
            return "Fixed"
        if adaptive_int == 1:
            return "Adaptive"
        return "Unknown"

    def _extract_oos_period_days(config_json_value: Any) -> Optional[int]:
        config_payload = _parse_json_dict(config_json_value)
        wfa_payload = config_payload.get("wfa")
        if not isinstance(wfa_payload, dict):
            return None
        return _safe_int(wfa_payload.get("oos_period_days"))

    @app.route("/analytics")
    def analytics_page() -> object:
        return render_template("analytics.html")

    @app.get("/api/analytics/summary")
    def analytics_summary() -> object:
        with get_db_connection() as conn:
            total_studies_row = conn.execute("SELECT COUNT(*) AS count FROM studies").fetchone()
            total_studies = int(total_studies_row["count"] if total_studies_row else 0)

            cursor = conn.execute(
                """
                SELECT
                    study_id,
                    strategy_id,
                    strategy_version,
                    csv_file_name,
                    adaptive_mode,
                    is_period_days,
                    config_json,
                    dataset_start_date,
                    dataset_end_date,
                    stitched_oos_net_profit_pct,
                    stitched_oos_max_drawdown_pct,
                    stitched_oos_total_trades,
                    stitched_oos_winning_trades,
                    best_value,
                    profitable_windows,
                    total_windows,
                    stitched_oos_win_rate,
                    median_window_profit,
                    median_window_wr,
                    stitched_oos_equity_curve,
                    stitched_oos_timestamps_json
                FROM studies
                WHERE LOWER(COALESCE(optimization_mode, '')) = 'wfa'
                """
            )
            rows = cursor.fetchall()

        studies: List[Dict[str, Any]] = []
        data_period_counts: Dict[Tuple[str, str], int] = {}
        strategy_values: set[str] = set()
        symbol_values: set[str] = set()
        timeframe_values: set[str] = set()
        wfa_mode_values: set[str] = set()
        is_oos_values: set[str] = set()

        for row in rows:
            row_dict = dict(row)

            strategy_label = _format_strategy_label(
                row_dict.get("strategy_id"),
                row_dict.get("strategy_version"),
            )
            strategy_values.add(strategy_label)

            symbol, tf = _parse_csv_filename(row_dict.get("csv_file_name"))
            if symbol:
                symbol_values.add(symbol)
            if tf:
                timeframe_values.add(tf)

            wfa_mode = _format_wfa_mode(row_dict.get("adaptive_mode"))
            wfa_mode_values.add(wfa_mode)

            is_period_days = _safe_int(row_dict.get("is_period_days"))
            oos_period_days = _extract_oos_period_days(row_dict.get("config_json"))
            if is_period_days is None and oos_period_days is None:
                is_oos = "N/A"
            else:
                is_oos = (
                    f"{is_period_days if is_period_days is not None else '?'}"
                    f"/{oos_period_days if oos_period_days is not None else '?'}"
                )
            is_oos_values.add(is_oos)

            dataset_start = str(row_dict.get("dataset_start_date") or "")
            dataset_end = str(row_dict.get("dataset_end_date") or "")
            key = (dataset_start, dataset_end)
            data_period_counts[key] = data_period_counts.get(key, 0) + 1

            profit_pct = _safe_float(row_dict.get("stitched_oos_net_profit_pct"))
            if profit_pct is None:
                profit_pct = 0.0
            max_dd_pct = _safe_float(row_dict.get("stitched_oos_max_drawdown_pct"))
            if max_dd_pct is None:
                max_dd_pct = 0.0
            total_trades = _safe_int(row_dict.get("stitched_oos_total_trades"))
            if total_trades is None:
                total_trades = 0
            winning_trades = _safe_int(row_dict.get("stitched_oos_winning_trades"))

            profitable_windows = _safe_int(row_dict.get("profitable_windows"))
            if profitable_windows is None:
                profitable_windows = 0
            total_windows = _safe_int(row_dict.get("total_windows"))
            if total_windows is None:
                total_windows = 0
            stitched_win_rate = _safe_float(row_dict.get("stitched_oos_win_rate"))
            if total_windows > 0:
                profitable_windows_pct = (profitable_windows / total_windows) * 100.0
            elif stitched_win_rate is not None:
                profitable_windows_pct = stitched_win_rate
            else:
                profitable_windows_pct = 0.0

            equity_curve = _parse_json_array(row_dict.get("stitched_oos_equity_curve"))
            equity_timestamps = _parse_json_array(row_dict.get("stitched_oos_timestamps_json"))
            has_equity_curve = len(equity_curve) > 0 and len(equity_curve) == len(equity_timestamps)
            if not has_equity_curve:
                equity_curve = []
                equity_timestamps = []

            studies.append(
                {
                    "study_id": row_dict.get("study_id"),
                    "strategy": strategy_label,
                    "strategy_id": row_dict.get("strategy_id"),
                    "strategy_version": row_dict.get("strategy_version"),
                    "symbol": symbol,
                    "tf": tf,
                    "wfa_mode": wfa_mode,
                    "is_oos": is_oos,
                    "dataset_start_date": dataset_start,
                    "dataset_end_date": dataset_end,
                    "profit_pct": profit_pct,
                    "max_dd_pct": max_dd_pct,
                    "total_trades": total_trades,
                    "winning_trades": winning_trades,
                    "wfe_pct": _safe_float(row_dict.get("best_value")),
                    "total_windows": total_windows,
                    "profitable_windows": profitable_windows,
                    "profitable_windows_pct": profitable_windows_pct,
                    "median_window_profit": _safe_float(row_dict.get("median_window_profit")),
                    "median_window_wr": _safe_float(row_dict.get("median_window_wr")),
                    "has_equity_curve": has_equity_curve,
                    "equity_curve": equity_curve,
                    "equity_timestamps": equity_timestamps,
                }
            )

        studies.sort(
            key=lambda study: (
                _date_sort_key(study.get("dataset_start_date")),
                _date_sort_key(study.get("dataset_end_date")),
                -(_safe_float(study.get("profit_pct")) or 0.0),
                str(study.get("study_id") or ""),
            )
        )

        data_periods = []
        for (start, end), count in sorted(
            data_period_counts.items(),
            key=lambda item: (_date_sort_key(item[0][0]), _date_sort_key(item[0][1])),
        ):
            data_periods.append(
                {
                    "start": start,
                    "end": end,
                    "days": _period_days(start, end),
                    "count": count,
                }
            )

        wfa_mode_order = {"Fixed": 0, "Adaptive": 1, "Unknown": 2}
        wfa_modes = sorted(wfa_mode_values, key=lambda value: (wfa_mode_order.get(value, 99), value))

        timeframes = sorted(
            timeframe_values,
            key=lambda value: (_timeframe_to_minutes(value), str(value)),
        )

        research_info: Dict[str, Any] = {
            "total_studies": total_studies,
            "wfa_studies": len(studies),
            "strategies": sorted(strategy_values),
            "symbols": sorted(symbol_values),
            "timeframes": timeframes,
            "wfa_modes": wfa_modes,
            "is_oos_periods": sorted(is_oos_values),
            "data_periods": data_periods,
        }

        if len(studies) == 0:
            if total_studies == 0:
                research_info["message"] = "No WFA studies found in this database."
            else:
                research_info["message"] = (
                    "Analytics requires WFA studies. This database contains only Optuna studies."
                )

        return jsonify(
            {
                "db_name": get_active_db_name(),
                "studies": studies,
                "research_info": research_info,
            }
        )
