# Merlin Analytics — Three-Layer Analytics Architecture v6

> A three-layer analytics system fully integrated into Merlin.
> Layer 3 — local SQLite database + Merlin UI (not Google Sheets).
> Principle: one tool, one UI component, two data sources.

**Changes in v6 relative to v5:**
- Layer 1: final metric names — `OOS` prefix for window-level aggregates, `(med)` suffix for medians; card format preserved (value + label in two rows), 2 new cards added
- Layer 1: new `stitched_oos_winning_trades` column added to studies for `TOTAL TRADES: 101/169` format
- GPT 5.3: Portfolio MaxDD contradiction fixed (equity curve in Phase 1, AVG note removed)
- GPT 5.3: "Metric Dictionary" section added (exact formulas, null-policy, rounding)
- GPT 5.3: `.gitignore` note added for `src/storage/global/`
- GPT 5.3: WAL + busy_timeout note added for analytics.db initialization
- All references to old metric names (WinRate, MedianProfit, MedianWR) updated throughout

---

## Table of Contents

- [1. Goals and Context](#1-goals-and-context)
- [2. Architecture: Three Layers](#2-architecture-three-layers)
- [3. Layer 1 — Single Study](#3-layer-1--single-study)
- [4. Layer 2 — Research Summary](#4-layer-2--research-summary)
- [5. Layer 3 — Global Analytics](#5-layer-3--global-analytics)
- [6. Unified Analytics Component](#6-unified-analytics-component)
- [7. Global Analytics DB — Schema](#7-global-analytics-db--schema)
- [8. Data Flow Between Layers](#8-data-flow-between-layers)
- [9. Full Workflow](#9-full-workflow)
- [10. Principles and Anti-Patterns](#10-principles-and-anti-patterns)
- [11. System Evolution](#11-system-evolution)
- [12. Open Questions](#12-open-questions)

---

## 1. Goals and Context

### 1.1 What the System Should Provide

- Understand which **tickers** and **timeframes** are worth trading
- Which **IS/OOS** period settings to use
- Which **strategies** work best for which tickers
- Evaluate **new strategies** against old ones
- Find **working combinations** for live trading
- Answer the question **"what if I only traded this?"**

### 1.2 Constraints and Solutions

| Constraint | Solution |
|---|---|
| 5-10 minutes to review a research | Maximum automation, auto-label, conditional formatting |
| Single user | No need for cloud/shared tools |
| No mobile access needed | Local DB instead of Google Sheets |
| Need unlimited customization | Everything in Merlin: Python + JS, no Sheets limitations |
| One-click export | Button in UI → write to global analytics DB |

### 1.3 Unit of Work — Research

A focused research effort with a specific hypothesis. Each research = **a separate .db file** in Merlin. Research runs are executed via the queue (Scheduled Run).

| Research | Goal | Composition | Studies |
|----------|------|-------------|---------|
| `S01_optimal_TF` | Find best TF for S01 | 6 tickers × 3 TFs | 18 |
| `S01_vs_S03` | Compare strategies | 2 tickers × 2 strategies × 1 TF | 4 |
| `IS_comparison` | Find optimal IS period | 6 tickers × 3 IS variants | 18 |
| `S01_full_matrix` | Full scan | 20 tickers × 3 TFs × 2 WFA modes | 120 |
| `S04_evaluation` | Evaluate new strategy | 6 tickers × 3 TFs | 18 |

### 1.4 Why Local DB Instead of Google Sheets

| Factor | Google Sheets | Local DB + Merlin UI |
|---|---|---|
| Workflow | CSV export → manual import → fill columns | One button |
| Equity aggregation | Impossible (no timestamp alignment) | Full support (Python) |
| Heatmaps | Pivot tables (limited) | Full control (JS/Python) |
| Filters/sorting | QUERY formulas (limited) | SQL (unlimited) |
| Complex calculations | Limited to Sheets formulas | Python (unlimited) |
| Scalability | Slow at 1000+ rows | SQLite — millions of rows |
| Customization | Depends on Sheets capabilities | Full |
| Mobile access | Yes | No (not needed) |
| Context switching | Merlin → browser → Sheets | Everything in Merlin |

---

## 2. Architecture: Three Layers

### 2.1 Overview

```
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                                                                                   ║
║  LAYER 1: Single Study                              Where: Merlin UI (per study) ║
║  ─────────────────────                                                            ║
║  Data: N OOS windows of one WFA study (Fixed or Adaptive)                        ║
║  Source: research DB (studies + wfa_windows)                                      ║
║  Question: "How does THIS specific combination perform?"                          ║
║                                                                                   ║
║  ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┐  ║
║  │Win 1 │Win 2 │Win 3 │Win 4 │Win 5 │Win 6 │Win 7 │Win 8 │Win 9 │Win10│Win12│  ║
║  │+8.2% │-3.1% │+5.4% │+12.1%│+2.8% │-1.5% │+7.6% │+4.2% │+9.8% │+3.1%│+5.8%│  ║
║  └──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┘  ║
║      ↓ 7 cards (value + label): Stitched OOS + Window aggregates                 ║
║  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐ ║
║  │ +58.9%   ││ -21.5%   ││ 87/169   ││  21.5%   ││10/12(83%)││  +5.2%   ││  65.3%   ║ ║
║  │NET PROFIT││MAX DRAWDN││TOT.TRADES││   WFE    ││ OOS WINS ││OOS P(med)││OOS WR(md)║ ║
║  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘ ║
║                                                                                   ║
╠═══════════════════════════════════════════════════════════════════════════════════╣
║                                                                                   ║
║  LAYER 2: Research Summary                    Where: Merlin UI (Analytics View)  ║
║  ─────────────────────────                                                        ║
║  Data: all WFA studies in one research DB                                         ║
║  Source: research DB                                                              ║
║  Question: "Which combinations work? What if I traded the selected ones?"         ║
║                                                                                   ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │ Study 1: LINK 1h    +72.8%  WFE 32%  OOS Wins 10/12  PASS   ☑             │  ║
║  │ Study 2: ETH 1h     +58.2%  WFE 28%  OOS Wins  9/12  PASS   ☑             │  ║
║  │ Study 3: LINK 4h    +31.5%  WFE 21%  OOS Wins  8/12  PASS   ☑             │  ║
║  │ Study 4: SUI 1h     +38.9%  WFE 22%  OOS Wins  7/12  MAYBE  ☐             │  ║
║  │ Study 5: ETH 30m    -15.2%  WFE  8%  OOS Wins  3/12  FAIL   ☐             │  ║
║  └─────────────────────────────────────────────────────────────────────────────┘  ║
║  Aggregate (3 selected): Portfolio equity curve + metrics                        ║
║  [Heatmaps]  [Export to Global DB]                                                ║
║                                                                                   ║
║       │ one button                                                                ║
║       ▼                                                                           ║
║                                                                                   ║
║  LAYER 3: Global Analytics                    Where: Merlin UI (Analytics View)  ║
║  ─────────────────────────                                                        ║
║  Data: all exported studies from all research                                     ║
║  Source: analytics.db (global DB, src/storage/global/)                           ║
║  Question: "What to trade globally? What are the trends?"                         ║
║                                                                                   ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │ [S01_optimal_TF]  LINK 1h   +72.8%  PASS  ☑                               │  ║
║  │ [S01_optimal_TF]  ETH 1h    +58.2%  PASS  ☑                               │  ║
║  │ [S01_vs_S03]      LINK 1h   +41.2%  MAYBE ☐                               │  ║
║  │ [IS_comparison]   LINK 1h   +72.8%  PASS  ☑                               │  ║
║  │ ...accumulates over months...                                                │  ║
║  └─────────────────────────────────────────────────────────────────────────────┘  ║
║  Aggregate  [Equity Curve]  [Heatmaps]  [Insights Journal]                       ║
║                                                                                   ║
║  *** INVARIANT: Layer 3 = Layer 2 + research column + research filter            ║
║                                  + insights journal                              ║
║  Same UI component, same set of columns, filters, checkboxes.                    ║
║  The only difference — a different DB and one additional column.                  ║
║                                                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
```

### 2.2 Key Architectural Decision: One UI — Two Data Sources

Layer 2 and Layer 3 are **structurally identical**. Same table, same columns, filters, checkboxes, aggregate equity, heatmaps. Differences:

| | Layer 2 | Layer 3 |
|---|---|---|
| Data source | Current research DB | `analytics.db` (global) |
| `research` column | No (single research) | Yes (which research it came from) |
| Filter by research | No | Yes |
| Insights journal | No | Yes |
| Export button | "Export to Global DB" | No (final destination) |

**Invariant:** the column set, checkbox logic, and equity aggregation in Layer 3 fully mirrors Layer 2. This is not merely an architectural principle — it affects the `runs` table schema and indexes in `analytics.db`.

This means: **one UI component is built once** and connected to different data sources.

### 2.3 Principle: No Data Duplication

| Data | Stored in | Do NOT duplicate in |
|------|-----------|---------------------|
| Per-window metrics (N windows) | Research DB: `wfa_windows` | Layer 2, Layer 3 |
| Per-window equity curves | Research DB: `wfa_windows` | Layer 2, Layer 3 |
| Study-level stitched metrics | Research DB: `studies` | — |
| Study-level window aggregates | Computed from `wfa_windows` in Python | Exported to analytics.db |
| Stitched equity curve | Research DB: `studies` | Copied to analytics.db on export |
| Labels, notes | Research DB + analytics.db | — |
| Aggregated equity (portfolio) | Computed on-the-fly in UI | Not stored |
| Heatmaps | Computed on-the-fly in UI | Not stored |
| Insights journal | analytics.db: `insights` | Not stored elsewhere |

---

## 3. Layer 1 — Single Study

### 3.1 Purpose

Detailed view of a single WFA study (Fixed or Adaptive). Answers the question: **"How does this specific ticker × TF × strategy × settings combination perform?"**

### 3.2 Layer 1 Questions

| # | Question | Metric |
|---|----------|--------|
| 1 | Is it profitable overall? | NET PROFIT (Stitched OOS) |
| 2 | What is the risk? | MAX DRAWDOWN (Stitched OOS) |
| 3 | Enough activity? What is trade win rate? | TOTAL TRADES: winning/total (Stitched OOS) |
| 4 | Does IS predict OOS? | WFE |
| 5 | How many OOS windows were profitable? | OOS WINS: N/M (%) |
| 6 | Typical return per window? | OOS PROFIT (med) |
| 7 | Typical trade win rate per window? | OOS WIN RATE (med) |

### 3.3 Final Metric Set — Final Names

**7 cards** in "value on top / label below" format (existing UI format preserved, 2 new cards added):

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  +284.31%    │ │  -34.95%     │ │  101/169     │ │   22.4%      │
│  NET PROFIT  │ │ MAX DRAWDOWN │ │ TOTAL TRADES │ │    WFE       │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘

┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│10/12 (83%)   │ │   +12.6%     │ │   65.3%      │
│  OOS WINS    │ │OOS PROFIT(med│ │OOS WIN RT(med│
└──────────────┘ └──────────────┘ └──────────────┘
```

**Naming logic:**

| Group | Metrics | Identifier |
|-------|---------|------------|
| Stitched OOS | NET PROFIT, MAX DRAWDOWN, TOTAL TRADES | Computed from the full stitched OOS equity curve |
| Study-level | WFE | IS→OOS efficiency, not tied to a single period |
| Window aggregates | OOS WINS, OOS PROFIT (med), OOS WIN RATE (med) | Aggregates over individual OOS windows; OOS prefix + (med) suffix where median is used |

The `OOS` prefix on window-level metrics distinguishes them from stitched metrics. The `(med)` suffix explicitly marks the aggregation method, leaving room for `(avg)` in the future without renaming.

**Description of each metric:**

| UI Label | Format | DB Column | Level | What it means |
|----------|--------|-----------|-------|---------------|
| `NET PROFIT` | +284.31% | `stitched_oos_net_profit_pct` | Stitched OOS | Total profit across the full stitched OOS equity |
| `MAX DRAWDOWN` | -34.95% | `stitched_oos_max_drawdown_pct` | Stitched OOS | Maximum drawdown of the stitched equity |
| `TOTAL TRADES` | 101/169 | `stitched_oos_winning_trades` / `stitched_oos_total_trades` | Stitched OOS | Winning trades / total trades — trade-level win rate |
| `WFE` | 22.4% | `best_value` | Study | Walk-Forward Efficiency: how well IS predicts OOS |
| `OOS WINS` | 10/12 (83%) | `stitched_oos_win_rate` (UI label changed) + `total_windows` | Window-level | How many OOS windows were profitable / total windows |
| `OOS PROFIT (med)` | +12.6% | `median_window_profit` | Window-level | Median net profit across OOS windows |
| `OOS WIN RATE (med)` | 65.3% | `median_window_wr` | Window-level | Median trade win rate across OOS windows |

**Note: two types of win rate**

`TOTAL TRADES: 101/169` — trade win rate across the entire stitched equity (169 total trades, 101 profitable).

`OOS WIN RATE (med): 65.3%` — typical trade win rate within a single OOS window. Computed as the median of `wfa_windows.oos_win_rate` (trade-level) across all windows.

`OOS WINS: 10/12 (83%)` — percentage of OOS periods that ended in profit. Not a trade win rate.

**Combination of OOS WINS + OOS PROFIT (med) — answer to the stability question:**

| OOS WINS | OOS PROFIT (med) | Conclusion |
|----------|-----------------|------------|
| 10/12 (83%) | +12% | Strong: most windows profitable, typical gain is substantial |
| 10/12 (83%) | +1% | Caution: windows are technically profitable but typical gain is negligible |
| 5/12 (42%) | +14% | Mixed: half the windows profitable, but when yes — good earnings |
| 3/12 (25%) | -8% | Weak: most windows are unprofitable |

Median is robust against outliers: if 1 window is +400% and 11 are at -5%, the median shows -5%, not a misleading +28%.

**OOS WIN RATE (med) — strategy profile:**

| OOS WIN RATE (med) | Interpretation |
|--------------------|----------------|
| >60% | Win-rate driven: strategy earns through frequency of wins |
| 45-55% | Reward-driven: earns through size of wins, not frequency |
| <45% | Either very high RR-ratio, or strategy is weak |

### 3.4 Current State vs New

```
Current view (5 cards, value + label):
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   +284.31%   │ │   -34.95%    │ │     169      │ │    22.4%     │ │    70.0%     │
│  NET PROFIT  │ │ MAX DRAWDOWN │ │ TOTAL TRADES │ │     WFE      │ │   WIN RATE   │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
  ↑ WIN RATE here = % of profitable OOS windows, not trade win rate (verified in code)

New view (7 cards, same format):
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   +284.31%   │ │   -34.95%    │ │   101/169    │ │    22.4%     │
│  NET PROFIT  │ │ MAX DRAWDOWN │ │ TOTAL TRADES │ │     WFE      │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘

┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ 10/12 (83%)  │ │    +12.6%    │ │    65.3%     │
│   OOS WINS   │ │OOS PROFIT(med│ │OOS WIN RT(med│
└──────────────┘ └──────────────┘ └──────────────┘

Changes:
  - WIN RATE → OOS WINS (renamed + new format N/M %)
  - TOTAL TRADES: 169 → 101/169 (winning trades added)
  - + 2 new cards: OOS PROFIT (med), OOS WIN RATE (med)
```

### 3.5 Layer 1 Metric Dictionary

Exact formulas, null-policy, rounding. Used as a reference during implementation — prevents discrepancies between Python computation and JS rendering.

| UI Label | Formula | Null / edge case | Rounding |
|----------|---------|-----------------|----------|
| `NET PROFIT` | `(stitched_equity_final / 100.0 - 1) × 100` | `0.0` if no trades | 2 decimal places, + / − sign |
| `MAX DRAWDOWN` | peak-to-trough on stitched equity array | `0.0` if no trades | 2 decimal places, − sign |
| `TOTAL TRADES` | `stitched_winning_trades / stitched_total_trades` | `"0/0"` if no trades | integers |
| `WFE` | `(oos_objective / is_objective) × 100` | `"N/A"` if no valid windows | 1 decimal place |
| `OOS WINS` | `profitable_windows / total_windows` + `(profitable_windows_pct)%` | `"0/0 (0%)"` if no windows | integers, 0 decimal places for % |
| `OOS PROFIT (med)` | `statistics.median([w.oos_net_profit_pct for w in windows])` | `"N/A"` if `len(windows) < 1` | 1 decimal place, + / − sign |
| `OOS WIN RATE (med)` | `statistics.median([w.oos_win_rate for w in windows])` where `oos_win_rate` is trade-level | `"N/A"` if `len(windows) < 1` | 1 decimal place |

**Data sources (DB columns):**

| UI Label | DB Table | DB Column |
|----------|----------|-----------|
| `NET PROFIT` | `studies` | `stitched_oos_net_profit_pct` |
| `MAX DRAWDOWN` | `studies` | `stitched_oos_max_drawdown_pct` |
| `TOTAL TRADES` (denominator) | `studies` | `stitched_oos_total_trades` |
| `TOTAL TRADES` (numerator) | `studies` | `stitched_oos_winning_trades` *(new)* |
| `WFE` | `studies` | `best_value` |
| `OOS WINS` (numerator) | `studies` | `profitable_windows` *(new)* |
| `OOS WINS` (denominator) | `studies` | `total_windows` *(new)* |
| `OOS WINS` (%) | `studies` | `stitched_oos_win_rate` *(UI label changed)* |
| `OOS PROFIT (med)` | `studies` | `median_window_profit` *(new)* |
| `OOS WIN RATE (med)` | `studies` | `median_window_wr` *(new)* |

### 3.6 Computing Aggregates

**All aggregates are computed in Python** when a WFA study finishes and are saved to the `studies` table. This allows Layer 2 to build the summary table with a single SQL query, no recomputation needed.

Medians are computed via `statistics.median()` (Python stdlib), not SQL. SQLite has no built-in `MEDIAN()` function — Python works consistently across all environments.

```python
import statistics

oos_profits    = [w.oos_net_profit_pct for w in windows]
oos_trade_wr   = [w.oos_win_rate for w in windows]   # trade-level per window

profitable_windows     = sum(1 for p in oos_profits if p > 0)
profitable_windows_pct = (profitable_windows / len(windows)) * 100.0

median_window_profit   = statistics.median(oos_profits)
median_window_wr       = statistics.median(oos_trade_wr)

# Winning trades from stitched OOS result (StrategyResult.trades):
stitched_winning_trades = sum(1 for t in stitched_result.trades if t.pnl > 0)

# Store in DB, do NOT show in Layer 1 UI:
worst_window_profit = min(oos_profits)
worst_window_dd     = min(w.oos_max_drawdown_pct for w in windows)
```

### 3.7 New Columns in `studies` Table

```sql
-- TOTAL TRADES: numerator (winning trades from stitched OOS)
ALTER TABLE studies ADD COLUMN stitched_oos_winning_trades INTEGER;

-- OOS WINS: numerator and denominator
ALTER TABLE studies ADD COLUMN profitable_windows INTEGER;
ALTER TABLE studies ADD COLUMN total_windows INTEGER;

-- OOS PROFIT (med) and OOS WIN RATE (med)
ALTER TABLE studies ADD COLUMN median_window_profit REAL;
ALTER TABLE studies ADD COLUMN median_window_wr REAL;

-- For Layer 2 auto-label (computed from profitable_windows / total_windows)
-- Note: stitched_oos_win_rate already stores this %, UI label changes to OOS WINS.
-- No additional column needed.

-- Stored for Layer 2 filtering, not shown in Layer 1 UI
ALTER TABLE studies ADD COLUMN worst_window_profit REAL;
ALTER TABLE studies ADD COLUMN worst_window_dd REAL;

-- Manual labels (filled in Layer 2)
ALTER TABLE studies ADD COLUMN analytics_label TEXT;
ALTER TABLE studies ADD COLUMN analytics_note TEXT;
```

Total new columns: 9. Computed once when WFA finishes, stored permanently.

**Note on `stitched_oos_win_rate`:** the DB column remains unchanged (stores % of profitable windows). Only the UI label changes: `WIN RATE` → `OOS WINS`. Additionally, `profitable_windows` (numerator) and `total_windows` (denominator) are added for the `N/M` format.

---

## 4. Layer 2 — Research Summary

### 4.1 Purpose

Summary analytics view of **all WFA studies in one research DB**. Answers: **"Which combinations work? What if I traded only the selected ones?"**

### 4.2 Layer 2 Questions

**Combination evaluation:**

| # | Question | How to answer |
|---|----------|---------------|
| 1 | Which ticker×TF combinations are profitable? | Summary table + conditional formatting |
| 2 | Which are unprofitable? | Filter profit < 0, label = FAIL |
| 3 | Which strategy is better? | Filter by strategy |
| 4 | Fixed vs Adaptive? | Filter by WFA mode |
| 5 | Which IS/OOS is optimal? | Filter by is/oos |

**Portfolio questions:**

| # | Question | How to answer |
|---|----------|---------------|
| 6 | What if trading ALL? | All checkboxes → portfolio equity curve + metrics |
| 7 | What if only PASS? | PASS checkboxes → recalculate |
| 8 | What if only 1h? | Filter TF → checkboxes → recalculate |
| 9 | What if S01 LINK/ETH 1h? | Manual selection → recalculate |
| 10 | Combined profit/DD/trades? | Portfolio metrics for checked items |

**Data quality:**

| # | Question | How to answer |
|---|----------|---------------|
| 11 | Are all studies valid? | Status + window count |
| 12 | Anomalies? | 0 trades, DD > 50%, WFE > 100% |
| 13 | What to redo? | Label + note |

### 4.3 Layer 2 Visualization

```
┌─── Research Analytics ──────────────────────────────────────────────────────────────────────┐
│                                                                                               │
│  DB: S01_all_tickers_feb2026.db                                    Studies: 18  │  WFA only  │
│                                                                                               │
│  ═══ Aggregated Equity Curve (3 selected) ══════════════════════════════════════════════     │
│                                                                                               │
│  200% ┤                                                              ╭───                     │
│  180% ┤                                                        ╭─────╯                        │
│  160% ┤                                                  ╭─────╯                              │
│  140% ┤                                            ╭─────╯                                    │
│  120% ┤                                      ╭─────╯                                          │
│  100% ┤──────────────────────────────────────╯                                                │
│       └──┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬───          │
│         Jan   Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec               │
│                                                                                               │
│  ═══ Portfolio Metrics (3 selected) ════════════════════════════════════════════════════     │
│                                                                                               │
│  Portfolio Profit: +54.2%  │  Portfolio MaxDD: -22.1%  │  Total Trades: 228  │  N: 3/18     │
│  Avg OOS Wins: 83.3%       │  Avg WFE: 27.5%           │  Avg OOS Profit(med): +10.4%       │
│                                                                                               │
│  ═══ Filters ══════════════════════════════════════════════════════════════════════════     │
│                                                                                               │
│  Strategy:[All▾]  Symbol:[All▾]  TF:[All▾]  IS/OOS:[All▾]  WFA:[All▾]  Label:[All▾]        │
│  [Select All]  [Select PASS only]  [Deselect All]                                             │
│                                                                                               │
│  ═══ Summary Table ══════════════════════════════════════════════════════════════════════     │
│                                                                                               │
│  ☑│#│Strategy│ Symbol      │TF │WFA  │IS/OOS│Profit%│MaxDD%│WFE% │OOS Wins  │OOS P(med)│Label│
│  ─┼─┼────────┼─────────────┼───┼─────┼──────┼───────┼──────┼─────┼──────────┼──────────┼─────│
│  ☑│1│S01 v26 │ LINKUSDT.P  │1h │Fixed│90/30 │ +72.8 │ 22.3 │ 32.1│10/12(83%)│   +14.2  │PASS │
│  ☑│2│S01 v26 │ ETHUSDT.P   │1h │Fixed│90/30 │ +58.2 │ 16.8 │ 28.9│ 9/12(75%)│   +11.8  │PASS │
│  ☑│3│S01 v26 │ LINKUSDT.P  │4h │Fixed│90/30 │ +31.5 │ 19.8 │ 21.4│ 8/12(67%)│    +7.3  │PASS │
│  ☐│4│S01 v26 │ SUIUSDT.P   │1h │Fixed│90/30 │ +38.9 │ 21.1 │ 22.8│ 7/12(58%)│    +5.1  │MAYBE│
│  ☐│5│S01 v26 │ ETHUSDT.P   │4h │Fixed│90/30 │ +22.1 │ 15.7 │ 18.9│ 7/12(58%)│    +3.2  │MAYBE│
│  ☐│6│S01 v26 │ ETHUSDT.P   │30m│Fixed│90/30 │ -15.2 │ 32.1 │  8.5│ 3/12(25%)│    -4.8  │FAIL │
│  ☐│7│S01 v26 │ LINKUSDT.P  │30m│Fixed│90/30 │ -28.4 │ 41.2 │  5.1│ 2/12(17%)│    -7.1  │FAIL │
│  ...                                                                                           │
│  ─┼─┼────────┼─────────────┼───┼─────┼──────┼───────┼──────┼─────┼──────────┼──────────┼─────│
│    │ │        │             │   │     │ AVG: │ +23.8 │ 23.0 │ 19.2│          │          │     │
│                                                                                               │
│  Conditional formatting:                                                                       │
│    Profit%:       ■ >+30  ■ 0..+30  ■ <0       WFE%:        ■ >20  ■ 10-20  ■ <10           │
│    MaxDD%:        ■ <20   ■ 20-35   ■ >35       OOS Wins:    ■ >70% ■ 40-70% ■ <40%          │
│    OOS P(med):    ■ >+5   ■ 0..+5   ■ <0        Label:       ■ PASS ■ MAYBE  ■ FAIL          │
│                                                                                               │
│  ═══ Heatmap: Profit% by Symbol × TF ════════════════════════════════════════════════════     │
│                                                                                               │
│                │  30m    │   1h    │   4h    │  AVG    │                                       │
│  ──────────────┼─────────┼─────────┼─────────┼─────────┤                                      │
│  ETHUSDT.P     │  -15.2  │  +58.2  │  +22.1  │  +21.7  │                                      │
│  LINKUSDT.P    │  -28.4  │  +72.8  │  +31.5  │  +25.3  │                                      │
│  SUIUSDT.P     │  -22.1  │  +38.9  │  +18.7  │  +11.8  │                                      │
│  ──────────────┼─────────┼─────────┼─────────┼─────────┤                                      │
│  AVG           │   -6.0  │  +45.9  │  +23.8  │         │                                      │
│                                                                                               │
│  ═══ Actions ══════════════════════════════════════════════════════════════════════════     │
│                                                                                               │
│  [Export Selected to Global DB]   [Save Labels]   [Export CSV]                                │
│                                                                                               │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Summary Table Columns

| # | Column | Source | Description |
|---|--------|--------|-------------|
| — | `☑` | UI state | Checkbox for aggregation selection |
| 1 | `Strategy` | `studies.strategy_id` + version | Strategy and version |
| 2 | `Symbol` | Parsed from `csv_file_name` | Ticker |
| 3 | `TF` | Parsed from `csv_file_name` | Timeframe |
| 4 | `WFA` | `studies.adaptive_mode` | Fixed / Adaptive |
| 5 | `IS/OOS` | `studies.is_period_days` + config_json | WFA periods |
| 6 | `Profit%` | `studies.stitched_oos_net_profit_pct` | Stitched OOS Net Profit |
| 7 | `MaxDD%` | `studies.stitched_oos_max_drawdown_pct` | Stitched OOS Max Drawdown |
| 8 | `WFE%` | `studies.best_value` | Walk-Forward Efficiency |
| 9 | `OOS Wins` | `profitable_windows` / `total_windows` (%) | Profitable windows / total |
| 10 | `OOS P(med)` | `studies.median_window_profit` | OOS PROFIT (med) |
| 11 | `Label` | `studies.analytics_label` | PASS / MAYBE / FAIL |

### 4.5 Auto-Label Logic

```
PASS:   profit > 0  AND  maxDD < 35  AND  profitable_windows_pct > 60  AND  total_trades >= 30
FAIL:   profit <= 0  OR  maxDD > 50  OR  profitable_windows_pct < 30
MAYBE:  everything else
```

Computed automatically when Research Analytics is opened. Manual override is saved to `studies.analytics_label`. Thresholds are configurable and should be adjusted after accumulating data.

### 4.6 Portfolio Metrics for Selected Studies

Portfolio Profit% and MaxDD% are computed **from the aggregated equity curve**, not as SUM/AVG of individual values (since adding percentages is mathematically incorrect).

```
Portfolio equity(t) = AVG( equity_1(t), equity_2(t), ..., equity_N(t) )

Portfolio Profit% = (portfolio_equity(t_end) / 100 - 1) × 100
Portfolio MaxDD%  = peak-to-trough drawdown on portfolio_equity(t)
```

Both metrics are computed from the equity curve starting from Phase 1 MVP. There is no AVG approximation at an intermediate stage — this avoids logic migration pain later.

Auxiliary aggregates (not "portfolio" metrics in the strict sense, explicitly labeled as "Avg"):

| Metric | Formula | Meaning |
|--------|---------|---------|
| Total Trades | SUM(total_trades_i) | Total activity |
| Avg OOS Wins | AVG(profitable_windows_pct_i) | Average % of profitable windows |
| Avg WFE | AVG(wfe_i) | Average IS→OOS efficiency |
| Avg OOS Profit(med) | AVG(median_window_profit_i) | Average typical return per window |

### 4.7 Aggregated Equity Curve — Time Range Rule

**MVP rule: intersection only.**

If selected studies have different OOS time ranges (different tickers, different CSV dates), only the **common period** present in all selected studies is used for aggregation. Studies with partially overlapping periods are not included in the calculation beyond the intersection.

This decision is closed as MVP — more complex approaches (gap-filling, weighted) can be added in Phase 2 if needed.

---

## 5. Layer 3 — Global Analytics

### 5.1 Purpose

Accumulates data **across all research** (all research .db files). Global trends, strategic decisions, insights journal. Fully within Merlin UI, data stored in `analytics.db`.

### 5.2 Invariant: Layer 3 = Layer 2 + research

Layer 3 uses the **same Analytics Component** as Layer 2, without exception:
- Same table columns
- Same checkbox logic and aggregation
- Same aggregated equity (portfolio metrics from curve)
- Same filters (Strategy, Symbol, TF, WFA, IS/OOS, Label)
- Same heatmaps

**Layer 3 additions relative to Layer 2:**
1. `Research` column (which research this row came from)
2. Filter by `Research`
3. Cross-research heatmaps (PASS rate across all research)
4. Insights journal

### 5.3 Layer 3 Questions

**Strategic decisions:**

| # | Question | How to answer |
|---|----------|---------------|
| 1 | Which tickers to trade? | PASS rate by symbol (all research) |
| 2 | Which timeframes to trade? | PASS rate by TF |
| 3 | Which strategy? | Median profit by strategy |
| 4 | Which IS/OOS? | Profit/WFE comparison by spec |
| 5 | Fixed vs Adaptive? | Comparison by WFA mode |
| 6 | Which post-process filters help? | Comparison with/without DSR, FT |

**Trends:**

| # | Question | How to answer |
|---|----------|---------------|
| 7 | Are results improving? | Profit trend by research date |
| 8 | Is the new strategy better? | Strategy version comparison |

**Production:**

| # | Question | How to answer |
|---|----------|---------------|
| 9 | What to run live? | Top-N by PASS rate + profit |
| 10 | What to exclude? | Consistently FAIL + note |

### 5.4 Insights Journal

```
═══ Insights ══════════════════════════════════════════════════════════════════════════

[+ Add Insight]

│ Date       │ Research          │ Scope    │ Statement                             │ Evidence              │ Action                │
│────────────┼───────────────────┼──────────┼───────────────────────────────────────┼───────────────────────┼───────────────────────│
│ 2026-02-15 │ S01_optimal_TF    │ TF       │ 1h consistently beats 30m and 4h     │ avg profit +46% vs -6%│ Focus on 1h           │
│ 2026-02-15 │ S01_optimal_TF    │ TF       │ 30m doesn't work on any ticker       │ 0/6 PASS              │ Exclude 30m            │
│ 2026-02-15 │ S01_optimal_TF    │ SYMBOL   │ LINK is best ticker for S01          │ 1h: +72.8%, WFE 32%  │ Priority for live       │
│ 2026-02-17 │ S01_vs_S03        │ STRATEGY │ S01 is more stable than S03          │ 2/2 PASS vs 0/2      │ S01 as primary          │
│ 2026-02-19 │ IS_comparison     │ SPEC     │ IS=90 is optimal                     │ WFE: 32.1 vs 22.5    │ IS=90 as standard       │
│ 2026-02-20 │ —                 │ PLAN     │ Trade: S01, LINK 1h, IS=90/OOS=30   │ All research          │ Paper trading           │
```

**Scope categories:**

| Scope | Purpose |
|-------|---------|
| HYPO | Hypothesis (before research) |
| TF | Conclusion about timeframes |
| SYMBOL | Conclusion about tickers |
| STRATEGY | Strategy comparison |
| SPEC | IS/OOS settings, sampler, budget |
| PP | Post-process filters |
| PARAM | Strategy parameters (future) |
| PLAN | Final decisions |

---

## 6. Unified Analytics Component

### 6.1 Component Structure

A single JS module that accepts an array of study rows and renders:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  ┌─ Equity Chart ─────────────────────────────────────────────────┐    │
│  │  Portfolio equity curve for selected studies                   │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─ Portfolio Metrics Bar ────────────────────────────────────────┐    │
│  │  Portfolio Profit | Portfolio MaxDD | Trades | Avg OOS Wins    │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─ Filters ──────────────────────────────────────────────────────┐    │
│  │  [Research ▾]* [Strategy ▾] [Symbol ▾] [TF ▾] [WFA ▾] ...    │    │
│  │  [Select All] [Select PASS] [Deselect]                         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─ Summary Table ────────────────────────────────────────────────┐    │
│  │  ☑ # Strategy Symbol TF WFA IS/OOS Profit MaxDD WFE OOSWins Label │ │
│  │  ... rows with conditional formatting ...                      │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─ Heatmaps (collapsible) ──────────────────────────────────────┐    │
│  │  Profit by Symbol×TF  │  WFE by Symbol×TF                     │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─ Insights* ────────────────────────────────────────────────────┐    │
│  │  [+ Add]  Journal entries                                      │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  * Research filter and Insights — Layer 3 (Global mode) only           │
│                                                                         │
│  ┌─ Actions ──────────────────────────────────────────────────────┐    │
│  │  [Export to Global DB]*  [Save Labels]  [Export CSV]           │    │
│  │  * Layer 2 only                                                │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 New API Endpoints

| Endpoint | Method | Layer | Purpose |
|----------|--------|-------|---------|
| `GET /api/analytics/summary` | GET | L2 | Summary table of WFA studies in current DB |
| `POST /api/analytics/equity` | POST | L2 | Portfolio equity for selected study_ids |
| `POST /api/analytics/heatmap` | POST | L2 | Heatmap data |
| `POST /api/analytics/label` | POST | L2 | Save label + note for a study |
| `POST /api/analytics/export-global` | POST | L2→L3 | Export selected studies to analytics.db |
| `GET /api/global/summary` | GET | L3 | Summary table from analytics.db |
| `POST /api/global/equity` | POST | L3 | Portfolio equity from analytics.db |
| `POST /api/global/heatmap` | POST | L3 | Heatmap from analytics.db |
| `GET /api/global/insights` | GET | L3 | List insights |
| `POST /api/global/insights` | POST | L3 | Add insight |
| `DELETE /api/global/insights/<id>` | DELETE | L3 | Delete insight |

### 6.3 UI Navigation

```
Results Page (existing)
  │
  ├── Studies Manager (left panel, already exists)
  │   ├── Study list
  │   └── [Research Analytics] button  → Layer 2 view
  │
  └── [Global Analytics] button (header or sidebar) → Layer 3 view
```

---

## 7. Global Analytics DB — Schema

### 7.1 Location

**`src/storage/global/analytics.db`** — separate subdirectory, fixed name.

Reason: in the current codebase, `_pick_newest_db()` and `list_db_files()` in `storage.py` glob `*.db` in `STORAGE_DIR`. If `analytics.db` were placed in `src/storage/` alongside research DBs, Merlin would treat it as another research database (and might select it as the active default). The separate `src/storage/global/` directory isolates the global DB from this logic.

**Git:** the current `.gitignore` covers `src/storage/` — verify that the rule extends to the `src/storage/global/` subdirectory. Add an explicit entry if needed:
```gitignore
src/storage/global/*.db
src/storage/global/*.db-wal
src/storage/global/*.db-shm
```
The directory is tracked via `src/storage/global/.gitkeep`.

### 7.2 analytics.db Initialization

When creating analytics.db, enable the same modes used for research DBs:

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")   # 5 seconds wait on locks
conn.execute("PRAGMA foreign_keys=ON")
```

### 7.3 `runs` Table

```sql
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source
    research TEXT NOT NULL,              -- research name (from .db filename or manual)
    source_db TEXT,                      -- path to source research .db (for reference)
    study_id TEXT UNIQUE NOT NULL,       -- study_id from research DB (deduplication)
    -- Note: study_id is generated via uuid.uuid4(); collisions between
    -- different .db files are practically impossible (p ≈ 1/2^122 per pair).
    -- source_db is stored for visibility and debugging, not used as a key.
    exported_at TEXT,                    -- export timestamp

    -- Identification
    strategy TEXT NOT NULL,              -- "S01 v26"
    symbol TEXT NOT NULL,                -- "LINKUSDT.P"
    tf TEXT NOT NULL,                    -- "1h"

    -- Settings
    wfa_mode TEXT,                       -- "fixed" / "adaptive"
    is_oos TEXT,                         -- "90/30"
    pp_spec TEXT,                        -- "DSR FT15" (string for MVP, split if needed)
    objectives TEXT,                     -- "net_profit_pct, max_drawdown_pct"
    sampler TEXT,                        -- "tpe"
    budget INTEGER,                      -- 500

    -- Stitched OOS metrics (correspond to Layer 1: NET PROFIT, MAX DRAWDOWN, TOTAL TRADES)
    profit_pct REAL,
    max_dd_pct REAL,
    total_trades INTEGER,
    winning_trades INTEGER,              -- for TOTAL TRADES: winning/total format

    -- Study-level
    wfe_pct REAL,                        -- WFE

    -- Window aggregates (correspond to Layer 1: OOS WINS, OOS PROFIT(med), OOS WIN RATE(med))
    total_windows INTEGER,
    profitable_windows INTEGER,
    profitable_windows_pct REAL,         -- OOS WINS (%)
    worst_window_profit REAL,            -- stored, not shown in Layer 1
    worst_window_dd REAL,                -- stored, not shown in Layer 1
    median_window_profit REAL,           -- OOS PROFIT (med)
    median_window_wr REAL,               -- OOS WIN RATE (med)

    -- Equity curve (JSON, for on-demand portfolio aggregation)
    equity_curve_json TEXT,
    equity_timestamps_json TEXT,

    -- Labels
    auto_label TEXT,                     -- computed at export time
    label TEXT,                          -- manual override
    note TEXT                            -- comment
);

CREATE INDEX IF NOT EXISTS idx_runs_research ON runs(research);
CREATE INDEX IF NOT EXISTS idx_runs_strategy ON runs(strategy);
CREATE INDEX IF NOT EXISTS idx_runs_symbol ON runs(symbol);
CREATE INDEX IF NOT EXISTS idx_runs_tf ON runs(tf);
CREATE INDEX IF NOT EXISTS idx_runs_label ON runs(label);
```

### 7.4 `insights` Table

```sql
CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT (datetime('now')),
    research TEXT,                        -- which research (optional)
    scope TEXT NOT NULL,                  -- HYPO/TF/SYMBOL/STRATEGY/SPEC/PP/PARAM/PLAN
    statement TEXT NOT NULL,              -- the insight itself
    evidence TEXT,                        -- what it's based on
    action TEXT                           -- concrete next step
);

CREATE INDEX IF NOT EXISTS idx_insights_research ON insights(research);
CREATE INDEX IF NOT EXISTS idx_insights_scope ON insights(scope);
```

### 7.5 Deduplication and Updates

When exporting from Layer 2 → Layer 3, **UPSERT** (`INSERT ... ON CONFLICT DO UPDATE`) is used instead of `INSERT OR REPLACE`.

Reason: `REPLACE` in SQLite is implemented as DELETE + INSERT, which destroys the row and creates a new one (losing `id`). UPSERT updates fields of the existing row, preserving manual labels.

```sql
INSERT INTO runs (study_id, research, strategy, symbol, tf, ...)
VALUES (?, ?, ?, ?, ?, ...)
ON CONFLICT(study_id) DO UPDATE SET
    research               = excluded.research,
    profit_pct             = excluded.profit_pct,
    max_dd_pct             = excluded.max_dd_pct,
    total_trades           = excluded.total_trades,
    winning_trades         = excluded.winning_trades,
    wfe_pct                = excluded.wfe_pct,
    total_windows          = excluded.total_windows,
    profitable_windows     = excluded.profitable_windows,
    profitable_windows_pct = excluded.profitable_windows_pct,
    median_window_profit   = excluded.median_window_profit,
    median_window_wr       = excluded.median_window_wr,
    worst_window_profit    = excluded.worst_window_profit,
    worst_window_dd        = excluded.worst_window_dd,
    equity_curve_json      = excluded.equity_curve_json,
    equity_timestamps_json = excluded.equity_timestamps_json,
    auto_label             = excluded.auto_label,
    exported_at            = excluded.exported_at;
    -- label and note are NOT updated: manual edits are preserved on re-export
```

---

## 8. Data Flow Between Layers

### 8.1 Detailed Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  MERLIN                                                                                  │
│                                                                                          │
│  ┌─ Research DB (one per research) ──────────────────────────────────────────────────┐  │
│  │                                                                                    │  │
│  │  studies                              wfa_windows                                 │  │
│  │  ┌─────────────────────────────┐      ┌─────────────────────────────┐             │  │
│  │  │ study_id                    │──┐   │ study_id (FK)               │             │  │
│  │  │ strategy_id                 │  │   │ window_number               │             │  │
│  │  │ csv_file_name               │  ├──→│ oos_net_profit_pct          │             │  │
│  │  │ stitched_oos_net_profit_pct │  │   │ oos_max_drawdown_pct        │             │  │
│  │  │ stitched_oos_max_drawdown.. │  │   │ oos_win_rate (trade-level)  │             │  │
│  │  │ stitched_oos_total_trades   │  │   │ oos_equity_curve            │             │  │
│  │  │ stitched_oos_winning_trades*│  │   │ param_id                    │             │  │
│  │  │ stitched_oos_win_rate       │  │   └─────────────────────────────┘             │  │
│  │  │   (UI: OOS WINS %)          │  │                                                │  │
│  │  │ best_value (WFE)            │  │   * new columns in studies                     │  │
│  │  │ total_windows           *   │  │   Computed in Python when WFA finishes         │  │
│  │  │ profitable_windows      *   │  │                                                │  │
│  │  │ profitable_windows_pct  *   │  │                                                │  │
│  │  │ worst_window_profit     *   │  │                                                │  │
│  │  │ worst_window_dd         *   │  │                                                │  │
│  │  │ median_window_profit    *   │  │                                                │  │
│  │  │ median_window_wr        *   │  │                                                │  │
│  │  │ analytics_label         *   │  │                                                │  │
│  │  │ analytics_note          *   │  │                                                │  │
│  │  └─────────────────────────────┘  │                                                │  │
│  └────────────────────────────────────┼────────────────────────────────────────────────┘  │
│                                       │                                                   │
│  ┌─ Layer 1: Study View ─────────────┼──────────────────────────────────────┐            │
│  │  7 cards (value + label):         │                                      │            │
│  │  NET PROFIT / MAX DRAWDOWN /       │  Source: studies table               │            │
│  │  TOTAL TRADES (W/T) / WFE /        │  (pre-computed aggregates)           │            │
│  │  OOS WINS (N/M%) /                 │                                      │            │
│  │  OOS PROFIT (med) /                │                                      │            │
│  │  OOS WIN RATE (med)               │                                      │            │
│  └────────────────────────────────────┼──────────────────────────────────────┘            │
│                                       │                                                   │
│  ┌─ Layer 2: Research Analytics ─────┼──────────────────────────────────────┐            │
│  │  1. Query all WFA studies ─────────┘                                      │            │
│  │  2. Summary table (from pre-computed aggregates)                          │            │
│  │  3. Compute auto-labels                                                   │            │
│  │  4. Table + filters + checkboxes + portfolio equity + heatmaps           │            │
│  │  5. [Save Labels] → analytics_label/note in studies table                │            │
│  │  6. [Export to Global DB] → UPSERT into analytics.db                     │            │
│  └─────────────────────────┬─────────────────────────────────────────────────┘            │
│                            │  one-click export (selected studies)                         │
│                            ▼                                                              │
│  ┌─ src/storage/global/analytics.db ────────────────────────────────────────────────┐   │
│  │  runs table (study_id UNIQUE, WAL mode)    insights table                         │   │
│  │  Accumulates across all research                                                   │   │
│  └────────────────────────────────────────────────────────────────────────────────────┘   │
│                            │                                                              │
│  ┌─ Layer 3: Global Analytics ──────────────────────────────────────────────────────┐    │
│  │  Same UI component as Layer 2 (invariant)                                        │    │
│  │  + research column + filter by research                                           │    │
│  │  + cross-research heatmaps (PASS rate)                                            │    │
│  │  + insights journal                                                               │    │
│  └──────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Full Workflow

```
STAGE 1: Planning                                         Where: Merlin Global Analytics
─────────────────
  → Record hypothesis in Insights journal (scope = HYPO):
    "S01 on 1h beats 30m and 4h"
  → Create new research DB in Merlin (name: S01_optimal_TF)
  → Set up queue: 6 tickers × 3 TFs = 18 studies


STAGE 2: Execution                                        Where: Merlin
──────────────────
  → Run queue (Scheduled Run)
  → Wait for completion
  → Aggregates computed automatically in Python when each study is saved


STAGE 3: Layer 1 — Quick Review                           Where: Merlin Results page
───────────────────────────────
  → Spot-check studies, review 7 cards:
    NET PROFIT / MAX DRAWDOWN / TOTAL TRADES / WFE /
    OOS WINS / OOS PROFIT (med) / OOS WIN RATE (med)
  → Equity curve: stable growth or chaos?
  → Flag obviously broken studies for deletion
  → ~2 minutes


STAGE 4: Layer 2 — Research Analytics                     Where: Merlin Research Analytics
──────────────────────────────────────
  → Click [Research Analytics]
  → Table assembled automatically, auto-labels assigned
  → Review heatmaps (Profit by Symbol×TF)
  → Override labels if needed
  → Try checkboxes:
    - Only 1h → portfolio equity + metrics
    - Only PASS → portfolio equity + metrics
    - Specific portfolio → "what if I traded this?"
  → [Save Labels]
  → [Export Selected to Global DB]
  → ~3-5 minutes


STAGE 5: Layer 3 — Global Analytics                       Where: Merlin Global Analytics
───────────────────────────────────
  → Click [Global Analytics]
  → New rows already in place
  → Review global heatmaps:
    - PASS rate by Symbol×TF — updated?
    - Profit by Strategy×TF — new trends?
  → Write 1-3 insights:
    - "1h beats 30m" → action: "Focus on 1h"
    - "LINK is best" → action: "Priority for live"
  → ~2-3 minutes


Total: 7-10 minutes for a full research review. Everything in one tool.
```

---

## 10. Principles and Anti-Patterns

### 10.1 Principles

| Principle | Description |
|-----------|-------------|
| **One tool** | Everything in Merlin: data, analytics, insights, export |
| **Invariant Layer 3 = Layer 2 + research** | One UI component, built once. Affects runs schema and indexes |
| **No data duplication** | Window metrics in research DB, aggregates pre-computed, global DB stores only study-level |
| **Automate numbers, humans make decisions** | Auto-label, auto-aggregates; human overrides labels and writes insights |
| **Compression going up** | N×12 windows → N study rows → selected → insights |
| **One button** | Export to Global DB — one click, zero manual steps |
| **Medians in Python** | Independent of SQLite version and percentile extension availability |
| **Portfolio metrics from equity curve** | Profit% and MaxDD% from aggregated curve from Phase 1, not SUM/AVG |
| **Metric dictionary** | Exact formulas, null-policy and rounding fixed before coding |
| **Evolution, not overdesign** | MVP → iterate |

### 10.2 What NOT to Do

| Anti-pattern | Why | Alternative |
|---|---|---|
| Google Sheets | Context switching, formula limitations | Local DB + Merlin UI |
| analytics.db alongside research DB | `_pick_newest_db()` will pick it up | `src/storage/global/analytics.db` |
| INSERT OR REPLACE | DELETE + INSERT, loses label/note | UPSERT with ON CONFLICT DO UPDATE |
| SQL OFFSET median | Depends on SQLite version | Python statistics.median() |
| SUM/AVG for Portfolio Profit% / MaxDD% | Mathematically incorrect to add percentages | From aggregated equity curve |
| "WIN RATE" for window-level metric | Semantically wrong (in trading = trade win rate) | OOS WINS (numerator/denominator explicit) |
| Worst/Best window in Layer 1 UI | The equity curve shows this visually | Store worst_window_* in DB, don't show |
| UniqueParams in UI | Useless with large param space | Remove entirely |
| Separate Batches/Research sheet | Duplication | `research` column + HYPO in insights |
| run_spec_hash, calc_version | Perfectionism for a personal tool | study_id + source_db for traceability |
| CSV import/export workflow | Manual steps | Button in UI → direct SQLite insert |

---

## 11. System Evolution

### Phase 1 — MVP

**Layer 1 (additions to existing):**
- Add 2 new cards: `OOS PROFIT (med)`, `OOS WIN RATE (med)`
- Rename card: `WIN RATE` → `OOS WINS`, format `N/M (%)`
- Change format: `TOTAL TRADES: 169` → `TOTAL TRADES: 101/169`
- 9 new columns in `studies` table, computed in Python when WFA finishes

**Layer 2 (new feature):**
- Research Analytics page/view
- Summary table with conditional formatting (11 columns)
- Filters: Strategy, Symbol, TF, WFA mode, IS/OOS, Label
- Checkboxes + portfolio metrics for selected (from equity curve)
- Aggregated portfolio equity curve (intersection rule)
- Auto-label (PASS/MAYBE/FAIL)
- Save Labels → `analytics_label`/`analytics_note` in studies
- Export to Global DB (UPSERT into analytics.db)
- Export CSV (backup)
- Heatmaps: Profit by Symbol×TF, WFE by Symbol×TF

**Layer 3 (new feature):**
- `src/storage/global/analytics.db` — schema (runs + insights), WAL + busy_timeout
- Global Analytics page/view (same UI component)
- Research column + filter by research
- Insights journal (add/view/delete)
- Deduplication by study_id UNIQUE + UPSERT

### Phase 2 — Optimization (after 10-15 research runs)

- Adjust auto-label thresholds and conditional formatting based on real data
- Add heatmaps: PASS rate by Symbol×TF, Strategy×TF
- Clickable heatmap cells → filter table
- Column sorting (click on header)
- Inline note editing directly in the table

### Phase 3 — Expansion

- Parameter Sensitivity & Stability Analysis (separate concept)
- Completeness matrix (ticker × TF = ✓/✗)
- Deployments tracking (paper/live)
- Re-optimization schedule
- Export global insights to markdown (archiving)

---

## 12. Open Questions

1. **Auto-label thresholds** — profit > 0, DD < 35, profW > 60%, trades >= 30 for PASS. Adjust after the first research runs.

2. **Research name** — automatically from the .db filename, or manual input at export time? Proposal: auto from .db name, with override option in the export dialog.

3. **Insights UI** — full table vs simple list. For MVP: simple list with an Add button (modal with fields). Table with filters — Phase 2.

4. **Per-study notes in Layer 3** — inline editing in the table (more convenient) vs modal only (simpler to implement). For MVP: via modal.

5. **PP-spec format** — single string "DSR FT15" vs structured (separate columns). For MVP: string. Split if filtering by individual PP components becomes necessary.

6. **Data period** — does Layer 3 need an explicit "data period" column (2024.01-2025.01)? Currently the CSV filename contains this information. Add if needed for strategy degradation analysis.

7. **Parameter analysis** — concept described in discussion notes. Implementation — Phase 3 or a separate project.
