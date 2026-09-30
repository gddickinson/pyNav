"""
Map Manager - Handles map tiles, caching, and layer management
Supports multiple tile servers including satellite imagery
"""

import os
import time
import math
import requests
from typing import Dict, List, Tuple, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor

from navigation.data.database import NavigationDatabase
from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

class TileServer:
    """Configuration for map tile servers."""

    SERVERS = {
        'OpenStreetMap': {
            'url': 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            'max_zoom': 19,
            'attribution': '© OpenStreetMap contributors',
            'user_agent': 'PyNav/1.0'
        },
        'Satellite': {
            'url': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            'max_zoom': 19,
            'attribution': '© Esri, DigitalGlobe, GeoEye, Earthstar Geographics',
            'user_agent': 'PyNav/1.0'
        },
        'Hybrid': {
            'url_base': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            'url_overlay': 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
            'max_zoom': 19,
            'attribution': '© Esri, DigitalGlobe, GeoEye',
            'user_agent': 'PyNav/1.0'
        },
        'Terrain': {
            'url': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Physical_Map/MapServer/tile/{z}/{y}/{x}',
            'max_zoom': 8,
            'attribution': '© Esri, USGS, NOAA',
            'user_agent': 'PyNav/1.0'
        },
        'OpenTopoMap': {
            'url': 'https://tile.opentopomap.org/{z}/{x}/{y}.png',
            'max_zoom': 17,
            'attribution': '© OpenTopoMap (CC-BY-SA)',
            'user_agent': 'PyNav/1.0'
        },
        'CyclOSM': {
            'url': 'https://c.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png',
            'max_zoom': 19,
            'attribution': '© CyclOSM contributors',
            'user_agent': 'PyNav/1.0'
        }
    }

class SimpleTileDownloader(QObject):
    """Simple tile downloader without threading issues."""

    tile_downloaded = pyqtSignal(int, int, int, QPixmap, str)  # x, y, z, pixmap, server
    download_error = pyqtSignal(int, int, int, str, str)  # x, y, z, server, error

    def __init__(self, database):
        super().__init__()
        self.database = database
        self.download_queue = []
        self.is_downloading = False

        # Use QTimer instead of threading for safer operation
        self.download_timer = QTimer()
        self.download_timer.timeout.connect(self._process_queue)
        self.download_timer.setSingleShot(True)

    def add_download(self, x: int, y: int, z: int, server: str):
        """Add tile to download queue."""
        tile_key = (x, y, z, server)
        if tile_key not in self.download_queue:
            self.download_queue.append(tile_key)
            logger.debug(f"Added tile to download queue: {x},{y},{z} from {server}")

            # Start processing if not already running
            if not self.is_downloading and not self.download_timer.isActive():
                self.download_timer.start(100)  # Start after 100ms

    def _process_queue(self):
        """Process download queue one item at a time."""
        if not self.download_queue:
            self.is_downloading = False
            return

        self.is_downloading = True

        try:
            x, y, z, server = self.download_queue.pop(0)
            pixmap = self._download_tile(x, y, z, server)

            if pixmap:
                self.tile_downloaded.emit(x, y, z, pixmap, server)
                logger.debug(f"Downloaded tile: {x},{y},{z} from {server}")
            else:
                self.download_error.emit(x, y, z, server, "Download failed")
                logger.warning(f"Failed to download tile: {x},{y},{z} from {server}")

        except Exception as e:
            logger.error(f"Error processing download queue: {e}")

        # Continue processing queue
        if self.download_queue:
            self.download_timer.start(50)  # Process next item after 50ms
        else:
            self.is_downloading = False

    def _download_tile(self, x: int, y: int, z: int, server: str) -> Optional[QPixmap]:
        """Download a single tile."""
        if server not in TileServer.SERVERS:
            logger.warning(f"Unknown tile server: {server}")
            return None

        server_config = TileServer.SERVERS[server]

        try:
            # Handle hybrid maps (base + overlay)
            if server == 'Hybrid':
                base_url = server_config['url_base'].format(x=x, y=y, z=z)
                overlay_url = server_config['url_overlay'].format(x=x, y=y, z=z)
                return self._download_hybrid_tile(base_url, overlay_url, server_config)
            else:
                url = server_config['url'].format(x=x, y=y, z=z)
                return self._download_single_tile(url, server_config)

        except Exception as e:
            logger.error(f"Error downloading tile {x},{y},{z} from {server}: {e}")
            return None

    def _download_single_tile(self, url: str, config: Dict) -> Optional[QPixmap]:
        """Download a single tile from URL."""
        try:
            headers = {'User-Agent': config['user_agent']}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                pixmap = QPixmap()
                if pixmap.loadFromData(response.content):
                    return pixmap
                else:
                    logger.warning(f"Failed to load pixmap from tile data")
            else:
                logger.warning(f"HTTP {response.status_code} for tile URL: {url}")

        except requests.exceptions.Timeout:
            logger.debug(f"Timeout downloading tile: {url}")
        except requests.exceptions.RequestException as e:
            logger.debug(f"Request error downloading tile: {e}")
        except Exception as e:
            logger.error(f"Unexpected error downloading tile: {e}")

        return None

    def _download_hybrid_tile(self, base_url: str, overlay_url: str, config: Dict) -> Optional[QPixmap]:
        """Download and combine hybrid map tiles."""
        try:
            headers = {'User-Agent': config['user_agent']}

            # Download base satellite image
            base_response = requests.get(base_url, headers=headers, timeout=10)
            if base_response.status_code != 200:
                return None

            base_pixmap = QPixmap()
            if not base_pixmap.loadFromData(base_response.content):
                return None

            # Download overlay (roads, labels)
            overlay_response = requests.get(overlay_url, headers=headers, timeout=10)
            if overlay_response.status_code != 200:
                return base_pixmap  # Return just base if overlay fails

            overlay_pixmap = QPixmap()
            if not overlay_pixmap.loadFromData(overlay_response.content):
                return base_pixmap

            # Combine base and overlay
            combined = QPixmap(base_pixmap.size())
            painter = QPainter(combined)
            painter.drawPixmap(0, 0, base_pixmap)
            painter.drawPixmap(0, 0, overlay_pixmap)
            painter.end()

            return combined

        except Exception as e:
            logger.error(f"Error downloading hybrid tile: {e}")

        return None

    def stop(self):
        """Stop the downloader."""
        self.download_timer.stop()
        self.download_queue.clear()
        self.is_downloading = False
        logger.info("Tile downloader stopped")

