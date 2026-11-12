# pyNav -- Interface Map

## Project Structure

### Entry Point
- **main.py** -- PyQt6 application entry point; NavigationWindow class, safe import helpers

### navigation/ Package
- **navigation/__init__.py** -- Package initialization and re-exports

#### navigation/core/
- **location_manager.py** -- LocationManager: GPS position tracking, NMEA parsing
- **map_manager.py** -- MapManager: tile-based map rendering, zoom/pan logic
- **routing_engine.py** -- RoutingEngine, OSRMRoutingService, GraphHopperRoutingService: route calculation, turn-by-turn directions
- **geocoding_service.py** -- GeocodingService, GeocodingResult, POIResult: address search, reverse geocoding, POI lookup

#### navigation/gui/
- **map_widget.py** -- NavigationMapWidget: interactive map display (PyQt6)
- **route_panel.py** -- RoutePlanningPanel: route input and display UI
- **poi_manager.py** -- POIManager: POI management and display UI

#### navigation/data/
- **database.py** -- NavigationDatabase: SQLite storage for POIs, routes, settings

#### navigation/utils/
- **logger.py** -- setup_logger, create_crash_log: logging configuration
- **settings.py** -- NavigationSettings: app settings management

### Root-level Modules (offline mapping)
- **enhanced_map_manager.py** -- OfflineCapableMapManager: extends MapManager with offline tile support
- **offline_map_manager.py** -- OfflineMapManager: download and manage offline map regions
- **offline_maps_dialog.py** -- OfflineMapsDialog: UI for managing offline maps
- **local_tile_source.py** -- LocalTileSource: serve tiles from local MBTiles database
- **vector_tile_renderer.py** -- VectorTileRenderer, VectorTileCache: render vector tiles to QPixmap
- **local_osm_settings_dialog.py** -- LocalOSMSettingsDialog: settings UI for local OSM data
- **gps_tracker_dialog.py** -- GPSTrackerDialog: GPS device tracking UI

### navmath/ (Qt-free navigation maths; imported by the desktop app and the web app)
- **geo.py** -- haversine_m, initial_bearing_deg, bearing_to_direction, deg2tile, tile2deg, estimate_gps_accuracy
- **route.py** -- offline_steps, offline_route (used by OfflineRoutingService), route_progress, follow_route,
  remaining_distance (used by RoutingEngine.update_location), waypoints_from_track
- **nmea.py** -- checksum, format_coord, format_gga, format_rmc (used by macbook_server.py and the GPS dialog),
  parse_nmea_log (pynmea2), KNOTS_TO_MS (used by GPSProvider)
- **gpx.py** -- parse_gpx, to_gpx, parse_time
- **track.py** -- load_log, cumulative_distance, track_stats, analyse_log
- **ports.py** -- candidate_serial_ports (used by LocationManager._discover_gps_devices and the live dashboard)

### web/ (web interface; `python run_web.py`, port 8179)
- **app.py** -- FastAPI app: /api/info, /api/demo (STATIC_ENDPOINTS), POST /api/analyse, /api/live/* (local only)
- **live.py** -- SerialReader (background NMEA reader), LiveSources, fetch_iphone (macbook_server /current), sources
- **static/** -- index.html, core.js (router, shared kit), main.js, pages home.js / replay.js (+ replay_panels.js,
  charts.js, map_view.js) / tools.js / live.js / about.js, fmt.js, static_api.js (static-site api()),
  nav_engine.js + nmea_engine.js (JS port of navmath) with nav_engine.test.mjs, demo/synthetic_drive.nmea

### scripts/
- **make_demo_track.py** -- writes the synthetic demo drive (NMEA) with navmath.nmea
- **make_nav_fixture.py** -- writes tests/fixtures/nav_fixture.json (Python outputs the JS port must match)
- **build_static.py** -- exports the static GitHub Pages site to site/
- **screenshots.py** -- Playwright smoke test and README screenshots

### map_tools/
- **convert_pbf_mbtiles.py** -- PBF to MBTiles conversion utility

### iphoneTracking/
- **iphone_location_tracker.py** -- iPhone GPS tracking client
- **macbook_server.py** -- Server for receiving iPhone location data
- **sensor_transmitter.py** -- iPhone sensor data transmitter
- **sensor_testing_app_4.py** -- Sensor testing application

### Tests
- **tests/test_smoke.py** -- Smoke tests for routing, geocoding, and imports
- **tests/test_fixes.py** -- Regression tests for fixed bugs (GPS speed units, offline arrival step, NMEA checksums, GPX times)
- **tests/test_navmath.py** -- navmath tests, fixture/demo currency, desktop RoutingEngine == navmath route following
- **tests/test_web.py** -- web API, static build, node test of the JS port
- **tests/fixtures/** -- sample.nmea, sample_gga_only.nmea, sample.gpx (synthetic edge cases), nav_fixture.json

### Archived
- **_archive/** -- Old/backup files (main copy.py, enhanced_map_manager_OLD.py, etc.)
