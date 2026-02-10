# Phase 1-3-1 Fix Report: Adaptive WFA Last-Window `0d` Issue

## 1. Problem Summary

After the adaptive WFA update, a trailing extra window could be created with:

- `oos_start_date == oos_end_date`
- `oos_actual_days = 0.0`

In the provided study (`src/storage/2026-02-10_192736_for-test-wfa-adaptive.db`), this appeared as Window 6:

- Window 5 already reached the configured end boundary (`2026-02-01 00:00`)
- Window 6 was incorrectly appended as `OOS: 2026-02-01 -> 2026-02-01 (0d)`


## 2. Root Cause

The issue was caused by boundary-semantics mismatch inside adaptive mode:

1. API preprocessing (`server_routes_run.py`) filtered data with exact timestamp end (`<= end_ts`).
2. Adaptive engine (`_run_adaptive_wfa`) used day-normalized end expansion (`trading_end.normalize() + 1 day`).
3. That expansion allowed one more boundary-start OOS window candidate.
4. OOS max-end lookup could resolve to the same boundary bar as OOS start, producing zero-duration OOS.


## 3. Fix Implemented

### File changed

- `src/core/walkforward_engine.py`

### Adaptive-only corrections

1. Removed end-day expansion in adaptive loop:
   - Uses exact `trading_end` (timestamp) for stop logic.

2. Stop condition aligned to exact end:
   - `if oos_start_target >= trading_end: break`

3. OOS max-end index resolution made exact-end inclusive:
   - `searchsorted(..., side="right") - 1`

4. Added hard guard against zero-length OOS window creation:
   - `if oos_max_end <= oos_start: break`

These changes are scoped only to `_run_adaptive_wfa` and do not modify fixed WFA or Optuna-only flow.


## 4. Why This Solves the Issue

- Adaptive end checks now follow the same exact boundary used by route-level filtering.
- A new window cannot start at or beyond the exact end timestamp.
- Even in edge boundary alignment cases, zero-length OOS windows are blocked explicitly.

Therefore, the invalid trailing `0d` window scenario is eliminated.


## 5. Regression Protection Added

### New test

- `tests/test_adaptive_wfa.py`
  - `test_adaptive_does_not_append_zero_day_last_window`

This test reproduces the problematic boundary pattern (explicit end timestamp at `00:00` with API-like truncation) and asserts:

- no window has non-positive OOS duration
- no window has non-positive `oos_actual_days`
- last OOS end does not exceed configured end boundary


## 6. Validation Results

Executed:

```bash
py -3 -m pytest tests/test_adaptive_wfa.py tests/test_walkforward.py tests/test_storage.py tests/test_server.py
```

Result:

- `35 passed`
- `0 failed`


## 7. Scope / Compatibility

- Fixed WFA behavior: unchanged.
- Optuna optimization behavior: unchanged.
- Adaptive WFA behavior: corrected at end-boundary handling only.


## 8. Notes

The fix is intentionally minimal and defensive:

- one semantic alignment (exact end timestamp)
- one index behavior correction (`side="right"`)
- one explicit invariant guard (no zero-length OOS window)

This keeps the implementation concise while ensuring robust boundary handling.
