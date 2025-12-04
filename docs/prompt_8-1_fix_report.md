# Phase 8.1 Fix Report

## Summary of Fixes
- Resolved false error popups during strategy loading by validating responses, guarding config parsing, and isolating UI rendering errors.
- Restored MA type selection for S01 optimization with a dedicated selector panel that appears only for S01 strategies and feeds MA type choices into optimizer payloads and combination counts.
- Prevented S04 optimizations from using S01 MA types by scoping MA-type handling to S01 in both the frontend payload builder and backend optimization config, and by making MA sampling optional in the Optuna engine.

## Tests
- `pytest` (76 tests) – all passing. 【2c3d61†L1-L17】

## Notes / Errors
- No errors encountered during this fix phase.
