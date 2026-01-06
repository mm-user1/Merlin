# Phase 4.5 Fixes — Centralize StrategyResult metric enrichment

You are an agent coder inside the Merlin repository. Implement the update described below as a clean patch with all tests passing.

---

## 0) TL;DR (what you ship)

1. Add **one helper**: `core.metrics.enrich_strategy_result(result, initial_balance=..., risk_free_rate=0.02)`
2. Export the helper from `core/__init__.py`
3. Update **all strategies** (S01, S04) to call it once and remove **all manual metric field assignment**
4. Fix docs that currently teach incorrect metric assignment (`win_rate`)
5. Add tests that prevent drift (e.g., `sortino_ratio` and `win_rate` must not become StrategyResult fields by accident)

---

## 1) Business constraints (do not violate)

- Reliability and consistency are the top priorities
- Keep the update simple and clear: **no frameworks**, **no registries**, **no large refactors**
- Preserve existing behavior and compatibility (especially `StrategyResult.to_dict()` output)
- Product owner explicitly states that single-backtest UI only needs Profit (net profit %), Max DD %, Total Trades
- We are **not** expanding single-backtest exposure of additional metrics (e.g., win rate) in this phase

---

## 2) Problem statement (what is broken / fragile)

### 2.1 Per-strategy duplication

Every strategy's `run()` ends with duplicated wiring:
- calculate basic metrics
- copy values into `StrategyResult` field-by-field
- calculate advanced metrics
- copy values into `StrategyResult` field-by-field

This creates a "touch N files" maintenance tax any time metric wiring changes.

**Evidence:**
- `src/strategies/s01_trailing_ma/strategy.py:406-429` — manual field assignments
- `src/strategies/s04_stochrsi/strategy.py:348-366` — manual field assignments

### 2.2 Drift + silent output loss

Strategies can assign ad-hoc attributes on `StrategyResult` that are:
- not declared in the `StrategyResult` dataclass
- and not included in `StrategyResult.to_dict()`

Result: silent mismatch between "what strategy computed" and "what UI/API can see".

**Evidence:**
- `src/strategies/s04_stochrsi/strategy.py:366` assigns `result.sortino_ratio`, but `StrategyResult` (backtest_engine.py:26-54) does not declare it

### 2.3 Documentation drift

`docs/ADDING_NEW_STRATEGY.md:234` shows assigning `result.win_rate`, but `StrategyResult` does not declare it. This encourages new drift.

---

## 3) Source of truth: contracts you must preserve

### 3.1 StrategyResult: single-backtest contract

**File:** `src/core/backtest_engine.py`

**Do not change the schema in this phase.** This phase is about wiring and DRYness.

StrategyResult declares:
- raw artifacts: `trades`, `equity_curve`, `balance_curve`, `timestamps`
- declared basic metrics: `net_profit`, `net_profit_pct`, `gross_profit`, `gross_loss`, `max_drawdown`, `max_drawdown_pct`, `total_trades`, `winning_trades`, `losing_trades`
- declared optional metrics: `sharpe_ratio`, `profit_factor`, `romad`, `ulcer_index`, `sqn`, `consistency_score`

`StrategyResult.to_dict()` exports the declared schema and only conditionally exports optional metrics if non-None.

### 3.2 Metrics sets: calculation contract

**File:** `src/core/metrics.py`

`BasicMetrics.to_dict()` includes StrategyResult-supported keys **and** additional optimization-only keys:
- StrategyResult-supported: `net_profit`, `net_profit_pct`, `gross_profit`, `gross_loss`, `max_drawdown`, `max_drawdown_pct`, `total_trades`, `winning_trades`, `losing_trades`
- Optimization-only (NOT in StrategyResult): `win_rate`, `avg_win`, `avg_loss`, `avg_trade`

`AdvancedMetrics.to_dict()` includes:
- StrategyResult-supported: `sharpe_ratio`, `profit_factor`, `romad`, `ulcer_index`, `sqn`, `consistency_score`
- Optimization-only (NOT in StrategyResult): `sortino_ratio`

