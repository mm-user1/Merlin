# Phase 3-4 OOS Test Update Report

## Summary of Work
- Implemented OOS Test backend: period splitting with inclusive, non-overlapping IS/FT/OOS boundaries; candidate selection across DSR/FT/Stress/Optuna; multiprocessing OOS test execution; and DB persistence for study/trial OOS metrics.
- Integrated OOS Test into the Optuna pipeline with correct stage reporting and metadata storage.
- Added Start page OOS configuration UI, mutual exclusion with WFA, and Results page OOS tab rendering with IS-vs-OOS deltas computed in the UI.
- Fixed Optuna IS Results table rendering by removing OOS-specific headers/columns and eliminating a JS error that prevented rows from rendering.
- Ensured OOS Source / Source Rank appear only in the OOS Test tab, and confirmed the OOS Test UI is a separate blue-bordered module between Post Process and Walk-Forward.
- Added comprehensive OOS unit tests plus a lightweight integration-style test for `run_oos_test`.

## Key Files Updated
- `src/core/post_process.py` (OOS dataclasses, candidate selection, period splitting, OOS runner)
- `src/core/storage.py` (schema additions + `save_oos_test_results`)
- `src/ui/server.py` (OOS config parsing, period splitting, OOS execution + persistence)
- `src/ui/templates/index.html` (OOS section in optimizer panel)
- `src/ui/templates/results.html` (OOS tab)
- `src/ui/static/js/post-process-ui.js` (OOS config, mutual exclusion with WFA)
- `src/ui/static/js/ui-handlers.js` (payload includes `oosTest`)
- `src/ui/static/js/results.js` (OOS state, tab, table rendering, comparisons)
- `tests/test_oos_test.py` (new tests)
- `CLAUDE.md` (documentation update)

## Tests Run
- `py -m pytest tests -q`
  - Result: **FAILED** (2 failed, 143 passed, 3 warnings, 26.53s)
  - Failures:
    - `tests/test_dsr.py::test_calculate_expected_max_sharpe_basic` (SciPy missing, DSR returns `None`)
    - `tests/test_dsr.py::test_calculate_dsr_high_sharpe_track_length` (SciPy missing, DSR returns `None`)

## Warnings
- Optuna `ExperimentalWarning` for `multivariate` in `tests/test_multiprocess_score.py` (3 occurrences).

## Deviations / Notes
- Did not add a dedicated `load_oos_test_results()` helper because `load_study_from_db()` already exposes the new OOS columns; the UI reads directly from study/trials payloads.
- No new OOS-specific trade download endpoint was added (not requested in the plan).

## Errors
- Full test suite failed because SciPy is not installed in this environment; DSR calculations returned `None` and broke two DSR tests.
