import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.backtest_engine import TradeRecord
from core.export import export_trades_csv


class TestExportTrades:
    def test_export_trades_csv_empty(self):
        csv_content = export_trades_csv([])
        assert csv_content.splitlines() == [
            "Symbol,Side,Qty,Fill Price,Closing Time"
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
        assert len(rows) == 3
        assert rows[1] == "LINKUSDT,Buy,100,12.45,2025-06-15 10:30:00"
        assert rows[2] == "LINKUSDT,Sell,100,12.98,2025-06-16 14:20:00"

    def test_export_trades_csv_multiple_trades(self):
        trades = [
            TradeRecord(entry_time=pd.Timestamp("2025-01-01", tz="UTC"), exit_time=pd.Timestamp("2025-01-02", tz="UTC"), entry_price=1.0, exit_price=2.0, net_pnl=1.0, profit_pct=100.0, size=1.0),
            TradeRecord(entry_time=pd.Timestamp("2025-02-01", tz="UTC"), exit_time=pd.Timestamp("2025-02-02", tz="UTC"), entry_price=2.0, exit_price=1.0, net_pnl=-1.0, profit_pct=-50.0, size=2.0),
        ]

        csv_content = export_trades_csv(trades)
        lines = csv_content.splitlines()
        assert len(lines) == 5
        assert lines[1].endswith("1,2025-01-01 00:00:00")
        assert lines[2].endswith("2,2025-01-02 00:00:00")
        assert lines[3].endswith("2,2025-02-01 00:00:00")
        assert lines[4].endswith("1,2025-02-02 00:00:00")

    def test_export_trades_csv_sorts_transactions_chronologically(self):
        trades = [
            TradeRecord(
                direction="long",
                entry_time=pd.Timestamp("2025-10-06 14:00", tz="UTC"),
                exit_time=pd.Timestamp("2025-10-07 12:00", tz="UTC"),
                entry_price=0.26209,
                exit_price=0.26422,
                size=393.56,
            ),
            TradeRecord(
                direction="short",
                entry_time=pd.Timestamp("2025-10-07 00:00", tz="UTC"),
                exit_time=pd.Timestamp("2025-10-07 06:00", tz="UTC"),
                entry_price=0.26582,
                exit_price=0.26049,
                size=376.19,
            ),
        ]

        csv_content = export_trades_csv(trades, symbol="OKX:DOGEUSDT.P")
        lines = csv_content.splitlines()
        assert len(lines) == 5
        assert lines[1].endswith("2025-10-06 14:00:00")
        assert lines[2].endswith("2025-10-07 00:00:00")
        assert lines[3].endswith("2025-10-07 06:00:00")
        assert lines[4].endswith("2025-10-07 12:00:00")

    def test_export_trades_csv_can_preserve_input_event_order(self):
        trades = [
            TradeRecord(
                direction="long",
                entry_time=pd.Timestamp("2025-10-06 14:00", tz="UTC"),
                exit_time=pd.Timestamp("2025-10-07 12:00", tz="UTC"),
                entry_price=0.26209,
                exit_price=0.26422,
                size=393.56,
            ),
            TradeRecord(
                direction="short",
                entry_time=pd.Timestamp("2025-10-07 00:00", tz="UTC"),
                exit_time=pd.Timestamp("2025-10-07 06:00", tz="UTC"),
                entry_price=0.26582,
                exit_price=0.26049,
                size=376.19,
            ),
        ]

        csv_content = export_trades_csv(
            trades,
            symbol="OKX:DOGEUSDT.P",
            sort_events_chronologically=False,
        )
        lines = csv_content.splitlines()
        assert len(lines) == 5
        assert lines[1].endswith("2025-10-06 14:00:00")
        assert lines[2].endswith("2025-10-07 12:00:00")
        assert lines[3].endswith("2025-10-07 00:00:00")
        assert lines[4].endswith("2025-10-07 06:00:00")

    def test_export_trades_csv_normalizes_float_artifacts(self):
        trade = TradeRecord(
            direction="long",
            entry_time=pd.Timestamp("2026-01-28 00:00", tz="UTC"),
            exit_time=pd.Timestamp("2026-01-29 01:00", tz="UTC"),
            entry_price=0.1257,
            exit_price=0.12333,
            size=722.9300000000001,
        )

        csv_content = export_trades_csv([trade], symbol="OKX:DOGEUSDT.P")
        lines = csv_content.splitlines()
        # Qty should not keep binary-float tails like ...0000000001
        assert "722.9300000000001" not in csv_content
        assert lines[1] == "OKX:DOGEUSDT.P,Buy,722.93,0.1257,2026-01-28 00:00:00"

