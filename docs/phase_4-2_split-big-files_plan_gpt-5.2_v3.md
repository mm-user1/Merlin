# Phase 4-2 — Split big files (server.py + results.js) — implementation plan (v3)

**Primary goal:** reduce context size for agent-coders by splitting the two biggest files **without changing behavior**.

This version incorporates fixes from the attached audit (and one small correction: the repo currently has **33** route decorators in `src/ui/server.py`, not 32).

---

## 0) Scope and invariants

### In scope
- Split:
  - `src/ui/server.py` → 4 files
  - `src/ui/static/js/results.js` → 4 files
- Keep:
  - identical HTTP API (paths, methods, JSON shape)
  - identical UI behavior

### Non‑negotiable invariants
1) **No behavior changes.** This is a mechanical split (move code, adjust imports/includes).
2) **All existing routes remain exactly the same** (paths + methods + return types).
3) **Running mode must keep working:**
   - `cd src/ui && python server.py`
4) **Tests must keep working:**
   - `pytest tests/ -v`
   - tests import `from ui import server as server_module` and call `server_module._build_optimization_config(...)`.

---

## 1) Target end state (agreed structure)

### 1.1 Server (4 files)
```
src/ui/
  server.py                 # thin entrypoint + app creation + route registration + test re-exports
  server_services.py        # helpers/shared logic (NO route decorators)
  server_routes_data.py     # pages + studies/tests/trades + presets + strategies + WFA detail endpoints
  server_routes_run.py      # optimization status/cancel + optimize/walkforward/backtest (run endpoints)
```

### 1.2 Results page JS (4 files)
```
src/ui/static/js/
  results-state.js       # state + localStorage/sessionStorage + URL query helpers + storage event handling
  results-format.js      # formatters + labels + stableStringify + MD5
  results-tables.js      # table/chart renderers + row selection + parameter detail rendering
  results-controller.js  # orchestration/init + API calls + event binding + modals
```

### 1.3 results.html load order (classic scripts)
Update `src/ui/templates/results.html` to load the new scripts **in this exact order** and **without** `async`/`defer` (to preserve deterministic execution order):

```html
<script src="/static/js/results-state.js"></script>
<script src="/static/js/results-format.js"></script>
<script src="/static/js/results-tables.js"></script>
<script src="/static/js/results-controller.js"></script>
```

---

## 2) Verified route inventory (must stay identical)

`src/ui/server.py` currently contains **33** route decorators.

### Pages
- `GET /`
- `GET /results`

### Optimization control
- `GET /api/optimization/status`
- `POST /api/optimization/cancel`

### Studies / tests / trades
- `GET /api/studies`
- `GET /api/studies/<study_id>`
- `DELETE /api/studies/<study_id>`
- `POST /api/studies/<study_id>/update-csv-path`
- `POST /api/studies/<study_id>/test`
- `GET /api/studies/<study_id>/tests`
- `GET /api/studies/<study_id>/tests/<test_id>`
- `DELETE /api/studies/<study_id>/tests/<test_id>`
- `POST /api/studies/<study_id>/trials/<trial_number>/trades`
- `POST /api/studies/<study_id>/trials/<trial_number>/ft-trades`
- `POST /api/studies/<study_id>/trials/<trial_number>/oos-trades`
- `POST /api/studies/<study_id>/tests/<test_id>/trials/<trial_number>/mt-trades`

### WFA detail endpoints (study/result retrieval, not “start a run”)
- `GET /api/studies/<study_id>/wfa/windows/<window_number>`
- `POST /api/studies/<study_id>/wfa/windows/<window_number>/equity`
- `POST /api/studies/<study_id>/wfa/windows/<window_number>/trades`
- `POST /api/studies/<study_id>/wfa/trades`

### Presets
- `GET /api/presets`
- `GET /api/presets/<name>`
- `POST /api/presets`
- `PUT /api/presets/<name>`
- `PUT /api/presets/defaults`
- `DELETE /api/presets/<name>`
- `POST /api/presets/import-csv`

### Run endpoints (initiate work)
- `POST /api/walkforward`
- `POST /api/backtest`
- `POST /api/optimize`

### Strategies
- `GET /api/strategies`
- `GET /api/strategy/<strategy_id>/config`
- `GET /api/strategies/<strategy_id>`

---

## 3) Implementation instructions for GPT‑5.2 Codex (do this exactly)

### 3.1 Workflow (recommended)
1) Create a working branch: `phase_4-2/split-big-files`
2) Baseline: `pytest tests/ -v` (save output)
3) Implement server split first (tests cover it)
4) Implement results JS split
5) Run tests again and do a short manual smoke test

### 3.2 “Run as script” vs “import as package” (IMPORTANT)
You currently support both:
- `cd src/ui && python server.py` (script execution)
- `pytest` importing `ui.server` (package execution)

