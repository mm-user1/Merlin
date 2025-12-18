# Invalid numeric CSV values silently became 0 / 0.0

## Summary
- **Problem:** When importing preset CSVs, non-numeric values for typed parameters (`int` / `float`) were coerced to `0` or `0.0` without warning in `_parse_csv_parameter_block`.
- **Impact:** A typo like `riskPerTrade,2o` looked like a successful import yet materially changed backtest/optimization inputs, risking misleading results.
- **Status:** Fixed. Invalid numeric fields now surface a structured error and block the import; no parameters are applied when conversion errors are present.

## Root cause
- In `src/ui/server.py` lines ~336–348, failed numeric conversions were caught and replaced with `0`/`0.0`, and the field was still marked as `applied`.
- The import endpoint treated this as success, returning HTTP 200 with the mutated values. The frontend therefore applied zeroed parameters with no indication of failure.

## What changed
1. **Error collection during parsing** (`src/ui/server.py`):
   - `_parse_csv_parameter_block` now tracks conversion errors for typed numeric parameters instead of defaulting to zero.
   - Invalid numerics are skipped (not added to `updates`/`applied`) and added to an `errors` list.
2. **Clear API failure response** (`/api/presets/import-csv`):
   - If any numeric conversion errors are detected, the endpoint now returns HTTP 400 with JSON payload `{"error": "Invalid numeric values in CSV.", "details": [...]}`.
   - Happy-path behavior is unchanged for valid CSVs; other existing validation paths are untouched.

## Validation
- **Tests added:** `tests/test_server.py`
  - `test_csv_import_rejects_invalid_int`
  - `test_csv_import_rejects_invalid_float`
  - `test_csv_import_stops_on_mixed_valid_and_invalid_numbers`
- **Test run:** `py -3 -m pytest tests/test_server.py -k import` → **8 passed**.

## Why this fixes the problem
- Any non-numeric value for an `int`/`float` parameter now produces a blocking 400 response with explicit field-level details, so the UI cannot silently apply corrupted defaults. Valid imports remain unaffected, preserving prior behavior where no errors occur.
