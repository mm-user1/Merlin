import io
import sys
import csv
from pathlib import Path

import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ui.server import app
from core.backtest_engine import TradeRecord
from core.walkforward_engine import OOSStitchedResult, WFConfig, WFResult, WindowResult
from core.storage import save_wfa_study_to_db
from strategies import get_strategy_config


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


def _build_params_from_config(strategy_id: str):
    config = get_strategy_config(strategy_id)
    parameters = config.get("parameters", {}) if isinstance(config, dict) else {}
    params = {}
    for name, spec in parameters.items():
        if not isinstance(spec, dict):
            continue
        default_value = spec.get("default")
        params[name] = default_value if default_value is not None else 0
    return params


def _create_wfa_study() -> str:
    data_path = Path(__file__).parent.parent / "data" / "raw" / "OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"
    if not data_path.exists():
        pytest.skip("Sample data file not available for WFA API tests.")

    strategy_id = "s01_trailing_ma"
    params = _build_params_from_config(strategy_id)
    wf_config = WFConfig(strategy_id=strategy_id, is_period_days=30, oos_period_days=15, warmup_bars=10)

    window = WindowResult(
        window_id=1,
        is_start=pd.Timestamp("2025-05-01", tz="UTC"),
        is_end=pd.Timestamp("2025-05-30", tz="UTC"),
        oos_start=pd.Timestamp("2025-05-31", tz="UTC"),
        oos_end=pd.Timestamp("2025-06-14", tz="UTC"),
        best_params=params,
        param_id="test_params",
        is_net_profit_pct=0.0,
        is_max_drawdown_pct=0.0,
        is_total_trades=0,
        oos_net_profit_pct=0.0,
        oos_max_drawdown_pct=0.0,
        oos_total_trades=0,
        oos_equity_curve=[100.0],
        oos_timestamps=[pd.Timestamp("2025-05-31", tz="UTC")],
        is_equity_curve=[100.0],
        is_timestamps=[pd.Timestamp("2025-05-01", tz="UTC")],
        best_params_source="optuna_is",
        available_modules=["optuna_is"],
        optuna_is_trials=[
            {
                "trial_number": 1,
                "params": params,
                "param_id": "test_params",
                "net_profit_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "total_trades": 0,
                "win_rate": 0.0,
                "is_selected": True,
            }
        ],
    )

    stitched = OOSStitchedResult(
        final_net_profit_pct=0.0,
        max_drawdown_pct=0.0,
        total_trades=0,
        wfe=0.0,
        oos_win_rate=0.0,
        equity_curve=[100.0],
        timestamps=[pd.Timestamp("2025-05-31", tz="UTC")],
        window_ids=[1],
    )

    wf_result = WFResult(
        config=wf_config,
        windows=[window],
        stitched_oos=stitched,
        strategy_id=strategy_id,
        total_windows=1,
        trading_start_date=window.is_start,
        trading_end_date=window.oos_end,
        warmup_bars=wf_config.warmup_bars,
    )

    study_id = save_wfa_study_to_db(
        wf_result=wf_result,
        config={"fixed_params": {}},
        csv_file_path=str(data_path),
        start_time=0.0,
        score_config=None,
    )
    return study_id


def test_get_wfa_window_details(client):
    study_id = _create_wfa_study()
    response = client.get(f"/api/studies/{study_id}/wfa/windows/1")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["window"]["window_number"] == 1
    assert "optuna_is" in payload["modules"]


