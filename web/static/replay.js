// Replay: load a GPX/NMEA log (or the synthetic demo), play it back on the map and run PyNav's route following
// (RoutingEngine.update_location, ported) against a straight-line route planned along the log.
import { $, api, app, download, esc, isStatic, onLeave, route } from './core.js';
import { createMap } from './map_view.js';
import { followRoute } from './nav_engine.js';
import { toGpx } from './nmea_engine.js';
import { renderStats, renderSteps, renderCharts, renderNav } from './replay_panels.js';

const DEMO_FILE = 'static/demo/synthetic_drive.nmea';
const S = { data: null, text: null, name: '', progress: [], i: 0, playing: false, rate: 10, legs: 6, tiles: false };

route('replay', async () => {
  app().innerHTML = `
  <h1>Replay a GPS log</h1>
  <p class="lead">Open a <b>GPX</b> or <b>NMEA</b> log and watch it play back with PyNav's navigation maths: distance travelled,
    speed, GPS accuracy, and turn-by-turn route following with distance to the next turn, remaining distance and ETA.</p>
  <div class="panel">
    <div class="row">
      <div class="drop" id="drop"><label for="file">GPX or NMEA file (.gpx, .nmea, .txt, .log)</label>
        <input type="file" id="file" accept=".gpx,.nmea,.txt,.log,.csv,application/gpx+xml,text/plain">
        <p class="small mute">${isStatic() ? 'Read in your browser: the file never leaves this device.' : 'Sent only to the PyNav server on this computer (127.0.0.1); nothing is stored.'}</p></div>
      <div><button type="button" id="demo" class="alt">Load the synthetic demo drive</button>
        <p class="small mute">A <b>made-up</b> drive (straight legs between invented waypoints near the README's Austin example),
          simulated by <code>scripts/make_demo_track.py</code>, not a recording. <a href="${DEMO_FILE}" download>Download it</a>.</p></div>
    </div>
    <p id="msg" class="small" role="status"></p>
  </div>
  <div id="body" class="hide">
    <div class="player">
      <button type="button" id="play" aria-label="Play">▶ Play</button>
      <label class="sr" for="seek" style="margin:0">Position</label>
      <input type="range" id="seek" min="0" max="1" value="0" aria-label="Replay position">
      <span class="clock" id="clock"></span>
      <label for="rate" style="margin:0">Speed</label>
      <select id="rate" style="width:auto"><option value="1">1×</option><option value="5">5×</option><option value="10" selected>10×</option><option value="30">30×</option><option value="120">120×</option></select>
    </div>
    <div class="two">
      <div><div id="map"></div>
        <div class="legend"><span><i style="background:#4fa3ff"></i>track</span><span><i style="background:#36f1cd"></i>replayed</span><span><i style="background:#ffb02e"></i>planned route (straight legs)</span></div>
        <div class="row">
          <label style="margin:0"><input type="checkbox" id="follow"> follow position</label>
          <label style="margin:0"><input type="checkbox" id="tiles"> OpenStreetMap tiles</label>
        </div>
        <p class="small mute">Tiles are off by default: switching them on loads map images from tile.openstreetmap.org (as the desktop app does), which tells that server which area you are viewing. Your file itself is still not sent.</p>
      </div>
      <div><div id="nav"></div><div id="stats"></div></div>
    </div>
    <div id="charts"></div>
    <div class="panel"><h3>Route</h3>
      <div class="row"><div><label for="legs">Route legs along the track <b id="legsv"></b></label><input type="range" id="legs" min="1" max="20" value="6"></div>
        <div><button type="button" id="gpx" class="alt">Export track as GPX</button></div></div>
      <p class="small mute" id="routesrc"></p><div id="steps"></div></div>
  </div>`;
  const map = createMap($('#map'));
  const msg = t => { $('#msg').innerHTML = t; };

  async function load(text, name) {
    msg('Reading…');
    try {
      const d = await api('/analyse', { body: { text, name, legs: S.legs } });
      show(d, text, name);
    } catch (e) { msg(`<span class="err">${esc(e.message)}</span>`); }
  }

  function show(d, text, name) {
    Object.assign(S, { data: d, text, name, i: 0 });
    S.progress = followRoute(d.route.steps, d.points.map(p => [p.lat, p.lon]));
    const how = isStatic() ? '<span class="badge js">analysed in your browser (JS port)</span>' : '<span class="badge py">analysed by navmath (Python)</span>';
    msg(`<b>${esc(name)}</b>: ${d.points.length} fixes${d.skipped ? `, ${d.skipped} lines skipped (bad checksum or unreadable)` : ''}. ${how}`);
    $('#body').classList.remove('hide');
    $('#seek').max = d.points.length - 1;
    $('#legsv').textContent = $('#legs').value;
    $('#routesrc').textContent = `Straight-line route through ${esc(d.route_source)} (PyNav's offline router: "Head/Continue <direction>", then "Arrive"). Route following uses the app's rule: the nearest of the previous step and the next four becomes the current step once it is ahead; remaining time assumes the app's 50 km/h.`;
    map.setTrack(d.points); map.setRoute(d.route.steps); map.fit();
    renderStats($('#stats'), d);
    renderSteps($('#steps'), d.route);
    S.charts = renderCharts($('#charts'), d);
    seek(0);
  }

  function seek(i) {
    const d = S.data; if (!d) return;
    S.i = Math.max(0, Math.min(d.points.length - 1, i));
    const k = Math.floor(S.i), p = d.points[k], pr = S.progress[k];
    $('#seek').value = k;
    map.setCursor({ ...p }, k, pr.step_index);
    renderNav($('#nav'), d, k, pr, S.name);
    $('#clock').textContent = `${k + 1} / ${d.points.length}`;
    S.charts?.cursor(k);
    document.querySelectorAll('#steps tr[data-i]').forEach(tr => tr.classList.toggle('on', +tr.dataset.i === pr.step_index));
  }

  // playback: advance by log time × rate (1 fix per second when untimed)
  let last = 0, raf = 0;
  function tick(t) {
    if (!S.playing) return;
    const d = S.data, dt = last ? (t - last) / 1000 : 0; last = t;
    let i = S.i, budget = dt * S.rate;
    while (budget > 0 && i < d.points.length - 1) {
      const k = Math.floor(i), a = d.points[k].t, b = d.points[k + 1].t;
      const step = a !== null && b !== null && b > a ? b - a : 1, left = (k + 1 - i) * step;
      if (budget >= left) { budget -= left; i = k + 1; } else { i += budget / step; budget = 0; }
    }
    seek(i);
    if (i >= d.points.length - 1) return setPlaying(false);
    raf = requestAnimationFrame(tick);
  }
  function setPlaying(on) {
    S.playing = on; $('#play').textContent = on ? '❚❚ Pause' : '▶ Play'; $('#play').setAttribute('aria-label', on ? 'Pause' : 'Play');
    if (on) { if (S.i >= S.data.points.length - 1) S.i = 0; last = 0; raf = requestAnimationFrame(tick); } else cancelAnimationFrame(raf);
  }
  onLeave(() => { S.playing = false; cancelAnimationFrame(raf); });

  $('#file').addEventListener('change', async e => { const f = e.target.files[0]; if (f) load(await f.text(), f.name); });
  const drop = $('#drop');
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', async e => { e.preventDefault(); drop.classList.remove('over'); const f = e.dataTransfer.files[0]; if (f) load(await f.text(), f.name); });
  $('#demo').addEventListener('click', loadDemo);
  $('#play').addEventListener('click', () => setPlaying(!S.playing));
  $('#seek').addEventListener('input', e => { setPlaying(false); seek(+e.target.value); });
  $('#rate').addEventListener('change', e => { S.rate = +e.target.value; });
  $('#follow').addEventListener('change', e => map.setFollow(e.target.checked));
  $('#tiles').addEventListener('change', e => map.setTiles(e.target.checked));
  $('#legs').addEventListener('input', e => { $('#legsv').textContent = e.target.value; });
  $('#legs').addEventListener('change', e => { S.legs = +e.target.value; if (S.text) load(S.text, S.name); });
  $('#gpx').addEventListener('click', () => download((S.name.replace(/\.[^.]+$/, '') || 'track') + '.gpx', toGpx(S.data.points, S.name || 'PyNav Track'), 'application/gpx+xml'));
  map.setFollow(false);

  async function loadDemo() {
    msg('Loading the demo…');
    const [d, text] = await Promise.all([api('/demo'), fetch(DEMO_FILE).then(r => r.text())]);
    S.legs = 6; $('#legs').value = 6;
    show(d, text, 'synthetic_drive.nmea');
    msg(`<b>Synthetic demo drive</b> (not a real recording): ${d.points.length} fixes, analysed by navmath (Python) when ${isStatic() ? 'this site was built' : 'the page asked'}.`);
  }
  await loadDemo();
});
