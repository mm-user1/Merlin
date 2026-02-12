/**
 * Preset management functions.
 * Dependencies: utils.js, api.js
 */

const DEFAULT_PRESET_KEY = 'defaults';
const PRESET_NAME_PATTERN = /^[A-Za-z0-9 _-]{1,64}$/;
const PRESET_LABELS = {
  dateFilter: 'Date Filter',
  start: 'Start Date/Time',
  end: 'End Date/Time'
};

const DEFAULT_PRESET = {
  dateFilter: true,
  start: '',
  end: ''
};

window.knownPresets = [];
window.selectedCsvPath = '';
window.defaults = clonePreset(DEFAULT_PRESET);
window.uiState = {
  csvPath: ''
};

function formatPresetLabel(key) {
  return PRESET_LABELS[key] || key;
}

function normalizePresetValues(rawValues) {
  const source = clonePreset(rawValues || {});

  if (!source.start && (Object.prototype.hasOwnProperty.call(source, 'startDate') || Object.prototype.hasOwnProperty.call(source, 'startTime'))) {
    source.start = composeISOTimestamp(source.startDate, source.startTime);
  }
  if (!source.end && (Object.prototype.hasOwnProperty.call(source, 'endDate') || Object.prototype.hasOwnProperty.call(source, 'endTime'))) {
    source.end = composeISOTimestamp(source.endDate, source.endTime);
  }

  const normalized = clonePreset(DEFAULT_PRESET);

  if (Object.prototype.hasOwnProperty.call(source, 'dateFilter')) {
    normalized.dateFilter = Boolean(source.dateFilter);
  }
  if (Object.prototype.hasOwnProperty.call(source, 'start')) {
    normalized.start = typeof source.start === 'string' ? source.start.trim() : '';
  }
  if (Object.prototype.hasOwnProperty.call(source, 'end')) {
    normalized.end = typeof source.end === 'string' ? source.end.trim() : '';
  }

  // Preserve any strategy/backtest parameters as-is
  Object.keys(source).forEach((key) => {
    if (['dateFilter', 'start', 'end', 'startDate', 'startTime', 'endDate', 'endTime'].includes(key)) {
      return;
    }
    normalized[key] = source[key];
  });

  return normalized;
}

function applyPresetValues(values, { clearResults = false } = {}) {
  if (!values || typeof values !== 'object') {
    return;
  }

  const normalized = normalizePresetValues(values);
  const csvFileInputEl = document.getElementById('csvFile');
  const optimizerResultsEl = document.getElementById('optimizerResults');
  const progressContainer = document.getElementById('optimizerProgress');

  if (Object.prototype.hasOwnProperty.call(normalized, 'dateFilter')) {
    setCheckboxValue('dateFilter', normalized.dateFilter);
  }
  if (Object.prototype.hasOwnProperty.call(normalized, 'start')) {
    const { date, time } = parseISOTimestamp(normalized.start);
    setInputValue('startDate', date);
    setInputValue('startTime', time);
  }
  if (Object.prototype.hasOwnProperty.call(normalized, 'end')) {
    const { date, time } = parseISOTimestamp(normalized.end);
    setInputValue('endDate', date);
    setInputValue('endTime', time);
  }

  applyDynamicBacktestParams(normalized);

  if (clearResults) {
    if (csvFileInputEl) {
      csvFileInputEl.value = '';
    }
    const resultsEl = document.getElementById('results');
    if (resultsEl) {
      resultsEl.textContent = '';
      resultsEl.classList.remove('ready', 'loading');
    }
    clearErrorMessage();
    if (optimizerResultsEl) {
      optimizerResultsEl.style.display = 'none';
      optimizerResultsEl.textContent = '';
      optimizerResultsEl.classList.remove('ready', 'loading');
    }
    if (progressContainer) {
      progressContainer.style.display = 'none';
    }
  }

  const currentFiles = csvFileInputEl ? Array.from(csvFileInputEl.files || []) : [];
  renderSelectedFiles(currentFiles);
  syncMinProfitFilterUI();
  syncScoreFilterUI();
  updateScoreFormulaPreview();
  if (typeof window.updateDatasetPreview === 'function') {
    window.updateDatasetPreview();
  }
}

