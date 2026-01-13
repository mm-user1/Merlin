# Phase 2: DSR (Deflated Sharpe Ratio) Post Process Module Implementation Plan (v1.2.1)

## Overview

This document outlines the implementation plan for adding DSR (Deflated Sharpe Ratio) to Merlin's Post Process module. DSR is a statistical correction for Sharpe ratio that accounts for selection bias (multiple testing), non-normal returns, and track record length.

**Author:** Claude Opus 4.5 (updated by GPT-5.2)
**Version:** 1.2.1
**Date:** 2026-01-12
**Updated:** v1.2.1 - Incorporated implementation clarifications, removed dsr.py module, clarified FT chaining, clarified trial count/variance source, fixed kurtosis test expectation, DSR tab label, explicit re-run for higher moments, and SciPy dependency.

---

## Key Design Decisions (Quick Reference)

| Decision | Choice |
|----------|--------|
| DSR module location | **Use existing modules**: `post_process.py` + `metrics.py` (no new dsr.py) |
| DSR Table Structure | **Same as Optuna table** (same columns, same metrics) |
| DSR-specific display | **Equity chart info line only**: Rank Change, DSR, Luck Share% |
| Sorting criterion | **DSR probability only** (highest first) |
| Luck Share purpose | **Informational only** (not used for sorting) |
| Pipeline with FT | **DSR re-ranks first** - FT uses DSR top-K as input |
| Kurtosis definition | **Raw kurtosis** = E[z^4] (NOT excess kurtosis) |
| DSR meaning | **P(SR > SR0)** - probability SR exceeds selection-bias threshold |
| SR0 null hypothesis | **mu = 0** (assumes no skill under null) |
| Effective trials | **Use N_eff if available**, else completed trials |
| Higher-moment data | **Re-run top-K IS** to compute skew/kurtosis + track length |
| SciPy | **Add to requirements.txt** (use scipy.stats.norm for CDF/PPF) |

---

## 1. Feature Summary

### 1.1 What is DSR?

DSR (Deflated Sharpe Ratio) corrects for two leading sources of performance inflation:
1. **Selection bias under multiple testing** - When running many trials and selecting the best, the reported Sharpe is inflated
2. **Non-normal returns** - Skewness and kurtosis affect the statistical significance of Sharpe

**DSR = P(SR > SR0)** - the probability that the observed Sharpe ratio exceeds SR0, where SR0 is the expected maximum Sharpe you'd see from N (or N_eff) random (zero-skill) trials due to selection bias alone.

- **DSR close to 1.0**: Strong evidence the strategy has genuine skill beyond luck
- **DSR close to 0.5**: The observed Sharpe is roughly what you'd expect from random chance
- **DSR close to 0.0**: The observed Sharpe is actually worse than expected from luck (suspicious)

### 1.2 User-Facing Behavior

**Start Page (index.html):**
- New "Enable DSR" checkbox in Post Process section (above Forward Test)
- Input for "Top Candidates" (default: 20)
- Independent toggle - can be enabled with or without Forward Test

**Results Page (results.html):**
- New "DSR" tab between "Top Parameter Sets" and "Forward Test"
- **DSR table = Same structure as Optuna table**, just:
  - Trimmed to DSR Top-K candidates
  - Re-ranked by DSR probability (highest first)
  - Same columns, same metrics display
- **Equity chart info line** (bottom of chart) shows DSR-specific metrics:
  - Rank Change (e.g., "Optuna #5 -> DSR #1")
  - DSR Value (probability 0-1)
  - Luck Share % (what portion of observed Sharpe is attributable to selection bias)

### 1.3 Pipeline Logic

| Configuration | Pipeline Flow |
|---------------|---------------|
| DSR only | Optuna -> DSR tab |
| FT only | Optuna -> FT tab (current behavior) |
| DSR + FT | Optuna -> DSR tab -> FT tab (FT uses DSR top-K as input) |

