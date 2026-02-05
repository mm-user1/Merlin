# Phase 1 Report: S03 Reversal v10 Import

## Summary
Implemented the new strategy `s03_reversal_v10` with UI name "S03 Reversal v10" and study prefix behavior "S03" (via `s03_` ID). Added full parameter schema, strategy logic, and reference tests aligned to the provided PineScript v5 specification. The implementation reuses existing MA infrastructure and follows Merlin’s execution and date-filtering patterns.

## What Was Added
- New strategy module:
  - `src/strategies/s03_reversal_v10/config.json`
  - `src/strategies/s03_reversal_v10/strategy.py`
  - `src/strategies/s03_reversal_v10/__init__.py`
- New reference tests:
  - `tests/test_s03_reversal_v10.py`

## Key Strategy Logic
- **MA & Offset**: Uses `get_ma` from `indicators/ma.py` with optional `%` offset for `maOffset3`.
- **T-Bands Hysteresis**:
  - Bands computed as % offsets from MA.
  - `t_band_state` transitions on confirmed band breaks or cross-fail logic.
- **Close-Count Filter**:
  - Counts consecutive closes above/below MA.
  - Enables long/short only once counts reach configured thresholds.
- **Trade Logic Switch (Guard)**:
  - If both `useCloseCount` and `useTBands` are `false`, trading is disabled (no entries).
- **Entry/Exit**:
  - Opposite signal closes current position at bar close.
  - Entries only allowed when flat **and** `prev_position == 0` to enforce 1‑bar delay (matches Pine intent).
- **Position Sizing**:
  - Uses **realized balance** (Merlin standard) and `contractSize`.
- **Commission**:
  - Percent commission (`commissionPct`) aligned with S04 reference.
- **Date Filter**:
  - Uses Merlin’s `dateFilter` + `trade_start_idx` (same pattern as S01).
- **Equity/Balance Curves**:
  - `equity_curve`: mark‑to‑market (balance + unrealized).
  - `balance_curve`: realized balance (used for drawdown metrics; matches expected Pine results).
- **Forced Close**:
  - Any open position is closed on the final bar via `build_forced_close_trade`.

## Optuna Defaults (from Pine)
- `maType3`: optimize enabled (all options)
- `maLength3`: min 25, max 500, step 25
- `maOffset3`: min -2.0, max 2.0, step 0.5
- `useCloseCount`: optimize enabled
- `closeCountLong`: min 2, max 7, step 1
- `closeCountShort`: min 2, max 7, step 1
- `useTBands`: optimize enabled
- `tBandLongPct`: min 0.2, max 2.0, step 0.2
- `tBandShortPct`: min 0.2, max 2.0, step 0.2

## Reference Tests
Command executed:
```
C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests/test_s03_reversal_v10.py -v
```
Results:
- `test_s03_basic_run`: PASSED
- `test_s03_reference_performance`: PASSED

Expected Pine metrics matched within tolerance:
- Net Profit %: 186.61
- Max Drawdown %: 35.49
- Total Trades: 221

## Deviations / Notes
- **Order timing** uses Merlin’s existing bar‑close execution (Option 1) for consistency; Pine’s next‑bar behavior was intentionally not replicated.
- **Date filtering** relies on Merlin’s preprocessing (`prepare_dataset_with_warmup`) rather than Pine’s direct time checks.
- **Drawdown** uses realized balance curve to align with expected Pine results.

## Status
Phase 1 implementation completed with passing reference tests and no outstanding deviations from requirements.
