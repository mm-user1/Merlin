# Phase 9-5-1: Foundation Refactoring - camelCase Standardization & Core Data Structures

**Target Agent**: GPT 5.1 Codex
**Project**: S_01 Trailing MA Backtesting Platform
**Task**: Phase 9-5-1 - Standardize Parameter Naming & Refactor Core Data Structures
**Complexity**: High (Multi-phase architectural refactoring)
**Priority**: Critical (Foundation for Phase 9-5-2)

---

## Executive Summary

You are tasked with the **foundation refactoring** of a cryptocurrency/forex trading strategy backtesting platform. The codebase currently has inconsistent parameter naming between two strategies (S01 and S04):

- **S01** uses snake_case parameters with conversion layers (legacy approach)
- **S04** uses camelCase parameters matching Pine Script (target approach)
- **Core modules** contain hardcoded S01-specific logic

This phase (9-5-1) focuses on **standardizing the data layer** by:
1. Converting all parameters to camelCase throughout the system
2. Making core data structures (OptimizationResult) generic
3. Creating a dynamic CSV export system driven by strategy config

**Success Metric**: After Phase 9-5-1, parameters flow unchanged from Pine Script → config.json → Python → CSV, and core data structures are strategy-agnostic.

**Next Phase**: Phase 9-5-2 will handle server/UI layer and complete the refactoring.

---

## Table of Contents

