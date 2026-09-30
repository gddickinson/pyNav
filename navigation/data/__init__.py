"""
Navigation Data Layer
====================

Database management and data persistence including:
- SQLite database operations
- Map tile caching
- Route and POI storage
- Settings and configuration persistence
- Search history and user data
"""

# Import data components
try:
    from .database import NavigationDatabase
    
    __all__ = [
        'NavigationDatabase'
    ]
    
except ImportError as e:
    import warnings
    warnings.warn(f"Could not import data components: {e}")
    __all__ = []

# Database configuration
DATABASE_VERSION = "1.0"
SCHEMA_VERSION = 1
DEFAULT_DB_NAME = "navigation.db"