### 3.3 Optuna and WFA contracts (do not change)

**Files:** `src/core/optuna_engine.py`, `src/core/walkforward_engine.py`

These modules already compute basic+advanced metrics directly and store a rich metric set in `OptimizationResult` and trial user attrs. Do not change them.

---

## 4) Chosen solution: Option 1 (minimal + future-proof)

Add one helper in `core.metrics` to:
- compute basic+advanced
- attach only the intersection of metric keys with StrategyResult declared dataclass fields
- return `(basic, advanced)`

Then strategies call it once.

**Why this is future-proof:**
- Adding a new StrategyResult field automatically becomes attachable without changing strategies
- Adding a new metric to BasicMetrics/AdvancedMetrics does not require strategy edits

---

## 5) Required changes (files)

You must modify these files:
1. `src/core/metrics.py` — add helper function
2. `src/core/__init__.py` — export the new helper
3. `src/strategies/s01_trailing_ma/strategy.py` — use helper
4. `src/strategies/s04_stochrsi/strategy.py` — use helper
5. `docs/ADDING_NEW_STRATEGY.md` — update example
6. `tests/test_metrics.py` — add drift guard tests

---

## 6) Implementation instructions

### 6.1 `src/core/metrics.py` — add helper `enrich_strategy_result`

#### 6.1.1 CRITICAL: Runtime safety (avoid NameError)

In this repo, `StrategyResult` is imported under `TYPE_CHECKING` in `core/metrics.py`, so it is **not** available at runtime.

To avoid importing `StrategyResult` at runtime (and to avoid any potential circular imports), use `dataclasses.fields()` on the **instance** `result` instead of on the class `StrategyResult`.

`dataclasses.fields()` accepts either a dataclass type or an instance of a dataclass, so `fields(result)` works and is the simplest/most robust option.

#### 6.1.2 Required imports

At the top of `core/metrics.py`, change:
```python
from dataclasses import dataclass
```
to:
```python
from dataclasses import dataclass, fields
```

#### 6.1.3 Function signature

```python
def enrich_strategy_result(
    result: StrategyResult,
    *,
    initial_balance: Optional[float] = None,
    risk_free_rate: float = 0.02,
) -> tuple[BasicMetrics, AdvancedMetrics]:
    """
    Compute metrics and attach declared fields to StrategyResult.

    Calculates BasicMetrics and AdvancedMetrics, then copies only the
    metric values whose keys match declared StrategyResult dataclass fields.
    This prevents drift where strategies assign undeclared attributes.

    Args:
        result: StrategyResult instance to enrich
        initial_balance: Starting capital for percentage calculations
        risk_free_rate: Annual risk-free rate for Sharpe/Sortino (default 0.02)

    Returns:
        Tuple of (BasicMetrics, AdvancedMetrics) for callers who need full metrics
    """
    ...
```

#### 6.1.4 Required behavior (must match exactly)

```python
def enrich_strategy_result(
    result: StrategyResult,
    *,
    initial_balance: Optional[float] = None,
    risk_free_rate: float = 0.02,
) -> tuple[BasicMetrics, AdvancedMetrics]:
    """Compute metrics and attach declared fields to StrategyResult."""
    # 1) Compute metrics
    basic = calculate_basic(result, initial_balance=initial_balance)
    advanced = calculate_advanced(result, initial_balance=initial_balance, risk_free_rate=risk_free_rate)

    # 2) Merge all metric values
    values = {**basic.to_dict(), **advanced.to_dict()}

    # 3) Attach ONLY declared StrategyResult dataclass fields
    #    Use fields(result) to introspect the instance (avoids TYPE_CHECKING import issues)
    allowed = {f.name for f in fields(result)}
    for key, value in values.items():
        if key in allowed:
            setattr(result, key, value)

    # 4) Return metrics for callers who need full access
    return basic, advanced
```

#### 6.1.5 Update architectural note