**Critical**: When both DSR and FT are enabled, Forward Test operates on DSR's re-ranked top candidates, not Optuna's original ranking.

### 1.4 WFA Pipeline Integration

Post Process is a **ranking module** that can apply in one or multiple steps before WFA OOS testing.

**WFA + DSR + FT (two-step Post Process):**
1. WFA IS Optuna (IS period reduced by FT period)
2. DSR re-rank on top-K
3. FT re-rank on top-K (by selected FT metric)
4. WFA OOS test (repeat per window)

**WFA + DSR only (one-step Post Process):**
1. WFA IS Optuna (full IS period)
2. DSR re-rank on top-K
3. WFA OOS test (repeat per window)

---

## 2. Technical Analysis

### 2.1 DSR Formula (Bailey & Lopez de Prado)

```python
# Expected Maximum Sharpe Ratio (under null hypothesis mu=0)
SR0 = 0 + sqrt(var_sr) * ((1 - gamma) * norm.ppf(1 - 1/n_trials)
                          + gamma * norm.ppf(1 - 1/(n_trials * e)))

# DSR probability: P(SR > SR0)
DSR = norm.cdf(((SR - SR0) * sqrt(T - 1)) /
               sqrt(1 - skew * SR + ((kurtosis - 1) / 4) * SR**2))
```

Where:
- `SR` = observed Sharpe ratio (unannualized)
- `SR0` = expected max Sharpe under null (no skill)
- `n_trials` = number of independent trials tested (N or N_eff)
- `T` = number of return observations (track record length)
- `skew` = return skewness (3rd standardized moment)
- `kurtosis` = return **raw kurtosis** (4th standardized moment, E[z^4]) **NOT excess kurtosis**
  - Normal distribution: kurtosis = 3
  - Excess kurtosis = kurtosis - 3 (we do NOT use this)
- `gamma` = Euler-Mascheroni constant (0.5772156649...)
- `e` = Euler's number (2.718...)
- `var_sr` = variance of Sharpe ratios across all completed trials

**Critical**: The formula uses **raw kurtosis**, not excess kurtosis. For normal returns, kurtosis = 3, so `(kurtosis - 1)/4 = 0.5`.

### 2.2 Required Inputs for DSR Calculation

| Input | Source | Notes |
|-------|--------|-------|
| Sharpe Ratio (SR) | `trial.sharpe_ratio` | Already calculated in metrics.py (monthly, unannualized) |
| Number of trials (N) | `optuna_summary.completed_trials` | Use completed trial count from Optuna summary, not filtered results |
| Track record length (T) | Derived from timestamps | Number of monthly returns |
| Skewness | Re-run top-K IS | 3rd standardized moment of **excess monthly returns** |
| Raw Kurtosis | Re-run top-K IS | **E[z^4]** of **excess monthly returns**, NOT excess kurtosis |
| Variance of SR | **All completed trials with valid SR** | Not just top-K or filtered results |

### 2.3 SR0 Parameter Definitions

**Critical clarifications for SR0 calculation:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **mu (mean SR under null)** | **0** | Null hypothesis assumes no skill - random strategies have expected SR = 0 |
| **N (number of trials)** | Completed trials from Optuna summary (or N_eff if available) | Avoid bias from filtered optuna_results |
| **var_sr (variance of SR)** | Variance across ALL completed trials with valid SR | Not just top-K; include all completed trials with valid Sharpe |

**Caveats:**
1. **Trial correlation**: Optuna trials with similar parameters may be correlated, reducing effective N. If an estimate of N_eff is available, use it; otherwise use total completed N as a conservative approximation.
2. **Feasible vs infeasible**: Include all completed trials with valid Sharpe ratio in variance calculation, regardless of constraint feasibility.
3. **No filtering**: Correct DSR calibration assumes completed trials are **not** filtered (no min-profit / no score filter). If filters are enabled, DSR must use the pre-filter completed-trial set to compute N and var_sr.
4. **In-memory aggregation**: Compute mean/variance of Sharpe across all completed trials **in memory** right after Optuna finishes (pre-filter), then discard the full list after DSR is calculated to avoid DB bloat.

