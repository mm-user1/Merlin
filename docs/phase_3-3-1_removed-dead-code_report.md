# Removed Dead Code Report (phase_3-3-1)

Date: 2026-01-22
Scope: Merlin repo cleanup of unused functions/imports only. All removals were based on repo-wide reference checks and confirmed by test runs.

## Summary
The following items were removed because they were completely unused within this repository. No functional behavior changes were intended; this is strictly dead-code elimination.

## Removed Functions (with rationale)

### `src/ui/server.py`
- `generate_output_filename(csv_filename, config, mode=None)`
  - Reason: Defined but never called anywhere in the repo.
- `_extract_file_prefix(csv_filename)`
  - Reason: Only referenced by `generate_output_filename`, which was unused.
- `_format_date_component(value)`
  - Reason: Only referenced by `generate_output_filename`, which was unused.
- `_create_param_id_for_strategy(strategy_id, params)`
  - Reason: Never referenced anywhere in the repo.
- `_unique_preserve_order(items)`
  - Reason: Never referenced anywhere in the repo.
- `_get_frontend_param_order(strategy_id)`
  - Reason: Never referenced anywhere in the repo.

### `src/core/metrics.py`
- `calculate_for_wfa(wfa_results)`
  - Reason: Never called anywhere in the repo.

### `src/core/optuna_engine.py`
- `_generate_numeric_sequence(start, stop, step, is_int)`
  - Reason: Never referenced anywhere in the repo.

### `src/core/storage.py`
- `update_study_status(study_id, status, error_message=None)`
  - Reason: Never referenced anywhere in the repo.

## Removed Imports / Constants (with rationale)

### `src/ui/server.py`
- `hashlib`
  - Reason: Only used by `_create_param_id_for_strategy`, which was removed.
- `_DATE_PREFIX_RE`, `_DATE_VALUE_RE`
  - Reason: Only used by `generate_output_filename`/`_format_date_component`, which were removed.

### `src/core/optuna_engine.py`
- `Iterable` (from `typing`)
  - Reason: Not referenced anywhere in the file.
- `Decimal` (from `decimal`)
  - Reason: Only used by `_generate_numeric_sequence`, which was removed.

### `src/indicators/oscillators.py`
- `numpy as np`
  - Reason: Not referenced anywhere in the file.

### `tools/generate_baseline_s01.py`
- `numpy as np`
  - Reason: Not referenced anywhere in the file.

## Notes
- The `atr` import in `src/core/backtest_engine.py` was initially removed as unused by static analysis, but tests revealed external tests depend on `core.backtest_engine.atr`. It was restored to keep API parity.
- Full test suite passed after cleanup (137 tests).
