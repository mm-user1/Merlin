# Adaptive WFA Re-Optimization Trigger - Implementation Report

## 1. Scope and Goal

Implemented the adaptive WFA update described in `docs/phase_1-3_wfa-re-optimization-trigger_plan_v2_opus_ENG.md` with the agreed clarifications:

- Keep full IS module chain: `Optuna -> DSR -> Forward Test -> Stress Test`.
- Adaptive mode changes only OOS duration logic.
- Trigger precedence: inactivity gap -> drawdown -> CUSUM (checkpointed).
- Fractional-day timing (`total_seconds()/86400.0`) for inactivity and OOS duration.
- Duration-weighted WFE in adaptive mode.
- Dual adaptive-config storage: dedicated DB columns + `config_json`.


## 2. Problems Solved

- Fixed WFA always re-optimized on a rigid OOS schedule.
- No mechanism to end OOS early on degradation.
- No adaptive metadata persisted in DB/UI.
- Existing WFE formula assumed fixed OOS length and was invalid for variable-length adaptive OOS windows.

Result: Merlin now supports adaptive re-optimization windows driven by trigger events while preserving backward-compatible fixed WFA behavior.


## 3. Backend Implementation

### 3.1 `src/core/walkforward_engine.py`

- Added adaptive config fields to `WFConfig`:
  - `adaptive_mode`
  - `max_oos_period_days`
  - `min_oos_trades`
  - `check_interval_trades`
  - `cusum_threshold`
  - `dd_threshold_multiplier`
  - `inactivity_multiplier`

- Extended `WindowResult` with adaptive metadata:
  - `trigger_type`
  - `cusum_final`
  - `cusum_threshold`
  - `dd_threshold`
  - `oos_actual_days` (`float`, fractional days)

- Added new dataclasses:
  - `TriggerResult`
  - `ISPipelineResult`

- Added/implemented adaptive helpers:
  - `_resolve_trading_bounds()`
  - `_run_period_backtest()`
  - `_run_window_is_pipeline()` (full IS module chain reused)
  - `_duration_days()`
  - `_compute_is_baseline()`
  - `_scan_triggers()`
  - `_truncate_oos_result()`
  - `_run_adaptive_wfa()`

- Updated `run_wf_optimization()`:
  - Dispatches to `_run_adaptive_wfa()` when `adaptive_mode=True`.
  - Fixed mode behavior remains unchanged.

- Updated stitched WFE calculation:
  - Fixed mode: old formula preserved.
  - Adaptive mode: duration-weighted OOS annualization:
    - `annualized_is = mean(is_net_profit_pct) * (365 / is_period_days)`
    - `annualized_oos = (sum(oos_net_profit_pct) / sum(oos_actual_days)) * 365`
    - `wfe = annualized_oos / annualized_is * 100`


### 3.2 `src/core/storage.py`

- Added new `studies` columns:
  - `adaptive_mode`
  - `max_oos_period_days`
  - `min_oos_trades`
  - `check_interval_trades`
  - `cusum_threshold`
  - `dd_threshold_multiplier`
  - `inactivity_multiplier`

- Added new `wfa_windows` columns:
  - `trigger_type`
  - `cusum_final`
  - `cusum_threshold`
  - `dd_threshold`
  - `oos_actual_days` (`REAL`)

- Added backward-compatible schema migration paths via `ALTER TABLE ADD COLUMN`.
- Updated `save_wfa_study_to_db()`:
  - Persists adaptive settings into `studies`.
  - Persists per-window trigger metadata into `wfa_windows`.


### 3.3 API Layer

- `src/ui/server_routes_run.py`
  - Added request parsing for:
    - `wf_adaptive_mode`
    - `wf_max_oos_period_days`
    - `wf_min_oos_trades`
    - `wf_check_interval_trades`
    - `wf_cusum_threshold`
    - `wf_dd_threshold_multiplier`
    - `wf_inactivity_multiplier`
  - Added value clamping to agreed ranges:
    - `max_oos_period_days`: `30..365`
    - `min_oos_trades`: `2..50`
    - `check_interval_trades`: `1..20`
    - `cusum_threshold`: `1.0..20.0`
    - `dd_threshold_multiplier`: `1.0..5.0`
    - `inactivity_multiplier`: `2.0..20.0`
  - Passes adaptive config into `WFConfig`.
  - Persists adaptive settings in base template and `wfa` config block for `config_json` hydration.

