# Merlin Phase 4.2 — Add “Sanitize if Total Trades <= …” Switch (GPT‑5.2 Codex Prompt)

You are an agent coder working inside the Merlin repository. Implement **Phase 4.2**: add a UI toggle + backend wiring for configurable objective sanitization.

This update is intentionally **small**, but it must be **correct**, **deterministic**, and **reproducible** (settings must be persisted with the study).

Do **not** refactor unrelated code. Keep diffs tight.

---

## 0) Background (behavior contract)

Merlin’s Optuna objective evaluation may produce non‑finite values (`None`, `NaN`, `+inf`, `-inf`) for ratio-like metrics on small samples (e.g., zero trades, zero variance). Optuna treats `NaN` objective returns as **FAILED trials** (the study continues), and **failed trials are ignored by samplers** when sampling new parameters. Optuna constraints are evaluated only after **successful** trials. (Links at bottom.)

Therefore, sanitization is a controlled policy:
- In specific low-trade situations, replace non‑finite objective values with a conservative finite value (`0.0`) so the trial stays successful.
- Otherwise, keep strict correctness: non‑finite objective values cause trial FAIL via NaN returns.
- Profit Factor `inf` is considered invalid and must fail.

**This Phase 4.2 update adds user control over sanitization** (enabled + trade threshold), and makes the existing backend sanitization logic depend on that config.

---

## 1) Target UX (index.html)

Add one line to the “Optuna Settings” section on the index page:

- Label: **Sanitize if Total Trades <=**
- Controls: a **checkbox** + **integer input**
- Default values:
  - checkbox: **checked**
  - input: **0**
- Placement:
  - Inside Optuna Settings
  - **Below** the “Optimization Objectives” block
  - **Above** “Optimization budget”
- Help text:
  - A small-font line below the input, same style as the primary objective hint:
    - `Sanitizes: Sharpe, Sortino, SQN, Profit Factor`

No tooltips, no constraint hints, no counters.

### UI behavior
- When checkbox is unchecked: disable the numeric input (and keep value as-is).
- When checked: enable it.
- Ensure the numeric input is clamped to integer `>= 0` (at least on submit; optionally on blur).

---

## 2) Target data contract (API)

### Request payload (`/api/optimize`)
Add two fields:

```json
{
  "sanitize_enabled": true,
  "sanitize_trades_threshold": 0
}
```

**Always send them** from the UI. Server must also tolerate missing fields (defaults below) for backward compatibility with older UI builds.

### Response payload
If the results page shows an “Optuna Settings summary” (it currently does in Merlin), include:

- `sanitize_enabled`
- `sanitize_trades_threshold`

No need to show a “sanitized trials count”.

---

## 3) Target backend behavior (sanitization rules)

Sanitization applies **only to objective values that are returned to Optuna**, not to the full metrics dict used for constraints.

### Definitions
- `total_trades`: read from the metrics dict using the same key you already rely on (likely `"total_trades"`).
- Non‑finite detection:
  - `None` => non‑finite
  - any `x` where `math.isfinite(float(x))` is False => non‑finite (covers NaN and ±inf)

### Metrics eligible for sanitization
Only these objective metrics are sanitized when enabled + threshold:
- `sharpe_ratio`
- `sortino_ratio`
- `sqn`
- `profit_factor`

### Rules
Let `N = sanitize_trades_threshold`.

**Gate condition**: sanitization is active only when:
- `sanitize_enabled == True`
- `total_trades` is finite
- `total_trades <= N`

Then apply:

1) `sharpe_ratio`, `sortino_ratio`, `sqn`:
   - if objective value is non‑finite (`None`, NaN, ±inf), set objective value to `0.0`.

2) `profit_factor` (special case):
   - If PF is `+inf` or `-inf`: the trial must **FAIL** (return NaN objective(s)).  
     This PF‑inf fail policy must be enforced **regardless** of sanitize switch state / threshold.
   - If PF is `None`/NaN: set PF objective to `0.0` only when gate condition is true (sanitize enabled + trades<=N).
   - Otherwise (finite PF): leave as is.

3) After sanitization, if any selected objective remains non‑finite: FAIL the trial by returning:
   - single objective: `float("nan")`
   - multi objective: `tuple(float("nan") for _ in objectives)`

4) Constraints:
   - Do not mutate `all_metrics` with sanitized values.
   - Constraints evaluation uses original metric values and your existing “missing => violated” logic.

