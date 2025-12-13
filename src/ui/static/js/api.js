/**
 * API communication functions for Strategy Backtester & Optimizer.
 * Dependencies: utils.js
 */

async function fetchStrategies() {
  const response = await fetch('/api/strategies');
  if (!response.ok) {
    throw new Error(`Failed to fetch strategies: ${response.status}`);
  }
  return response.json();
}

async function fetchStrategyConfig(strategyId) {
  const response = await fetch(`/api/strategy/${strategyId}/config`);
  if (!response.ok) {
    throw new Error(`Server returned ${response.status}: ${response.statusText}`);
  }
  const config = await response.json();

  if (!config || typeof config !== 'object') {
    throw new Error('Invalid config format');
  }

  if (!config.parameters || typeof config.parameters !== 'object') {
    throw new Error('Missing parameters in config');
  }

  return config;
}

async function runBacktestRequest(formData) {
  const response = await fetch('/api/backtest', {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Backtest request failed.');
  }

  return response.json();
}

async function runOptimizationRequest(formData) {
  const response = await fetch('/api/optimize', {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Optimization request failed.');
  }

  return {
    blob: await response.blob(),
    headers: response.headers
  };
}

async function runWalkForwardRequest(formData) {
  const response = await fetch('/api/walkforward', {
    method: 'POST',
    body: formData
  });

  const data = await response.json();

  if (!response.ok || data.status !== 'success') {
    const message = data && data.error ? data.error : 'Walk-Forward request failed.';
    throw new Error(message);
  }

  return data;
}

async function fetchPresetsList() {
  const response = await fetch('/api/presets');
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to fetch presets.');
  }
  return response.json();
}

async function loadPresetRequest(name) {
  const response = await fetch(`/api/presets/${encodeURIComponent(name)}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to load preset.');
  }
  return response.json();
}

async function savePresetRequest(name, values) {
  const response = await fetch('/api/presets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, values })
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to save preset.');
  }
  return response.json();
}

async function overwritePresetRequest(name, values) {
  const response = await fetch(`/api/presets/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values })
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to overwrite preset.');
  }
  return response.json();
}

async function saveDefaultsRequest(values) {
  const response = await fetch('/api/presets/defaults', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values })
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to save defaults.');
  }
  return response.json();
}

async function deletePresetRequest(name) {
  const response = await fetch(`/api/presets/${encodeURIComponent(name)}`, {
    method: 'DELETE'
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to delete preset.');
  }
}

async function importPresetFromCsvRequest(file) {
  const formData = new FormData();
  formData.append('file', file, file.name);

  const response = await fetch('/api/presets/import-csv', {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to import settings from CSV.');
  }

  return response.json();
}
