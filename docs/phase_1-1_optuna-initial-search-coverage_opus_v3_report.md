# Phase 1.1 Report: Optuna Initial Search Coverage (Opus v3 aligned)

## 1) Goal and Scope

Implemented the agreed update for deterministic initial search coverage in Optuna with a simple UI and reliability-first behavior:

1. `coverage_mode` toggle added to Optuna settings.
2. Deterministic structured startup trials are generated and enqueued before optimization.
3. Coverage logic works for both single-process and multiprocess Optuna runs.
4. Coverage mode is propagated through WFA flow.
5. TPE startup random phase is disabled in coverage mode (`n_startup_trials=0`) so coverage replaces random startup.
6. UI warning text is in English and uses the agreed format:
   `Need more initial trials (min: X, recommended: Y)`.
7. No new core module file was created; logic is implemented inside existing `src/core/optuna_engine.py`.

Out of scope (kept unchanged in this update):

1. Optuna seed feature.
2. DB schema changes.
3. Full grid search.

---

## 2) Files Changed

### Core / Backend

1. `src/core/optuna_engine.py`
2. `src/core/walkforward_engine.py`
3. `src/ui/server_services.py`
4. `src/ui/server_routes_run.py`

### Frontend

1. `src/ui/templates/index.html`
2. `src/ui/static/js/ui-handlers.js`
3. `src/ui/static/js/optuna-ui.js`
4. `src/ui/static/js/queue.js`
5. `src/ui/templates/results.html`
6. `src/ui/static/js/results-controller.js`
7. `src/ui/static/js/results-tables.js`

### Tests

1. `tests/test_coverage_startup.py` (new)
2. `tests/test_walkforward.py` (extended)
3. `tests/test_server.py` (extended)

---

## 3) Implemented Logic

## 3.1 Configuration and data flow

Added `coverage_mode: bool` support end-to-end:

1. Parsed in `_build_optimization_config()` from UI payload.
2. Stored on `OptimizationConfig`.
3. Passed into `OptunaConfig`.
4. Preserved in WFA `base_template` and `optuna_settings`.
5. Forwarded into per-window Optuna runs in `walkforward_engine.py`.
6. Persisted through existing JSON config storage (no migration required).

## 3.2 Deterministic coverage scheduler (in `optuna_engine.py`)

Implemented private helper set:

1. `_analyze_coverage_requirements(...)`
2. `_latin_hypercube_points(...)` (deterministic)
3. `_generate_coverage_trials(...)`
4. numeric denormalization and deterministic round-robin helpers.

Behavior:

1. If categorical parameters exist:
   - choose largest categorical axis as stratification axis;
   - split startup trials across axis options as evenly as possible;
   - generate LHS points for numeric dimensions within each stratum;
   - assign secondary categoricals via deterministic round-robin (no random drift).
2. If no categorical parameters:
   - generate plain deterministic LHS across numeric parameters.
3. Trial values are denormalized and snapped/clamped to parameter constraints.
4. Final list is deterministically shuffled for interleaving.

## 3.3 Coverage in Optuna execution

In both execution paths:

1. Build search space.
2. Create study.
3. If `coverage_mode` is enabled:
   - generate deterministic startup trial list;
   - enqueue with `study.enqueue_trial(...)`;
   - then run `study.optimize(...)`.

Applied for:

1. `OptunaOptimizer._optimize_single_process()`
2. `OptunaOptimizer._optimize_multiprocess()`

## 3.4 TPE startup override in coverage mode

In `OptunaOptimizer.__init__`:

1. If `coverage_mode=True` and sampler is TPE, set sampler config `n_startup_trials=0`.
2. This prevents additional random startup trials and makes coverage startup the effective warmup.

## 3.5 Warning metrics and message

Coverage requirement math implemented (`n_min`, `n_rec`) and wired into:

1. runtime summary (`optuna_summary`) for diagnostics;
2. Start page info line calculation.

UI warning text exactly as agreed:

`Need more initial trials (min: X, recommended: Y)`

