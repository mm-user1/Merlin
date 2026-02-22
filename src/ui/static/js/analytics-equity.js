(function () {
  function parseTimestamp(value) {
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function renderEmpty(message) {
    const svg = document.getElementById('analyticsChartSvg');
    const axis = document.getElementById('analyticsEquityAxis');
    if (!svg) return;

    svg.innerHTML = '';
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', '400');
    text.setAttribute('y', '130');
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('fill', '#999');
    text.setAttribute('font-size', '14');
    text.textContent = message || 'No data to display';
    svg.appendChild(text);

    if (axis) {
      axis.innerHTML = '';
    }
  }

  function renderChart(equityCurve, timestamps) {
    const svg = document.getElementById('analyticsChartSvg');
    const axis = document.getElementById('analyticsEquityAxis');
    if (!svg) return;

    const curve = Array.isArray(equityCurve)
      ? equityCurve.map((value) => Number(value)).filter((value) => Number.isFinite(value))
      : [];

    if (!curve.length) {
      renderEmpty('No data to display');
      return;
    }

    const width = 800;
    const height = 260;
    const padding = 20;
    const hasTimestamps = Array.isArray(timestamps) && timestamps.length === curve.length;

    let useTimeScale = false;
    let tStart = null;
    let tEnd = null;
    if (hasTimestamps) {
      const start = parseTimestamp(timestamps[0]);
      const end = parseTimestamp(timestamps[timestamps.length - 1]);
      if (start !== null && end !== null && end > start) {
        useTimeScale = true;
        tStart = start;
        tEnd = end;
      }
    }

    const toXRatioByIndex = (index) => {
      if (!useTimeScale) {
        const denom = Math.max(1, curve.length - 1);
        return index / denom;
      }
      const ts = parseTimestamp(timestamps[index]);
      if (ts === null) {
        const denom = Math.max(1, curve.length - 1);
        return index / denom;
      }
      const ratio = (ts - tStart) / (tEnd - tStart);
      return Math.min(1, Math.max(0, ratio));
    };

    const baseValue = 100.0;
    const minValue = Math.min(baseValue, ...curve);
    const maxValue = Math.max(baseValue, ...curve);
    const valueRange = maxValue - minValue || 1;
    const toY = (value) => {
      return height - padding - ((value - minValue) / valueRange) * (height - padding * 2);
    };

    svg.innerHTML = '';
    if (axis) axis.innerHTML = '';

    const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bg.setAttribute('width', '100%');
    bg.setAttribute('height', '100%');
    bg.setAttribute('fill', '#fafafa');
    svg.appendChild(bg);

    const baseY = toY(baseValue);
    const baseLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    baseLine.setAttribute('x1', '0');
    baseLine.setAttribute('y1', String(baseY));
    baseLine.setAttribute('x2', String(width));
    baseLine.setAttribute('y2', String(baseY));
    baseLine.setAttribute('stroke', '#c8c8c8');
    baseLine.setAttribute('stroke-width', '1');
    baseLine.setAttribute('stroke-dasharray', '3 4');
    svg.appendChild(baseLine);

    if (hasTimestamps && axis) {
      const tickCount = Math.min(5, curve.length);
      for (let i = 0; i < tickCount; i += 1) {
        const ratio = tickCount === 1 ? 0 : i / (tickCount - 1);
        const x = ratio * width;
        const xPct = ratio * 100;

        const grid = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        grid.setAttribute('x1', String(x));
        grid.setAttribute('y1', '0');
        grid.setAttribute('x2', String(x));
        grid.setAttribute('y2', String(height));
        grid.setAttribute('stroke', '#e3e3e3');
        grid.setAttribute('stroke-width', '1');
        svg.appendChild(grid);

        let labelDate = null;
        if (useTimeScale) {
          labelDate = new Date(tStart + ratio * (tEnd - tStart));
        } else {
          const index = Math.round(ratio * (curve.length - 1));
          labelDate = new Date(timestamps[index]);
        }
        if (Number.isNaN(labelDate.getTime())) continue;

        const month = String(labelDate.getUTCMonth() + 1).padStart(2, '0');
        const day = String(labelDate.getUTCDate()).padStart(2, '0');

        const label = document.createElement('div');
        label.className = 'chart-axis-label';
        if (i === 0) label.className += ' start';
        if (i === tickCount - 1) label.className += ' end';
        label.style.left = `${xPct}%`;
        label.textContent = `${month}.${day}`;
        axis.appendChild(label);
      }
    }

    const points = curve
      .map((value, index) => {
        const x = toXRatioByIndex(index) * width;
        const y = toY(value);
        return `${x},${y}`;
      })
      .join(' ');

    const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    line.setAttribute('points', points);
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', '#4a90e2');
    line.setAttribute('stroke-width', '1.5');
    svg.appendChild(line);
  }

  window.AnalyticsEquity = {
    renderChart,
    renderEmpty,
  };
})();
