## Base rules for project:

Act as an experienced Python and Pinescript developer with trading and crypto algorithmic trading expertise.
IMPORTANT: Work strictly according to the given specifications. Any deviations are prohibited without my explicit consent.
IMPORTANT: The script must be maximally efficient and fast.
IMPORTANT: The GUI must use a light theme.

"./data" folder is used for examples, market data files etc.
"./docs" folder is used for documentation, plans, reference scripts etc.
"./src" is the main project folder

## Project: Merlin

Cryptocurrency trading strategy backtesting and Optuna optimization platform with a Flask SPA frontend.

## Running the Application

### Web Server
```bash
cd src/ui
python server.py
```
Server runs at http://0.0.0.0:5000

### CLI Backtest
```bash
cd src
python run_backtest.py --csv ../data/raw/OKX_LINKUSDT.P,\ 15\ 2025.05.01-2025.11.20.csv
```

### Tests
```bash
pytest tests/ -v
```

### Dependencies
```bash
pip install -r requirements.txt
```
Key: Flask, pandas, numpy, matplotlib, optuna==4.4.0

## Architecture

### Core Principles

1. **Config-driven design** - Parameter schemas in `config.json`, UI renders dynamically
2. **camelCase naming** - End-to-end: Pine Script → config.json → Python → CSV
3. **Optuna-only optimization** - Grid search removed
4. **Strategy isolation** - Each strategy owns its params dataclass

### Directory Structure

```
src/
├── core/               # Engines + utilities
│   ├── backtest_engine.py    # Trade simulation, TradeRecord, StrategyResult
│   ├── optuna_engine.py      # Optimization, OptimizationResult, OptunaConfig
│   ├── walkforward_engine.py # WFA orchestration
│   ├── metrics.py            # BasicMetrics, AdvancedMetrics calculation
│   └── export.py             # CSV export functions
├── indicators/         # Technical indicators
│   ├── ma.py           # 11 MA types via get_ma()
│   ├── volatility.py   # ATR, NATR
│   └── oscillators.py  # RSI, StochRSI
├── strategies/         # Trading strategies
│   ├── base.py         # BaseStrategy class
│   ├── s01_trailing_ma/
│   └── s04_stochrsi/
└── ui/                 # Web interface
    ├── server.py       # Flask API
    ├── templates/      # HTML
    └── static/         # JS, CSS
```

### Data Structure Ownership

| Structure | Module |
|-----------|--------|
| `TradeRecord`, `StrategyResult` | `backtest_engine.py` |
| `BasicMetrics`, `AdvancedMetrics` | `metrics.py` |
| `OptimizationResult`, `OptunaConfig` | `optuna_engine.py` |
| Strategy params dataclass | Each strategy's `strategy.py` |

## Parameter Naming Rules

**CRITICAL: Use camelCase everywhere**

- ✅ `maType`, `closeCountLong`, `rsiLen`, `stopLongMaxPct`
- ❌ `ma_type`, `close_count_long`, `rsi_len`, `stop_long_max_pct`

Internal control fields (`use_backtester`, `start`, `end`) may use snake_case but are excluded from UI/config.

**Do NOT add:**
- `to_dict()` methods - use `dataclasses.asdict(params)` instead
- Snake↔camel conversion helpers
- Feature flags

## Adding New Strategies

See `docs/ADDING_NEW_STRATEGY.md` for complete guide.

Quick checklist:
1. Create `src/strategies/<strategy_id>/` directory
2. Create `config.json` with parameter schema (camelCase)
3. Create `strategy.py` with params dataclass and strategy class
4. Ensure `STRATEGY_ID`, `STRATEGY_NAME`, `STRATEGY_VERSION` class attributes
5. Implement `run(df, params, trade_start_idx) -> StrategyResult` static method
6. Strategy auto-discovered - no manual registration needed

## Common Tasks

### Running Single Backtest
```python
from core.backtest_engine import load_data, prepare_dataset_with_warmup
from strategies.s01_trailing_ma.strategy import S01TrailingMA

df = load_data("data/raw/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv")
df_prepared, trade_start_idx = prepare_dataset_with_warmup(df, start, end, warmup_bars=1000)
result = S01TrailingMA.run(df_prepared, params, trade_start_idx)
```

### Calculating Metrics
```python
from core import metrics
basic = metrics.calculate_basic(result, initial_capital=100.0)
advanced = metrics.calculate_advanced(result)
```

### Using Indicators
```python
from indicators.ma import get_ma
from indicators.volatility import atr
from indicators.oscillators import rsi, stoch_rsi

ma_values = get_ma(df["Close"], "HMA", 50)
atr_values = atr(df["High"], df["Low"], df["Close"], 14)
rsi_values = rsi(df["Close"], 14)
```

## Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Key Test Files
- `test_sanity.py` - Infrastructure checks
- `test_regression_s01.py` - S01 baseline regression
- `test_naming_consistency.py` - camelCase guardrails

### Regenerate S01 Baseline
```bash
python tools/generate_baseline_s01.py
```

## UI Notes

- Light theme (project requirement)
- Forms generated dynamically from `config.json`
- Strategy dropdown auto-populated from discovered strategies
- No hardcoded parameters in frontend

## Performance Considerations

- Use vectorized pandas/numpy operations
- Reuse indicator calculations where possible
- Avoid expensive logging in hot paths (optimization loops)
- `trade_start_idx` skips warmup bars in simulation

## Current Strategies

| ID | Name | Description |
|----|------|-------------|
| `s01_trailing_ma` | S01 Trailing MA | Complex trailing MA with 11 MA types, close counts, ATR stops |
| `s04_stochrsi` | S04 StochRSI | StochRSI swing strategy with swing-based stops |

## Key Files for Reference

| Purpose | File |
|---------|------|
| Full architecture | `docs/PROJECT_OVERVIEW.md` |
| Adding strategies | `docs/ADDING_NEW_STRATEGY.md` |
| S04 example | `src/strategies/s04_stochrsi/strategy.py` |
| config.json example | `src/strategies/s04_stochrsi/config.json` |
| Test baseline | `data/baseline/` |
