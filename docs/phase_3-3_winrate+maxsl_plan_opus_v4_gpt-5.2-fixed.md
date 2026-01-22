# Phase 3-3: Win Rate % & Max Consecutive Losses — Implementation Plan v4 (GPT‑5.2 fixed)

**Date:** 2026-01-21  
**Status:** ✅ Audited against current Merlin codebase (Merlin-GH_1.2.0_3-2_Updated-UI) — implementable with no known blockers  
**Scope:** 
- Make **Win Rate %** appear as a fixed column in Optuna / Forward Test / Manual Test tables (calculation already correct).
- Add **Max Consecutive Losses** (`max_consecutive_losses`) end-to-end:
  - computed in metrics,
  - available as an Optuna **constraint** (not an objective),
  - persisted to DB,
  - supported by Forward Test + Manual Test,
  - displayed in tables,
  - configurable in the Constraints panel.

---

## 0) Definitions (single source of truth)

### 0.1 Win Rate %
**Definition used by Merlin (already implemented):**
- Win trade: `trade.net_pnl > 0`
- Loss trade: `trade.net_pnl < 0`
- Breakeven: `trade.net_pnl == 0` (excluded from win/loss counts)
- Denominator: **all trades** (`total_trades = len(trades)`)

So breakevens reduce win rate because they count in total trades but not in winning trades.

✅ No backend logic changes for Win Rate %.

### 0.2 Max Consecutive Losses (Max CL)
**Definition: “maximum number of consecutive non-profitable trades.”**
- Non-profit (counts toward streak): `trade.net_pnl <= 0` (loss OR breakeven)
- Profit resets streak: `trade.net_pnl > 0`

Algorithm:

```python
max_consecutive_losses = 0
consecutive_losses = 0
for trade in trades:
    if trade.net_pnl <= 0:
        consecutive_losses += 1
        max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
    else:
        consecutive_losses = 0
```

**Naming / semantics**
- Use metric key: `max_consecutive_losses`
- UI label: `Max CL`
- Avoid “Max SL” naming because Merlin does not record exit reasons; `net_pnl` cannot distinguish stop-loss exits from other exits.

---

## 1) Backend: metrics calculation

### 1.1 `src/core/metrics.py`
**Goal:** Add `max_consecutive_losses` to `BasicMetrics`, calculate it in `calculate_basic()`, and expose via `to_dict()`.

#### A) Add field to `BasicMetrics`
Find:

```python
@dataclass
class BasicMetrics:
    ...
    avg_trade: float
```

Add:

```python
    max_consecutive_losses: int
```

#### B) Add to `to_dict()`
Add:

```python
"max_consecutive_losses": self.max_consecutive_losses,
```

#### C) Compute in `calculate_basic()`
Right after `avg_trade` is calculated (before returning `BasicMetrics(...)`), compute:

```python
max_consecutive_losses = 0
consecutive_losses = 0
for trade in trades:
    if trade.net_pnl <= 0:
        consecutive_losses += 1
        max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
    else:
        consecutive_losses = 0
```

Then pass it into `BasicMetrics(...)`:

```python
max_consecutive_losses=max_consecutive_losses,
```

✅ This is the only place the metric should be computed.

---

## 2) Backend: Optuna integration (constraints + persistence in trial.user_attrs)

### 2.1 `src/core/optuna_engine.py`

#### A) Add field to `OptimizationResult`
Find the `@dataclass class OptimizationResult:` and add:

```python
max_consecutive_losses: int = 0
```

Recommended placement: after `gross_loss`.

#### B) Register constraint operator
In `CONSTRAINT_OPERATORS`, add:

```python
"max_consecutive_losses": "lte",
```

#### C) Ensure metric is included in `all_metrics`
In `OptunaOptimizer._collect_metrics(...)`, add:

```python
"max_consecutive_losses": result.max_consecutive_losses,
```

#### D) Populate field where `OptimizationResult(...)` is constructed
There are **two** construction paths that must be updated:

1) Inside `_run_single_combination()` after `basic_metrics = metrics.calculate_basic(...)`  
Add:

```python
max_consecutive_losses=basic_metrics.max_consecutive_losses,
```