### Edge cases
- If `total_trades` is missing, `None`, NaN, or non-numeric: sanitization gate condition is false. (No sanitization.)
- If sanitize enabled but threshold input invalid: server validation must reject request (400).
- If sanitize disabled: no sanitization is performed, except PF inf still fails.

---

## 4) Repo reconnaissance (do this first)

Before changing code, locate existing Optuna settings plumbing and mirror the patterns.

Use search:
- In HTML templates, search for “Optimization Objectives”, “Optimization budget”, “Primary Objective”.
- In JS, search for where the Optuna request payload is built (likely in `ui-handlers.js`), and where objectives are collected (likely in `optuna-ui.js`).
- In server, find the `/api/optimize` handler and existing validation for Optuna settings.
- In core, find the optimization config type passed from server to `optuna_engine.run_*` and extend it.

Follow local conventions for naming, validation, and JSON keys.

---

## 5) Required implementation changes (exact file list)

### Frontend (UI)

#### A) `src/ui/templates/index.html`
- Add the new setting row in the specified position.
- Use stable IDs:
  - checkbox: `optuna_sanitize_enabled`
  - input: `optuna_sanitize_trades_threshold`
- Use existing CSS classes (the ones used for other Optuna settings) so styling matches.
- Add the small hint text line.

**Tip:** copy the DOM pattern used by “Primary Objective” and “Constraints” controls and adapt.

#### B) `src/ui/static/js/optuna-ui.js`
Add functions using the same module/export pattern you already use (e.g., `window.OptunaUI` or ES module depending on repo):

1) `initSanitizeControls()`
- Read DOM elements by ID.
- Set input disabled state based on checkbox.
- Add event listener on checkbox change to toggle input disabled state.
- Optionally normalize the input on blur (integer >= 0).

2) `collectSanitizeConfig()`
- Read checkbox checked state -> boolean.
- Read input value -> integer.
- Convert empty/NaN to 0.
- Clamp to int >= 0.
- Return:
  ```js
  { sanitize_enabled: boolean, sanitize_trades_threshold: number }
  ```

Hook `initSanitizeControls()` into the existing Optuna UI initialization path (where you already init objective controls, sampler controls, etc.). Do not create a new init entry point unless needed.

#### C) `src/ui/static/js/ui-handlers.js`
- In the payload builder for `/api/optimize`, merge sanitize config:

```js
const sanitizeCfg = OptunaUI.collectSanitizeConfig();
payload.sanitize_enabled = sanitizeCfg.sanitize_enabled;
payload.sanitize_trades_threshold = sanitizeCfg.sanitize_trades_threshold;
```

Keep changes minimal; do not move unrelated logic.

---

### Backend

#### D) `src/ui/server.py`
- Parse `sanitize_enabled` and `sanitize_trades_threshold` from request JSON.
- Defaults if missing:
  - `sanitize_enabled = True`
  - `sanitize_trades_threshold = 0`
- Validation rules:
  - `sanitize_enabled`:
    - accept bool
    - accept strings `"true"/"false"` if the server already supports this pattern
  - `sanitize_trades_threshold`:
    - accept int
    - accept numeric string convertible to int
    - must be `>= 0`
    - reject negatives and non-numeric (400)

- Add these fields into the Optuna configuration object passed to the engine.

Implementation suggestion: follow existing “parse X from payload with default + validation” helpers already present; do not introduce a new validation subsystem.

#### E) `src/core/optuna_engine.py`
- Extend the optimization configuration dataclass/struct with:
  - `sanitize_enabled: bool`
  - `sanitize_trades_threshold: int`

- Implement sanitization using a whitelist + PF special rules:
  - Replace any existing hard-coded `total_trades <= 0` sanitization gate with the config gate.
  - Enforce PF inf failure regardless of switch.

##### Suggested helper design (minimal + testable)

Add/adjust helpers (prefer local/private, consistent with current style):

```python
def _is_non_finite(x: object) -> bool:
    # None => True
    # float conversion try/except
    # not math.isfinite(float(x)) => True

def _is_inf(x: object) -> bool:
    # True for +/-inf (handle None/non-numeric safely)

SANITIZE_METRICS = {"sharpe_ratio", "sortino_ratio", "sqn", "profit_factor"}
```

Then in the objective value preparation:

1) Extract objective values from `all_metrics` as you currently do.
2) Get `total_trades`.
3) If PF is among selected objectives and PF is inf => FAIL immediately.
4) If sanitize enabled and trades<=threshold:
   - for each objective in sanitize list:
     - if metric is PF: sanitize only if non-finite but not inf (i.e., NaN/None) => 0.0
     - else sanitize non-finite => 0.0
