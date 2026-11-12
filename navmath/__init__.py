"""navmath: PyNav's navigation maths with no Qt, serial or network dependencies.

Shared by the desktop app (navigation/, gps_tracker_dialog.py, iphoneTracking/macbook_server.py) and the web
interface (web/), and ported to JavaScript in web/static/nav_engine.js and nmea_engine.js (node-tested against these
functions through tests/fixtures/nav_fixture.json).

Modules:
    geo     haversine_m, initial_bearing_deg, bearing_to_direction, deg2tile/tile2deg, estimate_gps_accuracy
    route   offline_steps/offline_route (straight legs + 'Arrive'), route_progress/follow_route (RoutingEngine's
            route following), remaining_distance, waypoints_from_track
    nmea    checksum, format_coord, format_gga/format_rmc, parse_nmea_log (pynmea2), KNOTS_TO_MS
    gpx     parse_gpx, to_gpx, parse_time
    track   load_log (GPX or NMEA), cumulative_distance, track_stats, analyse_log
    ports   candidate_serial_ports (USB/serial GPS device paths per OS)
"""
