# Phase 1-3-2 Report: WFA Adaptive Window Overlap and Download Trades Consistency

Date: 2026-02-11

## 1) Objective
Deliver a robust, concise, future-proof fix for the new WFA Adaptive mode so that:
1. Adaptive windows do not overlap at boundaries.
2. The previous `0d` last-window issue remains resolved.
3. Downloaded Adaptive OOS and stitched OOS trades match stored Merlin totals.
4. Fixed WFA behavior remains unchanged.

## 2) Root Cause Summary
Two coupled issues were present in Adaptive mode.

1. Window boundary overlap.
The adaptive loop could advance next window start using normalized-date alignment, allowing a same-date restart earlier than prior window actual OOS end (intraday overlap).

2. Export mismatch (`Merlin total` vs `downloaded CSV/TradingView total`).
Replay/export often relied on date-only bounds. For intraday OOS boundaries this widened the replay interval, which could include extra trades around boundaries.

These two factors together explained strange stitched OOS curve shapes near some window borders and trade-count mismatches.

## 3) Design Decision
Applied fix: next Adaptive window starts on the first bar strictly after previous OOS end bar.

Rationale:
1. It enforces strict non-overlap by construction.
2. It avoids skipping potentially valid data (which can happen with a coarse "next day only" rule).
3. It is timeframe-agnostic and works for intraday data.

Important: this is "next bar" semantics, not "next calendar day" semantics.

## 4) Implementation

### 4.1 Adaptive progression guard (core fix)
File: `src/core/walkforward_engine.py`

Changed adaptive next-start alignment:
1. From `searchsorted(next_start_target.normalize(), side="left")`
2. To `searchsorted(next_start_target, side="right")`

Effect: `next_window.oos_start` is always strictly greater than `prev_window.oos_end`.

### 4.2 Precise timestamp persistence for WFA windows
File: `src/core/storage.py`

Added/ensured WFA timestamp columns:
1. `optimization_start_ts`, `optimization_end_ts`
2. `ft_start_ts`, `ft_end_ts`
3. `is_start_ts`, `is_end_ts`
4. `oos_start_ts`, `oos_end_ts`

Save path now persists both date and timestamp boundaries. Insert code was made explicit via column list + generated placeholders for safer schema evolution.

### 4.3 Period resolution prefers exact timestamps
File: `src/ui/server_services.py`

`_resolve_wfa_period()` now resolves bounds in order:
1. exact `*_ts`
2. `*_date`
3. legacy keys where needed

Effect: adaptive replay/export uses precise intraday boundaries when available.

### 4.4 Adaptive OOS trade normalization in download routes
File: `src/ui/server_routes_data.py`

Added adaptive OOS normalization used in:
1. `POST /api/studies/<id>/wfa/windows/<n>/trades`
2. `POST /api/studies/<id>/wfa/trades`

Normalization rules:
1. closed trades only
2. bounded by resolved OOS start/end for entry/exit
3. deterministic ordering
4. capped by stored `oos_total_trades` when provided

Effect: downloaded adaptive OOS trades match stored window and stitched totals.

## 5) Treatment of Earlier `0d` Last-Window Fix
Commit `08422a48bd0720da61b8ab5f6698f34859e0d523` addressed terminal zero-day window creation. This fix set keeps that correction and adds strict non-overlap progression. They are complementary, not conflicting.

## 6) Fixed WFA Compatibility
No behavioral change was introduced for Fixed WFA logic. Adaptive-specific normalization is guarded by `adaptive_mode`.

## 7) Tests Added/Updated
1. `tests/test_adaptive_wfa.py`
Added `test_adaptive_oos_windows_do_not_overlap` asserting strict `next.oos_start > prev.oos_end`.

2. `tests/test_storage.py`
Extended schema checks for new timestamp columns and added precision persistence test.

3. `tests/test_server.py`
Added tests for timestamp-preferred period resolution and adaptive OOS download count/boundary consistency.

## 8) Validation Results
Interpreter used:
`C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe`

Targeted tests:
`C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q tests/test_adaptive_wfa.py tests/test_storage.py tests/test_server.py`

Result: `31 passed`.

Full suite:
`C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest -q`

Result: `177 passed`, `0 failed`, `3 warnings` (Optuna experimental warnings).

Reference DB replay verification:
`src/storage/2026-02-10_192736_for-test-wfa-adaptive.db`

1. DOGE study `b78548fd-5dd5-42fd-993c-4feff71c0406`
Stored stitched OOS trades: `54`
Downloaded stitched OOS trades: `54`
Per-window downloaded totals matched stored `oos_total_trades`.

2. SUI study `da8055a5-dc96-4eaa-908c-f7a0236a875d`
Stored stitched OOS trades: `105`
Downloaded stitched OOS trades: `105`
Per-window downloaded totals matched stored `oos_total_trades`.

## 9) Error/Issue Log
No unresolved implementation errors. Final code and tests completed successfully.

## 10) Final Status
Phase 1-3-2 fix is complete.
Adaptive WFA now has strict non-overlapping window progression and consistent OOS/stitched download behavior aligned with stored metrics, while Fixed WFA behavior remains unchanged.
