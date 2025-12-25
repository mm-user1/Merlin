import io
import json
import re
import sys
import time
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtest_engine import load_data, prepare_dataset_with_warmup
from core.export import export_optuna_results
from core.optuna_engine import OptimizationConfig, OptimizationResult, run_optimization

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
    static_url_path="/static",
)


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
    "normalization_method": "percentile",
}

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


@app.route("/")
def index() -> object:
    return render_template("index.html")


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
    opened_file = None

    try:
        if csv_file and csv_file.filename:
            data_source = csv_file
        elif csv_path_raw:
            resolved_path = _resolve_csv_path(csv_path_raw)
            opened_file = resolved_path.open("rb")
            data_source = opened_file
        else:
            return jsonify({"error": "CSV file is required."}), HTTPStatus.BAD_REQUEST
    except (FileNotFoundError, IsADirectoryError, ValueError):
        return jsonify({"error": "CSV file is required."}), HTTPStatus.BAD_REQUEST
    except OSError:
        return jsonify({"error": "Failed to access CSV file."}), HTTPStatus.BAD_REQUEST

    config_raw = data.get("config")
    if not config_raw:
        if opened_file:
            opened_file.close()
        return jsonify({"error": "Missing optimization config."}), HTTPStatus.BAD_REQUEST

    try:
        config_payload = json.loads(config_raw)
    except json.JSONDecodeError:
        if opened_file:
            opened_file.close()
        return jsonify({"error": "Invalid optimization config JSON."}), HTTPStatus.BAD_REQUEST

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
        if opened_file:
            opened_file.close()
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
    except Exception:  # pragma: no cover - defensive
        if opened_file:
            opened_file.close()
        app.logger.exception("Failed to build optimization config for walk-forward")
        return jsonify({"error": "Failed to prepare optimization config."}), HTTPStatus.INTERNAL_SERVER_ERROR

    if optimization_config.optimization_mode != "optuna":
        if opened_file:
            opened_file.close()
        return jsonify({"error": "Walk-Forward requires Optuna optimization mode."}), HTTPStatus.BAD_REQUEST

    if hasattr(data_source, "seek"):
        try:
            data_source.seek(0)
        except Exception:  # pragma: no cover - defensive
            pass

    try:
        df = load_data(data_source)
    except ValueError as exc:
        if opened_file:
            opened_file.close()
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
    except Exception:  # pragma: no cover - defensive
        if opened_file:
            opened_file.close()
        app.logger.exception("Failed to load CSV for walk-forward")
        return jsonify({"error": "Failed to load CSV data."}), HTTPStatus.INTERNAL_SERVER_ERROR

    # Apply date filtering for Walk-Forward Analysis
    use_date_filter = optimization_config.fixed_params.get('dateFilter', False)
    start_date = optimization_config.fixed_params.get('start')
    end_date = optimization_config.fixed_params.get('end')

    if use_date_filter and start_date is not None and end_date is not None:
        try:
            # Ensure dates are pandas Timestamps with UTC timezone
            if not isinstance(start_date, pd.Timestamp):
                start_ts = pd.Timestamp(start_date)
                if start_ts.tzinfo is None:
                    start_ts = start_ts.tz_localize('UTC')
                else:
                    start_ts = start_ts.tz_convert('UTC')
            else:
                start_ts = start_date if start_date.tzinfo else start_date.tz_localize('UTC')

            if not isinstance(end_date, pd.Timestamp):
                end_ts = pd.Timestamp(end_date)
                if end_ts.tzinfo is None:
                    end_ts = end_ts.tz_localize('UTC')
                else:
                    end_ts = end_ts.tz_convert('UTC')
            else:
                end_ts = end_date if end_date.tzinfo else end_date.tz_localize('UTC')

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
                if opened_file:
                    opened_file.close()
                return jsonify({
                    "error": f"Selected date range contains only {len(df_trading_period)} bars. Need at least 1000 bars for Walk-Forward Analysis."
                }), HTTPStatus.BAD_REQUEST

            df = df_filtered
            actual_warmup_bars = start_idx - warmup_start_idx
            print(f"Walk-Forward: Using date-filtered data with warmup: {len(df)} bars total")
            print(f"  Warmup period: {actual_warmup_bars} bars from {warmup_start_ts} to {start_ts}")
            print(f"  Trading period: {len(df_trading_period)} bars from {start_ts} to {end_ts}")

        except Exception as e:
            if opened_file:
                opened_file.close()
            return jsonify({"error": f"Failed to apply date filter: {str(e)}"}), HTTPStatus.BAD_REQUEST

    optimization_config.warmup_bars = warmup_bars

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
    }

    optuna_settings = {
        "target": getattr(optimization_config, "optuna_target", "score"),
        "budget_mode": getattr(optimization_config, "optuna_budget_mode", "trials"),
        "n_trials": int(getattr(optimization_config, "optuna_n_trials", 100)),
        "time_limit": int(getattr(optimization_config, "optuna_time_limit", 3600)),
        "convergence_patience": int(getattr(optimization_config, "optuna_convergence", 50)),
        "enable_pruning": bool(getattr(optimization_config, "optuna_enable_pruning", True)),
        "sampler": getattr(optimization_config, "optuna_sampler", "tpe"),
        "pruner": getattr(optimization_config, "optuna_pruner", "median"),
        "warmup_trials": int(getattr(optimization_config, "optuna_warmup_trials", 20)),
        "save_study": bool(getattr(optimization_config, "optuna_save_study", False)),
    }

    try:
        num_windows = int(data.get("wf_num_windows", 5))
        gap_bars = int(data.get("wf_gap_bars", 100))
        topk = int(data.get("wf_topk", 20))
    except (TypeError, ValueError):
        if opened_file:
            opened_file.close()
        return jsonify({"error": "Invalid Walk-Forward parameters."}), HTTPStatus.BAD_REQUEST

    num_windows = max(1, min(20, num_windows))
    gap_bars = max(0, gap_bars)
    topk = max(1, min(200, topk))

    from core.walkforward_engine import WFConfig, WalkForwardEngine
    from core.export import export_wf_results_csv

    wf_config = WFConfig(
        num_windows=num_windows,
        gap_bars=gap_bars,
        topk_per_window=topk,
        warmup_bars=warmup_bars,
        strategy_id=strategy_id,
    )
    engine = WalkForwardEngine(wf_config, base_template, optuna_settings)

    try:
        result = engine.run_wf_optimization(df)
    except ValueError as exc:
        if opened_file:
            opened_file.close()
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
    except Exception:  # pragma: no cover - defensive
        if opened_file:
            opened_file.close()
        app.logger.exception("Walk-forward optimization failed")
        return jsonify({"error": "Walk-forward optimization failed."}), HTTPStatus.INTERNAL_SERVER_ERROR

    # Generate CSV content without saving to disk
    csv_content = export_wf_results_csv(result, df)

    # Build top10 summary (common for both modes)
    top10: List[Dict[str, Any]] = []
    for rank, agg in enumerate(result.aggregated[:10], 1):
        forward_profit = result.forward_profits[rank - 1] if rank <= len(result.forward_profits) else None
        top10.append(
            {
                "rank": rank,
                "param_id": agg.param_id,
                "avg_oos_profit": round(agg.avg_oos_profit, 2),
                "oos_win_rate": round(agg.oos_win_rate * 100, 1),
                "forward_profit": round(forward_profit, 2) if isinstance(forward_profit, (int, float)) else None,
            }
        )

    # Get export trades settings from request
    export_trades = data.get("exportTrades") == "true"
    top_k_str = data.get("topK", "10")
    try:
        top_k = min(100, max(1, int(top_k_str)))
    except (ValueError, TypeError):
        top_k = 10

    # Get dates for filename generation
    start_date = df.index[0]
    end_date = df.index[-1]

    # Get original CSV filename
    original_csv_name = csv_file.filename if csv_file and hasattr(csv_file, 'filename') else ""
    if not original_csv_name and csv_path_raw:
        original_csv_name = csv_path_raw

    # Generate filenames
    from core.export import (
        _extract_symbol_from_csv_filename,
        export_wfa_trades_history,
        generate_wfa_output_filename,
    )

    csv_filename = generate_wfa_output_filename(
        original_csv_name,
        start_date,
        end_date,
        include_trades=False
    )

    if export_trades:
        # Export trades history for top-K combinations
        import tempfile
        import zipfile
        import shutil
        import base64
        from pathlib import Path

        # Extract symbol from CSV filename
        symbol = _extract_symbol_from_csv_filename(original_csv_name)

        # Create temporary directory for all files
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Export trades to CSVs
            trade_files = export_wfa_trades_history(
                wf_result=result,
                df=df,
                symbol=symbol,
                top_k=top_k,
                output_dir=temp_dir
            )

            # Create ZIP with trade CSVs only
            zip_filename = generate_wfa_output_filename(
                original_csv_name,
                start_date,
                end_date,
                include_trades=True
            )
            zip_path = temp_dir / zip_filename

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add all trade CSVs
                for trade_file in trade_files:
                    trade_path = temp_dir / trade_file
                    zf.write(trade_path, trade_file)

            # Read ZIP into base64
            with open(zip_path, 'rb') as f:
                zip_bytes = f.read()
            zip_base64 = base64.b64encode(zip_bytes).decode('utf-8')

            # Cleanup temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)

            # Close opened file before sending response
            if opened_file:
                opened_file.close()

            # Return JSON with embedded ZIP
            response_payload = {
                "status": "success",
                "summary": {
                    "total_windows": len(result.windows),
                    "top_param_id": result.aggregated[0].param_id if result.aggregated else "N/A",
                    "top_avg_oos_profit": round(result.aggregated[0].avg_oos_profit, 2) if result.aggregated else 0.0,
                },
                "top10": top10,
                "csv_content": csv_content,
                "csv_filename": csv_filename,
                "export_trades": True,
                "zip_filename": zip_filename,
                "zip_base64": zip_base64,
            }

            return jsonify(response_payload)

        except Exception as e:
            # Cleanup on error
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            if opened_file:
                opened_file.close()
            app.logger.exception("Failed to export trades history")
            return jsonify({"error": f"Failed to export trades: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR

    else:
        # No trades export - return JSON response (existing behavior)
        response_payload = {
            "status": "success",
            "summary": {
                "total_windows": len(result.windows),
                "top_param_id": result.aggregated[0].param_id if result.aggregated else "N/A",
                "top_avg_oos_profit": round(result.aggregated[0].avg_oos_profit, 2) if result.aggregated else 0.0,
            },
            "top10": top10,
            "csv_content": csv_content,
            "csv_filename": csv_filename,
        }

        if opened_file:
            opened_file.close()

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
    start = payload.get("start")
    end = payload.get("end")

    if use_date_filter and (start is not None or end is not None):
        # Parse dates
        if isinstance(start, str):
            start = pd.Timestamp(start, tz="UTC")
        if isinstance(end, str):
            end = pd.Timestamp(end, tz="UTC")

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

    optimization_mode_raw = payload.get("optimization_mode", "optuna")
    optimization_mode = str(optimization_mode_raw).strip().lower() or "optuna"
    if optimization_mode != "optuna":
        raise ValueError("Grid Search has been removed. Use Optuna optimization only.")

    optuna_target = str(payload.get("optuna_target", "score")).strip().lower()
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
        optuna_warmup_trials = int(payload.get("optuna_warmup_trials", 20))
    except (TypeError, ValueError):
        optuna_warmup_trials = 20

    optuna_enable_pruning = _parse_bool(payload.get("optuna_enable_pruning", True), True)
    optuna_sampler = str(payload.get("optuna_sampler", "tpe")).strip().lower()
    optuna_pruner = str(payload.get("optuna_pruner", "median")).strip().lower()
    optuna_save_study = _parse_bool(payload.get("optuna_save_study", False), False)

    allowed_targets = {"score", "net_profit", "romad", "sharpe", "max_drawdown"}
    allowed_budget_modes = {"trials", "time", "convergence"}
    allowed_samplers = {"tpe", "random"}
    allowed_pruners = {"median", "percentile", "patient", "none"}

    if optuna_target not in allowed_targets:
        raise ValueError(f"Invalid Optuna target: {optuna_target}")
    if optuna_budget_mode not in allowed_budget_modes:
        raise ValueError(f"Invalid Optuna budget mode: {optuna_budget_mode}")
    if optuna_sampler not in allowed_samplers:
        raise ValueError(f"Invalid Optuna sampler: {optuna_sampler}")
    if optuna_pruner not in allowed_pruners:
        raise ValueError(f"Invalid Optuna pruner: {optuna_pruner}")

    optuna_n_trials = max(10, optuna_n_trials)
    optuna_time_limit = max(60, optuna_time_limit)
    optuna_convergence = max(10, optuna_convergence)
    optuna_warmup_trials = max(0, optuna_warmup_trials)

    optuna_params: Dict[str, Any] = {
        "optuna_target": optuna_target,
        "optuna_budget_mode": optuna_budget_mode,
        "optuna_n_trials": optuna_n_trials,
        "optuna_time_limit": optuna_time_limit,
        "optuna_convergence": optuna_convergence,
        "optuna_enable_pruning": optuna_enable_pruning,
        "optuna_sampler": optuna_sampler,
        "optuna_pruner": optuna_pruner,
        "optuna_warmup_trials": optuna_warmup_trials,
        "optuna_save_study": optuna_save_study,
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
        optimization_mode=optimization_mode,
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
    opened_file = None
    source_name = ""

    if csv_file and csv_file.filename:
        data_source = csv_file
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
        try:
            opened_file = resolved_path.open("rb")
        except OSError:
            return ("Failed to access CSV file.", HTTPStatus.BAD_REQUEST)
        data_source = opened_file
        source_name = str(resolved_path)
    else:
        return ("CSV file is required.", HTTPStatus.BAD_REQUEST)

    config_raw = request.form.get("config")
    if not config_raw:
        return ("Optimization config is required.", HTTPStatus.BAD_REQUEST)
    try:
        config_payload = json.loads(config_raw)
    except json.JSONDecodeError:
        return ("Invalid optimization config JSON.", HTTPStatus.BAD_REQUEST)

    strategy_id, error_response = _resolve_strategy_id_from_request()
    if error_response:
        if opened_file:
            opened_file.close()
        return error_response

    warmup_bars_raw = request.form.get("warmupBars", "1000")
    try:
        warmup_bars = int(warmup_bars_raw)
        warmup_bars = max(100, min(5000, warmup_bars))
    except (TypeError, ValueError):
        warmup_bars = 1000

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
        if opened_file:
            opened_file.close()
            opened_file = None
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:  # pragma: no cover - defensive
        if opened_file:
            opened_file.close()
            opened_file = None
        app.logger.exception("Failed to construct optimization config")
        return ("Failed to prepare optimization config.", HTTPStatus.INTERNAL_SERVER_ERROR)

    results: List[OptimizationResult] = []
    optimization_metadata: Optional[Dict[str, Any]] = None
    try:
        start_time = time.time()
        results = run_optimization(optimization_config)
        end_time = time.time()

        optimization_time_seconds = max(0.0, end_time - start_time)
        minutes = int(optimization_time_seconds // 60)
        seconds = int(optimization_time_seconds % 60)
        optimization_time_str = f"{minutes}m {seconds}s"

        target_labels = {
            "score": "Composite Score",
            "net_profit": "Net Profit %",
            "romad": "RoMaD",
            "sharpe": "Sharpe Ratio",
            "max_drawdown": "Max Drawdown %",
        }

        summary = getattr(optimization_config, "optuna_summary", {})
        total_trials = int(summary.get("total_trials", getattr(optimization_config, "optuna_n_trials", 0)))
        completed_trials = int(summary.get("completed_trials", len(results)))
        pruned_trials = int(summary.get("pruned_trials", 0))
        best_value = summary.get("best_value")

        if best_value is None and results:
            best_result = results[0]
            if optimization_config.optuna_target == "score":
                best_value = best_result.score
            elif optimization_config.optuna_target == "net_profit":
                best_value = best_result.net_profit_pct
            elif optimization_config.optuna_target == "romad":
                best_value = best_result.romad
            elif optimization_config.optuna_target == "sharpe":
                best_value = best_result.sharpe_ratio
            elif optimization_config.optuna_target == "max_drawdown":
                best_value = best_result.max_drawdown_pct

        best_value_str = "-"
        if best_value is not None:
            try:
                best_value_str = f"{float(best_value):.4f}"
            except (TypeError, ValueError):
                best_value_str = str(best_value)

        optimization_metadata = {
            "method": "Optuna",
            "target": target_labels.get(optimization_config.optuna_target, "Composite Score"),
            "total_trials": total_trials,
            "completed_trials": completed_trials,
            "pruned_trials": pruned_trials,
            "best_trial_number": summary.get("best_trial_number"),
            "best_value": best_value_str,
            "optimization_time": optimization_time_str,
        }
    except ValueError as exc:
        if opened_file:
            opened_file.close()
            opened_file = None
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:  # pragma: no cover - defensive
        if opened_file:
            opened_file.close()
            opened_file = None
        app.logger.exception("Optimization run failed")
        return ("Optimization execution failed.", HTTPStatus.INTERNAL_SERVER_ERROR)
    finally:
        if opened_file:
            try:
                opened_file.close()
            except OSError:  # pragma: no cover - defensive
                pass
            opened_file = None

    fixed_parameters = []

    for name in _get_frontend_param_order(optimization_config.strategy_id):
        if bool(optimization_config.enabled_params.get(name, False)):
            continue

        value = optimization_config.fixed_params.get(name)
        if value is None:
            if results:
                value = getattr(results[0], "params", {}).get(name)
        fixed_parameters.append((name, value))

    csv_content = export_optuna_results(
        results,
        fixed_parameters,
        filter_min_profit=optimization_config.filter_min_profit,
        min_profit_threshold=optimization_config.min_profit_threshold,
        optimization_metadata=optimization_metadata,
        strategy_id=optimization_config.strategy_id,
    )
    buffer = io.BytesIO(csv_content.encode("utf-8"))
    filename = generate_output_filename(source_name, optimization_config)
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
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
