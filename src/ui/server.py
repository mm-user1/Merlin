import hashlib
import io
import json
import math
import re
import sys
import tempfile
import threading
import time
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtest_engine import align_date_bounds, load_data, prepare_dataset_with_warmup
from core.export import export_trades_csv
from core.optuna_engine import (
    CONSTRAINT_OPERATORS,
    OBJECTIVE_DIRECTIONS,
    OBJECTIVE_DISPLAY_NAMES,
    OptimizationConfig,
    OptimizationResult,
    run_optimization,
)
from core.post_process import (
    DSRConfig,
    PostProcessConfig,
    StressTestConfig,
    calculate_comparison_metrics,
    calculate_ft_dates,
    calculate_is_period_days,
    run_dsr_analysis,
    run_forward_test,
    run_stress_test,
    _parse_timestamp as _parse_pp_timestamp,
)
from core.storage import (
    delete_manual_test,
    delete_study,
    get_study_trial,
    list_manual_tests,
    list_studies,
    load_manual_test_results,
    load_study_from_db,
    save_dsr_results,
    save_forward_test_results,
    save_stress_test_results,
    save_manual_test_to_db,
    update_csv_path,
    update_study_config_json,
)

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
    static_url_path="/static",
)

OPTIMIZATION_STATE_LOCK = threading.Lock()
LAST_OPTIMIZATION_STATE: Dict[str, Any] = {
    "status": "idle",
    "updated_at": None,
}


def _set_optimization_state(payload: Dict[str, Any]) -> None:
    with OPTIMIZATION_STATE_LOCK:
        normalized = json.loads(json.dumps(payload))
        normalized["updated_at"] = datetime.utcnow().isoformat() + "Z"
        LAST_OPTIMIZATION_STATE.clear()
        LAST_OPTIMIZATION_STATE.update(normalized)


def _get_optimization_state() -> Dict[str, Any]:
    with OPTIMIZATION_STATE_LOCK:
        return json.loads(json.dumps(LAST_OPTIMIZATION_STATE))


def _persist_csv_upload(file_storage) -> str:
    temp_dir = Path(tempfile.gettempdir()) / "merlin_uploads"
    temp_dir.mkdir(exist_ok=True)
    suffix = Path(file_storage.filename or "upload.csv").suffix or ".csv"
    temp_path = temp_dir / f"upload_{int(time.time())}_{id(file_storage)}{suffix}"
    file_storage.seek(0)
    content = file_storage.read()
    if isinstance(content, str):
        content = content.encode("utf-8")
    temp_path.write_bytes(content)
    return str(temp_path)


def _run_trade_export(
    *,
    strategy_id: str,
    csv_path: str,
    params: Dict[str, Any],
    warmup_bars: int,
) -> Tuple[Optional[List[Any]], Optional[str]]:
    from strategies import get_strategy

    try:
        strategy_class = get_strategy(strategy_id)
    except ValueError as exc:
        return None, str(exc)

    try:
        df = load_data(csv_path)
    except Exception as exc:
        return None, str(exc)

    trade_start_idx = 0
    payload = dict(params or {})
    if payload.get("dateFilter"):
        start_raw = payload.get("start")
        end_raw = payload.get("end")
        start, end = align_date_bounds(df.index, start_raw, end_raw)
        if start_raw not in (None, "") and start is None:
            return None, "Invalid start date."
        if end_raw not in (None, "") and end is None:
            return None, "Invalid end date."
        payload["start"] = start
        payload["end"] = end
        try:
            df, trade_start_idx = prepare_dataset_with_warmup(
                df, start, end, int(warmup_bars)
            )
        except Exception:
            return None, "Failed to prepare dataset with warmup."

    try:
        result = strategy_class.run(df, payload, trade_start_idx)
    except Exception as exc:
        return None, str(exc)

    return result.trades, None


def _send_trades_csv(
    *,
    trades: List[Any],
    csv_path: str,
    study: Dict[str, Any],
    filename: str,
) -> object:
    from core.export import _extract_symbol_from_csv_filename

    csv_name = ""
    if csv_path:
        path_obj = Path(csv_path)
        name = path_obj.name
        parent = path_obj.parent.name
        if parent == "merlin_uploads" or name.startswith("upload_"):
            csv_name = study.get("csv_file_name") or name
        else:
            csv_name = name
    else:
        csv_name = study.get("csv_file_name") or ""
    symbol = _extract_symbol_from_csv_filename(csv_name)
    csv_content = export_trades_csv(trades, symbol=symbol)
    buffer = io.BytesIO(csv_content.encode("utf-8"))
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


def _create_param_id_for_strategy(strategy_id: str, params: Dict[str, Any]) -> str:
    param_str = json.dumps(params, sort_keys=True)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]

    try:
        from strategies import get_strategy_config

        config = get_strategy_config(strategy_id)
        parameters = config.get("parameters", {}) if isinstance(config, dict) else {}

        optimizable: List[str] = []
        for param_name, param_spec in parameters.items():
            if not isinstance(param_spec, dict):
                continue
            optimize_cfg = param_spec.get("optimize", {})
            if isinstance(optimize_cfg, dict) and optimize_cfg.get("enabled", False):
                optimizable.append(param_name)
            if len(optimizable) == 2:
                break

        label_parts = [str(params.get(param_name, "?")) for param_name in optimizable]
        if label_parts:
            label = " ".join(label_parts)
            return f"{label}_{param_hash}"
    except Exception:
        pass

    return param_hash


def _get_parameter_types(strategy_id: str) -> Dict[str, str]:
    """Load parameter types from strategy configuration."""

    from strategies import get_strategy_config

    config = get_strategy_config(strategy_id)
    parameters = config.get("parameters", {}) if isinstance(config, dict) else {}

    param_types: Dict[str, str] = {}
    for param_name, param_spec in parameters.items():
        if not isinstance(param_spec, dict):
            continue
        param_types[param_name] = str(param_spec.get("type", "float"))

    return param_types


def _resolve_strategy_id_from_request() -> Tuple[Optional[str], Optional[object]]:
    from strategies import list_strategies

    json_payload = request.get_json(silent=True) if request.is_json else None
    strategy_id = request.form.get("strategy")

    if not strategy_id and isinstance(json_payload, dict):
        strategy_id = json_payload.get("strategy")

    if strategy_id:
        return strategy_id, None

    available = list_strategies()
    if available:
        return available[0]["id"], None

    return None, (jsonify({"error": "No strategies available."}), HTTPStatus.INTERNAL_SERVER_ERROR)


SCORE_METRIC_KEYS: Tuple[str, ...] = (
    "romad",
    "sharpe",
    "pf",
    "ulcer",
    "sqn",
    "consistency",
)

DEFAULT_OPTIMIZER_SCORE_CONFIG: Dict[str, Any] = {
    "filter_enabled": False,
    "min_score_threshold": 60.0,
    "weights": {
        "romad": 0.25,
        "sharpe": 0.20,
        "pf": 0.20,
        "ulcer": 0.15,
        "sqn": 0.10,
        "consistency": 0.10,
    },
    "enabled_metrics": {
        "romad": True,
        "sharpe": True,
        "pf": True,
        "ulcer": True,
        "sqn": True,
        "consistency": True,
    },
    "invert_metrics": {"ulcer": True},
    "normalization_method": "minmax",
    "metric_bounds": {
        "romad": {"min": 0.0, "max": 10.0},
        "sharpe": {"min": -1.0, "max": 3.0},
        "pf": {"min": 0.0, "max": 5.0},
        "ulcer": {"min": 0.0, "max": 20.0},
        "sqn": {"min": -2.0, "max": 7.0},
        "consistency": {"min": 0.0, "max": 100.0},
    },
}


def validate_objectives_config(
    objectives: List[str],
    primary_objective: Optional[str],
) -> Tuple[bool, Optional[str]]:
    if not objectives or len(objectives) < 1:
        return False, "At least 1 objective is required."
    if len(objectives) > 6:
        return False, "Maximum 6 objectives allowed."
    for obj in objectives:
        if obj not in OBJECTIVE_DIRECTIONS:
            return False, f"Unknown objective: {obj}"
    if len(objectives) > 1:
        if not primary_objective:
            return False, "Primary objective required for multi-objective optimization."
        if primary_objective not in objectives:
            return False, "Primary objective must be one of the selected objectives."
    return True, None


def validate_constraints_config(
    constraints: List[Dict[str, Any]],
) -> Tuple[bool, Optional[str]]:
    for i, spec in enumerate(constraints or []):
        if not isinstance(spec, dict):
            return False, f"Constraint {i + 1}: Invalid constraint format"
        metric = spec.get("metric")
        threshold = spec.get("threshold")
        enabled = spec.get("enabled", False)
        if not enabled:
            continue
        if metric not in CONSTRAINT_OPERATORS:
            return False, f"Constraint {i + 1}: Unknown metric '{metric}'"
        if threshold is None:
            return False, f"Constraint {i + 1}: Threshold is required"
        try:
            float(threshold)
        except (TypeError, ValueError):
            return False, f"Constraint {i + 1}: Threshold must be a number"
    return True, None


def validate_sampler_config(
    sampler_type: str,
    population_size: Optional[int],
    crossover_prob: Optional[float],
) -> Tuple[bool, Optional[str]]:
    valid_samplers = {"tpe", "nsga2", "nsga3", "random"}
    if sampler_type not in valid_samplers:
        return False, f"Unknown sampler: {sampler_type}"
    if sampler_type in ("nsga2", "nsga3"):
        if population_size is not None:
            if population_size < 2:
                return False, "Population size must be at least 2"
            if population_size > 1000:
                return False, "Population size must be at most 1000"
        if crossover_prob is not None:
            if not (0.0 <= crossover_prob <= 1.0):
                return False, "Crossover probability must be between 0 and 1"
    return True, None

PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"
DEFAULT_PRESET_NAME = "defaults"
VALID_PRESET_NAME_RE = re.compile(r"^[A-Za-z0-9 _\-]{1,64}$")

# Default preset containing only date fields.
# Strategy/backtest parameters are added dynamically from payload.
DEFAULT_PRESET: Dict[str, Any] = {
    "dateFilter": True,
    "start": None,
    "end": None,
}
BOOL_FIELDS = {"dateFilter"}
INT_FIELDS = set()
FLOAT_FIELDS = set()

LIST_FIELDS: set = set()
STRING_FIELDS = {"start", "end"}
ALLOWED_PRESET_FIELDS = None  # None = accept all fields (strategy/backtest params included)


def _clone_default_template() -> Dict[str, Any]:
    # Use minimal defaults only. Strategy defaults are in strategy.py.
    return json.loads(json.dumps(DEFAULT_PRESET))


def _ensure_presets_directory() -> None:
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    defaults_path = PRESETS_DIR / f"{DEFAULT_PRESET_NAME}.json"
    if not defaults_path.exists():
        _write_preset(DEFAULT_PRESET_NAME, DEFAULT_PRESET)


def _validate_preset_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Preset name must be a string.")
    normalized = name.strip()
    if not normalized:
        raise ValueError("Preset name cannot be empty.")
    if normalized.lower() == DEFAULT_PRESET_NAME:
        raise ValueError("Use the defaults endpoint to overwrite default settings.")
    if not VALID_PRESET_NAME_RE.match(normalized):
        raise ValueError(
            "Preset name may only contain letters, numbers, spaces, hyphens, and underscores."
        )
    return normalized


def _preset_path(name: str) -> Path:
    safe_name = Path(name).name
    return PRESETS_DIR / f"{safe_name}.json"


def _write_preset(name: str, values: Dict[str, Any]) -> None:
    path = _preset_path(name)
    serialized = json.loads(json.dumps(values))
    with path.open("w", encoding="utf-8") as handle:
        json.dump(serialized, handle, ensure_ascii=False, indent=2, sort_keys=False)


def _load_preset(name: str) -> Dict[str, Any]:
    path = _preset_path(name)
    if not path.exists():
        raise FileNotFoundError(name)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Preset file is corrupted.")
    return data


