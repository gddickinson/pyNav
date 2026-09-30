"""
Navigation Utilities
===================

Utility modules providing:
- Application settings and configuration management
- Centralized logging system with rotation
- Performance monitoring and crash reporting
- Helper functions for common operations
"""

# Import utility components
try:
    from .settings import NavigationSettings
    from .logger import setup_logger, NavigationLogger
    
    __all__ = [
        'NavigationSettings',
        'setup_logger',
        'NavigationLogger'
    ]
    
except ImportError as e:
    import warnings
    warnings.warn(f"Could not import utility components: {e}")
    __all__ = []

# Utility configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_CONFIG_DIR = "~/.pynav"