Update the module docstring at the top of `metrics.py` to include the new helper. Change:

```python
"""
Metrics calculation module for S01 Trailing MA v26.

This module provides:
- BasicMetrics: Net profit, drawdown, trade statistics
- AdvancedMetrics: Sharpe, RoMaD, Profit Factor, SQN, Ulcer Index, Consistency
- Calculation functions that operate on StrategyResult

Architectural note: This module ONLY calculates metrics.
It does NOT orchestrate backtests or optimization.
Other modules (backtest_engine, optuna_engine, walkforward_engine) consume these metrics.
"""
```

to:

```python
"""
Metrics calculation module.

This module provides:
- BasicMetrics: Net profit, drawdown, trade statistics
- AdvancedMetrics: Sharpe, RoMaD, Profit Factor, SQN, Ulcer Index, Consistency
- Calculation functions that operate on StrategyResult
- enrich_strategy_result: Helper to compute and attach metrics to StrategyResult

Architectural note: This module ONLY calculates metrics.
It does NOT orchestrate backtests or optimization.
Other modules (backtest_engine, optuna_engine, walkforward_engine) consume these metrics.

Strategies should use enrich_strategy_result() to avoid manual field assignment
and prevent drift where undeclared attributes get set on StrategyResult.
"""
```

#### 6.1.6 Performance note (for transparency)

`calculate_advanced()` already calls `calculate_basic()` internally (line 425). The helper calls both separately, meaning basic metrics are computed twice per call. This matches current strategy behavior and is acceptable for Phase 4.5. Do not attempt to optimize this.

---

### 6.2 `src/core/__init__.py` — export the new helper

Add the new function to the imports and `__all__`:

```python
from .metrics import (
    BasicMetrics,
    AdvancedMetrics,
    WFAMetrics,
    calculate_basic,
    calculate_advanced,
    calculate_for_wfa,
    enrich_strategy_result,  # ADD THIS
)

__all__ = [
    # ... existing exports ...

    # metrics
    "BasicMetrics",
    "AdvancedMetrics",
    "WFAMetrics",
    "calculate_basic",
    "calculate_advanced",
    "calculate_for_wfa",
    "enrich_strategy_result",  # ADD THIS
]
```

---

### 6.3 Strategies — remove manual wiring and call helper once

#### S01 (`src/strategies/s01_trailing_ma/strategy.py`)

Find the section (around lines 406-429) that looks like:
```python
basic_metrics = metrics.calculate_basic(result, initial_balance=equity)

result.net_profit = basic_metrics.net_profit
result.net_profit_pct = basic_metrics.net_profit_pct
# ... many more assignments ...

advanced_metrics = metrics.calculate_advanced(...)

result.sharpe_ratio = advanced_metrics.sharpe_ratio
# ... more assignments ...

return result
```

Replace with:
```python
metrics.enrich_strategy_result(result, initial_balance=equity, risk_free_rate=0.02)
return result
```

#### S04 (`src/strategies/s04_stochrsi/strategy.py`)

Find the section (around lines 348-366) that includes:
```python
basic = metrics.calculate_basic(result, initial_balance=p.initialCapital)
result.net_profit = basic.net_profit
# ... many assignments including sortino_ratio ...
result.sortino_ratio = advanced.sortino_ratio  # THIS IS THE DRIFT BUG

return result
```

Replace with:
```python
metrics.enrich_strategy_result(result, initial_balance=p.initialCapital, risk_free_rate=0.02)
return result
```

#### After changes, strategies must NOT:
- Import or call `calculate_basic` / `calculate_advanced` directly
- Have any `result.<metric> = ...` assignments

---

### 6.4 Docs — update example to use helper

In `docs/ADDING_NEW_STRATEGY.md`, find the metrics section (around lines 227-238):

