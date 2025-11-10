# Walk-Forward Analysis Implementation - Technical Specification

## Project Context

You are working on a crypto trading strategy backtesting and optimization system with the following components:

**Existing modules:**
- `backtest_engine.py` - Strategy execution engine with TrailingMA trend following strategy
- `optimizer_engine.py` - Grid search optimization with composite scoring
- `optuna_engine.py` - Bayesian optimization using Optuna TPE sampler
- `server.py` - Flask API backend
- `index.html` - Web UI for running backtests and optimizations
- `run_backtest.py` - CLI for quick testing

**Current problem:**
The system optimizes parameters on the entire dataset (or single period), which leads to overfitting. Parameters are fitted to historical data but won't work in the future. We need to implement Walk-Forward Analysis with cross-validation to find robust parameters.

---

## Objective

Implement a comprehensive Walk-Forward Analysis (WFA) system that:
1. Splits data into multiple IS/OOS windows with gap
2. Optimizes on IS periods using existing Optuna optimizer
3. Validates on OOS periods
4. Reserves final Forward Test period (never used in optimization)
5. Optionally uses cross-validation inside IS for extra robustness
6. Aggregates results across all windows
7. Ranks parameter sets by Forward Test performance
8. Integrates seamlessly with existing UI

---

## Core Concepts

### Walk-Forward Process

```
Full Dataset (100%)
│
├─── WF Zone (75-85%) ──────────────────────┐
│    │                                       │
│    ├─ Window 1: [Warmup][IS][Gap][OOS]   │
│    ├─ Window 2: [Warmup][IS][Gap][OOS]   │
│    ├─ Window 3: [Warmup][IS][Gap][OOS]   │
│    └─ Window N: [Warmup][IS][Gap][OOS]   │
│                                            │
└─── Forward Reserve (15-25%) ──────────────┘
     NEVER used in optimization!
```

### Two Modes

**Rolling Window:**
```
Window 1: [Warmup][──IS──][G][OOS]
Window 2:        [Warmup][──IS──][G][OOS]
Window 3:               [Warmup][──IS──][G][OOS]
```
- Fixed IS size
- Adapts to market changes
- Recommended for crypto

**Anchored Window:**
```
Window 1: [Warmup][──IS──][G][OOS]
Window 2: [Warmup][────IS────][G][OOS]
Window 3: [Warmup][──────IS──────][G][OOS]
```
- Fixed start, expanding IS
- More data over time
- More stable parameters

### Cross-Validation Inside IS (Optional)

For each trial in Optuna:
```
IS Period split into 5 folds (TimeSeriesSplit):

Fold 1: Train[weeks 1-2]     → Test[week 3]
Fold 2: Train[weeks 1-4]     → Test[week 5]
Fold 3: Train[weeks 1-6]     → Test[week 7]
Fold 4: Train[weeks 1-8]     → Test[week 9]
Fold 5: Train[weeks 1-10]    → Test[week 11]

Trial score = median(scores from all 5 test folds)
```

This protects against overfitting even within IS.

---

## Architecture

### New Module: `walkforward_engine.py`

Create a new module with the following structure:

