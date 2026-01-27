const OPT_STATE_KEY = 'merlinOptimizationState';
const OPT_CONTROL_KEY = 'merlinOptimizationControl';

const ResultsState = {
  status: 'idle',
  mode: 'optuna',
  studyId: '',
  studyName: '',
  studyCreatedAt: '',
  strategy: {},
  strategyId: '',
  dataset: {},
  warmupBars: 1000,
  dateFilter: false,
  start: '',
  end: '',
  fixedParams: {},
  strategyConfig: {},
  optuna: {},
  wfa: {},
  summary: {},
  results: [],
  dsr: {
    enabled: false,
    topK: null,
    trials: [],
    nTrials: null,
    meanSharpe: null,
    varSharpe: null
  },
  forwardTest: {
    enabled: false,
    trials: [],
    startDate: '',
    endDate: '',
    periodDays: null,
    sortMetric: 'profit_degradation',
    source: 'optuna'
  },
  stressTest: {
    enabled: false,
    topK: null,
    trials: [],
    sortMetric: 'profit_retention',
    failureThreshold: 0.7,
    avgProfitRetention: null,
    avgRomadRetention: null,
    avgCombinedFailureRate: null,
    candidatesSkippedBadBase: 0,
    candidatesSkippedNoParams: 0,
    candidatesInsufficientData: 0,
    source: 'optuna'
  },
  oosTest: {
    enabled: false,
    topK: null,
    periodDays: null,
    startDate: '',
    endDate: '',
    source: '',
    trials: []
  },
  manualTests: [],
  activeManualTest: null,
  manualTestResults: [],
  activeTab: 'optuna',
  stitched_oos: {},
  dataPath: '',
  selectedRowId: null,
  multiSelect: false,
  selectedStudies: []
};

if (typeof window !== 'undefined') {
  window.ResultsState = ResultsState;
}

const OBJECTIVE_LABELS = {
  net_profit_pct: 'Net Profit %',
  max_drawdown_pct: 'Max DD %',
  sharpe_ratio: 'Sharpe Ratio',
  sortino_ratio: 'Sortino Ratio',
  romad: 'RoMaD',
  profit_factor: 'Profit Factor',
  win_rate: 'Win Rate %',
  max_consecutive_losses: 'Max CL',
  sqn: 'SQN',
  ulcer_index: 'Ulcer Index',
  consistency_score: 'Consistency %',
  composite_score: 'Composite Score'
};

const SORT_METRIC_LABELS = {
  profit_degradation: 'Profit Degradation',
  ft_romad: 'FT RoMaD',
  profit_retention: 'Profit Retention',
  romad_retention: 'RoMaD Retention'
};

const SOURCE_LABELS = {
  optuna: 'Optuna IS',
  dsr: 'DSR',
  forward_test: 'Forward Test',
  stress_test: 'Stress Test',
  oos_test: 'OOS Test',
  manual_tests: 'Manual Test'
};

const TOKEN_LABELS = {
  ft: 'FT',
  st: 'ST',
  is: 'IS',
  oos: 'OOS',
  dsr: 'DSR',
  romad: 'RoMaD',
  pf: 'PF',
  sqn: 'SQN',
  dd: 'DD',
  pnl: 'PnL'
};

const CONSTRAINT_OPERATORS = {
  total_trades: '>=',
  net_profit_pct: '>=',
  max_drawdown_pct: '<=',
  sharpe_ratio: '>=',
  sortino_ratio: '>=',
  romad: '>=',
  profit_factor: '>=',
  win_rate: '>=',
  max_consecutive_losses: '<=',
  sqn: '>=',
  ulcer_index: '<=',
  consistency_score: '>='
};

function readStoredState() {
  const raw = sessionStorage.getItem(OPT_STATE_KEY) || localStorage.getItem(OPT_STATE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (error) {
    return null;
  }
}

function applyState(state) {
  if (!state) return;
  Object.assign(ResultsState, state);
  ResultsState.status = state.status || 'idle';
  ResultsState.mode = state.mode || 'optuna';
  ResultsState.studyId = state.studyId || state.study_id || ResultsState.studyId;
  ResultsState.studyName = state.studyName || state.study_name || ResultsState.studyName;
  ResultsState.strategy = state.strategy || ResultsState.strategy;
  ResultsState.strategyId = state.strategyId || state.strategy_id || ResultsState.strategyId;
  ResultsState.dataset = state.dataset || ResultsState.dataset;
  ResultsState.dataPath = state.dataPath || state.data_path || ResultsState.dataPath;
  ResultsState.warmupBars = state.warmupBars || state.warmup_bars || ResultsState.warmupBars;
  ResultsState.fixedParams = state.fixedParams || ResultsState.fixedParams;
  if ((!ResultsState.fixedParams || Object.keys(ResultsState.fixedParams).length === 0) && state.config) {
    ResultsState.fixedParams = state.config.fixed_params || ResultsState.fixedParams;
  }
  ResultsState.strategyConfig = state.strategyConfig || ResultsState.strategyConfig;
  ResultsState.optuna = state.optuna || ResultsState.optuna;
  ResultsState.wfa = state.wfa || ResultsState.wfa;
  ResultsState.summary = state.summary || ResultsState.summary;
  ResultsState.results = state.results || state.windows || ResultsState.results;
  ResultsState.stitched_oos = state.stitched_oos || ResultsState.stitched_oos;
  ResultsState.dateFilter = Boolean(state.dateFilter ?? ResultsState.dateFilter);
  ResultsState.start = state.start || ResultsState.start;
  ResultsState.end = state.end || ResultsState.end;

  if (!ResultsState.stitched_oos || !ResultsState.stitched_oos.equity_curve) {
    const summary = state.summary || {};
    if (summary && summary.stitched_oos_net_profit_pct !== undefined) {
      ResultsState.stitched_oos = {
        final_net_profit_pct: summary.stitched_oos_net_profit_pct,
        max_drawdown_pct: summary.stitched_oos_max_drawdown_pct,
        total_trades: summary.stitched_oos_total_trades,
        wfe: summary.wfe,
        oos_win_rate: summary.oos_win_rate,
        equity_curve: [],
        timestamps: [],
        window_ids: []
      };
    }
  }
}

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

function getQueryStudyId() {
  const params = new URLSearchParams(window.location.search);
  return params.get('study') || '';
}

function setQueryStudyId(studyId) {
  if (!studyId) return;
  const params = new URLSearchParams(window.location.search);
  params.set('study', studyId);
  const newUrl = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState({}, '', newUrl);
}

function updateResultsHeader() {
  const header = document.querySelector('.results-header h2');
  if (!header) return;
  const runDateLabel = formatDateLabel(ResultsState.studyCreatedAt);
  if (ResultsState.studyName) {
    header.textContent = runDateLabel
      ? `${ResultsState.studyName} · ${runDateLabel}`
      : ResultsState.studyName;
  } else {
    header.textContent = runDateLabel
      ? `Optimization Results · ${runDateLabel}`
      : 'Optimization Results';
  }
}

function updateTableHeader(title, subtitle, periodLabel) {
  const titleEl = document.getElementById('resultsTableTitle');
  const subtitleEl = document.getElementById('resultsTableSubtitle');
  const safeTitle = title || '';
  const safePeriod = periodLabel ? ` · ${periodLabel}` : '';
  if (titleEl) titleEl.textContent = `${safeTitle}${safePeriod}`.trim();
  if (subtitleEl) subtitleEl.textContent = subtitle || '';
}

function setComparisonLine(text) {
  const line = document.getElementById('comparisonLine');
  if (!line) return;
  if (text) {
    line.textContent = text;
    line.style.display = 'flex';
  } else {
    line.textContent = '';
    line.style.display = 'none';
  }
}

function formatSigned(value, digits = 2, suffix = '') {
  const num = Number(value);
  if (!Number.isFinite(num)) return 'N/A';
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(digits)}${suffix}`;
}

function formatRankCell(rank, delta) {
  const baseRank = Number(rank);
  if (!Number.isFinite(baseRank)) return '';
  const change = Number(delta);
  if (!Number.isFinite(change) || change === 0) {
    return `<span class="rank-base">${baseRank}</span>`;
  }
  const direction = change > 0 ? 'up' : 'down';
  const magnitude = Math.abs(Math.round(change));
  const deltaLabel = change > 0 ? `+${magnitude}` : `-${magnitude}`;
  return `<span class="rank-base">${baseRank}</span><span class="rank-delta ${direction}">${deltaLabel}</span>`;
}

function formatDateLabel(value) {
  if (!value) return '';
  const text = String(value).trim();
  if (!text) return '';
  const match = text.match(/(\d{4})[.\-/](\d{2})[.\-/](\d{2})/);
  if (!match) return '';
  return `${match[1]}.${match[2]}.${match[3]}`;
}

function formatDuration(seconds) {
  const totalSeconds = Number(seconds);
  if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return '';
  const rounded = Math.round(totalSeconds);
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const secs = rounded % 60;
  if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

function buildPeriodLabel(startDate, endDate) {
  const startLabel = formatDateLabel(startDate);
  const endLabel = formatDateLabel(endDate);
  if (startLabel && endLabel) {
    return `${startLabel}-${endLabel}`;
  }
  return 'Period: N/A';
}

function getActivePeriodLabel() {
  if (ResultsState.activeTab === 'forward_test') {
    return buildPeriodLabel(ResultsState.forwardTest.startDate, ResultsState.forwardTest.endDate);
  }
  if (ResultsState.activeTab === 'oos_test') {
    return buildPeriodLabel(ResultsState.oosTest.startDate, ResultsState.oosTest.endDate);
  }
  if (ResultsState.activeTab === 'manual_tests') {
    const config = ResultsState.activeManualTest?.config || {};
    return buildPeriodLabel(config.start_date, config.end_date);
  }
  return buildPeriodLabel(ResultsState.start, ResultsState.end);
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
  const windowIds = [];
  let currentBalance = 100.0;

  (windows || []).forEach((window, index) => {
    const equity = window.oos_equity_curve || [];
    if (!equity.length) return;

    const startEquity = equity[0] || 100.0;
    const startIdx = index === 0 ? 0 : 1;

    for (let i = startIdx; i < equity.length; i += 1) {
      const pctChange = (equity[i] / startEquity) - 1.0;
      const newBalance = currentBalance * (1.0 + pctChange);
      stitched.push(newBalance);
      windowIds.push(window.window_number || window.window_id || index + 1);
    }

    if (stitched.length) {
      currentBalance = stitched[stitched.length - 1];
    }
  });

  return { equity_curve: stitched, window_ids: windowIds };
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
      timestamps: [],
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
    primaryObjective: study.primary_objective || optunaConfig.primary_objective || null,
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

function renderManualTestControls() {
  const controls = document.getElementById('testResultsControls');
  const select = document.getElementById('manualTestSelect');
  const baseline = document.getElementById('manualTestBaselineLabel');

  if (!controls || !select) return;

  if (ResultsState.activeTab !== 'manual_tests') {
    controls.style.display = 'none';
    return;
  }

  controls.style.display = 'flex';
  select.innerHTML = '';

  ResultsState.manualTests.forEach((test) => {
    const option = document.createElement('option');
    const dateLabel = test.created_at ? new Date(test.created_at).toLocaleString() : 'Unknown';
    const name = test.test_name ? ` - ${test.test_name}` : '';
    option.value = test.id;
    option.textContent = `#${test.id}${name} (${dateLabel})`;
    if (ResultsState.activeManualTest && ResultsState.activeManualTest.id === test.id) {
      option.selected = true;
    }
    select.appendChild(option);
  });

  if (baseline) {
    baseline.textContent = '';
    baseline.style.display = 'none';
  }
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

