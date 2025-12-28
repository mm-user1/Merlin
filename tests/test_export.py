import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.backtest_engine import TradeRecord
from core.export import export_trades_csv, export_trades_zip


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