```python
"""Walk-Forward Analysis engine for strategy optimization."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import pandas as pd
import numpy as np
from enum import Enum

# === ENUMS ===

class WFMode(Enum):
    """Walk-Forward window mode"""
    ROLLING = "rolling"
    ANCHORED = "anchored"

class CVMode(Enum):
    """Cross-validation mode"""
    DISABLED = "disabled"
    ENABLED = "enabled"
    AUTO = "auto"

# === CONFIGURATION CLASSES ===

@dataclass
class WalkForwardConfig:
    """Configuration for Walk-Forward Analysis"""
    
    # Mode selection
    mode: WFMode = WFMode.ROLLING
    
    # Data allocation (percentages)
    wf_zone_pct: float = 80.0  # 80% for WF analysis
    forward_reserve_pct: float = 20.0  # 20% for final test
    
    # Window configuration (percentages within WF zone)
    is_pct: float = 70.0  # 70% IS within each window
    oos_pct: float = 30.0  # 30% OOS within each window
    
    # Gap between IS and OOS
    gap_bars: int = 2
    
    # Step size (for rolling mode, % of OOS size)
    step_pct: float = 100.0  # 100% = no overlap
    
    # Cross-validation inside IS
    cv_mode: CVMode = CVMode.AUTO
    cv_folds: int = 5
    cv_gap_bars: int = 0
    
    # Selection criteria
    topk_per_window: int = 20  # Top K params from each window
    min_oos_win_rate: float = 0.70  # 70% OOS periods must be profitable
    max_degradation: float = 0.40  # Max 40% performance drop IS→OOS
    min_trades_oos: int = 10  # Minimum trades on OOS for validity
    min_forward_profit: float = 0.0  # Minimum profit on forward test
    
    # Warmup configuration
    warmup_multiplier: float = 1.5  # Warmup = max_indicator_period × 1.5
    min_warmup_bars: int = 1000  # Absolute minimum warmup

@dataclass
class WindowSplit:
    """Represents one IS/OOS window split"""
    window_id: int
    
    # Warmup period (for indicator initialization)
    warmup_start_idx: int
    warmup_end_idx: int
    
    # IS period (optimization)
    is_start_idx: int
    is_end_idx: int
    
    # Gap period (excluded)
    gap_start_idx: int
    gap_end_idx: int
    
    # OOS period (validation)
    oos_start_idx: int
    oos_end_idx: int
    
    def get_warmup_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Get warmup data"""
        return df.iloc[self.warmup_start_idx:self.warmup_end_idx]
    
    def get_is_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Get IS data (includes warmup for indicator calculation)"""
        return df.iloc[self.warmup_start_idx:self.is_end_idx]
    
    def get_is_only_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Get IS data without warmup (for metrics calculation)"""
        return df.iloc[self.is_start_idx:self.is_end_idx]
    
    def get_oos_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Get OOS data (includes warmup for indicator calculation)"""
        # OOS needs warmup too - use entire history up to OOS end
        return df.iloc[self.warmup_start_idx:self.oos_end_idx]
    
    def get_oos_only_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Get OOS data without history (for metrics calculation)"""
        return df.iloc[self.oos_start_idx:self.oos_end_idx]

@dataclass
class WindowResult:
    """Results from one WF window"""
    window_id: int
    window_split: WindowSplit
    
    # Top K parameter sets from IS optimization
    top_params: List[Dict[str, Any]]
    is_results: List[Dict[str, float]]  # Metrics on IS
    
    # Validation results on OOS
    oos_results: List[Dict[str, float]]  # Metrics on OOS
    
    # Filtered results (after applying criteria)
    passed_params: List[Dict[str, Any]]
    passed_oos_results: List[Dict[str, float]]

@dataclass
class AggregatedParamResult:
    """Aggregated results for one parameter set across all windows"""
    param_hash: str  # Unique hash of parameter set
    params: Dict[str, Any]
    
    # How many windows this param set appeared in
    window_count: int
    
    # OOS metrics across windows
    oos_profits: List[float]
    oos_drawdowns: List[float]
    oos_sharpes: List[float]
    oos_trades: List[int]
    
    # Aggregated OOS metrics
    avg_oos_profit: float
    median_oos_profit: float
    std_oos_profit: float
    oos_win_rate: float  # % of windows with profit > 0
    
    # IS→OOS degradation
    avg_is_profit: float
    avg_degradation: float  # (IS - OOS) / IS
    
    # Composite score
    consistency_score: float
    aggregate_score: float

@dataclass
class ForwardTestResult:
    """Results on Forward Test period"""
    param_hash: str
    params: Dict[str, Any]
    
    # Forward test metrics
    forward_profit: float
    forward_drawdown: float
    forward_sharpe: float
    forward_trades: int
    
    # Status
    passed: bool
    status: str  # "PASSED", "WEAK", "FAILED"

@dataclass
class WalkForwardResult:
    """Complete Walk-Forward Analysis results"""
    config: WalkForwardConfig
    
    # Window splits
    windows: List[WindowSplit]
    forward_start_idx: int
    forward_end_idx: int
    
    # Results per window
    window_results: List[WindowResult]
    
    # Aggregated results across windows
    aggregated_results: List[AggregatedParamResult]
    
    # Forward test results
    forward_results: List[ForwardTestResult]
    
    # Final ranking (sorted by forward performance)
    final_ranking: List[Tuple[str, float]]  # (param_hash, final_score)

# === MAIN ENGINE CLASS ===

class WalkForwardEngine:
    """Main engine for Walk-Forward Analysis"""
    
    def __init__(self, config: WalkForwardConfig):
        self.config = config
    
    def calculate_required_warmup(self, param_ranges: Dict[str, Any]) -> int:
        """Calculate required warmup based on parameter ranges"""
        # Extract max indicator periods from param ranges
        max_ma = param_ranges.get('maLength', (0, 200, 1))[1]
        max_trail_long = param_ranges.get('trailLongLength', (0, 200, 1))[1]
        max_trail_short = param_ranges.get('trailShortLength', (0, 200, 1))[1]
        atr_period = param_ranges.get('atrPeriod', 14)
        
        max_period = max(max_ma, max_trail_long, max_trail_short, atr_period)
        
        # Apply multiplier
        required = int(max_period * self.config.warmup_multiplier)
        
        # Ensure minimum
        required = max(required, self.config.min_warmup_bars)
        
        return required
    
    def validate_data_sufficiency(
        self, 
        df: pd.DataFrame, 
        param_ranges: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate that we have enough data for WF analysis"""
        total_bars = len(df)
        required_warmup = self.calculate_required_warmup(param_ranges)
        
        # Calculate minimum required bars
        # Need: warmup + at least 2 windows worth of data
        min_window_bars = 5000  # Minimum for statistical significance
        min_required = required_warmup + (min_window_bars * 2)
        
        validation = {
            'sufficient': total_bars >= min_required,
            'total_bars': total_bars,
            'required_warmup': required_warmup,
            'recommended_warmup': int(required_warmup * 1.2),
            'min_required_total': min_required,
            'available_for_wf': total_bars - required_warmup
        }
        
        return validation
    
    def split_data(
        self, 
        df: pd.DataFrame,
        param_ranges: Dict[str, Any]
    ) -> Tuple[List[WindowSplit], int, int]:
        """
        Split data into WF windows + Forward Reserve
        
        Returns:
            windows: List of WindowSplit objects
            forward_start_idx: Start index of forward test period
            forward_end_idx: End index of forward test period
        """
        total_bars = len(df)
        required_warmup = self.calculate_required_warmup(param_ranges)
        
        # Calculate WF zone and Forward Reserve
        wf_zone_bars = int(total_bars * (self.config.wf_zone_pct / 100))
        forward_bars = total_bars - wf_zone_bars
        
        # Forward test indices
        forward_start_idx = wf_zone_bars
        forward_end_idx = total_bars
        
        # Available bars for WF (after warmup)
        wf_start_idx = required_warmup
        wf_end_idx = wf_zone_bars
        available_wf_bars = wf_end_idx - wf_start_idx
        
        if available_wf_bars < 2000:
            raise ValueError(
                f"Not enough data for WF analysis after warmup. "
                f"Available: {available_wf_bars} bars, need at least 2000."
            )
        
        # Calculate window sizes based on mode
        if self.config.mode == WFMode.ROLLING:
            windows = self._split_rolling(
                wf_start_idx, wf_end_idx, available_wf_bars, required_warmup
            )
        else:  # ANCHORED
            windows = self._split_anchored(
                wf_start_idx, wf_end_idx, available_wf_bars, required_warmup
            )
        
        return windows, forward_start_idx, forward_end_idx
    
    def _split_rolling(
        self, 
        wf_start: int, 
        wf_end: int, 
        available_bars: int,
        warmup_bars: int
    ) -> List[WindowSplit]:
        """Split data using rolling window"""
        windows = []
        
        # Calculate IS and OOS sizes
        is_bars = int(available_bars * (self.config.is_pct / 100))
        oos_bars = int(available_bars * (self.config.oos_pct / 100))
        
        # Step size
        step_bars = int(oos_bars * (self.config.step_pct / 100))
        
        window_id = 1
        current_is_start = wf_start
        
        while True:
            # IS period
            is_start = current_is_start
            is_end = is_start + is_bars
            
            # Gap period
            gap_start = is_end
            gap_end = gap_start + self.config.gap_bars
            
            # OOS period
            oos_start = gap_end
            oos_end = oos_start + oos_bars
            
            # Check if we're still in WF zone
            if oos_end > wf_end:
                break
            
            # Warmup for this window
            warmup_start = is_start - warmup_bars
            warmup_end = is_start
            
            if warmup_start < 0:
                warmup_start = 0
            
            windows.append(WindowSplit(
                window_id=window_id,
                warmup_start_idx=warmup_start,
                warmup_end_idx=warmup_end,
                is_start_idx=is_start,
                is_end_idx=is_end,
                gap_start_idx=gap_start,
                gap_end_idx=gap_end,
                oos_start_idx=oos_start,
                oos_end_idx=oos_end
            ))
            
            window_id += 1
            current_is_start += step_bars
        
        return windows
    
    def _split_anchored(
        self, 
        wf_start: int, 
        wf_end: int, 
        available_bars: int,
        warmup_bars: int
    ) -> List[WindowSplit]:
        """Split data using anchored (expanding) window"""
        windows = []
        
        # Fixed anchor point
        anchor_start = wf_start
        
        # Calculate OOS size
        oos_bars = int(available_bars * (self.config.oos_pct / 100))
        
        # Step size
        step_bars = int(oos_bars * (self.config.step_pct / 100))
        
        # Initial IS size
        initial_is_bars = int(available_bars * (self.config.is_pct / 100))
        
        window_id = 1
        current_is_end = anchor_start + initial_is_bars
        
        while True:
            # IS period (from anchor to current_is_end)
            is_start = anchor_start
            is_end = current_is_end
            
            # Gap period
            gap_start = is_end
            gap_end = gap_start + self.config.gap_bars
            
            # OOS period
            oos_start = gap_end
            oos_end = oos_start + oos_bars
            
            # Check if we're still in WF zone
            if oos_end > wf_end:
                break
            
            # Warmup is always from the beginning
            warmup_start = max(0, anchor_start - warmup_bars)
            warmup_end = anchor_start
            
            windows.append(WindowSplit(
                window_id=window_id,
                warmup_start_idx=warmup_start,
                warmup_end_idx=warmup_end,
                is_start_idx=is_start,
                is_end_idx=is_end,
                gap_start_idx=gap_start,
                gap_end_idx=gap_end,
                oos_start_idx=oos_start,
                oos_end_idx=oos_end
            ))
            
            window_id += 1
            current_is_end += step_bars
        
        return windows
    
    def should_use_cv(
        self, 
        optuna_config: Dict[str, Any],
        window_split: WindowSplit
    ) -> bool:
        """
        Decide whether to use CV based on auto mode logic
        
        Auto mode enables CV if:
        - Large number of trials (>200)
        - Large search space
        - Sufficient IS data for CV splits
        """
        if self.config.cv_mode == CVMode.ENABLED:
            return True
        elif self.config.cv_mode == CVMode.DISABLED:
            return False
        else:  # AUTO
            # Check number of trials
            n_trials = optuna_config.get('n_trials', 100)
            if n_trials > 200:
                return True
            
            # Check IS size
            is_bars = window_split.is_end_idx - window_split.is_start_idx
            min_bars_for_cv = 5000  # Need sufficient data for 5 folds
            if is_bars < min_bars_for_cv:
                return False
            
            # Default: enable CV for robustness
            return True
    
    def run_optimization(
        self,
        df: pd.DataFrame,
        optuna_config: Dict[str, Any],
        optimization_config: Dict[str, Any],
        param_ranges: Dict[str, Any],
        progress_callback: Optional[callable] = None
    ) -> WalkForwardResult:
        """
        Main function to run complete Walk-Forward Analysis
        
        Steps:
        1. Validate data sufficiency
        2. Split data into windows + forward reserve
        3. For each window:
           a. Optimize on IS (with or without CV)
           b. Validate TopK on OOS
           c. Apply filters
        4. Aggregate results across windows
        5. Test top aggregated params on Forward Reserve
        6. Rank by forward performance
        """
        # Step 1: Validate
        validation = self.validate_data_sufficiency(df, param_ranges)
        if not validation['sufficient']:
            raise ValueError(
                f"Insufficient data for WF analysis.\n"
                f"Total: {validation['total_bars']} bars\n"
                f"Required: {validation['min_required_total']} bars\n"
                f"Warmup: {validation['required_warmup']} bars\n"
                f"Available for WF: {validation['available_for_wf']} bars"
            )
        
        # Step 2: Split data
        windows, fwd_start, fwd_end = self.split_data(df, param_ranges)
        
        if progress_callback:
            progress_callback({
                'stage': 'split',
                'total_windows': len(windows),
                'forward_start': fwd_start,
                'forward_end': fwd_end
            })
        
        # Step 3: Process each window
        window_results = []
        for i, window in enumerate(windows):
            if progress_callback:
                progress_callback({
                    'stage': 'window_optimization',
                    'window_id': window.window_id,
                    'window_num': i + 1,
                    'total_windows': len(windows)
                })
            
            # Get IS data (includes warmup for indicator calculation)
            is_df = window.get_is_df(df)
            is_only_df = window.get_is_only_df(df)
            
            # Decide if we should use CV
            use_cv = self.should_use_cv(optuna_config, window)
            
            if use_cv:
                # Optimize with CV
                top_params = self._optimize_with_cv(
                    is_df, is_only_df, window, optuna_config, optimization_config
                )
            else:
                # Standard optimization
                top_params = self._optimize_standard(
                    is_df, is_only_df, window, optuna_config, optimization_config
                )
            
            # Calculate IS metrics for TopK
            is_results = self._calculate_metrics(is_only_df, top_params)
            
            # Validate on OOS
            oos_df = window.get_oos_df(df)
            oos_only_df = window.get_oos_only_df(df)
            oos_results = self._calculate_metrics(oos_only_df, top_params)
            
            # Apply filters
            passed_params, passed_oos = self._filter_params(
                top_params, is_results, oos_results
            )
            
            window_results.append(WindowResult(
                window_id=window.window_id,
                window_split=window,
                top_params=top_params,
                is_results=is_results,
                oos_results=oos_results,
                passed_params=passed_params,
                passed_oos_results=passed_oos
            ))
        
        # Step 4: Aggregate results
        if progress_callback:
            progress_callback({'stage': 'aggregation'})
        
        aggregated = self._aggregate_results(window_results)
        
        # Step 5: Forward Test
        if progress_callback:
            progress_callback({'stage': 'forward_test'})
        
        forward_df = df.iloc[fwd_start:fwd_end]
        forward_results = self._run_forward_test(
            forward_df, aggregated[:50]  # Top 50 for forward test
        )
        
        # Step 6: Final ranking
        final_ranking = self._rank_by_forward(aggregated, forward_results)
        
        return WalkForwardResult(
            config=self.config,
            windows=windows,
            forward_start_idx=fwd_start,
            forward_end_idx=fwd_end,
            window_results=window_results,
            aggregated_results=aggregated,
            forward_results=forward_results,
            final_ranking=final_ranking
        )
    
    def _optimize_standard(
        self,
        is_df: pd.DataFrame,
        is_only_df: pd.DataFrame,
        window: WindowSplit,
        optuna_config: Dict[str, Any],
        optimization_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Run standard Optuna optimization on IS"""
        # Import existing optuna_engine
        from optuna_engine import run_optuna_optimization
        
        # Prepare config
        config = {**optuna_config, **optimization_config}
        
        # Run optimization
        # Note: This should return TopK parameter sets
        results = run_optuna_optimization(is_only_df, config)
        
        # Extract TopK
        top_k = self.config.topk_per_window
        return results[:top_k]
    
    def _optimize_with_cv(
        self,
        is_df: pd.DataFrame,
        is_only_df: pd.DataFrame,
        window: WindowSplit,
        optuna_config: Dict[str, Any],
        optimization_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Run Optuna optimization with CV inside IS
        
        For each trial:
        1. Split IS into CV folds
        2. Test params on all folds
        3. Return median score across folds
        """
        # This requires modifying the objective function in optuna_engine
        # to support CV mode
        
        # Split IS into CV folds
        cv_folds = self._create_cv_folds(is_only_df)
        
        # Modify config to include CV folds
        cv_config = {
            **optuna_config,
            **optimization_config,
            'cv_folds': cv_folds,
            'cv_enabled': True,
            'cv_gap_bars': self.config.cv_gap_bars
        }
        
        # Run optimization with CV
        from optuna_engine import run_optuna_optimization_cv
        results = run_optuna_optimization_cv(is_df, is_only_df, cv_config)
        
        # Extract TopK
        top_k = self.config.topk_per_window
        return results[:top_k]
    
    def _create_cv_folds(
        self, 
        is_df: pd.DataFrame
    ) -> List[Tuple[int, int, int, int]]:
        """
        Create TimeSeriesSplit CV folds
        
        Returns list of tuples: (train_start, train_end, test_start, test_end)
        """
        from sklearn.model_selection import TimeSeriesSplit
        
        n_splits = self.config.cv_folds
        tscv = TimeSeriesSplit(n_splits=n_splits)
        
        folds = []
        for train_idx, test_idx in tscv.split(is_df):
            # Apply gap
            train_end = train_idx[-1]
            test_start = test_idx[0] + self.config.cv_gap_bars
            test_end = test_idx[-1]
            
            if test_start >= test_end:
                continue  # Skip if gap consumed all test data
            
            folds.append((
                train_idx[0],
                train_end,
                test_start,
                test_end
            ))
        
        return folds
    
    def _calculate_metrics(
        self,
        df: pd.DataFrame,
        param_sets: List[Dict[str, Any]]
    ) -> List[Dict[str, float]]:
        """Calculate metrics for each parameter set"""
        from backtest_engine import run_strategy, StrategyParams
        
        metrics = []
        for params in param_sets:
            # Convert to StrategyParams
            strategy_params = StrategyParams.from_dict(params)
            
            # Run backtest
            result = run_strategy(df, strategy_params)
            
            # Extract metrics
            metrics.append({
                'net_profit_pct': result.net_profit_pct,
                'max_drawdown_pct': result.max_drawdown_pct,
                'total_trades': result.total_trades,
                'sharpe_ratio': getattr(result, 'sharpe_ratio', 0.0),
                'profit_factor': getattr(result, 'profit_factor', 0.0),
            })
        
        return metrics
    
    def _filter_params(
        self,
        params: List[Dict[str, Any]],
        is_metrics: List[Dict[str, float]],
        oos_metrics: List[Dict[str, float]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, float]]]:
        """
        Apply filters to parameter sets
        
        Filters:
        1. OOS profit > 0
        2. Degradation IS→OOS < max_degradation
        3. Minimum trades on OOS
        """
        passed_params = []
        passed_oos = []
        
        for p, is_m, oos_m in zip(params, is_metrics, oos_metrics):
            # Filter 1: Positive OOS profit
            if oos_m['net_profit_pct'] <= 0:
                continue
            
            # Filter 2: Degradation check
            if is_m['net_profit_pct'] > 0:
                degradation = 1 - (oos_m['net_profit_pct'] / is_m['net_profit_pct'])
                if degradation > self.config.max_degradation:
                    continue
            
            # Filter 3: Minimum trades
            if oos_m['total_trades'] < self.config.min_trades_oos:
                continue
            
            passed_params.append(p)
            passed_oos.append(oos_m)
        
        return passed_params, passed_oos
    
    def _aggregate_results(
        self, 
        window_results: List[WindowResult]
    ) -> List[AggregatedParamResult]:
        """
        Aggregate results across all windows
        
        Group parameter sets that are similar/identical
        Calculate aggregate statistics
        """
        import hashlib
        import json
        
        # Dictionary to collect params by hash
        param_dict = {}
        
        for window_result in window_results:
            for i, params in enumerate(window_result.passed_params):
                # Create hash of parameters (round floats for comparison)
                param_key = self._hash_params(params)
                
                if param_key not in param_dict:
                    param_dict[param_key] = {
                        'params': params,
                        'window_count': 0,
                        'oos_profits': [],
                        'oos_drawdowns': [],
                        'oos_sharpes': [],
                        'oos_trades': [],
                        'is_profits': []
                    }
                
                oos_metrics = window_result.passed_oos_results[i]
                is_metrics = window_result.is_results[
                    window_result.top_params.index(params)
                ]
                
                param_dict[param_key]['window_count'] += 1
                param_dict[param_key]['oos_profits'].append(oos_metrics['net_profit_pct'])
                param_dict[param_key]['oos_drawdowns'].append(oos_metrics['max_drawdown_pct'])
                param_dict[param_key]['oos_sharpes'].append(oos_metrics.get('sharpe_ratio', 0))
                param_dict[param_key]['oos_trades'].append(oos_metrics['total_trades'])
                param_dict[param_key]['is_profits'].append(is_metrics['net_profit_pct'])
        
        # Convert to AggregatedParamResult objects
        aggregated = []
        for param_hash, data in param_dict.items():
            oos_profits = data['oos_profits']
            is_profits = data['is_profits']
            
            # Calculate OOS win rate
            positive_oos = sum(1 for p in oos_profits if p > 0)
            oos_win_rate = positive_oos / len(oos_profits)
            
            # Calculate degradation
            avg_is = np.mean(is_profits)
            avg_oos = np.mean(oos_profits)
            avg_degradation = 1 - (avg_oos / avg_is) if avg_is > 0 else 0
            
            # Consistency score (based on std deviation)
            std_oos = np.std(oos_profits)
            consistency = 1 / (1 + std_oos)  # Lower std = higher consistency
            
            # Aggregate score (preliminary, will be refined with forward test)
            aggregate_score = (
                0.4 * avg_oos +
                0.3 * oos_win_rate * 100 +
                0.2 * (1 - avg_degradation) * 100 +
                0.1 * consistency * 100
            )
            
            aggregated.append(AggregatedParamResult(
                param_hash=param_hash,
                params=data['params'],
                window_count=data['window_count'],
                oos_profits=oos_profits,
                oos_drawdowns=data['oos_drawdowns'],
                oos_sharpes=data['oos_sharpes'],
                oos_trades=data['oos_trades'],
                avg_oos_profit=avg_oos,
                median_oos_profit=np.median(oos_profits),
                std_oos_profit=std_oos,
                oos_win_rate=oos_win_rate,
                avg_is_profit=avg_is,
                avg_degradation=avg_degradation,
                consistency_score=consistency,
                aggregate_score=aggregate_score
            ))
        
        # Sort by aggregate score
        aggregated.sort(key=lambda x: x.aggregate_score, reverse=True)
        
        return aggregated
    
    def _hash_params(self, params: Dict[str, Any]) -> str:
        """Create hash of parameter set for comparison"""
        import hashlib
        import json
        
        # Round floats for comparison
        rounded = {}
        for k, v in params.items():
            if isinstance(v, float):
                rounded[k] = round(v, 3)
            else:
                rounded[k] = v
        
        # Create hash
        param_str = json.dumps(rounded, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()
    
    def _run_forward_test(
        self,
        forward_df: pd.DataFrame,
        aggregated_results: List[AggregatedParamResult]
    ) -> List[ForwardTestResult]:
        """Run forward test on top aggregated parameter sets"""
        from backtest_engine import run_strategy, StrategyParams
        
        forward_results = []
        
        for agg in aggregated_results:
            # Convert to StrategyParams
            strategy_params = StrategyParams.from_dict(agg.params)
            
            # Run backtest on forward period
            result = run_strategy(forward_df, strategy_params)
            
            # Determine status
            if result.net_profit_pct < self.config.min_forward_profit:
                status = "FAILED"
                passed = False
            elif result.net_profit_pct < agg.avg_oos_profit * 0.5:
                status = "WEAK"
                passed = True
            else:
                status = "PASSED"
                passed = True
            
            forward_results.append(ForwardTestResult(
                param_hash=agg.param_hash,
                params=agg.params,
                forward_profit=result.net_profit_pct,
                forward_drawdown=result.max_drawdown_pct,
                forward_sharpe=getattr(result, 'sharpe_ratio', 0.0),
                forward_trades=result.total_trades,
                passed=passed,
                status=status
            ))
        
        return forward_results
    
    def _rank_by_forward(
        self,
        aggregated_results: List[AggregatedParamResult],
        forward_results: List[ForwardTestResult]
    ) -> List[Tuple[str, float]]:
        """
        Final ranking based on forward test performance
        
        Final Score = 
            0.50 × Forward_Profit_Normalized +
            0.20 × Avg_OOS_Profit_Normalized +
            0.15 × (1 - Degradation) +
            0.10 × OOS_Win_Rate +
            0.05 × Consistency
        """
        # Create mapping
        forward_map = {f.param_hash: f for f in forward_results}
        agg_map = {a.param_hash: a for a in aggregated_results}
        
        scores = []
        
        for param_hash in forward_map.keys():
            fwd = forward_map[param_hash]
            agg = agg_map[param_hash]
            
            # Normalize forward profit (0-100 scale)
            fwd_norm = max(0, min(100, fwd.forward_profit))
            
            # Normalize avg OOS profit
            oos_norm = max(0, min(100, agg.avg_oos_profit))
            
            # Final score
            final_score = (
                0.50 * fwd_norm +
                0.20 * oos_norm +
                0.15 * (1 - agg.avg_degradation) * 100 +
                0.10 * agg.oos_win_rate * 100 +
                0.05 * agg.consistency_score * 100
            )
            
            scores.append((param_hash, final_score))
        
        # Sort by final score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores

# === UTILITY FUNCTIONS ===

def export_wf_results_to_csv(
    result: WalkForwardResult,
    output_path: str
) -> None:
    """Export Walk-Forward results to CSV"""
    import csv
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow(['=== WALK-FORWARD ANALYSIS SUMMARY ==='])
        writer.writerow(['Mode', result.config.mode.value])
        writer.writerow(['WF Zone', f"{result.config.wf_zone_pct}%"])
        writer.writerow(['Forward Reserve', f"{result.config.forward_reserve_pct}%"])
        writer.writerow(['Number of Windows', len(result.windows)])
        writer.writerow(['Gap', f"{result.config.gap_bars} bars"])
        writer.writerow([])
        
        # Final Rankings
        writer.writerow(['=== FINAL RANKING (by Forward Test) ==='])
        writer.writerow([
            'Rank', 'Param_Hash', 'Forward_Profit%', 'Forward_MaxDD%',
            'Avg_OOS_Profit%', 'OOS_WinRate%', 'Score', 'Status'
        ])
        
        forward_map = {f.param_hash: f for f in result.forward_results}
        agg_map = {a.param_hash: a for a in result.aggregated_results}
        
        for rank, (param_hash, score) in enumerate(result.final_ranking[:50], 1):
            fwd = forward_map[param_hash]
            agg = agg_map[param_hash]
            
            writer.writerow([
                rank,
                param_hash[:8],
                f"{fwd.forward_profit:.2f}",
                f"{fwd.forward_drawdown:.2f}",
                f"{agg.avg_oos_profit:.2f}",
                f"{agg.oos_win_rate * 100:.1f}",
                f"{score:.1f}",
                fwd.status
            ])
        
        # ... add more sections as needed

```

