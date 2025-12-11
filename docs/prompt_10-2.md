# Phase 10: Full Frontend Separation - Part 2

## Continuation of Agent Instructions for GPT 5.1 Codex

---

## Step 4 (Continued): Extract JavaScript into Modules

### 4.5: Create `src/ui/static/js/ui-handlers.js`

**Content:** Event handlers, form state management, and submission logic.

```javascript
/**
 * UI event handlers and form management.
 * Dependencies: utils.js, api.js, strategy-config.js, presets.js
 */

// Score configuration constants
const SCORE_METRICS = ['romad', 'sharpe', 'pf', 'ulcer', 'recovery', 'consistency'];
const SCORE_DEFAULT_THRESHOLD = 60;
const SCORE_DEFAULT_WEIGHTS = {
  romad: 0.25,
  sharpe: 0.20,
  pf: 0.20,
  ulcer: 0.15,
  recovery: 0.10,
  consistency: 0.10
};
const SCORE_DEFAULT_ENABLED = {
  romad: true,
  sharpe: true,
  pf: true,
  ulcer: true,
  recovery: true,
  consistency: true
};
const SCORE_DEFAULT_INVERT = {
  ulcer: true
};

/**
 * Toggle Walk-Forward settings visibility.
 */
function toggleWFSettings() {
  const wfToggle = document.getElementById('enableWF');
  const wfSettings = document.getElementById('wfSettings');
  if (!wfToggle || !wfSettings) {
    return;
  }
  wfSettings.style.display = wfToggle.checked ? 'block' : 'none';
}

// Make globally available
window.toggleWFSettings = toggleWFSettings;

/**
 * Sync budget mode radio inputs.
 */
function syncBudgetInputs() {
  const budgetModeRadios = document.querySelectorAll('input[name="budgetMode"]');
  const optunaTrials = document.getElementById('optunaTrials');
  const optunaTimeLimit = document.getElementById('optunaTimeLimit');
  const optunaConvergence = document.getElementById('optunaConvergence');

  if (!budgetModeRadios || !budgetModeRadios.length) {
    return;
  }

  const selected = Array.from(budgetModeRadios).find((radio) => radio.checked)?.value || 'trials';

  if (optunaTrials) optunaTrials.disabled = selected !== 'trials';
  if (optunaTimeLimit) optunaTimeLimit.disabled = selected !== 'time';
  if (optunaConvergence) optunaConvergence.disabled = selected !== 'convergence';
}

// Filter elements helpers
function getMinProfitElements() {
  return {
    checkbox: document.getElementById('minProfitFilter'),
    input: document.getElementById('minProfitThreshold'),
    group: document.getElementById('minProfitFilterGroup')
  };
}

function getScoreElements() {
  return {
    checkbox: document.getElementById('scoreFilter'),
    input: document.getElementById('scoreThreshold'),
    group: document.getElementById('scoreFilterGroup')
  };
}

function syncMinProfitFilterUI() {
  const { checkbox, input, group } = getMinProfitElements();
  if (!checkbox || !input) return;

  const isChecked = Boolean(checkbox.checked);
  input.disabled = !isChecked;
  if (group) {
    group.classList.toggle('active', isChecked);
  }
}

function syncScoreFilterUI() {
  const { checkbox, input, group } = getScoreElements();
  if (!checkbox || !input) return;

  const isChecked = Boolean(checkbox.checked);
  input.disabled = !isChecked;
  if (group) {
    group.classList.toggle('active', isChecked);
  }
}

function readScoreUIState() {
  const { checkbox, input } = getScoreElements();
  const weights = {};
  const enabled = {};

  SCORE_METRICS.forEach((metric) => {
    const metricCheckbox = document.getElementById(`metric-${metric}`);
    const weightInput = document.getElementById(`weight-${metric}`);
    enabled[metric] = Boolean(metricCheckbox && metricCheckbox.checked);
    const rawWeight = weightInput ? Number(weightInput.value) : NaN;
    const fallback = SCORE_DEFAULT_WEIGHTS[metric] ?? 0;
    const parsedWeight = Number.isFinite(rawWeight) ? rawWeight : fallback;
    weights[metric] = Math.min(1, Math.max(0, parsedWeight));
  });

  const invertCheckbox = document.getElementById('invert-ulcer');
  const invert = {
    ulcer: Boolean(invertCheckbox && invertCheckbox.checked)
  };

  const thresholdRaw = input ? Number(input.value) : NaN;
  const threshold = Number.isFinite(thresholdRaw)
    ? Math.min(100, Math.max(0, thresholdRaw))
    : SCORE_DEFAULT_THRESHOLD;

  return {
    scoreFilterEnabled: Boolean(checkbox && checkbox.checked),
    scoreThreshold: threshold,
    scoreWeights: weights,
    scoreEnabledMetrics: enabled,
    scoreInvertMetrics: invert
  };
}

function applyScoreSettings(settings = {}) {
  const filterCheckbox = document.getElementById('scoreFilter');
  const thresholdInput = document.getElementById('scoreThreshold');

  const effectiveWeights = { ...SCORE_DEFAULT_WEIGHTS, ...(settings.scoreWeights || {}) };
  const effectiveEnabled = { ...SCORE_DEFAULT_ENABLED, ...(settings.scoreEnabledMetrics || {}) };
  const effectiveInvert = { ...SCORE_DEFAULT_INVERT, ...(settings.scoreInvertMetrics || {}) };

  const filterEnabled = Object.prototype.hasOwnProperty.call(settings, 'scoreFilterEnabled')
    ? Boolean(settings.scoreFilterEnabled)
    : Boolean(window.defaults.scoreFilterEnabled);
  const thresholdValue = Object.prototype.hasOwnProperty.call(settings, 'scoreThreshold')
    ? Number(settings.scoreThreshold)
    : Number(window.defaults.scoreThreshold);

  if (filterCheckbox) {
    filterCheckbox.checked = filterEnabled;
  }
  if (thresholdInput) {
    const safeValue = Number.isFinite(thresholdValue)
      ? Math.min(100, Math.max(0, thresholdValue))
      : SCORE_DEFAULT_THRESHOLD;
    thresholdInput.value = safeValue;
  }

  SCORE_METRICS.forEach((metric) => {
    const metricCheckbox = document.getElementById(`metric-${metric}`);
    const weightInput = document.getElementById(`weight-${metric}`);
    if (metricCheckbox) {
      metricCheckbox.checked = Boolean(effectiveEnabled[metric]);
    }
    if (weightInput) {
      const weightValue = Number.isFinite(Number(effectiveWeights[metric]))
        ? Math.min(1, Math.max(0, Number(effectiveWeights[metric])))
        : SCORE_DEFAULT_WEIGHTS[metric];
      weightInput.value = weightValue;
    }
  });

  const invertCheckbox = document.getElementById('invert-ulcer');
  if (invertCheckbox) {
    invertCheckbox.checked = Boolean(effectiveInvert.ulcer);
  }

  syncScoreFilterUI();
  updateScoreFormulaPreview();
}

function updateScoreFormulaPreview() {
  const previewEl = document.getElementById('formulaPreview');
  if (!previewEl) return;

  const state = readScoreUIState();
  const enabledWeights = SCORE_METRICS
    .filter((metric) => state.scoreEnabledMetrics[metric] && state.scoreWeights[metric] > 0)
    .map((metric) => {
      const labelMap = {
        romad: 'RoMaD',
        sharpe: 'Sharpe Ratio',
        pf: 'Profit Factor',
        ulcer: 'Ulcer Index',
        recovery: 'Recovery Factor',
        consistency: 'Consistency Score'
      };
      const label = labelMap[metric] || metric;
      const weight = state.scoreWeights[metric];
      return `${weight.toFixed(2)}×${label}`;
    });

  if (!enabledWeights.length) {
    previewEl.textContent = 'Score disabled (no metrics enabled).';
    return;
  }
  previewEl.textContent = `Score = ${enabledWeights.join(' + ')}`;
}

function collectScoreConfig() {
  const state = readScoreUIState();
  const config = {
    filter_enabled: state.scoreFilterEnabled,
    min_score_threshold: state.scoreThreshold,
    weights: {},
    enabled_metrics: {},
    invert_metrics: {},
    normalization_method: 'percentile'
  };

  SCORE_METRICS.forEach((metric) => {
    config.enabled_metrics[metric] = Boolean(state.scoreEnabledMetrics[metric]);
    const normalizedWeight = Math.min(1, Math.max(0, state.scoreWeights[metric]));
    config.weights[metric] = config.enabled_metrics[metric] ? normalizedWeight : 0;
  });

  if (state.scoreInvertMetrics.ulcer) {
    config.invert_metrics.ulcer = true;
  }

  return config;
}

// Dynamic backtest parameter handling
function collectDynamicBacktestParams() {
  const params = {};
  const container = document.getElementById('backtestParamsContent');

  if (!container || !window.currentStrategyConfig || !window.currentStrategyConfig.parameters) {
    return params;
  }

  Object.entries(window.currentStrategyConfig.parameters).forEach(([name, def]) => {
    const input = document.getElementById(`backtest_${name}`);
    if (!input) return;

    if (input.type === 'checkbox') {
      params[name] = Boolean(input.checked);
    } else if (input.type === 'number') {
      const value = parseFloat(input.value);
      const fallback = Object.prototype.hasOwnProperty.call(def, 'default') ? def.default : 0;
      params[name] = Number.isFinite(value) ? value : fallback;
    } else {
      params[name] = input.value;
    }
  });

  return params;
}

function applyDynamicBacktestParams(params) {
  if (!params || typeof params !== 'object') return;
  if (!window.currentStrategyConfig || !window.currentStrategyConfig.parameters) return;

  Object.entries(window.currentStrategyConfig.parameters).forEach(([name, def]) => {
    if (!Object.prototype.hasOwnProperty.call(params, name)) return;

    const input = document.getElementById(`backtest_${name}`);
    if (!input) return;

    const value = params[name];

    if (input.type === 'checkbox') {
      input.checked = Boolean(value);
    } else if (input.type === 'number') {
      input.value = value;
    } else if (input.tagName === 'SELECT') {
      input.value = value;
    } else {
      input.value = value;
    }
  });
}

function gatherFormState() {
  const start = composeDateTime(
    document.getElementById('startDate').value,
    document.getElementById('startTime').value
  );
  const end = composeDateTime(
    document.getElementById('endDate').value,
    document.getElementById('endTime').value
  );

  const dynamicParams = collectDynamicBacktestParams();

  const payload = {
    ...dynamicParams,
    dateFilter: document.getElementById('dateFilter').checked,
    backtester: document.getElementById('backtester').checked,
    start,
    end
  };

  return { start, end, payload };
}

function getBacktestParamValue(paramName, paramDef = {}, dynamicParams = {}) {
  if (Object.prototype.hasOwnProperty.call(dynamicParams, paramName)) {
    return dynamicParams[paramName];
  }

  const input = document.getElementById(`backtest_${paramName}`);
  if (input) {
    if (input.type === 'checkbox') {
      return Boolean(input.checked);
    }
    if (input.type === 'number') {
      const value = Number(input.value);
      if (Number.isFinite(value)) return value;
    }
    return input.value;
  }

  if (Object.prototype.hasOwnProperty.call(paramDef, 'default')) {
    return paramDef.default;
  }

  return null;
}

function getWorkerProcessesValue() {
  const workerInput = document.getElementById('workerProcesses');
  let workerProcesses = window.defaults.workerProcesses;
  if (workerInput) {
    const rawValue = Number(workerInput.value);
    if (Number.isFinite(rawValue)) {
      workerProcesses = rawValue;
    }
  }
  return Math.round(Math.min(32, Math.max(1, workerProcesses)));
}

function validateOptimizerForm(config) {
  const params = config?.parameters || {};
  const errors = [];
  let enabledCount = 0;

  getOptimizerParamElements().forEach(({ name, checkbox, fromInput, toInput, stepInput, def }) => {
    const paramDef = def || params[name] || {};
    const paramType = paramDef.type || 'float';
    const label = paramDef.label || name;
    const enabled = Boolean(checkbox && checkbox.checked);

    if (!enabled) return;

    enabledCount += 1;

    if (paramType === 'select' || paramType === 'options') {
      const selectedOptions = Array.from(
        document.querySelectorAll(
          `input.select-option-checkbox[data-param-name="${name}"]:not([data-option-value="__ALL__"])`
        )
      )
        .filter((cb) => cb.checked)
        .map((cb) => cb.dataset.optionValue);

      if (!selectedOptions.length) {
        errors.push(`${label}: select at least one option to optimize.`);
      }
      return;
    }

    if (paramType === 'bool') return;

    const fromVal = Number(fromInput?.value);
    const toVal = Number(toInput?.value);
    const stepVal = Number(stepInput?.value);

    if (!Number.isFinite(fromVal) || !Number.isFinite(toVal) || !Number.isFinite(stepVal)) {
      errors.push(`${label}: enter valid numeric values for range and step.`);
      return;
    }

    if (stepVal <= 0) {
      errors.push(`${label}: step must be greater than 0.`);
    }
    if (fromVal >= toVal) {
      errors.push(`${label}: from must be less than to.`);
    }

    const minBound = paramDef.optimize?.min ?? paramDef.min;
    const maxBound = paramDef.optimize?.max ?? paramDef.max;

    if (minBound !== undefined && fromVal < minBound) {
      errors.push(`${label}: from below minimum (${minBound}).`);
    }
    if (maxBound !== undefined && toVal > maxBound) {
      errors.push(`${label}: to above maximum (${maxBound}).`);
    }
  });

  if (enabledCount === 0) {
    errors.push('Enable at least one parameter to optimize.');
  }

  return errors;
}

function collectOptimizerParams() {
  const ranges = {};
  const params = window.currentStrategyConfig?.parameters || {};

  Object.entries(params).forEach(([paramName, paramDef]) => {
    const checkbox = document.getElementById(`opt-${paramName}`);
    if (!checkbox || !checkbox.checked) return;

    const paramType = paramDef.type || 'float';

    if (paramType === 'select' || paramType === 'options') {
      const selectedOptions = [];
      const optionCheckboxes = document.querySelectorAll(
        `input.select-option-checkbox[data-param-name="${paramName}"]:not([data-option-value="__ALL__"])`
      );

      optionCheckboxes.forEach((cb) => {
        if (cb.checked) {
          selectedOptions.push(cb.dataset.optionValue);
        }
      });

      if (selectedOptions.length > 0) {
        ranges[paramName] = {
          type: 'select',
          values: selectedOptions
        };
      }
      return;
    }

    const fromInput = document.getElementById(`opt-${paramName}-from`);
    const toInput = document.getElementById(`opt-${paramName}-to`);
    const stepInput = document.getElementById(`opt-${paramName}-step`);

    if (fromInput && toInput && stepInput) {
      const fromValue = parseFloat(fromInput.value);
      const toValue = parseFloat(toInput.value);
      const stepValue = parseFloat(stepInput.value);

      if (isNaN(fromValue) || isNaN(toValue) || isNaN(stepValue)) {
        console.warn(`Invalid values for parameter ${paramName}, skipping`);
        return;
      }

      if (fromValue >= toValue) {
        console.warn(`From >= To for parameter ${paramName}, skipping`);
        return;
      }

      if (stepValue <= 0) {
        console.warn(`Invalid step for parameter ${paramName}, skipping`);
        return;
      }

      ranges[paramName] = [fromValue, toValue, stepValue];
    }
  });

  return ranges;
}

function buildOptimizationConfig(state) {
  const enabledParams = {};
  const paramRanges = {};
  const paramTypes = {};
  const fixedParams = {
    dateFilter: state.payload.dateFilter,
    backtester: state.payload.backtester,
    start: state.start,
    end: state.end
  };

  const { checkbox: minProfitCheckbox, input: minProfitInput } = getMinProfitElements();
  const filterEnabled = Boolean(minProfitCheckbox && minProfitCheckbox.checked);
  let minProfitThreshold = 0;
  if (minProfitInput) {
    const parsedValue = Number(minProfitInput.value);
    if (Number.isFinite(parsedValue)) {
      minProfitThreshold = Math.min(99000, Math.max(0, parsedValue));
    }
  }

  const dynamicParams = collectDynamicBacktestParams();
  const paramsDef = window.currentStrategyConfig?.parameters || {};
  const optimizableNames = new Set();

  Object.entries(paramsDef).forEach(([name, def]) => {
    paramTypes[name] = def.type || 'float';
  });

  getOptimizerParamElements().forEach(({ name, checkbox, fromInput, toInput, stepInput, def }) => {
    optimizableNames.add(name);
    const paramDef = def || {};
    const paramType = paramDef.type || 'float';
    const isChecked = Boolean(checkbox && checkbox.checked);
    enabledParams[name] = isChecked;

    if (isChecked) {
      if (paramType === 'select' || paramType === 'options') {
        const selectedOptions = Array.from(
          document.querySelectorAll(
            `input.select-option-checkbox[data-param-name="${name}"]:not([data-option-value="__ALL__"])`
          )
        )
          .filter((cb) => cb.checked)
          .map((cb) => cb.dataset.optionValue);

        if (selectedOptions.length > 0) {
          paramRanges[name] = {
            type: 'select',
            values: selectedOptions
          };
        }
      } else if (paramType === 'bool') {
        // Boolean params require no range metadata
      } else if (fromInput && toInput && stepInput) {
        const fromValue = Number(fromInput.value);
        const toValue = Number(toInput.value);
        const stepValue = Math.abs(Number(stepInput.value));
        if (
          Number.isFinite(fromValue) &&
          Number.isFinite(toValue) &&
          Number.isFinite(stepValue) &&
          stepValue > 0 &&
          fromValue < toValue
        ) {
          paramRanges[name] = [fromValue, toValue, stepValue];
        }
      }
    } else {
      fixedParams[name] = getBacktestParamValue(name, paramDef, dynamicParams);
    }
  });

  Object.entries(paramsDef).forEach(([name, def]) => {
    if (optimizableNames.has(name)) return;
    fixedParams[name] = getBacktestParamValue(name, def, dynamicParams);
  });

  const workerProcesses = getWorkerProcessesValue();
  const riskPerTrade = getBacktestParamValue('riskPerTrade', paramsDef.riskPerTrade, dynamicParams) || 0;
  const contractSize = getBacktestParamValue('contractSize', paramsDef.contractSize, dynamicParams) || 0;
  const commissionRate = getBacktestParamValue('commissionPct', paramsDef.commissionPct, dynamicParams);

  return {
    enabled_params: enabledParams,
    param_ranges: paramRanges,
    fixed_params: fixedParams,
    param_types: paramTypes,
    risk_per_trade_pct: Number(riskPerTrade) || 0,
    contract_size: Number(contractSize) || 0,
    commission_rate: commissionRate !== undefined ? Number(commissionRate) || 0 : 0.0005,
    worker_processes: workerProcesses,
    filter_min_profit: filterEnabled,
    min_profit_threshold: minProfitThreshold,
    score_config: collectScoreConfig(),
    optimization_mode: 'optuna'
  };
}

function buildOptunaConfig(state) {
  const baseConfig = buildOptimizationConfig(state);
  const budgetModeRadios = document.querySelectorAll('input[name="budgetMode"]');
  const optunaTrials = document.getElementById('optunaTrials');
  const optunaTimeLimit = document.getElementById('optunaTimeLimit');
  const optunaConvergence = document.getElementById('optunaConvergence');
  const optunaTarget = document.getElementById('optunaTarget');
  const optunaPruning = document.getElementById('optunaPruning');
  const optunaSampler = document.getElementById('optunaSampler');
  const optunaPruner = document.getElementById('optunaPruner');
  const optunaWarmupTrials = document.getElementById('optunaWarmupTrials');
  const optunaSaveStudy = document.getElementById('optunaSaveStudy');

  const selectedBudget = Array.from(budgetModeRadios).find((radio) => radio.checked)?.value || 'trials';
  const trialsValue = Number(optunaTrials?.value);
  const timeLimitMinutes = Number(optunaTimeLimit?.value);
  const convergenceValue = Number(optunaConvergence?.value);
  const warmupValue = Number(optunaWarmupTrials?.value);

  const normalizedTrials = Number.isFinite(trialsValue) ? Math.max(10, Math.min(10000, Math.round(trialsValue))) : 500;
  const normalizedMinutes = Number.isFinite(timeLimitMinutes) ? Math.max(1, Math.round(timeLimitMinutes)) : 60;
  const normalizedConvergence = Number.isFinite(convergenceValue)
    ? Math.max(10, Math.min(500, Math.round(convergenceValue)))
    : 50;
  const normalizedWarmup = Number.isFinite(warmupValue) ? Math.max(0, Math.min(50000, Math.round(warmupValue))) : 20;

  return {
    ...baseConfig,
    optimization_mode: 'optuna',
    optuna_target: optunaTarget ? optunaTarget.value : 'score',
    optuna_budget_mode: selectedBudget,
    optuna_n_trials: normalizedTrials,
    optuna_time_limit: normalizedMinutes * 60,
    optuna_convergence: normalizedConvergence,
    optuna_enable_pruning: Boolean(optunaPruning && optunaPruning.checked),
    optuna_sampler: optunaSampler ? optunaSampler.value : 'tpe',
    optuna_pruner: optunaPruner ? optunaPruner.value : 'median',
    optuna_warmup_trials: normalizedWarmup,
    optuna_save_study: Boolean(optunaSaveStudy && optunaSaveStudy.checked)
  };
}

// Optimizer checkbox binding
let bindOptimizerInputs;
let handleOptimizerCheckboxChange;

bindOptimizerInputs = function() {
  const paramCheckboxes = document.querySelectorAll('.opt-param-toggle');

  paramCheckboxes.forEach((checkbox) => {
    checkbox.removeEventListener('change', handleOptimizerCheckboxChange);
    checkbox.addEventListener('change', handleOptimizerCheckboxChange);
    handleOptimizerCheckboxChange.call(checkbox);
  });
};

handleOptimizerCheckboxChange = function() {
  const paramName = this.dataset.paramName || this.id.replace('opt-', '');
  const row = this.closest('.opt-row');
  const fromInput = document.getElementById(`opt-${paramName}-from`);
  const toInput = document.getElementById(`opt-${paramName}-to`);
  const stepInput = document.getElementById(`opt-${paramName}-step`);
  const selectOptions = row
    ? row.querySelectorAll(`input.select-option-checkbox[data-param-name="${paramName}"]`)
    : document.querySelectorAll(`input.select-option-checkbox[data-param-name="${paramName}"]`);

  const disabled = !this.checked;

  if (fromInput) fromInput.disabled = disabled;
  if (toInput) toInput.disabled = disabled;
  if (stepInput) stepInput.disabled = disabled;
  if (selectOptions && selectOptions.length) {
    selectOptions.forEach((optionCheckbox) => {
      optionCheckbox.disabled = disabled;
    });
  }

  if (row) {
    if (disabled) {
      row.classList.add('disabled');
    } else {
      row.classList.remove('disabled');
    }
  }
};

// Make globally available
window.bindOptimizerInputs = bindOptimizerInputs;
window.handleOptimizerCheckboxChange = handleOptimizerCheckboxChange;

function bindMinProfitFilterControl() {
  const { checkbox, input } = getMinProfitElements();
  if (!checkbox || !input) return;

  checkbox.addEventListener('change', syncMinProfitFilterUI);
  syncMinProfitFilterUI();
}

function bindScoreControls() {
  const { checkbox, input } = getScoreElements();
  if (checkbox) {
    checkbox.addEventListener('change', () => {
      syncScoreFilterUI();
      updateScoreFormulaPreview();
    });
  }
  if (input) {
    input.addEventListener('input', updateScoreFormulaPreview);
  }

  SCORE_METRICS.forEach((metric) => {
    const metricCheckbox = document.getElementById(`metric-${metric}`);
    const weightInput = document.getElementById(`weight-${metric}`);
    if (metricCheckbox) {
      metricCheckbox.addEventListener('change', updateScoreFormulaPreview);
    }
    if (weightInput) {
      weightInput.addEventListener('input', updateScoreFormulaPreview);
    }
  });

  const invertCheckbox = document.getElementById('invert-ulcer');
  if (invertCheckbox) {
    invertCheckbox.addEventListener('change', updateScoreFormulaPreview);
  }

  const configButton = document.getElementById('scoreConfigBtn');
  const collapsible = document.getElementById('scoreConfigCollapsible');
  if (configButton && collapsible) {
    configButton.addEventListener('click', () => {
      const isOpen = collapsible.classList.toggle('open');
      configButton.setAttribute('aria-expanded', String(isOpen));
    });
  }

  const resetButton = document.getElementById('resetScoreBtn');
  if (resetButton) {
    resetButton.addEventListener('click', () => {
      applyScoreSettings({
        scoreFilterEnabled: false,
        scoreThreshold: SCORE_DEFAULT_THRESHOLD,
        scoreWeights: clonePreset(SCORE_DEFAULT_WEIGHTS),
        scoreEnabledMetrics: clonePreset(SCORE_DEFAULT_ENABLED),
        scoreInvertMetrics: clonePreset(SCORE_DEFAULT_INVERT)
      });
      updateScoreFormulaPreview();
    });
  }

  syncScoreFilterUI();
  updateScoreFormulaPreview();
}

// Walk-Forward results display
function clearWFResults() {
  const wfResultsContainer = document.getElementById('wfResults');
  const wfSummaryEl = document.getElementById('wfSummary');
  const wfTableBody = document.getElementById('wfTableBody');
  const wfStatusEl = document.getElementById('wfStatus');

  if (wfResultsContainer) wfResultsContainer.style.display = 'none';
  if (wfSummaryEl) wfSummaryEl.textContent = '';
  if (wfTableBody) wfTableBody.innerHTML = '';
  if (wfStatusEl) wfStatusEl.textContent = '';
}

function displayWFResults(data) {
  const wfResultsContainer = document.getElementById('wfResults');
  const wfSummaryEl = document.getElementById('wfSummary');
  const wfTableBody = document.getElementById('wfTableBody');
  const wfStatusEl = document.getElementById('wfStatus');

  if (!wfResultsContainer || !wfSummaryEl || !wfTableBody || !wfStatusEl) return;

  wfResultsContainer.style.display = 'block';
  wfStatusEl.textContent = '';

  const summary = data.summary || {};
  const totalWindowsValue = Number(summary.total_windows);
  const totalWindows = Number.isFinite(totalWindowsValue) ? totalWindowsValue : 0;
  const topParamId = summary.top_param_id || 'N/A';
  const topAvgValue = Number(summary.top_avg_oos_profit);
  const topAvgProfit = Number.isFinite(topAvgValue) ? topAvgValue : 0;

  wfSummaryEl.innerHTML = `
    <strong>Summary:</strong><br>
    Total Windows: ${totalWindows}<br>
    Best Parameter Set: ${topParamId}<br>
    Best Avg OOS Profit: ${topAvgProfit.toFixed(2)}%
  `;

  wfTableBody.innerHTML = '';
  (data.top10 || []).forEach((row) => {
    const avgValue = Number(row.avg_oos_profit);
    const winValue = Number(row.oos_win_rate);
    const forwardValue = row.forward_profit === null || row.forward_profit === undefined
      ? null
      : Number(row.forward_profit);
    const tr = document.createElement('tr');
    const avgOos = Number.isFinite(avgValue) ? avgValue.toFixed(2) : row.avg_oos_profit;
    const winRate = Number.isFinite(winValue) ? winValue.toFixed(1) : row.oos_win_rate;
    const forward = forwardValue === null || forwardValue === undefined || Number.isNaN(forwardValue)
      ? 'N/A'
      : `${forwardValue.toFixed(2)}%`;
    tr.innerHTML = `
      <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">${row.rank}</td>
      <td style="padding: 10px; border: 1px solid #ddd;">${row.param_id}</td>
      <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">${row.appearances}</td>
      <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">${avgOos}%</td>
      <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">${winRate}%</td>
      <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">${forward}</td>
    `;
    wfTableBody.appendChild(tr);
  });

  if (data.csv_content) {
    window.setTimeout(() => {
      const blob = new Blob([data.csv_content], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = data.csv_filename || `wf_results_${new Date().getTime()}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }, 200);
  }
}
```

**Note:** The `runBacktest`, `submitOptimization`, and `runWalkForward` functions are very long. Include them in the same file, continuing after `displayWFResults`.

---

### 4.6: Create `src/ui/static/js/main.js`

**Content:** Application initialization and event binding.

```javascript
/**
 * Main application initialization.
 * Dependencies: utils.js, api.js, strategy-config.js, presets.js, ui-handlers.js
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Load strategies list
  await loadStrategiesList();

  // Initialize collapsibles
  const collapsibles = document.querySelectorAll('.collapsible');
  collapsibles.forEach((collapsible) => {
    const header = collapsible.querySelector('.collapsible-header');
    header.addEventListener('click', () => {
      collapsible.classList.toggle('open');
    });
  });

  // Initialize budget input sync
  const budgetModeRadios = document.querySelectorAll('input[name="budgetMode"]');
  budgetModeRadios.forEach((radio) => {
    radio.addEventListener('change', syncBudgetInputs);
  });
  syncBudgetInputs();

  // Initialize Walk-Forward settings
  toggleWFSettings();

  // Link to score config scroll
  const linkToScoreConfig = document.getElementById('linkToScoreConfig');
  if (linkToScoreConfig) {
    linkToScoreConfig.addEventListener('click', (event) => {
      event.preventDefault();
      const scoreConfigBtn = document.getElementById('scoreConfigBtn');
      const scoreConfigCollapsible = document.getElementById('scoreConfigCollapsible');
      if (scoreConfigBtn && scoreConfigCollapsible) {
        if (!scoreConfigCollapsible.classList.contains('open')) {
          scoreConfigCollapsible.classList.add('open');
        }
        scoreConfigBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
        scoreConfigCollapsible.style.outline = '3px solid #90caf9';
        window.setTimeout(() => {
          scoreConfigCollapsible.style.outline = '';
        }, 2000);
      }
    });
  }

  // CSV file input handling
  const csvFileInputEl = document.getElementById('csvFile');
  if (csvFileInputEl) {
    csvFileInputEl.addEventListener('change', () => {
      const files = Array.from(csvFileInputEl.files || []);
      if (files.length) {
        const firstFile = files[0];
        const derivedPath =
          (firstFile && (firstFile.path || firstFile.webkitRelativePath)) || '';
        const fallbackName = firstFile && firstFile.name ? firstFile.name : '';
        window.selectedCsvPath = (derivedPath || fallbackName || '').trim();
      } else {
        window.selectedCsvPath = '';
      }
      renderSelectedFiles(files);
    });
  }

  // Preset menu handlers
  const presetToggleEl = document.getElementById('presetToggle');
  const presetMenuEl = document.getElementById('presetMenu');
  const presetDropdownEl = document.getElementById('presetDropdown');
  const presetImportInput = document.getElementById('presetImportInput');

  if (presetToggleEl) {
    presetToggleEl.addEventListener('click', (event) => {
      event.stopPropagation();
      togglePresetMenu();
    });
  }

  if (presetMenuEl) {
    presetMenuEl.addEventListener('click', (event) => {
      event.stopPropagation();
      const actionButton = event.target.closest('.preset-action');
      if (!actionButton) return;

      const action = actionButton.dataset.action;
      if (action === 'apply-defaults') {
        handleApplyDefaults();
      } else if (action === 'save-as') {
        handleSaveAsPreset();
      } else if (action === 'save-defaults') {
        handleSaveDefaults();
      } else if (action === 'import') {
        if (presetImportInput) {
          presetImportInput.value = '';
          presetImportInput.click();
        }
      }
    });
  }

  if (presetImportInput) {
    presetImportInput.addEventListener('change', async (event) => {
      const file = event.target.files && event.target.files[0];
      if (!file) {
        presetImportInput.value = '';
        closePresetMenu();
        return;
      }
      try {
        const data = await importPresetFromCsvRequest(file);
        applyPresetValues(data?.values || {}, { clearResults: false });
        const appliedKeys = Array.from(new Set(data?.applied || []));
        const appliedLabels = appliedKeys.map((key) => formatPresetLabel(key));
        const message = appliedLabels.length
          ? `Imported parameters: ${appliedLabels.join(', ')}.`
          : 'CSV import did not change any settings.';
        showResultsMessage(message);
        clearErrorMessage();
      } catch (error) {
        showErrorMessage(error.message || 'Failed to import settings from CSV');
      } finally {
        presetImportInput.value = '';
        closePresetMenu();
      }
    });
  }

  // Close preset menu on outside click
  document.addEventListener('click', (event) => {
    if (
      presetDropdownEl &&
      presetDropdownEl.classList.contains('open') &&
      !presetDropdownEl.contains(event.target)
    ) {
      closePresetMenu();
    }
  });

  // Close preset menu on Escape
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closePresetMenu();
    }
  });

  // Cancel button
  const cancelBtn = document.getElementById('cancelBtn');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      const backtestForm = document.getElementById('backtestForm');
      if (backtestForm) backtestForm.reset();
      applyDefaults({ clearResults: true });
    });
  }

  // Form submissions
  const backtestForm = document.getElementById('backtestForm');
  if (backtestForm) {
    backtestForm.addEventListener('submit', runBacktest);
  }

  const optimizerForm = document.getElementById('optimizerForm');
  if (optimizerForm) {
    optimizerForm.addEventListener('submit', submitOptimization);
  }

  // Initialize controls
  bindOptimizerInputs();
  bindMinProfitFilterControl();
  bindScoreControls();

  // Initialize presets
  await initializePresets();
});

/**
 * Run backtest handler.
 * @param {Event} event - Submit event
 */
