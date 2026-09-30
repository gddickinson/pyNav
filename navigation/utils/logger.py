"""
Navigation Logger - Centralized logging utility for the navigation application
Provides structured logging with different levels, file rotation, and formatting
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""
    
    # Color codes for different log levels
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        """Format log record with colors."""
        # Get the original formatted message
        message = super().format(record)
        
        # Add color if outputting to terminal
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            level_name = record.levelname
            color = self.COLORS.get(level_name, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
            return f"{color}{message}{reset}"
        else:
            return message

class NavigationLogger:
    """Main logger class for the navigation application."""
    
    _instance = None
    _loggers = {}
    
    def __new__(cls):
        """Singleton pattern to ensure only one logger instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the navigation logger."""
        if self._initialized:
            return
            
        self._initialized = True
        self.log_dir = None
        self.log_level = logging.INFO
        self.file_handler = None
        self.console_handler = None
        
        # Create default logger
        self.setup_logging()
    
    def setup_logging(self, log_dir: Optional[str] = None, 
                     log_level: int = logging.INFO,
                     enable_console: bool = True,
                     enable_file: bool = True):
        """Set up logging configuration.
        
        Args:
            log_dir: Directory for log files (default: ~/.pynav/logs)
            log_level: Logging level
            enable_console: Enable console output
            enable_file: Enable file output
        """
        try:
            # Set log directory
            if log_dir is None:
                home_dir = Path.home()
                self.log_dir = home_dir / ".pynav" / "logs"
            else:
                self.log_dir = Path(log_dir)
                
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.log_level = log_level
            
            # Configure root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(log_level)
            
            # Remove existing handlers
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            # Console handler
            if enable_console:
                self.console_handler = logging.StreamHandler(sys.stdout)
                console_formatter = ColoredFormatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%H:%M:%S'
                )
                self.console_handler.setFormatter(console_formatter)
                self.console_handler.setLevel(log_level)
                root_logger.addHandler(self.console_handler)
            
            # File handler with rotation
            if enable_file:
                log_file = self.log_dir / "navigation.log"
                self.file_handler = logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=5
                )
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                self.file_handler.setFormatter(file_formatter)
                self.file_handler.setLevel(log_level)
                root_logger.addHandler(self.file_handler)
            
            # Log the setup
            logger = self.get_logger(__name__)
            logger.info("Logging system initialized")
            logger.info(f"Log directory: {self.log_dir}")
            logger.info(f"Log level: {logging.getLevelName(log_level)}")
            
        except Exception as e:
            print(f"Error setting up logging: {e}")
            # Fall back to basic console logging
            logging.basicConfig(level=log_level)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance for a specific module.
        
        Args:
            name: Logger name (typically __name__)
            
        Returns:
            Logger instance
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            logger.setLevel(self.log_level)
            self._loggers[name] = logger
            
        return self._loggers[name]
    
    def set_log_level(self, level: int):
        """Set the logging level for all loggers.
        
        Args:
            level: Logging level (e.g., logging.DEBUG, logging.INFO)
        """
        try:
            self.log_level = level
            
            # Update root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(level)
            
            # Update handlers
            if self.console_handler:
                self.console_handler.setLevel(level)
            if self.file_handler:
                self.file_handler.setLevel(level)
                
            # Update all registered loggers
            for logger in self._loggers.values():
                logger.setLevel(level)
                
            logger = self.get_logger(__name__)
            logger.info(f"Log level changed to {logging.getLevelName(level)}")
            
        except Exception as e:
            print(f"Error setting log level: {e}")
    
    def add_file_handler(self, filename: str, level: int = None):
        """Add an additional file handler.
        
        Args:
            filename: Name of the log file
            level: Log level for this handler (optional)
        """
        try:
            if level is None:
                level = self.log_level
                
            log_file = self.log_dir / filename
            handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,  # 5MB
                backupCount=3
            )
            
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            handler.setLevel(level)
            
            # Add to root logger
            root_logger = logging.getLogger()
            root_logger.addHandler(handler)
            
            logger = self.get_logger(__name__)
            logger.info(f"Added file handler: {log_file}")
            
        except Exception as e:
            print(f"Error adding file handler: {e}")
    
    def enable_debug_logging(self):
        """Enable debug level logging."""
        self.set_log_level(logging.DEBUG)
    
    def disable_console_logging(self):
        """Disable console logging output."""
        if self.console_handler:
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.console_handler)
            self.console_handler = None
    
    def enable_console_logging(self):
        """Enable console logging output."""
        if not self.console_handler:
            self.console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = ColoredFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            self.console_handler.setFormatter(console_formatter)
            self.console_handler.setLevel(self.log_level)
            
            root_logger = logging.getLogger()
            root_logger.addHandler(self.console_handler)
    
    def log_exception(self, logger: logging.Logger, exception: Exception, 
                     context: str = ""):
        """Log an exception with full traceback.
        
        Args:
            logger: Logger instance to use
            exception: Exception that occurred
            context: Additional context about where/when the error occurred
        """
        import traceback
        
        error_msg = f"{context} - {str(exception)}" if context else str(exception)
        logger.error(error_msg)
        logger.debug(f"Full traceback:\n{traceback.format_exc()}")
    
    def log_performance(self, logger: logging.Logger, operation: str, 
                       duration: float, details: dict = None):
        """Log performance metrics.
        
        Args:
            logger: Logger instance
            operation: Description of the operation
            duration: Duration in seconds
            details: Additional details dict
        """
        msg = f"PERFORMANCE: {operation} took {duration:.3f}s"
        if details:
            detail_str = ", ".join([f"{k}={v}" for k, v in details.items()])
            msg += f" ({detail_str})"
            
        if duration > 5.0:  # Slow operations
            logger.warning(msg)
        elif duration > 1.0:  # Medium operations
            logger.info(msg)
        else:  # Fast operations
            logger.debug(msg)
    
    def log_memory_usage(self, logger: logging.Logger, context: str = ""):
        """Log current memory usage.
        
        Args:
            logger: Logger instance
            context: Context for the memory check
        """
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            msg = f"MEMORY{' (' + context + ')' if context else ''}: "
            msg += f"RSS={memory_info.rss / 1024 / 1024:.1f}MB, "
            msg += f"VMS={memory_info.vms / 1024 / 1024:.1f}MB"
            
            logger.debug(msg)
            
        except ImportError:
            logger.debug("psutil not available for memory monitoring")
        except Exception as e:
            logger.debug(f"Error getting memory usage: {e}")
    
    def create_crash_log(self, exception: Exception, context: dict = None):
        """Create a crash log file with detailed information.
        
        Args:
            exception: The exception that caused the crash
            context: Additional context information
        """
        try:
            import traceback
            import platform
            import sys
            
            # Create crash log filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            crash_file = self.log_dir / f"crash_{timestamp}.log"
            
            with open(crash_file, 'w') as f:
                f.write("=" * 50 + "\n")
                f.write("NAVIGATION APP CRASH REPORT\n")
                f.write("=" * 50 + "\n\n")
                
                # Timestamp
                f.write(f"Crash Time: {datetime.now().isoformat()}\n\n")
                
                # System information
                f.write("SYSTEM INFORMATION:\n")
                f.write("-" * 20 + "\n")
                f.write(f"Platform: {platform.platform()}\n")
                f.write(f"Python Version: {sys.version}\n")
                f.write(f"Architecture: {platform.architecture()}\n")
                f.write(f"Processor: {platform.processor()}\n\n")
                
                # Application context
                if context:
                    f.write("APPLICATION CONTEXT:\n")
                    f.write("-" * 20 + "\n")
                    for key, value in context.items():
                        f.write(f"{key}: {value}\n")
                    f.write("\n")
                
                # Exception information
                f.write("EXCEPTION INFORMATION:\n")
                f.write("-" * 20 + "\n")
                f.write(f"Exception Type: {type(exception).__name__}\n")
                f.write(f"Exception Message: {str(exception)}\n\n")
                
                # Full traceback
                f.write("FULL TRACEBACK:\n")
                f.write("-" * 20 + "\n")
                f.write(traceback.format_exc())
                f.write("\n")
                
                # Memory information if available
                try:
                    import psutil
                    process = psutil.Process()
                    memory_info = process.memory_info()
                    f.write("MEMORY INFORMATION:\n")
                    f.write("-" * 20 + "\n")
                    f.write(f"RSS: {memory_info.rss / 1024 / 1024:.1f} MB\n")
                    f.write(f"VMS: {memory_info.vms / 1024 / 1024:.1f} MB\n\n")
                except:
                    pass
                
            logger = self.get_logger(__name__)
            logger.critical(f"Crash log created: {crash_file}")
            
        except Exception as e:
            print(f"Error creating crash log: {e}")
    
    def archive_old_logs(self, days_to_keep: int = 30):
        """Archive old log files.
        
        Args:
            days_to_keep: Number of days to keep logs
        """
        try:
            import time
            import shutil
            
            current_time = time.time()
            cutoff_time = current_time - (days_to_keep * 24 * 60 * 60)
            
            # Create archive directory
            archive_dir = self.log_dir / "archive"
            archive_dir.mkdir(exist_ok=True)
            
            archived_count = 0
            
            for log_file in self.log_dir.glob("*.log*"):
                if log_file.is_file():
                    file_time = log_file.stat().st_mtime
                    
                    if file_time < cutoff_time:
                        # Move to archive
                        archive_file = archive_dir / log_file.name
                        shutil.move(str(log_file), str(archive_file))
                        archived_count += 1
            
            if archived_count > 0:
                logger = self.get_logger(__name__)
                logger.info(f"Archived {archived_count} old log files")
                
        except Exception as e:
            logger = self.get_logger(__name__)
            logger.error(f"Error archiving logs: {e}")
    
    def get_log_stats(self) -> dict:
        """Get statistics about log files.
        
        Returns:
            Dictionary with log statistics
        """
        try:
            stats = {
                'log_directory': str(self.log_dir),
                'total_files': 0,
                'total_size': 0,
                'files': []
            }
            
            for log_file in self.log_dir.glob("*.log*"):
                if log_file.is_file():
                    file_size = log_file.stat().st_size
                    stats['total_files'] += 1
                    stats['total_size'] += file_size
                    
                    stats['files'].append({
                        'name': log_file.name,
                        'size': file_size,
                        'modified': datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
                    })
            
            return stats
            
        except Exception as e:
            return {'error': str(e)}

# Global logger instance
_nav_logger = None

def setup_logger(name: str) -> logging.Logger:
    """Set up and get a logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    global _nav_logger
    
    if _nav_logger is None:
        _nav_logger = NavigationLogger()
    
    return _nav_logger.get_logger(name)