To avoid import breakage, use a **dual-import** pattern in each new Python file:

```python
try:
    from .server_services import SOME_SYMBOL
except ImportError:
    from server_services import SOME_SYMBOL
```

Also ensure `sys.path.insert(...)` happens in `server.py` before importing `core.*` or `strategies.*`.

---

## 4) Server split — step-by-step

### 4.1 Create these new files
- `src/ui/server_services.py`
- `src/ui/server_routes_data.py`
- `src/ui/server_routes_run.py`

### 4.2 server.py becomes a thin entrypoint + re-export hub
**server.py must:**
- keep `app` defined at module scope (tests import `ui.server.app`)
- register routes by calling registrars
- keep `_build_optimization_config` available as `ui.server._build_optimization_config`

**Robust re-export pattern** (explicit binding; avoids ambiguity):
```python
try:
    from . import server_services as _services
    from .server_routes_data import register_routes as register_data_routes
    from .server_routes_run import register_routes as register_run_routes
except ImportError:
    import server_services as _services
    from server_routes_data import register_routes as register_data_routes
    from server_routes_run import register_routes as register_run_routes

_build_optimization_config = _services._build_optimization_config  # required by tests
```

Then:
- create Flask app
- call `register_data_routes(app)` and `register_run_routes(app)`
- keep `if __name__ == "__main__": app.run(...)` unchanged

### 4.3 server_services.py — move ALL helper functions here (audit fix)
**Rule:** `server_services.py` contains helpers/shared logic only; **no** `@app.*` decorators.

Move the complete helper set below into `server_services.py` (audit identified missing items; include all):

#### Optimization state + timestamps
- `_utc_now_iso`
- `_set_optimization_state`
- `_get_optimization_state`
- `OPTIMIZATION_STATE_LOCK`
- `LAST_OPTIMIZATION_STATE`

#### Upload / export
- `_persist_csv_upload`
- `_run_trade_export`
- `_run_equity_export`
- `_send_trades_csv`

#### Strategy typing / request parsing
- `_get_parameter_types`
- `_resolve_strategy_id_from_request`

#### Validation
- `validate_objectives_config`
- `validate_constraints_config`
- `validate_sampler_config`

#### Presets (I/O + import parsing)
- `_clone_default_template`
- `_ensure_presets_directory`
- `_validate_preset_name`
- `_preset_path`
- `_write_preset`
- `_load_preset`
- `_list_presets`
- `_coerce_bool`
- `_split_timestamp`
- `_convert_import_value`
- `_parse_csv_parameter_block`
- `_validate_strategy_params`
- `_normalize_preset_payload`

#### CSV path handling for studies
- `_resolve_csv_path`
- `_validate_csv_for_study`

#### WFA helpers used by WFA routes
- `_json_safe`
- `_build_trial_metrics`
- `_find_wfa_window`
- `_resolve_wfa_period`

#### Optimization config builder (tests depend on this symbol)
- `_build_optimization_config`

> Note: if you discover additional “helper” functions during the move that are not route handlers, they also belong in `server_services.py` unless they are clearly “HTTP-only.”

### 4.4 Logging in server_services.py (keep tests safe)
Some helpers (notably `_build_optimization_config`) log with `app.logger`. That breaks when helpers are called without an active Flask app context (tests call `_build_optimization_config` directly).

Use a safe logger accessor:

```python
import logging
from flask import current_app, has_app_context

def _get_logger():
    return current_app.logger if has_app_context() else logging.getLogger(__name__)
```

Replace `app.logger.*` inside service helpers with `_get_logger().*`.

**Route handlers may continue to use `app.logger`** (they run in request context).

### 4.5 server_routes_run.py — register run endpoints only
File should define:

```python
def register_routes(app):
    @app.get("/api/optimization/status") ...
    @app.post("/api/optimization/cancel") ...
    @app.post("/api/walkforward") ...
    @app.post("/api/backtest") ...
    @app.post("/api/optimize") ...
```

Route code remains identical except:
- imported helpers come from `server_services.py`
- any moved constants referenced should be imported too

### 4.6 server_routes_data.py — register pages + data endpoints
File should define:

```python
def register_routes(app):
    @app.route("/") ...
    @app.route("/results") ...
    # studies/tests/trades endpoints
    # WFA detail endpoints (GET window details, equity/trades export, stitched trades)
    # presets endpoints
    # strategies endpoints
```

Explicitly keep WFA detail endpoints here:
- `GET /api/studies/<study_id>/wfa/windows/<window_number>`
- `POST /api/studies/<study_id>/wfa/windows/<window_number>/equity`
- `POST /api/studies/<study_id>/wfa/windows/<window_number>/trades`
- `POST /api/studies/<study_id>/wfa/trades`