async function runBacktest(event) {
  event.preventDefault();
  const resultsEl = document.getElementById('results');
  const errorEl = document.getElementById('error');
  const fileInput = document.getElementById('csvFile');

  errorEl.style.display = 'none';
  resultsEl.classList.remove('ready');

  const selectedFiles = Array.from(fileInput.files || []);
  const primaryFile = selectedFiles.length ? selectedFiles[0] : null;

  if (!primaryFile && !window.selectedCsvPath) {
    errorEl.textContent = 'Please select a CSV data file or use a saved path.';
    errorEl.style.display = 'block';
    return;
  }

  const state = gatherFormState();
  if (!state.start || !state.end) {
    errorEl.textContent = 'Please fill in start and end dates.';
    errorEl.style.display = 'block';
    return;
  }

  if (!window.currentStrategyId) {
    errorEl.textContent = 'Please select a strategy before running.';
    errorEl.style.display = 'block';
    return;
  }

  resultsEl.textContent = 'Running calculation...';
  resultsEl.classList.add('loading');

  if (primaryFile) {
    renderSelectedFiles(selectedFiles);
  } else {
    renderSelectedFiles([]);
  }

  const formData = new FormData();
  formData.append('strategy', window.currentStrategyId);
  const warmupInput = document.getElementById('warmupBars');
  formData.append('warmupBars', warmupInput ? warmupInput.value : '1000');
  if (primaryFile) {
    formData.append('file', primaryFile, primaryFile.name);
  }
  if (window.selectedCsvPath) {
    formData.append('csvPath', window.selectedCsvPath);
  }
  formData.append('payload', JSON.stringify(state.payload));

  try {
    const data = await runBacktestRequest(formData);
    resultsEl.textContent = formatResultBlock(1, 1, state.payload, data);
    resultsEl.classList.remove('loading');
    resultsEl.classList.add('ready');
  } catch (err) {
    resultsEl.textContent = 'An error occurred.';
    resultsEl.classList.remove('loading');
    errorEl.textContent = err.message;
    errorEl.style.display = 'block';
  }
}