def configure_logging(log_dir: str = None, log_level: int = logging.INFO,
                     enable_console: bool = True, enable_file: bool = True):
    """Configure the logging system.
    
    Args:
        log_dir: Directory for log files
        log_level: Logging level
        enable_console: Enable console output
        enable_file: Enable file output
    """
    global _nav_logger
    
    if _nav_logger is None:
        _nav_logger = NavigationLogger()
    
    _nav_logger.setup_logging(log_dir, log_level, enable_console, enable_file)

def get_logger_instance() -> NavigationLogger:
    """Get the global logger instance.
    
    Returns:
        NavigationLogger instance
    """
    global _nav_logger
    
    if _nav_logger is None:
        _nav_logger = NavigationLogger()
    
    return _nav_logger

def log_exception(logger: logging.Logger, exception: Exception, context: str = ""):
    """Log an exception with full traceback.
    
    Args:
        logger: Logger instance
        exception: Exception that occurred
        context: Additional context
    """
    nav_logger = get_logger_instance()
    nav_logger.log_exception(logger, exception, context)

def log_performance(logger: logging.Logger, operation: str, 
                   duration: float, details: dict = None):
    """Log performance metrics.
    
    Args:
        logger: Logger instance
        operation: Operation description
        duration: Duration in seconds
        details: Additional details
    """
    nav_logger = get_logger_instance()
    nav_logger.log_performance(logger, operation, duration, details)

def create_crash_log(exception: Exception, context: dict = None):
    """Create a crash log file.
    
    Args:
        exception: Exception that caused the crash
        context: Additional context information
    """
    nav_logger = get_logger_instance()
    nav_logger.create_crash_log(exception, context)

# Performance monitoring decorator
def log_performance_decorator(operation_name: str = None):
    """Decorator to log function performance.
    
    Args:
        operation_name: Name of the operation (defaults to function name)
    """
    def decorator(func):
        import functools
        import time
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger = setup_logger(func.__module__)
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                op_name = operation_name or func.__name__
                log_performance(logger, op_name, duration)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                op_name = operation_name or func.__name__
                logger.error(f"Operation '{op_name}' failed after {duration:.3f}s: {e}")
                raise
                
        return wrapper
    return decorator
