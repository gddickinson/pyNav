"""
Navigation Core Components
=========================

Core functionality for the navigation system including:
- Location management and GPS handling
- Map tile management and caching
- Route calculation and navigation
- Address geocoding and reverse geocoding
"""

# Import core components
try:
    from .location_manager import LocationManager, LocationProvider
    from .map_manager import MapManager, MapLayer, TileLayer, POILayer
    from .routing_engine import RoutingEngine, RoutePoint
    from .geocoding_service import GeocodingService, GeocodingResult

    __all__ = [
        # Location components
        'LocationManager',
        'LocationProvider',

        # Map components
        'MapManager',
        'MapLayer',
        'TileLayer',
        'POILayer',

        # Routing components
        'RoutingEngine',
        'RoutePoint',

        # Geocoding components
        'GeocodingService',
        'GeocodingResult'
    ]

except ImportError as e:
    import warnings
    warnings.warn(f"Could not import some core components: {e}")
    __all__ = []

# Version compatibility
MINIMUM_PYTHON_VERSION = (3, 8)
RECOMMENDED_PYTHON_VERSION = (3, 11)
