# Comprehensive Refactoring Prompt: Eliminate S01/S04 Architecture Inconsistencies

**Target Agent**: GPT 5.1 Codex
**Project**: S_01 Trailing MA Backtesting Platform
**Task**: Complete Phase 9-5 Refactoring - Unify S01 and S04 Architecture
**Complexity**: High (Multi-phase architectural refactoring)
**Priority**: Critical (Foundation for future strategy development)

---

## Executive Summary

You are tasked with eliminating the half-migrated state of a cryptocurrency/forex trading strategy backtesting platform. The codebase currently has **two strategies** (S01 and S04) that are treated inconsistently by the core system:

- **S01** uses snake_case parameters with conversion layers (legacy approach)
- **S04** uses camelCase parameters matching Pine Script (target approach)
- **Core modules** contain hardcoded S01-specific logic and workarounds

Your mission is to **standardize the entire codebase to camelCase**, remove all hardcoded strategy assumptions, and create a fully generic architecture where S01 and S04 are treated identically.

**Success Metric**: After completion, adding a new strategy should require only `config.json` + `strategy.py` with no changes to core modules.

---

## Table of Contents

1. [Project Context](#project-context)
2. [Current Architecture Problems](#current-architecture-problems)
3. [Target Architecture](#target-architecture)
4. [Implementation Plan - 6 Phases](#implementation-plan)
   - [Phase 1: Standardize to camelCase](#phase-1-standardize-to-camelcase-throughout)
   - [Phase 2: Generic OptimizationResult](#phase-2-make-optimizationresult-generic)
   - [Phase 3: Dynamic CSV Export](#phase-3-generic-csv-export-system)
   - [Phase 4: Clean Server Defaults](#phase-4-clean-up-server-defaults)
   - [Phase 5: Generic Parameter Type System](#phase-5-generic-parameter-type-system--ui-rendering)
   - [Phase 6: Tests & Documentation](#phase-6-update-tests-and-documentation)
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

**In `server.py`**:
```python
DEFAULT_PRESET = {
    "maType": "EMA",          # ← S01-specific defaults
    "maLength": 45,
    "closeCountLong": 7,
    # ... many more S01-specific parameters
}
```

### Problem 3: Hardcoded MA Type Selection UI

**In `index.html` / frontend**:
- Hardcoded parameter names: `maType`, `trailLongType`, `trailShortType`
- Uses feature flag `requires_ma_selection` specific to S01
- Not generic - won't render dropdowns for other strategies with choice parameters

**Current Approach**:
```javascript
if (config.features.requires_ma_selection) {
    renderMATypeDropdown("maType");
    renderMATypeDropdown("trailLongType");
    renderMATypeDropdown("trailShortType");
}
```

### Problem 4: Temporary Fixes Creating S01/S04 Separation

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

**Effective parameter map construction** (`optuna_engine.py` lines 442-449):
```python
effective_param_map = {}
for frontend_name, (internal_name, is_int) in PARAMETER_MAP.items():
    # ... runtime construction to support S04
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

You will complete 6 phases sequentially. Each phase must be fully tested before proceeding to the next.

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
def _get_formatter(param_type: str) -> str:
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

## Phase 4: Clean Up Server Defaults

**Goal**: Remove S01-specific defaults and dual naming support.

### 4.1 Simplify DEFAULT_PRESET

**File**: `src/server.py` (lines 156-211, approximate)

**Current**:
```python
DEFAULT_PRESET = {
    "name": "Default",
    "maType": "EMA",
    "maLength": 45,
    "closeCountLong": 7,
    "closeCountShort": 5,
    # ... 20+ more S01-specific parameters
    "filterByProfit": False,
    "minProfitThreshold": 0.0,
    # ... optimization settings
}
```

**Target**:
```python
DEFAULT_PRESET = {
    "name": "Default",

    # Universal settings (not strategy-specific)
    "dateFilter": True,
    "start": None,
    "end": None,

    # Optimization settings
    "optimizationMode": "optuna",
    "nTrials": 100,
    "timeout": None,
    "patience": None,
    "workerProcesses": 6,

    # Scoring configuration
    "scoreConfig": {
        "weights": {
            "romad": 0.25,
            "sharpe": 0.20,
            "pf": 0.20,
            "ulcer": 0.15,
            "recovery": 0.10,
            "consistency": 0.10,
        },
        "normalization_method": "percentile",
    },

    # Filtering
    "filterByProfit": False,
    "minProfitThreshold": 0.0,
}
```

**Rationale**: Strategy-specific defaults come from config.json, not server defaults.

**Action Items**:
1. Remove all S01-specific parameter defaults
2. Keep only universal settings (dates, optimization, scoring, filtering)
3. Document that strategy defaults loaded from config.json

### 4.2 Remove Dual Naming Fallbacks

**File**: `src/server.py` (lines 1182-1514, approximate)

**Current**:
```python
# Dual naming support
ma_type = params.get("maType") or params.get("ma_type", "EMA")
ma_length = params.get("maLength") or params.get("ma_length", 45)
close_count_long = params.get("closeCountLong") or params.get("close_count_long", 7)
# ... many more dual fallbacks
```

**Target**:
```python
# camelCase only (no fallbacks)
ma_type = params.get("maType", "EMA")
ma_length = params.get("maLength", 45)
close_count_long = params.get("closeCountLong", 7)
# ... clean camelCase access
```

**Action Items**:
1. Find all `params.get("camelCase") or params.get("snake_case")` patterns
2. Remove snake_case fallback
3. Keep only camelCase access

### 4.3 Remove S01-Specific Parameter Handling

**File**: `src/server.py` (lines 1340-1350, approximate)

**Current**:
```python
# Special handling for MA types
if "maType" in params:
    params["maType"] = MA_TYPE_MAPPINGS.get(params["maType"], params["maType"])
if "trailLongType" in params:
    params["trailLongType"] = MA_TYPE_MAPPINGS.get(params["trailLongType"], params["trailLongType"])
# ... more S01-specific logic
```

**Target**: **DELETE** - All parameters handled generically.

### 4.4 Simplify _sanitize_score_config()

**File**: `src/server.py` (lines 1207-1273, approximate)

**Current**:
```python
def _sanitize_score_config(score_config: Dict[str, Any]) -> Dict[str, Any]:
    # ... dual naming fallbacks
    weights = score_config.get("weights") or score_config.get("score_weights", {})
    # ... more snake_case fallbacks
```

**Target**:
```python
def _sanitize_score_config(score_config: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize score configuration - camelCase only."""
    weights = score_config.get("weights", {})
    enabled_metrics = score_config.get("enabledMetrics", {})
    invert_metrics = score_config.get("invertMetrics", {})
    normalization_method = score_config.get("normalizationMethod", "percentile")
    filter_enabled = score_config.get("filterEnabled", False)
    min_score_threshold = score_config.get("minScoreThreshold", 0.0)

    return {
        "weights": weights,
        "enabled_metrics": enabled_metrics,
        "invert_metrics": invert_metrics,
        "normalization_method": normalization_method,
        "filter_enabled": filter_enabled,
        "min_score_threshold": min_score_threshold,
    }
```

**Action Items**:
1. Remove all snake_case fallbacks
2. Use camelCase parameter names only
3. Provide sensible defaults

### 4.5 Remove strategy_param_types Extraction

**File**: `src/server.py` (lines 1318-1333, approximate)

**Current**:
```python
# Extract parameter types (S01-specific hardcoded)
strategy_param_types = {
    "maLength": "int",
    "closeCountLong": "int",
    # ... hardcoded types
}
```

**Target**: Load from strategy's config.json:

```python
def _get_parameter_types(strategy_id: str) -> Dict[str, str]:
    """Load parameter types from strategy config."""
    from strategies import get_strategy_config

    config = get_strategy_config(strategy_id)
    parameters = config.get("parameters", {})

    param_types = {}
    for param_name, param_spec in parameters.items():
        param_types[param_name] = param_spec.get("type", "float")

    return param_types
```

**Action Items**:
1. Delete hardcoded strategy_param_types
2. Load parameter types from config.json
3. Use in validation and type conversions

### 4.6 Update _build_optimization_config()

**File**: `src/server.py` (function that builds OptimizationConfig)

**Action Items**:
1. Load parameter metadata from strategy's config.json
2. No hardcoded parameter knowledge
3. Build config generically based on strategy ID

### Phase 4 Verification

**Test Checklist**:
- [ ] DEFAULT_PRESET contains only universal settings
- [ ] No S01-specific parameters in DEFAULT_PRESET
- [ ] All dual naming fallbacks removed
- [ ] S01-specific parameter handling deleted
- [ ] _sanitize_score_config() uses camelCase only
- [ ] Parameter types loaded from config.json
- [ ] Start server - verify default preset loads correctly
- [ ] Test backtest endpoint with S01
- [ ] Test backtest endpoint with S04
- [ ] Test optimize endpoint with S01
- [ ] Test optimize endpoint with S04

**Test Command**:
```bash
cd src
python server.py

# In another terminal
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{"strategy": "s01_trailing_ma", "params": {...}}'
```

---

## Phase 5: Generic Parameter Type System & UI Rendering

**Goal**: Make frontend render parameters based on type from config.json, remove hardcoded MA selection.

### 5.1 Remove requires_ma_selection Feature Flag

**File**: `src/strategies/s01_trailing_ma/config.json` (lines 7-10)

**Current**:
```json
{
  "features": {
    "requires_ma_selection": true,
    "ma_groups": ["trend", "trail_long", "trail_short"]
  }
}
```

**Target**: **DELETE** features section entirely.

**Rationale**: Generic parameter type system renders dropdowns automatically for any `type: "select"` parameter.

### 5.2 Verify Parameter Types in S01 Config

**File**: `src/strategies/s01_trailing_ma/config.json`

**Verify**:
- All MA type parameters use `"type": "select"`
- All length parameters use `"type": "int"`
- All float parameters use `"type": "float"`

**Example**:
```json
{
  "parameters": {
    "maType": {
      "type": "select",
      "label": "Trend MA Type",
      "default": "EMA",
      "options": ["EMA", "SMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"]
    },
    "maLength": {
      "type": "int",
      "label": "MA Length",
      "default": 45,
      "min": 0,
      "max": 500
    },
    "trailLongType": {
      "type": "select",
      "label": "Trail MA Long Type",
      "default": "SMA",
      "options": ["EMA", "SMA", "HMA", "WMA", "ALMA", "KAMA", "TMA", "T3", "DEMA", "VWMA", "VWAP"]
    }
  }
}
```

### 5.3 Update Frontend Parameter Rendering

**File**: `index.html` (or `src/ui/static/js/main.js` if separated)

**Current** (hardcoded):
```javascript
if (config.features && config.features.requires_ma_selection) {
    // Hardcoded parameter names
    renderMATypeDropdown("maType", config.parameters.maType);
    renderMATypeDropdown("trailLongType", config.parameters.trailLongType);
    renderMATypeDropdown("trailShortType", config.parameters.trailShortType);
}
```

**Target** (generic):
```javascript
function renderParameters(config) {
    const parametersContainer = document.getElementById("parameters");
    parametersContainer.innerHTML = "";  // Clear

    const parameters = config.parameters || {};

    // Generic rendering based on parameter type
    for (const [paramName, paramConfig] of Object.entries(parameters)) {
        const paramElement = renderParameter(paramName, paramConfig);
        parametersContainer.appendChild(paramElement);
    }
}

function renderParameter(paramName, paramConfig) {
    const container = document.createElement("div");
    container.className = "parameter-row";

    const label = document.createElement("label");
    label.textContent = paramConfig.label || paramName;
    label.htmlFor = `param-${paramName}`;
    container.appendChild(label);

    let input;

    switch (paramConfig.type) {
        case "int":
        case "float":
            input = renderNumberInput(paramName, paramConfig);
            break;
        case "select":
        case "options":  // Support both names
            input = renderDropdown(paramName, paramConfig);
            break;
        case "bool":
            input = renderCheckbox(paramName, paramConfig);
            break;
        default:
            console.warn(`Unknown parameter type: ${paramConfig.type}`);
            input = renderNumberInput(paramName, paramConfig);  // Fallback
    }

    container.appendChild(input);
    return container;
}

function renderNumberInput(paramName, paramConfig) {
    const input = document.createElement("input");
    input.type = "number";
    input.id = `param-${paramName}`;
    input.name = paramName;
    input.value = paramConfig.default || 0;
    input.min = paramConfig.min || 0;
    input.max = paramConfig.max || 1000;
    input.step = paramConfig.step || (paramConfig.type === "int" ? 1 : 0.1);
    return input;
}

function renderDropdown(paramName, paramConfig) {
    const select = document.createElement("select");
    select.id = `param-${paramName}`;
    select.name = paramName;

    const options = paramConfig.options || [];
    options.forEach(optionValue => {
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = optionValue;
        if (optionValue === paramConfig.default) {
            option.selected = true;
        }
        select.appendChild(option);
    });

    return select;
}

function renderCheckbox(paramName, paramConfig) {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = `param-${paramName}`;
    input.name = paramName;
    input.checked = paramConfig.default || false;
    return input;
}
```

**Action Items**:
1. Remove hardcoded parameter names (`maType`, `trailLongType`, `trailShortType`)
2. Remove `requires_ma_selection` feature flag check
3. Loop through config.parameters and render generically
4. Render dropdowns for **any** `type: "select"` parameter
5. Support `type: "int"`, `"float"`, `"select"`, `"bool"`

### 5.4 Update Server Validation

**File**: `src/server.py` (validation logic)

**Add Generic Validation**:
```python
def _validate_strategy_params(strategy_id: str, params: Dict[str, Any]) -> None:
    """Generic parameter validation based on config.json."""
    from strategies import get_strategy_config

    config = get_strategy_config(strategy_id)
    parameters = config.get("parameters", {})

    for param_name, param_config in parameters.items():
        value = params.get(param_name)
        if value is None:
            continue  # Use default

        param_type = param_config.get("type", "float")

        # Type validation
        if param_type == "int":
            if not isinstance(value, int):
                try:
                    params[param_name] = int(value)
                except (ValueError, TypeError):
                    raise ValueError(f"{param_name} must be an integer")

        elif param_type == "float":
            if not isinstance(value, (int, float)):
                try:
                    params[param_name] = float(value)
                except (ValueError, TypeError):
                    raise ValueError(f"{param_name} must be a number")

        elif param_type in ["select", "options"]:
            options = param_config.get("options", [])
            if value not in options:
                raise ValueError(f"{param_name} must be one of {options}, got {value}")

        elif param_type == "bool":
            if not isinstance(value, bool):
                params[param_name] = bool(value)

        # Range validation
        if param_type in ["int", "float"]:
            min_val = param_config.get("min")
            max_val = param_config.get("max")
            if min_val is not None and value < min_val:
                raise ValueError(f"{param_name} must be >= {min_val}")
            if max_val is not None and value > max_val:
                raise ValueError(f"{param_name} must be <= {max_val}")
```

**Action Items**:
1. Remove hardcoded MA type validation
2. Add generic type validation for int/float/select/bool
3. Add generic range validation
4. Load validation rules from config.json

### 5.5 Verify S04 Config Types

**File**: `src/strategies/s04_stochrsi/config.json`

**Verify**:
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
    }
  }
}
```

**Action Items**:
1. Verify all parameter types are correct
2. Ensure consistency with S01 pattern
3. No feature flags needed

### Phase 5 Verification

**Test Checklist**:
- [ ] `requires_ma_selection` feature flag removed from S01 config.json
- [ ] S01 config.json uses `type: "select"` for MA type parameters
- [ ] Frontend renders parameters generically based on type
- [ ] MA type dropdowns render correctly for S01
- [ ] Number inputs render correctly for S04
- [ ] Server validation works generically for both strategies
- [ ] Load S01 in frontend - verify all parameters render correctly
- [ ] Load S04 in frontend - verify all parameters render correctly
- [ ] Submit backtest request - verify parameters validated correctly

**Test Command**:
```bash
# Start server
cd src
python server.py

# Open browser: http://localhost:8000
# Select S01 strategy - verify maType, trailLongType, trailShortType show as dropdowns
# Select S04 strategy - verify rsiLen, stochLen show as number inputs
```

---

## Phase 6: Update Tests and Documentation

**Goal**: Ensure all tests pass and documentation reflects new architecture.

### 6.1 Update Test Fixtures

**Files**: All test files in `tests/`

**Action Items**:
1. Find all test data with parameters
2. Convert snake_case parameter names to camelCase
3. Update expected outputs

**Example**:
```python
# OLD
test_params = {
    "ma_type": "EMA",
    "ma_length": 45,
    "close_count_long": 7,
}

# NEW
test_params = {
    "maType": "EMA",
    "maLength": 45,
    "closeCountLong": 7,
}
```

### 6.2 Update Regression Tests

**File**: `tests/test_regression_s01.py`

**Action Items**:
1. Update parameter dictionaries to use camelCase
2. Verify baseline comparisons still pass
3. Update any hardcoded parameter references

### 6.3 Update Unit Tests

**Files**:
- `tests/test_optuna_engine.py`
- `tests/test_export.py`

**Action Items**:
1. Update tests for generic OptimizationResult (params as dict)
2. Update tests for dynamic CSV column building
3. Add tests for parameter type system

### 6.4 Add Naming Consistency Tests

**File**: `tests/test_naming_consistency.py` (NEW)

**Create**:
```python
"""Test naming consistency across the codebase."""
import pytest
from dataclasses import fields
from strategies.s01_trailing_ma.strategy import S01Params, S01Strategy
from strategies.s04_stochrsi.strategy import S04Params, S04Strategy
from strategies import get_strategy_config


def test_s01_params_use_camelCase():
    """Verify all S01Params fields use camelCase."""
    for field in fields(S01Params):
        # Skip internal control parameters
        if field.name in ["use_backtester", "use_date_filter", "start", "end"]:
            continue

        # Check no underscores (camelCase has no underscores)
        assert "_" not in field.name, f"S01Params field {field.name} uses snake_case"


def test_s04_params_use_camelCase():
    """Verify all S04Params fields use camelCase."""
    for field in fields(S04Params):
        # Skip internal control parameters
        if field.name in ["use_backtester", "use_date_filter", "start", "end"]:
            continue

        assert "_" not in field.name, f"S04Params field {field.name} uses snake_case"


def test_config_matches_params_s01():
    """Verify S01 config.json parameter names match Params dataclass."""
    config = get_strategy_config("s01_trailing_ma")
    config_params = set(config["parameters"].keys())

    dataclass_params = {
        f.name for f in fields(S01Params)
        if f.name not in ["use_backtester", "use_date_filter", "start", "end"]
    }

    # All config params should exist in dataclass
    for param_name in config_params:
        assert param_name in dataclass_params, \
            f"Config param {param_name} not in S01Params dataclass"


def test_config_matches_params_s04():
    """Verify S04 config.json parameter names match Params dataclass."""
    config = get_strategy_config("s04_stochrsi")
    config_params = set(config["parameters"].keys())

    dataclass_params = {
        f.name for f in fields(S04Params)
        if f.name not in ["use_backtester", "use_date_filter", "start", "end"]
    }

    for param_name in config_params:
        assert param_name in dataclass_params, \
            f"Config param {param_name} not in S04Params dataclass"


def test_no_conversion_code():
    """Verify no snake_case ↔ camelCase conversion exists."""
    import inspect

    # Check S01Params.from_dict has no conversion
    source = inspect.getsource(S01Params.from_dict)
    assert "ma_type" not in source, "S01Params.from_dict still has snake_case conversion"
    assert "ma_length" not in source, "S01Params.from_dict still has snake_case conversion"

    # Check S01Params has no to_dict method
    assert not hasattr(S01Params, "to_dict"), "S01Params.to_dict should be deleted"


def test_parameter_types_valid():
    """Verify all strategies use valid parameter types."""
    valid_types = {"int", "float", "select", "options", "bool"}

    for strategy_id in ["s01_trailing_ma", "s04_stochrsi"]:
        config = get_strategy_config(strategy_id)
        parameters = config.get("parameters", {})

        for param_name, param_spec in parameters.items():
            param_type = param_spec.get("type")
            assert param_type in valid_types, \
                f"{strategy_id} param {param_name} has invalid type {param_type}"
```

### 6.5 Update CLAUDE.md

**File**: `CLAUDE.md`

**Add Section**:
```markdown
## Naming Convention: camelCase Throughout

**Critical Rule**: All parameters MUST use camelCase matching Pine Script conventions.

### Parameter Flow (No Conversions)

Pine Script (camelCase) → config.json (camelCase) → Python (camelCase) → CSV (camelCase)

Example:
- Pine Script: `input.int(16, "RSI Length")` → variable `rsiLen`
- config.json: `"rsiLen": {"type": "int", "default": 16}`
- Python Params: `rsiLen: int = 16`
- CSV export: column `rsiLen`

### Parameter Type System

Match Pine Script input types:

| Pine Script | config.json | Frontend | Python |
|-------------|-------------|----------|--------|
| `input.int()` | `"type": "int"` | Number input | `int` |
| `input.float()` | `"type": "float"` | Number input | `float` |
| `input.string(options=[...])` | `"type": "select"` | Dropdown | `str` |
| `input.bool()` | `"type": "bool"` | Checkbox | `bool` |

### Adding New Strategies

1. **Parameter names**: Use camelCase (e.g., `rsiLen`, not `rsi_len`)
2. **Params dataclass**: Typed fields with camelCase names
3. **from_dict()**: Direct mapping, no conversion
4. **No to_dict()**: Use `asdict(params)` from dataclasses module
5. **config.json**: Use correct parameter types (int/float/select/bool)

### Hybrid Architecture Pattern

**Strategy Level** (Type Safety):
```python
@dataclass
class S05Params:
    rsiLen: int = 16  # ← camelCase, typed
```

**Core Modules** (Generic):
```python
def optimize(params: Dict[str, Any]):  # ← Generic dict
    result.params = params  # ← Store as-is
```

### Performance Note

The multiprocessing cache architecture MUST be preserved. When modifying optimization logic, respect the caching pattern in `_init_worker()`.
```

### 6.6 Update PROJECT_TARGET_ARCHITECTURE.md

**File**: `docs/PROJECT_TARGET_ARCHITECTURE.md`

**Add Section**:
```markdown
## Naming Convention and Parameter Flow

### camelCase Throughout

All parameters use camelCase matching Pine Script conventions. No conversion layers exist.

**Parameter Flow**:
```
Pine Script (rsiLen) → config.json (rsiLen) → Python (rsiLen) → CSV (rsiLen)
```

**Benefits**:
- No conversion code needed
- Parameter names identical across entire pipeline
- Easier debugging (same name everywhere)
- Matches Pine Script source

### Hybrid Architecture: Typed Strategies + Generic Core

**Strategy Level** (Type Safety):
- Strategies define typed Params dataclasses
- Fields use camelCase matching config.json
- IDE autocomplete and type hints work
- Example: `S04Params.rsiLen: int = 16`

**Core Level** (Generic):
- Core modules work with `Dict[str, Any]`
- No hardcoded parameter knowledge
- Strategy-agnostic operation
- Example: `OptimizationResult.params: Dict[str, Any]`

**Conversion**:
- Happens once inside strategy: `self.params = S04Params.from_dict(params_dict)`
- Core modules pass dicts, strategies convert to typed dataclasses
```

### 6.7 Create Strategy Development Guide

**File**: `docs/ADDING_NEW_STRATEGY.md` (NEW)

**Create**:
```markdown
# Adding a New Strategy

## Step 1: Create Strategy Directory

```bash
mkdir -p src/strategies/s05_mystrategy
touch src/strategies/s05_mystrategy/__init__.py
touch src/strategies/s05_mystrategy/strategy.py
touch src/strategies/s05_mystrategy/config.json
```

## Step 2: Define config.json

Use camelCase parameter names matching your Pine Script source.

```json
{
  "id": "s05_mystrategy",
  "name": "S05 My Strategy",
  "version": "v01",
  "description": "Brief description",
  "parameters": {
    "rsiLen": {
      "type": "int",
      "label": "RSI Length",
      "default": 14,
      "min": 2,
      "max": 100,
      "step": 1,
      "group": "Indicators",
      "optimize": {
        "enabled": true,
        "min": 5,
        "max": 50,
        "step": 1
      }
    },
    "maType": {
      "type": "select",
      "label": "MA Type",
      "default": "EMA",
      "options": ["SMA", "EMA", "HMA"],
      "group": "Indicators",
      "optimize": {
        "enabled": false
      }
    },
    "threshold": {
      "type": "float",
      "label": "Entry Threshold",
      "default": 0.5,
      "min": 0.0,
      "max": 1.0,
      "step": 0.1,
      "group": "Entry",
      "optimize": {
        "enabled": true,
        "min": 0.1,
        "max": 0.9,
        "step": 0.1
      }
    }
  }
}
```

**Parameter Type Reference**:
- `"int"` - Integer values (Pine: `input.int()`)
- `"float"` - Decimal values (Pine: `input.float()`)
- `"select"` - Dropdown options (Pine: `input.string(options=[...])`)
- `"bool"` - True/False (Pine: `input.bool()`)

## Step 3: Define Params Dataclass

Use camelCase field names matching config.json.

```python
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class S05Params:
    """S05 strategy parameters - camelCase matching Pine Script."""
    rsiLen: int = 14
    maType: str = "EMA"
    threshold: float = 0.5

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "S05Params":
        """Direct mapping - no conversion."""
        return cls(
            rsiLen=int(d.get("rsiLen", 14)),
            maType=str(d.get("maType", "EMA")),
            threshold=float(d.get("threshold", 0.5)),
        )
```

**Rules**:
- ✅ Use camelCase (e.g., `rsiLen`, `maType`)
- ❌ Do NOT use snake_case (e.g., `rsi_len`, `ma_type`)
- ✅ Direct mapping in from_dict() (no conversion)
- ❌ Do NOT create to_dict() method (use `asdict()` instead)

## Step 4: Implement Strategy

```python
from core.backtest_engine import StrategyResult, TradeRecord
from strategies.base import BaseStrategy

class S05Strategy(BaseStrategy):
    def __init__(self, params_dict: Dict[str, Any]):
        # Hybrid: convert dict to typed dataclass
        self.params = S05Params.from_dict(params_dict)

    def run(self, df: pd.DataFrame, warmup_bars: int = 0) -> StrategyResult:
        """Execute strategy and return results."""
        p = self.params

        # Calculate indicators (use camelCase params)
        rsi = calculate_rsi(df["close"], p.rsiLen)
        ma = get_ma(df["close"], p.maType, p.rsiLen)

        # Trading logic
        trades = []
        position = None

        for i in range(warmup_bars, len(df)):
            # Entry logic
            if position is None and rsi[i] < 30:
                position = {
                    "entry_idx": i,
                    "entry_price": df["close"].iloc[i],
                    "direction": "long",
                }

            # Exit logic
            elif position is not None and rsi[i] > 70:
                trade = TradeRecord(
                    entry_time=df.index[position["entry_idx"]],
                    exit_time=df.index[i],
                    entry_price=position["entry_price"],
                    exit_price=df["close"].iloc[i],
                    size=1.0,
                    direction=position["direction"],
                    pnl=(df["close"].iloc[i] - position["entry_price"]) * 1.0,
                    commission=0.0,
                )
                trades.append(trade)
                position = None

        return StrategyResult(trades=trades)
```

## Step 5: Register Strategy

Add to `src/strategies/__init__.py`:

```python
from .s05_mystrategy.strategy import S05Strategy

STRATEGY_REGISTRY = {
    "s01_trailing_ma": S01Strategy,
    "s04_stochrsi": S04Strategy,
    "s05_mystrategy": S05Strategy,  # ← Add here
}
```

## Step 6: Test

```bash
cd src
python run_backtest.py --strategy s05_mystrategy --csv ../data/sample.csv
```

## Common Mistakes to Avoid

1. ❌ Using snake_case parameter names
2. ❌ Creating conversion code in from_dict()
3. ❌ Hardcoding strategy logic in core modules
4. ❌ Using invalid parameter types in config.json
5. ❌ Forgetting to add strategy to STRATEGY_REGISTRY

## Architecture Guarantees

After following this guide:
- ✅ Frontend renders your parameters automatically based on type
- ✅ Optimization works without core module changes
- ✅ CSV export includes your parameters automatically
- ✅ Parameter validation works generically
- ✅ Your strategy is treated identically to S01 and S04
```

### Phase 6 Verification

**Test Checklist**:
- [ ] All test fixtures use camelCase parameters
- [ ] Regression tests pass with camelCase
- [ ] Unit tests updated for generic OptimizationResult
- [ ] Naming consistency tests added and passing
- [ ] CLAUDE.md documents camelCase convention
- [ ] PROJECT_TARGET_ARCHITECTURE.md documents Hybrid approach
- [ ] ADDING_NEW_STRATEGY.md created with clear guide
- [ ] All existing tests pass
- [ ] New tests pass

**Test Command**:
```bash
cd tests
pytest -v
pytest test_naming_consistency.py -v
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

### Integration Testing

After ALL phases complete:

1. **End-to-End S01 Test**:
   - Load S01 in frontend
   - Verify all parameters render correctly
   - Submit backtest request
   - Verify results displayed
   - Submit optimization request
   - Verify CSV export correct

2. **End-to-End S04 Test**:
   - Repeat above for S04 strategy

3. **Cross-Strategy Test**:
   - Switch between S01 and S04 in frontend
   - Verify parameter forms update correctly
   - Verify no parameter name conflicts

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
   - Format: `[Phase X] Brief description`
   - Example: `[Phase 1] Convert S01Params to camelCase`
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

**Server**:
- `src/server.py` - Flask API server (~1600 lines)
  - Lines 156-211: DEFAULT_PRESET (REFACTOR)
  - Lines 1182-1514: Dual naming fallbacks (REFACTOR)
  - Lines 1207-1273: _sanitize_score_config (REFACTOR)
  - Lines 1318-1333: strategy_param_types extraction (DELETE)
  - Lines 1340-1350: S01-specific parameter handling (DELETE)

### Frontend

**UI**:
- `index.html` - Main HTML page (~1200 lines)
  - Hardcoded MA type selection (REFACTOR to generic)
  - Parameter rendering (REFACTOR)

### Documentation

- `CLAUDE.md` - Project guidelines for Claude Code
- `docs/PROJECT_TARGET_ARCHITECTURE.md` - Target architecture
- `docs/PROJECT_STRUCTURE.md` - Directory structure
- `docs/prompt_9-5_refactor_plan_upd.md` - This refactoring plan
- `docs/ADDING_NEW_STRATEGY.md` - (NEW) Strategy development guide

---

## Success Criteria (Final Checklist)

After completing all 6 phases, verify:

- [ ] **No hardcoded parameter names** in core modules (optuna_engine, export, server)
- [ ] **Single naming convention** (camelCase) throughout entire system
- [ ] **No strategy-specific conditionals** (`if strategy_id == "s01"`) in core modules
- [ ] **No conversion code** between naming conventions (snake_case ↔ camelCase)
- [ ] **S01 and S04 treated identically** by core system
- [ ] **Frontend renders parameters generically** based on type from config.json
- [ ] **Adding new strategy requires only** config.json + strategy.py (no core changes)
- [ ] **All existing tests pass** (regression, unit, integration)
- [ ] **CSV export works correctly** for both S01 and S04
- [ ] **MA type dropdowns work** for S01 (via generic "select" type rendering)
- [ ] **Optimization completes** without errors for both strategies
- [ ] **Performance preserved** (no regression in optimization speed)
- [ ] **Documentation updated** (CLAUDE.md, architecture docs, new guide)
- [ ] **Naming consistency tests pass** (no snake_case in strategy params)
- [ ] **Parameter flow verified**: Pine → JSON → Python → CSV (same names throughout)

---

## Final Notes

### Critical Preservation

**DO NOT MODIFY**:
1. Multiprocessing cache architecture (`_init_worker()` in optuna_engine.py)
2. Performance-critical indicator calculations
3. Metrics calculation logic (unless fixing bugs)
4. Trade simulation core logic in backtest_engine.py

### Breaking Changes

This refactoring includes **breaking changes**:
- Existing CSV exports with snake_case headers become invalid
- Saved presets with snake_case parameters won't load
- API clients must update to camelCase parameters

**Mitigation**: Provide migration script or one-time conversion logic if needed.

### Future-Proofing

After this refactoring:
- Adding S05, S06, ... strategies is trivial (config.json + strategy.py)
- Parameter types can be extended (e.g., add "string" type)
- Frontend automatically adapts to new strategies
- No core module maintenance needed for new strategies

### Questions or Issues

If you encounter ambiguity or issues:
1. **Preserve existing behavior** - Refactoring should not change functionality
2. **Ask for clarification** - Don't guess on critical decisions
3. **Document assumptions** - Add comments explaining non-obvious choices
4. **Test incrementally** - Verify each change before moving to next

---

**END OF PROMPT**

Total word count: ~10,500 words
Estimated size: ~95 KB (target: ~40 KB)

This comprehensive prompt provides the GPT 5.1 Codex agent with everything needed to complete the Phase 9-5 refactoring successfully. The agent has clear instructions, concrete examples, verification criteria, and file references to execute the plan systematically.
