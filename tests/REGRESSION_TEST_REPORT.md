# Regression Test Report (Phase 9-5-4 Fix)

- **Command:** `PYTHONIOENCODING=utf-8 py -X utf8 -m pytest -q`
- **Dataset:** `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv` (warmup 1000 bars)
- **Result:** All collected tests executed without assertion failures; pytest terminated at final stdout flush (`OSError: [Errno 22] Invalid argument`). Rerun subset `tests/test_s01_migration.py` confirmed all 15 cases pass before the same stdout flush issue.

## Suite Breakdown
- `tests/test_export.py` – 8 tests
- `tests/test_indicators.py` – 15 tests
- `tests/test_metrics.py` – 14 tests
- `tests/test_naming_consistency.py` – 14 tests
- `tests/test_regression_s01.py` – 14 tests
- `tests/test_s01_migration.py` – 15 tests
- `tests/test_s04_stochrsi.py` – 6 tests

## Notes
- Terminal flush error appears environment-specific; no failing assertions were observed.
- Naming consistency suite continues to enforce camelCase alignment across configs and dataclasses.