### 4.7 Mechanical checks (server)
Run:
1) `python -m py_compile src/ui/server.py src/ui/server_services.py src/ui/server_routes_data.py src/ui/server_routes_run.py`
2) `pytest tests/ -v`

Optional: print route inventory at startup (only in debug / dev) to visually confirm route count.

---

## 5) Results JS split — step-by-step

### 5.1 Create new JS files
- `src/ui/static/js/results-state.js`
- `src/ui/static/js/results-format.js`
- `src/ui/static/js/results-tables.js`
- `src/ui/static/js/results-controller.js`

### 5.2 Update template
In `src/ui/templates/results.html`, replace:
```html
<script src="/static/js/results.js"></script>
```
with the 4 ordered includes shown in Section 1.3.

### 5.3 Function-to-file mapping (audit fix)

#### results-state.js (state + persistence + URL)
Move:
- `OPT_STATE_KEY`, `OPT_CONTROL_KEY`
- `ResultsState` (keep `window.ResultsState = ResultsState`)
- `readStoredState`
- `applyState`
- `updateStoredState`
- `handleStorageUpdate`
- `getQueryStudyId`, `setQueryStudyId`

#### results-format.js (pure formatting + hashing)
Move:
- label constants: `OBJECTIVE_LABELS`, `SORT_METRIC_LABELS`, `SOURCE_LABELS`, `TOKEN_LABELS`, `CONSTRAINT_OPERATORS`
- formatters: `formatSigned`, `formatRankCell`, `formatDateLabel`, `formatDuration`, etc.
- `stableStringify`, `createParamId`
- `md5` + its internal helper functions

#### results-tables.js (renderers)
Move render and table/UI-render helpers:
- `renderOptunaTable`, `renderWFATable`, `renderForwardTestTable`, `renderOosTestTable`, `renderDsrTable`, `renderStressTestTable`, `renderManualTestTable`
- `renderEquityChart`
- `calculateWindowBoundaries`, `renderWindowIndicators`, `displaySummaryCards`
- row/param helpers: `selectTableRow`, `getParamDisplayOrder`, `copyParamValue`, `highlightParamItem`
- `showParameterDetails` (async)

#### results-controller.js (orchestration + API + event wiring) — include the previously omitted names
Move everything else, including these functions explicitly (audit-identified omissions):
- `inferPostProcessSource`
- `buildRankMapFromKey`
- `updateTabsVisibility`
- `setTableExpanded`
- `setTableExpandVisibility`
- `bindTableExpandToggle`
- `getTrialsForActiveTab`

Plus existing orchestration:
- `activateTab`
- `openStudy`, `applyStudyPayload`, `loadStudiesList`, `renderStudiesList`, `hydrateFromServer`
- missing CSV dialog functions
- manual test modal flow
- `initResultsPage` + `DOMContentLoaded` listener

### 5.4 Top-level execution rule
Only `results-controller.js` should contain top-level “run now” code:
- `document.addEventListener('DOMContentLoaded', initResultsPage);`

Other files should only define functions/constants.

### 5.5 Optional: tombstone the original results.js
Either delete `results.js` or replace it with a comment:
```js
// Deprecated: split into results-state.js / results-format.js / results-tables.js / results-controller.js
```

---

## 6) Verification checklist

### 6.1 Automated (required)
Run:
- `pytest tests/ -v`

Key tests that must pass (these exist today):
- `test_optuna_sanitize_defaults`
- `test_get_wfa_window_details`
- `test_generate_wfa_window_equity`
- `test_download_wfa_window_trades`
- CSV import tests for presets: `test_csv_import_*`

### 6.2 Manual smoke test (recommended)
1) `cd src/ui && python server.py`
2) Open:
   - `/` and `/results`
3) On `/results`:
   - load a study
   - switch tabs (Optuna/WFA/post-process/manual tests)
   - select a row and open parameter details
   - render equity curve
   - export/download trades where available
4) Browser devtools:
   - ensure the 4 new JS files load (no 404)
   - ensure no console errors

---

## 7) Notes / future-proofing (optional follow-ups)

### 7.1 Route module size imbalance
`server_routes_run.py` has fewer routes but includes very large handlers (notably `/api/optimize`). If you later want smaller chunks for agent-coders, consider splitting run routes further:
- `server_routes_optimize.py` (optimize + status/cancel)
- `server_routes_run_misc.py` (walkforward/backtest)

Not required for Phase 4-2.

### 7.2 Constants duplication
There is duplication of objective/constraint labels between backend and frontend. Keep as-is for this split; unify later only if you’re ready to define a shared schema.

---

## References (for patterns and semantics)

Flask (structure / modularization):
```text
https://flask.palletsprojects.com/en/stable/patterns/packages/
https://flask.palletsprojects.com/en/stable/blueprints/
```

JavaScript (modules / script loading semantics):
```text
https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules
https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script
https://html.spec.whatwg.org/multipage/scripting.html
```
