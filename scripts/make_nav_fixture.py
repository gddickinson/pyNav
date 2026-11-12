"""Write tests/fixtures/nav_fixture.json: inputs and the Python (navmath) outputs that the JavaScript port
(web/static/nav_engine.js, nmea_engine.js) must reproduce. Checked by tests/test_navmath.py and the node test.

Run: python scripts/make_nav_fixture.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from navmath import geo, nmea, route, track  # noqa: E402
from navmath.gpx import to_gpx  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "nav_fixture.json"
LOGS = ["tests/fixtures/sample.nmea", "tests/fixtures/sample_gga_only.nmea", "tests/fixtures/sample.gpx",
        "web/static/demo/synthetic_drive.nmea"]
PAIRS = [(51.5007, -0.1246, 48.8584, 2.2945), (30.2747, -97.7404, 30.2669, -97.7729), (0, 0, 0, 0),
         (0, 179.5, 0, -179.5), (-33.8568, 151.2153, 40.6892, -74.0445), (89.9, 0, 89.9, 180), (10, 10, 10, 10.0001),
         (-45, -170, 45, 170), (52.2053, 0.1218, 52.2053, 0.1218001)]
ACC = [(fq, s, h) for fq in (0, 1, 2, 3, 4, None) for s in (0, 3, 4, 6, 8, 12, None) for h in (0, 1.5, 2, 4.9, 7, 15, 25, None)]
TILES = [(51.5, -0.12, 0), (51.5, -0.12, 10), (-33.86, 151.21, 15), (85.0, 179.99, 5), (0, 0, 1), (30.27, -97.74, 17)]
FIXES = [(51.4779, -0.0015, 1700000000, 10.0, 270.0, 12.5), (-33.8568, 151.2153, 1714557600, 0.0, 0.0, 0.0),
         (40.0, -73.99999999, 1600000000.7, 33.3, 359.95, -10.0), (0.0, 0.0, 0, 1.25, 0.25, 0.25)]
ROUTE_PTS = [[51.5, -0.12], [51.51, -0.11], [51.52, -0.10], [51.52, -0.13]]


def build():
    logs = {}
    for rel in LOGS:
        text = (ROOT / rel).read_text()
        r = track.analyse_log(text, Path(rel).name)
        positions = [(p["lat"], p["lon"]) for p in r["points"]]
        r["progress"] = route.follow_route(r["route"]["steps"], positions)
        r["waypoints_3"] = route.waypoints_from_track(positions, 3)
        r["gpx_out"] = to_gpx(r["points"][:5])
        logs[rel] = r
    return {
        "pairs": [{"in": p, "distance": geo.haversine_m(*p), "bearing": geo.initial_bearing_deg(*p),
                   "direction": geo.bearing_to_direction(geo.initial_bearing_deg(*p))} for p in PAIRS],
        "accuracy": [{"in": a, "out": geo.estimate_gps_accuracy(*a)} for a in ACC],
        "tiles": [{"in": t, "tile": geo.deg2tile(*t), "bounds": geo.tile2deg(*geo.deg2tile(*t), t[2])} for t in TILES],
        "sentences": [{"in": f, "rmc": nmea.format_rmc(f[0], f[1], f[2], speed_ms=f[3], course=f[4]),
                       "gga": nmea.format_gga(f[0], f[1], f[2], altitude=f[5], satellites=7, hdop=f[4]),
                       "gga3": nmea.format_gga(f[0], f[1], f[2], decimals=3)} for f in FIXES],
        "route": {"in": ROUTE_PTS, "out": route.offline_route(ROUTE_PTS)},
        "logs": logs,
    }


def main():
    OUT.write_text(json.dumps(build(), separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
