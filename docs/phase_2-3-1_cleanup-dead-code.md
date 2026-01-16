# Phase 2-3-1 Cleanup Plan: Dead/Duplicate Date Alignment Helpers

Date: 2026-01-16
Scope: Merlin codebase at `+Merlin/+Merlin-GH/`

## Goal
Reduce duplication and dead code introduced over time around date parsing and alignment. The objective is to make **one canonical alignment path** and remove redundant helpers once verification is complete. This is a **cleanup-only** plan (no behavioral changes intended).

---

## Why cleanup is needed
- Multiple helpers exist for the same logic (parsing timestamps, date-only alignment).
- Some are now redundant since `align_date_bounds()` is centralized in `core/backtest_engine.py`.
- Duplication increases maintenance risk and can cause future divergence.

---

## Scope of cleanup (proposed)

### 1) Remove duplicated alignment helper in WFA export (server.py)
**Current duplication**:
- `src/ui/server.py` contains a local helper for WFA export:
  - `_align_window_ts()` inside `download_wfa_trades()`.
- It replicates the same “date-only align to first/last bar” logic already centralized in `align_date_bounds()`.

**Plan**:
- Replace `_align_window_ts()` with a call to `align_date_bounds()`.
- This removes local logic and keeps one canonical implementation.

**Why**:
- One implementation reduces drift and simplifies future fixes.

**Estimated removal**: ~30–40 lines.

---

### 2) Remove redundant `_parse_timestamp()` in core modules
**Current duplication**:
- `src/core/optuna_engine.py` and `src/core/post_process.py` define their own `_parse_timestamp()` helpers.
- Most usages now route through `align_date_bounds()` or can safely do so.

**Plan**:
- Identify call sites still using these helpers.
- Replace with `align_date_bounds()` where appropriate.
- If no remaining uses, remove the local helper definitions.

**Why**:
- Simplifies the API: one canonical parse/alignment path.
- Eliminates dead code and reduces cognitive overhead.

**Estimated removal**: ~20–40 lines per file (depending on remaining usages).

---

### 3) Standardize server-side date parsing blocks
**Current duplication**:
- `src/ui/server.py` still contains multiple inline parsing blocks (some still using manual `pd.Timestamp` conversion).

**Plan**:
- Normalize all date parsing to go through `align_date_bounds()` when dealing with date-only ranges.
- Remove ad-hoc parsing blocks that have become redundant.

**Why**:
- Ensures uniform behavior across endpoints.
- Removes inconsistent manual parsing code.

**Estimated removal**: ~20–60 lines.

---

### 4) Documentation cleanup
**Current duplication**:
- Some docs/audit notes may still describe the old “end date at midnight” behavior.

**Plan**:
- Update internal docs if they describe date-only alignment incorrectly.
- Explicitly document that date-only bounds are aligned to dataset bars.

**Why**:
- Prevents future confusion or regressions.

**Estimated update**: 1–2 doc files; small edits.

---

## Safety checks before cleanup
- Confirm no functionality depends on old helpers.
- Ensure that any removal doesn’t break import cycles.
- Run a quick smoke test on:
  - Optuna run with date-only range
  - WFA export
  - Manual Test + FT export

---

## Expected outcome
- One canonical alignment function (`align_date_bounds`) used across the codebase.
- Less duplication, clearer maintenance path.
- No behavioral changes to date alignment.

---

## Estimated cleanup size
**Total**: ~120–220 lines removed/rewritten (rough estimate).

---

## Notes
This cleanup should be done in a **separate PR/patch** from functional fixes to keep risk low and reviewable.

---

End of plan.
