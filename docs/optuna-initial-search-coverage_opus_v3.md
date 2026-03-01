# Optuna Coverage Mode — Implementation Plan v3

## 1) Objective

Replace purely random initial trials with deterministic structured coverage.

Feature: `coverage_mode` checkbox in Advanced Settings.

Goals:
- Every categorical option (e.g., each of 11 MA types) gets equal representation in initial trials.
- Continuous parameters distributed via Latin Hypercube Sampling (LHS) within each category stratum.
- Initial coverage is identical for the same search space + trial count (deterministic, no seed dependency).
- Sampler receives complete information about the parameter space before Bayesian/evolutionary phase.

Non-goals for this PR:
- Seed feature (separate future PR).
- New core files (`sampling.py` etc.) — all logic stays in `optuna_engine.py`.
- N_min / N_rec formulas, warning panels with color badges, "Use Minimum" / "Use Recommended" buttons.
- Edge sentinels (boundary probes).
- Full Cartesian grid search.
- DB schema migration.


## 2) Locked Decisions

1. Default: `coverage_mode = False` (backward compatible).
2. Deterministic via fixed numpy RNG seed (no external seed dependency).
3. UI: checkbox + one dynamic info line (not a warning panel).
4. Label: "Initial trials:" (neutral, no "random" word).
5. Field name: `coverage_mode` (bool) everywhere.
6. When coverage is ON: sampler's `n_startup_trials` set to 0 so TPE goes Bayesian immediately after structured coverage.
7. All helper functions private inside `optuna_engine.py`.
8. Works with all samplers (TPE, NSGA-II, NSGA-III, Random).


## 3) Algorithm

### 3.1 Parameter classification

From the effective search space returned by `_build_search_space()`:
- `categorical`: params where `type == "categorical"` (includes select and bool params).
- `numeric`: params where `type in ("int", "float")`.

### 3.2 Trial generation

```
Input:
  search_space: Dict[str, Dict]  (from _build_search_space())
  n_trials: int                  (from "Initial trials" input)

Output:
  List[Dict[str, Any]]          (param dicts for study.enqueue_trial())

Algorithm:

1. CLASSIFY parameters into categorical and numeric.

2. IF no categorical params:
   → Generate n_trials LHS points across all numeric dimensions.
   → Denormalize to actual values (snap to step/type).
   → Return list of param dicts.

3. IF categorical params exist:
   a) Pick main_axis = categorical param with most choices.
      (If tied: first in dict order, which follows config.json insertion order.)

   b) Distribute trials:
      trials_per_option = n_trials // len(main_axis.choices)
      remainder = n_trials % len(main_axis.choices)
      Option at index i gets: trials_per_option + (1 if i < remainder else 0)

   c) For each main_axis option value:
      - Generate `count` LHS points for numeric params (independent LHS per stratum).
      - Assign main_axis = this option.
      - Assign other categoricals via deterministic round-robin with coprime stride:
          idx = (trial_index * stride) % len(other_options)
          where stride = smallest integer coprime to len(other_options), stride >= 2
      - Denormalize numeric params from LHS.

   d) Deterministic shuffle of final list (fixed seed) to interleave categories.

4. IF n_trials == 0: return empty list (skip coverage).
   IF n_trials < len(main_axis.choices): partial coverage (some options get 0 trials).
```

### 3.3 LHS implementation (numpy-only)

```python
def _latin_hypercube(n_dims: int, n_samples: int, seed: int = 42) -> np.ndarray:
    """
    Latin Hypercube Sample in [0, 1]^n_dims.
    Returns shape (n_samples, n_dims).
    Deterministic for same inputs (fixed seed).
    """
    rng = np.random.RandomState(seed)
    result = np.zeros((n_samples, n_dims))
    for d in range(n_dims):
        perm = rng.permutation(n_samples)
        for i in range(n_samples):
            low = perm[i] / n_samples
            high = (perm[i] + 1) / n_samples
            result[i, d] = rng.uniform(low, high)
    return result
```

Each dimension divided into `n_samples` equal intervals, one point per interval, intervals shuffled per dimension. Deterministic because `RandomState(seed)` is fixed.

### 3.4 Denormalization

```
For norm_value in [0, 1]:

  int param:   raw = low + norm * (high - low)
               snapped = round(raw / step) * step
               clamped = clamp(snapped, low, high)
               return int(clamped)

  float param: raw = low + norm * (high - low)
               if step: snapped = round(raw / step) * step
               clamped = clamp(snapped, low, high)
               return float(clamped)
```