function updateStatusBadge(status) {
  const badge = document.getElementById('statusBadge');
  if (!badge) return;
  badge.classList.remove('running', 'paused', 'cancelled');
  if (status === 'running') {
    badge.classList.add('running');
    badge.innerHTML = '<span class="status-dot"></span>Running';
    return;
  }
  if (status === 'paused') {
    badge.classList.add('paused');
    badge.textContent = 'Paused';
    return;
  }
  if (status === 'cancelled') {
    badge.classList.add('cancelled');
    badge.textContent = 'Cancelled';
    return;
  }
  badge.textContent = status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Idle';
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value ?? '-';
}

function setElementVisible(id, visible) {
  const el = document.getElementById(id);
  if (el) el.style.display = visible ? 'block' : 'none';
}

function formatObjectiveLabel(name) {
  return OBJECTIVE_LABELS[name] || name;
}

function formatTitleToken(token) {
  const safe = String(token || '').trim();
  if (!safe) return '';
  const lower = safe.toLowerCase();
  if (TOKEN_LABELS[lower]) return TOKEN_LABELS[lower];
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

function formatTitleFromKey(key) {
  const safe = String(key || '').trim();
  if (!safe) return '';
  return safe
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map(formatTitleToken)
    .join(' ');
}

function formatSortMetricLabel(metric) {
  const safe = String(metric || '').trim().toLowerCase();
  if (!safe) return '';
  return SORT_METRIC_LABELS[safe] || formatTitleFromKey(safe);
}

function formatSourceLabel(source) {
  const safe = String(source || '').trim().toLowerCase();
  if (!safe) return '';
  return SOURCE_LABELS[safe] || formatTitleFromKey(safe);
}

function formatObjectivesList(objectives) {
  if (!objectives || !objectives.length) return '-';
  return objectives.map((obj) => formatObjectiveLabel(obj)).join(', ');
}

function formatConstraintsSummary(constraints) {
  const enabled = (constraints || []).filter((c) => c && c.enabled);
  if (!enabled.length) return 'None';
  return enabled.map((c) => {
    const operator = CONSTRAINT_OPERATORS[c.metric] || '';
    const threshold = c.threshold !== undefined && c.threshold !== null ? c.threshold : '-';
    return `${formatObjectiveLabel(c.metric)} ${operator} ${threshold}`;
  }).join(', ');
}

function getOptunaSortSubtitle() {
  const objectives = ResultsState.optuna.objectives || [];
  if (!objectives.length) return 'Sorted by objectives';
  const primary = ResultsState.optuna.primaryObjective || null;
  const mainObjective = objectives.length > 1 ? (primary || objectives[0]) : objectives[0];
  const label = mainObjective ? formatObjectiveLabel(mainObjective) : '';
  if (!label) return 'Sorted by objectives';
  if (objectives.length > 1) {
    return `Sorted by Primary Objective: ${label}`;
  }
  return `Sorted by Objective: ${label}`;
}

function formatParamName(name) {
  return name.replace(/([A-Z])/g, ' $1').replace(/^./, (s) => s.toUpperCase());
}

function formatParamValue(value) {
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value : value.toFixed(4);
  }
  return value;
}

function createParamId(params, strategyConfig, fixedParams) {
  const merged = { ...(fixedParams || {}), ...(params || {}) };
  const paramStr = stableStringify(merged);
  const hash = md5(paramStr).slice(0, 8);
  const configParams = (strategyConfig && strategyConfig.parameters) || {};
  const optimizable = [];
  Object.entries(configParams).forEach(([name, spec]) => {
    if (spec && spec.optimize && spec.optimize.enabled) {
      optimizable.push(name);
    }
  });
  const preferred = ['maType', 'maLength'];
  const labelKeys = preferred.every((key) => Object.prototype.hasOwnProperty.call(merged, key))
    ? preferred
    : optimizable.slice(0, 2);
  const labelParts = labelKeys.map((key) => {
    const value = Object.prototype.hasOwnProperty.call(merged, key) ? merged[key] : '?';
    return String(value);
  });
  if (labelParts.length) {
    return `${labelParts.join(' ')}_${hash}`;
  }
  return hash;
}

