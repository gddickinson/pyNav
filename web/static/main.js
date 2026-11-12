// Entry point: lazy page modules, the mode label, a subtle "satellite" background, then the router.
import { $, app, isStatic, lazy, route, start } from './core.js';

const PAGES = { 'home.js': ['home'], 'replay.js': ['replay'], 'tools.js': ['tools'], 'live.js': ['live'], 'about.js': ['about'] };
lazy(Object.fromEntries(Object.entries(PAGES).flatMap(([file, names]) => names.map(n => [n, () => import('./' + file)]))));
route('notfound', () => { app().innerHTML = '<h1>Not found</h1><p><a href="#/">Back to the start</a></p>'; });

$('#mode').textContent = isStatic()
  ? 'static site: your logs are read in your browser (JS port of the navigation maths); live GPS needs the local app'
  : 'local app: logs analysed by the Python navigation maths on this computer; live GPS available';

// Background: a few slow orbiting dots with faint trails. Off under prefers-reduced-motion.
function background(canvas) {
  if (!canvas || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const g = canvas.getContext('2d');
  const fit = () => { canvas.width = innerWidth; canvas.height = innerHeight; g.fillStyle = '#05060c'; g.fillRect(0, 0, canvas.width, canvas.height); };
  fit(); addEventListener('resize', fit);
  const sats = Array.from({ length: 9 }, (_, i) => ({ r: 0.2 + 0.07 * i, a: i * 0.7, w: (i % 2 ? 1 : -1) * (0.0006 + 0.0002 * i), c: ['#36f1cd', '#ffb02e', '#4fa3ff'][i % 3] }));
  let last = 0;
  const tick = t => {
    requestAnimationFrame(tick);
    if (document.hidden || t - last < 50) return;
    last = t;
    g.fillStyle = 'rgba(5,6,12,.05)'; g.fillRect(0, 0, canvas.width, canvas.height);
    const cx = canvas.width * 0.7, cy = canvas.height * 0.45, R = Math.min(canvas.width, canvas.height);
    for (const s of sats) {
      s.a += s.w * 50;
      g.fillStyle = s.c;
      g.beginPath(); g.arc(cx + Math.cos(s.a) * s.r * R, cy + Math.sin(s.a) * s.r * R * 0.6, 1.6, 0, 2 * Math.PI); g.fill();
    }
  };
  requestAnimationFrame(tick);
}
background($('#bg'));
start();