```python
# Calculate metrics
basic = metrics.calculate_basic(result, p.initialCapital)
advanced = metrics.calculate_advanced(result)

result.net_profit_pct = basic.net_profit_pct
result.max_drawdown_pct = basic.max_drawdown_pct
result.total_trades = basic.total_trades
result.win_rate = basic.win_rate  # BUG: win_rate not in StrategyResult!
result.sharpe_ratio = advanced.sharpe_ratio
result.romad = advanced.romad

return result
```

Replace with:

```python
# Compute and attach all declared metrics to result
# This automatically handles the intersection of calculated metrics
# with StrategyResult's declared fields (no manual assignment needed)
metrics.enrich_strategy_result(result, initial_balance=p.initialCapital)
return result
```

Add a clarifying paragraph after the code block:

```markdown
**Note on metrics:** `enrich_strategy_result()` calculates BasicMetrics and
AdvancedMetrics, then attaches only the metrics that StrategyResult declares
as fields. Additional metrics (like `win_rate`, `sortino_ratio`) are available
in Optuna optimization results but are not exposed in single-backtest output
by design.
```

---

### 6.5 Tests — add helper unit test and drift guards

**Append** the following test class to `tests/test_metrics.py` (do NOT create a new file):

```python
class TestEnrichStrategyResult:
    """Test the enrich_strategy_result helper and drift guards."""

    def test_enrich_attaches_declared_fields(self):
        """Verify declared StrategyResult fields are populated."""
        from core.metrics import enrich_strategy_result

        result = StrategyResult(
            trades=[],
            equity_curve=[100.0, 105.0, 110.0],
            balance_curve=[100.0, 105.0, 110.0],
            timestamps=[
                pd.Timestamp("2025-01-01", tz="UTC"),
                pd.Timestamp("2025-01-02", tz="UTC"),
                pd.Timestamp("2025-01-03", tz="UTC"),
            ],
        )

        basic, advanced = enrich_strategy_result(result, initial_balance=100.0)

        # Verify declared fields are attached correctly
        assert result.net_profit == pytest.approx(basic.net_profit)
        assert result.net_profit_pct == pytest.approx(basic.net_profit_pct)
        assert result.max_drawdown_pct == pytest.approx(basic.max_drawdown_pct)
        assert result.total_trades == basic.total_trades

    def test_drift_guard_win_rate_not_attached(self):
        """win_rate exists in BasicMetrics but NOT in StrategyResult."""
        from core.metrics import enrich_strategy_result

        result = StrategyResult(
            trades=[],
            equity_curve=[100.0],
            balance_curve=[100.0],
            timestamps=[pd.Timestamp("2025-01-01", tz="UTC")],
        )

        enrich_strategy_result(result, initial_balance=100.0)

        # win_rate should NOT be attached (not declared in StrategyResult)
        assert not hasattr(result, "win_rate")

    def test_drift_guard_sortino_not_attached(self):
        """sortino_ratio exists in AdvancedMetrics but NOT in StrategyResult."""
        from core.metrics import enrich_strategy_result

        result = StrategyResult(
            trades=[],
            equity_curve=[100.0],
            balance_curve=[100.0],
            timestamps=[pd.Timestamp("2025-01-01", tz="UTC")],
        )

        enrich_strategy_result(result, initial_balance=100.0)

        # sortino_ratio should NOT be attached (not declared in StrategyResult)
        assert not hasattr(result, "sortino_ratio")

    def test_drift_guard_avg_metrics_not_attached(self):
        """avg_win, avg_loss, avg_trade exist in BasicMetrics but NOT in StrategyResult."""
        from core.metrics import enrich_strategy_result

        result = StrategyResult(
            trades=[],
            equity_curve=[100.0],
            balance_curve=[100.0],
            timestamps=[pd.Timestamp("2025-01-01", tz="UTC")],
        )

        enrich_strategy_result(result, initial_balance=100.0)

        assert not hasattr(result, "avg_win")
        assert not hasattr(result, "avg_loss")
        assert not hasattr(result, "avg_trade")

    def test_returns_both_metric_objects(self):
        """Helper returns BasicMetrics and AdvancedMetrics for full access."""
        from core.metrics import enrich_strategy_result

        result = StrategyResult(
            trades=[],
            equity_curve=[100.0],
            balance_curve=[100.0],
            timestamps=[pd.Timestamp("2025-01-01", tz="UTC")],
        )

        basic, advanced = enrich_strategy_result(result, initial_balance=100.0)

        # Callers can access optimization-only metrics from returned objects
        assert hasattr(basic, "win_rate")
        assert hasattr(basic, "avg_win")
        assert hasattr(advanced, "sortino_ratio")
```

