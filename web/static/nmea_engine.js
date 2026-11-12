// Track-log formats in JavaScript: a port of navmath/nmea.py (checksum, GGA/RMC writers, the NMEA log parser, which
// in Python uses pynmea2 as the app's serial GPS provider does), navmath/gpx.py and navmath/track.py (load + analyse).
// Pure functions, no DOM: node-tested against the Python in nav_engine.test.mjs. Files are parsed here, in the
// browser: nothing is uploaded.
import { cumulativeDistance, estimateGpsAccuracy, offlineRoute, trackStats, waypointsFromTrack } from './nav_engine.js';

export const KNOTS_TO_MS = 1852 / 3600;

export function checksum(body) {
  let x = 0;
  for (const c of body) x ^= c.charCodeAt(0);
  return x.toString(16).toUpperCase().padStart(2, '0');
}
export const sentence = body => `$${body}*${checksum(body)}`;

// Python round(): half to even.
function roundHalfEven(x) {
  const f = Math.floor(x), d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}
// Python f"{x:.{d}f}" (ties to even on the exact binary value).
// toFixed rounds exact ties up; detect an exact tie from the (exact) 40-digit expansion and round it to even instead.
export function fixed(x, d) {
  const exact = Math.abs(x).toFixed(40), dot = exact.indexOf('.');
  if (/^50*$/.test(exact.slice(dot + 1 + d))) {
    const kept = exact.slice(0, dot + 1 + d).replace('.', ''), last = +kept[kept.length - 1];
    if (last % 2 === 0) return (x < 0 ? '-' : '') + exact.slice(0, d ? dot + 1 + d : dot);
  }
  return x.toFixed(d);
}

export function formatCoord(value, isLat, decimals = 4) {
  const hemi = isLat ? (value >= 0 ? 'N' : 'S') : (value >= 0 ? 'E' : 'W');
  const scale = 10 ** decimals;
  const total = roundHalfEven(Math.abs(value) * 60 * scale);
  const deg = Math.floor(total / (60 * scale)), minutes = total - deg * 60 * scale;
  const width = isLat ? 2 : 3;
  return [String(deg).padStart(width, '0') + (minutes / scale).toFixed(decimals).padStart(decimals + 3, '0'), hemi];
}

const pad2 = n => String(n).padStart(2, '0');
function hms(ts) { const d = new Date(Math.floor(ts) * 1000); return pad2(d.getUTCHours()) + pad2(d.getUTCMinutes()) + pad2(d.getUTCSeconds()); }
function dmy(ts) { const d = new Date(Math.floor(ts) * 1000); return pad2(d.getUTCDate()) + pad2(d.getUTCMonth() + 1) + pad2(d.getUTCFullYear() % 100); }

export function formatGga(lat, lon, ts, { altitude = 0, fixQuality = 1, satellites = 8, hdop = 1.0, decimals = 4 } = {}) {
  const [la, ns] = formatCoord(lat, true, decimals), [lo, ew] = formatCoord(lon, false, decimals);
  return sentence(`GPGGA,${hms(ts)},${la},${ns},${lo},${ew},${Math.trunc(fixQuality)},${String(Math.trunc(satellites)).padStart(2, '0')},` +
    `${fixed(hdop, 1)},${fixed(altitude || 0, 1)},M,0.0,M,,`);
}

export function formatRmc(lat, lon, ts, { speedMs = 0, course = 0, decimals = 4 } = {}) {
  const [la, ns] = formatCoord(lat, true, decimals), [lo, ew] = formatCoord(lon, false, decimals);
  return sentence(`GPRMC,${hms(ts)},A,${la},${ns},${lo},${ew},${fixed((speedMs || 0) / KNOTS_TO_MS, 1)},${fixed(course || 0, 1)},${dmy(ts)},,`);
}

// --- parsing (mirrors what pynmea2 accepts) ------------------------------------------------------------------------
const SENTENCE_RE = /^\s*\$?((\w{2})(\w{3}),([^*]*))(?:\*([A-Fa-f0-9]{2}))?\s*$/;
class Skip extends Error {}