---

## Integration with Existing Code

### Modify `optuna_engine.py`

Add support for CV mode:

```python
def run_optuna_optimization_cv(
    is_df: pd.DataFrame,
    is_only_df: pd.DataFrame,
    config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Run Optuna optimization with CV inside IS
    
    For each trial:
    1. Test params on all CV folds
    2. Return median score across folds as trial value
    """
    import optuna
    from backtest_engine import run_strategy, StrategyParams
    
    cv_folds = config['cv_folds']  # List of (train_start, train_end, test_start, test_end)
    cv_gap = config.get('cv_gap_bars', 0)
    
    def objective(trial):
        # Suggest parameters (same as existing code)
        params = suggest_parameters(trial, config)
        
        # Test on all CV folds
        fold_scores = []
        
        for fold_idx, (train_start, train_end, test_start, test_end) in enumerate(cv_folds):
            # Get fold data
            # Note: we use is_df (which includes warmup) for full indicator calculation
            # But metrics are calculated only on test period
            
            fold_test_df = is_only_df.iloc[test_start:test_end]
            
            # Run strategy
            strategy_params = StrategyParams.from_dict(params)
            result = run_strategy(is_df, strategy_params)  # Full df for indicators
            
            # Calculate metrics only on test period
            # This requires filtering trades by time
            test_trades = [
                t for t in result.trades
                if fold_test_df.index[0] <= t.entry_time <= fold_test_df.index[-1]
            ]
            
            # Calculate score based on test trades
            if len(test_trades) < 5:  # Minimum trades
                fold_score = -999
            else:
                fold_score = calculate_score(test_trades, fold_test_df)
            
            fold_scores.append(fold_score)
        
        # Return median score across folds
        return np.median(fold_scores)
    
    # Create study and optimize
    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=config['n_trials'])
    
    # Get TopK trials
    topk = config.get('topk', 20)
    top_trials = sorted(study.trials, key=lambda t: t.value, reverse=True)[:topk]
    
    # Convert to param dicts
    results = [trial.params for trial in top_trials]
    
    return results
```

