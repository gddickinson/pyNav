"""
Navigation Database - Handles data storage, caching, and persistence
Manages map tiles, routes, POIs, and user data
"""

import sqlite3
import json
import time
import os
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from contextlib import contextmanager

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

class NavigationDatabase:
    """Main database class for navigation data storage."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to user's home directory
            home_dir = Path.home()
            app_dir = home_dir / ".pynav"
            app_dir.mkdir(exist_ok=True)
            db_path = app_dir / "navigation.db"
            
        self.db_path = str(db_path)
        self.init_database()
        
    def init_database(self):
        """Initialize database tables."""
        try:
            with self.get_connection() as conn:
                # Map tiles cache
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS map_tiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        x INTEGER NOT NULL,
                        y INTEGER NOT NULL, 
                        z INTEGER NOT NULL,
                        server TEXT NOT NULL,
                        tile_data BLOB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(x, y, z, server)
                    )
                """)
                
                # Create index for faster tile lookups
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tiles_xyz 
                    ON map_tiles(x, y, z, server)
                """)
                
                # Saved routes
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS saved_routes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        start_lat REAL NOT NULL,
                        start_lon REAL NOT NULL,
                        end_lat REAL NOT NULL,
                        end_lon REAL NOT NULL,
                        waypoints TEXT,  -- JSON array of waypoints
                        route_data TEXT NOT NULL,  -- JSON route data
                        distance REAL,
                        duration REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Points of Interest (POI)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS pois (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        category TEXT,
                        address TEXT,
                        phone TEXT,
                        website TEXT,
                        notes TEXT,
                        rating REAL,
                        is_favorite BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create spatial index for POIs
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_pois_location 
                    ON pois(latitude, longitude)
                """)
                
                # Search history
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS search_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query TEXT NOT NULL,
                        result_lat REAL,
                        result_lon REAL,
                        result_address TEXT,
                        search_type TEXT,  -- 'address', 'poi', 'coordinate'
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Location history
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS location_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        accuracy REAL,
                        speed REAL,
                        heading REAL,
                        source TEXT,  -- 'gps', 'ip', 'manual'
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Application settings
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Route cache for frequently used routes
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS route_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        start_lat REAL NOT NULL,
                        start_lon REAL NOT NULL,
                        end_lat REAL NOT NULL,
                        end_lon REAL NOT NULL,
                        options_hash TEXT NOT NULL,  -- Hash of routing options
                        route_data TEXT NOT NULL,    -- JSON route data
                        service TEXT NOT NULL,       -- Routing service used
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(start_lat, start_lon, end_lat, end_lon, options_hash)
                    )
                """)
                
                # Offline map areas
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS offline_areas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        min_lat REAL NOT NULL,
                        min_lon REAL NOT NULL,
                        max_lat REAL NOT NULL,
                        max_lon REAL NOT NULL,
                        min_zoom INTEGER NOT NULL,
                        max_zoom INTEGER NOT NULL,
                        server TEXT NOT NULL,
                        download_progress REAL DEFAULT 0,
                        is_complete BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
            
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Allow dict-like access to rows
        try:
            yield conn
        finally:
            conn.close()
            
    # Map tile caching methods
    def cache_tile(self, x: int, y: int, z: int, server: str, tile_data: bytes):
        """Cache a map tile."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO map_tiles 
                    (x, y, z, server, tile_data, last_accessed) 
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (x, y, z, server, tile_data))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error caching tile {x},{y},{z}: {e}")
            
    def get_cached_tile(self, x: int, y: int, z: int, server: str) -> Optional[bytes]:
        """Get cached tile data."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT tile_data FROM map_tiles 
                    WHERE x = ? AND y = ? AND z = ? AND server = ?
                """, (x, y, z, server))
                
                row = cursor.fetchone()
                if row:
                    # Update last accessed time
                    conn.execute("""
                        UPDATE map_tiles SET last_accessed = CURRENT_TIMESTAMP
                        WHERE x = ? AND y = ? AND z = ? AND server = ?
                    """, (x, y, z, server))
                    conn.commit()
                    return row['tile_data']
                    
        except Exception as e:
            logger.error(f"Error getting cached tile {x},{y},{z}: {e}")
            
        return None
        
    def clear_tile_cache(self, server: str = None, older_than_days: int = None):
        """Clear tile cache."""
        try:
            with self.get_connection() as conn:
                if older_than_days:
                    # Clear old tiles
                    conn.execute("""
                        DELETE FROM map_tiles 
                        WHERE last_accessed < datetime('now', '-{} days')
                    """.format(older_than_days))
                elif server:
                    # Clear tiles for specific server
                    conn.execute("DELETE FROM map_tiles WHERE server = ?", (server,))
                else:
                    # Clear all tiles
                    conn.execute("DELETE FROM map_tiles")
                    
                conn.commit()
                logger.info("Tile cache cleared")
                
        except Exception as e:
            logger.error(f"Error clearing tile cache: {e}")
            
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get tile cache statistics."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        server,
                        COUNT(*) as tile_count,
                        SUM(LENGTH(tile_data)) as total_size,
                        MIN(created_at) as oldest,
                        MAX(last_accessed) as newest
                    FROM map_tiles 
                    GROUP BY server
                """)
                
                stats = {}
                total_tiles = 0
                total_size = 0
                
                for row in cursor.fetchall():
                    server_stats = {
                        'tile_count': row['tile_count'],
                        'total_size': row['total_size'] or 0,
                        'oldest': row['oldest'],
                        'newest': row['newest']
                    }
                    stats[row['server']] = server_stats
                    total_tiles += row['tile_count']
                    total_size += row['total_size'] or 0
                    
                stats['total'] = {
                    'tile_count': total_tiles,
                    'total_size': total_size
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
            
    # Route management methods
    def save_route(self, name: str, start_lat: float, start_lon: float,
                   end_lat: float, end_lon: float, route_data: Dict,
                   waypoints: List[Tuple[float, float]] = None) -> int:
        """Save a route."""
        try:
            with self.get_connection() as conn:
                waypoints_json = json.dumps(waypoints) if waypoints else None
                
                cursor = conn.execute("""
                    INSERT INTO saved_routes 
                    (name, start_lat, start_lon, end_lat, end_lon, waypoints, 
                     route_data, distance, duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, start_lat, start_lon, end_lat, end_lon,
                    waypoints_json, json.dumps(route_data),
                    route_data.get('distance'), route_data.get('duration')
                ))
                
                conn.commit()
                route_id = cursor.lastrowid
                logger.info(f"Route saved with ID {route_id}")
                return route_id
                
        except Exception as e:
            logger.error(f"Error saving route: {e}")
            return -1
            
    def get_saved_routes(self) -> List[Dict]:
        """Get all saved routes."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM saved_routes 
                    ORDER BY last_used DESC, created_at DESC
                """)
                
                routes = []
                for row in cursor.fetchall():
                    route = dict(row)
                    route['waypoints'] = json.loads(row['waypoints']) if row['waypoints'] else []
                    route['route_data'] = json.loads(row['route_data'])
                    routes.append(route)
                    
                return routes
                
        except Exception as e:
            logger.error(f"Error getting saved routes: {e}")
            return []
            
    def delete_route(self, route_id: int):
        """Delete a saved route."""
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM saved_routes WHERE id = ?", (route_id,))
                conn.commit()
                logger.info(f"Route {route_id} deleted")
                
        except Exception as e:
            logger.error(f"Error deleting route: {e}")
            
    # POI management methods
    def add_poi(self, name: str, latitude: float, longitude: float,
                category: str = None, address: str = None, phone: str = None,
                website: str = None, notes: str = None, rating: float = None) -> int:
        """Add a point of interest."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO pois 
                    (name, latitude, longitude, category, address, phone, website, notes, rating)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, latitude, longitude, category, address, phone, website, notes, rating))
                
                conn.commit()
                poi_id = cursor.lastrowid
                logger.info(f"POI added with ID {poi_id}")
                return poi_id
                
        except Exception as e:
            logger.error(f"Error adding POI: {e}")
            return -1
            
    def get_pois_in_area(self, min_lat: float, min_lon: float,
                        max_lat: float, max_lon: float) -> List[Dict]:
        """Get POIs in a geographic area."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM pois 
                    WHERE latitude BETWEEN ? AND ? 
                    AND longitude BETWEEN ? AND ?
                    ORDER BY is_favorite DESC, name
                """, (min_lat, max_lat, min_lon, max_lon))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting POIs in area: {e}")
            return []
            
    def get_favorite_pois(self) -> List[Dict]:
        """Get favorite POIs."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM pois WHERE is_favorite = 1 
                    ORDER BY name
                """)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting favorite POIs: {e}")
            return []
            
    def update_poi(self, poi_id: int, **kwargs):
        """Update a POI."""
        try:
            if not kwargs:
                return
                
            # Build dynamic update query
            set_clauses = []
            values = []
            
            for key, value in kwargs.items():
                if key in ['name', 'latitude', 'longitude', 'category', 'address', 
                          'phone', 'website', 'notes', 'rating', 'is_favorite']:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
                    
            if not set_clauses:
                return
                
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            values.append(poi_id)
            
            query = f"UPDATE pois SET {', '.join(set_clauses)} WHERE id = ?"
            
            with self.get_connection() as conn:
                conn.execute(query, values)
                conn.commit()
                logger.info(f"POI {poi_id} updated")
                
        except Exception as e:
            logger.error(f"Error updating POI: {e}")
            
    def delete_poi(self, poi_id: int):
        """Delete a POI."""
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM pois WHERE id = ?", (poi_id,))
                conn.commit()
                logger.info(f"POI {poi_id} deleted")
                
        except Exception as e:
            logger.error(f"Error deleting POI: {e}")
            
    # Search history methods
    def add_search_history(self, query: str, result_lat: float = None,
                          result_lon: float = None, result_address: str = None,
                          search_type: str = 'address'):
        """Add search to history."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO search_history 
                    (query, result_lat, result_lon, result_address, search_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (query, result_lat, result_lon, result_address, search_type))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error adding search history: {e}")
            
    def get_search_history(self, limit: int = 50) -> List[Dict]:
        """Get recent search history."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM search_history 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting search history: {e}")
            return []
            
    def clear_search_history(self):
        """Clear search history."""
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM search_history")
                conn.commit()
                logger.info("Search history cleared")
                
        except Exception as e:
            logger.error(f"Error clearing search history: {e}")
            
    # Location history methods
    def add_location_history(self, latitude: float, longitude: float,
                           accuracy: float = None, speed: float = None,
                           heading: float = None, source: str = 'unknown'):
        """Add location to history."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO location_history 
                    (latitude, longitude, accuracy, speed, heading, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (latitude, longitude, accuracy, speed, heading, source))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error adding location history: {e}")
            
    def get_location_history(self, limit: int = 1000) -> List[Dict]:
        """Get recent location history."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM location_history 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting location history: {e}")
            return []
            
    def clear_old_location_history(self, days: int = 30):
        """Clear location history older than specified days."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    DELETE FROM location_history 
                    WHERE timestamp < datetime('now', '-{} days')
                """.format(days))
                conn.commit()
                logger.info(f"Cleared location history older than {days} days")
                
        except Exception as e:
            logger.error(f"Error clearing old location history: {e}")
            
    # Settings methods
    def set_setting(self, key: str, value: Any):
        """Set application setting."""
        try:
            # Convert value to JSON string
            value_str = json.dumps(value) if not isinstance(value, str) else value
            
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO settings (key, value) 
                    VALUES (?, ?)
                """, (key, value_str))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")
            
    def get_setting(self, key: str, default=None):
        """Get application setting."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                
                if row:
                    try:
                        # Try to parse as JSON
                        return json.loads(row['value'])
                    except json.JSONDecodeError:
                        # Return as string if not valid JSON
                        return row['value']
                        
                return default
                
        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            return default
            
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all application settings."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT key, value FROM settings")
                settings = {}
                
                for row in cursor.fetchall():
                    try:
                        settings[row['key']] = json.loads(row['value'])
                    except json.JSONDecodeError:
                        settings[row['key']] = row['value']
                        
                return settings
                
        except Exception as e:
            logger.error(f"Error getting all settings: {e}")
            return {}
            
    # Route caching methods
    def cache_route(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float,
                   options_hash: str, route_data: Dict, service: str):
        """Cache a calculated route."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO route_cache 
                    (start_lat, start_lon, end_lat, end_lon, options_hash, route_data, service)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (start_lat, start_lon, end_lat, end_lon, options_hash, 
                     json.dumps(route_data), service))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error caching route: {e}")
            
    def get_cached_route(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float,
                        options_hash: str, max_age_hours: int = 24) -> Optional[Dict]:
        """Get cached route if available and fresh."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT route_data FROM route_cache 
                    WHERE start_lat = ? AND start_lon = ? 
                    AND end_lat = ? AND end_lon = ? 
                    AND options_hash = ?
                    AND created_at > datetime('now', '-{} hours')
                """.format(max_age_hours), (start_lat, start_lon, end_lat, end_lon, options_hash))
                
                row = cursor.fetchone()
                if row:
                    return json.loads(row['route_data'])
                    
        except Exception as e:
            logger.error(f"Error getting cached route: {e}")
            
        return None
        
    def clear_route_cache(self):
        """Clear route cache."""
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM route_cache")
                conn.commit()
                logger.info("Route cache cleared")
                
        except Exception as e:
            logger.error(f"Error clearing route cache: {e}")
            
    # Database maintenance
    def optimize_database(self):
        """Optimize database performance."""
        try:
            with self.get_connection() as conn:
                # Vacuum database
                conn.execute("VACUUM")
                
                # Analyze query patterns
                conn.execute("ANALYZE")
                
                logger.info("Database optimized")
                
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            
    def get_database_size(self) -> int:
        """Get database file size in bytes."""
        try:
            return os.path.getsize(self.db_path)
        except Exception as e:
            logger.error(f"Error getting database size: {e}")
            return 0
            
    def close(self):
        """Close database connection."""
        # SQLite connections are closed automatically with context manager
        logger.info("Database connection closed")
