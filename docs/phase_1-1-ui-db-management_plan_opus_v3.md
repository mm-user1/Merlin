# Phase 1-1: UI Database Management

## Overview

Add multi-database file management to Merlin: select, switch, and rename `.db` files from the Results page; select target DB (existing or new) before optimization runs from the Start page. On startup, auto-load the newest (by creation time) database file.

---

## Changes from v2

| # | Source | Issue | Verdict | Fix |
|---|--------|-------|---------|-----|
| 5.1 | Audit #1 | Plan states Flask is single-threaded (`server.py:31`), but `app.run()` defaults `threaded=True` since Flask 1.0. Global mutable `_active_db_path` has a TOCTOU race in `get_db_connection()`: `init_database()` reads the path, then `sqlite3.connect()` reads it again — another thread's `set_active_db()` can change it between those two points. | **Valid (Medium)** — real TOCTOU gap, but practical risk is low in single-user desktop tool with optimization guard preventing the main dangerous interleave. | Snapshot `_active_db_path` into a local at the top of `get_db_connection()` and pass through to `init_database()`. Also update Current State to remove "single-threaded" claim. |
| 5.2 | Audit #2 | `switchDatabase()` reloads sidebar lists but doesn't clear the currently-open study view. Old study data from previous DB remains visible until manual reselection. | **Valid (Medium)** — stale UI state after DB switch. | After switch, clear `ResultsState` study fields and call `refreshResultsView()` to reset the main content area. |
| 5.3 | Audit #3 | Overview says "select, create, switch, and rename from both pages" but Results page only has Rename button and switch-by-dblclick — no Create action. | **Valid (Low)** — the overview over-promises. Create is naturally a Start-page action (paired with "Run Optimization"). Adding Create to Results adds complexity without clear benefit. | Update Overview wording to accurately reflect scope: Start page picks target (existing or new), Results page switches/renames. |
| 5.4 | Audit #4 | Plan hides the entire "Status & Controls" section via `style="display: none;"`. The Cancel button (`results.html:47`, wired at `results-controller.js:914-927`) lives inside it — hiding removes active cancel control during long runs. | **Valid (Medium)** — functional regression. | Do **not** hide Status & Controls. Insert the Database section between Studies Manager and Status & Controls without removing any existing sections. |
| 5.5 | Audit #5 | Step 3 snippet uses `data.get("dbTarget")` but the `/api/optimize` handler uses `request.form` directly — there is no `data` variable. The `/api/walkforward` handler *does* have `data = request.form` (line 142). | **Valid (Medium)** — would cause `NameError` in the optimize endpoint. | Use `request.form.get(...)` for the optimize handler. Keep `data.get(...)` for WFA handler where `data` exists. |
| 5.6 | Audit #6 | `set_active_db()` accepts any filename without checking if the file exists. Switching to a non-existent DB (stale UI, typo) silently creates an empty DB on next `init_database()` call. | **Valid (Medium)** — operationally risky for "switch existing DB" semantics. | Add existence check in `set_active_db()`. The `create_new_db()` path already bypasses this check correctly by calling `set_active_db()` then `init_database()`, so add a separate `_set_active_db_path()` internal helper that `create_new_db()` uses, while the public `set_active_db()` validates existence. |
| 5.7 | Audit #7 | Plan uses `&#9654;` (right-pointing triangle ►) for the collapsed Database section. Current code uses `&#9660;` (▼) for all sections, with CSS `.collapsible.open .collapsible-icon { transform: rotate(180deg); }`. Rotating ► by 180° produces ◄, not ▼. | **Valid (Low)** — visual inconsistency. | Use `&#9660;` to match all existing collapsible sections. Remove the inaccurate note about icon swapping. |
| 5.8 | Audit #8 | Test plan adds only storage unit tests. No route/integration tests for `/api/databases*` endpoints or `dbTarget`/`dbLabel` in run payloads. Existing tests use real `get_db_connection()` without isolation from the new mutable path. | **Partially Valid (Medium)** — test isolation is needed; route tests are nice-to-have but not critical for this project's test philosophy. | Add a `conftest.py` fixture that snapshots/restores `_active_db_path` and `DB_INITIALIZED` for test isolation. Add basic route test notes. |
| 5.9 | Audit #9 | File changes summary lists `server_services.py` as modified, but no implementation step defines changes to it. | **Valid (Low)** — internal inconsistency. | Remove `server_services.py` from the File Changes Summary. `_get_optimization_state` is already imported in `server_routes_data.py`. |
| 5.10 | Audit #10 | `os.path.getctime()` returns metadata-change time on Unix, not creation time. | **Valid (Low impact)** — Merlin is a Windows desktop tool. `getctime` on Windows returns the correct creation time. | Add a documentation note about Windows-only semantics. No code change needed. |

---

## Changes from v1

