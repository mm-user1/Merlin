# Phase 1-3-1 Fix Report: Adaptive WFA Boundary and Download Trades Reliability

## 1. Problems Addressed

Two high-impact issues were fixed in this phase:

1. Adaptive WFA could append an invalid final `0d` window (`oos_start == oos_end`).
2. Download Trades for WFA could over-include trades (especially adaptive OOS/stitched exports) because window boundaries were stored and resolved as date-only values.

The user-provided DB for investigation was:

- `src/storage/2026-02-10_192736_for-test-wfa-adaptive.db`


## 2. Root Causes

### 2.1 Adaptive `0d` last window

Boundary semantics mismatch:

1. API preprocessing used exact end timestamp (`<= end_ts`).
2. Adaptive loop used normalized day expansion (`trading_end.normalize() + 1 day`).
3. This permitted an extra boundary-start OOS candidate and could produce zero OOS duration.

### 2.2 Download Trades boundary drift

WFA boundaries in storage were persisted as date-only (`YYYY-MM-DD`) via `_format_date`, then re-aligned in export flow:

1. Date-only OOS end is expanded to end-of-day during `align_date_bounds`.
2. Adaptive OOS windows may end intraday (trigger point), so day expansion includes extra trades.
3. Stitched export accumulated the same boundary error across windows.


## 3. Implementation Summary

### 3.1 Adaptive engine hardening (already implemented in prior step)

File:

- `src/core/walkforward_engine.py`

Changes:

1. Removed normalized+1day end expansion in adaptive loop.
2. Used exact `trading_end` stop condition.
3. Switched OOS max-end index selection to `searchsorted(..., side="right") - 1`.
4. Added explicit zero-length OOS guard (`oos_max_end <= oos_start` -> break).

Scope:

- Adaptive WFA only.
- Fixed WFA and Optuna flows unchanged.

### 3.2 Download Trades robust boundary fix (this step)

Files:

- `src/core/storage.py`
- `src/ui/server_services.py`
- `src/ui/server_routes_data.py`

Changes:

1. Added exact WFA timestamp fields to persistence/migration schema:
   - `optimization_start_ts`, `optimization_end_ts`
   - `ft_start_ts`, `ft_end_ts`
   - `is_start_ts`, `is_end_ts`
   - `oos_start_ts`, `oos_end_ts`
2. Persisted both date-only and exact timestamp boundaries when saving WFA windows.
3. Updated `_resolve_wfa_period()` to prefer exact timestamps, then fallback to legacy fields.
4. Added legacy adaptive reconstruction fallback:
   - if exact OOS end is missing and only date fields exist,
   - reconstruct OOS end as `oos_start + oos_actual_days` (fractional days).
5. Updated stitched OOS export route to use `_resolve_wfa_period(window, "oos")` instead of raw date columns.
6. Exposed new timestamp fields in window details payload for consistency/debugging.


## 4. Why This Solves the Download Trades Issue

For new studies:

- exports use exact persisted boundaries (no date-only widening), so adaptive trigger truncation is respected.

For legacy adaptive studies:

- if exact timestamp columns are absent, OOS end is reconstructed from `oos_actual_days`, which significantly improves accuracy versus date-only expansion.

For fixed WFA and Optuna:

- behavior remains unchanged because their boundaries are day-based and resolver fallback preserves prior semantics.


## 5. Validation and Regression Coverage

### 5.1 Automated tests added/updated

- `tests/test_adaptive_wfa.py`
  - `test_adaptive_does_not_append_zero_day_last_window`
- `tests/test_storage.py`
  - extended schema assertions for new `*_ts` fields
  - `test_wfa_window_timestamp_precision_persisted`
- `tests/test_server.py`
  - `test_resolve_wfa_period_oos_prefers_precise_timestamp_and_legacy_timestamps`
  - `test_download_wfa_trades_uses_precise_oos_timestamp_bounds`

### 5.2 Test execution

Executed:

```bash
py -3 -m pytest tests/test_server.py tests/test_storage.py tests/test_adaptive_wfa.py tests/test_walkforward.py
```

Result:

- `39 passed`
- `0 failed`

Additional full-suite check:

```bash
py -3 -m pytest
```

Result:

- `174 passed`
- `2 failed` (both in `tests/test_dsr.py`, caused by missing `scipy` in environment, not related to WFA changes)


## 6. Reference DB Verification

Using `src/storage/2026-02-10_192736_for-test-wfa-adaptive.db` and the target study from screenshot:

- before this fix, stitched export recalculated trade count could exceed stored stitched OOS count due end-of-day expansion.
- after resolver/storage updates, recalculated stitched OOS trade count matched stored value exactly (`145`).