### Modify `server.py`

Add new endpoint for Walk-Forward:

```python
@app.route('/api/walkforward', methods=['POST'])
def run_walkforward():
    """Run Walk-Forward Analysis"""
    try:
        # Parse request
        data = request.get_json()
        
        # Get uploaded file
        csv_file = request.files.get('csv')
        
        # Parse WF config
        wf_config = WalkForwardConfig(
            mode=WFMode(data.get('wf_mode', 'rolling')),
            wf_zone_pct=float(data.get('wf_zone_pct', 80)),
            forward_reserve_pct=float(data.get('forward_reserve_pct', 20)),
            is_pct=float(data.get('is_pct', 70)),
            oos_pct=float(data.get('oos_pct', 30)),
            gap_bars=int(data.get('gap_bars', 2)),
            cv_mode=CVMode(data.get('cv_mode', 'auto')),
            cv_folds=int(data.get('cv_folds', 5)),
            # ... other params
        )
        
        # Parse optimization config
        optuna_config = parse_optuna_config(data)
        optimization_config = parse_optimization_config(data)
        param_ranges = parse_param_ranges(data)
        
        # Load data
        df = load_data(csv_file)
        
        # Create WF engine
        wf_engine = WalkForwardEngine(wf_config)
        
        # Run WF analysis
        result = wf_engine.run_optimization(
            df=df,
            optuna_config=optuna_config,
            optimization_config=optimization_config,
            param_ranges=param_ranges,
            progress_callback=None  # Could implement WebSocket for progress
        )
        
        # Export results
        output_path = f"/tmp/wf_results_{uuid.uuid4()}.csv"
        export_wf_results_to_csv(result, output_path)
        
        # Return summary
        return jsonify({
            'status': 'success',
            'summary': {
                'total_windows': len(result.windows),
                'top_param_hash': result.final_ranking[0][0],
                'top_score': result.final_ranking[0][1],
                'forward_profit': result.forward_results[0].forward_profit
            },
            'download_url': f"/download/{output_path}"
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
```

