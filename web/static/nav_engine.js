// PyNav navigation maths in JavaScript: a line-by-line port of navmath/geo.py, navmath/route.py and navmath/track.py
// (haversine distance, bearing, compass direction, tiles, GPS accuracy estimate, straight-line routes, turn-by-turn
// route following, track statistics). Pure functions, no DOM: node-tested against the Python in nav_engine.test.mjs.

export const EARTH_RADIUS_M = 6371000;
export const DIRECTIONS_8 = ['North', 'Northeast', 'East', 'Southeast', 'South', 'Southwest', 'West', 'Northwest'];
export const OFFLINE_SPEED_KMH = 50;
const rad = d => d * Math.PI / 180, deg = r => r * 180 / Math.PI;

// Python's x % m for floats (result has the sign of m).
const pmod = (x, m) => ((x % m) + m) % m;

export function haversineM(lat1, lon1, lat2, lon2) {
  const p1 = rad(lat1), p2 = rad(lat2), dlat = rad(lat2 - lat1), dlon = rad(lon2 - lon1);
  const a = Math.sin(dlat / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dlon / 2) ** 2;
  return EARTH_RADIUS_M * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function initialBearingDeg(lat1, lon1, lat2, lon2) {
  const p1 = rad(lat1), p2 = rad(lat2), dlon = rad(lon2 - lon1);
  const y = Math.sin(dlon) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dlon);
  return pmod(deg(Math.atan2(y, x)) + 360, 360);
}

export const bearingToDirection = b => DIRECTIONS_8[pmod(Math.trunc((b + 22.5) / 45), 8)];

export function deg2tile(lat, lon, zoom) {
  const n = 2 ** zoom;
  return [Math.trunc((lon + 180) / 360 * n), Math.trunc((1 - Math.asinh(Math.tan(rad(lat))) / Math.PI) / 2 * n)];
}

export function tile2deg(x, y, zoom) {
  const n = 2 ** zoom, lat = yy => deg(Math.atan(Math.sinh(Math.PI * (1 - 2 * yy / n))));
  return [x / n * 360 - 180, lat(y), (x + 1) / n * 360 - 180, lat(y + 1)];
}

// Fractional tile coordinates (for drawing a track over map tiles).
export function lonLatToTileXY(lat, lon, zoom) {
  const n = 2 ** zoom;
  return [(lon + 180) / 360 * n, (1 - Math.asinh(Math.tan(rad(lat))) / Math.PI) / 2 * n];
}

export function estimateGpsAccuracy(fixQuality, satellites, hdop) {
  const fq = fixQuality || 0, sats = satellites || 0, h = hdop || 0;
  if (fq === 0) return 999;
  const base = fq === 1 ? 5.0 : fq === 2 ? 2.0 : fq >= 3 ? 1.0 : 10.0;
  const satM = sats >= 8 ? 0.8 : sats >= 6 ? 1.0 : sats >= 4 ? 1.5 : 3.0;
  let hM = 1.0;
  if (h > 0) hM = h < 2 ? 1.0 : h < 5 ? 1.2 : h < 10 ? 1.5 : h < 20 ? 2.0 : 3.0;
  return base * satM * hM;
}

// --- routes (navmath/route.py) ---------------------------------------------------------------------------------
export function offlineSteps(points) {
  const steps = [];
  for (let i = 0; i < points.length - 1; i++) {
    const [lat1, lon1] = points[i], [lat2, lon2] = points[i + 1];
    const bearing = initialBearingDeg(lat1, lon1, lat2, lon2);
    steps.push({ latitude: lat1, longitude: lon1, instruction: `${i === 0 ? 'Head' : 'Continue'} ${bearingToDirection(bearing)}`,
      distance_to_next: haversineM(lat1, lon1, lat2, lon2), bearing, turn_type: 'straight' });
  }
  const [lat, lon] = points[points.length - 1];
  steps.push({ latitude: lat, longitude: lon, instruction: 'Arrive at destination', distance_to_next: 0, bearing: 0, turn_type: 'arrive' });
  return steps;
}