| # | Issue | Fix |
|---|-------|-----|
| 4.1 | `_pick_newest_db()` called at module level before it is defined — `NameError` | Move all helper functions (`_pick_newest_db`, `_generate_db_filename`) **above** the module-level call; place the call immediately after them |
| 4.2 | Rename button reads UI-selected item but backend always renames active DB — mismatch when they differ | Change backend `rename_db(filename, new_label)` to accept an explicit filename; frontend sends the highlighted filename |
| 4.3 | `.selected` class used for both "active DB" and "user-highlighted" — clicking a non-active item hides the active indicator | Use two separate classes: `.db-active` (server-sourced, persistent) and `.selected` (click-highlight, transient); distinct CSS styling for each |

---

## Current State

- **DB path**: Hardcoded module-level constant `DB_PATH = STORAGE_DIR / "studies.db"` in `src/core/storage.py:36`
- **DB init**: Lazy via `init_database()` — creates schema on first `get_db_connection()` call
- **DB access**: All through `get_db_connection()` context manager (per-request, no global connection)
- **`DB_INITIALIZED`**: Module-level boolean flag, thread-safe via `DB_INIT_LOCK`
- **Storage dir**: `src/storage/` (gitignored, only `.gitkeep` tracked)
- **Optimization runs**: Synchronous within Flask request handlers; `save_*_to_db()` called from same thread
- **Flask server**: `app.run()` uses Flask default `threaded=True` — multiple requests can be served concurrently on different threads
- **WAL mode**: Enabled — creates `.db-wal` and `.db-shm` companion files

---

## Design Decisions (Confirmed)

| Decision | Choice |
|----------|--------|
| **Start page DB control** | Dropdown in "Optimizer Run" section above "Run Optimization" button |
| **Results page DB control** | Collapsible section below Studies Manager, collapsed by default |
| **DB selection on run** | Included in optimization FormData payload (atomic) |
| **Naming convention** | `YYYY-MM-DD_HHMMSS.db` or `YYYY-MM-DD_HHMMSS_user-label.db` |
| **Auto-load on startup** | Newest by file creation time (`os.path.getctime()` — Windows only; on Unix `ctime` is metadata-change time) |
| **Rename scope** | Label portion only (timestamp prefix preserved) |
| **Delete from UI** | No — users delete manually from filesystem |
| **Legacy `studies.db`** | User will delete manually; no special handling needed |
| **Label sanitization** | Minimal — reject filesystem-illegal chars only (`/ \ : * ? " < > \|`) |
| **DB metadata in lists** | Filenames only (no study counts or file sizes) |

---

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/core/storage.py` | **Modify** | Make DB path mutable; add DB management functions; snapshot path in `get_db_connection()` |
| `src/ui/server_routes_data.py` | **Modify** | Add 4 new `/api/databases` endpoints |
| `src/ui/server_routes_run.py` | **Modify** | Accept `dbTarget`/`dbLabel` in optimize + walkforward payloads |
| `src/ui/templates/index.html` | **Modify** | Add DB dropdown in "Optimizer Run" section |
| `src/ui/templates/results.html` | **Modify** | Add Database section between Studies Manager and Status & Controls (Status & Controls kept visible) |
| `src/ui/static/js/api.js` | **Modify** | Add database API functions |
| `src/ui/static/js/main.js` | **Modify** | Populate DB dropdown on load; include in submit payload |
| `src/ui/static/js/results-controller.js` | **Modify** | Add DB section logic (load list, switch with state reset, rename) |
| `src/ui/static/css/style.css` | **Modify** | Add styles for DB dropdown and DB list items |

> **v3 fix (5.9):** Removed `src/ui/server_services.py` from this table — no changes needed there. `_get_optimization_state` is already imported in `server_routes_data.py`.

---

## Implementation Steps

### Step 1: Backend — Make DB Path Mutable (`storage.py`)

**Goal:** Replace the hardcoded `DB_PATH` constant with a mutable module-level variable controlled by getter/setter functions. Ensure thread-safe access via path snapshotting.

**Changes to `src/core/storage.py`:**

1. Replace lines 31-36:
```python
# Before:
DB_INITIALIZED = False
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
JOURNAL_DIR = STORAGE_DIR / "journals"
DB_PATH = STORAGE_DIR / "studies.db"

# After:
DB_INITIALIZED = False
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
JOURNAL_DIR = STORAGE_DIR / "journals"
_active_db_path: Path = STORAGE_DIR / "studies.db"  # mutable, private; overwritten below
```

2. Add helper functions **immediately after the variable declarations** (before `_utc_now_iso`), then call `_pick_newest_db()`:

> **v2 fix (4.1):** All helper functions are defined first, then the module-level call follows. This avoids the `NameError` that v1 would have caused by calling `_pick_newest_db()` before its definition.

```python
import os
import re as _re


def _generate_db_filename(label: str) -> str:
    """Generate a timestamped DB filename with optional label."""
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    if label:
        safe = _re.sub(r'[<>:"/\\|?*]', '', label).strip().replace(' ', '-')[:50]
        return f"{ts}_{safe}.db" if safe else f"{ts}.db"
    return f"{ts}.db"


