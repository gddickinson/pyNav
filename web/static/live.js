// Live GPS dashboard (local app only): a serial NMEA receiver read by the Python server, and the iPhone tracking
// server (iphoneTracking/macbook_server.py). On the static site it explains what it needs.
import { $, api, app, esc, isStatic, needsServer, onLeave, route } from './core.js';
import { createMap } from './map_view.js';
import { accuracy, clock, deg, kmh, num } from './fmt.js';

function fixCard(p, title) {
  if (!p) return `<div class="panel"><h3>${esc(title)}</h3><p class="mute">No fix yet.</p></div>`;
  return `<div class="panel"><h3>${esc(title)}</h3><dl class="kv">
    <dt>Time</dt><dd>${p.t ? clock(p.t, 'utc') : '–'}</dd><dt>Position</dt><dd>${p.lat.toFixed(6)}°, ${p.lon.toFixed(6)}°</dd>
    <dt>Speed</dt><dd>${kmh(p.speed)}</dd><dt>Course</dt><dd>${deg(p.course)}</dd><dt>Altitude</dt><dd>${num(p.altitude, 1, ' m')}</dd>
    <dt>Fix · sats · HDOP</dt><dd>${p.fix_quality ?? '–'} · ${p.satellites ?? '–'} · ${num(p.hdop, 1)}</dd>
    <dt>Accuracy</dt><dd>${accuracy(p.accuracy)}</dd></dl></div>`;
}

route('live', async () => {
  if (isStatic()) {
    app().innerHTML = `<h1>Live GPS</h1>
      <p class="lead">The dashboard reads a USB/serial GPS receiver (NMEA over pyserial, like the desktop app's GPS provider) or the
        position the iPhone tracking server has received. A web page on GitHub Pages cannot reach either, so this page works in the local app.</p>
      ${needsServer('The live GPS dashboard')}
      <div class="panel"><h3>Run it locally</h3><pre>pip install -r requirements-web.txt
python run_web.py            # http://127.0.0.1:8179/#/live
python iphoneTracking/macbook_server.py   # optional: the iPhone server on port 8000</pre></div>
      <p>Meanwhile you can <a href="#/replay">replay a recorded log</a> in your browser.</p>`;
    return;
  }
  const src = await api('/live/sources', { fresh: true });
  app().innerHTML = `<h1>Live GPS</h1>
    <p class="lead">Read a GPS receiver on this computer, or the iPhone tracking server, and watch the fix update. Parsing uses the same
      code as the replay page (navmath, with pynmea2).</p>
    <div class="two">
      <div class="panel"><h3>Serial GPS (NMEA)</h3>
        ${src.pyserial ? '' : '<p class="err">pyserial is not installed (pip install -r requirements-web.txt).</p>'}
        <label for="port">Port</label><select id="port">${src.serial_ports.length ? src.serial_ports.map(p => `<option>${esc(p)}</option>`).join('') : '<option value="">no USB/serial ports found</option>'}</select>
        <label for="baud">Baud rate</label><select id="baud">${[4800, 9600, 38400, 57600, 115200].map(b => `<option ${b === src.default_baud ? 'selected' : ''}>${b}</option>`).join('')}</select>
        <button type="button" id="start">Start</button><button type="button" id="stop" class="alt">Stop</button><button type="button" id="rescan" class="alt">Rescan</button>
        <p id="sst" class="small mute" role="status"></p></div>
      <div class="panel"><h3>iPhone tracking server</h3>
        <label for="iurl">Server address (this computer or the local network)</label><input id="iurl" value="${esc(src.iphone_default)}">
        <label style="margin-top:10px"><input type="checkbox" id="ipoll"> poll every 2 s</label>
        <p id="ist" class="small mute" role="status">Start <code>iphoneTracking/macbook_server.py</code> and the iPhone app (see iphoneTracking/setup_guide.md).</p></div>
    </div>
    <div class="two"><div id="map"></div><div id="fix"></div></div>
    <div class="panel"><h3>Last NMEA lines</h3><pre class="raw" id="raw">–</pre></div>`;
  const map = createMap($('#map'), { height: 360 });
  map.setFollow(true);
  let timer = 0, itimer = 0, fitted = false;

  async function pollSerial() {
    const { reader } = await api('/live/serial', { fresh: true });
    if (!reader) { $('#sst').textContent = 'Not reading.'; return; }
    $('#sst').innerHTML = reader.error ? `<span class="err">${esc(reader.error)}</span>`
      : `${esc(reader.port)} @ ${reader.baudrate}: ${reader.lines_read} lines${reader.skipped ? `, ${reader.skipped} bad in the last 200` : ''}${reader.running ? '' : ' (stopped)'}`;
    $('#raw').textContent = reader.raw.join('\n') || '–';
    $('#fix').innerHTML = fixCard(reader.fix, 'Serial fix');
    map.setTrack(reader.recent_fixes);
    if (reader.fix) { map.setCursor(reader.fix, reader.recent_fixes.length - 1); if (!fitted) { map.fit(); fitted = true; } }
  }
  async function pollIphone() {
    try {
      const r = await api('/live/iphone?url=' + encodeURIComponent($('#iurl').value), { fresh: true });
      if (!r.ok) { $('#ist').innerHTML = `<span class="err">${esc(r.server)}: ${esc(r.error)}</span>`; return; }
      const q = r.position;
      $('#ist').textContent = `${r.server}: position received.`;
      const p = { t: q.timestamp, lat: q.latitude, lon: q.longitude, speed: q.speed, course: q.heading, altitude: q.altitude, accuracy: q.accuracy };
      if (p.lat === null || p.lat === undefined) return;
      $('#fix').innerHTML = fixCard(p, 'iPhone fix (horizontal accuracy from the phone)');
      map.setTrack([p]); map.setCursor(p); if (!fitted) { map.fit([p]); fitted = true; }
    } catch (e) { $('#ist').innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  }

  $('#start').addEventListener('click', async () => {
    if (!$('#port').value) return;
    try {
      await api('/live/serial/start', { body: { port: $('#port').value, baudrate: +$('#baud').value } });
      fitted = false; clearInterval(timer); timer = setInterval(pollSerial, 1000); pollSerial();
    } catch (e) { $('#sst').innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  });
  $('#stop').addEventListener('click', async () => { clearInterval(timer); await api('/live/serial/stop', { body: {} }); pollSerial(); });
  $('#rescan').addEventListener('click', () => location.reload());
  $('#ipoll').addEventListener('change', e => { clearInterval(itimer); if (e.target.checked) { itimer = setInterval(pollIphone, 2000); pollIphone(); } });
  onLeave(() => { clearInterval(timer); clearInterval(itimer); });
  pollSerial();
});