### 2.4 Key Implementation Decisions

**Decision 1: Return Period for Higher Moments**
- **Options**: Daily, Weekly, Monthly
- **Recommendation**: Monthly returns (consistent with existing Sharpe calculation in metrics.py)
- **Rationale**: Monthly returns reduce noise while maintaining sufficient sample size

**Decision 2: Sharpe Ratio Consistency**
- DSR formula requires **unannualized** Sharpe ratio
- Current `metrics.py` computes Sharpe from monthly returns without annualization
- Use the **same monthly return series and risk-free adjustment** for skew/kurtosis (excess monthly returns)

**Decision 3: Minimum Data Requirements**
- Minimum 3 monthly returns for skewness/kurtosis
- Trials with insufficient data get `dsr = None`

**Decision 4: DSR Output and Luck Share**
- DSR returns **P(SR > SR0)** - probability observed SR exceeds selection-bias threshold
- Higher is better (>0.95 suggests robust strategy beyond luck)
- Also calculate **"Luck Share %"** = (SR0 / SR) * 100
  - Represents what portion of observed Sharpe is attributable to selection bias
  - Example: SR=2.0, SR0=0.5 -> Luck Share = 25% ("25% of your Sharpe is explainable by luck")
  - **No hard cap at 100%**: values > 100% mean observed Sharpe does not clear SR0 (noise floor)

**Decision 5: Treatment of Invalid/NaN Sharpe**
- Trials with `sharpe_ratio = None` receive `dsr = None`
- These trials rank last in DSR sorting
- If `SR <= 0`, **Luck Share = N/A** (no negative values)

---

## 3. Implementation Architecture

### 3.1 File Structure Changes

```
src/core/
    post_process.py          # Extend with DSR functions + DSRConfig + re-run logic
    metrics.py               # Add skewness/kurtosis helpers
    storage.py               # Extend schema for DSR columns

src/ui/
    server.py                # Extend optimize endpoint
    static/js/
        post-process-ui.js   # Extend for DSR config
        results.js           # Add DSR tab rendering
    templates/
        index.html           # Add DSR UI section
        results.html         # Add DSR tab button
```

### 3.2 Data Flow Diagram

```
START PAGE
  POST PROCESS
    [x] Enable DSR
        Top Candidates for DSR: [20]
    [ ] Enable Forward Test
        FT Period Days: [30]
        Top K for FT: [10]  (From DSR top if both enabled)
        Sort By: [profit_degradation]

SERVER: /api/optimize
  1. Run Optuna optimization -> results[]
  2. Save Optuna results to DB
  3. IF dsr_enabled:
     a. Re-run IS backtests for top-K candidates using the **same period and warmup** as Optuna
     b. Calculate skew/kurtosis/track length from these returns
     c. Compute DSR probability for each candidate
     d. Re-rank by DSR probability
     e. Save DSR results to DB
  4. IF ft_enabled:
     a. IF dsr_enabled: use DSR-ranked original OptimizationResult objects
     b. ELSE: use Optuna top-K as input
     c. Run forward test
     d. Save FT results to DB

RESULTS PAGE
  Tabs: [Top Parameter Sets] [DSR] [Forward Test]
  DSR Tab: same table structure as Optuna (re-ranked)
  Equity Chart Info Line (DSR tab):
    "Rank: #5 -> #1 | DSR: 0.92 | Luck: 25%"
```

### 3.3 Database Schema Extensions

#### Studies Table (new columns)
```sql
-- DSR configuration
dsr_enabled INTEGER DEFAULT 0,
dsr_top_k INTEGER,
dsr_n_trials INTEGER,           -- Total trials used for SR variance
dsr_mean_sharpe REAL,           -- Mean SR across all trials
dsr_var_sharpe REAL             -- Variance of SR across trials
```

