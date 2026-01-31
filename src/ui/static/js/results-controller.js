function inferPostProcessSource(trials, key) {
  const values = new Set();
  (trials || []).forEach((trial) => {
    const value = trial ? trial[key] : null;
    if (value) values.add(value);
  });
  if (values.size === 1) {
    return Array.from(values)[0];
  }
  return null;
}

function buildRankMapFromKey(trials, rankKey) {
  const map = {};
  (trials || []).forEach((trial) => {
    if (!trial) return;
    const rank = trial[rankKey];
    if (rank !== null && rank !== undefined) {
      map[trial.trial_number] = rank;
    }
  });
  return map;
}

function updateTabsVisibility() {
  const tabs = document.querySelectorAll('.tab-btn');
  const dsrTab = document.querySelector('.tab-btn[data-tab="dsr"]');
  const forwardTab = document.querySelector('.tab-btn[data-tab="forward_test"]');
  const stressTab = document.querySelector('.tab-btn[data-tab="stress_test"]');
  const oosTab = document.querySelector('.tab-btn[data-tab="oos_test"]');
  const manualTab = document.querySelector('.tab-btn[data-tab="manual_tests"]');
  const tabsContainer = document.getElementById('resultsTabs');
  const manualBtn = document.getElementById('manualTestBtn');

  if (ResultsState.mode !== 'optuna') {
    if (tabsContainer) tabsContainer.style.display = 'none';
    if (manualBtn) manualBtn.style.display = 'none';
    return;
  }

  if (tabsContainer) tabsContainer.style.display = 'flex';

  const hasDsr = ResultsState.dsr.enabled && ResultsState.dsr.trials.length > 0;
  const hasForwardTest = ResultsState.forwardTest.enabled && ResultsState.forwardTest.trials.length > 0;
  const hasStressTest = ResultsState.stressTest.enabled && ResultsState.stressTest.trials.length > 0;
  const hasOosTest = ResultsState.oosTest.enabled && ResultsState.oosTest.trials.length > 0;
  const hasManualTests = ResultsState.manualTests.length > 0;

  if (dsrTab) dsrTab.style.display = hasDsr ? 'inline-flex' : 'none';
  if (forwardTab) forwardTab.style.display = hasForwardTest ? 'inline-flex' : 'none';
  if (stressTab) stressTab.style.display = hasStressTest ? 'inline-flex' : 'none';
  if (oosTab) oosTab.style.display = hasOosTest ? 'inline-flex' : 'none';
  if (manualTab) manualTab.style.display = hasManualTests ? 'inline-flex' : 'none';
  if (manualBtn) {
    manualBtn.style.display = ['optuna', 'dsr', 'forward_test', 'stress_test'].includes(ResultsState.activeTab)
      ? 'inline-flex'
      : 'none';
  }

  if (!hasDsr && ResultsState.activeTab === 'dsr') {
    ResultsState.activeTab = 'optuna';
  }
  if (!hasForwardTest && ResultsState.activeTab === 'forward_test') {
    ResultsState.activeTab = 'optuna';
  }
  if (!hasStressTest && ResultsState.activeTab === 'stress_test') {
    ResultsState.activeTab = 'optuna';
  }
  if (!hasOosTest && ResultsState.activeTab === 'oos_test') {
    ResultsState.activeTab = 'optuna';
  }
  if (!hasManualTests && ResultsState.activeTab === 'manual_tests') {
    ResultsState.activeTab = 'optuna';
  }

  tabs.forEach((tab) => {
    const tabId = tab.dataset.tab;
    tab.classList.toggle('active', tabId === ResultsState.activeTab);
  });
}

function setTableExpanded(expanded) {
  const scroll = document.querySelector('.table-scroll');
  const toggle = document.getElementById('tableExpandToggle');
  if (!scroll || !toggle) return;
  scroll.classList.toggle('expanded', expanded);
  toggle.dataset.expanded = expanded ? '1' : '0';
  toggle.classList.toggle('expanded', expanded);
}

function setTableExpandVisibility() {
  const wrapper = document.querySelector('.table-expand');
  const scroll = document.querySelector('.table-scroll');
  if (!wrapper) return;
  const show = ResultsState.mode !== 'wfa';
  wrapper.style.display = show ? 'flex' : 'none';
  if (!show) setTableExpanded(false);
  if (scroll) {
    scroll.classList.toggle('wfa-tall', ResultsState.mode === 'wfa');
  }
}

function bindTableExpandToggle() {
  const toggle = document.getElementById('tableExpandToggle');
  if (!toggle) return;
  toggle.addEventListener('click', () => {
    const expanded = toggle.dataset.expanded === '1';
    setTableExpanded(!expanded);
  });
  setTableExpanded(false);
}

async function activateTab(tabId) {
  ResultsState.activeTab = tabId;
  ResultsState.selectedRowId = null;
  updateTabsVisibility();
  if (tabId === 'manual_tests') {
    await ensureManualTestSelection();
  }
  refreshResultsView();
}