2) In `_result_from_trial(...)` (rebuild from `trial.user_attrs["merlin.all_metrics"]`)  
Add:

```python
max_consecutive_losses=int(all_metrics.get("max_consecutive_losses", 0) or 0),
```

3) Inside `_run_single_combination()`’s local `_base_result(...)` default  
Add:

```python
max_consecutive_losses=0,
```

✅ After these steps, the metric exists for:
- live optimization,
- multi-process aggregation via `trial.user_attrs`,
- reload from persisted Optuna storage.

---

## 3) Backend: database schema + save/load

### 3.1 `src/core/storage.py` — trials schema
In `CREATE TABLE IF NOT EXISTS trials (...)`, add:

- After `win_rate REAL,` add:
```sql
max_consecutive_losses INTEGER,
```

- After `ft_win_rate REAL,` add:
```sql
ft_max_consecutive_losses INTEGER,
```

### 3.2 `src/core/storage.py` — migrate older DB files
In `_ensure_columns(conn)`, add:

```python
ensure("trials", "max_consecutive_losses", "INTEGER")
ensure("trials", "ft_max_consecutive_losses", "INTEGER")
```

(Do **not** add a default here; existing rows should remain NULL to avoid implying values for historical studies.)

### 3.3 `save_optuna_study_to_db()` — INSERT trials
This is the most error-prone step: tuple length must match placeholder count.

#### A) Add `result.max_consecutive_losses` to the `trial_rows.append(( ... ))` tuple
Find the tuple section:

```python
result.total_trades,
result.win_rate,
result.avg_win,
```

Insert between `result.win_rate` and `result.avg_win`:

```python
result.max_consecutive_losses,
```

#### B) Add the column to the INSERT column list
Find:

```sql
..., total_trades, win_rate, avg_win, avg_loss,
```

Change to:

```sql
..., total_trades, win_rate, max_consecutive_losses, avg_win, avg_loss,
```

#### C) Update placeholder count
Current statement uses **37** placeholders. Adding one value requires **38** placeholders.

✅ Verification rule: after edits,
- `len(trial_rows[0]) == number_of_question_marks_in_VALUES`
- both must be **38**.

### 3.4 `save_forward_test_results()` — UPDATE trials FT fields
Forward Test writes FT columns after optimization.

#### A) Add `ft_max_consecutive_losses` to `rows.append(( ... ))`
Find where the FT tuple is built:

```python
payload.get("ft_total_trades"),
payload.get("ft_win_rate"),
payload.get("ft_sharpe_ratio"),
```

Insert after `payload.get("ft_win_rate")`:

```python
payload.get("ft_max_consecutive_losses"),
```

#### B) Add column to UPDATE statement
Add line after `ft_win_rate = ?,`:

```sql
ft_max_consecutive_losses = ?,
```

#### C) Update placeholder count
This UPDATE currently has **16** placeholders; it becomes **17**.

✅ Verification rule:
- tuple length == placeholder count == 17.

---

## 4) Backend: Forward Test computation pipeline

### 4.1 `src/core/post_process.py`

#### A) Add metric to `_ft_worker_entry()` FT metrics dict
Find `ft_metrics = { ... }` in `_ft_worker_entry` (note: keys are **unprefixed**, e.g., `"net_profit_pct"`).

Add:

```python
"max_consecutive_losses": basic.max_consecutive_losses,
```

✅ Do **not** rename keys to `ft_*` here. The worker payload is consumed by `run_forward_test()` which expects **unprefixed** keys.

#### B) Add metric to in-sample metrics builder
In `_build_is_metrics(result)`, add:

```python
"max_consecutive_losses": getattr(result, "max_consecutive_losses", 0),
```

#### C) Extend `FTResult` dataclass (preserve existing fields)
In `FTResult`, add:

- After `is_win_rate: float` add:
```python
is_max_consecutive_losses: int
```

- After `ft_win_rate: float` add:
```python
ft_max_consecutive_losses: int
```

Do not remove or reorder existing fields like `max_dd_change`, `romad_change`, etc.

