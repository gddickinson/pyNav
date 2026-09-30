"""
Enhanced Map Manager - Modified to support offline-first tile loading
Checks local cache first, then downloads online when available
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

logger = setup_logger(__name__)

class OfflineCapableMapManager(QObject):
    """Enhanced map manager with offline capabilities."""

    tile_loaded = pyqtSignal(int, int, int, QPixmap, str)

    def __init__(self, database: NavigationDatabase):
        super().__init__()
        self.database = database
        self.layers = []
        self.current_server = 'OpenStreetMap'
        
        # Offline mode settings
        self.settings = QSettings('PyNav', 'NavigationApp')
        self.offline_mode = self.settings.value('offline_mode', False, type=bool)
        self.prefer_cached = self.settings.value('prefer_cached', True, type=bool)
        
        # Tile caching
        self.tile_cache = {}  # In-memory cache
        self.cache_size_limit = 500  # Maximum tiles in memory
        
        # Enhanced tile downloader
        self.downloader = SimpleTileDownloader(database)
        self.downloader.tile_downloaded.connect(self.on_tile_downloaded)
        self.downloader.download_error.connect(self.on_download_error)
        
        # Add default tile layer
        self.add_layer(TileLayer("Base Map", self.current_server, self))
        
        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.download_attempts = 0
        
        logger.info("Enhanced map manager initialized with offline support")

    def set_offline_mode(self, offline: bool):
        """Set offline mode - when True, only use cached tiles."""
        self.offline_mode = offline
        self.settings.setValue('offline_mode', offline)
        
        if offline:
            logger.info("Switched to offline mode - using cached tiles only")
        else:
            logger.info("Switched to online mode - downloading tiles when needed")

    def set_prefer_cached(self, prefer: bool):
        """Set whether to prefer cached tiles over downloading fresh ones."""
        self.prefer_cached = prefer
        self.settings.setValue('prefer_cached', prefer)

    def is_offline_mode(self) -> bool:
        """Check if currently in offline mode."""
        return self.offline_mode

    def get_tile(self, x: int, y: int, z: int, server: str) -> Optional[QPixmap]:
        """Get a map tile using offline-first strategy."""
        tile_key = f"{server}_{z}_{x}_{y}"

        # 1. Check memory cache first (fastest)
        if tile_key in self.tile_cache:
            self.cache_hits += 1
            return self.tile_cache[tile_key]

        # 2. Check database cache (local disk)
        tile_data = self.database.get_cached_tile(x, y, z, server)
        if tile_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(tile_data):
                # Add to memory cache
                self._add_to_cache(tile_key, pixmap)
                self.cache_hits += 1
                logger.debug(f"Loaded tile {x},{y},{z} from disk cache")
                return pixmap

        # 3. If offline mode, return placeholder
        if self.offline_mode:
            logger.debug(f"Offline mode: returning placeholder for {x},{y},{z}")
            self.cache_misses += 1
            return self._create_offline_placeholder(x, y, z)

        # 4. If prefer cached and we're here, no cache exists
        # Check if we should download or return placeholder
        if not self._should_download_tile(x, y, z, server):
            self.cache_misses += 1
            return self._create_placeholder_tile(x, y, z)

        # 5. Queue for download (non-blocking)
        self.downloader.add_download(x, y, z, server)
        self.download_attempts += 1
        self.cache_misses += 1

        # 6. Return loading placeholder
        return self._create_loading_placeholder(x, y, z)

    def _should_download_tile(self, x: int, y: int, z: int, server: str) -> bool:
        """Determine if we should download a tile based on current settings."""
        # Always download if not in offline mode and not preferring cached
        if not self.prefer_cached:
            return True
        
        # Check if this tile is part of any offline area
        if self._is_tile_in_offline_area(x, y, z, server):
            # This tile should exist in cache, but doesn't
            # Download it to complete the offline area
            return True
        
        # For tiles not in offline areas, download if online
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
                
                # Check if tile coordinates fall within any area bounds
                cursor = conn.execute("""
                    SELECT min_lat, min_lon, max_lat, max_lon FROM offline_areas 
                    WHERE server = ? AND min_zoom <= ? AND max_zoom >= ?
                """, (server, z, z))
                
                # Convert tile to lat/lon
                tile_bounds = self.tile2deg(x, y, z)
                tile_lat = (tile_bounds[1] + tile_bounds[3]) / 2  # Average of S and N
                tile_lon = (tile_bounds[0] + tile_bounds[2]) / 2  # Average of W and E
                
                for row in cursor.fetchall():
                    if (row['min_lat'] <= tile_lat <= row['max_lat'] and
                        row['min_lon'] <= tile_lon <= row['max_lon']):
                        return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error checking if tile is in offline area: {e}")
            return False

    def _create_offline_placeholder(self, x: int, y: int, z: int) -> QPixmap:
        """Create placeholder for offline mode."""
        pixmap = QPixmap(256, 256)
        pixmap.fill(QColor(250, 250, 250))

        painter = QPainter(pixmap)
        painter.setPen(QColor(150, 150, 150))
        painter.drawRect(0, 0, 255, 255)

        # Offline indicator
        painter.setPen(QColor(100, 100, 100))
        painter.drawText(10, 30, "OFFLINE")
        painter.drawText(10, 50, f"Tile {x},{y}")
        painter.drawText(10, 70, f"Zoom {z}")
        painter.drawText(10, 90, "Not in cache")
        
        # Draw offline icon (simple)
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

        # Loading indicator
        painter.setPen(QColor(100, 100, 150))
        painter.drawText(10, 30, f"Tile {x},{y}")
        painter.drawText(10, 50, f"Zoom {z}")
        painter.drawText(10, 70, "Downloading...")
        
        # Draw loading spinner (simple)
        painter.setPen(QColor(100, 150, 200))
        center_x, center_y = 220, 30
        for i in range(8):
            angle = i * 45
            start_x = center_x + 10 * math.cos(math.radians(angle))
            start_y = center_y + 10 * math.sin(math.radians(angle))
            end_x = center_x + 15 * math.cos(math.radians(angle))
            end_y = center_y + 15 * math.sin(math.radians(angle))
            
            alpha = 50 + (i * 25)  # Varying alpha for spinner effect
            painter.setPen(QColor(100, 150, 200, alpha))
            painter.drawLine(int(start_x), int(start_y), int(end_x), int(end_y))
        
        painter.end()
        return pixmap

    def get_offline_areas_for_bounds(self, min_lat: float, min_lon: float,
                                   max_lat: float, max_lon: float, zoom: int) -> List[Dict]:
        """Get offline areas that intersect with given bounds."""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM offline_areas 
                    WHERE min_zoom <= ? AND max_zoom >= ?
                    AND NOT (max_lat < ? OR min_lat > ? OR max_lon < ? OR min_lon > ?)
                """, (zoom, zoom, min_lat, max_lat, min_lon, max_lon))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting offline areas: {e}")
            return []

    def get_coverage_info(self, min_lat: float, min_lon: float,
                         max_lat: float, max_lon: float, zoom: int, server: str) -> Dict:
        """Get coverage information for a given area."""
        try:
            # Calculate total tiles in area
            min_tile_x, max_tile_y = self.deg2tile(min_lat, min_lon, zoom)
            max_tile_x, min_tile_y = self.deg2tile(max_lat, max_lon, zoom)
            
            total_tiles = (max_tile_x - min_tile_x + 1) * (max_tile_y - min_tile_y + 1)
            cached_tiles = 0
            
            # Count cached tiles
            for x in range(min_tile_x, max_tile_x + 1):
                for y in range(min_tile_y, max_tile_y + 1):
                    if self.database.get_cached_tile(x, y, zoom, server):
                        cached_tiles += 1
            
            coverage_percent = (cached_tiles / total_tiles * 100) if total_tiles > 0 else 0
            
            return {
                'total_tiles': total_tiles,
                'cached_tiles': cached_tiles,
                'coverage_percent': coverage_percent,
                'missing_tiles': total_tiles - cached_tiles
            }
            
        except Exception as e:
            logger.error(f"Error calculating coverage: {e}")
            return {
                'total_tiles': 0,
                'cached_tiles': 0,
                'coverage_percent': 0,
                'missing_tiles': 0
            }

    def preload_tiles_for_area(self, min_lat: float, min_lon: float,
                              max_lat: float, max_lon: float, zoom: int,
                              server: str = None, max_tiles: int = 100):
        """Preload tiles for a specific area (when online)."""
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
                        # Check if tile is already cached
                        if not self.database.get_cached_tile(x, y, zoom, server):
                            tiles_to_download.append((x, y, zoom))
                            
                            if len(tiles_to_download) >= max_tiles:
                                break
                
                if len(tiles_to_download) >= max_tiles:
                    break
            
            # Queue tiles for download
            for x, y, z in tiles_to_download:
                self.downloader.add_download(x, y, z, server)
            
            logger.info(f"Queued {len(tiles_to_download)} tiles for preloading")
            
        except Exception as e:
            logger.error(f"Error preloading tiles: {e}")

    def get_cache_statistics(self) -> Dict:
        """Get detailed cache statistics."""
        try:
            # Database statistics
            db_stats = self.database.get_cache_stats()
            
            # Memory cache statistics
            memory_stats = {
                'memory_tiles': len(self.tile_cache),
                'memory_limit': self.cache_size_limit,
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'hit_ratio': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
                'download_attempts': self.download_attempts
            }
            
            # Offline areas statistics
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
                'offline_areas': offline_stats,
                'offline_mode': self.offline_mode,
                'prefer_cached': self.prefer_cached
            }
            
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {}

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

    # Inherited methods from original MapManager with enhancements
    
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
            # Update base layer
            base_layer = self.get_layer("Base Map")
            if isinstance(base_layer, TileLayer):
                base_layer.server = server
            logger.info(f"Map type changed to: {server}")

    def _add_to_cache(self, key: str, pixmap: QPixmap):
        """Add tile to memory cache with size limit."""
        if len(self.tile_cache) >= self.cache_size_limit:
            # Remove oldest tile (simple FIFO)
            oldest_key = next(iter(self.tile_cache))
            del self.tile_cache[oldest_key]

        self.tile_cache[key] = pixmap

    def _create_placeholder_tile(self, x: int, y: int, z: int) -> QPixmap:
        """Create placeholder tile while downloading."""
        pixmap = QPixmap(256, 256)
        pixmap.fill(QColor(245, 245, 245))

        painter = QPainter(pixmap)
        painter.setPen(QColor(200, 200, 200))
        painter.drawRect(0, 0, 255, 255)

        # Draw tile coordinates
        painter.setPen(QColor(150, 150, 150))
        painter.drawText(10, 30, f"Tile {x},{y}")
        painter.drawText(10, 50, f"Zoom {z}")
        painter.drawText(10, 70, "Loading...")
        painter.end()

        return pixmap

    def on_tile_downloaded(self, x: int, y: int, z: int, pixmap: QPixmap, server: str):
        """Handle successful tile download."""
        tile_key = f"{server}_{z}_{x}_{y}"

        # Add to memory cache
        self._add_to_cache(tile_key, pixmap)

        # Cache to database (already done by downloader)
        
        # Emit signal for map refresh
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

        # Calculate next tile bounds
        next_lon_deg = (x + 1) / n * 360.0 - 180.0
        next_lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
        next_lat_deg = math.degrees(next_lat_rad)

        return (lon_deg, lat_deg, next_lon_deg, next_lat_deg)  # W, S, E, N

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
        # Get tile size in degrees
        n = 2.0 ** zoom
        tile_size_degrees = 360.0 / n

        # Convert to screen pixels
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
        """Preload tiles around a center point."""
        try:
            center_x, center_y = self.deg2tile(center_lat, center_lon, zoom)

            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    x, y = center_x + dx, center_y + dy
                    if 0 <= x < 2**zoom and 0 <= y < 2**zoom:
                        # Check if tile is already cached
                        tile_key = f"{self.current_server}_{zoom}_{x}_{y}"
                        if tile_key not in self.tile_cache:
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

    def cleanup(self):
        """Clean up resources."""
        try:
            self.downloader.stop()
            logger.info("Enhanced map manager cleaned up")
        except Exception as e:
            logger.error(f"Error during map manager cleanup: {e}")