function renderStudiesList(studies) {
  const listEl = document.querySelector('.studies-list');
  if (!listEl) return;
  listEl.innerHTML = '';

  if (!studies || !studies.length) {
    const empty = document.createElement('div');
    empty.className = 'study-item';
    empty.textContent = 'No saved studies yet.';
    listEl.appendChild(empty);
    return;
  }

  studies.forEach((study) => {
    const item = document.createElement('div');
    item.className = 'study-item';
    item.dataset.studyId = study.study_id;

    if (study.study_id === ResultsState.studyId && !ResultsState.multiSelect) {
      item.classList.add('selected');
    }
    if (ResultsState.multiSelect && ResultsState.selectedStudies.includes(study.study_id)) {
      item.classList.add('selected');
    }

    item.innerHTML = `
      <span class="study-name">${study.study_name}</span>
    `;

    item.addEventListener('click', (event) => {
      if (ResultsState.multiSelect) {
        event.preventDefault();
        toggleStudySelection(study.study_id);
      } else {
        openStudy(study.study_id);
      }
    });

    listEl.appendChild(item);
  });
}

async function loadStudiesList() {
  try {
    const data = await fetchStudiesList();
    renderStudiesList(data.studies || []);
    return data.studies || [];
  } catch (error) {
    console.warn('Failed to load studies list', error);
    renderStudiesList([]);
    return [];
  }
}

function buildStitchedFromWindows(windows) {
  const stitched = [];
  const stitchedTimestamps = [];
  const windowIds = [];
  let currentBalance = 100.0;
  let timestampsValid = true;

  (windows || []).forEach((window, index) => {
    const equity = window.oos_equity_curve || [];
    if (!equity.length) return;

    const timestamps = Array.isArray(window.oos_timestamps) ? window.oos_timestamps : [];
    const hasTimestamps = timestamps.length >= equity.length;

    const startEquity = equity[0] || 100.0;
    const startIdx = index === 0 ? 0 : 1;
    const windowId = window.window_number || window.window_id || index + 1;

    for (let i = startIdx; i < equity.length; i += 1) {
      const pctChange = (equity[i] / startEquity) - 1.0;
      const newBalance = currentBalance * (1.0 + pctChange);
      stitched.push(newBalance);
      windowIds.push(windowId);
      if (timestampsValid) {
        if (hasTimestamps) {
          stitchedTimestamps.push(timestamps[i]);
        } else {
          timestampsValid = false;
        }
      }
    }

    if (stitched.length) {
      currentBalance = stitched[stitched.length - 1];
    }
  });

  const timestamps = timestampsValid && stitchedTimestamps.length === stitched.length
    ? stitchedTimestamps
    : [];
  return { equity_curve: stitched, window_ids: windowIds, timestamps };
}

function calculateSummaryFromEquity(equityCurve) {
  if (!equityCurve || !equityCurve.length) {
    return { final_net_profit_pct: 0, max_drawdown_pct: 0 };
  }
  const finalValue = equityCurve[equityCurve.length - 1];
  const finalNetProfitPct = (finalValue / 100.0 - 1.0) * 100.0;

  let peak = equityCurve[0];
  let maxDd = 0;
  equityCurve.forEach((value) => {
    if (value > peak) peak = value;
    if (peak > 0) {
      const dd = (peak - value) / peak * 100.0;
      if (dd > maxDd) maxDd = dd;
    }
  });

  return { final_net_profit_pct: finalNetProfitPct, max_drawdown_pct: maxDd };
}

