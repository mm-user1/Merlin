/**
 * Preset management functions.
 * Dependencies: utils.js, api.js
 */

const DEFAULT_PRESET_KEY = 'defaults';
const PRESET_NAME_PATTERN = /^[A-Za-z0-9 _-]{1,64}$/;
const PRESET_LABELS = {
  dateFilter: 'Date Filter',
  backtester: 'Backtester',
  startDate: 'Start Date',
  startTime: 'Start Time',
  endDate: 'End Date',
  endTime: 'End Time',
  csvPath: 'CSV Path',
  workerProcesses: 'Worker Processes',
  minProfitFilter: 'Net Profit Filter',
  minProfitThreshold: 'Net Profit Min %',
  scoreFilterEnabled: 'Score Filter',
  scoreThreshold: 'Score Min Score',
  scoreWeights: 'Score Weights',
  scoreEnabledMetrics: 'Score Enabled Metrics',
  scoreInvertMetrics: 'Score Invert Metrics'
};

window.knownPresets = [];
window.selectedCsvPath = '';
window.defaults = {
  dateFilter: true,
  backtester: true,
  startDate: '',
  startTime: '',
  endDate: '',
  endTime: '',
  csvPath: '',
  workerProcesses: 6,
  minProfitFilter: false,
  minProfitThreshold: 0,
  scoreFilterEnabled: false,
  scoreThreshold: 60,
  scoreWeights: { romad: 0.25, sharpe: 0.20, pf: 0.20, ulcer: 0.15, recovery: 0.10, consistency: 0.10 },
  scoreEnabledMetrics: { romad: true, sharpe: true, pf: true, ulcer: true, recovery: true, consistency: true },
  scoreInvertMetrics: { ulcer: true }
};

function formatPresetLabel(key) {
  return PRESET_LABELS[key] || key;
}