- `src/ui/server_routes_data.py`
  - Extended WFA window details payload with adaptive trigger fields.


## 4. Frontend Implementation

### 4.1 Start Page

- `src/ui/templates/index.html`
  - Added Adaptive Re-Optimization section inside WFA settings.
  - Added fields for all adaptive parameters.
  - Set input constraints to agreed ranges.

- `src/ui/static/js/ui-handlers.js`
  - Added `toggleAdaptiveWFSettings()` and integrated with `toggleWFSettings()`.
  - Adaptive toggle disables classic fixed OOS-days input.
  - Sends all adaptive fields in `/api/walkforward` request.
  - Stores adaptive fields in optimization state (`ResultsState` handoff).

- `src/ui/static/js/main.js`
  - Initializes adaptive UI state on page load.


### 4.2 Results Page

- `src/ui/templates/results.html`
  - Added WFA sidebar fields for adaptive parameters.

- `src/ui/static/js/results-controller.js`
  - Hydrates adaptive WFA settings from both `study` columns and `config_json`.

- `src/ui/static/js/results-tables.js`
  - Displays adaptive settings in sidebar (with fallback support for camelCase/snake_case state keys).

- `src/ui/static/js/wfa-results-ui.js`
  - Enhanced window header rendering:
    - Shows actual OOS duration `(Nd)` from `oos_actual_days`.
    - Shows trigger badge from `trigger_type`.

- `src/ui/static/css/style.css`
  - Added trigger badge styles for:
    - `cusum`
    - `drawdown`
    - `inactivity`
    - `max_period`


## 5. Key Trigger Logic (Implemented)

- Closed trades only (`exit_time` required).
- Inactivity checks:
  - OOS start -> first trade
  - Between consecutive trades
  - Last trade -> OOS max end
  - Zero-trade OOS case
- Drawdown checked on every trade close (not gated by min trades).
- CUSUM updated on every trade close and checked only at checkpoints:
  - `closed_count >= min_oos_trades`
  - `(closed_count - min_oos_trades) % check_interval_trades == 0`
- Trigger precedence implemented as required:
  1. Inactivity
  2. Drawdown
  3. CUSUM
- Adaptive shift:
  - `next_is_start = current_is_start + (oos_actual_end - oos_start)`
  - Then normalized/aligned using index search.


## 6. Tests

### 6.1 New Tests

- Added `tests/test_adaptive_wfa.py`:
  - baseline edge cases (0 trades / 1 trade fallback)
  - trigger precedence (drawdown over CUSUM)
  - fractional-day inactivity behavior
  - inactivity between trades behavior
  - adaptive duration-weighted WFE

### 6.2 Updated Existing Tests

- Updated `tests/test_storage.py` to assert new schema columns in:
  - `studies`
  - `wfa_windows`

### 6.3 Executed Reference Test Suite

Command run:

```bash
py -3 -m pytest tests/test_adaptive_wfa.py tests/test_walkforward.py tests/test_storage.py tests/test_server.py
```

Result:

- `34 passed`
- `0 failed`
- `0 skipped` (for this run)


## 7. Deviations, Errors, and Risks

### Deviations from plan

- No architectural deviation from the clarified design.
- Internal implementation adds helper methods to keep adaptive logic explicit and maintainable.

### Errors encountered during implementation

- None in runtime logic after tests; final test suite passed.

### Residual risks / notes

- Adaptive OOS end timestamps are ultimately stored in date-form (`YYYY-MM-DD`) due existing storage formatting behavior (`_format_date`), which is pre-existing system behavior.
- Fixed and adaptive execution paths are both present; adaptive path reuses the same module-chain logic via shared helper.


## 8. Files Changed

- `src/core/walkforward_engine.py`
- `src/core/storage.py`
- `src/ui/server_routes_run.py`
- `src/ui/server_routes_data.py`
- `src/ui/templates/index.html`
- `src/ui/templates/results.html`
- `src/ui/static/js/ui-handlers.js`
- `src/ui/static/js/main.js`
- `src/ui/static/js/results-controller.js`
- `src/ui/static/js/results-tables.js`
- `src/ui/static/js/wfa-results-ui.js`
- `src/ui/static/css/style.css`
- `tests/test_adaptive_wfa.py` (new)
- `tests/test_storage.py`
