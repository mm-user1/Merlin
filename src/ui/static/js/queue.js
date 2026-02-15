/**
 * Run queue management for optimization / walk-forward execution.
 * Dependencies: utils.js, api.js, ui-handlers.js, strategy-config.js, presets.js
 */

const QUEUE_STORAGE_KEY = 'merlinRunQueue';
const QUEUE_FILE_DB_NAME = 'merlinQueueFiles';
const QUEUE_FILE_STORE = 'files';
const QUEUE_FILE_DB_VERSION = 1;
const CONSTRAINT_LE_METRICS = ['max_drawdown_pct', 'max_consecutive_losses', 'ulcer_index'];

let queueRunning = false;
let queueFileDbPromise = null;

function isAbsoluteFilesystemPath(path) {
  const value = String(path || '').trim();
  if (!value) return false;
  if (/^[A-Za-z]:[\\/]/.test(value)) return true; // Windows drive path
  if (/^\\\\[^\\]/.test(value)) return true; // UNC path
  if (value.startsWith('/')) return true; // POSIX path
  return false;
}

function getPathFileName(path) {
  return String(path || '').split(/[/\\]/).pop() || '';
}

function isBlobLike(value) {
  return Boolean(
    value
      && typeof value === 'object'
      && typeof value.size === 'number'
      && typeof value.type === 'string'
      && typeof value.arrayBuffer === 'function'
  );
}

function makeQueueFileKey(itemId, sourceIndex, fileName) {
  const safeName = String(fileName || 'file').replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 64);
  return itemId + '_' + sourceIndex + '_' + Date.now() + '_' + safeName;
}

function buildSourceDisplayLabel(source, fallbackIndex = 0) {
  if (!source || typeof source !== 'object') return 'source_' + (fallbackIndex + 1);
  if (source.type === 'path') {
    return getPathFileName(source.path) || String(source.path || '').trim() || ('source_' + (fallbackIndex + 1));
  }
  return String(source.name || '').trim() || ('source_' + (fallbackIndex + 1) + '.csv');
}

function buildSourceModeLabel(source) {
  return source && source.type === 'file' ? 'FILE' : 'PATH';
}

function normalizeQueueSource(rawSource, fallbackIndex) {
  if (!rawSource || typeof rawSource !== 'object') return null;
  const type = rawSource.type === 'file' ? 'file' : 'path';

  if (type === 'path') {
    const path = String(rawSource.path || '').trim();
    if (!path) return null;
    return { type: 'path', path };
  }

  const fileKey = String(rawSource.fileKey || '').trim();
  if (!fileKey) return null;

  const name = String(rawSource.name || '').trim() || ('source_' + (fallbackIndex + 1) + '.csv');
  const sizeRaw = Number(rawSource.size);
  const lastModifiedRaw = Number(rawSource.lastModified);
  return {
    type: 'file',
    fileKey,
    name,
    size: Number.isFinite(sizeRaw) && sizeRaw >= 0 ? Math.floor(sizeRaw) : 0,
    lastModified: Number.isFinite(lastModifiedRaw) && lastModifiedRaw >= 0 ? Math.floor(lastModifiedRaw) : 0
  };
}

function getQueueSources(item) {
  if (!item || typeof item !== 'object') return [];

  const rawSources = Array.isArray(item.sources) ? item.sources : [];

  const sources = [];
  rawSources.forEach((source, index) => {
    const normalized = normalizeQueueSource(source, index);
    if (normalized) {
      if (source && typeof source === 'object' && source.type === 'file' && source._file) {
        normalized._file = source._file;
      }
      sources.push(normalized);
    }
  });
  return sources;
}

function cloneSourcesForStorage(sources) {
  return (Array.isArray(sources) ? sources : [])
    .map((source, index) => normalizeQueueSource(source, index))
    .filter(Boolean)
    .map((source) => {
      if (source.type === 'file') {
        return {
          type: 'file',
          fileKey: source.fileKey,
          name: source.name,
          size: source.size || 0,
          lastModified: source.lastModified || 0
        };
      }
      return {
        type: 'path',
        path: source.path
      };
    });
}

function collectFileKeysFromItem(item) {
  return getQueueSources(item)
    .filter((source) => source.type === 'file' && source.fileKey)
    .map((source) => source.fileKey);
}

function normalizeQueueItem(raw, fallbackIndex) {
  if (!raw || typeof raw !== 'object') return null;

  const sources = getQueueSources(raw);
  if (!sources.length) return null;

  const indexRaw = Number(raw.index);
  const index = Number.isFinite(indexRaw) && indexRaw > 0
    ? Math.round(indexRaw)
    : Math.max(1, fallbackIndex);

  const item = {
    ...raw,
    index,
    sources: cloneSourcesForStorage(sources)
  };

  const cursorRaw = Number(raw.sourceCursor);
  item.sourceCursor = Number.isFinite(cursorRaw)
    ? Math.max(0, Math.min(item.sources.length, Math.floor(cursorRaw)))
    : 0;

  const successRaw = Number(raw.successCount);
  item.successCount = Number.isFinite(successRaw) ? Math.max(0, Math.floor(successRaw)) : 0;

  const failureRaw = Number(raw.failureCount);
  item.failureCount = Number.isFinite(failureRaw) ? Math.max(0, Math.floor(failureRaw)) : 0;

  if (typeof item.label !== 'string' || !item.label.trim()) {
    item.label = generateQueueLabel(item);
  }

  return item;
}

