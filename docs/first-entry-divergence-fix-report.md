# Walk-Forward Entry Divergence Fix Report

## What was happening
- Boundary trades could appear later in exported WFA trades than in TradingView, while all subsequent trades matched. Examples:
  - Forward start: `T3 300_34869924` — export showed first trade at **2025-06-15 10:00**, TradingView at **00:00**.
  - OOS Window 2: `WMA 450_2f5a57f6` — export first trade at **2025-04-04 23:00**, TradingView at **00:00**.

## Root cause
- WFA window boundaries (IS start, gap→OOS start, Forward start) were set by bar counts, so they could land **mid-day**. The summary CSV shows only dates, so users and TradingView assume the boundary is at the day’s open (00:00). When the boundary landed mid-day, TradingView could take a valid setup on the first day bar while Merlin started later and missed it.
- Time zones and warmup were not involved; the misalignment was purely intra-day boundary placement.

## Fix implemented
- File: `src/core/walkforward_engine.py`
- Added helper `_align_to_day_start(bar_idx, lower_bound)`:
  - Snaps a boundary index to the first bar of its calendar day using the dataframe index.
  - Never moves before `lower_bound`, preserving window ordering.
- Applied this alignment to **all** WFA boundaries when `dateFilter` is used:
  - IS start
  - Gap→OOS start (gap shrinks if needed but order is preserved)
  - Forward start
- Consolidated alignment logic to avoid repetition and ensure consistent behavior.

## Why it solves the issue
- Each window now starts at 00:00 of its boundary date, matching what the summary communicates and what TradingView evaluates. Early-day setups are no longer skipped, eliminating first-trade divergence while leaving intra-window behavior unchanged.

## Validation
- Forward case: first trade moved from **2025-06-15 10:00** to **2025-06-15 00:00**.
- OOS Window 2 case: first trade moved from **2025-04-04 23:00** to **2025-04-04 00:00**.
- All subsequent trades remained aligned.

## Scope
- Affects only WFA window splitting under `dateFilter`; strategy logic and warmup handling are unchanged.
- Alignment operates in UTC using existing index timestamps; no time-zone conversions were added.