export function offlineRoute(points, speedKmh = OFFLINE_SPEED_KMH) {
  const pts = points.map(([a, b]) => [Number(a), Number(b)]);
  if (pts.length < 2) throw new Error('a route needs at least two points');
  const steps = offlineSteps(pts);
  const distance = steps.reduce((s, x) => s + x.distance_to_next, 0);
  return { coordinates: pts, steps, distance, duration: distance / (speedKmh * 1000 / 3600),
    geometry: pts.map(([la, lo]) => [lo, la]), service: 'Offline' };
}

export function remainingDistance(steps, idx, lat, lon) {
  if (!steps.length) return 0;
  let total = 0;
  if (idx < steps.length) total += haversineM(lat, lon, steps[idx].latitude, steps[idx].longitude);
  for (let i = idx; i < steps.length - 1; i++) total += steps[i].distance_to_next;
  return total;
}

// One RoutingEngine.update_location step (see navmath/route.py route_progress).
export function routeProgress(steps, stepIndex, lat, lon, speedKmh = OFFLINE_SPEED_KMH) {
  let best = Infinity, closest = stepIndex;
  for (let i = Math.max(0, stepIndex - 1); i < Math.min(steps.length, stepIndex + 5); i++) {
    const d = haversineM(lat, lon, steps[i].latitude, steps[i].longitude);
    if (d < best) { best = d; closest = i; }
  }
  if (closest > stepIndex) stepIndex = closest;
  const cur = stepIndex < steps.length ? steps[stepIndex] : null;
  const toTurn = cur ? haversineM(lat, lon, cur.latitude, cur.longitude) : 0;
  const remaining = remainingDistance(steps, stepIndex, lat, lon);
  return { step_index: stepIndex, total_steps: steps.length, distance_to_turn: toTurn,
    distance_remaining: remaining, time_remaining: remaining / (speedKmh * 1000 / 3600) };
}

export function followRoute(steps, positions, speedKmh = OFFLINE_SPEED_KMH) {
  const out = [];
  let idx = 0;
  for (const [lat, lon] of positions) { const p = routeProgress(steps, idx, lat, lon, speedKmh); idx = p.step_index; out.push(p); }
  return out;
}

export function waypointsFromTrack(positions, legs = 6) {
  const n = positions.length;
  if (n < 2) throw new Error('need at least two positions');
  legs = Math.max(1, Math.min(Math.trunc(legs), n - 1));
  const idx = [...new Set(Array.from({ length: legs + 1 }, (_, k) => Math.trunc(k * (n - 1) / legs + 0.5)))].sort((a, b) => a - b);
  return idx.map(i => [positions[i][0], positions[i][1]]);
}

// --- tracks (navmath/track.py) ---------------------------------------------------------------------------------
export function cumulativeDistance(points) {
  if (!points.length) return [];
  const out = [0];
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    total += haversineM(points[i - 1].lat, points[i - 1].lon, points[i].lat, points[i].lon);
    out.push(total);
  }
  return out;
}

export function trackStats(points) {
  const n = points.length;
  if (!n) return { n: 0, distance_m: 0, duration_s: null, avg_speed_ms: null, max_speed_ms: null, min_alt: null, max_alt: null, bbox: null };
  const cd = cumulativeDistance(points), dist = cd[cd.length - 1];
  const has = k => points.map(p => p[k]).filter(v => v !== null && v !== undefined);
  const times = has('t'), speeds = has('speed'), alts = has('altitude');
  const duration = times.length >= 2 ? times[times.length - 1] - times[0] : null;
  const lats = points.map(p => p.lat), lons = points.map(p => p.lon);
  const mx = a => a.reduce((m, v) => (v > m ? v : m), -Infinity), mn = a => a.reduce((m, v) => (v < m ? v : m), Infinity);
  return { n, distance_m: dist, duration_s: duration, avg_speed_ms: duration ? dist / duration : null,
    max_speed_ms: speeds.length ? mx(speeds) : null, min_alt: alts.length ? mn(alts) : null, max_alt: alts.length ? mx(alts) : null,
    bbox: [mn(lats), mn(lons), mx(lats), mx(lons)] };
}

// Position at fractional index f along the points (linear between fixes), for smooth replay.
export function interpolate(points, f) {
  const i = Math.max(0, Math.min(points.length - 1, Math.floor(f))), j = Math.min(points.length - 1, i + 1), w = f - i;
  return { lat: points[i].lat + (points[j].lat - points[i].lat) * w, lon: points[i].lon + (points[j].lon - points[i].lon) * w };
}
