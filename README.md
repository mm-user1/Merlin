# Merlin

Config-driven backtesting and Optuna optimization platform for cryptocurrency trading strategies with SQLite database persistence and web-based studies management.

## Features

- **Database persistence** - All optimization results automatically saved to SQLite database
- **Studies browser** - Web UI for browsing, opening, and managing historical optimization studies
- **Multi-strategy support** - S01 Trailing MA and S04 StochRSI included, easily extensible
- **Optuna optimization** - Bayesian parameter optimization with multiple targets (score, net profit, Sharpe, RoMaD)
- **Walk-forward analysis** - IS/OOS validation with stitched equity curves and WFE metrics
- **Two-page UI** - Start page for configuration, Results page for studies management
- **On-demand trade export** - Generate TradingView-compatible CSV for any saved trial
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
│   ├── core/           # Backtest, Optuna, WFA engines + metrics + database + export
│   ├── indicators/     # MA (11 types), ATR, RSI, StochRSI
│   ├── strategies/     # s01_trailing_ma, s04_stochrsi
│   ├── storage/        # SQLite database (studies.db)
│   └── ui/             # Flask server + two-page frontend (Start/Results)
├── data/               # OHLCV CSVs and regression baselines
├── tests/              # Pytest test suite
├── tools/              # Development utilities
└── docs/               # Documentation
```

## Documentation

- [Project Overview](docs/PROJECT_OVERVIEW.md) - Architecture and module details
- [Adding New Strategy](docs/ADDING_NEW_STRATEGY.md) - PineScript to Python conversion guide

## Usage

### Start Page (Configuration)
1. Upload OHLCV CSV data (or use included `data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`)
2. Select strategy from dropdown
3. Configure parameters via dynamic form
4. Run Optuna optimization or Walk-Forward Analysis
5. Results automatically saved to database

### Results Page (Studies Browser)
1. View all historical optimization studies
2. Select and open any study to view trials/windows
3. Analyze equity curves and performance metrics
4. Download trades CSV for any trial (TradingView format)
5. Delete old studies or update CSV file paths

## CLI Backtest

```bash
cd src
python run_backtest.py --csv ../data/raw/OKX_LINKUSDT.P,\ 15\ 2025.05.01-2025.11.20.csv
```

## Tests

```bash
pytest tests/ -v
```
