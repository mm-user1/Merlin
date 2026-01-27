# Phase 4: WFA Refactor - Comprehensive Implementation Plan


> **GPT-5.2 Fixed v2 (merged, full-length)**  
> This document is a corrected, merged replacement for `phase_4_wfa-refactor_plan_opus_v1.md`.  
> It keeps the original structure and detail, but fixes multiple plan-vs-codebase mismatches (Optuna field names, StressTest params handling, rank ordering, endpoint runtime integration, and time-slice correctness when Forward Test is enabled).  
> Normative keywords (**MUST/SHOULD/MAY**) are used with RFC 2119 meanings where applicable.


**Version**: v1.0
**Date**: 2026-01-25
**Target**: GPT 5.2 Codex Agent

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Requirements Summary](#2-requirements-summary)
3. [Current Architecture](#3-current-architecture)
4. [Database Schema Changes](#4-database-schema-changes)
5. [Backend Engine Changes](#5-backend-engine-changes)
6. [API Endpoint Changes](#6-api-endpoint-changes)
7. [Frontend Changes](#7-frontend-changes)
8. [Start Page Changes](#8-start-page-changes)
9. [Testing Requirements](#9-testing-requirements)
10. [Implementation Phases](#10-implementation-phases)

---

## 1. Executive Summary

### Goal

Refactor the Walk-Forward Analysis (WFA) module to display detailed results for each window with drill-down capability into intermediate module results (Optuna IS, DSR, Forward Test, Stress Test).

### Current State

- WFA stores only the "winning" trial per window
- Intermediate post-process results (DSR rankings, FT validation, ST robustness) are discarded
- No ability to inspect why a parameter set was selected
- Simple table showing only IS/OOS metrics per window

### Target State

- Store intermediate results from all enabled modules per window
- Expandable window rows with tabs for each module's trial table
- On-demand equity curve generation for any trial
- P/C (Pareto/Constraints) badges for selected window params
- Download trades for Window IS, OOS, or IS+OOS periods

### Key Design Decisions

| Decision | Choice |
|----------|--------|
| Window trials loading | On-demand (API call when expanding window) |
| OOS Test in WFA | No - mutually exclusive with WFA |
| Tab visibility | Only enabled modules shown |
| Equity curve storage | Only stitched OOS stored; others generated on-demand |
| P/C badges for Window rows | Yes - display from Optuna IS selected trial |
| P/C badges for Stitched OOS | Empty (aggregate row) |
| best_params_source display | Not shown in UI (skip for now) |

---

## 2. Requirements Summary

### Functional Requirements

#### 2.1 WFA Results Table Structure

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            [EQUITY CHART - Stitched OOS]                         │
└──────────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────────────┐
│ WFE: 78%  │  OOS Win Rate: 70% (7/10)  │  Windows: 10  │  Net: +45.2%  │ DD: -12%│
└──────────────────────────────────────────────────────────────────────────────────┘

╔══════════════════════════════════════════════════════════════════════════════════╗
║ Stitched OOS · 2025.06.15 - 2025.11.15                                           ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║ #  │ Param ID     │ P │ C │ WR%  │ Net%   │ DD%   │ Trades │ MaxCL │ Score │ ... ║
╠════╪══════════════╪═══╪═══╪══════╪════════╪═══════╪════════╪═══════╪═══════╪═════╣
║ -  │ Stitched OOS │ - │ - │ 58.2 │ +45.2  │ -12.3 │ 156    │ 4     │ -     │ ... ║
╚════╧══════════════╧═══╧═══╧══════╧════════╧═══════╧════════╧═══════╧═══════╧═════╝

╔══════════════════════════════════════════════════════════════════════════════════╗
║ ▶ Window 1 │ IS: 2025.01.01 - 2025.06.30 │ OOS: 2025.07.01 - 2025.08.31         ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║ #  │ Param ID     │ P │ C │ WR%  │ Net%   │ DD%   │ Trades │ MaxCL │ Score │ ... ║
╠════╪══════════════╪═══╪═══╪══════╪════════╪═══════╪════════╪═══════╪═══════╪═════╣
║    │ HMA 50 IS    │ ● │ ● │ 62.0 │ +23.4  │ -8.2  │ 45     │ 3     │ 1.85  │ ... ║
╠════╪══════════════╪═══╪═══╪══════╪════════╪═══════╪════════╪═══════╪═══════╪═════╣
║    │ HMA 50 OOS   │ ● │ ● │ 58.0 │ +12.1  │ -6.1  │ 18     │ 2     │ -     │ ... ║
╚════╧══════════════╧═══╧═══╧══════╧════════╧═══════╧════════╧═══════╧═══════╧═════╝

   ┌─── EXPANDED (on ▶ click) ───────────────────────────────────────────────────┐
   │                                                                              │
   │ [Optuna IS] [DSR] [Forward Test] [Stress Test]              ← tabs          │
   │                                                                              │
   │ ╔════════════════════════════════════════════════════════════════════════╗  │
   │ ║ Optuna IS · Sorted by composite score                                  ║  │
   │ ╠════════════════════════════════════════════════════════════════════════╣  │
   │ ║ # │ Param ID   │ P │ C │ WR%  │ Net%  │ DD%  │ Trades │ MaxCL │ Score  ║  │
   │ ╠═══╪════════════╪═══╪═══╪══════╪═══════╪══════╪════════╪═══════╪════════╣  │
   │ ║ 1 │ HMA 50     │ ● │ ● │ 62.0 │ +23.4 │ -8.2 │ 45     │ 3     │ 1.85   ║  │
   │ ║ 2 │ HMA 48     │ ● │ ● │ 61.2 │ +22.1 │ -7.9 │ 43     │ 3     │ 1.82   ║  │
   │ ║ 3 │ EMA 55     │   │ ● │ 59.8 │ +21.5 │ -9.1 │ 48     │ 4     │ 1.78   ║  │
   │ ╚═══╧════════════╧═══╧═══╧══════╧═══════╧══════╧════════╧═══════╧════════╝  │
   │                                                                              │
   └──────────────────────────────────────────────────────────────────────────────┘
```

#### 2.2 Interactivity

| Element | Action |
|---------|--------|
| "Stitched OOS" row | Show stitched OOS equity curve (stored) |
| Window header row | Show IS+OOS stitched curve for that window (generated on-demand) |
| Window IS row | Show IS equity curve (generated on-demand) |
| Window OOS row | Show OOS equity curve (generated on-demand) |
| Triangle ▶ | Expand/collapse module tabs section |
| Row inside module tab | Show equity curve for that trial (generated on-demand) |

#### 2.3 P and C Badges

- **Blue circle** (`dot-pareto`): Pareto optimal trial
- **Green circle** (`dot-ok`): Constraints satisfied
- **Red circle** (`dot-fail`): Constraints violated
- **Empty**: No badge (for Stitched OOS aggregate row)

**Badge display rules:**
- Stitched OOS row: P and C cells empty
- Window IS/OOS rows: Display P/C from the Optuna IS trial that was selected
- Module tabs (Optuna IS, DSR, etc.): Display P/C for each trial

#### 2.4 Module Tab Visibility

Only show tabs for modules that were enabled during WFA run:
- Order always: `[Optuna IS] → [DSR] → [Forward Test] → [Stress Test]`
- Disabled modules: Hidden (not shown as disabled tabs)

#### 2.5 Trades Download

Support downloading trades for:
- Stitched OOS (existing endpoint)
- Window N IS period
- Window N OOS period
- Window N IS+OOS combined

---

## 3. Current Architecture

### 3.1 File Structure

```
src/
├── core/
│   ├── walkforward_engine.py    # WFA orchestration
│   ├── storage.py               # Database operations
│   ├── post_process.py          # DSR, FT, ST modules
│   ├── metrics.py               # Metrics calculation
│   └── export.py                # Trade CSV export
├── ui/
│   ├── server.py                # Flask API
│   ├── static/
│   │   ├── js/
│   │   │   ├── results.js           # Results page logic
│   │   │   ├── api.js               # API client
│   │   │   ├── optuna-results-ui.js # Optuna trial rendering
│   │   │   └── post-process-ui.js   # Post-process UI helpers
│   │   └── css/
│   │       └── style.css            # Styles including dot badges
│   └── templates/
│       └── results.html             # Results page template
```

### 3.2 Current Data Structures

#### WindowResult (walkforward_engine.py:60-91)
```python
@dataclass
class WindowResult:
    window_id: int
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp

    best_params: Dict[str, Any]
    param_id: str

    # IS metrics
    is_net_profit_pct: float
    is_max_drawdown_pct: float
    is_total_trades: int

    # OOS metrics
    oos_net_profit_pct: float
    oos_max_drawdown_pct: float
    oos_total_trades: int

    # Equity curves
    oos_equity_curve: List[float]
    oos_timestamps: List[pd.Timestamp]

    # Optional
    is_best_trial_number: Optional[int] = None
    is_equity_curve: Optional[List[float]] = None
```

#### Post-Process Result Structures (post_process.py)

**DSRResult (lines 103-117):**
```python
@dataclass
class DSRResult:
    trial_number: int
    optuna_rank: int
    params: dict
    original_result: Any
    dsr_probability: Optional[float]
    dsr_rank: Optional[int] = None
    dsr_skewness: Optional[float] = None
    dsr_kurtosis: Optional[float] = None
    dsr_track_length: Optional[int] = None
    dsr_luck_share_pct: Optional[float] = None
```

**FTResult (lines 63-100):**
```python
@dataclass
class FTResult:
    trial_number: int
    source_rank: int
    params: dict

    # IS metrics
    is_net_profit_pct: float
    is_max_drawdown_pct: float
    is_total_trades: int
    is_win_rate: float
    is_max_consecutive_losses: int
    is_sharpe_ratio: Optional[float]
    is_romad: Optional[float]
    is_profit_factor: Optional[float]

    # FT metrics
    ft_net_profit_pct: float
    ft_max_drawdown_pct: float
    ft_total_trades: int
    ft_win_rate: float
    ft_max_consecutive_losses: int
    ft_sharpe_ratio: Optional[float]
    ft_sortino_ratio: Optional[float]
    ft_romad: Optional[float]
    ft_profit_factor: Optional[float]
    ft_ulcer_index: Optional[float]
    ft_sqn: Optional[float]
    ft_consistency_score: Optional[float]

    # Comparison
    profit_degradation: float
    max_dd_change: float
    romad_change: float
    sharpe_change: float
    pf_change: float

    ft_rank: Optional[int] = None
    rank_change: Optional[int] = None
```

**StressTestResult (lines 165-208):**
```python
@dataclass
class StressTestResult:
    trial_number: int
    source_rank: int
    status: str

    base_net_profit_pct: float
    base_max_drawdown_pct: float
    base_romad: Optional[float]
    base_sharpe_ratio: Optional[float]

    profit_retention: Optional[float]
    romad_retention: Optional[float]

    profit_worst: Optional[float]
    profit_lower_tail: Optional[float]
    profit_median: Optional[float]

    romad_worst: Optional[float]
    romad_lower_tail: Optional[float]
    romad_median: Optional[float]

    profit_failure_rate: Optional[float]
    romad_failure_rate: Optional[float]
    combined_failure_rate: float
    profit_failure_count: int
    romad_failure_count: int
    combined_failure_count: int
    total_perturbations: int
    failure_threshold: float

    param_worst_ratios: dict
    most_sensitive_param: Optional[str]

    st_rank: Optional[int] = None
    rank_change: Optional[int] = None
```

### 3.3 Current Database Schema

#### wfa_windows Table (storage.py:307-334)
```sql
CREATE TABLE IF NOT EXISTS wfa_windows (
    window_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    window_number INTEGER NOT NULL,

    best_params_json TEXT NOT NULL,
    param_id TEXT,

    is_start_date TEXT,
    is_end_date TEXT,
    is_net_profit_pct REAL,
    is_max_drawdown_pct REAL,
    is_total_trades INTEGER,
    is_best_trial_number INTEGER,
    is_equity_curve TEXT,

    oos_start_date TEXT,
    oos_end_date TEXT,
    oos_net_profit_pct REAL,
    oos_max_drawdown_pct REAL,
    oos_total_trades INTEGER,
    oos_equity_curve TEXT,

    wfe REAL,

    FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE,
    UNIQUE(study_id, window_number)
);
```

### 3.4 Current WFA Table Rendering (results.js:1578-1626)

```javascript
function renderWFATable(windows) {
  const tbody = document.querySelector('.data-table tbody');
  if (!tbody) return;

  tbody.innerHTML = '';

  const thead = document.querySelector('.data-table thead tr');
  if (thead) {
    thead.innerHTML = `
      <th>#</th>
      <th>Param ID</th>
      <th>IS Profit %</th>
      <th>OOS Profit %</th>
      <th>IS Trades</th>
      <th>OOS Trades</th>
      <th>OOS DD %</th>
    `;
  }

  (windows || []).forEach((window, index) => {
    const row = document.createElement('tr');
    row.className = 'clickable';
    row.dataset.index = index;
    row.dataset.windowNumber = window.window_number || index + 1;

    row.innerHTML = `
      <td class="rank">${window.window_number || index + 1}</td>
      <td class="param-hash">${window.param_id}</td>
      <td class="${window.is_net_profit_pct >= 0 ? 'val-positive' : 'val-negative'}">
        ${window.is_net_profit_pct >= 0 ? '+' : ''}${Number(window.is_net_profit_pct || 0).toFixed(2)}%
      </td>
      <td class="${window.oos_net_profit_pct >= 0 ? 'val-positive' : 'val-negative'}">
        ${window.oos_net_profit_pct >= 0 ? '+' : ''}${Number(window.oos_net_profit_pct || 0).toFixed(2)}%
      </td>
      <td>${window.is_total_trades ?? '-'}</td>
      <td>${window.oos_total_trades ?? '-'}</td>
      <td class="val-negative">-${Math.abs(Number(window.oos_max_drawdown_pct || 0)).toFixed(2)}%</td>
    `;

    row.addEventListener('click', async () => {
      const windowNumber = window.window_number || window.window_id || index + 1;
      selectTableRow(index, windowNumber);
      await showParameterDetails(window);
      setComparisonLine('');
    });

    tbody.appendChild(row);
  });
}
```

### 3.5 P/C Badge CSS (style.css:400-422)

```css
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid transparent;
  vertical-align: middle;
}

.dot-pareto {
  background: #4a90e2;
  border-color: #2f6fb2;
}

.dot-ok {
  background: #27ae60;
  border-color: #1e8a4c;
}

.dot-fail {
  background: #e74c3c;
  border-color: #c0392b;
}
```

---

## 4. Database Schema Changes


### 4.1 New Table: wfa_window_trials

Store intermediate results from each module for each window.

**Key rules**
- `trial_number` MUST refer to the **Optuna trial number** for identity across tabs.
  - Optuna: `OptimizationResult.optuna_trial_number`
  - DSR/FT/ST: `result.trial_number` already matches Optuna.
- `params_json` MUST be populated for every stored row.  
  - Stress Test results do not include params; you MUST attach params from the *source candidate list* by `trial_number`.

```sql
CREATE TABLE IF NOT EXISTS wfa_window_trials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Link back to the window (existing wfa_windows PK)
    window_id TEXT NOT NULL,                 -- FK to wfa_windows.window_id
    module_type TEXT NOT NULL,               -- 'optuna_is' | 'dsr' | 'forward_test' | 'stress_test'
    trial_number INTEGER NOT NULL,           -- Optuna trial number

    -- Params and identity
    params_json TEXT NOT NULL,               -- JSON dict of params (ST must be attached from source candidates)
    param_id TEXT,                           -- stable hash/label used across UI

    -- Ordering / provenance
    source_rank INTEGER,                     -- rank coming into this module (optuna rank -> dsr/ft/st)
    module_rank INTEGER,                     -- rank produced by this module (dsr_rank/ft_rank/st_rank or optuna row rank)

    -- Core metrics (shared display set)
    net_profit_pct REAL,
    max_drawdown_pct REAL,
    total_trades INTEGER,
    win_rate REAL,
    profit_factor REAL,
    romad REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    sqn REAL,
    ulcer_index REAL,
    consistency_score REAL,
    max_consecutive_losses INTEGER,

    -- Optuna/MO metadata (nullable for non-optuna modules)
    composite_score REAL,                    -- MUST store OptimizationResult.score (name kept for compatibility)
    objective_values_json TEXT,              -- JSON list[float]
    constraint_values_json TEXT,             -- JSON list[float]
    constraints_satisfied INTEGER,           -- 1/0/NULL (tri-state)
    is_pareto_optimal INTEGER,               -- 1/0/NULL (tri-state)
    dominance_rank INTEGER,                  -- int/NULL

    -- Stress test status (nullable elsewhere)
    status TEXT,                             -- e.g. 'ok' | 'skipped_bad_base'

    -- Selection tracking (per module stage)
    is_selected INTEGER DEFAULT 0,           -- 1 if selected as winner at that module stage

    -- Module-specific rich metrics in JSON (FT deltas, DSR stats, ST percentiles, etc.)
    module_metrics_json TEXT,

    created_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (window_id) REFERENCES wfa_windows(window_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_window
    ON wfa_window_trials(window_id);

CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_module
    ON wfa_window_trials(window_id, module_type);

CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_trial
    ON wfa_window_trials(window_id, trial_number);

CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_selected
    ON wfa_window_trials(window_id, module_type, is_selected);
```

**Why keep the column name `composite_score`?**  
Merlin already maps `composite_score -> score` when loading Optuna trials from DB. Keeping the name avoids churn while still storing the correct value (`OptimizationResult.score`).


### 4.2 Modifications to wfa_windows Table

The v1 plan focused on P/C badges plus extra metrics. v2 keeps that, **and adds required time-slice metadata** so equity/trades can be generated correctly when Forward Test is enabled.

#### 4.2.1 Selection + module metadata (NEW / corrected)

```sql
-- Selection chain and module availability/status
ALTER TABLE wfa_windows ADD COLUMN best_params_source TEXT;       -- 'optuna_is' | 'dsr' | 'forward_test' | 'stress_test'
ALTER TABLE wfa_windows ADD COLUMN available_modules TEXT;        -- JSON array of modules available for this window
ALTER TABLE wfa_windows ADD COLUMN module_status_json TEXT;       -- JSON object (enabled/ran/reason per module)
ALTER TABLE wfa_windows ADD COLUMN selection_chain_json TEXT;     -- JSON: {"optuna_is":120,"dsr":55,"forward_test":55,"stress_test":55}

-- Store how many trials were stored (0 means disabled)
ALTER TABLE wfa_windows ADD COLUMN store_top_n_trials INTEGER;

-- P/C badges for the *selected* Optuna trial (tri-state 1/0/NULL)
ALTER TABLE wfa_windows ADD COLUMN is_pareto_optimal INTEGER;
ALTER TABLE wfa_windows ADD COLUMN constraints_satisfied INTEGER;
```

#### 4.2.2 Time-slice metadata (REQUIRED for correctness)

When Forward Test is enabled, Optuna does not necessarily run on the full IS period.  
To render correct curves and to export trades by period, each window MUST store:

```sql
ALTER TABLE wfa_windows ADD COLUMN optimization_start_date TEXT;
ALTER TABLE wfa_windows ADD COLUMN optimization_end_date TEXT;

ALTER TABLE wfa_windows ADD COLUMN ft_start_date TEXT;
ALTER TABLE wfa_windows ADD COLUMN ft_end_date TEXT;

-- Optional but strongly recommended for date-axis charting without recomputation
ALTER TABLE wfa_windows ADD COLUMN is_timestamps_json TEXT;
ALTER TABLE wfa_windows ADD COLUMN oos_timestamps_json TEXT;
```

#### 4.2.3 Additional IS metrics for display (kept from v1)

```sql
ALTER TABLE wfa_windows ADD COLUMN is_win_rate REAL;
ALTER TABLE wfa_windows ADD COLUMN is_max_consecutive_losses INTEGER;
ALTER TABLE wfa_windows ADD COLUMN is_romad REAL;
ALTER TABLE wfa_windows ADD COLUMN is_sharpe_ratio REAL;
ALTER TABLE wfa_windows ADD COLUMN is_profit_factor REAL;
ALTER TABLE wfa_windows ADD COLUMN is_sqn REAL;
ALTER TABLE wfa_windows ADD COLUMN is_ulcer_index REAL;
ALTER TABLE wfa_windows ADD COLUMN is_consistency_score REAL;

-- Name kept for compatibility: stores OptimizationResult.score
ALTER TABLE wfa_windows ADD COLUMN is_composite_score REAL;
```

#### 4.2.4 Additional OOS metrics for display (kept from v1)

```sql
ALTER TABLE wfa_windows ADD COLUMN oos_win_rate REAL;
ALTER TABLE wfa_windows ADD COLUMN oos_max_consecutive_losses INTEGER;
ALTER TABLE wfa_windows ADD COLUMN oos_romad REAL;
ALTER TABLE wfa_windows ADD COLUMN oos_sharpe_ratio REAL;
ALTER TABLE wfa_windows ADD COLUMN oos_profit_factor REAL;
ALTER TABLE wfa_windows ADD COLUMN oos_sqn REAL;
ALTER TABLE wfa_windows ADD COLUMN oos_ulcer_index REAL;
ALTER TABLE wfa_windows ADD COLUMN oos_consistency_score REAL;
```

> **SQLite note:** SQLite does not support `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.  
> Use `PRAGMA table_info` checks before altering (see §4.4).

### 4.3 Complete Updated wfa_windows Schema

```sql
CREATE TABLE IF NOT EXISTS wfa_windows (
    window_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    window_number INTEGER NOT NULL,

    -- Best params
    best_params_json TEXT NOT NULL,
    param_id TEXT,
    best_params_source TEXT,           -- NEW: 'optuna_is', 'dsr', 'forward_test', 'stress_test'

    -- Pareto/Constraints from selected trial
    is_pareto_optimal INTEGER,         -- NEW
    constraints_satisfied INTEGER,     -- NEW

    -- Module availability
    available_modules TEXT,            -- NEW: JSON array
    store_top_n_trials INTEGER,        -- NEW

    -- IS period
    is_start_date TEXT,
    is_end_date TEXT,
    is_net_profit_pct REAL,
    is_max_drawdown_pct REAL,
    is_total_trades INTEGER,
    is_best_trial_number INTEGER,
    is_equity_curve TEXT,

    -- NEW: Additional IS metrics
    is_win_rate REAL,
    is_max_consecutive_losses INTEGER,
    is_romad REAL,
    is_sharpe_ratio REAL,
    is_profit_factor REAL,
    is_sqn REAL,
    is_ulcer_index REAL,
    is_consistency_score REAL,
    is_composite_score REAL,

    -- OOS period
    oos_start_date TEXT,
    oos_end_date TEXT,
    oos_net_profit_pct REAL,
    oos_max_drawdown_pct REAL,
    oos_total_trades INTEGER,
    oos_equity_curve TEXT,

    -- NEW: Additional OOS metrics
    oos_win_rate REAL,
    oos_max_consecutive_losses INTEGER,
    oos_romad REAL,
    oos_sharpe_ratio REAL,
    oos_profit_factor REAL,
    oos_sqn REAL,
    oos_ulcer_index REAL,
    oos_consistency_score REAL,

    -- WFE
    wfe REAL,

    FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE,
    UNIQUE(study_id, window_number)
);
```

### 4.4 Migration Strategy

**No migration required.** The existing database does not contain WFA studies with intermediate data. Create new tables/columns when the application starts. Use `IF NOT EXISTS` and `ALTER TABLE ... ADD COLUMN` with error handling for idempotency.

**Implementation in storage.py:**

```python
def _ensure_wfa_schema_updated(conn):
    # Ensure Phase 4 WFA schema is present.
    #
    # IMPORTANT:
    # - SQLite does NOT support "ADD COLUMN IF NOT EXISTS".
    # - Prefer PRAGMA table_info checks then ALTER TABLE ADD COLUMN.
    # - Keep tri-state booleans: store 1/0/NULL (do not coerce NULL to 0).
    cur = conn.cursor()

    # 1) Create new table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS wfa_window_trials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            window_id TEXT NOT NULL,
            module_type TEXT NOT NULL,
            trial_number INTEGER NOT NULL,
            params_json TEXT NOT NULL,
            param_id TEXT,
            source_rank INTEGER,
            module_rank INTEGER,
            net_profit_pct REAL,
            max_drawdown_pct REAL,
            total_trades INTEGER,
            win_rate REAL,
            profit_factor REAL,
            romad REAL,
            sharpe_ratio REAL,
            sortino_ratio REAL,
            sqn REAL,
            ulcer_index REAL,
            consistency_score REAL,
            max_consecutive_losses INTEGER,
            composite_score REAL,
            objective_values_json TEXT,
            constraint_values_json TEXT,
            constraints_satisfied INTEGER,
            is_pareto_optimal INTEGER,
            dominance_rank INTEGER,
            status TEXT,
            is_selected INTEGER DEFAULT 0,
            module_metrics_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (window_id) REFERENCES wfa_windows(window_id) ON DELETE CASCADE
        );
        """
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_window ON wfa_window_trials(window_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_module ON wfa_window_trials(window_id, module_type);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_trial ON wfa_window_trials(window_id, trial_number);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_wfa_window_trials_selected ON wfa_window_trials(window_id, module_type, is_selected);")

    # 2) Ensure wfa_windows has required columns (PRAGMA table_info)
    cur.execute("PRAGMA table_info(wfa_windows);")
    existing = {row[1] for row in cur.fetchall()}  # row[1] = column name

    def add_col(col_sql: str, col_name: str):
        if col_name not in existing:
            cur.execute(col_sql)

    # Selection + module metadata
    add_col("ALTER TABLE wfa_windows ADD COLUMN best_params_source TEXT;", "best_params_source")
    add_col("ALTER TABLE wfa_windows ADD COLUMN available_modules TEXT;", "available_modules")
    add_col("ALTER TABLE wfa_windows ADD COLUMN module_status_json TEXT;", "module_status_json")
    add_col("ALTER TABLE wfa_windows ADD COLUMN selection_chain_json TEXT;", "selection_chain_json")
    add_col("ALTER TABLE wfa_windows ADD COLUMN store_top_n_trials INTEGER;", "store_top_n_trials")

    # P/C badges (tri-state)
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_pareto_optimal INTEGER;", "is_pareto_optimal")
    add_col("ALTER TABLE wfa_windows ADD COLUMN constraints_satisfied INTEGER;", "constraints_satisfied")

    # Time-slice metadata
    add_col("ALTER TABLE wfa_windows ADD COLUMN optimization_start_date TEXT;", "optimization_start_date")
    add_col("ALTER TABLE wfa_windows ADD COLUMN optimization_end_date TEXT;", "optimization_end_date")
    add_col("ALTER TABLE wfa_windows ADD COLUMN ft_start_date TEXT;", "ft_start_date")
    add_col("ALTER TABLE wfa_windows ADD COLUMN ft_end_date TEXT;", "ft_end_date")

    # Optional timestamps
    add_col("ALTER TABLE wfa_windows ADD COLUMN is_timestamps_json TEXT;", "is_timestamps_json")
    add_col("ALTER TABLE wfa_windows ADD COLUMN oos_timestamps_json TEXT;", "oos_timestamps_json")

    conn.commit()
```

---

## 5. Backend Engine Changes

### 5.1 WFConfig Updates (walkforward_engine.py)

Add new parameter for controlling trial storage:

```python
@dataclass
class WFConfig:
    strategy_id: str
    is_period_days: int = 180
    oos_period_days: int = 60
    warmup_bars: int = 1000

    # Post-process configs
    post_process: Optional[PostProcessConfig] = None
    dsr_config: Optional[DSRConfig] = None
    stress_test_config: Optional[StressTestConfig] = None

    # NEW: Trial storage limit
    store_top_n_trials: int = 100  # Per window, per module
```

### 5.2 WindowResult Updates (walkforward_engine.py)

Extend to include intermediate module results and P/C badges:

```python
@dataclass
class WindowResult:
    window_id: int
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp

    best_params: Dict[str, Any]
    param_id: str

    # IS metrics
    is_net_profit_pct: float
    is_max_drawdown_pct: float
    is_total_trades: int

    # OOS metrics
    oos_net_profit_pct: float
    oos_max_drawdown_pct: float
    oos_total_trades: int

    # Equity curves
    oos_equity_curve: List[float]
    oos_timestamps: List[pd.Timestamp]

    # Optional IS details
    is_best_trial_number: Optional[int] = None
    is_equity_curve: Optional[List[float]] = None

    # NEW: P/C badges from selected trial
    is_pareto_optimal: Optional[bool] = None
    constraints_satisfied: Optional[bool] = None

    # NEW: Source of best params
    best_params_source: str = "optuna_is"  # 'optuna_is', 'dsr', 'forward_test', 'stress_test'

    # NEW: Available modules for this window
    available_modules: List[str] = field(default_factory=list)

    # NEW: Intermediate results (for storage)
    optuna_is_trials: Optional[List[Dict]] = None
    dsr_trials: Optional[List[Dict]] = None
    forward_test_trials: Optional[List[Dict]] = None
    stress_test_trials: Optional[List[Dict]] = None

    # NEW: Additional IS metrics
    is_win_rate: Optional[float] = None
    is_max_consecutive_losses: Optional[int] = None
    is_romad: Optional[float] = None
    is_sharpe_ratio: Optional[float] = None
    is_profit_factor: Optional[float] = None
    is_sqn: Optional[float] = None
    is_ulcer_index: Optional[float] = None
    is_consistency_score: Optional[float] = None
    is_composite_score: Optional[float] = None

    # NEW: Additional OOS metrics
    oos_win_rate: Optional[float] = None
    oos_max_consecutive_losses: Optional[int] = None
    oos_romad: Optional[float] = None
    oos_sharpe_ratio: Optional[float] = None
    oos_profit_factor: Optional[float] = None
    oos_sqn: Optional[float] = None
    oos_ulcer_index: Optional[float] = None
    oos_consistency_score: Optional[float] = None
```

### 5.3 Pipeline Refactoring (walkforward_engine.py)

The key change is capturing intermediate results from each module instead of just the best selection.

**Current flow (simplified):**
```python
# Lines 340-464 in walkforward_engine.py
optuna_results = self._run_optuna_on_window(...)
best_result = optuna_results[0]  # Top by composite score

if dsr_enabled:
    dsr_results = run_dsr(optuna_results, ...)
    best_result = dsr_results[0]  # Discard others

if ft_enabled:
    ft_results = run_forward_test(best_result, ...)  # Only runs on best
    best_result = ft_results[0]

if st_enabled:
    st_results = run_stress_test(best_result, ...)
    best_result = st_results[0]
```

**New flow:**
```python
def _process_window_with_modules(self, window_split, ...):
    """Process a single WFA window, capturing all intermediate results."""

    available_modules = ["optuna_is"]  # Always have Optuna IS

    # 1. Run Optuna optimization
    optuna_results = self._run_optuna_on_window(...)

    # Convert to storable format (top N trials)
    optuna_is_trials = self._convert_optuna_results_for_storage(
        optuna_results,
        limit=self.config.store_top_n_trials
    )

    # Track best result and source
    best_result = optuna_results[0]
    best_params_source = "optuna_is"

    # Get P/C from best Optuna trial
    is_pareto_optimal = getattr(best_result, 'is_pareto_optimal', None)
    constraints_satisfied = getattr(best_result, 'constraints_satisfied', None)

    # Mark selected trial
    if optuna_is_trials:
        optuna_is_trials[0]['is_selected'] = True

    # 2. DSR (if enabled)
    dsr_trials = None
    if self.config.dsr_config and self.config.dsr_config.enabled:
        available_modules.append("dsr")

        dsr_results = run_dsr(
            optuna_results,
            self.config.dsr_config,
            ...
        )

        dsr_trials = self._convert_dsr_results_for_storage(dsr_results)

        if dsr_results:
            best_result = dsr_results[0].original_result
            best_params_source = "dsr"
            dsr_trials[0]['is_selected'] = True

    # 3. Forward Test (if enabled)
    ft_trials = None
    if self.config.post_process and self.config.post_process.ft_enabled:
        available_modules.append("forward_test")

        # Run FT on top K candidates from previous stage
        candidates = self._get_top_k_candidates(best_result, previous_results, k=ft_top_k)

        ft_results = run_forward_test(
            candidates,
            self.config.post_process,
            ...
        )

        ft_trials = self._convert_ft_results_for_storage(ft_results)

        if ft_results:
            best_result = ft_results[0]
            best_params_source = "forward_test"
            ft_trials[0]['is_selected'] = True

    # 4. Stress Test (if enabled)
    st_trials = None
    if self.config.stress_test_config and self.config.stress_test_config.enabled:
        available_modules.append("stress_test")

        candidates = self._get_top_k_candidates(best_result, previous_results, k=st_top_k)

        st_results = run_stress_test(
            candidates,
            self.config.stress_test_config,
            ...
        )

        st_trials = self._convert_st_results_for_storage(st_results)

        if st_results:
            best_result = st_results[0]
            best_params_source = "stress_test"
            st_trials[0]['is_selected'] = True

    # 5. Run IS and OOS backtests with best params
    is_result = self._run_backtest_on_period(best_params, is_period, ...)
    oos_result = self._run_backtest_on_period(best_params, oos_period, ...)

    # 6. Build WindowResult with all data
    return WindowResult(
        window_id=window_split.window_id,
        is_start=window_split.is_start,
        is_end=window_split.is_end,
        oos_start=window_split.oos_start,
        oos_end=window_split.oos_end,

        best_params=best_params,
        param_id=self._create_param_id(best_params),
        best_params_source=best_params_source,

        is_pareto_optimal=is_pareto_optimal,
        constraints_satisfied=constraints_satisfied,

        available_modules=available_modules,

        # IS metrics
        is_net_profit_pct=is_result.net_profit_pct,
        is_max_drawdown_pct=is_result.max_drawdown_pct,
        is_total_trades=is_result.total_trades,
        is_win_rate=is_result.win_rate,
        is_max_consecutive_losses=is_result.max_consecutive_losses,
        is_romad=is_result.romad,
        is_sharpe_ratio=is_result.sharpe_ratio,
        is_profit_factor=is_result.profit_factor,
        is_sqn=is_result.sqn,
        is_ulcer_index=is_result.ulcer_index,
        is_consistency_score=is_result.consistency_score,
        is_composite_score=getattr(best_result, 'composite_score', None),

        # OOS metrics
        oos_net_profit_pct=oos_result.net_profit_pct,
        oos_max_drawdown_pct=oos_result.max_drawdown_pct,
        oos_total_trades=oos_result.total_trades,
        oos_win_rate=oos_result.win_rate,
        oos_max_consecutive_losses=oos_result.max_consecutive_losses,
        oos_romad=oos_result.romad,
        oos_sharpe_ratio=oos_result.sharpe_ratio,
        oos_profit_factor=oos_result.profit_factor,
        oos_sqn=oos_result.sqn,
        oos_ulcer_index=oos_result.ulcer_index,
        oos_consistency_score=oos_result.consistency_score,

        # Equity curves
        oos_equity_curve=oos_result.equity_curve,
        oos_timestamps=oos_result.timestamps,
        is_equity_curve=is_result.equity_curve,

        best_trial_number=getattr(best_result, 'optuna_trial_number', None) or getattr(best_result, 'trial_number', None),

        is_best_trial_number=best_trial_number,

        # Intermediate results for storage
        optuna_is_trials=optuna_is_trials,
        dsr_trials=dsr_trials,
        forward_test_trials=ft_trials,
        stress_test_trials=st_trials,
    )
```

### 5.4 Result Conversion Functions

These converters MUST align with the actual dataclasses in Merlin:
- `OptimizationResult.score` and `OptimizationResult.optuna_trial_number` (not `composite_score` / `trial_number`).
- `StressTestResult` has no params, so params MUST be attached from source candidates by `trial_number`.

```python
def _convert_optuna_results_for_storage(self, results: List, limit: int) -> List[Dict]:
    # Convert Optuna OptimizationResult rows to storage format.
    trials = []
    for i, result in enumerate(results[:limit]):
        trial_number = getattr(result, "optuna_trial_number", None)
        if trial_number is None:
            trial_number = i

        params = getattr(result, "params", {}) or {}
        trials.append({
            "trial_number": trial_number,
            "params": params,
            "param_id": self._create_param_id(params),

            "net_profit_pct": getattr(result, "net_profit_pct", None),
            "max_drawdown_pct": getattr(result, "max_drawdown_pct", None),
            "total_trades": getattr(result, "total_trades", None),
            "win_rate": getattr(result, "win_rate", None),
            "profit_factor": getattr(result, "profit_factor", None),
            "romad": getattr(result, "romad", None),
            "max_consecutive_losses": getattr(result, "max_consecutive_losses", None),
            "sharpe_ratio": getattr(result, "sharpe_ratio", None),
            "sortino_ratio": getattr(result, "sortino_ratio", None),
            "sqn": getattr(result, "sqn", None),
            "ulcer_index": getattr(result, "ulcer_index", None),
            "consistency_score": getattr(result, "consistency_score", None),

            # DB column name kept for compatibility, but value MUST be OptimizationResult.score
            "composite_score": getattr(result, "score", None),

            "objective_values": getattr(result, "objective_values", []) or [],
            "constraint_values": getattr(result, "constraint_values", []) or [],
            "constraints_satisfied": getattr(result, "constraints_satisfied", None),
            "is_pareto_optimal": getattr(result, "is_pareto_optimal", None),
            "dominance_rank": getattr(result, "dominance_rank", None),
        })
    return trials


def _convert_dsr_results_for_storage(self, results: List, limit: int) -> List[Dict]:
    # Convert DSRResult rows to storage format (preserve Optuna identity).
    trials = []
    for result in results[:limit]:
        original = getattr(result, "original_result", None)
        params = getattr(result, "params", {}) or {}

        trials.append({
            "trial_number": getattr(result, "trial_number", None),
            "params": params,
            "param_id": self._create_param_id(params),

            "net_profit_pct": getattr(original, "net_profit_pct", None) if original else getattr(result, "net_profit_pct", None),
            "max_drawdown_pct": getattr(original, "max_drawdown_pct", None) if original else getattr(result, "max_drawdown_pct", None),
            "total_trades": getattr(original, "total_trades", None) if original else getattr(result, "total_trades", None),
            "win_rate": getattr(original, "win_rate", None) if original else getattr(result, "win_rate", None),
            "profit_factor": getattr(original, "profit_factor", None) if original else getattr(result, "profit_factor", None),
            "romad": getattr(original, "romad", None) if original else getattr(result, "romad", None),
            "max_consecutive_losses": getattr(original, "max_consecutive_losses", None) if original else getattr(result, "max_consecutive_losses", None),
            "sharpe_ratio": getattr(original, "sharpe_ratio", None) if original else getattr(result, "sharpe_ratio", None),
            "sortino_ratio": getattr(original, "sortino_ratio", None) if original else getattr(result, "sortino_ratio", None),
            "sqn": getattr(original, "sqn", None) if original else getattr(result, "sqn", None),
            "ulcer_index": getattr(original, "ulcer_index", None) if original else getattr(result, "ulcer_index", None),
            "consistency_score": getattr(original, "consistency_score", None) if original else getattr(result, "consistency_score", None),
            "composite_score": getattr(original, "score", None) if original else getattr(result, "score", None),

            "is_pareto_optimal": getattr(original, "is_pareto_optimal", None) if original else None,
            "constraints_satisfied": getattr(original, "constraints_satisfied", None) if original else None,
            "objective_values": getattr(original, "objective_values", []) if original else [],
            "constraint_values": getattr(original, "constraint_values", []) if original else [],
            "dominance_rank": getattr(original, "dominance_rank", None) if original else None,

            "source_rank": getattr(result, "optuna_rank", None),
            "module_rank": getattr(result, "dsr_rank", None),

            "module_metrics": {
                "dsr_probability": getattr(result, "dsr_probability", None),
                "track_length": getattr(result, "track_length", None),
                "luck_share_pct": getattr(result, "luck_share_pct", None),
                "skewness": getattr(result, "skewness", None),
                "kurtosis": getattr(result, "kurtosis", None),
            },
        })
    return trials


def _convert_ft_results_for_storage(self, results: List, limit: int) -> List[Dict]:
    # Convert FTResult rows to storage format (primary display metrics are FT slice).
    trials = []
    for result in results[:limit]:
        params = getattr(result, "params", {}) or {}
        trials.append({
            "trial_number": getattr(result, "trial_number", None),
            "params": params,
            "param_id": self._create_param_id(params),

            "net_profit_pct": getattr(result, "ft_net_profit_pct", None),
            "max_drawdown_pct": getattr(result, "ft_max_drawdown_pct", None),
            "total_trades": getattr(result, "ft_total_trades", None),
            "win_rate": getattr(result, "ft_win_rate", None),
            "profit_factor": getattr(result, "ft_profit_factor", None),
            "romad": getattr(result, "ft_romad", None),
            "max_consecutive_losses": getattr(result, "ft_max_consecutive_losses", None),
            "sharpe_ratio": getattr(result, "ft_sharpe_ratio", None),
            "sortino_ratio": getattr(result, "ft_sortino_ratio", None),
            "sqn": getattr(result, "ft_sqn", None),
            "ulcer_index": getattr(result, "ft_ulcer_index", None),
            "consistency_score": getattr(result, "ft_consistency_score", None),

            "source_rank": getattr(result, "source_rank", None),
            "module_rank": getattr(result, "ft_rank", None),

            "module_metrics": {
                "is_net_profit_pct": getattr(result, "is_net_profit_pct", None),
                "is_max_drawdown_pct": getattr(result, "is_max_drawdown_pct", None),
                "profit_delta": getattr(result, "profit_delta", None),
                "drawdown_delta": getattr(result, "drawdown_delta", None),
                "stability_score": getattr(result, "stability_score", None),
            },
        })
    return trials


def _convert_st_results_for_storage(self, results: List, limit: int, trial_to_params: Dict[int, Dict]) -> List[Dict]:
    # Convert StressTestResult rows to storage format.
    # IMPORTANT: StressTestResult has no params; attach from source candidates.
    trials = []
    for result in results[:limit]:
        tn = getattr(result, "trial_number", None)
        params = trial_to_params.get(tn) or {}
        trials.append({
            "trial_number": tn,
            "params": params,
            "param_id": self._create_param_id(params),

            "net_profit_pct": getattr(result, "base_net_profit_pct", None),
            "max_drawdown_pct": getattr(result, "base_max_drawdown_pct", None),
            "romad": getattr(result, "base_romad", None),
            "sharpe_ratio": getattr(result, "base_sharpe_ratio", None),

            "source_rank": getattr(result, "source_rank", None),
            "module_rank": getattr(result, "st_rank", None),
            "status": getattr(result, "status", None),

            "module_metrics": {
                "profit_retention": getattr(result, "profit_retention", None),
                "romad_retention": getattr(result, "romad_retention", None),
                "profit_worst": getattr(result, "profit_worst", None),
                "profit_lower_tail": getattr(result, "profit_lower_tail", None),
                "profit_median": getattr(result, "profit_median", None),
                "romad_worst": getattr(result, "romad_worst", None),
                "romad_lower_tail": getattr(result, "romad_lower_tail", None),
                "romad_median": getattr(result, "romad_median", None),
                "profit_failure_rate": getattr(result, "profit_failure_rate", None),
                "romad_failure_rate": getattr(result, "romad_failure_rate", None),
            },
        })
    return trials
```

**Storage note:** when writing to DB, dump `objective_values`, `constraint_values`, and `module_metrics` as JSON strings.


## 6. API Endpoint Changes

### 6.1 Storage Functions (storage.py)

#### 6.1.1 Update save_wfa_study_to_db()

Extend to save window trials:

```python
def save_wfa_study_to_db(
    wf_result: WFResult,
    config: Dict,
    csv_file_path: str,
    start_time: float,
    score_config: Optional[Dict] = None,
) -> str:
    """Save WFA study with intermediate module results."""

    # ... existing study save logic ...

    # Ensure schema is updated
    _ensure_wfa_schema_updated(conn)

    # Save windows with new columns
    for window in wf_result.windows:
        window_id = f"{study_id}_w{window.window_id}"

        cursor.execute("""
            INSERT INTO wfa_windows (
                window_id, study_id, window_number,
                best_params_json, param_id, best_params_source,
                is_pareto_optimal, constraints_satisfied,
                available_modules, store_top_n_trials,

                is_start_date, is_end_date,
                is_net_profit_pct, is_max_drawdown_pct, is_total_trades,
                is_best_trial_number, is_equity_curve,
                is_win_rate, is_max_consecutive_losses, is_romad,
                is_sharpe_ratio, is_profit_factor, is_sqn,
                is_ulcer_index, is_consistency_score, is_composite_score,

                oos_start_date, oos_end_date,
                oos_net_profit_pct, oos_max_drawdown_pct, oos_total_trades,
                oos_equity_curve,
                oos_win_rate, oos_max_consecutive_losses, oos_romad,
                oos_sharpe_ratio, oos_profit_factor, oos_sqn,
                oos_ulcer_index, oos_consistency_score,

                wfe
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            window_id,
            study_id,
            window.window_id,
            json.dumps(window.best_params),
            window.param_id,
            window.best_params_source,
            1 if window.is_pareto_optimal else 0 if window.is_pareto_optimal is not None else None,
            1 if window.constraints_satisfied else 0 if window.constraints_satisfied is not None else None,
            json.dumps(window.available_modules),
            wf_result.config.store_top_n_trials,

            _format_date(window.is_start),
            _format_date(window.is_end),
            window.is_net_profit_pct,
            window.is_max_drawdown_pct,
            window.is_total_trades,
            window.is_best_trial_number,
            json.dumps(list(window.is_equity_curve)) if window.is_equity_curve else None,
            window.is_win_rate,
            window.is_max_consecutive_losses,
            window.is_romad,
            window.is_sharpe_ratio,
            window.is_profit_factor,
            window.is_sqn,
            window.is_ulcer_index,
            window.is_consistency_score,
            window.is_composite_score,

            _format_date(window.oos_start),
            _format_date(window.oos_end),
            window.oos_net_profit_pct,
            window.oos_max_drawdown_pct,
            window.oos_total_trades,
            json.dumps(list(window.oos_equity_curve)) if window.oos_equity_curve else None,
            window.oos_win_rate,
            window.oos_max_consecutive_losses,
            window.oos_romad,
            window.oos_sharpe_ratio,
            window.oos_profit_factor,
            window.oos_sqn,
            window.oos_ulcer_index,
            window.oos_consistency_score,

            None,  # wfe per-window not used
        ))

        # Save window trials for each module
        _save_window_trials(conn, window_id, "optuna_is", window.optuna_is_trials)
        _save_window_trials(conn, window_id, "dsr", window.dsr_trials)
        _save_window_trials(conn, window_id, "forward_test", window.forward_test_trials)
        _save_window_trials(conn, window_id, "stress_test", window.stress_test_trials)

    conn.commit()
    return study_id


def _save_window_trials(conn, window_id: str, module_type: str, trials: Optional[List[Dict]]):
    """Save trials for a specific module in a window."""
    if not trials:
        return

    cursor = conn.cursor()

    for trial in trials:
        cursor.execute("""
            INSERT INTO wfa_window_trials (
                window_id, module_type, trial_number,
                params_json, param_id,

                net_profit_pct, max_drawdown_pct, total_trades,
                win_rate, profit_factor, romad,
                max_consecutive_losses, sharpe_ratio, sqn,
                ulcer_index, consistency_score,

                composite_score, is_pareto_optimal, constraints_satisfied,
                objective_values,

                dsr_probability, dsr_rank, dsr_skewness,
                dsr_kurtosis, dsr_track_length, dsr_luck_share_pct,

                ft_net_profit_pct, ft_max_drawdown_pct, ft_total_trades,
                ft_win_rate, ft_romad, ft_sharpe_ratio, ft_profit_factor,
                profit_degradation, ft_rank,

                st_status, profit_retention, romad_retention,
                profit_failure_rate, romad_failure_rate, combined_failure_rate,
                most_sensitive_param, st_rank,

                is_selected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            window_id,
            module_type,
            trial.get('trial_number'),
            json.dumps(trial.get('params', {})),
            trial.get('param_id'),

            trial.get('net_profit_pct'),
            trial.get('max_drawdown_pct'),
            trial.get('total_trades'),
            trial.get('win_rate'),
            trial.get('profit_factor'),
            trial.get('romad'),
            trial.get('max_consecutive_losses'),
            trial.get('sharpe_ratio'),
            trial.get('sqn'),
            trial.get('ulcer_index'),
            trial.get('consistency_score'),

            trial.get('composite_score'),
            1 if trial.get('is_pareto_optimal') else 0 if trial.get('is_pareto_optimal') is not None else None,
            1 if trial.get('constraints_satisfied') else 0 if trial.get('constraints_satisfied') is not None else None,
            json.dumps(trial.get('objective_values')) if trial.get('objective_values') else None,

            trial.get('dsr_probability'),
            trial.get('dsr_rank'),
            trial.get('dsr_skewness'),
            trial.get('dsr_kurtosis'),
            trial.get('dsr_track_length'),
            trial.get('dsr_luck_share_pct'),

            trial.get('ft_net_profit_pct'),
            trial.get('ft_max_drawdown_pct'),
            trial.get('ft_total_trades'),
            trial.get('ft_win_rate'),
            trial.get('ft_romad'),
            trial.get('ft_sharpe_ratio'),
            trial.get('ft_profit_factor'),
            trial.get('profit_degradation'),
            trial.get('ft_rank'),

            trial.get('st_status'),
            trial.get('profit_retention'),
            trial.get('romad_retention'),
            trial.get('profit_failure_rate'),
            trial.get('romad_failure_rate'),
            trial.get('combined_failure_rate'),
            trial.get('most_sensitive_param'),
            trial.get('st_rank'),

            1 if trial.get('is_selected') else 0,
        ))
```

#### 6.1.2 Add load_wfa_window_trials()

```python
def load_wfa_window_trials(window_id: str) -> Dict[str, List[Dict]]:
    # Load intermediate trials for a WFA window.
    #
    # Ordering rules:
    # - Rank-based modules (dsr/forward_test/stress_test): rank 1 is best -> ASC
    # - optuna_is: prefer module_rank ASC if stored; otherwise fallback to composite_score DESC
    # - Avoid relying on NULLS LAST (SQLite version-dependent); use (col IS NULL) pattern.
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            module_type,
            trial_number,
            params_json,
            param_id,
            source_rank,
            module_rank,
            net_profit_pct, max_drawdown_pct, total_trades, win_rate,
            profit_factor, romad, sharpe_ratio, sortino_ratio, sqn, ulcer_index,
            consistency_score, max_consecutive_losses,
            composite_score,
            objective_values_json, constraint_values_json,
            constraints_satisfied, is_pareto_optimal, dominance_rank,
            status,
            is_selected,
            module_metrics_json
        FROM wfa_window_trials
        WHERE window_id = ?
        ORDER BY
            (module_type IS NULL), module_type ASC,
            (module_rank IS NULL), module_rank ASC,
            (source_rank IS NULL), source_rank ASC,
            (composite_score IS NULL), composite_score DESC,
            trial_number ASC
        """,
        (window_id,),
    )

    rows = cur.fetchall()
    conn.close()

    grouped: Dict[str, List[Dict]] = {"optuna_is": [], "dsr": [], "forward_test": [], "stress_test": []}

    for r in rows:
        (module_type, trial_number, params_json, param_id, source_rank, module_rank,
         net_profit_pct, max_drawdown_pct, total_trades, win_rate,
         profit_factor, romad, sharpe_ratio, sortino_ratio, sqn, ulcer_index,
         consistency_score, max_consecutive_losses,
         composite_score,
         objective_values_json, constraint_values_json,
         constraints_satisfied, is_pareto_optimal, dominance_rank,
         status, is_selected, module_metrics_json) = r

        trial = {
            "trial_number": trial_number,
            "param_id": param_id,
            "params": json.loads(params_json) if params_json else {},
            "source_rank": source_rank,
            "module_rank": module_rank,
            "net_profit_pct": net_profit_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "romad": romad,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "sqn": sqn,
            "ulcer_index": ulcer_index,
            "consistency_score": consistency_score,
            "max_consecutive_losses": max_consecutive_losses,
            "composite_score": composite_score,
            "score": composite_score,
            "objective_values": json.loads(objective_values_json) if objective_values_json else [],
            "constraint_values": json.loads(constraint_values_json) if constraint_values_json else [],
            # Preserve tri-state: None stays None
            "constraints_satisfied": constraints_satisfied if constraints_satisfied is None else bool(constraints_satisfied),
            "is_pareto_optimal": is_pareto_optimal if is_pareto_optimal is None else bool(is_pareto_optimal),
            "dominance_rank": dominance_rank,
            "status": status,
            "is_selected": bool(is_selected),
            "module_metrics": json.loads(module_metrics_json) if module_metrics_json else {},
        }
        grouped.setdefault(module_type, []).append(trial)

    return grouped
```

### 6.2 New API Endpoints (server.py)

#### 6.2.1 GET /api/studies/<study_id>/wfa/windows/<window_number>

Get detailed window data with all module trials:

```python
@app.get("/api/studies/<string:study_id>/wfa/windows/<int:window_number>")
def get_wfa_window_endpoint(study_id: str, window_number: int) -> object:
    # Get detailed WFA window data including module trials and period metadata.
    study_data = load_study_from_db(study_id)
    if not study_data:
        return jsonify({"error": "Study not found"}), HTTPStatus.NOT_FOUND

    study = study_data["study"]
    if study.get("optimization_mode") != "wfa":
        return jsonify({"error": "Not a WFA study"}), HTTPStatus.BAD_REQUEST

    windows = study_data.get("windows") or []
    window = next((w for w in windows if int(w.get("window_number", -1)) == window_number), None)
    if not window:
        return jsonify({"error": "Window not found"}), HTTPStatus.NOT_FOUND

    window_id = window.get("window_id") or f"{study_id}_w{window_number}"

    # Load module trials (may be empty for legacy studies)
    modules = load_wfa_window_trials(window_id)

    def parse_json_field(val):
        if val is None:
            return None
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return None
        return None

    def tri_bool(val):
        if val is None:
            return None
        return bool(val)

    return jsonify({
        "window": {
            "window_number": window_number,
            "window_id": window_id,

            "is_start_date": window.get("is_start_date"),
            "is_end_date": window.get("is_end_date"),
            "oos_start_date": window.get("oos_start_date"),
            "oos_end_date": window.get("oos_end_date"),

            # NEW: time-slice metadata
            "optimization_start_date": window.get("optimization_start_date"),
            "optimization_end_date": window.get("optimization_end_date"),
            "ft_start_date": window.get("ft_start_date"),
            "ft_end_date": window.get("ft_end_date"),

            # Selected params for the window
            "best_params": window.get("best_params"),
            "param_id": window.get("param_id"),
            "best_params_source": window.get("best_params_source") or "optuna_is",

            # P/C badges (tri-state)
            "is_pareto_optimal": tri_bool(window.get("is_pareto_optimal")),
            "constraints_satisfied": tri_bool(window.get("constraints_satisfied")),

            # Metadata for UI
            "available_modules": parse_json_field(window.get("available_modules")) or ["optuna_is"],
            "module_status": parse_json_field(window.get("module_status_json")),
            "selection_chain": parse_json_field(window.get("selection_chain_json")),

            # Metrics
            "is_metrics": {
                "net_profit_pct": window.get("is_net_profit_pct"),
                "max_drawdown_pct": window.get("is_max_drawdown_pct"),
                "total_trades": window.get("is_total_trades"),
                "win_rate": window.get("is_win_rate"),
                "max_consecutive_losses": window.get("is_max_consecutive_losses"),
                "romad": window.get("is_romad"),
                "sharpe_ratio": window.get("is_sharpe_ratio"),
                "profit_factor": window.get("is_profit_factor"),
                "sqn": window.get("is_sqn"),
                "ulcer_index": window.get("is_ulcer_index"),
                "consistency_score": window.get("is_consistency_score"),
                "composite_score": window.get("is_composite_score"),
            },
            "oos_metrics": {
                "net_profit_pct": window.get("oos_net_profit_pct"),
                "max_drawdown_pct": window.get("oos_max_drawdown_pct"),
                "total_trades": window.get("oos_total_trades"),
                "win_rate": window.get("oos_win_rate"),
                "max_consecutive_losses": window.get("oos_max_consecutive_losses"),
                "romad": window.get("oos_romad"),
                "sharpe_ratio": window.get("oos_sharpe_ratio"),
                "profit_factor": window.get("oos_profit_factor"),
                "sqn": window.get("oos_sqn"),
                "ulcer_index": window.get("oos_ulcer_index"),
                "consistency_score": window.get("oos_consistency_score"),
            },
        },
        "modules": modules,
    })
```

#### 6.2.2 POST /api/studies/<study_id>/wfa/windows/<window_number>/equity

Returns equity curve + timestamps for a **selected module trial** inside a WFA window.

**Request (JSON)**  
Accept both camelCase and snake_case keys:

```json
{
  "moduleType": "optuna_is | dsr | forward_test | stress_test | oos_result",
  "trialNumber": 120,
  "period": "optuna_is | is | ft | oos | both"
}
```

**Rules**
- `moduleType` and `trialNumber` MUST be provided for module tabs.
- For "OOS Result" row, you MAY omit `trialNumber` and use the window's `best_params`, but the v2 default is to require it for consistency.
- Period meaning:
  - `optuna_is`: `optimization_start_date` -> `optimization_end_date`
  - `is`: `is_start_date` -> `is_end_date`
  - `ft`: `ft_start_date` -> `ft_end_date`
  - `oos`: `oos_start_date` -> `oos_end_date`
  - `both`: `is_start_date` -> `oos_end_date`

**Response**
```json
{
  "equity_curve": [1000.0, 1005.2, 998.1],
  "timestamps": ["2025-01-01T00:00:00", "2025-01-02T00:00:00"]
}
```


#### 6.2.3 POST /api/studies/<study_id>/wfa/windows/<window_number>/trades

Downloads trades CSV for a **selected module trial** inside a WFA window.

**Request (JSON)**

```json
{
  "moduleType": "optuna_is | dsr | forward_test | stress_test | oos_result",
  "trialNumber": 120,
  "period": "optuna_is | is | ft | oos | both"
}
```

**Response**
- CSV file download (`text/csv`) via existing `export_trades_csv(...)`.

**Implementation note**
This endpoint MUST mirror the existing `/api/studies/<id>/wfa/trades` runtime pattern:
- Load CSV
- align date bounds
- warmup prep
- `strategy_class.run(...)`
- filter trades to requested period


### 6.3 Update /api/walkforward Endpoint

Add `store_top_n_trials` parameter:

```python
# In /api/walkforward handler, add to WFConfig creation:
store_top_n_trials = int(request.form.get('wf_store_top_n_trials', 100))

wf_config = WFConfig(
    strategy_id=strategy_id,
    is_period_days=is_period_days,
    oos_period_days=oos_period_days,
    warmup_bars=warmup_bars,
    post_process=post_process_config,
    dsr_config=dsr_config,
    stress_test_config=stress_test_config,
    store_top_n_trials=store_top_n_trials,  # NEW
)
```

---

## 7. Frontend Changes

### 7.1 New File: wfa-results-ui.js

Create `src/ui/static/js/wfa-results-ui.js`:

```javascript
/**
 * WFA Results UI Module
 * Handles WFA-specific table rendering with expandable windows and module tabs.
 */
(function () {
  'use strict';

  // Module state
  const WFAState = {
    expandedWindows: new Set(),  // Track which windows are expanded
    windowTrials: {},            // Cache: windowNumber -> { modules, loaded }
    activeTab: {},               // windowNumber -> activeTabName
  };

  // ============================================================================
  // Constants
  // ============================================================================

  const MODULE_ORDER = ['optuna_is', 'dsr', 'forward_test', 'stress_test'];

  const MODULE_LABELS = {
    'optuna_is': 'Optuna IS',
    'dsr': 'DSR',
    'forward_test': 'Forward Test',
    'stress_test': 'Stress Test',
  };

  // ============================================================================
  // Table Column Definitions
  // ============================================================================

  /**
   * Build table headers for WFA main table (IS/OOS summary rows).
   */
  function buildWFATableHeaders(hasConstraints) {
    const headers = [
      '<th class="col-expand"></th>',  // Expand/collapse column
      '<th>#</th>',
      '<th>Param ID</th>',
      '<th>P</th>',
    ];

    if (hasConstraints) {
      headers.push('<th>C</th>');
    }

    headers.push(
      '<th>WR %</th>',
      '<th>Net Profit %</th>',
      '<th>Max DD %</th>',
      '<th>Trades</th>',
      '<th>Max CL</th>',
      '<th>Score</th>',
      '<th>RoMaD</th>',
      '<th>Sharpe</th>',
      '<th>PF</th>',
      '<th>Ulcer</th>',
      '<th>SQN</th>',
      '<th>Consist</th>'
    );

    return headers.join('');
  }

  // ============================================================================
  // Badge Rendering
  // ============================================================================

  /**
   * Render Pareto badge (blue circle).
   */
  function renderParetoBadge(isPareto) {
    if (isPareto === null || isPareto === undefined) {
      return '';
    }
    return isPareto ? '<span class="dot dot-pareto"></span>' : '';
  }

  /**
   * Render Constraints badge (green/red circle).
   */
  function renderConstraintsBadge(isFeasible, hasConstraints) {
    if (!hasConstraints) {
      return '';
    }
    if (isFeasible === null || isFeasible === undefined) {
      return '';
    }
    return isFeasible
      ? '<span class="dot dot-ok"></span>'
      : '<span class="dot dot-fail"></span>';
  }

  // ============================================================================
  // Row Rendering
  // ============================================================================

  /**
   * Render the Stitched OOS summary row.
   */
  function renderStitchedOOSRow(stitchedOOS, hasConstraints) {
    const metrics = stitchedOOS || {};

    const netProfit = Number(metrics.final_net_profit_pct || 0);
    const maxDd = Math.abs(Number(metrics.max_drawdown_pct || 0));

    let html = `
      <tr class="wfa-stitched-row clickable" data-row-type="stitched">
        <td class="col-expand"></td>
        <td class="rank">-</td>
        <td class="param-hash">Stitched OOS</td>
        <td></td>
    `;

    if (hasConstraints) {
      html += '<td></td>';
    }

    html += `
        <td>${formatNumber(metrics.win_rate, 2)}${metrics.win_rate != null ? '%' : ''}</td>
        <td class="${netProfit >= 0 ? 'val-positive' : 'val-negative'}">
          ${netProfit >= 0 ? '+' : ''}${formatNumber(netProfit, 2)}%
        </td>
        <td class="val-negative">-${formatNumber(maxDd, 2)}%</td>
        <td>${metrics.total_trades ?? '-'}</td>
        <td>${metrics.max_consecutive_losses ?? '-'}</td>
        <td>-</td>
        <td>${formatNumber(metrics.romad, 3)}</td>
        <td>${formatNumber(metrics.sharpe_ratio, 3)}</td>
        <td>${formatNumber(metrics.profit_factor, 3)}</td>
        <td>${formatNumber(metrics.ulcer_index, 2)}</td>
        <td>${formatNumber(metrics.sqn, 3)}</td>
        <td>${formatNumber(metrics.consistency_score, 1)}${metrics.consistency_score != null ? '%' : ''}</td>
      </tr>
    `;

    return html;
  }

  /**
   * Render a window section (header + IS row + OOS row + expandable area).
   */
  function renderWindowSection(window, index, hasConstraints) {
    const windowNumber = window.window_number || index + 1;
    const isExpanded = WFAState.expandedWindows.has(windowNumber);
    const expandIcon = isExpanded ? '▼' : '▶';

    // Window header row
    let html = `
      <tr class="wfa-window-header" data-window-number="${windowNumber}">
        <td colspan="${hasConstraints ? 17 : 16}">
          <span class="expand-toggle" data-window="${windowNumber}">${expandIcon}</span>
          <strong>Window ${windowNumber}</strong>
          │ IS: ${window.is_start_date} - ${window.is_end_date}
          │ OOS: ${window.oos_start_date} - ${window.oos_end_date}
        </td>
      </tr>
    `;

    // IS row
    html += renderWindowMetricsRow(window, 'is', windowNumber, hasConstraints);

    // OOS row
    html += renderWindowMetricsRow(window, 'oos', windowNumber, hasConstraints);

    // Expandable section (modules tabs)
    html += `
      <tr class="wfa-window-expand ${isExpanded ? '' : 'hidden'}" data-window-number="${windowNumber}">
        <td colspan="${hasConstraints ? 17 : 16}">
          <div class="wfa-modules-container" id="wfa-modules-${windowNumber}">
            ${isExpanded ? renderModuleTabs(windowNumber, window.available_modules) : ''}
          </div>
        </td>
      </tr>
    `;

    return html;
  }

  /**
   * Render a window's IS or OOS metrics row.
   */
  function renderWindowMetricsRow(window, period, windowNumber, hasConstraints) {
    const prefix = period === 'is' ? 'is_' : 'oos_';
    const label = period === 'is' ? 'IS' : 'OOS';

    const netProfit = Number(window[`${prefix}net_profit_pct`] || 0);
    const maxDd = Math.abs(Number(window[`${prefix}max_drawdown_pct`] || 0));

    // P/C badges come from the selected Optuna IS trial
    const isPareto = window.is_pareto_optimal;
    const isFeasible = window.constraints_satisfied;

    let html = `
      <tr class="wfa-window-row clickable"
          data-window-number="${windowNumber}"
          data-period="${period}"
          data-row-type="window-${period}">
        <td class="col-expand"></td>
        <td class="rank"></td>
        <td class="param-hash">${window.param_id || '-'} ${label}</td>
        <td>${renderParetoBadge(isPareto)}</td>
    `;

    if (hasConstraints) {
      html += `<td>${renderConstraintsBadge(isFeasible, hasConstraints)}</td>`;
    }

    const score = period === 'is' ? window.is_composite_score : null;

    html += `
        <td>${formatNumber(window[`${prefix}win_rate`], 2)}${window[`${prefix}win_rate`] != null ? '%' : ''}</td>
        <td class="${netProfit >= 0 ? 'val-positive' : 'val-negative'}">
          ${netProfit >= 0 ? '+' : ''}${formatNumber(netProfit, 2)}%
        </td>
        <td class="val-negative">-${formatNumber(maxDd, 2)}%</td>
        <td>${window[`${prefix}total_trades`] ?? '-'}</td>
        <td>${window[`${prefix}max_consecutive_losses`] ?? '-'}</td>
        <td>${score != null ? formatNumber(score, 1) : '-'}</td>
        <td>${formatNumber(window[`${prefix}romad`], 3)}</td>
        <td>${formatNumber(window[`${prefix}sharpe_ratio`], 3)}</td>
        <td>${formatNumber(window[`${prefix}profit_factor`], 3)}</td>
        <td>${formatNumber(window[`${prefix}ulcer_index`], 2)}</td>
        <td>${formatNumber(window[`${prefix}sqn`], 3)}</td>
        <td>${formatNumber(window[`${prefix}consistency_score`], 1)}${window[`${prefix}consistency_score`] != null ? '%' : ''}</td>
      </tr>
    `;

    return html;
  }

  // ============================================================================
  // Module Tabs
  // ============================================================================

  /**
   * Render module tabs for an expanded window.
   */
  function renderModuleTabs(windowNumber, availableModules) {
    const modules = availableModules || ['optuna_is'];
    const activeTab = WFAState.activeTab[windowNumber] || modules[0];

    // Tab buttons
    let tabsHtml = '<div class="wfa-module-tabs">';
    for (const moduleType of MODULE_ORDER) {
      if (modules.includes(moduleType)) {
        const isActive = moduleType === activeTab;
        tabsHtml += `
          <button class="wfa-tab-btn ${isActive ? 'active' : ''}"
                  data-window="${windowNumber}"
                  data-module="${moduleType}">
            ${MODULE_LABELS[moduleType]}
          </button>
        `;
      }
    }
    tabsHtml += '</div>';

    // Tab content area
    tabsHtml += `
      <div class="wfa-tab-content" id="wfa-tab-content-${windowNumber}">
        <div class="loading-spinner">Loading...</div>
      </div>
    `;

    return tabsHtml;
  }

  /**
   * Render trials table for a specific module.
   */
  function renderModuleTrialsTable(trials, moduleType, windowNumber, hasConstraints) {
    if (!trials || trials.length === 0) {
      return '<p class="no-data">No trials available for this module.</p>';
    }

    // Use existing OptunaResultsUI functions if available
    const objectives = [];  // Could be passed from study config

    let html = `
      <table class="wfa-module-table data-table">
        <thead>
          <tr>${OptunaResultsUI.buildTrialTableHeaders(objectives, hasConstraints)}</tr>
        </thead>
        <tbody>
    `;

    trials.forEach((trial, index) => {
      // Add rank and param_id to trial for rendering
      const trialWithRank = {
        ...trial,
        trial_number: trial.trial_number ?? index,
      };

      html += OptunaResultsUI.renderTrialRow(trialWithRank, objectives, { hasConstraints });
    });

    html += '</tbody></table>';

    return html;
  }

  // ============================================================================
  // Main Render Function
  // ============================================================================

  /**
   * Render the complete WFA results table.
   */
  function renderWFAResultsTable(windows, stitchedOOS, hasConstraints) {
    const container = document.querySelector('.data-table-container');
    if (!container) return;

    // Clear existing content
    container.innerHTML = '';

    // Build table
    let html = `
      <table class="data-table wfa-table">
        <thead>
          <tr>${buildWFATableHeaders(hasConstraints)}</tr>
        </thead>
        <tbody>
    `;

    // Stitched OOS section header
    const dateRange = getStitchedDateRange(windows);
    html += `
      <tr class="wfa-section-header">
        <td colspan="${hasConstraints ? 17 : 16}">
          <strong>Stitched OOS</strong> · ${dateRange}
        </td>
      </tr>
    `;

    // Stitched OOS row
    html += renderStitchedOOSRow(stitchedOOS, hasConstraints);

    // Window sections
    (windows || []).forEach((window, index) => {
      html += renderWindowSection(window, index, hasConstraints);
    });

    html += '</tbody></table>';

    container.innerHTML = html;

    // Attach event listeners
    attachWFAEventListeners();
  }

  /**
   * Get date range string from windows.
   */
  function getStitchedDateRange(windows) {
    if (!windows || windows.length === 0) return '';

    const firstOOS = windows[0]?.oos_start_date || '';
    const lastOOS = windows[windows.length - 1]?.oos_end_date || '';

    return `${firstOOS} - ${lastOOS}`;
  }

  // ============================================================================
  // Event Handlers
  // ============================================================================

  /**
   * Attach event listeners for WFA table interactions.
   */
  function attachWFAEventListeners() {
    // Expand/collapse toggles
    document.querySelectorAll('.expand-toggle').forEach(toggle => {
      toggle.addEventListener('click', handleExpandToggle);
    });

    // Row clicks for equity chart
    document.querySelectorAll('.wfa-stitched-row, .wfa-window-row').forEach(row => {
      row.addEventListener('click', handleRowClick);
    });

    // Tab clicks
    document.querySelectorAll('.wfa-tab-btn').forEach(btn => {
      btn.addEventListener('click', handleTabClick);
    });
  }

  /**
   * Handle expand/collapse toggle click.
   */
  async function handleExpandToggle(event) {
    event.stopPropagation();

    const windowNumber = parseInt(event.target.dataset.window);
    const isExpanded = WFAState.expandedWindows.has(windowNumber);

    if (isExpanded) {
      // Collapse
      WFAState.expandedWindows.delete(windowNumber);
      event.target.textContent = '▶';

      const expandRow = document.querySelector(
        `.wfa-window-expand[data-window-number="${windowNumber}"]`
      );
      if (expandRow) {
        expandRow.classList.add('hidden');
      }
    } else {
      // Expand
      WFAState.expandedWindows.add(windowNumber);
      event.target.textContent = '▼';

      const expandRow = document.querySelector(
        `.wfa-window-expand[data-window-number="${windowNumber}"]`
      );
      if (expandRow) {
        expandRow.classList.remove('hidden');

        // Load trials if not cached
        await loadWindowTrials(windowNumber);
      }
    }
  }

  /**
   * Handle row click for equity chart display.
   */
  async function handleRowClick(event) {
    const row = event.currentTarget;
    const rowType = row.dataset.rowType;

    // Highlight selected row
    document.querySelectorAll('.wfa-table tr').forEach(r => r.classList.remove('selected'));
    row.classList.add('selected');

    if (rowType === 'stitched') {
      // Show stored stitched OOS equity
      displayStitchedEquity();
    } else if (rowType.startsWith('window-')) {
      // Generate equity for window IS/OOS
      const windowNumber = parseInt(row.dataset.windowNumber);
      const period = row.dataset.period;
      await generateWindowEquity(windowNumber, period);
    }
  }

  /**
   * Handle module tab click.
   */
  async function handleTabClick(event) {
    const btn = event.currentTarget;
    const windowNumber = parseInt(btn.dataset.window);
    const moduleType = btn.dataset.module;

    // Update active state
    document.querySelectorAll(`.wfa-tab-btn[data-window="${windowNumber}"]`).forEach(b => {
      b.classList.remove('active');
    });
    btn.classList.add('active');

    WFAState.activeTab[windowNumber] = moduleType;

    // Render module table
    renderActiveModuleTable(windowNumber, moduleType);
  }

  // ============================================================================
  // Data Loading
  // ============================================================================

  /**
   * Load trials for a window from API.
   */
  async function loadWindowTrials(windowNumber) {
    // Check cache
    if (WFAState.windowTrials[windowNumber]?.loaded) {
      renderActiveModuleTable(
        windowNumber,
        WFAState.activeTab[windowNumber] || 'optuna_is'
      );
      return;
    }

    const studyId = window.ResultsState?.studyId;
    if (!studyId) return;

    try {
      const response = await fetch(
        `/api/studies/${studyId}/wfa/windows/${windowNumber}`
      );

      if (!response.ok) {
        throw new Error(`Failed to load window data: ${response.status}`);
      }

      const data = await response.json();

      // Cache the data
      WFAState.windowTrials[windowNumber] = {
        modules: data.modules,
        availableModules: data.available_modules,
        loaded: true,
      };

      // Set default active tab
      if (!WFAState.activeTab[windowNumber]) {
        WFAState.activeTab[windowNumber] = data.available_modules[0] || 'optuna_is';
      }

      // Render tabs and first module
      const container = document.getElementById(`wfa-modules-${windowNumber}`);
      if (container) {
        container.innerHTML = renderModuleTabs(windowNumber, data.available_modules);
        attachTabListeners(windowNumber);
        renderActiveModuleTable(windowNumber, WFAState.activeTab[windowNumber]);
      }
    } catch (error) {
      console.error('Error loading window trials:', error);
      const container = document.getElementById(`wfa-modules-${windowNumber}`);
      if (container) {
        container.innerHTML = `<p class="error">Error loading data: ${error.message}</p>`;
      }
    }
  }

  /**
   * Attach tab listeners after dynamic content load.
   */
  function attachTabListeners(windowNumber) {
    document.querySelectorAll(`.wfa-tab-btn[data-window="${windowNumber}"]`).forEach(btn => {
      btn.addEventListener('click', handleTabClick);
    });
  }

  /**
   * Render the active module's trials table.
   */
  function renderActiveModuleTable(windowNumber, moduleType) {
    const cached = WFAState.windowTrials[windowNumber];
    if (!cached?.loaded) return;

    const trials = cached.modules[moduleType] || [];
    const hasConstraints = window.ResultsState?.hasConstraints || false;

    const contentContainer = document.getElementById(`wfa-tab-content-${windowNumber}`);
    if (contentContainer) {
      contentContainer.innerHTML = renderModuleTrialsTable(
        trials,
        moduleType,
        windowNumber,
        hasConstraints
      );

      // Attach row click listeners for equity generation
      contentContainer.querySelectorAll('tr.clickable').forEach(row => {
        row.addEventListener('click', async () => {
          const trialNumber = parseInt(row.dataset.trialNumber);
          const period = defaultPeriodForModule(moduleType);
          await generateTrialEquity(windowNumber, moduleType, trialNumber, period);
        });
      });
    }
  }

  // ============================================================================
    /**
   * Default period per module tab.
   * - optuna_is/dsr/stress_test default to 'optuna_is' to match the IS slice used by selection.
   * - forward_test defaults to 'ft'.
   */
  function defaultPeriodForModule(moduleType) {
    switch (moduleType) {
      case 'forward_test': return 'ft';
      case 'optuna_is': return 'optuna_is';
      case 'dsr': return 'optuna_is';
      case 'stress_test': return 'optuna_is';
      default: return 'is';
    }
  }

// Equity Chart Generation
  // ============================================================================

  /**
   * Display stored stitched OOS equity curve.
   */
  function displayStitchedEquity() {
    const stitched = window.ResultsState?.stitched_oos;
    if (stitched?.equity_curve) {
      // Use existing renderEquityChart function
      if (typeof renderEquityChart === 'function') {
        const boundaries = calculateWindowBoundaries(
          window.ResultsState?.results || [],
          stitched
        );
        renderEquityChart(stitched.equity_curve, boundaries);
      }
    }
  }

  /**
   * Generate equity curve for window IS/OOS period.
   */
  async function generateWindowEquity(windowNumber, period) {
    const studyId = window.ResultsState?.studyId;
    if (!studyId) return;

    try {
      showChartLoading();

      const response = await fetch(
        `/api/studies/${studyId}/wfa/windows/${windowNumber}/equity`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ period }),
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to generate equity: ${response.status}`);
      }

      const data = await response.json();

      if (typeof renderEquityChart === 'function') {
        renderEquityChart(data.equity_curve, []);
      }
    } catch (error) {
      console.error('Error generating window equity:', error);
      showChartError(error.message);
    }
  }

  /**
   * Generate equity curve for a specific (window, module trial, period).
   *
   * IMPORTANT:
   * - moduleType is REQUIRED to disambiguate which tab the row came from.
   * - period MUST be one of: 'optuna_is' | 'is' | 'ft' | 'oos' | 'both'
   */
  async function generateTrialEquity(windowNumber, moduleType, trialNumber, period) {
    const studyId = window.ResultsState?.studyId;
    if (!studyId) return;

    try {
      showChartLoading();

      const response = await fetch(
        `/api/studies/${studyId}/wfa/windows/${windowNumber}/equity`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            moduleType,
            trialNumber,
            period
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to generate equity: ${response.status}`);
      }

      const data = await response.json();

      if (typeof renderEquityChart === 'function') {
        renderEquityChart(data.equity_curve, data.timestamps || []);
      }
    } catch (error) {
      console.error('Error generating trial equity:', error);
      showChartError(error.message);
    }
  }

      );

      if (!response.ok) {
        throw new Error(`Failed to generate equity: ${response.status}`);
      }

      const data = await response.json();

      if (typeof renderEquityChart === 'function') {
        renderEquityChart(data.equity_curve, []);
      }
    } catch (error) {
      console.error('Error generating trial equity:', error);
      showChartError(error.message);
    }
  }

  /**
   * Show loading state in chart area.
   */
  function showChartLoading() {
    const chartContainer = document.getElementById('equityChart');
    if (chartContainer) {
      // Could show a loading spinner overlay
    }
  }

  /**
   * Show error in chart area.
   */
  function showChartError(message) {
    const chartContainer = document.getElementById('equityChart');
    if (chartContainer) {
      console.error('Chart error:', message);
    }
  }

  // ============================================================================
  // Utility Functions
  // ============================================================================

  /**
   * Format number for display.
   */
  function formatNumber(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return 'N/A';
    }
    const num = Number(value);
    if (!Number.isFinite(num)) {
      return num > 0 ? 'Inf' : '-Inf';
    }
    return num.toFixed(digits);
  }

  // ============================================================================
  // Public API
  // ============================================================================

  window.WFAResultsUI = {
    renderWFAResultsTable,
    loadWindowTrials,
    resetState: function() {
      WFAState.expandedWindows.clear();
      WFAState.windowTrials = {};
      WFAState.activeTab = {};
    },
  };

})();
```

### 7.2 CSS Additions (style.css)

Add WFA-specific styles:

```css
/* ============================================================================
   WFA Results Table Styles
   ============================================================================ */

.wfa-table {
  width: 100%;
  border-collapse: collapse;
}

.wfa-section-header {
  background: #e8f4fc;
  font-weight: 600;
}

.wfa-section-header td {
  padding: 10px 12px;
  border-bottom: 2px solid #b8d4e8;
}

.wfa-stitched-row {
  background: #f0f8ff;
}

.wfa-stitched-row:hover {
  background: #e0f0ff;
}

.wfa-window-header {
  background: #f5f5f5;
  cursor: default;
}

.wfa-window-header td {
  padding: 8px 12px;
  border-top: 1px solid #ddd;
  font-size: 13px;
}

.wfa-window-row {
  background: #fff;
}

.wfa-window-row:hover {
  background: #f8f8f8;
}

.wfa-window-expand {
  background: #fafafa;
}

.wfa-window-expand.hidden {
  display: none;
}

.wfa-window-expand > td {
  padding: 0;
}

.col-expand {
  width: 30px;
  text-align: center;
}

.expand-toggle {
  cursor: pointer;
  font-size: 12px;
  padding: 4px 8px;
  color: #666;
  user-select: none;
}

.expand-toggle:hover {
  color: #333;
  background: #eee;
  border-radius: 3px;
}

/* Module Tabs */
.wfa-modules-container {
  padding: 12px 16px;
  border-top: 1px solid #e0e0e0;
}

.wfa-module-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  border-bottom: 1px solid #ddd;
  padding-bottom: 8px;
}

.wfa-tab-btn {
  padding: 6px 16px;
  border: 1px solid #ccc;
  background: #f5f5f5;
  cursor: pointer;
  font-size: 13px;
  border-radius: 4px 4px 0 0;
  transition: all 0.15s ease;
}

.wfa-tab-btn:hover {
  background: #e8e8e8;
}

.wfa-tab-btn.active {
  background: #fff;
  border-bottom-color: #fff;
  font-weight: 600;
  color: #2c5282;
}

.wfa-tab-content {
  min-height: 100px;
}

.wfa-module-table {
  width: 100%;
  font-size: 12px;
  margin-top: 8px;
}

.wfa-module-table th,
.wfa-module-table td {
  padding: 6px 8px;
}

/* Loading and Error States */
.loading-spinner {
  text-align: center;
  padding: 20px;
  color: #666;
}

.no-data {
  text-align: center;
  padding: 20px;
  color: #888;
  font-style: italic;
}

.error {
  color: #c53030;
  padding: 12px;
  background: #fff5f5;
  border: 1px solid #feb2b2;
  border-radius: 4px;
}
```

### 7.3 Integration with results.js

Update `results.js` to use the new WFA module:

```javascript
// In displayStudyData() function (around line 2084)

if (ResultsState.mode === 'wfa') {
  setComparisonLine('');
  const summary = ResultsState.stitched_oos || ResultsState.summary || {};
  displaySummaryCards(summary);

  // NEW: Use WFA-specific rendering
  if (window.WFAResultsUI) {
    WFAResultsUI.resetState();
    WFAResultsUI.renderWFAResultsTable(
      ResultsState.results || [],
      summary,
      (Array.isArray(ResultsState.optuna?.constraints) && ResultsState.optuna.constraints.some(c => c && c.enabled))
    );
  } else {
    // Fallback to old simple rendering
    renderWFATable(ResultsState.results || []);
  }

  const boundaries = calculateWindowBoundaries(ResultsState.results || [], summary);
  renderEquityChart(summary.equity_curve || [], boundaries);
  renderWindowIndicators(ResultsState.summary?.total_windows || ResultsState.results?.length || 0);
} else {
  // ... existing Optuna handling ...
}
```

### 7.4 Add Script to results.html

Include the new JS file in `templates/results.html`:

```html
<!-- After optuna-results-ui.js -->
<script src="{{ url_for('static', filename='js/wfa-results-ui.js') }}"></script>
```

---

## 8. Start Page Changes

### 8.1 Add Store Top N Trials Input

In `templates/index.html`, add to WFA Settings section:

```html
<!-- In WFA Settings section -->
<div class="form-row">
  <label for="wfStoreTopNTrials">Store Top N Trials (per module)</label>
  <input type="number" id="wfStoreTopNTrials" value="100" min="10" max="500" step="10">
  <small class="help-text">Number of trials to store per window per module (default: 100)</small>
</div>
```

### 8.2 Update main.js Form Handling

In `main.js`, include the new parameter when launching WFA:

```javascript
// In runWFA() or similar function
const formData = new FormData();
// ... existing params ...
formData.append('wf_store_top_n_trials', document.getElementById('wfStoreTopNTrials')?.value || '100');
```

---

## 9. Testing Requirements

### 9.1 Unit Tests

#### Database Tests (test_storage.py)
```python
def test_wfa_window_trials_table_created():
    """Verify wfa_window_trials table is created."""
    pass

def test_save_wfa_study_with_trials():
    """Test saving WFA study with intermediate module results."""
    pass

def test_load_wfa_window_trials():
    """Test loading trials for a specific window."""
    pass

def test_wfa_window_new_columns():
    """Verify new columns added to wfa_windows table."""
    pass
```

#### Engine Tests (test_walkforward.py)
```python
def test_window_result_includes_module_trials():
    """Verify WindowResult contains optuna_is_trials, dsr_trials, etc."""
    pass

def test_pareto_constraints_captured():
    """Verify is_pareto_optimal and constraints_satisfied are captured."""
    pass

def test_best_params_source_tracked():
    """Verify best_params_source correctly identifies source module."""
    pass

def test_store_top_n_trials_limit():
    """Verify only top N trials are stored per module."""
    pass
```

#### API Tests (test_api.py)
```python
def test_get_wfa_window_details():
    """Test GET /api/studies/<id>/wfa/windows/<n>"""
    pass

def test_generate_wfa_window_equity():
    """Test POST /api/studies/<id>/wfa/windows/<n>/equity"""
    pass

def test_download_wfa_window_trades():
    """Test POST /api/studies/<id>/wfa/windows/<n>/trades"""
    pass
```

### 9.2 Integration Tests

```python
def test_full_wfa_workflow_with_dsr():
    """Run WFA with DSR enabled, verify all data stored and retrievable."""
    pass

def test_full_wfa_workflow_with_all_modules():
    """Run WFA with DSR, FT, ST enabled, verify complete data chain."""
    pass

def test_wfa_results_page_rendering():
    """Verify results page loads and displays WFA data correctly."""
    pass
```

### 9.3 Manual Test Checklist

- [ ] Run WFA with only Optuna IS (no post-process)
- [ ] Run WFA with DSR enabled
- [ ] Run WFA with DSR + FT enabled
- [ ] Run WFA with all modules enabled
- [ ] Verify Stitched OOS row displays correctly
- [ ] Verify window sections collapse/expand
- [ ] Verify tabs show only enabled modules
- [ ] Click through all tabs, verify trials load
- [ ] Click Stitched OOS row, verify equity chart
- [ ] Click Window IS row, verify equity generated
- [ ] Click Window OOS row, verify equity generated
- [ ] Click trial in module tab, verify equity generated
- [ ] Download stitched OOS trades
- [ ] Download Window N IS trades
- [ ] Download Window N OOS trades
- [ ] Verify P/C badges display correctly

---

## 10. Implementation Phases

### Phase 1: Storage (Priority: High)

**Files to modify:**
- `src/core/storage.py`

**Tasks:**
1. Add `_ensure_wfa_schema_updated()` function
2. Create `wfa_window_trials` table schema
3. Add new columns to `wfa_windows` table
4. Implement `_save_window_trials()` helper
5. Update `save_wfa_study_to_db()` to save window trials
6. Implement `load_wfa_window_trials()` function

**Deliverables:**
- Updated storage.py with all new functions
- Database schema supports new data

### Phase 2: Backend Engine (Priority: High)

**Files to modify:**
- `src/core/walkforward_engine.py`

**Tasks:**
1. Add `store_top_n_trials` to `WFConfig`
2. Extend `WindowResult` dataclass with new fields
3. Implement `_convert_optuna_results_for_storage()`
4. Implement `_convert_dsr_results_for_storage()`
5. Implement `_convert_ft_results_for_storage()`
6. Implement `_convert_st_results_for_storage()`
7. Refactor `_process_window_with_modules()` to capture intermediate results
8. Track `best_params_source`, `is_pareto_optimal`, `constraints_satisfied`

**Deliverables:**
- WindowResult captures all module data
- Data flows correctly to storage layer

### Phase 3: Backend API (Priority: Medium)

**Files to modify:**
- `src/ui/server.py`

**Tasks:**
1. Add `GET /api/studies/<id>/wfa/windows/<n>` endpoint
2. Add `POST /api/studies/<id>/wfa/windows/<n>/equity` endpoint
3. Add `POST /api/studies/<id>/wfa/windows/<n>/trades` endpoint
4. Update `/api/walkforward` to accept `wf_store_top_n_trials`

**Deliverables:**
- All new endpoints functional
- API documentation updated

### Phase 4: Frontend (Priority: Medium)

**Files to create/modify:**
- `src/ui/static/js/wfa-results-ui.js` (NEW)
- `src/ui/static/js/results.js`
- `src/ui/static/css/style.css`
- `src/ui/templates/results.html`

**Tasks:**
1. Create `wfa-results-ui.js` with all components
2. Add WFA-specific CSS styles
3. Integrate with `results.js`
4. Add script include to `results.html`

**Deliverables:**
- WFA table renders with expandable windows
- Module tabs work correctly
- Equity charts generate on-demand

### Phase 5: Start Page (Priority: Low)

**Files to modify:**
- `src/ui/templates/index.html`
- `src/ui/static/js/main.js`

**Tasks:**
1. Add "Store Top N Trials" input field
2. Update form submission to include new parameter

**Deliverables:**
- UI control for trial storage limit
- Parameter passed to backend

---

## Appendix A: API Reference

### GET /api/studies/<study_id>/wfa/windows/<window_number>

Returns a single window's drill-down payload.

**Response keys**
- `window`: includes IS/OOS dates, **optimization/FT slice dates**, selected params, P/C tri-state, and metrics.
- `modules`: grouped trials by module type (`optuna_is`, `dsr`, `forward_test`, `stress_test`).

**Response (shape)**
```json
{
  "window": {
    "window_number": 1,
    "window_id": "....",
    "is_start_date": "...",
    "is_end_date": "...",
    "oos_start_date": "...",
    "oos_end_date": "...",
    "optimization_start_date": "...",
    "optimization_end_date": "...",
    "ft_start_date": "...",
    "ft_end_date": "...",
    "best_params": {...},
    "param_id": "...",
    "best_params_source": "optuna_is",
    "is_pareto_optimal": null,
    "constraints_satisfied": true,
    "available_modules": ["optuna_is","dsr","forward_test","stress_test"],
    "module_status": {...},
    "selection_chain": {...},
    "is_metrics": {...},
    "oos_metrics": {...}
  },
  "modules": {
    "optuna_is": [...],
    "dsr": [...],
    "forward_test": [...],
    "stress_test": [...]
  }
}
```


### POST /api/studies/<study_id>/wfa/windows/<window_number>/equity

**Request**
```json
{
  "moduleType": "optuna_is | dsr | forward_test | stress_test | oos_result",
  "trialNumber": 120,
  "period": "optuna_is | is | ft | oos | both"
}
```

**Response**
```json
{
  "equity_curve": [...],
  "timestamps": [...]
}
```


### POST /api/studies/<study_id>/wfa/windows/<window_number>/trades

**Request**
```json
{
  "moduleType": "optuna_is | dsr | forward_test | stress_test | oos_result",
  "trialNumber": 120,
  "period": "optuna_is | is | ft | oos | both"
}
```

**Response**
- Trades CSV download


## Appendix B: Database Schema Summary

### wfa_windows (Updated)

| Column | Type | Description |
|--------|------|-------------|
| window_id | TEXT | Primary key |
| study_id | TEXT | Foreign key to studies |
| window_number | INTEGER | Window index (1-based) |
| best_params_json | TEXT | JSON params |
| param_id | TEXT | Hash-based identifier |
| best_params_source | TEXT | NEW: 'optuna_is', 'dsr', 'forward_test', 'stress_test' |
| is_pareto_optimal | INTEGER | NEW: Boolean |
| constraints_satisfied | INTEGER | NEW: Boolean |
| available_modules | TEXT | NEW: JSON array |
| store_top_n_trials | INTEGER | NEW: Limit setting |
| is_* | Various | IS period metrics |
| oos_* | Various | OOS period metrics |
| wfe | REAL | Walk-forward efficiency |

### wfa_window_trials (New)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto) |
| window_id | TEXT | Foreign key to wfa_windows |
| module_type | TEXT | 'optuna_is', 'dsr', 'forward_test', 'stress_test' |
| trial_number | INTEGER | Trial index |
| params_json | TEXT | JSON params |
| param_id | TEXT | Hash-based identifier |
| [metrics columns] | Various | Same as trials table |
| [module-specific] | Various | DSR/FT/ST specific metrics |
| is_selected | INTEGER | Boolean: selected for next stage |
| created_at | TEXT | Timestamp |

---

## Appendix C: File Change Summary

| File | Action | Changes |
|------|--------|---------|
| `src/core/storage.py` | Modify | Add schema migration, save/load functions |
| `src/core/walkforward_engine.py` | Modify | Extend WindowResult, capture module results |
| `src/ui/server.py` | Modify | Add 3 new API endpoints |
| `src/ui/static/js/wfa-results-ui.js` | Create | New 500+ line module |
| `src/ui/static/js/results.js` | Modify | Integrate WFA module |
| `src/ui/static/css/style.css` | Modify | Add WFA-specific styles |
| `src/ui/templates/results.html` | Modify | Add script include |
| `src/ui/templates/index.html` | Modify | Add store_top_n input |
| `src/ui/static/js/main.js` | Modify | Handle new form field |

---

**End of Implementation Plan**
