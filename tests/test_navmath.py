"""Tests for navmath (the Qt-free navigation maths shared by the desktop app and the web interface)."""
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from navmath import geo, gpx, nmea, route, track  # noqa: E402

pytest.importorskip("pynmea2")


def _close(a, b, path=""):
    """Numbers to rtol 1e-9 (libm differs in the last digit between macOS and Linux); tuples == lists."""
    if isinstance(b, (int, float)) and not isinstance(b, bool) and isinstance(a, (int, float)):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), f"{path}: {a} != {b}"
    elif isinstance(b, (list, tuple)):
        assert isinstance(a, (list, tuple)) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _close(x, y, f"{path}[{i}]")
    elif isinstance(b, dict):
        assert isinstance(a, dict) and set(a) == set(b), f"{path}: keys {set(a) ^ set(b)}"
        for k in b:
            _close(a[k], b[k], f"{path}.{k}")
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


def test_fixture_is_current():
    import make_nav_fixture
    stored = json.loads(make_nav_fixture.OUT.read_text())
    _close(json.loads(json.dumps(make_nav_fixture.build())), stored)


def test_demo_log_is_current():
    import make_demo_track
    assert make_demo_track.OUT.read_text() == "\n".join(make_demo_track.simulate()) + "\n"


def test_known_distances_and_bearings():
    # equator to pole is a quarter great circle; due east along the equator is bearing 90
    assert geo.haversine_m(0, 0, 90, 0) == pytest.approx(math.pi / 2 * geo.EARTH_RADIUS_M)
    assert geo.initial_bearing_deg(0, 0, 0, 1) == pytest.approx(90)
    assert geo.bearing_to_direction(359) == "North" and geo.bearing_to_direction(200) == "South"
    assert geo.deg2tile(0, 0, 1) == (1, 1)


def test_sentences_round_trip_through_pynmea2():
    import pynmea2
    for lat, lon in [(51.4779, -0.0015), (-33.8568, 151.2153), (0.0, 0.0), (89.99999999, -179.99999999)]:
        for line in (nmea.format_gga(lat, lon, 1700000000), nmea.format_rmc(lat, lon, 1700000000, 3.0, 45.0)):
            msg = pynmea2.parse(line, check=True)
            assert msg.latitude == pytest.approx(lat, abs=1e-6) and msg.longitude == pytest.approx(lon, abs=1e-6)


def test_nmea_parser_edge_cases():
    r = nmea.parse_nmea_log((ROOT / "tests/fixtures/sample.nmea").read_text())
    assert r["skipped"] == 1  # the '*00' checksum line; status V, GSV and non-NMEA lines are ignored
    assert len(r["points"]) == 4 and r["time_basis"] == "utc"
    first = r["points"][0]
    assert first["speed"] == pytest.approx(22.4 * nmea.KNOTS_TO_MS)
    assert first["satellites"] == 8 and first["accuracy"] == pytest.approx(5.0 * 0.8 * 1.0)
    g = nmea.parse_nmea_log((ROOT / "tests/fixtures/sample_gga_only.nmea").read_text())
    assert [p["t"] for p in g["points"]] == [86398.0, 86399.0, 86400.0]  # across midnight, fix 0 dropped


def test_gpx_round_trip():
    pts = track.load_log((ROOT / "tests/fixtures/sample.gpx").read_text(), "x.gpx")["points"]
    back = gpx.parse_gpx(gpx.to_gpx(pts))["points"]
    assert [(round(p["lat"], 6), round(p["lon"], 6), p["t"] // 1) for p in back] == \
           [(round(p["lat"], 6), round(p["lon"], 6), p["t"] // 1) for p in pts]


def test_routing_engine_uses_the_same_route_following():
    """The desktop RoutingEngine (Qt) gives the same progress as navmath.route.follow_route."""
    pytest.importorskip("PyQt6")
    from navigation.core.routing_engine import OfflineRoutingService, RoutingEngine
    r = OfflineRoutingService().calculate_route(51.5, -0.12, 51.52, -0.13, waypoints=[(51.51, -0.11), (51.52, -0.10)])
    _close([{k: v for k, v in s.__dict__.items() if k != "street_name"} for s in r["steps"]], route.offline_route([(51.5, -0.12), (51.51, -0.11), (51.52, -0.10),
                                                                   (51.52, -0.13)])["steps"])
    eng = RoutingEngine.__new__(RoutingEngine)
    eng.current_route, eng.current_step_index, eng.is_navigating = r, 0, True
    updates = []
    eng.navigation_update = type("Sig", (), {"emit": staticmethod(updates.append)})()
    path = [(51.5, -0.12), (51.505, -0.115), (51.511, -0.109), (51.52, -0.101), (51.52, -0.12), (51.52, -0.13)]
    for lat, lon in path:
        eng.update_location({"latitude": lat, "longitude": lon})
    want = route.follow_route(r["steps"], path)
    for u, w in zip(updates, want):
        assert u["step_index"] == w["step_index"]
        assert u["distance_remaining"] == pytest.approx(w["distance_remaining"])
        assert u["time_remaining"] == pytest.approx(w["time_remaining"])
    assert updates[-1]["current_step"].instruction == "Arrive at destination"