def test_generate_wfa_window_equity(client):
    study_id = _create_wfa_study()
    response = client.post(
        f"/api/studies/{study_id}/wfa/windows/1/equity",
        json={"period": "is"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert "equity_curve" in payload


def test_download_wfa_window_trades(client):
    study_id = _create_wfa_study()
    response = client.post(
        f"/api/studies/{study_id}/wfa/windows/1/trades",
        json={"period": "oos"},
    )
    assert response.status_code == 200
    assert response.headers.get("Content-Type", "").startswith("text/csv")


def test_resolve_wfa_period_oos_prefers_precise_timestamp():
    from ui.server_services import _resolve_wfa_period

    window = {
        "oos_start_date": "2025-01-01",
        "oos_end_date": "2025-01-02",
        "oos_start_ts": "2025-01-01T00:00:00+00:00",
        "oos_end_ts": "2025-01-02T12:00:00+00:00",
    }
    start, end, error = _resolve_wfa_period(window, "oos")
    assert error is None
    assert start == "2025-01-01T00:00:00+00:00"
    assert end == "2025-01-02T12:00:00+00:00"

    # Backward compatibility: when ts fields are missing, date fields are used.
    legacy_window = {
        "oos_start_date": "2025-01-01",
        "oos_end_date": "2025-01-02",
    }
    legacy_start, legacy_end, legacy_error = _resolve_wfa_period(legacy_window, "oos")
    assert legacy_error is None
    assert legacy_start == "2025-01-01"
    assert legacy_end == "2025-01-02"


def test_download_wfa_window_trades_respects_stored_oos_trade_count(client, monkeypatch):
    import ui.server_routes_data as routes_data

    csv_path = Path(__file__).parent / "_tmp_wfa_window_trades.csv"
    csv_path.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")

    try:
        study_id = "wfa_window_count_limit"
        study_data = {
            "study": {
                "study_id": study_id,
                "study_name": "wfa_window_count_limit",
                "optimization_mode": "wfa",
                "adaptive_mode": 1,
                "strategy_id": "s01_trailing_ma",
                "csv_file_path": str(csv_path),
                "csv_file_name": "OKX_TESTUSDT.csv",
                "warmup_bars": 0,
                "config_json": {"fixed_params": {}},
            },
            "windows": [
                {
                    "window_number": 1,
                    "window_id": f"{study_id}_w1",
                    "best_params": {},
                    "oos_start_ts": "2025-01-01T00:00:00+00:00",
                    "oos_end_ts": "2025-01-02T23:00:00+00:00",
                    "oos_start_date": "2025-01-01",
                    "oos_end_date": "2025-01-02",
                    "oos_total_trades": 1,
                }
            ],
        }

        monkeypatch.setattr(
            routes_data,
            "load_study_from_db",
            lambda sid: study_data if sid == study_id else None,
        )

        fake_trades = [
            TradeRecord(
                direction="long",
                entry_time=pd.Timestamp("2025-01-02 10:00:00+00:00"),
                exit_time=pd.Timestamp("2025-01-02 10:30:00+00:00"),
                entry_price=100.0,
                exit_price=101.0,
                size=1.0,
            ),
            TradeRecord(
                direction="long",
                entry_time=pd.Timestamp("2025-01-02 20:00:00+00:00"),
                exit_time=pd.Timestamp("2025-01-02 20:30:00+00:00"),
                entry_price=100.0,
                exit_price=99.0,
                size=1.0,
            ),
        ]

        monkeypatch.setattr(
            routes_data,
            "_run_trade_export",
            lambda **_kwargs: (fake_trades, None),
        )

        response = client.post(
            f"/api/studies/{study_id}/wfa/windows/1/trades",
            json={"period": "oos"},
        )
        assert response.status_code == 200

        rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
        # Header + 2 rows (entry/exit) for exactly one trade after cap.
        assert len(rows) == 3
    finally:
        if csv_path.exists():
            csv_path.unlink()


def test_download_wfa_trades_uses_precise_oos_bounds(client, monkeypatch):
    import strategies
    import ui.server_routes_data as routes_data

    csv_path = Path(__file__).parent / "_tmp_wfa_precise_bounds.csv"
    csv_path.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")

    try:
        study_id = "wfa_precise_bounds"
        study_data = {
            "study": {
                "study_id": study_id,
                "study_name": "wfa_precise_bounds",
                "optimization_mode": "wfa",
                "adaptive_mode": 1,
                "strategy_id": "s01_trailing_ma",
                "csv_file_path": str(csv_path),
                "csv_file_name": "OKX_TESTUSDT.csv",
                "warmup_bars": 0,
                "config_json": {"fixed_params": {}},
            },
            "windows": [
                {
                    "window_number": 1,
                    "best_params": {},
                    "oos_start_date": "2025-01-01",
                    "oos_end_date": "2025-01-02",
                    "oos_start_ts": "2025-01-01T00:00:00+00:00",
                    "oos_end_ts": "2025-01-02T12:00:00+00:00",
                    "oos_total_trades": 1,
                }
            ],
        }

        monkeypatch.setattr(
            routes_data,
            "load_study_from_db",
            lambda sid: study_data if sid == study_id else None,
        )

        index = pd.date_range("2025-01-01 00:00:00+00:00", periods=72, freq="h")
        df = pd.DataFrame(
            {
                "Open": 1.0,
                "High": 1.0,
                "Low": 1.0,
                "Close": 1.0,
                "Volume": 1.0,
            },
            index=index,
        )
        monkeypatch.setattr(routes_data, "load_data", lambda _: df)
        monkeypatch.setattr(routes_data, "prepare_dataset_with_warmup", lambda data, *_: (data, 0))

        class FakeResult:
            def __init__(self, trades):
                self.trades = trades

        class FakeStrategy:
            @staticmethod
            def run(*_args, **_kwargs):
                return FakeResult(
                    [
                        TradeRecord(
                            direction="long",
                            entry_time=pd.Timestamp("2025-01-02 10:00:00+00:00"),
                            exit_time=pd.Timestamp("2025-01-02 10:30:00+00:00"),
                            entry_price=100.0,
                            exit_price=101.0,
                            size=1.0,
                        ),
                        TradeRecord(
                            direction="long",
                            entry_time=pd.Timestamp("2025-01-02 20:00:00+00:00"),
                            exit_time=pd.Timestamp("2025-01-02 20:30:00+00:00"),
                            entry_price=100.0,
                            exit_price=99.0,
                            size=1.0,
                        ),
                    ]
                )

        monkeypatch.setattr(strategies, "get_strategy", lambda _sid: FakeStrategy)

        response = client.post(f"/api/studies/{study_id}/wfa/trades")
        assert response.status_code == 200

        rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
        # Header + 2 rows (entry/exit) for exactly one trade within precise OOS end.
        assert len(rows) == 3
    finally:
        if csv_path.exists():
            csv_path.unlink()


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
