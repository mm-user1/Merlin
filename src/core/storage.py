"""SQLite storage utilities for persisted optimization studies."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

DB_INIT_LOCK = threading.Lock()
DB_INITIALIZED = False

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
JOURNAL_DIR = STORAGE_DIR / "journals"
DB_PATH = STORAGE_DIR / "studies.db"


def init_database() -> None:
    """Initialize database schema and ensure storage directories exist."""
    global DB_INITIALIZED
    if DB_INITIALIZED:
        return
    with DB_INIT_LOCK:
        if DB_INITIALIZED:
            return
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(
            str(DB_PATH),
            check_same_thread=False,
            timeout=30.0,
            isolation_level="DEFERRED",
        ) as conn:
            _configure_connection(conn)
            _create_schema(conn)
            _run_migrations(conn)
        DB_INITIALIZED = True


def _configure_connection(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS studies (
            study_id TEXT PRIMARY KEY,
            study_name TEXT UNIQUE NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            optimization_mode TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',

            total_trials INTEGER,
            saved_trials INTEGER,
            completed_trials INTEGER,
            pruned_trials INTEGER,

            best_trial_number INTEGER,
            best_value REAL,
            target_metric TEXT,

            filter_score_enabled INTEGER DEFAULT 0,
            filter_score_threshold REAL,
            filter_profit_enabled INTEGER DEFAULT 0,
            filter_profit_threshold REAL,

            config_json TEXT,
            score_config_json TEXT,

            optimization_time_seconds REAL,
            warmup_bars INTEGER,
            worker_processes INTEGER,

            csv_file_path TEXT NOT NULL,
            csv_file_name TEXT NOT NULL,
            csv_last_verified TIMESTAMP,

            dataset_start_date TEXT,
            dataset_end_date TEXT,

            error_message TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_studies_strategy ON studies(strategy_id);
        CREATE INDEX IF NOT EXISTS idx_studies_created ON studies(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_studies_status ON studies(status);
        CREATE INDEX IF NOT EXISTS idx_studies_name ON studies(study_name);

        CREATE TABLE IF NOT EXISTS trials (
            trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_id TEXT NOT NULL,
            trial_number INTEGER NOT NULL,
            optuna_trial_number INTEGER,

            params_json TEXT NOT NULL,

            net_profit_pct REAL,
            max_drawdown_pct REAL,
            total_trades INTEGER,

            romad REAL,
            sharpe_ratio REAL,
            profit_factor REAL,
            ulcer_index REAL,
            sqn REAL,
            consistency_score REAL,

            score REAL,

            FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE,
            UNIQUE(study_id, trial_number)
        );

        CREATE INDEX IF NOT EXISTS idx_trials_study ON trials(study_id);
        CREATE INDEX IF NOT EXISTS idx_trials_score ON trials(study_id, score DESC);
        CREATE INDEX IF NOT EXISTS idx_trials_trial_number ON trials(study_id, trial_number);

        CREATE TABLE IF NOT EXISTS wfa_windows (
            window_id TEXT PRIMARY KEY,
            study_id TEXT NOT NULL,
            window_number INTEGER NOT NULL,

            best_params_json TEXT NOT NULL,
            param_id TEXT,

            is_start_date TEXT,
            is_end_date TEXT,
            is_net_profit_pct REAL,
            is_max_drawdown_pct REAL,
            is_total_trades INTEGER,
            is_best_trial_number INTEGER,
            is_equity_curve TEXT,

            oos_start_date TEXT,
            oos_end_date TEXT,
            oos_net_profit_pct REAL,
            oos_max_drawdown_pct REAL,
            oos_total_trades INTEGER,
            oos_equity_curve TEXT,

            wfe REAL,

            FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE,
            UNIQUE(study_id, window_number)
        );

        CREATE INDEX IF NOT EXISTS idx_wfa_windows_study ON wfa_windows(study_id);
        CREATE INDEX IF NOT EXISTS idx_wfa_windows_number ON wfa_windows(study_id, window_number);
        """
    )

    cursor = conn.execute("SELECT MAX(version) AS version FROM schema_version")
    current = cursor.fetchone()
    current_version = current["version"] if current and current["version"] is not None else 0
    if current_version == 0:
        conn.execute(
            "INSERT INTO schema_version (version, description) VALUES (1, 'Initial schema')"
        )
        conn.commit()


