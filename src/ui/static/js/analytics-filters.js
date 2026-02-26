(function () {
  const FILTER_DEFS = [
    { key: 'strategy', label: 'Strategy', studyField: 'strategy' },
    { key: 'symbol', label: 'Symbol', studyField: 'symbol' },
    { key: 'tf', label: 'TF', studyField: 'tf' },
    { key: 'wfa', label: 'WFA', studyField: 'wfa_mode' },
    { key: 'isOos', label: 'IS/OOS', studyField: 'is_oos' },
  ];

  const state = {
    studies: [],
    options: {},
    filters: {
      strategy: null,
      symbol: null,
      tf: null,
      wfa: null,
      isOos: null,
    },
    openKey: null,
    onChange: null,
    initialized: false,
    outsideBound: false,
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

  function timeframeToMinutes(value) {
    const token = String(value || '').trim().toLowerCase();
    if (!token) return Number.POSITIVE_INFINITY;
    let match = token.match(/^(\d+)(m)?$/);
    if (match) return Number(match[1]);
    match = token.match(/^(\d+)h$/);
    if (match) return Number(match[1]) * 60;
    match = token.match(/^(\d+)d$/);
    if (match) return Number(match[1]) * 1440;
    match = token.match(/^(\d+)w$/);
    if (match) return Number(match[1]) * 10080;
    return Number.POSITIVE_INFINITY;
  }

  function sortValues(key, values) {
    const list = Array.from(values || []);
    if (key === 'tf') {
      list.sort((left, right) => {
        const leftMinutes = timeframeToMinutes(left);
        const rightMinutes = timeframeToMinutes(right);
        if (leftMinutes !== rightMinutes) return leftMinutes - rightMinutes;
        return String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: 'base' });
      });
      return list;
    }
    if (key === 'wfa') {
      const rank = { Fixed: 0, Adaptive: 1, Unknown: 2 };
      list.sort((left, right) => {
        const leftRank = rank[String(left)] ?? 99;
        const rightRank = rank[String(right)] ?? 99;
        if (leftRank !== rightRank) return leftRank - rightRank;
        return String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: 'base' });
      });
      return list;
    }
    list.sort((left, right) => String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: 'base' }));
    return list;
  }

  function cloneFilters(filters) {
    const snapshot = {};
    FILTER_DEFS.forEach((def) => {
      const current = filters?.[def.key];
      snapshot[def.key] = current instanceof Set ? new Set(current) : null;
    });
    return snapshot;
  }

  function filtersEqual(left, right) {
    return FILTER_DEFS.every((def) => {
      const leftSet = left?.[def.key];
      const rightSet = right?.[def.key];
      const leftIsSet = leftSet instanceof Set;
      const rightIsSet = rightSet instanceof Set;
      if (leftIsSet !== rightIsSet) return false;
      if (!leftIsSet) return true;
      if (leftSet.size !== rightSet.size) return false;
      for (const value of leftSet) {
        if (!rightSet.has(value)) return false;
      }
      return true;
    });
  }

  function optionsEqual(left, right) {
    return FILTER_DEFS.every((def) => {
      const leftValues = Array.isArray(left?.[def.key]) ? left[def.key] : [];
      const rightValues = Array.isArray(right?.[def.key]) ? right[def.key] : [];
      if (leftValues.length !== rightValues.length) return false;
      for (let index = 0; index < leftValues.length; index += 1) {
        if (leftValues[index] !== rightValues[index]) return false;
      }
      return true;
    });
  }

  function getFilters() {
    return cloneFilters(state.filters);
  }

  function isFilterActive(filterSet) {
    return filterSet instanceof Set;
  }

  function hasActiveFilters() {
    return FILTER_DEFS.some((def) => isFilterActive(state.filters[def.key]));
  }

  function buildOptions(studies) {
    const next = {};
    FILTER_DEFS.forEach((def) => {
      const values = new Set();
      (Array.isArray(studies) ? studies : []).forEach((study) => {
        const raw = study?.[def.studyField];
        const value = String(raw ?? '').trim();
        if (!value) return;
        values.add(value);
      });
      next[def.key] = sortValues(def.key, values);
    });
    return next;
  }

  function reconcileFilters() {
    FILTER_DEFS.forEach((def) => {
      const values = state.options[def.key] || [];
      const current = state.filters[def.key];
      if (!values.length || current === null) {
        state.filters[def.key] = null;
        return;
      }

      const selected = Array.from(current).filter((value) => values.includes(value));
      if (!selected.length || selected.length === values.length) {
        state.filters[def.key] = null;
        return;
      }
      state.filters[def.key] = new Set(selected);
    });
  }

  function notifyFiltersChanged() {
    if (typeof state.onChange !== 'function') return;
    state.onChange(getFilters());
  }

  function clearAllFilters() {
    FILTER_DEFS.forEach((def) => {
      state.filters[def.key] = null;
    });
    state.openKey = null;
    render();
    notifyFiltersChanged();
  }

  function setAllForFilter(key) {
    state.filters[key] = null;
    render();
    notifyFiltersChanged();
  }

  function toggleFilterValue(key, value, onlyThis) {
    const options = state.options[key] || [];
    if (!options.length) return;

    const current = state.filters[key];
    const selected = current === null ? new Set(options) : new Set(current);

    if (onlyThis) {
      if (selected.size === 1 && selected.has(value)) {
        state.filters[key] = null;
        render();
        notifyFiltersChanged();
        return;
      }
      selected.clear();
      selected.add(value);
    } else if (selected.has(value)) {
      selected.delete(value);
    } else {
      selected.add(value);
    }

    if (!selected.size || selected.size === options.length) {
      state.filters[key] = null;
    } else {
      state.filters[key] = selected;
    }

    render();
    notifyFiltersChanged();
  }

  function getFilterTagText(def, selectedValues) {
    const values = Array.from(selectedValues);
    if (values.length <= 3) {
      return `${def.label}: ${values.join(', ')}`;
    }
    const preview = values.slice(0, 2).join(', ');
    const remainder = values.length - 2;
    return `${def.label}: ${preview}, +${remainder} more`;
  }

  function updateActiveFiltersStrip() {
    const container = document.getElementById('analyticsActiveFilters');
    if (!container) return;

    const activeDefs = FILTER_DEFS.filter((def) => isFilterActive(state.filters[def.key]));
    if (!activeDefs.length) {
      container.hidden = true;
      container.innerHTML = '';
      return;
    }

    container.hidden = false;

    const tagsHtml = activeDefs
      .map((def) => {
        const selectedValues = state.filters[def.key] || new Set();
        const tagText = escapeHtml(getFilterTagText(def, selectedValues));
        return `<button type="button" class="analytics-filter-tag" data-clear-key="${def.key}">${tagText} &times;</button>`;
      })
      .join('');

    container.innerHTML = `
      <div class="analytics-active-label">Active:</div>
      <div class="analytics-active-tags">${tagsHtml}</div>
      <button type="button" class="analytics-clear-all" id="analyticsFiltersClearAll">Clear All</button>
    `;

    container.querySelectorAll('[data-clear-key]').forEach((button) => {
      button.addEventListener('click', () => {
        const key = button.dataset.clearKey || '';
        if (!key) return;
        setAllForFilter(key);
      });
    });

    const clearAllBtn = document.getElementById('analyticsFiltersClearAll');
    if (clearAllBtn) {
      clearAllBtn.addEventListener('click', clearAllFilters);
    }
  }

  function renderFilterControl(def) {
    const options = state.options[def.key] || [];
    if (!options.length) {
      return `
        <div class="analytics-filter">
          <button type="button" class="analytics-filter-btn" disabled>${escapeHtml(def.label)} ▾</button>
        </div>
      `;
    }

    const selected = state.filters[def.key];
    const selectedCount = selected === null ? options.length : selected.size;
    const isAll = selected === null;
    const buttonLabel = isAll ? def.label : `${def.label} (${selectedCount})`;
    const isOpen = state.openKey === def.key;

    const itemsHtml = options
      .map((value) => {
        const encodedValue = encodeURIComponent(value);
        const checked = isAll || selected?.has(value);
        return `
          <label class="analytics-filter-item" data-filter-key="${def.key}" data-filter-value="${encodedValue}">
            <input type="checkbox" ${checked ? 'checked' : ''} />
            <span>${escapeHtml(value)}</span>
          </label>
        `;
      })
      .join('');

    return `
      <div class="analytics-filter ${isOpen ? 'open' : ''}" data-filter="${def.key}">
        <button type="button" class="analytics-filter-btn" data-filter-toggle="${def.key}">
          ${escapeHtml(buttonLabel)} ▾
        </button>
        <div class="analytics-filter-menu" ${isOpen ? '' : 'hidden'}>
          <label class="analytics-filter-item analytics-filter-all" data-filter-key="${def.key}" data-filter-all="1">
            <input type="checkbox" ${isAll ? 'checked' : ''} />
            <span>All</span>
          </label>
          <div class="analytics-filter-divider"></div>
          ${itemsHtml}
        </div>
      </div>
    `;
  }

  function bindFilterEvents() {
    const bar = document.getElementById('analyticsFiltersBar');
    if (!bar) return;

    bar.querySelectorAll('[data-filter-toggle]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        const key = button.dataset.filterToggle || '';
        if (!key) return;
        state.openKey = state.openKey === key ? null : key;
        render();
      });
    });

    bar.querySelectorAll('[data-filter-all]').forEach((item) => {
      item.addEventListener('click', (event) => {
        event.stopPropagation();
      });
      const input = item.querySelector('input[type="checkbox"]');
      if (!input) return;
      input.addEventListener('click', (event) => {
        event.preventDefault();
        const key = item.dataset.filterKey || '';
        if (!key) return;
        setAllForFilter(key);
      });
    });

    bar.querySelectorAll('[data-filter-value]').forEach((item) => {
      item.addEventListener('click', (event) => {
        event.stopPropagation();
      });
      const input = item.querySelector('input[type="checkbox"]');
      if (!input) return;
      input.addEventListener('click', (event) => {
        event.preventDefault();
        const key = item.dataset.filterKey || '';
        const encodedValue = item.dataset.filterValue || '';
        if (!key || !encodedValue) return;
        let value = encodedValue;
        try {
          value = decodeURIComponent(encodedValue);
        } catch (_error) {
          value = encodedValue;
        }
        toggleFilterValue(key, value, Boolean(event.ctrlKey));
      });
    });
  }

  function render() {
    const bar = document.getElementById('analyticsFiltersBar');
    if (!bar) return;

    bar.innerHTML = FILTER_DEFS.map((def) => renderFilterControl(def)).join('');
    bindFilterEvents();
    updateActiveFiltersStrip();
  }

  function bindOutsideClickOnce() {
    if (state.outsideBound) return;
    document.addEventListener('click', () => {
      if (!state.openKey) return;
      state.openKey = null;
      render();
    });
    state.outsideBound = true;
  }

  function updateStudies(studies, options = {}) {
    const emitChange = options.emitChange !== false;
    const beforeOptions = state.options;
    const beforeFilters = getFilters();

    state.studies = Array.isArray(studies) ? studies.slice() : [];
    state.options = buildOptions(state.studies);
    reconcileFilters();

    const afterFilters = getFilters();
    const optionsChanged = !optionsEqual(beforeOptions, state.options);
    const filtersChanged = !filtersEqual(beforeFilters, afterFilters);
    if (optionsChanged || filtersChanged) {
      render();
    }
    if (emitChange && filtersChanged) {
      notifyFiltersChanged();
    }
  }

  function init(params) {
    const payload = params || {};
    state.onChange = typeof payload.onChange === 'function' ? payload.onChange : null;
    state.initialized = true;
    bindOutsideClickOnce();
    updateStudies(payload.studies || [], { emitChange: false });
  }

  window.AnalyticsFilters = {
    init,
    updateStudies,
    clearAll: clearAllFilters,
    getFilters,
    hasActiveFilters,
  };
})();
