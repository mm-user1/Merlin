# Silent strategy resolution failure during CSV import typing

## Summary
- **Problem:** CSV preset imports could “succeed” while strategy parameters stayed as raw strings when the server failed to resolve strategy typing (missing/undiscoverable strategies or config load errors). The API returned 200 with no warning, risking incorrect presets being applied silently.
- **Impact:** Incorrect parameter types (e.g., `"45"` instead of `45` or `"EMA"` uppercasing not applied) could propagate to backtests or defaults without users noticing.
- **Fix:** Enforce type availability for strategy-specific fields: if type inference is unavailable and the CSV contains any non-date/non-dateFilter fields, the API now returns HTTP 400 with a clear reason. Existing happy-path behavior is unchanged when typing is available; date-only imports still work.

## Root cause
- `_parse_csv_parameter_block` attempted to infer `strategy_id` (request payload → first discovered strategy). When this failed (empty registry, bad working directory, broken config import), `param_types` stayed `{}`.
- The function then continued parsing all CSV parameters, falling back to `_convert_import_value`, which only knows about a handful of generic fields. Strategy parameters therefore remained untyped strings, yet the endpoint returned success.
- Frontend requests do not include a `strategy` field, so the server relied on discovery; if discovery failed, the silent fallback always triggered.

## What changed
1. **Defensive guard in `_parse_csv_parameter_block`** (`src/ui/server.py`):
   - Track why strategy typing is unavailable.
   - If no parameter types are available and the CSV contains any fields beyond the safe generic set `{start, end, dateFilter}`, raise `ValueError` with a precise explanation and the offending fields. This prevents silent mis-typed imports while still allowing date-only imports.
2. **Better API error surfacing** (`import_preset_from_csv` endpoint):
   - Catch `ValueError` from the parser and return HTTP 400 with the informative message instead of a generic failure.
3. **Regression tests** (`tests/test_server.py`):
   - Added coverage for two failure modes: no strategies discoverable and strategy config load failure. Both now assert a 400 response with the new message. Existing happy-path tests remain green.

## Verification
- Ran `py -m pytest tests/test_server.py -k import` → **5 passed** (includes new guards and existing import scenarios).

## Notes / scope
- No UI change made (per request). The server-side fix is sufficient to prevent silent mis-typed imports even when the client omits the `strategy` field.