def _run_migrations(conn: sqlite3.Connection) -> None:
    cursor = conn.execute("SELECT MAX(version) AS version FROM schema_version")
    current = cursor.fetchone()
    current_version = current["version"] if current and current["version"] is not None else 0
    if current_version < 1:
        conn.execute(
            "INSERT INTO schema_version (version, description) VALUES (1, 'Initial schema')"
        )
        conn.commit()


@contextmanager
def get_db_connection() -> Iterator[sqlite3.Connection]:
    init_database()
    conn = sqlite3.connect(
        str(DB_PATH),
        check_same_thread=False,
        timeout=30.0,
        isolation_level="DEFERRED",
    )
    _configure_connection(conn)
    try:
        yield conn
    finally:
        conn.close()


def generate_study_id() -> str:
    return str(uuid.uuid4())


def generate_study_name(
    strategy_id: str,
    csv_filename: str,
    start_date,
    end_date,
    mode: str,
) -> str:
    match = re.match(r"s(\d+)_", strategy_id)
    prefix = f"S{match.group(1).zfill(2)}" if match else strategy_id.upper()[:3]

    ticker_tf = _extract_file_prefix(csv_filename or "")

    if hasattr(start_date, "strftime"):
        start_str = start_date.strftime("%Y.%m.%d")
    else:
        start_str = str(start_date)[:10].replace("-", ".") if start_date else "0000.00.00"

    if hasattr(end_date, "strftime"):
        end_str = end_date.strftime("%Y.%m.%d")
    else:
        end_str = str(end_date)[:10].replace("-", ".") if end_date else "0000.00.00"

    mode_suffix = "WFA" if str(mode).lower() == "wfa" else "Optuna"
    base_name = f"{prefix}_{ticker_tf} {start_str}-{end_str}_{mode_suffix}"

    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT study_name FROM studies WHERE study_name LIKE ? ORDER BY study_name",
            (f"{base_name}%",),
        )
        existing = {row[0] for row in cursor.fetchall()}

    if base_name not in existing:
        return base_name

    counter = 1
    while f"{base_name} ({counter})" in existing:
        counter += 1
    return f"{base_name} ({counter})"


def _extract_file_prefix(csv_filename: str) -> str:
    name = Path(csv_filename).stem
    date_pattern = re.compile(r"\b\d{4}[.\-/]\d{2}[.\-/]\d{2}\b")
    match = date_pattern.search(name)
    if match:
        prefix = name[:match.start()].rstrip()
        return prefix if prefix else name
    return name or "dataset"


def _get_csv_display_name(config: Any, csv_file_path: str) -> str:
    if isinstance(config, dict):
        name = config.get("csv_original_name") or config.get("csv_file_name") or ""
        if name:
            return str(Path(name).name)
    name = getattr(config, "csv_original_name", None)
    if name:
        return str(Path(name).name)
    if csv_file_path:
        return str(Path(csv_file_path).name)
    return "upload"