5) After that, if any objective value is still non-finite => FAIL by returning NaN(s).

**Important**: Do not mutate `all_metrics`; sanitize into a local `objective_values` list.

---

### Storage / Reproducibility

#### F) Study config persistence (`src/core/storage.py` and any schema file)

Persist sanitize settings with the study so that the results view and exports can show the exact run settings.

Minimal requirement:
- When saving the study/run config, store:
  - `sanitize_enabled`
  - `sanitize_trades_threshold`

Preferred approach:
- If you already have explicit columns for Optuna settings in `studies` table: add columns
  - `sanitize_enabled INTEGER NOT NULL DEFAULT 1`
  - `sanitize_trades_threshold INTEGER NOT NULL DEFAULT 0`
- If you store settings as JSON: add keys in the JSON object.

Then ensure study summary responses include these settings. If you have a DTO/serializer that returns study settings to the UI, add these two fields there.

No migration scripts are required if this project assumes fresh DBs; however schema creation must include them.

---

## 6) Tests (small but required)

Add minimal tests. Keep them focused; do not build an end-to-end UI test.

### Unit tests for engine sanitization
Create or extend a test module (example name `tests/test_optuna_sanitization.py`) that tests the sanitization behavior without running full Optuna.

You can test a helper that takes:
- selected objectives list
- `all_metrics` dict
- sanitize config
- returns either objective values or NaN fail marker

Test cases (minimum set):

1) Sanitization enabled, N=0, trades=0:
   - sharpe/sortino/sqn are NaN/inf/None => become 0.0
   - PF is NaN/None => becomes 0.0
   - outcome: finite objective(s), not failed

2) Sanitization enabled, N=0, trades=1:
   - sharpe is NaN => gate not satisfied => objective remains non-finite => FAIL (NaN return)

3) Sanitization disabled, trades=0:
   - sharpe NaN => FAIL (NaN return)
   - PF NaN => FAIL (unless PF not selected)

4) PF is +inf (any trades, sanitize either on/off):
   - MUST FAIL

5) Multi-objective: objectives include (`net_profit_pct`, `profit_factor`):
   - PF inf => returns tuple(NaN, NaN)

### Server parsing validation tests
In `tests/test_server.py` or a new small test:
- Missing sanitize fields -> defaults set (enabled True, threshold 0)
- Negative threshold -> 400
- Non-numeric string -> 400

Keep tests aligned with your current test infra.

---

## 7) Manual smoke test checklist (do after tests)

1) Open index page:
   - verify new sanitize controls appear at correct position
   - checkbox toggles input disabled/enabled

2) Start a small Optuna run with:
   - objective includes `profit_factor`
   - sanitize enabled, N=0
   - confirm no crash and settings show in results summary

3) Force PF inf scenario (if you can reproduce quickly):
   - verify trials fail (NaN objective) and are not stored as “complete” results.

---

## 8) Acceptance criteria (must pass)

1) UI:
   - The new sanitize row is present in the correct position.
   - Checkbox toggles numeric input disabled state.
   - Defaults: enabled + 0.
   - Small descriptive text lists sanitized metrics.

2) Request payload includes sanitize fields.

3) Backend:
   - Sanitization uses the new config.
   - PF `inf` always fails.
   - Sanitization modifies objective return values only; constraints still use raw metrics.

4) Study persistence:
   - sanitize settings saved with study.
   - settings returned in any settings summary.

5) Existing tests pass; new tests pass.

---

## 9) Notes for future-proofing

- Keep sanitization whitelist explicit (do not sanitize “everything non-finite”).
- Keep PF infinite special case strict (fail always).
- Keep server defaults (enabled True, threshold 0) so older clients do not break.

---

## 10) Reference links (for coder)

```text
Optuna FAQ: NaN return -> FAIL but study continues
https://optuna.readthedocs.io/en/stable/faq.html#how-are-nans-returned-by-trials-handled

Optuna samplers note: failed trials ignored by samplers (TPESampler)
https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.TPESampler.html

Optuna constraints_func behavior (evaluated after successful trials only)
(See sampler docs above; also visible in Optuna sampler source code.)

Python math.isfinite docs (False for NaN and infinities)
https://docs.python.org/3/library/math.html#math.isfinite
```

---

## 11) Deliverable

Implement the changes, keep diffs tight, and ensure the project runs and tests pass.

If any assumption about file locations differs from the repo, follow existing patterns and add a short comment near new code explaining the final placement.
