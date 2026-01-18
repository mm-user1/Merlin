# DSR filtered results fix report

Date: 2026-01-18

## Goal
Make DSR calculate mean/var Sharpe using all completed trials while still applying Score/Net Profit filters only to DSR candidates.

## Changes
- Stored a full (unfiltered) list of Optuna results before `calculate_score` filtering for later DSR statistics.
- Passed the full results list into DSR so mean/var Sharpe are based on all completed trials.
- Kept candidate filtering intact (DSR still evaluates only filtered trials for top-K).
- WFA path updated to pass all results when available.

## Files touched
- `+Merlin/+Merlin-GH/src/core/optuna_engine.py`
- `+Merlin/+Merlin-GH/src/core/post_process.py`
- `+Merlin/+Merlin-GH/src/ui/server.py`
- `+Merlin/+Merlin-GH/src/core/walkforward_engine.py`

## Tests
- `C:\Users\mt\Desktop\Strategy\S_Python\.venv\Scripts\python.exe -m pytest tests/test_dsr.py -q`

## Result
DSR now uses Sharpe distribution from all completed trials to compute mean/var and SR0, while DSR candidate selection remains filtered. No behavioral changes outside DSR candidate selection and WFA DSR statistics.
