// Small SVG line chart with a movable cursor (speed and elevation profiles on the replay page).
import { esc } from './core.js';

// series: [{ y: [...numbers|null], cls: 'line'|'line2', label }]; x: numbers (same length). Returns { svg, cursor(i) }.
export function lineChart(host, { x, series, xLabel = '', yLabel = '', height = 150 }) {
  const W = 600, H = height, L = 44, R = 8, T = 10, B = 26;
  const ys = series.flatMap(s => s.y.filter(v => v !== null && v !== undefined && Number.isFinite(v)));
  if (!ys.length || x.length < 2) { host.innerHTML = '<p class="mute small">No data for this chart in this log.</p>'; return { cursor() {} }; }
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (y1 - y0 < 1e-9) { y0 -= 1; y1 += 1; }
  const x0 = x[0], x1 = x[x.length - 1] === x0 ? x0 + 1 : x[x.length - 1];
  const px = v => L + (v - x0) / (x1 - x0) * (W - L - R), py = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  const path = y => {
    let d = '', pen = false;
    y.forEach((v, i) => {
      if (v === null || v === undefined || !Number.isFinite(v)) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${px(x[i]).toFixed(1)},${py(v).toFixed(1)}`; pen = true;
    });
    return d;
  };
  const ticks = [y0, (y0 + y1) / 2, y1];
  host.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(yLabel)} against ${esc(xLabel)}">
    <line class="axis" x1="${L}" y1="${H - B}" x2="${W - R}" y2="${H - B}"/><line class="axis" x1="${L}" y1="${T}" x2="${L}" y2="${H - B}"/>
    ${ticks.map(t => `<text x="${L - 4}" y="${py(t) + 4}" text-anchor="end">${t.toFixed(t < 10 ? 1 : 0)}</text>`).join('')}
    <text x="${W - R}" y="${H - 6}" text-anchor="end">${esc(xLabel)}</text><text x="${L + 4}" y="${T + 10}">${esc(yLabel)}</text>
    ${series.map(s => `<path class="${s.cls || 'line'}" d="${path(s.y)}"/>`).join('')}
    <line class="cursor" x1="${L}" y1="${T}" x2="${L}" y2="${H - B}"/></svg>`;
  const cur = host.querySelector('.cursor');
  return { cursor(i) { const v = px(x[Math.max(0, Math.min(x.length - 1, i))]); cur.setAttribute('x1', v); cur.setAttribute('x2', v); } };
}
