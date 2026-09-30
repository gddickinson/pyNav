#!/usr/bin/env python3
"""
Navigation Software - Main Application with GPS Tracker
Enhanced with search history, copy coordinates, map bookmarks, and zoom controls
"""

import sys
import os
import json
import traceback
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging first
try:
    from navigation.utils.logger import setup_logger, create_crash_log
    logger = setup_logger(__name__)
except ImportError as e:
    print(f"Could not initialize logging: {e}")
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if all required dependencies are available."""
    missing_deps = []

    try:
        import PyQt6
        logger.info(f"PyQt6 version: {PyQt6.QtCore.PYQT_VERSION_STR}")
    except ImportError:
        missing_deps.append("PyQt6")

    try:
        import requests
    except ImportError:
        missing_deps.append("requests")

    # Optional dependencies
    optional_missing = []

    try:
        import pynmea2
    except ImportError:
        optional_missing.append("pynmea2 (GPS support)")

    try:
        import serial
    except ImportError:
        optional_missing.append("pyserial (GPS support)")

    if missing_deps:
        logger.error(f"Missing required dependencies: {', '.join(missing_deps)}")
        return False

    if optional_missing:
        logger.warning(f"Missing optional dependencies: {', '.join(optional_missing)}")

    return True

def safe_import_qt():
    """Safely import PyQt6 components with error handling."""
    try:
        from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                   QHBoxLayout, QTabWidget, QLabel, QPushButton,
                                   QLineEdit, QComboBox, QListWidget, QSplitter,
                                   QFrame, QProgressBar, QMessageBox, QCheckBox,
                                   QMenuBar, QMenu, QCompleter, QInputDialog)
        from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject, QStringListModel
        from PyQt6.QtGui import QIcon, QFont, QPixmap, QAction, QClipboard

        return {
            'QApplication': QApplication,
            'QMainWindow': QMainWindow,
            'QWidget': QWidget,
            'QVBoxLayout': QVBoxLayout,
            'QHBoxLayout': QHBoxLayout,
            'QTabWidget': QTabWidget,
            'QLabel': QLabel,
            'QPushButton': QPushButton,
            'QLineEdit': QLineEdit,
            'QComboBox': QComboBox,
            'QListWidget': QListWidget,
            'QSplitter': QSplitter,
            'QFrame': QFrame,
            'QProgressBar': QProgressBar,
            'QMessageBox': QMessageBox,
            'QCheckBox': QCheckBox,
            'QMenuBar': QMenuBar,
            'QMenu': QMenu,
            'QCompleter': QCompleter,
            'QInputDialog': QInputDialog,
            'Qt': Qt,
            'QTimer': QTimer,
            'pyqtSignal': pyqtSignal,
            'QThread': QThread,
            'QObject': QObject,
            'QIcon': QIcon,
            'QFont': QFont,
            'QPixmap': QPixmap,
            'QAction': QAction,
            'QClipboard': QClipboard,
            'QStringListModel': QStringListModel
        }
    except Exception as e:
        logger.error(f"Failed to import PyQt6 components: {e}")
        return None

def safe_import_navigation():
    """Safely import navigation modules with error handling."""
    try:
        from navigation.core.location_manager import LocationManager
        from navigation.core.map_manager import MapManager
        from navigation.core.routing_engine import RoutingEngine
        from navigation.core.geocoding_service import GeocodingService
        from navigation.gui.map_widget import NavigationMapWidget
        from navigation.gui.route_panel import RoutePlanningPanel
        from navigation.gui.poi_manager import POIManager
        from navigation.data.database import NavigationDatabase
        from navigation.utils.settings import NavigationSettings

        return {
            'LocationManager': LocationManager,
            'MapManager': MapManager,
            'RoutingEngine': RoutingEngine,
            'GeocodingService': GeocodingService,
            'NavigationMapWidget': NavigationMapWidget,
            'RoutePlanningPanel': RoutePlanningPanel,
            'POIManager': POIManager,
            'NavigationDatabase': NavigationDatabase,
            'NavigationSettings': NavigationSettings
        }
    except Exception as e:
        logger.error(f"Failed to import navigation modules: {e}")
        return None

def safe_import_gps_tracker():
    """Safely import GPS tracker dialog."""
    try:
        # Import the GPS tracker dialog we just created
        from gps_tracker_dialog import GPSTrackerDialog
        return GPSTrackerDialog
    except ImportError as e:
        logger.warning(f"GPS Tracker dialog not available: {e}")
        return None

class NavigationMainWindow:
    """Main window for the navigation application."""

    def __init__(self, qt_classes, nav_classes, gps_tracker_class=None):
        """Initialize with safely imported classes."""
        self.qt = qt_classes
        self.nav = nav_classes
        self.gps_tracker_class = gps_tracker_class

        # Create the main window
        self.window = self.qt['QMainWindow']()
        self.window.setWindowTitle("PyNav - Navigation Software")
        self.window.setGeometry(100, 100, 1400, 900)

        # Initialize core components
        self.settings = None
        self.database = None
        self.location_manager = None
        self.map_manager = None
        self.routing_engine = None
        self.geocoding_service = None
        self.map_widget = None

        # GPS tracker dialog
        self.gps_tracker_dialog = None

        # Search and navigation state
        self.current_search_results = []
        self.current_route = None
        self.navigation_active = False

        # New features state
        self.search_history = []
        self.map_bookmarks = []

        # Initialize step by step
        if not self.init_core_components():
            logger.error("Failed to initialize core components")
            return

        if not self.init_ui():
            logger.error("Failed to initialize UI")
            return

        self.setup_connections()
        self.start_timers()

        # Load saved data
        self.load_search_history()
        self.load_map_bookmarks()
        self.setup_search_autocomplete()

        logger.info("Navigation application initialized successfully")

    def init_core_components(self):
        """Initialize core components with error handling."""
        try:
            # Settings
            self.settings = self.nav['NavigationSettings']()
            logger.info("Settings initialized")

            # Database
            self.database = self.nav['NavigationDatabase']()
            logger.info("Database initialized")

            # Initialize bookmarks table
            self.init_bookmarks_table()

            # Location manager
            self.location_manager = self.nav['LocationManager']()
            logger.info("Location manager initialized")

            # Map manager
            self.map_manager = self.nav['MapManager'](self.database)
            logger.info("Map manager initialized")

            # Routing engine
            self.routing_engine = self.nav['RoutingEngine']()
            logger.info("Routing engine initialized")

            # Geocoding service
            self.geocoding_service = self.nav['GeocodingService']()
            logger.info("Geocoding service initialized")

            return True

        except Exception as e:
            logger.error(f"Error initializing core components: {e}")
            logger.error(traceback.format_exc())
            return False

    def init_bookmarks_table(self):
        """Initialize map bookmarks table in database."""
        try:
            with self.database.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS map_bookmarks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        zoom_level INTEGER NOT NULL,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Error creating bookmarks table: {e}")

    def init_ui(self):
        """Initialize UI components with error handling."""
        try:
            # Create menu bar
            self.setup_menu_bar()

            # Create central widget
            central_widget = self.qt['QWidget']()
            self.window.setCentralWidget(central_widget)

            # Main layout
            main_layout = self.qt['QHBoxLayout'](central_widget)

            # Create splitter for resizable panels
            splitter = self.qt['QSplitter'](self.qt['Qt'].Orientation.Horizontal)
            main_layout.addWidget(splitter)

            # Left panel for navigation controls
            self.setup_left_panel(splitter)

            # Main map area
            self.setup_map_area(splitter)

            # Right panel for route info
            self.setup_right_panel(splitter)

            # Set splitter proportions
            splitter.setSizes([300, 800, 300])

            # Status bar
            self.setup_status_bar()

            return True

        except Exception as e:
            logger.error(f"Error initializing UI: {e}")
            logger.error(traceback.format_exc())
            return False

    def setup_menu_bar(self):
        """Set up the menu bar."""
        try:
            menubar = self.window.menuBar()

            # File menu
            file_menu = menubar.addMenu('File')

            # GPS Tracker action
            if self.gps_tracker_class:
                gps_action = self.qt['QAction']('GPS Tracker...', self.window)
                gps_action.setStatusTip('Open GPS device monitor and tracker')
                gps_action.triggered.connect(self.open_gps_tracker)
                file_menu.addAction(gps_action)
                file_menu.addSeparator()

            # Exit action
            exit_action = self.qt['QAction']('Exit', self.window)
            exit_action.setStatusTip('Exit application')
            exit_action.triggered.connect(self.window.close)
            file_menu.addAction(exit_action)

            # Bookmarks menu
            bookmarks_menu = menubar.addMenu('Bookmarks')

            add_bookmark_action = self.qt['QAction']('Add Current View...', self.window)
            add_bookmark_action.setStatusTip('Save current map view as bookmark')
            add_bookmark_action.triggered.connect(self.add_current_bookmark)
            bookmarks_menu.addAction(add_bookmark_action)

            manage_bookmarks_action = self.qt['QAction']('Manage Bookmarks...', self.window)
            manage_bookmarks_action.setStatusTip('Manage saved bookmarks')
            manage_bookmarks_action.triggered.connect(self.manage_bookmarks)
            bookmarks_menu.addAction(manage_bookmarks_action)

            bookmarks_menu.addSeparator()
            self.bookmarks_menu = bookmarks_menu  # Store reference for dynamic updates

            # Tools menu
            tools_menu = menubar.addMenu('Tools')

            copy_location_action = self.qt['QAction']('Copy Current Location', self.window)
            copy_location_action.setStatusTip('Copy current GPS location to clipboard')
            copy_location_action.triggered.connect(self.copy_current_location)
            tools_menu.addAction(copy_location_action)

            tools_menu.addSeparator()

            settings_action = self.qt['QAction']('Settings...', self.window)
            settings_action.setStatusTip('Open application settings')
            settings_action.triggered.connect(self.open_settings)
            tools_menu.addAction(settings_action)

            # Help menu
            help_menu = menubar.addMenu('Help')

            about_action = self.qt['QAction']('About PyNav', self.window)
            about_action.setStatusTip('About this application')
            about_action.triggered.connect(self.show_about)
            help_menu.addAction(about_action)

        except Exception as e:
            logger.error(f"Error setting up menu bar: {e}")

    def setup_left_panel(self, splitter):
        """Set up the left navigation panel."""
        try:
            left_panel = self.qt['QFrame']()
            left_panel.setFrameStyle(self.qt['QFrame'].Shape.StyledPanel)
            left_layout = self.qt['QVBoxLayout'](left_panel)

            # Search section
            search_frame = self.qt['QFrame']()
            search_frame.setFrameStyle(self.qt['QFrame'].Shape.Box)
            search_layout = self.qt['QVBoxLayout'](search_frame)

            search_layout.addWidget(self.qt['QLabel']("Search & Navigation"))

            # Address search with autocomplete
            self.address_input = self.qt['QLineEdit']()
            self.address_input.setPlaceholderText("Enter address or coordinates...")
            self.address_input.returnPressed.connect(self.search_address)
            search_layout.addWidget(self.address_input)

            search_btn = self.qt['QPushButton']("Search")
            search_btn.clicked.connect(self.search_address)
            search_layout.addWidget(search_btn)

            # Search results
            self.search_results_label = self.qt['QLabel']("Search Results:")
            search_layout.addWidget(self.search_results_label)

            self.search_results_list = self.qt['QListWidget']()
            self.search_results_list.setMaximumHeight(120)
            self.search_results_list.itemClicked.connect(self.on_search_result_selected)
            search_layout.addWidget(self.search_results_list)

            # Quick navigation buttons
            nav_buttons_layout = self.qt['QHBoxLayout']()

            self.find_me_btn = self.qt['QPushButton']("Find Me")
            self.find_me_btn.clicked.connect(self.center_on_user)
            nav_buttons_layout.addWidget(self.find_me_btn)

            self.navigate_btn = self.qt['QPushButton']("Navigate")
            self.navigate_btn.clicked.connect(self.start_navigation)
            self.navigate_btn.setEnabled(False)
            nav_buttons_layout.addWidget(self.navigate_btn)

            search_layout.addLayout(nav_buttons_layout)

            # Copy coordinates button
            copy_coords_btn = self.qt['QPushButton']("Copy Current Coords")
            copy_coords_btn.clicked.connect(self.copy_current_location)
            search_layout.addWidget(copy_coords_btn)

            left_layout.addWidget(search_frame)

            # Bookmarks section
            bookmarks_frame = self.qt['QFrame']()
            bookmarks_frame.setFrameStyle(self.qt['QFrame'].Shape.Box)
            bookmarks_layout = self.qt['QVBoxLayout'](bookmarks_frame)

            bookmarks_layout.addWidget(self.qt['QLabel']("Quick Bookmarks"))

            self.bookmarks_combo = self.qt['QComboBox']()
            self.bookmarks_combo.addItem("Select bookmark...")
            self.bookmarks_combo.currentTextChanged.connect(self.goto_bookmark)
            bookmarks_layout.addWidget(self.bookmarks_combo)

            bookmark_buttons_layout = self.qt['QHBoxLayout']()

            add_bookmark_btn = self.qt['QPushButton']("Add")
            add_bookmark_btn.clicked.connect(self.add_current_bookmark)
            bookmark_buttons_layout.addWidget(add_bookmark_btn)

            manage_bookmarks_btn = self.qt['QPushButton']("Manage")
            manage_bookmarks_btn.clicked.connect(self.manage_bookmarks)
            bookmark_buttons_layout.addWidget(manage_bookmarks_btn)

            bookmarks_layout.addLayout(bookmark_buttons_layout)
            left_layout.addWidget(bookmarks_frame)

            # GPS Tracker button (prominent placement)
            if self.gps_tracker_class:
                gps_frame = self.qt['QFrame']()
                gps_frame.setFrameStyle(self.qt['QFrame'].Shape.Box)
                gps_layout = self.qt['QVBoxLayout'](gps_frame)

                gps_layout.addWidget(self.qt['QLabel']("GPS Monitoring"))

                self.gps_tracker_btn = self.qt['QPushButton']("Open GPS Tracker")
                self.gps_tracker_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
                self.gps_tracker_btn.clicked.connect(self.open_gps_tracker)
                gps_layout.addWidget(self.gps_tracker_btn)

                left_layout.addWidget(gps_frame)

            # Location source selection
            location_frame = self.qt['QFrame']()
            location_frame.setFrameStyle(self.qt['QFrame'].Shape.Box)
            location_layout = self.qt['QVBoxLayout'](location_frame)

            location_layout.addWidget(self.qt['QLabel']("Location Source"))
            self.location_source = self.qt['QComboBox']()
            if self.location_manager:
                sources = self.location_manager.get_available_sources()
                self.location_source.addItems(sources)
            self.location_source.currentTextChanged.connect(self.change_location_source)
            location_layout.addWidget(self.location_source)

            self.location_status = self.qt['QLabel']("Status: Starting...")
            location_layout.addWidget(self.location_status)

            left_layout.addWidget(location_frame)
            left_layout.addStretch()
            splitter.addWidget(left_panel)

        except Exception as e:
            logger.error(f"Error setting up left panel: {e}")

    def setup_map_area(self, splitter):
        """Set up the main map display area."""
        try:
            map_frame = self.qt['QFrame']()
            map_layout = self.qt['QVBoxLayout'](map_frame)
            map_layout.setContentsMargins(0, 0, 0, 0)

            # Map controls toolbar
            controls_layout = self.qt['QHBoxLayout']()

            # Zoom controls
            zoom_layout = self.qt['QHBoxLayout']()

            self.zoom_in_btn = self.qt['QPushButton']("+")
            self.zoom_in_btn.setFixedSize(30, 30)
            self.zoom_in_btn.setStyleSheet("QPushButton { font-weight: bold; font-size: 16px; }")
            self.zoom_in_btn.clicked.connect(self.zoom_in)
            zoom_layout.addWidget(self.zoom_in_btn)

            self.zoom_out_btn = self.qt['QPushButton']("-")
            self.zoom_out_btn.setFixedSize(30, 30)
            self.zoom_out_btn.setStyleSheet("QPushButton { font-weight: bold; font-size: 16px; }")
            self.zoom_out_btn.clicked.connect(self.zoom_out)
            zoom_layout.addWidget(self.zoom_out_btn)

            controls_layout.addLayout(zoom_layout)

            # Layer controls
            self.satellite_cb = self.qt['QCheckBox']("Satellite")
            self.satellite_cb.stateChanged.connect(self.toggle_satellite_layer)
            controls_layout.addWidget(self.satellite_cb)

            self.traffic_cb = self.qt['QCheckBox']("Traffic")
            self.traffic_cb.stateChanged.connect(self.toggle_traffic_layer)
            controls_layout.addWidget(self.traffic_cb)

            self.poi_cb = self.qt['QCheckBox']("POI")
            self.poi_cb.setChecked(True)
            self.poi_cb.stateChanged.connect(self.toggle_poi_layer)
            controls_layout.addWidget(self.poi_cb)

            controls_layout.addStretch()

            # Clear route button
            self.clear_route_btn = self.qt['QPushButton']("Clear Route")
            self.clear_route_btn.clicked.connect(self.clear_route)
            self.clear_route_btn.setEnabled(False)
            controls_layout.addWidget(self.clear_route_btn)

            # Map type selector
            self.map_type = self.qt['QComboBox']()
            self.map_type.addItems([
                "OpenStreetMap", "Satellite", "Hybrid", "Terrain",
                "OpenTopoMap", "CyclOSM"
            ])
            self.map_type.currentTextChanged.connect(self.change_map_type)
            controls_layout.addWidget(self.qt['QLabel']("Map Type:"))
            controls_layout.addWidget(self.map_type)

            map_layout.addLayout(controls_layout)

            # Main map widget
            try:
                self.map_widget = self.nav['NavigationMapWidget'](
                    self.map_manager,
                    self.location_manager,
                    self.routing_engine
                )

                # Connect map widget signals for coordinate copying
                self.map_widget.location_clicked.connect(self.on_map_location_clicked)

                map_layout.addWidget(self.map_widget)
                logger.info("Map widget created successfully")

                # Center on user's detected location if available
                if self.location_manager:
                    current_location = self.location_manager.get_current_location()
                    if current_location:
                        self.map_widget.center_on_location(
                            current_location['latitude'],
                            current_location['longitude']
                        )
                        logger.info(f"Centered map on detected location: {current_location['latitude']:.4f}, {current_location['longitude']:.4f}")
                    else:
                        # Default to Austin, TX (from your IP location)
                        self.map_widget.center_on_location(30.2625, -97.7463)
                        logger.info("Centered map on default location (Austin, TX)")

            except Exception as e:
                logger.error(f"Error creating map widget: {e}")
                # Fallback to placeholder if map widget fails
                placeholder = self.qt['QLabel']("Map widget failed to load. Check console for errors.")
                placeholder.setAlignment(self.qt['Qt'].AlignmentFlag.AlignCenter)
                placeholder.setStyleSheet("background-color: #ffe6e6; border: 1px solid #ff9999; color: #cc0000;")
                map_layout.addWidget(placeholder)

            splitter.addWidget(map_frame)

        except Exception as e:
            logger.error(f"Error setting up map area: {e}")

    def setup_right_panel(self, splitter):
        """Set up the right information panel."""
        try:
            right_panel = self.qt['QFrame']()
            right_panel.setFrameStyle(self.qt['QFrame'].Shape.StyledPanel)
            right_layout = self.qt['QVBoxLayout'](right_panel)

            # Tab widget for different info panels
            self.info_tabs = self.qt['QTabWidget']()

            # Navigation tab
            nav_widget = self.qt['QWidget']()
            nav_layout = self.qt['QVBoxLayout'](nav_widget)

            # Route summary
            self.route_summary = self.qt['QLabel']("No route calculated")
            self.route_summary.setWordWrap(True)
            self.route_summary.setStyleSheet("padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;")
            nav_layout.addWidget(self.route_summary)

            # Navigation instructions
            nav_layout.addWidget(self.qt['QLabel']("Turn-by-turn directions:"))
            self.navigation_instructions = self.qt['QListWidget']()
            self.navigation_instructions.setMaximumHeight(200)
            nav_layout.addWidget(self.navigation_instructions)

            nav_layout.addStretch()
            self.info_tabs.addTab(nav_widget, "Navigation")

            # GPS Status tab
            gps_widget = self.qt['QWidget']()
            gps_layout = self.qt['QVBoxLayout'](gps_widget)

            self.gps_info_label = self.qt['QLabel']("GPS Status:\nNo GPS data available")
            self.gps_info_label.setWordWrap(True)
            gps_layout.addWidget(self.gps_info_label)

            if self.gps_tracker_class:
                open_tracker_btn = self.qt['QPushButton']("Open GPS Tracker")
                open_tracker_btn.clicked.connect(self.open_gps_tracker)
                gps_layout.addWidget(open_tracker_btn)

            gps_layout.addStretch()
            self.info_tabs.addTab(gps_widget, "GPS Status")

            # Route Planning tab - embed the route planning panel
            try:
                self.route_planning_panel = self.nav['RoutePlanningPanel']()
                # Connect route planning signals
                self.route_planning_panel.route_requested.connect(self.calculate_route_from_panel)
                self.route_planning_panel.route_loaded.connect(self.display_loaded_route)
                self.info_tabs.addTab(self.route_planning_panel, "Route Planning")
            except Exception as e:
                logger.error(f"Error creating route planning panel: {e}")
                # Fallback info tab
                info_widget = self.qt['QWidget']()
                info_layout = self.qt['QVBoxLayout'](info_widget)
                self.info_label = self.qt['QLabel']("PyNav Navigation Software\n\nFeatures:\n• Interactive mapping\n• GPS tracking\n• Route planning\n• Points of interest")
                self.info_label.setWordWrap(True)
                info_layout.addWidget(self.info_label)
                info_layout.addStretch()
                self.info_tabs.addTab(info_widget, "Info")

            right_layout.addWidget(self.info_tabs)
            splitter.addWidget(right_panel)

        except Exception as e:
            logger.error(f"Error setting up right panel: {e}")

    def setup_status_bar(self):
        """Set up the status bar."""
        try:
            self.status_bar = self.window.statusBar()

            # Location info
            self.location_label = self.qt['QLabel']("Location: Unknown")
            self.status_bar.addWidget(self.location_label)

            self.status_bar.addPermanentWidget(self.qt['QLabel'](" | "))

            # GPS status
            self.gps_status = self.qt['QLabel']("GPS: Offline")
            self.status_bar.addPermanentWidget(self.gps_status)

            # GPS device count
            if self.location_manager:
                sources = self.location_manager.get_available_sources()
                gps_count = len([s for s in sources if 'GPS' in s])
                self.status_bar.addPermanentWidget(self.qt['QLabel'](f" | GPS Devices: {gps_count}"))

        except Exception as e:
            logger.error(f"Error setting up status bar: {e}")

    def setup_connections(self):
        """Set up signal connections with error handling."""
        try:
            if self.location_manager:
                self.location_manager.location_changed.connect(self.on_location_changed)
                self.location_manager.status_changed.connect(self.on_location_status_changed)

            # Connect geocoding service signals
            if self.geocoding_service:
                self.geocoding_service.results_ready.connect(self.on_search_results)
                self.geocoding_service.operation_failed.connect(self.on_search_failed)

            # Connect routing engine signals
            if self.routing_engine:
                self.routing_engine.route_calculated.connect(self.on_route_calculated)
                self.routing_engine.calculation_failed.connect(self.on_route_calculation_failed)

            logger.info("Signal connections setup completed")

        except Exception as e:
            logger.error(f"Error setting up connections: {e}")

    def start_timers(self):
        """Start update timers with error handling."""
        try:
            # Location update timer
            self.location_timer = self.qt['QTimer']()
            self.location_timer.timeout.connect(self.update_location)
            self.location_timer.start(2000)  # Update every 2 seconds

            logger.info("Timers started")

        except Exception as e:
            logger.error(f"Error starting timers: {e}")

    # NEW FEATURES IMPLEMENTATION

    def load_search_history(self):
        """Load search history from database."""
        try:
            history = self.database.get_search_history(20)  # Get last 20 searches
            self.search_history = [item['query'] for item in history]
            logger.info(f"Loaded {len(self.search_history)} search history items")
        except Exception as e:
            logger.error(f"Error loading search history: {e}")
            self.search_history = []

    def setup_search_autocomplete(self):
        """Set up autocomplete for search input."""
        try:
            if self.search_history:
                model = self.qt['QStringListModel'](self.search_history)
                completer = self.qt['QCompleter'](model)
                completer.setCaseSensitivity(self.qt['Qt'].CaseSensitivity.CaseInsensitive)
                self.address_input.setCompleter(completer)
                logger.info("Search autocomplete configured")
        except Exception as e:
            logger.error(f"Error setting up autocomplete: {e}")

    def add_to_search_history(self, query):
        """Add search query to history."""
        try:
            if query and query not in self.search_history:
                self.search_history.insert(0, query)
                self.search_history = self.search_history[:20]  # Keep only 20 items

                # Update autocomplete
                self.setup_search_autocomplete()

                # Save to database
                self.database.add_search_history(query)
                logger.debug(f"Added to search history: {query}")
        except Exception as e:
            logger.error(f"Error adding to search history: {e}")

    def copy_current_location(self):
        """Copy current GPS location to clipboard."""
        try:
            location = self.location_manager.get_current_location()
            if location:
                lat = location['latitude']
                lon = location['longitude']
                coords_text = f"{lat:.6f}, {lon:.6f}"

                clipboard = self.qt['QApplication'].clipboard()
                clipboard.setText(coords_text)

                self.status_bar.showMessage(f"Copied coordinates: {coords_text}", 3000)
                logger.info(f"Copied coordinates to clipboard: {coords_text}")
            else:
                self.qt['QMessageBox'].information(
                    self.window, "No Location",
                    "Current location not available"
                )
        except Exception as e:
            logger.error(f"Error copying location: {e}")

    def on_map_location_clicked(self, lat, lon):
        """Handle map clicks for coordinate copying."""
        try:
            coords_text = f"{lat:.6f}, {lon:.6f}"

            # Show context menu
            menu = self.qt['QMenu'](self.window)

            copy_action = self.qt['QAction'](f"Copy coordinates ({coords_text})", self.window)
            copy_action.triggered.connect(lambda: self.copy_coordinates_to_clipboard(coords_text))
            menu.addAction(copy_action)

            search_action = self.qt['QAction']("Search nearby", self.window)
            search_action.triggered.connect(lambda: self.reverse_geocode_location(lat, lon))
            menu.addAction(search_action)

            # Show menu at cursor position would be ideal, but for now just show info
            self.status_bar.showMessage(f"Clicked: {coords_text} (Right-click map for options)", 5000)

        except Exception as e:
            logger.error(f"Error handling map click: {e}")

    def copy_coordinates_to_clipboard(self, coords_text):
        """Copy coordinates to clipboard."""
        try:
            clipboard = self.qt['QApplication'].clipboard()
            clipboard.setText(coords_text)
            self.status_bar.showMessage(f"Copied: {coords_text}", 3000)
        except Exception as e:
            logger.error(f"Error copying coordinates: {e}")

    def reverse_geocode_location(self, lat, lon):
        """Reverse geocode a clicked location."""
        try:
            self.geocoding_service.reverse_geocode(lat, lon)
        except Exception as e:
            logger.error(f"Error reverse geocoding: {e}")

    def load_map_bookmarks(self):
        """Load map bookmarks from database."""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM map_bookmarks ORDER BY name")
                self.map_bookmarks = [dict(row) for row in cursor.fetchall()]

            # Update UI
            self.update_bookmarks_ui()
            logger.info(f"Loaded {len(self.map_bookmarks)} bookmarks")
        except Exception as e:
            logger.error(f"Error loading bookmarks: {e}")
            self.map_bookmarks = []

    def update_bookmarks_ui(self):
        """Update bookmarks UI elements."""
        try:
            # Update combo box
            self.bookmarks_combo.clear()
            self.bookmarks_combo.addItem("Select bookmark...")
            for bookmark in self.map_bookmarks:
                self.bookmarks_combo.addItem(bookmark['name'])

            # Update menu
            # Clear existing bookmark actions (keep the static ones)
            for action in self.bookmarks_menu.actions()[2:]:  # Skip first 2 static actions
                self.bookmarks_menu.removeAction(action)

            # Add bookmark actions
            if self.map_bookmarks:
                for bookmark in self.map_bookmarks[:10]:  # Limit to 10 in menu
                    action = self.qt['QAction'](bookmark['name'], self.window)
                    action.triggered.connect(lambda checked, b=bookmark: self.goto_bookmark_data(b))
                    self.bookmarks_menu.addAction(action)

        except Exception as e:
            logger.error(f"Error updating bookmarks UI: {e}")

    def add_current_bookmark(self):
        """Add current map view as bookmark."""
        try:
            if not self.map_widget:
                return

            # Get current map state
            lat = self.map_widget.center_lat
            lon = self.map_widget.center_lon
            zoom = self.map_widget.zoom_level

            # Get bookmark name from user
            name, ok = self.qt['QInputDialog'].getText(
                self.window, 'Add Bookmark',
                'Enter bookmark name:',
                text=f'Bookmark {len(self.map_bookmarks) + 1}'
            )

            if ok and name.strip():
                # Save to database
                with self.database.get_connection() as conn:
                    conn.execute("""
                        INSERT INTO map_bookmarks (name, latitude, longitude, zoom_level)
                        VALUES (?, ?, ?, ?)
                    """, (name.strip(), lat, lon, zoom))
                    conn.commit()

                # Reload bookmarks
                self.load_map_bookmarks()

                self.status_bar.showMessage(f"Added bookmark: {name.strip()}", 3000)
                logger.info(f"Added bookmark: {name.strip()} at {lat:.6f}, {lon:.6f}")

        except Exception as e:
            logger.error(f"Error adding bookmark: {e}")

    def goto_bookmark(self, bookmark_name):
        """Go to selected bookmark."""
        try:
            if bookmark_name == "Select bookmark...":
                return

            for bookmark in self.map_bookmarks:
                if bookmark['name'] == bookmark_name:
                    self.goto_bookmark_data(bookmark)
                    break

        except Exception as e:
            logger.error(f"Error going to bookmark: {e}")

    def goto_bookmark_data(self, bookmark):
        """Go to bookmark using bookmark data."""
        try:
            if self.map_widget:
                self.map_widget.center_on_location(bookmark['latitude'], bookmark['longitude'])
                self.map_widget.set_zoom_level(bookmark['zoom_level'])

                self.status_bar.showMessage(f"Went to bookmark: {bookmark['name']}", 3000)
                logger.info(f"Navigated to bookmark: {bookmark['name']}")

        except Exception as e:
            logger.error(f"Error navigating to bookmark: {e}")

    def manage_bookmarks(self):
        """Open bookmark management dialog."""
        try:
            # Simple management for now - show list with delete option
            if not self.map_bookmarks:
                self.qt['QMessageBox'].information(
                    self.window, "No Bookmarks",
                    "No bookmarks saved yet. Use 'Add Current View' to create bookmarks."
                )
                return

            # Create simple list dialog
            bookmark_names = [f"{b['name']} ({b['latitude']:.4f}, {b['longitude']:.4f})"
                            for b in self.map_bookmarks]

            item, ok = self.qt['QInputDialog'].getItem(
                self.window, 'Manage Bookmarks',
                'Select bookmark to delete:',
                bookmark_names, 0, False
            )

            if ok and item:
                # Find and delete bookmark
                for i, bookmark in enumerate(self.map_bookmarks):
                    if bookmark_names[i] == item:
                        reply = self.qt['QMessageBox'].question(
                            self.window, 'Delete Bookmark',
                            f"Delete bookmark '{bookmark['name']}'?",
                            self.qt['QMessageBox'].StandardButton.Yes |
                            self.qt['QMessageBox'].StandardButton.No
                        )

                        if reply == self.qt['QMessageBox'].StandardButton.Yes:
                            with self.database.get_connection() as conn:
                                conn.execute("DELETE FROM map_bookmarks WHERE id = ?",
                                           (bookmark['id'],))
                                conn.commit()

                            self.load_map_bookmarks()
                            self.status_bar.showMessage(f"Deleted bookmark: {bookmark['name']}", 3000)
                        break

        except Exception as e:
            logger.error(f"Error managing bookmarks: {e}")

    def zoom_in(self):
        """Zoom in on map."""
        try:
            if self.map_widget:
                current_zoom = self.map_widget.zoom_level
                self.map_widget.set_zoom_level(min(19, current_zoom + 1))
        except Exception as e:
            logger.error(f"Error zooming in: {e}")

    def zoom_out(self):
        """Zoom out on map."""
        try:
            if self.map_widget:
                current_zoom = self.map_widget.zoom_level
                self.map_widget.set_zoom_level(max(1, current_zoom - 1))
        except Exception as e:
            logger.error(f"Error zooming out: {e}")

    # EXISTING SEARCH AND NAVIGATION METHODS (keep all existing functionality)

    def search_address(self):
        """Handle search functionality."""
        try:
            query = self.address_input.text().strip()
            if not query:
                return

            logger.info(f"Searching for: {query}")

            # Add to search history
            self.add_to_search_history(query)

            # Clear previous results
            self.current_search_results = []
            self.search_results_list.clear()
            self.navigate_btn.setEnabled(False)

            # Show searching status
            self.search_results_list.addItem("Searching...")

            # Start geocoding search
            self.geocoding_service.geocode_address(query)

        except Exception as e:
            logger.error(f"Error handling search: {e}")
            self.qt['QMessageBox'].warning(
                self.window, "Search Error", f"Search failed: {str(e)}"
            )

    def on_search_results(self, results):
        """Handle search results from geocoding service."""
        try:
            self.search_results_list.clear()
            self.current_search_results = results

            if not results:
                self.search_results_list.addItem("No results found")
                return

            # Add results to list
            for i, result in enumerate(results[:5]):  # Limit to 5 results
                item_text = f"{i+1}. {result.address}"
                if result.confidence < 0.5:
                    item_text += " (low confidence)"
                self.search_results_list.addItem(item_text)

            # Automatically show first result on map
            if results:
                first_result = results[0]
                self.show_search_result_on_map(first_result)
                self.navigate_btn.setEnabled(True)

            logger.info(f"Found {len(results)} search results")

        except Exception as e:
            logger.error(f"Error handling search results: {e}")

    def on_search_failed(self, error):
        """Handle search failure."""
        self.search_results_list.clear()
        self.search_results_list.addItem(f"Search failed: {error}")
        logger.error(f"Search failed: {error}")

    def on_search_result_selected(self, item):
        """Handle selection of a search result."""
        try:
            # Get the index from the item text
            text = item.text()
            if text.startswith(('1.', '2.', '3.', '4.', '5.')):
                index = int(text[0]) - 1
                if 0 <= index < len(self.current_search_results):
                    result = self.current_search_results[index]
                    self.show_search_result_on_map(result)
                    self.navigate_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"Error handling search result selection: {e}")

    def show_search_result_on_map(self, result):
        """Show a search result on the map."""
        try:
            if self.map_widget:
                # Clear previous search markers
                self.map_widget.clear_search_markers()

                # Add marker for this result
                self.map_widget.add_search_marker(
                    result.latitude,
                    result.longitude,
                    result.address
                )

                # Center map on result
                self.map_widget.center_on_location(result.latitude, result.longitude)

                logger.info(f"Showing search result: {result.address}")

        except Exception as e:
            logger.error(f"Error showing search result on map: {e}")

    # Navigation functionality
    def start_navigation(self):
        """Start navigation to selected search result."""
        try:
            if not self.current_search_results:
                self.qt['QMessageBox'].information(
                    self.window, "No Destination",
                    "Please search for a destination first."
                )
                return

            # Get current location
            current_location = self.location_manager.get_current_location()
            if not current_location:
                self.qt['QMessageBox'].information(
                    self.window, "No Location",
                    "Current location not available. Please enable location services."
                )
                return

            # Use first search result as destination
            destination = self.current_search_results[0]

            # Create location dictionaries for routing
            start = {
                'latitude': current_location['latitude'],
                'longitude': current_location['longitude'],
                'address': 'Current Location'
            }

            end = {
                'latitude': destination.latitude,
                'longitude': destination.longitude,
                'address': destination.address
            }

            logger.info(f"Starting navigation from {start['address']} to {end['address']}")

            # Calculate route
            self.routing_engine.calculate_route(start, end)

            # Update UI
            self.route_summary.setText("Calculating route...")
            self.navigation_active = True

        except Exception as e:
            logger.error(f"Error starting navigation: {e}")
            self.qt['QMessageBox'].critical(
                self.window, "Navigation Error", f"Failed to start navigation: {str(e)}"
            )

    def calculate_route_from_panel(self, start, end):
        """Calculate route from route planning panel."""
        try:
            logger.info(f"Calculating route from panel: {start} to {end}")
            self.routing_engine.calculate_route(start, end)
        except Exception as e:
            logger.error(f"Error calculating route from panel: {e}")

    def display_loaded_route(self, route_data):
        """Display a loaded route."""
        try:
            self.current_route = route_data
            if self.map_widget:
                self.map_widget.display_route(route_data)
            self.update_route_display(route_data)
            self.clear_route_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"Error displaying loaded route: {e}")

    def on_route_calculated(self, route):
        """Handle successful route calculation."""
        try:
            self.current_route = route

            # Display route on map
            if self.map_widget:
                self.map_widget.display_route(route)

            # Update route summary
            self.update_route_display(route)

            # Enable clear route button
            self.clear_route_btn.setEnabled(True)

            # Update route planning panel if it exists
            if hasattr(self, 'route_planning_panel'):
                self.route_planning_panel.on_route_calculated(route)

            logger.info(f"Route calculated: {route['distance']/1000:.1f} km, {route['duration']/60:.0f} min")

        except Exception as e:
            logger.error(f"Error handling route calculation: {e}")

    def on_route_calculation_failed(self, error):
        """Handle route calculation failure."""
        self.route_summary.setText(f"Route calculation failed: {error}")
        logger.error(f"Route calculation failed: {error}")

        self.qt['QMessageBox'].warning(
            self.window, "Route Calculation Failed",
            f"Could not calculate route: {error}"
        )

    def update_route_display(self, route):
        """Update route information display."""
        try:
            distance = route.get('distance', 0)
            duration = route.get('duration', 0)
            service = route.get('service', 'Unknown')

            # Format distance
            if distance > 1000:
                distance_text = f"{distance/1000:.1f} km"
            else:
                distance_text = f"{distance:.0f} m"

            # Format duration
            if duration > 3600:
                hours = int(duration // 3600)
                minutes = int((duration % 3600) // 60)
                duration_text = f"{hours}h {minutes}m"
            else:
                minutes = int(duration // 60)
                duration_text = f"{minutes}m"

            # Update summary
            summary = f"Route calculated:\n"
            summary += f"Distance: {distance_text}\n"
            summary += f"Duration: {duration_text}\n"
            summary += f"Via: {service}"

            self.route_summary.setText(summary)

            # Update turn-by-turn instructions
            self.navigation_instructions.clear()
            steps = route.get('steps', [])
            for i, step in enumerate(steps[:10]):  # Show first 10 steps
                if hasattr(step, 'instruction'):
                    instruction = step.instruction
                else:
                    instruction = f"Step {i+1}"

                self.navigation_instructions.addItem(f"{i+1}. {instruction}")

        except Exception as e:
            logger.error(f"Error updating route display: {e}")

    def clear_route(self):
        """Clear current route."""
        try:
            self.current_route = None
            self.navigation_active = False

            # Clear map
            if self.map_widget:
                self.map_widget.display_route(None)

            # Clear UI
            self.route_summary.setText("No route calculated")
            self.navigation_instructions.clear()
            self.clear_route_btn.setEnabled(False)

            logger.info("Route cleared")

        except Exception as e:
            logger.error(f"Error clearing route: {e}")

    # KEEP ALL EXISTING METHODS (location updates, GPS tracker, etc.)

    def update_location(self):
        """Update location with error handling."""
        try:
            if self.location_manager:
                location = self.location_manager.get_current_location()
                if location:
                    lat = location.get('latitude', 0)
                    lon = location.get('longitude', 0)
                    source = location.get('source', 'Unknown')
                    accuracy = location.get('accuracy', 0)

                    # Update status bar
                    self.location_label.setText(f"Location: {lat:.6f}, {lon:.6f} ({source})")

                    # Update GPS info in right panel
                    gps_info = f"GPS Status:\nSource: {source}\nLatitude: {lat:.6f}°\nLongitude: {lon:.6f}°"
                    if accuracy:
                        if accuracy < 1000:
                            gps_info += f"\nAccuracy: {accuracy:.1f}m"
                        else:
                            gps_info += f"\nAccuracy: {accuracy/1000:.1f}km"

                    self.gps_info_label.setText(gps_info)

                    # Update map widget with new location
                    if self.map_widget:
                        self.map_widget.update_user_location(location)

        except Exception as e:
            logger.error(f"Error updating location: {e}")

    def on_location_changed(self, location):
        """Handle location changes."""
        try:
            logger.info(f"Location changed: {location}")
            if self.map_widget:
                # Center map on new location if this is the first location update
                if not hasattr(self, '_first_location_set'):
                    self.map_widget.center_on_location(
                        location['latitude'],
                        location['longitude']
                    )
                    self._first_location_set = True
                    logger.info("Centered map on first location update")
        except Exception as e:
            logger.error(f"Error handling location change: {e}")

    def on_location_status_changed(self, status):
        """Handle status changes."""
        try:
            self.gps_status.setText(f"GPS: {status}")
            self.location_status.setText(f"Status: {status}")
            logger.info(f"Status changed: {status}")
        except Exception as e:
            logger.error(f"Error handling status change: {e}")

    def center_on_user(self):
        """Center map on user's current location."""
        try:
            if self.location_manager and self.map_widget:
                location = self.location_manager.get_current_location()
                if location:
                    self.map_widget.center_on_location(
                        location['latitude'],
                        location['longitude']
                    )
                    logger.info("Centered map on user location")
                else:
                    self.qt['QMessageBox'].information(
                        self.window, "Location Unavailable",
                        "Current location is not available"
                    )
        except Exception as e:
            logger.error(f"Error centering on user: {e}")

    def change_location_source(self, source):
        """Change the active location source."""
        try:
            if self.location_manager:
                success = self.location_manager.set_active_source(source)
                logger.info(f"Location source changed to: {source}, success: {success}")
        except Exception as e:
            logger.error(f"Error changing location source: {e}")

    def change_map_type(self, map_type):
        """Change the map tile source."""
        try:
            if self.map_widget:
                self.map_widget.set_map_type(map_type)
                logger.info(f"Map type changed to: {map_type}")
        except Exception as e:
            logger.error(f"Error changing map type: {e}")

    def toggle_satellite_layer(self, enabled):
        """Toggle satellite imagery layer."""
        try:
            if self.map_widget:
                self.map_widget.toggle_layer('satellite', enabled)
        except Exception as e:
            logger.error(f"Error toggling satellite layer: {e}")

    def toggle_traffic_layer(self, enabled):
        """Toggle traffic information layer."""
        try:
            if self.map_widget:
                self.map_widget.toggle_layer('traffic', enabled)
        except Exception as e:
            logger.error(f"Error toggling traffic layer: {e}")

    def toggle_poi_layer(self, enabled):
        """Toggle points of interest layer."""
        try:
            if self.map_widget:
                self.map_widget.toggle_layer('poi', enabled)
        except Exception as e:
            logger.error(f"Error toggling POI layer: {e}")

    def open_gps_tracker(self):
        """Open the GPS tracker dialog."""
        try:
            if not self.gps_tracker_class:
                self.qt['QMessageBox'].warning(
                    self.window, "GPS Tracker Unavailable",
                    "GPS Tracker dialog is not available."
                )
                return

            if not self.gps_tracker_dialog:
                self.gps_tracker_dialog = self.gps_tracker_class(self.location_manager, self.window)

            self.gps_tracker_dialog.show()
            self.gps_tracker_dialog.raise_()
            self.gps_tracker_dialog.activateWindow()

            logger.info("GPS Tracker dialog opened")

        except Exception as e:
            logger.error(f"Error opening GPS tracker: {e}")
            self.qt['QMessageBox'].critical(
                self.window, "Error", f"Failed to open GPS tracker: {e}"
            )

    def open_settings(self):
        """Open settings dialog."""
        try:
            self.qt['QMessageBox'].information(
                self.window, "Settings", "Settings dialog coming soon!"
            )
        except Exception as e:
            logger.error(f"Error opening settings: {e}")

    def show_about(self):
        """Show about dialog."""
        try:
            about_text = """
            <h2>PyNav Navigation Software</h2>
            <p><b>Version:</b> 1.0.0</p>
            <p><b>Description:</b> Complete GPS navigation and tracking solution</p>

            <p><b>Features:</b></p>
            <ul>
            <li>Interactive mapping with multiple tile sources</li>
            <li>GPS device detection and monitoring</li>
            <li>Real-time location tracking</li>
            <li>Route planning and navigation</li>
            <li>Address search with autocomplete</li>
            <li>Map bookmarks and favorites</li>
            <li>Coordinate copying and sharing</li>
            <li>Points of interest management</li>
            <li>Track recording and data logging</li>
            </ul>

            <p><b>GPS Devices Detected:</b> {gps_count}</p>

            <p>Built with PyQt6 and Python</p>
            """.format(
                gps_count=len([s for s in self.location_manager.get_available_sources() if 'GPS' in s])
                if self.location_manager else 0
            )

            self.qt['QMessageBox'].about(self.window, "About PyNav", about_text)

        except Exception as e:
            logger.error(f"Error showing about dialog: {e}")

    def show(self):
        """Show the main window."""
        self.window.show()

    def cleanup(self):
        """Cleanup resources."""
        try:
            # Close GPS tracker dialog
            if self.gps_tracker_dialog:
                self.gps_tracker_dialog.close()

            if self.location_manager:
                self.location_manager.cleanup()
            if self.database:
                self.database.close()
            logger.info("Application cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """Main application entry point."""
    try:
        logger.info("Starting PyNav Navigation Application")

        # Check dependencies first
        if not check_dependencies():
            print("Missing required dependencies. Please install them first.")
            return 1

        # Import Qt components
        qt_classes = safe_import_qt()
        if not qt_classes:
            logger.error("Failed to import PyQt6 components")
            return 1

        # Import navigation components
        nav_classes = safe_import_navigation()
        if not nav_classes:
            logger.error("Failed to import navigation components")
            return 1

        # Import GPS tracker (optional)
        gps_tracker_class = safe_import_gps_tracker()

        # Create Qt application
        app = qt_classes['QApplication'](sys.argv)
        app.setApplicationName("PyNav")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("Navigation Software")

        logger.info("Qt application created")

        # Create main window
        main_window = NavigationMainWindow(qt_classes, nav_classes, gps_tracker_class)

        if main_window.settings is None:
            logger.error("Failed to initialize main window")
            return 1

        # Show window
        main_window.show()
        logger.info("Main window shown")

        # Run event loop
        try:
            result = app.exec()
            logger.info("Application event loop finished")

            # Cleanup
            main_window.cleanup()

            return result

        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
            main_window.cleanup()
            return 0

    except Exception as e:
        error_msg = f"Fatal error in main application: {e}"
        logger.critical(error_msg)
        logger.critical(traceback.format_exc())

        # Create crash log
        try:
            create_crash_log(e, {
                'function': 'main',
                'python_version': sys.version,
                'platform': sys.platform
            })
        except:
            pass

        print(error_msg)
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
