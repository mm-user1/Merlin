# CamelCase Optimization Pipeline Migration Report

## Overview
- Implemented the recommended Variant 1: unified camelCase flow derived from each strategy's `config.json`.
- Grid and Optuna optimizers now build parameter spaces directly from strategy metadata, eliminating manual snake_case ↔ camelCase maps.
- Walk-forward and API layers were aligned with the new camelCase pipeline to keep multi-strategy support consistent.

## Key Changes
1. **Parameter discovery**
   - Added `ParameterSpec` abstraction that reads strategy parameters (type, defaults, optimize rules) from `config.json` and respects user overrides for select options and ranges.
   - Strategy metadata is auto-loaded when missing, ensuring new strategies are immediately discoverable.

2. **Grid optimizer**
   - Parameter grids are generated in camelCase only; trailing MA lock logic now runs on unified select-option lists.
   - Worker execution passes camelCase payloads directly to strategies, while results remain in existing snake_case structures for exports/UI tables.

3. **Optuna optimizer**
   - Search space is built from `ParameterSpec` objects with automatic select-option intersections when `lock_trail_types` is enabled.
   - Trial preparation seeds fixed parameters from strategy defaults/overrides and samples only the parameters marked as optimizable in the strategy config.

4. **Server & walk-forward engine**
   - Optimization configs now carry `strategy_parameters` and `select_param_options` to keep the backend strategy-agnostic.
   - CSV export metadata and WFA templates use camelCase inputs, deriving fixed values without hard-coded maps.

## Testing
- Smoke grid optimization with all parameters fixed at defaults on sample dataset (`OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`): **pass** (1 combination evaluated, results produced). Output excerpt:
  - `Smoke optimization completed 1`
  - `First result net profit 203.23207586649744`

## Remaining Considerations
- Frontend consumers should prefer `select_param_options` and `strategy_parameters` from the API for future strategies; legacy `ma_types_*` keys remain in responses for backward compatibility.
- When adding new strategies, ensure their `config.json` includes accurate `optimize` blocks (min/max/step or options) so optimizers can auto-generate ranges.

## Readiness
All observed naming conflicts are removed, and both grid and Optuna paths now source parameters from strategy configs. The system is ready to onboard additional strategies without manual mapping updates.
