"""SQLite storage utilities for persisted optimization studies."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
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
    if DB_INITIALIZED and not DB_PATH.exists():
        DB_INITIALIZED = False
    if DB_INITIALIZED and DB_PATH.exists():
        with sqlite3.connect(
            str(DB_PATH),
            check_same_thread=False,
            timeout=30.0,
            isolation_level="DEFERRED",
        ) as conn:
            _configure_connection(conn)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='studies'"
            )
            if cursor.fetchone():
                return
        DB_INITIALIZED = False
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

            st_enabled INTEGER DEFAULT 0,
            st_top_k INTEGER,
            st_failure_threshold REAL,
            st_sort_metric TEXT,
            st_avg_profit_retention REAL,
            st_avg_romad_retention REAL,
            st_avg_combined_failure_rate REAL,
            st_total_perturbations INTEGER,
            st_candidates_skipped_bad_base INTEGER,
            st_candidates_skipped_no_params INTEGER,
            st_candidates_insufficient_data INTEGER,
            optimization_time_seconds INTEGER,

            oos_test_enabled INTEGER DEFAULT 0,
            oos_test_period_days INTEGER,
            oos_test_top_k INTEGER,
            oos_test_start_date TEXT,
            oos_test_end_date TEXT,
            oos_test_source_module TEXT,

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
            max_consecutive_losses INTEGER,
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
            ft_max_consecutive_losses INTEGER,
            ft_sharpe_ratio REAL,
            ft_sortino_ratio REAL,
            ft_romad REAL,
            ft_profit_factor REAL,
            ft_ulcer_index REAL,
            ft_sqn REAL,
            ft_consistency_score REAL,
            profit_degradation REAL,
            ft_rank INTEGER,
            ft_source TEXT,

            dsr_probability REAL,
            dsr_rank INTEGER,
            dsr_skewness REAL,
            dsr_kurtosis REAL,
            dsr_track_length INTEGER,
            dsr_luck_share_pct REAL,

            st_rank INTEGER,
            st_status TEXT,
            profit_retention REAL,
            romad_retention REAL,
            profit_worst REAL,
            profit_lower_tail REAL,
            profit_median REAL,
            romad_worst REAL,
            romad_lower_tail REAL,
            romad_median REAL,
            profit_failure_rate REAL,
            romad_failure_rate REAL,
            combined_failure_rate REAL,
            profit_failure_count INTEGER,
            romad_failure_count INTEGER,
            combined_failure_count INTEGER,
            total_perturbations INTEGER,
            st_failure_threshold REAL,
            param_worst_ratios TEXT,
            most_sensitive_param TEXT,
            st_source TEXT,

            oos_test_net_profit_pct REAL,
            oos_test_max_drawdown_pct REAL,
            oos_test_total_trades INTEGER,
            oos_test_win_rate REAL,
            oos_test_max_consecutive_losses INTEGER,
            oos_test_sharpe_ratio REAL,
            oos_test_sortino_ratio REAL,
            oos_test_romad REAL,
            oos_test_profit_factor REAL,
            oos_test_ulcer_index REAL,
            oos_test_sqn REAL,
            oos_test_consistency_score REAL,
            oos_test_profit_degradation REAL,
            oos_test_source TEXT,
            oos_test_source_rank INTEGER,

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
    _ensure_wfa_schema_updated(conn)


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
    ensure("studies", "st_enabled", "INTEGER DEFAULT 0")
    ensure("studies", "st_top_k", "INTEGER")
    ensure("studies", "st_failure_threshold", "REAL")
    ensure("studies", "st_sort_metric", "TEXT")
    ensure("studies", "st_avg_profit_retention", "REAL")
    ensure("studies", "st_avg_romad_retention", "REAL")
    ensure("studies", "st_avg_combined_failure_rate", "REAL")
    ensure("studies", "st_total_perturbations", "INTEGER")
    ensure("studies", "st_candidates_skipped_bad_base", "INTEGER")
    ensure("studies", "st_candidates_skipped_no_params", "INTEGER")
    ensure("studies", "st_candidates_insufficient_data", "INTEGER")
    ensure("studies", "optimization_time_seconds", "INTEGER")
    ensure("studies", "oos_test_enabled", "INTEGER DEFAULT 0")
    ensure("studies", "oos_test_period_days", "INTEGER")
    ensure("studies", "oos_test_top_k", "INTEGER")
    ensure("studies", "oos_test_start_date", "TEXT")
    ensure("studies", "oos_test_end_date", "TEXT")
    ensure("studies", "oos_test_source_module", "TEXT")

    ensure("trials", "max_consecutive_losses", "INTEGER")
    ensure("trials", "ft_max_consecutive_losses", "INTEGER")
    ensure("trials", "dsr_probability", "REAL")
    ensure("trials", "dsr_rank", "INTEGER")
    ensure("trials", "dsr_skewness", "REAL")
    ensure("trials", "dsr_kurtosis", "REAL")
    ensure("trials", "dsr_track_length", "INTEGER")
    ensure("trials", "dsr_luck_share_pct", "REAL")
    ensure("trials", "st_rank", "INTEGER")
    ensure("trials", "st_status", "TEXT")
    ensure("trials", "profit_retention", "REAL")
    ensure("trials", "romad_retention", "REAL")
    ensure("trials", "profit_worst", "REAL")
    ensure("trials", "profit_lower_tail", "REAL")
    ensure("trials", "profit_median", "REAL")
    ensure("trials", "romad_worst", "REAL")
    ensure("trials", "romad_lower_tail", "REAL")
    ensure("trials", "romad_median", "REAL")
    ensure("trials", "profit_failure_rate", "REAL")
    ensure("trials", "romad_failure_rate", "REAL")
    ensure("trials", "combined_failure_rate", "REAL")
    ensure("trials", "profit_failure_count", "INTEGER")
    ensure("trials", "romad_failure_count", "INTEGER")
    ensure("trials", "combined_failure_count", "INTEGER")
    ensure("trials", "total_perturbations", "INTEGER")
    ensure("trials", "st_failure_threshold", "REAL")
    ensure("trials", "param_worst_ratios", "TEXT")
    ensure("trials", "most_sensitive_param", "TEXT")
    ensure("trials", "oos_test_net_profit_pct", "REAL")
    ensure("trials", "oos_test_max_drawdown_pct", "REAL")
    ensure("trials", "oos_test_total_trades", "INTEGER")
    ensure("trials", "oos_test_win_rate", "REAL")
    ensure("trials", "oos_test_max_consecutive_losses", "INTEGER")
    ensure("trials", "oos_test_sharpe_ratio", "REAL")
    ensure("trials", "oos_test_sortino_ratio", "REAL")
    ensure("trials", "oos_test_romad", "REAL")
    ensure("trials", "oos_test_profit_factor", "REAL")
    ensure("trials", "oos_test_ulcer_index", "REAL")
    ensure("trials", "oos_test_sqn", "REAL")
    ensure("trials", "oos_test_consistency_score", "REAL")
    ensure("trials", "oos_test_profit_degradation", "REAL")
    ensure("trials", "oos_test_source", "TEXT")
    ensure("trials", "oos_test_source_rank", "INTEGER")


def _ensure_wfa_schema_updated(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS wfa_window_trials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            window_id TEXT NOT NULL,
            module_type TEXT NOT NULL,
            trial_number INTEGER NOT NULL,
            params_json TEXT NOT NULL,
            param_id TEXT,
            source_rank INTEGER,
            module_rank INTEGER,
            net_profit_pct REAL,
            max_drawdown_pct REAL,
            total_trades INTEGER,
            win_rate REAL,
            profit_factor REAL,
            romad REAL,
            sharpe_ratio REAL,
            sortino_ratio REAL,
            sqn REAL,
            ulcer_index REAL,
            consistency_score REAL,
            max_consecutive_losses INTEGER,
            composite_score REAL,
            objective_values_json TEXT,
            constraint_values_json TEXT,
            constraints_satisfied INTEGER,
            is_pareto_optimal INTEGER,
            dominance_rank INTEGER,
            status TEXT,
            is_selected INTEGER DEFAULT 0,
            module_metrics_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (window_id) REFERENCES wfa_windows(window_id) ON DELETE CASCADE
        );
        """
    )

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_window ON wfa_window_trials(window_id);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_module ON wfa_window_trials(window_id, module_type);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_trial ON wfa_window_trials(window_id, trial_number);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_selected ON wfa_window_trials(window_id, module_type, is_selected);"
    )

    cur.execute("PRAGMA table_info(wfa_windows);")
    existing = {row[1] for row in cur.fetchall()}

    def add_col(col_sql: str, col_name: str) -> None:
        if col_name not in existing:
            cur.execute(col_sql)

    add_col("ALTER TABLE wfa_windows ADD COLUMN best_params_source TEXT;", "best_params_source")
    add_col("ALTER TABLE wfa_windows ADD COLUMN available_modules TEXT;", "available_modules")
    add_col("ALTER TABLE wfa_windows ADD COLUMN module_status_json TEXT;", "module_status_json")
    add_col("ALTER TABLE wfa_windows ADD COLUMN selection_chain_json TEXT;", "selection_chain_json")
    add_col("ALTER TABLE wfa_windows ADD COLUMN store_top_n_trials INTEGER;", "store_top_n_trials")
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_pareto_optimal INTEGER;", "is_pareto_optimal")
    add_col("ALTER TABLE wfa_windows ADD COLUMN constraints_satisfied INTEGER;", "constraints_satisfied")

    add_col("ALTER TABLE wfa_windows ADD COLUMN optimization_start_date TEXT;", "optimization_start_date")
    add_col("ALTER TABLE wfa_windows ADD COLUMN optimization_end_date TEXT;", "optimization_end_date")
    add_col("ALTER TABLE wfa_windows ADD COLUMN ft_start_date TEXT;", "ft_start_date")
    add_col("ALTER TABLE wfa_windows ADD COLUMN ft_end_date TEXT;", "ft_end_date")
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_timestamps_json TEXT;", "is_timestamps_json")
    add_col("ALTER TABLE wfa_windows ADD COLUMN oos_timestamps_json TEXT;", "oos_timestamps_json")

    add_col("ALTER TABLE wfa_windows ADD COLUMN is_win_rate REAL;", "is_win_rate")
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_max_consecutive_losses INTEGER;", "is_max_consecutive_losses")
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_romad REAL;", "is_romad")
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_sharpe_ratio REAL;", "is_sharpe_ratio")
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_profit_factor REAL;", "is_profit_factor")
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_sqn REAL;", "is_sqn")
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_ulcer_index REAL;", "is_ulcer_index")
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_consistency_score REAL;", "is_consistency_score")
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_composite_score REAL;", "is_composite_score")

    add_col("ALTER TABLE wfa_windows ADD COLUMN oos_win_rate REAL;", "oos_win_rate")
    add_col("ALTER TABLE wfa_windows ADD COLUMN oos_max_consecutive_losses INTEGER;", "oos_max_consecutive_losses")
    add_col("ALTER TABLE wfa_windows ADD COLUMN oos_romad REAL;", "oos_romad")
    add_col("ALTER TABLE wfa_windows ADD COLUMN oos_sharpe_ratio REAL;", "oos_sharpe_ratio")
    add_col("ALTER TABLE wfa_windows ADD COLUMN oos_profit_factor REAL;", "oos_profit_factor")
    add_col("ALTER TABLE wfa_windows ADD COLUMN oos_sqn REAL;", "oos_sqn")
    add_col("ALTER TABLE wfa_windows ADD COLUMN oos_ulcer_index REAL;", "oos_ulcer_index")
    add_col("ALTER TABLE wfa_windows ADD COLUMN oos_consistency_score REAL;", "oos_consistency_score")

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

    summary = getattr(config, "optuna_summary", None) or {}
    optimization_time_seconds = summary.get("optimization_time_seconds")
    if optimization_time_seconds is None and start_time:
        optimization_time_seconds = max(0, time.time() - float(start_time))
    try:
        optimization_time_seconds = int(round(float(optimization_time_seconds))) if optimization_time_seconds is not None else None
    except (TypeError, ValueError):
        optimization_time_seconds = None

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
            _ensure_wfa_schema_updated(conn)
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
                    optimization_time_seconds,
                    completed_at,
                    filter_min_profit, min_profit_threshold,
                    sanitize_enabled, sanitize_trades_threshold
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    optimization_time_seconds,
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
                        result.max_consecutive_losses,
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
                        net_profit_pct, max_drawdown_pct, total_trades, win_rate, max_consecutive_losses, avg_win, avg_loss,
                        gross_profit, gross_loss,
                        romad, sharpe_ratio, sortino_ratio, profit_factor, ulcer_index, sqn,
                        consistency_score, composite_score,
                        ft_net_profit_pct, ft_max_drawdown_pct, ft_total_trades, ft_win_rate,
                        ft_sharpe_ratio, ft_sortino_ratio, ft_romad, ft_profit_factor,
                        ft_ulcer_index, ft_sqn, ft_consistency_score, profit_degradation, ft_rank
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

            def _tri_state(value: Optional[bool]) -> Optional[int]:
                if value is None:
                    return None
                return 1 if value else 0

            def _serialize_timestamps(values: Optional[List[Any]]) -> Optional[str]:
                if not values:
                    return None
                return json.dumps(
                    [
                        value.isoformat() if hasattr(value, "isoformat") else value
                        for value in values
                    ]
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
                oos_timestamps = _serialize_timestamps(getattr(window, "oos_timestamps", None))
                is_timestamps = _serialize_timestamps(getattr(window, "is_timestamps", None))
                available_modules = getattr(window, "available_modules", None)
                window_rows.append(
                    (
                        f"{study_id}_w{window.window_id}",
                        study_id,
                        window.window_id,
                        json.dumps(window.best_params),
                        window.param_id,
                        getattr(window, "best_params_source", None),
                        _tri_state(getattr(window, "is_pareto_optimal", None)),
                        _tri_state(getattr(window, "constraints_satisfied", None)),
                        json.dumps(available_modules) if available_modules is not None else None,
                        getattr(wf_result.config, "store_top_n_trials", None),
                        json.dumps(getattr(window, "module_status", None))
                        if getattr(window, "module_status", None) is not None
                        else None,
                        json.dumps(getattr(window, "selection_chain", None))
                        if getattr(window, "selection_chain", None) is not None
                        else None,
                        _format_date(getattr(window, "optimization_start", None)),
                        _format_date(getattr(window, "optimization_end", None)),
                        _format_date(getattr(window, "ft_start", None)),
                        _format_date(getattr(window, "ft_end", None)),
                        is_timestamps,
                        _format_date(window.is_start),
                        _format_date(window.is_end),
                        window.is_net_profit_pct,
                        window.is_max_drawdown_pct,
                        window.is_total_trades,
                        getattr(window, "is_best_trial_number", None),
                        is_equity,
                        getattr(window, "is_win_rate", None),
                        getattr(window, "is_max_consecutive_losses", None),
                        getattr(window, "is_romad", None),
                        getattr(window, "is_sharpe_ratio", None),
                        getattr(window, "is_profit_factor", None),
                        getattr(window, "is_sqn", None),
                        getattr(window, "is_ulcer_index", None),
                        getattr(window, "is_consistency_score", None),
                        getattr(window, "is_composite_score", None),
                        _format_date(window.oos_start),
                        _format_date(window.oos_end),
                        window.oos_net_profit_pct,
                        window.oos_max_drawdown_pct,
                        window.oos_total_trades,
                        oos_equity,
                        oos_timestamps,
                        getattr(window, "oos_win_rate", None),
                        getattr(window, "oos_max_consecutive_losses", None),
                        getattr(window, "oos_romad", None),
                        getattr(window, "oos_sharpe_ratio", None),
                        getattr(window, "oos_profit_factor", None),
                        getattr(window, "oos_sqn", None),
                        getattr(window, "oos_ulcer_index", None),
                        getattr(window, "oos_consistency_score", None),
                        getattr(window, "wfe", None),
                    )
                )

            if window_rows:
                conn.executemany(
                    """
                    INSERT INTO wfa_windows (
                        window_id, study_id, window_number,
                        best_params_json, param_id, best_params_source,
                        is_pareto_optimal, constraints_satisfied,
                        available_modules, store_top_n_trials,
                        module_status_json, selection_chain_json,
                        optimization_start_date, optimization_end_date,
                        ft_start_date, ft_end_date,
                        is_timestamps_json,
                        is_start_date, is_end_date,
                        is_net_profit_pct, is_max_drawdown_pct, is_total_trades, is_best_trial_number,
                        is_equity_curve,
                        is_win_rate, is_max_consecutive_losses, is_romad, is_sharpe_ratio,
                        is_profit_factor, is_sqn, is_ulcer_index, is_consistency_score, is_composite_score,
                        oos_start_date, oos_end_date,
                        oos_net_profit_pct, oos_max_drawdown_pct, oos_total_trades,
                        oos_equity_curve, oos_timestamps_json,
                        oos_win_rate, oos_max_consecutive_losses, oos_romad, oos_sharpe_ratio,
                        oos_profit_factor, oos_sqn, oos_ulcer_index, oos_consistency_score,
                        wfe
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    window_rows,
                )

            for window in wf_result.windows:
                window_key = f"{study_id}_w{window.window_id}"
                _save_window_trials(conn, window_key, "optuna_is", window.optuna_is_trials)
                _save_window_trials(conn, window_key, "dsr", window.dsr_trials)
                _save_window_trials(conn, window_key, "forward_test", window.forward_test_trials)
                _save_window_trials(conn, window_key, "stress_test", window.stress_test_trials)

            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            raise RuntimeError(f"Failed to save WFA study to database: {exc}")

    return study_id


def _save_window_trials(
    conn: sqlite3.Connection,
    window_id: str,
    module_type: str,
    trials: Optional[List[Dict[str, Any]]],
) -> None:
    if not trials:
        return

    def _tri_state(value: Optional[bool]) -> Optional[int]:
        if value is None:
            return None
        return 1 if value else 0

    rows = []
    for trial in trials:
        params = trial.get("params") or {}
        rows.append(
            (
                window_id,
                module_type,
                trial.get("trial_number"),
                json.dumps(params),
                trial.get("param_id"),
                trial.get("source_rank"),
                trial.get("module_rank"),
                trial.get("net_profit_pct"),
                trial.get("max_drawdown_pct"),
                trial.get("total_trades"),
                trial.get("win_rate"),
                trial.get("profit_factor"),
                trial.get("romad"),
                trial.get("sharpe_ratio"),
                trial.get("sortino_ratio"),
                trial.get("sqn"),
                trial.get("ulcer_index"),
                trial.get("consistency_score"),
                trial.get("max_consecutive_losses"),
                trial.get("composite_score"),
                json.dumps(trial.get("objective_values") or []),
                json.dumps(trial.get("constraint_values") or []),
                _tri_state(trial.get("constraints_satisfied")),
                _tri_state(trial.get("is_pareto_optimal")),
                trial.get("dominance_rank"),
                trial.get("status"),
                1 if trial.get("is_selected") else 0,
                json.dumps(trial.get("module_metrics") or {}),
            )
        )

    conn.executemany(
        """
        INSERT INTO wfa_window_trials (
            window_id, module_type, trial_number,
            params_json, param_id,
            source_rank, module_rank,
            net_profit_pct, max_drawdown_pct, total_trades, win_rate, profit_factor,
            romad, sharpe_ratio, sortino_ratio, sqn, ulcer_index, consistency_score,
            max_consecutive_losses,
            composite_score, objective_values_json, constraint_values_json,
            constraints_satisfied, is_pareto_optimal, dominance_rank,
            status, is_selected, module_metrics_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def load_wfa_window_trials(window_id: str) -> Dict[str, List[Dict[str, Any]]]:
    def _parse_json(value: Optional[str], default):
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                module_type,
                trial_number,
                params_json,
                param_id,
                source_rank,
                module_rank,
                net_profit_pct,
                max_drawdown_pct,
                total_trades,
                win_rate,
                profit_factor,
                romad,
                sharpe_ratio,
                sortino_ratio,
                sqn,
                ulcer_index,
                consistency_score,
                max_consecutive_losses,
                composite_score,
                objective_values_json,
                constraint_values_json,
                constraints_satisfied,
                is_pareto_optimal,
                dominance_rank,
                status,
                is_selected,
                module_metrics_json
            FROM wfa_window_trials
            WHERE window_id = ?
            ORDER BY
                CASE WHEN module_type IS NULL THEN 1 ELSE 0 END,
                module_type ASC,
                module_rank ASC,
                source_rank ASC,
                trial_number ASC
            """,
            (window_id,),
        )
        for row in cursor.fetchall():
            trial = dict(row)
            trial["params"] = _parse_json(trial.pop("params_json", None), {})
            trial["objective_values"] = _parse_json(trial.pop("objective_values_json", None), [])
            trial["constraint_values"] = _parse_json(trial.pop("constraint_values_json", None), [])
            trial["module_metrics"] = _parse_json(trial.pop("module_metrics_json", None), {})
            trial["constraints_satisfied"] = (
                None if trial.get("constraints_satisfied") is None else bool(trial.get("constraints_satisfied"))
            )
            trial["is_pareto_optimal"] = (
                None if trial.get("is_pareto_optimal") is None else bool(trial.get("is_pareto_optimal"))
            )
            trial["is_selected"] = bool(trial.get("is_selected"))
            if trial.get("composite_score") is not None and trial.get("score") is None:
                trial["score"] = trial.get("composite_score")
            grouped.setdefault(trial.get("module_type") or "optuna_is", []).append(trial)
    return grouped


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
                if trial.get("param_worst_ratios"):
                    try:
                        trial["param_worst_ratios"] = json.loads(trial["param_worst_ratios"])
                    except json.JSONDecodeError:
                        pass
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
                if window.get("available_modules"):
                    try:
                        window["available_modules"] = json.loads(window["available_modules"])
                    except json.JSONDecodeError:
                        pass
                if window.get("module_status_json"):
                    try:
                        window["module_status"] = json.loads(window["module_status_json"])
                    except json.JSONDecodeError:
                        pass
                if window.get("selection_chain_json"):
                    try:
                        window["selection_chain"] = json.loads(window["selection_chain_json"])
                    except json.JSONDecodeError:
                        pass
                if window.get("is_timestamps_json"):
                    try:
                        window["is_timestamps"] = json.loads(window["is_timestamps_json"])
                    except json.JSONDecodeError:
                        pass
                if window.get("oos_timestamps_json"):
                    try:
                        window["oos_timestamps"] = json.loads(window["oos_timestamps_json"])
                    except json.JSONDecodeError:
                        pass
                if window.get("is_pareto_optimal") is not None:
                    window["is_pareto_optimal"] = bool(window.get("is_pareto_optimal"))
                if window.get("constraints_satisfied") is not None:
                    window["constraints_satisfied"] = bool(window.get("constraints_satisfied"))
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
    ft_source: Optional[str] = None,
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
                            payload.get("ft_max_consecutive_losses"),
                            payload.get("ft_sharpe_ratio"),
                            payload.get("ft_sortino_ratio"),
                            payload.get("ft_romad"),
                            payload.get("ft_profit_factor"),
                            payload.get("ft_ulcer_index"),
                            payload.get("ft_sqn"),
                            payload.get("ft_consistency_score"),
                            payload.get("profit_degradation"),
                            payload.get("ft_rank"),
                            ft_source,
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
                        ft_max_consecutive_losses = ?,
                        ft_sharpe_ratio = ?,
                        ft_sortino_ratio = ?,
                        ft_romad = ?,
                        ft_profit_factor = ?,
                        ft_ulcer_index = ?,
                        ft_sqn = ?,
                        ft_consistency_score = ?,
                        profit_degradation = ?,
                        ft_rank = ?,
                        ft_source = ?
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


def save_stress_test_results(
    study_id: str,
    st_results: List[Any],
    st_summary: Dict[str, Any],
    config: Any,
    *,
    st_source: Optional[str] = None,
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
                    st_enabled = ?,
                    st_top_k = ?,
                    st_failure_threshold = ?,
                    st_sort_metric = ?,
                    st_avg_profit_retention = ?,
                    st_avg_romad_retention = ?,
                    st_avg_combined_failure_rate = ?,
                    st_total_perturbations = ?,
                    st_candidates_skipped_bad_base = ?,
                    st_candidates_skipped_no_params = ?,
                    st_candidates_insufficient_data = ?
                WHERE study_id = ?
                """,
                (
                    1 if getattr(config, "enabled", False) else 0,
                    getattr(config, "top_k", None),
                    getattr(config, "failure_threshold", None),
                    getattr(config, "sort_metric", None),
                    st_summary.get("avg_profit_retention"),
                    st_summary.get("avg_romad_retention"),
                    st_summary.get("avg_combined_failure_rate"),
                    st_summary.get("total_perturbations_run"),
                    st_summary.get("candidates_skipped_bad_base", 0),
                    st_summary.get("candidates_skipped_no_params", 0),
                    st_summary.get("candidates_insufficient_data", 0),
                    study_id,
                ),
            )

            conn.execute(
                """
                UPDATE trials
                SET
                    st_rank = NULL,
                    st_status = NULL,
                    profit_retention = NULL,
                    romad_retention = NULL,
                    profit_worst = NULL,
                    profit_lower_tail = NULL,
                    profit_median = NULL,
                    romad_worst = NULL,
                    romad_lower_tail = NULL,
                    romad_median = NULL,
                    profit_failure_rate = NULL,
                    romad_failure_rate = NULL,
                    combined_failure_rate = NULL,
                    profit_failure_count = NULL,
                    romad_failure_count = NULL,
                    combined_failure_count = NULL,
                    total_perturbations = NULL,
                    st_failure_threshold = NULL,
                    param_worst_ratios = NULL,
                    most_sensitive_param = NULL,
                    st_source = NULL
                WHERE study_id = ?
                """,
                (study_id,),
            )

            if st_results:
                rows = []
                for result in st_results:
                    payload = result
                    if hasattr(result, "__dict__"):
                        payload = result.__dict__
                    param_worst = payload.get("param_worst_ratios") or {}
                    param_worst_json = json.dumps(param_worst) if param_worst else None
                    rows.append(
                        (
                            payload.get("st_rank"),
                            payload.get("status"),
                            payload.get("profit_retention"),
                            payload.get("romad_retention"),
                            payload.get("profit_worst"),
                            payload.get("profit_lower_tail"),
                            payload.get("profit_median"),
                            payload.get("romad_worst"),
                            payload.get("romad_lower_tail"),
                            payload.get("romad_median"),
                            payload.get("profit_failure_rate"),
                            payload.get("romad_failure_rate"),
                            payload.get("combined_failure_rate"),
                            payload.get("profit_failure_count"),
                            payload.get("romad_failure_count"),
                            payload.get("combined_failure_count"),
                            payload.get("total_perturbations"),
                            payload.get("failure_threshold"),
                            param_worst_json,
                            payload.get("most_sensitive_param"),
                            st_source,
                            study_id,
                            payload.get("trial_number"),
                        )
                    )

                conn.executemany(
                    """
                    UPDATE trials
                    SET
                        st_rank = ?,
                        st_status = ?,
                        profit_retention = ?,
                        romad_retention = ?,
                        profit_worst = ?,
                        profit_lower_tail = ?,
                        profit_median = ?,
                        romad_worst = ?,
                        romad_lower_tail = ?,
                        romad_median = ?,
                        profit_failure_rate = ?,
                        romad_failure_rate = ?,
                        combined_failure_rate = ?,
                        profit_failure_count = ?,
                        romad_failure_count = ?,
                        combined_failure_count = ?,
                        total_perturbations = ?,
                        st_failure_threshold = ?,
                        param_worst_ratios = ?,
                        most_sensitive_param = ?,
                        st_source = ?
                    WHERE study_id = ? AND trial_number = ?
                    """,
                    rows,
                )

            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            raise RuntimeError(f"Failed to save stress test results: {exc}")

    return True


def save_oos_test_results(
    study_id: str,
    oos_results: List[Dict[str, Any]],
    *,
    oos_enabled: bool,
    oos_period_days: Optional[int],
    oos_top_k: Optional[int],
    oos_start_date: Optional[str],
    oos_end_date: Optional[str],
    oos_source_module: Optional[str],
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
                    oos_test_enabled = ?,
                    oos_test_period_days = ?,
                    oos_test_top_k = ?,
                    oos_test_start_date = ?,
                    oos_test_end_date = ?,
                    oos_test_source_module = ?
                WHERE study_id = ?
                """,
                (
                    1 if oos_enabled else 0,
                    oos_period_days,
                    oos_top_k,
                    _format_date(oos_start_date),
                    _format_date(oos_end_date),
                    oos_source_module,
                    study_id,
                ),
            )

            conn.execute(
                """
                UPDATE trials
                SET
                    oos_test_net_profit_pct = NULL,
                    oos_test_max_drawdown_pct = NULL,
                    oos_test_total_trades = NULL,
                    oos_test_win_rate = NULL,
                    oos_test_max_consecutive_losses = NULL,
                    oos_test_sharpe_ratio = NULL,
                    oos_test_sortino_ratio = NULL,
                    oos_test_romad = NULL,
                    oos_test_profit_factor = NULL,
                    oos_test_ulcer_index = NULL,
                    oos_test_sqn = NULL,
                    oos_test_consistency_score = NULL,
                    oos_test_profit_degradation = NULL,
                    oos_test_source = NULL,
                    oos_test_source_rank = NULL
                WHERE study_id = ?
                """,
                (study_id,),
            )

            if oos_results:
                rows = []
                for result in oos_results:
                    test_metrics = result.get("test_metrics") or {}
                    comparison = result.get("comparison") or {}
                    rows.append(
                        (
                            test_metrics.get("net_profit_pct"),
                            test_metrics.get("max_drawdown_pct"),
                            test_metrics.get("total_trades"),
                            test_metrics.get("win_rate"),
                            test_metrics.get("max_consecutive_losses"),
                            test_metrics.get("sharpe_ratio"),
                            test_metrics.get("sortino_ratio"),
                            test_metrics.get("romad"),
                            test_metrics.get("profit_factor"),
                            test_metrics.get("ulcer_index"),
                            test_metrics.get("sqn"),
                            test_metrics.get("consistency_score"),
                            comparison.get("profit_degradation"),
                            result.get("oos_test_source"),
                            result.get("oos_test_source_rank"),
                            study_id,
                            result.get("trial_number"),
                        )
                    )

                conn.executemany(
                    """
                    UPDATE trials
                    SET
                        oos_test_net_profit_pct = ?,
                        oos_test_max_drawdown_pct = ?,
                        oos_test_total_trades = ?,
                        oos_test_win_rate = ?,
                        oos_test_max_consecutive_losses = ?,
                        oos_test_sharpe_ratio = ?,
                        oos_test_sortino_ratio = ?,
                        oos_test_romad = ?,
                        oos_test_profit_factor = ?,
                        oos_test_ulcer_index = ?,
                        oos_test_sqn = ?,
                        oos_test_consistency_score = ?,
                        oos_test_profit_degradation = ?,
                        oos_test_source = ?,
                        oos_test_source_rank = ?
                    WHERE study_id = ? AND trial_number = ?
                    """,
                    rows,
                )

            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            raise RuntimeError(f"Failed to save OOS test results: {exc}")

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
