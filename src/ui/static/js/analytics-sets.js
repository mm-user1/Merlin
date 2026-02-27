(function () {
  const VIEW_MODES = {
    ALL: 'allStudies',
    FOCUS: 'setFocus',
    CHECKBOXES: 'setCheckboxes',
  };

  const state = {
    studies: [],
    studyMap: new Map(),
    sets: [],
    focusedSetId: null,
    checkedSetIds: new Set(),
    viewMode: VIEW_MODES.ALL,
    checkedStudyIds: new Set(),
    forceAllStudies: false,
    moveMode: false,
    moveOriginalOrder: [],
    rangeAnchorSetId: null,
    rangeAnchorChecked: null,
    panelOpen: true,
    panelTouched: false,
    expandedRows: false,
    updateMenuOpen: false,
    onStateChange: null,
    bound: false,
    metricsByGroupId: new Map(),
    metricsBatchKey: null,
    metricsPending: false,
    metricsRequestToken: 0,
    metricsAbortController: null,
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

  function average(values) {
    const finite = values
      .map((value) => toFiniteNumber(value))
      .filter((value) => value !== null);
    if (!finite.length) return null;
    return finite.reduce((acc, value) => acc + value, 0) / finite.length;
  }

  function normalizeSetId(raw) {
    const parsed = Number(raw);
    if (!Number.isInteger(parsed) || parsed <= 0) return null;
    return parsed;
  }

  function cloneCheckedSetIds() {
    return new Set(Array.from(state.checkedSetIds));
  }

  function cloneSetList(rawSets) {
    if (!Array.isArray(rawSets)) return [];
    return rawSets
      .map((setItem) => {
        const id = normalizeSetId(setItem?.id);
        if (id === null) return null;
        const studyIds = Array.isArray(setItem?.study_ids)
          ? setItem.study_ids.map((value) => String(value || '').trim()).filter(Boolean)
          : [];
        return {
          id,
          name: String(setItem?.name || '').trim(),
          sort_order: Number.isFinite(Number(setItem?.sort_order)) ? Number(setItem.sort_order) : 0,
          created_at: setItem?.created_at || null,
          study_ids: studyIds,
        };
      })
      .filter(Boolean)
      .sort((left, right) => {
        if (left.sort_order !== right.sort_order) return left.sort_order - right.sort_order;
        return left.id - right.id;
      });
  }

  function getSetById(setId) {
    const normalized = normalizeSetId(setId);
    if (normalized === null) return null;
    return state.sets.find((item) => item.id === normalized) || null;
  }

  function hasSet(setId) {
    return Boolean(getSetById(setId));
  }

  function getAllSetIds() {
    return state.sets.map((item) => item.id);
  }

  function getCheckedSetArray() {
    return Array.from(state.checkedSetIds)
      .map((setId) => getSetById(setId))
      .filter(Boolean);
  }

  function resolveViewMode() {
    if (state.focusedSetId !== null && !hasSet(state.focusedSetId)) {
      state.focusedSetId = null;
    }
    state.checkedSetIds = new Set(Array.from(state.checkedSetIds).filter((setId) => hasSet(setId)));

    if (state.focusedSetId !== null) {
      state.viewMode = VIEW_MODES.FOCUS;
      return;
    }
    if (state.forceAllStudies) {
      state.viewMode = VIEW_MODES.ALL;
      return;
    }
    if (state.checkedSetIds.size > 0) {
      state.viewMode = VIEW_MODES.CHECKBOXES;
      return;
    }
    state.viewMode = VIEW_MODES.ALL;
  }

  function computeVisibleStudyIds() {
    if (state.viewMode === VIEW_MODES.ALL) return null;
    const ids = new Set();

    if (state.viewMode === VIEW_MODES.FOCUS) {
      const focused = getSetById(state.focusedSetId);
      if (!focused) return new Set();
      focused.study_ids.forEach((studyId) => ids.add(studyId));
      return ids;
    }

    getCheckedSetArray().forEach((setItem) => {
      setItem.study_ids.forEach((studyId) => ids.add(studyId));
    });
    return ids;
  }

  function resolveStudiesForSet(setItem) {
    if (!setItem) return [];
    const studies = [];
    setItem.study_ids.forEach((studyId) => {
      const study = state.studyMap.get(String(studyId || ''));
      if (study) studies.push(study);
    });
    return studies;
  }

  function computeNonCurveMetrics(studies) {
    const list = Array.isArray(studies) ? studies : [];
    if (!list.length) {
      return {
        profitableText: '0/0 (0%)',
        wfePct: null,
        oosWinsPct: null,
      };
    }

    const profitableCount = list.reduce((acc, study) => {
      const profit = toFiniteNumber(study?.profit_pct);
      return acc + (profit !== null && profit > 0 ? 1 : 0);
    }, 0);
    const profitablePct = list.length > 0 ? Math.round((profitableCount / list.length) * 100) : 0;
    const profitableText = `${profitableCount}/${list.length} (${profitablePct}%)`;

    const wfePct = average(list.map((study) => study?.wfe_pct));
    const oosWinsPct = average(list.map((study) => study?.profitable_windows_pct));

    return {
      profitableText,
      wfePct,
      oosWinsPct,
    };
  }

  function computeMetrics(studies, groupId) {
    const list = Array.isArray(studies) ? studies : [];
    const nonCurve = computeNonCurveMetrics(list);
    const curve = state.metricsByGroupId.get(String(groupId || ''));

    return {
      annProfitPct: toFiniteNumber(curve?.ann_profit_pct),
      profitPct: toFiniteNumber(curve?.profit_pct),
      maxDdPct: toFiniteNumber(curve?.max_drawdown_pct),
      profitableText: nonCurve.profitableText,
      wfePct: nonCurve.wfePct,
      oosWinsPct: nonCurve.oosWinsPct,
    };
  }

  function buildMetricsGroups() {
    const groups = [];
    groups.push({
      group_id: 'all',
      study_ids: state.studies
        .map((study) => String(study?.study_id || '').trim())
        .filter(Boolean),
    });

    state.sets.forEach((setItem) => {
      groups.push({
        group_id: `set:${setItem.id}`,
        study_ids: Array.from(new Set(
          (Array.isArray(setItem?.study_ids) ? setItem.study_ids : [])
            .map((studyId) => String(studyId || '').trim())
            .filter(Boolean)
        )),
      });
    });
    return groups;
  }

  function buildMetricsBatchKey(groups) {
    return (Array.isArray(groups) ? groups : [])
      .map((group) => {
        const groupId = String(group?.group_id || '').trim();
        const ids = Array.isArray(group?.study_ids) ? group.study_ids : [];
        return `${groupId}=${ids.join(',')}`;
      })
      .join('|');
  }

  function cancelMetricsRequest() {
    if (state.metricsAbortController) {
      state.metricsAbortController.abort();
      state.metricsAbortController = null;
    }
    state.metricsPending = false;
    state.metricsRequestToken += 1;
  }

  function scheduleMetricsAggregation() {
    if (typeof fetchAnalyticsEquityBatchRequest !== 'function') return;
    const groups = buildMetricsGroups();
    const batchKey = buildMetricsBatchKey(groups);
    if (state.metricsBatchKey === batchKey && state.metricsByGroupId.size) {
      return;
    }

    cancelMetricsRequest();
    state.metricsByGroupId = new Map();
    state.metricsBatchKey = batchKey;

    const requestToken = state.metricsRequestToken + 1;
    state.metricsRequestToken = requestToken;
    state.metricsPending = true;
    const controller = new AbortController();
    state.metricsAbortController = controller;

    fetchAnalyticsEquityBatchRequest(groups, controller.signal)
      .then((payload) => {
        if (requestToken !== state.metricsRequestToken) return;
        if (!payload || !Array.isArray(payload.results)) return;

        const nextMap = new Map();
        payload.results.forEach((item) => {
          const key = String(item?.group_id || '').trim();
          if (!key) return;
          nextMap.set(key, item);
        });
        state.metricsByGroupId = nextMap;
        state.metricsPending = false;
        state.metricsAbortController = null;
        renderTable();
      })
      .catch((error) => {
        if (controller.signal.aborted || error?.name === 'AbortError') {
          return;
        }
        if (requestToken !== state.metricsRequestToken) return;
        state.metricsPending = false;
        state.metricsAbortController = null;
        console.warn('Analytics sets metrics aggregation failed:', error);
      });
  }

  function formatSignedPercent(value, digits = 1) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return 'N/A';
    if (parsed === 0) return `0.${'0'.repeat(digits)}%`;
    const sign = parsed > 0 ? '+' : '-';
    return `${sign}${Math.abs(parsed).toFixed(digits)}%`;
  }

  function formatNegativePercent(value, digits = 1) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return 'N/A';
    return `-${Math.abs(parsed).toFixed(digits)}%`;
  }

  function formatUnsignedPercent(value, digits = 1) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return 'N/A';
    return `${parsed.toFixed(digits)}%`;
  }

  function getSignedClass(value) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return '';
    return parsed >= 0 ? 'val-positive' : 'val-negative';
  }

  function getMaxDdClass(value) {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return '';
    return Math.abs(parsed) > 40 ? 'val-negative' : '';
  }

  function updateStudyMap() {
    state.studyMap = new Map();
    state.studies.forEach((study) => {
      const studyId = String(study?.study_id || '').trim();
      if (studyId) state.studyMap.set(studyId, study);
    });
  }

  function emitStateChange(meta = {}) {
    if (typeof state.onStateChange !== 'function') return;
    state.onStateChange({
      ...meta,
      focusedSetId: state.focusedSetId,
      checkedSetIds: cloneCheckedSetIds(),
      viewMode: state.viewMode,
    });
  }

  function getDom() {
    return {
      section: document.getElementById('analyticsSetsSection'),
      root: document.getElementById('analytics-sets-collapsible'),
      header: document.getElementById('analyticsSetsHeader'),
      summary: document.getElementById('analyticsSetsSummary'),
      updateWrap: document.getElementById('analyticsSetUpdateWrap'),
      updateBtn: document.getElementById('analyticsSetUpdateBtn'),
      updateMenu: document.getElementById('analyticsSetUpdateMenu'),
      saveBtn: document.getElementById('analyticsSaveSetBtn'),
      tableWrap: document.getElementById('analyticsSetsTableWrap'),
      actions: document.getElementById('analyticsSetsActions'),
      expandWrap: document.getElementById('analyticsSetsExpand'),
      expandToggle: document.getElementById('analyticsSetsExpandToggle'),
    };
  }

  function isEventInsideElement(event, element) {
    if (!event || !element) return false;
    const target = event.target instanceof Node ? event.target : null;
    if (!target) return false;
    if (element.contains(target)) return true;
    if (typeof event.composedPath === 'function') {
      const path = event.composedPath();
      if (Array.isArray(path) && path.includes(element)) return true;
    }
    return false;
  }

  function setPanelOpen(open) {
    state.panelOpen = Boolean(open);
    state.panelTouched = true;
    const { root } = getDom();
    if (!root) return;
    root.classList.toggle('open', state.panelOpen);
  }

  function moveFocusedToIndex(targetIndex) {
    if (!state.moveMode || state.focusedSetId === null) return;
    const sourceIndex = state.sets.findIndex((item) => item.id === state.focusedSetId);
    if (sourceIndex < 0) return;

    const boundedTarget = Math.max(0, Math.min(state.sets.length - 1, targetIndex));
    if (boundedTarget === sourceIndex) return;

    const reordered = state.sets.slice();
    const [moved] = reordered.splice(sourceIndex, 1);
    reordered.splice(boundedTarget, 0, moved);
    state.sets = reordered;
    render();
  }

  function startMoveMode() {
    if (state.focusedSetId === null || state.moveMode) return;
    state.updateMenuOpen = false;
    state.moveMode = true;
    state.moveOriginalOrder = state.sets.map((setItem) => setItem.id);
    render();
  }

  async function confirmMoveMode() {
    if (!state.moveMode) return;
    const newOrder = state.sets.map((setItem) => setItem.id);
    const oldOrder = state.moveOriginalOrder.slice();
    const changed = oldOrder.length === newOrder.length
      ? oldOrder.some((value, index) => value !== newOrder[index])
      : true;

    if (!changed) {
      state.moveMode = false;
      state.moveOriginalOrder = [];
      render();
      return;
    }

    try {
      await reorderAnalyticsSetsRequest(newOrder);
      state.moveMode = false;
      state.moveOriginalOrder = [];
      state.sets.forEach((setItem, index) => {
        setItem.sort_order = index;
      });
      render();
      emitStateChange({ reason: 'moveConfirm' });
    } catch (error) {
      window.alert(error?.message || 'Failed to reorder sets.');
    }
  }

  function cancelMoveMode() {
    if (!state.moveMode) return;
    const byId = new Map(state.sets.map((setItem) => [setItem.id, setItem]));
    const restored = state.moveOriginalOrder
      .map((setId) => byId.get(setId))
      .filter(Boolean);
    if (restored.length === state.sets.length) {
      state.sets = restored;
    }
    state.moveMode = false;
    state.moveOriginalOrder = [];
    render();
  }

  function setCheckedSet(setId, checked) {
    const normalized = normalizeSetId(setId);
    if (normalized === null || !hasSet(normalized)) return;
    if (checked) state.checkedSetIds.add(normalized);
    else state.checkedSetIds.delete(normalized);
  }

  function applyRangeSelection(targetSetId) {
    if (state.rangeAnchorSetId === null || typeof state.rangeAnchorChecked !== 'boolean') return false;
    const ids = state.sets.map((item) => item.id);
    const anchorIndex = ids.indexOf(state.rangeAnchorSetId);
    const targetIndex = ids.indexOf(targetSetId);
    if (anchorIndex < 0 || targetIndex < 0) return false;

    const [start, end] = anchorIndex <= targetIndex
      ? [anchorIndex, targetIndex]
      : [targetIndex, anchorIndex];
    for (let index = start; index <= end; index += 1) {
      setCheckedSet(ids[index], state.rangeAnchorChecked);
    }
    return true;
  }

  function rememberRangeAnchor(setId, checked) {
    state.rangeAnchorSetId = normalizeSetId(setId);
    state.rangeAnchorChecked = Boolean(checked);
  }

  function handleAllStudiesClick() {
    if (state.moveMode) return;
    state.updateMenuOpen = false;
    const previousMode = state.viewMode;
    state.focusedSetId = null;
    state.forceAllStudies = true;
    resolveViewMode();
    render();
    if (previousMode !== state.viewMode) {
      emitStateChange({ reason: 'allStudiesClick', syncCheckedStudyIds: null });
    }
  }

  function handleCheckboxToggle(setId, event) {
    if (state.moveMode) return;
    state.updateMenuOpen = false;
    const normalized = normalizeSetId(setId);
    if (normalized === null) return;
    const focused = state.focusedSetId;
    state.forceAllStudies = false;
    const wasChecked = state.checkedSetIds.has(normalized);

    if (event.ctrlKey) {
      const next = !wasChecked;
      getAllSetIds().forEach((id) => setCheckedSet(id, next));
      rememberRangeAnchor(normalized, next);
    } else if (event.shiftKey) {
      if (!applyRangeSelection(normalized)) {
        const next = !wasChecked;
        setCheckedSet(normalized, next);
        rememberRangeAnchor(normalized, next);
      }
    } else {
      const next = !wasChecked;
      setCheckedSet(normalized, next);
      rememberRangeAnchor(normalized, next);
    }

    const prevMode = state.viewMode;
    resolveViewMode();
    render();

    if (focused !== null) {
      emitStateChange({ reason: 'setCheckboxWhileFocus', syncCheckedStudyIds: null });
      return;
    }

    if (state.viewMode === VIEW_MODES.CHECKBOXES) {
      const unionIds = computeVisibleStudyIds();
      emitStateChange({
        reason: 'setCheckboxesChanged',
        syncCheckedStudyIds: Array.from(unionIds || []),
      });
      return;
    }

    if (prevMode !== state.viewMode) {
      emitStateChange({ reason: 'setCheckboxesCleared', syncCheckedStudyIds: null });
    }
  }

  function toggleFocus(setId) {
    if (state.moveMode) return;
    state.updateMenuOpen = false;
    const normalized = normalizeSetId(setId);
    if (normalized === null || !hasSet(normalized)) return;

    if (state.focusedSetId === normalized) {
      state.focusedSetId = null;
      state.forceAllStudies = false;
      resolveViewMode();
      render();
      if (state.viewMode === VIEW_MODES.CHECKBOXES) {
        const unionIds = computeVisibleStudyIds();
        emitStateChange({
          reason: 'setFocusClearedToCheckboxes',
          syncCheckedStudyIds: Array.from(unionIds || []),
        });
      } else {
        emitStateChange({ reason: 'setFocusClearedToAll', syncCheckedStudyIds: null });
      }
      return;
    }

    state.focusedSetId = normalized;
    state.forceAllStudies = false;
    resolveViewMode();
    render();
    const focusedSet = getSetById(normalized);
    emitStateChange({
      reason: 'setFocused',
      syncCheckedStudyIds: Array.from(new Set((focusedSet?.study_ids || []).slice())),
    });
  }

  async function handleSaveSet() {
    const selectedStudyIds = Array.from(state.checkedStudyIds);
    if (!selectedStudyIds.length) return;

    const nameRaw = window.prompt('Enter set name:', '');
    if (nameRaw === null) return;
    const name = String(nameRaw || '').trim();
    if (!name) {
      window.alert('Set name cannot be empty.');
      return;
    }

    try {
      await createAnalyticsSetRequest(name, selectedStudyIds);
      await loadSets({ preserveSelection: true, emitState: true });
    } catch (error) {
      window.alert(error?.message || 'Failed to save set.');
    }
  }

  async function handleRenameSet() {
    const focused = getSetById(state.focusedSetId);
    if (!focused) return;
    const nameRaw = window.prompt('Enter new set name:', focused.name);
    if (nameRaw === null) return;
    const name = String(nameRaw || '').trim();
    if (!name) {
      window.alert('Set name cannot be empty.');
      return;
    }

    try {
      await updateAnalyticsSetRequest(focused.id, { name });
      await loadSets({ preserveSelection: true, emitState: true, preferredFocusId: focused.id });
    } catch (error) {
      window.alert(error?.message || 'Failed to rename set.');
    }
  }

  async function handleDeleteSet() {
    const focused = getSetById(state.focusedSetId);
    if (!focused) return;
    const confirmed = window.confirm(`Delete set "${focused.name}"?`);
    if (!confirmed) return;

    try {
      await deleteAnalyticsSetRequest(focused.id);
      await loadSets({ preserveSelection: true, emitState: false, preferredFocusId: null });
      resolveViewMode();
      render();
      if (state.viewMode === VIEW_MODES.CHECKBOXES) {
        const unionIds = computeVisibleStudyIds();
        emitStateChange({
          reason: 'setDeletedToCheckboxes',
          syncCheckedStudyIds: Array.from(unionIds || []),
        });
      } else {
        emitStateChange({ reason: 'setDeletedToAll', syncCheckedStudyIds: null });
      }
    } catch (error) {
      window.alert(error?.message || 'Failed to delete set.');
    }
  }

  async function updateSetMembers(setItem, preferredFocusId) {
    if (!setItem) return;
    const selectedStudyIds = Array.from(state.checkedStudyIds);
    if (!selectedStudyIds.length) {
      window.alert('Select at least one study before updating a set.');
      return;
    }

    const confirmed = window.confirm(`Update "${setItem.name}" with current selected studies only?`);
    if (!confirmed) return;

    try {
      state.updateMenuOpen = false;
      await updateAnalyticsSetRequest(setItem.id, { study_ids: selectedStudyIds });
      await loadSets({ preserveSelection: true, emitState: true, preferredFocusId });
    } catch (error) {
      window.alert(error?.message || 'Failed to update set members.');
    }
  }

  async function handleUpdateCurrentSet() {
    const focused = getSetById(state.focusedSetId);
    if (!focused) return;
    await updateSetMembers(focused, focused.id);
  }

  async function handleDropdownUpdateSet(setIdRaw) {
    const setId = normalizeSetId(setIdRaw);
    if (setId === null) return;
    const setItem = getSetById(setId);
    if (!setItem) return;
    await updateSetMembers(setItem, null);
  }

  function renderActions() {
    const { actions } = getDom();
    if (!actions) return;

    const focused = getSetById(state.focusedSetId);
    if (!focused) {
      actions.style.display = 'none';
      actions.innerHTML = '';
      return;
    }

    actions.style.display = 'flex';
    if (state.moveMode) {
      actions.innerHTML = '<span class="hint">Move mode active. Enter = save, Esc = cancel.</span>';
      return;
    }

    actions.innerHTML = `
      <button class="sel-btn" id="analyticsSetMoveBtn" type="button">Move</button>
      <button class="sel-btn" id="analyticsSetRenameBtn" type="button">Rename</button>
      <button class="sel-btn" id="analyticsSetDeleteBtn" type="button">Delete</button>
    `;

    const moveBtn = document.getElementById('analyticsSetMoveBtn');
    const renameBtn = document.getElementById('analyticsSetRenameBtn');
    const deleteBtn = document.getElementById('analyticsSetDeleteBtn');
    if (moveBtn) moveBtn.addEventListener('click', startMoveMode);
    if (renameBtn) renameBtn.addEventListener('click', handleRenameSet);
    if (deleteBtn) deleteBtn.addEventListener('click', handleDeleteSet);
  }

  function renderSummaryText() {
    const { summary } = getDom();
    if (!summary) return;
    if (state.focusedSetId !== null) {
      const focused = getSetById(state.focusedSetId);
      if (focused) {
        summary.textContent = `Focused: ${focused.name} (${focused.study_ids.length})`;
        return;
      }
    }
    if (state.viewMode === VIEW_MODES.CHECKBOXES && state.checkedSetIds.size > 0) {
      summary.textContent = `Checked sets: ${state.checkedSetIds.size}`;
      return;
    }
    summary.textContent = '';
  }

  function renderExpandToggle() {
    const { tableWrap, expandWrap, expandToggle } = getDom();
    if (!tableWrap || !expandWrap || !expandToggle) return;
    const shouldShow = state.sets.length > 5;
    expandWrap.style.display = shouldShow ? 'flex' : 'none';
    tableWrap.classList.toggle('expanded', shouldShow && state.expandedRows);
    expandToggle.dataset.expanded = shouldShow && state.expandedRows ? '1' : '0';
    expandToggle.classList.toggle('expanded', shouldShow && state.expandedRows);
  }

  function renderTable() {
    const { tableWrap } = getDom();
    if (!tableWrap) return;

    scheduleMetricsAggregation();
    const allMetrics = computeMetrics(state.studies, 'all');
    const rows = [];
    rows.push(`
      <tr class="analytics-set-all-row" data-all-studies="1">
        <td class="col-check"></td>
        <td title="All WFA studies in active database">All Studies</td>
        <td class="${getSignedClass(allMetrics.annProfitPct)}">${escapeHtml(formatSignedPercent(allMetrics.annProfitPct, 1))}</td>
        <td class="${getSignedClass(allMetrics.profitPct)}">${escapeHtml(formatSignedPercent(allMetrics.profitPct, 1))}</td>
        <td class="${getMaxDdClass(allMetrics.maxDdPct)}">${escapeHtml(formatNegativePercent(allMetrics.maxDdPct, 1))}</td>
        <td>${escapeHtml(allMetrics.profitableText)}</td>
        <td>${escapeHtml(formatUnsignedPercent(allMetrics.wfePct, 1))}</td>
        <td>${escapeHtml(formatUnsignedPercent(allMetrics.oosWinsPct, 1))}</td>
      </tr>
    `);

    state.sets.forEach((setItem) => {
      const setStudies = resolveStudiesForSet(setItem);
      const metrics = computeMetrics(setStudies, `set:${setItem.id}`);
      const checked = state.checkedSetIds.has(setItem.id) ? ' checked' : '';
      const focusedClass = state.focusedSetId === setItem.id ? ' analytics-set-focused' : '';
      const movingClass = state.moveMode && state.focusedSetId === setItem.id ? ' analytics-set-moving' : '';
      const encodedName = escapeHtml(setItem.name || `Set ${setItem.id}`);
      rows.push(`
        <tr class="analytics-set-row${focusedClass}${movingClass}" data-set-id="${setItem.id}">
          <td class="col-check"><input type="checkbox" class="analytics-set-check" data-set-id="${setItem.id}"${checked} /></td>
          <td title="${encodedName}">${encodedName} (${setItem.study_ids.length})</td>
          <td class="${getSignedClass(metrics.annProfitPct)}">${escapeHtml(formatSignedPercent(metrics.annProfitPct, 1))}</td>
          <td class="${getSignedClass(metrics.profitPct)}">${escapeHtml(formatSignedPercent(metrics.profitPct, 1))}</td>
          <td class="${getMaxDdClass(metrics.maxDdPct)}">${escapeHtml(formatNegativePercent(metrics.maxDdPct, 1))}</td>
          <td>${escapeHtml(metrics.profitableText)}</td>
          <td>${escapeHtml(formatUnsignedPercent(metrics.wfePct, 1))}</td>
          <td>${escapeHtml(formatUnsignedPercent(metrics.oosWinsPct, 1))}</td>
        </tr>
      `);
    });

    tableWrap.innerHTML = `
      <table class="analytics-sets-table">
        <thead>
          <tr>
            <th class="col-check"></th>
            <th>Set Name</th>
            <th>Ann.P%</th>
            <th>Profit%</th>
            <th>MaxDD%</th>
            <th>Profitable</th>
            <th>WFE%</th>
            <th>OOS Wins</th>
          </tr>
        </thead>
        <tbody>${rows.join('')}</tbody>
      </table>
    `;

    const allRow = tableWrap.querySelector('tr[data-all-studies="1"]');
    if (allRow) {
      allRow.addEventListener('click', (event) => {
        event.preventDefault();
        handleAllStudiesClick();
      });
    }

    tableWrap.querySelectorAll('tr.analytics-set-row').forEach((row) => {
      const setId = normalizeSetId(row.dataset.setId || '');
      if (setId === null) return;

      const checkbox = row.querySelector('input.analytics-set-check');
      if (checkbox) {
        checkbox.addEventListener('click', (event) => {
          event.preventDefault();
          if (event.altKey) {
            toggleFocus(setId);
            return;
          }
          handleCheckboxToggle(setId, event);
        });
      }

      row.addEventListener('click', (event) => {
        if (event.target && event.target.closest('input.analytics-set-check')) return;
        event.preventDefault();
        if (event.altKey) {
          toggleFocus(setId);
          return;
        }
        handleCheckboxToggle(setId, event);
      });
    });
  }

  function renderHeaderAndButtons() {
    const {
      root,
      updateWrap,
      updateBtn,
      updateMenu,
      saveBtn,
    } = getDom();
    if (root) {
      root.classList.toggle('open', state.panelOpen);
    }

    const hasSets = state.sets.length > 0;
    const focusedSet = getSetById(state.focusedSetId);
    const isFocused = Boolean(focusedSet);
    const canUpdate = hasSets && state.checkedStudyIds.size > 0 && !state.moveMode;

    if (updateWrap) {
      updateWrap.style.display = hasSets ? '' : 'none';
    }

    if (!hasSets || isFocused || !canUpdate) {
      state.updateMenuOpen = false;
    }

    if (updateBtn) {
      updateBtn.disabled = !canUpdate;
      updateBtn.textContent = isFocused ? 'Update Current Set' : 'Update Set ▼';
      updateBtn.setAttribute('aria-haspopup', isFocused ? 'false' : 'menu');
      updateBtn.setAttribute('aria-expanded', !isFocused && state.updateMenuOpen ? 'true' : 'false');
    }

    if (updateMenu) {
      if (!isFocused && canUpdate && state.updateMenuOpen) {
        const menuItems = state.sets
          .map((setItem) => (
            `<button class="analytics-set-update-item" type="button" data-update-set-id="${setItem.id}">`
            + `${escapeHtml(setItem.name)} (${setItem.study_ids.length})`
            + '</button>'
          ))
          .join('');
        updateMenu.innerHTML = menuItems || '<div class="analytics-set-update-empty">No sets available.</div>';
        updateMenu.hidden = false;
        updateMenu.querySelectorAll('[data-update-set-id]').forEach((button) => {
          button.addEventListener('click', async (event) => {
            event.preventDefault();
            event.stopPropagation();
            const setIdRaw = button.getAttribute('data-update-set-id');
            await handleDropdownUpdateSet(setIdRaw);
          });
        });
      } else {
        updateMenu.hidden = true;
        updateMenu.innerHTML = '';
      }
    }

    if (saveBtn) {
      saveBtn.style.display = state.checkedStudyIds.size > 0 ? '' : 'none';
    }
  }

  function render() {
    renderHeaderAndButtons();
    renderSummaryText();
    renderTable();
    renderActions();
    renderExpandToggle();
  }

  function syncFromLoadedSets(newSets, options = {}) {
    const preserveSelection = options.preserveSelection !== false;
    const preferredFocusId = options.preferredFocusId;
    const prevChecked = cloneCheckedSetIds();
    const prevFocused = state.focusedSetId;
    const prevForceAll = state.forceAllStudies;

    state.sets = cloneSetList(newSets);
    state.forceAllStudies = preserveSelection ? prevForceAll : false;
    const availableIds = new Set(state.sets.map((setItem) => setItem.id));

    if (preserveSelection) {
      state.checkedSetIds = new Set(Array.from(prevChecked).filter((setId) => availableIds.has(setId)));
      if (preferredFocusId === null) {
        state.focusedSetId = null;
      } else if (preferredFocusId !== undefined) {
        const preferred = normalizeSetId(preferredFocusId);
        state.focusedSetId = preferred !== null && availableIds.has(preferred) ? preferred : null;
      } else {
        state.focusedSetId = prevFocused !== null && availableIds.has(prevFocused) ? prevFocused : null;
      }
    } else {
      state.checkedSetIds = new Set();
      state.focusedSetId = null;
    }

    resolveViewMode();
    if (!state.panelTouched) {
      state.panelOpen = state.sets.length > 0;
    }
    if (!state.sets.length) {
      state.updateMenuOpen = false;
    }
  }

  async function loadSets(options = {}) {
    const payload = await fetchAnalyticsSetsRequest();
    syncFromLoadedSets(payload?.sets || [], options);
    render();
    if (options.emitState !== false) {
      emitStateChange({ reason: 'setsLoaded', syncCheckedStudyIds: null });
    }
  }

  function updateStudies(studies) {
    cancelMetricsRequest();
    state.metricsByGroupId = new Map();
    state.metricsBatchKey = null;
    state.studies = Array.isArray(studies) ? studies.slice() : [];
    updateStudyMap();
    render();
  }

  function updateCheckedStudyIds(checkedStudyIds) {
    state.checkedStudyIds = new Set(Array.from(checkedStudyIds || []));
    renderHeaderAndButtons();
    renderActions();
  }

  function handleEscapeFromSetFocus() {
    if (state.focusedSetId === null) return false;
    state.updateMenuOpen = false;
    state.focusedSetId = null;
    state.forceAllStudies = false;
    resolveViewMode();
    render();

    if (state.viewMode === VIEW_MODES.CHECKBOXES) {
      const unionIds = computeVisibleStudyIds();
      emitStateChange({
        reason: 'setFocusEscToCheckboxes',
        syncCheckedStudyIds: Array.from(unionIds || []),
      });
    } else {
      emitStateChange({ reason: 'setFocusEscToAll', syncCheckedStudyIds: null });
    }
    return true;
  }

  function bindEventsOnce() {
    if (state.bound) return;
    const {
      section,
      header,
      updateWrap,
      updateBtn,
      saveBtn,
      expandToggle,
    } = getDom();
    if (!section || !header) return;

    header.addEventListener('click', (event) => {
      if (event.target && event.target.closest('#analyticsSaveSetBtn')) return;
      if (event.target && event.target.closest('#analyticsSetUpdateWrap')) return;
      setPanelOpen(!state.panelOpen);
      render();
    });

    if (updateBtn) {
      updateBtn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (state.moveMode || state.sets.length === 0 || state.checkedStudyIds.size === 0) return;
        if (state.focusedSetId !== null) {
          handleUpdateCurrentSet();
          return;
        }
        state.updateMenuOpen = !state.updateMenuOpen;
        renderHeaderAndButtons();
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        handleSaveSet();
      });
    }

    if (expandToggle) {
      expandToggle.addEventListener('click', () => {
        state.expandedRows = !state.expandedRows;
        renderExpandToggle();
      });
    }

    document.addEventListener('keydown', (event) => {
      if (state.updateMenuOpen && event.key === 'Escape') {
        event.preventDefault();
        state.updateMenuOpen = false;
        renderHeaderAndButtons();
        return;
      }

      if (!state.moveMode || event.defaultPrevented) return;
      if (event.key === 'Enter') {
        event.preventDefault();
        confirmMoveMode();
        return;
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        moveFocusedToIndex(state.sets.findIndex((item) => item.id === state.focusedSetId) - 1);
        return;
      }
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        moveFocusedToIndex(state.sets.findIndex((item) => item.id === state.focusedSetId) + 1);
        return;
      }
      if (event.key === 'PageUp') {
        event.preventDefault();
        moveFocusedToIndex(state.sets.findIndex((item) => item.id === state.focusedSetId) - 3);
        return;
      }
      if (event.key === 'PageDown') {
        event.preventDefault();
        moveFocusedToIndex(state.sets.findIndex((item) => item.id === state.focusedSetId) + 3);
        return;
      }
      if (event.key === 'Home') {
        event.preventDefault();
        moveFocusedToIndex(0);
        return;
      }
      if (event.key === 'End') {
        event.preventDefault();
        moveFocusedToIndex(state.sets.length - 1);
      }
    });

    document.addEventListener('pointerdown', (event) => {
      if (state.updateMenuOpen && updateWrap && !isEventInsideElement(event, updateWrap)) {
        state.updateMenuOpen = false;
        renderHeaderAndButtons();
      }

      if (!state.moveMode) return;
      if (isEventInsideElement(event, section)) return;
      cancelMoveMode();
    });

    state.bound = true;
  }

  function init(options = {}) {
    state.onStateChange = typeof options.onStateChange === 'function' ? options.onStateChange : null;
    state.checkedStudyIds = new Set(Array.from(options.checkedStudyIds || []));
    state.forceAllStudies = false;
    state.panelTouched = false;
    state.panelOpen = true;
    state.expandedRows = false;
    state.updateMenuOpen = false;
    state.moveMode = false;
    state.moveOriginalOrder = [];
    state.rangeAnchorSetId = null;
    state.rangeAnchorChecked = null;
    updateStudies(options.studies || []);
    bindEventsOnce();
    render();
  }

  function getVisibleStudyIds() {
    const visible = computeVisibleStudyIds();
    if (visible === null) return null;
    return new Set(Array.from(visible));
  }

  function getCheckedSetIds() {
    return cloneCheckedSetIds();
  }

  function getFocusedSetId() {
    return state.focusedSetId;
  }

  function getViewMode() {
    return state.viewMode;
  }

  function clearFocus() {
    if (state.focusedSetId === null) return;
    state.updateMenuOpen = false;
    state.focusedSetId = null;
    state.forceAllStudies = false;
    resolveViewMode();
    render();
    emitStateChange({ reason: 'setFocusCleared', syncCheckedStudyIds: null });
  }

  function setFocusedSetId(setId, options = {}) {
    const normalized = normalizeSetId(setId);
    if (normalized === null) {
      if (state.focusedSetId === null) return;
      state.updateMenuOpen = false;
      state.focusedSetId = null;
      state.forceAllStudies = false;
      resolveViewMode();
      render();
      if (options.emitState !== false) {
        emitStateChange({ reason: 'setFocusedExternalClear', syncCheckedStudyIds: null });
      }
      return;
    }

    if (!hasSet(normalized)) return;
    state.updateMenuOpen = false;
    state.focusedSetId = normalized;
    state.forceAllStudies = false;
    resolveViewMode();
    render();

    if (options.emitState === false) return;
    const focusedSet = getSetById(normalized);
    emitStateChange({
      reason: 'setFocusedExternal',
      syncCheckedStudyIds: Array.from(new Set((focusedSet?.study_ids || []).slice())),
    });
  }

  function isMoveMode() {
    return state.moveMode;
  }

  function getSets() {
    return state.sets.map((setItem) => ({
      id: setItem.id,
      name: setItem.name,
      sort_order: setItem.sort_order,
      created_at: setItem.created_at,
      study_ids: setItem.study_ids.slice(),
    }));
  }

  window.AnalyticsSets = {
    init,
    updateStudies,
    updateCheckedStudyIds,
    loadSets,
    getFocusedSetId,
    getCheckedSetIds,
    getVisibleStudyIds,
    getViewMode,
    setFocusedSetId,
    clearFocus,
    handleEscapeFromSetFocus,
    cancelMoveMode,
    isMoveMode,
    getSets,
  };
})();
