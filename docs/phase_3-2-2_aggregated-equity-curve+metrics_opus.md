# Phase 3-2-2: Aggregated Equity Curve + Portfolio Metrics

> Implementation plan for Portfolio Equity Aggregation in Merlin Analytics page.
> Covers: aggregated equity chart, portfolio metric cards upgrade, Ann.P% card addition,
> study sets curve-based metrics, and supporting backend module.

---

## Table of Contents

- [1. Scope](#1-scope)
- [2. Architecture Decisions](#2-architecture-decisions)
- [3. Backend: core/analytics.py](#3-backend-coreanalyticspy)
- [4. Backend: POST /api/analytics/equity](#4-backend-post-apianalyticsequity)
- [5. Frontend: Aggregated Equity Chart](#5-frontend-aggregated-equity-chart)
- [6. Frontend: Metric Cards Upgrade](#6-frontend-metric-cards-upgrade)
- [7. Frontend: Card Size Reduction](#7-frontend-card-size-reduction)
- [8. Frontend: Study Sets Metrics Upgrade](#8-frontend-study-sets-metrics-upgrade)
- [9. Frontend: Client-Side Aggregation Utility](#9-frontend-client-side-aggregation-utility)
- [10. Edge Cases and Warnings](#10-edge-cases-and-warnings)
- [11. Files Changed](#11-files-changed)
- [12. Testing Plan](#12-testing-plan)

---

## 1. Scope

### What This Update Implements

1. **Aggregated equity chart** — when 2+ studies are checked, show an aggregated portfolio equity curve instead of a single study's curve
2. **Portfolio metric cards upgrade** — Portfolio Profit and MaxDD computed from the aggregated equity curve (not SUM/MAX of individual values)
3. **Ann.P% card** — new metric card added to both portfolio mode and focus mode (8 cards total)
4. **Study Sets curve-based metrics** — Ann.P%, Profit%, MaxDD% in the sets table computed from client-side equity aggregation (consistent with portfolio cards)
5. **Backend analytics module** — new `core/analytics.py` with reusable aggregation functions

### What This Update Does NOT Implement

- Conditional formatting (separate update)
- AVG footer row (separate update)
- Auto-labels, notes column, label persistence
- Heatmaps
- Compare set equity curves overlay
- Export CSV / Export to Global DB
- Results page Ann.P% card (separate update)

### Database Changes

**None.** All required data (stitched_oos_equity_curve, stitched_oos_timestamps_json) already exists in the studies table and is already served by the summary endpoint.

---

## 2. Architecture Decisions

### 2.1 Separate Python Module

**Decision:** Create `src/core/analytics.py` (~100-150 lines) for aggregation logic.

**Rationale:**
- Functions are purely computational (no DB, no Flask dependencies)
- `metrics.py` (530 lines) handles per-trade/per-strategy metrics — different abstraction level
- `storage.py` (2,883 lines) is already large
- Future features reuse the same module: Compare Set Equity (Section 11), Auto-labels (Section 4), Export to Global DB (Section 13)
- Independently testable via `test_analytics.py`

### 2.2 Ann.P% Consistency

**Decision:** Use the same CAGR formula everywhere. The formula is identical for individual studies and for the aggregated portfolio — only the inputs differ.

```
Ann.P% = ((1 + profit_pct / 100) ^ (365 / span_days) - 1) × 100
```

- Individual study: `profit_pct` = study's stitched OOS profit, `span_days` = study's OOS time span
- Aggregated portfolio: `profit_pct` = portfolio profit from curve, `span_days` = intersection overlap days

When comparing AVG-of-individual-Ann.P% vs Ann.P%-from-aggregated-curve, the values differ because:
- AVG uses each study's full OOS period (different spans, different normalizations)
- Curve-based uses only the common intersection period with equal-weight normalization

The curve-based Ann.P% answers "what would this portfolio earn per year?" — the correct metric for portfolio analysis.

### 2.3 Study Sets Metrics

**Decision:** Upgrade sets table metrics (Ann.P%, Profit%, MaxDD%) to curve-based, computed client-side.

**Rationale:**
- Equity curves are already in frontend memory (loaded via `/api/analytics/summary`)
- Client-side aggregation for 30 sets with 15 studies each ≈ 150,000 operations → <10ms in JS
- Consistency: sets are mini-portfolios, their metrics should match the main portfolio cards
- No API calls needed — zero network overhead

**Fallback:** If a set has no overlapping study time ranges, show "N/A" for curve-based metrics (Ann.P%, Profit%, MaxDD%). Other metrics (Profitable, WFE%, OOS Wins) remain AVG-based and always available.

### 2.4 Computation Location Split

| Context | Where | Method |
|---------|-------|--------|
| Main equity chart (2+ checked) | Backend endpoint | `POST /api/analytics/equity` |
| Metric cards (2+ checked) | Backend endpoint | Uses response from same endpoint |
| Metric cards (1 checked / focus) | Frontend | Study's own data (no aggregation) |
| Study Sets table (per-set metrics) | Frontend (JS) | Client-side aggregation from curves in memory |
| "All Studies" row in sets table | Frontend (JS) | Client-side aggregation from all curves |

---

## 3. Backend: core/analytics.py

### 3.1 Module Purpose

Pure computational functions for portfolio equity aggregation. No database or Flask dependencies.

### 3.2 Public API

```python
def aggregate_equity_curves(
    studies_data: List[Dict],
) -> Optional[Dict[str, Any]]:
    """
    Aggregate multiple equity curves into a single portfolio curve.

    Args:
        studies_data: list of dicts, each with keys:
            - "equity_curve": List[float] (starting at 100.0)
            - "timestamps": List[str] (ISO date strings, same length as equity_curve)

    Returns:
        None if no valid data or no overlap.
        Dict with keys:
            - "curve": List[float] — aggregated portfolio equity (starts at 100.0)
            - "timestamps": List[str] — daily ISO date strings
            - "profit_pct": float — portfolio profit from curve
            - "max_drawdown_pct": float — peak-to-trough on aggregated curve
            - "ann_profit_pct": float | None — CAGR annualized profit (None if overlap <= 30 days)
            - "overlap_days": int — length of common time range
            - "studies_used": int — how many studies were included
            - "studies_excluded": int — how many were excluded (missing data)
            - "warning": str | None — warning message if applicable
    """
```

### 3.3 Internal Functions

```python
def _generate_daily_grid(t_start: date, t_end: date) -> List[date]:
    """Generate list of dates from t_start to t_end inclusive, daily intervals."""

def _forward_fill(
    source_dates: List[date],
    source_values: List[float],
    target_dates: List[date],
) -> List[float]:
    """
    Align source values to target date grid using forward-fill (LOCF).
    For target dates before the first source date, use the first source value.
    """

def _compute_max_drawdown(equity_curve: List[float]) -> float:
    """Peak-to-trough drawdown on equity array. Returns positive number."""

def _annualize_profit(profit_pct: float, span_days: int) -> Optional[float]:
    """
    CAGR annualization: ((1 + profit/100)^(365/days) - 1) * 100.
    Returns None if span_days <= 30 or return_multiple <= 0.
    """
```

### 3.4 Algorithm Detail

```python
def aggregate_equity_curves(studies_data):
    # 1. Validate and filter: keep only studies with valid equity_curve + timestamps
    valid = []
    excluded = 0
    for study in studies_data:
        curve = study.get("equity_curve", [])
        ts = study.get("timestamps", [])
        if len(curve) >= 2 and len(curve) == len(ts):
            # Parse timestamps to date objects
            dates = [parse_date(t) for t in ts]
            if all(d is not None for d in dates):
                valid.append({"dates": dates, "values": curve})
            else:
                excluded += 1
        else:
            excluded += 1

    if len(valid) == 0:
        return None

    if len(valid) == 1:
        # Single study — return its own curve, no aggregation
        study = valid[0]
        profit = (study["values"][-1] / study["values"][0] - 1) * 100
        span = (study["dates"][-1] - study["dates"][0]).days
        return {
            "curve": study["values"],
            "timestamps": [d.isoformat() for d in study["dates"]],
            "profit_pct": round(profit, 4),
            "max_drawdown_pct": round(_compute_max_drawdown(study["values"]), 4),
            "ann_profit_pct": _annualize_profit(profit, span),
            "overlap_days": span,
            "studies_used": 1,
            "studies_excluded": excluded,
            "warning": None,
        }

    # 2. Find intersection (common time range)
    t_start = max(study["dates"][0] for study in valid)
    t_end = min(study["dates"][-1] for study in valid)

    if t_start >= t_end:
        return {
            "curve": None,
            "timestamps": None,
            "profit_pct": None,
            "max_drawdown_pct": None,
            "ann_profit_pct": None,
            "overlap_days": 0,
            "studies_used": len(valid),
            "studies_excluded": excluded,
            "warning": "Selected studies have no overlapping time period.",
        }

    overlap_days = (t_end - t_start).days

    # 3. Build common daily grid
    common_dates = _generate_daily_grid(t_start, t_end)

    # 4. Align each study using forward-fill, normalize to 100.0 at t_start
    aligned = []
    for study in valid:
        filled = _forward_fill(study["dates"], study["values"], common_dates)
        start_val = filled[0]
        if start_val <= 0:
            excluded += 1
            continue
        normalized = [v / start_val * 100.0 for v in filled]
        aligned.append(normalized)

    if len(aligned) == 0:
        return None

    # 5. Equal-weight average
    n = len(aligned)
    portfolio = []
    for i in range(len(common_dates)):
        avg = sum(curve[i] for curve in aligned) / n
        portfolio.append(round(avg, 6))

    # 6. Compute portfolio metrics
    profit_pct = (portfolio[-1] / 100.0 - 1.0) * 100.0
    max_dd = _compute_max_drawdown(portfolio)
    ann_profit = _annualize_profit(profit_pct, overlap_days)

    warning = None
    if overlap_days < 30:
        warning = f"Short overlapping period ({overlap_days} days) — metrics may be unreliable."

    return {
        "curve": portfolio,
        "timestamps": [d.isoformat() for d in common_dates],
        "profit_pct": round(profit_pct, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "ann_profit_pct": round(ann_profit, 2) if ann_profit is not None else None,
        "overlap_days": overlap_days,
        "studies_used": len(aligned),
        "studies_excluded": excluded,
        "warning": warning,
    }
```

### 3.5 Forward-Fill Detail

```python
def _forward_fill(source_dates, source_values, target_dates):
    """
    For each target date, find the latest source date <= target date
    and use its value. If target date is before all source dates,
    use the first source value.
    """
    result = []
    src_idx = 0
    src_len = len(source_dates)

    for target in target_dates:
        # Advance src_idx to the latest source date <= target
        while src_idx < src_len - 1 and source_dates[src_idx + 1] <= target:
            src_idx += 1
        result.append(source_values[src_idx])

    return result
```

### 3.6 Max Drawdown

```python
def _compute_max_drawdown(equity_curve):
    """Peak-to-trough drawdown. Returns positive number (e.g. 22.5 for -22.5%)."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        if peak > 0:
            dd = (peak - val) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
    return max_dd
```

### 3.7 Annualize Profit (CAGR)

```python
def _annualize_profit(profit_pct, span_days):
    """
    CAGR: ((1 + profit/100)^(365/days) - 1) * 100.
    Returns None if span_days <= 30 or return_multiple <= 0.
    Matches the formula used in analytics-table.js and analytics-sets.js.
    """
    if span_days is None or span_days <= 30:
        return None
    return_multiple = 1.0 + (profit_pct / 100.0)
    if return_multiple <= 0:
        return None
    ann = (return_multiple ** (365.0 / span_days) - 1.0) * 100.0
    if not math.isfinite(ann):
        return None
    return ann
```

---

## 4. Backend: POST /api/analytics/equity

### 4.1 Endpoint Contract

**Route:** `POST /api/analytics/equity`

**File:** `src/ui/server_routes_analytics.py`

**Request:**
```json
{
  "study_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

**Response (success):**
```json
{
  "curve": [100.0, 101.2, 99.8, 103.5, "..."],
  "timestamps": ["2025-05-01", "2025-05-02", "..."],
  "profit_pct": 48.6,
  "max_drawdown_pct": 19.8,
  "ann_profit_pct": 72.3,
  "overlap_days": 280,
  "studies_used": 3,
  "studies_excluded": 0,
  "warning": null
}
```

**Response (no overlap):**
```json
{
  "curve": null,
  "timestamps": null,
  "profit_pct": null,
  "max_drawdown_pct": null,
  "ann_profit_pct": null,
  "overlap_days": 0,
  "studies_used": 3,
  "studies_excluded": 0,
  "warning": "Selected studies have no overlapping time period."
}
```

**Errors:**
- `400` if `study_ids` is missing or not an array
- `400` if `study_ids` is empty

### 4.2 Implementation Outline

```python
@app.post("/api/analytics/equity")
def analytics_equity():
    payload = request.get_json(silent=True) or {}
    study_ids = _parse_study_ids_payload(payload.get("study_ids"))
    if not study_ids:
        return _json_error("study_ids is required and must be a non-empty array.", 400)

    # Load equity curves from DB
    with get_db_connection() as conn:
        placeholders = ",".join("?" for _ in study_ids)
        rows = conn.execute(
            f"""SELECT study_id, stitched_oos_equity_curve, stitched_oos_timestamps_json
                FROM studies WHERE study_id IN ({placeholders})""",
            study_ids,
        ).fetchall()

    # Build input for aggregate function
    studies_data = []
    for row in rows:
        curve = _parse_json_array(row["stitched_oos_equity_curve"])
        timestamps = _parse_json_array(row["stitched_oos_timestamps_json"])
        studies_data.append({"equity_curve": curve, "timestamps": timestamps})

    from core.analytics import aggregate_equity_curves
    result = aggregate_equity_curves(studies_data)

    if result is None:
        return jsonify({
            "curve": None, "timestamps": None,
            "profit_pct": None, "max_drawdown_pct": None, "ann_profit_pct": None,
            "overlap_days": 0, "studies_used": 0, "studies_excluded": len(study_ids),
            "warning": "No valid equity data found for selected studies.",
        })

    return jsonify(result)
```

---

## 5. Frontend: Aggregated Equity Chart

### 5.1 Chart Behavior Rules

| Checked Studies | Focus Mode | Chart Shows |
|----------------|------------|-------------|
| 0 | No | Empty placeholder: "No data to display" |
| 1 | No | That study's stitched OOS curve (current behavior) |
| 2+ | No | **Aggregated portfolio equity curve (NEW)** |
| Any | Yes (Alt+click) | Focused study's individual curve (current behavior) |

Focus mode always takes priority. When focus is cleared with 2+ studies checked, trigger portfolio aggregation.

### 5.2 Chart Title

| Mode | Title |
|------|-------|
| Empty | "Stitched OOS Equity" |
| 1 study | "Stitched OOS Equity - #N SYMBOL TF" (current) |
| 2+ aggregated | "Portfolio Equity (N studies, D days)" where D = overlap_days |
| Focus | "Stitched OOS Equity - #N SYMBOL TF [x]" (current) |

### 5.3 Data Flow

```
User checks/unchecks studies
  → debounce 300ms
  → if count >= 2 and no focus:
      → POST /api/analytics/equity { study_ids: [...] }
      → render aggregated curve via AnalyticsEquity.renderChart()
      → update metric cards from response (profit_pct, max_drawdown_pct, ann_profit_pct)
  → if count == 1:
      → render single study curve (existing behavior, no API call)
  → if count == 0:
      → render empty state
```

### 5.4 Changes in analytics.js

Modify `renderSelectedStudyChart()`:
- Keep existing behavior for 0 and 1 checked studies
- For 2+ checked (and no focus): call `POST /api/analytics/equity` endpoint
- Store the portfolio response in a transient state variable (`portfolioData`)
- Use `portfolioData.curve` and `portfolioData.timestamps` for rendering

Modify `updateVisualsForSelection()`:
- When portfolio data is available (2+ checked, no focus), pass portfolio metrics to `renderSummaryCards()`

Add debounce mechanism:
- 300ms debounce on checkbox changes before calling the equity endpoint
- Cancel pending request if selection changes before response arrives

### 5.5 Changes in analytics-equity.js

No changes to the rendering functions. The chart already accepts any equity curve and timestamp array. Only the calling code in analytics.js changes.

---

## 6. Frontend: Metric Cards Upgrade

### 6.1 Card Layout — Portfolio Mode (2+ studies checked, no focus)

**Current (7 cards):**
```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  +162.5%     │ │  -22.3%      │ │    358       │ │  3/5 (60%)   │
│ PORT.PROFIT  │ │ PORT.MAXDD   │ │ TOTAL TRADES │ │  PROFITABLE  │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   75.0%      │ │   27.5%      │ │  +10.4%      │
│ AVG OOS WINS │ │   AVG WFE    │ │AVG OOS P(med)│
└──────────────┘ └──────────────┘ └──────────────┘
```

**New (8 cards):**
```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  +38.2%     │ │  +59.6%     │ │  -14.8%     │ │    358      │
│ PORT.PROFIT │ │ PORT.ANN.P% │ │ PORT.MAXDD  │ │ TOTAL TRADES│
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  3/5 (60%)  │ │   75.0%     │ │   27.5%     │ │  +10.4%     │
│ PROFITABLE  │ │AVG OOS WINS │ │  AVG WFE    │ │AVG OOS P(md)│
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

Changes:
- Card 1 (`PORT. PROFIT`): from `SUM(profit_pct_i)` → from aggregated curve `profit_pct`
- Card 2 (`PORT. ANN.P%`): **NEW** — from aggregated curve `ann_profit_pct`
- Card 3 (`PORT. MAXDD`): from `MAX(max_dd_i)` → from aggregated curve `max_drawdown_pct`
- Cards 4-8: unchanged (SUM trades, Profitable count, AVG OOS Wins, AVG WFE, AVG OOS P(med))

**Source:** Cards 1-3 use values from `POST /api/analytics/equity` response. Cards 4-8 computed client-side from individual study data (unchanged).

### 6.2 Card Layout — Focus Mode (Alt+click on study row)

**Current (7 cards):**
```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  +72.8%      │ │  -22.3%      │ │   87/169     │ │   22.4%      │
│  NET PROFIT  │ │ MAX DRAWDOWN │ │ TOTAL TRADES │ │    WFE       │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│10/12 (83%)   │ │   +12.6%     │ │   65.3%      │
│  OOS WINS    │ │OOS PROFIT(med│ │OOS WIN RT(med│
└──────────────┘ └──────────────┘ └──────────────┘
```

**New (8 cards):**
```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  +72.8%     │ │  +72.8%     │ │  -22.3%     │ │   87/169    │
│ NET PROFIT  │ │   ANN.P%    │ │ MAX DRAWDOWN│ │ TOTAL TRADES│
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   22.4%     │ │10/12 (83%)  │ │   +12.6%    │ │   65.3%     │
│    WFE      │ │  OOS WINS   │ │OOS PROF(med)│ │OOS WR (med) │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

Changes:
- Card 2 (`ANN.P%`): **NEW** — uses `computeAnnualizedProfitMetrics(study)` from analytics-table.js (same CAGR formula already used for the table column)
- All other cards: unchanged
- Ann.P% shows "N/A" if OOS span ≤ 30 days, adds `*` suffix if span 31-89 days (same rules as table column)

### 6.3 Card Layout — Empty State (0 studies checked)

**New (8 cards):**
```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│      -      │ │      -      │ │      -      │ │      -      │
│ PORT.PROFIT │ │ PORT.ANN.P% │ │ PORT.MAXDD  │ │ TOTAL TRADES│
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│      -      │ │      -      │ │      -      │ │      -      │
│ PROFITABLE  │ │AVG OOS WINS │ │  AVG WFE    │ │AVG OOS P(md)│
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

### 6.4 Single Study Checked (1 study, no focus)

When exactly 1 study is checked (no focus), show cards in **portfolio mode** but with that study's own values. No API call needed:
- `PORT. PROFIT` = study.profit_pct
- `PORT. ANN.P%` = computeAnnualizedProfitMetrics(study).annProfitPct
- `PORT. MAXDD` = study.max_dd_pct
- Remaining cards computed from that single study's data

This is consistent because a single-study "portfolio" = that study itself.

---

## 7. Frontend: Card Size Reduction

### 7.1 CSS Changes

Reduce card dimensions by ~15% to accommodate the 8th card.

**Current values (style.css):**
```css
.summary-card {
    padding: 8px 12px;
}
.summary-card .value {
    font-size: 22px;
}
.summary-card .label {
    font-size: 12px;
}
```

**New values:**
```css
.summary-card {
    padding: 6px 8px;
}
.summary-card .value {
    font-size: 19px;
}
.summary-card .label {
    font-size: 11px;
}
```

The summary row uses `display: flex; flex-wrap: wrap; gap: 8px;` — already flexible. With smaller cards, 8 cards fit on a standard 1200px+ display in a single row, wrapping to 2 rows on narrower screens.

---

## 8. Frontend: Study Sets Metrics Upgrade

### 8.1 Current Sets Table Metrics

```
┌──────────────────────────────────────────────────────────────────┐
│ ☑ │ Set Name           │ Ann.P% │ Profit% │ MaxDD% │ Prof │ WFE │ OOS W │
│───┼────────────────────┼────────┼─────────┼────────┼──────┼─────┼───────│
│   │ All Studies         │ +64.4% │ +162.5% │ -22.3% │ 3/5  │27.5%│ 75.0% │
│ ☑ │ Best Picks (3)      │ +70.3% │ +162.5% │ -22.3% │ 3/3  │27.3%│ 80.6% │
│ ☐ │ High Vol Tickers (4)│ +48.1% │ +191.0% │ -32.1% │ 3/4  │22.1%│ 68.8% │
└──────────────────────────────────────────────────────────────────┘

Current formulas:
  Ann.P%   = AVG of individual CAGR values
  Profit%  = SUM of individual profit_pct values
  MaxDD%   = worst (MAX abs) of individual max_dd_pct values
  Prof     = count(profit>0) / total
  WFE%     = AVG of individual wfe_pct values
  OOS Wins = AVG of individual profitable_windows_pct values
```

### 8.2 Upgraded Sets Table Metrics

```
┌──────────────────────────────────────────────────────────────────┐
│ ☑ │ Set Name           │ Ann.P% │ Profit% │ MaxDD% │ Prof │ WFE │ OOS W │
│───┼────────────────────┼────────┼─────────┼────────┼──────┼─────┼───────│
│   │ All Studies         │ +59.6% │  +38.2% │ -14.8% │ 3/5  │27.5%│ 75.0% │
│ ☑ │ Best Picks (3)      │ +72.1% │  +41.5% │ -12.3% │ 3/3  │27.3%│ 80.6% │
│ ☐ │ High Vol Tickers (4)│  N/A   │   N/A   │  N/A   │ 3/4  │22.1%│ 68.8% │
└──────────────────────────────────────────────────────────────────┘

Upgraded formulas:
  Ann.P%   = CAGR from aggregated curve          ← CHANGED (was AVG)
  Profit%  = profit_pct from aggregated curve     ← CHANGED (was SUM)
  MaxDD%   = max_drawdown_pct from aggregated     ← CHANGED (was worst)
  Prof     = count(profit>0) / total              ← unchanged
  WFE%     = AVG of individual wfe_pct values     ← unchanged
  OOS Wins = AVG of individual profitable_windows ← unchanged
```

Note: "High Vol Tickers" shows N/A because its studies have no overlapping time period.

### 8.3 How It Works

The `computeMetrics()` function in `analytics-sets.js` currently computes SUM/AVG/MAX. It will be upgraded to call the client-side aggregation utility (Section 9) for Ann.P%, Profit%, MaxDD%, while keeping Profitable, WFE%, and OOS Wins as-is.

---

## 9. Frontend: Client-Side Aggregation Utility

### 9.1 Purpose

A lightweight JS function that mirrors `core/analytics.py` logic for computing curve-based metrics from studies already in memory. Used by Study Sets only (the main chart uses the backend endpoint for its higher-quality daily-grid curve).

### 9.2 Location

Add to `analytics-sets.js` as an internal function (not exported). Only the sets module needs client-side aggregation.

### 9.3 Implementation Outline

```js
function computeCurveBasedMetrics(studies) {
  // 1. Filter studies with valid equity_curve + timestamps
  const valid = studies.filter(s =>
    Array.isArray(s.equity_curve) && s.equity_curve.length >= 2 &&
    Array.isArray(s.equity_timestamps) && s.equity_timestamps.length === s.equity_curve.length
  );

  if (valid.length === 0) return { profitPct: null, maxDdPct: null, annProfitPct: null };

  if (valid.length === 1) {
    const s = valid[0];
    const profit = toFiniteNumber(s.profit_pct);
    const maxDd = toFiniteNumber(s.max_dd_pct);
    const ann = computeAnnualizedProfitPct(s);
    return { profitPct: profit, maxDdPct: maxDd, annProfitPct: ann };
  }

  // 2. Parse timestamps to ms, find intersection
  const parsed = valid.map(s => ({
    dates: s.equity_timestamps.map(t => new Date(t).getTime()),
    values: s.equity_curve.map(Number),
  })).filter(s => s.dates.every(d => Number.isFinite(d)));

  if (parsed.length < 2) return { profitPct: null, maxDdPct: null, annProfitPct: null };

  const tStart = Math.max(...parsed.map(s => s.dates[0]));
  const tEnd = Math.min(...parsed.map(s => s.dates[s.dates.length - 1]));

  if (tStart >= tEnd) return { profitPct: null, maxDdPct: null, annProfitPct: null };

  // 3. Build daily grid
  const MS_PER_DAY = 86400000;
  const gridLen = Math.floor((tEnd - tStart) / MS_PER_DAY) + 1;
  const grid = Array.from({ length: gridLen }, (_, i) => tStart + i * MS_PER_DAY);

  // 4. Forward-fill + normalize each study to 100 at tStart
  const aligned = [];
  for (const study of parsed) {
    const filled = forwardFillMs(study.dates, study.values, grid);
    const startVal = filled[0];
    if (!startVal || startVal <= 0) continue;
    aligned.push(filled.map(v => v / startVal * 100));
  }

  if (aligned.length === 0) return { profitPct: null, maxDdPct: null, annProfitPct: null };

  // 5. Average
  const n = aligned.length;
  const portfolio = grid.map((_, i) =>
    aligned.reduce((sum, curve) => sum + curve[i], 0) / n
  );

  // 6. Compute metrics
  const profitPct = (portfolio[portfolio.length - 1] / 100 - 1) * 100;
  const maxDdPct = computeMaxDrawdown(portfolio);
  const overlapDays = (tEnd - tStart) / MS_PER_DAY;
  const annProfitPct = annualizeProfit(profitPct, overlapDays);

  return { profitPct, maxDdPct, annProfitPct };
}

function forwardFillMs(sourceDates, sourceValues, targetDates) {
  const result = [];
  let srcIdx = 0;
  for (const target of targetDates) {
    while (srcIdx < sourceDates.length - 1 && sourceDates[srcIdx + 1] <= target) {
      srcIdx++;
    }
    result.push(sourceValues[srcIdx]);
  }
  return result;
}

function computeMaxDrawdown(curve) {
  let peak = curve[0];
  let maxDd = 0;
  for (const val of curve) {
    if (val > peak) peak = val;
    if (peak > 0) {
      const dd = (peak - val) / peak * 100;
      if (dd > maxDd) maxDd = dd;
    }
  }
  return maxDd;
}

function annualizeProfit(profitPct, spanDays) {
  if (spanDays <= 30) return null;
  const rm = 1 + profitPct / 100;
  if (rm <= 0) return null;
  const ann = (Math.pow(rm, 365 / spanDays) - 1) * 100;
  return Number.isFinite(ann) ? ann : null;
}
```

### 9.4 Integration into computeMetrics()

```js
function computeMetrics(studies) {
  const list = Array.isArray(studies) ? studies : [];
  if (!list.length) {
    return {
      annProfitPct: null, profitPct: null, maxDdPct: null,
      profitableText: '0/0 (0%)', wfePct: null, oosWinsPct: null,
    };
  }

  // Curve-based metrics (replaces SUM/AVG/MAX)
  const curveMetrics = computeCurveBasedMetrics(list);

  // Non-curve metrics (unchanged)
  const profitableCount = list.reduce((acc, s) => {
    const p = toFiniteNumber(s?.profit_pct);
    return acc + (p !== null && p > 0 ? 1 : 0);
  }, 0);
  const profitablePct = list.length > 0 ? Math.round((profitableCount / list.length) * 100) : 0;
  const profitableText = `${profitableCount}/${list.length} (${profitablePct}%)`;
  const wfePct = average(list.map(s => s?.wfe_pct));
  const oosWinsPct = average(list.map(s => s?.profitable_windows_pct));

  return {
    annProfitPct: curveMetrics.annProfitPct,
    profitPct: curveMetrics.profitPct,
    maxDdPct: curveMetrics.maxDdPct,
    profitableText,
    wfePct,
    oosWinsPct,
  };
}
```

---

## 10. Edge Cases and Warnings

| Scenario | Behavior | Where |
|----------|----------|-------|
| No overlapping time range | Warning banner above chart: "Selected studies have no overlapping time period." Metric cards 1-3 show "N/A" | Chart + cards |
| Short overlap (< 30 days) | Warning icon on chart title. Ann.P% = "N/A" (too short). Profit% and MaxDD% still shown | Chart + cards |
| Study missing equity curve | Excluded from aggregation. Chart subtitle shows "(N of M studies used)" if any excluded | Chart |
| All selected studies missing curves | Same as "no data": empty chart, "N/A" metrics | Chart + cards |
| Single study checked | No aggregation, show study's own curve (no API call). Cards show portfolio labels but single-study values | Chart + cards |
| Focus mode active with 2+ checked | Show focused study's curve (focus overrides portfolio). Cards show focused study's individual metrics | Chart + cards |
| Focus cleared with 2+ checked | Trigger portfolio aggregation (debounced) | Chart + cards |
| Set with no overlapping studies | Ann.P%, Profit%, MaxDD% = "N/A". Other set metrics (Profitable, WFE%, OOS Wins) shown normally | Sets table |
| Set with 1 study | Metrics are that study's own values (no aggregation needed) | Sets table |
| Set with 0 studies | All metrics = "N/A" or "0/0 (0%)" | Sets table |
| API call in-flight when selection changes | Cancel pending request, start new debounced call | Chart |

---

## 11. Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/core/analytics.py` | **NEW** | Portfolio equity aggregation functions |
| `src/ui/server_routes_analytics.py` | Modified | Add `POST /api/analytics/equity` endpoint |
| `src/ui/static/js/analytics.js` | Modified | Portfolio chart logic, debounced API call, updated card rendering (add Ann.P% card, use portfolio data for cards 1-3) |
| `src/ui/static/js/analytics-sets.js` | Modified | `computeMetrics()` upgrade to curve-based for Ann.P%/Profit%/MaxDD%, add client-side aggregation utility |
| `src/ui/static/css/style.css` | Modified | Reduce `.summary-card` padding and font sizes (~15%) |
| `tests/test_analytics.py` | **NEW** | Tests for `core/analytics.py` |

**Files NOT changed:**
- `analytics-equity.js` — chart rendering already generic, no changes needed
- `analytics-table.js` — summary table columns unchanged
- `analytics-filters.js` — filters unchanged
- `storage.py` — no DB schema changes
- `api.js` — the equity POST call will be made directly from analytics.js (consistent with how other analytics API calls are made inline)

---

## 12. Testing Plan

### 12.1 Backend Tests (test_analytics.py)

| Test | What to Verify |
|------|----------------|
| `test_aggregate_two_studies_full_overlap` | Two curves with identical date ranges → correct averaged curve, profit, maxDD |
| `test_aggregate_partial_overlap` | Two curves with 50% overlap → only intersection used, correct normalization |
| `test_aggregate_no_overlap` | Two curves with no time overlap → returns warning, curve=None |
| `test_aggregate_single_study` | One study passed → returns study's own curve, no averaging |
| `test_aggregate_empty_input` | Empty list → returns None |
| `test_aggregate_missing_equity` | Study with empty equity_curve → excluded from aggregation |
| `test_forward_fill_basic` | Source with gaps → correct step-aligned values on daily grid |
| `test_forward_fill_before_first` | Target dates before first source date → uses first value |
| `test_max_drawdown_flat` | Flat curve → DD = 0 |
| `test_max_drawdown_simple` | 100→120→90→110 → DD ≈ 25% |
| `test_annualize_profit_one_year` | profit=60%, span=365 → ann≈60% |
| `test_annualize_profit_half_year` | profit=30%, span=183 → CAGR correctly computed |
| `test_annualize_short_period` | span<=30 → returns None |
| `test_annualize_negative_return` | profit=-100% → returns None (return_multiple=0) |
| `test_normalization_at_intersection` | Studies with different starting values → all normalized to 100 at t_start |

### 12.2 Backend Tests (test_server.py addition)

| Test | What to Verify |
|------|----------------|
| `test_analytics_equity_endpoint_success` | POST with valid study_ids → 200, correct response shape |
| `test_analytics_equity_endpoint_empty` | POST with empty study_ids → 400 |
| `test_analytics_equity_endpoint_no_payload` | POST without JSON → 400 |

### 12.3 Frontend Tests (Manual)

| Test | What to Verify |
|------|----------------|
| Check 0 studies | Empty chart, dash cards |
| Check 1 study | That study's curve, portfolio-labeled cards with study's own values |
| Check 2+ studies | Aggregated curve appears, cards 1-3 show curve-based values |
| Check 2+ then Alt+click one | Focus overrides: single study curve + focus cards |
| Escape from focus with 2+ checked | Returns to aggregated chart |
| Check studies with no time overlap | Warning message, N/A for cards 1-3 |
| Rapidly check/uncheck | Debounce works, no race conditions |
| Sets table Ann.P%/Profit%/MaxDD% | Curve-based values match what cards would show for that set's studies |
| Set with non-overlapping studies | N/A for Ann.P%/Profit%/MaxDD% in sets table |
| 8 cards fit on screen | Cards properly sized, no overflow or squishing |
| Ann.P% short period warning | Shows N/A with tooltip for ≤30 days, `*` for 31-89 days |

---

*Document version: v1 | Created: 2026-02-27 | For: Merlin Phase 3-2-2*
*Scope: Aggregated Equity Curve + Portfolio Metrics only*