#### D) Populate the new FTResult fields in `run_forward_test()`
Where `FTResult(...)` is constructed, add:

```python
is_max_consecutive_losses=is_metrics.get("max_consecutive_losses", 0),
ft_max_consecutive_losses=ft_metrics.get("max_consecutive_losses", 0),
```

✅ After this, `FTResult.__dict__` will contain `ft_max_consecutive_losses`, which `save_forward_test_results()` will persist.

---

## 5) Backend: Manual Test endpoint

### 5.1 `src/ui/server.py`
In the manual test route where `test_metrics = { ... }` is created, add:

```python
"max_consecutive_losses": basic.max_consecutive_losses,
```

Recommended (for completeness): also include it in `original_metrics` for both branches:
- forward_test branch: `trial.get("ft_max_consecutive_losses")`
- optuna branch: `trial.get("max_consecutive_losses")`

This does not change comparison math (which currently ignores that metric) but keeps payloads consistent.

---

## 6) Frontend: labels, constraints summary, and table columns

### 6.1 `src/ui/static/js/results.js`
#### A) Labels
Add:

```js
max_consecutive_losses: 'Max CL',
```

to `OBJECTIVE_LABELS`.

#### B) Constraint operator display
Add:

```js
max_consecutive_losses: '<=',
```

to `CONSTRAINT_OPERATORS`.

#### C) Forward Test mapping
In `renderForwardTestTable()`, extend `mapped` with:

```js
max_consecutive_losses: trial.ft_max_consecutive_losses,
```

(placed near the other metric remaps)

#### D) Manual Test mapping
In `renderManualTestTable()`, extend `mapped` with:

```js
max_consecutive_losses: metrics.max_consecutive_losses,
```

### 6.2 `src/ui/static/js/optuna-results-ui.js`
Goal: add fixed columns for **WR %** and **Max CL**, and prevent duplication if `win_rate` is also an objective.

#### A) Add label (optional, harmless)
Add:

```js
max_consecutive_losses: 'Max CL',
```

to `OBJECTIVE_LABELS`.

#### B) Prevent objective duplication
In both `buildTrialTableHeaders()` and `renderTrialRow()` rawMetricColumns sets, add:

```js
'win_rate',
'max_consecutive_losses',
```

#### C) Add headers (fixed columns)
In `buildTrialTableHeaders()` fixed header block, use:

```
..., [dynamic objectives], WR %, Net Profit %, Max DD %, Trades, Max CL, Score, ...
```

Concretely add:

```js
columns.push('<th>WR %</th>');
...
columns.push('<th>Max CL</th>');
```

#### D) Add cells (fixed columns)
In `renderTrialRow()`:
- Build `winRateCell` (percent):
```js
const winRate = trial.win_rate;
const winRateFormatted = formatNumber(winRate, 2);
const winRateCell = `<td>${winRateFormatted}${winRateFormatted !== 'N/A' ? '%' : ''}</td>`;
```

- Build `maxClCell` (integer):
```js
const maxClCell = `<td>${trial.max_consecutive_losses ?? '-'}</td>`;
```

- Insert them into the returned row template in the same order as headers.

**Important:** Do not place `// comments` inside template literals; keep comments outside of backticks.

### 6.3 `src/ui/templates/index.html` — Constraints panel
Add one new constraint row inside `.constraints-grid`:

- `data-constraint-metric="max_consecutive_losses"`
- operator: `≤`
- numeric input: integer, `min="0"`, `step="1"`, default `value="5"` (or your preferred default)

Example:

```html
<div class="constraint-row">
  <label class="constraint-label">
    <input type="checkbox" class="constraint-checkbox" data-constraint-metric="max_consecutive_losses" />
    Max Consecutive Losses
  </label>
  <span class="constraint-operator">&le;</span>
  <input type="number" class="constraint-input" data-constraint-threshold="max_consecutive_losses" value="5" min="0" step="1" />
</div>
```

No JS changes required: `OptunaUI.collectConstraints()` iterates all `.constraint-row` entries automatically.

---

## 7) Tests

### 7.1 `tests/test_metrics.py` (unit tests for max_consecutive_losses)

