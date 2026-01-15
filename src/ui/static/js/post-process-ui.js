(function () {
  function getPostProcessElements() {
    return {
      enable: document.getElementById('enablePostProcess'),
      period: document.getElementById('ftPeriodDays'),
      topK: document.getElementById('ftTopK'),
      sortMetric: document.getElementById('ftSortMetric'),
      ftSettings: document.getElementById('ftSettings'),
      dsrEnable: document.getElementById('enableDSR'),
      dsrTopK: document.getElementById('dsrTopK'),
      dsrSettings: document.getElementById('dsrSettings'),
      stEnable: document.getElementById('enableStressTest'),
      stTopK: document.getElementById('stTopK'),
      stFailureThreshold: document.getElementById('stFailureThreshold'),
      stSortMetric: document.getElementById('stSortMetric'),
      stSettings: document.getElementById('stressTestSettings')
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

  function syncPostProcessUI() {
    const {
      enable,
      period,
      topK,
      sortMetric,
      ftSettings,
      dsrEnable,
      dsrTopK,
      dsrSettings,
      stEnable,
      stTopK,
      stFailureThreshold,
      stSortMetric,
      stSettings
    } = getPostProcessElements();
    if (enable) {
      const disabled = !enable.checked;
      if (period) period.disabled = disabled;
      if (topK) topK.disabled = disabled;
      if (sortMetric) sortMetric.disabled = disabled;
      if (ftSettings) ftSettings.style.display = disabled ? 'none' : 'block';
    }
    if (dsrEnable) {
      const dsrDisabled = !dsrEnable.checked;
      if (dsrTopK) dsrTopK.disabled = dsrDisabled;
      if (dsrSettings) dsrSettings.style.display = dsrDisabled ? 'none' : 'block';
    }
    if (stEnable) {
      const stDisabled = !stEnable.checked;
      if (stTopK) stTopK.disabled = stDisabled;
      if (stFailureThreshold) stFailureThreshold.disabled = stDisabled;
      if (stSortMetric) stSortMetric.disabled = stDisabled;
      if (stSettings) stSettings.style.display = stDisabled ? 'none' : 'block';
    }
  }

  function collectConfig() {
    const {
      enable,
      period,
      topK,
      sortMetric,
      dsrEnable,
      dsrTopK,
      stEnable,
      stTopK,
      stFailureThreshold,
      stSortMetric
    } = getPostProcessElements();
    const enabled = Boolean(enable && enable.checked);
    const dsrEnabled = Boolean(dsrEnable && dsrEnable.checked);
    const stEnabled = Boolean(stEnable && stEnable.checked);
    const failureRaw = Number(stFailureThreshold?.value);
    const failurePct = Number.isFinite(failureRaw) ? Math.min(100, Math.max(0, failureRaw)) : 70;
    return {
      enabled,
      ftPeriodDays: normalizeInt(period?.value, 30, 1, 3650),
      topK: normalizeInt(topK?.value, 20, 1, 10000),
      sortMetric: sortMetric?.value || 'profit_degradation',
      dsrEnabled,
      dsrTopK: normalizeInt(dsrTopK?.value, 20, 1, 10000),
      stressTest: {
        enabled: stEnabled,
        topK: normalizeInt(stTopK?.value, 5, 1, 100),
        failureThreshold: failurePct / 100,
        sortMetric: stSortMetric?.value || 'profit_retention'
      }
    };
  }

  function bind() {
    const { enable, dsrEnable, stEnable } = getPostProcessElements();
    if (enable) {
      enable.addEventListener('change', syncPostProcessUI);
    }
    if (dsrEnable) {
      dsrEnable.addEventListener('change', syncPostProcessUI);
    }
    if (stEnable) {
      stEnable.addEventListener('change', syncPostProcessUI);
    }
    syncPostProcessUI();
  }

  function buildComparisonMetrics(trial) {
    const isNet = Number(trial.net_profit_pct || 0);
    const ftNet = Number(trial.ft_net_profit_pct || 0);
    const isDd = Number(trial.max_drawdown_pct || 0);
    const ftDd = Number(trial.ft_max_drawdown_pct || 0);
    const isRomad = Number(trial.romad || 0);
    const ftRomad = Number(trial.ft_romad || 0);
    const isSharpe = Number(trial.sharpe_ratio || 0);
    const ftSharpe = Number(trial.ft_sharpe_ratio || 0);
    const isPf = Number(trial.profit_factor || 0);
    const ftPf = Number(trial.ft_profit_factor || 0);

    return {
      profit_degradation: trial.profit_degradation,
      max_dd_change: ftDd - isDd,
      romad_change: ftRomad - isRomad,
      sharpe_change: ftSharpe - isSharpe,
      pf_change: ftPf - isPf,
      is_net_profit_pct: isNet,
      ft_net_profit_pct: ftNet
    };
  }

  window.PostProcessUI = {
    bind,
    collectConfig,
    buildComparisonMetrics
  };
})();