def _pick_newest_db() -> Path:
    """Return the newest .db file in STORAGE_DIR by creation time, or default."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    db_files = sorted(
        STORAGE_DIR.glob("*.db"),
        key=lambda p: os.path.getctime(p),
        reverse=True,
    )
    return db_files[0] if db_files else STORAGE_DIR / _generate_db_filename("")


# Auto-select newest DB on module load
_active_db_path = _pick_newest_db()
```

3. **Modify `init_database()` to accept an optional path parameter** for thread-safe usage:

> **v3 fix (5.1):** `init_database()` now accepts an optional `db_path` parameter. When called from `get_db_connection()`, the snapshotted path is passed through, eliminating the TOCTOU window where another thread could change `_active_db_path` between `init_database()` and `sqlite3.connect()`.

```python
def init_database(db_path: Path | None = None) -> None:
    """Initialize database schema and ensure storage directories exist."""
    global DB_INITIALIZED
    path = db_path or _active_db_path

    if DB_INITIALIZED and not path.exists():
        DB_INITIALIZED = False
    if DB_INITIALIZED and path.exists():
        with sqlite3.connect(
            str(path),
            check_same_thread=False,
            timeout=30.0,
            isolation_level="DEFERRED",
        ) as conn:
            _configure_connection(conn)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='studies'"
            )
            if cursor.fetchone():
                return
        DB_INITIALIZED = False
    with DB_INIT_LOCK:
        if DB_INITIALIZED:
            return
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(
            str(path),
            check_same_thread=False,
            timeout=30.0,
            isolation_level="DEFERRED",
        ) as conn:
            _configure_connection(conn)
            _create_schema(conn)
        DB_INITIALIZED = True
```

4. **Modify `get_db_connection()` to snapshot the active path:**

> **v3 fix (5.1):** The path is captured once into a local variable at function entry and reused for both `init_database()` and `sqlite3.connect()`. This prevents TOCTOU races when another thread calls `set_active_db()` concurrently.

```python
@contextmanager
def get_db_connection() -> Iterator[sqlite3.Connection]:
    path = _active_db_path  # snapshot — immune to concurrent set_active_db()
    init_database(db_path=path)
    conn = sqlite3.connect(
        str(path),
        check_same_thread=False,
        timeout=30.0,
        isolation_level="DEFERRED",
    )
    _configure_connection(conn)
    try:
        yield conn
    finally:
        conn.close()
```

5. Add the remaining public functions (after `_utc_now_iso` or grouped with the helpers above — either works since they are all below the module-level call):

> **v3 fix (5.6):** `set_active_db()` now validates that the target file exists, preventing accidental empty DB creation from stale UI or typos. A separate internal `_set_active_db_path()` is used by `create_new_db()` to set the path for a not-yet-existing file.

```python
def get_active_db_name() -> str:
    """Return the filename (not full path) of the active database."""
    return _active_db_path.name


def _set_active_db_path(filename: str) -> None:
    """Internal: set _active_db_path without existence check (for create_new_db)."""
    global _active_db_path, DB_INITIALIZED
    target = STORAGE_DIR / filename
    # Safety: reject path traversal
    if target.parent.resolve() != STORAGE_DIR.resolve():
        raise ValueError("Invalid database filename")
    _active_db_path = target
    DB_INITIALIZED = False


def set_active_db(filename: str) -> None:
    """Switch the active database to an existing file. Resets initialization flag."""
    target = STORAGE_DIR / filename
    # Safety: reject path traversal
    if target.parent.resolve() != STORAGE_DIR.resolve():
        raise ValueError("Invalid database filename")
    if not target.exists():
        raise ValueError(f"Database '{filename}' not found")
    _set_active_db_path(filename)


def create_new_db(label: str = "") -> str:
    """Create a new timestamped database file, set it active, initialize schema.
    Returns the new filename."""
    filename = _generate_db_filename(label)
    _set_active_db_path(filename)  # uses internal helper — file doesn't exist yet
    init_database()  # creates the file + schema
    return filename


def list_db_files() -> list[dict]:
    """List all .db files in STORAGE_DIR, sorted by creation time (newest first).
    Returns list of {name, active} dicts."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    active_name = _active_db_path.name
    db_files = sorted(
        STORAGE_DIR.glob("*.db"),
        key=lambda p: os.path.getctime(p),
        reverse=True,
    )
    return [
        {"name": f.name, "active": f.name == active_name}
        for f in db_files
    ]