function stableStringify(obj) {
  const keys = Object.keys(obj || {}).sort();
  const ordered = {};
  keys.forEach((key) => {
    ordered[key] = obj[key];
  });
  return JSON.stringify(ordered);
}

function renderOptunaTable(results) {
  const tbody = document.querySelector('.data-table tbody');
  if (!tbody) return;

  tbody.innerHTML = '';

  const thead = document.querySelector('.data-table thead tr');
  const objectives = ResultsState.optuna.objectives || [];
  const constraints = ResultsState.optuna.constraints || [];
  const hasConstraints = constraints.some((c) => c && c.enabled);
  if (thead && window.OptunaResultsUI) {
    thead.innerHTML = window.OptunaResultsUI.buildTrialTableHeaders(objectives, hasConstraints);
  }

  const list = results || [];
  list.forEach((result, index) => {
    const temp = document.createElement('tbody');
    if (window.OptunaResultsUI) {
      temp.innerHTML = window.OptunaResultsUI.renderTrialRow(result, objectives, { hasConstraints }).trim();
    }
    const row = temp.firstElementChild || document.createElement('tr');
    row.className = 'clickable';
    row.dataset.index = index;
    const trialNumber = result.trial_number ?? (index + 1);
    row.dataset.trialNumber = trialNumber;

    const paramId = result.param_id
      || createParamId(result.params || {}, ResultsState.strategyConfig, ResultsState.fixedParams);

    const rankCell = row.querySelector('.rank');
    if (rankCell) rankCell.textContent = index + 1;
    const hashCell = row.querySelector('.param-hash');
    if (hashCell) hashCell.textContent = paramId;

      row.addEventListener('click', async () => {
        selectTableRow(index, trialNumber);
        await showParameterDetails({ ...result, param_id: paramId });
        setComparisonLine('');
        if (result.equity_curve && result.equity_curve.length) {
          renderEquityChart(result.equity_curve, null, result.timestamps);
          return;
        }
        const payload = await fetchEquityCurve(result);
        if (payload && payload.equity && payload.equity.length) {
          renderEquityChart(payload.equity, null, payload.timestamps);
        }
    });

    tbody.appendChild(row);
  });
}

function renderForwardTestTable(results) {
  const tbody = document.querySelector('.data-table tbody');
  if (!tbody) return;

  tbody.innerHTML = '';

  const thead = document.querySelector('.data-table thead tr');
  const objectives = ResultsState.optuna.objectives || [];
  const constraints = ResultsState.optuna.constraints || [];
  const hasConstraints = constraints.some((c) => c && c.enabled);
  if (thead && window.OptunaResultsUI) {
    thead.innerHTML = window.OptunaResultsUI.buildTrialTableHeaders(objectives, hasConstraints);
  }

  const ftSource = ResultsState.forwardTest?.source || 'optuna';
  let sourceRankMap = {};
  if (ftSource === 'dsr') {
    sourceRankMap = buildRankMapFromKey(ResultsState.results || [], 'dsr_rank');
  } else {
    (ResultsState.results || []).forEach((trial, idx) => {
      if (trial.trial_number !== undefined) {
        sourceRankMap[trial.trial_number] = idx + 1;
      }
    });
  }

  (results || []).forEach((trial, index) => {
    const mapped = {
      ...trial,
      net_profit_pct: trial.ft_net_profit_pct,
      max_drawdown_pct: trial.ft_max_drawdown_pct,
      total_trades: trial.ft_total_trades,
      win_rate: trial.ft_win_rate,
      max_consecutive_losses: trial.ft_max_consecutive_losses,
      sharpe_ratio: trial.ft_sharpe_ratio,
      sortino_ratio: trial.ft_sortino_ratio,
      romad: trial.ft_romad,
      profit_factor: trial.ft_profit_factor,
      ulcer_index: trial.ft_ulcer_index,
      sqn: trial.ft_sqn,
      consistency_score: trial.ft_consistency_score,
      score: null
    };

    const temp = document.createElement('tbody');
    if (window.OptunaResultsUI) {
      temp.innerHTML = window.OptunaResultsUI.renderTrialRow(mapped, objectives, { hasConstraints }).trim();
    }
    const row = temp.firstElementChild || document.createElement('tr');
    row.className = 'clickable';
    row.dataset.index = index;
    const trialNumber = trial.trial_number ?? (index + 1);
    row.dataset.trialNumber = trialNumber;

    const paramId = trial.param_id
      || createParamId(trial.params || {}, ResultsState.strategyConfig, ResultsState.fixedParams);

    const rankCell = row.querySelector('.rank');
    const displayedRank = trial.ft_rank || index + 1;
    const sourceRank = sourceRankMap[trialNumber];
    const rankChange = sourceRank != null ? sourceRank - displayedRank : null;
    if (rankCell) rankCell.innerHTML = formatRankCell(displayedRank, rankChange);
    const hashCell = row.querySelector('.param-hash');
    if (hashCell) hashCell.textContent = paramId;

    row.addEventListener('click', async () => {
      selectTableRow(index, trialNumber);
      await showParameterDetails({ ...trial, param_id: paramId });

      const comparison = window.PostProcessUI
        ? window.PostProcessUI.buildComparisonMetrics(trial)
        : null;
      const rankSourceLabel = ftSource === 'dsr' ? 'DSR' : 'Optuna';

      if (comparison) {
        const line = [
          rankChange !== null ? `Rank: ${formatSigned(rankChange, 0)} (vs ${rankSourceLabel})` : null,
          `Profit Deg: ${formatSigned(comparison.profit_degradation || 0, 2)}`,
          `Max DD: ${formatSigned(comparison.max_dd_change || 0, 2, '%')}`,
          `ROMAD: ${formatSigned(comparison.romad_change || 0, 2)}`,
          `Sharpe: ${formatSigned(comparison.sharpe_change || 0, 2)}`,
          `PF: ${formatSigned(comparison.pf_change || 0, 2)}`
        ].filter(Boolean).join(' | ');
        setComparisonLine(line);
      }

      const equity = await fetchEquityCurve(trial, {
        start: ResultsState.forwardTest.startDate,
        end: ResultsState.forwardTest.endDate
      });
      if (equity && equity.equity && equity.equity.length) {
        renderEquityChart(equity.equity, null, equity.timestamps);
      }
    });

    tbody.appendChild(row);
  });
}

function renderDsrTable(results) {
  const tbody = document.querySelector('.data-table tbody');
  if (!tbody) return;

  tbody.innerHTML = '';

  const thead = document.querySelector('.data-table thead tr');
  const objectives = ResultsState.optuna.objectives || [];
  const constraints = ResultsState.optuna.constraints || [];
  const hasConstraints = constraints.some((c) => c && c.enabled);
  if (thead && window.OptunaResultsUI) {
    thead.innerHTML = window.OptunaResultsUI.buildTrialTableHeaders(objectives, hasConstraints);
  }

  const optunaRankMap = {};
  (ResultsState.results || []).forEach((trial, idx) => {
    if (trial.trial_number !== undefined) {
      optunaRankMap[trial.trial_number] = idx + 1;
    }
  });

  (results || []).forEach((trial, index) => {
    const temp = document.createElement('tbody');
    if (window.OptunaResultsUI) {
      temp.innerHTML = window.OptunaResultsUI.renderTrialRow(trial, objectives, { hasConstraints }).trim();
    }
    const row = temp.firstElementChild || document.createElement('tr');
    row.className = 'clickable';
    row.dataset.index = index;
    const trialNumber = trial.trial_number ?? (index + 1);
    row.dataset.trialNumber = trialNumber;

    const paramId = trial.param_id
      || createParamId(trial.params || {}, ResultsState.strategyConfig, ResultsState.fixedParams);

    const rankCell = row.querySelector('.rank');
    const dsrRank = trial.dsr_rank || index + 1;
    const optunaRank = optunaRankMap[trialNumber];
    const rankDelta = optunaRank != null ? (optunaRank - dsrRank) : null;
    if (rankCell) rankCell.innerHTML = formatRankCell(dsrRank, rankDelta);
    const hashCell = row.querySelector('.param-hash');
    if (hashCell) hashCell.textContent = paramId;

    row.addEventListener('click', async () => {
      selectTableRow(index, trialNumber);
      await showParameterDetails({ ...trial, param_id: paramId });

      const rankLine = rankDelta !== null ? `Rank: ${formatSigned(rankDelta, 0)}` : null;

      const dsrValue = Number(trial.dsr_probability);
      const dsrLabel = Number.isFinite(dsrValue) ? dsrValue.toFixed(3) : 'N/A';
      const luckValue = Number(trial.dsr_luck_share_pct);
      const luckLabel = Number.isFinite(luckValue) ? `${luckValue.toFixed(1)}%` : 'N/A';

      const line = [
        rankLine,
        `DSR: ${dsrLabel}`,
        `Luck: ${luckLabel}`
      ].filter(Boolean).join(' | ');
      setComparisonLine(line);

      const equity = await fetchEquityCurve(trial);
      if (equity && equity.equity && equity.equity.length) {
        renderEquityChart(equity.equity, null, equity.timestamps);
      }
    });

    tbody.appendChild(row);
  });
}

