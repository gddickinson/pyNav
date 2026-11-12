"""Regression tests for bugs fixed in the existing code (see SESSION_LOG.md, 2026-11-12)."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

pynmea2 = pytest.importorskip("pynmea2")

RMC = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A\r\n"


def test_serial_gps_speed_is_metres_per_second():
    """NMEA RMC speed is in knots; the app (map widget, GPS dialog) treats 'speed' as m/s."""
    from navigation.core.location_manager import GPSProvider
    gps = GPSProvider("/dev/null")
    gps.is_active = True
    gps.serial_connection = MagicMock()
    gps.serial_connection.readline.return_value = RMC.encode("ascii")
    loc = gps.get_location()
    assert loc["speed"] == pytest.approx(22.4 * 1852 / 3600)


def test_offline_route_arrives_at_the_destination():
    """The 'Arrive' instruction belongs at the destination, not at the start of the last leg."""
    from navigation.core.routing_engine import OfflineRoutingService
    r = OfflineRoutingService().calculate_route(51.5, -0.12, 51.52, -0.10, waypoints=[(51.51, -0.11)])
    steps = r["steps"]
    assert steps[-1].instruction == "Arrive at destination"
    assert (steps[-1].latitude, steps[-1].longitude) == (51.52, -0.10)
    assert steps[-1].distance_to_next == 0
    assert all(not s.instruction.startswith("Arrive") for s in steps[:-1])
    assert sum(s.distance_to_next for s in steps) == pytest.approx(r["distance"])


def test_macbook_server_nmea_checksum_is_valid(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "iphoneTracking"))
    import macbook_server
    monkeypatch.chdir(tmp_path)
    macbook_server.NavigationProcessor().write_nmea_format(
        {"timestamp": 1700000000, "latitude": -33.8568, "longitude": 151.2153, "altitude": 12.0})
    line = (tmp_path / "navigation_nmea.txt").read_text().strip()
    msg = pynmea2.parse(line, check=True)
    assert msg.latitude == pytest.approx(-33.8568, abs=1e-5)
    assert msg.longitude == pytest.approx(151.2153, abs=1e-5)


def test_gpx_track_export_time_is_utc(tmp_path):
    """GPX <time> ends in Z (UTC), so it must not be local time; points at longitude 0 are kept."""
    from gps_tracker_dialog import TrackingWidget
    ts = 1700000000.0
    fake = SimpleNamespace(track_points=[{"latitude": 51.4779, "longitude": 0.0, "timestamp": ts}])
    out = tmp_path / "t.gpx"
    TrackingWidget.export_to_gpx(fake, str(out))
    text = out.read_text()
    expected = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert f"<time>{expected}</time>" in text
    assert 'lon="0.0"' in text


@pytest.mark.parametrize("lat,lon", [(51.4779, -0.0015), (-33.8568, 151.2153), (40.0, -73.99999999)])
def test_generated_rmc_is_valid_nmea(lat, lon):
    """The GPS dialog's NMEA line used decimal degrees, always N/W and a fixed checksum."""
    from navmath.nmea import format_rmc
    msg = pynmea2.parse(format_rmc(lat, lon, 1700000000, speed_ms=10.0, course=270.0), check=True)
    assert msg.latitude == pytest.approx(lat, abs=1e-5) and msg.longitude == pytest.approx(lon, abs=1e-5)
    assert float(msg.spd_over_grnd) == pytest.approx(10.0 / (1852 / 3600), abs=0.05)