def rename_db(filename: str, new_label: str) -> str:
    """Rename a database file's label portion (keep timestamp prefix).
    If the renamed file is the active DB, update _active_db_path.
    Returns the new filename."""
    global _active_db_path, DB_INITIALIZED
    old_path = STORAGE_DIR / filename

    # Safety: reject path traversal
    if old_path.parent.resolve() != STORAGE_DIR.resolve():
        raise ValueError("Invalid database filename")
    if not old_path.exists():
        raise ValueError(f"Database '{filename}' not found")

    old_name = old_path.stem  # without .db

    # Extract timestamp prefix (YYYY-MM-DD_HHMMSS)
    ts_match = _re.match(r'(\d{4}-\d{2}-\d{2}_\d{6})', old_name)
    if not ts_match:
        raise ValueError("Cannot rename: filename has no timestamp prefix")

    ts_prefix = ts_match.group(1)
    safe_label = _re.sub(r'[<>:"/\\|?*]', '', new_label).strip().replace(' ', '-')[:50]
    new_stem = f"{ts_prefix}_{safe_label}" if safe_label else ts_prefix
    new_filename = f"{new_stem}.db"
    new_path = STORAGE_DIR / new_filename

    if new_path.exists() and new_path != old_path:
        raise ValueError(f"Database '{new_filename}' already exists")

    # If renaming the active DB, reset init to close any cached state
    is_active = old_path.resolve() == _active_db_path.resolve()
    if is_active:
        DB_INITIALIZED = False

    # Rename .db and companion files (-wal, -shm)
    for suffix in ("", "-wal", "-shm"):
        src = old_path.parent / f"{old_path.name}{suffix}"
        dst = new_path.parent / f"{new_filename}{suffix}"
        if src.exists():
            src.rename(dst)

    if is_active:
        _active_db_path = new_path

    return new_filename
```

> **v2 fix (4.2):** `rename_active_db(new_label)` replaced by `rename_db(filename, new_label)` which accepts an explicit filename. This decouples the rename operation from the active DB, so the frontend can rename whichever DB the user has highlighted. If the renamed file happens to be the active DB, `_active_db_path` is updated automatically.

6. Replace all references to `DB_PATH` with `_active_db_path` in the same file (6 occurrences: lines 46, 48, 50, 69, 541 and anywhere else `DB_PATH` appears).

7. Update the public exports: keep `JOURNAL_DIR` exported (used by `optuna_engine.py`), add new functions to module scope. Remove `DB_PATH` from any `__all__` if present.

**Important:** The existing `init_database()` function already handles the case where the `.db` file doesn't exist — it creates directories and runs `_create_schema()`. The v3 change adds an optional `db_path` parameter for thread-safe pass-through while maintaining backward compatibility (callers that don't pass `db_path` use the global `_active_db_path`).

**Final file layout (top-down order):**
```
imports
OBJECTIVE_DIRECTIONS dict
DB_INIT_LOCK, DB_INITIALIZED
BASE_DIR, STORAGE_DIR, JOURNAL_DIR
_active_db_path (initial default)
_generate_db_filename()          <- helper, defined before call
_pick_newest_db()                <- helper, defined before call
_active_db_path = _pick_newest_db()  <- module-level call (safe: both functions defined above)
_utc_now_iso()
init_database(db_path=None)      <- v3: accepts optional path for thread safety
get_db_connection()              <- v3: snapshots _active_db_path into local
...existing functions...
get_active_db_name()
_set_active_db_path()            <- v3: internal helper for create_new_db
set_active_db()                  <- v3: validates file exists
create_new_db()
list_db_files()
rename_db()
```

---

### Step 2: Backend — New API Endpoints (`server_routes_data.py`)

**Goal:** Add endpoints for listing, switching, creating, and renaming databases.

**New imports in `server_routes_data.py`:**
```python
from core.storage import (
    list_db_files,
    set_active_db,
    create_new_db,
    rename_db,
    get_active_db_name,
    # ... existing imports ...
)
```

> **v3 fix (5.9):** `_get_optimization_state` is already imported in `server_routes_data.py` (line 66/96). No changes needed to `server_services.py`.

**New endpoints in `server_routes_data.py` (inside `register_routes`):**

```python
@app.get("/api/databases")
def list_databases() -> object:
    """List all database files and the currently active one."""
    return jsonify({
        "databases": list_db_files(),
        "active": get_active_db_name(),
    })


@app.post("/api/databases/active")
def switch_database() -> object:
    """Switch the active database file."""
    # Guard: reject if optimization is running
    state = _get_optimization_state()
    if state.get("status") == "running":
        return jsonify({"error": "Cannot switch database while optimization is running."}), HTTPStatus.CONFLICT

    body = request.get_json(silent=True) or {}
    filename = (body.get("filename") or "").strip()
    if not filename:
        return jsonify({"error": "Missing filename."}), HTTPStatus.BAD_REQUEST
    if not filename.endswith(".db"):
        return jsonify({"error": "Invalid filename."}), HTTPStatus.BAD_REQUEST

    try:
        set_active_db(filename)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    return jsonify({"active": get_active_db_name()})


@app.post("/api/databases")
def create_database() -> object:
    """Create a new timestamped database and set it active."""
    state = _get_optimization_state()
    if state.get("status") == "running":
        return jsonify({"error": "Cannot create database while optimization is running."}), HTTPStatus.CONFLICT

    body = request.get_json(silent=True) or {}
    label = (body.get("label") or "").strip()

    try:
        filename = create_new_db(label)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    return jsonify({"filename": filename, "active": filename})


