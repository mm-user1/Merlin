(function () {
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

  function inferPrimaryNumericName(mainAxisName, numericNames) {
    if (!Array.isArray(numericNames) || !numericNames.length) return null;
    if (!mainAxisName) return numericNames[0];

    const axis = String(mainAxisName);
    const axisLower = axis.toLowerCase();
    const candidates = [
      axis.replace('Type', 'Length'),
      axis.replace('type', 'length'),
      axis.replace('_type', '_length'),
      axis.replace('_Type', '_Length'),
      axis.replace('Type', 'Period'),
      axis.replace('type', 'period'),
      axis.replace('_type', '_period'),
      axis.replace('_Type', '_Period')
    ];

    if (axisLower.endsWith('type')) {
      const root = axis.slice(0, -4);
      candidates.push(`${root}Length`, `${root}length`, `${root}Period`, `${root}period`);
    }
    if (axisLower.endsWith('_type')) {
      const root = axis.slice(0, -5);
      candidates.push(`${root}_Length`, `${root}_length`, `${root}_Period`, `${root}_period`);
    }

    const deduped = [];
    const seen = new Set();
    candidates.forEach((item) => {
      if (!item || seen.has(item)) return;
      seen.add(item);
      deduped.push(item);
    });

    for (const name of deduped) {
      if (numericNames.includes(name)) return name;
    }

    const digits = axis.replace(/\D+/g, '');
    if (digits) {
      const match = numericNames.find((name) => (
        String(name).endsWith(digits)
        && /length|period/i.test(String(name))
      ));
      if (match) return match;
    }

    const lengthLike = numericNames.find((name) => /length|period/i.test(String(name)));
    return lengthLike || numericNames[0];
  }

  function collectCoverageAnalysis() {
    const strategyParams = window.currentStrategyConfig?.parameters || {};
    const paramRows = typeof getOptimizerParamElements === 'function'
      ? getOptimizerParamElements()
      : [];

    const categoricalAxes = [];
    const numericNames = [];

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
        }
        return;
      }

      if (paramType === 'int' || paramType === 'float') {
        numericNames.push(name);
      }
    });

    let blockSize = 1;
    categoricalAxes.forEach((axis) => {
      blockSize *= Math.max(1, Number(axis.count) || 1);
    });
    const nMin = Math.max(1, blockSize);
    const nRec = Math.max(nMin, nMin * 2);

    const mainAxis = categoricalAxes.length
      ? categoricalAxes.reduce((best, item) => (
        !best || item.count > best.count ? item : best
      ), null)
      : null;
    const primaryNumericName = inferPrimaryNumericName(mainAxis?.name || null, numericNames);

    return {
      nMin,
      nRec,
      blockSize: nMin,
      categoricalAxes: categoricalAxes.length,
      numericAxes: numericNames.length,
      mainAxisName: mainAxis?.name || null,
      mainAxisOptions: mainAxis?.count || 0,
      primaryNumericName
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
    if (trialCount < analysis.nMin) {
      infoEl.textContent = `Need more initial trials (min: ${analysis.nMin}, recommended: ${analysis.nRec})`;
      infoEl.style.color = COVERAGE_WARNING_COLOR;
      return;
    }

    const fullBlocks = Math.floor(trialCount / analysis.blockSize);
    const remainder = trialCount % analysis.blockSize;
    const axisPart = analysis.mainAxisName && analysis.mainAxisOptions > 0
      ? `${analysis.mainAxisName}: ${analysis.mainAxisOptions} options`
      : `${analysis.categoricalAxes} categorical params`;
    const primaryPart = analysis.primaryNumericName
      ? `, primary numeric: ${analysis.primaryNumericName}`
      : '';
    const tailPart = remainder > 0 ? ` + ${remainder} partial` : '';
    infoEl.textContent = `Coverage block size: ${analysis.blockSize}, blocks: ${fullBlocks}${tailPart}, ${axisPart}${primaryPart}`;
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