#### Trials Table (new columns)
```sql
-- DSR metrics per trial
dsr_probability REAL,           -- DSR value (0-1)
dsr_rank INTEGER,               -- Rank after DSR sorting
dsr_skewness REAL,              -- Return skewness
dsr_kurtosis REAL,              -- Return RAW kurtosis (E[z^4])
dsr_track_length INTEGER,       -- Number of monthly returns (T)
dsr_luck_share_pct REAL         -- Luck share: (SR0 / SR) * 100
```

---

## 4. Detailed Implementation Steps

### Phase 2.1: DSR Core (post_process.py + metrics.py)

**Priority: HIGH**

**4.1.1 Add DSR helpers to `post_process.py`**
- Add `DSRConfig` dataclass
- Add DSR math helpers (expected max SR, SR std error, DSR, luck share)
- Add `run_dsr_analysis()`
- Add a top-K **re-run IS backtest** step to compute monthly returns

**Re-run requirement**
- OptimizationResult does not store equity/timestamps
- For DSR, re-run IS backtest for top-K to reconstruct equity + timestamps
- Use the same config params as Optuna results and the **exact same IS date range and warmup** used by Optuna
- Compute higher moments on **excess monthly returns** (monthly return minus monthly risk-free)

**4.1.2 Add moment helpers to `metrics.py`**
```python
def calculate_higher_moments_from_monthly_returns(monthly_returns: List[float]) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculate skewness and RAW kurtosis from monthly returns.
    Returns (skewness, raw_kurtosis) or (None, None) if insufficient data.
    """
```

### Phase 2.2: Extend storage.py

**Priority: MEDIUM**

Add new DSR columns (see schema section) and new save/load helpers:
- `save_dsr_results(study_id, dsr_results, ...)`
- Extend `load_study_from_db()` to include DSR fields in trial payload

### Phase 2.3: Server Integration (server.py)

**Priority: HIGH**

Extend `/api/optimize` endpoint:
```python
if dsr_enabled and study_id:
    dsr_config = DSRConfig(
        enabled=True,
        top_k=int(post_process_payload.get("dsrTopK", 20)),
    )
    dsr_results = run_dsr_analysis(
        optuna_results=results,          # full results list
        config=dsr_config,
        n_trials_total=completed_trials, # from optuna summary
        # include params for IS re-run (csv, strategy_id, date range)
    )
    save_dsr_results(study_id, dsr_results, ...)

    # If FT also enabled, use DSR-ranked ORIGINAL OptimizationResult objects
    if ft_enabled:
        ft_input_candidates = [r.original_result for r in dsr_results[:ft_top_k]]
```

**FT chaining fix**
- `run_forward_test` expects OptimizationResult-like attributes
- DSR results should carry a reference to the original OptimizationResult
- FT should receive those original objects in DSR rank order

### Phase 2.4: Frontend - Start Page (index.html)

**Priority: MEDIUM**

```html
<!-- Inside POST PROCESS section, before Forward Test -->
<div class="form-group">
  <div class="checkbox-group">
    <input type="checkbox" id="enableDSR" />
    <label for="enableDSR"><strong>Enable DSR Analysis</strong></label>
  </div>
  <p style="font-size: 12px; color: #666;">
    Deflated Sharpe Ratio corrects for selection bias and non-normal returns.
  </p>
</div>

<div class="form-group" id="dsrSettings" style="display: none;">
  <label for="dsrTopK">Top Candidates for DSR:</label>
  <input type="number" id="dsrTopK" value="20" min="1" max="10000" />
</div>
```

### Phase 2.5: Frontend - post-process-ui.js

**Priority: MEDIUM**

Extend module with DSR config collection and toggle behavior.

### Phase 2.6: Frontend - Results Page (results.html)

**Priority: MEDIUM**

```html
<!-- Add DSR tab button between optuna and forward_test -->
<button class="tab-btn" data-tab="dsr" style="display: none;">DSR</button>
```

### Phase 2.7: Frontend - results.js

**Priority: MEDIUM**