async function applyStudyPayload(data) {
  const study = data.study || {};
  ResultsState.studyId = study.study_id || ResultsState.studyId;
  ResultsState.studyName = study.study_name || ResultsState.studyName;
  ResultsState.studyCreatedAt = study.completed_at || study.created_at || ResultsState.studyCreatedAt;
  ResultsState.mode = study.optimization_mode || ResultsState.mode;
  ResultsState.status = study.status || (study.completed_at ? 'completed' : ResultsState.status);
  ResultsState.strategyId = study.strategy_id || ResultsState.strategyId;
  ResultsState.dataset = { label: study.csv_file_name || '' };
  ResultsState.dataPath = study.csv_file_path || ResultsState.dataPath;

  const config = study.config_json || {};
  ResultsState.wfa = {
    ...(ResultsState.wfa || {}),
    postProcess: config.postProcess || {}
  };
  ResultsState.fixedParams = config.fixed_params || ResultsState.fixedParams;
  ResultsState.dateFilter = Boolean(ResultsState.fixedParams.dateFilter ?? ResultsState.dateFilter);
  ResultsState.start = ResultsState.fixedParams.start || ResultsState.start;
  ResultsState.end = ResultsState.fixedParams.end || ResultsState.end;

  if (ResultsState.mode === 'wfa') {
    ResultsState.results = data.windows || [];
  } else {
    ResultsState.results = data.trials || [];
  }
  ResultsState.selectedRowId = null;

  ResultsState.forwardTest.enabled = Boolean(study.ft_enabled);
  ResultsState.forwardTest.startDate = study.ft_start_date || '';
  ResultsState.forwardTest.endDate = study.ft_end_date || '';
  ResultsState.forwardTest.periodDays = study.ft_period_days ?? null;
  ResultsState.forwardTest.sortMetric = study.ft_sort_metric || 'profit_degradation';
  ResultsState.forwardTest.trials = (data.trials || []).filter((trial) => trial.ft_rank !== null && trial.ft_rank !== undefined);
  ResultsState.forwardTest.trials.sort((a, b) => (a.ft_rank || 0) - (b.ft_rank || 0));

  const dsrTrials = (data.trials || []).filter((trial) => trial.dsr_rank !== null && trial.dsr_rank !== undefined);
  dsrTrials.sort((a, b) => (a.dsr_rank || 0) - (b.dsr_rank || 0));
  ResultsState.dsr = {
    enabled: Boolean(study.dsr_enabled),
    topK: study.dsr_top_k ?? null,
    trials: dsrTrials,
    nTrials: study.dsr_n_trials ?? null,
    meanSharpe: study.dsr_mean_sharpe ?? null,
    varSharpe: study.dsr_var_sharpe ?? null
  };
  ResultsState.forwardTest.source = study.ft_source
    || inferPostProcessSource(data.trials || [], 'ft_source')
    || 'optuna';

  const stTrials = (data.trials || []).filter((trial) => trial.st_rank !== null && trial.st_rank !== undefined);
  stTrials.sort((a, b) => (a.st_rank || 0) - (b.st_rank || 0));
  ResultsState.stressTest = {
    enabled: Boolean(study.st_enabled),
    topK: study.st_top_k ?? null,
    trials: stTrials,
    sortMetric: study.st_sort_metric || 'profit_retention',
    failureThreshold: study.st_failure_threshold ?? 0.7,
    avgProfitRetention: study.st_avg_profit_retention ?? null,
    avgRomadRetention: study.st_avg_romad_retention ?? null,
    avgCombinedFailureRate: study.st_avg_combined_failure_rate ?? null,
    candidatesSkippedBadBase: study.st_candidates_skipped_bad_base ?? 0,
    candidatesSkippedNoParams: study.st_candidates_skipped_no_params ?? 0,
    candidatesInsufficientData: study.st_candidates_insufficient_data ?? 0,
    source: study.st_source
      || inferPostProcessSource(data.trials || [], 'st_source')
      || 'optuna'
  };

  const oosTrials = (data.trials || []).filter(
    (trial) => trial.oos_test_source_rank !== null && trial.oos_test_source_rank !== undefined
  );
  oosTrials.sort((a, b) => (a.oos_test_source_rank || 0) - (b.oos_test_source_rank || 0));
  ResultsState.oosTest = {
    enabled: Boolean(study.oos_test_enabled),
    topK: study.oos_test_top_k ?? null,
    periodDays: study.oos_test_period_days ?? null,
    startDate: study.oos_test_start_date || '',
    endDate: study.oos_test_end_date || '',
    source: study.oos_test_source_module
      || inferPostProcessSource(data.trials || [], 'oos_test_source')
      || '',
    trials: oosTrials
  };

  ResultsState.manualTests = data.manual_tests || [];
  ResultsState.activeManualTest = null;
  ResultsState.manualTestResults = [];

  if (ResultsState.mode === 'optuna') {
    const hasDsr = ResultsState.dsr.enabled && ResultsState.dsr.trials.length > 0;
    const hasForward = ResultsState.forwardTest.enabled && ResultsState.forwardTest.trials.length > 0;
    const hasStress = ResultsState.stressTest.enabled && ResultsState.stressTest.trials.length > 0;
    const hasOos = ResultsState.oosTest.enabled && ResultsState.oosTest.trials.length > 0;
    const hasManual = ResultsState.manualTests.length > 0;
    if (ResultsState.activeTab === 'dsr' && !hasDsr) {
      ResultsState.activeTab = 'optuna';
    }
    if (ResultsState.activeTab === 'forward_test' && !hasForward) {
      ResultsState.activeTab = 'optuna';
    }
    if (ResultsState.activeTab === 'stress_test' && !hasStress) {
      ResultsState.activeTab = 'optuna';
    }
    if (ResultsState.activeTab === 'oos_test' && !hasOos) {
      ResultsState.activeTab = 'optuna';
    }
    if (ResultsState.activeTab === 'manual_tests' && !hasManual) {
      ResultsState.activeTab = 'optuna';
    }
    if (!ResultsState.activeTab) {
      ResultsState.activeTab = 'optuna';
    }
  }

  if (ResultsState.mode === 'wfa') {
    const stitched = buildStitchedFromWindows(ResultsState.results);
    const summary = calculateSummaryFromEquity(stitched.equity_curve);
    const profitable = (ResultsState.results || []).filter((w) => (w.oos_net_profit_pct || 0) > 0).length;
    const winRate = ResultsState.results && ResultsState.results.length
      ? (profitable / ResultsState.results.length) * 100
      : 0;
    ResultsState.stitched_oos = {
      final_net_profit_pct: summary.final_net_profit_pct,
      max_drawdown_pct: summary.max_drawdown_pct,
      total_trades: ResultsState.results.reduce((sum, w) => sum + (w.oos_total_trades || 0), 0),
      wfe: study.best_value || 0,
      oos_win_rate: winRate,
      equity_curve: stitched.equity_curve,
      timestamps: stitched.timestamps || [],
      window_ids: stitched.window_ids
    };
  }

  if (ResultsState.strategyId) {
    try {
      const strategyConfig = await fetchStrategyConfig(ResultsState.strategyId);
      ResultsState.strategyConfig = strategyConfig || {};
      ResultsState.strategy = {
        name: strategyConfig.name || ResultsState.strategyId,
        version: strategyConfig.version || ''
      };
    } catch (error) {
      console.warn('Failed to load strategy config', error);
    }
  }

  const optunaConfig = config.optuna_config || {};
  const primaryObjective = study.primary_objective
    ?? optunaConfig.primary_objective
    ?? config.primary_objective
    ?? null;
  const objectives = study.objectives || optunaConfig.objectives || study.objectives_json || [];
  const constraints = study.constraints || optunaConfig.constraints || study.constraints_json || [];
  const sanitizeEnabledRaw = optunaConfig.sanitize_enabled ?? study.sanitize_enabled;
  const sanitizeEnabled = sanitizeEnabledRaw === undefined || sanitizeEnabledRaw === null
    ? ResultsState.optuna.sanitizeEnabled
    : Boolean(sanitizeEnabledRaw);
  const sanitizeThresholdRaw = optunaConfig.sanitize_trades_threshold ?? study.sanitize_trades_threshold;
  const sanitizeThreshold = sanitizeThresholdRaw === undefined || sanitizeThresholdRaw === null
    ? ResultsState.optuna.sanitizeTradesThreshold
    : sanitizeThresholdRaw;
  const filterMinProfitRaw = study.filter_min_profit ?? optunaConfig.filter_min_profit;
  const filterMinProfit = filterMinProfitRaw === undefined || filterMinProfitRaw === null
    ? ResultsState.optuna.filterMinProfit
    : Boolean(filterMinProfitRaw);
  const minProfitThresholdRaw = study.min_profit_threshold ?? optunaConfig.min_profit_threshold;
  const minProfitThreshold = minProfitThresholdRaw === undefined || minProfitThresholdRaw === null
    ? ResultsState.optuna.minProfitThreshold
    : minProfitThresholdRaw;
  const scoreConfig = study.score_config_json || optunaConfig.score_config || {};
  const scoreFilterRaw = scoreConfig ? scoreConfig.filter_enabled : null;
  const scoreFilterEnabled = scoreFilterRaw === undefined || scoreFilterRaw === null
    ? ResultsState.optuna.scoreFilterEnabled
    : Boolean(scoreFilterRaw);
  const scoreThresholdRaw = scoreConfig ? scoreConfig.min_score_threshold : null;
  const scoreThreshold = scoreThresholdRaw === undefined || scoreThresholdRaw === null
    ? ResultsState.optuna.scoreThreshold
    : scoreThresholdRaw;
  ResultsState.optuna = {
    objectives,
    primaryObjective,
    constraints,
    budgetMode: optunaConfig.budget_mode || study.budget_mode || ResultsState.optuna.budgetMode,
    nTrials: optunaConfig.n_trials || study.n_trials || ResultsState.optuna.nTrials,
    timeLimit: optunaConfig.time_limit || study.time_limit || ResultsState.optuna.timeLimit,
    convergence: optunaConfig.convergence_patience || study.convergence_patience || ResultsState.optuna.convergence,
    sampler: (optunaConfig.sampler_config && optunaConfig.sampler_config.sampler_type)
      || optunaConfig.sampler_type
      || study.sampler_type
      || ResultsState.optuna.sampler,
    pruner: optunaConfig.pruner || ResultsState.optuna.pruner,
    workers: config.worker_processes || ResultsState.optuna.workers,
    sanitizeEnabled,
    sanitizeTradesThreshold: sanitizeThreshold,
    filterMinProfit,
    minProfitThreshold,
    scoreFilterEnabled,
    scoreThreshold,
    optimizationTimeSeconds: study.optimization_time_seconds ?? ResultsState.optuna.optimizationTimeSeconds
  };

  updateResultsHeader();
}