@app.put("/api/databases/rename")
def rename_database() -> object:
    """Rename a database file's label portion."""
    state = _get_optimization_state()
    if state.get("status") == "running":
        return jsonify({"error": "Cannot rename database while optimization is running."}), HTTPStatus.CONFLICT

    body = request.get_json(silent=True) or {}
    filename = (body.get("filename") or "").strip()
    new_label = body.get("newLabel")
    if not filename:
        return jsonify({"error": "Missing filename."}), HTTPStatus.BAD_REQUEST
    if new_label is None:
        return jsonify({"error": "Missing newLabel."}), HTTPStatus.BAD_REQUEST

    try:
        new_filename = rename_db(filename, new_label.strip())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    return jsonify({"filename": new_filename, "active": get_active_db_name()})
```

> **v2 fix (4.2):** The rename endpoint now requires `filename` in the request body alongside `newLabel`. This allows renaming any DB file, not just the active one.

---

### Step 3: Backend — Accept DB Target in Optimization Payloads (`server_routes_run.py`)

**Goal:** Allow the optimization and WFA endpoints to receive `dbTarget` and `dbLabel` fields, switching the active DB before running.

> **v3 fix (5.5):** The optimize handler (`/api/optimize`) uses `request.form` directly and has no `data` variable. The WFA handler (`/api/walkforward`) assigns `data = request.form` at line 142. The snippet below uses the correct accessor for each endpoint.

**Changes to `/api/optimize` endpoint (in `server_routes_run.py`):**

Add early in the handler, after parsing `config_payload` but before building the optimization config:

```python
# --- DB target handling ---
db_target = request.form.get("dbTarget", "").strip()
db_label = request.form.get("dbLabel", "").strip()

if db_target == "new":
    try:
        create_new_db(db_label)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
elif db_target and db_target != get_active_db_name():
    try:
        set_active_db(db_target)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
```

**Changes to `/api/walkforward` endpoint (in `server_routes_run.py`):**

Add early in the handler, after parsing `config_payload` but before building the optimization config. Note: the WFA handler already has `data = request.form` at line 142:

```python
# --- DB target handling ---
db_target = data.get("dbTarget", "").strip()
db_label = data.get("dbLabel", "").strip()

if db_target == "new":
    try:
        create_new_db(db_label)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
elif db_target and db_target != get_active_db_name():
    try:
        set_active_db(db_target)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST
```

Add to response payloads:
```python
"active_db": get_active_db_name(),
```

**New imports needed in `server_routes_run.py`:**
```python
from core.storage import create_new_db, set_active_db, get_active_db_name
```

---

### Step 4: Frontend — API Functions (`api.js`)

**Goal:** Add JavaScript API functions for database management.

**Add to `src/ui/static/js/api.js`:**

```javascript
// -- Database Management --

async function fetchDatabasesList() {
  const resp = await fetch('/api/databases');
  if (!resp.ok) throw new Error('Failed to fetch databases');
  return resp.json();
}

async function switchDatabaseRequest(filename) {
  const resp = await fetch('/api/databases/active', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to switch database');
  }
  return resp.json();
}

async function createDatabaseRequest(label) {
  const resp = await fetch('/api/databases', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to create database');
  }
  return resp.json();
}

async function renameDatabaseRequest(filename, newLabel) {
  const resp = await fetch('/api/databases/rename', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, newLabel }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to rename database');
  }
  return resp.json();
}
```

> **v2 fix (4.2):** `renameDatabaseRequest` now takes `filename` as its first argument and sends it in the request body, so the backend knows which file to rename.

---

### Step 5: Frontend — Start Page DB Dropdown (`index.html`, `main.js`)

**Goal:** Add a DB target dropdown in the "Optimizer Run" section above the "Run Optimization" button.

**HTML changes to `src/ui/templates/index.html`:**

Insert new section between the WFA section (ends ~line 800) and the `opt-actions` div (line 802):

```html
<!-- Database Target (insert before opt-actions) -->
<div class="wf-section" style="margin-top: 0; margin-bottom: 16px; padding: 20px; border: 2px solid #3498db; border-radius: 8px; background-color: #f8f9fa;">
  <h3 style="color: #3498db; margin-bottom: 12px;">Database Target</h3>
  <div class="form-group">
    <label for="dbTarget" style="min-width: 100px;">Save to</label>
    <select id="dbTarget" style="flex: 1;">
      <option value="new">Create new DB</option>
    </select>
  </div>
  <div class="form-group" id="dbLabelGroup" style="display: none;">
    <label for="dbLabel" style="min-width: 100px;">Label</label>
    <input type="text" id="dbLabel" placeholder="optional label (e.g. link-15m)" style="flex: 1;">
  </div>
</div>
```

**JavaScript changes to `src/ui/static/js/main.js`:**

1. Add function to populate the DB dropdown on page load:

```javascript
async function loadDatabasesList() {
  try {
    const data = await fetchDatabasesList();
    const select = document.getElementById('dbTarget');
    const currentOptions = select.querySelectorAll('option:not([value="new"])');
    currentOptions.forEach(opt => opt.remove());

    (data.databases || []).forEach(db => {
      const opt = document.createElement('option');
      opt.value = db.name;
      opt.textContent = db.name;
      if (db.active) opt.selected = true;
      select.appendChild(opt);
    });

    // If no DBs exist, "Create new DB" stays selected
    if (!data.databases || data.databases.length === 0) {
      select.value = 'new';
    }

    toggleDbLabelVisibility();
  } catch (e) {
    console.warn('Failed to load databases list:', e);
  }
}