class MapLayer:
    """Base class for map layers."""

    def __init__(self, name: str, visible: bool = True):
        self.name = name
        self.visible = visible
        self.opacity = 1.0

    def render(self, painter: QPainter, viewport_bounds: Tuple[float, float, float, float],
               zoom: int, width: int, height: int):
        """Render the layer. Override in subclasses."""
        pass

class TileLayer(MapLayer):
    """Map tile layer."""

    def __init__(self, name: str, server: str, map_manager):
        super().__init__(name)
        self.server = server
        self.map_manager = map_manager

    def render(self, painter: QPainter, viewport_bounds: Tuple[float, float, float, float],
               zoom: int, width: int, height: int):
        """Render map tiles."""
        if not self.visible:
            return

        min_lon, min_lat, max_lon, max_lat = viewport_bounds

        # Calculate tile bounds
        min_tile_x, max_tile_y = self.map_manager.deg2tile(min_lat, min_lon, zoom)
        max_tile_x, min_tile_y = self.map_manager.deg2tile(max_lat, max_lon, zoom)

        # Render tiles
        for tile_x in range(min_tile_x - 1, max_tile_x + 2):
            for tile_y in range(min_tile_y - 1, max_tile_y + 2):
                if tile_x < 0 or tile_y < 0 or tile_x >= 2**zoom or tile_y >= 2**zoom:
                    continue

                tile = self.map_manager.get_tile(tile_x, tile_y, zoom, self.server)
                if tile:
                    # Calculate tile position on screen
                    tile_bounds = self.map_manager.tile2deg(tile_x, tile_y, zoom)
                    screen_pos = self.map_manager.world_to_screen(
                        tile_bounds[1], tile_bounds[0], viewport_bounds, width, height
                    )

                    # Calculate tile size on screen
                    tile_size = self.map_manager.calculate_tile_screen_size(zoom, viewport_bounds, width, height)

                    # Draw tile
                    painter.setOpacity(self.opacity)
                    painter.drawPixmap(int(screen_pos[0]), int(screen_pos[1]),
                                     int(tile_size), int(tile_size), tile)