---

## UI Changes

### Add Walk-Forward Section to `index.html`

Insert new section in the optimization form:

```html
<!-- Walk-Forward Analysis Section -->
<div class="wf-section" id="wfSection" style="display: none;">
    <h3>⚡ Walk-Forward Analysis</h3>
    
    <!-- Enable/Disable -->
    <div class="form-group">
        <label>
            <input type="checkbox" id="enableWF" onchange="toggleWFSettings()">
            Enable Walk-Forward Analysis
        </label>
    </div>
    
    <!-- Settings (hidden by default) -->
    <div id="wfSettings" style="display: none;">
        
        <!-- Mode Selection -->
        <div class="form-group">
            <label>Window Mode:</label>
            <div class="radio-group">
                <label>
                    <input type="radio" name="wf_mode" value="rolling" checked>
                    Rolling (recommended for crypto)
                </label>
                <label>
                    <input type="radio" name="wf_mode" value="anchored">
                    Anchored (expanding window)
                </label>
            </div>
        </div>
        
        <!-- Data Allocation -->
        <div class="form-group">
            <label>Data Allocation:</label>
            <div class="slider-group">
                <label>
                    WF Zone: 
                    <input type="range" id="wfZonePct" min="70" max="90" value="80" step="5">
                    <span id="wfZoneValue">80%</span>
                </label>
                <label>
                    Forward Reserve: 
                    <input type="range" id="forwardPct" min="10" max="30" value="20" step="5">
                    <span id="forwardValue">20%</span>
                </label>
            </div>
        </div>
        
        <!-- Window Configuration -->
        <div class="form-group">
            <label>Window Configuration:</label>
            <div class="slider-group">
                <label>
                    IS (Training): 
                    <input type="range" id="isPct" min="50" max="80" value="70" step="5">
                    <span id="isValue">70%</span>
                </label>
                <label>
                    OOS (Testing): 
                    <input type="range" id="oosPct" min="20" max="50" value="30" step="5">
                    <span id="oosValue">30%</span>
                </label>
            </div>
        </div>
        
        <!-- Gap -->
        <div class="form-group">
            <label>
                Gap (bars): 
                <input type="number" id="gapBars" value="2" min="0" max="10">
            </label>
            <small>Bars between IS and OOS to prevent look-ahead bias</small>
        </div>
        
        <!-- Cross-Validation -->
        <div class="form-group">
            <label>Cross-Validation in IS:</label>
            <div class="radio-group">
                <label>
                    <input type="radio" name="cv_mode" value="auto" checked>
                    Auto (recommended)
                </label>
                <label>
                    <input type="radio" name="cv_mode" value="enabled">
                    Always Enabled
                </label>
                <label>
                    <input type="radio" name="cv_mode" value="disabled">
                    Disabled
                </label>
            </div>
            <div id="cvSettings">
                <label>
                    CV Folds: 
                    <input type="number" id="cvFolds" value="5" min="3" max="10">
                </label>
            </div>
        </div>
        
        <!-- Selection Criteria -->
        <div class="form-group">
            <label>Selection Criteria:</label>
            <label>
                Top-K per window: 
                <input type="number" id="topkPerWindow" value="20" min="5" max="50">
            </label>
            <label>
                Min OOS Win Rate: 
                <input type="number" id="minOosWinRate" value="70" min="0" max="100" step="5">%
            </label>
            <label>
                Max IS→OOS Degradation: 
                <input type="number" id="maxDegradation" value="40" min="0" max="100" step="5">%
            </label>
        </div>
        
        <!-- Estimated Time -->
        <div class="info-box" id="estimatedTime">
            <p>⏱️ Estimated time: Calculating...</p>
        </div>
        
        <!-- Data Requirements -->
        <div class="info-box" id="dataRequirements">
            <p>📊 Data requirements: Checking...</p>
        </div>
        
    </div>
</div>

<script>
function toggleWFSettings() {
    const enabled = document.getElementById('enableWF').checked;
    document.getElementById('wfSettings').style.display = enabled ? 'block' : 'none';
    
    if (enabled) {
        calculateEstimates();
    }
}

function calculateEstimates() {
    // Calculate estimated number of windows, time, etc.
    // Based on form values
    
    const wfZone = parseInt(document.getElementById('wfZonePct').value);
    const isPct = parseInt(document.getElementById('isPct').value);
    const oosPct = parseInt(document.getElementById('oosPct').value);
    
    // Show estimates in UI
    // ...
}

// Update sliders in real-time
document.getElementById('wfZonePct').oninput = function() {
    document.getElementById('wfZoneValue').textContent = this.value + '%';
    document.getElementById('forwardValue').textContent = (100 - this.value) + '%';
    document.getElementById('forwardPct').value = 100 - this.value;
    calculateEstimates();
};

// Similar for other sliders...
</script>
```