function toggleDbLabelVisibility() {
  const select = document.getElementById('dbTarget');
  const labelGroup = document.getElementById('dbLabelGroup');
  labelGroup.style.display = select.value === 'new' ? 'flex' : 'none';
}
```

2. In `DOMContentLoaded` handler, add:
```javascript
await loadDatabasesList();
document.getElementById('dbTarget').addEventListener('change', toggleDbLabelVisibility);
```

3. In the optimization submit flow (`ui-handlers.js`, inside `submitOptimization` or where FormData is built), add to the FormData:

```javascript
const dbTarget = document.getElementById('dbTarget').value;
formData.append('dbTarget', dbTarget);
if (dbTarget === 'new') {
  formData.append('dbLabel', document.getElementById('dbLabel').value.trim());
}
```

The same fields must be added to the WFA submission flow.

---

### Step 6: Frontend — Results Page DB Section (`results.html`, `results-controller.js`)

**Goal:** Add a collapsible "Database" section below Studies Manager, collapsed by default. Keep Status & Controls visible.

**HTML changes to `src/ui/templates/results.html`:**

> **v3 fix (5.4):** Status & Controls is **not** hidden. The Database section is inserted between Studies Manager and Status & Controls.

> **v3 fix (5.7):** Use `&#9660;` (downward triangle) to match all existing collapsible sections. The CSS `.collapsible.open .collapsible-icon { transform: rotate(180deg); }` rotates ▼ to ▲ when open, and the collapsed state shows ▼ unrotated. Since the Database section starts collapsed (no `open` class), ▼ appears unrotated — which is the correct closed indicator matching the convention when a section loses its `open` class.

**Insert Database section** after Studies Manager (after line 34, before Status & Controls at line 36):

```html
<div class="collapsible" id="database-section">
  <div class="collapsible-header">
    <span class="collapsible-icon">&#9660;</span>
    <span class="collapsible-title">Database</span>
  </div>
  <div class="collapsible-content">
    <div class="database-list">
    </div>
    <div class="manager-buttons">
      <button class="manager-btn" id="dbRenameBtn">Rename</button>
    </div>
  </div>
</div>
```

**JavaScript changes to `src/ui/static/js/results-controller.js`:**

1. Add DB list loading and rendering:

> **v2 fix (4.3):** Two separate CSS classes are used: `.db-active` marks the currently active DB (set from server data, never removed by clicks), and `.selected` marks the user-highlighted item (set on click). Both can coexist on the same element. This prevents the active indicator from disappearing when the user clicks a different item.

> **v3 fix (5.2):** `switchDatabase()` now clears the current study state and resets the main content view after switching, preventing stale study data from a previous DB from remaining visible.

```javascript
async function loadDatabasesList() {
  try {
    const data = await fetchDatabasesList();
    renderDatabasesList(data.databases || [], data.active);
  } catch (e) {
    console.warn('Failed to load databases:', e);
  }
}

function renderDatabasesList(databases, activeName) {
  const container = document.querySelector('.database-list');
  if (!container) return;
  container.innerHTML = '';

  databases.forEach(db => {
    const item = document.createElement('div');
    // .db-active = currently active DB (persistent, from server)
    // .selected  = user-highlighted item (transient, from click)
    // On initial render, the active DB gets both classes
    const classes = ['study-item'];
    if (db.active) classes.push('db-active', 'selected');
    item.className = classes.join(' ');
    item.textContent = db.name;
    item.dataset.dbName = db.name;

    item.addEventListener('click', () => selectDatabaseItem(item));
    item.addEventListener('dblclick', async () => {
      if (db.name === activeName) return; // already active
      await switchDatabase(db.name);
    });

    container.appendChild(item);
  });
}

function selectDatabaseItem(item) {
  // Move .selected to the clicked item; .db-active stays on active DB untouched
  document.querySelectorAll('.database-list .study-item').forEach(el =>
    el.classList.remove('selected')
  );
  item.classList.add('selected');
}

async function switchDatabase(filename) {
  try {
    await switchDatabaseRequest(filename);

    // v3 fix: clear current study state to prevent stale data
    ResultsState.studyId = null;
    ResultsState.studyName = '';
    ResultsState.mode = null;
    ResultsState.results = [];
    ResultsState.windows = [];
    ResultsState.selectedRowId = null;
    ResultsState.selectedRows = [];
    ResultsState.equityCurve = [];
    ResultsState.equityTimestamps = [];
    refreshResultsView();

    await loadStudiesList();
    await loadDatabasesList();
  } catch (e) {
    alert(e.message);
  }
}
```

> **Interaction model:** Single-click highlights (`.selected`), double-click switches the active DB. This is consistent with the Studies Manager pattern (click to highlight, action to act).