function loadQueue() {
  try {
    const raw = localStorage.getItem(QUEUE_STORAGE_KEY);
    if (!raw) return { items: [], nextIndex: 1 };

    const parsed = JSON.parse(raw);
    const rawItems = parsed && Array.isArray(parsed.items) ? parsed.items : [];
    const items = [];
    rawItems.forEach((item, idx) => {
      const normalized = normalizeQueueItem(item, idx + 1);
      if (normalized) items.push(normalized);
    });

    const maxIndex = items.reduce((acc, item) => Math.max(acc, Number(item.index) || 0), 0);
    const parsedNext = Number(parsed && parsed.nextIndex);
    const nextIndex = Number.isFinite(parsedNext) && parsedNext > maxIndex
      ? Math.floor(parsedNext)
      : (maxIndex + 1);

    return {
      items,
      nextIndex: Math.max(1, nextIndex)
    };
  } catch (error) {
    console.warn('Failed to load queue from localStorage', error);
    return { items: [], nextIndex: 1 };
  }
}

function saveQueue(queue) {
  try {
    const items = Array.isArray(queue && queue.items)
      ? queue.items.map((item, idx) => {
        const normalized = normalizeQueueItem(item, idx + 1);
        if (!normalized) return null;
        return {
          ...normalized,
          sources: cloneSourcesForStorage(normalized.sources)
        };
      }).filter(Boolean)
      : [];
    const maxIndex = items.reduce((acc, item) => Math.max(acc, Number(item.index) || 0), 0);
    const nextRaw = Number(queue && queue.nextIndex);
    const nextIndex = Number.isFinite(nextRaw) && nextRaw > maxIndex
      ? Math.floor(nextRaw)
      : (maxIndex + 1);
    localStorage.setItem(QUEUE_STORAGE_KEY, JSON.stringify({
      items,
      nextIndex: Math.max(1, nextIndex)
    }));
  } catch (error) {
    console.warn('Failed to save queue to localStorage', error);
  }
}

function isQueueRunning() {
  return queueRunning;
}

function supportsQueueFileStorage() {
  return typeof indexedDB !== 'undefined';
}

function openQueueFileDb() {
  if (!supportsQueueFileStorage()) {
    return Promise.reject(new Error('IndexedDB is not available in this environment.'));
  }
  if (queueFileDbPromise) return queueFileDbPromise;

  queueFileDbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(QUEUE_FILE_DB_NAME, QUEUE_FILE_DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(QUEUE_FILE_STORE)) {
        db.createObjectStore(QUEUE_FILE_STORE);
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => {
      queueFileDbPromise = null;
      reject(request.error || new Error('Failed to open queue file storage.'));
    };
    request.onblocked = () => {
      queueFileDbPromise = null;
      reject(new Error('Queue file storage is blocked.'));
    };
  });

  return queueFileDbPromise;
}

function withQueueFileStore(mode, handler) {
  return openQueueFileDb().then((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_FILE_STORE, mode);
    const store = tx.objectStore(QUEUE_FILE_STORE);
    let settled = false;
    let hasResult = false;
    let resultValue;

    const fail = (error) => {
      if (settled) return;
      settled = true;
      reject(error);
    };

    const done = (error, value) => {
      if (error) {
        fail(error);
        return;
      }
      hasResult = true;
      resultValue = value;
    };

    tx.oncomplete = () => {
      if (settled) return;
      settled = true;
      resolve(hasResult ? resultValue : undefined);
    };
    tx.onabort = () => fail(tx.error || new Error('Queue file storage transaction aborted.'));
    tx.onerror = () => fail(tx.error || new Error('Queue file storage transaction failed.'));

    try {
      handler(store, done);
    } catch (error) {
      fail(error);
    }
  }));
}

function putQueuedFileBlob(fileKey, fileBlob) {
  return withQueueFileStore('readwrite', (store, done) => {
    const request = store.put(fileBlob, fileKey);
    request.onsuccess = () => done(null, true);
    request.onerror = () => done(request.error || new Error('Failed to store queued file.'));
  });
}

function getQueuedFileBlob(fileKey) {
  return withQueueFileStore('readonly', (store, done) => {
    const request = store.get(fileKey);
    request.onsuccess = () => done(null, request.result || null);
    request.onerror = () => done(request.error || new Error('Failed to load queued file.'));
  });
}

function deleteQueuedFileBlob(fileKey) {
  return withQueueFileStore('readwrite', (store, done) => {
    const request = store.delete(fileKey);
    request.onsuccess = () => done(null, true);
    request.onerror = () => done(request.error || new Error('Failed to delete queued file.'));
  });
}

async function deleteQueuedFileKeys(keys) {
  if (!supportsQueueFileStorage()) return;
  const uniqueKeys = Array.from(new Set((keys || []).map((key) => String(key || '').trim()).filter(Boolean)));
  for (const key of uniqueKeys) {
    try {
      await deleteQueuedFileBlob(key);
    } catch (error) {
      console.warn('Failed to clean queued file key:', key, error);
    }
  }
}

