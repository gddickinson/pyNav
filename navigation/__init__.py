"""
PyNav Navigation Software - Core Package
=======================================

A comprehensive GPS navigation and mapping application built with PyQt6.

This package provides:
- Location tracking and GPS integration
- Interactive mapping and visualization  
- Route planning and turn-by-turn navigation
- Points of Interest (POI) management
- Address geocoding and search
- Persistent data storage
"""

__version__ = "1.0.0"
__author__ = "PyNav Development Team"

# Import main components for easier access
try:
    from .core.location_manager import LocationManager
    from .core.map_manager import MapManager
    from .core.routing_engine import RoutingEngine
    from .core.geocoding_service import GeocodingService
    from .data.database import NavigationDatabase
    from .utils.settings import NavigationSettings
    from .utils.logger import setup_logger
    
    __all__ = [
        'LocationManager',
        'MapManager', 
        'RoutingEngine',
        'GeocodingService',
        'NavigationDatabase',
        'NavigationSettings',
        'setup_logger'
    ]
    
except ImportError as e:
    # Handle missing dependencies gracefully during development
    import warnings
    warnings.warn(f"Some navigation components could not be imported: {e}")
    __all__ = []
