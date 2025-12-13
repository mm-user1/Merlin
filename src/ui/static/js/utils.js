/**
 * Utility functions for the Strategy Backtester & Optimizer UI.
 * No dependencies on other modules.
 */

function clonePreset(data) {
  try {
    return JSON.parse(JSON.stringify(data || {}));
  } catch (error) {
    return {};
  }
}

function parseNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatMetric(value, digits = 2) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toFixed(digits);
  }
  if (value === undefined || value === null) {
    return 'N/A';
  }
  return value;
}

function formatResultBlock(index, total, payload, data) {
  const metrics = data.metrics || {};
  return [
    `#${index}/${total}`,
    `Net Profit %: ${formatMetric(metrics.net_profit_pct)}`,
    `Max Drawdown %: ${formatMetric(metrics.max_drawdown_pct)}`,
    `Total Trades: ${metrics.total_trades ?? 'N/A'}`
  ].join('\n');
}

function composeDateTime(datePart, timePart) {
  const date = (datePart || '').trim();
  const time = (timePart || '').trim();
  if (!date) {
    return '';
  }
  const normalizedTime = time || '00:00';
  return `${date}T${normalizedTime}`;
}

function setCheckboxValue(id, checked) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }
  element.checked = Boolean(checked);
}

function setInputValue(id, value) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }
  if (value === undefined || value === null) {
    element.value = '';
  } else {
    element.value = value;
  }
}

function showErrorMessage(message) {
  const errorEl = document.getElementById('error');
  if (!errorEl) {
    return;
  }
  errorEl.textContent = message;
  errorEl.style.display = message ? 'block' : 'none';
}

function clearErrorMessage() {
  showErrorMessage('');
}

function showResultsMessage(message) {
  const resultsEl = document.getElementById('results');
  if (!resultsEl) {
    return;
  }
  resultsEl.textContent = message;
  resultsEl.classList.remove('loading');
  if (message) {
    resultsEl.classList.add('ready');
  } else {
    resultsEl.classList.remove('ready');
  }
}

function renderSelectedFiles(files) {
  const selectedFilesWrapper = document.getElementById('selectedFilesWrapper');
  const selectedFilesList = document.getElementById('selectedFilesList');

  if (!selectedFilesWrapper || !selectedFilesList) {
    return;
  }

  const entries = [];
  if (files && files.length) {
    files.forEach((file) => {
      entries.push(file.name);
    });
  } else if (window.selectedCsvPath) {
    entries.push(window.selectedCsvPath);
  }

  selectedFilesList.innerHTML = '';
  if (!entries.length) {
    selectedFilesWrapper.style.display = 'none';
    return;
  }

  const fragment = document.createDocumentFragment();
  entries.forEach((label) => {
    const item = document.createElement('li');
    item.textContent = label;
    fragment.appendChild(item);
  });

  selectedFilesList.appendChild(fragment);
  selectedFilesWrapper.style.display = 'block';
}