function updateDefaults(values) {
  window.defaults = normalizePresetValues(values);
}

function applyDefaults(options = {}) {
  const clearResults =
    options && Object.prototype.hasOwnProperty.call(options, 'clearResults')
      ? Boolean(options.clearResults)
      : true;
  applyPresetValues(window.defaults, { clearResults });
}

async function handleApplyDefaults() {
  closePresetMenu();
  try {
    if (window.currentStrategyId && typeof loadStrategyConfig === 'function') {
      await loadStrategyConfig(window.currentStrategyId);
    }
    applyPresetValues(window.defaults, { clearResults: true });
    clearErrorMessage();
  } catch (error) {
    showErrorMessage(error.message || 'Failed to load defaults.');
  }
}

function collectPresetValues() {
  const start = composeISOTimestamp(
    document.getElementById('startDate')?.value,
    document.getElementById('startTime')?.value
  );
  const end = composeISOTimestamp(
    document.getElementById('endDate')?.value,
    document.getElementById('endTime')?.value
  );

  const dynamicParams = collectDynamicBacktestParams();

  return {
    dateFilter: Boolean(document.getElementById('dateFilter')?.checked),
    start: start || window.defaults.start,
    end: end || window.defaults.end,
    ...dynamicParams
  };
}

async function loadPreset(name, { clearResults = false } = {}) {
  const data = await loadPresetRequest(name);
  const values = data?.values || {};
  if (name.toLowerCase() === DEFAULT_PRESET_KEY) {
    updateDefaults(values);
    applyDefaults({ clearResults });
  } else {
    applyPresetValues(values, { clearResults });
  }
  return values;
}

function renderPresetList() {
  const presetListEl = document.getElementById('presetList');
  const presetEmptyEl = document.getElementById('presetEmpty');

  if (!presetListEl || !presetEmptyEl) {
    return;
  }

  presetListEl.innerHTML = '';
  const userPresets = window.knownPresets.filter((item) => !item.is_default);
  if (!userPresets.length) {
    presetEmptyEl.style.display = 'block';
    return;
  }

  presetEmptyEl.style.display = 'none';
  const fragment = document.createDocumentFragment();
  userPresets.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'preset-item';

    const applyButton = document.createElement('button');
    applyButton.type = 'button';
    applyButton.className = 'preset-entry';
    applyButton.textContent = item.name;
    applyButton.addEventListener('click', (event) => {
      event.stopPropagation();
      handlePresetSelection(item.name);
    });

    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'preset-actions';

    const overwriteButton = document.createElement('button');
    overwriteButton.type = 'button';
    overwriteButton.className = 'preset-action-btn preset-overwrite';
    overwriteButton.setAttribute('aria-label', `Overwrite preset ${item.name}`);
    overwriteButton.title = 'Overwrite preset';
    overwriteButton.textContent = 'Overwrite';
    overwriteButton.addEventListener('click', (event) => {
      event.stopPropagation();
      handlePresetOverwrite(item.name);
    });

    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'preset-action-btn preset-delete';
    deleteButton.setAttribute('aria-label', `Delete preset ${item.name}`);
    deleteButton.title = 'Delete preset';
    deleteButton.textContent = 'Delete';
    deleteButton.addEventListener('click', (event) => {
      event.stopPropagation();
      handlePresetDelete(item.name);
    });

    actionsContainer.appendChild(overwriteButton);
    actionsContainer.appendChild(deleteButton);
    row.appendChild(applyButton);
    row.appendChild(actionsContainer);
    fragment.appendChild(row);
  });

  presetListEl.appendChild(fragment);
}

async function refreshPresetList(silent = false) {
  try {
    const data = await fetchPresetsList();
    window.knownPresets = Array.isArray(data?.presets) ? data.presets : [];
  } catch (error) {
    window.knownPresets = [];
    if (!silent) {
      showErrorMessage(error.message || 'Failed to fetch presets.');
    }
    console.error(error);
  }
  renderPresetList();
}