function listQueuedFileKeys() {
  if (!supportsQueueFileStorage()) return Promise.resolve([]);
  return withQueueFileStore('readonly', (store, done) => {
    const keys = [];
    const request = store.openCursor();
    request.onsuccess = (event) => {
      const cursor = event.target.result;
      if (!cursor) {
        done(null, keys);
        return;
      }
      keys.push(String(cursor.key || ''));
      cursor.continue();
    };
    request.onerror = () => done(request.error || new Error('Failed to list queued file keys.'));
  });
}

async function cleanupStaleQueueFiles() {
  if (!supportsQueueFileStorage()) return;
  const queue = loadQueue();
  const validKeys = new Set();
  queue.items.forEach((item) => {
    collectFileKeysFromItem(item).forEach((key) => validKeys.add(key));
  });

  try {
    const storedKeys = await listQueuedFileKeys();
    const staleKeys = storedKeys.filter((key) => !validKeys.has(key));
    await deleteQueuedFileKeys(staleKeys);
  } catch (error) {
    console.warn('Failed to clean stale queue file blobs', error);
  }
}

function setQueueControlsDisabled(disabled) {
  const addBtn = document.getElementById('addToQueueBtn');
  const clearBtn = document.getElementById('clearQueueBtn');
  if (addBtn) addBtn.disabled = Boolean(disabled);
  if (clearBtn) clearBtn.disabled = Boolean(disabled);

  const removeButtons = document.querySelectorAll('.queue-item-remove');
  removeButtons.forEach((btn) => {
    const isLocked = btn.dataset.locked === '1';
    btn.disabled = Boolean(disabled) || isLocked;
    btn.style.visibility = btn.disabled ? 'hidden' : 'visible';
  });
}

function requestServerCancelBestEffort() {
  if (typeof cancelOptimizationRequest !== 'function') return Promise.resolve();
  return cancelOptimizationRequest().catch((error) => {
    console.warn('Queue cancel: failed to notify server cancel endpoint', error);
  });
}

function collectQueueSources(itemId) {
  void itemId;
  const paths = typeof getSelectedCsvPaths === 'function'
    ? getSelectedCsvPaths()
    : (window.selectedCsvPath ? [window.selectedCsvPath] : []);
  const sources = [];
  const seen = new Set();

  paths.forEach((path) => {
    const value = String(path || '').trim();
    if (!value) return;
    if (!isAbsoluteFilesystemPath(value)) {
      showQueueError(
        'Queue requires absolute CSV paths.\n'
        + 'Set CSV Directory and choose files from the browser before adding to queue.'
      );
      return;
    }
    const identity = 'path:' + value.toLowerCase();
    if (seen.has(identity)) return;
    seen.add(identity);
    sources.push({ type: 'path', path: value });
  });

  return sources;
}

async function persistQueueFilesForItem(item) {
  const sources = getQueueSources(item);
  const fileSources = sources.filter((source) => source.type === 'file');
  if (!fileSources.length) {
    item.sources = cloneSourcesForStorage(sources);
    return true;
  }

  if (!supportsQueueFileStorage()) {
    showQueueError(
      'Queue file mode requires browser IndexedDB support.\n'
      + 'Please use absolute CSV paths or run without queue.'
    );
    return false;
  }

  const persistedKeys = [];
  try {
    for (const source of fileSources) {
      const fileBlob = source._file;
      if (!isBlobLike(fileBlob)) {
        throw new Error('Selected file data is no longer available. Please reselect CSV files.');
      }
      await putQueuedFileBlob(source.fileKey, fileBlob);
      persistedKeys.push(source.fileKey);
      delete source._file;
    }
    item.sources = cloneSourcesForStorage(sources);
    return true;
  } catch (error) {
    await deleteQueuedFileKeys(persistedKeys);
    showQueueError('Failed to store selected CSV files for queue: ' + (error?.message || 'Unknown error.'));
    return false;
  }
}

