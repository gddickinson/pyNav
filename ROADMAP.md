# PyNav -- Roadmap

## Current State
A feature-rich PyQt6 GPS navigation app with interactive mapping, routing (OSRM, GraphHopper), geocoding, POI management, and GPS tracking. Well-organized under `navigation/` (core, gui, data, utils) but has accumulated cruft: `main copy.py`, `enhanced_map_manager_OLD.py`, `sensor_transmitter copy.py`, and an `iphoneTracking/` experimental directory with multiple iterations (`sensor_testing_app_4.py`). Core modules (`location_manager.py`, `map_manager.py`, `routing_engine.py`, `geocoding_service.py`) are solid. Has offline map support (`offline_map_manager.py`, `vector_tile_renderer.py`, `local_tile_source.py`) but these live at the project root instead of inside `navigation/`.

## Short-term Improvements
- [x] Delete `main copy.py` and `enhanced_map_manager_OLD.py` -- stale backup files (moved to _archive/)
- [x] Delete `sensor_transmitter copy.py` in `iphoneTracking/` (moved to _archive/)
- [ ] Move `offline_map_manager.py`, `vector_tile_renderer.py`, `local_tile_source.py`, `enhanced_map_manager.py` into `navigation/core/`
- [ ] Move `local_osm_settings_dialog.py` and `offline_maps_dialog.py` into `navigation/gui/`
- [ ] Move `gps_tracker_dialog.py` into `navigation/gui/`
- [x] Add unit tests for `routing_engine.py` route calculation and `geocoding_service.py` address parsing
- [x] Create `INTERFACE.md` for project navigation

## Feature Enhancements
- [ ] Add voice-guided navigation using pyttsx3 or system TTS (mentioned in README roadmap)
- [ ] Implement weather layer overlay using OpenWeatherMap API
- [ ] Add GPX track import/export in `navigation/data/database.py`
- [ ] Implement route elevation profile visualization
- [ ] Add dark mode theme for night navigation
- [ ] Build trip statistics dashboard (distance, time, average speed, elevation gain)
- [ ] Add multi-stop route optimization (traveling salesman approximation)

## Long-term Vision
- [ ] Implement real-time traffic data integration
- [ ] Add 3D terrain visualization using OpenGL or VTK
- [ ] Build mobile companion via Flask API serving to phone browser
- [ ] Plugin architecture for custom map layers and data sources
- [ ] Cloud sync for POIs, routes, and settings across devices
- [ ] Package as standalone app with PyInstaller for distribution

## Technical Debt
- [ ] `main.py` is likely very large -- split navigation window setup from app initialization
- [ ] `iphoneTracking/` has 5 experimental scripts with overlapping functionality -- consolidate into one clean module
- [x] `map tools/convert_pbf_mbtiles.py` uses a space in directory name -- rename to `map_tools/`
- [ ] Several root-level files should be inside the `navigation/` package (see Short-term above)
- [x] No `requirements.txt` version pins for PyQt6, requests, pynmea2, pyserial
- [x] Add `.gitignore` for cache directories (`~/.pynav/cache/`), `.db` files, `__pycache__`
- [x] Missing test infrastructure entirely -- add pytest with mocked API responses
