# Session log

## 2026-11-12 -- web interface and static site (branch `web-interface`)
- Added `web/` (FastAPI on port 8179 + plain ES-module front end) and a GitHub Pages static site: Replay (GPX/NMEA
  log replay with route following), Nav maths (calculators), Live GPS (local only: serial NMEA reader, iPhone server),
  About.
- Factored the navigation maths into `navmath/` (Qt-free); the desktop modules now call it (six copies of the
  haversine formula removed). JS port in `web/static/nav_engine.js` + `nmea_engine.js`, node-tested against
  `tests/fixtures/nav_fixture.json` (made by `scripts/make_nav_fixture.py`).
- Demo data is synthetic (`scripts/make_demo_track.py`); no real GPS logs are committed or published.
- Bugs fixed (each in its own commit, regression tests in `tests/test_fixes.py`):
  - Serial GPS speed: RMC knots were stored as m/s, so displayed speeds were about 1.94x too high.
  - Offline router put "Arrive at destination" at the start of the last leg; it now has a final arrive step.
  - Generated NMEA: macbook_server wrote GGA with a fixed `*00` checksum; the GPS dialog's NMEA line had decimal
    degrees, hemispheres always N/W and a fixed checksum. Both now use navmath.nmea.
  - GPX track export wrote local time with a `Z` (UTC) suffix and dropped points at latitude/longitude 0.
- Tests: `pytest tests` all pass; `node web/static/nav_engine.test.mjs` passes; screenshots.py static and live OK.
