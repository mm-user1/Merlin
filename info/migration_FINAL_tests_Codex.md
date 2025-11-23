# Migration Audit & Final Test Report (Codex)

## Audit Summary
- Verified advanced metrics defect (Issue 2 from assessment) is resolved: `StrategyResult` now persists equity curve/timestamps alongside Sharpe, profit factor, RoMaD, ulcer index, recovery factor, and consistency metrics, enabling exports and optimizer scoring.【F:src/backtest_engine.py†L45-L100】【F:src/backtest_engine.py†L1014-L1040】
- Confirmed strategy run path exercises `calculate_advanced_metrics` and surfaces values to optimizer flows; no regressions observed in reference tolerance tests (`test_reference.py`, `test_metrics_populated.py`).【746f9a†L1-L20】【ff0de1†L1-L25】

## Test Matrix
- Baseline backtest (production params/warmup 1000): PASS. Net Profit 230.75% (Δ 0%), Max DD 20.03% (Δ 0%), Trades 93; advanced metrics populated. Artifacts: `info/test_outputs/baseline_result.json`, `baseline_equity_curve.csv`, `baseline_trades.csv`.【F:info/test_outputs/baseline_result.json†L1-L49】【7c4e2f†L1-L5】
- Grid search (maType SMA/EMA; maLength 280/300/320; closeCountLong 7/9): PASS. 12/12 combos executed, best by net profit & Sharpe = SMA/280/CCL7. Results exported to `info/test_outputs/grid_results.json|csv`.【b52ae0†L1-L4】【F:info/test_outputs/grid_results.json†L1-L46】
- Optuna search (20 trials, net_profit target, constrained ranges): PASS. Trials completed without pruning; best net profit 68.57%. Exported `info/test_outputs/optuna_results.json|csv`.【a3489b†L1-L5】【F:info/test_outputs/optuna_results.json†L1-L18】
- Walk-Forward Analysis (3 folds, warmup 1000): PASS. IS/OOS folds executed with Optuna per fold, forward test completed; summary CSV/JSON generated (`wfa_summary.csv|json`).【139d79†L1-L33】【F:info/test_outputs/wfa_summary.json†L1-L22】
- Preset save/load: PASS. Baseline params saved to `baseline_preset.json`, reload backtest matched reference KPIs (230.75%/20.03%/93). Artifact `preset_reload_result.json`.【00a95e†L1-L3】【F:info/test_outputs/preset_reload_result.json†L1-L6】
- CSV exports: PASS. Baseline equity/trade CSVs generated; trade rows = total trades, equity rows = bars incl. warmup (warmup idx 1000).【F:info/test_outputs/baseline_result.json†L2-L50】
- Trade export API/CLI: PASS via programmatic export using `StrategyResult.trades` to CSV (see `baseline_trades.csv`).【7c4e2f†L1-L5】
- Regression smoke (baseline, grid, Optuna 20-trial, WFA 3-fold): PASS. All flows completed without exceptions.

## Notes & Follow-ups
- Optuna/WFA logs show repeated identical objective values due to narrow search space; consider broadening ranges if further exploration is required.
- Performance warnings from Optuna (`multivariate`, `constant_liar`) are expected experimental notices; no action needed currently.
