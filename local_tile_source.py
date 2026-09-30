"""
Local Tile Source Manager - Support for local OSM data sources
Handles MBTiles databases and other local tile formats as primary tile source
with fallback to online sources when tiles are unavailable
"""

import os
import sqlite3
import struct
from typing import Optional, Dict, Tuple
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)


class MBTilesReader:
    """Reader for MBTiles format SQLite databases."""

    SUPPORTED_FORMATS = ['png', 'jpg', 'jpeg', 'webp'] #add 'pbf' for vector files

    def __init__(self, mbtiles_path: str):
        """
        Initialize MBTiles reader.

        Args:
            mbtiles_path: Path to .mbtiles file
        """
        self.mbtiles_path = mbtiles_path
        self.connection = None
        self.metadata = {}
        self.is_vector = False

        if not os.path.exists(mbtiles_path):
            raise FileNotFoundError(f"MBTiles file not found: {mbtiles_path}")

        self._open_connection()
        self._load_metadata()

        # Check format
        self.is_vector = self.is_vector_format()

        logger.info(f"MBTiles format: {'vector' if self.is_vector else 'raster'} ({self.get_format()})")

        # VALIDATE FORMAT - ADD THIS
        tile_format = self.get_format()
        if tile_format not in self.SUPPORTED_FORMATS:
            self.close()
            raise ValueError(
                f"Unsupported tile format: '{tile_format}'. "
                f"PyNav only supports raster tiles ({', '.join(self.SUPPORTED_FORMATS)}). "
                f"This MBTiles file contains vector tiles which are not currently supported."
            )

    def _open_connection(self):
        """Open connection to MBTiles database."""
        try:
            self.connection = sqlite3.connect(self.mbtiles_path)
            self.connection.row_factory = sqlite3.Row
            logger.info(f"Opened MBTiles database: {self.mbtiles_path}")
        except Exception as e:
            logger.error(f"Error opening MBTiles database: {e}")
            raise

    def _load_metadata(self):
        """Load metadata from MBTiles database."""
        try:
            if not self.connection:
                return

            cursor = self.connection.execute("SELECT name, value FROM metadata")
            self.metadata = {row['name']: row['value'] for row in cursor.fetchall()}

            logger.info(f"MBTiles metadata: {self.metadata}")
        except Exception as e:
            logger.error(f"Error loading MBTiles metadata: {e}")

    def get_tile(self, z: int, x: int, y: int) -> Optional[bytes]:
            """
            Get raw tile data from MBTiles database.

            Args:
                z: Zoom level
                x: Tile X coordinate
                y: Tile Y coordinate

            Returns:
                Raw tile data as bytes, or None if not available
            """
            if not self.connection:
                return None

            try:
                # MBTiles uses TMS tile scheme - flip Y coordinate
                tms_y = (2 ** z - 1) - y

                cursor = self.connection.execute(
                    "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                    (z, x, tms_y)
                )

                row = cursor.fetchone()
                if row:
                    return row['tile_data']

            except Exception as e:
                logger.error(f"Error getting tile {z}/{x}/{y} from MBTiles: {e}")

            return None

    def get_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Get geographic bounds of the MBTiles dataset.

        Returns:
            Tuple of (min_lon, min_lat, max_lon, max_lat) or None
        """
        bounds_str = self.metadata.get('bounds')
        if bounds_str:
            try:
                bounds = [float(x) for x in bounds_str.split(',')]
                if len(bounds) == 4:
                    return tuple(bounds)
            except Exception as e:
                logger.error(f"Error parsing bounds: {e}")
        return None

    def get_center(self) -> Optional[Tuple[float, float, int]]:
        """
        Get center point and zoom of the MBTiles dataset.

        Returns:
            Tuple of (lon, lat, zoom) or None
        """
        center_str = self.metadata.get('center')
        if center_str:
            try:
                center = [float(x) for x in center_str.split(',')]
                if len(center) == 3:
                    return (center[0], center[1], int(center[2]))
            except Exception as e:
                logger.error(f"Error parsing center: {e}")
        return None

    def get_min_zoom(self) -> int:
        """Get minimum zoom level."""
        try:
            return int(self.metadata.get('minzoom', 0))
        except:
            return 0

    def get_max_zoom(self) -> int:
        """Get maximum zoom level."""
        try:
            return int(self.metadata.get('maxzoom', 18))
        except:
            return 18

    def get_tile_count(self) -> int:
        """Get total number of tiles in database."""
        try:
            if not self.connection:
                return 0

            cursor = self.connection.execute("SELECT COUNT(*) as count FROM tiles")
            row = cursor.fetchone()
            return row['count'] if row else 0
        except Exception as e:
            logger.error(f"Error counting tiles: {e}")
            return 0

    def get_format(self) -> str:
        """Get tile format (png, jpg, pbf, etc.)."""
        return self.metadata.get('format', 'png')

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info(f"Closed MBTiles database: {self.mbtiles_path}")

    def is_vector_format(self) -> bool:
        """Check if this MBTiles contains vector tiles."""
        format_str = self.get_format()
        return format_str in ['pbf', 'mvt']

class LocalTileSource(QObject):
    """
    Manager for local tile sources with fallback to online sources.
    Supports MBTiles and other local tile formats.
    """

    # Signals
    tile_loaded = pyqtSignal(int, int, int, QPixmap, str)  # z, x, y, pixmap, source
    stats_updated = pyqtSignal(dict)  # Statistics update
    source_changed = pyqtSignal(bool)  # Availability changed

    def __init__(self, enabled: bool = False, mbtiles_path: str = None):
        super().__init__()

        self.enabled = enabled
        self.mbtiles_path = mbtiles_path
        self.mbtiles_reader = None

        # Statistics
        self.stats = {
            'local_hits': 0,
            'local_misses': 0,
            'total_requests': 0,
            'hit_ratio': 0.0
        }

        # Try to initialize if enabled and path provided
        if self.enabled and self.mbtiles_path:
            success = self.initialize()
            self.source_changed.emit(success)

    def initialize(self) -> bool:
        """
        Initialize the local tile source.

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.mbtiles_path:
                logger.warning("No MBTiles path specified")
                return False

            # Expand user home directory if needed
            expanded_path = os.path.expanduser(self.mbtiles_path)

            if not os.path.exists(expanded_path):
                logger.warning(f"MBTiles file not found: {expanded_path}")
                return False

            # Close existing reader if any
            if self.mbtiles_reader:
                self.mbtiles_reader.close()

            # Open new reader
            self.mbtiles_reader = MBTilesReader(expanded_path)

            # Log information
            bounds = self.mbtiles_reader.get_bounds()
            tile_count = self.mbtiles_reader.get_tile_count()
            zoom_range = f"{self.mbtiles_reader.get_min_zoom()}-{self.mbtiles_reader.get_max_zoom()}"
            tile_type = "vector" if self.mbtiles_reader.is_vector else "raster"

            logger.info(f"Initialized local tile source:")
            logger.info(f"  Path: {expanded_path}")
            logger.info(f"  Type: {tile_type}")
            logger.info(f"  Tiles: {tile_count:,}")
            logger.info(f"  Zoom range: {zoom_range}")
            logger.info(f"  Bounds: {bounds}")

            return True

        except Exception as e:
            logger.error(f"Error initializing local tile source: {e}")
            self.mbtiles_reader = None
            return False

    def set_enabled(self, enabled: bool):
        """Enable or disable local tile source."""
        self.enabled = enabled
        logger.info(f"Local tile source {'enabled' if enabled else 'disabled'}")

    def set_mbtiles_path(self, path: str):
        """Set MBTiles database path and reinitialize."""
        self.mbtiles_path = path
        if self.enabled:
            self.initialize()

    def get_tile_data(self, z: int, x: int, y: int) -> Optional[bytes]:
        """
        Get raw tile data from local source (for vector tiles).

        Args:
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate

        Returns:
            Raw tile data as bytes, or None if not available
        """
        if not self.enabled or not self.mbtiles_reader:
            return None

        try:
            return self.mbtiles_reader.get_tile(z, x, y)
        except Exception as e:
            logger.error(f"Error getting tile data {z}/{x}/{y}: {e}")
            return None

    def get_tile(self, z: int, x: int, y: int) -> Optional[QPixmap]:
        """
        Get tile from local source as QPixmap (for raster tiles only).

        Args:
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate

        Returns:
            QPixmap with tile image, or None if not available locally
        """
        self.stats['total_requests'] += 1

        if not self.enabled or not self.mbtiles_reader:
            self.stats['local_misses'] += 1
            self._update_stats()
            return None

        # Vector tiles should NOT be loaded here as pixmaps
        # They need special rendering - return None
        if self.mbtiles_reader.is_vector:
            self.stats['local_misses'] += 1
            self._update_stats()
            return None

        try:
            # Get tile data from MBTiles (raster tiles only)
            tile_data = self.mbtiles_reader.get_tile(z, x, y)

            if tile_data:
                # Convert to QPixmap
                pixmap = QPixmap()
                if pixmap.loadFromData(tile_data):
                    self.stats['local_hits'] += 1
                    self._update_stats()
                    logger.debug(f"Loaded local raster tile: {z}/{x}/{y}")
                    return pixmap
                else:
                    logger.warning(f"Failed to load tile data as pixmap: {z}/{x}/{y}")

            self.stats['local_misses'] += 1
            self._update_stats()

        except Exception as e:
            logger.error(f"Error getting local tile {z}/{x}/{y}: {e}")
            self.stats['local_misses'] += 1
            self._update_stats()

        return None

    def is_available(self) -> bool:
        """Check if local tile source is available."""
        return self.enabled and self.mbtiles_reader is not None

    def get_info(self) -> Dict:
        """Get information about the local tile source."""
        if not self.mbtiles_reader:
            return {
                'enabled': self.enabled,
                'available': False,
                'path': self.mbtiles_path
            }

        info = {
            'enabled': self.enabled,
            'available': True,
            'path': self.mbtiles_path,
            'format': self.mbtiles_reader.get_format(),
            'is_vector': self.mbtiles_reader.is_vector,
            'bounds': self.mbtiles_reader.get_bounds(),
            'center': self.mbtiles_reader.get_center(),
            'min_zoom': self.mbtiles_reader.get_min_zoom(),
            'max_zoom': self.mbtiles_reader.get_max_zoom(),
            'tile_count': self.mbtiles_reader.get_tile_count(),
            'metadata': self.mbtiles_reader.metadata
        }

        # Add friendly type description
        if info['is_vector']:
            info['type_description'] = 'Vector tiles (rendered on-the-fly)'
        else:
            info['type_description'] = 'Raster tiles (pre-rendered images)'

        return info

    def get_statistics(self) -> Dict:
        """Get usage statistics."""
        return self.stats.copy()

    def _update_stats(self):
        """Update statistics and emit signal."""
        if self.stats['total_requests'] > 0:
            self.stats['hit_ratio'] = (
                self.stats['local_hits'] / self.stats['total_requests']
            )
        self.stats_updated.emit(self.stats.copy())

    def reset_statistics(self):
        """Reset usage statistics."""
        self.stats = {
            'local_hits': 0,
            'local_misses': 0,
            'total_requests': 0,
            'hit_ratio': 0.0
        }
        self._update_stats()

    def cleanup(self):
        """Clean up resources."""
        if self.mbtiles_reader:
            self.mbtiles_reader.close()
            self.mbtiles_reader = None
        logger.info("Local tile source cleaned up")
