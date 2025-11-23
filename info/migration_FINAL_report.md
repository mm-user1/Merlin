# Final Migration Audit Report

## Overview
Comprehensive audit of the 7-stage migration identified multiple critical gaps preventing the system from meeting the target architecture and reference performance. Key findings are summarized below with detailed notes per phase.

## Phase 1: Migration Stage Verification

### Stage 1 – Config creation
- **Status:** ❌ Issues found
- **Findings:**
  - Parameter optimization flags do not follow the prompt. Strategy parameters like `maType` are shipped with `optimize.enabled: false` instead of true by default, while only platform parameters should be disabled for optimization.【F:src/strategies/s01_trailing_ma/config.json†L8-L29】

### Stage 2 – Strategy extraction & registry
- **Status:** ❌ Issues found
- **Findings:**
  - `S01TrailingMA.run` simply wraps `run_strategy` and does not extract parameters directly or compute advanced metrics as required. The stage prompt expected explicit parameter handling and advanced metric integration in the strategy module.【F:src/strategies/s01_trailing_ma/strategy.py†L14-L44】
  - `run_strategy` returns only basic metrics and never invokes `calculate_advanced_metrics`, so Sharpe/ROMAD/consistency/etc. are absent from results despite being defined in `StrategyResult`.【F:src/backtest_engine.py†L673-L740】【F:src/backtest_engine.py†L900-L940】【F:src/backtest_engine.py†L28-L71】【F:src/backtest_engine.py†L22-L40】

### Stages 3–7
- **Status:** ⚠️ Not fully validated
- **Findings:**
  - Server endpoints and optimizer wiring were inspected at a high level; however, due to earlier stage failures and failing reference test (see below), deeper checks were deferred. Further validation is required once Stage 1–2 issues are corrected.

## Phase 2: System Integration Testing

### Reference backtest (from Stage 5 prompt)
- **Input:** S01, SMA 300, closeCountLong=9, closeCountShort=5, warmup=1000, date filter 2025-06-15–2025-11-15, reference CSV.
- **Expected:** ~230.75% profit, ~20.03% max DD, 93 trades.
- **Observed:** 42.04% profit, 25.97% max DD, 98 trades (via direct engine call).【b58226†L1-L5】
- **Status:** ❌ Fails reference tolerance; indicates trading logic or parameter handling regression.

### Other integration tests (grid/Optuna/WFA/presets)
- **Status:** ⚠️ Not executed
- **Reason:** Baseline backtest already fails and advanced metrics are missing, making optimization scoring unreliable. These should be rerun after fixing core issues.

## Phase 3: Readiness for New Strategies
- Registry discovery works (S01 and S02 test strategy detected), but correctness depends on fixing `run` and metrics integration before adding further strategies.【b58226†L1-L5】

## Phase 4: Code Quality Audit
- Core concerns: missing advanced metric calculation in runtime path; strategy module delegates entirely to legacy function, reducing modularity required by new architecture.

## Phase 5: Performance Comparison
- Not assessed due to failing functional baseline.

## Conclusions
Migration is **incomplete and not ready**. Critical gaps in parameter optimization flags, advanced metric propagation, and backtest accuracy must be addressed before claiming completion. Integration tests beyond the baseline were not run because foundational functionality is failing.

## Recommendations (ordered)
1. Integrate advanced metric calculation into `run_strategy` and ensure `StrategyResult.to_dict()` exposes them for API/UI/optimizers. Update `S01TrailingMA.run` to call these metrics and to parse parameters directly per prompt.
2. Correct `config.json` optimization defaults so all strategy parameters (non-platform) have `optimize.enabled: true` by default.
3. Revalidate the reference backtest after fixes; only then run full grid/Optuna/WFA/preset test matrix from `migration_FINAL_audit.md`.
