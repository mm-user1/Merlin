(function () {
  const AnalyticsState = {
    dbName: '',
    studies: [],
    researchInfo: {},
    checkedStudyIds: new Set(),
    orderedStudyIds: [],
    dbSwitchInProgress: false,
  };

  const MISSING_TEXT = '-';

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

  function formatSignedPercent(value, digits = 1) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return MISSING_TEXT;
    if (parsed === 0) return `0.${'0'.repeat(digits)}%`;
    const sign = parsed > 0 ? '+' : '-';
    return `${sign}${Math.abs(parsed).toFixed(digits)}%`;
  }

  function formatNegativePercent(value, digits = 1) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return MISSING_TEXT;
    return `-${Math.abs(parsed).toFixed(digits)}%`;
  }

  function formatUnsignedPercent(value, digits = 1) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return MISSING_TEXT;
    return `${parsed.toFixed(digits)}%`;
  }

  function formatInteger(value) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return MISSING_TEXT;
    return String(Math.max(0, Math.round(parsed)));
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

  function renderSummaryCards() {
    const container = document.getElementById('analyticsSummaryRow');
    if (!container) return;

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

    const portfolioProfit = selected.reduce((acc, study) => {
      return acc + (toFiniteNumber(study.profit_pct) || 0);
    }, 0);
    const portfolioMaxDd = selected.reduce((acc, study) => {
      const current = toFiniteNumber(study.max_dd_pct) || 0;
      return Math.max(acc, current);
    }, 0);
    const totalTrades = selected.reduce((acc, study) => {
      return acc + Math.max(0, Math.round(toFiniteNumber(study.total_trades) || 0));
    }, 0);
    const profitableCount = selected.reduce((acc, study) => {
      const value = toFiniteNumber(study.profit_pct) || 0;
      return acc + (value > 0 ? 1 : 0);
    }, 0);
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

  function renderSelectedStudyChart() {
    const titleEl = document.getElementById('analyticsChartTitle');
    if (!titleEl) return;

    if (!AnalyticsState.checkedStudyIds.size) {
      titleEl.textContent = 'Stitched OOS Equity';
      window.AnalyticsEquity.renderEmpty('No data to display');
      return;
    }

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

    const study = selectedId ? map.get(selectedId) : null;
    if (!study) {
      titleEl.textContent = 'Stitched OOS Equity';
      window.AnalyticsEquity.renderEmpty('No data to display');
      return;
    }

    const rowNumber = Math.max(1, AnalyticsState.orderedStudyIds.indexOf(String(study.study_id || '')) + 1);
    const symbol = study.symbol || '-';
    const tf = study.tf || '-';
    titleEl.textContent = `Stitched OOS Equity - #${rowNumber} ${symbol} ${tf}`;

    if (!study.has_equity_curve) {
      window.AnalyticsEquity.renderEmpty('No stitched OOS equity data for selected study');
      return;
    }

    window.AnalyticsEquity.renderChart(study.equity_curve || [], study.equity_timestamps || []);
  }

  function updateVisualsForSelection() {
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
      val.textContent = String(row.val || MISSING_TEXT);

      item.appendChild(key);
      item.appendChild(val);
      container.appendChild(item);
    });
  }

  function renderTableSubtitle() {
    const subtitle = document.getElementById('analyticsTableSubtitle');
    if (!subtitle) return;
    const info = AnalyticsState.researchInfo || {};
    const wfaCount = Number(info.wfa_studies || 0);
    const periods = Array.isArray(info.data_periods) ? info.data_periods.length : 0;
    subtitle.textContent = `${wfaCount} WFA studies | ${periods} data periods | Sorted by Profit% desc`;
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

  async function loadDatabases() {
    const payload = await fetchDatabasesList();
    renderDatabasesList(payload.databases || []);
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

    renderDbName();
    renderResearchInfo();
    renderTableSubtitle();
    showMessage(AnalyticsState.researchInfo.message || '');

    window.AnalyticsTable.renderTable(
      AnalyticsState.studies,
      AnalyticsState.checkedStudyIds,
      (checkedSet) => {
        AnalyticsState.checkedStudyIds = new Set(checkedSet || []);
        updateVisualsForSelection();
      }
    );
    AnalyticsState.orderedStudyIds = window.AnalyticsTable.getOrderedStudyIds();

    updateVisualsForSelection();
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

  async function initAnalyticsPage() {
    bindCollapsibleHeaders();
    bindSelectionButtons();
    try {
      await Promise.all([loadDatabases(), loadSummary()]);
    } catch (error) {
      showMessage(error.message || 'Failed to initialize analytics page.');
      window.AnalyticsEquity.renderEmpty('No data to display');
    }
  }

  document.addEventListener('DOMContentLoaded', initAnalyticsPage);
})();
