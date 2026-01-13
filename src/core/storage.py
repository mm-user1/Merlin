"""SQLite storage utilities for persisted optimization studies."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

OBJECTIVE_DIRECTIONS: Dict[str, str] = {
    "net_profit_pct": "maximize",
    "max_drawdown_pct": "minimize",
    "sharpe_ratio": "maximize",
    "sortino_ratio": "maximize",
    "romad": "maximize",
    "profit_factor": "maximize",
    "win_rate": "maximize",
    "sqn": "maximize",
    "ulcer_index": "minimize",
    "consistency_score": "maximize",
    "composite_score": "maximize",
}

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
        CREATE TABLE IF NOT EXISTS studies (
            study_id TEXT PRIMARY KEY,
            study_name TEXT UNIQUE NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT,

            optimization_mode TEXT NOT NULL,

            objectives_json TEXT,
            n_objectives INTEGER DEFAULT 1,
            directions_json TEXT,
            primary_objective TEXT,

            constraints_json TEXT,

            sampler_type TEXT DEFAULT 'tpe',
            population_size INTEGER,
            crossover_prob REAL,
            mutation_prob REAL,
            swapping_prob REAL,

            budget_mode TEXT,
            n_trials INTEGER,
            time_limit INTEGER,
            convergence_patience INTEGER,

            total_trials INTEGER DEFAULT 0,
            completed_trials INTEGER DEFAULT 0,
            pruned_trials INTEGER DEFAULT 0,
            pareto_front_size INTEGER,

            best_value REAL,
            best_values_json TEXT,

            score_config_json TEXT,
            config_json TEXT,

            csv_file_path TEXT,
            csv_file_name TEXT,

            dataset_start_date TEXT,
            dataset_end_date TEXT,
            warmup_bars INTEGER,

            ft_enabled INTEGER DEFAULT 0,
            ft_period_days INTEGER,
            ft_top_k INTEGER,
            ft_sort_metric TEXT,
            ft_start_date TEXT,
            ft_end_date TEXT,
            is_period_days INTEGER,

            dsr_enabled INTEGER DEFAULT 0,
            dsr_top_k INTEGER,
            dsr_n_trials INTEGER,
            dsr_mean_sharpe REAL,
            dsr_var_sharpe REAL,

            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,

            filter_min_profit INTEGER DEFAULT 0,
            min_profit_threshold REAL DEFAULT 0.0,
            sanitize_enabled INTEGER DEFAULT 1,
            sanitize_trades_threshold INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_studies_strategy ON studies(strategy_id);
        CREATE INDEX IF NOT EXISTS idx_studies_created ON studies(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_studies_name ON studies(study_name);

        CREATE TABLE IF NOT EXISTS trials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_id TEXT NOT NULL,
            trial_number INTEGER NOT NULL,

            params_json TEXT NOT NULL,

            objective_values_json TEXT,

            is_pareto_optimal INTEGER DEFAULT 0,
            dominance_rank INTEGER,

            constraints_satisfied INTEGER DEFAULT 1,
            constraint_values_json TEXT,

            net_profit_pct REAL,
            max_drawdown_pct REAL,
            total_trades INTEGER,
            win_rate REAL,
            avg_win REAL,
            avg_loss REAL,
            gross_profit REAL,
            gross_loss REAL,
            sharpe_ratio REAL,
            sortino_ratio REAL,
            romad REAL,
            profit_factor REAL,
            sqn REAL,
            ulcer_index REAL,
            consistency_score REAL,

            composite_score REAL,

            ft_net_profit_pct REAL,
            ft_max_drawdown_pct REAL,
            ft_total_trades INTEGER,
            ft_win_rate REAL,
            ft_sharpe_ratio REAL,
            ft_sortino_ratio REAL,
            ft_romad REAL,
            ft_profit_factor REAL,
            ft_ulcer_index REAL,
            ft_sqn REAL,
            ft_consistency_score REAL,
            profit_degradation REAL,
            ft_rank INTEGER,

            dsr_probability REAL,
            dsr_rank INTEGER,
            dsr_skewness REAL,
            dsr_kurtosis REAL,
            dsr_track_length INTEGER,
            dsr_luck_share_pct REAL,

            created_at TEXT DEFAULT (datetime('now')),

            UNIQUE(study_id, trial_number),
            FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_trials_pareto ON trials(study_id, is_pareto_optimal);
        CREATE INDEX IF NOT EXISTS idx_trials_constraints ON trials(study_id, constraints_satisfied);

        CREATE TABLE IF NOT EXISTS manual_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_id TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),

            test_name TEXT,
            data_source TEXT NOT NULL,
            csv_path TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,

            source_tab TEXT NOT NULL,

            trials_count INTEGER NOT NULL,
            trials_tested_csv TEXT NOT NULL,
            best_profit_degradation REAL,
            worst_profit_degradation REAL,

            results_json TEXT NOT NULL,

            FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_manual_tests_study ON manual_tests(study_id);
        CREATE INDEX IF NOT EXISTS idx_manual_tests_created ON manual_tests(created_at DESC);

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
    _ensure_columns(conn)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    def ensure(table: str, column: str, definition: str) -> None:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        existing = {row["name"] for row in cursor.fetchall()}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    ensure("studies", "dsr_enabled", "INTEGER DEFAULT 0")
    ensure("studies", "dsr_top_k", "INTEGER")
    ensure("studies", "dsr_n_trials", "INTEGER")
    ensure("studies", "dsr_mean_sharpe", "REAL")
    ensure("studies", "dsr_var_sharpe", "REAL")

    ensure("trials", "dsr_probability", "REAL")
    ensure("trials", "dsr_rank", "INTEGER")
    ensure("trials", "dsr_skewness", "REAL")
    ensure("trials", "dsr_kurtosis", "REAL")
    ensure("trials", "dsr_track_length", "INTEGER")
    ensure("trials", "dsr_luck_share_pct", "REAL")


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

    mode_suffix = "WFA" if str(mode).lower() == "wfa" else "OPT"
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

    best_result = filtered_results[0] if filtered_results else None

    completed_trials = len(trial_results or [])
    pruned_trials = 0
    total_trials = completed_trials

    if study is not None:
        try:
            completed_trials = sum(1 for t in study.trials if t.state == TrialState.COMPLETE)
            pruned_trials = sum(1 for t in study.trials if t.state == TrialState.PRUNED)
            total_trials = len(study.trials)
        except Exception:
            completed_trials = len(trial_results or [])
            pruned_trials = 0
            total_trials = completed_trials

    objectives = list(getattr(optuna_config, "objectives", None) or [])
    if not objectives:
        objectives = ["net_profit_pct"]

    directions = None
    if study is not None:
        try:
            directions = [str(d).lower() for d in study.directions]
        except Exception:
            directions = None

    primary_objective = getattr(optuna_config, "primary_objective", None)
    constraints_payload = []
    for spec in getattr(optuna_config, "constraints", []) or []:
        if isinstance(spec, dict):
            constraints_payload.append(spec)
        else:
            constraints_payload.append(
                {
                    "metric": getattr(spec, "metric", None),
                    "threshold": getattr(spec, "threshold", None),
                    "enabled": bool(getattr(spec, "enabled", False)),
                }
            )

    sampler_cfg = getattr(optuna_config, "sampler_config", None)
    if isinstance(sampler_cfg, dict):
        sampler_payload = sampler_cfg
    else:
        sampler_payload = {
            "sampler_type": getattr(sampler_cfg, "sampler_type", None),
            "population_size": getattr(sampler_cfg, "population_size", None),
            "crossover_prob": getattr(sampler_cfg, "crossover_prob", None),
            "mutation_prob": getattr(sampler_cfg, "mutation_prob", None),
            "swapping_prob": getattr(sampler_cfg, "swapping_prob", None),
            "n_startup_trials": getattr(sampler_cfg, "n_startup_trials", None),
        }

    best_value = None
    best_values_json = None
    if best_result is not None and getattr(best_result, "objective_values", None):
        if len(objectives) > 1:
            best_values_json = json.dumps(
                dict(zip(objectives, list(best_result.objective_values)))
            )
        else:
            best_value = float(best_result.objective_values[0])

    pareto_front_size = sum(
        1 for r in filtered_results if getattr(r, "is_pareto_optimal", False)
    ) if len(objectives) > 1 else None

    config_payload = _safe_dict(config)
    if optuna_config is not None:
        config_payload["optuna_config"] = _safe_dict(optuna_config)

    ft_enabled = int(getattr(config, "ft_enabled", 0) or 0)
    ft_period_days = getattr(config, "ft_period_days", None)
    ft_top_k = getattr(config, "ft_top_k", None)
    ft_sort_metric = getattr(config, "ft_sort_metric", None)
    ft_start_date = getattr(config, "ft_start_date", None)
    ft_end_date = getattr(config, "ft_end_date", None)
    is_period_days = getattr(config, "is_period_days", None)

    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute(
                """
                INSERT INTO studies (
                    study_id, study_name, strategy_id, strategy_version,
                    optimization_mode,
                    objectives_json, n_objectives, directions_json, primary_objective,
                    constraints_json,
                    sampler_type, population_size, crossover_prob, mutation_prob, swapping_prob,
                    budget_mode, n_trials, time_limit, convergence_patience,
                    total_trials, completed_trials, pruned_trials, pareto_front_size,
                    best_value, best_values_json,
                    score_config_json, config_json,
                    csv_file_path, csv_file_name,
                    dataset_start_date, dataset_end_date, warmup_bars,
                    ft_enabled, ft_period_days, ft_top_k, ft_sort_metric,
                    ft_start_date, ft_end_date, is_period_days,
                    completed_at,
                    filter_min_profit, min_profit_threshold,
                    sanitize_enabled, sanitize_trades_threshold
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    study_id,
                    study_name,
                    config.strategy_id,
                    strategy_version,
                    "optuna",
                    json.dumps(objectives) if objectives else None,
                    len(objectives),
                    json.dumps(directions) if directions else None,
                    primary_objective,
                    json.dumps(constraints_payload) if constraints_payload else None,
                    sampler_payload.get("sampler_type") or "tpe",
                    sampler_payload.get("population_size"),
                    sampler_payload.get("crossover_prob"),
                    sampler_payload.get("mutation_prob"),
                    sampler_payload.get("swapping_prob"),
                    getattr(optuna_config, "budget_mode", None),
                    getattr(optuna_config, "n_trials", None),
                    getattr(optuna_config, "time_limit", None),
                    getattr(optuna_config, "convergence_patience", None),
                    total_trials,
                    completed_trials,
                    pruned_trials,
                    pareto_front_size,
                    best_value,
                    best_values_json,
                    json.dumps(resolved_score_config) if resolved_score_config else None,
                    json.dumps(config_payload),
                    str(Path(csv_file_path).resolve()) if csv_file_path else "",
                    csv_display_name,
                    _format_date(start_date),
                    _format_date(end_date),
                    getattr(config, "warmup_bars", None),
                    ft_enabled,
                    ft_period_days,
                    ft_top_k,
                    ft_sort_metric,
                    _format_date(ft_start_date),
                    _format_date(ft_end_date),
                    is_period_days,
                    datetime.utcnow().isoformat() + "Z",
                    1 if getattr(config, "filter_min_profit", False) else 0,
                    getattr(config, "min_profit_threshold", None)
                    if getattr(config, "filter_min_profit", False)
                    else None,
                    1 if getattr(optuna_config, "sanitize_enabled", True) else 0,
                    int(getattr(optuna_config, "sanitize_trades_threshold", 0) or 0),
                ),
            )

            trial_rows = []
            used_trial_numbers = set()
            next_fallback = 1
            for idx, result in enumerate(filtered_results, 1):
                trial_number = getattr(result, "optuna_trial_number", None)
                if trial_number is None:
                    trial_number = idx
                trial_number = int(trial_number)
                if trial_number in used_trial_numbers:
                    while next_fallback in used_trial_numbers:
                        next_fallback += 1
                    trial_number = next_fallback
                used_trial_numbers.add(trial_number)
                constraint_values = list(getattr(result, "constraint_values", []) or [])
                constraints_satisfied = getattr(result, "constraints_satisfied", None)
                if constraints_satisfied is None:
                    constraints_satisfied = all(v <= 0.0 for v in constraint_values) if constraint_values else True
                trial_rows.append(
                    (
                        study_id,
                        int(trial_number),
                        json.dumps(result.params),
                        json.dumps(list(getattr(result, "objective_values", []) or [])),
                        1 if getattr(result, "is_pareto_optimal", False) else 0,
                        getattr(result, "dominance_rank", None),
                        1 if constraints_satisfied else 0,
                        json.dumps(constraint_values) if constraint_values else None,
                        result.net_profit_pct,
                        result.max_drawdown_pct,
                        result.total_trades,
                        result.win_rate,
                        result.avg_win,
                        result.avg_loss,
                        result.gross_profit,
                        result.gross_loss,
                        result.romad,
                        result.sharpe_ratio,
                        result.sortino_ratio,
                        result.profit_factor,
                        result.ulcer_index,
                        result.sqn,
                        result.consistency_score,
                        result.score,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    )
                )

            if trial_rows:
                conn.executemany(
                    """
                    INSERT INTO trials (
                        study_id, trial_number,
                        params_json, objective_values_json, is_pareto_optimal, dominance_rank,
                        constraints_satisfied, constraint_values_json,
                        net_profit_pct, max_drawdown_pct, total_trades, win_rate, avg_win, avg_loss,
                        gross_profit, gross_loss,
                        romad, sharpe_ratio, sortino_ratio, profit_factor, ulcer_index, sqn,
                        consistency_score, composite_score,
                        ft_net_profit_pct, ft_max_drawdown_pct, ft_total_trades, ft_win_rate,
                        ft_sharpe_ratio, ft_sortino_ratio, ft_romad, ft_profit_factor,
                        ft_ulcer_index, ft_sqn, ft_consistency_score, profit_degradation, ft_rank
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    objectives = []
    constraints_payload: List[Dict[str, Any]] = []
    if isinstance(config, dict):
        objectives = list(config.get("objectives") or [])
        constraints_payload = list(config.get("constraints") or [])

    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute(
                """
                INSERT INTO studies (
                    study_id, study_name, strategy_id, strategy_version,
                    optimization_mode,
                    objectives_json, n_objectives, directions_json, primary_objective,
                    constraints_json,
                    sampler_type, population_size, crossover_prob, mutation_prob, swapping_prob,
                    budget_mode, n_trials, time_limit, convergence_patience,
                    total_trials, completed_trials, pruned_trials, pareto_front_size,
                    best_value, best_values_json,
                    score_config_json, config_json,
                    csv_file_path, csv_file_name,
                    dataset_start_date, dataset_end_date, warmup_bars,
                    completed_at,
                    filter_min_profit, min_profit_threshold
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    study_id,
                    study_name,
                    wf_result.strategy_id,
                    strategy_version,
                    "wfa",
                    json.dumps(objectives) if objectives else None,
                    len(objectives) if objectives else 1,
                    None,
                    None,
                    json.dumps(constraints_payload) if constraints_payload else None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    wf_result.total_windows,
                    wf_result.total_windows,
                    0,
                    None,
                    getattr(wf_result.stitched_oos, "wfe", None),
                    None,
                    json.dumps(score_config) if score_config else None,
                    json.dumps(_safe_dict(config)),
                    str(Path(csv_file_path).resolve()) if csv_file_path else "",
                    csv_display_name,
                    _format_date(wf_result.trading_start_date),
                    _format_date(wf_result.trading_end_date),
                    wf_result.warmup_bars,
                    datetime.utcnow().isoformat() + "Z",
                    1 if isinstance(config, dict) and config.get("filter_min_profit") else 0,
                    config.get("min_profit_threshold") if isinstance(config, dict) else None,
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
                created_at, completed_at, completed_trials, best_value,
                csv_file_name
            FROM studies
            ORDER BY created_at DESC
            """
        )
        rows = []
        for row in cursor.fetchall():
            study = dict(row)
            if "status" not in study:
                study["status"] = "completed" if study.get("completed_at") else "unknown"
            rows.append(study)
        return rows


def load_study_from_db(study_id: str) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM studies WHERE study_id = ?", (study_id,))
        study_row = cursor.fetchone()
        if not study_row:
            return None

        study = dict(study_row)
        for key in (
            "config_json",
            "score_config_json",
            "objectives_json",
            "directions_json",
            "constraints_json",
            "best_values_json",
        ):
            if study.get(key):
                try:
                    study[key] = json.loads(study[key])
                except json.JSONDecodeError:
                    pass

        if isinstance(study.get("objectives_json"), list):
            study["objectives"] = study["objectives_json"]
        if isinstance(study.get("directions_json"), list):
            study["directions"] = study["directions_json"]
        if isinstance(study.get("constraints_json"), list):
            study["constraints"] = study["constraints_json"]
        if isinstance(study.get("best_values_json"), dict):
            study["best_values"] = study["best_values_json"]

        csv_path = study.get("csv_file_path")
        csv_exists = bool(csv_path and Path(csv_path).exists())

        trials: List[Dict] = []
        windows: List[Dict] = []
        manual_tests: List[Dict] = []

        if study.get("optimization_mode") == "optuna":
            cursor = conn.execute(
                "SELECT * FROM trials WHERE study_id = ?",
                (study_id,),
            )
            for row in cursor.fetchall():
                trial = dict(row)
                trial["params"] = json.loads(trial["params_json"])
                trial["objective_values"] = json.loads(trial["objective_values_json"] or "[]")
                trial["constraint_values"] = json.loads(trial["constraint_values_json"] or "[]")
                trial["is_pareto_optimal"] = bool(trial.get("is_pareto_optimal"))
                trial["constraints_satisfied"] = bool(trial.get("constraints_satisfied"))
                if trial.get("composite_score") is not None:
                    trial["score"] = trial.get("composite_score")
                trials.append(trial)
            objectives = study.get("objectives_json") or []
            if isinstance(objectives, list) and objectives:
                directions = study.get("directions_json") or []
                primary_objective = study.get("primary_objective") or objectives[0]
                try:
                    primary_idx = objectives.index(primary_objective)
                except ValueError:
                    primary_idx = 0
                primary_direction = None
                if isinstance(directions, list) and len(directions) > primary_idx:
                    primary_direction = directions[primary_idx]
                if primary_direction not in {"maximize", "minimize"}:
                    primary_direction = OBJECTIVE_DIRECTIONS.get(primary_objective, "maximize")

                constraints_payload = study.get("constraints_json") or []
                constraints_enabled = any(
                    bool(item.get("enabled")) for item in constraints_payload if isinstance(item, dict)
                )

                if len(objectives) == 1:
                    reverse = primary_direction == "maximize"
                    trials.sort(
                        key=lambda t: float(t.get("objective_values", [0.0])[0]),
                        reverse=reverse,
                    )
                else:
                    def _calculate_total_violation(item: Dict[str, Any]) -> float:
                        values = item.get("constraint_values") or []
                        if not values:
                            if item.get("constraints_satisfied") is False:
                                return float("inf")
                            return 0.0
                        try:
                            return sum(max(0.0, float(v)) for v in values)
                        except (TypeError, ValueError):
                            return float("inf")

                    def group_rank(item: Dict[str, Any]) -> int:
                        if constraints_enabled:
                            if not item.get("constraints_satisfied", True):
                                return 2
                            return 0 if item.get("is_pareto_optimal") else 1
                        return 0 if item.get("is_pareto_optimal") else 1

                    def primary_value(item: Dict[str, Any]) -> float:
                        values = item.get("objective_values") or []
                        value = float(values[primary_idx]) if len(values) > primary_idx else 0.0
                        return -value if primary_direction == "maximize" else value

                    trials.sort(
                        key=lambda t: (
                            group_rank(t),
                            _calculate_total_violation(t),
                            primary_value(t),
                            int(t.get("trial_number") or 0),
                        ),
                    )
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

        cursor = conn.execute(
            """
            SELECT
                id, study_id, created_at, test_name, data_source, csv_path,
                start_date, end_date, source_tab, trials_count, trials_tested_csv,
                best_profit_degradation, worst_profit_degradation
            FROM manual_tests
            WHERE study_id = ?
            ORDER BY created_at DESC
            """,
            (study_id,),
        )
        manual_tests = [dict(row) for row in cursor.fetchall()]

    return {
        "study": study,
        "trials": trials,
        "windows": windows,
        "manual_tests": manual_tests,
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
            SET csv_file_path = ?
            WHERE study_id = ?
            """,
            (new_path, study_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def update_study_status(study_id: str, status: str, error_message: Optional[str] = None) -> bool:
    if not status:
        return False
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE studies
            SET completed_at = ?
            WHERE study_id = ?
            """,
            (datetime.utcnow().isoformat() + "Z", study_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def update_study_config_json(study_id: str, config_json: Dict[str, Any]) -> bool:
    if not isinstance(config_json, dict):
        return False
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE studies
            SET config_json = ?
            WHERE study_id = ?
            """,
            (json.dumps(config_json), study_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def save_forward_test_results(
    study_id: str,
    ft_results: List[Any],
    *,
    ft_enabled: bool,
    ft_period_days: Optional[int],
    ft_top_k: Optional[int],
    ft_sort_metric: Optional[str],
    ft_start_date: Optional[str],
    ft_end_date: Optional[str],
    is_period_days: Optional[int],
) -> bool:
    if not study_id:
        return False

    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute(
                """
                UPDATE studies
                SET
                    ft_enabled = ?,
                    ft_period_days = ?,
                    ft_top_k = ?,
                    ft_sort_metric = ?,
                    ft_start_date = ?,
                    ft_end_date = ?,
                    is_period_days = ?
                WHERE study_id = ?
                """,
                (
                    1 if ft_enabled else 0,
                    ft_period_days,
                    ft_top_k,
                    ft_sort_metric,
                    _format_date(ft_start_date),
                    _format_date(ft_end_date),
                    is_period_days,
                    study_id,
                ),
            )

            if ft_results:
                rows = []
                for result in ft_results:
                    payload = result
                    if hasattr(result, "__dict__"):
                        payload = result.__dict__
                    rows.append(
                        (
                            payload.get("ft_net_profit_pct"),
                            payload.get("ft_max_drawdown_pct"),
                            payload.get("ft_total_trades"),
                            payload.get("ft_win_rate"),
                            payload.get("ft_sharpe_ratio"),
                            payload.get("ft_sortino_ratio"),
                            payload.get("ft_romad"),
                            payload.get("ft_profit_factor"),
                            payload.get("ft_ulcer_index"),
                            payload.get("ft_sqn"),
                            payload.get("ft_consistency_score"),
                            payload.get("profit_degradation"),
                            payload.get("ft_rank"),
                            study_id,
                            payload.get("trial_number"),
                        )
                    )

                conn.executemany(
                    """
                    UPDATE trials
                    SET
                        ft_net_profit_pct = ?,
                        ft_max_drawdown_pct = ?,
                        ft_total_trades = ?,
                        ft_win_rate = ?,
                        ft_sharpe_ratio = ?,
                        ft_sortino_ratio = ?,
                        ft_romad = ?,
                        ft_profit_factor = ?,
                        ft_ulcer_index = ?,
                        ft_sqn = ?,
                        ft_consistency_score = ?,
                        profit_degradation = ?,
                        ft_rank = ?
                    WHERE study_id = ? AND trial_number = ?
                    """,
                    rows,
                )

            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            raise RuntimeError(f"Failed to save FT results: {exc}")

    return True


def save_dsr_results(
    study_id: str,
    dsr_results: List[Any],
    *,
    dsr_enabled: bool,
    dsr_top_k: Optional[int],
    dsr_n_trials: Optional[int],
    dsr_mean_sharpe: Optional[float],
    dsr_var_sharpe: Optional[float],
) -> bool:
    if not study_id:
        return False

    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute(
                """
                UPDATE studies
                SET
                    dsr_enabled = ?,
                    dsr_top_k = ?,
                    dsr_n_trials = ?,
                    dsr_mean_sharpe = ?,
                    dsr_var_sharpe = ?
                WHERE study_id = ?
                """,
                (
                    1 if dsr_enabled else 0,
                    dsr_top_k,
                    dsr_n_trials,
                    dsr_mean_sharpe,
                    dsr_var_sharpe,
                    study_id,
                ),
            )

            conn.execute(
                """
                UPDATE trials
                SET
                    dsr_probability = NULL,
                    dsr_rank = NULL,
                    dsr_skewness = NULL,
                    dsr_kurtosis = NULL,
                    dsr_track_length = NULL,
                    dsr_luck_share_pct = NULL
                WHERE study_id = ?
                """,
                (study_id,),
            )

            if dsr_results:
                rows = []
                for result in dsr_results:
                    payload = result
                    if hasattr(result, "__dict__"):
                        payload = result.__dict__
                    rows.append(
                        (
                            payload.get("dsr_probability"),
                            payload.get("dsr_rank"),
                            payload.get("dsr_skewness"),
                            payload.get("dsr_kurtosis"),
                            payload.get("dsr_track_length"),
                            payload.get("dsr_luck_share_pct"),
                            study_id,
                            payload.get("trial_number"),
                        )
                    )

                conn.executemany(
                    """
                    UPDATE trials
                    SET
                        dsr_probability = ?,
                        dsr_rank = ?,
                        dsr_skewness = ?,
                        dsr_kurtosis = ?,
                        dsr_track_length = ?,
                        dsr_luck_share_pct = ?
                    WHERE study_id = ? AND trial_number = ?
                    """,
                    rows,
                )

            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            raise RuntimeError(f"Failed to save DSR results: {exc}")

    return True


def save_manual_test_to_db(
    *,
    study_id: str,
    test_name: Optional[str],
    data_source: str,
    csv_path: Optional[str],
    start_date: str,
    end_date: str,
    source_tab: str,
    trials_count: int,
    trials_tested_csv: str,
    best_profit_degradation: Optional[float],
    worst_profit_degradation: Optional[float],
    results_json: Dict[str, Any],
) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO manual_tests (
                study_id, test_name, data_source, csv_path,
                start_date, end_date, source_tab,
                trials_count, trials_tested_csv,
                best_profit_degradation, worst_profit_degradation,
                results_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                study_id,
                test_name,
                data_source,
                csv_path,
                start_date,
                end_date,
                source_tab,
                trials_count,
                trials_tested_csv,
                best_profit_degradation,
                worst_profit_degradation,
                json.dumps(results_json),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_manual_tests(study_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                id, study_id, created_at, test_name, data_source, csv_path,
                start_date, end_date, source_tab, trials_count, trials_tested_csv,
                best_profit_degradation, worst_profit_degradation
            FROM manual_tests
            WHERE study_id = ?
            ORDER BY created_at DESC
            """,
            (study_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def load_manual_test_results(study_id: str, test_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM manual_tests WHERE study_id = ? AND id = ?",
            (study_id, int(test_id)),
        )
        row = cursor.fetchone()
        if not row:
            return None
        payload = dict(row)
        if payload.get("results_json"):
            try:
                payload["results_json"] = json.loads(payload["results_json"])
            except json.JSONDecodeError:
                pass
        return payload


def delete_manual_test(study_id: str, test_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM manual_tests WHERE study_id = ? AND id = ?",
            (study_id, int(test_id)),
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
