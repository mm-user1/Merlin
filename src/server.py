import io
import json
from datetime import datetime
from http import HTTPStatus
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

from backtest_engine import StrategyParams, load_data, run_strategy
from optimizer_engine import (
    OptimizationConfig,
    export_to_csv,
    run_optimization,
)

app = Flask(__name__)


@app.route("/")
def index() -> object:
    return send_from_directory(Path(app.root_path), "index.html")


@app.post("/api/backtest")
def run_backtest() -> object:
    if "file" not in request.files:
        return ("CSV file is required.", HTTPStatus.BAD_REQUEST)

    csv_file = request.files["file"]
    if csv_file.filename == "":
        return ("CSV file is required.", HTTPStatus.BAD_REQUEST)

    payload_raw = request.form.get("payload", "{}")
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        return ("Invalid payload JSON.", HTTPStatus.BAD_REQUEST)

    try:
        params = StrategyParams.from_dict(payload)
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)

    try:
        df = load_data(csv_file)
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:  # pragma: no cover - defensive
        app.logger.exception("Failed to load CSV")
        return ("Failed to load CSV data.", HTTPStatus.INTERNAL_SERVER_ERROR)

    try:
        result = run_strategy(df, params)
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:  # pragma: no cover - defensive
        app.logger.exception("Backtest execution failed")
        return ("Backtest execution failed.", HTTPStatus.INTERNAL_SERVER_ERROR)

    return jsonify({
        "metrics": result.to_dict(),
        "parameters": params.to_dict(),
    })


def _build_optimization_config(csv_file, payload: dict) -> OptimizationConfig:
    if not isinstance(payload, dict):
        raise ValueError("Invalid optimization config payload.")

    enabled_params = payload.get("enabled_params")
    if not isinstance(enabled_params, dict):
        raise ValueError("enabled_params must be a dictionary.")

    param_ranges_raw = payload.get("param_ranges", {})
    if not isinstance(param_ranges_raw, dict):
        raise ValueError("param_ranges must be a dictionary.")
    param_ranges = {}
    for name, values in param_ranges_raw.items():
        if not isinstance(values, (list, tuple)) or len(values) != 3:
            raise ValueError(f"Invalid range for parameter '{name}'.")
        start, stop, step = values
        param_ranges[name] = (float(start), float(stop), float(step))

    fixed_params = payload.get("fixed_params", {})
    if not isinstance(fixed_params, dict):
        raise ValueError("fixed_params must be a dictionary.")

    ma_types_trend = payload.get("ma_types_trend") or payload.get("maTypesTrend") or []
    ma_types_trail_long = (
        payload.get("ma_types_trail_long")
        or payload.get("maTypesTrailLong")
        or []
    )
    ma_types_trail_short = (
        payload.get("ma_types_trail_short")
        or payload.get("maTypesTrailShort")
        or []
    )

    risk_per_trade = payload.get("risk_per_trade_pct")
    if risk_per_trade is None:
        risk_per_trade = payload.get("riskPerTrade", 2.0)
    contract_size = payload.get("contract_size")
    if contract_size is None:
        contract_size = payload.get("contractSize", 0.01)
    commission_rate = payload.get("commission_rate")
    if commission_rate is None:
        commission_rate = payload.get("commissionRate", 0.0005)
    atr_period = payload.get("atr_period")
    if atr_period is None:
        atr_period = payload.get("atrPeriod", 14)

    if hasattr(csv_file, "seek"):
        try:
            csv_file.seek(0)
        except Exception:  # pragma: no cover - defensive
            pass
    elif hasattr(csv_file, "stream") and hasattr(csv_file.stream, "seek"):
        csv_file.stream.seek(0)
    return OptimizationConfig(
        csv_file=csv_file,
        enabled_params=enabled_params,
        param_ranges=param_ranges,
        fixed_params=fixed_params,
        ma_types_trend=[str(ma).upper() for ma in ma_types_trend],
        ma_types_trail_long=[str(ma).upper() for ma in ma_types_trail_long],
        ma_types_trail_short=[str(ma).upper() for ma in ma_types_trail_short],
        risk_per_trade_pct=float(risk_per_trade),
        contract_size=float(contract_size),
        commission_rate=float(commission_rate),
        atr_period=int(atr_period),
    )


@app.post("/api/optimize")
def run_optimization_endpoint() -> object:
    if "file" not in request.files:
        return ("CSV file is required.", HTTPStatus.BAD_REQUEST)

    csv_file = request.files["file"]
    if csv_file.filename == "":
        return ("CSV file is required.", HTTPStatus.BAD_REQUEST)

    config_raw = request.form.get("config")
    if not config_raw:
        return ("Optimization config is required.", HTTPStatus.BAD_REQUEST)
    try:
        config_payload = json.loads(config_raw)
    except json.JSONDecodeError:
        return ("Invalid optimization config JSON.", HTTPStatus.BAD_REQUEST)

    try:
        optimization_config = _build_optimization_config(csv_file, config_payload)
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:  # pragma: no cover - defensive
        app.logger.exception("Failed to construct optimization config")
        return ("Failed to prepare optimization config.", HTTPStatus.INTERNAL_SERVER_ERROR)

    try:
        results = run_optimization(optimization_config)
    except ValueError as exc:
        return (str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:  # pragma: no cover - defensive
        app.logger.exception("Optimization run failed")
        return ("Optimization execution failed.", HTTPStatus.INTERNAL_SERVER_ERROR)

    csv_content = export_to_csv(results)
    buffer = io.BytesIO(csv_content.encode("utf-8"))
    filename = f"optimization_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
