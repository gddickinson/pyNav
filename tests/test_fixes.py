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