function dmToSd(dm) {
  if (!dm || dm === '0') return 0;
  const m = /^(\d+)(\d\d\.\d+)$/.exec(dm);
  if (!m) throw new Skip('bad coordinate');
  return Number(m[1]) + Number(m[2]) / 60;
}
const latOf = (v, dir) => (dir === 'N' ? dmToSd(v) : dir === 'S' ? -dmToSd(v) : 0);
const lonOf = (v, dir) => (dir === 'E' ? dmToSd(v) : dir === 'W' ? -dmToSd(v) : 0);
const num = v => (v === undefined || v === null || v.trim() === '' || !Number.isFinite(Number(v)) ? null : Number(v));
const int = v => (v !== undefined && /^\s*[+-]?\d+\s*$/.test(v) ? parseInt(v, 10) : null);

// 'hhmmss[.sss]' -> seconds of day; '' -> null; invalid -> Skip (pynmea2 returns the raw string, which then fails).
function secondsOfDay(s) {
  if (s === undefined || s === '') return null;
  const m = /^(\d\d)(\d\d)(\d\d)(.*)$/.exec(s);
  if (!m || +m[1] > 23 || +m[2] > 59 || +m[3] > 59) throw new Skip('bad time');
  let us = 0;
  if (m[4]) { const f = Number(m[4]); if (!Number.isFinite(f)) throw new Skip('bad time'); us = Math.trunc(f * 1e6); }
  return +m[1] * 3600 + +m[2] * 60 + +m[3] + us / 1e6;
}
// 'ddmmyy' -> UNIX seconds at 00:00 UTC; '' -> null; invalid -> Skip.
function dateEpoch(s) {
  if (s === undefined || s === '') return null;
  const m = /^(\d\d)(\d\d)(\d\d)$/.exec(s);
  if (!m) throw new Skip('bad date');
  const yy = +m[3], y = yy < 69 ? 2000 + yy : 1900 + yy, ms = Date.UTC(y, +m[2] - 1, +m[1]);
  const d = new Date(ms);
  if (d.getUTCDate() !== +m[1] || d.getUTCMonth() !== +m[2] - 1) throw new Skip('bad date');
  return ms / 1000;
}

export function parseNmeaLog(text) {
  const rmc = [], gga = [];
  let skipped = 0, sentences = 0;
  let q = { fix_quality: null, satellites: null, hdop: null, altitude: null };
  for (const raw of text.split(/\r\n|\r|\n/)) {
    const line = raw.trim();
    if (!line.startsWith('$')) continue;
    sentences++;
    try {
      const m = SENTENCE_RE.exec(line);
      if (!m) throw new Skip('no sentence');
      if (m[5] !== undefined && parseInt(m[5], 16) !== parseInt(checksum(m[1]), 16)) throw new Skip('checksum');
      const type = m[3].toUpperCase(), f = m[4].split(',');
      if (type === 'RMC') {
        if (f[1] !== 'A') continue;
        const sod = secondsOfDay(f[0]);
        const day = sod !== null ? dateEpoch(f[8]) : null;
        const lat = latOf(f[2], f[3]), lon = lonOf(f[4], f[5]);
        rmc.push({ t: sod !== null && day !== null ? day + sod : null, sod, lat, lon,
          speed: (num(f[6]) || 0) * KNOTS_TO_MS, course: num(f[7]), ...q });
      } else if (type === 'GGA') {
        q = { fix_quality: int(f[5]) || 0, satellites: int(f[6]), hdop: num(f[7]), altitude: num(f[8]) };
        const sod = secondsOfDay(f[0]);
        if (rmc.length && rmc[rmc.length - 1].sod === sod) Object.assign(rmc[rmc.length - 1], q);
        if (q.fix_quality > 0 && f[1]) gga.push({ t: sod, sod, lat: latOf(f[1], f[2]), lon: lonOf(f[3], f[4]), speed: null, course: null, ...q });
      }
    } catch (e) {
      if (!(e instanceof Skip)) throw e;
      skipped++;
    }
  }
  const points = rmc.length ? rmc : gga;
  if (!rmc.length) {
    let day = 0;
    points.forEach((p, i) => {
      if (i && p.t !== null && points[i - 1].t !== null && p.sod + day < points[i - 1].t) day += 86400;
      p.t = p.t === null ? null : p.sod + day;
    });
  }
  for (const p of points) {
    delete p.sod;
    p.accuracy = p.fix_quality !== null ? estimateGpsAccuracy(p.fix_quality, p.satellites, p.hdop) : null;
  }
  return { format: 'nmea', points, gpx_route: [], skipped, sentences, time_basis: rmc.length ? 'utc' : 'time of day' };
}

