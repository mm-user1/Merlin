# Project Migration Guide: Modular Strategy System

## Overview

This directory contains step-by-step migration prompts to transform the hardcoded S01 trading strategy into a modular, multi-strategy system.

## Migration Stages

The migration is divided into 7 logical stages, each with its own prompt file:

### 📁 Stage 1: Base Infrastructure Setup
**File:** `migration_prompt_1.md`
**Duration:** ~1-2 hours
**Complexity:** Low

Creates the foundational structure:
- Directory structure (`strategies/`, `strategies/s01_trailing_ma/`)
- Base class (`BaseStrategy`)
- Configuration file (`config.json`) for S01 strategy

**Deliverables:**
- `src/strategies/base.py`
- `src/strategies/s01_trailing_ma/config.json`
- Empty `src/strategies/__init__.py`

---

### 🔧 Stage 2: Extract Strategy & Create Registry
**File:** `migration_prompt_2.md`
**Duration:** ~2-3 hours
**Complexity:** Medium

Extracts S01 logic from `backtest_engine.py`:
- Move `run_strategy()` into separate strategy module
- Create auto-discovery registry system
- Implement strategy loading mechanism

**Deliverables:**
- `src/strategies/s01_trailing_ma/strategy.py`
- `src/strategies/__init__.py` (complete registry)
- Strategy auto-discovery working

---

### 🌐 Stage 3: Update Server with Strategy Endpoints
**File:** `migration_prompt_3.md`
**Duration:** ~2 hours
**Complexity:** Medium

Adds new API endpoints and warmup parameter:
- `/api/strategies` - list all strategies
- `/api/strategies/{id}/config` - get strategy config
- `/api/strategies/{id}` - get strategy metadata
- Update `prepare_dataset_with_warmup()` to accept warmup_bars parameter
- Add warmup_bars handling to existing endpoints

**Deliverables:**
- 3 new API endpoints in `server.py`
- Modified `prepare_dataset_with_warmup()` signature
- Backward compatibility wrapper

---

### 🎨 Stage 4: Dynamic UI Forms
**File:** `migration_prompt_4.md`
**Duration:** ~3-4 hours
**Complexity:** High

Creates dynamic form generation system:
- Strategy selector dropdown
- Warmup bars input field
- JavaScript form generator (from config.json)
- Backtest and optimizer form containers

**Deliverables:**
- Strategy selector in UI
- Dynamic form generation JavaScript
- Warmup bars field
- Parameter grouping by category

---

### ✅ Stage 5: API Integration & Basic Testing
**File:** `migration_prompt_5.md`
**Duration:** ~2-3 hours
**Complexity:** High

Integrates basic backtest endpoint:
- Update `/api/backtest` to use strategy system
- Update UI JavaScript to send strategy_id and warmup_bars
- Basic backtest testing
- Reference test validation for single backtest

**Deliverables:**
- `/api/backtest` endpoint integrated
- JavaScript updated
- Reference test passing (230.75% profit, 20.03% DD, 93 trades)

---

### ⚙️ Stage 6: Update Optimization Engines (Grid & Optuna)
**File:** `migration_prompt_6.md`
**Duration:** ~3-4 hours
**Complexity:** Very High

Updates optimization engines to work with modular strategies:
- Remove hardcoded S01 logic from `optimizer_engine.py`
- Replace `_simulate_combination()` with `strategy_class.run()`
- Update `optuna_engine.py` to use new approach
- Disable caching for MVP (can be re-added later)
- Update `/api/optimize` endpoint

**Deliverables:**
- Grid search working with any strategy
- Optuna working with any strategy
- Multi-parameter optimization tested
- Performance impact documented (~3× slower without cache)

---

### 🔄 Stage 7: Update Walk-Forward Analysis Engine
**File:** `migration_prompt_7.md`
**Duration:** ~3-4 hours
**Complexity:** Very High

Updates WFA to work with modular strategies:
- Replace all `run_strategy()` calls with `strategy_class.run()`
- Update `prepare_dataset_with_warmup()` calls to use warmup_bars
- Update `/api/walkforward` endpoint
- Update trade export functionality
- Comprehensive end-to-end testing

**Deliverables:**
- WFA working with any strategy
- Trade export working
- All E2E tests passing (backtest, grid, optuna, WFA)
- Migration complete!

---

## Total Estimated Time

**17-24 hours** of focused development work, spread across 7 stages:
- Stages 1-4: ~8-11 hours (infrastructure and UI)
- Stage 5: ~2-3 hours (basic backtest integration)
- Stage 6: ~3-4 hours (optimization engines)
- Stage 7: ~3-4 hours (WFA engine)
- Testing and debugging: ~1-2 hours buffer

## Prerequisites

- Python 3.8+
- All dependencies from `requirements.txt` installed
- Flask server running successfully
- Current S01 strategy working

## Success Criteria

Migration is complete when:
1. ✅ Reference test produces expected results (±0.5% tolerance)
2. ✅ All three modes work (Backtest, Optimize, WFA)
3. ✅ New strategies can be added with just 2 files
4. ✅ UI dynamically adapts to different strategies
5. ✅ No backward compatibility issues

## Reference Test Parameters

**Test CSV:** `data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`

**Configuration:**
- Strategy: S01 Trailing MA v26
- Date range: 2025-06-15 to 2025-11-15
- Warmup bars: 1000
- MA Type: SMA, Length: 300
- Close Count Long: 9, Short: 5
- (Full parameters in each prompt file)

**Expected Results:**
```
Net Profit:     230.75% (±0.5%)
Max Drawdown:   20.03%  (±0.5%)
Total Trades:   93      (±2)
```

## Post-Migration Structure

```
src/
├── strategies/
│   ├── __init__.py              # Registry with auto-discovery
│   ├── base.py                  # BaseStrategy class
│   │
│   └── s01_trailing_ma/         # S01 Strategy
│       ├── strategy.py          # Trading logic
│       └── config.json          # Parameters + metadata
│
├── backtest_engine.py           # Common functions (get_ma, atr, etc.)
├── optimizer_engine.py          # Grid search (no cache in MVP)
├── optuna_engine.py             # Bayesian optimization
├── walkforward_engine.py        # WFA
├── server.py                    # Flask API (+ strategy endpoints)
└── index.html                   # UI (+ dynamic forms)
```

## Adding New Strategies (Post-Migration)

After migration is complete, adding a new strategy is simple:

1. Create directory: `src/strategies/s02_my_strategy/`
2. Create `config.json` with parameters and metadata
3. Create `strategy.py` with `run()` method
4. Refresh browser - strategy appears automatically!

## Important Notes

- Each stage includes comprehensive tests
- Always commit after completing a stage
- Test backward compatibility throughout
- Reference test must pass at the end
- Keep old code until final verification

## Getting Started

1. Read all 7 prompt files first
2. Understand the overall architecture
3. Start with `migration_prompt_1.md`
4. Complete each stage sequentially
5. Test thoroughly after each stage
6. Commit after each successful stage

## Support

If you encounter issues during migration:
- Review the test section in each prompt
- Check console/server logs for errors
- Verify previous stages completed correctly
- Compare with reference test parameters

---

**Good luck with the migration! 🚀**