/**
 * Submit optimization handler.
 * @param {Event} event - Submit event
 */
async function submitOptimization(event) {
  event.preventDefault();
  const optimizerResultsEl = document.getElementById('optimizerResults');
  const progressContainer = document.getElementById('optimizerProgress');
  const optunaProgress = document.getElementById('optunaProgress');
  const optunaProgressFill = document.getElementById('optunaProgressFill');
  const optunaProgressText = document.getElementById('optunaProgressText');
  const optunaBestTrial = document.getElementById('optunaBestTrial');
  const optunaCurrentTrial = document.getElementById('optunaCurrentTrial');
  const optunaEta = document.getElementById('optunaEta');

  const fileInput = document.getElementById('csvFile');
  const fileList = fileInput ? Array.from(fileInput.files || []) : [];
  const sources = fileList.length ? fileList : (window.selectedCsvPath ? [{ path: window.selectedCsvPath }] : []);

  if (!sources.length) {
    optimizerResultsEl.textContent = 'Please select at least one CSV file or saved path.';
    optimizerResultsEl.classList.remove('ready');
    optimizerResultsEl.style.display = 'block';
    return;
  }

  const state = gatherFormState();

  if (!window.currentStrategyId) {
    optimizerResultsEl.textContent = 'Please select a strategy.';
    optimizerResultsEl.classList.remove('ready');
    optimizerResultsEl.style.display = 'block';
    return;
  }

  const validationErrors = validateOptimizerForm(window.currentStrategyConfig);
  if (validationErrors.length) {
    optimizerResultsEl.textContent = `Validation errors:\n\n${validationErrors.join('\n')}`;
    optimizerResultsEl.classList.remove('ready');
    optimizerResultsEl.style.display = 'block';
    return;
  }

  const wfEnabled = Boolean(document.getElementById('enableWF')?.checked);

  if (!state.start || !state.end) {
    optimizerResultsEl.textContent = 'Please specify start and end dates.';
    optimizerResultsEl.classList.remove('ready');
    optimizerResultsEl.style.display = 'block';
    return;
  }

  // Handle Walk-Forward mode
  if (wfEnabled) {
    clearWFResults();
    await runWalkForward({ sources, state });
    return;
  }

  // Regular optimization
  const config = buildOptunaConfig(state);
  const hasEnabledParams = Object.values(config.enabled_params || {}).some(Boolean);
  if (!hasEnabledParams) {
    optimizerResultsEl.textContent = 'Enable at least one parameter to optimize.';
    optimizerResultsEl.classList.remove('ready', 'loading');
    optimizerResultsEl.style.display = 'block';
    return;
  }

  // Show progress UI
  optimizerResultsEl.textContent = '';
  optimizerResultsEl.classList.add('loading');
  optimizerResultsEl.classList.remove('ready');
  optimizerResultsEl.style.display = 'block';
  progressContainer.style.display = 'block';

  if (optunaProgress) optunaProgress.style.display = 'block';
  if (optunaProgressFill) optunaProgressFill.style.width = '0%';
  if (optunaBestTrial) optunaBestTrial.textContent = 'Waiting for first trial...';
  if (optunaCurrentTrial) optunaCurrentTrial.textContent = 'Current trial: -';
  if (optunaEta) optunaEta.textContent = 'Est. time remaining: -';

  const totalSources = sources.length;
  const statusMessages = new Array(totalSources).fill('');
  const updateStatus = (index, message) => {
    statusMessages[index] = message;
    optimizerResultsEl.textContent = statusMessages.filter(Boolean).join('\n');
  };

  let successCount = 0;

  for (let index = 0; index < totalSources; index++) {
    const source = sources[index];
    const isFileObject = typeof File !== 'undefined' && source instanceof File;
    const rawSourceName = isFileObject ? source.name : source && source.path;
    const sourceName = rawSourceName || (isFileObject ? 'Unnamed file' : 'Saved path');
    const sourceNumber = index + 1;

    updateStatus(index, `Processing source ${sourceNumber} of ${totalSources}: ${sourceName} — processing...`);

    const formData = new FormData();
    formData.append('strategy', window.currentStrategyId);
    const warmupValue = document.getElementById('warmupBars')?.value || '1000';
    formData.append('warmupBars', warmupValue);
    if (isFileObject) {
      formData.append('file', source, source.name);
    } else if (source && source.path) {
      formData.append('csvPath', source.path);
    }
    formData.append('config', JSON.stringify(config));

    try {
      const { blob, headers } = await runOptimizationRequest(formData);

      // Download CSV
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;

      const disposition = headers.get('Content-Disposition');
      let downloadName = `optimization_${Date.now()}.csv`;
      if (disposition) {
        const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
        const asciiMatch = disposition.match(/filename="?([^";]+)"?/i);
        if (utf8Match && utf8Match[1]) {
          try {
            downloadName = decodeURIComponent(utf8Match[1]);
          } catch (err) {
            downloadName = utf8Match[1];
          }
        } else if (asciiMatch && asciiMatch[1]) {
          downloadName = asciiMatch[1];
        }
      }
      link.download = downloadName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      if (optunaProgressFill) optunaProgressFill.style.width = '100%';
      if (optunaBestTrial) optunaBestTrial.textContent = 'Review the downloaded CSV for best trial and metrics.';

      updateStatus(index, `✅ Source ${sourceNumber} of ${totalSources} (${sourceName}) processed successfully.`);
      successCount++;
    } catch (err) {
      const message = err && err.message ? err.message : 'Optimization failed.';
      console.error(`Optimization failed for source ${sourceName}`, err);

      if (optunaProgressFill) optunaProgressFill.style.width = '0%';
      if (optunaProgressText) optunaProgressText.textContent = `Error: ${message}`;

      updateStatus(index, `❌ Source ${sourceNumber} of ${totalSources} (${sourceName}) failed: ${message}`);
    }
  }

  optimizerResultsEl.classList.remove('loading');
  if (successCount > 0) {
    optimizerResultsEl.classList.add('ready');
  } else {
    optimizerResultsEl.classList.remove('ready');
  }

  const summaryMessages = statusMessages.filter(Boolean);
  if (successCount === totalSources) {
    summaryMessages.push(`Optimization complete! All ${totalSources} source(s) processed successfully.`);
  } else if (successCount > 0) {
    summaryMessages.push(`Optimization finished: ${successCount} successful, ${totalSources - successCount} failed.`);
  } else {
    summaryMessages.push('Optimization failed for all sources. See error details above.');
  }
  optimizerResultsEl.textContent = summaryMessages.join('\n');
}

