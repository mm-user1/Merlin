import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.analytics import (  # noqa: E402
    WARNING_NO_OVERLAP,
    WARNING_NO_VALID_DATA,
    aggregate_equity_curves,
)


def _study(points):
    return {
        "timestamps": [ts for ts, _ in points],
        "equity_curve": [value for _, value in points],
    }


def test_aggregate_two_studies_full_overlap():
    result = aggregate_equity_curves(
        [
            _study(
                [
                    ("2025-01-01T00:00:00+00:00", 100.0),
                    ("2025-01-02T00:00:00+00:00", 110.0),
                    ("2025-01-03T00:00:00+00:00", 120.0),
                ]
            ),
            _study(
                [
                    ("2025-01-01T00:00:00+00:00", 100.0),
                    ("2025-01-02T00:00:00+00:00", 100.0),
                    ("2025-01-03T00:00:00+00:00", 90.0),
                ]
            ),
        ]
    )

    assert "Short overlapping period" in str(result["warning"] or "")
    assert result["studies_used"] == 2
    assert result["studies_excluded"] == 0
    assert result["curve"] == pytest.approx([100.0, 105.0, 105.0], rel=1e-9)
    assert result["profit_pct"] == pytest.approx(5.0, abs=1e-6)
    assert result["max_drawdown_pct"] == pytest.approx(0.0, abs=1e-6)
    assert result["ann_profit_pct"] is None  # only 2 days overlap


def test_aggregate_partial_overlap_uses_intersection():
    result = aggregate_equity_curves(
        [
            _study(
                [
                    ("2025-01-01T00:00:00+00:00", 100.0),
                    ("2025-01-02T00:00:00+00:00", 110.0),
                    ("2025-01-04T00:00:00+00:00", 121.0),
                ]
            ),
            _study(
                [
                    ("2025-01-02T00:00:00+00:00", 200.0),
                    ("2025-01-03T00:00:00+00:00", 220.0),
                    ("2025-01-04T00:00:00+00:00", 220.0),
                ]
            ),
        ]
    )

    # Intersection starts on 2025-01-02.
    assert result["timestamps"][0] == "2025-01-02T00:00:00+00:00"
    assert result["curve"][0] == pytest.approx(100.0, abs=1e-9)
    assert result["profit_pct"] == pytest.approx(10.0, abs=1e-6)


def test_aggregate_no_overlap_returns_warning_payload():
    result = aggregate_equity_curves(
        [
            _study(
                [
                    ("2025-01-01T00:00:00+00:00", 100.0),
                    ("2025-01-02T00:00:00+00:00", 110.0),
                ]
            ),
            _study(
                [
                    ("2025-01-03T00:00:00+00:00", 100.0),
                    ("2025-01-04T00:00:00+00:00", 105.0),
                ]
            ),
        ]
    )

    assert result["curve"] is None
    assert result["timestamps"] is None
    assert result["warning"] == WARNING_NO_OVERLAP
    assert result["studies_used"] == 2


def test_aggregate_empty_input_returns_no_valid_data_payload():
    result = aggregate_equity_curves([])
    assert result["curve"] is None
    assert result["warning"] == WARNING_NO_VALID_DATA
    assert result["studies_used"] == 0


def test_aggregate_excludes_invalid_and_nonpositive_start_values():
    result = aggregate_equity_curves(
        [
            _study(
                [
                    ("2025-01-01T00:00:00+00:00", 100.0),
                    ("2025-01-02T00:00:00+00:00", 120.0),
                ]
            ),
            # Invalid curve length.
            {"timestamps": ["2025-01-01T00:00:00+00:00"], "equity_curve": [100.0, 110.0]},
            # Valid structure but nonpositive start after alignment.
            _study(
                [
                    ("2025-01-01T00:00:00+00:00", 0.0),
                    ("2025-01-02T00:00:00+00:00", 10.0),
                ]
            ),
        ]
    )

    assert result["studies_used"] == 1
    assert result["studies_excluded"] == 2
    assert result["curve"] is not None


def test_intraday_precision_is_preserved_for_curve_and_metrics():
    result = aggregate_equity_curves(
        [
            _study(
                [
                    ("2025-01-01T00:00:00+00:00", 100.0),
                    ("2025-01-01T12:00:00+00:00", 120.0),
                    ("2025-01-02T00:00:00+00:00", 120.0),
                ]
            ),
            _study(
                [
                    ("2025-01-01T00:00:00+00:00", 100.0),
                    ("2025-01-02T00:00:00+00:00", 100.0),
                ]
            ),
        ]
    )

    assert result["timestamps"] == [
        "2025-01-01T00:00:00+00:00",
        "2025-01-01T12:00:00+00:00",
        "2025-01-02T00:00:00+00:00",
    ]
    assert result["curve"] == pytest.approx([100.0, 110.0, 110.0], rel=1e-9)
    assert result["profit_pct"] == pytest.approx(10.0, abs=1e-6)


def test_annualized_profit_present_when_span_is_long_enough():
    result = aggregate_equity_curves(
        [
            _study(
                [
                    ("2025-01-01T00:00:00+00:00", 100.0),
                    ("2025-02-15T00:00:00+00:00", 120.0),
                ]
            )
        ]
    )

    assert result["warning"] is None
    assert result["ann_profit_pct"] is not None
    assert math.isfinite(result["ann_profit_pct"])


def test_duplicate_timestamps_keep_last_value():
    result = aggregate_equity_curves(
        [
            _study(
                [
                    ("2025-01-01T00:00:00+00:00", 100.0),
                    ("2025-01-01T00:00:00+00:00", 110.0),
                    ("2025-02-20T00:00:00+00:00", 121.0),
                ]
            )
        ]
    )

    assert result["curve"] is not None
    # Dedup should keep 110 at start timestamp.
    assert result["profit_pct"] == pytest.approx(10.0, abs=1e-6)
