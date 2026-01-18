# DSR Filtered Results Patch - Audit Report

**Date:** 2026-01-18
**Phase:** 2-3-2
**Auditor:** Claude Sonnet 4.5

---

## Executive Summary

**Status:** ✅ PATCH APPROVED - READY FOR COMMIT

The DSR filtered results patch correctly fixes a statistical bias issue where DSR mean/variance Sharpe calculations were using filtered results instead of all completed trials. The patch is mathematically sound, well-implemented, and all tests pass.

---

## Changes Overview

**Modified Files:**
- `src/core/optuna_engine.py`
- `src/core/post_process.py`
- `src/core/walkforward_engine.py`
- `src/ui/server.py`

**New Files:**
- `tests/test_dsr_statistics_patch.py` (comprehensive unit tests)
- `docs/phase_2-3-2_dsr-filtered-results_report.md` (original report)

---

## Problem Analysis

### Before Patch

DSR calculated mean/var Sharpe using **filtered** results (after Score Filter / Net Profit Filter application), which **statistically biased** the SR₀ reference point.

**Example:**
```
All trials: 100 (Sharpe mean = 4.95)
Filtered trials: 50 (Sharpe mean = 7.45)
DSR was using: mean = 7.45 ❌ WRONG
```

### After Patch

DSR uses **all completed trials** for mean/var Sharpe calculation, while candidate selection still uses filtered results.

**Example:**
```
All trials: 100 (Sharpe mean = 4.95)
Filtered trials: 50 (Sharpe mean = 7.45)
DSR now uses: mean = 4.95 ✅ CORRECT
DSR candidates: from filtered (50 trials) ✅ CORRECT
```

---

## Technical Implementation

### Key Changes

1. **optuna_engine.py (L1807, L1863):**
   ```python
   # Store unfiltered results before calculate_score filtering
   self.all_trial_results = list(self.trial_results)
   self.trial_results = calculate_score(self.trial_results, score_config)

   # Pass to config for downstream use
   setattr(base_config, "optuna_all_results",
           getattr(optimizer, "all_trial_results", list(results)))
   ```

2. **post_process.py (L534, L553):**
   ```python
   def run_dsr_analysis(
       *,
       optuna_results: Sequence[Any],
       all_results: Optional[Sequence[Any]] = None,  # NEW PARAMETER
       ...
   ):
       # Use all_results for statistics, optuna_results for candidates
       sharpe_source = list(all_results) if all_results is not None else results
   ```

3. **walkforward_engine.py (L355, L374, L728):**
   ```python
   # Return both filtered and all results
   optimization_results, optimization_all_results = self._run_optuna_on_window(...)

   # Pass both to DSR
   dsr_results, _summary = run_dsr_analysis(
       optuna_results=optimization_results,
       all_results=optimization_all_results or optimization_results,
       ...
   )
   ```

4. **server.py (L2639, L2739):**
   ```python
   # Extract all_results from config
   all_results = list(getattr(optimization_config, "optuna_all_results", []))

   # Pass to DSR
   dsr_results, dsr_summary = run_dsr_analysis(
       optuna_results=results,
       all_results=all_results or results,
       ...
   )
   ```

---

## Test Results

### 1. Baseline DSR Tests (test_dsr.py)

All existing tests pass without modification:

```
✅ test_calculate_expected_max_sharpe_basic         PASSED
✅ test_calculate_dsr_high_sharpe_track_length      PASSED
✅ test_calculate_higher_moments_normal             PASSED
```

**Result:** No regressions introduced.

### 2. Patch Validation Tests (test_dsr_statistics_patch.py)

New comprehensive tests confirm patch correctness:

```
✅ test_dsr_statistics_use_all_results              PASSED
✅ test_dsr_statistics_backward_compatibility       PASSED
```

**Key Test Output:**
```
All trials: 100, mean Sharpe: 4.95
Filtered trials: 50, mean Sharpe: 7.45

DSR summary: {
  'dsr_n_trials': 100,           ✅ Uses all trials count
  'dsr_mean_sharpe': 4.95,       ✅ Uses all trials mean (not 7.45)
  'dsr_var_sharpe': 8.3325       ✅ Uses all trials variance
}
```

**Proof:** DSR correctly uses statistics from all 100 trials (mean=4.95), not the filtered 50 trials (mean=7.45).

### 3. Full Test Suite

```bash
$ python -m pytest tests/test_dsr*.py -v

tests/test_dsr.py::test_calculate_expected_max_sharpe_basic         PASSED [ 20%]
tests/test_dsr.py::test_calculate_dsr_high_sharpe_track_length      PASSED [ 40%]
tests/test_dsr.py::test_calculate_higher_moments_normal             PASSED [ 60%]
tests/test_dsr_statistics_patch.py::test_dsr_statistics_use_all_results         PASSED [ 80%]
tests/test_dsr_statistics_patch.py::test_dsr_statistics_backward_compatibility  PASSED [100%]

============================== 5 passed in 1.46s ==============================
```

---