def _list_presets() -> List[Dict[str, Any]]:
    presets: List[Dict[str, Any]] = []
    for path in sorted(PRESETS_DIR.glob("*.json")):
        name = path.stem
        presets.append({"name": name, "is_default": name.lower() == DEFAULT_PRESET_NAME})
    return presets


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    return False


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            if math.isinf(value):
                return "inf" if value > 0 else "-inf"
            return "nan"
        return value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _split_timestamp(value: str) -> Tuple[str, str]:
    normalized = (value or "").strip()
    if not normalized:
        return "", ""
    candidate = normalized.replace(" ", "T", 1)
    candidate = candidate.rstrip("Zz")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        if "T" in normalized:
            date_part, _, time_part = normalized.partition("T")
        elif " " in normalized:
            date_part, _, time_part = normalized.partition(" ")
        else:
            return normalized, ""
        return date_part.strip(), time_part.strip()
    date_part = parsed.date().isoformat()
    if parsed.time().second == 0 and parsed.time().microsecond == 0:
        time_part = parsed.time().strftime("%H:%M")
    else:
        time_part = parsed.time().strftime("%H:%M:%S")
    return date_part, time_part


def _convert_import_value(name: str, raw_value: str) -> Any:
    if name in BOOL_FIELDS:
        return _coerce_bool(raw_value)
    if name in INT_FIELDS:
        try:
            return int(round(float(raw_value)))
        except (TypeError, ValueError):
            return 0
    if name in FLOAT_FIELDS:
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return 0.0
    return raw_value


def _parse_csv_parameter_block(file_storage) -> Tuple[Dict[str, Any], List[str], List[str]]:
    content = file_storage.read()
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = str(content)

    lines = text.splitlines()
    csv_parameters: Dict[str, Any] = {}
    applied: List[str] = []

    header_seen = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if header_seen:
                break
            continue
        if not header_seen:
            header_seen = True
            continue
        name, _, value = line.partition(",")
        param_name = name.strip()
        if not param_name:
            continue
        csv_parameters[param_name] = value.strip()

    updates: Dict[str, Any] = {}
    # Use strategy config to drive type-aware parsing so imports stay generic across strategies.
    strategy_id = request.form.get("strategy")
    if not strategy_id and request.is_json:
        payload = request.get_json(silent=True) or {}
        if isinstance(payload, dict):
            strategy_id = payload.get("strategy")

    param_types: Dict[str, str] = {}
    strategy_resolution_error = None
    if not strategy_id:
        try:
            from strategies import list_strategies

            available = list_strategies()
            if available:
                strategy_id = available[0]["id"]
        except Exception:
            strategy_id = None
            strategy_resolution_error = (
                "Strategy not provided and no strategies discovered to infer parameter types."
            )

    if strategy_id:
        try:
            from strategies import get_strategy_config

            config = get_strategy_config(strategy_id)
            config_parameters = config.get("parameters", {}) if isinstance(config, dict) else {}
            for param_name, param_spec in config_parameters.items():
                if not isinstance(param_spec, dict):
                    continue
                param_types[param_name] = str(param_spec.get("type", "float")).lower()
        except Exception:
            param_types = {}
            strategy_resolution_error = (
                f"Strategy '{strategy_id}' configuration could not be loaded for type inference."
            )

    # If strategy typing is unavailable, refuse to silently import strategy-specific parameters.
    if not param_types:
        # Fields that are safe to import without strategy typing.
        untyped_allowed_fields = {"start", "end", "dateFilter"}
        missing_typed_fields = [
            name for name in csv_parameters.keys() if name not in untyped_allowed_fields
        ]
        if missing_typed_fields:
            reason = strategy_resolution_error or "Parameter types unavailable."
            formatted = ", ".join(sorted(missing_typed_fields))
            raise ValueError(
                f"Cannot import CSV because strategy parameter types are unavailable. "
                f"Unsupported fields without typing: {formatted}. {reason}"
            )

    errors: List[str] = []

    for name, raw_value in csv_parameters.items():
        if name == "start":
            date_part, time_part = _split_timestamp(raw_value)
            if date_part:
                updates["startDate"] = date_part
                applied.append("startDate")
            if time_part:
                updates["startTime"] = time_part
                applied.append("startTime")
            continue
        if name == "end":
            date_part, time_part = _split_timestamp(raw_value)
            if date_part:
                updates["endDate"] = date_part
                applied.append("endDate")
            if time_part:
                updates["endTime"] = time_part
                applied.append("endTime")
            continue

        param_type = param_types.get(name, "")
        if param_type in {"select", "options"}:
            value = str(raw_value or "").strip().upper()
            if value:
                updates[name] = value
                applied.append(name)
            continue
        if param_type == "int":
            try:
                updates[name] = int(round(float(raw_value)))
            except (TypeError, ValueError):
                errors.append(f"{name}: expected integer, got '{raw_value}'")
            else:
                applied.append(name)
            continue
        if param_type == "float":
            try:
                updates[name] = float(raw_value)
            except (TypeError, ValueError):
                errors.append(f"{name}: expected number, got '{raw_value}'")
            else:
                applied.append(name)
            continue
        if param_type in {"bool", "boolean"}:
            updates[name] = _coerce_bool(raw_value)
            applied.append(name)
            continue

        converted = _convert_import_value(name, raw_value)
        updates[name] = converted
        applied.append(name)

    return updates, applied, errors


def _validate_strategy_params(strategy_id: str, params: Dict[str, Any]) -> None:
    """Validate and coerce strategy parameters based on config definitions."""

    from strategies import get_strategy_config

    try:
        config = get_strategy_config(strategy_id)
    except Exception:
        return

    definitions = config.get("parameters", {}) if isinstance(config, dict) else {}
    if not isinstance(definitions, dict):
        return

    for name, definition in definitions.items():
        if not isinstance(definition, dict):
            continue

        value = params.get(name)
        if value is None:
            continue

        param_type = definition.get("type", "float")

        if param_type == "int":
            if not isinstance(value, int):
                try:
                    params[name] = int(value)
                except (TypeError, ValueError):
                    raise ValueError(f"{name} must be an integer")
        elif param_type == "float":
            if not isinstance(value, (int, float)):
                try:
                    params[name] = float(value)
                except (TypeError, ValueError):
                    raise ValueError(f"{name} must be a number")
        elif param_type in {"select", "options"}:
            options = definition.get("options", [])
            if options and value not in options:
                raise ValueError(f"{name} must be one of {options}, got {value}")
        elif param_type == "bool":
            if not isinstance(value, bool):
                params[name] = bool(value)

        if param_type in {"int", "float"}:
            min_value = definition.get("min")
            max_value = definition.get("max")
            numeric_value = params.get(name)
            if min_value is not None and numeric_value < min_value:
                raise ValueError(f"{name} must be >= {min_value}")
            if max_value is not None and numeric_value > max_value:
                raise ValueError(f"{name} must be <= {max_value}")


_ensure_presets_directory()


def _normalize_preset_payload(values: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(values, dict):
        raise ValueError("Preset values must be provided as a dictionary.")
    normalized = _clone_default_template()
    for key, value in values.items():
        if key in LIST_FIELDS:
            if isinstance(value, (list, tuple)):
                cleaned = [str(item).strip().upper() for item in value if str(item).strip()]
            elif isinstance(value, str) and value.strip():
                cleaned = [value.strip().upper()]
            else:
                cleaned = []
            if cleaned:
                normalized[key] = cleaned
            continue
        if key in BOOL_FIELDS:
            normalized[key] = _coerce_bool(value)
            continue
        if key in INT_FIELDS:
            try:
                converted = int(round(float(value)))
            except (TypeError, ValueError):
                continue
            if key == "workerProcesses":
                if converted < 1:
                    converted = 1
                elif converted > 32:
                    converted = 32
            normalized[key] = converted
            continue
        if key in FLOAT_FIELDS:
            try:
                converted_float = float(value)
            except (TypeError, ValueError):
                continue
            if key == "minProfitThreshold":
                converted_float = max(0.0, min(99000.0, converted_float))
            normalized[key] = converted_float
            continue
        if key in STRING_FIELDS:
            normalized[key] = str(value).strip()
            continue
        normalized[key] = value
    return normalized


def _resolve_csv_path(raw_path: str) -> Path:
    if raw_path is None:
        raise ValueError("CSV path is empty.")
    raw_value = str(raw_path).strip()
    if not raw_value:
        raise ValueError("CSV path is empty.")
    candidate = Path(raw_value).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(str(candidate)) from exc
    if not resolved.is_file():
        raise IsADirectoryError(str(resolved))
    return resolved


def _validate_csv_for_study(csv_path: str, study: Dict[str, Any]) -> Tuple[bool, List[str], Optional[str]]:
    warnings: List[str] = []
    try:
        df = load_data(csv_path)
    except Exception as exc:
        return False, warnings, str(exc)

    expected_start = study.get("dataset_start_date")
    expected_end = study.get("dataset_end_date")
    if expected_start:
        try:
            expected_start_ts = pd.Timestamp(expected_start).date()
            if df.index[0].date() != expected_start_ts:
                warnings.append(
                    f"Dataset start date differs (expected {expected_start}, got {df.index[0].date()})."
                )
        except Exception:
            warnings.append("Could not validate dataset start date.")
    if expected_end:
        try:
            expected_end_ts = pd.Timestamp(expected_end).date()
            if df.index[-1].date() != expected_end_ts:
                warnings.append(
                    f"Dataset end date differs (expected {expected_end}, got {df.index[-1].date()})."
                )
        except Exception:
            warnings.append("Could not validate dataset end date.")

    original_name = study.get("csv_file_name")
    if original_name:
        selected_name = Path(csv_path).name
        if selected_name != original_name:
            warnings.append(
                f"Filename differs from original ({original_name} vs {selected_name})."
            )

    return True, warnings, None


@app.route("/")
def index() -> object:
    return render_template("index.html")


@app.route("/results")
def results_page() -> object:
    return render_template("results.html")


@app.get("/api/optimization/status")
def optimization_status() -> object:
    return jsonify(_get_optimization_state())


@app.post("/api/optimization/cancel")
def optimization_cancel() -> object:
    state = _get_optimization_state()
    state["status"] = "cancelled"
    _set_optimization_state(state)
    return jsonify({"status": "cancelled"})


@app.get("/api/studies")
def list_studies_endpoint() -> object:
    return jsonify({"studies": list_studies()})


@app.get("/api/studies/<string:study_id>")
def get_study_endpoint(study_id: str) -> object:
    study_data = load_study_from_db(study_id)
    if not study_data:
        return jsonify({"error": "Study not found."}), HTTPStatus.NOT_FOUND
    return jsonify(_json_safe(study_data))


@app.delete("/api/studies/<string:study_id>")
def delete_study_endpoint(study_id: str) -> object:
    deleted = delete_study(study_id)
    if not deleted:
        return jsonify({"error": "Study not found."}), HTTPStatus.NOT_FOUND
    return ("", HTTPStatus.NO_CONTENT)


@app.post("/api/studies/<string:study_id>/update-csv-path")
def update_study_csv_path_endpoint(study_id: str) -> object:
    study_data = load_study_from_db(study_id)
    if not study_data:
        return jsonify({"error": "Study not found."}), HTTPStatus.NOT_FOUND

    csv_file = request.files.get("file")
    csv_path_raw = None
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if isinstance(payload, dict):
            csv_path_raw = payload.get("csvPath") or payload.get("csv_file_path")
    if csv_path_raw is None:
        csv_path_raw = request.form.get("csvPath")

    if csv_file and csv_file.filename:
        new_path = _persist_csv_upload(csv_file)
    elif csv_path_raw:
        try:
            new_path = str(_resolve_csv_path(csv_path_raw))
        except (FileNotFoundError, IsADirectoryError, ValueError, OSError) as exc:
            return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
    else:
        return jsonify({"error": "CSV file or path is required."}), HTTPStatus.BAD_REQUEST

    is_valid, warnings, error = _validate_csv_for_study(new_path, study_data["study"])
    if not is_valid:
        return jsonify({"error": error or "CSV validation failed."}), HTTPStatus.BAD_REQUEST

    updated = update_csv_path(study_id, new_path)
    if not updated:
        return jsonify({"error": "Failed to update CSV path."}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"status": "updated", "warnings": warnings, "csv_file_path": new_path})