### 3.5 Example: S01 with 100 initial trials

```
Categorical:
  maType: 11 options [EMA, SMA, HMA, WMA, ALMA, KAMA, TMA, T3, DEMA, VWMA, VWAP]
  trailMaType: 11 options (secondary — round-robin)

Numeric (~12 enabled params):
  maLength:       int,   min=25,  max=500, step=25
  closeCountLong: int,   min=2,   max=10,  step=1
  stopLongX:      float, min=1.0, max=3.0, step=0.1
  ...

Stratification on maType (11 options):
  100 / 11 = 9 per option, remainder 1 → first option gets 10

  EMA:   10 trials, LHS(dims=12, n=10), trailMaType round-robin
  SMA:    9 trials, LHS(dims=12, n=9),  trailMaType round-robin
  HMA:    9 trials, LHS(dims=12, n=9),  trailMaType round-robin
  ...
  VWAP:   9 trials, LHS(dims=12, n=9),  trailMaType round-robin

Each MA type gets ~equal representation.
Each stratum has LHS-distributed continuous params.
trailMaType cycles deterministically across all 11 values.
```

### 3.6 Example: S04 with 50 initial trials

```
No categorical params.
8 numeric params: rsiLen, stochLen, kLen, dLen, obLevel, osLevel, ...

→ Plain LHS(dims=8, n=50)
→ Denormalize each point to actual values with step snapping.
→ Still better than random (guaranteed even coverage per dimension).
```


## 4) UI Design

### 4.1 Start Page — Advanced Settings

Current (index.html lines 512-515):
```html
<div class="form-group">
  <label for="optunaWarmupTrials">Initial random trials:</label>
  <input type="number" id="optunaWarmupTrials" min="0" max="50000" value="20" style="width: 80px;" />
</div>
```

New:
```html
<div class="form-group">
  <label for="optunaWarmupTrials">Initial trials:</label>
  <input type="number" id="optunaWarmupTrials" min="0" max="50000" value="20" style="width: 80px;" />
</div>
<div class="form-group">
  <div class="checkbox-group">
    <input type="checkbox" id="optunaCoverageMode" />
    <label for="optunaCoverageMode">Coverage mode (stratified LHS)</label>
  </div>
  <small id="coverageInfo" class="form-hint" style="color: #888; font-size: 11px; display: none;">
    <!-- Populated dynamically by JS -->
  </small>
</div>
```

Visual states:

**Coverage OFF:**
```
│ Initial trials:        [ 20 ]                        │
│ ☐ Coverage mode (stratified LHS)                     │
```

**Coverage ON, S01, 100 trials:**
```
│ Initial trials:        [ 100 ]                       │
│ ☑ Coverage mode (stratified LHS)                     │
│   maType: 11 options × ~9 trials each                │
```

**Coverage ON, S04, 50 trials:**
```
│ Initial trials:        [ 50 ]                        │
│ ☑ Coverage mode (stratified LHS)                     │
│   8 params, LHS coverage                             │
```

**Coverage ON, S01, 5 trials (warning):**
```
│ Initial trials:        [ 5 ]                         │
│ ☑ Coverage mode (stratified LHS)                     │
│   ⚠ 5 trials < 11 maType options — incomplete        │
```

### 4.2 Results Page — Optuna Settings block

Current results.html (lines 122-128) has Sampler and Pruner rows.

Add new row after Pruner, before Sanitize (between lines 128 and 130):
```html
<div class="setting-item">
  <span class="key">Initial</span>
  <span class="val" id="optuna-initial">-</span>
</div>
```

Display values:
- Coverage ON:  `100 (coverage)`
- Coverage OFF: `20`
- Old studies:  `–`


