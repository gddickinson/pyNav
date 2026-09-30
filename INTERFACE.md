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

### map_tools/
- **convert_pbf_mbtiles.py** -- PBF to MBTiles conversion utility

### iphoneTracking/
- **iphone_location_tracker.py** -- iPhone GPS tracking client
- **macbook_server.py** -- Server for receiving iPhone location data
- **sensor_transmitter.py** -- iPhone sensor data transmitter
- **sensor_testing_app_4.py** -- Sensor testing application

### Tests
- **tests/test_smoke.py** -- Smoke tests for routing, geocoding, and imports

### Archived
- **_archive/** -- Old/backup files (main copy.py, enhanced_map_manager_OLD.py, etc.)