function renderStressTestTable(results) {
  const tbody = document.querySelector('.data-table tbody');
  if (!tbody) return;

  tbody.innerHTML = '';

  const thead = document.querySelector('.data-table thead tr');
  const objectives = ResultsState.optuna.objectives || [];
  const constraints = ResultsState.optuna.constraints || [];
  const hasConstraints = constraints.some((c) => c && c.enabled);
  if (thead && window.OptunaResultsUI) {
    thead.innerHTML = window.OptunaResultsUI.buildTrialTableHeaders(objectives, hasConstraints);
  }

  const stSource = ResultsState.stressTest?.source || 'optuna';
  let sourceRankMap = {};
  if (stSource === 'ft') {
    sourceRankMap = buildRankMapFromKey(ResultsState.results || [], 'ft_rank');
  } else if (stSource === 'dsr') {
    sourceRankMap = buildRankMapFromKey(ResultsState.results || [], 'dsr_rank');
  } else {
    (ResultsState.results || []).forEach((trial, idx) => {
      if (trial.trial_number !== undefined) {
        sourceRankMap[trial.trial_number] = idx + 1;
      }
    });
  }

  (results || []).forEach((trial, index) => {
    const temp = document.createElement('tbody');
    if (window.OptunaResultsUI) {
      temp.innerHTML = window.OptunaResultsUI.renderTrialRow(trial, objectives, { hasConstraints }).trim();
    }
    const row = temp.firstElementChild || document.createElement('tr');
    row.className = 'clickable';
    row.dataset.index = index;
    const trialNumber = trial.trial_number ?? (index + 1);
    row.dataset.trialNumber = trialNumber;

    const paramId = trial.param_id
      || createParamId(trial.params || {}, ResultsState.strategyConfig, ResultsState.fixedParams);

    const stRank = trial.st_rank || index + 1;
    const rankCell = row.querySelector('.rank');
    const sourceRank = sourceRankMap[trialNumber];
    const rankDelta = sourceRank != null ? (sourceRank - stRank) : null;
    if (rankCell) rankCell.innerHTML = formatRankCell(stRank, rankDelta);
    const hashCell = row.querySelector('.param-hash');
    if (hashCell) {
      hashCell.textContent = paramId;
      if (trial.st_status && trial.st_status !== 'ok') {
        hashCell.classList.add('param-hash-warning');
      }
    }

    row.addEventListener('click', async () => {
      selectTableRow(index, trialNumber);
      await showParameterDetails({ ...trial, param_id: paramId });

      const rankSourceLabel = stSource === 'ft' ? 'FT' : (stSource === 'dsr' ? 'DSR' : 'Optuna');

      if (trial.st_status === 'skipped_bad_base') {
        const baseProfit = Number((trial.base_net_profit_pct ?? trial.net_profit_pct) || 0);
        const line = `Status: Bad Base (profit <= 0%) | Base Profit: ${baseProfit.toFixed(1)}%`;
        setComparisonLine(line);
      } else if (trial.st_status === 'insufficient_data') {
        const totalPerturbations = Number(trial.total_perturbations || 0);
        const combinedFailures = Number(trial.combined_failure_count || 0);
        const validNeighbors = totalPerturbations - combinedFailures;
        const line = `Status: Insufficient Data (${validNeighbors} valid neighbors, minimum 4 required) | Profit Ret: N/A | RoMaD Ret: N/A`;
        setComparisonLine(line);
      } else if (trial.st_status === 'skipped_no_params') {
        const line = 'Status: No Testable Parameters (strategy has only categorical params)';
        setComparisonLine(line);
      } else {
        const rankLine = rankDelta !== null ? `Rank: ${formatSigned(rankDelta, 0)} (vs ${rankSourceLabel})` : null;

        const profitRet = trial.profit_retention;
        const profitRetLabel = profitRet !== null && profitRet !== undefined
          ? `${(profitRet * 100).toFixed(1)}%`
          : 'N/A';

        const romadRet = trial.romad_retention;
        const romadRetLabel = romadRet !== null && romadRet !== undefined
          ? `${(romadRet * 100).toFixed(1)}%`
          : 'N/A';

        const failRate = trial.combined_failure_rate;
        const failRateLabel = failRate !== null && failRate !== undefined
          ? `${(failRate * 100).toFixed(1)}%`
          : 'N/A';

        const romadValid = trial.romad_failure_rate !== null && trial.romad_failure_rate !== undefined;
        const failRateType = romadValid ? 'Fail' : 'Fail (profit)';

        const sensParam = trial.most_sensitive_param || null;
        const sensLine = sensParam ? `Sens: ${sensParam}` : null;

        const line = [
          rankLine,
          `Profit Ret: ${profitRetLabel}`,
          `RoMaD Ret: ${romadRetLabel}`,
          `${failRateType}: ${failRateLabel}`,
          sensLine
        ].filter(Boolean).join(' | ');
        setComparisonLine(line);
      }

      const equity = await fetchEquityCurve(trial);
      if (equity && equity.equity && equity.equity.length) {
        renderEquityChart(equity.equity, null, equity.timestamps);
      }
    });

    tbody.appendChild(row);
  });
}