/**
 * Run Walk-Forward analysis.
 * NOTE: This function is complex - copy the full implementation from index.html
 * lines 2446-2648 into this file.
 */
async function runWalkForward({ sources, state }) {
  // Copy the full runWalkForward implementation from current index.html
  // This is approximately 200 lines of code
  console.log('Walk-Forward implementation needs to be copied from index.html');
}
```

---

## Step 5: Create Clean HTML Template

**File:** `src/ui/templates/index.html`

**Action:** Copy lines 1-525 from current `src/index.html` (the HTML structure before `<script>` tag) to the new location, then add script tags at the end.

**Modifications needed:**

1. **Update CSS link:**
```html
<link rel="stylesheet" href="/static/css/style.css" />
```

2. **Remove all `<style>` blocks** (should already be removed - they were extracted in Phase 8)

3. **Replace the entire `<script>...</script>` block with external script includes:**

At the end of `<body>`, just before `</body>`, add:

```html
  <!-- JavaScript modules -->
  <script src="/static/js/utils.js"></script>
  <script src="/static/js/api.js"></script>
  <script src="/static/js/strategy-config.js"></script>
  <script src="/static/js/presets.js"></script>
  <script src="/static/js/ui-handlers.js"></script>
  <script src="/static/js/main.js"></script>