async function openStudy(studyId) {
  if (!studyId) return;
  try {
    const data = await fetchStudyDetails(studyId);
    ResultsState.studyId = studyId;
    ResultsState.studyName = data.study?.study_name || ResultsState.studyName;

    if (!data.csv_exists) {
      showMissingCsvDialog(studyId, data.study?.csv_file_path || '', data.study?.csv_file_name || '');
      return;
    }

    await applyStudyPayload(data);
    if (ResultsState.activeTab === 'manual_tests') {
      await ensureManualTestSelection();
    }
    setQueryStudyId(studyId);
    await loadStudiesList();
    refreshResultsView();
  } catch (error) {
    console.warn('Failed to open study', error);
  }
}

const MissingCsvState = {
  studyId: '',
  originalPath: '',
  originalName: ''
};

function showMissingCsvDialog(studyId, originalPath, originalName) {
  MissingCsvState.studyId = studyId;
  MissingCsvState.originalPath = originalPath || '';
  MissingCsvState.originalName = originalName || '';

  const modal = document.getElementById('missingCsvModal');
  const pathEl = document.getElementById('missingCsvPath');
  const nameEl = document.getElementById('missingCsvName');
  if (pathEl) pathEl.textContent = MissingCsvState.originalPath || 'Unknown path';
  if (nameEl) nameEl.textContent = MissingCsvState.originalName || 'Unknown file';
  if (modal) modal.classList.add('show');
}