2. Bind Rename button:

> **v2 fix (4.2):** The Rename button reads the filename from the `.selected` item and sends it explicitly to the backend. The backend `rename_db(filename, new_label)` renames that specific file, regardless of which DB is currently active.

```javascript
document.getElementById('dbRenameBtn').addEventListener('click', async () => {
  const selectedItem = document.querySelector('.database-list .study-item.selected');
  if (!selectedItem) return;
  const targetFilename = selectedItem.dataset.dbName;

  // Extract current label from filename
  const match = targetFilename.match(/^\d{4}-\d{2}-\d{2}_\d{6}(?:_(.*))?.db$/);
  const currentLabel = match ? (match[1] || '') : '';

  const newLabel = prompt('Enter new label (leave empty to remove):', currentLabel);
  if (newLabel === null) return; // cancelled

  try {
    await renameDatabaseRequest(targetFilename, newLabel.trim());
    await loadDatabasesList();
    await loadStudiesList();
  } catch (e) {
    alert(e.message);
  }
});
```

3. Call `loadDatabasesList()` during Results page initialization (in `initResultsPage()`), and bind the rename button in a new `bindDatabaseSection()` function called from `initResultsPage()`.

---

### Step 7: CSS Styling (`style.css`)

**Goal:** Style the database list items and the DB dropdown on the start page.

**Add to `src/ui/static/css/style.css`:**

> **v2 fix (4.3):** `.db-active` and `.selected` are visually distinct. `.db-active` always shows a left border accent so the user can tell which DB is currently active even after clicking a different item.

```css
/* Database list in Results sidebar */
.database-list {
  max-height: 200px;
  overflow-y: auto;
  margin-bottom: 8px;
}

.database-list .study-item {
  cursor: pointer;
}

/* Active DB indicator (persistent, from server) */
.database-list .study-item.db-active {
  border-left: 3px solid #27ae60;
  padding-left: 9px;
  font-weight: 600;
}

/* User-highlighted item (click selection) */
.database-list .study-item.selected {
  background: #d4e9ff;
}

/* When the active DB is also selected */
.database-list .study-item.db-active.selected {
  background: #d4e9ff;
  border-left: 3px solid #27ae60;
}
```

The `.study-item` class is already styled for the Studies Manager — reusing it for the DB list gives consistent look-and-feel. The `.db-active` class uses a green left border to distinguish it from the blue border used by `.study-item.selected` in the Studies Manager.

For the Start page DB dropdown, the existing `select` and `input` styles from the `.wf-section` context should be sufficient — no new CSS needed.

---

### Step 8: Tests

**Goal:** Verify the new storage functions work correctly and existing tests aren't broken.

> **v3 fix (5.8):** Added test isolation fixture and route test notes.

**Test isolation fixture — add to `tests/conftest.py` (create if needed):**

```python
import pytest
from core import storage


@pytest.fixture(autouse=True)
def isolate_active_db(tmp_path):
    """Snapshot and restore _active_db_path and DB_INITIALIZED for test isolation."""
    original_path = storage._active_db_path
    original_initialized = storage.DB_INITIALIZED
    original_storage_dir = storage.STORAGE_DIR

    # Point storage to a temp directory for isolation
    storage.STORAGE_DIR = tmp_path
    storage._active_db_path = tmp_path / "test.db"
    storage.DB_INITIALIZED = False

    yield tmp_path

    # Restore
    storage.STORAGE_DIR = original_storage_dir
    storage._active_db_path = original_path
    storage.DB_INITIALIZED = original_initialized
```

**Note:** This `autouse` fixture should only be applied to the new DB management tests, not all tests. Use a more targeted approach (e.g., put it in `tests/test_db_management.py` only, or use a marker) if existing tests rely on the real storage directory.

**New test cases (add to new `tests/test_db_management.py`):**

1. `test_list_db_files` — create temp DB files, verify listing and sort order
2. `test_set_active_db` — switch DB, verify `get_active_db_name()` returns new name
3. `test_set_active_db_nonexistent` — verify switching to non-existent file raises `ValueError`
4. `test_set_active_db_path_traversal` — verify `../evil.db` is rejected
5. `test_create_new_db` — create with label, verify file exists with correct name pattern
6. `test_create_new_db_no_label` — create without label, verify `YYYY-MM-DD_HHMMSS.db` format
7. `test_rename_db` — rename, verify old files gone, new files exist
8. `test_rename_db_active` — rename the active DB, verify `_active_db_path` updated
9. `test_rename_db_non_active` — rename a non-active DB, verify `_active_db_path` unchanged
10. `test_rename_db_no_timestamp` — rename non-timestamped file, verify error
11. `test_rename_db_not_found` — rename non-existent file, verify error
12. `test_generate_db_filename` — test label sanitization edge cases
13. `test_get_db_connection_snapshot` — verify `get_db_connection()` uses snapshotted path (change `_active_db_path` mid-connection, verify connection is to original path)

**Route tests (optional, nice-to-have):**

