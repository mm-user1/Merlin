# Phase 3-1 (Layer 1) Implementation Report

## 1. Scope and Goal

This update implements **Layer 1 only** for WFA analytics in Merlin, with focus on:

- Correct metric semantics
- Safe/idempotent persistence
- Reliable UI rendering
- Backward compatibility with existing studies

Target Layer 1 cards now follow the planned 7-card set:

1. `NET PROFIT`
2. `MAX DRAWDOWN`
3. `TOTAL TRADES` (`winning/total`)
4. `WFE`
5. `OOS WINS` (`N/M (%)`)
6. `OOS PROFIT (MED)`
7. `OOS WIN RATE (MED)`

---

## 2. Problems Addressed

The following technical issues were solved:

1. **Winning trades for stitched OOS were not persisted**
- Added explicit support to compute/store stitched winning trades safely.

2. **Plan-level WFE simplification was inconsistent with Merlin engine**
- Kept canonical Merlin WFE semantics from engine (`best_value` / stitched WFE), no formula drift introduced.

3. **Window-level drawdown “worst” semantics**
- Stored `worst_window_dd` as the **maximum** drawdown magnitude across windows (correct for positive DD values).

4. **Layer 1 metric availability for old studies**
- Added UI fallback computation from window-level data when new persisted columns are absent.

5. **Schema update safety**
- Implemented all new DB fields using Merlin’s idempotent migration pattern (`ensure(...)` / guarded `ALTER TABLE`), avoiding non-repeatable migrations.

---

## 3. Implementation Details

### 3.1 Core Engine (`src/core/walkforward_engine.py`)

- Extended `WindowResult` with:
  - `oos_winning_trades: Optional[int] = None`
- Populated this field in both fixed and adaptive WFA flows from `oos_basic.winning_trades`.

Purpose:
- Enables exact stitched winning-trade aggregation without lossy inference.

### 3.2 Storage Schema and Persistence (`src/core/storage.py`)

#### Added `studies` columns

- `stitched_oos_winning_trades INTEGER`
- `profitable_windows INTEGER`
- `total_windows INTEGER`
- `median_window_profit REAL`
- `median_window_wr REAL`
- `worst_window_profit REAL`
- `worst_window_dd REAL`

#### Added `wfa_windows` column

- `oos_winning_trades INTEGER`

#### Migration safety

- Added via idempotent schema guards:
  - `ensure("studies", ...)`
  - guarded `add_col(...)` for `wfa_windows`

#### Aggregate computation on WFA save

During `save_wfa_study_to_db(...)`, Layer 1 aggregates are now computed and stored:

- `stitched_oos_winning_trades`
  - Exact from `oos_winning_trades` where available
  - Safe fallback derivation from `oos_total_trades * oos_win_rate / 100` when needed
- `profitable_windows` / `total_windows`
- `median_window_profit` via Python `statistics.median`
- `median_window_wr` via Python `statistics.median`
- `worst_window_profit = min(oos_net_profit_pct)`
- `worst_window_dd = max(oos_max_drawdown_pct)`

#### Study load payload extension

`load_study_from_db(...)` now includes new Layer 1 fields in `stitched_oos` payload:

- `winning_trades`
- `profitable_windows`
- `total_windows`
- `median_window_profit`
- `median_window_wr`
- `worst_window_profit`
- `worst_window_dd`

### 3.3 Results State Assembly (`src/ui/static/js/results-controller.js`)

Added robust client-side fallback helpers:

- `buildWindowAggregates(...)`
- `deriveWindowWinningTrades(...)`
- `calculateMedian(...)`

Behavior:

- If new study-level fields exist, UI uses them.
- If not (legacy studies), UI derives from `wfa_windows` data.
- Prevents incorrect/blank cards for older DB entries.

### 3.4 Layer 1 Card Rendering (`src/ui/static/js/results-tables.js`)

Reworked `displaySummaryCards(...)`:

- Upgraded from 5 cards to 7 cards
- Updated labels and formats:
  - `TOTAL TRADES`: `winning/total`
  - `WIN RATE` renamed to `OOS WINS` with `N/M (%)`
  - Added `OOS PROFIT (MED)` and `OOS WIN RATE (MED)`
- Added safe formatting helpers for null/legacy cases (`N/A` handling).

### 3.5 Layout (`src/ui/static/css/style.css`)

- Made summary card grid responsive for 7 cards:
  - `grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));`

---

## 4. Tests and Validation

## Test updates

Updated `tests/test_storage.py`:

- Schema assertions for new `studies` and `wfa_windows` columns
- Persistence assertions for new Layer 1 fields
- New multi-window aggregate test for:
  - stitched winning trades
  - profitable/total windows
  - median profit / median WR
  - worst window profit / DD

## Executed test commands

1. Targeted:

```bash
C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests/test_storage.py tests/test_walkforward.py tests/test_server.py -q
```

Result: **40 passed**

2. Full suite:

```bash
C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests/ -q
```

Result: **186 passed**, 3 warnings (Optuna experimental warnings, pre-existing/non-blocking)

---

## 5. Reliability and Future-Proofing Notes

- No destructive migrations used.
- New metrics computed in Python (stable across SQLite builds).
- Legacy-study fallback paths implemented in UI.
- WFE source remains canonical Merlin engine value, avoiding semantic divergence.
- Added dedicated tests to protect new Layer 1 behavior from regressions.

---

## 6. Errors / Incidents During Update

- No implementation/runtime regressions in final test runs.
- One temporary shell quoting issue occurred during an ad-hoc local DB inspection command; it did not affect code or data and was immediately corrected.

---

## 7. Final Outcome

Layer 1 update has been implemented with high accuracy and safe migration behavior.

The update:

- Correctly introduces the 7-card Layer 1 analytics view
- Resolves identified semantic mismatches
- Preserves compatibility with existing studies
- Passes full automated regression testing