- Add `ResultsState.dsr` payload
- Add DSR tab rendering (reuse same table renderer as Optuna)
- Update tab visibility logic
- DSR tab equity info line shows DSR rank change, DSR value, luck share

---

## 5. Testing Strategy

### 5.1 Unit Tests (`tests/test_dsr.py`)

```python
def test_calculate_expected_max_sharpe_basic():
    """Expected max SR increases with number of trials."""
    sr0_10 = calculate_expected_max_sharpe(0, 1.0, 10)
    sr0_100 = calculate_expected_max_sharpe(0, 1.0, 100)
    sr0_1000 = calculate_expected_max_sharpe(0, 1.0, 1000)
    assert sr0_10 < sr0_100 < sr0_1000


def test_calculate_dsr_high_sharpe():
    """High Sharpe with short track record should have lower DSR."""
    dsr_long = calculate_dsr(2.0, 0.5, 0, 3, 36)  # 3 years
    dsr_short = calculate_dsr(2.0, 0.5, 0, 3, 12)  # 1 year
    assert dsr_long > dsr_short


def test_calculate_higher_moments_normal():
    """Normal returns should have near-zero skew and ~3 raw kurtosis."""
    np.random.seed(42)
    returns = np.random.normal(0, 1, 1000).tolist()
    skew, kurt = calculate_higher_moments(returns)
    assert abs(skew) < 0.5
    assert 2.0 < kurt < 4.5
```

### 5.2 Integration Tests

```python
def test_dsr_pipeline_integration():
    """Full DSR pipeline from Optuna results."""
    ...

def test_dsr_ft_pipeline_chaining():
    """When both enabled, FT should use DSR-ranked original results."""
    ...
```

### 5.3 UI Tests (Manual)

1. Enable DSR only - verify DSR tab appears with same columns as Optuna tab
2. Enable FT only - verify FT tab appears (existing behavior)
3. Enable both - verify both tabs, FT uses DSR ranking as input
4. Verify DSR settings toggle on checkbox change
5. Verify DSR table shows same metrics as Optuna (re-ranked)
6. Verify equity chart info line shows: Rank Change, DSR Value, Luck Share %
7. Verify trials with insufficient data show "N/A" for DSR metrics

---

## 6. Implementation Order

### Step 1: DSR Core (Estimated: 3-4 hours)
1. Add DSR helpers to `post_process.py`
2. Add higher-moment helper to `metrics.py` (excess monthly returns)
3. Implement top-K IS re-run to derive monthly returns using the same IS period/warmup as Optuna
4. Write unit tests for DSR calculations

### Step 2: Database Schema (Estimated: 1 hour)
1. Extend studies table schema
2. Extend trials table schema
3. Add `save_dsr_results()` function
4. Update `load_study_from_db()` to include DSR fields

### Step 3: Post Process Integration (Estimated: 2 hours)
1. Add `DSRConfig` dataclass to post_process.py
2. Implement `run_dsr_analysis()` function
3. Write integration tests

### Step 4: Server Endpoint (Estimated: 2 hours)
1. Extend `/api/optimize` for DSR flow
2. Handle DSR+FT chaining using original OptimizationResult objects
3. Test end-to-end pipeline

### Step 5: Frontend - Start Page (Estimated: 1 hour)
1. Add DSR UI section to index.html
2. Extend post-process-ui.js for DSR config
3. Update ui-handlers.js for payload construction

### Step 6: Frontend - Results Page (Estimated: 1-2 hours)
1. Add DSR tab button to results.html (label: "DSR")
2. Extend ResultsState for DSR data (trials array + metadata)
3. Reuse existing table rendering (same columns as Optuna)
4. Add DSR-specific equity chart info line (Rank Change, DSR, Luck Share%)
5. Update tab visibility logic

### Step 7: Testing & Polish (Estimated: 2 hours)
1. Run full test suite
2. Manual UI testing
3. Edge case handling
4. Documentation updates

