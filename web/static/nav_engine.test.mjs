// Node test: the JS port (nav_engine.js, nmea_engine.js) reproduces the Python navmath outputs stored in
// tests/fixtures/nav_fixture.json (regenerate with scripts/make_nav_fixture.py). Run: node web/static/nav_engine.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as nav from './nav_engine.js';
import * as nm from './nmea_engine.js';

const here = dirname(fileURLToPath(import.meta.url)), root = join(here, '..', '..');
const fx = JSON.parse(readFileSync(join(root, 'tests', 'fixtures', 'nav_fixture.json'), 'utf8'));
let checks = 0;

// Deep comparison: numbers to rtol 1e-9 (atol 1e-9), everything else exactly; tuples and arrays alike.
function close(a, b, path = '') {
  checks++;
  if (typeof b === 'number' && typeof a === 'number') {
    assert.ok(Math.abs(a - b) <= 1e-9 + 1e-9 * Math.abs(b), `${path}: ${a} != ${b}`);
  } else if (Array.isArray(b)) {
    assert.ok(Array.isArray(a), `${path}: not an array`);
    assert.equal(a.length, b.length, `${path}: length`);
    b.forEach((v, i) => close(a[i], v, `${path}[${i}]`));
  } else if (b && typeof b === 'object') {
    assert.ok(a && typeof a === 'object', `${path}: not an object`);
    assert.deepEqual(Object.keys(a).sort(), Object.keys(b).sort(), `${path}: keys`);
    for (const k of Object.keys(b)) close(a[k], b[k], `${path}.${k}`);
  } else {
    assert.equal(a, b, path);
  }
}

for (const c of fx.pairs) {
  close(nav.haversineM(...c.in), c.distance, `distance ${c.in}`);
  close(nav.initialBearingDeg(...c.in), c.bearing, `bearing ${c.in}`);
  close(nav.bearingToDirection(c.bearing), c.direction, `direction ${c.in}`);
}
for (const c of fx.accuracy) close(nav.estimateGpsAccuracy(...c.in), c.out, `accuracy ${c.in}`);
for (const c of fx.tiles) {
  const t = nav.deg2tile(...c.in);
  close(t, c.tile, `tile ${c.in}`);
  close(nav.tile2deg(...t, c.in[2]), c.bounds, `bounds ${c.in}`);
}
for (const c of fx.sentences) {
  const [lat, lon, ts, speed, course, alt] = c.in;
  close(nm.formatRmc(lat, lon, ts, { speedMs: speed, course }), c.rmc, `rmc ${c.in}`);
  close(nm.formatGga(lat, lon, ts, { altitude: alt, satellites: 7, hdop: course }), c.gga, `gga ${c.in}`);
  close(nm.formatGga(lat, lon, ts, { decimals: 3 }), c.gga3, `gga3 ${c.in}`);
}
close(nav.offlineRoute(fx.route.in), fx.route.out, 'offline route');

for (const [rel, want] of Object.entries(fx.logs)) {
  const text = readFileSync(join(root, rel), 'utf8'), name = rel.split('/').pop();
  const got = nm.analyseLog(text, name);
  const positions = got.points.map(p => [p.lat, p.lon]);
  got.progress = nav.followRoute(got.route.steps, positions);
  got.waypoints_3 = nav.waypointsFromTrack(positions, 3);
  got.gpx_out = nm.toGpx(got.points.slice(0, 5));
  close(got, want, rel);
}

// round trips: generated sentences parse back to the same fix
const back = nm.parseNmeaLog([nm.formatGga(51.4779, -0.0015, 1700000000), nm.formatRmc(51.4779, -0.0015, 1700000000, { speedMs: 5 })].join('\n'));
assert.equal(back.points.length, 1);
assert.ok(Math.abs(back.points[0].lat - 51.4779) < 1e-6 && Math.abs(back.points[0].lon + 0.0015) < 1e-6);
assert.equal(back.points[0].t, 1700000000);
assert.throws(() => nm.parseGpx('hello'), /not a GPX/);
console.log(`nav_engine: ${checks} checks against the Python fixture passed`);