### Results Display

Add new results view for Walk-Forward:

```html
<div id="wfResults" style="display: none;">
    <h3>Walk-Forward Results</h3>
    
    <!-- Summary Cards -->
    <div class="summary-cards">
        <div class="card">
            <h4>Best Parameter Set</h4>
            <p id="bestParamHash"></p>
            <p>Forward Profit: <span id="bestForwardProfit"></span></p>
            <p>Score: <span id="bestScore"></span></p>
        </div>
        
        <div class="card">
            <h4>Overall Performance</h4>
            <p>OOS Consistency: <span id="oosConsistency"></span></p>
            <p>Median OOS Profit: <span id="medianOosProfit"></span></p>
        </div>
    </div>
    
    <!-- Top 10 Ranking Table -->
    <table id="wfRankingTable">
        <thead>
            <tr>
                <th>Rank</th>
                <th>Param Hash</th>
                <th>Forward Profit</th>
                <th>Avg OOS Profit</th>
                <th>OOS Win Rate</th>
                <th>Score</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody id="wfRankingBody">
            <!-- Populated by JavaScript -->
        </tbody>
    </table>
    
    <!-- Window Details (collapsible) -->
    <div class="window-details">
        <h4>Window-by-Window Results</h4>
        <div id="windowAccordion">
            <!-- Each window as collapsible section -->
        </div>
    </div>
    
    <!-- Download Button -->
    <button onclick="downloadWFResults()">Download Full Report (CSV)</button>
</div>
```