@app.post("/api/studies/<string:study_id>/test")
def run_manual_test_endpoint(study_id: str) -> object:
    payload = request.get_json(silent=True) if request.is_json else None
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid manual test payload."}), HTTPStatus.BAD_REQUEST

    data_source = payload.get("dataSource")
    csv_path = payload.get("csvPath")
    start_date = payload.get("startDate")
    end_date = payload.get("endDate")
    trial_numbers = payload.get("trialNumbers") or []
    source_tab = payload.get("sourceTab")
    test_name = payload.get("testName")

    if data_source not in {"original_csv", "new_csv"}:
        return jsonify({"error": "dataSource must be 'original_csv' or 'new_csv'."}), HTTPStatus.BAD_REQUEST
    if source_tab not in {"optuna", "forward_test", "dsr"}:
        return jsonify({"error": "sourceTab must be 'optuna', 'forward_test', or 'dsr'."}), HTTPStatus.BAD_REQUEST
    if not start_date or not end_date:
        return jsonify({"error": "startDate and endDate are required."}), HTTPStatus.BAD_REQUEST
    if not isinstance(trial_numbers, list) or not trial_numbers:
        return jsonify({"error": "trialNumbers must be a non-empty array."}), HTTPStatus.BAD_REQUEST

    study_data = load_study_from_db(study_id)
    if not study_data:
        return jsonify({"error": "Study not found."}), HTTPStatus.NOT_FOUND
    study = study_data["study"]
    if study.get("optimization_mode") != "optuna":
        return jsonify({"error": "Manual tests are supported only for Optuna studies."}), HTTPStatus.BAD_REQUEST

    if data_source == "original_csv":
        csv_path = study.get("csv_file_path")
        if not csv_path:
            return jsonify({"error": "Original CSV path is missing."}), HTTPStatus.BAD_REQUEST
    elif not csv_path:
        return jsonify({"error": "csvPath is required when dataSource is 'new_csv'."}), HTTPStatus.BAD_REQUEST

    if not csv_path or not Path(csv_path).exists():
        return jsonify({"error": "CSV file not found."}), HTTPStatus.BAD_REQUEST

    start_ts = _parse_pp_timestamp(start_date)
    end_ts = _parse_pp_timestamp(end_date)
    if start_ts is None or end_ts is None:
        return jsonify({"error": "Invalid startDate/endDate."}), HTTPStatus.BAD_REQUEST

    test_period_days = max(0, (end_ts - start_ts).days)
    if test_period_days <= 0:
        return jsonify({"error": "Test period must be at least 1 day."}), HTTPStatus.BAD_REQUEST

    config = study.get("config_json") or {}
    fixed_params = config.get("fixed_params") or {}
    warmup_bars = study.get("warmup_bars") or config.get("warmup_bars") or 1000

    trials = study_data.get("trials") or []
    trial_map = {int(t.get("trial_number")): t for t in trials}
    missing = [n for n in trial_numbers if int(n) not in trial_map]
    if missing:
        return jsonify({"error": f"Trials not found: {', '.join(map(str, missing))}."}), HTTPStatus.BAD_REQUEST

    baseline_rank_map: Dict[int, int] = {}
    if source_tab == "optuna":
        for idx, trial in enumerate(trials, 1):
            number = int(trial.get("trial_number") or 0)
            if number:
                baseline_rank_map[number] = idx
    elif source_tab == "forward_test":
        for trial in trials:
            number = int(trial.get("trial_number") or 0)
            rank = trial.get("ft_rank")
            if number and rank:
                baseline_rank_map[number] = int(rank)
    else:
        for trial in trials:
            number = int(trial.get("trial_number") or 0)
            rank = trial.get("dsr_rank")
            if number and rank:
                baseline_rank_map[number] = int(rank)

    if not baseline_rank_map:
        for idx, trial in enumerate(trials, 1):
            number = int(trial.get("trial_number") or 0)
            if number:
                baseline_rank_map[number] = idx

    try:
        df = load_data(csv_path)
    except Exception as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    aligned_start, aligned_end = align_date_bounds(df.index, start_date, end_date)
    if aligned_start is None or aligned_end is None:
        return jsonify({"error": "Invalid startDate/endDate."}), HTTPStatus.BAD_REQUEST
    start_ts = aligned_start
    end_ts = aligned_end

    from strategies import get_strategy
    from core import metrics

    try:
        strategy_class = get_strategy(study.get("strategy_id"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    baseline_period_days = None
    if source_tab == "forward_test":
        baseline_period_days = study.get("ft_period_days")
    if baseline_period_days is None:
        baseline_period_days = study.get("is_period_days")
    if baseline_period_days is None:
        baseline_period_days = calculate_is_period_days(config) or 0

    results_payload: List[Dict[str, Any]] = []
    for number in trial_numbers:
        trial_number = int(number)
        trial = trial_map[trial_number]

        params = {**fixed_params, **(trial.get("params") or {})}
        params["dateFilter"] = True
        params["start"] = start_ts
        params["end"] = end_ts

        try:
            df_prepared, trade_start_idx = prepare_dataset_with_warmup(
                df, start_ts, end_ts, int(warmup_bars)
            )
        except Exception as exc:
            return jsonify({"error": f"Failed to prepare dataset: {exc}"}), HTTPStatus.BAD_REQUEST

        try:
            result = strategy_class.run(df_prepared, params, trade_start_idx)
        except Exception as exc:
            return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

        basic = metrics.calculate_basic(result, 100.0)
        advanced = metrics.calculate_advanced(result, 100.0)

        test_metrics = {
            "net_profit_pct": basic.net_profit_pct,
            "max_drawdown_pct": basic.max_drawdown_pct,
            "total_trades": basic.total_trades,
            "win_rate": basic.win_rate,
            "sharpe_ratio": advanced.sharpe_ratio,
            "romad": advanced.romad,
            "profit_factor": advanced.profit_factor,
        }

        if source_tab == "forward_test":
            original_metrics = {
                "net_profit_pct": trial.get("ft_net_profit_pct") or 0.0,
                "max_drawdown_pct": trial.get("ft_max_drawdown_pct") or 0.0,
                "total_trades": trial.get("ft_total_trades") or 0,
                "win_rate": trial.get("ft_win_rate") or 0.0,
                "sharpe_ratio": trial.get("ft_sharpe_ratio"),
                "romad": trial.get("ft_romad"),
                "profit_factor": trial.get("ft_profit_factor"),
            }
        else:
            original_metrics = {
                "net_profit_pct": trial.get("net_profit_pct") or 0.0,
                "max_drawdown_pct": trial.get("max_drawdown_pct") or 0.0,
                "total_trades": trial.get("total_trades") or 0,
                "win_rate": trial.get("win_rate") or 0.0,
                "sharpe_ratio": trial.get("sharpe_ratio"),
                "romad": trial.get("romad"),
                "profit_factor": trial.get("profit_factor"),
            }

        comparison = calculate_comparison_metrics(
            original_metrics,
            test_metrics,
            int(baseline_period_days or 0),
            int(test_period_days),
        )

        results_payload.append(
            {
                "trial_number": trial_number,
                "original_metrics": original_metrics,
                "test_metrics": test_metrics,
                "comparison": comparison,
            }
        )

    for idx, item in enumerate(results_payload, 1):
        trial_number = item.get("trial_number")
        baseline_rank = baseline_rank_map.get(trial_number)
        if baseline_rank is not None:
            item["comparison"]["rank_change"] = baseline_rank - idx
        else:
            item["comparison"]["rank_change"] = None

    degradations = [item["comparison"].get("profit_degradation", 0.0) for item in results_payload]
    best_deg = max(degradations) if degradations else None
    worst_deg = min(degradations) if degradations else None

    results_json = {
        "config": {
            "data_source": data_source,
            "csv_path": csv_path,
            "start_date": start_date,
            "end_date": end_date,
            "period_days": int(test_period_days),
        },
        "results": results_payload,
    }

    trials_tested_csv = ",".join(str(int(n)) for n in trial_numbers)
    test_id = save_manual_test_to_db(
        study_id=study_id,
        test_name=test_name,
        data_source=data_source,
        csv_path=csv_path,
        start_date=start_date,
        end_date=end_date,
        source_tab=source_tab,
        trials_count=len(results_payload),
        trials_tested_csv=trials_tested_csv,
        best_profit_degradation=best_deg,
        worst_profit_degradation=worst_deg,
        results_json=results_json,
    )

    return jsonify(
        {
            "status": "success",
            "test_id": test_id,
            "summary": {
                "trials_count": len(results_payload),
                "best_profit_degradation": best_deg,
                "worst_profit_degradation": worst_deg,
            },
        }
    )


@app.get("/api/studies/<string:study_id>/tests")
def list_manual_tests_endpoint(study_id: str) -> object:
    if not study_id:
        return jsonify({"error": "Study ID is required."}), HTTPStatus.BAD_REQUEST
    return jsonify({"tests": list_manual_tests(study_id)})


@app.get("/api/studies/<string:study_id>/tests/<int:test_id>")
def get_manual_test_results_endpoint(study_id: str, test_id: int) -> object:
    result = load_manual_test_results(study_id, test_id)
    if not result:
        return jsonify({"error": "Manual test not found."}), HTTPStatus.NOT_FOUND
    return jsonify(result)


@app.delete("/api/studies/<string:study_id>/tests/<int:test_id>")
def delete_manual_test_endpoint(study_id: str, test_id: int) -> object:
    deleted = delete_manual_test(study_id, test_id)
    if not deleted:
        return jsonify({"error": "Manual test not found."}), HTTPStatus.NOT_FOUND
    return ("", HTTPStatus.NO_CONTENT)


@app.post("/api/studies/<string:study_id>/trials/<int:trial_number>/trades")
def download_trial_trades(study_id: str, trial_number: int) -> object:
    study_data = load_study_from_db(study_id)
    if not study_data:
        return jsonify({"error": "Study not found."}), HTTPStatus.NOT_FOUND

    study = study_data["study"]
    if study.get("optimization_mode") != "optuna":
        return jsonify({"error": "Trade export is only supported for Optuna studies."}), HTTPStatus.BAD_REQUEST

    csv_path = study.get("csv_file_path")
    if not csv_path or not Path(csv_path).exists():
        return jsonify({"error": "CSV file is missing for this study."}), HTTPStatus.BAD_REQUEST

    trial = get_study_trial(study_id, trial_number)
    if not trial:
        return jsonify({"error": "Trial not found."}), HTTPStatus.NOT_FOUND

    config = study.get("config_json") or {}
    fixed_params = config.get("fixed_params") or {}

    params = {**fixed_params, **(trial.get("params") or {})}
    warmup_bars = study.get("warmup_bars") or config.get("warmup_bars") or 1000

    trades, error = _run_trade_export(
        strategy_id=study.get("strategy_id"),
        csv_path=csv_path,
        params=params,
        warmup_bars=warmup_bars,
    )
    if error:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    filename = f"{study.get('study_name', 'study')}_trial_{trial_number}_trades.csv"
    return _send_trades_csv(
        trades=trades or [],
        csv_path=csv_path,
        study=study,
        filename=filename,
    )


@app.post("/api/studies/<string:study_id>/trials/<int:trial_number>/ft-trades")
def download_forward_test_trades(study_id: str, trial_number: int) -> object:
    study_data = load_study_from_db(study_id)
    if not study_data:
        return jsonify({"error": "Study not found."}), HTTPStatus.NOT_FOUND

    study = study_data["study"]
    if study.get("optimization_mode") != "optuna":
        return jsonify({"error": "Trade export is only supported for Optuna studies."}), HTTPStatus.BAD_REQUEST
    if not study.get("ft_enabled"):
        return jsonify({"error": "Forward test is not enabled for this study."}), HTTPStatus.BAD_REQUEST

    csv_path = study.get("csv_file_path")
    if not csv_path or not Path(csv_path).exists():
        return jsonify({"error": "CSV file is missing for this study."}), HTTPStatus.BAD_REQUEST

    trial = get_study_trial(study_id, trial_number)
    if not trial:
        return jsonify({"error": "Trial not found."}), HTTPStatus.NOT_FOUND

    ft_start = study.get("ft_start_date")
    ft_end = study.get("ft_end_date")
    if not ft_start or not ft_end:
        return jsonify({"error": "Forward test date range is missing."}), HTTPStatus.BAD_REQUEST

    config = study.get("config_json") or {}
    fixed_params = config.get("fixed_params") or {}
    params = {**fixed_params, **(trial.get("params") or {})}
    params["dateFilter"] = True
    params["start"] = ft_start
    params["end"] = ft_end

    warmup_bars = study.get("warmup_bars") or config.get("warmup_bars") or 1000

    trades, error = _run_trade_export(
        strategy_id=study.get("strategy_id"),
        csv_path=csv_path,
        params=params,
        warmup_bars=warmup_bars,
    )
    if error:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    filename = f"{study.get('study_name', 'study')}_trial_{trial_number}_ft_trades.csv"
    return _send_trades_csv(
        trades=trades or [],
        csv_path=csv_path,
        study=study,
        filename=filename,
    )


@app.post("/api/studies/<string:study_id>/tests/<int:test_id>/trials/<int:trial_number>/mt-trades")
def download_manual_test_trades(study_id: str, test_id: int, trial_number: int) -> object:
    study_data = load_study_from_db(study_id)
    if not study_data:
        return jsonify({"error": "Study not found."}), HTTPStatus.NOT_FOUND

    study = study_data["study"]
    if study.get("optimization_mode") != "optuna":
        return jsonify({"error": "Manual trade export is only supported for Optuna studies."}), HTTPStatus.BAD_REQUEST

    test = load_manual_test_results(study_id, test_id)
    if not test:
        return jsonify({"error": "Manual test not found."}), HTTPStatus.NOT_FOUND

    csv_path = test.get("csv_path")
    if not csv_path and test.get("data_source") == "original_csv":
        csv_path = study.get("csv_file_path")
    if not csv_path or not Path(csv_path).exists():
        return jsonify({"error": "CSV file is missing for this manual test."}), HTTPStatus.BAD_REQUEST

    trial = get_study_trial(study_id, trial_number)
    if not trial:
        return jsonify({"error": "Trial not found."}), HTTPStatus.NOT_FOUND
    trials_tested_csv = test.get("trials_tested_csv") or ""
    if trials_tested_csv:
        try:
            tested = {int(item.strip()) for item in trials_tested_csv.split(",") if item.strip()}
        except ValueError:
            tested = set()
        if tested and int(trial_number) not in tested:
            return jsonify({"error": "Trial not included in this manual test."}), HTTPStatus.BAD_REQUEST

    start_date = test.get("start_date")
    end_date = test.get("end_date")
    if not start_date or not end_date:
        return jsonify({"error": "Manual test date range is missing."}), HTTPStatus.BAD_REQUEST

    config = study.get("config_json") or {}
    fixed_params = config.get("fixed_params") or {}
    params = {**fixed_params, **(trial.get("params") or {})}
    params["dateFilter"] = True
    params["start"] = start_date
    params["end"] = end_date

    warmup_bars = study.get("warmup_bars") or config.get("warmup_bars") or 1000

    trades, error = _run_trade_export(
        strategy_id=study.get("strategy_id"),
        csv_path=csv_path,
        params=params,
        warmup_bars=warmup_bars,
    )
    if error:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    filename = f"{study.get('study_name', 'study')}_test_{test_id}_trial_{trial_number}_mt_trades.csv"
    return _send_trades_csv(
        trades=trades or [],
        csv_path=csv_path,
        study=study,
        filename=filename,
    )


@app.post("/api/studies/<string:study_id>/wfa/trades")
def download_wfa_trades(study_id: str) -> object:
    study_data = load_study_from_db(study_id)
    if not study_data:
        return jsonify({"error": "Study not found."}), HTTPStatus.NOT_FOUND

    study = study_data["study"]
    if study.get("optimization_mode") != "wfa":
        return jsonify({"error": "Trade export is only supported for WFA studies."}), HTTPStatus.BAD_REQUEST

    csv_path = study.get("csv_file_path")
    if not csv_path or not Path(csv_path).exists():
        return jsonify({"error": "CSV file is missing for this study."}), HTTPStatus.BAD_REQUEST

    windows = study_data.get("windows") or []
    if not windows:
        return jsonify({"error": "No WFA windows available for this study."}), HTTPStatus.BAD_REQUEST

    config = study.get("config_json") or {}
    fixed_params = config.get("fixed_params") or {}
    warmup_bars = study.get("warmup_bars") or config.get("warmup_bars") or 1000

    from strategies import get_strategy

    try:
        strategy_class = get_strategy(study.get("strategy_id"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    try:
        df = load_data(csv_path)
    except Exception as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    def _normalize_ts(value: Any) -> Optional[pd.Timestamp]:
        if value is None or value == "":
            return None
        if isinstance(value, pd.Timestamp):
            ts = value
        else:
            ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")

    def _align_window_ts(value: Any, *, side: str) -> Optional[pd.Timestamp]:
        """Align date-only window boundaries to actual bar timestamps in the dataset."""
        ts = _normalize_ts(value)
        if ts is None or df.empty:
            return ts
        is_date_only = False
        if isinstance(value, str):
            stripped = value.strip()
            is_date_only = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", stripped))
        if not is_date_only:
            return ts
        if side == "start":
            idx = df.index.searchsorted(ts, side="left")
            if idx >= len(df.index):
                return None
            return df.index[idx]
        if side == "end":
            day_end = ts + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            idx = df.index.searchsorted(day_end, side="right") - 1
            if idx < 0:
                return None
            return df.index[idx]
        return ts

    all_trades = []
    for window in windows:
        start = _align_window_ts(window.get("oos_start_date") or window.get("oos_start"), side="start")
        end = _align_window_ts(window.get("oos_end_date") or window.get("oos_end"), side="end")
        if start is None or end is None:
            continue

        params = {**fixed_params, **(window.get("best_params") or {})}
        params["dateFilter"] = True
        params["start"] = start
        params["end"] = end

        try:
            df_prepared, trade_start_idx = prepare_dataset_with_warmup(
                df, start, end, int(warmup_bars)
            )
        except Exception:
            return jsonify({"error": "Failed to prepare dataset with warmup."}), HTTPStatus.BAD_REQUEST

        try:
            result = strategy_class.run(df_prepared, params, trade_start_idx)
        except Exception as exc:
            return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

        window_trades = [
            trade
            for trade in result.trades
            if trade.entry_time and start <= trade.entry_time <= end
        ]
        all_trades.extend(window_trades)


    all_trades.sort(key=lambda t: t.entry_time or pd.Timestamp.min)

    from core.export import _extract_symbol_from_csv_filename

    symbol = _extract_symbol_from_csv_filename(study.get("csv_file_name") or "")
    csv_content = export_trades_csv(all_trades, symbol=symbol)
    buffer = io.BytesIO(csv_content.encode("utf-8"))
    buffer.seek(0)

    filename = f"{study.get('study_name', 'study')}_wfa_oos_trades.csv"
    return send_file(
        buffer,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


@app.get("/api/presets")
def list_presets_endpoint() -> object:
    presets = _list_presets()
    return jsonify({"presets": presets})


@app.get("/api/presets/<string:name>")
def load_preset_endpoint(name: str) -> object:
    target = Path(name).stem
    try:
        values = _load_preset(target)
    except FileNotFoundError:
        return ("Preset not found.", HTTPStatus.NOT_FOUND)
    except ValueError as exc:
        app.logger.exception("Failed to load preset '%s'", name)
        return (str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
    return jsonify({"name": target, "values": values})


@app.post("/api/presets")
def create_preset_endpoint() -> object:
    if not request.is_json:
        return ("Expected JSON body.", HTTPStatus.BAD_REQUEST)
    payload = request.get_json() or {}
    try:
        name = _validate_preset_name(payload.get("name"))
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)

    normalized_name_lower = name.lower()
    for entry in _list_presets():
        if entry["name"].lower() == normalized_name_lower:
            return ("Preset with this name already exists.", HTTPStatus.CONFLICT)

    try:
        values = _normalize_preset_payload(payload.get("values", {}))
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)

    try:
        _write_preset(name, values)
    except Exception:  # pragma: no cover - defensive
        app.logger.exception("Failed to save preset '%s'", name)
        return ("Failed to save preset.", HTTPStatus.INTERNAL_SERVER_ERROR)

    return jsonify({"name": name, "values": values}), HTTPStatus.CREATED


@app.put("/api/presets/<string:name>")
def overwrite_preset_endpoint(name: str) -> object:
    if not request.is_json:
        return ("Expected JSON body.", HTTPStatus.BAD_REQUEST)
    try:
        normalized_name = _validate_preset_name(name)
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)

    preset_path = _preset_path(normalized_name)
    if not preset_path.exists():
        return ("Preset not found.", HTTPStatus.NOT_FOUND)

    payload = request.get_json() or {}
    try:
        values = _normalize_preset_payload(payload.get("values", {}))
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)

    try:
        _write_preset(normalized_name, values)
    except Exception:  # pragma: no cover - defensive
        app.logger.exception("Failed to overwrite preset '%s'", name)
        return ("Failed to save preset.", HTTPStatus.INTERNAL_SERVER_ERROR)

    return jsonify({"name": normalized_name, "values": values})


@app.put("/api/presets/defaults")
def overwrite_defaults_endpoint() -> object:
    if not request.is_json:
        return ("Expected JSON body.", HTTPStatus.BAD_REQUEST)
    payload = request.get_json() or {}
    try:
        values = _normalize_preset_payload(payload.get("values", {}))
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)

    try:
        _write_preset(DEFAULT_PRESET_NAME, values)
    except Exception:  # pragma: no cover - defensive
        app.logger.exception("Failed to overwrite default preset")
        return ("Failed to save default preset.", HTTPStatus.INTERNAL_SERVER_ERROR)

    return jsonify({"name": DEFAULT_PRESET_NAME, "values": values})


@app.delete("/api/presets/<string:name>")
def delete_preset_endpoint(name: str) -> object:
    target = Path(name).stem
    if target.lower() == DEFAULT_PRESET_NAME:
        return ("Default preset cannot be deleted.", HTTPStatus.BAD_REQUEST)
    path = _preset_path(target)
    if not path.exists():
        return ("Preset not found.", HTTPStatus.NOT_FOUND)
    try:
        path.unlink()
    except Exception:  # pragma: no cover - defensive
        app.logger.exception("Failed to delete preset '%s'", name)
        return ("Failed to delete preset.", HTTPStatus.INTERNAL_SERVER_ERROR)
    return ("", HTTPStatus.NO_CONTENT)


@app.post("/api/presets/import-csv")
def import_preset_from_csv() -> object:
    if "file" not in request.files:
        return ("CSV file is required.", HTTPStatus.BAD_REQUEST)
    csv_file = request.files["file"]
    if not csv_file or csv_file.filename == "":
        return ("CSV file is required.", HTTPStatus.BAD_REQUEST)
    try:
        updates, applied, errors = _parse_csv_parameter_block(csv_file)
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception:  # pragma: no cover - defensive
        app.logger.exception("Failed to parse CSV for preset import")
        return ("Failed to parse CSV file.", HTTPStatus.BAD_REQUEST)
    if errors:
        return (
            jsonify({"error": "Invalid numeric values in CSV.", "details": errors}),
            HTTPStatus.BAD_REQUEST,
        )
    if not updates:
        return ("No fixed parameters found in CSV.", HTTPStatus.BAD_REQUEST)
    return jsonify({"values": updates, "applied": applied})


@app.post("/api/walkforward")
def run_walkforward_optimization() -> object:
    """Run Walk-Forward Analysis"""
    data = request.form
    csv_file = request.files.get("file")
    csv_path_raw = (data.get("csvPath") or "").strip()
    data_source = None
    data_path = ""
    original_csv_name = ""

    try:
        if csv_file and csv_file.filename:
            data_path = _persist_csv_upload(csv_file)
            data_source = data_path
            original_csv_name = csv_file.filename
        elif csv_path_raw:
            resolved_path = _resolve_csv_path(csv_path_raw)
            data_source = str(resolved_path)
            data_path = str(resolved_path)
            original_csv_name = Path(resolved_path).name
        else:
            return jsonify({"error": "CSV file is required."}), HTTPStatus.BAD_REQUEST
    except (FileNotFoundError, IsADirectoryError, ValueError):
        return jsonify({"error": "CSV file is required."}), HTTPStatus.BAD_REQUEST
    except OSError:
        return jsonify({"error": "Failed to access CSV file."}), HTTPStatus.BAD_REQUEST

    config_raw = data.get("config")
    if not config_raw:
        return jsonify({"error": "Missing optimization config."}), HTTPStatus.BAD_REQUEST

    try:
        config_payload = json.loads(config_raw)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid optimization config JSON."}), HTTPStatus.BAD_REQUEST

    post_process_payload = config_payload.get("postProcess")
    if not isinstance(post_process_payload, dict):
        post_process_payload = {}

    objectives = config_payload.get("objectives", [])
    primary_objective = config_payload.get("primary_objective")
    valid, error = validate_objectives_config(objectives, primary_objective)
    if not valid:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    constraints = config_payload.get("constraints", [])
    valid, error = validate_constraints_config(constraints)
    if not valid:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    sampler_type = str(config_payload.get("sampler", "tpe")).strip().lower()
    population_size = config_payload.get("population_size")
    crossover_prob = config_payload.get("crossover_prob")
    try:
        population_size_val = int(population_size) if population_size is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "Population size must be a number."}), HTTPStatus.BAD_REQUEST
    try:
        crossover_prob_val = float(crossover_prob) if crossover_prob is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "Crossover probability must be a number."}), HTTPStatus.BAD_REQUEST

    valid, error = validate_sampler_config(sampler_type, population_size_val, crossover_prob_val)
    if not valid:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    strategy_id, error_response = _resolve_strategy_id_from_request()
    if error_response:
        return error_response

    warmup_bars_raw = data.get("warmupBars", "1000")
    try:
        warmup_bars = int(warmup_bars_raw)
        warmup_bars = max(100, min(5000, warmup_bars))
    except (TypeError, ValueError):
        warmup_bars = 1000

    try:
        optimization_config = _build_optimization_config(
            data_source,
            config_payload,
            warmup_bars=warmup_bars,
            strategy_id=strategy_id,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
    except Exception:  # pragma: no cover - defensive
        app.logger.exception("Failed to build optimization config for walk-forward")
        return jsonify({"error": "Failed to prepare optimization config."}), HTTPStatus.INTERNAL_SERVER_ERROR

    if optimization_config.optimization_mode != "optuna":
        return jsonify({"error": "Walk-Forward requires Optuna optimization mode."}), HTTPStatus.BAD_REQUEST

    if hasattr(data_source, "seek"):
        try:
            data_source.seek(0)
        except Exception:  # pragma: no cover - defensive
            pass

    try:
        df = load_data(data_source)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
    except Exception:  # pragma: no cover - defensive
        app.logger.exception("Failed to load CSV for walk-forward")
        return jsonify({"error": "Failed to load CSV data."}), HTTPStatus.INTERNAL_SERVER_ERROR

    # Apply date filtering for Walk-Forward Analysis
    use_date_filter = optimization_config.fixed_params.get('dateFilter', False)
    start_date = optimization_config.fixed_params.get('start')
    end_date = optimization_config.fixed_params.get('end')

    if use_date_filter and start_date is not None and end_date is not None:
        try:
            # Ensure dates are pandas Timestamps with UTC timezone
            start_ts, end_ts = align_date_bounds(df.index, start_date, end_date)
            if start_ts is None or end_ts is None:
                return jsonify({"error": "Invalid date filter range."}), HTTPStatus.BAD_REQUEST

            # IMPORTANT: Add warmup period before start_ts for Walk-Forward Analysis
            # The first WFA window will start from start_ts, so it needs historical data.
            # Use the user-specified warmup bars (default 1000) as-is to avoid strategy-specific logic.

            # Find the index of start_ts in the dataframe
            start_idx = df.index.searchsorted(start_ts)

            # Calculate warmup_start_idx (go back warmup_bars, but not before 0)
            warmup_start_idx = max(0, start_idx - warmup_bars)

            # Get the actual warmup start timestamp
            warmup_start_ts = df.index[warmup_start_idx]

            # Filter dataframe: include warmup period before start_ts
            df_filtered = df[(df.index >= warmup_start_ts) & (df.index <= end_ts)].copy()

            # Check that we have enough data in the ACTUAL trading period (start_ts to end_ts)
            df_trading_period = df[(df.index >= start_ts) & (df.index <= end_ts)]
            if len(df_trading_period) < 1000:
                return jsonify({
                    "error": f"Selected date range contains only {len(df_trading_period)} bars. Need at least 1000 bars for Walk-Forward Analysis."
                }), HTTPStatus.BAD_REQUEST

            df = df_filtered
            actual_warmup_bars = start_idx - warmup_start_idx
            print(f"Walk-Forward: Using date-filtered data with warmup: {len(df)} bars total")
            print(f"  Warmup period: {actual_warmup_bars} bars from {warmup_start_ts} to {start_ts}")
            print(f"  Trading period: {len(df_trading_period)} bars from {start_ts} to {end_ts}")

        except Exception as e:
            return jsonify({"error": f"Failed to apply date filter: {str(e)}"}), HTTPStatus.BAD_REQUEST

    optimization_config.warmup_bars = warmup_bars
    optimization_config.csv_original_name = original_csv_name

    base_template = {
        "enabled_params": json.loads(json.dumps(optimization_config.enabled_params)),
        "param_ranges": json.loads(json.dumps(optimization_config.param_ranges)),
        "param_types": json.loads(json.dumps(optimization_config.param_types)),
        "fixed_params": json.loads(json.dumps(optimization_config.fixed_params)),
        "risk_per_trade_pct": float(optimization_config.risk_per_trade_pct),
        "contract_size": float(optimization_config.contract_size),
        "commission_rate": float(optimization_config.commission_rate),
        "worker_processes": int(optimization_config.worker_processes),
        "filter_min_profit": bool(optimization_config.filter_min_profit),
        "min_profit_threshold": float(optimization_config.min_profit_threshold),
        "score_config": json.loads(json.dumps(optimization_config.score_config or {})),
        "strategy_id": optimization_config.strategy_id,
        "warmup_bars": optimization_config.warmup_bars,
        "csv_original_name": original_csv_name,
        "objectives": list(getattr(optimization_config, "objectives", []) or []),
        "primary_objective": getattr(optimization_config, "primary_objective", None),
        "constraints": json.loads(json.dumps(getattr(optimization_config, "constraints", []) or [])),
        "sampler_type": getattr(optimization_config, "sampler_type", "tpe"),
        "population_size": getattr(optimization_config, "population_size", None),
        "crossover_prob": getattr(optimization_config, "crossover_prob", None),
        "mutation_prob": getattr(optimization_config, "mutation_prob", None),
        "swapping_prob": getattr(optimization_config, "swapping_prob", None),
        "n_startup_trials": getattr(optimization_config, "n_startup_trials", 20),
    }
    if post_process_payload:
        base_template["postProcess"] = post_process_payload

    optuna_settings = {
        "objectives": list(getattr(optimization_config, "objectives", []) or []),
        "primary_objective": getattr(optimization_config, "primary_objective", None),
        "constraints": json.loads(json.dumps(getattr(optimization_config, "constraints", []) or [])),
        "budget_mode": getattr(optimization_config, "optuna_budget_mode", "trials"),
        "n_trials": int(getattr(optimization_config, "optuna_n_trials", 100)),
        "time_limit": int(getattr(optimization_config, "optuna_time_limit", 3600)),
        "convergence_patience": int(getattr(optimization_config, "optuna_convergence", 50)),
        "enable_pruning": bool(getattr(optimization_config, "optuna_enable_pruning", True)),
        "sampler": getattr(optimization_config, "sampler_type", "tpe"),
        "population_size": getattr(optimization_config, "population_size", None),
        "crossover_prob": getattr(optimization_config, "crossover_prob", None),
        "mutation_prob": getattr(optimization_config, "mutation_prob", None),
        "swapping_prob": getattr(optimization_config, "swapping_prob", None),
        "pruner": getattr(optimization_config, "optuna_pruner", "median"),
        "warmup_trials": int(getattr(optimization_config, "n_startup_trials", 20)),
        "save_study": bool(getattr(optimization_config, "optuna_save_study", False)),
    }

    try:
        is_period_days = int(data.get("wf_is_period_days", 90))
        oos_period_days = int(data.get("wf_oos_period_days", 30))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid Walk-Forward parameters."}), HTTPStatus.BAD_REQUEST

    is_period_days = max(1, min(3650, is_period_days))
    oos_period_days = max(1, min(3650, oos_period_days))

    from core.walkforward_engine import WFConfig, WalkForwardEngine

    post_process_config = None
    if post_process_payload.get("enabled"):
        post_process_config = PostProcessConfig(
            enabled=True,
            ft_period_days=int(post_process_payload.get("ftPeriodDays", 15)),
            top_k=int(post_process_payload.get("topK", 5)),
            sort_metric=str(post_process_payload.get("sortMetric", "profit_degradation")),
            warmup_bars=warmup_bars,
        )

    dsr_config = None
    if post_process_payload.get("dsrEnabled"):
        try:
            dsr_top_k = int(post_process_payload.get("dsrTopK", 20))
        except (TypeError, ValueError):
            dsr_top_k = 20
        dsr_config = DSRConfig(
            enabled=True,
            top_k=dsr_top_k,
            warmup_bars=warmup_bars,
        )

    st_config = None
    st_payload = post_process_payload.get("stressTest")
    if isinstance(st_payload, dict) and st_payload.get("enabled"):
        try:
            st_top_k = int(st_payload.get("topK", 5))
        except (TypeError, ValueError):
            st_top_k = 5
        try:
            threshold_raw = float(st_payload.get("failureThreshold", 0.7))
        except (TypeError, ValueError):
            threshold_raw = 0.7
        failure_threshold = threshold_raw / 100.0 if threshold_raw > 1 else threshold_raw
        st_config = StressTestConfig(
            enabled=True,
            top_k=st_top_k,
            failure_threshold=failure_threshold,
            sort_metric=str(st_payload.get("sortMetric", "profit_retention")),
            warmup_bars=warmup_bars,
        )

    wf_config = WFConfig(
        is_period_days=is_period_days,
        oos_period_days=oos_period_days,
        warmup_bars=warmup_bars,
        strategy_id=strategy_id,
        post_process=post_process_config,
        dsr_config=dsr_config,
        stress_test_config=st_config,
    )
    engine = WalkForwardEngine(wf_config, base_template, optuna_settings, csv_file_path=data_path)

    _set_optimization_state(
        {
            "status": "running",
            "mode": "wfa",
            "strategy_id": strategy_id,
            "data_path": data_path,
            "config": config_payload,
            "wfa": {
                "is_period_days": is_period_days,
                "oos_period_days": oos_period_days,
            },
        }
    )

    try:
        result, study_id = engine.run_wf_optimization(df)
    except ValueError as exc:
        _set_optimization_state(
            {
                "status": "error",
                "mode": "wfa",
                "strategy_id": strategy_id,
                "error": str(exc),
            }
        )
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
    except Exception:  # pragma: no cover - defensive
        _set_optimization_state(
            {
                "status": "error",
                "mode": "wfa",
                "strategy_id": strategy_id,
                "error": "Walk-forward optimization failed.",
            }
        )
        app.logger.exception("Walk-forward optimization failed")
        return jsonify({"error": "Walk-forward optimization failed."}), HTTPStatus.INTERNAL_SERVER_ERROR

    stitched_oos = result.stitched_oos

    response_payload = {
        "status": "success",
        "summary": {
            "total_windows": result.total_windows,
            "stitched_oos_net_profit_pct": round(result.stitched_oos.final_net_profit_pct, 2),
            "stitched_oos_max_drawdown_pct": round(result.stitched_oos.max_drawdown_pct, 2),
            "stitched_oos_total_trades": result.stitched_oos.total_trades,
            "wfe": round(result.stitched_oos.wfe, 2),
            "oos_win_rate": round(result.stitched_oos.oos_win_rate, 1),
        },
        "mode": "wfa",
        "strategy_id": strategy_id,
        "data_path": data_path,
        "study_id": study_id,
    }

    _set_optimization_state(
        {
            "status": "completed",
            "mode": "wfa",
            "strategy_id": strategy_id,
            "data_path": data_path,
            "summary": response_payload.get("summary", {}),
            "study_id": study_id,
        }
    )

    return jsonify(response_payload)


@app.post("/api/backtest")
def run_backtest() -> object:
    """Run single backtest with selected strategy"""

    strategy_id, error_response = _resolve_strategy_id_from_request()
    if error_response:
        return error_response

    # Get warmup bars
    warmup_bars_raw = request.form.get("warmupBars", "1000")
    try:
        warmup_bars = int(warmup_bars_raw)
        warmup_bars = max(100, min(5000, warmup_bars))
    except (TypeError, ValueError):
        warmup_bars = 1000

    csv_file = request.files.get("file")
    csv_path_raw = (request.form.get("csvPath") or "").strip()
    data_source = None
    opened_file = None

    if csv_file and csv_file.filename:
        data_source = csv_file
    elif csv_path_raw:
        try:
            resolved_path = _resolve_csv_path(csv_path_raw)
        except FileNotFoundError:
            return ("CSV file not found.", HTTPStatus.BAD_REQUEST)
        except IsADirectoryError:
            return ("CSV path must point to a file.", HTTPStatus.BAD_REQUEST)
        except ValueError:
            return ("CSV file is required.", HTTPStatus.BAD_REQUEST)
        except OSError:
            return ("Failed to access CSV file.", HTTPStatus.BAD_REQUEST)
        try:
            opened_file = resolved_path.open("rb")
        except OSError:
            return ("Failed to access CSV file.", HTTPStatus.BAD_REQUEST)
        data_source = opened_file
    else:
        return ("CSV file is required.", HTTPStatus.BAD_REQUEST)

    payload_raw = request.form.get("payload", "{}")
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        return ("Invalid payload JSON.", HTTPStatus.BAD_REQUEST)

    # Load strategy
    from strategies import get_strategy

    try:
        strategy_class = get_strategy(strategy_id)
    except ValueError as e:
        return (str(e), HTTPStatus.BAD_REQUEST)

    # Load data
    try:
        df = load_data(data_source)
    except ValueError as exc:
        if opened_file:
            opened_file.close()
            opened_file = None
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:  # pragma: no cover - defensive
        if opened_file:
            opened_file.close()
            opened_file = None
        app.logger.exception("Failed to load CSV")
        return ("Failed to load CSV data.", HTTPStatus.INTERNAL_SERVER_ERROR)
    finally:
        if opened_file:
            try:
                opened_file.close()
            except OSError:  # pragma: no cover - defensive
                pass
            opened_file = None

    # Prepare dataset with warmup
    trade_start_idx = 0
    use_date_filter = payload.get("dateFilter", False)
    start_raw = payload.get("start")
    end_raw = payload.get("end")

    if use_date_filter and (start_raw is not None or end_raw is not None):
        start, end = align_date_bounds(df.index, start_raw, end_raw)
        if start_raw not in (None, "") and start is None:
            return ("Invalid start date.", HTTPStatus.BAD_REQUEST)
        if end_raw not in (None, "") and end is None:
            return ("Invalid end date.", HTTPStatus.BAD_REQUEST)

        # Apply warmup
        try:
            df, trade_start_idx = prepare_dataset_with_warmup(
                df, start, end, warmup_bars
            )
        except Exception as exc:  # pragma: no cover - defensive
            app.logger.exception("Failed to prepare dataset with warmup")
            return ("Failed to prepare dataset.", HTTPStatus.INTERNAL_SERVER_ERROR)

    try:
        _validate_strategy_params(strategy_id, payload)
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)

    # Run strategy
    try:
        result = strategy_class.run(df, payload, trade_start_idx)
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:  # pragma: no cover - defensive
        app.logger.exception("Backtest execution failed")
        return ("Backtest execution failed.", HTTPStatus.INTERNAL_SERVER_ERROR)

    return jsonify({
        "metrics": result.to_dict(),
        "parameters": payload,
    })


