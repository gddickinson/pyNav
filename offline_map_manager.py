"""
Offline Map Manager - Handles bulk downloading and management of offline map areas
Supports downloading map tiles for specified regions and zoom levels
"""

import math
import time
import hashlib
import requests
from typing import Dict, List, Tuple, Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import QMessageBox

from navigation.core.map_manager import TileServer
from navigation.data.database import NavigationDatabase
from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

class OfflineArea:
    """Represents an offline map area."""

    def __init__(self, name: str, min_lat: float, min_lon: float,
                 max_lat: float, max_lon: float, min_zoom: int, max_zoom: int,
                 server: str = "OpenStreetMap"):
        self.name = name
        self.min_lat = min_lat
        self.min_lon = min_lon
        self.max_lat = max_lat
        self.max_lon = max_lon
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.server = server

    def calculate_tile_count(self) -> int:
        """Calculate total number of tiles for this area."""
        total_tiles = 0

        for zoom in range(self.min_zoom, self.max_zoom + 1):
            # Calculate tile bounds for this zoom level
            min_tile_x, max_tile_y = self._deg2tile(self.min_lat, self.min_lon, zoom)
            max_tile_x, min_tile_y = self._deg2tile(self.max_lat, self.max_lon, zoom)

            # Count tiles in this zoom level
            tiles_x = max_tile_x - min_tile_x + 1
            tiles_y = max_tile_y - min_tile_y + 1
            total_tiles += tiles_x * tiles_y

        return total_tiles

    def estimate_size_mb(self) -> float:
        """Estimate download size in MB (assumes ~20KB per tile average)."""
        tile_count = self.calculate_tile_count()
        return (tile_count * 20) / 1024  # Convert KB to MB

    def _deg2tile(self, lat: float, lon: float, zoom: int) -> Tuple[int, int]:
        """Convert latitude/longitude to tile coordinates."""
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x, y)

    def get_tile_list(self) -> List[Tuple[int, int, int]]:
        """Get list of all tiles (x, y, z) for this area."""
        tiles = []

        for zoom in range(self.min_zoom, self.max_zoom + 1):
            min_tile_x, max_tile_y = self._deg2tile(self.min_lat, self.min_lon, zoom)
            max_tile_x, min_tile_y = self._deg2tile(self.max_lat, self.max_lon, zoom)

            for x in range(min_tile_x, max_tile_x + 1):
                for y in range(min_tile_y, max_tile_y + 1):
                    if 0 <= x < 2**zoom and 0 <= y < 2**zoom:
                        tiles.append((x, y, zoom))

        return tiles