---

## Validation & Testing

### Unit Tests to Write

1. **Test data splitting:**
   - Rolling mode produces correct windows
   - Anchored mode produces correct windows
   - Gap is correctly applied
   - Forward reserve is correctly excluded

2. **Test warmup calculation:**
   - Warmup is sufficient for max indicator period
   - Warning when warmup is less than recommended

3. **Test CV fold creation:**
   - TimeSeriesSplit produces correct folds
   - Gap between train/test in CV is applied
   - Minimum fold size is enforced

4. **Test filtering:**
   - Negative OOS profits are filtered
   - Excessive degradation is filtered
   - Insufficient trades are filtered

5. **Test aggregation:**
   - Similar parameter sets are grouped correctly
   - OOS metrics are aggregated correctly
   - Win rate calculation is correct

### Integration Tests

1. **End-to-end WF run:**
   - Load sample data
   - Run complete WF analysis
   - Verify results structure
   - Check CSV export

2. **UI integration:**
   - Form submission works
   - Results display correctly
   - Download functionality works

---

## Implementation Checklist

### Phase 1: Core Engine
- [ ] Create `walkforward_engine.py` with all classes
- [ ] Implement data splitting (rolling and anchored)
- [ ] Implement warmup calculation and validation
- [ ] Implement window processing loop
- [ ] Implement aggregation logic
- [ ] Implement forward test
- [ ] Implement final ranking

### Phase 2: CV Integration
- [ ] Modify `optuna_engine.py` to support CV mode
- [ ] Implement TimeSeriesSplit fold creation
- [ ] Implement CV objective function
- [ ] Test CV mode with sample data

### Phase 3: Server Integration
- [ ] Add `/api/walkforward` endpoint
- [ ] Add config parsing for WF params
- [ ] Add progress tracking (optional)
- [ ] Add CSV export functionality
- [ ] Test API with Postman/curl

### Phase 4: UI Integration
- [ ] Add WF section to HTML form
- [ ] Add JavaScript for form interactions
- [ ] Add sliders and validation
- [ ] Add results display section
- [ ] Add download functionality
- [ ] Test full workflow in browser

### Phase 5: Testing & Refinement
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Test with real data
- [ ] Optimize performance
- [ ] Add logging
- [ ] Add error handling
- [ ] Write documentation

---

## Expected Behavior

### User Workflow

1. User uploads CSV with 1-2 years of data
2. User enables "Walk-Forward Analysis" checkbox
3. User selects mode (Rolling recommended)
4. User adjusts sliders for data allocation (or uses defaults)
5. User sees estimated number of windows and time
6. User sees data requirements validation (warmup sufficient or not)
7. User clicks "Run Walk-Forward Optimization"
8. Progress bar shows:
   - Window 1/6: Optimizing...
   - Window 1/6: Validating...
   - Window 2/6: Optimizing...
   - ...
   - Aggregating results...
   - Running forward test...
9. Results display shows:
   - Top 10 parameter sets ranked by forward performance
   - Overall OOS consistency metrics
   - Window-by-window breakdown (collapsible)
   - Download button for full CSV report
10. User downloads CSV with complete results
11. User can click "Use This" to export specific parameter set

### CSV Report Structure

```csv
=== WALK-FORWARD ANALYSIS SUMMARY ===
Mode,rolling
Total Windows,6
WF Zone,80%
Forward Reserve,20%
Gap,2 bars

=== FINAL RANKING ===
Rank,Hash,Forward_Profit%,Forward_DD%,Avg_OOS_Profit%,OOS_WinRate%,Score,Status
1,abc12345,+12.8,-11.3,+15.2,100.0,87.3,PASSED
2,def67890,+11.2,-13.5,+14.8,100.0,85.1,PASSED
...

=== DETAILED RESULTS FOR #1 ===
Window,Type,Start,End,Profit%,MaxDD%,Trades,Sharpe
1,IS,0,16800,+18.5,-8.2,45,2.1
1,OOS,16802,22400,+16.3,-9.1,12,1.9
2,IS,5600,22400,+19.1,-7.8,52,2.3
2,OOS,22402,28000,+14.8,-10.2,15,1.7
...
FORWARD,FORWARD,28000,35000,+12.8,-11.3,18,1.5

=== PARAMETERS FOR #1 ===
ma_type,EMA
ma_length,45
close_count_long,7
...
```

