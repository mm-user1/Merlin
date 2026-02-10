# Phase 1-3-1 Download Trades Issues: Full Investigation Changelog

## Scope

This document is a full step-by-step changelog of the Download Trades investigation and fixes performed in this session for WFA Adaptive studies (with comparisons to Fixed WFA behavior).

Primary user-reported symptoms:

1. Adaptive WFA produced an incorrect last window with `0d`.
2. Downloaded stitched OOS trades for adaptive studies diverged from Results page and TradingView metrics/trade count.


## Environment and Reference Data

- Project: `./+Merlin/+Merlin-GH/`
- Main DB used for investigation:
  - `src/storage/2026-02-10_192736_for-test-wfa-adaptive.db`
- Key study IDs repeatedly validated:
  - `b78548fd-5dd5-42fd-993c-4feff71c0406` (`S03_OKX_DOGEUSDT.P, 1h 2025.06.01-2026.02.01_WFA`)
  - `734bcd48-8dab-43d2-b03c-334cbc514713` (`S01_OKX_SUIUSDT.P, 30 ... WFA (2)`)
- CSV samples supplied by user:
  - `docs/S03_OKX_DOGEUSDT.P, 1h 2025.06.01-2026.02.01_WFA_wfa_oos_trades.csv`
  - `docs/S03_OKX_DOGEUSDT.P, 1h 2025.06.01-2026.02.01_WFA_wfa_oos_trades (2).csv`
  - `docs/S03_OKX_DOGEUSDT.P, 1h 2025.06.01-2026.02.01_WFA_wfa_oos_trades (3).csv`
  - `docs/S03_OKX_DOGEUSDT.P, 1h 2024.10.02-2026.02.01_WFA_wfa_oos_trades.csv`
- Required interpreter used for checks/tests:
  - `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe`


## Phase 1: Initial Adaptive Bug (`0d` Last Window)

### Hypothesis A

The adaptive loop can incorrectly append a final window when OOS end is at/after the dataset boundary and alignment logic allows a zero-duration OOS segment.

### Investigation

1. Reviewed adaptive split/loop logic in `src/core/walkforward_engine.py`.
2. Checked boundary calculations and index alignment (`searchsorted`) in adaptive mode.
3. Compared fixed WFA shift logic vs adaptive shift logic.

### Findings

1. Adaptive next-window shift and boundary normalization could create an extra terminal window in edge cases.
2. That window could display as `0d` (same start/end day after alignment).

### Fix Applied

1. Tightened adaptive boundary checks and stop conditions.
2. Enforced non-overlap/forward-only progression in adaptive next-window alignment.
3. Added adaptive regression coverage:
   - `tests/test_adaptive_wfa.py` (including non-overlap and no `0d` trailing window behavior).

### Result

New adaptive runs no longer append the invalid `0d` terminal window.


## Phase 2: Download Trades Mismatch (Count and Metrics Drift)

After the window bug, focus moved to Download Trades inconsistency for adaptive stitched OOS.

### User-Observed Symptom

Results page showed one trade count/metrics, while downloaded CSV imported into TradingView showed more trades and different metrics.

### Hypothesis B

Date-only boundary persistence in WFA windows (`YYYY-MM-DD`) causes range widening during export replay (especially adaptive intraday trigger end), including extra trades.

### Investigation

1. Inspected storage schema and save/load pipeline:
   - `src/core/storage.py`
2. Inspected period resolver used by export routes:
   - `src/ui/server_services.py` (`_resolve_wfa_period`)
3. Inspected download routes:
   - `src/ui/server_routes_data.py`
4. Compared per-window stored OOS totals vs replayed exports.

### Findings

1. Adaptive OOS often ends intraday (trigger time), but date-only end can be expanded to end-of-day on replay.
2. This can over-include trades in export.
3. Stitched export amplifies this when concatenating windows.

### Fix Applied

1. Added precise timestamp columns for WFA windows (`*_ts`) in storage/migrations and persistence.
2. Updated `_resolve_wfa_period` to prefer precise timestamp fields.
3. Added fallback reconstruction for legacy adaptive rows using `oos_actual_days` when precise end timestamp is absent.
4. Added OOS trade normalization/capping by stored `oos_total_trades` in download routes.

### Validation

1. Added/updated server and storage tests:
   - `tests/test_server.py`
   - `tests/test_storage.py`
2. Verified key adaptive study counts against stored totals.

### Interim Result

Most count drift was fixed, but one important TradingView mismatch remained (`54` vs `59`) for adaptive stitched export.


## Phase 3: Deep Dive Into Remaining `54 vs 59` TradingView Divergence

### Symptom

For study `b78548fd-5dd5-42fd-993c-4feff71c0406`:

1. Merlin stitched OOS: `54` trades.
2. TradingView import from downloaded CSV: `59` trades.
3. CSV file itself had `108` rows (exactly `54` entry/exit pairs).

### Hypothesis C (Interim, Incorrect)

The issue is due to float artifacts or pure timestamp ordering in CSV serializer.

### Investigation

