# Walk-Forward Entry Divergence Fix Report

## What was happening
- In exported WFA trades for `T3 300_34869924`, the first Forward trade occurred at **2025-06-15 10:00**, while TradingView took it at **2025-06-15 00:00** (20 bars earlier on 30m data). All subsequent trades matched, so the drift was limited to the boundary of the Forward Reserve.

## Root cause
- The WFA splitter computed the Forward Reserve start (`forward_start`) as a bar index derived from the WF zone percentage. This index often landed **mid-day** (e.g., the bar at 10:00), but the CSV summary displays only the date, leading users (and TradingView setups) to assume the boundary is at **00:00** of that day.
- TradingView evaluates conditions from the exact date boundary, so it could trigger on the first bar of that day. Merlin’s replay started forward testing several hours later, leaving earlier eligible setups unseen.
- Time zone and warmup were not the issue: other trades aligned perfectly; only the first forward-bar entry shifted.

## Fix implemented
- File: `src/core/walkforward_engine.py`
- Change: After computing `forward_start`, align it to the **first bar of its calendar day**:
  - Take the timestamp at `forward_start`, normalize to day start, find the first bar at or after that normalized timestamp.
  - Keep the index within the trading period (no backward shift before trading_start_idx).
- This preserves the same number of forward bars but moves the boundary to the day open, matching user expectation and TradingView behavior.

## Why this solves it
- Forward testing now begins at 00:00 of the Forward Reserve start date, so Merlin evaluates the same first forward bar TradingView sees. The previously missed early setup (20 bars gap) is captured, aligning the first trade timing while leaving subsequent windows and trades unchanged.

## Validation steps performed
- Re-ran WFA with the same data/params; first forward trade timestamp moved from **2025-06-15 10:00** to **2025-06-15 00:00**, matching TradingView; later trades remained identical.

## Notes and scope
- Impacted only WFA window splitting for the Forward Reserve boundary; IS/OOS windows and warmup handling are unchanged.
- No time-zone changes; alignment is within the existing UTC index.
