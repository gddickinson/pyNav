// Home: hero, real numbers from the synthetic demo (computed by navmath), cards to the pages.
import { api, app, isStatic, route } from './core.js';
import { dist, dur } from './fmt.js';

route('home', async () => {
  const info = await api('/info');
  const d = info.demo;
  app().innerHTML = `
  <section class="hero">
    <p class="kicker">GPS navigation · PyQt6 desktop app · web companion</p>
    <h1 class="glow">PyNav</h1>
    <p class="lead">PyNav is a desktop GPS navigator: live tracking from a serial NMEA receiver or an iPhone, OSRM / GraphHopper /
      offline routing with turn-by-turn directions, tile maps and points of interest. This page runs its navigation maths
      on <b>your own GPS logs</b>: open a GPX or NMEA file and replay it with distance, speed, accuracy and route following.</p>
    <a class="btn" href="#/replay">Replay a log</a><a class="btn alt" href="#/tools">Navigation maths</a><a class="btn alt" href="#/live">Live GPS</a>
  </section>
  <div class="tiles">
    <div class="tile"><b>${d.n}</b><span>fixes in the synthetic demo drive</span></div>
    <div class="tile"><b>${dist(d.distance_m)}</b><span>demo distance (haversine)</span></div>
    <div class="tile"><b>${dur(d.duration_s)}</b><span>demo duration</span></div>
    <div class="tile"><b>${d.steps}</b><span>steps in its offline route</span></div>
    <div class="tile"><b>${info.offline_speed_kmh} km/h</b><span>the app's ETA speed</span></div>
  </div>
  ${isStatic() ? `<div class="callout">Static site: files you open are read <b>in your browser</b> by a JavaScript port of PyNav's
    navigation code (tested against the Python on the same inputs) and never uploaded. The live GPS dashboard needs the local app.</div>` : ''}
  <h2>Pages</h2>
  <div class="grid">
    <a class="card" href="#/replay"><b>Replay</b><span>Open a GPX or NMEA log (or the synthetic demo), play it on a map, see speed and altitude profiles and the turn-by-turn state at every fix.</span></a>
    <a class="card" href="#/tools"><b>Navigation maths</b><span>Distance and bearing, straight-line routes, the GPS accuracy estimate, an NMEA sentence checker and slippy-map tiles.</span></a>
    <a class="card" href="#/live"><b>Live GPS</b><span>Local app: read a USB/serial GPS receiver or the iPhone tracking server and watch the fix update.</span></a>
    <a class="card" href="#/about"><b>About</b><span>What PyNav is, how to run the desktop app and this web app, privacy and credits.</span></a>
  </div>
  <h2>Formats read</h2>
  <ul>${info.formats.map(f => `<li>${f}</li>`).join('')}</ul>`;
});
