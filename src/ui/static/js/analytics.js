(function () {
  const DEFAULT_SORT_STATE = {
    sortColumn: null,
    sortDirection: null,
    sortClickCount: 0,
  };

  const SORT_LABELS = {
    study_name: 'Study Name',
    ann_profit_pct: 'Ann.P%',
    profit_pct: 'Profit%',
    max_dd_pct: 'MaxDD%',
    total_trades: 'Trades',
    wfe_pct: 'WFE%',
    profitable_windows_pct: 'OOS Wins',
    median_window_profit: 'OOS P(med)',
    median_window_wr: 'OOS WR(med)',
  };

  const AnalyticsState = {
    dbName: '',
    studies: [],
    researchInfo: {},
    checkedStudyIds: new Set(),
    orderedStudyIds: [],
    dbSwitchInProgress: false,
    filters: {
      strategy: null,
      symbol: null,
      tf: null,
      wfa: null,
      isOos: null,
    },
    autoSelect: false,
    sortState: { ...DEFAULT_SORT_STATE },
    filtersInitialized: false,
    focusedStudyId: null,
  };

  const MISSING_TEXT = '-';
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
    total_trades: 'Total Trades',
    composite_score: 'Composite Score',
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
    consistency_score: '>=',
  };

  function toFiniteNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function average(values) {
    const finite = values
      .map((value) => toFiniteNumber(value))
      .filter((value) => value !== null);
    if (!finite.length) return null;
    const sum = finite.reduce((acc, value) => acc + value, 0);
    return sum / finite.length;
  }

  function formatSignedPercent(value, digits) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return MISSING_TEXT;
    if (parsed === 0) return `0.${'0'.repeat(digits)}%`;
    const sign = parsed > 0 ? '+' : '-';
    return `${sign}${Math.abs(parsed).toFixed(digits)}%`;
  }

  function formatNegativePercent(value, digits) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return MISSING_TEXT;
    return `-${Math.abs(parsed).toFixed(digits)}%`;
  }

  function formatUnsignedPercent(value, digits) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return MISSING_TEXT;
    return `${parsed.toFixed(digits)}%`;
  }

  function formatInteger(value) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return MISSING_TEXT;
    return String(Math.max(0, Math.round(parsed)));
  }

  function isMissingValue(value) {
    if (value === null || value === undefined) return true;
    if (typeof value === 'string') return value.trim() === '';
    return false;
  }

  function displayValue(value) {
    return isMissingValue(value) ? MISSING_TEXT : String(value);
  }

  function showMessage(message) {
    const messageEl = document.getElementById('analyticsMessage');
    if (!messageEl) return;
    const text = String(message || '').trim();
    if (!text) {
      messageEl.hidden = true;
      messageEl.textContent = '';
      return;
    }
    messageEl.hidden = false;
    messageEl.textContent = text;
  }

  function getStudyMap() {
    const map = new Map();
    AnalyticsState.studies.forEach((study) => {
      map.set(String(study.study_id || ''), study);
    });
    return map;
  }

  function getSelectedStudies() {
    const map = getStudyMap();
    return Array.from(AnalyticsState.checkedStudyIds)
      .map((studyId) => map.get(studyId))
      .filter(Boolean);
  }

  function formatObjectiveLabel(name) {
    const key = String(name || '').trim();
    return OBJECTIVE_LABELS[key] || key || MISSING_TEXT;
  }

  function formatObjectivesList(objectives) {
    if (!Array.isArray(objectives) || !objectives.length) return MISSING_TEXT;
    return objectives.map((item) => formatObjectiveLabel(item)).join(', ');
  }

  function formatConstraintsSummary(constraints) {
    if (!Array.isArray(constraints) || !constraints.length) return 'None';
    const enabled = constraints.filter((item) => item && item.enabled);
    if (!enabled.length) return 'None';
    return enabled.map((item) => {
      const metric = String(item.metric || '').trim();
      const operator = CONSTRAINT_OPERATORS[metric] || '';
      const threshold = item.threshold !== undefined && item.threshold !== null ? item.threshold : '-';
      return `${formatObjectiveLabel(metric)}${operator ? ` ${operator}` : ''} ${threshold}`;
    }).join(', ');
  }

  function formatBudgetLabel(settings) {
    const mode = String(settings?.budget_mode || '').trim().toLowerCase();
    if (!mode) return MISSING_TEXT;
    if (mode === 'trials') {
      const nTrials = toFiniteNumber(settings?.n_trials);
      return `${nTrials === null ? 0 : Math.max(0, Math.round(nTrials))} trials`;
    }
    if (mode === 'time') {
      const timeLimit = toFiniteNumber(settings?.time_limit);
      const minutes = timeLimit === null ? 0 : Math.round(timeLimit / 60);
      return `${Math.max(0, minutes)} min`;
    }
    if (mode === 'convergence') {
      const patience = toFiniteNumber(settings?.convergence_patience);
      return `No improvement ${patience === null ? 0 : Math.max(0, Math.round(patience))} trials`;
    }
    return MISSING_TEXT;
  }

  function renderSettingsList(container, rows) {
    if (!container) return;
    container.innerHTML = '';
    (rows || []).forEach((row) => {
      const item = document.createElement('div');
      item.className = 'setting-item';

      const key = document.createElement('span');
      key.className = 'key';
      key.textContent = String(row.key || '');

      const val = document.createElement('span');
      val.className = 'val';
      val.textContent = displayValue(row.val);

      item.appendChild(key);
      item.appendChild(val);
      container.appendChild(item);
    });
  }

  function hideFocusSidebar() {
    const optunaSection = document.getElementById('analytics-optuna-section');
    const wfaSection = document.getElementById('analytics-wfa-section');
    if (optunaSection) optunaSection.style.display = 'none';
    if (wfaSection) wfaSection.style.display = 'none';
  }

  function renderFocusedSidebar(study) {
    const optunaSection = document.getElementById('analytics-optuna-section');
    const wfaSection = document.getElementById('analytics-wfa-section');
    const optunaContainer = document.getElementById('analyticsOptunaSettings');
    const wfaContainer = document.getElementById('analyticsWfaSettings');
    if (!optunaSection || !wfaSection || !optunaContainer || !wfaContainer) return;

    const optunaSettings = study?.optuna_settings || {};
    const wfaSettings = study?.wfa_settings || {};
    const enablePruning = optunaSettings.enable_pruning === null || optunaSettings.enable_pruning === undefined
      ? null
      : Boolean(optunaSettings.enable_pruning);
    const prunerValue = enablePruning === false
      ? '-'
      : (String(optunaSettings.pruner || '').trim() || (enablePruning ? 'On' : MISSING_TEXT));

    const optunaRows = [
      { key: 'Objectives', val: formatObjectivesList(optunaSettings.objectives) },
      {
        key: 'Primary',
        val: optunaSettings.primary_objective ? formatObjectiveLabel(optunaSettings.primary_objective) : MISSING_TEXT,
      },
      { key: 'Constraints', val: formatConstraintsSummary(optunaSettings.constraints) },
      { key: 'Budget', val: formatBudgetLabel(optunaSettings) },
      {
        key: 'Sampler',
        val: String(optunaSettings.sampler_type || '').trim()
          ? String(optunaSettings.sampler_type).toUpperCase()
          : MISSING_TEXT,
      },
      { key: 'Pruner', val: prunerValue },
      {
        key: 'Workers',
        val: toFiniteNumber(optunaSettings.workers) === null
          ? MISSING_TEXT
          : String(Math.max(0, Math.round(Number(optunaSettings.workers)))),
      },
    ];
    renderSettingsList(optunaContainer, optunaRows);

    const adaptiveModeRaw = wfaSettings.adaptive_mode;
    const adaptiveMode = adaptiveModeRaw === null || adaptiveModeRaw === undefined
      ? null
      : Boolean(adaptiveModeRaw);
    const wfaRows = [
      {
        key: 'IS (days)',
        val: toFiniteNumber(wfaSettings.is_period_days) === null
          ? MISSING_TEXT
          : String(Math.max(0, Math.round(Number(wfaSettings.is_period_days)))),
      },
      {
        key: 'OOS (days)',
        val: toFiniteNumber(wfaSettings.oos_period_days) === null
          ? MISSING_TEXT
          : String(Math.max(0, Math.round(Number(wfaSettings.oos_period_days)))),
      },
      { key: 'Adaptive', val: adaptiveMode === null ? MISSING_TEXT : (adaptiveMode ? 'On' : 'Off') },
    ];
    if (adaptiveMode === true) {
      wfaRows.push(
        {
          key: 'Max OOS (days)',
          val: toFiniteNumber(wfaSettings.max_oos_period_days) === null
            ? MISSING_TEXT
            : String(Math.max(0, Math.round(Number(wfaSettings.max_oos_period_days)))),
        },
        {
          key: 'Min OOS Trades',
          val: toFiniteNumber(wfaSettings.min_oos_trades) === null
            ? MISSING_TEXT
            : String(Math.max(0, Math.round(Number(wfaSettings.min_oos_trades)))),
        },
        {
          key: 'CUSUM Threshold',
          val: toFiniteNumber(wfaSettings.cusum_threshold) === null
            ? MISSING_TEXT
            : Number(wfaSettings.cusum_threshold).toFixed(2),
        },
        {
          key: 'DD Multiplier',
          val: toFiniteNumber(wfaSettings.dd_threshold_multiplier) === null
            ? MISSING_TEXT
            : Number(wfaSettings.dd_threshold_multiplier).toFixed(2),
        },
        {
          key: 'Inactivity Mult.',
          val: toFiniteNumber(wfaSettings.inactivity_multiplier) === null
            ? MISSING_TEXT
            : Number(wfaSettings.inactivity_multiplier).toFixed(2),
        }
      );
    }
    renderSettingsList(wfaContainer, wfaRows);

    optunaSection.style.display = '';
    wfaSection.style.display = '';
  }

  function getFocusedStudy() {
    const focusedId = String(AnalyticsState.focusedStudyId || '');
    if (!focusedId) return null;
    return getStudyMap().get(focusedId) || null;
  }

  function renderFocusedCards(study) {
    const container = document.getElementById('analyticsSummaryRow');
    if (!container || !study) return;

    const netProfit = toFiniteNumber(study.profit_pct);
    const maxDrawdown = toFiniteNumber(study.max_dd_pct);
    const totalTradesRaw = toFiniteNumber(study.total_trades);
    const winningTradesRaw = toFiniteNumber(study.winning_trades);
    const totalTrades = totalTradesRaw === null ? null : Math.max(0, Math.round(totalTradesRaw));
    let winningTrades = winningTradesRaw === null ? null : Math.max(0, Math.round(winningTradesRaw));
    if (winningTrades !== null && totalTrades !== null) {
      winningTrades = Math.min(winningTrades, totalTrades);
    } else if (winningTrades === null && totalTrades === 0) {
      winningTrades = 0;
    }
    const totalTradesText = totalTrades !== null
      ? `${winningTrades !== null ? winningTrades : 'N/A'}/${totalTrades}`
      : (winningTrades !== null ? `${winningTrades}/N/A` : 'N/A');

    const profitableWindowsRaw = toFiniteNumber(study.profitable_windows);
    const totalWindowsRaw = toFiniteNumber(study.total_windows);
    const profitableWindows = profitableWindowsRaw === null ? null : Math.max(0, Math.round(profitableWindowsRaw));
    const totalWindows = totalWindowsRaw === null ? null : Math.max(0, Math.round(totalWindowsRaw));
    const oosWinsPctRaw = toFiniteNumber(study.profitable_windows_pct);
    const oosWinsPct = oosWinsPctRaw !== null
      ? oosWinsPctRaw
      : (profitableWindows !== null && totalWindows !== null && totalWindows > 0
        ? (profitableWindows / totalWindows) * 100
        : 0);
    const oosWinsText = (profitableWindows !== null && totalWindows !== null)
      ? `${Math.min(profitableWindows, totalWindows)}/${totalWindows} (${Math.round(totalWindows > 0 ? oosWinsPct : 0)}%)`
      : (oosWinsPctRaw !== null ? `${Math.round(oosWinsPctRaw)}%` : 'N/A');

    const wfe = toFiniteNumber(study.wfe_pct);
    const medianProfit = toFiniteNumber(study.median_window_profit);
    const medianWr = toFiniteNumber(study.median_window_wr);

    const netClass = netProfit === null ? '' : (netProfit >= 0 ? 'positive' : 'negative');
    const medianProfitClass = medianProfit === null ? '' : (medianProfit >= 0 ? 'positive' : 'negative');

    container.innerHTML = `
      <div class="summary-card highlight">
        <div class="value ${netClass}">${formatSignedPercent(netProfit, 2)}</div>
        <div class="label">NET PROFIT</div>
      </div>
      <div class="summary-card">
        <div class="value negative">${formatNegativePercent(maxDrawdown, 2)}</div>
        <div class="label">MAX DRAWDOWN</div>
      </div>
      <div class="summary-card">
        <div class="value">${totalTradesText}</div>
        <div class="label">TOTAL TRADES</div>
      </div>
      <div class="summary-card">
        <div class="value">${wfe === null ? 'N/A' : `${wfe.toFixed(1)}%`}</div>
        <div class="label">WFE</div>
      </div>
      <div class="summary-card">
        <div class="value">${oosWinsText}</div>
        <div class="label">OOS WINS</div>
      </div>
      <div class="summary-card">
        <div class="value ${medianProfitClass}">${formatSignedPercent(medianProfit, 1)}</div>
        <div class="label">OOS PROFIT (MED)</div>
      </div>
      <div class="summary-card">
        <div class="value">${formatUnsignedPercent(medianWr, 1)}</div>
        <div class="label">OOS WIN RATE (MED)</div>
      </div>
    `;
  }

  function renderSummaryCards() {
    const container = document.getElementById('analyticsSummaryRow');
    if (!container) return;

    const focusedStudy = getFocusedStudy();
    if (focusedStudy) {
      renderFocusedCards(focusedStudy);
      return;
    }

    const selected = getSelectedStudies();
    if (!selected.length) {
      container.innerHTML = `
        <div class="summary-card highlight"><div class="value">-</div><div class="label">Portfolio Profit</div></div>
        <div class="summary-card"><div class="value">-</div><div class="label">Portfolio MaxDD</div></div>
        <div class="summary-card"><div class="value">-</div><div class="label">Total Trades</div></div>
        <div class="summary-card"><div class="value">-</div><div class="label">Profitable</div></div>
        <div class="summary-card"><div class="value">-</div><div class="label">Avg OOS Wins</div></div>
        <div class="summary-card"><div class="value">-</div><div class="label">Avg WFE</div></div>
        <div class="summary-card"><div class="value">-</div><div class="label">Avg OOS P(med)</div></div>
      `;
      return;
    }

    const portfolioProfit = selected.reduce((acc, study) => acc + (toFiniteNumber(study.profit_pct) || 0), 0);
    const portfolioMaxDd = selected.reduce((acc, study) => Math.max(acc, toFiniteNumber(study.max_dd_pct) || 0), 0);
    const totalTrades = selected.reduce((acc, study) => acc + Math.max(0, Math.round(toFiniteNumber(study.total_trades) || 0)), 0);
    const profitableCount = selected.reduce((acc, study) => acc + ((toFiniteNumber(study.profit_pct) || 0) > 0 ? 1 : 0), 0);
    const profitablePct = selected.length > 0 ? Math.round((profitableCount / selected.length) * 100) : 0;

    const avgOosWins = average(selected.map((study) => study.profitable_windows_pct));
    const avgWfe = average(selected.map((study) => study.wfe_pct));
    const avgOosProfitMed = average(selected.map((study) => study.median_window_profit));

    const profitClass = portfolioProfit >= 0 ? 'positive' : 'negative';
    const oosProfitClass = (avgOosProfitMed || 0) >= 0 ? 'positive' : 'negative';

    container.innerHTML = `
      <div class="summary-card highlight">
        <div class="value ${profitClass}">${formatSignedPercent(portfolioProfit, 1)}</div>
        <div class="label">Portfolio Profit</div>
      </div>
      <div class="summary-card">
        <div class="value negative">${formatNegativePercent(portfolioMaxDd, 1)}</div>
        <div class="label">Portfolio MaxDD</div>
      </div>
      <div class="summary-card">
        <div class="value">${formatInteger(totalTrades)}</div>
        <div class="label">Total Trades</div>
      </div>
      <div class="summary-card">
        <div class="value">${profitableCount}/${selected.length} (${profitablePct}%)</div>
        <div class="label">Profitable</div>
      </div>
      <div class="summary-card">
        <div class="value">${formatUnsignedPercent(avgOosWins, 1)}</div>
        <div class="label">Avg OOS Wins</div>
      </div>
      <div class="summary-card">
        <div class="value">${formatUnsignedPercent(avgWfe, 1)}</div>
        <div class="label">Avg WFE</div>
      </div>
      <div class="summary-card">
        <div class="value ${oosProfitClass}">${formatSignedPercent(avgOosProfitMed, 1)}</div>
        <div class="label">Avg OOS P(med)</div>
      </div>
    `;
  }

  function renderChartTitle(study) {
    const titleEl = document.getElementById('analyticsChartTitle');
    if (!titleEl) return;
    titleEl.textContent = '';

    if (!study) {
      titleEl.textContent = 'Stitched OOS Equity';
      return;
    }

    const rowNumber = Math.max(1, AnalyticsState.orderedStudyIds.indexOf(String(study.study_id || '')) + 1);
    const symbol = study.symbol || '-';
    const tf = study.tf || '-';
    titleEl.appendChild(document.createTextNode(`Stitched OOS Equity - #${rowNumber} ${symbol} ${tf}`));

    if (String(AnalyticsState.focusedStudyId || '') === String(study.study_id || '')) {
      const dismissBtn = document.createElement('button');
      dismissBtn.type = 'button';
      dismissBtn.className = 'focus-dismiss';
      dismissBtn.id = 'analyticsFocusDismiss';
      dismissBtn.title = 'Exit focus mode';
      dismissBtn.setAttribute('aria-label', 'Exit focus mode');
      dismissBtn.textContent = 'x';
      dismissBtn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        clearFocus();
      });
      titleEl.appendChild(dismissBtn);
    }
  }

  function getPrimaryCheckedStudy() {
    const map = getStudyMap();
    let selectedId = null;
    for (const studyId of AnalyticsState.orderedStudyIds) {
      if (AnalyticsState.checkedStudyIds.has(studyId)) {
        selectedId = studyId;
        break;
      }
    }
    if (!selectedId) {
      selectedId = Array.from(AnalyticsState.checkedStudyIds)[0] || null;
    }
    return selectedId ? map.get(selectedId) || null : null;
  }

  function renderSelectedStudyChart() {
    const focusedStudy = getFocusedStudy();
    const study = focusedStudy || getPrimaryCheckedStudy();
    renderChartTitle(study);

    if (!study) {
      window.AnalyticsEquity.renderEmpty('No data to display');
      return;
    }
    if (!study.has_equity_curve) {
      window.AnalyticsEquity.renderEmpty('No stitched OOS equity data for selected study');
      return;
    }
    window.AnalyticsEquity.renderChart(study.equity_curve || [], study.equity_timestamps || []);
  }

  function updateVisualsForSelection() {
    const focusedStudy = getFocusedStudy();
    if (focusedStudy) {
      renderFocusedSidebar(focusedStudy);
    } else {
      hideFocusSidebar();
    }
    renderSummaryCards();
    renderSelectedStudyChart();
  }

  function buildResearchInfoRows(info) {
    const symbols = Array.isArray(info.symbols) ? info.symbols : [];
    const strategies = Array.isArray(info.strategies) ? info.strategies : [];
    const timeframes = Array.isArray(info.timeframes) ? info.timeframes : [];
    const wfaModes = Array.isArray(info.wfa_modes) ? info.wfa_modes : [];
    const isOosPeriods = Array.isArray(info.is_oos_periods) ? info.is_oos_periods : [];
    const dataPeriods = Array.isArray(info.data_periods) ? info.data_periods : [];

    return [
      { key: 'Studies', val: `${info.total_studies || 0} total (${info.wfa_studies || 0} WFA)` },
      { key: 'Strategies', val: strategies.length ? strategies.join(', ') : MISSING_TEXT },
      { key: 'Symbols', val: symbols.length ? `${symbols.length} tickers` : MISSING_TEXT },
      { key: 'Timeframes', val: timeframes.length ? timeframes.join(', ') : MISSING_TEXT },
      { key: 'WFA Mode', val: wfaModes.length ? wfaModes.join(', ') : MISSING_TEXT },
      { key: 'IS / OOS', val: isOosPeriods.length ? isOosPeriods.join(', ') : MISSING_TEXT },
      { key: 'Data Periods', val: `${dataPeriods.length} periods` },
    ];
  }

  function renderResearchInfo() {
    const container = document.getElementById('analyticsResearchInfo');
    if (!container) return;
    const rows = buildResearchInfoRows(AnalyticsState.researchInfo || {});
    container.innerHTML = '';

    rows.forEach((row) => {
      const item = document.createElement('div');
      item.className = 'setting-item';

      const key = document.createElement('span');
      key.className = 'key';
      key.textContent = String(row.key || '');

      const val = document.createElement('span');
      val.className = 'val';
      val.textContent = displayValue(row.val);

      item.appendChild(key);
      item.appendChild(val);
      container.appendChild(item);
    });
  }

  function renderTableSubtitle() {
    const subtitle = document.getElementById('analyticsTableSubtitle');
    if (!subtitle) return;

    const sortColumn = AnalyticsState.sortState.sortColumn;
    const sortDirection = AnalyticsState.sortState.sortDirection;
    if (!sortColumn || !sortDirection) {
      subtitle.textContent = 'Sorted by date added (newest first)';
      return;
    }

    const label = SORT_LABELS[sortColumn] || sortColumn;
    const arrow = sortDirection === 'asc' ? '▲' : '▼';
    subtitle.textContent = `Sorted by ${label} ${arrow}`;
  }

  function renderDbName() {
    const dbNameEl = document.getElementById('analyticsDbName');
    if (!dbNameEl) return;
    dbNameEl.textContent = AnalyticsState.dbName || '-';
  }

  function renderDatabasesList(databases) {
    const container = document.getElementById('analyticsDbList');
    if (!container) return;

    container.innerHTML = '';
    if (!Array.isArray(databases) || !databases.length) {
      container.innerHTML = '<div class="study-item">No database files found.</div>';
      return;
    }

    databases.forEach((db) => {
      const item = document.createElement('div');
      item.className = db.active ? 'study-item selected' : 'study-item';
      item.textContent = db.name;
      item.dataset.dbName = db.name;
      item.addEventListener('click', async () => {
        if (AnalyticsState.dbSwitchInProgress || db.active) return;
        AnalyticsState.dbSwitchInProgress = true;
        try {
          await switchDatabaseRequest(db.name);
          AnalyticsState.checkedStudyIds = new Set();
          AnalyticsState.sortState = { ...DEFAULT_SORT_STATE };
          AnalyticsState.focusedStudyId = null;
          await Promise.all([loadDatabases(), loadSummary()]);
        } catch (error) {
          alert(error.message || 'Failed to switch database.');
        } finally {
          AnalyticsState.dbSwitchInProgress = false;
        }
      });
      container.appendChild(item);
    });
  }

  function onTableSelectionChange(checkedSet) {
    AnalyticsState.checkedStudyIds = new Set(checkedSet || []);
    updateVisualsForSelection();
  }

  function clearFocus() {
    if (!AnalyticsState.focusedStudyId) return;
    AnalyticsState.focusedStudyId = null;
    if (window.AnalyticsTable && typeof window.AnalyticsTable.setFocusedStudyId === 'function') {
      window.AnalyticsTable.setFocusedStudyId(null);
    }
    updateVisualsForSelection();
  }

  function setFocus(studyId) {
    const normalized = String(studyId || '').trim();
    if (!normalized) {
      clearFocus();
      return;
    }
    if (AnalyticsState.focusedStudyId === normalized) {
      clearFocus();
      return;
    }
    AnalyticsState.focusedStudyId = normalized;
    if (window.AnalyticsTable && typeof window.AnalyticsTable.setFocusedStudyId === 'function') {
      window.AnalyticsTable.setFocusedStudyId(normalized);
    }
    updateVisualsForSelection();
  }

  function onTableFocusToggle(studyId) {
    setFocus(studyId);
  }

  function onTableSortChange(sortState) {
    AnalyticsState.sortState = {
      sortColumn: sortState?.sortColumn || null,
      sortDirection: sortState?.sortDirection || null,
      sortClickCount: Number(sortState?.sortClickCount || 0),
    };
    renderTableSubtitle();
    AnalyticsState.orderedStudyIds = window.AnalyticsTable.getOrderedStudyIds();
    updateVisualsForSelection();
  }

  function renderTableWithCurrentState() {
    window.AnalyticsTable.renderTable(
      AnalyticsState.studies,
      AnalyticsState.checkedStudyIds,
      onTableSelectionChange,
      {
        filters: AnalyticsState.filters,
        autoSelect: AnalyticsState.autoSelect,
        sortState: AnalyticsState.sortState,
        onSortChange: onTableSortChange,
        onFocusToggle: onTableFocusToggle,
        focusedStudyId: AnalyticsState.focusedStudyId,
      }
    );

    AnalyticsState.checkedStudyIds = new Set(window.AnalyticsTable.getCheckedStudyIds());
    AnalyticsState.orderedStudyIds = window.AnalyticsTable.getOrderedStudyIds();
    if (AnalyticsState.focusedStudyId && typeof window.AnalyticsTable.getVisibleStudyIds === 'function') {
      const visibleSet = new Set(window.AnalyticsTable.getVisibleStudyIds());
      if (!visibleSet.has(AnalyticsState.focusedStudyId)) {
        AnalyticsState.focusedStudyId = null;
      }
    }
    if (typeof window.AnalyticsTable.setFocusedStudyId === 'function') {
      window.AnalyticsTable.setFocusedStudyId(AnalyticsState.focusedStudyId);
    }
    updateVisualsForSelection();
  }

  function handleFiltersChanged(nextFilters) {
    AnalyticsState.filters = nextFilters || {
      strategy: null,
      symbol: null,
      tf: null,
      wfa: null,
      isOos: null,
    };
    renderTableWithCurrentState();
  }

  function bindAutoSelect() {
    const autoSelectInput = document.getElementById('analyticsAutoSelect');
    if (!autoSelectInput) return;
    autoSelectInput.checked = AnalyticsState.autoSelect;
    autoSelectInput.addEventListener('change', () => {
      AnalyticsState.autoSelect = Boolean(autoSelectInput.checked);
      renderTableWithCurrentState();
    });
  }

  async function loadDatabases() {
    const payload = await fetchDatabasesList();
    renderDatabasesList(payload.databases || []);
  }

  function ensureFiltersInitialized() {
    if (!window.AnalyticsFilters) return;
    if (!AnalyticsState.filtersInitialized) {
      window.AnalyticsFilters.init({
        studies: AnalyticsState.studies,
        onChange: handleFiltersChanged,
      });
      AnalyticsState.filtersInitialized = true;
      return;
    }
    window.AnalyticsFilters.updateStudies(AnalyticsState.studies);
  }

  async function loadSummary() {
    const response = await fetch('/api/analytics/summary');
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.error || 'Failed to load analytics summary.');
    }
    const data = await response.json();

    AnalyticsState.dbName = String(data.db_name || '');
    AnalyticsState.studies = Array.isArray(data.studies) ? data.studies : [];
    AnalyticsState.researchInfo = data.research_info || {};
    AnalyticsState.checkedStudyIds = new Set();
    AnalyticsState.focusedStudyId = null;

    renderDbName();
    renderResearchInfo();
    showMessage(AnalyticsState.researchInfo.message || '');

    ensureFiltersInitialized();
    AnalyticsState.filters = window.AnalyticsFilters
      ? window.AnalyticsFilters.getFilters()
      : {
          strategy: null,
          symbol: null,
          tf: null,
          wfa: null,
          isOos: null,
        };

    renderTableSubtitle();
    renderTableWithCurrentState();
  }

  function bindCollapsibleHeaders() {
    const headers = document.querySelectorAll('.sidebar .collapsible-header');
    headers.forEach((header) => {
      header.addEventListener('click', () => {
        const root = header.closest('.collapsible');
        if (!root) return;
        root.classList.toggle('open');
      });
    });
  }

  function bindSelectionButtons() {
    const selectAllBtn = document.getElementById('analyticsSelectAllBtn');
    const deselectAllBtn = document.getElementById('analyticsDeselectAllBtn');

    if (selectAllBtn) {
      selectAllBtn.addEventListener('click', () => {
        window.AnalyticsTable.setAllChecked(true);
      });
    }
    if (deselectAllBtn) {
      deselectAllBtn.addEventListener('click', () => {
        window.AnalyticsTable.setAllChecked(false);
      });
    }
  }

  function bindFocusHotkeys() {
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && AnalyticsState.focusedStudyId) {
        clearFocus();
      }
    });
  }

  async function initAnalyticsPage() {
    bindCollapsibleHeaders();
    bindSelectionButtons();
    bindAutoSelect();
    bindFocusHotkeys();
    try {
      await Promise.all([loadDatabases(), loadSummary()]);
    } catch (error) {
      showMessage(error.message || 'Failed to initialize analytics page.');
      window.AnalyticsEquity.renderEmpty('No data to display');
    }
  }

  document.addEventListener('DOMContentLoaded', initAnalyticsPage);
})();