function collectQueueItem() {
  const itemId = 'q_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6);
  const sources = collectQueueSources(itemId);
  if (sources === null) {
    return null;
  }

  if (!sources.length) {
    showQueueError(
      'Please select at least one CSV file before adding to queue.\n\n'
      + 'Set CSV Directory and use Choose Files to add data sources.'
    );
    return null;
  }

  if (!window.currentStrategyId) {
    showQueueError('Please select a strategy before adding to queue.');
    return null;
  }

  const validationErrors = validateOptimizerForm(window.currentStrategyConfig);
  if (validationErrors.length) {
    showQueueError('Validation errors:\n' + validationErrors.join('\n'));
    return null;
  }

  const state = gatherFormState();
  if (!state.start || !state.end) {
    showQueueError('Please specify both start and end dates.');
    return null;
  }

  const dbTargetError = getDatabaseTargetValidationError();
  if (dbTargetError) {
    showQueueError(dbTargetError);
    return null;
  }

  const config = buildOptunaConfig(state);
  const hasEnabledParams = Object.values(config.enabled_params || {}).some(Boolean);
  if (!hasEnabledParams) {
    showQueueError('Please enable at least one parameter to optimize.');
    return null;
  }

  const wfToggle = document.getElementById('enableWF');
  const wfEnabled = Boolean(wfToggle && wfToggle.checked && !wfToggle.disabled);
  const mode = wfEnabled ? 'wfa' : 'optuna';

  const queue = loadQueue();
  const itemIndex = queue.nextIndex || 1;

  const item = {
    id: itemId,
    index: itemIndex,
    addedAt: new Date().toISOString(),
    mode,
    strategyId: window.currentStrategyId,
    strategyConfig: clonePreset(window.currentStrategyConfig || {}),
    sources,
    warmupBars: Number(document.getElementById('warmupBars')?.value) || 1000,
    config,
    dbTarget: document.getElementById('dbTarget')?.value || '',
    sourceCursor: 0,
    successCount: 0,
    failureCount: 0
  };

  if (mode === 'wfa') {
    const adaptiveMode = Boolean(document.getElementById('enableAdaptiveWF')?.checked);
    item.wfa = {
      isPeriodDays: Number(document.getElementById('wfIsPeriodDays')?.value) || 90,
      oosPeriodDays: Number(document.getElementById('wfOosPeriodDays')?.value) || 30,
      storeTopNTrials: Number(document.getElementById('wfStoreTopNTrials')?.value) || 50,
      adaptiveMode,
      maxOosPeriodDays: Number(document.getElementById('wfMaxOosPeriodDays')?.value) || 90,
      minOosTrades: Number(document.getElementById('wfMinOosTrades')?.value) || 5,
      checkIntervalTrades: Number(document.getElementById('wfCheckIntervalTrades')?.value) || 3,
      cusumThreshold: Number(document.getElementById('wfCusumThreshold')?.value) || 5.0,
      ddThresholdMultiplier: Number(document.getElementById('wfDdThresholdMultiplier')?.value) || 1.5,
      inactivityMultiplier: Number(document.getElementById('wfInactivityMultiplier')?.value) || 5.0
    };
  }

  item.label = generateQueueLabel(item);
  return item;
}

function generateQueueLabel(item) {
  const index = item.index || '?';

  const strategyName = item.strategyConfig?.name || item.strategyId || '???';
  const strategyVersion = item.strategyConfig?.version || '';
  const strategyLabel = strategyVersion ? (strategyName + ' v' + strategyVersion) : strategyName;

  const csvCount = getQueueSources(item).length;
  const csvLabel = csvCount === 1 ? '1 CSV' : (csvCount + ' CSVs');

  const startRaw = item.config?.fixed_params?.start || '';
  const endRaw = item.config?.fixed_params?.end || '';
  const dateFilter = Boolean(item.config?.fixed_params?.dateFilter);
  let dateLabel = 'no filter';
  if (dateFilter && startRaw && endRaw) {
    const fmtDate = (isoValue) => String(isoValue).slice(0, 10).replace(/-/g, '.');
    dateLabel = fmtDate(startRaw) + '-' + fmtDate(endRaw);
  }

  let modeLabel = 'OPT';
  if (item.mode === 'wfa') {
    const isPeriod = item.wfa?.isPeriodDays || '?';
    const oosPeriod = item.wfa?.oosPeriodDays || '?';
    modeLabel = (item.wfa?.adaptiveMode ? 'WFA-A' : 'WFA-F') + ' ' + isPeriod + '/' + oosPeriod;
  }

  let budgetLabel;
  const budgetMode = item.config?.optuna_budget_mode || 'trials';
  if (budgetMode === 'trials') {
    budgetLabel = String(item.config?.optuna_n_trials || 500) + 't';
  } else if (budgetMode === 'time') {
    const minutes = Math.round((item.config?.optuna_time_limit || 3600) / 60);
    budgetLabel = String(minutes) + 'min';
  } else {
    budgetLabel = 'conv ' + String(item.config?.optuna_convergence || 50);
  }

  return '#' + index + ' \u00B7 ' + strategyLabel + ' \u00B7 ' + csvLabel + ' \u00B7 '
    + dateLabel + ' \u00B7 ' + modeLabel + ' \u00B7 ' + budgetLabel;
}

async function addToQueue(item) {
  if (!item || typeof item !== 'object') return false;

  const queue = loadQueue();
  if (!item.index || item.index <= 0) {
    item.index = queue.nextIndex || 1;
  }
  if (!item.label) {
    item.label = generateQueueLabel(item);
  }

  const persisted = await persistQueueFilesForItem(item);
  if (!persisted) return false;

  queue.items.push(item);
  queue.nextIndex = Math.max(queue.nextIndex || 1, item.index + 1);
  saveQueue(queue);
  renderQueue();
  updateRunButtonState();
  return true;
}

async function removeFromQueue(itemId) {
  if (queueRunning) return;
  const queue = loadQueue();
  let removedItem = null;
  queue.items = queue.items.filter((item) => {
    if (item.id === itemId && !removedItem) {
      removedItem = item;
      return false;
    }
    return true;
  });
  saveQueue(queue);
  if (removedItem) {
    await deleteQueuedFileKeys(collectFileKeysFromItem(removedItem));
  }
  renderQueue();
  updateRunButtonState();
}

async function clearQueue() {
  if (queueRunning) return;
  const queue = loadQueue();
  const fileKeys = [];
  queue.items.forEach((item) => {
    collectFileKeysFromItem(item).forEach((key) => fileKeys.push(key));
  });
  queue.items = [];
  // Keep nextIndex monotonic to avoid label reuse across clears.
  saveQueue(queue);
  await deleteQueuedFileKeys(fileKeys);
  renderQueue();
  updateRunButtonState();
}

