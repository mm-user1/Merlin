(function () {
  const OBJECTIVE_LABELS = {
    net_profit_pct: 'Net Profit %',
    max_drawdown_pct: 'Min Drawdown %',
    sharpe_ratio: 'Sharpe Ratio',
    sortino_ratio: 'Sortino Ratio',
    romad: 'RoMaD',
    profit_factor: 'Profit Factor',
    win_rate: 'Win Rate %',
    sqn: 'SQN',
    ulcer_index: 'Ulcer Index',
    consistency_score: 'Consistency %',
    composite_score: 'Composite Score'
  };
  function getObjectiveCheckboxes() {
    return Array.from(document.querySelectorAll('.objective-checkbox'));
  }

  function updateObjectiveSelection() {
    const checkboxes = getObjectiveCheckboxes();
    const selected = checkboxes.filter((cb) => cb.checked).map((cb) => cb.dataset.objective);

    if (selected.length === 0 && checkboxes.length) {
      checkboxes[0].checked = true;
      selected.push(checkboxes[0].dataset.objective);
    }

    const disableExtra = selected.length >= 6;
    checkboxes.forEach((cb) => {
      if (!cb.checked) {
        cb.disabled = disableExtra;
      } else {
        cb.disabled = false;
      }
    });

    const primaryRow = document.getElementById('primaryObjectiveRow');
    const primarySelect = document.getElementById('primaryObjective');
    if (primaryRow && primarySelect) {
      if (selected.length > 1) {
        primaryRow.style.display = 'flex';
        const previous = primarySelect.value;
        primarySelect.innerHTML = '';
        selected.forEach((obj) => {
          const option = document.createElement('option');
          option.value = obj;
          option.textContent = OBJECTIVE_LABELS[obj] || obj;
          primarySelect.appendChild(option);
        });
        primarySelect.value = selected.includes(previous) ? previous : selected[0];
      } else {
        primaryRow.style.display = 'none';
        primarySelect.innerHTML = '';
      }
    }

    const pruningCheckbox = document.getElementById('optunaPruning');
    const prunerSelect = document.getElementById('optunaPruner');
    const disablePruning = selected.length > 1;
    if (pruningCheckbox) {
      if (disablePruning) {
        pruningCheckbox.checked = false;
      }
      pruningCheckbox.disabled = disablePruning;
    }
    if (prunerSelect) {
      prunerSelect.disabled = disablePruning;
    }
  }

  function toggleNsgaSettings() {
    const sampler = document.getElementById('optunaSampler');
    const nsgaSettings = document.getElementById('nsgaSettings');
    if (!sampler || !nsgaSettings) {
      return;
    }
    const isNsga = sampler.value === 'nsga2' || sampler.value === 'nsga3';
    nsgaSettings.style.display = isNsga ? 'block' : 'none';
  }

  function collectObjectives() {
    const checkboxes = getObjectiveCheckboxes();
    const selected = checkboxes.filter((cb) => cb.checked).map((cb) => cb.dataset.objective);
    const primarySelect = document.getElementById('primaryObjective');
    const primaryObjective = selected.length > 1 && primarySelect ? primarySelect.value : null;
    return {
      objectives: selected,
      primary_objective: primaryObjective
    };
  }

  function collectConstraints() {
    const rows = Array.from(document.querySelectorAll('.constraint-row'));
    return rows.map((row) => {
      const checkbox = row.querySelector('.constraint-checkbox');
      const input = row.querySelector('.constraint-input');
      const metric = checkbox ? checkbox.dataset.constraintMetric : null;
      let threshold = null;
      if (input && input.value !== '') {
        const parsed = Number(input.value);
        threshold = Number.isFinite(parsed) ? parsed : null;
      }
      return {
        metric,
        threshold,
        enabled: Boolean(checkbox && checkbox.checked)
      };
    }).filter((item) => item.metric);
  }

  window.OptunaUI = {
    updateObjectiveSelection,
    toggleNsgaSettings,
    collectObjectives,
    collectConstraints
  };
})();


