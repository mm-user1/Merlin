(function () {
  function getOosElements() {
    return {
      enable: document.getElementById('enableOosTest'),
      period: document.getElementById('oosPeriodDays'),
      topK: document.getElementById('oosTopK'),
      settings: document.getElementById('oosTestSettings')
    };
  }

  function normalizeInt(value, fallback, min, max) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return fallback;
    const rounded = Math.round(parsed);
    if (min !== undefined && rounded < min) return min;
    if (max !== undefined && rounded > max) return max;
    return rounded;
  }

  function syncOosUI() {
    const { enable, period, topK, settings } = getOosElements();
    if (!enable) return;
    const disabled = !enable.checked;
    if (period) period.disabled = disabled;
    if (topK) topK.disabled = disabled;
    if (settings) settings.style.display = disabled ? 'none' : 'block';
  }

  function collectConfig() {
    const { enable, period, topK } = getOosElements();
    return {
      enabled: Boolean(enable && enable.checked),
      periodDays: normalizeInt(period?.value, 30, 1, 3650),
      topK: normalizeInt(topK?.value, 20, 1, 10000)
    };
  }

  function bind() {
    const { enable } = getOosElements();
    if (enable) {
      enable.addEventListener('change', syncOosUI);
    }
    syncOosUI();
  }

  window.OosTestUI = {
    bind,
    collectConfig
  };
})();
