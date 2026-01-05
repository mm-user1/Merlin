import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ui.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_csv_import_s01_parameters(client):
    csv_content = "parameter,value\nmaType,ema\nmaLength,45\n"

    response = client.post(
        "/api/presets/import-csv",
        data={
            "file": (io.BytesIO(csv_content.encode("utf-8")), "params.csv"),
            "strategy": "s01_trailing_ma",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["values"]["maType"] == "EMA"
    assert payload["values"]["maLength"] == 45


def test_csv_import_s04_parameters(client):
    csv_content = "parameter,value\nrsiLen,16\nstochLen,20\n"

    response = client.post(
        "/api/presets/import-csv",
        data={
            "file": (io.BytesIO(csv_content.encode("utf-8")), "params.csv"),
            "strategy": "s04_stochrsi",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["values"]["rsiLen"] == 16
    assert payload["values"]["stochLen"] == 20


def test_csv_import_without_strategy_uses_first_available(client, monkeypatch):
    import strategies

    monkeypatch.setattr(
        strategies,
        "list_strategies",
        lambda: [{"id": "s04_stochrsi", "name": "S04 StochRSI"}],
    )

    csv_content = "parameter,value\nrsiLen,16\n"

    response = client.post(
        "/api/presets/import-csv",
        data={"file": (io.BytesIO(csv_content.encode("utf-8")), "params.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["values"]["rsiLen"] == 16


def test_csv_import_fails_when_no_strategy_typing(monkeypatch, client):
    import strategies

    # Simulate discovery failure (no strategies available).
    monkeypatch.setattr(strategies, "list_strategies", lambda: [])

    csv_content = "parameter,value\nmaLength,45\n"

    response = client.post(
        "/api/presets/import-csv",
        data={"file": (io.BytesIO(csv_content.encode("utf-8")), "params.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    message = response.get_data(as_text=True).lower()
    assert "parameter types are unavailable" in message
    assert "maLength".lower() in message


def test_csv_import_fails_when_strategy_config_unloadable(monkeypatch, client):
    import strategies

    monkeypatch.setattr(strategies, "get_strategy_config", lambda _sid: (_ for _ in ()).throw(ValueError("boom")))

    csv_content = "parameter,value\nmaLength,45\n"

    response = client.post(
        "/api/presets/import-csv",
        data={
            "file": (io.BytesIO(csv_content.encode("utf-8")), "params.csv"),
            "strategy": "s01_trailing_ma",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    message = response.get_data(as_text=True)
    assert "s01_trailing_ma" in message
    assert "parameter types are unavailable" in message


def test_csv_import_rejects_invalid_int(client):
    csv_content = "parameter,value\nmaLength,abc\n"

    response = client.post(
        "/api/presets/import-csv",
        data={
            "file": (io.BytesIO(csv_content.encode("utf-8")), "params.csv"),
            "strategy": "s01_trailing_ma",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "Invalid numeric values in CSV."
    assert any("maLength" in detail for detail in payload["details"])


def test_csv_import_rejects_invalid_float(client):
    csv_content = "parameter,value\nstopLongX,abc\n"

    response = client.post(
        "/api/presets/import-csv",
        data={
            "file": (io.BytesIO(csv_content.encode("utf-8")), "params.csv"),
            "strategy": "s01_trailing_ma",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "Invalid numeric values in CSV."
    assert any("stopLongX" in detail for detail in payload["details"])


def test_csv_import_stops_on_mixed_valid_and_invalid_numbers(client):
    csv_content = "parameter,value\nmaLength,abc\nstopLongX,2.5\n"

    response = client.post(
        "/api/presets/import-csv",
        data={
            "file": (io.BytesIO(csv_content.encode("utf-8")), "params.csv"),
            "strategy": "s01_trailing_ma",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "Invalid numeric values in CSV."
    assert any("maLength" in detail for detail in payload["details"])
    # Ensure even valid numeric fields do not get applied when an error is present.
    assert "values" not in payload


def _build_minimal_optuna_payload():
    return {
        "strategy": "s01_trailing_ma",
        "enabled_params": {},
        "param_ranges": {},
        "fixed_params": {},
        "objectives": ["net_profit_pct"],
        "primary_objective": None,
        "optuna_budget_mode": "trials",
        "optuna_n_trials": 10,
        "optuna_time_limit": 60,
        "optuna_convergence": 10,
    }


def test_optuna_sanitize_defaults():
    from ui import server as server_module

    payload = _build_minimal_optuna_payload()
    config = server_module._build_optimization_config(
        "dummy.csv",
        payload,
        worker_processes=1,
        strategy_id="s01_trailing_ma",
        warmup_bars=1000,
    )
    assert config.sanitize_enabled is True
    assert config.sanitize_trades_threshold == 0


@pytest.mark.parametrize("threshold", [-1, "bad"])
def test_optuna_sanitize_threshold_validation(threshold):
    from ui import server as server_module

    payload = _build_minimal_optuna_payload()
    payload["sanitize_trades_threshold"] = threshold

    with pytest.raises(ValueError):
        server_module._build_optimization_config(
            "dummy.csv",
            payload,
            worker_processes=1,
            strategy_id="s01_trailing_ma",
            warmup_bars=1000,
        )
