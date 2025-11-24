# TODO Optimizer Snake Case Fix - Report

## Summary of Changes
- Added strategy-level camelCase to snake_case conversion helpers and automatic parameter mapping generation from `config.json`.
- Refactored grid and Optuna optimizers to build parameter maps from strategy configs and pass mappings to worker processes, removing hardcoded S01-specific mappings.
- Ensured strategy registry attaches configs to strategy classes for mapping generation.

## Reference Tests
- `python -m compileall src` (syntax validation) – passed.
- Minimal grid optimization run using `data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv` with all parameters fixed to defaults and single MA type combination – completed successfully (1 combination, top net profit 68.57%).

## Notes
- Implemented the refactor as described in the prompt; no deviations from the requested approach were required.