function renderOosTestTable(results) {
  const tbody = document.querySelector('.data-table tbody');
  if (!tbody) return;

  tbody.innerHTML = '';

  const thead = document.querySelector('.data-table thead tr');
  const objectives = ResultsState.optuna.objectives || [];
  const constraints = ResultsState.optuna.constraints || [];
  const hasConstraints = constraints.some((c) => c && c.enabled);
  if (thead && window.OptunaResultsUI) {
    thead.innerHTML = window.OptunaResultsUI.buildTrialTableHeaders(objectives, hasConstraints);
  }

  (results || []).forEach((trial, index) => {
    const source = trial.oos_test_source || ResultsState.oosTest.source || '';
    const baseMetrics = source === 'forward_test'
      ? {
        net_profit_pct: trial.ft_net_profit_pct,
        max_drawdown_pct: trial.ft_max_drawdown_pct,
        romad: trial.ft_romad,
        sharpe_ratio: trial.ft_sharpe_ratio,
        profit_factor: trial.ft_profit_factor
      }
      : {
        net_profit_pct: trial.net_profit_pct,
        max_drawdown_pct: trial.max_drawdown_pct,
        romad: trial.romad,
        sharpe_ratio: trial.sharpe_ratio,
        profit_factor: trial.profit_factor
      };

    const metrics = {
      net_profit_pct: trial.oos_test_net_profit_pct,
      max_drawdown_pct: trial.oos_test_max_drawdown_pct,
      total_trades: trial.oos_test_total_trades,
      win_rate: trial.oos_test_win_rate,
      max_consecutive_losses: trial.oos_test_max_consecutive_losses,
      sharpe_ratio: trial.oos_test_sharpe_ratio,
      sortino_ratio: trial.oos_test_sortino_ratio,
      romad: trial.oos_test_romad,
      profit_factor: trial.oos_test_profit_factor,
      ulcer_index: trial.oos_test_ulcer_index,
      sqn: trial.oos_test_sqn,
      consistency_score: trial.oos_test_consistency_score,
      score: null
    };
    const mapped = { ...trial, ...metrics };

    const temp = document.createElement('tbody');
    if (window.OptunaResultsUI) {
      temp.innerHTML = window.OptunaResultsUI.renderTrialRow(mapped, objectives, { hasConstraints }).trim();
    }
    const row = temp.firstElementChild || document.createElement('tr');
    row.className = 'clickable';
    row.dataset.index = index;
    row.dataset.trialNumber = trial.trial_number;

    const paramId = trial.param_id
      || createParamId(trial.params || {}, ResultsState.strategyConfig, ResultsState.fixedParams);

    const rankCell = row.querySelector('.rank');
    if (rankCell) rankCell.textContent = trial.oos_test_source_rank || index + 1;
    const hashCell = row.querySelector('.param-hash');
    if (hashCell) hashCell.textContent = paramId;

    row.addEventListener('click', async () => {
      selectTableRow(index, trial.trial_number);
      await showParameterDetails({ ...trial, param_id: paramId });

      const profitDeg = trial.oos_test_profit_degradation;
      const maxDdChange = Number(metrics.max_drawdown_pct || 0) - Number(baseMetrics.max_drawdown_pct || 0);
      const romadChange = Number(metrics.romad || 0) - Number(baseMetrics.romad || 0);
      const sharpeChange = Number(metrics.sharpe_ratio || 0) - Number(baseMetrics.sharpe_ratio || 0);
      const pfChange = Number(metrics.profit_factor || 0) - Number(baseMetrics.profit_factor || 0);

      const line = [
        profitDeg !== null && profitDeg !== undefined ? `Profit Deg: ${formatSigned(profitDeg, 2)}` : null,
        `Max DD: ${formatSigned(maxDdChange || 0, 2, '%')}`,
        `ROMAD: ${formatSigned(romadChange || 0, 2)}`,
        `Sharpe: ${formatSigned(sharpeChange || 0, 2)}`,
        `PF: ${formatSigned(pfChange || 0, 2)}`
      ].filter(Boolean).join(' | ');
      setComparisonLine(line);

      if (ResultsState.oosTest.startDate && ResultsState.oosTest.endDate) {
        const equity = await fetchEquityCurve(trial, {
          start: ResultsState.oosTest.startDate,
          end: ResultsState.oosTest.endDate
        });
        if (equity && equity.equity && equity.equity.length) {
          renderEquityChart(equity.equity, null, equity.timestamps);
        }
      }
    });

    tbody.appendChild(row);
  });
}

function renderManualTestTable(results) {
  const tbody = document.querySelector('.data-table tbody');
  if (!tbody) return;

  tbody.innerHTML = '';

  const thead = document.querySelector('.data-table thead tr');
  const objectives = ResultsState.optuna.objectives || [];
  const constraints = ResultsState.optuna.constraints || [];
  const hasConstraints = constraints.some((c) => c && c.enabled);
  if (thead && window.OptunaResultsUI) {
    thead.innerHTML = window.OptunaResultsUI.buildTrialTableHeaders(objectives, hasConstraints);
  }

  const trialMap = {};
  (ResultsState.results || []).forEach((trial) => {
    if (trial.trial_number !== undefined) {
      trialMap[trial.trial_number] = trial;
    }
  });

  (results || []).forEach((entry, index) => {
    const trialNumber = entry.trial_number;
    const baseTrial = trialMap[trialNumber] || {};
    const metrics = entry.test_metrics || {};
    const mapped = {
      ...baseTrial,
      net_profit_pct: metrics.net_profit_pct,
      max_drawdown_pct: metrics.max_drawdown_pct,
      total_trades: metrics.total_trades,
      win_rate: metrics.win_rate,
      max_consecutive_losses: metrics.max_consecutive_losses,
      sharpe_ratio: metrics.sharpe_ratio,
      sortino_ratio: metrics.sortino_ratio,
      romad: metrics.romad,
      profit_factor: metrics.profit_factor,
      ulcer_index: metrics.ulcer_index,
      sqn: metrics.sqn,
      consistency_score: metrics.consistency_score,
      score: null
    };

    const temp = document.createElement('tbody');
    if (window.OptunaResultsUI) {
      temp.innerHTML = window.OptunaResultsUI.renderTrialRow(mapped, objectives, { hasConstraints }).trim();
    }
    const row = temp.firstElementChild || document.createElement('tr');
    row.className = 'clickable';
    row.dataset.index = index;
    row.dataset.trialNumber = trialNumber;

    const paramId = baseTrial.param_id
      || createParamId(baseTrial.params || {}, ResultsState.strategyConfig, ResultsState.fixedParams);

    const rankCell = row.querySelector('.rank');
    if (rankCell) rankCell.textContent = index + 1;
    const hashCell = row.querySelector('.param-hash');
    if (hashCell) hashCell.textContent = paramId;

    row.addEventListener('click', async () => {
      selectTableRow(index, trialNumber);
      await showParameterDetails({ ...baseTrial, param_id: paramId });

      const comparison = entry.comparison || {};
      const line = [
        `Profit Deg: ${formatSigned(comparison.profit_degradation || 0, 2)}`,
        `Max DD: ${formatSigned(comparison.max_dd_change || 0, 2, '%')}`,
        `ROMAD: ${formatSigned(comparison.romad_change || 0, 2)}`,
        `Sharpe: ${formatSigned(comparison.sharpe_change || 0, 2)}`,
        `PF: ${formatSigned(comparison.pf_change || 0, 2)}`
      ].filter(Boolean).join(' | ');
      setComparisonLine(line);

      if (ResultsState.activeManualTest && ResultsState.activeManualTest.config) {
        const config = ResultsState.activeManualTest.config;
        const equity = await fetchEquityCurve(baseTrial, {
          start: config.start_date,
          end: config.end_date
        });
        if (equity && equity.equity && equity.equity.length) {
          renderEquityChart(equity.equity, null, equity.timestamps);
        }
      }
    });

    tbody.appendChild(row);
  });
}

function renderWFATable(windows) {
  const tbody = document.querySelector('.data-table tbody');
  if (!tbody) return;

  tbody.innerHTML = '';

  const thead = document.querySelector('.data-table thead tr');
  if (thead) {
    thead.innerHTML = `
      <th>#</th>
      <th>Param ID</th>
      <th>IS Profit %</th>
      <th>OOS Profit %</th>
      <th>IS Trades</th>
      <th>OOS Trades</th>
      <th>OOS DD %</th>
    `;
  }

  (windows || []).forEach((window, index) => {
    const row = document.createElement('tr');
    row.className = 'clickable';
    row.dataset.index = index;
    row.dataset.windowNumber = window.window_number || index + 1;

    row.innerHTML = `
      <td class="rank">${window.window_number || index + 1}</td>
      <td class="param-hash">${window.param_id}</td>
      <td class="${window.is_net_profit_pct >= 0 ? 'val-positive' : 'val-negative'}">
        ${window.is_net_profit_pct >= 0 ? '+' : ''}${Number(window.is_net_profit_pct || 0).toFixed(2)}%
      </td>
      <td class="${window.oos_net_profit_pct >= 0 ? 'val-positive' : 'val-negative'}">
        ${window.oos_net_profit_pct >= 0 ? '+' : ''}${Number(window.oos_net_profit_pct || 0).toFixed(2)}%
      </td>
      <td>${window.is_total_trades ?? '-'}</td>
      <td>${window.oos_total_trades ?? '-'}</td>
      <td class="val-negative">-${Math.abs(Number(window.oos_max_drawdown_pct || 0)).toFixed(2)}%</td>
    `;

      row.addEventListener('click', async () => {
        const windowNumber = window.window_number || window.window_id || index + 1;
        selectTableRow(index, windowNumber);
        await showParameterDetails(window);
        setComparisonLine('');
      });

    tbody.appendChild(row);
  });
}

