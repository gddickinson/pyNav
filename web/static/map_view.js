// Canvas map for tracks and routes: Web Mercator, drag to pan, wheel / buttons to zoom. Plain dark grid by default;
// OpenStreetMap tiles (as the desktop app uses, with attribution) only when the user switches them on, because tile
// requests tell the tile server which area is being viewed.
import { lonLatToTileXY } from './nav_engine.js';

const TILE = 256, OSM = 'https://tile.openstreetmap.org/';
const world = (lat, lon) => { const [x, y] = lonLatToTileXY(lat, lon, 0); return [x * TILE, y * TILE]; };

export function createMap(host, { height } = {}) {
  host.classList.add('mapbox');
  host.innerHTML = `<canvas role="img" aria-label="Map of the track"></canvas>
    <div class="zoom"><button type="button" class="alt" data-z="1" aria-label="Zoom in">+</button><button type="button" class="alt" data-z="-1" aria-label="Zoom out">−</button></div>
    <div class="attr hide">© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors</div>`;
  const canvas = host.querySelector('canvas'), g = canvas.getContext('2d'), attr = host.querySelector('.attr');
  if (height) canvas.style.height = height + 'px';
  const s = { track: [], route: [], cursor: null, upto: -1, tiles: false, cx: 0, cy: 0, z: 2, follow: false };
  const cache = new Map();
  let queued = false;

  const size = () => { const r = canvas.getBoundingClientRect(); return [Math.max(50, r.width), Math.max(50, r.height)]; };
  const scale = () => 2 ** s.z;
  const toScreen = (lat, lon, w, h) => { const [x, y] = world(lat, lon); return [(x - s.cx) * scale() + w / 2, (y - s.cy) * scale() + h / 2]; };

  function tile(z, x, y) {
    const key = `${z}/${x}/${y}`;
    if (!cache.has(key)) {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = redraw; img.onerror = () => { img.failed = true; };
      img.src = `${OSM}${key}.png`;
      cache.set(key, img);
    }
    return cache.get(key);
  }

  function drawTiles(w, h) {
    const zi = Math.max(0, Math.min(19, Math.round(s.z))), k = 2 ** (s.z - zi), n = 2 ** zi, size = TILE * k;
    const x0 = (s.cx * 2 ** zi - (w / 2) / k) / TILE, y0 = (s.cy * 2 ** zi - (h / 2) / k) / TILE;
    for (let ty = Math.floor(y0); ty < y0 + h / size + 1; ty++) {
      if (ty < 0 || ty >= n) continue;
      for (let tx = Math.floor(x0); tx < x0 + w / size + 1; tx++) {
        const img = tile(zi, ((tx % n) + n) % n, ty);
        if (img.complete && !img.failed && img.naturalWidth) g.drawImage(img, (tx - x0) * size, (ty - y0) * size, size + 0.5, size + 0.5);
      }
    }
    g.fillStyle = 'rgba(3,5,11,.25)'; g.fillRect(0, 0, w, h);
  }

  function drawGrid(w, h) {
    // lines every power-of-ten metres-ish in world units: just a light tile grid at the nearest zoom
    const zi = Math.max(0, Math.round(s.z) + 2), step = TILE / 2 ** zi * scale() * 2 ** Math.round(s.z);
    if (step < 8) return;
    g.strokeStyle = 'rgba(79,163,255,.08)'; g.lineWidth = 1;
    const ox = (-(s.cx * scale()) + w / 2) % step, oy = (-(s.cy * scale()) + h / 2) % step;
    g.beginPath();
    for (let x = ox; x < w; x += step) { g.moveTo(x, 0); g.lineTo(x, h); }
    for (let y = oy; y < h; y += step) { g.moveTo(0, y); g.lineTo(w, y); }
    g.stroke();
  }

  function metresPerPixel(lat) { return Math.cos(lat * Math.PI / 180) * 2 * Math.PI * 6378137 / (TILE * scale()); }

  function drawScale(w, h) {
    const lat = s.cursor ? s.cursor.lat : s.track.length ? s.track[0].lat : 0, mpp = metresPerPixel(lat);
    const target = mpp * 100, p = 10 ** Math.floor(Math.log10(target)), nice = [1, 2, 5, 10].map(v => v * p).filter(v => v <= target).pop() || p;
    const px = nice / mpp;
    g.strokeStyle = '#e8f1ff'; g.fillStyle = '#e8f1ff'; g.lineWidth = 2; g.font = '11px ui-monospace,Menlo,monospace';
    g.beginPath(); g.moveTo(12, h - 14); g.lineTo(12 + px, h - 14); g.stroke();
    g.fillText(nice >= 1000 ? `${nice / 1000} km` : `${nice} m`, 12, h - 20);
  }

  function draw() {
    queued = false;
    const dpr = devicePixelRatio || 1, [w, h] = size();
    if (canvas.width !== Math.round(w * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = '#03050b'; g.fillRect(0, 0, w, h);
    attr.classList.toggle('hide', !s.tiles);
    if (s.tiles) drawTiles(w, h); else drawGrid(w, h);
    if (s.route.length) {
      g.setLineDash([6, 5]); g.strokeStyle = '#ffb02e'; g.lineWidth = 2; g.beginPath();
      s.route.forEach((st, i) => { const [x, y] = toScreen(st.latitude, st.longitude, w, h); i ? g.lineTo(x, y) : g.moveTo(x, y); });
      g.stroke(); g.setLineDash([]);
      s.route.forEach((st, i) => {
        const [x, y] = toScreen(st.latitude, st.longitude, w, h);
        g.fillStyle = i === s.routeOn ? '#ffb02e' : '#03050b'; g.strokeStyle = '#ffb02e'; g.lineWidth = 2;
        g.beginPath(); g.arc(x, y, 5, 0, 2 * Math.PI); g.fill(); g.stroke();
      });
    }
    const line = (from, to, colour, width) => {
      if (to - from < 1) return;
      g.strokeStyle = colour; g.lineWidth = width; g.lineJoin = 'round'; g.beginPath();
      for (let i = from; i <= to; i++) { const [x, y] = toScreen(s.track[i].lat, s.track[i].lon, w, h); i === from ? g.moveTo(x, y) : g.lineTo(x, y); }
      g.stroke();
    };
    if (s.track.length) {
      line(0, s.track.length - 1, 'rgba(79,163,255,.55)', 2);
      if (s.upto > 0) line(0, Math.min(s.upto, s.track.length - 1), '#36f1cd', 3);
    }
    if (s.cursor) {
      const c = s.cursor, [x, y] = toScreen(c.lat, c.lon, w, h);
      if (c.accuracy && c.accuracy < 999) {
        const r = c.accuracy / metresPerPixel(c.lat);
        if (r > 3) { g.fillStyle = 'rgba(54,241,205,.12)'; g.beginPath(); g.arc(x, y, r, 0, 2 * Math.PI); g.fill(); }
      }
      g.save(); g.translate(x, y);
      if (c.course !== null && c.course !== undefined) {
        g.rotate(c.course * Math.PI / 180);
        g.fillStyle = '#36f1cd'; g.beginPath(); g.moveTo(0, -11); g.lineTo(7, 8); g.lineTo(0, 4); g.lineTo(-7, 8); g.closePath(); g.fill();
      } else { g.fillStyle = '#36f1cd'; g.beginPath(); g.arc(0, 0, 6, 0, 2 * Math.PI); g.fill(); }
      g.restore();
    }
    drawScale(w, h);
  }
  function redraw() { if (!queued) { queued = true; requestAnimationFrame(draw); } }

  function fit(points = s.track.length ? s.track : s.route.map(r => ({ lat: r.latitude, lon: r.longitude }))) {
    if (!points.length) return;
    const xy = points.map(p => world(p.lat, p.lon)), xs = xy.map(p => p[0]), ys = xy.map(p => p[1]);
    const [w, h] = size(), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    s.cx = (x0 + x1) / 2; s.cy = (y0 + y1) / 2;
    const span = Math.max((x1 - x0) / (w - 60), (y1 - y0) / (h - 60), 1e-9);
    s.z = Math.max(1, Math.min(19, Math.log2(1 / span)));
    redraw();
  }

  function zoomBy(dz, px, py) {
    const [w, h] = size(), ax = px ?? w / 2, ay = py ?? h / 2;
    const wx = s.cx + (ax - w / 2) / scale(), wy = s.cy + (ay - h / 2) / scale();
    s.z = Math.max(1, Math.min(19, s.z + dz));
    s.cx = wx - (ax - w / 2) / scale(); s.cy = wy - (ay - h / 2) / scale();
    redraw();
  }

  host.querySelectorAll('[data-z]').forEach(b => b.addEventListener('click', () => zoomBy(+b.dataset.z * 0.5)));
  canvas.addEventListener('wheel', e => { e.preventDefault(); const r = canvas.getBoundingClientRect(); zoomBy(-Math.sign(e.deltaY) * 0.25, e.clientX - r.left, e.clientY - r.top); }, { passive: false });
  let drag = null;
  canvas.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY }; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', e => {
    if (!drag) return;
    s.cx -= (e.clientX - drag.x) / scale(); s.cy -= (e.clientY - drag.y) / scale();
    drag = { x: e.clientX, y: e.clientY }; s.follow = false; redraw();
  });
  canvas.addEventListener('pointerup', () => { drag = null; });
  addEventListener('resize', redraw);

  return {
    setTrack(points) { s.track = points || []; s.upto = -1; redraw(); },
    setRoute(steps, on = -1) { s.route = steps || []; s.routeOn = on; redraw(); },
    setCursor(c, upto = -1, routeOn = -1) {
      s.cursor = c; s.upto = upto; s.routeOn = routeOn;
      if (c && s.follow) { [s.cx, s.cy] = world(c.lat, c.lon); }
      redraw();
    },
    setTiles(on) { s.tiles = !!on; redraw(); },
    setFollow(on) { s.follow = !!on; redraw(); },
    fit, redraw,
  };
}
