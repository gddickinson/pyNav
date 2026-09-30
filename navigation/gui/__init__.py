"""
Navigation GUI Components
========================

PyQt6-based user interface components including:
- Interactive map widget with navigation overlays
- Route planning and management interface
- Points of Interest (POI) management
- Settings and configuration dialogs
"""

# Import GUI components
try:
    from .map_widget import NavigationMapWidget
    from .route_panel import RoutePlanningPanel, WaypointItem, SavedRouteItem
    from .poi_manager import POIManager, POIItem, POIEditDialog
    
    __all__ = [
        # Map display
        'NavigationMapWidget',
        
        # Route planning
        'RoutePlanningPanel',
        'WaypointItem',
        'SavedRouteItem',
        
        # POI management
        'POIManager',
        'POIItem', 
        'POIEditDialog'
    ]
    
except ImportError as e:
    import warnings
    warnings.warn(f"Could not import GUI components (PyQt6 may not be installed): {e}")
    __all__ = []

# GUI framework requirements
REQUIRED_QT_VERSION = "6.4.0"
REQUIRED_PYQT_VERSION = "6.4.0"