def save_optuna_study_to_db(
    study,
    config,
    optuna_config,
    trial_results: List,
    csv_file_path: str,
    start_time: float,
    score_config: Optional[Dict] = None,
) -> str:
    import pandas as pd
    from optuna.trial import TrialState

    init_database()

    study_id = generate_study_id()

    start_date = config.fixed_params.get("start") or pd.Timestamp.now(tz="UTC")
    end_date = config.fixed_params.get("end") or pd.Timestamp.now(tz="UTC")

    csv_display_name = _get_csv_display_name(config, csv_file_path)

    study_name = generate_study_name(
        strategy_id=config.strategy_id,
        csv_filename=csv_display_name,
        start_date=start_date,
        end_date=end_date,
        mode="optuna",
    )

    strategy_version = None
    try:
        from strategies import get_strategy

        strategy_class = get_strategy(config.strategy_id)
        strategy_version = getattr(strategy_class, "STRATEGY_VERSION", None)
    except Exception:
        pass

    resolved_score_config = score_config or getattr(config, "score_config", None) or {}
    filter_score_enabled = bool(resolved_score_config.get("filter_enabled", False))
    try:
        filter_score_threshold = float(resolved_score_config.get("min_score_threshold", 0.0))
    except (TypeError, ValueError):
        filter_score_threshold = 0.0

    filtered_results = list(trial_results or [])

    if filter_score_enabled:
        filtered_results = [r for r in filtered_results if float(r.score) >= filter_score_threshold]

    if getattr(config, "filter_min_profit", False):
        threshold = float(getattr(config, "min_profit_threshold", 0.0) or 0.0)
        filtered_results = [r for r in filtered_results if float(r.net_profit_pct) >= threshold]

    best_result = max(filtered_results, key=lambda r: float(r.score), default=None)

    optimization_time = time.time() - start_time

    summary = getattr(config, "optuna_summary", {}) or {}
    completed_trials = len(trial_results or [])
    pruned_trials = 0
    total_trials = completed_trials
    best_trial_number = getattr(best_result, "optuna_trial_number", None) if best_result else None

    if study is not None:
        try:
            completed_trials = sum(1 for t in study.trials if t.state == TrialState.COMPLETE)
            pruned_trials = sum(1 for t in study.trials if t.state == TrialState.PRUNED)
            total_trials = len(study.trials)
            best_trial_number = study.best_trial.number if study.best_trial else best_trial_number
        except Exception:
            completed_trials = int(summary.get("completed_trials", completed_trials))
            pruned_trials = int(summary.get("pruned_trials", pruned_trials))
            total_trials = int(summary.get("total_trials", total_trials))
            best_trial_number = summary.get("best_trial_number", best_trial_number)

    best_value = None
    if best_result is not None:
        if getattr(optuna_config, "target", "score") == "score":
            best_value = float(best_result.score)
        else:
            best_value = float(getattr(best_result, "optuna_value", best_result.score))

    config_payload = _safe_dict(config)
    if optuna_config is not None:
        config_payload["optuna_config"] = _safe_dict(optuna_config)

    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute(
                """
                INSERT INTO studies (
                    study_id, study_name, strategy_id, strategy_version,
                    optimization_mode, status,
                    total_trials, saved_trials, completed_trials, pruned_trials,
                    best_trial_number, best_value, target_metric,
                    filter_score_enabled, filter_score_threshold,
                    filter_profit_enabled, filter_profit_threshold,
                    config_json, score_config_json,
                    optimization_time_seconds, warmup_bars, worker_processes,
                    csv_file_path, csv_file_name, csv_last_verified,
                    dataset_start_date, dataset_end_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    study_id,
                    study_name,
                    config.strategy_id,
                    strategy_version,
                    "optuna",
                    "completed",
                    total_trials,
                    len(filtered_results),
                    completed_trials,
                    pruned_trials,
                    best_trial_number,
                    best_value,
                    getattr(optuna_config, "target", "score"),
                    1 if filter_score_enabled else 0,
                    filter_score_threshold if filter_score_enabled else None,
                    1 if getattr(config, "filter_min_profit", False) else 0,
                    getattr(config, "min_profit_threshold", None)
                    if getattr(config, "filter_min_profit", False)
                    else None,
                    json.dumps(config_payload),
                    json.dumps(resolved_score_config) if resolved_score_config else None,
                    optimization_time,
                    getattr(config, "warmup_bars", None),
                    getattr(config, "worker_processes", None),
                    str(Path(csv_file_path).resolve()) if csv_file_path else "",
                    csv_display_name,
                    time.time(),
                    _format_date(start_date),
                    _format_date(end_date),
                ),
            )

            trial_rows = []
            for idx, result in enumerate(filtered_results, 1):
                trial_rows.append(
                    (
                        study_id,
                        idx,
                        getattr(result, "optuna_trial_number", None),
                        json.dumps(result.params),
                        result.net_profit_pct,
                        result.max_drawdown_pct,
                        result.total_trades,
                        result.romad,
                        result.sharpe_ratio,
                        result.profit_factor,
                        result.ulcer_index,
                        result.sqn,
                        result.consistency_score,
                        result.score,
                    )
                )

            if trial_rows:
                conn.executemany(
                    """
                    INSERT INTO trials (
                        study_id, trial_number, optuna_trial_number,
                        params_json, net_profit_pct, max_drawdown_pct, total_trades,
                        romad, sharpe_ratio, profit_factor, ulcer_index, sqn,
                        consistency_score, score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    trial_rows,
                )

            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            raise RuntimeError(f"Failed to save study to database: {exc}")

    return study_id


def save_wfa_study_to_db(
    wf_result,
    config,
    csv_file_path: str,
    start_time: float,
    score_config: Optional[Dict] = None,
) -> str:
    init_database()

    study_id = generate_study_id()
    csv_display_name = _get_csv_display_name(config, csv_file_path)

    study_name = generate_study_name(
        strategy_id=wf_result.strategy_id,
        csv_filename=csv_display_name,
        start_date=wf_result.trading_start_date,
        end_date=wf_result.trading_end_date,
        mode="wfa",
    )

    strategy_version = None
    try:
        from strategies import get_strategy

        strategy_class = get_strategy(wf_result.strategy_id)
        strategy_version = getattr(strategy_class, "STRATEGY_VERSION", None)
    except Exception:
        pass

    optimization_time = time.time() - start_time

    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute(
                """
                INSERT INTO studies (
                    study_id, study_name, strategy_id, strategy_version,
                    optimization_mode, status,
                    total_trials, saved_trials,
                    best_value, target_metric,
                    config_json, score_config_json,
                    optimization_time_seconds, warmup_bars, worker_processes,
                    csv_file_path, csv_file_name, csv_last_verified,
                    dataset_start_date, dataset_end_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    study_id,
                    study_name,
                    wf_result.strategy_id,
                    strategy_version,
                    "wfa",
                    "completed",
                    wf_result.total_windows,
                    wf_result.total_windows,
                    getattr(wf_result.stitched_oos, "wfe", None),
                    "WFE",
                    json.dumps(_safe_dict(config)),
                    json.dumps(score_config) if score_config else None,
                    optimization_time,
                    wf_result.warmup_bars,
                    getattr(config, "worker_processes", None)
                    if not isinstance(config, dict)
                    else config.get("worker_processes"),
                    str(Path(csv_file_path).resolve()) if csv_file_path else "",
                    csv_display_name,
                    time.time(),
                    _format_date(wf_result.trading_start_date),
                    _format_date(wf_result.trading_end_date),
                ),
            )

            window_rows = []
            for window in wf_result.windows:
                is_equity = (
                    json.dumps(list(window.is_equity_curve))
                    if getattr(window, "is_equity_curve", None)
                    else None
                )
                oos_equity = (
                    json.dumps(list(window.oos_equity_curve))
                    if window.oos_equity_curve
                    else None
                )
                window_rows.append(
                    (
                        f"{study_id}_w{window.window_id}",
                        study_id,
                        window.window_id,
                        json.dumps(window.best_params),
                        window.param_id,
                        _format_date(window.is_start),
                        _format_date(window.is_end),
                        window.is_net_profit_pct,
                        window.is_max_drawdown_pct,
                        window.is_total_trades,
                        getattr(window, "is_best_trial_number", None),
                        is_equity,
                        _format_date(window.oos_start),
                        _format_date(window.oos_end),
                        window.oos_net_profit_pct,
                        window.oos_max_drawdown_pct,
                        window.oos_total_trades,
                        oos_equity,
                        getattr(window, "wfe", None),
                    )
                )

            if window_rows:
                conn.executemany(
                    """
                    INSERT INTO wfa_windows (
                        window_id, study_id, window_number,
                        best_params_json, param_id,
                        is_start_date, is_end_date,
                        is_net_profit_pct, is_max_drawdown_pct, is_total_trades, is_best_trial_number,
                        is_equity_curve,
                        oos_start_date, oos_end_date,
                        oos_net_profit_pct, oos_max_drawdown_pct, oos_total_trades,
                        oos_equity_curve, wfe
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    window_rows,
                )

            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            raise RuntimeError(f"Failed to save WFA study to database: {exc}")

    return study_id


def list_studies() -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                study_id, study_name, strategy_id, optimization_mode,
                status, created_at, saved_trials, best_value, target_metric,
                csv_file_name
            FROM studies
            ORDER BY created_at DESC
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def load_study_from_db(study_id: str) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM studies WHERE study_id = ?", (study_id,))
        study_row = cursor.fetchone()
        if not study_row:
            return None

        study = dict(study_row)
        for key in ("config_json", "score_config_json"):
            if study.get(key):
                try:
                    study[key] = json.loads(study[key])
                except json.JSONDecodeError:
                    pass

        csv_path = study.get("csv_file_path")
        csv_exists = bool(csv_path and Path(csv_path).exists())
        if csv_exists:
            conn.execute(
                "UPDATE studies SET csv_last_verified = ?, updated_at = CURRENT_TIMESTAMP WHERE study_id = ?",
                (time.time(), study_id),
            )
            conn.commit()

        trials: List[Dict] = []
        windows: List[Dict] = []

        if study.get("optimization_mode") == "optuna":
            cursor = conn.execute(
                "SELECT * FROM trials WHERE study_id = ? ORDER BY score DESC",
                (study_id,),
            )
            for row in cursor.fetchall():
                trial = dict(row)
                trial["params"] = json.loads(trial["params_json"])
                trials.append(trial)
        elif study.get("optimization_mode") == "wfa":
            cursor = conn.execute(
                "SELECT * FROM wfa_windows WHERE study_id = ? ORDER BY window_number",
                (study_id,),
            )
            for row in cursor.fetchall():
                window = dict(row)
                window["best_params"] = json.loads(window["best_params_json"])
                if window.get("oos_equity_curve"):
                    window["oos_equity_curve"] = json.loads(window["oos_equity_curve"])
                if window.get("is_equity_curve"):
                    window["is_equity_curve"] = json.loads(window["is_equity_curve"])
                windows.append(window)

    return {
        "study": study,
        "trials": trials,
        "windows": windows,
        "csv_exists": csv_exists,
    }


def get_study_trial(study_id: str, trial_number: int) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM trials WHERE study_id = ? AND trial_number = ?",
            (study_id, trial_number),
        )
        row = cursor.fetchone()
        if not row:
            return None
        trial = dict(row)
        trial["params"] = json.loads(trial["params_json"])
        return trial


def update_csv_path(study_id: str, new_path: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE studies
            SET csv_file_path = ?, csv_last_verified = ?, updated_at = CURRENT_TIMESTAMP
            WHERE study_id = ?
            """,
            (new_path, time.time(), study_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def update_study_status(study_id: str, status: str, error_message: Optional[str] = None) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE studies
            SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE study_id = ?
            """,
            (status, error_message, study_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_study(study_id: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM studies WHERE study_id = ?", (study_id,))
        conn.commit()
        return cursor.rowcount > 0


def _safe_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "__dataclass_fields__"):
        try:
            data = asdict(obj)
        except Exception:
            data = {}
        return _serialize_dict(data)
    if isinstance(obj, dict):
        return _serialize_dict(obj)
    return {"value": str(obj)}


def _serialize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in data.items():
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        elif isinstance(value, (list, dict, str, int, float, bool, type(None))):
            result[key] = value
        else:
            result[key] = str(value)
    return result


def _format_date(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    if value:
        return str(value)[:10]
    return ""