// --- GPX -----------------------------------------------------------------------------------------------------------
export function parseTime(s) {
  if (!s) return null;
  s = s.trim();
  const m = /^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d)(?::(\d\d)(\.\d+)?)?(Z|z|[+-]\d\d:?\d\d)?$/.exec(s);
  if (!m) return null;
  let t = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0)) / 1000 + (m[7] ? Number(m[7]) : 0);
  if (m[8] && !/^z$/i.test(m[8])) {
    const z = m[8].replace(':', ''), sign = z[0] === '-' ? -1 : 1;
    t -= sign * (+z.slice(1, 3) * 3600 + +z.slice(3, 5) * 60);
  }
  return t;
}

const attr = (attrs, name) => { const m = new RegExp(`\\b${name}\\s*=\\s*("([^"]*)"|'([^']*)')`).exec(attrs); return m ? (m[2] ?? m[3]) : null; };
const child = (body, name) => { const m = new RegExp(`<(?:\\w+:)?${name}\\b[^>]*>([^<]*)<`).exec(body || ''); return m ? m[1].trim() : null; };

export function parseGpx(text) {
  const clean = text.replace(/<!--[\s\S]*?-->/g, '');
  if (!/<(?:\w+:)?gpx\b/.test(clean)) throw new Error('not a GPX file (no <gpx> element)');
  const found = { trkpt: [], rtept: [], wpt: [] };
  const re = /<(?:\w+:)?(trkpt|rtept|wpt)\b([^>]*?)(\/>|>([\s\S]*?)<\/(?:\w+:)?\1\s*>)/g;
  let m;
  while ((m = re.exec(clean))) {
    const lat = attr(m[2], 'lat'), lon = attr(m[2], 'lon');
    if (lat === null || lon === null) continue;
    const body = m[4] || '';
    found[m[1]].push({ t: parseTime(child(body, 'time')), lat: Number(lat), lon: Number(lon), speed: num(child(body, 'speed') ?? ''),
      course: num(child(body, 'course') ?? ''), fix_quality: null, satellites: null, hdop: num(child(body, 'hdop') ?? ''),
      altitude: num(child(body, 'ele') ?? ''), accuracy: null });
  }
  const points = found.trkpt.length ? found.trkpt : found.rtept.length ? found.rtept : found.wpt;
  return { format: 'gpx', points, gpx_route: found.rtept.map(p => [p.lat, p.lon]), skipped: 0, sentences: 0, time_basis: 'utc' };
}

export function toGpx(points, name = 'PyNav Track', creator = 'PyNav') {
  const out = ['<?xml version="1.0" encoding="UTF-8"?>', `<gpx version="1.1" creator="${creator}" xmlns="http://www.topografix.com/GPX/1/1">`,
    '  <trk>', `    <name>${name.replace(/[<&>]/g, '')}</name>`, '    <trkseg>'];
  for (const p of points) {
    out.push(`      <trkpt lat="${fixed(p.lat, 7)}" lon="${fixed(p.lon, 7)}">`);
    if (p.altitude !== null && p.altitude !== undefined) out.push(`        <ele>${fixed(p.altitude, 1)}</ele>`);
    if (p.t !== null && p.t !== undefined) out.push(`        <time>${new Date(Math.floor(p.t) * 1000).toISOString().replace('.000Z', 'Z')}</time>`);
    out.push('      </trkpt>');
  }
  out.push('    </trkseg>', '  </trk>', '</gpx>', '');
  return out.join('\n');
}

// --- load + analyse (navmath/track.py) -----------------------------------------------------------------------------
export function loadLog(text, name = '') {
  const head = text.trimStart().slice(0, 200).toLowerCase();
  if (name.toLowerCase().endsWith('.gpx') || head.startsWith('<?xml') || head.includes('<gpx')) return parseGpx(text);
  return parseNmeaLog(text);
}

export function analyseLog(text, name = '', legs = 6) {
  const log = loadLog(text, name), pts = log.points;
  if (pts.length < 2) throw new Error('no track found: the file needs at least two GPX points or valid NMEA fixes');
  const fromGpx = log.gpx_route.length >= 2;
  const via = fromGpx ? log.gpx_route : waypointsFromTrack(pts.map(p => [p.lat, p.lon]), legs);
  return { name, ...log, stats: trackStats(pts), cumdist: cumulativeDistance(pts),
    route_source: fromGpx ? "the GPX file's route" : 'evenly spaced points of the track', route: offlineRoute(via) };
}