function hideMissingCsvDialog() {
  const modal = document.getElementById('missingCsvModal');
  if (modal) modal.classList.remove('show');
  MissingCsvState.studyId = '';
  MissingCsvState.originalPath = '';
  MissingCsvState.originalName = '';
}

function bindMissingCsvDialog() {
  const modal = document.getElementById('missingCsvModal');
  const cancelBtn = document.getElementById('missingCsvCancel');
  const updateBtn = document.getElementById('missingCsvUpdate');
  const fileInput = document.getElementById('missingCsvFile');
  const pathInput = document.getElementById('missingCsvInput');

  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      hideMissingCsvDialog();
    });
  }

  if (updateBtn) {
    updateBtn.addEventListener('click', async () => {
      if (!MissingCsvState.studyId) return;
      const formData = new FormData();
      if (fileInput && fileInput.files && fileInput.files.length) {
        const file = fileInput.files[0];
        formData.append('file', file, file.name);
      } else if (pathInput && pathInput.value) {
        formData.append('csvPath', pathInput.value.trim());
      } else {
        alert('Select a CSV file or provide a path.');
        return;
      }

      try {
        const response = await updateStudyCsvPathRequest(MissingCsvState.studyId, formData);
        if (response.warnings && response.warnings.length) {
          alert(`CSV updated with warnings:\n- ${response.warnings.join('\n- ')}`);
        }
        hideMissingCsvDialog();
        await openStudy(MissingCsvState.studyId);
      } catch (error) {
        alert(error.message || 'Failed to update CSV path.');
      }
    });
  }

  if (modal) {
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        hideMissingCsvDialog();
      }
    });
  }
}

async function refreshManualTestsList() {
  if (!ResultsState.studyId) return;
  try {
    const data = await fetchManualTestsList(ResultsState.studyId);
    ResultsState.manualTests = data.tests || [];
  } catch (error) {
    ResultsState.manualTests = [];
  }
}

async function loadManualTestResultsById(testId) {
  if (!ResultsState.studyId || !testId) return;
  try {
    const data = await fetchManualTestResults(ResultsState.studyId, testId);
    ResultsState.activeManualTest = {
      id: data.id,
      source_tab: data.source_tab,
      config: data.results_json?.config || null
    };
    ResultsState.manualTestResults = data.results_json?.results || [];
  } catch (error) {
    ResultsState.activeManualTest = null;
    ResultsState.manualTestResults = [];
  }
}

async function ensureManualTestSelection() {
  if (!ResultsState.manualTests.length) {
    ResultsState.activeManualTest = null;
    ResultsState.manualTestResults = [];
    return;
  }
  const activeId = ResultsState.activeManualTest?.id;
  const exists = ResultsState.manualTests.some((test) => test.id === activeId);
  if (activeId && exists) {
    await loadManualTestResultsById(activeId);
    return;
  }
  await loadManualTestResultsById(ResultsState.manualTests[0].id);
}

function getTrialsForActiveTab() {
  if (ResultsState.activeTab === 'forward_test') {
    return ResultsState.forwardTest.trials || [];
  }
  if (ResultsState.activeTab === 'dsr') {
    return ResultsState.dsr.trials || [];
  }
  if (ResultsState.activeTab === 'stress_test') {
    return ResultsState.stressTest.trials || [];
  }
  return ResultsState.results || [];
}

function bindTabs() {
  document.querySelectorAll('.tab-btn').forEach((tab) => {
    tab.addEventListener('click', async () => {
      await activateTab(tab.dataset.tab);
    });
  });
}

async function fetchEquityCurve(result, options = null) {
  if (!ResultsState.dataPath) {
    return null;
  }
  const params = { ...(ResultsState.fixedParams || {}), ...(result.params || {}) };
  let start = ResultsState.start;
  let end = ResultsState.end;
  let dateFilter = typeof ResultsState.dateFilter === 'boolean' ? ResultsState.dateFilter : false;

  if (options && options.start && options.end) {
    start = options.start;
    end = options.end;
    dateFilter = true;
  }

  if (start) params.start = start;
  if (end) params.end = end;
  params.dateFilter = dateFilter;

  const formData = new FormData();
  formData.append('strategy', ResultsState.strategyId || ResultsState.strategy.id || '');
  formData.append('warmupBars', String(ResultsState.warmupBars || 1000));
  formData.append('csvPath', ResultsState.dataPath);
  formData.append('payload', JSON.stringify(params));

  const response = await fetch('/api/backtest', {
    method: 'POST',
    body: formData
  });
  if (!response.ok) {
    return null;
  }
  const data = await response.json();
  if (!data || !data.metrics) return null;
  const equity = data.metrics.equity_curve || data.metrics.balance_curve || [];
  const timestamps = data.metrics.timestamps || [];
  return { equity, timestamps };
}