If route tests are added later, they should cover:
- `GET /api/databases` — returns list with `active` field
- `POST /api/databases/active` — switches DB, returns 400 for missing file
- `POST /api/databases` — creates new DB, returns filename
- `PUT /api/databases/rename` — renames, returns 400 for invalid input
- `POST /api/optimize` with `dbTarget=new` — creates DB before running
- All mutation endpoints return 409 when optimization is running

**Existing test considerations:**
- `test_storage.py` and `test_stress_test.py` use `get_db_connection()` which reads `_active_db_path`. These tests should still work since they are not affected by the new mutable path — they create their own data and read it back.
- If interference is observed, add a targeted fixture to those test files that sets `_active_db_path` to a known test path before each test.

---

## API Endpoints (Complete)

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|--------------|----------|
| `GET` | `/api/databases` | List all DB files | — | `{databases: [{name, active}], active: "name"}` |
| `POST` | `/api/databases` | Create new DB | `{label?: "..."}` | `{filename, active}` |
| `POST` | `/api/databases/active` | Switch active DB | `{filename: "..."}` | `{active: "name"}` |
| `PUT` | `/api/databases/rename` | Rename any DB file | `{filename: "...", newLabel: "..."}` | `{filename, active}` |

---

## Safety & Edge Cases

| Concern | Mitigation |
|---------|------------|
| Path traversal (`../evil.db`) | `set_active_db()` and `rename_db()` validate parent dir equals `STORAGE_DIR` |
| Switch to non-existent DB | `set_active_db()` validates file exists; `create_new_db()` uses internal `_set_active_db_path()` which skips this check |
| Switch during running optimization | All mutation endpoints check optimization state, return 409 |
| WAL companion files on rename | `rename_db()` moves `.db`, `.db-wal`, `.db-shm` |
| Non-timestamped file rename | `rename_db()` raises `ValueError` if no timestamp prefix |
| Rename non-existent file | `rename_db()` raises `ValueError` if file not found |
| Rename non-active DB | `rename_db()` only updates `_active_db_path` if the renamed file was active |
| Thread-safety of `get_db_connection()` | Path snapshotted into local variable at function entry; passed through to `init_database()` |
| Concurrent tab state | Acceptable: single-user tool, last write wins |
| Stale study view after DB switch | `switchDatabase()` clears `ResultsState` study fields and calls `refreshResultsView()` |
| Empty storage dir on first run | `_pick_newest_db()` returns generated filename; `init_database()` creates file |
| Schema migration for old DBs | `init_database()` already runs `_ensure_columns()` on every init |
| Module-level function order | `_pick_newest_db()` and `_generate_db_filename()` defined before module-level call |

---

## UI Mockups (ASCII)

### Start Page — "Optimizer Run" section bottom

```
+-- Optimizer Run -----------------------------+
|                                             |
|  +-- Database Target ---------------------+ |
|  |  Save to  [2025-11-20_143052.db    v]  | |
|  |                                        | |
|  |  (When "Create new DB" selected:)      | |
|  |  Label    [link-15m_____________]      | |
|  +----------------------------------------+ |
|                                             |
|                    [Run Optimization]        |
|                                             |
+---------------------------------------------+
```

### Results Page — Left sidebar

```
+-- Sidebar ---------------------------+
|                                      |
| v Studies Manager                    |
| +----------------------------------+ |
| | Study: LINK 180d WFA             | |
| | Study: BTC optimization          | |
| +----------------------------------+ |
| [Select] [Delete]                    |
|                                      |
| > Database                           |  <- collapsed by default
|                                      |
| v Status & Controls                  |  <- v3: kept visible (not hidden)
| [Idle] [Pause] [Stop] [Cancel]       |
| Trial 0 / 0 (0%)                    |
|                                      |
| v Optuna Settings                    |
| ...                                  |
+--------------------------------------+
```

When Database section expanded:
```
| v Database                           |
| +----------------------------------+ |
| |>2025-11-20_143052.db             | |  <- green left border = .db-active
| | 2025-11-18_091200_link           | |  <- blue bg when clicked = .selected
| | 2025-11-15_080000.db             | |
| +----------------------------------+ |
| [Rename]                             |
```

---

## Execution Order

1. **Storage layer** (Step 1) — foundation, no UI impact yet
2. **API endpoints** (Step 2) — server can serve DB data
3. **Optimization payload** (Step 3) — runs can target specific DBs
4. **API JS functions** (Step 4) — frontend can call new endpoints
5. **Start page dropdown** (Step 5) — user can select DB before runs
6. **Results page section** (Step 6) — user can switch DBs while browsing
7. **CSS** (Step 7) — polish styling
8. **Tests** (Step 8) — verify everything works

Steps 4-7 can be partially parallelized (API functions are independent of HTML/CSS).

---

## Out of Scope

- Database deletion from UI (manual filesystem operation)
- Study counts or file sizes in DB list
- Cross-tab notification when DB switches
- Database file location outside `src/storage/`
- Auto-rename of legacy `studies.db`
- Create DB action on Results page (create is paired with Run on Start page)