function openPresetMenu() {
  const presetDropdownEl = document.getElementById('presetDropdown');
  const presetToggleEl = document.getElementById('presetToggle');
  const presetMenuEl = document.getElementById('presetMenu');

  if (!presetDropdownEl) return;

  presetDropdownEl.classList.add('open');
  if (presetToggleEl) presetToggleEl.setAttribute('aria-expanded', 'true');
  if (presetMenuEl) presetMenuEl.setAttribute('aria-hidden', 'false');
}

function closePresetMenu() {
  const presetDropdownEl = document.getElementById('presetDropdown');
  const presetToggleEl = document.getElementById('presetToggle');
  const presetMenuEl = document.getElementById('presetMenu');

  if (!presetDropdownEl) return;

  presetDropdownEl.classList.remove('open');
  if (presetToggleEl) presetToggleEl.setAttribute('aria-expanded', 'false');
  if (presetMenuEl) presetMenuEl.setAttribute('aria-hidden', 'true');
}

function togglePresetMenu() {
  const presetDropdownEl = document.getElementById('presetDropdown');
  if (!presetDropdownEl) return;

  if (presetDropdownEl.classList.contains('open')) {
    closePresetMenu();
  } else {
    openPresetMenu();
  }
}

async function handleApplyDefaults() {
  closePresetMenu();
  try {
    await loadPreset(DEFAULT_PRESET_KEY, { clearResults: true });
    clearErrorMessage();
  } catch (error) {
    showErrorMessage(error.message || 'Failed to load defaults.');
  }
}

async function handlePresetSelection(name) {
  closePresetMenu();
  try {
    await loadPreset(name, { clearResults: false });
    clearErrorMessage();
  } catch (error) {
    showErrorMessage(error.message || 'Failed to load preset.');
  }
}

async function handleSaveAsPreset() {
  closePresetMenu();
  const values = collectPresetValues();
  let presetName = '';

  while (true) {
    const input = window.prompt('Enter preset name:', '');
    if (input === null) return;

    const trimmed = input.trim();
    if (!trimmed) {
      window.alert('Preset name cannot be empty.');
      continue;
    }
    if (trimmed.toLowerCase() === DEFAULT_PRESET_KEY) {
      window.alert('Cannot use name "defaults".');
      continue;
    }
    if (!PRESET_NAME_PATTERN.test(trimmed)) {
      window.alert('Name can only contain letters, numbers, spaces, hyphens and underscores.');
      continue;
    }
    if (window.knownPresets.some((item) => item.name.toLowerCase() === trimmed.toLowerCase())) {
      window.alert('Preset with this name already exists.');
      continue;
    }
    presetName = trimmed;
    break;
  }

  try {
    await savePresetRequest(presetName, values);
    await refreshPresetList(false);
    window.alert(`Preset "${presetName}" saved.`);
  } catch (error) {
    showErrorMessage(error.message || 'Failed to save preset.');
  }
}

async function handlePresetDelete(name) {
  const confirmed = window.confirm(`Delete preset "${name}"?`);
  if (!confirmed) return;

  closePresetMenu();
  try {
    await deletePresetRequest(name);
    await refreshPresetList(false);
  } catch (error) {
    showErrorMessage(error.message || 'Failed to delete preset.');
  }
}

async function handlePresetOverwrite(name) {
  const confirmed = window.confirm(`Overwrite preset "${name}" with current settings?`);
  if (!confirmed) return;

  closePresetMenu();
  const values = collectPresetValues();
  try {
    await overwritePresetRequest(name, values);
    await refreshPresetList(false);
    window.alert(`Preset "${name}" overwritten.`);
  } catch (error) {
    showErrorMessage(error.message || 'Failed to overwrite preset.');
  }
}

async function initializePresets() {
  try {
    await loadPreset(DEFAULT_PRESET_KEY, { clearResults: true });
  } catch (error) {
    console.warn('Failed to load defaults preset at startup, using local fallback.', error);
    applyDefaults({ clearResults: true });
  }
  await refreshPresetList(true);
}

function handleImportAction() {
  const presetImportInput = document.getElementById('presetImportInput');
  if (!presetImportInput) {
    return;
  }
  presetImportInput.value = '';
  presetImportInput.click();
}