function refreshResultsView() {
  updateStatusBadge(ResultsState.status || 'idle');
  updateSidebarSettings();
  updateResultsHeader();
  updateTabsVisibility();
  setTableExpandVisibility();

  const progressLabel = document.getElementById('progressLabel');
  const progressPercent = document.getElementById('progressPercent');
  if (progressLabel) progressLabel.textContent = 'Trial - / -';
  if (progressPercent) progressPercent.textContent = '0%';

  if (ResultsState.mode === 'wfa') {
    setComparisonLine('');
    updateTableHeader('Stitched OOS', '', getWfaStitchedPeriodLabel(ResultsState.results || []));
    const summary = ResultsState.stitched_oos || ResultsState.summary || {};
    displaySummaryCards(summary);
    if (window.WFAResultsUI) {
      WFAResultsUI.resetState();
      WFAResultsUI.renderWFAResultsTable(
        ResultsState.results || [],
        summary
      );
    } else {
      renderWFATable(ResultsState.results || []);
    }
    const boundaries = calculateWindowBoundaries(ResultsState.results || [], summary);
    renderEquityChart(summary.equity_curve || [], boundaries, summary.timestamps || []);
    renderWindowIndicators(ResultsState.summary?.total_windows || ResultsState.results?.length || 0);
  } else {
    setComparisonLine('');
    const summaryRow = document.querySelector('.summary-row');
    if (summaryRow) summaryRow.style.display = 'none';
    const periodLabel = getActivePeriodLabel();
    if (ResultsState.activeTab === 'forward_test') {
      const sortLabel = formatSortMetricLabel(ResultsState.forwardTest.sortMetric) || 'FT results';
      updateTableHeader('Forward Test', `Sorted by ${sortLabel}`, periodLabel);
      renderForwardTestTable(ResultsState.forwardTest.trials || []);
    } else if (ResultsState.activeTab === 'stress_test') {
      const sortLabel = formatSortMetricLabel(ResultsState.stressTest.sortMetric) || 'retention';
      updateTableHeader('Stress Test', `Sorted by ${sortLabel}`, periodLabel);
      renderStressTestTable(ResultsState.stressTest.trials || []);
    } else if (ResultsState.activeTab === 'oos_test') {
      const sourceLabel = formatSourceLabel(ResultsState.oosTest.source);
      const subtitle = sourceLabel ? `Source: ${sourceLabel}` : 'Source: -';
      updateTableHeader('OOS Test', subtitle, periodLabel);
      renderOosTestTable(ResultsState.oosTest.trials || []);
    } else if (ResultsState.activeTab === 'dsr') {
      updateTableHeader('DSR', 'Sorted by DSR probability', periodLabel);
      renderDsrTable(ResultsState.dsr.trials || []);
    } else if (ResultsState.activeTab === 'manual_tests') {
      const sourceLabel = formatSourceLabel(ResultsState.activeManualTest?.source_tab);
      const subtitle = sourceLabel ? `Source: ${sourceLabel}` : 'Source: -';
      updateTableHeader('Test Results', subtitle, periodLabel);
      renderManualTestTable(ResultsState.manualTestResults || []);
    } else {
      updateTableHeader('Optuna IS', getOptunaSortSubtitle(), periodLabel);
      renderOptunaTable(ResultsState.results || []);
    }
    renderManualTestControls();
  }
}

function bindCollapsibles() {
  document.querySelectorAll('.collapsible-header').forEach((header) => {
    header.addEventListener('click', () => {
      const parent = header.parentElement;
      if (parent) parent.classList.toggle('open');
    });
  });
}

function bindStudiesManager() {
  const selectBtn = document.getElementById('studySelectBtn');
  const deleteBtn = document.getElementById('studyDeleteBtn');

  if (selectBtn) {
    selectBtn.textContent = ResultsState.multiSelect ? 'Cancel' : 'Select';
    selectBtn.classList.toggle('active', ResultsState.multiSelect);
    selectBtn.addEventListener('click', () => {
      ResultsState.multiSelect = !ResultsState.multiSelect;
      if (!ResultsState.multiSelect) {
        ResultsState.selectedStudies = [];
      }
      selectBtn.classList.toggle('active', ResultsState.multiSelect);
      selectBtn.textContent = ResultsState.multiSelect ? 'Cancel' : 'Select';
      loadStudiesList();
    });
  }

  if (deleteBtn) {
    deleteBtn.addEventListener('click', async () => {
      const selected = ResultsState.multiSelect
        ? ResultsState.selectedStudies.slice()
        : (ResultsState.studyId ? [ResultsState.studyId] : []);
      if (!selected.length) {
        alert('Select a study first.');
        return;
      }
      const confirmed = window.confirm(
        selected.length > 1
          ? `Delete ${selected.length} studies? This cannot be undone.`
          : 'Delete this study? This cannot be undone.'
      );
      if (!confirmed) return;
      try {
        for (const studyId of selected) {
          await deleteStudyRequest(studyId);
        }
        ResultsState.studyId = '';
        ResultsState.studyName = '';
        ResultsState.results = [];
        ResultsState.selectedStudies = [];
        refreshResultsView();
        await loadStudiesList();
      } catch (error) {
        alert(error.message || 'Failed to delete study.');
      }
    });
  }
}

function toggleStudySelection(studyId) {
  const selected = new Set(ResultsState.selectedStudies || []);
  if (selected.has(studyId)) {
    selected.delete(studyId);
  } else {
    selected.add(studyId);
  }
  ResultsState.selectedStudies = Array.from(selected);
  loadStudiesList();
}