1. [Project Context](#project-context)
2. [Current Architecture Problems](#current-architecture-problems)
3. [Target Architecture](#target-architecture)
4. [Implementation Plan - 3 Phases](#implementation-plan)
   - [Phase 1: Standardize to camelCase](#phase-1-standardize-to-camelcase-throughout)
   - [Phase 2: Generic OptimizationResult](#phase-2-make-optimizationresult-generic)
   - [Phase 3: Dynamic CSV Export](#phase-3-generic-csv-export-system)
5. [Testing Requirements](#testing-requirements)
6. [Code Quality Standards](#code-quality-standards)
7. [File Reference Guide](#file-reference-guide)

---

## Project Context

### What This Project Does

This is a **backtesting and optimization platform** for trading strategies:

- **Strategies**: S01 (Trailing MA), S04 (StochRSI), future strategies
- **Core Engines**:
  - `backtest_engine.py` - Single backtest execution
  - `optuna_engine.py` - Bayesian parameter optimization (Optuna-based)
  - `walkforward_engine.py` - Walk-forward analysis orchestrator
- **Interface**: Flask web server + HTML/JS frontend, optional CLI
- **Data Flow**: OHLCV CSV → Strategy simulation → Metrics → CSV export

### Key Architecture Principles (Must Preserve)

1. **Performance Critical**: Multiprocessing with pre-computed caches for indicators
2. **Data Structure Ownership**: "Structures live where they're populated"
   - `TradeRecord`, `StrategyResult` → `backtest_engine.py`
   - `BasicMetrics`, `AdvancedMetrics` → `metrics.py`
   - `OptimizationResult`, `OptunaConfig` → `optuna_engine.py`
   - `StrategyParams` → `strategies/<strategy_name>/strategy.py` (each strategy owns its own)
3. **No separate `types.py`**: Import data structures from their home modules
4. **Hybrid approach** (new):
   - **Strategies**: Typed dataclasses for type safety (e.g., `S01Params`, `S04Params`)
   - **Core modules**: Generic dicts `Dict[str, Any]` for strategy-agnostic operation

### Pine Script Connection

Strategies are originally written in **Pine Script** (TradingView's scripting language) and then ported to Python. Parameter names in Pine Script use **camelCase** (e.g., `rsiLen`, `stochLen`, `kLen`, `dLen`). The target architecture matches this convention throughout the entire pipeline.

---

## Current Architecture Problems

### Problem 1: Parameter Naming Inconsistency

**Current Flow (Broken)**:
```
Pine Script (camelCase: rsiLen)
    ↓
config.json (camelCase: "rsiLen")
    ↓
S01 Params (snake_case: rsi_len) ← CONVERSION LAYER 1
    ↓
Core modules (hardcoded S01 parameters) ← BREAKS FOR S04
    ↓
CSV export (camelCase: rsiLen) ← CONVERSION LAYER 2
```

**Issues**:
- S01 uses snake_case internally (e.g., `ma_type`, `close_count_long`)
- S04 uses camelCase internally (e.g., `rsiLen`, `stochLen`)
- Frontend/API/CSV all use camelCase
- Each strategy has `from_dict()` and `to_dict()` conversion methods
- Conversions scattered across multiple files

### Problem 2: Hardcoded S01 Legacy Code

**In `optuna_engine.py`**:
```python
PARAMETER_MAP: Dict[str, Tuple[str, bool]] = {
    "maLength": ("ma_length", True),  # ← S01-specific mapping
    "closeCountLong": ("close_count_long", True),
    # ... 16 more hardcoded S01 parameters
}

@dataclass
class OptimizationResult:
    ma_type: str              # ← S01-specific field
    ma_length: int            # ← S01-specific field
    close_count_long: int     # ← S01-specific field
    # ... 18 more S01-specific fields
```

**In `export.py`**:
```python
CSV_COLUMN_SPECS: List[Tuple[str, Optional[str], str, Optional[str]]] = [
    ("MA Type", "maType", "ma_type", None),  # ← S01-specific columns
    ("MA Length", "maLength", "ma_length", None),
    # ... 19 more S01-specific columns
]

if strategy_id == "s01_trailing_ma":
    return CSV_COLUMN_SPECS  # ← Hardcoded fallback
```

### Problem 3: Temporary Fixes Creating S01/S04 Separation

**Dynamic attribute setting** (`optuna_engine.py` lines 290-292):
```python
for param_name, value in params_dict.items():
    setattr(opt_result, param_name, value)  # ← Workaround for S04
```

**Strategy-aware CSV column building** (`export.py` lines 100-154):
```python
def _build_column_specs_for_strategy(strategy_id: str):
    if strategy_id == "s01_trailing_ma":
        return CSV_COLUMN_SPECS  # ← Hardcoded path
    # ... generic path for other strategies
```

---

## Target Architecture

### Target Flow (Clean)

```
Pine Script (camelCase: rsiLen)
    ↓
config.json (camelCase: "rsiLen")
    ↓
Python Params (camelCase: rsiLen) ← NO CONVERSION!
    ↓
Core modules (generic, config-driven) ← WORKS FOR ANY STRATEGY
    ↓
CSV export (camelCase: rsiLen) ← NO CONVERSION!
```

### Hybrid Approach: Typed Strategies + Generic Core

**At Strategy Level (Type Safety)**:
```python
@dataclass
class S04Params:
    rsiLen: int = 16
    stochLen: int = 16
    kLen: int = 3
    dLen: int = 3
    # IDE autocomplete, type checking, validation

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "S04Params":
        """Direct mapping - no conversion"""
        return cls(
            rsiLen=int(d.get("rsiLen", 16)),
            stochLen=int(d.get("stochLen", 16)),
            kLen=int(d.get("kLen", 3)),
            dLen=int(d.get("dLen", 3)),
        )

class S04Strategy:
    def __init__(self, params_dict: Dict[str, Any]):
        # Hybrid: convert dict to typed dataclass for type safety
        self.params = S04Params.from_dict(params_dict)

    def run(self, data):
        # IDE autocomplete works, type hints work
        rsi = calculate_rsi(data, self.params.rsiLen)
```

**At Core Level (Generic)**:
```python
@dataclass
class OptimizationResult:
    params: Dict[str, Any]  # ← Generic dict, no hardcoded fields
    net_profit_pct: float
    max_drawdown_pct: float
    total_trades: int
    romad: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    # ... metrics only (universal across strategies)

def run_optimization(config: Dict[str, Any]) -> OptimizationResult:
    params_dict = {"rsiLen": 16, "stochLen": 16, ...}  # Works for any strategy
    result = OptimizationResult(
        params=params_dict,  # Generic dict
        net_profit_pct=1234.56,
        # ... metrics
    )
    return result
```

### Parameter Type System (Matching Pine Script)

| Pine Script Input | config.json Type | Frontend Widget | Python Type | Formatter |
|-------------------|------------------|-----------------|-------------|-----------|
| `input.int()` | `"int"` | Number input | `int` | `f"{int(x)}"` |
| `input.float()` | `"float"` | Number input (decimals) | `float` | `f"{float(x):.4f}"` |
| `input.string(options=[...])` | `"select"` or `"options"` | Dropdown/select | `str` | `str(x)` |
| `input.bool()` | `"bool"` | Checkbox | `bool` | `str(x)` |

**Example config.json**:
```json
{
  "parameters": {
    "rsiLen": {
      "type": "int",
      "label": "RSI Length",
      "default": 16,
      "min": 1,
      "max": 200
    },
    "obLevel": {
      "type": "float",
      "label": "Overbought Level",
      "default": 75.0,
      "min": 0.0,
      "max": 100.0
    },
    "maType": {
      "type": "select",
      "label": "MA Type",
      "options": ["SMA", "EMA", "HMA"],
      "default": "EMA"
    }
  }
}
```

---

## Implementation Plan

You will complete 3 phases sequentially. Each phase must be fully tested before proceeding to the next.

---

## Phase 1: Standardize to camelCase Throughout

**Goal**: Eliminate parameter name conversions by using camelCase everywhere.

### 1.1 Update S01Params Dataclass

**File**: `src/strategies/s01_trailing_ma/strategy.py`

**Current** (lines 21-52):
```python
@dataclass
class S01Params:
    ma_type: str = "EMA"
    ma_length: int = 45
    close_count_long: int = 7
    close_count_short: int = 5
    stop_long_atr: float = 2.0
    # ... 19 more snake_case parameters
```

**Target**:
```python
@dataclass
class S01Params:
    maType: str = "EMA"
    maLength: int = 45
    closeCountLong: int = 7
    closeCountShort: int = 5
    stopLongX: float = 2.0
    stopLongRR: float = 3.0
    stopLongLP: int = 2
    stopShortX: float = 2.0
    stopShortRR: float = 3.0
    stopShortLP: int = 2
    stopLongMaxPct: float = 3.0
    stopShortMaxPct: float = 3.0
    stopLongMaxDays: int = 2
    stopShortMaxDays: int = 4
    trailRRLong: float = 1.0
    trailRRShort: float = 1.0
    trailLongType: str = "SMA"
    trailLongLength: int = 160
    trailLongOffset: float = -1.0
    trailShortType: str = "SMA"
    trailShortLength: int = 160
    trailShortOffset: float = 1.0
    riskPerTrade: float = 2.0
    contractSize: float = 0.01
    commissionRate: float = 0.0005
    atrPeriod: int = 14
    # Non-strategy parameters (keep snake_case for internal use)
    use_backtester: bool = True
    use_date_filter: bool = True
    start: Optional[pd.Timestamp] = None
    end: Optional[pd.Timestamp] = None
```

**Action Items**:
1. Convert all 24 strategy parameters from snake_case to camelCase
2. Keep internal control parameters (use_backtester, use_date_filter, start, end) in snake_case
3. Update all references throughout the file (lines 166-465)

### 1.2 Simplify S01Params.from_dict()

**File**: `src/strategies/s01_trailing_ma/strategy.py` (lines 54-125)

**Current**:
```python
@classmethod
def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "S01Params":
    """Maps camelCase (frontend) to snake_case (Python)."""
    d = payload or {}
    return cls(
        ma_type=str(d.get("maType", "EMA")),
        ma_length=int(d.get("maLength", 45)),
        # ... conversion logic
    )
```

**Target**:
```python
@classmethod
def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "S01Params":
    """Parse S01 parameters - direct mapping, no conversion."""
    d = payload or {}

    # Date handling
    start = d.get("start")
    end = d.get("end")
    if isinstance(start, str):
        start = pd.Timestamp(start, tz="UTC")
    if isinstance(end, str):
        end = pd.Timestamp(end, tz="UTC")

    return cls(
        # Internal control parameters
        use_backtester=bool(d.get("backtester", True)),
        use_date_filter=bool(d.get("dateFilter", True)),
        start=start,
        end=end,

        # Strategy parameters - direct camelCase mapping
        maType=str(d.get("maType", "EMA")),
        maLength=int(d.get("maLength", 45)),
        closeCountLong=int(d.get("closeCountLong", 7)),
        closeCountShort=int(d.get("closeCountShort", 5)),
        stopLongX=float(d.get("stopLongX", 2.0)),
        stopLongRR=float(d.get("stopLongRR", 3.0)),
        stopLongLP=int(d.get("stopLongLP", 2)),
        stopShortX=float(d.get("stopShortX", 2.0)),
        stopShortRR=float(d.get("stopShortRR", 3.0)),
        stopShortLP=int(d.get("stopShortLP", 2)),
        stopLongMaxPct=float(d.get("stopLongMaxPct", 3.0)),
        stopShortMaxPct=float(d.get("stopShortMaxPct", 3.0)),
        stopLongMaxDays=int(d.get("stopLongMaxDays", 2)),
        stopShortMaxDays=int(d.get("stopShortMaxDays", 4)),
        trailRRLong=float(d.get("trailRRLong", 1.0)),
        trailRRShort=float(d.get("trailRRShort", 1.0)),
        trailLongType=str(d.get("trailLongType", "SMA")),
        trailLongLength=int(d.get("trailLongLength", 160)),
        trailLongOffset=float(d.get("trailLongOffset", -1.0)),
        trailShortType=str(d.get("trailShortType", "SMA")),
        trailShortLength=int(d.get("trailShortLength", 160)),
        trailShortOffset=float(d.get("trailShortOffset", 1.0)),
        riskPerTrade=float(d.get("riskPerTrade", 2.0)),
        contractSize=float(d.get("contractSize", 0.01)),
        commissionRate=float(d.get("commissionRate", 0.0005)),
        atrPeriod=int(d.get("atrPeriod", 14)),
    )
```

**Action Items**:
1. Remove all snake_case conversion logic
2. Use direct camelCase parameter names matching config.json
3. Preserve date handling and type conversions

### 1.3 Delete S01Params.to_dict()

**File**: `src/strategies/s01_trailing_ma/strategy.py` (lines 127-160, approximate)

**Current**:
```python
def to_dict(self) -> Dict[str, Any]:
    """Convert snake_case to camelCase for export."""
    # ... conversion logic
```

**Target**: **DELETE THIS METHOD ENTIRELY**

**Replacement Pattern**:
Anywhere `to_dict()` is used, replace with:
```python
from dataclasses import asdict

params_dict = asdict(params)  # Built-in, no conversion
```

**Note**: The built-in `asdict()` preserves field names as-is (camelCase after refactoring).

### 1.4 Update S01 Strategy Logic

**File**: `src/strategies/s01_trailing_ma/strategy.py` (lines 166-465)

Replace all snake_case parameter references with camelCase:

**Current**:
```python
ma = get_ma(df["close"], p.ma_type, p.ma_length)
if closes_above >= p.close_count_long:
    # ... entry logic
```

**Target**:
```python
ma = get_ma(df["close"], p.maType, p.maLength)
if closes_above >= p.closeCountLong:
    # ... entry logic
```

**Action Items**:
1. Find all references to `p.<snake_case_field>`
2. Replace with `p.<camelCaseField>`
3. Update all 24 parameter references throughout the strategy logic

**Search/Replace Guide**:
- `p.ma_type` → `p.maType`
- `p.ma_length` → `p.maLength`
- `p.close_count_long` → `p.closeCountLong`
- `p.close_count_short` → `p.closeCountShort`
- `p.stop_long_atr` → `p.stopLongX`
- `p.stop_long_rr` → `p.stopLongRR`
- `p.stop_long_lp` → `p.stopLongLP`
- `p.stop_short_atr` → `p.stopShortX`
- `p.stop_short_rr` → `p.stopShortRR`
- `p.stop_short_lp` → `p.stopShortLP`
- `p.stop_long_max_pct` → `p.stopLongMaxPct`
- `p.stop_short_max_pct` → `p.stopShortMaxPct`
- `p.stop_long_max_days` → `p.stopLongMaxDays`
- `p.stop_short_max_days` → `p.stopShortMaxDays`
- `p.trail_rr_long` → `p.trailRRLong`
- `p.trail_rr_short` → `p.trailRRShort`
- `p.trail_ma_long_type` → `p.trailLongType`
- `p.trail_ma_long_length` → `p.trailLongLength`
- `p.trail_ma_long_offset` → `p.trailLongOffset`
- `p.trail_ma_short_type` → `p.trailShortType`
- `p.trail_ma_short_length` → `p.trailShortLength`
- `p.trail_ma_short_offset` → `p.trailShortOffset`
- `p.risk_per_trade_pct` → `p.riskPerTrade`
- `p.contract_size` → `p.contractSize`
- `p.commission_rate` → `p.commissionRate`
- `p.atr_period` → `p.atrPeriod`

### 1.5 Verify S04Params Consistency

**File**: `src/strategies/s04_stochrsi/strategy.py`

**Action Items**:
1. Verify S04Params already uses camelCase (it should)
2. Verify S04Params.from_dict() uses direct mapping (no conversion)
3. Ensure consistency with S01 pattern

**Expected S04Params**:
```python
@dataclass
class S04Params:
    rsiLen: int = 16
    stochLen: int = 16
    kLen: int = 3
    dLen: int = 3
    obLevel: float = 75.0
    osLevel: float = 15.0
    extLookback: int = 23
    confirmBars: int = 14
    riskPerTrade: float = 2.0
    contractSize: float = 0.01
    initialCapital: float = 100.0
    commissionPct: float = 0.05
```

If any snake_case found, convert to camelCase following S01 pattern.

### Phase 1 Verification

**Test Checklist**:
- [ ] S01Params dataclass has all fields in camelCase
- [ ] S01Params.from_dict() uses direct mapping (no conversion code)
- [ ] S01Params.to_dict() method deleted
- [ ] All strategy logic uses camelCase parameter references
- [ ] S04Params verified to use camelCase consistently
- [ ] Run S01 backtest with sample parameters - no errors
- [ ] Run S04 backtest with sample parameters - no errors
- [ ] Parameter names flow unchanged: JSON → Python dataclass

**Test Command**:
```bash
cd src
python run_backtest.py --strategy s01_trailing_ma --csv ../data/sample.csv
python run_backtest.py --strategy s04_stochrsi --csv ../data/sample.csv
```

---

## Phase 2: Make OptimizationResult Generic

**Goal**: Remove hardcoded S01 parameter fields, store params as dict.

### 2.1 Update OptimizationResult Dataclass

**File**: `src/core/optuna_engine.py` (lines 57-92)

**Current**:
```python
@dataclass
class OptimizationResult:
    """Represents a single optimization result row."""
    ma_type: str
    ma_length: int
    close_count_long: int
    close_count_short: int
    stop_long_atr: float
    # ... 16 more S01-specific parameters
    net_profit_pct: float
    max_drawdown_pct: float
    total_trades: int
    romad: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    # ... other metrics
    score: float = 0.0
```

**Target**:
```python
@dataclass
class OptimizationResult:
    """Generic optimization result for any strategy."""
    params: Dict[str, Any]  # ← Generic parameter dict

    # Metrics (universal across all strategies)
    net_profit_pct: float
    max_drawdown_pct: float
    total_trades: int
    romad: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    ulcer_index: Optional[float] = None
    recovery_factor: Optional[float] = None
    consistency_score: Optional[float] = None
    score: float = 0.0
```

**Action Items**:
1. Delete all 21 S01-specific parameter fields
2. Add single `params: Dict[str, Any]` field
3. Keep all metric fields (universal)

### 2.2 Delete Hardcoded Parameter Maps

**File**: `src/core/optuna_engine.py` (lines 117-153)

**Delete Entirely**:
```python
PARAMETER_MAP: Dict[str, Tuple[str, bool]] = {
    "maLength": ("ma_length", True),
    "closeCountLong": ("close_count_long", True),
    # ... 16 more hardcoded mappings
}

INTERNAL_TO_FRONTEND_MAP: Dict[str, str] = {
    internal: frontend for frontend, (internal, _) in PARAMETER_MAP.items()
}
```

**Rationale**: With camelCase throughout (Phase 1), no mapping needed. Parameters flow directly from config.json.

### 2.3 Update _objective Function

**File**: `src/core/optuna_engine.py` (lines 246-294)

**Current**:
```python
def _objective(trial: Trial) -> float:
    # ... suggest parameters

    # Build OptimizationResult with hardcoded fields
    opt_result = OptimizationResult(
        ma_type=params_dict.get("maType", "EMA"),
        ma_length=params_dict.get("maLength", 45),
        # ... 19 more hardcoded parameter assignments
        net_profit_pct=basic.net_profit_pct,
        # ... metrics
    )

    # Workaround for S04
    for param_name, value in params_dict.items():
        if not hasattr(opt_result, param_name):
            setattr(opt_result, param_name, value)  # ← DELETE THIS
```

**Target**:
```python
def _objective(trial: Trial) -> float:
    # ... suggest parameters

    # Build generic OptimizationResult
    opt_result = OptimizationResult(
        params=params_dict.copy(),  # ← Generic dict storage
        net_profit_pct=basic.net_profit_pct,
        max_drawdown_pct=basic.max_drawdown_pct,
        total_trades=basic.total_trades,
        romad=advanced.romad,
        sharpe_ratio=advanced.sharpe_ratio,
        profit_factor=advanced.profit_factor,
        ulcer_index=advanced.ulcer_index,
        recovery_factor=advanced.recovery_factor,
        consistency_score=advanced.consistency_score,
        score=score,
    )
```

**Action Items**:
1. Remove all hardcoded parameter assignments
2. Store params as `params=params_dict.copy()`
3. Remove dynamic `setattr()` workaround (lines 290-292)
4. Keep all metric assignments

### 2.4 Update Strategy Payload Construction

**File**: `src/core/optuna_engine.py` (lines 279-282, approximate)

**Current**:
```python
# Suggest parameters and build payload
params_dict = {
    "maType": trial.suggest_categorical("maType", ma_types_trend),
    "maLength": trial.suggest_int("maLength", min_val, max_val, step=step),
    # ... build dict
}

# Convert to snake_case for legacy S01Params
strategy_params = {
    "ma_type": params_dict["maType"],
    "ma_length": params_dict["maLength"],
    # ... conversion
}
```

**Target**:
```python
# Suggest parameters and build payload
params_dict = {
    "maType": trial.suggest_categorical("maType", ma_types_trend),
    "maLength": trial.suggest_int("maLength", min_val, max_val, step=step),
    # ... build dict in camelCase
}

# Direct pass-through (no conversion after Phase 1)
strategy_params = params_dict.copy()
```

**Action Items**:
1. Remove snake_case conversion logic
2. Pass camelCase params directly to strategy
3. Verify strategy receives camelCase dict

### 2.5 Remove effective_param_map Construction

**File**: `src/core/optuna_engine.py` (lines 442-449, approximate)

**Delete**:
```python
# Build effective parameter map at runtime
effective_param_map = {}
for frontend_name, (internal_name, is_int) in PARAMETER_MAP.items():
    if config.enabled_params.get(frontend_name, False):
        effective_param_map[frontend_name] = (internal_name, is_int)
```

**Replacement**: Read parameter metadata directly from strategy's config.json:

```python
def _build_search_space(config: OptimizationConfig):
    """Build Optuna search space from strategy config."""
    from strategies import get_strategy_config

    strategy_config = get_strategy_config(config.strategy_id)
    parameters = strategy_config.get("parameters", {})

    search_space = {}
    for param_name, param_spec in parameters.items():
        if not config.enabled_params.get(param_name, False):
            continue  # Skip disabled parameters

        param_type = param_spec.get("type", "float")
        opt_config = param_spec.get("optimize", {})

        if param_type == "int":
            min_val = opt_config.get("min", param_spec.get("min", 0))
            max_val = opt_config.get("max", param_spec.get("max", 100))
            step = opt_config.get("step", 1)
            search_space[param_name] = ("int", min_val, max_val, step)
        elif param_type == "float":
            min_val = opt_config.get("min", param_spec.get("min", 0.0))
            max_val = opt_config.get("max", param_spec.get("max", 10.0))
            step = opt_config.get("step", 0.1)
            search_space[param_name] = ("float", min_val, max_val, step)
        elif param_type == "select":
            options = param_spec.get("options", [])
            search_space[param_name] = ("categorical", options)

    return search_space
```

**Action Items**:
1. Delete hardcoded PARAMETER_MAP usage
2. Load parameter metadata from strategy's config.json
3. Build search space dynamically based on parameter types

### Phase 2 Verification

**Test Checklist**:
- [ ] OptimizationResult has `params: Dict[str, Any]` field
- [ ] No S01-specific parameter fields in OptimizationResult
- [ ] PARAMETER_MAP and INTERNAL_TO_FRONTEND_MAP deleted
- [ ] _objective function stores params as dict
- [ ] Dynamic setattr() workaround removed
- [ ] Strategy payload construction uses camelCase directly
- [ ] Run optimization for S01 - verify params dict correct
- [ ] Run optimization for S04 - verify params dict correct
- [ ] Results can be exported to CSV

**Test Command**:
```bash
# Via API endpoint
curl -X POST http://localhost:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{"strategy": "s01_trailing_ma", "nTrials": 10, ...}'
```

---

## Phase 3: Generic CSV Export System

**Goal**: Remove hardcoded CSV_COLUMN_SPECS, build dynamically from config.json.

### 3.1 Delete Hardcoded CSV_COLUMN_SPECS

**File**: `src/core/export.py` (lines 36-69)

**Delete Entirely**:
```python
CSV_COLUMN_SPECS: List[Tuple[str, Optional[str], str, Optional[str]]] = [
    ("MA Type", "maType", "ma_type", None),
    ("MA Length", "maLength", "ma_length", None),
    # ... 19 more S01-specific columns
]
```

**Rationale**: Column specs will be built dynamically from each strategy's config.json.

### 3.2 Add Formatter Helper Function

**File**: `src/core/export.py` (add after line 98)

**Add**:
```python
def _get_formatter(param_type: str) -> Optional[str]:
    """Map parameter type to CSV formatter."""
    if param_type == "int":
        return None  # No special formatting for integers
    elif param_type == "float":
        return "float1"  # 1 decimal place
    elif param_type in ["select", "options"]:
        return None  # String as-is
    elif param_type == "bool":
        return None  # String representation
    else:
        return None  # Fallback: no formatting
```

### 3.3 Enhance _build_column_specs_for_strategy()

**File**: `src/core/export.py` (lines 100-154)

**Current**:
```python
def _build_column_specs_for_strategy(
    strategy_id: str,
) -> List[Tuple[str, Optional[str], str, Optional[str]]]:
    """Build CSV column specifications based on strategy configuration."""

    if strategy_id == "s01_trailing_ma":
        return CSV_COLUMN_SPECS  # ← Hardcoded fallback

    # ... generic logic for other strategies
```

**Target**:
```python
def _build_column_specs_for_strategy(
    strategy_id: str,
) -> List[Tuple[str, Optional[str], str, Optional[str]]]:
    """Build CSV column specifications dynamically from strategy config.

    Returns list of tuples: (display_name, frontend_name, internal_name, formatter)
    For camelCase throughout: frontend_name == internal_name
    """
    from strategies import get_strategy_config

    try:
        config = get_strategy_config(strategy_id)
    except Exception as e:
        logger.warning(f"Could not load config for {strategy_id}: {e}")
        return _get_default_metric_columns()

    parameters = config.get("parameters", {})
    if not isinstance(parameters, dict):
        logger.warning(f"Invalid parameters in config for {strategy_id}")
        return _get_default_metric_columns()

    specs: List[Tuple[str, Optional[str], str, Optional[str]]] = []

    # Build parameter columns dynamically
    for param_name, param_spec in parameters.items():
        if not isinstance(param_spec, dict):
            continue

        # Get parameter metadata
        param_type = param_spec.get("type", "float")
        label = param_spec.get("label", param_name)
        formatter = _get_formatter(param_type)

        # With camelCase throughout: frontend == internal
        specs.append((label, param_name, param_name, formatter))

    # Add universal metric columns
    specs.extend(_get_metric_columns())

    return specs


def _get_metric_columns() -> List[Tuple[str, Optional[str], str, Optional[str]]]:
    """Return universal metric column specifications."""
    return [
        ("Net Profit%", None, "net_profit_pct", "percent"),
        ("Max DD%", None, "max_drawdown_pct", "percent"),
        ("Trades", None, "total_trades", None),
        ("Score", None, "score", "float"),
        ("RoMaD", None, "romad", "optional_float"),
        ("Sharpe", None, "sharpe_ratio", "optional_float"),
        ("PF", None, "profit_factor", "optional_float"),
        ("Ulcer", None, "ulcer_index", "optional_float"),
        ("Recover", None, "recovery_factor", "optional_float"),
        ("Consist", None, "consistency_score", "optional_float"),
    ]


def _get_default_metric_columns() -> List[Tuple[str, Optional[str], str, Optional[str]]]:
    """Fallback when strategy config unavailable."""
    return _get_metric_columns()
```

**Action Items**:
1. Remove hardcoded S01 fallback
2. Load strategy config.json dynamically
3. Build column specs from `parameters` section
4. Use parameter type to determine formatter
5. Add metric columns (universal)

### 3.4 Update export_optuna_results()

**File**: `src/core/export.py` (lines 218-240, approximate)

**Current**:
```python
def export_optuna_results(...):
    # ... setup

    # Read from OptimizationResult attributes
    row = {
        col_name: _format_csv_value(getattr(result, internal_name), formatter)
        for col_name, _, internal_name, formatter in column_specs
    }
```

**Target**:
```python
def export_optuna_results(
    results: List[OptimizationResult],
    fixed_params: Dict[str, Any],
    strategy_id: str,
    output_path: Optional[str] = None,
) -> str:
    """Export optimization results to CSV with dynamic column building."""

    column_specs = _build_column_specs_for_strategy(strategy_id)

    # Build CSV header
    header = [col_name for col_name, _, _, _ in column_specs]

    # Build parameter block (fixed params that weren't varied)
    param_block_lines = []
    for param_name, value in fixed_params.items():
        param_block_lines.append(f"{param_name},{_format_fixed_param_value(value)}")

    # Build result rows
    rows = []
    for result in results:
        row = {}

        # Add parameter values from result.params dict
        for col_name, frontend_name, internal_name, formatter in column_specs:
            if frontend_name is None:
                # Metric column - read from result attributes
                value = getattr(result, internal_name, None)
            else:
                # Parameter column - read from result.params dict
                value = result.params.get(internal_name, "")

            row[col_name] = _format_csv_value(value, formatter)

        rows.append(row)

    # Write CSV
    output = StringIO()

    # Write parameter block
    for line in param_block_lines:
        output.write(line + "\n")
    output.write("\n")  # Blank line separator

    # Write results table
    writer = csv.DictWriter(output, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)

    csv_content = output.getvalue()

    # Save to file if path provided
    if output_path:
        Path(output_path).write_text(csv_content, encoding="utf-8")

    return csv_content
```

**Action Items**:
1. Read parameters from `result.params` dict (not attributes)
2. Read metrics from `result.<metric_name>` attributes
3. Use dynamic column specs from config.json
4. Handle both parameter and metric columns correctly

### 3.5 Remove S01-Specific Error Handling

**File**: `src/core/export.py` (line 112, approximate)

**Current**:
```python
if strategy_id == "s01_trailing_ma":
    return CSV_COLUMN_SPECS
```

**Target**: **DELETE** - All strategies use dynamic building.

### Phase 3 Verification

**Test Checklist**:
- [ ] CSV_COLUMN_SPECS hardcoded list deleted
- [ ] _get_formatter() helper added
- [ ] _build_column_specs_for_strategy() builds dynamically from config.json
- [ ] export_optuna_results() reads from result.params dict
- [ ] S01-specific fallback removed
- [ ] Export S01 optimization results - verify CSV columns match config.json
- [ ] Export S04 optimization results - verify CSV columns match config.json
- [ ] CSV column formatting correct (int vs float vs string)
- [ ] Parameter block includes fixed params

**Test Command**:
```bash
# Run optimization and export
curl -X POST http://localhost:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{"strategy": "s01_trailing_ma", "nTrials": 10, ...}' \
  > s01_results.csv

# Verify CSV format
head -20 s01_results.csv
```

---

## Testing Requirements

### Regression Testing

After EACH phase, run regression tests to ensure no behavior changes:

1. **S01 Backtest Regression**:
   - Run S01 backtest with known parameters
   - Compare results to baseline (trade count, net profit, max DD)
   - Verify within acceptable tolerance (< 0.01% difference)

2. **S04 Backtest Regression**:
   - Run S04 backtest with known parameters
   - Verify results match expected baseline

3. **Optimization Regression**:
   - Run small optimization (10 trials)
   - Verify optimization completes without errors
   - Verify CSV export format correct

### Performance Testing

Verify no performance regression:

1. **Benchmark Optimization Speed**:
   - Run 100-trial optimization before refactoring
   - Run 100-trial optimization after refactoring
   - Verify throughput within 5% (caching architecture preserved)

2. **Memory Usage**:
   - Monitor memory during optimization
   - Verify no memory leaks or excessive growth

---

## Code Quality Standards

### Style Guidelines

1. **Type Hints**: Use type hints for all function signatures
2. **Docstrings**: Document all public functions with Google-style docstrings
3. **Naming**: Follow PEP 8 for function/variable names (snake_case), camelCase for parameters matching Pine Script
4. **Line Length**: Max 100 characters (relaxed from PEP 8's 79 for readability)

### Error Handling

1. **Validation**: Validate all inputs at API boundaries
2. **Logging**: Use logging module, not print statements
3. **Exceptions**: Raise specific exceptions with clear messages
4. **Graceful Degradation**: Fallback to sensible defaults when possible

### Comments

1. **WHY not WHAT**: Explain rationale, not obvious operations
2. **TODOs**: Include author and date for any TODO comments
3. **Complex Logic**: Document non-obvious algorithms or edge cases

### Git Commits

1. **Atomic Commits**: One logical change per commit
2. **Commit Messages**:
   - Format: `[Phase 9-5-1.X] Brief description`
   - Example: `[Phase 9-5-1.1] Convert S01Params to camelCase`
3. **Testing**: Ensure tests pass before committing

---

## File Reference Guide

### Strategy Files

**S01 Trailing MA**:
- `src/strategies/s01_trailing_ma/strategy.py` - Strategy implementation (465 lines)
- `src/strategies/s01_trailing_ma/config.json` - Parameter definitions (412 lines)

**S04 StochRSI**:
- `src/strategies/s04_stochrsi/strategy.py` - Strategy implementation
- `src/strategies/s04_stochrsi/config.json` - Parameter definitions (134 lines)

### Core Modules

**Optimization**:
- `src/core/optuna_engine.py` - Bayesian optimization engine (~800 lines)
  - Lines 57-92: OptimizationResult dataclass (REFACTOR)
  - Lines 117-153: PARAMETER_MAP and mappings (DELETE)
  - Lines 246-294: _objective function (REFACTOR)
  - Lines 442-449: effective_param_map construction (DELETE)

**Export**:
- `src/core/export.py` - CSV export utilities (~400 lines)
  - Lines 36-69: CSV_COLUMN_SPECS (DELETE)
  - Lines 100-154: _build_column_specs_for_strategy (REFACTOR)
  - Lines 218-240: export_optuna_results (REFACTOR)

---

## Success Criteria (Phase 9-5-1 Checklist)

After completing all 3 phases of 9-5-1, verify:

- [ ] **Single naming convention** (camelCase) throughout parameter definitions
- [ ] **No conversion code** between naming conventions (snake_case ↔ camelCase)
- [ ] **S01Params uses camelCase** for all strategy parameters
- [ ] **S01Params.to_dict() deleted** - using built-in asdict() instead
- [ ] **OptimizationResult is generic** with `params: Dict[str, Any]`
- [ ] **No S01-specific fields** in OptimizationResult
- [ ] **PARAMETER_MAP deleted** from optuna_engine.py
- [ ] **Dynamic setattr() workaround removed**
- [ ] **CSV_COLUMN_SPECS deleted** from export.py
- [ ] **CSV columns built dynamically** from strategy config.json
- [ ] **All existing tests pass** (regression, unit)
- [ ] **CSV export works correctly** for both S01 and S04
- [ ] **Performance preserved** (no regression in optimization speed)
- [ ] **Parameter flow verified**: Pine → JSON → Python → CSV (same names throughout)

---

## Next Steps

After completing Phase 9-5-1:

1. **Commit all changes** with clear commit messages
2. **Run full test suite** to ensure no regressions
3. **Document any issues** encountered during implementation
4. **Proceed to Phase 9-5-2** which will:
   - Clean up server defaults and dual naming fallbacks
   - Implement generic parameter type system & UI rendering
   - Update tests and documentation

---

## Critical Preservation

**DO NOT MODIFY**:
1. Multiprocessing cache architecture (`_init_worker()` in optuna_engine.py)
2. Performance-critical indicator calculations
3. Metrics calculation logic (unless fixing bugs)
4. Trade simulation core logic in backtest_engine.py

---

## Questions or Issues

If you encounter ambiguity or issues:
1. **Preserve existing behavior** - Refactoring should not change functionality
2. **Ask for clarification** - Don't guess on critical decisions
3. **Document assumptions** - Add comments explaining non-obvious choices
4. **Test incrementally** - Verify each change before moving to next

---

**END OF PHASE 9-5-1 PROMPT**