def _build_optimization_config(
    csv_file,
    payload: dict,
    worker_processes=None,
    strategy_id=None,
    warmup_bars: Optional[int] = None,
) -> OptimizationConfig:
    if not isinstance(payload, dict):
        raise ValueError("Invalid optimization config payload.")

    from strategies import list_strategies

    def _parse_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y", "on"}:
                return True
            if lowered in {"false", "0", "no", "n", "off"}:
                return False
        return default

    def _sanitize_score_config(raw_config: Any) -> Dict[str, Any]:
        source = raw_config if isinstance(raw_config, dict) else {}
        normalized = json.loads(json.dumps(DEFAULT_OPTIMIZER_SCORE_CONFIG))

        filter_value = source.get("filter_enabled")
        normalized["filter_enabled"] = _parse_bool(
            filter_value, normalized.get("filter_enabled", False)
        )

        try:
            threshold = float(source.get("min_score_threshold"))
        except (TypeError, ValueError):
            threshold = normalized.get("min_score_threshold", 0.0)
        normalized["min_score_threshold"] = max(0.0, min(100.0, threshold))

        weights_raw = source.get("weights")
        if isinstance(weights_raw, dict):
            weights: Dict[str, float] = {}
            for key in SCORE_METRIC_KEYS:
                try:
                    weight_value = float(weights_raw.get(key, normalized["weights"].get(key, 0.0)))
                except (TypeError, ValueError):
                    weight_value = normalized["weights"].get(key, 0.0)
                weights[key] = max(0.0, min(1.0, weight_value))
            normalized["weights"].update(weights)

        enabled_raw = source.get("enabled_metrics")
        if isinstance(enabled_raw, dict):
            enabled: Dict[str, bool] = {}
            for key in SCORE_METRIC_KEYS:
                enabled[key] = _parse_bool(
                    enabled_raw.get(key, normalized["enabled_metrics"].get(key, False)),
                    normalized["enabled_metrics"].get(key, False),
                )
            normalized["enabled_metrics"].update(enabled)

        invert_raw = source.get("invert_metrics")
        invert_flags: Dict[str, bool] = {}
        if isinstance(invert_raw, dict):
            for key in SCORE_METRIC_KEYS:
                invert_flags[key] = _parse_bool(
                    invert_raw.get(key, False),
                    False,
                )
        else:
            for key in SCORE_METRIC_KEYS:
                invert_flags[key] = normalized["invert_metrics"].get(key, False)
        normalized["invert_metrics"] = {
            key: value for key, value in invert_flags.items() if value
        }

        normalization_value = source.get("normalization_method")
        if isinstance(normalization_value, str) and normalization_value.strip():
            normalized["normalization_method"] = normalization_value.strip().lower()

        bounds_raw = source.get("metric_bounds")
        if isinstance(bounds_raw, dict):
            bounds: Dict[str, Dict[str, float]] = {}
            for metric_key in SCORE_METRIC_KEYS:
                if metric_key in bounds_raw and isinstance(bounds_raw[metric_key], dict):
                    metric_bounds = bounds_raw[metric_key]
                    try:
                        bounds[metric_key] = {
                            "min": float(
                                metric_bounds.get(
                                    "min", normalized["metric_bounds"][metric_key]["min"]
                                )
                            ),
                            "max": float(
                                metric_bounds.get(
                                    "max", normalized["metric_bounds"][metric_key]["max"]
                                )
                            ),
                        }
                    except (TypeError, ValueError, KeyError):
                        bounds[metric_key] = normalized["metric_bounds"].get(
                            metric_key, {"min": 0.0, "max": 100.0}
                        )
                else:
                    bounds[metric_key] = normalized["metric_bounds"].get(
                        metric_key, {"min": 0.0, "max": 100.0}
                    )
            normalized["metric_bounds"] = bounds

        return normalized

    if strategy_id is None:
        strategy_id = payload.get("strategy")

    if not strategy_id:
        available_strategies = list_strategies()
        if available_strategies:
            strategy_id = available_strategies[0]["id"]
        else:
            raise ValueError("Strategy ID is required for optimization.")

    if warmup_bars is None:
        warmup_bars_raw = payload.get("warmup_bars", 1000)
        try:
            warmup_bars = int(warmup_bars_raw)
            warmup_bars = max(100, min(5000, warmup_bars))
        except (TypeError, ValueError):
            warmup_bars = 1000
    else:
        try:
            warmup_bars = max(100, min(5000, int(warmup_bars)))
        except (TypeError, ValueError):
            warmup_bars = 1000

    enabled_params = payload.get("enabled_params")
    if not isinstance(enabled_params, dict):
        raise ValueError("enabled_params must be a dictionary.")

    param_ranges_raw = payload.get("param_ranges", {})
    if not isinstance(param_ranges_raw, dict):
        raise ValueError("param_ranges must be a dictionary.")
    param_ranges = {}
    select_range_options: Dict[str, List[Any]] = {}
    for name, values in param_ranges_raw.items():
        if isinstance(values, dict):
            range_type = str(values.get("type", "")).lower()
            if range_type in {"select", "options"}:
                raw_options = values.get("values") or values.get("options") or []
                if isinstance(raw_options, (list, tuple)):
                    normalized = [opt for opt in raw_options if str(opt).strip()]
                    if normalized:
                        select_range_options[name] = normalized
                continue
            raise ValueError(f"Unsupported range specification for parameter '{name}'.")

        if not isinstance(values, (list, tuple)) or len(values) != 3:
            raise ValueError(f"Invalid range for parameter '{name}'.")
        start, stop, step = values
        param_ranges[name] = (float(start), float(stop), float(step))

    fixed_params = payload.get("fixed_params", {})
    if not isinstance(fixed_params, dict):
        raise ValueError("fixed_params must be a dictionary.")

    try:
        strategy_param_types = _get_parameter_types(strategy_id)
    except Exception as exc:
        app.logger.warning(
            "Could not load parameter types for %s: %s", strategy_id, exc
        )
        strategy_param_types = {}
    payload_param_types = payload.get("param_types", {})
    if isinstance(payload_param_types, dict):
        merged_param_types = {**strategy_param_types, **payload_param_types}
    else:
        merged_param_types = strategy_param_types

    for name, options in select_range_options.items():
        if not options:
            continue
        key = f"{name}_options"
        existing = fixed_params.get(key)
        if not existing:
            fixed_params[key] = list(options)

    risk_per_trade = payload.get("risk_per_trade_pct", 2.0)
    contract_size = payload.get("contract_size", 0.01)
    commission_rate = payload.get("commission_rate", 0.0005)

    filter_min_profit_raw = payload.get("filter_min_profit")
    filter_min_profit = _parse_bool(filter_min_profit_raw, False)

    threshold_raw = payload.get("min_profit_threshold", 0.0)
    try:
        min_profit_threshold = float(threshold_raw)
    except (TypeError, ValueError):
        min_profit_threshold = 0.0
    min_profit_threshold = max(0.0, min(99000.0, min_profit_threshold))

    if hasattr(csv_file, "seek"):
        try:
            csv_file.seek(0)
        except Exception:  # pragma: no cover - defensive
            pass
    elif hasattr(csv_file, "stream") and hasattr(csv_file.stream, "seek"):
        csv_file.stream.seek(0)
    worker_processes_value = 6 if worker_processes is None else int(worker_processes)
    if worker_processes_value < 1:
        worker_processes_value = 1
    elif worker_processes_value > 32:
        worker_processes_value = 32

    score_config_payload = payload.get("score_config")
    score_config = _sanitize_score_config(score_config_payload)
    detailed_log = _parse_bool(payload.get("detailed_log", False), False)

    optimization_mode_raw = payload.get("optimization_mode", "optuna")
    optimization_mode = str(optimization_mode_raw).strip().lower() or "optuna"
    if optimization_mode != "optuna":
        raise ValueError("Grid Search has been removed. Use Optuna optimization only.")

    objectives = payload.get("objectives", [])
    if not isinstance(objectives, list):
        objectives = []
    primary_objective = payload.get("primary_objective")

    optuna_budget_mode = str(payload.get("optuna_budget_mode", "trials")).strip().lower()

    try:
        optuna_n_trials = int(payload.get("optuna_n_trials", 500))
    except (TypeError, ValueError):
        optuna_n_trials = 500

    try:
        optuna_time_limit = int(payload.get("optuna_time_limit", 3600))
    except (TypeError, ValueError):
        optuna_time_limit = 3600

    try:
        optuna_convergence = int(payload.get("optuna_convergence", 50))
    except (TypeError, ValueError):
        optuna_convergence = 50

    try:
        n_startup_trials = int(payload.get("n_startup_trials", 20))
    except (TypeError, ValueError):
        n_startup_trials = 20

    optuna_enable_pruning = _parse_bool(payload.get("optuna_enable_pruning", True), True)
    optuna_pruner = str(payload.get("optuna_pruner", "median")).strip().lower()
    optuna_save_study = _parse_bool(payload.get("optuna_save_study", False), False)

    sanitize_enabled = _parse_bool(payload.get("sanitize_enabled", True), True)
    sanitize_trades_threshold_raw = payload.get("sanitize_trades_threshold", 0)
    try:
        sanitize_trades_threshold = int(sanitize_trades_threshold_raw)
    except (TypeError, ValueError):
        raise ValueError("sanitize_trades_threshold must be a non-negative integer.")
    if sanitize_trades_threshold < 0:
        raise ValueError("sanitize_trades_threshold must be >= 0.")

    sampler_type = str(payload.get("sampler", "tpe")).strip().lower()
    population_size = payload.get("population_size")
    crossover_prob = payload.get("crossover_prob")
    mutation_prob = payload.get("mutation_prob")
    swapping_prob = payload.get("swapping_prob")

    def _parse_optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_optional_float(value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    population_size = _parse_optional_int(population_size)
    crossover_prob = _parse_optional_float(crossover_prob)
    mutation_prob = _parse_optional_float(mutation_prob)
    swapping_prob = _parse_optional_float(swapping_prob)

    allowed_budget_modes = {"trials", "time", "convergence"}
    allowed_pruners = {"median", "percentile", "patient", "none"}

    if optuna_budget_mode not in allowed_budget_modes:
        raise ValueError(f"Invalid Optuna budget mode: {optuna_budget_mode}")
    if optuna_pruner not in allowed_pruners:
        raise ValueError(f"Invalid Optuna pruner: {optuna_pruner}")

    optuna_n_trials = max(10, optuna_n_trials)
    optuna_time_limit = max(60, optuna_time_limit)
    optuna_convergence = max(10, optuna_convergence)
    n_startup_trials = max(0, n_startup_trials)

    if len(objectives) > 1:
        optuna_enable_pruning = False

    optuna_params: Dict[str, Any] = {
        "objectives": objectives,
        "primary_objective": primary_objective,
        "constraints": payload.get("constraints", []),
        "sampler_type": sampler_type,
        "population_size": population_size,
        "crossover_prob": crossover_prob,
        "mutation_prob": mutation_prob,
        "swapping_prob": swapping_prob,
        "n_startup_trials": n_startup_trials,
        "optuna_budget_mode": optuna_budget_mode,
        "optuna_n_trials": optuna_n_trials,
        "optuna_time_limit": optuna_time_limit,
        "optuna_convergence": optuna_convergence,
        "optuna_enable_pruning": optuna_enable_pruning,
        "optuna_pruner": optuna_pruner,
        "optuna_save_study": optuna_save_study,
        "sanitize_enabled": sanitize_enabled,
        "sanitize_trades_threshold": sanitize_trades_threshold,
    }

    config = OptimizationConfig(
        csv_file=csv_file,
        strategy_id=str(strategy_id),
        enabled_params=enabled_params,
        param_ranges=param_ranges,
        param_types=merged_param_types,
        fixed_params=fixed_params,
        worker_processes=worker_processes_value,
        warmup_bars=int(warmup_bars),
        contract_size=float(contract_size),
        commission_rate=float(commission_rate),
        risk_per_trade_pct=float(risk_per_trade),
        filter_min_profit=filter_min_profit,
        min_profit_threshold=min_profit_threshold,
        score_config=score_config,
        detailed_log=detailed_log,
        optimization_mode=optimization_mode,
        objectives=objectives,
        primary_objective=primary_objective,
        constraints=payload.get("constraints", []),
        sanitize_enabled=sanitize_enabled,
        sanitize_trades_threshold=sanitize_trades_threshold,
        sampler_type=sampler_type,
        population_size=population_size if population_size is not None else 50,
        crossover_prob=crossover_prob if crossover_prob is not None else 0.9,
        mutation_prob=mutation_prob if mutation_prob is not None else None,
        swapping_prob=swapping_prob if swapping_prob is not None else 0.5,
        n_startup_trials=n_startup_trials,
    )

    if optimization_mode == "optuna":
        for key, value in optuna_params.items():
            setattr(config, key, value)

    return config


_DATE_PREFIX_RE = re.compile(r"\b\d{4}[.\-/]\d{2}[.\-/]\d{2}\b")
_DATE_VALUE_RE = re.compile(r"(\d{4})[.\-/]?(\d{2})[.\-/]?(\d{2})")


def _extract_file_prefix(csv_filename: str) -> str:
    """
    Extract file prefix (exchange, ticker, timeframe) from CSV filename.

    Examples:
        "OKX_LINKUSDT.P, 15 2025.02.01-2025.09.09.csv" -> "OKX_LINKUSDT.P, 15"
        "BINANCE_BTCUSDT, 1h.csv" -> "BINANCE_BTCUSDT, 1h"

    Returns original filename stem if pattern not found.
    """
    name = Path(csv_filename).stem

    # Remove date pattern if exists (YYYY.MM.DD-YYYY.MM.DD)
    match = _DATE_PREFIX_RE.search(name)
    if match:
        prefix = name[:match.start()].rstrip()
        return prefix if prefix else name

    return name


def _format_date_component(value: object) -> str:
    if value in (None, ""):
        return "0000.00.00"
    value_str = str(value).strip()
    if not value_str:
        return "0000.00.00"
    match = _DATE_VALUE_RE.search(value_str)
    if match:
        year, month, day = match.groups()
        return f"{year}.{month}.{day}"
    normalized = value_str.rstrip("Zz")
    normalized = normalized.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return "0000.00.00"
    return parsed.strftime("%Y.%m.%d")


def _unique_preserve_order(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _get_frontend_param_order(strategy_id: str) -> List[str]:
    """Return parameter order from strategy config for consistent CSV output."""

    try:
        from strategies import get_strategy_config

        config = get_strategy_config(strategy_id)
        parameters = config.get("parameters", {}) if isinstance(config, dict) else {}
        if isinstance(parameters, dict):
            return list(parameters.keys())
    except Exception:  # pragma: no cover - defensive
        return []
    return []


def generate_output_filename(csv_filename: str, config: OptimizationConfig, mode: str = None) -> str:
    """
    Generate standardized output filename.

    Format: EXCHANGE_TICKER TF START-END_MODE.csv
    Example: "OKX_LINKUSDT.P, 15 2025.05.01-2025.09.01_Optuna.csv"

    Args:
        csv_filename: Input CSV filename
        config: Optimization configuration
        mode: Output mode ("Optuna" or "Optuna+WFA")

    Returns:
        Formatted filename string
    """
    # Extract prefix (exchange, ticker, timeframe)
    prefix = _extract_file_prefix(csv_filename or "")
    if not prefix:
        prefix = "optimization"

    # Format dates
    start_formatted = _format_date_component(config.fixed_params.get("start"))
    end_formatted = _format_date_component(config.fixed_params.get("end"))

    # Handle dateFilter=false: extract dates from input filename
    if not config.fixed_params.get("dateFilter"):
        original_name = Path(csv_filename or "").stem
        match = _DATE_PREFIX_RE.search(original_name)
        if match:
            # Found dates in filename, use them
            date_str = match.group()
            parts = date_str.split("-")
            if len(parts) == 2:
                start_formatted = parts[0]
                end_formatted = parts[1]

    # Determine mode
    if mode is None:
        mode = "Optuna"

    # Build filename
    return f"{prefix} {start_formatted}-{end_formatted}_{mode}.csv"


@app.post("/api/optimize")
def run_optimization_endpoint() -> object:
    csv_file = request.files.get("file")
    csv_path_raw = (request.form.get("csvPath") or "").strip()
    data_path = ""
    source_name = ""

    if csv_file and csv_file.filename:
        data_path = _persist_csv_upload(csv_file)
        data_source = data_path
        source_name = csv_file.filename
    elif csv_path_raw:
        try:
            resolved_path = _resolve_csv_path(csv_path_raw)
        except FileNotFoundError:
            return ("CSV file not found.", HTTPStatus.BAD_REQUEST)
        except IsADirectoryError:
            return ("CSV path must point to a file.", HTTPStatus.BAD_REQUEST)
        except ValueError:
            return ("CSV file is required.", HTTPStatus.BAD_REQUEST)
        except OSError:
            return ("Failed to access CSV file.", HTTPStatus.BAD_REQUEST)
        data_source = str(resolved_path)
        data_path = str(resolved_path)
        source_name = Path(resolved_path).name
    else:
        return ("CSV file is required.", HTTPStatus.BAD_REQUEST)

    config_raw = request.form.get("config")
    if not config_raw:
        return ("Optimization config is required.", HTTPStatus.BAD_REQUEST)
    try:
        config_payload = json.loads(config_raw)
    except json.JSONDecodeError:
        return ("Invalid optimization config JSON.", HTTPStatus.BAD_REQUEST)

    post_process_payload = config_payload.get("postProcess")
    if not isinstance(post_process_payload, dict):
        post_process_payload = {}

    objectives = config_payload.get("objectives", [])
    primary_objective = config_payload.get("primary_objective")
    valid, error = validate_objectives_config(objectives, primary_objective)
    if not valid:
        return (error, HTTPStatus.BAD_REQUEST)

    constraints = config_payload.get("constraints", [])
    valid, error = validate_constraints_config(constraints)
    if not valid:
        return (error, HTTPStatus.BAD_REQUEST)

    sampler_type = str(config_payload.get("sampler", "tpe")).strip().lower()
    population_size = config_payload.get("population_size")
    crossover_prob = config_payload.get("crossover_prob")
    try:
        population_size_val = int(population_size) if population_size is not None else None
    except (TypeError, ValueError):
        return ("Population size must be a number.", HTTPStatus.BAD_REQUEST)
    try:
        crossover_prob_val = float(crossover_prob) if crossover_prob is not None else None
    except (TypeError, ValueError):
        return ("Crossover probability must be a number.", HTTPStatus.BAD_REQUEST)

    valid, error = validate_sampler_config(sampler_type, population_size_val, crossover_prob_val)
    if not valid:
        return (error, HTTPStatus.BAD_REQUEST)

    strategy_id, error_response = _resolve_strategy_id_from_request()
    if error_response:
        return error_response

    warmup_bars_raw = request.form.get("warmupBars", "1000")
    try:
        warmup_bars = int(warmup_bars_raw)
        warmup_bars = max(100, min(5000, warmup_bars))
    except (TypeError, ValueError):
        warmup_bars = 1000

    ft_enabled = bool(post_process_payload.get("enabled", False))
    dsr_enabled = bool(post_process_payload.get("dsrEnabled", False))
    st_payload = post_process_payload.get("stressTest")
    if not isinstance(st_payload, dict):
        st_payload = {}
    st_enabled = bool(st_payload.get("enabled", False))
    try:
        dsr_top_k = int(post_process_payload.get("dsrTopK", 20))
    except (TypeError, ValueError):
        dsr_top_k = 20
    ft_start = None
    ft_end = None
    is_days = None
    ft_days = None

    if ft_enabled:
        fixed_params_payload = config_payload.get("fixed_params") or {}
        config_payload["fixed_params"] = fixed_params_payload

        original_user_start = fixed_params_payload.get("start")
        original_user_end = fixed_params_payload.get("end")
        user_start = _parse_pp_timestamp(original_user_start)
        user_end = _parse_pp_timestamp(original_user_end)

        if user_start is None or user_end is None:
            try:
                df_temp = load_data(data_source)
            except Exception as exc:
                return (f"Failed to load CSV for FT split: {exc}", HTTPStatus.BAD_REQUEST)
            user_start = df_temp.index.min()
            user_end = df_temp.index.max()

        if user_start is None or user_end is None:
            return ("Failed to determine FT date range.", HTTPStatus.BAD_REQUEST)

        try:
            ft_period_days = int(post_process_payload.get("ftPeriodDays", 30))
        except (TypeError, ValueError):
            return ("Invalid FT period days.", HTTPStatus.BAD_REQUEST)

        try:
            is_end, ft_start, ft_end, is_days, ft_days = calculate_ft_dates(
                user_start, user_end, ft_period_days
            )
        except ValueError as exc:
            return (str(exc), HTTPStatus.BAD_REQUEST)

        fixed_params_payload["dateFilter"] = True
        if not fixed_params_payload.get("start"):
            fixed_params_payload["start"] = user_start.isoformat()
        fixed_params_payload["end"] = is_end.isoformat()

    fixed_params_payload = config_payload.get("fixed_params") or {}
    is_start_date = fixed_params_payload.get("start")
    is_end_date = fixed_params_payload.get("end")

    try:
        worker_processes_raw = config_payload.get("worker_processes")
        if worker_processes_raw is None:
            worker_processes_raw = config_payload.get("workerProcesses")
        if worker_processes_raw is None:
            worker_processes = 6
        else:
            try:
                worker_processes = int(worker_processes_raw)
            except (TypeError, ValueError):
                return ("Invalid worker process count.", HTTPStatus.BAD_REQUEST)
            if worker_processes < 1:
                worker_processes = 1
            elif worker_processes > 32:
                worker_processes = 32

        optimization_config = _build_optimization_config(
            data_source,
            config_payload,
            worker_processes,
            strategy_id,
            warmup_bars,
        )
    except ValueError as exc:
        _set_optimization_state({
            "status": "error",
            "mode": "optuna",
            "error": str(exc),
        })
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception:  # pragma: no cover - defensive
        _set_optimization_state({
            "status": "error",
            "mode": "optuna",
            "error": "Failed to prepare optimization config.",
        })
        app.logger.exception("Failed to construct optimization config")
        return ("Failed to prepare optimization config.", HTTPStatus.INTERNAL_SERVER_ERROR)

    optimization_config.csv_original_name = source_name
    optimization_config.ft_enabled = ft_enabled
    if ft_enabled:
        optimization_config.ft_period_days = ft_days
        optimization_config.ft_top_k = int(post_process_payload.get("topK", 20))
        optimization_config.ft_sort_metric = post_process_payload.get("sortMetric", "profit_degradation")
        optimization_config.ft_start_date = ft_start.strftime("%Y-%m-%d") if ft_start else None
        optimization_config.ft_end_date = ft_end.strftime("%Y-%m-%d") if ft_end else None
        optimization_config.is_period_days = is_days

    _set_optimization_state({
        "status": "running",
        "mode": "optuna",
        "strategy_id": optimization_config.strategy_id,
        "data_path": data_path,
        "source_name": source_name,
        "warmup_bars": warmup_bars,
        "config": config_payload,
    })

    results: List[OptimizationResult] = []
    optimization_metadata: Optional[Dict[str, Any]] = None
    study_id: Optional[str] = None
    try:
        start_time = time.time()
        results, study_id = run_optimization(optimization_config)
        end_time = time.time()

        optimization_time_seconds = max(0.0, end_time - start_time)
        minutes = int(optimization_time_seconds // 60)
        seconds = int(optimization_time_seconds % 60)
        optimization_time_str = f"{minutes}m {seconds}s"

        summary = getattr(optimization_config, "optuna_summary", {})
        total_trials = int(summary.get("total_trials", getattr(optimization_config, "optuna_n_trials", 0)))
        completed_trials = int(summary.get("completed_trials", len(results)))
        pruned_trials = int(summary.get("pruned_trials", 0))
        best_value = summary.get("best_value")
        best_values = summary.get("best_values")

        if best_value is None and best_values is None and results:
            best_result = results[0]
            if getattr(best_result, "objective_values", None):
                if len(best_result.objective_values) > 1:
                    best_values = dict(
                        zip(
                            getattr(optimization_config, "objectives", []) or [],
                            best_result.objective_values,
                        )
                    )
                else:
                    best_value = best_result.objective_values[0]

        best_value_str = "-"
        if best_values:
            parts = []
            for metric, value in best_values.items():
                label = OBJECTIVE_DISPLAY_NAMES.get(metric, metric)
                try:
                    formatted = f"{float(value):.4f}"
                except (TypeError, ValueError):
                    formatted = str(value)
                parts.append(f"{label}={formatted}")
            best_value_str = ", ".join(parts) if parts else "-"
        elif best_value is not None:
            try:
                best_value_str = f"{float(best_value):.4f}"
            except (TypeError, ValueError):
                best_value_str = str(best_value)

        objectives = getattr(optimization_config, "objectives", []) or []
        primary_objective = getattr(optimization_config, "primary_objective", None)
        objective_label = (
            OBJECTIVE_DISPLAY_NAMES.get(objectives[0], objectives[0])
            if len(objectives) == 1
            else "Multi-objective"
        )

        optimization_metadata = {
            "method": "Optuna",
            "target": objective_label,
            "objectives": objectives,
            "primary_objective": primary_objective,
            "total_trials": total_trials,
            "completed_trials": completed_trials,
            "pruned_trials": pruned_trials,
            "best_trial_number": summary.get("best_trial_number"),
            "best_value": best_value_str,
            "pareto_front_size": summary.get("pareto_front_size"),
            "optimization_time": optimization_time_str,
        }
    except ValueError as exc:
        _set_optimization_state({
            "status": "error",
            "mode": "optuna",
            "strategy_id": optimization_config.strategy_id,
            "error": str(exc),
        })
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception:  # pragma: no cover - defensive
        _set_optimization_state({
            "status": "error",
            "mode": "optuna",
            "strategy_id": optimization_config.strategy_id,
            "error": "Optimization execution failed.",
        })
        app.logger.exception("Optimization run failed")
        return ("Optimization execution failed.", HTTPStatus.INTERNAL_SERVER_ERROR)

    if study_id:
        study_data = load_study_from_db(study_id) or {}
        config_json = (study_data.get("study") or {}).get("config_json") or {}
        if post_process_payload:
            config_json["postProcess"] = post_process_payload
            update_study_config_json(study_id, config_json)

    dsr_results: List[Any] = []
    if dsr_enabled and study_id:
        dsr_config = DSRConfig(
            enabled=True,
            top_k=dsr_top_k,
            warmup_bars=warmup_bars,
        )
        dsr_results, dsr_summary = run_dsr_analysis(
            optuna_results=results,
            config=dsr_config,
            n_trials_total=completed_trials,
            csv_path=data_path,
            strategy_id=strategy_id,
            fixed_params=config_payload.get("fixed_params") or {},
            warmup_bars=warmup_bars,
            score_config=getattr(optimization_config, "score_config", None),
            filter_min_profit=bool(getattr(optimization_config, "filter_min_profit", False)),
            min_profit_threshold=float(getattr(optimization_config, "min_profit_threshold", 0.0) or 0.0),
        )
        save_dsr_results(
            study_id,
            dsr_results,
            dsr_enabled=True,
            dsr_top_k=dsr_top_k,
            dsr_n_trials=dsr_summary.get("dsr_n_trials"),
            dsr_mean_sharpe=dsr_summary.get("dsr_mean_sharpe"),
            dsr_var_sharpe=dsr_summary.get("dsr_var_sharpe"),
        )

    ft_results: List[Any] = []
    if ft_enabled and study_id:
        ft_candidates = results
        if dsr_results:
            ft_candidates = [item.original_result for item in dsr_results]
        ft_source = "dsr" if dsr_results else "optuna"

        pp_config = PostProcessConfig(
            enabled=True,
            ft_period_days=int(ft_days or 0),
            top_k=int(post_process_payload.get("topK", 20)),
            sort_metric=str(post_process_payload.get("sortMetric", "profit_degradation")),
            warmup_bars=warmup_bars,
        )
        ft_results = run_forward_test(
            csv_path=data_path,
            strategy_id=strategy_id,
            optuna_results=ft_candidates,
            config=pp_config,
            is_period_days=int(is_days or 0),
            ft_period_days=int(ft_days or 0),
            ft_start_date=ft_start.strftime("%Y-%m-%d") if ft_start else "",
            ft_end_date=ft_end.strftime("%Y-%m-%d") if ft_end else "",
            n_workers=worker_processes,
        )
        save_forward_test_results(
            study_id,
            ft_results,
            ft_enabled=True,
            ft_period_days=int(ft_days or 0),
            ft_top_k=int(post_process_payload.get("topK", 20)),
            ft_sort_metric=str(post_process_payload.get("sortMetric", "profit_degradation")),
            ft_start_date=ft_start.strftime("%Y-%m-%d") if ft_start else None,
            ft_end_date=ft_end.strftime("%Y-%m-%d") if ft_end else None,
            is_period_days=int(is_days or 0),
            ft_source=ft_source,
        )

    st_results: List[Any] = []
    if st_enabled and study_id:
        try:
            from strategies import get_strategy_config

            strategy_config_json = get_strategy_config(strategy_id)
        except Exception as exc:
            strategy_config_json = {}
            app.logger.warning("Failed to load strategy config for stress test: %s", exc)

        try:
            st_top_k = int(st_payload.get("topK", 5))
        except (TypeError, ValueError):
            st_top_k = 5
        try:
            threshold_raw = float(st_payload.get("failureThreshold", 0.7))
        except (TypeError, ValueError):
            threshold_raw = 0.7
        failure_threshold = threshold_raw / 100.0 if threshold_raw > 1 else threshold_raw

        stress_test_config = StressTestConfig(
            enabled=True,
            top_k=st_top_k,
            failure_threshold=failure_threshold,
            sort_metric=str(st_payload.get("sortMetric", "profit_retention")),
            warmup_bars=warmup_bars,
        )

        st_candidates = results
        st_source = "optuna"
        if ft_enabled and ft_results:
            st_candidates = ft_results
            st_source = "ft"
        elif dsr_results:
            st_candidates = dsr_results
            st_source = "dsr"

        st_results, st_summary = run_stress_test(
            csv_path=data_path,
            strategy_id=strategy_id,
            source_results=st_candidates,
            config=stress_test_config,
            is_start_date=is_start_date,
            is_end_date=is_end_date,
            fixed_params=fixed_params_payload,
            config_json=strategy_config_json,
            n_workers=worker_processes,
        )
        save_stress_test_results(
            study_id,
            st_results,
            st_summary,
            stress_test_config,
            st_source=st_source,
        )

    _set_optimization_state(
        {
            "status": "completed",
            "mode": "optuna",
            "strategy_id": optimization_config.strategy_id,
            "data_path": data_path,
            "source_name": source_name,
            "warmup_bars": optimization_config.warmup_bars,
            "config": config_payload,
            "summary": optimization_metadata or {},
            "study_id": study_id,
        }
    )

    return jsonify(
        {
            "status": "success",
            "mode": "optuna",
            "study_id": study_id,
            "summary": optimization_metadata or {},
            "strategy_id": optimization_config.strategy_id,
            "data_path": data_path,
        }
    )


# ============================================
# STRATEGY MANAGEMENT ENDPOINTS
# ============================================


@app.get("/api/strategies")
def list_strategies_endpoint() -> object:
    """
    List all available strategies.

    Returns:
        JSON: {
            "strategies": [
                {
                    "id": "s01_trailing_ma",
                    "name": "S01 Trailing MA",
                    "version": "v26",
                    "description": "...",
                    "author": "..."
                }
            ]
        }
    """
    from strategies import list_strategies

    strategies = list_strategies()
    return jsonify({"strategies": strategies})

@app.route("/api/strategy/<strategy_id>/config", methods=["GET"])
def get_strategy_config_single(strategy_id: str):
    """Return strategy configuration for frontend rendering.

    Args:
        strategy_id: Strategy identifier (e.g., "s01_trailing_ma")

    Returns:
        JSON response with strategy configuration
    """
    try:
        from strategies import get_strategy_config

        config = get_strategy_config(strategy_id)
        return jsonify(config), HTTPStatus.OK

    except FileNotFoundError:
        return (
            jsonify({"error": f"Strategy '{strategy_id}' not found"}),
            HTTPStatus.NOT_FOUND,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load config for %s", strategy_id)
        return (
            jsonify({"error": f"Failed to load strategy config: {str(exc)}"}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@app.get("/api/strategies/<string:strategy_id>")
def get_strategy_metadata_endpoint(strategy_id: str) -> object:
    """
    Get strategy metadata (lightweight version without full parameters).

    Args:
        strategy_id: Strategy identifier

    Returns:
        JSON: {
            "id": "s01_trailing_ma",
            "name": "S01 Trailing MA",
            "version": "v26",
            "description": "...",
            "parameter_count": 25
        }

    Errors:
        404: Strategy not found
    """
    from strategies import get_strategy_config

    try:
        config = get_strategy_config(strategy_id)
        return jsonify({
            "id": config.get('id'),
            "name": config.get('name'),
            "version": config.get('version'),
            "description": config.get('description'),
            "author": config.get('author', ''),
            "parameter_count": len(config.get('parameters', {}))
        })
    except ValueError as e:
        return (str(e), HTTPStatus.NOT_FOUND)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
