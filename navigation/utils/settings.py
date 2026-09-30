"""
Navigation Settings - Configuration management for the navigation application
Handles application settings, preferences, and configuration storage
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from PyQt6.QtCore import QSettings

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

class NavigationSettings:
    """Main settings manager for the navigation application."""
    
    DEFAULT_SETTINGS = {
        # Application settings
        'app': {
            'version': '1.0.0',
            'first_run': True,
            'language': 'en',
            'theme': 'system',  # 'light', 'dark', 'system'
            'auto_save_interval': 300,  # seconds
            'check_updates': True
        },
        
        # Map settings
        'map': {
            'default_zoom': 15,
            'default_center': [40.7589, -73.9851],  # NYC
            'tile_server': 'OpenStreetMap',
            'satellite_enabled': False,
            'traffic_enabled': False,
            'poi_enabled': True,
            'show_scale_bar': True,
            'show_attribution': True,
            'cache_size_mb': 500,
            'offline_mode': False
        },
        
        # Navigation settings
        'navigation': {
            'routing_service': 'OSRM',
            'vehicle_type': 'car',
            'avoid_tolls': False,
            'avoid_highways': False,
            'voice_guidance': True,
            'voice_language': 'en',
            'units': 'metric',  # 'metric' or 'imperial'
            'route_recalculation': True,
            'traffic_consideration': True
        },
        
        # Location settings
        'location': {
            'preferred_source': 'GPS',
            'gps_timeout': 30,
            'location_history_enabled': True,
            'location_history_days': 30,
            'high_accuracy_mode': False,
            'mock_location_detection': True
        },
        
        # UI settings
        'ui': {
            'window_geometry': None,
            'window_state': None,
            'last_tab': 0,
            'show_toolbar': True,
            'show_statusbar': True,
            'compact_mode': False,
            'animation_enabled': True
        },
        
        # Privacy settings
        'privacy': {
            'collect_analytics': False,
            'share_usage_data': False,
            'location_sharing': False,
            'crash_reporting': True,
            'clear_history_on_exit': False
        },
        
        # Performance settings
        'performance': {
            'max_cached_tiles': 10000,
            'max_route_history': 100,
            'background_updates': True,
            'gpu_acceleration': True,
            'low_power_mode': False
        },
        
        # API settings
        'api': {
            'here_api_key': '',
            'mapbox_api_key': '',
            'google_api_key': '',
            'openweather_api_key': '',
            'rate_limit_enabled': True
        }
    }
    
    def __init__(self):
        """Initialize settings manager."""
        # Setup file paths
        self.app_dir = Path.home() / ".pynav"
        self.app_dir.mkdir(exist_ok=True)
        
        self.settings_file = self.app_dir / "settings.json"
        self.backup_file = self.app_dir / "settings_backup.json"
        
        # Use QSettings for some system-specific settings
        self.qt_settings = QSettings('PyNav', 'NavigationApp')
        
        # Load settings
        self.settings = self.load_settings()
        
        logger.info(f"Settings initialized from {self.settings_file}")
        
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    
                # Merge with defaults (to handle new settings in updates)
                settings = self._deep_merge(self.DEFAULT_SETTINGS.copy(), loaded_settings)
                
                # Validate settings
                settings = self._validate_settings(settings)
                
                logger.info("Settings loaded successfully")
                return settings
            else:
                logger.info("No settings file found, using defaults")
                return self.DEFAULT_SETTINGS.copy()
                
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            
            # Try to load backup
            if self.backup_file.exists():
                try:
                    with open(self.backup_file, 'r') as f:
                        backup_settings = json.load(f)
                    logger.info("Loaded settings from backup")
                    return self._deep_merge(self.DEFAULT_SETTINGS.copy(), backup_settings)
                except Exception as backup_e:
                    logger.error(f"Error loading backup settings: {backup_e}")
                    
            logger.info("Using default settings")
            return self.DEFAULT_SETTINGS.copy()
            
    def save_settings(self):
        """Save settings to file."""
        try:
            # Create backup of current settings
            if self.settings_file.exists():
                import shutil
                shutil.copy2(self.settings_file, self.backup_file)
                
            # Save new settings
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
                
            logger.info("Settings saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            raise
            
    def get(self, key_path: str, default=None) -> Any:
        """Get a setting value using dot notation.
        
        Args:
            key_path: Setting path like 'map.default_zoom'
            default: Default value if setting not found
            
        Returns:
            Setting value or default
        """
        try:
            keys = key_path.split('.')
            value = self.settings
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
                    
            return value
            
        except Exception as e:
            logger.error(f"Error getting setting '{key_path}': {e}")
            return default
            
    def set(self, key_path: str, value: Any):
        """Set a setting value using dot notation.
        
        Args:
            key_path: Setting path like 'map.default_zoom'
            value: Value to set
        """
        try:
            keys = key_path.split('.')
            current = self.settings
            
            # Navigate to the parent of the target key
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
                
            # Set the value
            current[keys[-1]] = value
            
            logger.debug(f"Set setting '{key_path}' = {value}")
            
        except Exception as e:
            logger.error(f"Error setting '{key_path}': {e}")
            raise
            
    def reset_to_defaults(self, section: str = None):
        """Reset settings to defaults.
        
        Args:
            section: Optional section to reset (e.g. 'map'), or None for all
        """
        try:
            if section:
                if section in self.DEFAULT_SETTINGS:
                    self.settings[section] = self.DEFAULT_SETTINGS[section].copy()
                    logger.info(f"Reset section '{section}' to defaults")
                else:
                    logger.warning(f"Unknown settings section: {section}")
            else:
                self.settings = self.DEFAULT_SETTINGS.copy()
                logger.info("Reset all settings to defaults")
                
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            raise
            
    def export_settings(self, file_path: str):
        """Export settings to file.
        
        Args:
            file_path: Path to export file
        """
        try:
            # Don't export sensitive data like API keys
            export_settings = self._sanitize_for_export(self.settings.copy())
            
            with open(file_path, 'w') as f:
                json.dump(export_settings, f, indent=2)
                
            logger.info(f"Settings exported to {file_path}")
            
        except Exception as e:
            logger.error(f"Error exporting settings: {e}")
            raise
            
    def import_settings(self, file_path: str):
        """Import settings from file.
        
        Args:
            file_path: Path to import file
        """
        try:
            with open(file_path, 'r') as f:
                imported_settings = json.load(f)
                
            # Validate and merge with current settings
            imported_settings = self._validate_settings(imported_settings)
            self.settings = self._deep_merge(self.settings, imported_settings)
            
            logger.info(f"Settings imported from {file_path}")
            
        except Exception as e:
            logger.error(f"Error importing settings: {e}")
            raise
            
    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in update.items():
            if (key in result and 
                isinstance(result[key], dict) and 
                isinstance(value, dict)):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
        
    def _validate_settings(self, settings: Dict) -> Dict:
        """Validate settings values."""
        try:
            # Validate zoom level
            if 'map' in settings and 'default_zoom' in settings['map']:
                zoom = settings['map']['default_zoom']
                if not isinstance(zoom, int) or zoom < 1 or zoom > 19:
                    settings['map']['default_zoom'] = self.DEFAULT_SETTINGS['map']['default_zoom']
                    
            # Validate center coordinates
            if 'map' in settings and 'default_center' in settings['map']:
                center = settings['map']['default_center']
                if (not isinstance(center, list) or len(center) != 2 or
                    not all(isinstance(x, (int, float)) for x in center)):
                    settings['map']['default_center'] = self.DEFAULT_SETTINGS['map']['default_center']
                    
            # Validate units
            if 'navigation' in settings and 'units' in settings['navigation']:
                units = settings['navigation']['units']
                if units not in ['metric', 'imperial']:
                    settings['navigation']['units'] = 'metric'
                    
            # Validate cache size
            if 'map' in settings and 'cache_size_mb' in settings['map']:
                cache_size = settings['map']['cache_size_mb']
                if not isinstance(cache_size, int) or cache_size < 10 or cache_size > 10000:
                    settings['map']['cache_size_mb'] = 500
                    
            return settings
            
        except Exception as e:
            logger.error(f"Error validating settings: {e}")
            return settings
            
    def _sanitize_for_export(self, settings: Dict) -> Dict:
        """Remove sensitive data from settings for export."""
        sanitized = settings.copy()
        
        # Remove API keys
        if 'api' in sanitized:
            for key in sanitized['api']:
                if 'key' in key.lower():
                    sanitized['api'][key] = ''
                    
        # Remove personal data
        if 'privacy' in sanitized:
            sanitized['privacy']['location_sharing'] = False
            
        return sanitized
        
    def get_app_data_dir(self) -> Path:
        """Get application data directory."""
        return self.app_dir
        
    def get_cache_dir(self) -> Path:
        """Get cache directory."""
        cache_dir = self.app_dir / "cache"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir
        
    def get_logs_dir(self) -> Path:
        """Get logs directory."""
        logs_dir = self.app_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        return logs_dir
        
    def is_first_run(self) -> bool:
        """Check if this is the first run of the application."""
        return self.get('app.first_run', True)
        
    def mark_first_run_complete(self):
        """Mark first run as complete."""
        self.set('app.first_run', False)
        self.save_settings()
        
    def get_window_geometry(self) -> Optional[bytes]:
        """Get window geometry from Qt settings."""
        return self.qt_settings.value('window_geometry')
        
    def set_window_geometry(self, geometry: bytes):
        """Save window geometry to Qt settings."""
        self.qt_settings.setValue('window_geometry', geometry)
        
    def get_window_state(self) -> Optional[bytes]:
        """Get window state from Qt settings."""
        return self.qt_settings.value('window_state')
        
    def set_window_state(self, state: bytes):
        """Save window state to Qt settings."""
        self.qt_settings.setValue('window_state', state)
        
    def get_recent_searches(self) -> list:
        """Get recent search terms."""
        return self.get('ui.recent_searches', [])
        
    def add_recent_search(self, search_term: str):
        """Add a recent search term."""
        recent = self.get_recent_searches()
        
        # Remove if already exists
        if search_term in recent:
            recent.remove(search_term)
            
        # Add to beginning
        recent.insert(0, search_term)
        
        # Keep only last 20
        recent = recent[:20]
        
        self.set('ui.recent_searches', recent)
        
    def clear_recent_searches(self):
        """Clear recent searches."""
        self.set('ui.recent_searches', [])
        
    def get_api_key(self, service: str) -> str:
        """Get API key for a service.
        
        Args:
            service: Service name (e.g. 'here', 'mapbox', 'google')
            
        Returns:
            API key string (empty if not set)
        """
        key_name = f"{service}_api_key"
        return self.get(f'api.{key_name}', '')
        
    def set_api_key(self, service: str, api_key: str):
        """Set API key for a service.
        
        Args:
            service: Service name (e.g. 'here', 'mapbox', 'google')
            api_key: API key string
        """
        key_name = f"{service}_api_key"
        self.set(f'api.{key_name}', api_key)
        
    def get_map_servers(self) -> Dict[str, Dict]:
        """Get custom map server configurations."""
        return self.get('map.custom_servers', {})
        
    def add_map_server(self, name: str, config: Dict):
        """Add custom map server configuration.
        
        Args:
            name: Server name
            config: Server configuration dict
        """
        servers = self.get_map_servers()
        servers[name] = config
        self.set('map.custom_servers', servers)
        
    def remove_map_server(self, name: str):
        """Remove custom map server configuration."""
        servers = self.get_map_servers()
        if name in servers:
            del servers[name]
            self.set('map.custom_servers', servers)
            
    def cleanup_old_data(self):
        """Clean up old data based on settings."""
        try:
            # Clean location history
            if not self.get('location.location_history_enabled', True):
                # Clear location history if disabled
                # This would call database methods to clear location history
                pass
                
            # Clean search history if privacy setting is enabled
            if self.get('privacy.clear_history_on_exit', False):
                self.clear_recent_searches()
                
            logger.info("Cleaned up old data based on settings")
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            
    def get_performance_settings(self) -> Dict[str, Any]:
        """Get performance-related settings."""
        return {
            'max_cached_tiles': self.get('performance.max_cached_tiles', 10000),
            'max_route_history': self.get('performance.max_route_history', 100),
            'background_updates': self.get('performance.background_updates', True),
            'gpu_acceleration': self.get('performance.gpu_acceleration', True),
            'low_power_mode': self.get('performance.low_power_mode', False)
        }
        
    def get_privacy_settings(self) -> Dict[str, Any]:
        """Get privacy-related settings."""
        return {
            'collect_analytics': self.get('privacy.collect_analytics', False),
            'share_usage_data': self.get('privacy.share_usage_data', False),
            'location_sharing': self.get('privacy.location_sharing', False),
            'crash_reporting': self.get('privacy.crash_reporting', True),
            'clear_history_on_exit': self.get('privacy.clear_history_on_exit', False)
        }
        
    def migrate_settings(self, from_version: str, to_version: str):
        """Migrate settings between versions.
        
        Args:
            from_version: Previous version
            to_version: Current version
        """
        try:
            logger.info(f"Migrating settings from {from_version} to {to_version}")
            
            # Example migration logic
            if from_version == "0.9.0" and to_version == "1.0.0":
                # Migrate old setting names to new ones
                if 'old_setting_name' in self.settings:
                    self.set('new_setting_name', self.settings['old_setting_name'])
                    del self.settings['old_setting_name']
                    
            # Update version
            self.set('app.version', to_version)
            self.save_settings()
            
            logger.info("Settings migration completed")
            
        except Exception as e:
            logger.error(f"Error migrating settings: {e}")
            raise
