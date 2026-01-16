# Phase 2-2: Fix Post Process Rank Comparison Logic

## Problem Statement

The **Rank comparison** displayed in the **Comparison Line** (below the equity chart) for Post Process modules (DSR, Forward Test, Stress Test) is **incorrect**. All modules currently compare their rank against **Optuna IS results**, but they should compare against the **previous module in the chain**.

### Severity

**High** - This misrepresents the actual value provided by each Post Process module, making it impossible to understand how each module reorders the parameter sets.

---

## Required Behavior (Post Process Chain Logic)

### Core Principle

Post Process modules form a **processing chain**: **DSR → Forward Test → Stress Test**

Each module:
1. **Takes top-K candidates from the previous module's ranking** (or Optuna IS if it's the first module)
2. **Uses metrics and data from Optuna IS** (doesn't recalculate previous module)
3. **Processes using its own algorithm** (DSR probability, OOS testing, parameter perturbations)
4. **Re-ranks results** by its own metric (DSR probability, Profit Degradation, Profit Retention)
5. **Rank change shows position change vs PREVIOUS module**, not vs Optuna

---

### Detailed Module Chain

#### 1. **DSR (Deflated Sharpe Ratio)**
- **Source**: Optuna IS results (top-K by Optuna ranking)
- **Processing**: Recalculates DSR probability using same IS data
- **Ranking**: By DSR probability (descending)
- **Rank change**: `Optuna Rank - DSR Rank`
- **Correct** ✓ (first module, should compare with Optuna)

#### 2. **Forward Test (FT)**
- **Source**:
  - DSR results (top-K) if DSR was enabled
  - Optuna IS results (top-K) if DSR was not enabled
- **Processing**: Tests on OOS period, calculates Profit Degradation
- **Ranking**: By Profit Degradation or FT RoMaD
- **Rank change**:
  - `DSR Rank - FT Rank` (if DSR was enabled) ← **INCORRECT NOW**
  - `Optuna Rank - FT Rank` (if DSR was not enabled) ← Correct ✓

#### 3. **Stress Test (ST)**
- **Source**:
  - FT results (top-K) if FT was enabled
  - DSR results (top-K) if DSR was enabled but FT was not
  - Optuna IS results (top-K) if neither DSR nor FT were enabled
- **Processing**: Parameter perturbations (OAT), calculates Retention metrics
- **Ranking**: By Profit Retention or RoMaD Retention
- **Rank change**:
  - `FT Rank - ST Rank` (if FT was enabled) ← **INCORRECT NOW**
  - `DSR Rank - ST Rank` (if DSR was enabled but FT was not) ← **INCORRECT NOW**
  - `Optuna Rank - ST Rank` (if neither DSR nor FT were enabled) ← Correct ✓

#### 4. **Manual Test**
- **Does NOT re-rank**
- Preserves sort order from source table
- Shows Comparison Line metrics but **NO Rank change**

---

## Current (Incorrect) Behavior

### Frontend Always Compares with Optuna

**File**: `src/ui/static/js/results.js`

All three module renderers build the same `optunaRankMap`:

```javascript
// Line 867-871 (Forward Test)
// Line 958-962 (DSR)
// Line 1029-1033 (Stress Test)

const optunaRankMap = {};
(ResultsState.results || []).forEach((trial, idx) => {
  if (trial.trial_number !== undefined) {
    optunaRankMap[trial.trial_number] = idx + 1;  // ALWAYS Optuna position!
  }
});
```

Then each module calculates rank change vs Optuna:

```javascript
// Forward Test (line 917)
const rankChange = optunaRank - trial.ft_rank;  // ✗ Should use DSR rank if DSR enabled

// DSR (line 990)
const rankDelta = optunaRank - dsrRank;  // ✓ Correct (first module)

// Stress Test (line 1066)
const rankDelta = optunaRank - stRank;  // ✗ Should use FT/DSR rank if enabled
```

**Problem**: Frontend doesn't know which module was the source for the current module.

---

### Backend Issues

#### Issue 1: Forward Test uses misleading variable name

**File**: `src/core/post_process.py:739-827`

```python
def run_forward_test(..., optuna_results: Sequence[Any], ...):
    candidates = list(optuna_results or [])  # May actually be DSR results!

    for idx, result in enumerate(candidates[:top_k], 1):
        tasks.append({
            "optuna_rank": idx,  # ✗ Misleading! This is DSR rank if candidates=dsr_results
            ...
        })

    # Later (line 827)
    result.rank_change = result.optuna_rank - idx  # ✗ Wrong if DSR enabled
```

**Issue**: Variable named `optuna_rank` but actually holds position in `candidates`, which may be DSR results.

#### Issue 2: No source tracking in database

**File**: `src/core/storage.py` - `trials` table schema

Missing fields:
- `ft_source` (where FT got candidates: "optuna" or "dsr")
- `st_source` (where ST got candidates: "optuna", "dsr", or "ft")

Without this information, frontend cannot determine which module to compare against.

#### Issue 3: Stress Test rank_change is correct in backend but ignored by frontend

**File**: `src/core/post_process.py:1449`

```python
result.rank_change = result.source_rank - idx
# where source_rank comes from enumerate(candidates, 1)
# candidates can be FT/DSR/Optuna results ✓
```

Backend **correctly** calculates `rank_change` based on source rank, but:
1. This value is saved to database
2. Frontend **ignores** it and recalculates using `optunaRank`

---

## Real Data Example

From study: `S01_OKX_LINKUSDT.P, 15 2025.06.15-2025.09.15_OPT`
Configuration: DSR enabled, FT enabled, ST enabled

### Trial 38 (showing the problem)

```
Optuna Rank: 5  (by RoMaD desc)
DSR Rank: 3     (by DSR probability)
FT Rank: 3      (by Profit Degradation)
ST Rank: 1      (by Profit Retention)
```

#### Current (Incorrect) Display:

**Forward Test tab** - Comparison Line shows:
```
Rank: +2 | DSR: 0.832 | Luck: 71.2%
```
Calculation: `optunaRank - ft_rank = 5 - 3 = +2`

**Stress Test tab** - Comparison Line shows:
```
Rank: +4 | Profit Ret: 0.95 | RoMaD Ret: 0.89
```
Calculation: `optunaRank - st_rank = 5 - 1 = +4`

#### Required (Correct) Display:

**Forward Test tab** - Should show:
```
Rank: 0 | DSR: 0.832 | Luck: 71.2%
```
Calculation: `dsrRank - ft_rank = 3 - 3 = 0`

**Stress Test tab** - Should show:
```
Rank: +2 | Profit Ret: 0.95 | RoMaD Ret: 0.89
```
Calculation: `ftRank - st_rank = 3 - 1 = +2`

---

### Another Example: Trial 15

```
Optuna Rank: 18
DSR Rank: 1     (huge improvement!)
FT Rank: 2      (slight drop)
ST Rank: 4      (drop again)
```

#### Current Display:
- FT Rank change: `18 - 2 = +16` (looks amazing)
- ST Rank change: `18 - 4 = +14` (looks amazing)

#### Required Display:
- FT Rank change: `1 - 2 = -1` (slight drop from DSR)
- ST Rank change: `2 - 4 = -2` (drop from FT)

**Impact**: Current display hides that Trial 15 is **degrading** through the pipeline, making it look like it's improving!

---

## Why This Is Wrong

### 1. **Misrepresents Module Value**

The purpose of each Post Process module is to **refine** the ranking from the previous step. Users need to see:
- "Did DSR find something Optuna missed?" (DSR vs Optuna)
- "Did Forward Test validate DSR's top picks?" (FT vs DSR)
- "Did Stress Test confirm FT's robustness?" (ST vs FT)

Current behavior only shows: "How does each module compare to Optuna?"

### 2. **Hides Parameter Set Degradation**

A parameter set may:
- Rank #1 in DSR
- Drop to #5 in FT (fails OOS validation)
- Drop to #10 in ST (fails robustness test)

**Current display**: Shows Rank +X for all modules (comparing to Optuna rank #30)
**User perception**: "This set is improving!"
**Reality**: Set is degrading through the pipeline

### 3. **Breaks Chain Logic**

Post Process is designed as a **funnel/filter chain**:
```
Optuna IS (100 trials)
    ↓
DSR (top 20) → re-ranks → outputs 20 ranked sets
    ↓
FT (top 20 from DSR) → re-ranks → outputs 20 ranked sets
    ↓
ST (top 5 from FT) → re-ranks → outputs 5 ranked sets
```

Each module should show **incremental value** vs previous step, not absolute value vs Optuna.

---

## Code Locations

### Frontend (JavaScript)

**File**: `src/ui/static/js/results.js`

1. **Forward Test table renderer**: Lines 867-930
   - Build rank map: Lines 867-872
   - Calculate rank change: Line 917
   - Set comparison line: Line 928

2. **DSR table renderer**: Lines 958-1006
   - Build rank map: Lines 958-963
   - Calculate rank delta: Line 990
   - Set comparison line: Line 1003

3. **Stress Test table renderer**: Lines 1029-1113
   - Build rank map: Lines 1029-1034
   - Calculate rank delta: Line 1066
   - Set comparison line: Line 1112

### Backend (Python)

**File**: `src/core/post_process.py`

1. **FTResult dataclass**: Lines 63-98
   - `optuna_rank` field (line 67) - misleading name
   - `rank_change` field (line 97)

2. **run_forward_test()**: Lines 721-829
   - `candidates` assignment (line 739) - may be DSR results
   - Task building (lines 746-756) - sets `optuna_rank`
   - Rank change calculation (line 827)

3. **DSRResult dataclass**: Lines 100-115
   - Has `optuna_rank` (line 105)
   - **Missing** `rank_change` field (calculated in frontend)

4. **StressTestResult dataclass**: Lines 163-206
   - `source_rank` field (line 173) - correct name!
   - `rank_change` field (line 205)

5. **run_stress_test()**: Lines 1280-1492
   - `source_rank` assignment (line 1303) - correct!
   - Rank change calculation (line 1449) - correct!

**File**: `src/ui/server.py`

6. **Optimization endpoint**: Lines 2632-2716
   - DSR candidates selection (line 2632-2634) - correct
   - FT candidates selection (line 2632-2634) - correct
   - ST candidates selection (lines 2694-2698) - correct

**File**: `src/core/storage.py`

7. **Database schema**: Lines 67-180 (`_create_schema()`)
   - `trials` table definition
   - Missing: `ft_source`, `st_source` columns

8. **save_forward_test_results()**: Lines 1119-1215
   - Saves FT metrics to trials table
   - Should also save `ft_source`

9. **save_stress_test_results()**: Lines 1312-1406
   - Saves ST metrics to trials table
   - Should also save `st_source`

10. **load_study_from_db()**: Lines 907-1056
    - Loads trials and builds trial list
    - Should pass source info to frontend

---

## Required Changes

### 1. Database Schema Changes

**File**: `src/core/storage.py`

Add columns to `trials` table:
```sql
ALTER TABLE trials ADD COLUMN ft_source TEXT;  -- 'optuna' or 'dsr'
ALTER TABLE trials ADD COLUMN st_source TEXT;  -- 'optuna', 'dsr', or 'ft'
```

### 2. Backend: Track Source Module

**File**: `src/ui/server.py` - Optimization endpoint

When calling `run_forward_test()`:
```python
ft_source = "dsr" if dsr_results else "optuna"
```

When calling `run_stress_test()`:
```python
if ft_enabled and ft_results:
    st_source = "ft"
elif dsr_results:
    st_source = "dsr"
else:
    st_source = "optuna"
```

**File**: `src/core/storage.py`

- `save_forward_test_results()`: Add `ft_source` parameter and save to DB
- `save_stress_test_results()`: Add `st_source` parameter and save to DB

### 3. Backend: Fix Variable Naming

**File**: `src/core/post_process.py`

Rename `optuna_rank` → `source_rank` in:
- `FTResult` dataclass (line 67)
- `run_forward_test()` function (line 751, 818, 827)

This makes it clear that rank comes from source (Optuna or DSR), not always Optuna.

### 4. Frontend: Use Source-Aware Rank Maps

**File**: `src/ui/static/js/results.js`

#### For Forward Test (lines 867-930):

```javascript
// Build rank map from CORRECT source
let sourceRankMap = {};
const ftSource = (ResultsState.study?.ft_source || 'optuna');

if (ftSource === 'dsr') {
  // Build map from DSR results (sorted by dsr_rank)
  const dsrResults = [...ResultsState.results]
    .filter(t => t.dsr_rank != null)
    .sort((a, b) => a.dsr_rank - b.dsr_rank);

  dsrResults.forEach((trial, idx) => {
    sourceRankMap[trial.trial_number] = trial.dsr_rank;
  });
} else {
  // Build map from Optuna results
  ResultsState.results.forEach((trial, idx) => {
    sourceRankMap[trial.trial_number] = idx + 1;
  });
}

// Calculate rank change
const sourceRank = sourceRankMap[trialNumber];
const rankChange = sourceRank != null && trial.ft_rank != null
  ? sourceRank - trial.ft_rank
  : null;
```

#### For Stress Test (lines 1029-1113):

```javascript
// Build rank map from CORRECT source
let sourceRankMap = {};
const stSource = (ResultsState.study?.st_source || 'optuna');

if (stSource === 'ft') {
  // Build map from FT results (sorted by ft_rank)
  const ftResults = [...ResultsState.results]
    .filter(t => t.ft_rank != null)
    .sort((a, b) => a.ft_rank - b.ft_rank);

  ftResults.forEach((trial, idx) => {
    sourceRankMap[trial.trial_number] = trial.ft_rank;
  });
} else if (stSource === 'dsr') {
  // Build map from DSR results (sorted by dsr_rank)
  const dsrResults = [...ResultsState.results]
    .filter(t => t.dsr_rank != null)
    .sort((a, b) => a.dsr_rank - b.dsr_rank);

  dsrResults.forEach((trial, idx) => {
    sourceRankMap[trial.trial_number] = trial.dsr_rank;
  });
} else {
  // Build map from Optuna results
  ResultsState.results.forEach((trial, idx) => {
    sourceRankMap[trial.trial_number] = idx + 1;
  });
}

// Calculate rank change
const sourceRank = sourceRankMap[trialNumber];
const rankDelta = sourceRank != null && trial.st_rank != null
  ? sourceRank - trial.st_rank
  : null;
```

#### DSR remains unchanged (lines 958-1006)
DSR always compares with Optuna, so current implementation is correct.

### 5. Database Migration

For existing studies in database, set default values:
```sql
UPDATE trials SET ft_source = 'optuna' WHERE ft_rank IS NOT NULL AND ft_source IS NULL;
UPDATE trials SET st_source = 'optuna' WHERE st_rank IS NOT NULL AND st_source IS NULL;
```

This assumes old studies didn't use chained modules (safe assumption for Merlin v1.1.0).

---

## Testing Strategy

### Test Case 1: DSR → FT → ST Chain

**Setup**: Run Optuna with all three Post Process modules enabled

**Verification**:
1. Check database: `ft_source` should be 'dsr', `st_source` should be 'ft'
2. Pick a trial that moved significantly (e.g., Optuna #18 → DSR #1 → FT #2 → ST #4)
3. **Forward Test tab**: Rank should show `-1` (DSR 1 → FT 2)
4. **Stress Test tab**: Rank should show `-2` (FT 2 → ST 4)

### Test Case 2: FT Only (no DSR)

**Setup**: Run Optuna with only FT enabled (DSR disabled)

**Verification**:
1. Check database: `ft_source` should be 'optuna', `st_source` should be NULL
2. **Forward Test tab**: Rank should compare with Optuna rank

### Test Case 3: ST Only (no DSR, no FT)

**Setup**: Run Optuna with only ST enabled

**Verification**:
1. Check database: `st_source` should be 'optuna'
2. **Stress Test tab**: Rank should compare with Optuna rank

### Test Case 4: WFA with Post Process

**Setup**: Run WFA with DSR/FT/ST enabled

**Verification**: Same logic should apply for each window's IS optimization

---

## Additional Considerations

### Manual Test
Manual Test does **NOT** re-rank, so it should **NOT** show rank change in Comparison Line. Current behavior may already be correct, but verify.

### WFA Post Process
The same chain logic applies to WFA. Each window's IS optimization can have Post Process modules, and they should chain the same way.

### UI Label Clarity
Consider adding source info to Comparison Line:
```
Rank: +2 (vs DSR) | Profit Deg: 0.89 | ...
```
or
```
Rank: +2 (vs FT) | Profit Ret: 0.95 | ...
```

This makes it explicit what the rank change is comparing against.

---

## Success Criteria

1. ✅ Database stores `ft_source` and `st_source` for each trial
2. ✅ Backend correctly identifies and stores source module
3. ✅ Frontend builds rank maps from correct source module
4. ✅ Rank changes accurately reflect position change vs previous module
5. ✅ Real data examples (like Trial 38) show correct rank changes
6. ✅ All test cases pass
7. ✅ Existing studies with old data still display (using 'optuna' as default source)

---

## References

- Post Process module: `src/core/post_process.py`
- Storage layer: `src/core/storage.py`
- Results UI: `src/ui/static/js/results.js`
- Server endpoint: `src/ui/server.py:2580-2716` (optimize endpoint)
- Database: `src/storage/studies.db`