## 5) Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ START PAGE                                                      │
│                                                                 │
│ #optunaWarmupTrials → n_startup_trials: 100                    │
│ #optunaCoverageMode → coverage_mode: true                      │
│                                                                 │
│ buildOptunaConfig() returns:                                    │
│   { ..., n_startup_trials: 100, coverage_mode: true, ... }     │
└────────────────────────┬────────────────────────────────────────┘
                         │ POST /api/optimize or /api/walkforward
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ SERVER (server_services.py + server_routes_run.py)              │
│                                                                 │
│ _build_optimization_config():                                   │
│   coverage_mode = bool(payload.get("coverage_mode", False))    │
│   setattr(config, "coverage_mode", coverage_mode)              │
│                                                                 │
│ optuna_settings dict (for WFA):                                 │
│   "coverage_mode": coverage_mode                               │
│                                                                 │
│ Persisted in study config_json → DB                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
┌───────────────────────┐  ┌──────────────────────────────────────┐
│ OPTUNA ENGINE         │  │ WFA ENGINE                           │
│                       │  │                                      │
│ OptunaConfig:         │  │ _run_optuna_on_window():             │
│   coverage_mode=True  │  │   coverage_mode from optuna_settings │
│                       │  │   → OptunaConfig(coverage_mode=True) │
│ SamplerConfig:        │  │                                      │
│   n_startup_trials=0  │  │ Each window gets same coverage rules │
│   (when coverage ON)  │  └──────────────────────────────────────┘
│                       │
│ _optimize_*():        │
│   search_space = ...  │
│   study = create...() │
│   if coverage_mode:   │
│     trials = _generate_coverage_trials(search_space, n)        │
│     for t in trials:  │
│       study.enqueue_trial(t)                                   │
│   study.optimize(...)                                          │
└───────────────────────┘
```


## 6) Implementation by Layer

### 6.1 Core — optuna_engine.py

**A) New field on OptunaConfig (after line 1025):**
```python
coverage_mode: bool = False
```

**B) New private helpers (~120 LOC, add before _build_search_space):**

```python
# ------------------------------------------------------------------
# Coverage mode: deterministic initial trial generation
# ------------------------------------------------------------------

def _generate_coverage_trials(
    search_space: Dict[str, Dict[str, Any]],
    n_trials: int,
) -> List[Dict[str, Any]]:
    """Generate deterministic structured initial trials for study.enqueue_trial()."""
    ...

def _latin_hypercube(n_dims: int, n_samples: int, seed: int = 42) -> np.ndarray:
    """Latin Hypercube Sample in [0,1]^n_dims. Deterministic for same inputs."""
    ...

def _denormalize_value(norm_value: float, spec: Dict[str, Any]) -> Any:
    """Convert [0,1] normalized value to actual parameter value."""
    ...
```

`_generate_coverage_trials` implements the algorithm from section 3.2.
Param dict keys match search_space keys exactly (same format as `_prepare_trial_parameters` output).

**C) Enqueue in _optimize_single_process (after line 1589, before line 1591):**
```python
if self.optuna_config.coverage_mode:
    search_space_for_coverage = self._build_search_space()
    # n_initial = the user's "Initial trials" count
    n_initial = self.optuna_config.warmup_trials
    coverage_trials = _generate_coverage_trials(search_space_for_coverage, n_initial)
    for params in coverage_trials:
        self.study.enqueue_trial(params)
    logger.info("Enqueued %d coverage trials", len(coverage_trials))
```

Note: `search_space` is already built on line 1567. Reuse it:
```python
if self.optuna_config.coverage_mode:
    coverage_trials = _generate_coverage_trials(search_space, n_initial)
    ...
```

**D) Enqueue in _optimize_multiprocess (after line 1675, before line 1677):**
```python
if self.optuna_config.coverage_mode:
    mp_search_space = self._build_search_space()
    n_initial = self.optuna_config.warmup_trials
    coverage_trials = _generate_coverage_trials(mp_search_space, n_initial)
    for params in coverage_trials:
        self.study.enqueue_trial(params)
    logger.info("Enqueued %d coverage trials (multiprocess)", len(coverage_trials))
```

Enqueued trials are written to JournalStorage and visible to all workers.
Workers consume them before sampler-guided trials.

**E) Set n_startup_trials=0 when coverage ON:**

In `__init__` (around line 1050) or wherever SamplerConfig is built:
```python
if self.optuna_config.coverage_mode:
    self.sampler_config = SamplerConfig(
        sampler_type=self.sampler_config.sampler_type,
        population_size=self.sampler_config.population_size,
        crossover_prob=self.sampler_config.crossover_prob,
        mutation_prob=self.sampler_config.mutation_prob,
        swapping_prob=self.sampler_config.swapping_prob,
        n_startup_trials=0,  # Coverage replaces random startup
    )