function buildQueueTooltip(item) {
  const lines = [];

  const strategyName = item.strategyConfig?.name || item.strategyId || '(unknown)';
  const strategyVersion = item.strategyConfig?.version || '';
  lines.push('Strategy: ' + strategyName + (strategyVersion ? (' v' + strategyVersion) : ''));

  const sources = getQueueSources(item);
  const pathCount = sources.filter((source) => source.type === 'path').length;
  const fileCount = sources.filter((source) => source.type === 'file').length;
  lines.push('CSV Sources: ' + sources.length + ' file(s) [PATH: ' + pathCount + ', FILE: ' + fileCount + ']');
  const maxShow = 5;
  sources.slice(0, maxShow).forEach((source, index) => {
    const fileName = buildSourceDisplayLabel(source, index);
    lines.push('  - [' + buildSourceModeLabel(source) + '] ' + fileName);
  });
  if (sources.length > maxShow) {
    lines.push('  ... and ' + (sources.length - maxShow) + ' more');
  }

  if (item.mode === 'wfa') {
    const typeLabel = item.wfa?.adaptiveMode ? 'Adaptive' : 'Fixed';
    lines.push('Mode: WFA ' + typeLabel + ' (IS: ' + item.wfa?.isPeriodDays + 'd, OOS: ' + item.wfa?.oosPeriodDays + 'd)');
  } else {
    lines.push('Mode: Optuna Optimization');
  }

  const budgetMode = item.config?.optuna_budget_mode || 'trials';
  const sampler = (item.config?.sampler || 'tpe').toUpperCase();
  if (budgetMode === 'trials') {
    lines.push('Budget: ' + item.config?.optuna_n_trials + ' trials (' + sampler + ' sampler)');
  } else if (budgetMode === 'time') {
    const minutes = Math.round((item.config?.optuna_time_limit || 3600) / 60);
    lines.push('Budget: ' + minutes + ' min (' + sampler + ' sampler)');
  } else {
    lines.push('Budget: convergence ' + item.config?.optuna_convergence + ' (' + sampler + ' sampler)');
  }

  const objectives = item.config?.objectives || [];
  if (objectives.length) {
    const objectiveNames = objectives.map((objective) => objective.replace(/_/g, ' ').replace(/pct/g, '%'));
    lines.push('Objectives: ' + objectiveNames.join(', '));
  }

  const constraints = Array.isArray(item.config?.constraints) ? item.config.constraints : [];
  const enabledConstraints = constraints.filter((constraint) => constraint && constraint.enabled && constraint.threshold != null);
  if (enabledConstraints.length) {
    const labels = enabledConstraints.map((constraint) => {
      const operator = CONSTRAINT_LE_METRICS.includes(constraint.metric) ? '<=' : '>=';
      return constraint.metric + ' ' + operator + ' ' + constraint.threshold;
    });
    lines.push('Constraints: ' + labels.join(', '));
  }

  const postProcess = item.config?.postProcess;
  if (postProcess?.enabled) {
    lines.push('Forward Test: ' + postProcess.ftPeriodDays + 'd (top ' + postProcess.topK + ')');
  }
  if (item.config?.oosTest?.enabled) {
    lines.push('OOS Test: ' + item.config.oosTest.periodDays + 'd (top ' + item.config.oosTest.topK + ')');
  }

  const dateFilter = item.config?.fixed_params?.dateFilter;
  const start = item.config?.fixed_params?.start || '';
  const end = item.config?.fixed_params?.end || '';
  if (dateFilter && start && end) {
    lines.push('Date Filter: ' + start.slice(0, 16).replace('T', ' ') + ' -> ' + end.slice(0, 16).replace('T', ' '));
  }

  lines.push('Warmup: ' + item.warmupBars + ' bars');
  lines.push('DB Target: ' + (item.dbTarget || '(none)'));

  const enabledCount = Object.values(item.config?.enabled_params || {}).filter(Boolean).length;
  const totalCount = Object.keys(item.config?.enabled_params || {}).length;
  lines.push('Enabled Params: ' + enabledCount + ' of ' + totalCount);

  if (item.sourceCursor && sources.length) {
    lines.push('Progress: source ' + item.sourceCursor + ' of ' + sources.length + ' already processed');
  }

  return lines.join('\n');
}

function renderQueue() {
  const emptyState = document.getElementById('queueEmptyState');
  const itemsList = document.getElementById('queueItemsList');
  const clearBtn = document.getElementById('clearQueueBtn');
  const queue = loadQueue();

  if (!queue.items.length) {
    if (emptyState) emptyState.style.display = 'block';
    if (itemsList) {
      itemsList.style.display = 'none';
      itemsList.innerHTML = '';
    }
    if (clearBtn) clearBtn.style.display = 'none';
    setQueueControlsDisabled(queueRunning);
    return;
  }

  if (emptyState) emptyState.style.display = 'none';
  if (clearBtn) clearBtn.style.display = 'inline-block';
  if (!itemsList) return;

  itemsList.innerHTML = '';
  itemsList.style.display = 'flex';

  const fragment = document.createDocumentFragment();
  queue.items.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'queue-item';
    row.dataset.queueId = item.id;
    row.title = buildQueueTooltip(item);

    const label = document.createElement('span');
    label.className = 'queue-item-label';
    label.textContent = item.label;

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'queue-item-remove';
    removeBtn.setAttribute('aria-label', 'Remove from queue');
    removeBtn.innerHTML = '&times;';
    removeBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      void removeFromQueue(item.id);
    });

    row.appendChild(label);
    row.appendChild(removeBtn);
    fragment.appendChild(row);
  });

  itemsList.appendChild(fragment);
  setQueueControlsDisabled(queueRunning);
}