function selectTableRow(index, rowId) {
  document.querySelectorAll('.data-table tr.clickable').forEach((row) => {
    row.classList.remove('selected');
  });
  const rows = document.querySelectorAll('.data-table tr.clickable');
  if (rows[index]) {
    rows[index].classList.add('selected');
  }
  ResultsState.selectedRowId = rowId;
}

async function showParameterDetails(result) {
  const section = document.getElementById('paramDetailsSection');
  const title = document.getElementById('paramDetailsTitle');
  const content = document.getElementById('paramDetailsContent');

  if (!section || !content) return;

  if ((!ResultsState.strategyConfig || !ResultsState.strategyConfig.parameters) && ResultsState.strategyId) {
    try {
      ResultsState.strategyConfig = await fetchStrategyConfig(ResultsState.strategyId);
    } catch (error) {
      console.warn('Failed to load strategy config for parameter ordering', error);
    }
  }

  const label = result.param_id
    || createParamId(result.params || result.best_params || {}, ResultsState.strategyConfig, ResultsState.fixedParams);
  if (title) {
    title.textContent = `Parameters: ${label}`;
  }

  const params = result.params || result.best_params || {};
  content.innerHTML = '';

  const orderedKeys = getParamDisplayOrder(params, ResultsState.strategyConfig);
  const paramDefs = ResultsState.strategyConfig?.parameters || {};
  const groupOrder = ResultsState.strategyConfig?.group_order || [];
  const groups = {};

  orderedKeys.forEach((key) => {
    if (['dateFilter', 'start', 'end'].includes(key)) return;
    const def = paramDefs[key];
    const group = (def && def.group) || 'Other';
    if (!groups[group]) {
      groups[group] = [];
    }
    groups[group].push({ key, value: params[key], def });
  });

  const orderedGroups = [];
  groupOrder.forEach((group) => {
    if (groups[group] && groups[group].length) {
      orderedGroups.push(group);
    }
  });
  Object.keys(groups).forEach((group) => {
    if (!orderedGroups.includes(group)) {
      orderedGroups.push(group);
    }
  });

  orderedGroups.forEach((group) => {
    const items = groups[group] || [];
    if (!items.length) return;
    const card = document.createElement('div');
    card.className = 'param-group-card';

    const header = document.createElement('div');
    header.className = 'param-group-title';
    header.textContent = group;
    card.appendChild(header);

    items.forEach(({ key, value, def }) => {
      const formattedValue = formatParamValue(value);
      const labelText = (def && def.label) ? def.label : formatParamName(key);
      const optimized = def && def.optimize && def.optimize.enabled === true;
      const item = document.createElement('div');
      item.className = `param-item${optimized ? '' : ' param-fixed'}`;

      const nameEl = document.createElement('span');
      nameEl.className = 'param-item-name';
      nameEl.textContent = labelText;

      const valueEl = document.createElement('span');
      valueEl.className = 'param-item-value';
      valueEl.textContent = formattedValue;

      const copyHandler = () => {
        copyParamValue(formattedValue);
        highlightParamItem(item);
      };
      nameEl.addEventListener('click', copyHandler);
      valueEl.addEventListener('click', copyHandler);

      item.appendChild(nameEl);
      item.appendChild(valueEl);
      card.appendChild(item);
    });

    content.appendChild(card);
  });

  section.classList.add('show');
}

function getParamDisplayOrder(params, strategyConfig) {
  const configParams = strategyConfig?.parameters || {};
  const configKeys = strategyConfig?.parameter_order || Object.keys(configParams);
  const paramsKeys = Object.keys(params || {});
  const ordered = [];
  const seen = new Set();

  configKeys.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(params, key)) {
      ordered.push(key);
      seen.add(key);
    }
  });

  paramsKeys.forEach((key) => {
    if (!seen.has(key)) {
      ordered.push(key);
    }
  });

  return ordered;
}

function copyParamValue(value) {
  const text = value === undefined || value === null ? '' : String(value);
  if (!text) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).catch(() => {});
    return;
  }
  const temp = document.createElement('textarea');
  temp.value = text;
  temp.setAttribute('readonly', '');
  temp.style.position = 'absolute';
  temp.style.left = '-9999px';
  document.body.appendChild(temp);
  temp.select();
  try {
    document.execCommand('copy');
  } catch (error) {
    // ignore
  }
  document.body.removeChild(temp);
}

function highlightParamItem(item) {
  if (!item) return;
  item.classList.add('copied');
  window.setTimeout(() => {
    item.classList.remove('copied');
  }, 800);
}

function renderEquityChart(equityData, windowBoundaries = null, timestamps = null) {
  const svg = document.querySelector('.chart-svg');
  const axis = document.getElementById('equityAxis');
  if (!svg || !equityData || equityData.length === 0) return;

  const width = 800;
  const height = 260;
  const padding = 20;

  const baseValue = 100.0;
  const minValue = Math.min(...equityData, baseValue);
  const maxValue = Math.max(...equityData, baseValue);
  const valueRange = maxValue - minValue || 1;

  svg.innerHTML = '';
  if (axis) {
    axis.innerHTML = '';
  }

  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  bg.setAttribute('width', '100%');
  bg.setAttribute('height', '100%');
  bg.setAttribute('fill', '#fafafa');
  svg.appendChild(bg);

  const baseY = height - padding - ((baseValue - minValue) / valueRange) * (height - 2 * padding);
  const baseLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  baseLine.setAttribute('x1', 0);
  baseLine.setAttribute('y1', baseY);
  baseLine.setAttribute('x2', width);
  baseLine.setAttribute('y2', baseY);
  baseLine.setAttribute('stroke', '#c8c8c8');
  baseLine.setAttribute('stroke-width', '1');
  baseLine.setAttribute('stroke-dasharray', '3 4');
  svg.appendChild(baseLine);

  if (windowBoundaries && windowBoundaries.length > 0) {
    windowBoundaries.forEach((boundary, index) => {
      const x = (boundary.index / (equityData.length - 1)) * width;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x);
      line.setAttribute('y1', 0);
      line.setAttribute('x2', x);
      line.setAttribute('y2', height);
      line.setAttribute('stroke', '#e0e0e0');
      line.setAttribute('stroke-width', '1');
      line.setAttribute('stroke-dasharray', '4');
      svg.appendChild(line);

      const labelX = index < windowBoundaries.length - 1
        ? (x + (windowBoundaries[index + 1].index / (equityData.length - 1)) * width) / 2
        : x + 40;

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', labelX);
      text.setAttribute('y', 20);
      text.setAttribute('font-size', '10');
      text.setAttribute('fill', '#999');
      text.setAttribute('text-anchor', 'middle');
      text.textContent = `W${index + 1}`;
      svg.appendChild(text);
    });
  }

  if (Array.isArray(timestamps) && timestamps.length === equityData.length && axis) {
    const startDate = new Date(timestamps[0]);
    const endDate = new Date(timestamps[timestamps.length - 1]);
    if (!Number.isNaN(startDate.getTime()) && !Number.isNaN(endDate.getTime())) {
      const tickCount = Math.min(5, equityData.length);
      if (tickCount >= 2) {
        for (let i = 0; i < tickCount; i += 1) {
          const ratio = tickCount === 1 ? 0 : i / (tickCount - 1);
          const index = Math.round(ratio * (equityData.length - 1));
          const tickDate = new Date(timestamps[index]);
          if (Number.isNaN(tickDate.getTime())) continue;
          const xPct = (index / (equityData.length - 1)) * 100;
          const x = (index / (equityData.length - 1)) * width;

          const grid = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          grid.setAttribute('x1', x);
          grid.setAttribute('y1', 0);
          grid.setAttribute('x2', x);
          grid.setAttribute('y2', height);
          grid.setAttribute('stroke', '#e3e3e3');
          grid.setAttribute('stroke-width', '1');
          svg.appendChild(grid);

          const m = String(tickDate.getUTCMonth() + 1).padStart(2, '0');
          const d = String(tickDate.getUTCDate()).padStart(2, '0');
          const label = `${m}.${d}`;

          const text = document.createElement('div');
          let labelClass = 'chart-axis-label';
          if (i === 0) {
            labelClass += ' start';
          } else if (i === tickCount - 1) {
            labelClass += ' end';
          }
          text.className = labelClass;
          text.style.left = `${xPct}%`;
          text.textContent = label;
          axis.appendChild(text);
        }
      }
    }
  }

  const points = equityData.map((value, index) => {
    const x = (index / (equityData.length - 1)) * width;
    const y = height - padding - ((value - minValue) / valueRange) * (height - 2 * padding);
    return `${x},${y}`;
  }).join(' ');

  const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  polyline.setAttribute('points', points);
  polyline.setAttribute('fill', 'none');
  polyline.setAttribute('stroke', '#4a90e2');
  polyline.setAttribute('stroke-width', '1.5');
  svg.appendChild(polyline);
}