class POILayer(MapLayer):
    """Points of Interest layer."""

    def __init__(self, name: str, pois: List[Dict]):
        super().__init__(name)
        self.pois = pois

    def render(self, painter: QPainter, viewport_bounds: Tuple[float, float, float, float],
               zoom: int, width: int, height: int):
        """Render POI markers."""
        if not self.visible or zoom < 10:  # Don't show POIs at low zoom
            return

        min_lon, min_lat, max_lon, max_lat = viewport_bounds

        for poi in self.pois:
            lat, lon = poi['latitude'], poi['longitude']

            # Check if POI is in viewport
            if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                continue

            # Convert to screen coordinates
            screen_x = (lon - min_lon) / (max_lon - min_lon) * width
            screen_y = (max_lat - lat) / (max_lat - min_lat) * height

            # Draw POI marker
            painter.setOpacity(self.opacity)
            painter.setPen(QColor(255, 0, 0))
            painter.setBrush(QColor(255, 255, 0))
            painter.drawEllipse(int(screen_x - 5), int(screen_y - 5), 10, 10)

            # Draw label if zoom is high enough
            if zoom >= 14:
                painter.setPen(QColor(0, 0, 0))
                painter.drawText(int(screen_x + 8), int(screen_y + 4), poi.get('name', ''))

class MapManager(QObject):
    """Main map management class."""

    tile_loaded = pyqtSignal(int, int, int, QPixmap, str)

    def __init__(self, database: NavigationDatabase):
        super().__init__()
        self.database = database
        self.layers = []
        self.current_server = 'OpenStreetMap'

        # Tile caching
        self.tile_cache = {}  # In-memory cache
        self.cache_size_limit = 500  # Maximum tiles in memory

        # Simple tile downloader (no threading issues)
        self.downloader = SimpleTileDownloader(database)
        self.downloader.tile_downloaded.connect(self.on_tile_downloaded)
        self.downloader.download_error.connect(self.on_download_error)

        # Add default tile layer
        self.add_layer(TileLayer("Base Map", self.current_server, self))

        logger.info("Map manager initialized with simple downloader")

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

    def get_tile(self, x: int, y: int, z: int, server: str) -> Optional[QPixmap]:
        """Get a map tile from cache or download it."""
        tile_key = f"{server}_{z}_{x}_{y}"

        # Check memory cache first
        if tile_key in self.tile_cache:
            return self.tile_cache[tile_key]

        # Check database cache
        tile_data = self.database.get_cached_tile(x, y, z, server)
        if tile_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(tile_data):
                # Add to memory cache
                self._add_to_cache(tile_key, pixmap)
                return pixmap

        # Queue for download (non-blocking)
        self.downloader.add_download(x, y, z, server)

        # Return placeholder tile
        return self._create_placeholder_tile(x, y, z)

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

        # Cache to database
        try:
            pixmap_data = self._pixmap_to_bytes(pixmap)
            self.database.cache_tile(x, y, z, server, pixmap_data)
        except Exception as e:
            logger.error(f"Error caching tile to database: {e}")

        # Emit signal for map refresh
        self.tile_loaded.emit(x, y, z, pixmap, server)

    def on_download_error(self, x: int, y: int, z: int, server: str, error: str):
        """Handle download errors."""
        logger.warning(f"Tile download error for {x},{y},{z} from {server}: {error}")

    def _pixmap_to_bytes(self, pixmap: QPixmap) -> bytes:
        """Convert QPixmap to bytes for database storage."""
        from PyQt6.QtCore import QBuffer, QIODevice

        byte_array = bytearray()
        buffer = QBuffer()
        buffer.setData(byte_array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        return bytes(buffer.data())

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

    def render_layers(self, painter: QPainter, viewport_bounds: Tuple[float, float, float, float],
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
                            if not tile_data:
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
            logger.info("Map manager cleaned up")
        except Exception as e:
            logger.error(f"Error during map manager cleanup: {e}")
