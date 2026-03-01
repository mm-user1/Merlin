# Phase 1.2 Report: Refactored Optuna Initial Search Coverage

## 1) Objective

Implemented the requested refactor of initial search behavior:

1. Removed the previous `stratified LHS` startup logic.
2. Kept classic random startup behavior (`coverage_mode = false`).
3. Reworked `coverage_mode = true` to deterministic:
   - full categorical coverage per block,
   - fixed numeric anchors,
   - only one numeric parameter varies across blocks (primary numeric paired with the main categorical axis).

Main target: reliability, consistency, and deterministic reproducibility of startup trials.

---

## 2) What Was Changed

### Core

1. `src/core/optuna_engine.py`
   - Removed LHS-specific coverage scheduler/helpers.
   - Implemented deterministic full-coverage scheduler:
     - categorical Cartesian product as base coverage block,
     - midpoint anchoring for all numeric params,
     - varying only inferred primary numeric param across coverage blocks.
   - Added robust helper logic:
     - axis extraction,
     - primary numeric inference (`maType -> maLength`, `maType3 -> maLength3`, etc.),
     - tie-safe quantization (midpoint ties go to lower level),
     - anchor schedule and partial block handling.
   - Coverage analysis now computes:
     - `n_min = coverage_block_size = product(cardinalities of categorical params)`,
     - `n_rec = 2 * n_min`.
   - Coverage warning in summary now triggers only when `initial_trials < n_min`.
   - Summary now includes:
     - `coverage_block_size`,
     - `coverage_primary_numeric`.

### UI

1. `src/ui/static/js/optuna-ui.js`
   - Removed LHS-oriented UI analysis (numeric continuity heuristics, NSGA-dependent recommendation logic).
   - Added coverage analysis aligned with new backend model:
     - block size as categorical product,
     - min/recommended derived from block size (`C`, `2C`),
     - primary numeric inference in UI.
   - Warning remains in agreed English format:
     - `Need more initial trials (min: X, recommended: Y)`
   - Info line now shows block-oriented status:
     - block size,
     - full blocks + partial remainder,
     - main categorical axis and inferred primary numeric.

### Tests

1. `tests/test_coverage_startup.py` (rewritten)
   - Removed LHS tests.
   - Added deterministic full-coverage tests:
     - deterministic generation,
     - full block categorical coverage,
     - primary numeric-only variation across blocks,
     - min/mid/max behavior for `A=3` blocks,
     - deterministic partial block behavior,
     - `n_min/n_rec` product logic,
     - TPE startup override in coverage mode,
     - warning/no-warning summary behavior around minimum threshold.

---

## 3) Final Coverage Logic (Implemented)

For `coverage_mode = true`:

1. Build search space.
2. Split parameters:
   - categorical axes,
   - numeric axes.
3. Compute coverage block size:
   - `C = product(cardinality of each categorical axis)`,
   - if no categorical params, `C = 1`.
4. Compute blocks:
   - `A = floor(initial_trials / C)` full blocks,
   - `R = initial_trials % C` partial remainder.
5. Generate full blocks:
   - enumerate all categorical combinations (`Cartesian product`) in deterministic order,
   - set all numeric params to midpoint,
   - vary only `primary_numeric` by block anchor fraction.
6. Anchor fractions:
   - `A=1`: `[0.5]`
   - `A=2`: `[1/3, 2/3]`
   - `A>=3`: evenly spaced including edges `[0 ... 1]` (so edges are included from step 3 onward).
7. If `R > 0`:
   - add deterministic partial block with one deterministic "next" anchor,
   - deterministic rotated subset of categorical combinations.

For `coverage_mode = false`:

1. Existing random startup path remains unchanged.

---

## 4) Problems Solved

1. Removed complexity and side-effects from LHS-specific startup logic.
2. Ensured startup determinism and consistency for same strategy/search space configuration.
3. Guaranteed categorical coverage in complete blocks.
4. Enforced a clean and interpretable startup structure:
   - one changing numeric driver,
   - all other numeric dimensions fixed at midpoint anchors.
5. Preserved backward-compatible random mode.

---

## 5) Reliability / Compatibility

1. No DB schema migration required.
2. Existing `coverage_mode` configuration flag is preserved and reused.
3. WFA forwarding of `coverage_mode` remains intact.
4. TPE behavior remains safe:
   - in coverage mode startup random phase is disabled (`n_startup_trials = 0`) so enqueued coverage trials are authoritative.

---

## 6) Test Execution

Interpreter used (as requested):

1. `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe`

Commands run:

1. `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q tests/test_coverage_startup.py tests/test_walkforward.py::test_run_optuna_on_window_forwards_coverage_mode tests/test_server.py::test_optuna_coverage_mode_parsed`
2. `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q`

Results:

1. Targeted tests: `10 passed`.
2. Full suite: `227 passed`, `3 warnings`, `0 failed`.

Warnings were Optuna experimental warnings (`multivariate`), not functional failures.

---

## 7) Errors Encountered

No implementation/runtime errors during this update.

---

## 8) Outcome

The update now matches the agreed design direction:

1. No LHS startup path.
2. Two clear modes only:
   - random,
   - deterministic full categorical coverage with fixed numeric anchors.
3. Deterministic, block-structured startup suitable for stable cross-ticker/cross-period comparison.