function openManualTestModal() {
  const modal = document.getElementById('manualTestModal');
  const selectedLabel = document.getElementById('manualSelectedLabel');
  const dataFile = document.getElementById('manualDataFile');
  const dataOriginal = document.getElementById('manualDataOriginal');
  if (selectedLabel) {
    selectedLabel.textContent = ResultsState.selectedRowId
      ? `Trial #${ResultsState.selectedRowId}`
      : 'Trial # -';
  }
  if (dataFile && dataOriginal) {
    dataFile.disabled = dataOriginal.checked;
  }
  if (modal) modal.classList.add('show');
}

function closeManualTestModal() {
  const modal = document.getElementById('manualTestModal');
  if (modal) modal.classList.remove('show');
}

function bindManualDataSourceToggle() {
  const dataOriginal = document.getElementById('manualDataOriginal');
  const dataNew = document.getElementById('manualDataNew');
  const dataFile = document.getElementById('manualDataFile');
  if (!dataFile) return;
  const sync = () => {
    dataFile.disabled = dataOriginal && dataOriginal.checked;
  };
  if (dataOriginal) dataOriginal.addEventListener('change', sync);
  if (dataNew) dataNew.addEventListener('change', sync);
  sync();
}

function getManualTrialNumbers() {
  const topMode = document.getElementById('manualTrialTop');
  const topInput = document.getElementById('manualTopK');
  const selectedMode = document.getElementById('manualTrialSelected');

  if (selectedMode && selectedMode.checked) {
    if (!ResultsState.selectedRowId) return [];
    return [ResultsState.selectedRowId];
  }

  const topK = topInput ? Number(topInput.value) : 0;
  const normalized = Number.isFinite(topK) ? Math.max(1, Math.round(topK)) : 1;
  const trials = getTrialsForActiveTab();
  return trials.slice(0, normalized).map((trial) => trial.trial_number);
}

async function runManualTestFromModal() {
  const dataOriginal = document.getElementById('manualDataOriginal');
  const dataFile = document.getElementById('manualDataFile');
  const startInput = document.getElementById('manualStartDate');
  const endInput = document.getElementById('manualEndDate');

  const dataSource = dataOriginal && dataOriginal.checked ? 'original_csv' : 'new_csv';
  const startDate = startInput ? startInput.value.trim() : '';
  const endDate = endInput ? endInput.value.trim() : '';

  const trialNumbers = getManualTrialNumbers();
  if (!trialNumbers.length) {
    alert('Select at least one trial.');
    return;
  }

  let csvPath = null;
  if (dataSource === 'new_csv') {
    const file = dataFile && dataFile.files && dataFile.files[0];
    if (!file) {
      alert('Select a CSV file for the manual test.');
      return;
    }
    csvPath = file.path || file.name || '';
    if (!csvPath) {
      alert('Unable to resolve CSV path for the selected file.');
      return;
    }
  }

  let sourceTab = 'optuna';
  if (ResultsState.activeTab === 'forward_test') {
    sourceTab = 'forward_test';
  } else if (ResultsState.activeTab === 'dsr') {
    sourceTab = 'dsr';
  } else if (ResultsState.activeTab === 'stress_test') {
    sourceTab = 'stress_test';
  }

  const payload = {
    dataSource,
    csvPath,
    startDate,
    endDate,
    trialNumbers,
    sourceTab
  };

  try {
    await runManualTestRequest(ResultsState.studyId, payload);
    await refreshManualTestsList();
    ResultsState.activeTab = 'manual_tests';
    await ensureManualTestSelection();
    updateTabsVisibility();
    renderManualTestControls();
    refreshResultsView();
    closeManualTestModal();
  } catch (error) {
    alert(error.message || 'Manual test failed.');
  }
}

