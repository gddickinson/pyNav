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

