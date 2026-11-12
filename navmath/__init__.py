"""navmath: PyNav's navigation maths with no Qt, serial or network dependencies.

Shared by the desktop app (navigation/, gps_tracker_dialog.py, iphoneTracking/macbook_server.py) and the web
interface (web/), and ported to JavaScript in web/static/nav_engine.js and nmea_engine.js (node-tested against these
functions through tests/fixtures/nav_fixture.json).

Modules:
    nmea   NMEA 0183 checksum, coordinate formatting, GGA/RMC sentence writers
"""