function updateRunButtonState() {
  const btn = document.getElementById('runOptimizationBtn');
  if (!btn) return;

  if (queueRunning) {
    btn.textContent = 'Cancel Queue';
    btn.classList.remove('queue-active');
    btn.classList.add('queue-cancel');
    return;
  }

  const queue = loadQueue();
  const count = queue.items.length;
  btn.classList.remove('queue-cancel');

  if (count > 0) {
    btn.textContent = 'Run Queue (' + count + ')';
    btn.classList.add('queue-active');
  } else {
    btn.textContent = 'Run Optimization';
    btn.classList.remove('queue-active');
  }
}

function showQueueError(message) {
  const optimizerResultsEl = document.getElementById('optimizerResults');
  if (!optimizerResultsEl) return;
  optimizerResultsEl.textContent = message;
  optimizerResultsEl.classList.remove('ready', 'loading');
  optimizerResultsEl.style.display = 'block';
}

function setQueueItemState(itemId, state) {
  const row = document.querySelector('.queue-item[data-queue-id="' + itemId + '"]');
  if (!row) return;
  row.classList.remove('running', 'completed', 'failed', 'skipped');
  row.classList.add(state);

  const removeBtn = row.querySelector('.queue-item-remove');
  if (!removeBtn) return;

  if (state === 'running' || state === 'completed' || state === 'failed' || state === 'skipped') {
    removeBtn.disabled = true;
    removeBtn.dataset.locked = '1';
    removeBtn.style.visibility = 'hidden';
  }
}

function buildStrategySummary(item) {
  return {
    id: item.strategyId || '',
    name: item.strategyConfig?.name || '',
    version: item.strategyConfig?.version || '',
    description: item.strategyConfig?.description || ''
  };
}

function buildDatasetLabel(path) {
  if (path && typeof path === 'object') {
    return buildSourceDisplayLabel(path);
  }
  return getPathFileName(path);
}

function buildStateForItem(item, status) {
  const firstSource = getQueueSources(item)[0];
  const state = {
    status,
    mode: item.mode || 'optuna',
    strategy: buildStrategySummary(item),
    strategyId: item.strategyId || '',
    dataset: { label: buildDatasetLabel(firstSource) },
    warmupBars: item.warmupBars,
    dateFilter: item.config?.fixed_params?.dateFilter,
    start: item.config?.fixed_params?.start,
    end: item.config?.fixed_params?.end,
    optuna: {
      objectives: item.config?.objectives,
      primaryObjective: item.config?.primary_objective,
      budgetMode: item.config?.optuna_budget_mode,
      nTrials: item.config?.optuna_n_trials,
      timeLimit: item.config?.optuna_time_limit,
      convergence: item.config?.optuna_convergence,
      sampler: item.config?.sampler,
      pruner: item.config?.optuna_pruner,
      workers: item.config?.worker_processes,
      sanitizeEnabled: item.config?.sanitize_enabled,
      sanitizeTradesThreshold: item.config?.sanitize_trades_threshold
    },
    fixedParams: clonePreset(item.config?.fixed_params || {}),
    strategyConfig: clonePreset(item.strategyConfig || {})
  };

  if (item.mode === 'wfa') {
    state.wfa = clonePreset(item.wfa || {});
  } else {
    state.wfa = {};
  }

  return state;
}

function persistItemProgress(itemId, patch) {
  const queue = loadQueue();
  const item = queue.items.find((entry) => entry.id === itemId);
  if (!item) return;

  Object.assign(item, patch || {});
  saveQueue(queue);
}

