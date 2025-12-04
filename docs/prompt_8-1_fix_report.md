# Phase 8.1 Fix Report

## Summary of Fixes
- Fixed optimizer form rendering errors by lifting MA helper utilities to the global scope so strategy switches no longer trigger missing-function alerts.
- Ensured S01 MA-type selectors appear and collect payload data by wiring the selectors to strategy detection without crashing non-S01 strategies.
- Corrected optimization payload assembly to use dynamically generated backtest parameters for all strategies, preventing S04 runs from inheriting S01-specific fields while still supporting S01 MA combinations.

## Tests
- `pytest` (76 tests) – all passing. 【a62b48†L1-L14】

## Notes / Errors
- No errors encountered during this fix phase.
