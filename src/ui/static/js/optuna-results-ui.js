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

  function formatObjectiveLabel(key) {
    return OBJECTIVE_LABELS[key] || key;
  }

  function formatNumber(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return 'N/A';
    }
    const num = Number(value);
    if (!Number.isFinite(num)) {
      return String(value);
    }
    return num.toFixed(digits);
  }

  function buildTrialTableHeaders(objectives, hasConstraints) {
    const columns = [];
    columns.push('<th>#</th>');
    columns.push('<th>Param ID</th>');
    columns.push('<th>Pareto</th>');
    if (hasConstraints) {
      columns.push('<th>Constraints</th>');
    }

    const objectiveList = Array.isArray(objectives) ? objectives : [];
    const objectiveSet = new Set(objectiveList);
    objectiveList.forEach((objective) => {
      columns.push(`<th>${formatObjectiveLabel(objective)}</th>`);
    });

    if (!objectiveSet.has('net_profit_pct')) {
      columns.push('<th>Net Profit %</th>');
    }
    if (!objectiveSet.has('max_drawdown_pct')) {
      columns.push('<th>Max DD %</th>');
    }
    columns.push('<th>Trades</th>');
    columns.push('<th>Score</th>');
    columns.push('<th>RoMaD</th>');
    columns.push('<th>Sharpe</th>');
    columns.push('<th>PF</th>');
    columns.push('<th>Ulcer</th>');
    columns.push('<th>SQN</th>');
    columns.push('<th>Consist</th>');
    return columns.join('');
  }

  function renderTrialRow(trial, objectives, flags) {
    const objectiveList = Array.isArray(objectives) ? objectives : [];
    const objectiveSet = new Set(objectiveList);
    const hasConstraints = Boolean(flags && flags.hasConstraints);
    const isPareto = Boolean(trial.is_pareto_optimal);
    const feasible = trial.constraints_satisfied !== undefined
      ? Boolean(trial.constraints_satisfied)
      : true;

    const paretoBadge = isPareto
      ? '<span class="badge badge-pareto">Pareto</span>'
      : '';

    let constraintBadge = '';
    if (hasConstraints) {
      constraintBadge = feasible
        ? '<span class="badge badge-feasible">OK</span>'
        : '<span class="badge badge-infeasible">Fail</span>';
    }

    const objectiveValues = Array.isArray(trial.objective_values) ? trial.objective_values : [];
    const objectiveCells = objectiveList.map((objective, idx) => {
      const value = objectiveValues[idx];
      const isPercent = objective.includes('pct') || objective === 'win_rate';
      const formatted = formatNumber(value, isPercent ? 2 : 3);
      return `<td>${formatted}${isPercent && formatted !== 'N/A' ? '%' : ''}</td>`;
    });

    let netProfitCell = '';
    if (!objectiveSet.has('net_profit_pct')) {
      const netProfit = Number(trial.net_profit_pct || 0);
      netProfitCell = `<td class="${netProfit >= 0 ? 'val-positive' : 'val-negative'}">${netProfit >= 0 ? '+' : ''}${formatNumber(netProfit, 2)}%</td>`;
    }
    let maxDdCell = '';
    if (!objectiveSet.has('max_drawdown_pct')) {
      const maxDd = Math.abs(Number(trial.max_drawdown_pct || 0));
      maxDdCell = `<td class="val-negative">-${formatNumber(maxDd, 2)}%</td>`;
    }

    const scoreValue = trial.score !== undefined && trial.score !== null
      ? Number(trial.score)
      : null;
    const romad = trial.romad;
    const sharpe = trial.sharpe_ratio;
    const pf = trial.profit_factor;
    const ulcer = trial.ulcer_index;
    const sqn = trial.sqn;
    const consistency = trial.consistency_score;

    return `
      <tr class="clickable" data-trial-number="${trial.trial_number ?? ''}">
        <td class="rank"></td>
        <td class="param-hash"></td>
        <td>${paretoBadge}</td>
        ${hasConstraints ? `<td>${constraintBadge}</td>` : ''}
        ${objectiveCells.join('')}
        ${netProfitCell}
        ${maxDdCell}
        <td>${trial.total_trades ?? '-'}</td>
        <td>${scoreValue !== null ? formatNumber(scoreValue, 1) : 'N/A'}</td>
        <td>${formatNumber(romad, 3)}</td>
        <td>${formatNumber(sharpe, 3)}</td>
        <td>${formatNumber(pf, 3)}</td>
        <td>${formatNumber(ulcer, 2)}</td>
        <td>${formatNumber(sqn, 3)}</td>
        <td>${formatNumber(consistency, 1)}${consistency !== null && consistency !== undefined ? '%' : ''}</td>
      </tr>
    `;
  }

  window.OptunaResultsUI = {
    buildTrialTableHeaders,
    renderTrialRow
  };
})();