1. Parsed exported CSVs directly.
2. Confirmed:
   - 108 data rows
   - 54 pairs structurally
   - one duplicate timestamp (`2026-01-05 00:00:00`) existed but not enough alone to explain +5 trades
3. Checked event ordering around suspicious timestamp clusters.

### Interim Action

1. Strengthened formatting in `src/core/export.py`:
   - numeric normalization to remove float tails
   - chronological event sorting logic (already in place during earlier attempts)
2. Added export tests.

### Interim Outcome

Not sufficient to explain/fix the final TradingView mismatch.


## Phase 4: Root Cause Isolation (Final)

### Hypothesis D (Confirmed Root Cause)

Adaptive legacy windows in the problematic study overlap in OOS time, and global event sorting interleaves transactions across windows. That interleaving breaks flat-position sequencing for TradingView parser and creates synthetic extra trades.

### Investigation Steps

1. Queried DB window boundaries for study `b78548fd-5dd5-42fd-993c-4feff71c0406`:
   - W1 OOS: `2025-08-30 00:00:00` to `2025-10-07 12:00:00`
   - W2 OOS: `2025-10-07 00:00:00` to `2026-01-05 00:00:00`
   - W3 OOS: `2026-01-05 00:00:00` to `2026-02-01 00:00:00`
2. Confirmed explicit overlap:
   - W1 ends after W2 starts (`2025-10-07 12:00` vs `2025-10-07 00:00`).
3. Simulated trade event replay:
   - preserving window/trade sequence -> 54 opens / 54 closes (flat, correct)
   - global timestamp re-sort -> trade pairing shifts and closed-trade semantics drift.

### Key Clarification

User strategy does not require same-bar entry+exit to trigger this bug. The issue is cross-window transaction interleaving due to overlap + global resort.


## Phase 5: Final Robust Fix for Download Trades

### Design Decision

Keep normal chronological sort behavior for non-stitched exports, but for stitched WFA OOS export preserve original per-window/per-trade sequence to keep deterministic pairing consistent with how WFA results are produced.

### Code Changes

1. `src/core/export.py`
   - Added `sort_events_chronologically: bool = True` to `export_trades_csv`.
   - If `False`, events are emitted in input sequence.
2. `src/ui/server_routes_data.py`
   - In stitched WFA route (`/api/studies/<id>/wfa/trades`) call:
     - `export_trades_csv(..., sort_events_chronologically=False)`
   - This avoids cross-window interleaving in legacy-overlap cases.
3. Retained all previous boundary precision and normalization fixes.

### Regression Tests Added

1. `tests/test_export.py`
   - `test_export_trades_csv_can_preserve_input_event_order`
2. `tests/test_server.py`
   - `test_download_wfa_trades_preserves_window_sequence_for_overlap`
3. Existing tests retained for precision bounds and trade-count capping.


## Phase 6: Test Execution and Verification

Executed targeted tests with required interpreter:

`C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests/test_export.py tests/test_server.py tests/test_adaptive_wfa.py`

Result:

- `32 passed`
- `0 failed`

Direct endpoint replay check on problematic study:

1. `/api/studies/b78548fd-5dd5-42fd-993c-4feff71c0406/wfa/trades`
2. Export produced 108 rows (54 pairs).
3. Pairing replay showed:
   - opens: 54
   - closes: 54
   - final position: flat


## Evolution of Hypotheses and What Was Learned

1. `0d` final window was a real adaptive loop boundary issue.
2. Date-only boundary storage/resolution was a real over-inclusion source for adaptive exports.
3. Float artifacts were real formatting noise but not the main reason for `54 vs 59`.
4. Pure chronological sorting is generally good, but stitched adaptive legacy overlap is a special case where global resort harms pair semantics.
5. Final root cause for `54 vs 59`: overlap + cross-window interleaving in exported transaction stream.


## Fixed vs Adaptive vs Legacy Impact

1. Optuna exports:
   - unchanged behavior.
2. Fixed WFA:
   - unchanged functional behavior in normal cases.
3. Adaptive WFA (new studies):
   - no overlap after adaptive split fix.
4. Adaptive WFA (older studies made before split fix):
   - stitched export now robust against overlap-induced interleaving by preserving sequence.


## Remaining Operational Guidance

1. For production evaluation, prefer rerunning adaptive studies after non-overlap adaptive fix.
2. Legacy adaptive studies should still export consistently after this final sequencing fix, but rerun is still preferable for clean statistical integrity.
3. If any new discrepancy appears, compare:
   - stored `stitched_oos_total_trades`
   - per-window `oos_total_trades`
   - exported event sequence around window boundaries.


## Files Touched During This Investigation/Fix Path

Core:

- `src/core/walkforward_engine.py`
- `src/core/storage.py`
- `src/core/export.py`

UI/API:

- `src/ui/server_services.py`
- `src/ui/server_routes_data.py`

Tests:

- `tests/test_adaptive_wfa.py`
- `tests/test_storage.py`
- `tests/test_export.py`
- `tests/test_server.py`

Reports:

- `docs/phase_1-3-1_fixes-adaptive-wfa_report.md`
- `docs/phase_1-3-1_download-trades-issues.md` (this file)