function applyPresetValues(values, { clearResults = false } = {}) {
  if (!values || typeof values !== 'object') {
    return;
  }

  const csvFileInputEl = document.getElementById('csvFile');
  const optimizerResultsEl = document.getElementById('optimizerResults');
  const progressContainer = document.getElementById('optimizerProgress');

  if (Object.prototype.hasOwnProperty.call(values, 'csvPath')) {
    const csvPathValue = typeof values.csvPath === 'string' ? values.csvPath.trim() : '';
    window.selectedCsvPath = csvPathValue;
  } else {
    window.selectedCsvPath = '';
  }

  if (Object.prototype.hasOwnProperty.call(values, 'dateFilter')) {
    setCheckboxValue('dateFilter', values.dateFilter);
  }
  if (Object.prototype.hasOwnProperty.call(values, 'backtester')) {
    setCheckboxValue('backtester', values.backtester);
  }
  if (Object.prototype.hasOwnProperty.call(values, 'startDate')) {
    setInputValue('startDate', values.startDate);
  }
  if (Object.prototype.hasOwnProperty.call(values, 'startTime')) {
    setInputValue('startTime', values.startTime);
  }
  if (Object.prototype.hasOwnProperty.call(values, 'endDate')) {
    setInputValue('endDate', values.endDate);
  }
  if (Object.prototype.hasOwnProperty.call(values, 'endTime')) {
    setInputValue('endTime', values.endTime);
  }

  if (Object.prototype.hasOwnProperty.call(values, 'workerProcesses')) {
    const workerInput = document.getElementById('workerProcesses');
    if (workerInput) {
      workerInput.value = values.workerProcesses;
    }
  }

  const { checkbox: minProfitCheckbox, input: minProfitInput } = getMinProfitElements();
  if (minProfitCheckbox && Object.prototype.hasOwnProperty.call(values, 'minProfitFilter')) {
    minProfitCheckbox.checked = Boolean(values.minProfitFilter);
  }
  if (minProfitInput && Object.prototype.hasOwnProperty.call(values, 'minProfitThreshold')) {
    setInputValue('minProfitThreshold', values.minProfitThreshold);
  }

  const scoreSettings = {
    scoreFilterEnabled: Object.prototype.hasOwnProperty.call(values, 'scoreFilterEnabled')
      ? values.scoreFilterEnabled
      : window.defaults.scoreFilterEnabled,
    scoreThreshold: Object.prototype.hasOwnProperty.call(values, 'scoreThreshold')
      ? values.scoreThreshold
      : window.defaults.scoreThreshold,
    scoreWeights: clonePreset(
      Object.prototype.hasOwnProperty.call(values, 'scoreWeights')
        ? values.scoreWeights
        : window.defaults.scoreWeights
    ),
    scoreEnabledMetrics: clonePreset(
      Object.prototype.hasOwnProperty.call(values, 'scoreEnabledMetrics')
        ? values.scoreEnabledMetrics
        : window.defaults.scoreEnabledMetrics
    ),
    scoreInvertMetrics: clonePreset(
      Object.prototype.hasOwnProperty.call(values, 'scoreInvertMetrics')
        ? values.scoreInvertMetrics
        : window.defaults.scoreInvertMetrics
    )
  };
  applyScoreSettings(scoreSettings);

  applyDynamicBacktestParams(values);

  if (clearResults) {
    if (csvFileInputEl) {
      csvFileInputEl.value = '';
    }
    const resultsEl = document.getElementById('results');
    if (resultsEl) {
      resultsEl.textContent = '?ø?ñ‘\'ç ‚<Run‚> ?>‘? úøõ‘?‘?óø +‘?ó‘\'ç‘?‘\'ø¢?³';
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
}

function updateDefaults(values) {
  const merged = { ...window.defaults, ...clonePreset(values) };
  window.defaults = merged;
}

function applyDefaults(options = {}) {
  const clearResults =
    options && Object.prototype.hasOwnProperty.call(options, 'clearResults')
      ? Boolean(options.clearResults)
      : true;
  applyPresetValues(window.defaults, { clearResults });
}

function collectPresetValues() {
  const { checkbox: minProfitCheckbox, input: minProfitInput } = getMinProfitElements();
  const workerInput = document.getElementById('workerProcesses');
  const csvPathValue = typeof window.selectedCsvPath === 'string' ? window.selectedCsvPath.trim() : '';
  const scoreState = readScoreUIState();
  const dynamicParams = collectDynamicBacktestParams();

  return {
    dateFilter: document.getElementById('dateFilter').checked,
    backtester: document.getElementById('backtester').checked,
    startDate: document.getElementById('startDate').value.trim(),
    startTime: document.getElementById('startTime').value.trim(),
    endDate: document.getElementById('endDate').value.trim(),
    endTime: document.getElementById('endTime').value.trim(),
    csvPath: csvPathValue,
    workerProcesses: workerInput
      ? parseNumber(workerInput.value, window.defaults.workerProcesses)
      : window.defaults.workerProcesses,
    minProfitFilter: Boolean(minProfitCheckbox && minProfitCheckbox.checked),
    minProfitThreshold: minProfitInput
      ? parseNumber(minProfitInput.value, window.defaults.minProfitThreshold)
      : window.defaults.minProfitThreshold,
    scoreFilterEnabled: Boolean(scoreState.scoreFilterEnabled),
    scoreThreshold: scoreState.scoreThreshold,
    scoreWeights: { ...scoreState.scoreWeights },
    scoreEnabledMetrics: { ...scoreState.scoreEnabledMetrics },
    scoreInvertMetrics: { ...scoreState.scoreInvertMetrics },
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
    overwriteButton.textContent = '¢??';
    overwriteButton.addEventListener('click', (event) => {
      event.stopPropagation();
      handlePresetOverwrite(item.name);
    });

    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'preset-action-btn preset-delete';
    deleteButton.setAttribute('aria-label', `Delete preset ${item.name}`);
    deleteButton.title = 'Delete preset';
    deleteButton.textContent = '¢?';
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

async function handleSaveDefaults() {
  closePresetMenu();
  const values = collectPresetValues();
  try {
    const response = await saveDefaultsRequest(values);
    updateDefaults(response?.values || values);
    window.alert('Current settings saved as defaults.');
  } catch (error) {
    showErrorMessage(error.message || 'Failed to save defaults.');
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
    clearErrorMessage();
  } catch (error) {
    console.error(error);
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