class OfflineDownloadThread(QThread):
    """Enhanced download thread with hang prevention."""

    progress_updated = pyqtSignal(int, int, str)
    tile_downloaded = pyqtSignal(int, int, int)
    download_completed = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, area, database):
        super().__init__()
        self.area = area
        self.database = database
        self.is_cancelled = False
        self.is_paused = False
        self.download_delay = 0.1

        # Enhanced error handling
        self.max_retries = 3
        self.timeout = 10  # Reduced from 30 seconds
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10

    def run(self):
        """Download tiles with improved error handling."""
        try:
            tiles = self.area.get_tile_list()
            total_tiles = len(tiles)
            downloaded = 0
            errors = 0

            logger.info(f"Starting download of {total_tiles} tiles")

            server_config = TileServer.SERVERS.get(self.area.server)
            if not server_config:
                self.error_occurred.emit(f"Unknown server: {self.area.server}")
                return

            # Progress update throttling
            last_progress_update = 0
            progress_update_interval = 1.0  # Update UI every 1 second max

            for i, (x, y, z) in enumerate(tiles):
                if self.is_cancelled:
                    break

                # Handle pausing
                while self.is_paused and not self.is_cancelled:
                    self.msleep(100)

                if self.is_cancelled:
                    break

                # Check if tile exists (with timeout protection)
                try:
                    existing_tile = self.database.get_cached_tile(x, y, z, self.area.server)
                    if existing_tile:
                        downloaded += 1
                        # Throttled progress update
                        current_time = time.time()
                        if current_time - last_progress_update >= progress_update_interval:
                            self.progress_updated.emit(downloaded, total_tiles, "Checking existing tiles...")
                            last_progress_update = current_time
                        continue
                except Exception as e:
                    logger.warning(f"Database check failed for tile {x},{y},{z}: {e}")

                # Download with retry logic
                success = False
                for retry in range(self.max_retries):
                    if self.is_cancelled:
                        break

                    try:
                        tile_data = self._download_tile_with_timeout(x, y, z, server_config)
                        if tile_data:
                            # Cache tile (with error handling)
                            try:
                                self.database.cache_tile(x, y, z, self.area.server, tile_data)
                                downloaded += 1
                                self.tile_downloaded.emit(x, y, z)
                                self.consecutive_failures = 0
                                success = True
                                break
                            except Exception as e:
                                logger.error(f"Failed to cache tile {x},{y},{z}: {e}")
                                errors += 1

                    except Exception as e:
                        logger.warning(f"Download attempt {retry + 1} failed for tile {x},{y},{z}: {e}")
                        if retry < self.max_retries - 1:
                            self.msleep(1000)  # Wait 1 second before retry

                if not success:
                    errors += 1
                    self.consecutive_failures += 1

                    # Stop if too many consecutive failures (prevents infinite hanging)
                    if self.consecutive_failures >= self.max_consecutive_failures:
                        error_msg = f"Too many consecutive failures ({self.consecutive_failures}). Stopping download."
                        self.error_occurred.emit(error_msg)
                        break

                # Throttled progress update
                current_time = time.time()
                if current_time - last_progress_update >= progress_update_interval:
                    status = f"Downloaded {downloaded}/{total_tiles} tiles (errors: {errors})"
                    self.progress_updated.emit(downloaded, total_tiles, status)
                    last_progress_update = current_time

                # Respectful delay (but allow cancellation)
                if self.download_delay > 0:
                    self.msleep(int(self.download_delay * 1000))

            # Final update
            if not self.is_cancelled:
                self._update_area_status(downloaded, total_tiles)

            success = not self.is_cancelled and errors < total_tiles * 0.5  # Allow 50% error rate
            message = f"Downloaded {downloaded}/{total_tiles} tiles"
            if errors > 0:
                message += f" ({errors} errors)"

            self.download_completed.emit(success, message)

        except Exception as e:
            logger.error(f"Download thread critical error: {e}")
            self.error_occurred.emit(f"Critical download error: {str(e)}")

    def _download_tile_with_timeout(self, x: int, y: int, z: int, server_config: dict) -> bytes:
        """Download single tile with timeout protection."""
        try:
            url = server_config['url'].format(x=x, y=y, z=z)
            headers = {'User-Agent': server_config.get('user_agent', 'PyNav/1.0')}

            # Use session for connection reuse
            if not hasattr(self, '_session'):
                self._session = requests.Session()
                self._session.headers.update(headers)

            response = self._session.get(url, timeout=self.timeout, stream=True)
            response.raise_for_status()

            # Read content in chunks to avoid memory issues
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                if self.is_cancelled:
                    raise Exception("Download cancelled")
                content += chunk

            return content

        except requests.exceptions.Timeout:
            raise Exception(f"Timeout downloading tile {x},{y},{z}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error downloading tile {x},{y},{z}: {e}")
        except Exception as e:
            raise Exception(f"Error downloading tile {x},{y},{z}: {e}")

    def _update_area_status(self, downloaded: int, total: int):
        """Update area status with error protection."""
        try:
            progress = downloaded / total if total > 0 else 0
            is_complete = progress >= 0.95

            with self.database.get_connection() as conn:
                conn.execute("""
                    UPDATE offline_areas
                    SET download_progress = ?, is_complete = ?,
                        completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE name = ? AND server = ?
                """, (progress, is_complete, is_complete, self.area.name, self.area.server))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating area status: {e}")

    def cancel(self):
        """Cancel download and cleanup."""
        self.is_cancelled = True
        if hasattr(self, '_session'):
            self._session.close()

    def cleanup(self):
        """Cleanup resources."""
        if hasattr(self, '_session'):
            self._session.close()