function calculateWindowBoundaries(windows, stitchedOOS) {
  if (!windows || !stitchedOOS || !stitchedOOS.window_ids) return [];
  const boundaries = [];
  let lastWindowId = null;
  stitchedOOS.window_ids.forEach((windowId, index) => {
    if (windowId !== lastWindowId) {
      boundaries.push({ index, windowId });
      lastWindowId = windowId;
    }
  });
  return boundaries;
}

function displaySummaryCards(stitchedOOS) {
  const container = document.querySelector('.summary-row');
  if (!container) return;

  container.innerHTML = `
    <div class="summary-card highlight">
      <div class="value ${stitchedOOS.final_net_profit_pct >= 0 ? 'positive' : 'negative'}">
        ${stitchedOOS.final_net_profit_pct >= 0 ? '+' : ''}${Number(stitchedOOS.final_net_profit_pct || 0).toFixed(2)}%
      </div>
      <div class="label">Net Profit</div>
    </div>
    <div class="summary-card">
      <div class="value negative">-${Math.abs(Number(stitchedOOS.max_drawdown_pct || 0)).toFixed(2)}%</div>
      <div class="label">Max Drawdown</div>
    </div>
    <div class="summary-card">
      <div class="value">${stitchedOOS.total_trades ?? 0}</div>
      <div class="label">Total Trades</div>
    </div>
    <div class="summary-card">
      <div class="value">${Number(stitchedOOS.wfe || 0).toFixed(1)}%</div>
      <div class="label">WFE</div>
    </div>
    <div class="summary-card">
      <div class="value">${Number(stitchedOOS.oos_win_rate || 0).toFixed(1)}%</div>
      <div class="label">Win Rate</div>
    </div>
  `;

  container.style.display = 'grid';
}

function updateSidebarSettings() {
  setText('optuna-objectives', formatObjectivesList(ResultsState.optuna.objectives || []));
  setText('optuna-primary', ResultsState.optuna.primaryObjective ? formatObjectiveLabel(ResultsState.optuna.primaryObjective) : '-');
  setText('optuna-constraints', formatConstraintsSummary(ResultsState.optuna.constraints || []));
  const budgetMode = ResultsState.optuna.budgetMode || '';
  let budgetLabel = '-';
  if (budgetMode === 'trials') {
    budgetLabel = `${ResultsState.optuna.nTrials || 0} trials`;
  } else if (budgetMode === 'time') {
    const minutes = Math.round((ResultsState.optuna.timeLimit || 0) / 60);
    budgetLabel = `${minutes} min`;
  } else if (budgetMode === 'convergence') {
    budgetLabel = `No improvement ${ResultsState.optuna.convergence || 0} trials`;
  }
  setText('optuna-budget', budgetLabel);
  setText('optuna-sampler', (ResultsState.optuna.sampler || '').toUpperCase() || '-');
  setText('optuna-pruner', ResultsState.optuna.pruner ? ResultsState.optuna.pruner : '-');
  const sanitizeEnabled = ResultsState.optuna.sanitizeEnabled;
  const sanitizeThresholdRaw = ResultsState.optuna.sanitizeTradesThreshold;
  const sanitizeThreshold = Number.isFinite(Number(sanitizeThresholdRaw))
    ? Math.max(0, Math.round(Number(sanitizeThresholdRaw)))
    : 0;
  let sanitizeLabel = '-';
  if (sanitizeEnabled === true) {
    sanitizeLabel = `On (<= ${sanitizeThreshold})`;
  } else if (sanitizeEnabled === false) {
    sanitizeLabel = 'Off';
  }
  setText('optuna-sanitize', sanitizeLabel);
  const filterMinProfit = ResultsState.optuna.filterMinProfit;
  const minProfitThresholdRaw = ResultsState.optuna.minProfitThreshold;
  const minProfitThreshold = Number.isFinite(Number(minProfitThresholdRaw))
    ? Math.max(0, Math.round(Number(minProfitThresholdRaw)))
    : null;
  const scoreFilterEnabled = ResultsState.optuna.scoreFilterEnabled;
  const scoreThresholdRaw = ResultsState.optuna.scoreThreshold;
  const scoreThreshold = Number.isFinite(Number(scoreThresholdRaw))
    ? Math.max(0, Math.round(Number(scoreThresholdRaw)))
    : null;
  const filterParts = [];
  if (filterMinProfit) {
    filterParts.push(`Net Profit = ${minProfitThreshold !== null ? minProfitThreshold : 0}`);
  }
  if (scoreFilterEnabled) {
    filterParts.push(`Score = ${scoreThreshold !== null ? scoreThreshold : 0}`);
  }
  const filterLabel = filterParts.length ? filterParts.join(', ') : 'Off';
  setText('optuna-filter', filterLabel);
  setText('optuna-workers', ResultsState.optuna.workers ?? '-');
  const optimizationTime = ResultsState.optuna.optimizationTimeSeconds;
  const timeLabel = ResultsState.mode === 'wfa' ? '-' : (formatDuration(optimizationTime) || '-');
  setText('optuna-time', timeLabel);

  if (ResultsState.mode === 'wfa') {
    setElementVisible('wfa-progress-section', true);
    setElementVisible('wfa-settings-section', true);
    setText('wfa-is-days', ResultsState.wfa.isPeriodDays ?? '-');
    setText('wfa-oos-days', ResultsState.wfa.oosPeriodDays ?? '-');
  } else {
    setElementVisible('wfa-progress-section', false);
    setElementVisible('wfa-settings-section', false);
  }

  setText('strategy-name', ResultsState.strategy.name || ResultsState.strategyId || '-');
  setText('strategy-version', ResultsState.strategy.version || '-');
  setText('strategy-dataset', ResultsState.dataset.label || '-');
}

