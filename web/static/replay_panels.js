// Panels of the replay page: navigation card, fix details, track summary, route steps table and the charts.
import { esc } from './core.js';
import { lineChart } from './charts.js';
import { accuracy, clock, deg, dist, dur, kmh, num } from './fmt.js';

export function renderNav(host, d, k, pr, name) {
  const steps = d.route.steps, cur = steps[pr.step_index], next = steps[pr.step_index + 1];
  const p = d.points[k], done = d.cumdist[k], t0 = d.points[0].t;
  const elapsed = p.t !== null && t0 !== null ? p.t - t0 : null;
  const avg = elapsed ? done / elapsed : null;
  host.innerHTML = `
  <div class="panel navcard" aria-live="polite">
    <h3>Navigation · step ${pr.step_index + 1} of ${pr.total_steps}</h3>
    <div class="instr">${esc(cur.instruction)}</div>
    <div class="next">${dist(pr.distance_to_turn)} to this step's point${next ? ` · then: ${esc(next.instruction)}` : ''}</div>
    <dl class="kv" style="margin-top:10px">
      <dt>Remaining</dt><dd>${dist(pr.distance_remaining)}</dd>
      <dt>ETA (app's 50 km/h)</dt><dd>${dur(pr.time_remaining)}</dd>
      <dt>ETA (this log's average so far)</dt><dd>${avg ? dur(pr.distance_remaining / avg) : '–'}</dd>
    </dl>
  </div>
  <div class="panel"><h3>Fix ${k + 1}</h3>
    <dl class="kv">
      <dt>Time</dt><dd>${clock(p.t, d.time_basis)}</dd>
      <dt>Position</dt><dd>${p.lat.toFixed(6)}°, ${p.lon.toFixed(6)}°</dd>
      <dt>Speed</dt><dd>${kmh(p.speed)}</dd>
      <dt>Course</dt><dd>${deg(p.course)}</dd>
      <dt>Altitude</dt><dd>${num(p.altitude, 1, ' m')}</dd>
      <dt>Fix · sats · HDOP</dt><dd>${p.fix_quality ?? '–'} · ${p.satellites ?? '–'} · ${num(p.hdop, 1)}</dd>
      <dt>Accuracy (app's estimate)</dt><dd>${accuracy(p.accuracy)}</dd>
      <dt>Travelled</dt><dd>${dist(done)}${elapsed !== null ? ` in ${dur(elapsed)}` : ''}</dd>
    </dl></div>`;
}

export function renderStats(host, d) {
  const s = d.stats;
  host.innerHTML = `<div class="panel"><h3>Whole log</h3><dl class="kv">
    <dt>Fixes</dt><dd>${s.n}</dd><dt>Distance</dt><dd>${dist(s.distance_m)}</dd>
    <dt>Duration</dt><dd>${dur(s.duration_s)}${d.time_basis === 'time of day' ? ' (time of day only)' : ''}</dd>
    <dt>Average speed</dt><dd>${kmh(s.avg_speed_ms)}</dd><dt>Max recorded speed</dt><dd>${kmh(s.max_speed_ms)}</dd>
    <dt>Altitude</dt><dd>${s.min_alt === null ? '–' : `${s.min_alt.toFixed(0)}–${s.max_alt.toFixed(0)} m`}</dd>
    <dt>Format</dt><dd>${esc(d.format.toUpperCase())}</dd></dl></div>`;
}

export function renderSteps(host, r) {
  host.innerHTML = `<div class="scroll"><table class="tbl"><thead><tr><th>#</th><th>Instruction</th><th>Leg</th><th>Bearing</th><th>Position</th></tr></thead><tbody>
    ${r.steps.map((s, i) => `<tr data-i="${i}"><td>${i + 1}</td><td>${esc(s.instruction)}</td><td>${s.distance_to_next ? dist(s.distance_to_next) : ''}</td>
      <td>${s.turn_type === 'arrive' ? '' : deg(s.bearing)}</td><td>${s.latitude.toFixed(5)}, ${s.longitude.toFixed(5)}</td></tr>`).join('')}
    </tbody></table></div><p class="small mute">Total ${dist(r.distance)}, ${dur(r.duration)} at the offline router's 50 km/h.</p>`;
}

export function renderCharts(host, d) {
  const x = d.cumdist.map(m => m / 1000);
  host.innerHTML = '<div class="two"><div class="panel"><h3>Speed</h3><div id="ch-speed"></div></div><div class="panel"><h3>Altitude</h3><div id="ch-alt"></div></div></div>';
  const a = lineChart(host.querySelector('#ch-speed'), { x, xLabel: 'km', yLabel: 'km/h', series: [{ y: d.points.map(p => (p.speed === null ? null : p.speed * 3.6)) }] });
  const b = lineChart(host.querySelector('#ch-alt'), { x, xLabel: 'km', yLabel: 'm', series: [{ y: d.points.map(p => p.altitude), cls: 'line2' }] });
  return { cursor(i) { a.cursor(i); b.cursor(i); } };
}
