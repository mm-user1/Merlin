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

  function syncMutualExclusion() {
    const { enable } = getOosElements();
    const wfToggle = document.getElementById('enableWF');
    const oosLabel = document.getElementById('oosEnableLabel');
    const wfLabel = document.getElementById('wfEnableLabel');
    if (!enable || !wfToggle) return;
    const oosChecked = Boolean(enable.checked);
    const wfChecked = Boolean(wfToggle.checked);

    if (oosChecked) {
      wfToggle.disabled = true;
      wfToggle.dataset.guard = 'oos';
    } else {
      wfToggle.disabled = false;
      delete wfToggle.dataset.guard;
    }

    if (wfChecked) {
      enable.disabled = true;
      enable.dataset.guard = 'wfa';
    } else {
      enable.disabled = false;
      delete enable.dataset.guard;
    }

    if (oosLabel) oosLabel.style.color = enable.disabled ? '#9a9a9a' : '';
    if (wfLabel) wfLabel.style.color = wfToggle.disabled ? '#9a9a9a' : '';
  }

  function collectConfig() {
    const { enable, period, topK } = getOosElements();
    const blocked = Boolean(enable && enable.disabled && enable.dataset.guard === 'wfa');
    return {
      enabled: Boolean(enable && enable.checked && !blocked),
      periodDays: normalizeInt(period?.value, 30, 1, 3650),
      topK: normalizeInt(topK?.value, 20, 1, 10000)
    };
  }

  function bind() {
    const { enable } = getOosElements();
    if (enable) {
      enable.addEventListener('change', () => {
        syncMutualExclusion();
        syncOosUI();
      });
    }
    const wfToggle = document.getElementById('enableWF');
    if (wfToggle) {
      wfToggle.addEventListener('change', () => {
        syncMutualExclusion();
        syncOosUI();
      });
    }
    syncOosUI();
    syncMutualExclusion();
  }

  window.OosTestUI = {
    bind,
    collectConfig
  };
})();
