# Phase 3-4-1 Fixes Report

Date: 2026-01-24

## Summary
This session focused on UI consistency and robustness for OOS/Manual Test comparison lines, enforcing a safe mutual-exclusion guard between OOS and WFA, and hardening OOS source selection when Stress Test runs but yields no OK candidates. The changes are intentionally small and targeted to maintain reliability and avoid unintended behavior changes.

## What Changed and Why (Chronological)
1. **OOS vs Manual Test comparison line alignment**: The OOS Comparison Line now mirrors the Manual Test Comparison Line metrics set (Profit Deg, Max DD, ROMAD, Sharpe, PF). This removes confusion and makes OOS interpretation consistent across tabs.
2. **Removed meaningless Rank from Manual Test Comparison Line**: Manual Test does not re-rank results, so rank change is always 0. Removing it reduces noise and potential misinterpretation.
3. **Mutual exclusion guard for OOS and WFA**: When OOS is enabled, WFA is disabled (and vice versa). This prevents unsupported simultaneous operation and clarifies user intent without auto-unchecking. The disabled label text is greyed for clearer UX.
4. **OOS source selection fix for Stress Test failures**: If Stress Test ran but produced no OK candidates, the OOS source remains "stress_test" and the OOS stage now fails clearly ("Stress Test produced no OK candidates; OOS Test skipped.") instead of silently falling back to earlier stages. This preserves "last finished module" semantics and avoids unintended source changes.
5. **Safer OOS source rank fallback**: If a source rank is missing, it now falls back to candidate index to avoid sorting artifacts.
6. **Test updates**: Adjusted OOS selection tests to cover the new Stress Test behavior, and reran the full test suite.

## Files Modified
- `src/ui/static/js/results.js`
  - OOS Comparison Line now shows Profit Deg, Max DD, ROMAD, Sharpe, PF (matching Manual Test).
  - Manual Test Comparison Line removes Rank.
  - OOS base metrics selection now respects FT vs non-FT sources to calculate comparison deltas correctly.
- `src/ui/static/js/oos-test-ui.js`
  - Added OOS/WFA mutual-disable guard and label greying.
  - OOS config payload treats disabled (guarded) checkbox as inactive.
- `src/ui/static/js/ui-handlers.js`
  - WFA settings are hidden when disabled by guard.
  - WFA enabled state respects disabled status to avoid conflicting payloads.
- `src/ui/templates/index.html`
  - Added label IDs for OOS/WFA to support greying behavior.
- `src/core/testing.py`
  - `select_oos_source_candidates` now takes `st_ran` and returns `stress_test` even with 0 OK candidates when Stress Test ran.
- `src/ui/server.py`
  - Passes `st_ran` into OOS selection.
  - Explicit error when Stress Test ran but no OK candidates.
  - OOS source rank fallback uses candidate index.
- `tests/test_oos_selection.py`
  - Updated expectations for the Stress Test no-OK-candidates path.

## Tests
- Full suite: `python -m pytest -v tests\`
  - **Result**: 142 passed
  - **Warnings**: 3 Optuna `ExperimentalWarning` (multivariate argument)

## Notes
- No DB migration functions were introduced in this session.
- The OOS source selection fix follows the “last finished module” rule even when that module yields no OK candidates, and now surfaces a clear user-facing error instead of silently switching sources.