```

This ensures TPE goes Bayesian immediately after consuming coverage trials (not adding more random trials). NSGA is unaffected (doesn't use n_startup_trials).

**F) `n_initial` source:**

The number of coverage trials comes from the same input as warmup trials:
- `self.optuna_config.warmup_trials` (which maps from UI "Initial trials" input)
- This keeps backward compatibility: same input field, different behavior based on checkbox.


### 6.2 WFA — walkforward_engine.py

**In _run_optuna_on_window() (around line 2195):**

Add `coverage_mode` to OptunaConfig construction:
```python
optuna_cfg = OptunaConfig(
    ...,
    coverage_mode=bool(self.optuna_settings.get("coverage_mode", False)),
)
```

That's it. The OptunaOptimizer inside each window handles the rest.


### 6.3 Backend — server_services.py + server_routes_run.py

**In _build_optimization_config() (server_services.py, ~line 1676):**

Parse from payload:
```python
coverage_mode = bool(payload.get("coverage_mode", False))
```

Add to optuna_params dict (which gets setattr'd onto config):
```python
"coverage_mode": coverage_mode,
```

**In /api/walkforward route — optuna_settings dict (server_routes_run.py, ~line 402):**

Add:
```python
"coverage_mode": bool(getattr(optimization_config, "coverage_mode", False)),
```

**In /api/optimize route:**

Same: ensure `coverage_mode` flows from payload through config to OptunaOptimizer.


### 6.4 Frontend — index.html

**Replace lines 512-515 with:**

```html
<div class="form-group">
  <label for="optunaWarmupTrials">Initial trials:</label>
  <input type="number" id="optunaWarmupTrials" min="0" max="50000" value="20" style="width: 80px;" />
</div>
<div class="form-group">
  <div class="checkbox-group">
    <input type="checkbox" id="optunaCoverageMode" />
    <label for="optunaCoverageMode">Coverage mode (stratified LHS)</label>
  </div>
  <small id="coverageInfo" class="form-hint" style="color: #888; font-size: 11px; display: none;"></small>
</div>
```


### 6.5 Frontend — ui-handlers.js

**In buildOptunaConfig() (after line 1071):**

Add reading of coverage checkbox:
```javascript
const optunaCoverageMode = document.getElementById('optunaCoverageMode');
```

**In return object (after n_startup_trials line ~1125):**

Add:
```javascript
coverage_mode: Boolean(optunaCoverageMode && optunaCoverageMode.checked),
```


### 6.6 Frontend — optuna-ui.js

**Add new function and event wiring (~30 LOC):**

```javascript
/**
 * Update coverage info line based on current strategy config and trial count.
 * Called on: strategy change, param enable/disable, trial count change, checkbox toggle.
 */
function updateCoverageInfo() {
    const checkbox = document.getElementById('optunaCoverageMode');
    const infoEl = document.getElementById('coverageInfo');
    if (!checkbox || !infoEl) return;

    if (!checkbox.checked) {
        infoEl.style.display = 'none';
        return;
    }

    infoEl.style.display = 'block';
    const trialCount = parseInt(document.getElementById('optunaWarmupTrials')?.value) || 0;

    // Get enabled categorical params from current strategy config
    // (strategy config is already loaded in strategy-config.js)
    const categoricals = getCategoricalParams();  // {name: optionCount}
    const numericCount = getNumericParamCount();

    if (Object.keys(categoricals).length === 0) {
        infoEl.textContent = `${numericCount} params, LHS coverage`;
        infoEl.style.color = '#888';
        return;
    }

    // Find main axis (largest categorical)
    const mainAxis = Object.entries(categoricals)
        .sort((a, b) => b[1] - a[1])[0];
    const [axisName, optionCount] = mainAxis;

    if (trialCount < optionCount) {
        infoEl.innerHTML = `⚠ ${trialCount} trials &lt; ${optionCount} ${axisName} options — incomplete`;
        infoEl.style.color = '#c57600';
    } else {
        const perOption = Math.floor(trialCount / optionCount);
        const remainder = trialCount % optionCount;
        const label = remainder > 0 ? `~${perOption}–${perOption + 1}` : `${perOption}`;
        infoEl.textContent = `${axisName}: ${optionCount} options × ${label} trials each`;
        infoEl.style.color = '#888';
    }
}
```

Helper functions `getCategoricalParams()` and `getNumericParamCount()` read from the currently loaded strategy config and enabled_params checkboxes. These are ~15 LOC each, reading from DOM state that `strategy-config.js` already renders.

**Event binding:**
- `#optunaCoverageMode` change → `updateCoverageInfo()`
- `#optunaWarmupTrials` input → `updateCoverageInfo()`
- Strategy dropdown change → `updateCoverageInfo()` (after config loads)
- Parameter enable/disable checkboxes → `updateCoverageInfo()`


