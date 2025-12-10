# Trailing MA Backtesting Platform

Config-driven backtesting and Optuna optimization platform for cryptocurrency strategies with a light-themed Flask SPA frontend.

## Quick Start

```bash
pip install -r requirements.txt
cd src
python server.py
```
Open http://0.0.0.0:8000 and upload `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv` for reference tests.

## Development Notes

- All strategy parameters use **camelCase** throughout the stack (Pine Script → `config.json` → Python → CSV). Examples: `maType`, `closeCountLong`, `rsiLen`. Avoid snake_case (`ma_type`, `close_count_long`).
- Strategy schemas and UI rendering are driven by each strategy's `config.json`; new strategies require only `config.json` + `strategy.py` (see `docs/ADDING_NEW_STRATEGY.md`).