**Total Estimated Time: 11-13 hours** (includes top-K re-run for DSR)

---

## 7. Risk Assessment & Mitigations

### 7.1 Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Insufficient track length | DSR = None for short backtests | Display warning, graceful fallback |
| Extreme skew/kurtosis | Unstable DSR values | Bound inputs, validate results |
| All-zero variance | Division by zero | Check before calculation, return None |
| Large n_trials | Numerical overflow | Use log-space calculations if needed |
| Extra compute for re-run | Longer post-process | Limit to top-K and reuse IS data range |

### 7.2 UX Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| User confusion about DSR meaning | Misinterpretation of results | Add tooltip/help text |
| DSR reorders favorite strategy | User frustration | Show rank change clearly |
| Slow computation | Poor responsiveness | Limit to top-K and keep DSR optional |

---

## 8. Future Enhancements (Out of Scope)

1. **Effective Trials Estimation**: Account for correlated Optuna trials
2. **Bootstrap DSR Confidence Intervals**: Monte Carlo uncertainty estimation
3. **DSR as Optuna Constraint**: Reject trials with DSR < threshold
4. **Multiple DSR Methods**: Support alternative DSR formulations

---

## 9. Dependencies

Add SciPy for Normal CDF/PPF:
```
scipy
```

---

## 10. References

1. Bailey, D.H. & Lopez de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality." Journal of Portfolio Management, 40(5), 94-107.
   - PDF: https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
   - SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551

2. Implementation references:
   - Tutorial: https://gmarti.gitlab.io/qfin/2018/05/30/deflated-sharpe-ratio.html
   - pypbo library: https://github.com/esvhd/pypbo
   - Wikipedia: https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio

---

## 11. Appendix: DSR & Luck Share Interpretation Guide

### 11.1 DSR Value Interpretation

| DSR Value | Interpretation |
|-----------|----------------|
| > 0.95 | Strong evidence of genuine skill |
| 0.80 - 0.95 | Moderate evidence, exercise caution |
| 0.50 - 0.80 | Weak evidence, likely luck component |
| < 0.50 | Insufficient evidence, assume luck |

**Key Insight**: A strategy showing 2.5 annual Sharpe after testing 1000 parameter sets has only ~60-70% DSR probability. The same Sharpe after testing 10 sets might have >95% DSR probability.

### 11.2 Luck Share Explanation

**Luck Share** tells you "what portion of your Sharpe ratio is attributable to selection bias from testing many strategies."

**Formula**: `Luck Share = SR0 / Your Observed Sharpe * 100%` (no cap; **N/A if SR <= 0**)

Where SR0 = expected maximum Sharpe from N random (zero-skill) strategies

**Example**:
| Scenario | Your Sharpe | SR0 (expected from luck) | Luck Share |
|----------|-------------|--------------------------|------------|
| Tested 10 strategies | 2.0 | 0.5 | 25% |
| Tested 100 strategies | 2.0 | 1.0 | 50% |
| Tested 1000 strategies | 2.0 | 1.5 | 75% |

**Interpretation**:
- Luck Share 25% -> "25% of your observed Sharpe is explainable by luck"
- Luck Share 50% -> "Half of your Sharpe is probably selection bias"
- Luck Share 75% -> "Most of your Sharpe is probably luck from testing many strategies"
- Luck Share > 100% -> "Observed Sharpe is below the selection-bias noise floor (SR0)"

**Note**: Luck Share is informational only. DSR probability is used for ranking (DSR incorporates luck share plus track record length and return distribution adjustments).

### 11.3 Sorting Logic

**Ranking is by DSR probability only** (highest first). Luck Share is displayed for user insight but does not affect ranking.

Trials with `DSR = N/A` (insufficient data) are ranked last.

---

## Approval & Sign-off

- [ ] Technical review completed
- [ ] UI/UX review completed
- [ ] Test plan reviewed
- [ ] Implementation approved

**Next Step**: Begin implementation with Phase 2.1 (DSR core in post_process.py + metrics.py)
