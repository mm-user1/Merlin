(function () {
  const FILTER_TO_FIELD = {
    strategy: 'strategy',
    symbol: 'symbol',
    tf: 'tf',
    wfa: 'wfa_mode',
    isOos: 'is_oos',
  };

  const SORT_META = {
    study_name: { label: 'Study Name', bestDirection: 'asc' },
    profit_pct: { label: 'Profit%', bestDirection: 'desc' },
    max_dd_pct: { label: 'MaxDD%', bestDirection: 'asc' },
    total_trades: { label: 'Trades', bestDirection: 'desc' },
    wfe_pct: { label: 'WFE%', bestDirection: 'desc' },
    profitable_windows_pct: { label: 'OOS Wins', bestDirection: 'desc' },
    median_window_profit: { label: 'OOS P(med)', bestDirection: 'desc' },
    median_window_wr: { label: 'OOS WR(med)', bestDirection: 'desc' },
  };

  const tableState = {
    studies: [],
    checkedSet: new Set(),
    visibleSet: new Set(),
    orderedStudyIds: [],
    sortState: {
      sortColumn: null,
      sortDirection: null,
      sortClickCount: 0,
    },
    filters: {
      strategy: null,
      symbol: null,
      tf: null,
      wfa: null,
      isOos: null,
    },
    autoSelect: false,
    onSelectionChange: null,
    onSortChange: null,
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

  function toFiniteNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function parseTimestampMs(value) {
    if (!value) return null;
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function parseDateFlexible(value) {
    const token = String(value || '').trim();
    if (!token) return null;
    const normalized = token.replace(/\./g, '-');
    const parsed = Date.parse(`${normalized}T00:00:00Z`);
    if (!Number.isFinite(parsed)) return null;
    return new Date(parsed);
  }

  function periodDays(start, end) {
    const startDate = parseDateFlexible(start);
    const endDate = parseDateFlexible(end);
    if (!startDate || !endDate) return null;
    const diff = Math.floor((endDate.getTime() - startDate.getTime()) / (24 * 60 * 60 * 1000));
    return Math.max(0, diff);
  }

  function normalizeTfToken(value) {
    const token = String(value || '').trim();
    if (!token) return '';

    const numeric = token.match(/^(\d+)$/);
    if (numeric) {
      const minutes = Number(numeric[1]);
      if (!Number.isFinite(minutes)) return token;
      if (minutes >= 1440 && minutes % 1440 === 0) return `${minutes / 1440}D`;
      if (minutes >= 60 && minutes % 60 === 0) return `${minutes / 60}h`;
      return `${minutes}m`;
    }

    const lower = token.toLowerCase();
    const withM = lower.match(/^(\d+)m$/);
    if (withM) {
      const minutes = Number(withM[1]);
      if (minutes >= 1440 && minutes % 1440 === 0) return `${minutes / 1440}D`;
      if (minutes >= 60 && minutes % 60 === 0) return `${minutes / 60}h`;
      return `${minutes}m`;
    }

    if (/^\d+h$/i.test(token)) return token.toLowerCase();
    if (/^\d+d$/i.test(token)) return `${token.slice(0, -1)}D`;
    if (/^\d+w$/i.test(token)) return token.toLowerCase();
    return token;
  }

  function fallbackStudyName(study) {
    const symbol = String(study?.symbol || '').trim();
    const tf = normalizeTfToken(study?.tf || '');
    if (symbol && tf) return `${symbol}, ${tf}`;
    if (symbol) return symbol;
    if (tf) return tf;
    return 'Unknown';
  }

  function buildDisplayStudyName(study) {
    const rawName = String(study?.study_name || '').trim();
    if (!rawName) return fallbackStudyName(study);

    let working = rawName;
    let counterSuffix = '';

    const counterMatch = working.match(/\s\((\d+)\)\s*$/);
    if (counterMatch) {
      counterSuffix = ` (${counterMatch[1]})`;
      working = working.slice(0, counterMatch.index).trim();
    }

    working = working.replace(/_(WFA|OPT)\s*$/i, '').trim();
    working = working.replace(
      /\s+\d{4}[.\-/]\d{2}[.\-/]\d{2}\s*-\s*\d{4}[.\-/]\d{2}[.\-/]\d{2}\s*$/i,
      ''
    ).trim();
    working = working.replace(/^S\d{2}_/i, '').trim();

    const commaIndex = working.lastIndexOf(',');
    if (commaIndex >= 0) {
      const left = working.slice(0, commaIndex + 1);
      const right = working.slice(commaIndex + 1).trim();
      if (right) {
        working = `${left} ${normalizeTfToken(right)}`.replace(/\s+/g, ' ').trim();
      }
    }

    if (!working) {
      working = fallbackStudyName(study);
    }
    return `${working}${counterSuffix}`.trim();
  }

  function withDerivedFields(study) {
    const createdEpoch = toFiniteNumber(study?.created_at_epoch);
    const completedEpoch = toFiniteNumber(study?.completed_at_epoch);
    const createdMs = createdEpoch === null ? parseTimestampMs(study?.created_at) : createdEpoch * 1000;
    const completedMs = completedEpoch === null ? parseTimestampMs(study?.completed_at) : completedEpoch * 1000;
    return {
      ...study,
      _study_name_display: buildDisplayStudyName(study),
      _created_ms: createdMs,
      _completed_ms: completedMs,
      _default_order_ms: createdMs === null ? completedMs : createdMs,
    };
  }

  function compareDefaultRows(leftStudy, rightStudy) {
    const leftTs = leftStudy?._default_order_ms;
    const rightTs = rightStudy?._default_order_ms;

    if (leftTs === null && rightTs !== null) return 1;
    if (leftTs !== null && rightTs === null) return -1;
    if (leftTs !== null && rightTs !== null && leftTs !== rightTs) return rightTs - leftTs;

    const leftId = String(leftStudy?.study_id || '');
    const rightId = String(rightStudy?.study_id || '');
    return leftId.localeCompare(rightId, undefined, { numeric: true, sensitivity: 'base' });
  }

  function compareNumbersWithNulls(leftValue, rightValue, direction) {
    const left = toFiniteNumber(leftValue);
    const right = toFiniteNumber(rightValue);
    if (left === null && right === null) return 0;
    if (left === null) return 1;
    if (right === null) return -1;
    if (left === right) return 0;
    return direction === 'asc' ? left - right : right - left;
  }

  function compareBySortColumn(leftStudy, rightStudy, sortColumn, sortDirection) {
    if (!sortColumn || !sortDirection) {
      return compareDefaultRows(leftStudy, rightStudy);
    }

    if (sortColumn === 'study_name') {
      const leftText = String(leftStudy?._study_name_display || '');
      const rightText = String(rightStudy?._study_name_display || '');
      const cmp = leftText.localeCompare(rightText, undefined, { numeric: true, sensitivity: 'base' });
      if (cmp !== 0) return sortDirection === 'asc' ? cmp : -cmp;
      return compareDefaultRows(leftStudy, rightStudy);
    }

    const cmp = compareNumbersWithNulls(leftStudy?.[sortColumn], rightStudy?.[sortColumn], sortDirection);
    if (cmp !== 0) return cmp;
    return compareDefaultRows(leftStudy, rightStudy);
  }

  function normalizeFilters(filters) {
    const next = {};
    Object.keys(FILTER_TO_FIELD).forEach((key) => {
      const current = filters?.[key];
      next[key] = current instanceof Set ? new Set(current) : null;
    });
    return next;
  }

  function normalizeSortState(sortState) {
    const sortColumn = sortState?.sortColumn ?? null;
    const sortDirection = sortState?.sortDirection ?? null;
    const clickCount = Number(sortState?.sortClickCount || 0);
    if (!sortColumn || !sortDirection || clickCount <= 0) {
      return {
        sortColumn: null,
        sortDirection: null,
        sortClickCount: 0,
      };
    }
    return {
      sortColumn,
      sortDirection,
      sortClickCount: clickCount,
    };
  }

  function cloneSortState() {
    return {
      sortColumn: tableState.sortState.sortColumn,
      sortDirection: tableState.sortState.sortDirection,
      sortClickCount: tableState.sortState.sortClickCount,
    };
  }

  function setsEqual(leftSet, rightSet) {
    if (leftSet.size !== rightSet.size) return false;
    for (const value of leftSet) {
      if (!rightSet.has(value)) return false;
    }
    return true;
  }

  function matchesFilters(study) {
    return Object.keys(FILTER_TO_FIELD).every((filterKey) => {
      const selected = tableState.filters[filterKey];
      if (!(selected instanceof Set)) return true;
      const field = FILTER_TO_FIELD[filterKey];
      const value = String(study?.[field] ?? '').trim();
      return selected.has(value);
    });
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

  function getStudyRows() {
    const { table } = getTableElements();
    if (!table) return [];
    return Array.from(table.querySelectorAll('tbody tr.analytics-study-row'));
  }

  function isElementVisible(element) {
    if (!element) return false;
    return element.style.display !== 'none';
  }

  function getVisibleRowCheckboxes() {
    return getRowCheckboxes().filter((checkbox) => isElementVisible(checkbox.closest('tr.analytics-study-row')));
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
    getStudyRows().forEach((row) => {
      const checkbox = row.querySelector('.analytics-row-check');
      const checked = Boolean(checkbox && checkbox.checked);
      row.classList.toggle('selected', checked);
    });
  }

  function updateGroupVisibility() {
    const { table } = getTableElements();
    if (!table) return;

    getGroupCheckboxes().forEach((groupCheckbox) => {
      const group = groupCheckbox.dataset.group || '';
      const groupRow = groupCheckbox.closest('tr.analytics-group-row');
      const children = getStudyRows().filter((row) => row.dataset.group === group);
      const visibleChildren = children.filter((row) => isElementVisible(row));
      if (groupRow) {
        groupRow.style.display = visibleChildren.length ? '' : 'none';
      }
    });
  }

  function renumberVisibleRows() {
    let counter = 1;
    getStudyRows().forEach((row) => {
      const numberCell = row.querySelector('.analytics-row-number');
      if (!numberCell) return;
      if (isElementVisible(row)) {
        numberCell.textContent = String(counter);
        counter += 1;
      } else {
        numberCell.textContent = '';
      }
    });
  }

  function syncHierarchyCheckboxes() {
    const { table, headerCheck } = getTableElements();
    if (!table) return;

    getGroupCheckboxes().forEach((groupCheckbox) => {
      const groupKey = groupCheckbox.dataset.group || '';
      const children = Array.from(
        table.querySelectorAll(`tbody .analytics-row-check[data-group="${groupKey}"]`)
      ).filter((checkbox) => isElementVisible(checkbox.closest('tr.analytics-study-row')));

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
      const visibleRows = getVisibleRowCheckboxes();
      const checkedCount = visibleRows.filter((checkbox) => checkbox.checked).length;
      headerCheck.checked = visibleRows.length > 0 && checkedCount === visibleRows.length;
      headerCheck.indeterminate = checkedCount > 0 && checkedCount < visibleRows.length;
    }

    updateRowSelectionClasses();
  }

  function notifySelectionChanged() {
    if (typeof tableState.onSelectionChange !== 'function') return;
    tableState.onSelectionChange(new Set(getCheckedStudyIds()));
  }

  function notifySortChanged() {
    if (typeof tableState.onSortChange !== 'function') return;
    tableState.onSortChange(cloneSortState());
  }

  function updateSortHeaders() {
    const { table } = getTableElements();
    if (!table) return;

    const activeColumn = tableState.sortState.sortColumn;
    const activeDirection = tableState.sortState.sortDirection;

    Array.from(table.querySelectorAll('thead th.analytics-sortable')).forEach((header) => {
      const key = header.dataset.sortKey || '';
      const arrow = header.querySelector('.sort-arrow');
      const active = key && key === activeColumn && activeDirection;

      header.classList.toggle('sort-active', Boolean(active));
      header.classList.toggle('sort-asc', active && activeDirection === 'asc');
      header.classList.toggle('sort-desc', active && activeDirection === 'desc');
      if (arrow) {
        arrow.textContent = active ? (activeDirection === 'asc' ? '▲' : '▼') : '↕';
      }
    });
  }

  function cycleSortForColumn(sortKey) {
    const current = tableState.sortState;

    if (current.sortColumn !== sortKey || !current.sortColumn) {
      const bestDirection = SORT_META[sortKey]?.bestDirection || 'desc';
      tableState.sortState = {
        sortColumn: sortKey,
        sortDirection: bestDirection,
        sortClickCount: 1,
      };
      return;
    }

    if (current.sortClickCount === 1) {
      tableState.sortState = {
        sortColumn: sortKey,
        sortDirection: current.sortDirection === 'asc' ? 'desc' : 'asc',
        sortClickCount: 2,
      };
      return;
    }

    tableState.sortState = {
      sortColumn: null,
      sortDirection: null,
      sortClickCount: 0,
    };
  }

  function buildGroupedStudies() {
    const groupsMap = new Map();
    tableState.studies.forEach((originalStudy) => {
      const study = withDerivedFields(originalStudy);
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
      group.defaultSortedStudies = group.studies.slice().sort(compareDefaultRows);
      group.newestStudy = group.defaultSortedStudies[0] || null;
    });

    groups.sort((left, right) => {
      const baseCmp = compareDefaultRows(left.newestStudy, right.newestStudy);
      if (baseCmp !== 0) return baseCmp;
      return String(left.key).localeCompare(String(right.key), undefined, {
        numeric: true,
        sensitivity: 'base',
      });
    });

    const sortColumn = tableState.sortState.sortColumn;
    const sortDirection = tableState.sortState.sortDirection;
    groups.forEach((group, index) => {
      const rows = sortColumn
        ? group.studies.slice().sort((left, right) => compareBySortColumn(left, right, sortColumn, sortDirection))
        : group.defaultSortedStudies.slice();
      group.displayStudies = rows;
      group.token = `g${index + 1}`;
    });

    return groups;
  }

  function renderTableBody() {
    const { tbody } = getTableElements();
    if (!tbody) return;

    const beforeChecked = new Set(tableState.checkedSet);
    const groups = buildGroupedStudies();
    tableState.orderedStudyIds = [];
    tableState.visibleSet = new Set();

    if (!groups.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="13" class="analytics-empty-cell">No WFA studies found in this database.</td>
        </tr>
      `;
      updateSortHeaders();
      return;
    }

    const html = [];
    const nextChecked = new Set();

    groups.forEach((group) => {
      const groupToken = group.token || '';
      const days = periodDays(group.start, group.end);
      const daysText = days === null ? '?' : String(days);
      const groupStart = escapeHtml(group.start || 'Unknown');
      const groupEnd = escapeHtml(group.end || 'Unknown');

      const rowSnippets = [];
      let visibleChildren = 0;

      group.displayStudies.forEach((study) => {
        const studyId = String(study.study_id || '');
        const encodedStudyId = encodeURIComponent(studyId);
        const visible = matchesFilters(study);
        const checked = tableState.autoSelect ? visible : tableState.checkedSet.has(studyId);
        const styleHidden = visible ? '' : ' style="display:none;"';

        if (checked) nextChecked.add(studyId);
        if (visible) {
          visibleChildren += 1;
          tableState.visibleSet.add(studyId);
        }
        tableState.orderedStudyIds.push(studyId);

        const profitText = escapeHtml(formatSignedValue(study.profit_pct, 1));
        const maxDdText = escapeHtml(formatUnsignedValue(study.max_dd_pct, 1));
        const wfeRaw = toFiniteNumber(study.wfe_pct);
        const wfeText = escapeHtml(wfeRaw === null ? 'N/A' : wfeRaw.toFixed(1));
        const oosProfitText = escapeHtml(formatSignedValue(study.median_window_profit, 1));
        const oosWrRaw = toFiniteNumber(study.median_window_wr);
        const oosWrText = escapeHtml(oosWrRaw === null ? 'N/A' : oosWrRaw.toFixed(1));

        const profitClass = (toFiniteNumber(study.profit_pct) || 0) >= 0 ? 'val-positive' : 'val-negative';
        const oosProfitClass = (toFiniteNumber(study.median_window_profit) || 0) >= 0 ? 'val-positive' : 'val-negative';

        const strategyText = escapeHtml(study.strategy || 'Unknown');
        const studyNameText = escapeHtml(study._study_name_display || fallbackStudyName(study));
        const studyNameTitle = escapeHtml(study.study_name || '');
        const wfaModeText = escapeHtml(study.wfa_mode || 'Unknown');
        const isOosText = escapeHtml(study.is_oos || 'N/A');
        const totalTradesText = escapeHtml(formatInteger(study.total_trades, '0'));
        const oosWinsText = escapeHtml(formatOosWins(study));

        rowSnippets.push(`
          <tr class="clickable analytics-study-row" data-group="${groupToken}" data-study-id="${encodedStudyId}"${styleHidden}>
            <td class="col-check">
              <input type="checkbox" class="analytics-row-check" data-group="${groupToken}" data-study-id="${encodedStudyId}" ${checked ? 'checked' : ''} />
            </td>
            <td class="analytics-row-number"></td>
            <td>${strategyText}</td>
            <td title="${studyNameTitle}">${studyNameText}</td>
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
      });

      const groupHiddenStyle = visibleChildren > 0 ? '' : ' style="display:none;"';
      html.push(`
        <tr class="group-row analytics-group-row" data-group="${groupToken}"${groupHiddenStyle}>
          <td class="col-check"><input type="checkbox" class="analytics-group-check" data-group="${groupToken}" /></td>
          <td colspan="12">
            <div class="group-label">
              <span class="group-dates">${groupStart} &mdash; ${groupEnd}</span>
              <span class="group-duration">(${daysText} days)</span>
              <span class="group-count">${group.displayStudies.length} studies</span>
            </div>
          </td>
        </tr>
      `);
      html.push(...rowSnippets);
    });

    tbody.innerHTML = html.join('');

    tableState.checkedSet = nextChecked;
    updateGroupVisibility();
    renumberVisibleRows();
    syncHierarchyCheckboxes();
    updateSortHeaders();

    const afterChecked = new Set(getCheckedStudyIds());
    tableState.checkedSet = afterChecked;
    if (!setsEqual(beforeChecked, afterChecked)) {
      notifySelectionChanged();
    }
  }

  function formatSignedValue(value, digits) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return 'N/A';
    if (parsed === 0) return `0.${'0'.repeat(digits)}`;
    const sign = parsed > 0 ? '+' : '-';
    return `${sign}${Math.abs(parsed).toFixed(digits)}`;
  }

  function formatUnsignedValue(value, digits) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return 'N/A';
    return Math.abs(parsed).toFixed(digits);
  }

  function formatInteger(value, fallback) {
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

  function bindEventsOnce() {
    if (tableState.bound) return;
    const { table } = getTableElements();
    if (!table) return;

    table.addEventListener('change', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;

      if (target.id === 'analyticsHeaderCheck') {
        getVisibleRowCheckboxes().forEach((checkbox) => {
          checkbox.checked = target.checked;
        });
      } else if (target.classList.contains('analytics-group-check')) {
        const group = target.dataset.group || '';
        getVisibleRowCheckboxes()
          .filter((checkbox) => checkbox.dataset.group === group)
          .forEach((checkbox) => {
            checkbox.checked = target.checked;
          });
      }

      syncHierarchyCheckboxes();
      tableState.checkedSet = new Set(getCheckedStudyIds());
      notifySelectionChanged();
    });

    table.addEventListener('click', (event) => {
      const header = event.target instanceof Element
        ? event.target.closest('th.analytics-sortable')
        : null;
      if (!header) return;
      const sortKey = header.dataset.sortKey || '';
      if (!SORT_META[sortKey]) return;

      tableState.checkedSet = new Set(getCheckedStudyIds());
      cycleSortForColumn(sortKey);
      notifySortChanged();
      renderTableBody();
    });

    tableState.bound = true;
  }

  function renderTable(studies, checkedStudyIds, onSelectionChange, options) {
    const opts = options || {};

    tableState.studies = Array.isArray(studies) ? studies.slice() : [];
    tableState.checkedSet = new Set(Array.from(checkedStudyIds || []));
    tableState.onSelectionChange = onSelectionChange;
    tableState.onSortChange = typeof opts.onSortChange === 'function' ? opts.onSortChange : null;
    tableState.filters = normalizeFilters(opts.filters);
    tableState.autoSelect = Boolean(opts.autoSelect);
    tableState.sortState = normalizeSortState(opts.sortState);

    bindEventsOnce();
    renderTableBody();
  }

  function setAllChecked(checked) {
    getRowCheckboxes().forEach((checkbox) => {
      checkbox.checked = Boolean(checked);
    });
    syncHierarchyCheckboxes();
    tableState.checkedSet = new Set(getCheckedStudyIds());
    notifySelectionChanged();
  }

  function getOrderedStudyIds() {
    return tableState.orderedStudyIds.slice();
  }

  function getSortState() {
    return cloneSortState();
  }

  window.AnalyticsTable = {
    renderTable,
    setAllChecked,
    getCheckedStudyIds,
    getOrderedStudyIds,
    getSortState,
  };
})();
