(function () {
  const tableState = {
    orderedStudyIds: [],
    onSelectionChange: null,
    bound: false,
  };

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function parseDateFlexible(value) {
    const token = String(value || '').trim();
    if (!token) return null;
    const normalized = token.replace(/\./g, '-');
    const parsed = Date.parse(`${normalized}T00:00:00Z`);
    if (!Number.isFinite(parsed)) return null;
    return new Date(parsed);
  }

  function toDateKey(value) {
    const parsed = parseDateFlexible(value);
    if (parsed) {
      return { missing: 0, value: parsed.getTime() };
    }
    return { missing: 1, value: String(value || '') };
  }

  function toFiniteNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function periodDays(start, end) {
    const startDate = parseDateFlexible(start);
    const endDate = parseDateFlexible(end);
    if (!startDate || !endDate) return null;
    const diff = Math.floor((endDate.getTime() - startDate.getTime()) / (24 * 60 * 60 * 1000));
    return Math.max(0, diff);
  }

  function formatSignedValue(value, digits = 1) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return 'N/A';
    if (parsed === 0) return `0.${'0'.repeat(digits)}`;
    const sign = parsed > 0 ? '+' : '-';
    return `${sign}${Math.abs(parsed).toFixed(digits)}`;
  }

  function formatUnsignedValue(value, digits = 1) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return 'N/A';
    return Math.abs(parsed).toFixed(digits);
  }

  function formatInteger(value, fallback = '0') {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return fallback;
    return String(Math.max(0, Math.round(parsed)));
  }

  function formatOosWins(study) {
    const profitable = Math.max(0, Math.round(toFiniteNumber(study.profitable_windows) || 0));
    const total = Math.max(0, Math.round(toFiniteNumber(study.total_windows) || 0));
    const pct = toFiniteNumber(study.profitable_windows_pct);
    if (total <= 0) {
      const pctText = pct === null ? 0 : Math.round(pct);
      return `0/0 (${pctText}%)`;
    }
    const bounded = Math.min(profitable, total);
    const computedPct = Math.round((bounded / total) * 100);
    return `${bounded}/${total} (${computedPct}%)`;
  }

  function compareByDateKey(a, b) {
    if (a.missing !== b.missing) return a.missing - b.missing;
    if (typeof a.value === 'number' && typeof b.value === 'number') return a.value - b.value;
    return String(a.value).localeCompare(String(b.value), undefined, { sensitivity: 'base' });
  }

  function groupStudies(studies) {
    const groupsMap = new Map();
    (Array.isArray(studies) ? studies : []).forEach((study) => {
      const start = String(study.dataset_start_date || '').trim();
      const end = String(study.dataset_end_date || '').trim();
      const groupKey = `${start}||${end}`;
      if (!groupsMap.has(groupKey)) {
        groupsMap.set(groupKey, {
          key: groupKey,
          start,
          end,
          studies: [],
        });
      }
      groupsMap.get(groupKey).studies.push(study);
    });

    const groups = Array.from(groupsMap.values());
    groups.forEach((group) => {
      group.studies.sort((left, right) => {
        const leftProfit = toFiniteNumber(left.profit_pct) || 0;
        const rightProfit = toFiniteNumber(right.profit_pct) || 0;
        if (rightProfit !== leftProfit) return rightProfit - leftProfit;
        return String(left.study_id || '').localeCompare(String(right.study_id || ''));
      });
    });

    groups.sort((left, right) => {
      const startCmp = compareByDateKey(toDateKey(left.start), toDateKey(right.start));
      if (startCmp !== 0) return startCmp;
      return compareByDateKey(toDateKey(left.end), toDateKey(right.end));
    });

    groups.forEach((group, index) => {
      group.token = `g${index + 1}`;
    });

    return groups;
  }

  function getTableElements() {
    const table = document.getElementById('analyticsSummaryTable');
    const tbody = document.getElementById('analyticsSummaryTableBody');
    const headerCheck = document.getElementById('analyticsHeaderCheck');
    return { table, tbody, headerCheck };
  }

  function getRowCheckboxes() {
    const { table } = getTableElements();
    if (!table) return [];
    return Array.from(table.querySelectorAll('tbody .analytics-row-check'));
  }

  function getGroupCheckboxes() {
    const { table } = getTableElements();
    if (!table) return [];
    return Array.from(table.querySelectorAll('tbody .analytics-group-check'));
  }

  function getCheckedStudyIds() {
    return getRowCheckboxes()
      .filter((checkbox) => checkbox.checked)
      .map((checkbox) => {
        const encodedId = checkbox.dataset.studyId || '';
        try {
          return decodeURIComponent(encodedId);
        } catch (_error) {
          return encodedId;
        }
      })
      .filter(Boolean);
  }

  function updateRowSelectionClasses() {
    const { table } = getTableElements();
    if (!table) return;
    const rows = Array.from(table.querySelectorAll('tbody tr.analytics-study-row'));
    rows.forEach((row) => {
      const checkbox = row.querySelector('.analytics-row-check');
      const checked = Boolean(checkbox && checkbox.checked);
      row.classList.toggle('selected', checked);
    });
  }

  function syncHierarchyCheckboxes() {
    const { table, headerCheck } = getTableElements();
    if (!table) return;

    getGroupCheckboxes().forEach((groupCheckbox) => {
      const groupKey = groupCheckbox.dataset.group || '';
      const children = Array.from(
        table.querySelectorAll(`tbody .analytics-row-check[data-group="${groupKey}"]`)
      );
      if (!children.length) {
        groupCheckbox.checked = false;
        groupCheckbox.indeterminate = false;
        return;
      }
      const checkedCount = children.filter((checkbox) => checkbox.checked).length;
      groupCheckbox.checked = checkedCount === children.length;
      groupCheckbox.indeterminate = checkedCount > 0 && checkedCount < children.length;
    });

    if (headerCheck) {
      const rowCheckboxes = getRowCheckboxes();
      const checkedCount = rowCheckboxes.filter((checkbox) => checkbox.checked).length;
      headerCheck.checked = rowCheckboxes.length > 0 && checkedCount === rowCheckboxes.length;
      headerCheck.indeterminate = checkedCount > 0 && checkedCount < rowCheckboxes.length;
    }

    updateRowSelectionClasses();
  }

  function notifySelectionChanged() {
    if (typeof tableState.onSelectionChange !== 'function') return;
    tableState.onSelectionChange(new Set(getCheckedStudyIds()));
  }

  function bindEventsOnce() {
    if (tableState.bound) return;
    const { table } = getTableElements();
    if (!table) return;

    table.addEventListener('change', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;

      if (target.id === 'analyticsHeaderCheck') {
        getRowCheckboxes().forEach((checkbox) => {
          checkbox.checked = target.checked;
        });
      } else if (target.classList.contains('analytics-group-check')) {
        const group = target.dataset.group || '';
        getRowCheckboxes()
          .filter((checkbox) => checkbox.dataset.group === group)
          .forEach((checkbox) => {
            checkbox.checked = target.checked;
          });
      }

      syncHierarchyCheckboxes();
      notifySelectionChanged();
    });

    tableState.bound = true;
  }

  function renderTable(studies, checkedStudyIds, onSelectionChange) {
    const { tbody } = getTableElements();
    if (!tbody) return;

    tableState.onSelectionChange = onSelectionChange;
    bindEventsOnce();

    const checkedSet = new Set(Array.from(checkedStudyIds || []));
    const groups = groupStudies(studies);
    tableState.orderedStudyIds = [];

    if (!groups.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="14" class="analytics-empty-cell">No WFA studies found in this database.</td>
        </tr>
      `;
      syncHierarchyCheckboxes();
      return;
    }

    let rowIndex = 1;
    const html = [];

    groups.forEach((group) => {
      const days = periodDays(group.start, group.end);
      const daysText = days === null ? '?' : String(days);
      const groupToken = group.token || '';
      const groupStart = escapeHtml(group.start || 'Unknown');
      const groupEnd = escapeHtml(group.end || 'Unknown');
      html.push(`
        <tr class="group-row analytics-group-row" data-group="${groupToken}">
          <td class="col-check"><input type="checkbox" class="analytics-group-check" data-group="${groupToken}" /></td>
          <td colspan="13">
            <div class="group-label">
              <span class="group-dates">${groupStart} &mdash; ${groupEnd}</span>
              <span class="group-duration">(${daysText} days)</span>
              <span class="group-count">${group.studies.length} studies</span>
            </div>
          </td>
        </tr>
      `);

      group.studies.forEach((study) => {
        const studyId = String(study.study_id || '');
        const encodedStudyId = encodeURIComponent(studyId);
        tableState.orderedStudyIds.push(studyId);
        const checked = checkedSet.has(studyId) ? 'checked' : '';

        const profitText = formatSignedValue(study.profit_pct, 1);
        const maxDdText = formatUnsignedValue(study.max_dd_pct, 1);
        const wfeRaw = toFiniteNumber(study.wfe_pct);
        const wfeText = wfeRaw === null ? 'N/A' : wfeRaw.toFixed(1);
        const oosProfitText = formatSignedValue(study.median_window_profit, 1);
        const oosWrRaw = toFiniteNumber(study.median_window_wr);
        const oosWrText = oosWrRaw === null ? 'N/A' : oosWrRaw.toFixed(1);

        const profitClass = (toFiniteNumber(study.profit_pct) || 0) >= 0 ? 'val-positive' : 'val-negative';
        const oosProfitClass = (toFiniteNumber(study.median_window_profit) || 0) >= 0 ? 'val-positive' : 'val-negative';
        const strategyText = escapeHtml(study.strategy || 'Unknown');
        const symbolText = escapeHtml(study.symbol || '-');
        const tfText = escapeHtml(study.tf || '-');
        const wfaModeText = escapeHtml(study.wfa_mode || 'Unknown');
        const isOosText = escapeHtml(study.is_oos || 'N/A');
        const totalTradesText = escapeHtml(formatInteger(study.total_trades, '0'));
        const oosWinsText = escapeHtml(formatOosWins(study));

        html.push(`
          <tr class="clickable analytics-study-row" data-group="${groupToken}" data-study-id="${encodedStudyId}">
            <td class="col-check">
              <input type="checkbox" class="analytics-row-check" data-group="${groupToken}" data-study-id="${encodedStudyId}" ${checked} />
            </td>
            <td>${rowIndex}</td>
            <td>${strategyText}</td>
            <td>${symbolText}</td>
            <td>${tfText}</td>
            <td>${wfaModeText}</td>
            <td>${isOosText}</td>
            <td class="${profitClass}">${profitText}</td>
            <td>${maxDdText}</td>
            <td>${totalTradesText}</td>
            <td>${wfeText}</td>
            <td>${oosWinsText}</td>
            <td class="${oosProfitClass}">${oosProfitText}</td>
            <td>${oosWrText}</td>
          </tr>
        `);
        rowIndex += 1;
      });
    });

    tbody.innerHTML = html.join('');
    syncHierarchyCheckboxes();
  }

  function setAllChecked(checked) {
    getRowCheckboxes().forEach((checkbox) => {
      checkbox.checked = Boolean(checked);
    });
    syncHierarchyCheckboxes();
    notifySelectionChanged();
  }

  function getOrderedStudyIds() {
    return tableState.orderedStudyIds.slice();
  }

  window.AnalyticsTable = {
    renderTable,
    setAllChecked,
    getCheckedStudyIds,
    getOrderedStudyIds,
  };
})();
