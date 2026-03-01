(function () {
  const COVERAGE_SMALL_LEVEL_THRESHOLD = 12;
  const COVERAGE_WARNING_COLOR = '#c57600';
  let coverageListenersBound = false;

  const OBJECTIVE_LABELS = {
    net_profit_pct: 'Net Profit %',
  max_drawdown_pct: 'Max DD %',
    sharpe_ratio: 'Sharpe Ratio',
    sortino_ratio: 'Sortino Ratio',
    romad: 'RoMaD',
    profit_factor: 'Profit Factor',
    win_rate: 'Win Rate %',
    sqn: 'SQN',
    ulcer_index: 'Ulcer Index',
    consistency_score: 'Consistency %',
    composite_score: 'Composite Score'
  };
  function getObjectiveCheckboxes() {
    return Array.from(document.querySelectorAll('.objective-checkbox'));
  }

  function updateObjectiveSelection() {
    const checkboxes = getObjectiveCheckboxes();
    const selected = checkboxes.filter((cb) => cb.checked).map((cb) => cb.dataset.objective);

    if (selected.length === 0 && checkboxes.length) {
      checkboxes[0].checked = true;
      selected.push(checkboxes[0].dataset.objective);
    }

    const disableExtra = selected.length >= 6;
    checkboxes.forEach((cb) => {
      if (!cb.checked) {
        cb.disabled = disableExtra;
      } else {
        cb.disabled = false;
      }
    });

    const primaryRow = document.getElementById('primaryObjectiveRow');
    const primarySelect = document.getElementById('primaryObjective');
    if (primaryRow && primarySelect) {
      if (selected.length > 1) {
        primaryRow.style.display = 'flex';
        const previous = primarySelect.value;
        primarySelect.innerHTML = '';
        selected.forEach((obj) => {
          const option = document.createElement('option');
          option.value = obj;
          option.textContent = OBJECTIVE_LABELS[obj] || obj;
          primarySelect.appendChild(option);
        });
        primarySelect.value = selected.includes(previous) ? previous : selected[0];
      } else {
        primaryRow.style.display = 'none';
        primarySelect.innerHTML = '';
      }
    }

    const pruningCheckbox = document.getElementById('optunaPruning');
    const prunerSelect = document.getElementById('optunaPruner');
    const disablePruning = selected.length > 1;
    if (pruningCheckbox) {
      if (disablePruning) {
        pruningCheckbox.checked = false;
      }
      pruningCheckbox.disabled = disablePruning;
    }
    if (prunerSelect) {
      prunerSelect.disabled = disablePruning;
    }
  }

  function toggleNsgaSettings() {
    const sampler = document.getElementById('optunaSampler');
    const nsgaSettings = document.getElementById('nsgaSettings');
    if (!sampler || !nsgaSettings) {
      return;
    }
    const isNsga = sampler.value === 'nsga2' || sampler.value === 'nsga3';
    nsgaSettings.style.display = isNsga ? 'block' : 'none';
  }

  function estimateNumericLevels(paramType, low, high, step) {
    if (!Number.isFinite(low) || !Number.isFinite(high) || high < low) return null;
    if (paramType === 'int') {
      const safeStep = Number.isFinite(step) && step > 0 ? Math.max(1, Math.round(step)) : 1;
      const lowInt = Math.round(low);
      const highInt = Math.round(high);
      if (highInt < lowInt) return null;
      return Math.floor((highInt - lowInt) / safeStep) + 1;
    }
    if (!Number.isFinite(step) || step <= 0) {
      return null;
    }
    return Math.floor(((high - low) / step) + 1e-9) + 1;
  }

  function readSelectedCategoricalCount(paramName, paramDef) {
    const choices = Array.isArray(paramDef?.options) ? paramDef.options : [];
    const optionNodes = document.querySelectorAll(
      `input.select-option-checkbox[data-param-name="${paramName}"]:not([data-option-value="__ALL__"])`
    );
    if (!optionNodes.length) {
      return choices.length || 0;
    }
    const selected = Array.from(optionNodes).filter((node) => node.checked).length;
    return selected > 0 ? selected : (choices.length || 0);
  }

  function collectCoverageAnalysis() {
    const strategyParams = window.currentStrategyConfig?.parameters || {};
    const paramRows = typeof getOptimizerParamElements === 'function'
      ? getOptimizerParamElements()
      : [];

    const categoricalAxes = [];
    const discreteAxes = [];
    let numericContinuousCount = 0;

    paramRows.forEach((entry) => {
      if (!entry || !entry.checkbox || !entry.checkbox.checked) return;
      const name = entry.name;
      const paramDef = strategyParams[name] || entry.def || {};
      const paramType = String(paramDef.type || '').toLowerCase();

      if (paramType === 'select' || paramType === 'options' || paramType === 'bool' || paramType === 'boolean') {
        const count = (paramType === 'bool' || paramType === 'boolean')
          ? 2
          : readSelectedCategoricalCount(name, paramDef);
        if (count > 0) {
          categoricalAxes.push({ name, count });
          discreteAxes.push({ name, count });
        }
        return;
      }

      if (paramType === 'int' || paramType === 'float') {
        const optimizeDef = paramDef.optimize || {};
        const low = Number(entry.fromInput?.value ?? optimizeDef.min ?? paramDef.min);
        const high = Number(entry.toInput?.value ?? optimizeDef.max ?? paramDef.max);
        const defaultStep = paramType === 'int' ? 1 : null;
        const step = Number(entry.stepInput?.value ?? optimizeDef.step ?? paramDef.step ?? defaultStep);
        const levels = estimateNumericLevels(paramType, low, high, step);
        if (Number.isFinite(levels) && levels > 0 && levels <= COVERAGE_SMALL_LEVEL_THRESHOLD) {
          discreteAxes.push({ name, count: levels });
        } else {
          numericContinuousCount += 1;
        }
      }
    });

    const cAxis = discreteAxes.length
      ? Math.max(...discreteAxes.map((item) => Number(item.count) || 0))
      : 1;
    const nMin = Math.max(cAxis, 1 + (2 * numericContinuousCount));
    const sampler = String(document.getElementById('optunaSampler')?.value || 'tpe').toLowerCase();
    const populationRaw = Number(document.getElementById('nsgaPopulationSize')?.value);
    const populationSize = Number.isFinite(populationRaw) ? Math.max(2, Math.round(populationRaw)) : 50;
    const nRecBase = Math.max(2 * nMin, cAxis + (4 * numericContinuousCount), 12);
    const nRec = (sampler === 'nsga2' || sampler === 'nsga3')
      ? Math.max(nRecBase, populationSize)
      : nRecBase;

    const mainAxis = categoricalAxes.length
      ? categoricalAxes.reduce((best, item) => (
        !best || item.count > best.count ? item : best
      ), null)
      : null;

    return {
      nMin,
      nRec,
      nNum: numericContinuousCount,
      mainAxisName: mainAxis?.name || null,
      mainAxisOptions: mainAxis?.count || 0
    };
  }

  function updateCoverageInfo() {
    const checkbox = document.getElementById('optunaCoverageMode');
    const infoEl = document.getElementById('coverageInfo');
    const warmupInput = document.getElementById('optunaWarmupTrials');
    if (!checkbox || !infoEl || !warmupInput) return;

    if (!checkbox.checked) {
      infoEl.style.display = 'none';
      return;
    }

    const trialCountRaw = Number(warmupInput.value);
    const trialCount = Number.isFinite(trialCountRaw) ? Math.max(0, Math.round(trialCountRaw)) : 0;
    const analysis = collectCoverageAnalysis();

    infoEl.style.display = 'block';
    if (trialCount < analysis.nRec) {
      infoEl.textContent = `Need more initial trials (min: ${analysis.nMin}, recommended: ${analysis.nRec})`;
      infoEl.style.color = COVERAGE_WARNING_COLOR;
      return;
    }

    if (analysis.mainAxisName && analysis.mainAxisOptions > 0) {
      const perOption = Math.floor(trialCount / analysis.mainAxisOptions);
      const remainder = trialCount % analysis.mainAxisOptions;
      const perOptionLabel = remainder > 0
        ? `~${perOption}-${perOption + 1}`
        : `${perOption}`;
      infoEl.textContent = `${analysis.mainAxisName}: ${analysis.mainAxisOptions} options x ${perOptionLabel} trials each`;
      infoEl.style.color = '#888';
      return;
    }

    infoEl.textContent = `${analysis.nNum} numeric params, LHS coverage`;
    infoEl.style.color = '#888';
  }

  function shouldRefreshCoverageFromEventTarget(target) {
    if (!target) return false;
    const id = target.id || '';
    if (id === 'optunaCoverageMode'
      || id === 'optunaWarmupTrials'
      || id === 'optunaSampler'
      || id === 'nsgaPopulationSize'
      || id === 'strategySelect') {
      return true;
    }
    if (target.classList) {
      if (target.classList.contains('opt-param-toggle')
        || target.classList.contains('select-option-checkbox')) {
        return true;
      }
    }
    return /^opt-.+-(from|to|step)$/.test(id);
  }

  function initCoverageInfo() {
    if (!coverageListenersBound) {
      coverageListenersBound = true;
      document.addEventListener('change', (event) => {
        if (shouldRefreshCoverageFromEventTarget(event.target)) {
          updateCoverageInfo();
        }
      });
      document.addEventListener('input', (event) => {
        if (shouldRefreshCoverageFromEventTarget(event.target)) {
          updateCoverageInfo();
        }
      });
    }
    updateCoverageInfo();
  }

  function initSanitizeControls() {
    const checkbox = document.getElementById('optuna_sanitize_enabled');
    const input = document.getElementById('optuna_sanitize_trades_threshold');
    if (!checkbox || !input) {
      return;
    }

    const sync = () => {
      input.disabled = !checkbox.checked;
    };

    checkbox.addEventListener('change', sync);
    input.addEventListener('blur', () => {
      const parsed = Number.parseInt(input.value, 10);
      const normalized = Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
      input.value = normalized;
    });

    sync();
  }

  function collectObjectives() {
    const checkboxes = getObjectiveCheckboxes();
    const selected = checkboxes.filter((cb) => cb.checked).map((cb) => cb.dataset.objective);
    const primarySelect = document.getElementById('primaryObjective');
    const primaryObjective = selected.length > 1 && primarySelect ? primarySelect.value : null;
    return {
      objectives: selected,
      primary_objective: primaryObjective
    };
  }

  function collectSanitizeConfig() {
    const checkbox = document.getElementById('optuna_sanitize_enabled');
    const input = document.getElementById('optuna_sanitize_trades_threshold');
    const enabled = Boolean(checkbox && checkbox.checked);
    const parsed = Number.parseInt(input ? input.value : '', 10);
    const threshold = Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
    return {
      sanitize_enabled: enabled,
      sanitize_trades_threshold: threshold
    };
  }

  function collectConstraints() {
    const rows = Array.from(document.querySelectorAll('.constraint-row'));
    return rows.map((row) => {
      const checkbox = row.querySelector('.constraint-checkbox');
      const input = row.querySelector('.constraint-input');
      const metric = checkbox ? checkbox.dataset.constraintMetric : null;
      let threshold = null;
      if (input && input.value !== '') {
        const parsed = Number(input.value);
        threshold = Number.isFinite(parsed) ? parsed : null;
      }
      return {
        metric,
        threshold,
        enabled: Boolean(checkbox && checkbox.checked)
      };
    }).filter((item) => item.metric);
  }

  window.OptunaUI = {
    updateObjectiveSelection,
    toggleNsgaSettings,
    updateCoverageInfo,
    initCoverageInfo,
    initSanitizeControls,
    collectObjectives,
    collectSanitizeConfig,
    collectConstraints
  };
})();