async function runQueue() {
  if (queueRunning) return;

  const initialQueue = loadQueue();
  if (!initialQueue.items.length) {
    updateRunButtonState();
    return;
  }

  queueRunning = true;
  setQueueControlsDisabled(true);
  updateRunButtonState();

  const optimizerResultsEl = document.getElementById('optimizerResults');
  const progressContainer = document.getElementById('optimizerProgress');
  const optunaProgress = document.getElementById('optunaProgress');
  const optunaProgressFill = document.getElementById('optunaProgressFill');
  const optunaProgressText = document.getElementById('optunaProgressText');
  const optunaBestTrial = document.getElementById('optunaBestTrial');

  const controller = new AbortController();
  window.optimizationAbortController = controller;
  const signal = controller.signal;

  const firstItem = initialQueue.items[0];
  saveOptimizationState(buildStateForItem(firstItem, 'running'));
  openResultsPage();

  if (optimizerResultsEl) {
    optimizerResultsEl.textContent = '';
    optimizerResultsEl.classList.add('loading');
    optimizerResultsEl.classList.remove('ready');
    optimizerResultsEl.style.display = 'block';
  }
  if (progressContainer) progressContainer.style.display = 'block';
  if (optunaProgress) optunaProgress.style.display = 'block';

  const totalItems = initialQueue.items.length;
  let fullySucceededItems = 0;
  let partiallySucceededItems = 0;
  let failedItems = 0;
  let aborted = false;
  let lastStudyId = '';
  let lastSummary = null;
  let lastDataPath = '';
  let lastMode = firstItem.mode || 'optuna';
  let lastStrategyId = firstItem.strategyId || '';
  let cancelNotified = false;

  try {
    while (true) {
      const currentQueue = loadQueue();
      const item = currentQueue.items[0];
      if (!item) break;

      if (signal.aborted) {
        aborted = true;
        break;
      }

      lastMode = item.mode || 'optuna';
      lastStrategyId = item.strategyId || '';
      updateOptimizationState(buildStateForItem(item, 'running'));
      setQueueItemState(item.id, 'running');

      const sources = getQueueSources(item);
      const totalSources = sources.length;
      if (totalSources === 0) {
        setQueueItemState(item.id, 'failed');
        failedItems += 1;
        const updatedQueue = loadQueue();
        updatedQueue.items = updatedQueue.items.filter((entry) => entry.id !== item.id);
        saveQueue(updatedQueue);
        await deleteQueuedFileKeys(collectFileKeysFromItem(item));
        continue;
      }

      const startCursorRaw = Number(item.sourceCursor);
      const startCursor = Number.isFinite(startCursorRaw)
        ? Math.max(0, Math.min(totalSources, Math.floor(startCursorRaw)))
        : 0;
      let itemSuccess = Number.isFinite(Number(item.successCount)) ? Math.max(0, Math.floor(Number(item.successCount))) : 0;
      let itemFailure = Number.isFinite(Number(item.failureCount)) ? Math.max(0, Math.floor(Number(item.failureCount))) : 0;
      let processedCursor = startCursor;

      for (let sourceIndex = startCursor; sourceIndex < totalSources; sourceIndex += 1) {
        if (signal.aborted) {
          aborted = true;
          break;
        }

        const source = sources[sourceIndex];
        const sourceName = buildSourceDisplayLabel(source, sourceIndex);
        const sourceMode = buildSourceModeLabel(source);
        if (optimizerResultsEl) {
          optimizerResultsEl.textContent = (
            'Queue item: ' + item.label + '\n'
            + 'Source ' + (sourceIndex + 1) + '/' + totalSources + ': [' + sourceMode + '] ' + sourceName + ' - processing...'
          );
        }

        if (optunaProgressFill) optunaProgressFill.style.width = '0%';
        if (optunaProgressText) {
          const budgetMode = item.config?.optuna_budget_mode;
          if (budgetMode === 'trials') {
            const trials = item.config?.optuna_n_trials || 500;
            optunaProgressText.textContent = 'Trial: 0 / ' + trials.toLocaleString('en-US') + ' (0%)';
          } else if (budgetMode === 'time') {
            const minutes = Math.round((item.config?.optuna_time_limit || 3600) / 60);
            optunaProgressText.textContent = 'Time budget: ' + minutes + ' min';
          } else {
            optunaProgressText.textContent = 'Running...';
          }
        }
        if (optunaBestTrial) {
          optunaBestTrial.textContent = 'Waiting for first trial...';
        }

        const formData = new FormData();
        formData.append('strategy', item.strategyId);
        formData.append('warmupBars', String(item.warmupBars));
        formData.append('config', JSON.stringify(item.config));
        if (item.dbTarget) {
          formData.append('dbTarget', item.dbTarget);
        }

        if (source.type === 'path') {
          const csvPath = String(source.path || '').trim();
          if (!isAbsoluteFilesystemPath(csvPath)) {
            itemFailure += 1;
            processedCursor = sourceIndex + 1;
            persistItemProgress(item.id, {
              sourceCursor: processedCursor,
              successCount: itemSuccess,
              failureCount: itemFailure
            });
            continue;
          }
          formData.append('csvPath', csvPath);
        } else if (source.type === 'file') {
          let fileBlob;
          try {
            fileBlob = await getQueuedFileBlob(source.fileKey);
          } catch (error) {
            console.error('Queue file load failed for key:', source.fileKey, error);
            fileBlob = null;
          }

          if (!isBlobLike(fileBlob)) {
            itemFailure += 1;
            processedCursor = sourceIndex + 1;
            if (optimizerResultsEl) {
              optimizerResultsEl.textContent = (
                'Queue item: ' + item.label + '\n'
                + 'Source ' + (sourceIndex + 1) + '/' + totalSources + ': [' + sourceMode + '] ' + sourceName + ' - failed (file data missing).'
              );
            }
            persistItemProgress(item.id, {
              sourceCursor: processedCursor,
              successCount: itemSuccess,
              failureCount: itemFailure
            });
            continue;
          }

          const uploadName = source.name || ('source_' + (sourceIndex + 1) + '.csv');
          formData.append('file', fileBlob, uploadName);
        } else {
          itemFailure += 1;
          processedCursor = sourceIndex + 1;
          persistItemProgress(item.id, {
            sourceCursor: processedCursor,
            successCount: itemSuccess,
            failureCount: itemFailure
          });
          continue;
        }

        try {
          let data;
          if (item.mode === 'wfa' && item.wfa) {
            formData.append('wf_is_period_days', String(item.wfa.isPeriodDays));
            formData.append('wf_oos_period_days', String(item.wfa.oosPeriodDays));
            formData.append('wf_store_top_n_trials', String(item.wfa.storeTopNTrials));
            formData.append('wf_adaptive_mode', item.wfa.adaptiveMode ? 'true' : 'false');
            formData.append('wf_max_oos_period_days', String(item.wfa.maxOosPeriodDays));
            formData.append('wf_min_oos_trades', String(item.wfa.minOosTrades));
            formData.append('wf_check_interval_trades', String(item.wfa.checkIntervalTrades));
            formData.append('wf_cusum_threshold', String(item.wfa.cusumThreshold));
            formData.append('wf_dd_threshold_multiplier', String(item.wfa.ddThresholdMultiplier));
            formData.append('wf_inactivity_multiplier', String(item.wfa.inactivityMultiplier));
            data = await runWalkForwardRequest(formData, signal);
          } else {
            data = await runOptimizationRequest(formData, signal);
          }

          itemSuccess += 1;
          lastStudyId = data && data.study_id ? data.study_id : lastStudyId;
          lastSummary = data && data.summary ? data.summary : lastSummary;
          lastDataPath = data && data.data_path ? data.data_path : (sourceName || lastDataPath);
        } catch (error) {
          if (error && error.name === 'AbortError') {
            aborted = true;
            break;
          }
          itemFailure += 1;
          console.error('Queue source failed: ' + sourceName, error);
        }

        processedCursor = sourceIndex + 1;
        persistItemProgress(item.id, {
          sourceCursor: processedCursor,
          successCount: itemSuccess,
          failureCount: itemFailure
        });
      }

      if (aborted) {
        setQueueItemState(item.id, 'skipped');
        if (!cancelNotified) {
          cancelNotified = true;
          await requestServerCancelBestEffort();
        }
        break;
      }

      if (itemSuccess === totalSources) {
        setQueueItemState(item.id, 'completed');
        fullySucceededItems += 1;
      } else if (itemSuccess > 0) {
        setQueueItemState(item.id, 'completed');
        partiallySucceededItems += 1;
      } else {
        setQueueItemState(item.id, 'failed');
        failedItems += 1;
      }

      if (lastStudyId) {
        updateOptimizationState({
          status: 'running',
          mode: lastMode,
          study_id: lastStudyId,
          summary: lastSummary || {},
          dataPath: lastDataPath,
          strategyId: lastStrategyId
        });
      }

      const updatedQueue = loadQueue();
      let removed = false;
      updatedQueue.items = updatedQueue.items.filter((entry) => {
        if (removed) return true;
        if (entry.id === item.id) {
          removed = true;
          return false;
        }
        return true;
      });
      saveQueue(updatedQueue);
      await deleteQueuedFileKeys(collectFileKeysFromItem(item));
    }

    if (optimizerResultsEl) {
      optimizerResultsEl.classList.remove('loading');
      const processedItems = fullySucceededItems + partiallySucceededItems + failedItems;

      if (aborted) {
        optimizerResultsEl.textContent = (
          'Queue cancelled. Processed ' + processedItems + ' of ' + totalItems + ' item(s).\n'
          + 'Successful: ' + fullySucceededItems
          + ', Partial: ' + partiallySucceededItems
          + ', Failed: ' + failedItems
          + '. Remaining items stay queued.'
        );
      } else if (failedItems === 0 && partiallySucceededItems === 0) {
        optimizerResultsEl.textContent = 'Queue complete! All ' + totalItems + ' item(s) processed successfully.';
        optimizerResultsEl.classList.add('ready');
      } else {
        optimizerResultsEl.textContent = (
          'Queue finished.\n'
          + 'Successful: ' + fullySucceededItems
          + ', Partial: ' + partiallySucceededItems
          + ', Failed: ' + failedItems + '.'
        );
      }
    }

    if (aborted) {
      updateOptimizationState({
        status: 'cancelled',
        mode: lastMode,
        study_id: lastStudyId,
        summary: lastSummary || {},
        dataPath: lastDataPath,
        strategyId: lastStrategyId
      });
    } else {
      const succeededItems = fullySucceededItems + partiallySucceededItems;
      if (succeededItems > 0) {
        updateOptimizationState({
          status: 'completed',
          mode: lastMode,
          study_id: lastStudyId,
          summary: lastSummary || {},
          dataPath: lastDataPath,
          strategyId: lastStrategyId
        });
      } else {
        updateOptimizationState({
          status: 'error',
          mode: lastMode,
          study_id: lastStudyId,
          summary: lastSummary || {},
          dataPath: lastDataPath,
          strategyId: lastStrategyId,
          error: 'Queue finished with no successful items.'
        });
      }
    }
  } catch (error) {
    console.error('Queue execution failed unexpectedly', error);
    showQueueError('Queue execution failed: ' + (error?.message || 'Unknown error'));
    updateOptimizationState({
      status: 'error',
      mode: lastMode,
      error: error?.message || 'Queue execution failed.'
    });
  } finally {
    queueRunning = false;
    window.optimizationAbortController = null;
    renderQueue();
    setQueueControlsDisabled(false);
    updateRunButtonState();
  }
}

function initQueue() {
  renderQueue();
  updateRunButtonState();
  void cleanupStaleQueueFiles();
}