function renderWindowIndicators(total) {
  const container = document.querySelector('.window-indicator');
  if (!container) return;
  container.innerHTML = '';
  const count = total || 0;
  for (let i = 0; i < count; i += 1) {
    const dot = document.createElement('div');
    dot.className = 'window-dot completed';
    container.appendChild(dot);
  }
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
    renderEquityChart(summary.equity_curve || [], boundaries);
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

function updateStoredState(patch) {
  const current = readStoredState() || {};
  const updated = { ...current, ...patch };
  try {
    const raw = JSON.stringify(updated);
    sessionStorage.setItem(OPT_STATE_KEY, raw);
    localStorage.setItem(OPT_STATE_KEY, raw);
  } catch (error) {
    return;
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

function handleStorageUpdate(event) {
  if (event.key !== OPT_STATE_KEY) return;
  if (!event.newValue) return;
  try {
    const state = JSON.parse(event.newValue);
    applyState(state);
    if (state.study_id || state.studyId) {
      openStudy(state.study_id || state.studyId);
    } else {
      refreshResultsView();
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
function md5(string) {
  function rotateLeft(value, shift) {
    return (value << shift) | (value >>> (32 - shift));
  }
  function addUnsigned(x, y) {
    const x8 = (x & 0x80000000);
    const y8 = (y & 0x80000000);
    const x4 = (x & 0x40000000);
    const y4 = (y & 0x40000000);
    const result = (x & 0x3fffffff) + (y & 0x3fffffff);
    if (x4 & y4) return (result ^ 0x80000000 ^ x8 ^ y8);
    if (x4 | y4) {
      if (result & 0x40000000) return (result ^ 0xc0000000 ^ x8 ^ y8);
      return (result ^ 0x40000000 ^ x8 ^ y8);
    }
    return (result ^ x8 ^ y8);
  }
  function f(x, y, z) { return (x & y) | ((~x) & z); }
  function g(x, y, z) { return (x & z) | (y & (~z)); }
  function h(x, y, z) { return x ^ y ^ z; }
  function i(x, y, z) { return y ^ (x | (~z)); }
  function ff(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(f(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function gg(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(g(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function hh(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(h(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function ii(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(i(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function convertToWordArray(str) {
    const wordCount = ((str.length + 8) >> 6) + 1;
    const wordArray = new Array(wordCount * 16).fill(0);
    let bytePos = 0;
    for (; bytePos < str.length; bytePos += 1) {
      wordArray[bytePos >> 2] |= str.charCodeAt(bytePos) << ((bytePos % 4) * 8);
    }
    wordArray[bytePos >> 2] |= 0x80 << ((bytePos % 4) * 8);
    wordArray[wordCount * 16 - 2] = str.length * 8;
    return wordArray;
  }
  function wordToHex(value) {
    let hex = '';
    for (let i = 0; i <= 3; i += 1) {
      const byte = (value >> (i * 8)) & 255;
      const temp = `0${byte.toString(16)}`;
      hex += temp.substr(temp.length - 2, 2);
    }
    return hex;
  }

  let a = 0x67452301;
  let b = 0xefcdab89;
  let c = 0x98badcfe;
  let d = 0x10325476;

  const x = convertToWordArray(string);

  for (let k = 0; k < x.length; k += 16) {
    const aa = a;
    const bb = b;
    const cc = c;
    const dd = d;

    a = ff(a, b, c, d, x[k + 0], 7, 0xd76aa478);
    d = ff(d, a, b, c, x[k + 1], 12, 0xe8c7b756);
    c = ff(c, d, a, b, x[k + 2], 17, 0x242070db);
    b = ff(b, c, d, a, x[k + 3], 22, 0xc1bdceee);
    a = ff(a, b, c, d, x[k + 4], 7, 0xf57c0faf);
    d = ff(d, a, b, c, x[k + 5], 12, 0x4787c62a);
    c = ff(c, d, a, b, x[k + 6], 17, 0xa8304613);
    b = ff(b, c, d, a, x[k + 7], 22, 0xfd469501);
    a = ff(a, b, c, d, x[k + 8], 7, 0x698098d8);
    d = ff(d, a, b, c, x[k + 9], 12, 0x8b44f7af);
    c = ff(c, d, a, b, x[k + 10], 17, 0xffff5bb1);
    b = ff(b, c, d, a, x[k + 11], 22, 0x895cd7be);
    a = ff(a, b, c, d, x[k + 12], 7, 0x6b901122);
    d = ff(d, a, b, c, x[k + 13], 12, 0xfd987193);
    c = ff(c, d, a, b, x[k + 14], 17, 0xa679438e);
    b = ff(b, c, d, a, x[k + 15], 22, 0x49b40821);

    a = gg(a, b, c, d, x[k + 1], 5, 0xf61e2562);
    d = gg(d, a, b, c, x[k + 6], 9, 0xc040b340);
    c = gg(c, d, a, b, x[k + 11], 14, 0x265e5a51);
    b = gg(b, c, d, a, x[k + 0], 20, 0xe9b6c7aa);
    a = gg(a, b, c, d, x[k + 5], 5, 0xd62f105d);
    d = gg(d, a, b, c, x[k + 10], 9, 0x02441453);
    c = gg(c, d, a, b, x[k + 15], 14, 0xd8a1e681);
    b = gg(b, c, d, a, x[k + 4], 20, 0xe7d3fbc8);
    a = gg(a, b, c, d, x[k + 9], 5, 0x21e1cde6);
    d = gg(d, a, b, c, x[k + 14], 9, 0xc33707d6);
    c = gg(c, d, a, b, x[k + 3], 14, 0xf4d50d87);
    b = gg(b, c, d, a, x[k + 8], 20, 0x455a14ed);
    a = gg(a, b, c, d, x[k + 13], 5, 0xa9e3e905);
    d = gg(d, a, b, c, x[k + 2], 9, 0xfcefa3f8);
    c = gg(c, d, a, b, x[k + 7], 14, 0x676f02d9);
    b = gg(b, c, d, a, x[k + 12], 20, 0x8d2a4c8a);

    a = hh(a, b, c, d, x[k + 5], 4, 0xfffa3942);
    d = hh(d, a, b, c, x[k + 8], 11, 0x8771f681);
    c = hh(c, d, a, b, x[k + 11], 16, 0x6d9d6122);
    b = hh(b, c, d, a, x[k + 14], 23, 0xfde5380c);
    a = hh(a, b, c, d, x[k + 1], 4, 0xa4beea44);
    d = hh(d, a, b, c, x[k + 4], 11, 0x4bdecfa9);
    c = hh(c, d, a, b, x[k + 7], 16, 0xf6bb4b60);
    b = hh(b, c, d, a, x[k + 10], 23, 0xbebfbc70);
    a = hh(a, b, c, d, x[k + 13], 4, 0x289b7ec6);
    d = hh(d, a, b, c, x[k + 0], 11, 0xeaa127fa);
    c = hh(c, d, a, b, x[k + 3], 16, 0xd4ef3085);
    b = hh(b, c, d, a, x[k + 6], 23, 0x04881d05);
    a = hh(a, b, c, d, x[k + 9], 4, 0xd9d4d039);
    d = hh(d, a, b, c, x[k + 12], 11, 0xe6db99e5);
    c = hh(c, d, a, b, x[k + 15], 16, 0x1fa27cf8);
    b = hh(b, c, d, a, x[k + 2], 23, 0xc4ac5665);

    a = ii(a, b, c, d, x[k + 0], 6, 0xf4292244);
    d = ii(d, a, b, c, x[k + 7], 10, 0x432aff97);
    c = ii(c, d, a, b, x[k + 14], 15, 0xab9423a7);
    b = ii(b, c, d, a, x[k + 5], 21, 0xfc93a039);
    a = ii(a, b, c, d, x[k + 12], 6, 0x655b59c3);
    d = ii(d, a, b, c, x[k + 3], 10, 0x8f0ccc92);
    c = ii(c, d, a, b, x[k + 10], 15, 0xffeff47d);
    b = ii(b, c, d, a, x[k + 1], 21, 0x85845dd1);
    a = ii(a, b, c, d, x[k + 8], 6, 0x6fa87e4f);
    d = ii(d, a, b, c, x[k + 15], 10, 0xfe2ce6e0);
    c = ii(c, d, a, b, x[k + 6], 15, 0xa3014314);
    b = ii(b, c, d, a, x[k + 13], 21, 0x4e0811a1);
    a = ii(a, b, c, d, x[k + 4], 6, 0xf7537e82);
    d = ii(d, a, b, c, x[k + 11], 10, 0xbd3af235);
    c = ii(c, d, a, b, x[k + 2], 15, 0x2ad7d2bb);
    b = ii(b, c, d, a, x[k + 9], 21, 0xeb86d391);

    a = addUnsigned(a, aa);
    b = addUnsigned(b, bb);
    c = addUnsigned(c, cc);
    d = addUnsigned(d, dd);
  }

  return (wordToHex(a) + wordToHex(b) + wordToHex(c) + wordToHex(d)).toLowerCase();
}

document.addEventListener('DOMContentLoaded', initResultsPage);


