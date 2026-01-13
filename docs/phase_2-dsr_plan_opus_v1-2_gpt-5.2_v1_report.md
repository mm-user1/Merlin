# Phase 2 DSR Implementation Report (v1.2.1)

Date: 2026-01-13

## Summary of Work Completed
- Added DSR core calculations and higher-moment helpers in `src/core/post_process.py` and `src/core/metrics.py`.
- Implemented DSR top-K IS re-run logic (monthly excess returns, skew/kurtosis, track length) and ranking by DSR probability.
- Extended SQLite schema with DSR study/trial columns and added `save_dsr_results()` to persist DSR output.
- Integrated DSR into `/api/optimize` and chained FT to use DSR-ranked candidates when both are enabled.
- Integrated DSR into Walk-Forward analysis (DSR re-rank before FT per window).
- Updated UI:
  - Start page: DSR toggle + top-K input in Post Process section.
  - Results page: DSR tab with Optuna-equivalent table and DSR info line (rank change, DSR, luck share).
- Added unit tests for DSR helpers and higher-moment calculations.
- Added SciPy to `requirements.txt`.

## Reference Tests & Results
Full test suite executed:
- Command: `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests -q`
- Result: 123 passed in 25.08s, 3 warnings (Optuna ExperimentalWarning: multivariate)

Targeted tests executed:
- `tests/test_dsr.py`: 3 passed
- `tests/test_post_process.py`: 4 passed

Reference dataset for any DSR/FT verification:
- `./data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`

## Deviations / Notes
- DSR candidate selection applies the same min-profit and score filters as Optuna storage when those filters are enabled. This keeps the DSR table aligned with what the Results page displays, while still using the full completed-trial set for SR variance and N (as required by the plan).
- Integration tests for full DSR pipeline and DSR+FT chaining were not added; only unit-level DSR helper tests were implemented.

## Errors or Issues Encountered
None during implementation.