### 6.7 Frontend — queue.js

**In applyQueueConfigFallback() (after line ~733):**

Add:
```javascript
if (hasOwnProperty(config, 'coverage_mode')) {
    setCheckboxValue('optunaCoverageMode', config.coverage_mode);
}
```

Coverage checkbox state is automatically captured by `buildOptunaConfig()` when queue item is collected (no separate save logic needed — it's part of the config payload).


### 6.8 Frontend — results.html

**Add row after Pruner (between current lines 128-130):**

```html
<div class="setting-item">
  <span class="key">Initial</span>
  <span class="val" id="optuna-initial">–</span>
</div>
```


### 6.9 Frontend — results-tables.js

**In updateSidebarSettings() (after line ~1190 where optuna-pruner is set):**

```javascript
const warmupTrials = ResultsState.optuna.warmupTrials;
const coverageMode = ResultsState.optuna.coverageMode;
if (warmupTrials != null) {
    const suffix = coverageMode ? ' (coverage)' : '';
    setText('optuna-initial', `${warmupTrials}${suffix}`);
} else {
    setText('optuna-initial', '–');
}
```


### 6.10 Frontend — results-state.js

**Where ResultsState.optuna is populated from study data (around line 112):**

The `state.optuna` object comes directly from server JSON. The server already includes `warmup_trials` and `coverage_mode` in the optuna_settings/config JSON that is persisted in the DB. No special extraction needed — the fields are available as `ResultsState.optuna.warmup_trials` and `ResultsState.optuna.coverage_mode`.

If the rendering code expects camelCase keys, add mapping in the results controller where study data is parsed:
```javascript
warmupTrials: optunaConfig?.warmup_trials ?? null,
coverageMode: optunaConfig?.coverage_mode ?? false,
```


## 7) Interaction with Optuna Internals

### 7.1 enqueue_trial + TPE

When coverage trials are enqueued:
1. `study.optimize()` calls the objective function for each enqueued trial first.
2. Enqueued trials bypass the sampler — params are pre-specified.
3. After all enqueued trials are consumed, TPE checks `len(completed_trials) >= n_startup_trials`.
4. Since `n_startup_trials = 0` (set in 6.1.E), TPE immediately enters Bayesian phase.
5. TPE uses ALL completed trials (including coverage ones) as training data for the kernel density estimator.
6. Result: structured coverage → immediate Bayesian optimization. No wasted random trials.

### 7.2 enqueue_trial + NSGA-II/III

1. Enqueued trials form the initial population.
2. If `n_enqueued >= population_size`, the first generation is fully specified.
3. NSGA uses these as parents for crossover/mutation in subsequent generations.
4. `n_startup_trials` is not meaningful for NSGA (it controls TPE only).

### 7.3 enqueue_trial + multiprocess

1. Main process enqueues trials to JournalStorage before spawning workers.
2. Workers load the study from the same JournalStorage.
3. Optuna's internal queue is storage-backed — workers consume enqueued trials concurrently without duplication.
4. Order of consumption is non-deterministic (depends on scheduling), but coverage of the parameter space is guaranteed.

### 7.4 Coverage trials vs budget

If budget = 200 trials and coverage = 100:
- 100 trials are coverage (enqueued, consumed first).
- 100 trials are sampler-guided (Bayesian/evolutionary).
- Total = 200 (budget is a hard cap, respected).

If coverage >= budget: all trials are coverage, zero sampler-guided trials. The user controls this — no special guardrail needed beyond the info line.


## 8) Testing

### New test file: tests/test_coverage_startup.py

**Unit tests for coverage helpers:**

1. `test_lhs_shape_and_range` — output shape (n, dims), all values in [0, 1].
2. `test_lhs_deterministic` — same inputs → same output.
3. `test_lhs_interval_coverage` — each interval has exactly one sample per dimension.
4. `test_denormalize_int` — int rounding, step snapping, clamping.
5. `test_denormalize_float` — float step snapping, clamping.
6. `test_denormalize_float_no_step` — continuous float (no step).
7. `test_generate_no_categorical` — all numeric → plain LHS, correct count.
8. `test_generate_stratified` — categorical present → balanced distribution (diff ≤ 1 per option).
9. `test_generate_multiple_categoricals` — secondary categoricals use round-robin.
10. `test_generate_n_less_than_options` — partial coverage, no crash.
11. `test_generate_n_zero` — returns empty list.
12. `test_generate_deterministic` — same space + same n → same trials.
13. `test_param_dict_keys_match_search_space` — output keys = search_space keys.
14. `test_param_values_within_bounds` — all values within [low, high].

**Integration tests (can be in same file or existing test files):**

15. `test_enqueue_trial_accepted_by_optuna` — create study, enqueue generated trial, run 1 trial, no error.
16. `test_coverage_mode_in_optuna_config` — OptunaConfig(coverage_mode=True) accepted.
17. `test_sampler_n_startup_zero_when_coverage` — verify SamplerConfig.n_startup_trials == 0.

**Server tests (in tests/test_server.py):**

18. `test_api_accepts_coverage_mode` — POST /api/optimize with coverage_mode=true, verify it's persisted.
19. `test_queue_roundtrip_coverage_mode` — save queue item with coverage_mode, restore, verify.


## 9) LOC Estimate

| File | LOC | What |
|------|-----|------|
| `optuna_engine.py` — helpers | ~100 | `_generate_coverage_trials`, `_latin_hypercube`, `_denormalize_value` |
| `optuna_engine.py` — integration | ~25 | enqueue in single/multi + SamplerConfig override + OptunaConfig field |
| `walkforward_engine.py` | ~3 | forward `coverage_mode` to OptunaConfig |
| `server_services.py` | ~5 | parse `coverage_mode` from payload |
| `server_routes_run.py` | ~5 | include in optuna_settings dict |
| `index.html` | ~12 | checkbox + info container + label change |
| `ui-handlers.js` | ~4 | read checkbox, add to return object |
| `optuna-ui.js` | ~50 | `updateCoverageInfo()` + helpers + event wiring |
| `queue.js` | ~3 | restore coverage checkbox |
| `results.html` | ~4 | add "Initial" setting row |
| `results-tables.js` | ~8 | populate "Initial" row |
| `results-state.js` / controller | ~5 | map coverage fields from study data |
| **Production total** | **~224** | |
| `tests/test_coverage_startup.py` | ~120 | 19 test cases |
| **Grand total** | **~344** | |


## 10) Implementation Sequence

**Phase A — Core algorithm (can be tested standalone):**
1. Add `_latin_hypercube()`, `_denormalize_value()`, `_generate_coverage_trials()` to `optuna_engine.py`.
2. Add `coverage_mode` field to `OptunaConfig`.
3. Write unit tests (cases 1-14).

**Phase B — Engine integration:**
4. Add enqueue logic to `_optimize_single_process()` and `_optimize_multiprocess()`.
5. Add `n_startup_trials=0` override when coverage ON.
6. Write integration tests (cases 15-17).

**Phase C — API wiring:**
7. Parse `coverage_mode` in `server_services.py` and `server_routes_run.py`.
8. Forward to WFA engine in `walkforward_engine.py`.
9. Write server test (case 18).

**Phase D — UI:**
10. Update `index.html` (label + checkbox + info container).
11. Update `ui-handlers.js` (buildOptunaConfig).
12. Add `updateCoverageInfo()` to `optuna-ui.js`.
13. Update `queue.js` (restore).
14. Update Results page (`results.html` + `results-tables.js` + `results-state.js`).
15. Write queue roundtrip test (case 19).


## 11) Acceptance Criteria

1. Coverage checkbox visible in Start Page Advanced Settings.
2. When enabled, initial trials are deterministically pre-enqueued via `study.enqueue_trial()`.
3. Largest categorical axis gets balanced representation (counts differ by ≤ 1).
4. Other categoricals: deterministic round-robin coverage.
5. Numeric params: LHS-distributed within each stratum, snapped to step.
6. Same search space + same trial count → same enqueued trials (deterministic).
7. Works with all samplers: TPE, NSGA-II, NSGA-III, Random.
8. Works in both single-process and multi-process modes.
9. Works in WFA mode (each window gets structured coverage).
10. TPE goes Bayesian immediately after coverage (n_startup_trials=0).
11. Info line shows main axis breakdown or warning when trials < options.
12. Persisted in study config_json (no DB migration).
13. Displayed in Results page Optuna Settings as "100 (coverage)" or "20".
14. Queue roundtrip preserves coverage_mode setting.
15. Default OFF — existing behavior unchanged.
16. All 19 tests pass.