---

## 7) Verification commands (must run)

### 7.1 Run tests

```bash
pytest -q
```

All tests must pass.

### 7.2 Verify strategies are clean

Choose your shell:

#### Unix / Git Bash / WSL

```bash
grep -rn "calculate_basic\|calculate_advanced" src/strategies/
grep -rn "result\.\(net_profit\|net_profit_pct\|gross_profit\|gross_loss\|max_drawdown\|max_drawdown_pct\|total_trades\|winning_trades\|losing_trades\|sharpe_ratio\|profit_factor\|romad\|ulcer_index\|sqn\|consistency_score\|sortino_ratio\|win_rate\|avg_win\|avg_loss\|avg_trade\)" src/strategies/
```

#### Windows PowerShell

```powershell
Get-ChildItem -Recurse -Filter "*.py" -Path src/strategies | Select-String -Pattern "calculate_basic|calculate_advanced"
Get-ChildItem -Recurse -Filter "*.py" -Path src/strategies | Select-String -Pattern "result\.(net_profit|net_profit_pct|gross_profit|gross_loss|max_drawdown|max_drawdown_pct|total_trades|winning_trades|losing_trades|sharpe_ratio|profit_factor|romad|ulcer_index|sqn|consistency_score|sortino_ratio|win_rate|avg_win|avg_loss|avg_trade)"
```

**Expected result:** No matches.

---

## 8) Definition of Done

- [ ] Helper `enrich_strategy_result` exists in `metrics.py` using `fields(result)` for field intersection
- [ ] Helper exported from `core/__init__.py`
- [ ] S01 calls helper once, no manual wiring
- [ ] S04 calls helper once, no manual wiring (sortino_ratio assignment removed)
- [ ] `docs/ADDING_NEW_STRATEGY.md` corrected (win_rate example removed)
- [ ] New drift guard tests added to `test_metrics.py`
- [ ] All tests pass (`pytest -q`)
- [ ] Verification grep/PowerShell commands return no matches
- [ ] Optuna and WFA engines unchanged

---

## 9) Common mistakes to avoid

1. **DO NOT import StrategyResult at runtime in metrics.py** — use `fields(result)` on the instance
2. **DO NOT use `hasattr(result, key)`** — use `fields(result)` for dataclass introspection
3. **DO NOT change StrategyResult schema** — this phase is wiring only
4. **DO NOT change optuna_engine.py or walkforward_engine.py** — they use metrics differently
5. **DO NOT optimize double calculation** — keep changes minimal for this phase
6. **DO NOT forget to export from `core/__init__.py`**

---

## 10) Appendix: Maintenance playbook (how this becomes future-proof)

### A.1 Add a new metric to calculation sets

1. Add the new field to `BasicMetrics` or `AdvancedMetrics`
2. Include it in that dataclass's `to_dict()` output
3. Compute it in `calculate_basic` / `calculate_advanced`

After this:
- **No strategy file needs editing**
- If StrategyResult declares a field with the same key, the helper will attach it automatically
- If StrategyResult does NOT declare it, it remains available for optimization but not single-backtest output

### A.2 Expose a metric in single-backtest output

1. Add the field to `StrategyResult` dataclass
2. Add it to `StrategyResult.to_dict()` optional list if optional

After that:
- Helper will attach it automatically (no strategy edits)
- Strategies stay clean

---

## 11) Final deliverable

Provide a clean patch implementing only the above, with `pytest -q` passing and verification commands showing no matches.