Shown when coverage mode is enabled and initial trials are below recommended.

## 3.6 UI changes

### Start page

1. Renamed label:
   - `Initial random trials` -> `Initial trials`.
2. Added checkbox:
   - `Coverage mode (stratified LHS)`.
3. Added compact dynamic info/warning line under checkbox.
4. Added automatic UI recalculation when relevant controls change:
   - coverage checkbox, initial trials, sampler, NSGA population;
   - strategy change, parameter enable/disable, options selection, range edits.

### Queue

1. Queue restore now applies `coverage_mode` checkbox.
2. Queue form refresh now triggers coverage info refresh.

### Results page

1. Added `Initial` row in Optuna Settings.
2. Displays:
   - `N (coverage)` if coverage mode enabled;
   - `N` otherwise;
   - `-` for legacy data.

---

## 4) Problems Solved

1. Removed startup randomness dependence by replacing random warmup with deterministic coverage startup.
2. Prevented TPE from adding extra random warmup when coverage mode is active.
3. Ensured consistent startup behavior across:
   - normal Optuna runs;
   - WFA window-level runs;
   - multiprocess execution.
4. Added clear user-facing guidance when initial trial count is insufficient.
5. Kept implementation backward-compatible and isolated behind `coverage_mode`.

---

## 5) Reliability and Compatibility Notes

1. Default behavior remains unchanged (`coverage_mode=False`).
2. No DB schema changes.
3. Existing studies continue to load.
4. Queue and WFA pipelines preserve coverage mode configuration.
5. Determinism is based on internal fixed scheduling and deterministic helpers, independent of external seed.

---

## 6) Test Coverage Added / Updated

### New tests (`tests/test_coverage_startup.py`)

1. LHS shape/range/interval coverage.
2. Deterministic generation repeatability.
3. Main-axis balancing and bounds/step correctness.
4. Requirement math (`n_min`, `n_rec`, NSGA population effect).
5. TPE startup override (`n_startup_trials=0`) in coverage mode.
6. Coverage warning message in runtime summary.

### Extended tests

1. `tests/test_walkforward.py`
   - added coverage forwarding test for `_run_optuna_on_window`.
2. `tests/test_server.py`
   - added parser test for `coverage_mode`.

---

## 7) Test Execution Results

Executed:

1. `py -3 -m pytest -q tests/test_coverage_startup.py tests/test_walkforward.py::test_run_optuna_on_window_forwards_coverage_mode tests/test_server.py::test_optuna_coverage_mode_parsed`
2. `py -3 -m pytest -q tests/test_optuna_sanitization.py`
3. `py -3 -m pytest -q` (full suite)

Result:

1. `8 passed` for the targeted coverage/WFA/server tests.
2. `6 passed` for optuna sanitization regression check.
3. Full suite: `223 passed`, `2 failed`, `3 warnings`.
4. Failing tests:
   - `tests/test_dsr.py::test_calculate_expected_max_sharpe_basic`
   - `tests/test_dsr.py::test_calculate_dsr_high_sharpe_track_length`
5. Failure reason from logs:
   - `SciPy not available for DSR calculation: No module named 'scipy'`
6. These failures are environment/dependency related and outside this coverage-mode update scope.

---

## 8) Errors / Issues During Implementation

1. `pytest` command was not available in PATH in this environment.
2. Resolved by using Python launcher invocation:
   - `py -3 -m pytest ...`
3. Full regression suite reports 2 DSR-related failures due to missing SciPy dependency in environment.
4. No functional errors were found in the implemented coverage-mode paths in targeted tests.

---

## 9) Final Outcome

The update has been implemented with the agreed behavior and constraints:

1. Deterministic coverage startup is operational.
2. Coverage mode is wired through Optuna + WFA + UI + queue + results display.
3. Warning message is concise and in English, exactly matching requested format.
4. Existing behavior is preserved when coverage mode is off.
5. Tests validate core scheduling behavior, parser wiring, and WFA forwarding.
