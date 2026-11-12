// Navigation maths: small calculators over the JS port of navmath (distance/bearing, offline route, GPS accuracy,
// NMEA checker, tiles). All run in the browser, in both the static site and the local app.
import { $, app, esc, route } from './core.js';
import * as nav from './nav_engine.js';
import { checksum, parseNmeaLog } from './nmea_engine.js';
import { accuracy, deg, dist, dur, kmh } from './fmt.js';

const DEFAULT_ROUTE = '30.2747, -97.7404\n30.2655, -97.7445\n30.2630, -97.7520\n30.2669, -97.7729';
const SAMPLE_NMEA = '$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\n$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A\n$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6B';

function coords(s) {
  const m = String(s).trim().split(/[\s,;]+/).map(Number);
  if (m.length !== 2 || m.some(v => !Number.isFinite(v)) || Math.abs(m[0]) > 90 || Math.abs(m[1]) > 180) throw new Error(`"${s}" is not "latitude, longitude" in degrees`);
  return m;
}
const out = (el, fn) => { try { el.innerHTML = fn(); } catch (e) { el.innerHTML = `<p class="err">${esc(e.message)}</p>`; } };

route('tools', () => {
  app().innerHTML = `
  <h1>Navigation maths</h1>
  <p class="lead">The calculations PyNav uses, running in your browser (<span class="badge js">JS port</span> of <code>navmath/</code>,
    checked against the Python in <code>web/static/nav_engine.test.mjs</code>). The Earth is a sphere of radius 6371 km, as in the app.</p>
  <div class="two">
    <div class="panel"><h3>Distance and bearing</h3>
      <label for="a">From (latitude, longitude)</label><input id="a" value="51.5007, -0.1246">
      <label for="b">To</label><input id="b" value="48.8584, 2.2945"><div id="ab"></div></div>
    <div class="panel"><h3>GPS accuracy estimate</h3>
      <label for="fq">GGA fix quality</label><select id="fq"><option value="0">0 no fix</option><option value="1" selected>1 GPS</option><option value="2">2 DGPS</option><option value="4">4 RTK</option></select>
      <label for="sats">Satellites</label><input id="sats" type="number" min="0" max="40" value="8">
      <label for="hdop">HDOP</label><input id="hdop" type="number" min="0" step="0.1" value="1.2"><div id="acc"></div></div>
  </div>
  <div class="panel"><h3>Straight-line route (the offline router)</h3>
    <label for="pts">Points, one "latitude, longitude" per line (start, waypoints, destination)</label><textarea id="pts">${DEFAULT_ROUTE}</textarea>
    <div id="rt"></div></div>
  <div class="panel"><h3>NMEA checker</h3>
    <label for="nm">Paste NMEA sentences</label><textarea id="nm">${SAMPLE_NMEA}</textarea><div id="nmo"></div></div>
  <div class="panel"><h3>Map tile</h3>
    <div class="row"><div><label for="tp">Point</label><input id="tp" value="30.2747, -97.7404"></div>
      <div><label for="tz">Zoom</label><input id="tz" type="number" min="0" max="19" value="15"></div></div><div id="to"></div></div>`;

  const ab = () => out($('#ab'), () => {
    const [la1, lo1] = coords($('#a').value), [la2, lo2] = coords($('#b').value);
    const d = nav.haversineM(la1, lo1, la2, lo2), b = nav.initialBearingDeg(la1, lo1, la2, lo2);
    return `<dl class="kv" style="margin-top:10px"><dt>Distance</dt><dd>${dist(d)} (${d.toFixed(1)} m)</dd>
      <dt>Initial bearing</dt><dd>${deg(b)} · ${nav.bearingToDirection(b)}</dd>
      <dt>Back bearing</dt><dd>${deg(nav.initialBearingDeg(la2, lo2, la1, lo1))}</dd>
      <dt>At 50 km/h</dt><dd>${dur(d / (50 / 3.6))}</dd></dl>`;
  });
  const acc = () => out($('#acc'), () => {
    const a = nav.estimateGpsAccuracy(+$('#fq').value, +$('#sats').value, +$('#hdop').value);
    return `<p style="margin-top:10px">Estimated accuracy: <b>${accuracy(a)}</b></p><p class="small mute">Base 5 m (GPS), 2 m (DGPS) or 1 m (RTK);
      × 0.8 with 8+ satellites, 1.0 with 6–7, 1.5 with 4–5, 3 with fewer; × 1.0 / 1.2 / 1.5 / 2 / 3 for HDOP below 2 / 5 / 10 / 20 / above.
      This is the desktop app's rule of thumb (GPSProvider), not a statistical error model.</p>`;
  });
  const rt = () => out($('#rt'), () => {
    const pts = $('#pts').value.split('\n').filter(l => l.trim()).map(coords), r = nav.offlineRoute(pts);
    return `<div class="scroll"><table class="tbl"><thead><tr><th>#</th><th>Instruction</th><th>Leg</th><th>Bearing</th></tr></thead><tbody>
      ${r.steps.map((s, i) => `<tr><td>${i + 1}</td><td>${esc(s.instruction)}</td><td>${s.distance_to_next ? dist(s.distance_to_next) : ''}</td><td>${s.turn_type === 'arrive' ? '' : deg(s.bearing)}</td></tr>`).join('')}
      </tbody></table></div><p>Total <b>${dist(r.distance)}</b>, <b>${dur(r.duration)}</b> at 50 km/h.</p>`;
  });
  const nm = () => out($('#nmo'), () => {
    const rows = $('#nm').value.split('\n').filter(l => l.trim()).map(l => {
      const m = /^\s*\$([^*]*)(?:\*([0-9A-Fa-f]{2}))?/.exec(l);
      if (!m) return `<tr><td class="bad">not NMEA</td><td colspan="2">${esc(l.slice(0, 80))}</td></tr>`;
      const want = checksum(m[1]), ok = !m[2] || m[2].toUpperCase() === want;
      const p = parseNmeaLog(l).points[0];
      return `<tr><td class="${ok ? 'okk' : 'bad'}">${m[2] ? (ok ? 'checksum ok' : `checksum ${m[2]} ≠ ${want}`) : `no checksum (${want})`}</td>
        <td>${esc(m[1].split(',')[0])}</td><td>${p ? `${p.lat.toFixed(6)}, ${p.lon.toFixed(6)} · ${kmh(p.speed)} · ${deg(p.course)}` : ''}</td></tr>`;
    });
    return `<div class="scroll"><table class="tbl"><thead><tr><th>Check</th><th>Type</th><th>Fix (RMC)</th></tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
  });
  const to = () => out($('#to'), () => {
    const [la, lo] = coords($('#tp').value), z = Math.max(0, Math.min(19, Math.trunc(+$('#tz').value)));
    const [x, y] = nav.deg2tile(la, lo, z), [w, n, e, s] = nav.tile2deg(x, y, z);
    return `<dl class="kv" style="margin-top:10px"><dt>Tile</dt><dd>z ${z} · x ${x} · y ${y}</dd>
      <dt>Bounds</dt><dd>lon ${w.toFixed(5)} to ${e.toFixed(5)}, lat ${s.toFixed(5)} to ${n.toFixed(5)}</dd>
      <dt>OSM path</dt><dd>${z}/${x}/${y}.png</dd></dl>`;
  });
  for (const [ids, fn] of [[['a', 'b'], ab], [['fq', 'sats', 'hdop'], acc], [['pts'], rt], [['nm'], nm], [['tp', 'tz'], to]]) {
    ids.forEach(id => $('#' + id).addEventListener('input', fn));
    fn();
  }
});
