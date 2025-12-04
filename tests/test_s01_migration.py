import json
import sys
from pathlib import Path

import pandas as pd
import pytest

SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))

from core.backtest_engine import load_data, prepare_dataset_with_warmup
from strategies.s01_trailing_ma.strategy import S01TrailingMA
from strategies.s01_trailing_ma_migrated.strategy import (
    S01Params,
    S01TrailingMAMigrated,
)

DATA_PATH = "data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv"


@pytest.fixture(scope="module")
def baseline_metrics():
    baseline_path = Path("data/baseline/s01_metrics.json")
    with open(baseline_path) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def test_data():
    return load_data(DATA_PATH)


@pytest.fixture(scope="module")
def baseline_params(baseline_metrics):
    return baseline_metrics["parameters"]


class TestS01Migration:
    def test_params_dataclass_from_dict(self, baseline_params):
        params = S01Params.from_dict(baseline_params)
        assert params.ma_type == baseline_params["maType"]
        assert params.ma_length == baseline_params["maLength"]
        assert params.close_count_long == baseline_params["closeCountLong"]
        assert params.close_count_short == baseline_params["closeCountShort"]

    def test_params_dataclass_to_dict(self, baseline_params):
        params = S01Params.from_dict(baseline_params)
        params_dict = params.to_dict()
        assert params_dict["maType"] == baseline_params["maType"]
        assert params_dict["maLength"] == baseline_params["maLength"]
        assert params_dict["closeCountLong"] == baseline_params["closeCountLong"]
        assert params_dict["closeCountShort"] == baseline_params["closeCountShort"]

    def test_migrated_runs_without_error(self, test_data, baseline_params):
        start_ts = pd.Timestamp(baseline_params["start"], tz="UTC")
        end_ts = pd.Timestamp(baseline_params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        result = S01TrailingMAMigrated.run(df_prepared, baseline_params, trade_start_idx)
        assert result is not None
        assert isinstance(result.trades, list)
        assert len(result.equity_curve) > 0
        assert len(result.balance_curve) > 0

    def test_legacy_vs_migrated_exact_match(
        self, test_data, baseline_params, baseline_metrics
    ):
        start_ts = pd.Timestamp(baseline_params["start"], tz="UTC")
        end_ts = pd.Timestamp(baseline_params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        legacy_result = S01TrailingMA.run(df_prepared, baseline_params, trade_start_idx)
        migrated_result = S01TrailingMAMigrated.run(df_prepared, baseline_params, trade_start_idx)

        assert abs(legacy_result.net_profit_pct - migrated_result.net_profit_pct) < 1e-6
        assert abs(legacy_result.max_drawdown_pct - migrated_result.max_drawdown_pct) < 1e-6
        assert legacy_result.total_trades == migrated_result.total_trades
        assert len(legacy_result.trades) == len(migrated_result.trades)

        for i, (legacy_trade, migrated_trade) in enumerate(
            zip(legacy_result.trades, migrated_result.trades)
        ):
            assert legacy_trade.entry_time == migrated_trade.entry_time, (
                f"Trade {i}: Entry time mismatch"
            )
            assert legacy_trade.exit_time == migrated_trade.exit_time, (
                f"Trade {i}: Exit time mismatch"
            )
            assert abs(legacy_trade.entry_price - migrated_trade.entry_price) < 1e-6, (
                f"Trade {i}: Entry price mismatch"
            )
            assert abs(legacy_trade.exit_price - migrated_trade.exit_price) < 1e-6, (
                f"Trade {i}: Exit price mismatch"
            )
            assert abs(legacy_trade.net_pnl - migrated_trade.net_pnl) < 1e-6, (
                f"Trade {i}: Net PnL mismatch"
            )
            assert legacy_trade.direction == migrated_trade.direction

        assert len(legacy_result.equity_curve) == len(migrated_result.equity_curve)
        for i, (legacy_equity, migrated_equity) in enumerate(
            zip(legacy_result.equity_curve, migrated_result.equity_curve)
        ):
            assert abs(legacy_equity - migrated_equity) < 1e-6, (
                f"Equity curve mismatch at index {i}"
            )

        assert migrated_result.net_profit_pct == pytest.approx(
            baseline_metrics["net_profit_pct"], rel=0, abs=1e-6
        )
        assert migrated_result.max_drawdown_pct == pytest.approx(
            baseline_metrics["max_drawdown_pct"], rel=0, abs=1e-6
        )
        assert migrated_result.total_trades == baseline_metrics["total_trades"]


class TestS01MigrationMATypes:
    @pytest.mark.parametrize(
        "ma_type",
        ["SMA", "EMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"],
    )
    def test_ma_type_compatibility(self, test_data, baseline_params, ma_type):
        params = baseline_params.copy()
        params["maType"] = ma_type
        params["trailLongType"] = ma_type
        params["trailShortType"] = ma_type

        start_ts = pd.Timestamp(params["start"], tz="UTC")
        end_ts = pd.Timestamp(params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        legacy_result = S01TrailingMA.run(df_prepared, params, trade_start_idx)
        migrated_result = S01TrailingMAMigrated.run(df_prepared, params, trade_start_idx)

        assert abs(legacy_result.net_profit_pct - migrated_result.net_profit_pct) < 1e-6
        assert legacy_result.total_trades == migrated_result.total_trades


class TestS01MigrationEdgeCases:
    def test_very_short_ma(self, test_data, baseline_params):
        params = baseline_params.copy()
        params["maLength"] = 5

        start_ts = pd.Timestamp(params["start"], tz="UTC")
        end_ts = pd.Timestamp(params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        legacy = S01TrailingMA.run(df_prepared, params, trade_start_idx)
        migrated = S01TrailingMAMigrated.run(df_prepared, params, trade_start_idx)

        assert abs(legacy.net_profit_pct - migrated.net_profit_pct) < 1e-6

    def test_very_long_ma(self, test_data, baseline_params):
        params = baseline_params.copy()
        params["maLength"] = 500

        start_ts = pd.Timestamp(params["start"], tz="UTC")
        end_ts = pd.Timestamp(params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        legacy = S01TrailingMA.run(df_prepared, params, trade_start_idx)
        migrated = S01TrailingMAMigrated.run(df_prepared, params, trade_start_idx)

        assert abs(legacy.net_profit_pct - migrated.net_profit_pct) < 1e-6

    def test_no_trailing(self, test_data, baseline_params):
        params = baseline_params.copy()
        params["trailRRLong"] = 999.0
        params["trailRRShort"] = 999.0

        start_ts = pd.Timestamp(params["start"], tz="UTC")
        end_ts = pd.Timestamp(params["end"], tz="UTC")
        df_prepared, trade_start_idx = prepare_dataset_with_warmup(
            test_data, start_ts, end_ts, warmup_bars=1000
        )

        legacy = S01TrailingMA.run(df_prepared, params, trade_start_idx)
        migrated = S01TrailingMAMigrated.run(df_prepared, params, trade_start_idx)

        assert abs(legacy.net_profit_pct - migrated.net_profit_pct) < 1e-6
