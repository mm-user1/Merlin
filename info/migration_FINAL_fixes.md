# Final Migration Fixes Prompt

## Objectives
Address all gaps identified in `migration_FINAL_report.md` so the project fully meets the target architecture, produces reference-equivalent results, and unlocks optimizer/WFA/test flows.

## Required Fixes
1. **Parameter optimization defaults**
   - In `src/strategies/s01_trailing_ma/config.json`, set `optimize.enabled: true` for all strategy-level parameters (e.g., `maType`, `maLength`, stop/trailing inputs). Only platform/global parameters may remain disabled.
2. **Strategy module autonomy**
   - Refactor `src/strategies/s01_trailing_ma/strategy.py` so `S01TrailingMA.run` parses incoming `params` explicitly, calls the calculation functions directly (not via the legacy wrapper), and returns a fully populated `StrategyResult`.
3. **Advanced metrics integration**
   - Ensure `run_strategy` (or its refactored equivalent) computes and propagates advanced metrics (Sharpe, Sortino, Calmar/ROMAD, win rate, trade consistency, exposure, etc.). Wire these into `StrategyResult`, serialization, and any API/optimizer consumers.
4. **Reference logic alignment**
   - Reconcile any logic or parameter handling discrepancies causing the reference backtest to deviate (profit/drawdown/trade count). Prioritize parity with Stage 5 expectations over legacy behaviors.
5. **Stage 3–7 completeness**
   - After the above fixes, validate optimizer endpoints (grid/Optuna), WFA, preset loading/saving, CSV export, and trade export pathways to ensure compatibility with the updated strategy result structure.

## Final Validation Test Suite
Perform the following end-to-end tests after implementing fixes. Use the same environment/configs intended for production. Record outputs (JSON/CSV artifacts and logs) for each test.

### Common Setup
- **Strategy:** S01 Trailing MA v26
- **CSV File:** `data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
- **Date Range:** start `2025-06-15 00:00`, end `2025-11-15 00:00`
- **Warmup Bars:** 1000
- **Parameters:**
  - MA Type: SMA
  - MA Length: 300
  - Close Count Long: 9
  - Close Count Short: 5
  - Stop Long ATR: 2.0
  - Stop Long RR: 3
  - Stop Long LP: 2
  - Stop Short ATR: 2.0
  - Stop Short RR: 3
  - Stop Short LP: 2
  - Stop Long Max %: 7.0
  - Stop Short Max %: 10.0
  - Stop Long Max Days: 5
  - Stop Short Max Days: 2
  - Trail RR Long: 1
  - Trail RR Short: 1
  - Trail MA Long Type: EMA
  - Trail MA Long Length: 90
  - Trail MA Long Offset: -0.5
  - Trail MA Short Type: EMA
  - Trail MA Short Length: 190
  - Trail MA Short Offset: 2.0
- **Expected KPIs (tolerance):** Net Profit 230.75% ±0.5%; Max Drawdown 20.03% ±0.5%; Total Trades 93 ±2.

### 1) Baseline Backtest
- **Goal:** Confirm strategy output matches expected KPIs and returns populated advanced metrics.
- **Method:** Run a single backtest via the primary engine interface using the common setup. Verify KPI tolerances and presence of advanced metrics (Sharpe/Sortino/Calmar, win rate, average trade, exposure, profit factor). Save result JSON and equity curve CSV.

### 2) Grid Search
- **Goal:** Verify grid optimizer respects `optimize.enabled` flags and can rank results using advanced metrics.
- **Method:**
  - Create a small grid varying `maType` (SMA/EMA) and `maLength` (280/300/320) plus `closeCountLong` (7/9) while keeping other params fixed.
  - Run grid search and confirm: all combinations execute without errors; best run by net profit and by Sharpe is reported; top result meets or exceeds baseline KPIs within tolerance.

### 3) Optuna Search
- **Goal:** Confirm stochastic optimization works with advanced metrics and new strategy API.
- **Method:**
  - Run Optuna with at least 20 trials optimizing net profit (or Sharpe if supported). Constrain parameter ranges around the baseline (e.g., maLength 250–350, closeCountLong 6–10, closeCountShort 4–7, trail offsets ±1).
  - Validate trials run to completion, best metrics are recorded, and exported study results include advanced metrics fields.

### 4) Walk-Forward Analysis (WFA)
- **Goal:** Ensure WFA pipeline integrates strategy outputs and metrics correctly.
- **Method:**
  - Configure at least 3 folds within the given date range with 1000-bar warmup per fold.
  - Verify each in-sample optimization uses advanced metrics, out-of-sample evaluation runs successfully, and aggregate WFA report summarizes KPIs per fold plus combined performance. Confirm no missing fields in CSV/JSON exports.

### 5) Preset Save/Load
- **Goal:** Confirm presets capture full parameter sets and reload correctly.
- **Method:** Save a preset from the baseline parameters, reload it, rerun the baseline backtest, and verify KPIs remain within tolerance and metadata (dates/warmup) persist.

### 6) CSV Export
- **Goal:** Validate backtest results and equity curve CSV outputs.
- **Method:** From a completed baseline backtest, export trades and equity curve to CSV. Confirm row counts match total trades and price bars (minus warmup), columns include PnL, position size, timestamps, and no missing advanced metric summaries in accompanying metadata.

### 7) Trade Export API/CLI
- **Goal:** Ensure trade export works in API and CLI flows.
- **Method:** Invoke trade export via both interfaces (if available) using the baseline run ID. Verify files contain all trades with correct side/entry/exit/fees/MA values and align with total trades KPI.

### 8) Regression Pack (Smoke)
- **Goal:** Guard against strategy/engine regressions.
- **Method:** Execute a minimal smoke suite: (a) baseline backtest, (b) one grid run, (c) 5-trial Optuna run, (d) single-fold WFA. All must complete without exceptions and produce non-empty outputs. Track runtime for performance regression comparison.

## Deliverables
- Updated code implementing fixes.
- Logs/JSON/CSV artifacts for all tests above, including KPI deltas vs. expectations.
- Short summary noting any residual deviations and proposed follow-ups.
