# Merlin

Config-driven backtesting and Optuna optimization platform for cryptocurrency trading strategies.

## Features

- **Multi-strategy support** - S01 Trailing MA and S04 StochRSI included, easily extensible
- **Optuna optimization** - Bayesian parameter optimization with multiple targets (score, net profit, Sharpe, RoMaD)
- **Walk-forward analysis** - IS/OOS validation with aggregated metrics
- **Dynamic UI** - Light-themed Flask SPA that auto-generates forms from strategy configs
- **Config-driven architecture** - Add new strategies via `config.json` + `strategy.py` only

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start web server
cd src/ui
python server.py
```

Open http://0.0.0.0:5000 in your browser.

## Project Structure

```
project-root/
├── src/
│   ├── core/           # Backtest, Optuna, WFA engines + metrics + export
│   ├── indicators/     # MA (11 types), ATR, RSI, StochRSI
│   ├── strategies/     # s01_trailing_ma, s04_stochrsi
│   └── ui/             # Flask server + frontend
├── data/               # OHLCV CSVs and regression baselines
├── tests/              # Pytest test suite
├── tools/              # Development utilities
└── docs/               # Documentation
```

## Documentation

- [Project Overview](docs/PROJECT_OVERVIEW.md) - Architecture and module details
- [Adding New Strategy](docs/ADDING_NEW_STRATEGY.md) - PineScript to Python conversion guide

## Usage

1. Upload OHLCV CSV data (or use included `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`)
2. Select strategy from dropdown
3. Configure parameters via dynamic form
4. Run single backtest or Optuna optimization
5. Export results to CSV

## CLI Backtest

```bash
cd src
python run_backtest.py --csv ../data/raw/OKX_LINKUSDT.P,\ 15\ 2025.05.01-2025.11.20.csv
```

## Tests

```bash
pytest tests/ -v
```
