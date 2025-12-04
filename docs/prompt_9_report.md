# Phase 9 Report

## Summary
- Promoted the migrated S01 implementation by removing the legacy folder, renaming the package to `s01_trailing_ma`, and aligning its config/class metadata and dependent scripts/tests with the new identifiers.
- Removed the legacy `StrategyParams`/`run_strategy` workflow from `core.backtest_engine`, while keeping shared dataclasses and indicator helpers available for compatibility, and updated tooling/tests to use the strategy-owned `S01Params` runner.
- Hardened backend strategy handling (server, optuna, walk-forward) to require explicit strategy IDs or fall back to the first available strategy; cleaned optimizer defaults and dynamic warmup handling accordingly.
- Updated the UI to eliminate hardcoded S01 fallbacks (forms now require a selected strategy) and refreshed the page title; documentation now reflects the promoted S01 location and current migration phase.

## Reference Tests
- `python -c "import sys; sys.path.insert(0, 'src'); from strategies import list_strategies; print([s['id'] for s in list_strategies()])"`
- `pytest tests -v` (uses `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`)

## Notes
- When no strategy is supplied in API requests, the server now selects the first discovered strategy and returns an explicit error only if none are registered.