</body>
</html>
```

**The HTML file should now be approximately 530-550 lines.**

---

## Step 6: Delete Old Files

After all new files are created and working:

```bash
# Remove old index.html from src/
rm src/index.html

# Remove old server.py from src/
rm src/server.py

# Remove empty static directory if exists
rm -rf src/static
```

---

## Step 7: Update run_backtest.py

**File:** `src/run_backtest.py`

Update imports if necessary to account for server.py moving. The CLI should continue to work as it likely imports from `core/` directly.

---

## Step 8: Testing Procedures

### 8.1: Start Server from New Location

```bash
cd src/ui
python server.py
```

Or from project root:
```bash
cd src
python -m ui.server
```

### 8.2: Browser Testing Checklist

Open http://localhost:8000 and verify:

1. **Page Load:**
   - [ ] Page loads without errors
   - [ ] CSS is applied correctly (light theme)
   - [ ] No JavaScript errors in browser console

2. **Strategy Selection:**
   - [ ] Strategy dropdown loads S01 and S04
   - [ ] Selecting a strategy updates info panel
   - [ ] Strategy parameters load correctly

3. **Backtest Form:**
   - [ ] Date inputs work
   - [ ] File upload works
   - [ ] Parameter inputs work
   - [ ] Run button submits successfully

4. **Optimizer Form:**
   - [ ] Parameter checkboxes work
   - [ ] From/To/Step inputs work
   - [ ] Budget mode selection works
   - [ ] Run Optimization button works

5. **Walk-Forward:**
   - [ ] Enable WF checkbox shows settings
   - [ ] WF settings inputs work
   - [ ] WF runs and shows results

6. **Presets:**
   - [ ] Presets dropdown opens
   - [ ] Apply defaults works
   - [ ] Save as works
   - [ ] Load preset works
   - [ ] Delete preset works

7. **Results:**
   - [ ] Backtest results display
   - [ ] Optimization CSV downloads
   - [ ] WF results table displays

### 8.3: Run Automated Tests

```bash
cd tests
pytest -v
```

All existing tests should pass (70+ tests).

---

## Validation Checklist

Before marking Phase 10 complete:

- [ ] `src/ui/` directory structure created
- [ ] `src/ui/__init__.py` created
- [ ] `src/ui/server.py` moved and updated
- [ ] `src/ui/templates/index.html` created (clean HTML)
- [ ] `src/ui/static/css/style.css` moved
- [ ] `src/ui/static/js/utils.js` created
- [ ] `src/ui/static/js/api.js` created
- [ ] `src/ui/static/js/strategy-config.js` created
- [ ] `src/ui/static/js/presets.js` created
- [ ] `src/ui/static/js/ui-handlers.js` created
- [ ] `src/ui/static/js/main.js` created
- [ ] Old `src/index.html` deleted
- [ ] Old `src/server.py` deleted
- [ ] Old `src/static/` directory deleted
- [ ] Server starts without errors
- [ ] All browser tests pass
- [ ] All automated tests pass
- [ ] UI looks identical to before
- [ ] No functional regressions

---

## Success Criteria

- **UI appearance:** IDENTICAL to before migration
- **UI functionality:** IDENTICAL to before migration
- **No regressions:** All tests passing
- **Clean architecture:** HTML/CSS/JS properly separated
- **Maintainability:** Easy to find and modify code

---

## Common Issues and Solutions

### Issue: Module not found errors in server.py

**Solution:** Ensure sys.path manipulation is at the top of server.py:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

### Issue: Static files not loading (404)

**Solution:** Check Flask static configuration:
```python
app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
    static_url_path="/static"
)
```

### Issue: JavaScript errors in console

**Solution:** Check script load order in HTML. Dependencies must load first:
1. utils.js (no dependencies)
2. api.js (depends on utils)
3. strategy-config.js (depends on utils, api)
4. presets.js (depends on utils, api)
5. ui-handlers.js (depends on all above)
6. main.js (depends on all above)

### Issue: Preset menu not working

**Solution:** Check if preset functions are available globally. Add `window.` prefix if needed.

### Issue: Strategy config not loading

**Solution:** Verify API endpoints work:
- GET /api/strategies
- GET /api/strategy/{id}/config

---

## Git Commit

After successful validation:

```bash
git add -A
git commit -m "Phase 10: Full frontend separation

- Created src/ui/ directory structure
- Moved server.py to src/ui/server.py
- Extracted JavaScript into modular files:
  - utils.js: Utility functions
  - api.js: API communication
  - strategy-config.js: Form generation
  - presets.js: Preset management
  - ui-handlers.js: Event handlers
  - main.js: App initialization
- Cleaned HTML template (templates/index.html)
- Moved static files to ui/static/
- Updated Flask configuration
- All tests passing
- No functional changes"

git tag phase-10-complete
```

---

## Notes for Agent

1. **Copy JavaScript exactly** - Do not refactor or improve code during migration
2. **Test frequently** - After each file, verify the application still works
3. **Use browser DevTools** - Check Network tab and Console for errors
4. **Preserve all functionality** - This is a structural refactoring only
5. **Keep comments** - Preserve inline comments from original code
6. **Handle global state** - Use `window.` prefix for variables that need global access

---

**END OF PHASE 10 PROMPT**