---

## Performance Considerations

### Time Complexity

**Without CV:**
- Single window: `O(N_trials × T_backtest)`
- Full WF: `O(N_windows × N_trials × T_backtest)`
- Example: 6 windows × 100 trials × 5 sec = 30 minutes

**With CV:**
- Single window: `O(N_trials × N_folds × T_backtest)`
- Full WF: `O(N_windows × N_trials × N_folds × T_backtest)`
- Example: 6 windows × 100 trials × 5 folds × 5 sec = 2.5 hours

### Optimization Tips

1. **Parallel processing:** Run multiple trials in parallel (if CPU allows)
2. **Caching:** Cache indicator calculations that don't change
3. **Early stopping:** Use Optuna pruning to skip bad trials early
4. **Reduce trials:** For testing, use fewer trials (50 instead of 300)
5. **Progress feedback:** Show real-time progress to keep user informed

---

## Edge Cases to Handle

1. **Insufficient data:**
   - Less than 2 windows possible
   - Warmup period larger than available data
   - Solution: Show clear error message with requirements

2. **No profitable params:**
   - All params fail filters on all windows
   - Solution: Relax filters and show warning

3. **CV impossible:**
   - IS too small for 5 folds
   - Solution: Automatically disable CV and warn user

4. **Forward test all negative:**
   - All Top K fail forward test
   - Solution: Still show results, but mark as "Strategy not robust"

5. **Very large search space:**
   - Estimated time > 12 hours
   - Solution: Warn user, suggest reducing trials or using Grid search

---

## Documentation

Add to README:

```markdown
## Walk-Forward Analysis

### Overview
Walk-Forward Analysis (WFA) is a method to validate strategy robustness by:
1. Splitting data into multiple training (IS) and testing (OOS) windows
2. Optimizing parameters on each IS window
3. Validating on corresponding OOS window
4. Testing final candidates on unseen Forward Reserve data

This prevents overfitting and provides realistic performance expectations.

### Usage

1. **Enable WFA:** Check "Enable Walk-Forward Analysis" in optimization form
2. **Configure:** Adjust settings or use recommended defaults
   - Mode: Rolling (for crypto) or Anchored
   - Data allocation: 80% WF / 20% Forward
   - Window split: 70% IS / 30% OOS
3. **Run:** Click "Run Walk-Forward Optimization"
4. **Review:** Examine top-ranked parameter sets
5. **Download:** Get complete CSV report

### Recommended Settings for Crypto (15min TF)

- **Rolling mode** (adapts to market changes)
- **WF Zone:** 80% (leaves 20% for forward test)
- **IS/OOS:** 70%/30% (sufficient data for both)
- **Gap:** 2-3 bars (prevents look-ahead)
- **CV:** Auto mode (enables for large search spaces)
- **Min OOS Win Rate:** 70% (consistency requirement)

### Interpreting Results

- **Forward Profit:** Most important metric - real performance on unseen data
- **OOS Win Rate:** % of windows where params were profitable
- **Degradation:** Performance drop from IS to OOS (lower is better)
- **Status:**
  - PASSED: Forward profit positive and comparable to OOS
  - WEAK: Forward profit positive but much lower than OOS
  - FAILED: Forward profit negative

### Example Timeline

```
[Warmup][──IS──][G][OOS] [Warmup][──IS──][G][OOS] ... [===FORWARD===]
 Window 1               Window 2                      Final Test (20%)
```

- Warmup: 1-2 months (indicator initialization)
- IS: 3 months (optimization)
- Gap: 2 bars (safety margin)
- OOS: 1 month (validation)
- Forward: Held out for final test (never used in optimization)
```

---

## Final Notes

### Key Design Decisions

1. **Warmup handled separately:** User provides extra data before IS, not enlarging first CV fold
2. **CV is optional:** Auto-mode decides based on search space and data size
3. **Forward test is mandatory:** Always reserve 15-25% for final validation
4. **Median for aggregation:** More robust to outliers than mean
5. **Forward performance is king:** Final ranking prioritizes forward test results

### Extensibility

Future enhancements (not in MVP):
- Ensemble of top-K parameter sets
- PBO (Probability of Backtest Overfitting) calculation
- Deflated Sharpe Ratio
- Parameter stability visualization
- Regime detection and adaptive window sizing
- WebSocket for real-time progress updates
- Distributed computation across multiple machines

### Success Criteria

Implementation is successful when:
1. User can run WF analysis through UI
2. Results show clear improvement over single-period optimization
3. Forward test results are realistic (not overly optimistic)
4. Top-ranked parameters are stable across windows
5. CSV export contains all necessary information for analysis
6. Execution time is reasonable (< 4 hours for typical setup)

---

## Questions to Consider During Implementation

1. How to handle warmup in Rolling mode when window shifts?
   - Answer: Warmup shifts with window, using appropriate history

2. Should we allow overlapping windows?
   - Answer: Step size controls this (100% = no overlap, 50% = 50% overlap)

3. What if a parameter set appears in only 1 window?
   - Answer: Still include in aggregation, but lower window_count hurts its score

4. How to handle ties in final ranking?
   - Answer: Use secondary criteria (OOS consistency, then degradation)

5. Should we cache backtest results?
   - Answer: Yes, if same params tested on same period multiple times

6. What about parameter types (string vs numeric)?
   - Answer: Hash function handles all types via JSON serialization

7. Should CV gap be user-configurable?
   - Answer: Yes, but default to 0 (same as main gap)

8. How granular should progress updates be?
   - Answer: Per window, plus stages (optimization, validation, aggregation)

---

## Summary

This specification provides:
- Complete implementation of Walk-Forward Analysis
- Two modes: Rolling and Anchored
- Optional Cross-Validation inside IS
- Mandatory Forward Test reserve
- Warmup period handling
- Integration with existing Optuna optimizer
- Full UI/UX design
- Comprehensive filtering and ranking
- CSV export functionality

The design prioritizes:
- **Robustness:** Multiple validation layers (IS, OOS, Forward)
- **Usability:** Sensible defaults, auto-mode, clear UI
- **Flexibility:** User can tune all parameters
- **Performance:** Optional CV, caching, parallel processing
- **Transparency:** Detailed results showing per-window performance

This should give you everything needed to implement a production-ready Walk-Forward Analysis system.
