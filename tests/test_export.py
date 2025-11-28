import json
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.backtest_engine import TradeRecord
from core.export import export_optuna_results, export_trades_csv, export_trades_zip


@dataclass
class MockResult:
    ma_type: str = "HMA"
    ma_length: int = 50
    close_count_long: int = 9
    close_count_short: int = 5
    stop_long_atr: float = 2.0
    stop_long_rr: float = 3.0
    stop_long_lp: int = 2
    stop_short_atr: float = 2.0
    stop_short_rr: float = 3.0
    stop_short_lp: int = 2
    stop_long_max_pct: float = 3.0
    stop_short_max_pct: float = 3.0
    stop_long_max_days: int = 2
    stop_short_max_days: int = 4
    trail_rr_long: float = 1.0
    trail_rr_short: float = 1.0
    trail_ma_long_type: str = "SMA"
    trail_ma_long_length: int = 160
    trail_ma_long_offset: float = -1.0
    trail_ma_short_type: str = "SMA"
    trail_ma_short_length: int = 160
    trail_ma_short_offset: float = 1.0
    net_profit_pct: float = 230.75
    max_drawdown_pct: float = 20.03
    total_trades: int = 93
    score: float = 11.52
    romad: float = 11.52
    sharpe_ratio: float = 0.92
    profit_factor: float = 1.76
    ulcer_index: float = 12.01
    recovery_factor: float = 11.52
    consistency_score: float = 66.67


class TestExportOptunaResults:
    def test_export_optuna_results_basic(self):
        results = [MockResult()]
        fixed_params = {"maType": "HMA", "maLength": 50}

        csv_content = export_optuna_results(results, fixed_params)

        lines = csv_content.strip().splitlines()
        assert lines[0] == "Fixed Parameters"
        assert "Net Profit%" in lines[-2]
        assert "230.75%" in csv_content
        assert "Fixed Parameters" in csv_content

    def test_export_optuna_results_with_metadata(self):
        results = [MockResult()]
        fixed_params = {"maType": "HMA", "maLength": 50}
        metadata = {
            "method": "Optuna",
            "target": "Composite Score",
            "total_trials": 10,
            "completed_trials": 10,
            "pruned_trials": 0,
            "best_trial_number": 3,
            "best_value": 11.52,
            "optimization_time": "00:01:00",
        }

        csv_content = export_optuna_results(
            results,
            fixed_params,
            optimization_metadata=metadata,
        )

        assert "Optuna Metadata" in csv_content
        assert "Method,Optuna" in csv_content
        assert "Total Trials,10" in csv_content
        assert "Best Value,11.52" in csv_content

    def test_export_optuna_results_filter(self):
        profitable = MockResult(net_profit_pct=10.0)
        unprofitable = MockResult(net_profit_pct=-1.0)
        csv_content = export_optuna_results(
            [profitable, unprofitable],
            fixed_params={},
            filter_min_profit=True,
            min_profit_threshold=0.0,
        )

        lines = csv_content.strip().splitlines()
        # Only one data row should be present
        assert "-1.00%" not in csv_content
        assert lines[-1].startswith("HMA,50,9,5")


class TestExportTrades:
    def test_export_trades_csv_empty(self):
        csv_content = export_trades_csv([])
        assert csv_content.splitlines() == [
            "Symbol,Type,Entry Time,Entry Price,Exit Time,Exit Price,Profit,Profit %,Size"
        ]

    def test_export_trades_csv_single_trade(self):
        trade = TradeRecord(
            direction="long",
            entry_time=pd.Timestamp("2025-06-15 10:30", tz="UTC"),
            exit_time=pd.Timestamp("2025-06-16 14:20", tz="UTC"),
            entry_price=12.45,
            exit_price=12.98,
            net_pnl=53.0,
            profit_pct=4.26,
            size=100,
        )

        csv_content = export_trades_csv([trade], symbol="LINKUSDT")
        rows = csv_content.splitlines()
        assert len(rows) == 2
        assert rows[1] == "LINKUSDT,Long,2025-06-15 10:30:00,12.45,2025-06-16 14:20:00,12.98,53.00,4.26%,100.00"

    def test_export_trades_csv_multiple_trades(self):
        trades = [
            TradeRecord(entry_time=pd.Timestamp("2025-01-01", tz="UTC"), exit_time=pd.Timestamp("2025-01-02", tz="UTC"), entry_price=1.0, exit_price=2.0, net_pnl=1.0, profit_pct=100.0, size=1.0),
            TradeRecord(entry_time=pd.Timestamp("2025-02-01", tz="UTC"), exit_time=pd.Timestamp("2025-02-02", tz="UTC"), entry_price=2.0, exit_price=1.0, net_pnl=-1.0, profit_pct=-50.0, size=2.0),
        ]

        csv_content = export_trades_csv(trades)
        lines = csv_content.splitlines()
        assert len(lines) == 3
        assert lines[1].endswith("100.00%,1.00")
        assert lines[2].endswith("-50.00%,2.00")

    def test_export_trades_zip_content(self):
        trade = TradeRecord(
            direction="short",
            entry_time=pd.Timestamp("2025-03-01", tz="UTC"),
            exit_time=pd.Timestamp("2025-03-02", tz="UTC"),
            entry_price=10.0,
            exit_price=9.0,
            net_pnl=5.0,
            profit_pct=10.0,
            size=2.0,
        )
        metrics = {"net_profit_pct": 10.0, "total_trades": 1}

        zip_bytes = export_trades_zip([trade], metrics)

        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            assert set(zf.namelist()) == {"trades.csv", "summary.json"}
            trades_csv = zf.read("trades.csv").decode("utf-8")
            summary_data = json.loads(zf.read("summary.json"))

        assert "Short" in trades_csv
        assert summary_data["metrics"] == metrics
        assert summary_data["total_trades"] == 1
        assert "generated_at" in summary_data
