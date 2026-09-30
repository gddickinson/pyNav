"""
Enhanced Map Manager - Modified to support local OSM data with offline-first tile loading
Priority: Local OSM tiles → Cached tiles → Online download (when enabled)
"""

import os
import time
import math
import requests
from typing import Dict, List, Tuple, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor

from navigation.core.map_manager import (TileServer, SimpleTileDownloader,
                                       MapLayer, TileLayer, POILayer)
from navigation.data.database import NavigationDatabase
from navigation.utils.logger import setup_logger
from local_tile_source import LocalTileSource
from vector_tile_renderer import VectorTileRenderer, VectorTileCache

logger = setup_logger(__name__)


class OfflineCapableMapManager(QObject):
    """Enhanced map manager with local OSM and offline capabilities."""

    tile_loaded = pyqtSignal(int, int, int, QPixmap, str)

    def __init__(self, database: NavigationDatabase):
        super().__init__()
        self.database = database
        self.layers = []
        self.current_server = 'OpenStreetMap'

        # Settings
        self.settings = QSettings('PyNav', 'NavigationApp')
        self.offline_mode = self.settings.value('offline_mode', False, type=bool)
        self.prefer_cached = self.settings.value('prefer_cached', True, type=bool)

        # Local OSM tile source (NEW!)
        local_enabled = self.settings.value('local_osm/enabled', False, type=bool)
        local_path = self.settings.value('local_osm/mbtiles_path', '', type=str)
        self.local_tile_source = LocalTileSource(enabled=local_enabled, mbtiles_path=local_path)
        self.local_tile_source.stats_updated.connect(self._on_local_stats_updated)

        # Tile caching
        self.tile_cache = {}  # In-memory cache
        self.cache_size_limit = 500  # Maximum tiles in memory

        # Enhanced tile downloader
        self.downloader = SimpleTileDownloader(database)
        self.downloader.tile_downloaded.connect(self.on_tile_downloaded)
        self.downloader.download_error.connect(self.on_download_error)

        # Add default tile layer
        self.add_layer(TileLayer("Base Map", self.current_server, self))

        # Vector tile rendering
        self.vector_renderer = VectorTileRenderer()
        self.vector_cache = VectorTileCache(max_size=100)

        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.download_attempts = 0
        self.local_tile_hits = 0

        logger.info("Enhanced map manager initialized with local OSM support")

        # Log local OSM status
        if self.local_tile_source.is_available():
            info = self.local_tile_source.get_info()
            logger.info(f"Local OSM tiles available: {info['tile_count']:,} tiles, "
                       f"zoom {info['min_zoom']}-{info['max_zoom']}")
        else:
            logger.info("Local OSM tiles not available - will use online/cached tiles")

    # ========== Local OSM Configuration ==========

    def set_local_osm_enabled(self, enabled: bool):
        """Enable or disable local OSM tile source."""
        self.local_tile_source.set_enabled(enabled)
        self.settings.setValue('local_osm/enabled', enabled)

        status = "enabled" if enabled else "disabled"
        logger.info(f"Local OSM tiles {status}")

    def set_local_osm_path(self, mbtiles_path: str) -> bool:
        """
        Set path to MBTiles database and initialize.

        Args:
            mbtiles_path: Path to .mbtiles file

        Returns:
            True if successfully initialized, False otherwise
        """
        self.local_tile_source.set_mbtiles_path(mbtiles_path)
        self.settings.setValue('local_osm/mbtiles_path', mbtiles_path)

        if self.local_tile_source.is_available():
            logger.info(f"Local OSM tiles loaded from: {mbtiles_path}")
            return True
        else:
            logger.warning(f"Failed to load local OSM tiles from: {mbtiles_path}")
            return False

    def is_local_osm_available(self) -> bool:
        """Check if local OSM tiles are available."""
        return self.local_tile_source.is_available()

    def get_local_osm_info(self) -> Dict:
        """Get information about local OSM tile source."""
        return self.local_tile_source.get_info()

    # ========== Core Tile Retrieval with Local OSM Priority ==========

    def get_tile(self, x: int, y: int, z: int, server: str) -> Optional[QPixmap]:
        """
        Get a map tile using priority: Local OSM → Memory cache → Disk cache → Download

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            z: Zoom level
            server: Tile server name

        Returns:
            QPixmap with tile image, or placeholder if unavailable
        """
        tile_key = f"{server}_{z}_{x}_{y}"

        # PRIORITY 1: Check local OSM tiles (if enabled and server is OSM-compatible)
        if self._should_use_local_osm(server):
            # Check if we have vector or raster tiles
            if (hasattr(self.local_tile_source, 'mbtiles_reader') and
                self.local_tile_source.mbtiles_reader and
                self.local_tile_source.mbtiles_reader.is_vector):
                # Vector tiles - get raw data and render them
                tile_data = self.local_tile_source.get_tile_data(z, x, y)
                if tile_data:
                    pixmap = self._render_vector_tile(tile_data, x, y, z)
                    if pixmap:
                        self._add_to_cache(tile_key, pixmap)
                        self.local_tile_hits += 1
                        self.cache_hits += 1
                        logger.debug(f"Rendered vector tile {x},{y},{z} from local OSM")
                        return pixmap
            else:
                # Raster tiles - use directly
                local_tile = self.local_tile_source.get_tile(z, x, y)
                if local_tile:
                    self._add_to_cache(tile_key, local_tile)
                    self.local_tile_hits += 1
                    self.cache_hits += 1
                    logger.debug(f"Loaded raster tile {x},{y},{z} from local OSM")
                    return local_tile

        # PRIORITY 2: Check memory cache
        if tile_key in self.tile_cache:
            self.cache_hits += 1
            return self.tile_cache[tile_key]

        # PRIORITY 3: Check database cache
        tile_data = self.database.get_cached_tile(x, y, z, server)
        if tile_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(tile_data):
                self._add_to_cache(tile_key, pixmap)
                self.cache_hits += 1
                logger.debug(f"Loaded tile {x},{y},{z} from disk cache")
                return pixmap

        # PRIORITY 4: If offline mode, return placeholder
        if self.offline_mode:
            logger.debug(f"Offline mode: returning placeholder for {x},{y},{z}")
            self.cache_misses += 1
            return self._create_offline_placeholder(x, y, z)

        # PRIORITY 5: Check if we should download
        if not self._should_download_tile(x, y, z, server):
            self.cache_misses += 1
            return self._create_placeholder_tile(x, y, z)

        # PRIORITY 6: Queue for download (non-blocking)
        self.downloader.add_download(x, y, z, server)
        self.download_attempts += 1
        self.cache_misses += 1

        # Return loading placeholder
        return self._create_loading_placeholder(x, y, z)

    def _should_use_local_osm(self, server: str) -> bool:
        """
        Determine if local OSM should be used for this server.

        Args:
            server: Tile server name

        Returns:
            True if local OSM should be checked for this server
        """
        # Local OSM tiles are typically compatible with OpenStreetMap-based servers
        osm_compatible_servers = ['OpenStreetMap', 'OpenTopoMap', 'CyclOSM']

        return (self.local_tile_source.is_available() and
                server in osm_compatible_servers)

    def _should_download_tile(self, x: int, y: int, z: int, server: str) -> bool:
        """Determine if we should download a tile based on current settings."""
        if not self.prefer_cached:
            return True

        if self._is_tile_in_offline_area(x, y, z, server):
            return True

        return True

    def _is_tile_in_offline_area(self, x: int, y: int, z: int, server: str) -> bool:
        """Check if a tile is part of any offline area."""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM offline_areas
                    WHERE server = ? AND min_zoom <= ? AND max_zoom >= ?
                """, (server, z, z))

                if cursor.fetchone()[0] == 0:
                    return False

                cursor = conn.execute("""
                    SELECT min_lat, min_lon, max_lat, max_lon FROM offline_areas
                    WHERE server = ? AND min_zoom <= ? AND max_zoom >= ?
                """, (server, z, z))

                tile_bounds = self.tile2deg(x, y, z)
                tile_lat = (tile_bounds[1] + tile_bounds[3]) / 2
                tile_lon = (tile_bounds[0] + tile_bounds[2]) / 2

                for row in cursor.fetchall():
                    if (row['min_lat'] <= tile_lat <= row['max_lat'] and
                        row['min_lon'] <= tile_lon <= row['max_lon']):
                        return True

                return False

        except Exception as e:
            logger.error(f"Error checking if tile is in offline area: {e}")
            return False

    # ========== Statistics and Info ==========

    def _on_local_stats_updated(self, stats: Dict):
        """Handle local tile source statistics updates."""
        logger.debug(f"Local OSM stats: {stats['local_hits']} hits, "
                    f"{stats['local_misses']} misses, "
                    f"hit ratio: {stats['hit_ratio']*100:.1f}%")

    def get_cache_statistics(self) -> Dict:
        """Get detailed cache statistics including local OSM."""
        try:
            db_stats = self.database.get_cache_stats()

            memory_stats = {
                'memory_tiles': len(self.tile_cache),
                'memory_limit': self.cache_size_limit,
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'hit_ratio': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
                'download_attempts': self.download_attempts,
                'local_tile_hits': self.local_tile_hits
            }

            # Add local OSM statistics
            local_osm_stats = {
                'enabled': self.local_tile_source.enabled,
                'available': self.local_tile_source.is_available(),
                'statistics': self.local_tile_source.get_statistics(),
                'info': self.local_tile_source.get_info() if self.local_tile_source.is_available() else {}
            }

            offline_stats = {}
            try:
                with self.database.get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT server, COUNT(*) as area_count,
                               SUM(CASE WHEN is_complete THEN 1 ELSE 0 END) as complete_areas,
                               AVG(download_progress) as avg_progress
                        FROM offline_areas GROUP BY server
                    """)

                    for row in cursor.fetchall():
                        offline_stats[row['server']] = {
                            'area_count': row['area_count'],
                            'complete_areas': row['complete_areas'],
                            'avg_progress': row['avg_progress'] or 0
                        }
            except Exception as e:
                logger.error(f"Error getting offline statistics: {e}")

            return {
                'database': db_stats,
                'memory': memory_stats,
                'local_osm': local_osm_stats,
                'offline_areas': offline_stats,
                'offline_mode': self.offline_mode,
                'prefer_cached': self.prefer_cached
            }

        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {}

    # ========== Placeholder Tile Creation ==========

    def _create_offline_placeholder(self, x: int, y: int, z: int) -> QPixmap:
        """Create placeholder for offline mode."""
        pixmap = QPixmap(256, 256)
        pixmap.fill(QColor(250, 250, 250))

        painter = QPainter(pixmap)
        painter.setPen(QColor(150, 150, 150))
        painter.drawRect(0, 0, 255, 255)

        painter.setPen(QColor(100, 100, 100))
        painter.drawText(10, 30, "OFFLINE")
        painter.drawText(10, 50, f"Tile {x},{y}")
        painter.drawText(10, 70, f"Zoom {z}")
        painter.drawText(10, 90, "Not in cache")

        painter.setPen(QColor(200, 100, 100))
        painter.drawEllipse(200, 10, 40, 40)
        painter.drawLine(210, 20, 230, 40)

        painter.end()
        return pixmap

    def _create_loading_placeholder(self, x: int, y: int, z: int) -> QPixmap:
        """Create placeholder for tiles being downloaded."""
        pixmap = QPixmap(256, 256)
        pixmap.fill(QColor(245, 245, 255))

        painter = QPainter(pixmap)
        painter.setPen(QColor(180, 180, 200))
        painter.drawRect(0, 0, 255, 255)

        painter.setPen(QColor(100, 100, 150))
        painter.drawText(10, 30, f"Tile {x},{y}")
        painter.drawText(10, 50, f"Zoom {z}")
        painter.drawText(10, 70, "Downloading...")

        painter.setPen(QColor(100, 150, 200))
        center_x, center_y = 220, 30
        for i in range(8):
            angle = i * 45
            start_x = center_x + 10 * math.cos(math.radians(angle))
            start_y = center_y + 10 * math.sin(math.radians(angle))
            end_x = center_x + 15 * math.cos(math.radians(angle))
            end_y = center_y + 15 * math.sin(math.radians(angle))

            alpha = 50 + (i * 25)
            painter.setPen(QColor(100, 150, 200, alpha))
            painter.drawLine(int(start_x), int(start_y), int(end_x), int(end_y))

        painter.end()
        return pixmap

    def _create_placeholder_tile(self, x: int, y: int, z: int) -> QPixmap:
        """Create placeholder tile while downloading."""
        pixmap = QPixmap(256, 256)
        pixmap.fill(QColor(245, 245, 245))

        painter = QPainter(pixmap)
        painter.setPen(QColor(200, 200, 200))
        painter.drawRect(0, 0, 255, 255)

        painter.setPen(QColor(150, 150, 150))
        painter.drawText(10, 30, f"Tile {x},{y}")
        painter.drawText(10, 50, f"Zoom {z}")
        painter.drawText(10, 70, "Loading...")
        painter.end()

        return pixmap

    # ========== Offline Mode Management ==========

    def set_offline_mode(self, offline: bool):
        """Set offline mode - when True, only use cached/local tiles."""
        self.offline_mode = offline
        self.settings.setValue('offline_mode', offline)

        if offline:
            logger.info("Switched to offline mode - using cached/local tiles only")
        else:
            logger.info("Switched to online mode - downloading tiles when needed")

    def set_prefer_cached(self, prefer: bool):
        """Set whether to prefer cached tiles over downloading fresh ones."""
        self.prefer_cached = prefer
        self.settings.setValue('prefer_cached', prefer)

    def is_offline_mode(self) -> bool:
        """Check if currently in offline mode."""
        return self.offline_mode

    # ========== Coverage and Preloading ==========

    def get_coverage_info(self, min_lat: float, min_lon: float,
                         max_lat: float, max_lon: float, zoom: int, server: str) -> Dict:
        """Get coverage information for a given area including local OSM coverage."""
        try:
            min_tile_x, max_tile_y = self.deg2tile(min_lat, min_lon, zoom)
            max_tile_x, min_tile_y = self.deg2tile(max_lat, max_lon, zoom)

            total_tiles = (max_tile_x - min_tile_x + 1) * (max_tile_y - min_tile_y + 1)
            cached_tiles = 0
            local_tiles = 0

            for x in range(min_tile_x, max_tile_x + 1):
                for y in range(min_tile_y, max_tile_y + 1):
                    # Check local OSM first
                    if self._should_use_local_osm(server):
                        local_tile = self.local_tile_source.get_tile(zoom, x, y)
                        if local_tile:
                            local_tiles += 1
                            cached_tiles += 1
                            continue

                    # Check database cache
                    if self.database.get_cached_tile(x, y, zoom, server):
                        cached_tiles += 1

            coverage_percent = (cached_tiles / total_tiles * 100) if total_tiles > 0 else 0

            return {
                'total_tiles': total_tiles,
                'cached_tiles': cached_tiles,
                'local_tiles': local_tiles,
                'coverage_percent': coverage_percent,
                'missing_tiles': total_tiles - cached_tiles
            }

        except Exception as e:
            logger.error(f"Error calculating coverage: {e}")
            return {
                'total_tiles': 0,
                'cached_tiles': 0,
                'local_tiles': 0,
                'coverage_percent': 0,
                'missing_tiles': 0
            }

    def preload_tiles_for_area(self, min_lat: float, min_lon: float,
                              max_lat: float, max_lon: float, zoom: int,
                              server: str = None, max_tiles: int = 100):
        """Preload tiles for a specific area (when online), skipping those in local OSM."""
        if self.offline_mode:
            logger.info("Cannot preload tiles in offline mode")
            return

        if server is None:
            server = self.current_server

        try:
            min_tile_x, max_tile_y = self.deg2tile(min_lat, min_lon, zoom)
            max_tile_x, min_tile_y = self.deg2tile(max_lat, max_lon, zoom)

            tiles_to_download = []

            for x in range(min_tile_x, max_tile_x + 1):
                for y in range(min_tile_y, max_tile_y + 1):
                    if 0 <= x < 2**zoom and 0 <= y < 2**zoom:
                        # Skip if in local OSM
                        if self._should_use_local_osm(server):
                            if self.local_tile_source.get_tile(zoom, x, y):
                                continue

                        # Check if already cached in database
                        if not self.database.get_cached_tile(x, y, zoom, server):
                            tiles_to_download.append((x, y, zoom))

                            if len(tiles_to_download) >= max_tiles:
                                break

                if len(tiles_to_download) >= max_tiles:
                    break

            for x, y, z in tiles_to_download:
                self.downloader.add_download(x, y, z, server)

            logger.info(f"Queued {len(tiles_to_download)} tiles for preloading "
                       f"(skipped tiles available in local OSM)")

        except Exception as e:
            logger.error(f"Error preloading tiles: {e}")

    # ========== Inherited/Standard Methods ==========

    def add_layer(self, layer: MapLayer):
        """Add a map layer."""
        self.layers.append(layer)
        logger.debug(f"Added layer: {layer.name}")

    def remove_layer(self, layer_name: str):
        """Remove a map layer."""
        self.layers = [layer for layer in self.layers if layer.name != layer_name]

    def get_layer(self, layer_name: str) -> Optional[MapLayer]:
        """Get layer by name."""
        for layer in self.layers:
            if layer.name == layer_name:
                return layer
        return None

    def set_layer_visibility(self, layer_name: str, visible: bool):
        """Set layer visibility."""
        layer = self.get_layer(layer_name)
        if layer:
            layer.visible = visible

    def set_layer_opacity(self, layer_name: str, opacity: float):
        """Set layer opacity (0.0 - 1.0)."""
        layer = self.get_layer(layer_name)
        if layer:
            layer.opacity = max(0.0, min(1.0, opacity))

    def set_map_type(self, server: str):
        """Change the base map tile server."""
        if server in TileServer.SERVERS:
            self.current_server = server
            base_layer = self.get_layer("Base Map")
            if isinstance(base_layer, TileLayer):
                base_layer.server = server
            logger.info(f"Map type changed to: {server}")

    def _add_to_cache(self, key: str, pixmap: QPixmap):
        """Add tile to memory cache with size limit."""
        if len(self.tile_cache) >= self.cache_size_limit:
            oldest_key = next(iter(self.tile_cache))
            del self.tile_cache[oldest_key]

        self.tile_cache[key] = pixmap

    def on_tile_downloaded(self, x: int, y: int, z: int, pixmap: QPixmap, server: str):
        """Handle successful tile download."""
        tile_key = f"{server}_{z}_{x}_{y}"
        self._add_to_cache(tile_key, pixmap)
        self.tile_loaded.emit(x, y, z, pixmap, server)

    def on_download_error(self, x: int, y: int, z: int, server: str, error: str):
        """Handle download errors."""
        logger.warning(f"Tile download error for {x},{y},{z} from {server}: {error}")

    def deg2tile(self, lat: float, lon: float, zoom: int) -> Tuple[int, int]:
        """Convert latitude/longitude to tile coordinates."""
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x, y)

    def tile2deg(self, x: int, y: int, zoom: int) -> Tuple[float, float, float, float]:
        """Convert tile coordinates to lat/lon bounds."""
        n = 2.0 ** zoom
        lon_deg = x / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_deg = math.degrees(lat_rad)

        next_lon_deg = (x + 1) / n * 360.0 - 180.0
        next_lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
        next_lat_deg = math.degrees(next_lat_rad)

        return (lon_deg, lat_deg, next_lon_deg, next_lat_deg)

    def world_to_screen(self, lat: float, lon: float, viewport_bounds: Tuple[float, float, float, float],
                       width: int, height: int) -> Tuple[float, float]:
        """Convert world coordinates to screen coordinates."""
        min_lon, min_lat, max_lon, max_lat = viewport_bounds
        x = (lon - min_lon) / (max_lon - min_lon) * width
        y = (max_lat - lat) / (max_lat - min_lat) * height
        return (x, y)

    def screen_to_world(self, x: float, y: float, viewport_bounds: Tuple[float, float, float, float],
                       width: int, height: int) -> Tuple[float, float]:
        """Convert screen coordinates to world coordinates."""
        min_lon, min_lat, max_lon, max_lat = viewport_bounds
        lon = min_lon + (x / width) * (max_lon - min_lon)
        lat = max_lat - (y / height) * (max_lat - min_lat)
        return (lat, lon)

    def calculate_tile_screen_size(self, zoom: int, viewport_bounds: Tuple[float, float, float, float],
                                  width: int, height: int) -> float:
        """Calculate how big tiles should be on screen."""
        n = 2.0 ** zoom
        tile_size_degrees = 360.0 / n
        min_lon, min_lat, max_lon, max_lat = viewport_bounds
        world_width = max_lon - min_lon
        pixels_per_degree = width / world_width
        return tile_size_degrees * pixels_per_degree

    def render_layers(self, painter, viewport_bounds: Tuple[float, float, float, float],
                     zoom: int, width: int, height: int):
        """Render all visible layers."""
        for layer in self.layers:
            if layer.visible:
                try:
                    layer.render(painter, viewport_bounds, zoom, width, height)
                except Exception as e:
                    logger.error(f"Error rendering layer {layer.name}: {e}")

    def preload_tiles(self, center_lat: float, center_lon: float, zoom: int, radius: int = 1):
        """Preload tiles around a center point, skipping local OSM tiles."""
        try:
            center_x, center_y = self.deg2tile(center_lat, center_lon, zoom)

            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    x, y = center_x + dx, center_y + dy
                    if 0 <= x < 2**zoom and 0 <= y < 2**zoom:
                        tile_key = f"{self.current_server}_{zoom}_{x}_{y}"
                        if tile_key not in self.tile_cache:
                            # Skip if in local OSM
                            if self._should_use_local_osm(self.current_server):
                                if self.local_tile_source.get_tile(zoom, x, y):
                                    continue

                            tile_data = self.database.get_cached_tile(x, y, zoom, self.current_server)
                            if not tile_data and not self.offline_mode:
                                self.downloader.add_download(x, y, zoom, self.current_server)
        except Exception as e:
            logger.error(f"Error preloading tiles: {e}")

    def clear_cache(self):
        """Clear tile cache."""
        self.tile_cache.clear()
        try:
            self.database.clear_tile_cache()
        except Exception as e:
            logger.error(f"Error clearing database cache: {e}")

    def export_cache_info(self, filename: str):
        """Export cache information to JSON file."""
        try:
            import json
            stats = self.get_cache_statistics()
            with open(filename, 'w') as f:
                json.dump(stats, f, indent=2, default=str)
            logger.info(f"Cache information exported to {filename}")
        except Exception as e:
            logger.error(f"Error exporting cache info: {e}")
            raise

    def cleanup(self):
        """Clean up resources."""
        try:
            self.downloader.stop()
            self.local_tile_source.cleanup()
            logger.info("Enhanced map manager cleaned up")
        except Exception as e:
            logger.error(f"Error during map manager cleanup: {e}")

    def _render_vector_tile(self, tile_data: bytes, x: int, y: int, z: int) -> Optional[QPixmap]:
        """Render a vector tile to a QPixmap."""
        try:
            # Create pixmap
            pixmap = QPixmap(256, 256)
            pixmap.fill(QColor(242, 239, 233))  # OSM background color

            # Create painter
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Render vector tile
            success = self.vector_renderer.render_tile(
                painter, tile_data, x, y, z,
                0, 0,  # Draw at origin
                256    # Tile size
            )

            painter.end()

            return pixmap if success else None

        except Exception as e:
            logger.error(f"Error rendering vector tile {z}/{x}/{y}: {e}")
            return None