function bindEventHandlers() {
  const cancelBtn = document.querySelector('.control-btn.cancel');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', async () => {
      try {
        await cancelOptimizationRequest();
      } catch (error) {
        console.warn('Cancel request failed', error);
      }
      ResultsState.status = 'cancelled';
      updateStatusBadge('cancelled');
      localStorage.setItem(OPT_CONTROL_KEY, JSON.stringify({ action: 'cancel', at: Date.now() }));
      updateStoredState({ status: 'cancelled' });
    });
  }

  const pauseBtn = document.querySelector('.control-btn.pause');
  if (pauseBtn) {
    pauseBtn.addEventListener('click', () => {
      alert('Pause functionality coming soon');
    });
  }

  const stopBtn = document.querySelector('.control-btn.stop');
  if (stopBtn) {
    stopBtn.addEventListener('click', () => {
      alert('Stop functionality coming soon');
    });
  }

  const downloadBtn = document.getElementById('downloadTradesBtn');
  if (downloadBtn) {
    downloadBtn.addEventListener('click', async () => {
      if (!ResultsState.studyId) {
        alert('Select a study first.');
        return;
      }
      let endpoint = null;
      let requestOptions = { method: 'POST' };
      if (ResultsState.mode === 'wfa') {
        const selection = ResultsState.wfaSelection || {};
        if (selection.windowNumber) {
          endpoint = `/api/studies/${encodeURIComponent(ResultsState.studyId)}/wfa/windows/${selection.windowNumber}/trades`;
          requestOptions = {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              moduleType: selection.moduleType,
              trialNumber: selection.trialNumber,
              period: selection.period
            })
          };
        } else {
          endpoint = `/api/studies/${encodeURIComponent(ResultsState.studyId)}/wfa/trades`;
        }
      } else {
        const activeTab = ResultsState.activeTab || 'optuna';
        if (activeTab === 'forward_test') {
          if (!ResultsState.selectedRowId) {
            alert('Select a trial in the table.');
            return;
          }
          endpoint = `/api/studies/${encodeURIComponent(ResultsState.studyId)}/trials/${ResultsState.selectedRowId}/ft-trades`;
        } else if (activeTab === 'oos_test') {
          if (!ResultsState.selectedRowId) {
            alert('Select a trial in the table.');
            return;
          }
          endpoint = `/api/studies/${encodeURIComponent(ResultsState.studyId)}/trials/${ResultsState.selectedRowId}/oos-trades`;
        } else if (activeTab === 'manual_tests') {
          if (!ResultsState.activeManualTest || !ResultsState.activeManualTest.id) {
            alert('Select a manual test first.');
            return;
          }
          if (!ResultsState.selectedRowId) {
            alert('Select a trial in the table.');
            return;
          }
          endpoint = `/api/studies/${encodeURIComponent(ResultsState.studyId)}/tests/${ResultsState.activeManualTest.id}/trials/${ResultsState.selectedRowId}/mt-trades`;
        } else {
          if (!ResultsState.selectedRowId) {
            alert('Select a trial in the table.');
            return;
          }
          endpoint = `/api/studies/${encodeURIComponent(ResultsState.studyId)}/trials/${ResultsState.selectedRowId}/trades`;
        }
      }
      try {
        const response = await fetch(endpoint, requestOptions);
        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || 'Trade export failed.');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        const disposition = response.headers.get('Content-Disposition');
        let filename = `trades_${Date.now()}.csv`;
        if (disposition) {
          const match = disposition.match(/filename="?([^";]+)"?/i);
          if (match && match[1]) {
            filename = match[1];
          }
        }
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      } catch (error) {
        alert(error.message || 'Trade export failed.');
      }
    });
  }

  const manualBtn = document.getElementById('manualTestBtn');
  if (manualBtn) {
    manualBtn.addEventListener('click', () => {
      if (!ResultsState.studyId) {
        alert('Select a study first.');
        return;
      }
      openManualTestModal();
    });
  }

  const manualCancel = document.getElementById('manualTestCancel');
  if (manualCancel) {
    manualCancel.addEventListener('click', () => {
      closeManualTestModal();
    });
  }

  const manualRun = document.getElementById('manualTestRun');
  if (manualRun) {
    manualRun.addEventListener('click', async () => {
      await runManualTestFromModal();
    });
  }

  const manualSelect = document.getElementById('manualTestSelect');
  if (manualSelect) {
    manualSelect.addEventListener('change', async () => {
      const testId = manualSelect.value;
      await loadManualTestResultsById(testId);
      renderManualTestControls();
      refreshResultsView();
    });
  }

  const manualDelete = document.getElementById('manualTestDelete');
  if (manualDelete) {
    manualDelete.addEventListener('click', async () => {
      const testId = ResultsState.activeManualTest?.id;
      if (!testId) {
        alert('Select a test to delete.');
        return;
      }
      const confirmed = window.confirm('Delete this manual test? This cannot be undone.');
      if (!confirmed) return;
      try {
        await deleteManualTestRequest(ResultsState.studyId, testId);
        await refreshManualTestsList();
        ResultsState.activeManualTest = null;
        ResultsState.manualTestResults = [];
        await ensureManualTestSelection();
        renderManualTestControls();
        refreshResultsView();
      } catch (error) {
        alert(error.message || 'Failed to delete manual test.');
      }
    });
  }
}

async function hydrateFromServer() {
  try {
    const data = await fetchOptimizationStatus();
    if (!data || !data.status) return;

    const stored = readStoredState();
    const storedUpdated = stored && stored.updated_at ? Date.parse(stored.updated_at) : 0;
    const serverUpdated = data.updated_at ? Date.parse(data.updated_at) : 0;
    const shouldApply = !stored || !storedUpdated || (serverUpdated && serverUpdated >= storedUpdated);

      if (shouldApply) {
        applyState(data);
        if (data.study_id) {
          await openStudy(data.study_id);
        } else {
          refreshResultsView();
        }
      }
  } catch (error) {
    return;
  }
}

function initResultsPage() {
  bindCollapsibles();
  bindStudiesManager();
  bindEventHandlers();
  bindMissingCsvDialog();
  bindTabs();
  bindManualDataSourceToggle();
  bindTableExpandToggle();

  const stored = readStoredState();
  if (stored) {
    applyState(stored);
    refreshResultsView();
  }

  loadStudiesList().then((studies) => {
    const urlStudyId = getQueryStudyId();
    if (urlStudyId) {
      openStudy(urlStudyId);
      return;
    }
    if (stored && (stored.study_id || stored.studyId)) {
      openStudy(stored.study_id || stored.studyId);
      return;
    }
    if (studies && studies.length && studies[0].study_id) {
      openStudy(studies[0].study_id);
    }
  });

  hydrateFromServer();

  window.addEventListener('storage', handleStorageUpdate);
}

// Minimal MD5 implementation (ASCII only)

document.addEventListener('DOMContentLoaded', initResultsPage);