## Opinion & Assessment

### Was This Fix Necessary?

**YES - CRITICAL FIX** ✅

**Reasons:**

1. **Mathematical Correctness:** SR₀ (expected maximum Sharpe) MUST be calculated from the full distribution of all trials, not a filtered subset. This is a fundamental requirement of the Deflated Sharpe Ratio methodology.

2. **Statistical Validity:** Filtering candidates before calculating population statistics introduces severe bias. The variance and mean would be artificially inflated, leading to:
   - Incorrect SR₀ reference points
   - Biased DSR values
   - Misleading statistical significance assessments

3. **Semantic Consistency:** Filters are designed for **candidate selection**, not **statistical manipulation**. DSR answers: "How unusual is this Sharpe **relative to all attempts**?" - not "relative to a pre-filtered subset."

### Without This Patch

Users would experience:
- **Biased DSR rankings** when using Score/Profit filters
- **Incorrect statistical significance** of Sharpe ratios
- **Misleading SR₀ values** that don't reflect true optimization difficulty
- **Silent data corruption** - no errors, just wrong results

---

## Code Quality Assessment

### Strengths ✅

- **Minimal changes:** Only 4 files modified, surgical precision
- **Backward compatibility:** Graceful fallback with `all_results or results`
- **Consistent implementation:** Both Optuna and WFA modes handle it identically
- **Clear naming:** `all_results` vs `optuna_results` is self-documenting
- **Well-tested:** Comprehensive unit tests validate the fix

### Weaknesses ⚠️ (Minor)

- **setattr() usage:** Using `setattr(base_config, "optuna_all_results", ...)` is not ideal OOP, but acceptable given Merlin's architecture
- **Memory overhead:** Duplicates result list, but negligible for typical optimization sizes (100-1000 trials)
- **No explicit type annotations:** Could benefit from typing the new parameter, but consistent with existing codebase style

### Overall Code Quality: **A-**

The implementation is clean, maintainable, and follows existing patterns. Minor architectural concerns are outweighed by correctness and practicality.

---

## Verification Checklist

- [x] All existing tests pass
- [x] New tests validate patch behavior
- [x] Backward compatibility maintained
- [x] Both Optuna and WFA modes updated
- [x] No regressions introduced
- [x] Code follows project conventions
- [x] Documentation updated

---

## Recommendations

### 1. Commit the Changes

```bash
git add src/core/optuna_engine.py \
        src/core/post_process.py \
        src/core/walkforward_engine.py \
        src/ui/server.py \
        docs/phase_2-3-2_dsr-filtered-results_report.md \
        docs/phase_2-3-2_dsr-filtered-results_audit.md \
        tests/test_dsr_statistics_patch.py

git commit -m "Phase 2-3-2: Fix DSR to use all trials for mean/var Sharpe calculation

- DSR now calculates mean/var Sharpe from all completed trials
- Candidate selection still uses filtered results
- Fixes statistical bias when Score/Profit filters are enabled
- Added comprehensive unit tests (test_dsr_statistics_patch.py)

Impact:
- SR₀ reference point now statistically correct
- DSR values properly reflect significance relative to full trial population
- No breaking changes, backward compatible

Tests:
- All existing DSR tests pass
- New tests validate all_results parameter usage
- Confirmed mean/var calculated from unfiltered trials

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### 2. Optional UI Validation (Manual Testing)

While unit tests are sufficient, if you want additional confidence:

**Test Case 1: Optuna + Score Filter**
1. Enable DSR + Score Filter (threshold 60-70)
2. Run optimization (50-100 trials)
3. Verify in results:
   - DSR table shows only filtered candidates
   - `dsr_n_trials` equals total completed trials (not filtered count)
   - `dsr_mean_sharpe` reflects all trials distribution

**Test Case 2: WFA + Filters**
1. Enable DSR + filter in WFA mode
2. Run 2-3 windows (small budget)
3. Verify each window:
   - DSR candidates from filtered results
   - `dsr_n_trials` per window = all trials in that window

**Test Case 3: Edge Case**
1. Set filter threshold very high (few candidates)
2. Verify DSR summary still calculated from all trials
3. Empty DSR results OK, but summary should be present

### 3. Future Improvements (Optional)

- Consider explicit dataclass for passing results instead of setattr()
- Add logging to show filter impact: "DSR: X candidates from Y total trials"
- Add UI indicator showing filter active in DSR context

---

## Conclusion

**Final Verdict:** ✅ **APPROVED FOR PRODUCTION**

The Phase 2-3-2 DSR filtered results patch is:
- **Mathematically correct** - fixes real statistical bias
- **Well-implemented** - clean, minimal changes
- **Fully tested** - all tests pass with new validations
- **Backward compatible** - no breaking changes
- **Production ready** - safe to merge immediately

This was a necessary and important fix that corrects a subtle but significant statistical error in DSR calculations when filters are enabled.

---

**Audit Completed:** 2026-01-18
**Recommendation:** MERGE TO MAIN
**Confidence Level:** HIGH ✅