This confirms boundary precision is now correctly applied for the investigated case.


## 7. Compatibility and Scope

- Fixed WFA: unchanged behavior.
- Optuna optimization: unchanged behavior.
- Adaptive WFA: corrected end-window generation and precise export boundaries.
- Legacy adaptive studies: improved export accuracy through `oos_actual_days` reconstruction fallback when exact timestamp columns are absent.


## 8. Deviations / Notes

- No architectural deviation from existing design; changes are additive and backward compatible.
- One known legacy limitation remains possible when old records lack exact start timestamps and require reconstruction from date-only + duration (rare edge alignment drift); new studies are not affected because exact timestamps are persisted directly.


## 9. Final Download Trades Parity Fix (Completed)

After additional user verification, one remaining mismatch was found on stitched export for an adaptive legacy study:

- Results page: `190` stitched OOS trades
- Downloaded CSV / TradingView: `191` trades

### 9.1 Final root cause

Even with improved timestamp boundaries, export still reconstructed trades from rerun date ranges.  
Adaptive WFA metrics are truncated by trigger logic (trade-index semantics), so a boundary trade could remain in export even when stored window metrics already excluded it.

### 9.2 Final implementation

File changed:

- `src/ui/server_routes_data.py`

Added robust OOS export normalization helper and applied it to:

1. `/api/studies/<id>/wfa/windows/<n>/trades` for OOS result export
2. `/api/studies/<id>/wfa/trades` stitched OOS export

Normalization rules:

- closed trades only (`entry_time` + `exit_time` required)
- bounded by resolved OOS interval (`entry_time` and `exit_time` inside period)
- deterministic order by exit time (then entry time)
- hard cap by stored `oos_total_trades` per window when available

This aligns exported trade count/order with stored WFA window metrics.

### 9.3 Verification

1. Automated tests:
   - added `test_download_wfa_window_trades_respects_stored_oos_trade_count` in `tests/test_server.py`
   - full targeted WFA/server/storage suite:
     - `39 passed`, `0 failed`

2. Reference DB re-check (`2026-02-10_192736_for-test-wfa-adaptive.db`):
   - target study `S01_OKX_SUIUSDT.P, 30 2024.11.01-2026.02.01_WFA (2)` now recalculates stitched export count exactly:
     - `190` (calculated/export path) == `190` (stored stitched OOS)
   - two other related studies in same DB also matched stitched counts exactly.


## 10. Final Stitched CSV Sequencing Fix (TradingView 59 vs 54)

Additional investigation found a TradingView divergence for adaptive stitched export:

- Results page stitched OOS trades: `54`
- TradingView report from exported CSV: `59`

### 10.1 Root cause

This was **not** caused by strategy logic placing entry+exit on one bar.

Root issue was stitched export sequencing:

1. Stitched WFA export merged trades from multiple windows.
2. CSV writer globally re-sorted all entry/exit events by timestamp.
3. For legacy adaptive windows with overlap (created before adaptive boundary fix), timestamp sorting interleaved transactions from different windows.
4. Interleaving broke flat-position trade pairing and TradingView interpreted extra synthetic trades.

### 10.2 Fix

Files changed:

- `src/core/export.py`
- `src/ui/server_routes_data.py`

Changes:

1. Added `sort_events_chronologically` flag to `export_trades_csv()`:
   - default `True` for existing non-stitched exports
   - `False` preserves incoming event sequence.
2. Updated stitched WFA download endpoint (`/api/studies/<id>/wfa/trades`) to:
   - keep per-window concatenation order
   - call `export_trades_csv(..., sort_events_chronologically=False)`.
3. Kept numeric normalization for `Qty`/`Fill Price` (float artifact cleanup).

Result: stitched export preserves intended window trade sequence and avoids synthetic cross-window interleaving.

### 10.3 Verification

1. Added regression tests:
   - `tests/test_export.py::test_export_trades_csv_can_preserve_input_event_order`
   - `tests/test_server.py::test_download_wfa_trades_preserves_window_sequence_for_overlap`
2. Executed targeted suite with required interpreter:
   - `C:\\Users\\mt\\Desktop\\Strategy\\S_Python\\.venv\\Scripts\\python.exe -m pytest tests/test_export.py tests/test_server.py tests/test_adaptive_wfa.py`
   - Result: `32 passed`, `0 failed`
3. Direct endpoint replay for problematic study `b78548fd-5dd5-42fd-993c-4feff71c0406`:
   - exported rows: `108` (`54` round-trips)
   - replayed pairing: `54` opens / `54` closes / final flat position
   - confirms no synthetic extra trades in stitched transaction sequence semantics