Add tests that match the actual dataclass signatures in this repo (`TradeRecord` has: direction, entry_time, exit_time, entry_price, exit_price, size, net_pnl).

Recommended minimal set (add under `TestMetricsEdgeCases`):

1) Streak counts consecutive losses
2) Breakeven continues streak
3) Profit resets streak
4) No trades → 0

Example (adjust timestamps as needed):

```python
def test_max_consecutive_losses_counts_and_resets():
    trades = [
        TradeRecord(direction="Long", entry_time=pd.Timestamp("2025-01-01", tz="UTC"),
                    exit_time=pd.Timestamp("2025-01-02", tz="UTC"),
                    entry_price=100.0, exit_price=95.0, size=1.0, net_pnl=-5.0),
        TradeRecord(direction="Long", entry_time=pd.Timestamp("2025-01-03", tz="UTC"),
                    exit_time=pd.Timestamp("2025-01-04", tz="UTC"),
                    entry_price=95.0, exit_price=95.0, size=1.0, net_pnl=0.0),  # breakeven
        TradeRecord(direction="Long", entry_time=pd.Timestamp("2025-01-05", tz="UTC"),
                    exit_time=pd.Timestamp("2025-01-06", tz="UTC"),
                    entry_price=95.0, exit_price=90.0, size=1.0, net_pnl=-5.0),
        TradeRecord(direction="Long", entry_time=pd.Timestamp("2025-01-07", tz="UTC"),
                    exit_time=pd.Timestamp("2025-01-08", tz="UTC"),
                    entry_price=90.0, exit_price=100.0, size=1.0, net_pnl=10.0),  # profit resets
        TradeRecord(direction="Long", entry_time=pd.Timestamp("2025-01-09", tz="UTC"),
                    exit_time=pd.Timestamp("2025-01-10", tz="UTC"),
                    entry_price=100.0, exit_price=99.0, size=1.0, net_pnl=-1.0),
    ]

    result = StrategyResult(
        trades=trades,
        equity_curve=[100.0, 95.0, 95.0, 90.0, 100.0, 99.0],
        balance_curve=[100.0, 95.0, 95.0, 90.0, 100.0, 99.0],
        timestamps=[pd.Timestamp("2025-01-01", tz="UTC")] * 6,
    )

    basic = calculate_basic(result, initial_balance=100.0)
    assert basic.max_consecutive_losses == 3
```

---

## 8) Manual verification checklist (post-implementation)

### Optuna Tab
- WR % column appears after dynamic objectives and before Net Profit %
- Max CL column appears after Trades and before Score
- No duplicate WR % column when `win_rate` is selected as an objective
- Constraint row appears and produces feasible/infeasible (C badge) behavior

### Forward Test Tab
- WR % uses `ft_win_rate`
- Max CL uses `ft_max_consecutive_losses`
- Values persist after reloading the saved study

### Manual Test Tab
- WR % and Max CL render from `test_metrics`
- No `undefined`/`NaN` rendering

---

## 9) “No blockers” integration map (everything that must be updated)

This plan updates every required integration point:

1. **Metric computed**: `metrics.calculate_basic()` → `BasicMetrics.max_consecutive_losses`
2. **Optuna constraints**: `optuna_engine.CONSTRAINT_OPERATORS` + `_collect_metrics()` + `OptimizationResult` plumbing
3. **Optuna persistence**: `trial.user_attrs["merlin.all_metrics"]` round-trip via `_result_from_trial()`
4. **DB persistence**:
   - trials schema has `max_consecutive_losses`
   - `save_optuna_study_to_db()` inserts it (placeholder count updated)
5. **Forward Test**:
   - worker returns `ft_metrics["max_consecutive_losses"]`
   - `run_forward_test()` maps into `FTResult.ft_max_consecutive_losses`
   - DB schema has `ft_max_consecutive_losses`
   - `save_forward_test_results()` updates it (placeholder count updated)
6. **UI**:
   - constraints row exists in index.html
   - JS label + operator maps updated
   - Optuna/FT/Manual tables map and render the metric
   - Win Rate appears as fixed column without duplication

✅ With these steps applied, the feature is implementable without missing wiring.