class OfflineMapManager(QObject):
    """Main manager for offline map operations."""

    download_started = pyqtSignal(str)  # area name
    download_progress = pyqtSignal(str, int, int, str)  # area name, current, total, status
    download_completed = pyqtSignal(str, bool, str)  # area name, success, message
    area_added = pyqtSignal(dict)  # area data
    area_removed = pyqtSignal(str)  # area name

    def __init__(self, database: NavigationDatabase):
        super().__init__()
        self.database = database
        self.active_downloads = {}  # area_name -> DownloadThread
        self.offline_areas = []

        # Load existing offline areas
        self.load_offline_areas()

    def load_offline_areas(self):
        """Load offline areas from database."""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM offline_areas ORDER BY created_at DESC")
                self.offline_areas = [dict(row) for row in cursor.fetchall()]

            logger.info(f"Loaded {len(self.offline_areas)} offline areas")

        except Exception as e:
            logger.error(f"Error loading offline areas: {e}")
            self.offline_areas = []

    def add_offline_area(self, area: OfflineArea) -> bool:
        """Add a new offline area."""
        try:
            # Check if area already exists
            if self.get_offline_area(area.name):
                raise ValueError(f"Area '{area.name}' already exists")

            # Calculate estimates
            tile_count = area.calculate_tile_count()
            size_mb = area.estimate_size_mb()

            # Save to database
            with self.database.get_connection() as conn:
                conn.execute("""
                    INSERT INTO offline_areas
                    (name, min_lat, min_lon, max_lat, max_lon, min_zoom, max_zoom, server)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (area.name, area.min_lat, area.min_lon, area.max_lat, area.max_lon,
                     area.min_zoom, area.max_zoom, area.server))
                conn.commit()

            # Reload areas and emit signal
            self.load_offline_areas()

            area_data = {
                'name': area.name,
                'tile_count': tile_count,
                'size_mb': size_mb,
                'server': area.server
            }
            self.area_added.emit(area_data)

            logger.info(f"Added offline area: {area.name}")
            return True

        except Exception as e:
            logger.error(f"Error adding offline area: {e}")
            return False

    def remove_offline_area(self, area_name: str) -> bool:
        """Remove an offline area and its tiles."""
        try:
            # Stop any active download
            if area_name in self.active_downloads:
                self.cancel_download(area_name)

            # Get area info before deletion
            area_data = self.get_offline_area(area_name)
            if not area_data:
                return False

            # Remove tiles from cache
            self._remove_area_tiles(area_data)

            # Remove from database
            with self.database.get_connection() as conn:
                conn.execute("DELETE FROM offline_areas WHERE name = ?", (area_name,))
                conn.commit()

            # Reload areas and emit signal
            self.load_offline_areas()
            self.area_removed.emit(area_name)

            logger.info(f"Removed offline area: {area_name}")
            return True

        except Exception as e:
            logger.error(f"Error removing offline area: {e}")
            return False

    def start_download(self, area_name: str) -> bool:
        """Start downloading an offline area."""
        try:
            # Check if already downloading
            if area_name in self.active_downloads:
                logger.warning(f"Download already active for area: {area_name}")
                return False

            # Get area data
            area_data = self.get_offline_area(area_name)
            if not area_data:
                logger.error(f"Area not found: {area_name}")
                return False

            # Create OfflineArea object
            area = OfflineArea(
                area_data['name'],
                area_data['min_lat'],
                area_data['min_lon'],
                area_data['max_lat'],
                area_data['max_lon'],
                area_data['min_zoom'],
                area_data['max_zoom'],
                area_data['server']
            )

            # Create and start download thread
            download_thread = OfflineDownloadThread(area, self.database)

            # Connect signals
            download_thread.progress_updated.connect(
                lambda current, total, status: self.download_progress.emit(
                    area_name, current, total, status
                )
            )
            download_thread.download_completed.connect(
                lambda success, message: self._on_download_completed(
                    area_name, success, message
                )
            )
            download_thread.error_occurred.connect(
                lambda error: self.download_completed.emit(area_name, False, error)
            )

            # Start download
            self.active_downloads[area_name] = download_thread
            download_thread.start()

            self.download_started.emit(area_name)
            logger.info(f"Started download for area: {area_name}")
            return True

        except Exception as e:
            logger.error(f"Error starting download: {e}")
            return False

    def cancel_download(self, area_name: str):
        """Cancel an active download."""
        if area_name in self.active_downloads:
            self.active_downloads[area_name].cancel()
            self.active_downloads[area_name].wait()
            del self.active_downloads[area_name]
            logger.info(f"Cancelled download for area: {area_name}")

    def pause_download(self, area_name: str):
        """Pause an active download."""
        if area_name in self.active_downloads:
            self.active_downloads[area_name].pause()

    def resume_download(self, area_name: str):
        """Resume a paused download."""
        if area_name in self.active_downloads:
            self.active_downloads[area_name].resume()

    def _on_download_completed(self, area_name: str, success: bool, message: str):
        """Handle download completion."""
        if area_name in self.active_downloads:
            self.active_downloads[area_name].wait()
            del self.active_downloads[area_name]

        # Reload areas to get updated progress
        self.load_offline_areas()

        self.download_completed.emit(area_name, success, message)
        logger.info(f"Download completed for {area_name}: {message}")

    def get_offline_area(self, area_name: str) -> Optional[Dict]:
        """Get offline area data by name."""
        for area in self.offline_areas:
            if area['name'] == area_name:
                return area
        return None

    def get_offline_areas(self) -> List[Dict]:
        """Get all offline areas."""
        return self.offline_areas.copy()

    def is_downloading(self, area_name: str) -> bool:
        """Check if an area is currently downloading."""
        return area_name in self.active_downloads

    def get_storage_stats(self) -> Dict:
        """Get storage statistics for offline maps."""
        try:
            total_size = 0
            area_stats = {}

            for area in self.offline_areas:
                # Count tiles for this area
                tile_count = self._count_area_tiles(area)

                # Estimate size (this is approximate)
                estimated_size = tile_count * 20 * 1024  # 20KB per tile average

                area_stats[area['name']] = {
                    'tile_count': tile_count,
                    'size_bytes': estimated_size,
                    'progress': area.get('download_progress', 0),
                    'is_complete': area.get('is_complete', False)
                }

                total_size += estimated_size

            return {
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'areas': area_stats
            }

        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {'total_size_bytes': 0, 'total_size_mb': 0, 'areas': {}}

    def _count_area_tiles(self, area_data: Dict) -> int:
        """Count tiles stored for an area."""
        try:
            # Create temporary OfflineArea to get tile list
            area = OfflineArea(
                area_data['name'],
                area_data['min_lat'],
                area_data['min_lon'],
                area_data['max_lat'],
                area_data['max_lon'],
                area_data['min_zoom'],
                area_data['max_zoom'],
                area_data['server']
            )

            tiles = area.get_tile_list()
            count = 0

            for x, y, z in tiles:
                if self.database.get_cached_tile(x, y, z, area_data['server']):
                    count += 1

            return count

        except Exception as e:
            logger.error(f"Error counting area tiles: {e}")
            return 0

    def _remove_area_tiles(self, area_data: Dict):
        """Remove all tiles for an area."""
        try:
            # Create temporary OfflineArea to get tile list
            area = OfflineArea(
                area_data['name'],
                area_data['min_lat'],
                area_data['min_lon'],
                area_data['max_lat'],
                area_data['max_lon'],
                area_data['min_zoom'],
                area_data['max_zoom'],
                area_data['server']
            )

            tiles = area.get_tile_list()

            with self.database.get_connection() as conn:
                for x, y, z in tiles:
                    conn.execute(
                        "DELETE FROM map_tiles WHERE x = ? AND y = ? AND z = ? AND server = ?",
                        (x, y, z, area_data['server'])
                    )
                conn.commit()

            logger.info(f"Removed {len(tiles)} tiles for area {area_data['name']}")

        except Exception as e:
            logger.error(f"Error removing area tiles: {e}")

    def cleanup_old_tiles(self, days: int = 30):
        """Clean up old tiles not part of any offline area."""
        try:
            # Get all tiles that are part of offline areas
            protected_tiles = set()

            for area_data in self.offline_areas:
                area = OfflineArea(
                    area_data['name'],
                    area_data['min_lat'],
                    area_data['min_lon'],
                    area_data['max_lat'],
                    area_data['max_lon'],
                    area_data['min_zoom'],
                    area_data['max_zoom'],
                    area_data['server']
                )

                for x, y, z in area.get_tile_list():
                    protected_tiles.add((x, y, z, area_data['server']))

            # Delete old tiles not in protected set
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT x, y, z, server FROM map_tiles
                    WHERE last_accessed < datetime('now', '-{} days')
                """.format(days))

                deleted_count = 0
                for row in cursor.fetchall():
                    tile_key = (row['x'], row['y'], row['z'], row['server'])
                    if tile_key not in protected_tiles:
                        conn.execute(
                            "DELETE FROM map_tiles WHERE x = ? AND y = ? AND z = ? AND server = ?",
                            tile_key
                        )
                        deleted_count += 1

                conn.commit()

            logger.info(f"Cleaned up {deleted_count} old tiles")

        except Exception as e:
            logger.error(f"Error cleaning up old tiles: {e}")
