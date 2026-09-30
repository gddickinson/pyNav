"""
Enhanced OfflineMapsDialog - Integrated hang prevention with existing functionality
"""

import time
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                           QWidget, QLabel, QPushButton, QLineEdit, QComboBox,
                           QListWidget, QListWidgetItem, QProgressBar, QGroupBox,
                           QFormLayout, QSpinBox, QDoubleSpinBox, QTextEdit,
                           QMessageBox, QFileDialog, QSplitter, QFrame,
                           QTableWidget, QTableWidgetItem, QHeaderView,
                           QSlider, QCheckBox, QApplication)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush

from navigation.core.map_manager import TileServer
from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

class AreaSelectorWidget(QWidget):
    """Widget for selecting map areas on a simple coordinate display."""

    area_selected = pyqtSignal(float, float, float, float)  # min_lat, min_lon, max_lat, max_lon

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)

        # World bounds
        self.world_min_lat = -85
        self.world_max_lat = 85
        self.world_min_lon = -180
        self.world_max_lon = 180

        # Selection state
        self.selection_start = None
        self.selection_end = None
        self.is_selecting = False

        # Current view
        self.view_min_lat = -85
        self.view_max_lat = 85
        self.view_min_lon = -180
        self.view_max_lon = 180

        self.setMouseTracking(True)

    def set_view(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float):
        """Set the current view bounds."""
        self.view_min_lat = max(-85, min_lat)
        self.view_max_lat = min(85, max_lat)
        self.view_min_lon = max(-180, min_lon)
        self.view_max_lon = min(180, max_lon)
        self.update()

    def screen_to_geo(self, x: int, y: int) -> tuple[float, float]:
        """Convert screen coordinates to geographic coordinates."""
        lat_range = self.view_max_lat - self.view_min_lat
        lon_range = self.view_max_lon - self.view_min_lon

        lat = self.view_max_lat - (y / self.height()) * lat_range
        lon = self.view_min_lon + (x / self.width()) * lon_range

        return (lat, lon)

    def geo_to_screen(self, lat: float, lon: float) -> tuple[int, int]:
        """Convert geographic coordinates to screen coordinates."""
        lat_range = self.view_max_lat - self.view_min_lat
        lon_range = self.view_max_lon - self.view_min_lon

        x = int(((lon - self.view_min_lon) / lon_range) * self.width())
        y = int(((self.view_max_lat - lat) / lat_range) * self.height())

        return (x, y)

    def mousePressEvent(self, event):
        """Handle mouse press to start area selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse move during selection."""
        if self.is_selecting and self.selection_start:
            self.selection_end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release to complete selection."""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.selection_end = event.pos()
            self.is_selecting = False

            # Convert to geographic coordinates
            if self.selection_start and self.selection_end:
                start_lat, start_lon = self.screen_to_geo(
                    self.selection_start.x(), self.selection_start.y()
                )
                end_lat, end_lon = self.screen_to_geo(
                    self.selection_end.x(), self.selection_end.y()
                )

                # Ensure proper min/max order
                min_lat = min(start_lat, end_lat)
                max_lat = max(start_lat, end_lat)
                min_lon = min(start_lon, end_lon)
                max_lon = max(start_lon, end_lon)

                self.area_selected.emit(min_lat, min_lon, max_lat, max_lon)

            self.update()

    def paintEvent(self, event):
        """Paint the area selector."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), QColor(240, 248, 255))

        # Draw world outline
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

        # Draw grid lines
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        for i in range(1, 4):
            # Vertical lines
            x = int(i * self.width() / 4)
            painter.drawLine(x, 0, x, self.height())

            # Horizontal lines
            y = int(i * self.height() / 4)
            painter.drawLine(0, y, self.width(), y)

        # Draw coordinate labels
        painter.setPen(QColor(80, 80, 80))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        # Corner coordinates
        painter.drawText(5, 15, f"{self.view_max_lat:.1f}°, {self.view_min_lon:.1f}°")
        painter.drawText(self.width() - 80, 15, f"{self.view_max_lat:.1f}°, {self.view_max_lon:.1f}°")
        painter.drawText(5, self.height() - 5, f"{self.view_min_lat:.1f}°, {self.view_min_lon:.1f}°")
        painter.drawText(self.width() - 80, self.height() - 5, f"{self.view_min_lat:.1f}°, {self.view_max_lon:.1f}°")

        # Draw current selection
        if self.selection_start and self.selection_end:
            start_x = min(self.selection_start.x(), self.selection_end.x())
            start_y = min(self.selection_start.y(), self.selection_end.y())
            width = abs(self.selection_end.x() - self.selection_start.x())
            height = abs(self.selection_end.y() - self.selection_start.y())

            # Selection rectangle
            painter.setBrush(QBrush(QColor(0, 120, 215, 50)))
            painter.setPen(QPen(QColor(0, 120, 215), 2))
            painter.drawRect(start_x, start_y, width, height)

class OfflineMapsDialog(QDialog):
    """Enhanced offline maps dialog with hang prevention."""

    def __init__(self, offline_manager, map_manager, parent=None):
        super().__init__(parent)
        self.offline_manager = offline_manager
        self.map_manager = map_manager

        self.setWindowTitle("Offline Maps Management")
        self.setModal(False)
        self.resize(800, 600)

        # Enhanced progress tracking with throttling
        self.download_progress = {}
        self.last_progress_update = {}
        self.progress_update_interval = 0.5  # Update every 500ms max

        # Active download tracking for hang prevention
        self.active_downloads = set()
        self.max_concurrent_downloads = 2  # Limit concurrent downloads

        self.setup_ui()
        self.connect_signals()
        self.refresh_areas_list()

        # Enhanced refresh timer with longer interval
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_storage_stats)
        self.refresh_timer.start(10000)  # Refresh every 10 seconds instead of 5

        # Progress cleanup timer to prevent memory leaks
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_old_progress)
        self.cleanup_timer.start(30000)  # Cleanup every 30 seconds

        logger.info("Enhanced OfflineMapsDialog initialized with hang prevention")

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Add Area tab
        self.setup_add_area_tab()

        # Manage Areas tab
        self.setup_manage_areas_tab()

        # Storage Management tab
        self.setup_storage_tab()

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_layout.addWidget(close_btn)

        layout.addLayout(close_layout)

    def setup_add_area_tab(self):
        """Set up the Add Area tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Area selection section
        selection_group = QGroupBox("Area Selection")
        selection_layout = QVBoxLayout(selection_group)

        # Area selector widget
        self.area_selector = AreaSelectorWidget()
        self.area_selector.area_selected.connect(self.on_area_selected)
        selection_layout.addWidget(self.area_selector)

        # Preset locations
        presets_layout = QHBoxLayout()
        presets_layout.addWidget(QLabel("Quick presets:"))

        preset_btn1 = QPushButton("Current View")
        preset_btn1.clicked.connect(self.use_current_view)
        presets_layout.addWidget(preset_btn1)

        preset_btn2 = QPushButton("City Area")
        preset_btn2.clicked.connect(lambda: self.use_preset_area(0.1))
        presets_layout.addWidget(preset_btn2)

        preset_btn3 = QPushButton("Metro Area")
        preset_btn3.clicked.connect(lambda: self.use_preset_area(0.5))
        presets_layout.addWidget(preset_btn3)

        preset_btn4 = QPushButton("State/Region")
        preset_btn4.clicked.connect(lambda: self.use_preset_area(2.0))
        presets_layout.addWidget(preset_btn4)

        presets_layout.addStretch()
        selection_layout.addLayout(presets_layout)

        layout.addWidget(selection_group)

        # Area details section
        details_group = QGroupBox("Area Details")
        details_layout = QFormLayout(details_group)

        # Area name
        self.area_name_edit = QLineEdit()
        self.area_name_edit.setPlaceholderText("Enter area name...")
        details_layout.addRow("Name:", self.area_name_edit)

        # Coordinates
        coord_layout = QHBoxLayout()

        self.min_lat_spin = QDoubleSpinBox()
        self.min_lat_spin.setRange(-85, 85)
        self.min_lat_spin.setDecimals(6)
        self.min_lat_spin.setSuffix("°")
        coord_layout.addWidget(QLabel("Min Lat:"))
        coord_layout.addWidget(self.min_lat_spin)

        self.min_lon_spin = QDoubleSpinBox()
        self.min_lon_spin.setRange(-180, 180)
        self.min_lon_spin.setDecimals(6)
        self.min_lon_spin.setSuffix("°")
        coord_layout.addWidget(QLabel("Min Lon:"))
        coord_layout.addWidget(self.min_lon_spin)

        details_layout.addRow("SW Corner:", coord_layout)

        coord_layout2 = QHBoxLayout()

        self.max_lat_spin = QDoubleSpinBox()
        self.max_lat_spin.setRange(-85, 85)
        self.max_lat_spin.setDecimals(6)
        self.max_lat_spin.setSuffix("°")
        coord_layout2.addWidget(QLabel("Max Lat:"))
        coord_layout2.addWidget(self.max_lat_spin)

        self.max_lon_spin = QDoubleSpinBox()
        self.max_lon_spin.setRange(-180, 180)
        self.max_lon_spin.setDecimals(6)
        self.max_lon_spin.setSuffix("°")
        coord_layout2.addWidget(QLabel("Max Lon:"))
        coord_layout2.addWidget(self.max_lon_spin)

        details_layout.addRow("NE Corner:", coord_layout2)

        # Zoom levels
        zoom_layout = QHBoxLayout()

        self.min_zoom_spin = QSpinBox()
        self.min_zoom_spin.setRange(1, 19)
        self.min_zoom_spin.setValue(8)
        zoom_layout.addWidget(QLabel("Min:"))
        zoom_layout.addWidget(self.min_zoom_spin)

        self.max_zoom_spin = QSpinBox()
        self.max_zoom_spin.setRange(1, 19)
        self.max_zoom_spin.setValue(16)
        zoom_layout.addWidget(QLabel("Max:"))
        zoom_layout.addWidget(self.max_zoom_spin)

        zoom_layout.addStretch()
        details_layout.addRow("Zoom Levels:", zoom_layout)

        # Map server
        self.server_combo = QComboBox()
        for server_name in TileServer.SERVERS.keys():
            self.server_combo.addItem(server_name)
        details_layout.addRow("Map Server:", self.server_combo)

        # Size estimate
        self.size_estimate_label = QLabel("Select an area to see size estimate")
        details_layout.addRow("Estimated Size:", self.size_estimate_label)

        # Connect spinboxes to update estimate
        self.min_lat_spin.valueChanged.connect(self.update_size_estimate)
        self.max_lat_spin.valueChanged.connect(self.update_size_estimate)
        self.min_lon_spin.valueChanged.connect(self.update_size_estimate)
        self.max_lon_spin.valueChanged.connect(self.update_size_estimate)
        self.min_zoom_spin.valueChanged.connect(self.update_size_estimate)
        self.max_zoom_spin.valueChanged.connect(self.update_size_estimate)

        layout.addWidget(details_group)

        # Action buttons
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()

        self.add_area_btn = QPushButton("Add Offline Area")
        self.add_area_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        self.add_area_btn.clicked.connect(self.add_offline_area)
        actions_layout.addWidget(self.add_area_btn)

        layout.addLayout(actions_layout)
        layout.addStretch()

        self.tab_widget.addTab(widget, "Add Area")

    def setup_manage_areas_tab(self):
        """Set up the Manage Areas tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Areas list
        areas_group = QGroupBox("Offline Areas")
        areas_layout = QVBoxLayout(areas_group)

        # Table for areas
        self.areas_table = QTableWidget()
        self.areas_table.setColumnCount(6)
        self.areas_table.setHorizontalHeaderLabels([
            "Name", "Size", "Progress", "Status", "Server", "Actions"
        ])

        # Set column widths
        header = self.areas_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Size
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Progress
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Server
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Actions

        areas_layout.addWidget(self.areas_table)

        # Global actions
        global_actions_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_areas_list)
        global_actions_layout.addWidget(refresh_btn)

        global_actions_layout.addStretch()

        cancel_all_btn = QPushButton("Cancel All Downloads")
        cancel_all_btn.clicked.connect(self.cancel_all_downloads)
        global_actions_layout.addWidget(cancel_all_btn)

        areas_layout.addLayout(global_actions_layout)
        layout.addWidget(areas_group)

        self.tab_widget.addTab(widget, "Manage Areas")

    def setup_storage_tab(self):
        """Set up the Storage Management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Storage overview
        overview_group = QGroupBox("Storage Overview")
        overview_layout = QFormLayout(overview_group)

        self.total_size_label = QLabel("Calculating...")
        overview_layout.addRow("Total Storage Used:", self.total_size_label)

        self.total_areas_label = QLabel("0")
        overview_layout.addRow("Total Areas:", self.total_areas_label)

        self.cache_location_label = QLabel("Unknown")
        overview_layout.addRow("Cache Location:", self.cache_location_label)

        layout.addWidget(overview_group)

        # Storage actions
        actions_group = QGroupBox("Storage Actions")
        actions_layout = QVBoxLayout(actions_group)

        # Clean up old tiles
        cleanup_layout = QHBoxLayout()
        cleanup_layout.addWidget(QLabel("Clean up tiles older than:"))

        self.cleanup_days_spin = QSpinBox()
        self.cleanup_days_spin.setRange(1, 365)
        self.cleanup_days_spin.setValue(30)
        self.cleanup_days_spin.setSuffix(" days")
        cleanup_layout.addWidget(self.cleanup_days_spin)

        cleanup_btn = QPushButton("Clean Up")
        cleanup_btn.clicked.connect(self.cleanup_old_tiles)
        cleanup_layout.addWidget(cleanup_btn)

        cleanup_layout.addStretch()
        actions_layout.addLayout(cleanup_layout)

        # Clear all cache
        clear_layout = QHBoxLayout()
        clear_layout.addWidget(QLabel("Clear entire map cache:"))

        clear_cache_btn = QPushButton("Clear All Cache")
        clear_cache_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        clear_cache_btn.clicked.connect(self.clear_all_cache)
        clear_layout.addWidget(clear_cache_btn)

        clear_layout.addStretch()
        actions_layout.addLayout(clear_layout)

        # Export/Import
        export_layout = QHBoxLayout()

        export_btn = QPushButton("Export Areas List")
        export_btn.clicked.connect(self.export_areas_list)
        export_layout.addWidget(export_btn)

        import_btn = QPushButton("Import Areas List")
        import_btn.clicked.connect(self.import_areas_list)
        export_layout.addWidget(import_btn)

        export_layout.addStretch()
        actions_layout.addLayout(export_layout)

        actions_layout.addStretch()
        layout.addWidget(actions_group)

        layout.addStretch()

        self.tab_widget.addTab(widget, "Storage")

    def connect_signals(self):
        """Enhanced signal connection with error handling."""
        try:
            self.offline_manager.download_started.connect(self.on_download_started)
            self.offline_manager.download_progress.connect(self.on_download_progress_throttled)
            self.offline_manager.download_completed.connect(self.on_download_completed)
            self.offline_manager.area_added.connect(self.refresh_areas_list)
            self.offline_manager.area_removed.connect(self.refresh_areas_list)
            logger.debug("Enhanced signal connections established")
        except Exception as e:
            logger.error(f"Error connecting signals: {e}")

    def on_area_selected(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float):
        """Handle area selection from the area selector."""
        self.min_lat_spin.setValue(min_lat)
        self.min_lon_spin.setValue(min_lon)
        self.max_lat_spin.setValue(max_lat)
        self.max_lon_spin.setValue(max_lon)

        # Generate default name
        if not self.area_name_edit.text():
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            self.area_name_edit.setText(f"Area_{center_lat:.2f}_{center_lon:.2f}")

    def use_current_view(self):
        """Use current map view as area selection."""
        # This would need to get current view from main map widget
        # For now, use a default area around Austin, TX
        self.min_lat_spin.setValue(30.1)
        self.min_lon_spin.setValue(-97.9)
        self.max_lat_spin.setValue(30.4)
        self.max_lon_spin.setValue(-97.6)

        if not self.area_name_edit.text():
            self.area_name_edit.setText("Current View")

    def use_preset_area(self, size_degrees: float):
        """Use a preset area size centered on Austin, TX."""
        center_lat = 30.25
        center_lon = -97.75

        half_size = size_degrees / 2

        self.min_lat_spin.setValue(center_lat - half_size)
        self.min_lon_spin.setValue(center_lon - half_size)
        self.max_lat_spin.setValue(center_lat + half_size)
        self.max_lon_spin.setValue(center_lon + half_size)

        size_names = {0.1: "City", 0.5: "Metro", 2.0: "Region"}
        if not self.area_name_edit.text():
            self.area_name_edit.setText(f"{size_names.get(size_degrees, 'Area')} Area")

    def update_size_estimate(self):
        """Update the size estimate for the current area selection."""
        try:
            from offline_map_manager import OfflineArea

            area = OfflineArea(
                "temp",
                self.min_lat_spin.value(),
                self.min_lon_spin.value(),
                self.max_lat_spin.value(),
                self.max_lon_spin.value(),
                self.min_zoom_spin.value(),
                self.max_zoom_spin.value()
            )

            tile_count = area.calculate_tile_count()
            size_mb = area.estimate_size_mb()

            self.size_estimate_label.setText(f"~{size_mb:.1f} MB ({tile_count:,} tiles)")

            # Warn if very large
            if size_mb > 1000:  # > 1GB
                self.size_estimate_label.setStyleSheet("color: red; font-weight: bold;")
            elif size_mb > 100:  # > 100MB
                self.size_estimate_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.size_estimate_label.setStyleSheet("")

        except Exception as e:
            self.size_estimate_label.setText("Error calculating size")
            logger.error(f"Error calculating size estimate: {e}")

    def add_offline_area(self):
        """Add the configured offline area."""
        try:
            from offline_map_manager import OfflineArea

            name = self.area_name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "Invalid Input", "Please enter an area name.")
                return

            # Validate coordinates
            if (self.min_lat_spin.value() >= self.max_lat_spin.value() or
                self.min_lon_spin.value() >= self.max_lon_spin.value()):
                QMessageBox.warning(self, "Invalid Coordinates",
                                  "Please ensure min coordinates are less than max coordinates.")
                return

            # Validate zoom levels
            if self.min_zoom_spin.value() > self.max_zoom_spin.value():
                QMessageBox.warning(self, "Invalid Zoom Levels",
                                  "Minimum zoom must be less than or equal to maximum zoom.")
                return

            # Create area
            area = OfflineArea(
                name,
                self.min_lat_spin.value(),
                self.min_lon_spin.value(),
                self.max_lat_spin.value(),
                self.max_lon_spin.value(),
                self.min_zoom_spin.value(),
                self.max_zoom_spin.value(),
                self.server_combo.currentText()
            )

            # Check size and warn if large
            size_mb = area.estimate_size_mb()
            if size_mb > 500:  # > 500MB
                reply = QMessageBox.question(
                    self, "Large Download",
                    f"This area will download approximately {size_mb:.1f} MB of data. "
                    f"This may take a long time and use significant storage space. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            # Add area
            if self.offline_manager.add_offline_area(area):
                QMessageBox.information(self, "Area Added",
                                      f"Offline area '{name}' has been added successfully.")

                # Clear form
                self.area_name_edit.clear()

                # Switch to manage tab
                self.tab_widget.setCurrentIndex(1)
            else:
                QMessageBox.warning(self, "Error",
                                  f"Failed to add offline area '{name}'. It may already exist.")

        except Exception as e:
            logger.error(f"Error adding offline area: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add offline area: {str(e)}")

    def refresh_areas_list(self):
        """Refresh the areas list in the manage tab."""
        try:
            areas = self.offline_manager.get_offline_areas()

            self.areas_table.setRowCount(len(areas))

            for row, area in enumerate(areas):
                # Name
                name_item = QTableWidgetItem(area['name'])
                self.areas_table.setItem(row, 0, name_item)

                # Size estimate
                from offline_map_manager import OfflineArea
                area_obj = OfflineArea(
                    area['name'], area['min_lat'], area['min_lon'],
                    area['max_lat'], area['max_lon'], area['min_zoom'],
                    area['max_zoom'], area['server']
                )
                size_mb = area_obj.estimate_size_mb()
                size_item = QTableWidgetItem(f"{size_mb:.1f} MB")
                self.areas_table.setItem(row, 1, size_item)

                # Progress
                progress = area.get('download_progress', 0)
                progress_item = QTableWidgetItem(f"{progress*100:.1f}%")
                self.areas_table.setItem(row, 2, progress_item)

                # Status
                if area.get('is_complete', False):
                    status = "Complete"
                elif self.offline_manager.is_downloading(area['name']):
                    status = "Downloading"
                elif progress > 0:
                    status = "Partial"
                else:
                    status = "Not Downloaded"

                status_item = QTableWidgetItem(status)
                if status == "Complete":
                    status_item.setBackground(QColor(200, 255, 200))
                elif status == "Downloading":
                    status_item.setBackground(QColor(255, 255, 200))
                elif status == "Partial":
                    status_item.setBackground(QColor(255, 220, 200))

                self.areas_table.setItem(row, 3, status_item)

                # Server
                server_item = QTableWidgetItem(area['server'])
                self.areas_table.setItem(row, 4, server_item)

                # Actions - create action buttons
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)

                if status == "Complete":
                    # Only show delete for complete areas
                    delete_btn = QPushButton("Delete")
                    delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
                    delete_btn.clicked.connect(lambda checked, name=area['name']: self.delete_area(name))
                    actions_layout.addWidget(delete_btn)
                elif status == "Downloading":
                    # Show cancel for downloading areas
                    cancel_btn = QPushButton("Cancel")
                    cancel_btn.clicked.connect(lambda checked, name=area['name']: self.cancel_download(name))
                    actions_layout.addWidget(cancel_btn)
                else:
                    # Show download and delete for other statuses
                    download_btn = QPushButton("Download")
                    download_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
                    download_btn.clicked.connect(lambda checked, name=area['name']: self.start_download(name))
                    actions_layout.addWidget(download_btn)

                    delete_btn = QPushButton("Delete")
                    delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
                    delete_btn.clicked.connect(lambda checked, name=area['name']: self.delete_area(name))
                    actions_layout.addWidget(delete_btn)

                self.areas_table.setCellWidget(row, 5, actions_widget)

        except Exception as e:
            logger.error(f"Error refreshing areas list: {e}")

    def start_download(self, area_name: str) -> bool:
        """Enhanced start download with hang prevention."""
        try:
            # Prevent multiple simultaneous downloads of same area
            if area_name in self.active_downloads:
                QMessageBox.warning(self, "Download Active",
                                  f"Download already active for area '{area_name}'.")
                return False

            # Limit concurrent downloads to prevent system overload
            if len(self.active_downloads) >= self.max_concurrent_downloads:
                QMessageBox.warning(self, "Too Many Downloads",
                                  f"Please wait for current downloads to complete. "
                                  f"(Maximum {self.max_concurrent_downloads} concurrent downloads)")
                return False

            if self.offline_manager.start_download(area_name):
                self.active_downloads.add(area_name)
                QMessageBox.information(self, "Download Started",
                                      f"Download started for area '{area_name}'.")
                return True
            else:
                QMessageBox.warning(self, "Download Failed",
                                  f"Failed to start download for area '{area_name}'.")
                return False

        except Exception as e:
            logger.error(f"Error starting download: {e}")
            QMessageBox.critical(self, "Error", f"Error starting download: {e}")
            return False

    def cancel_download(self, area_name: str):
        """Enhanced cancel download with cleanup."""
        try:
            reply = QMessageBox.question(
                self, "Cancel Download",
                f"Are you sure you want to cancel the download for '{area_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.offline_manager.cancel_download(area_name)

                # Clean up tracking data
                self.active_downloads.discard(area_name)
                if area_name in self.download_progress:
                    del self.download_progress[area_name]
                if area_name in self.last_progress_update:
                    del self.last_progress_update[area_name]

                QMessageBox.information(self, "Download Cancelled",
                                      f"Download cancelled for area '{area_name}'.")

        except Exception as e:
            logger.error(f"Error cancelling download: {e}")

    def delete_area(self, area_name: str):
        """Delete an offline area."""
        reply = QMessageBox.question(
            self, "Delete Area",
            f"Are you sure you want to delete offline area '{area_name}'? "
            f"This will also delete all downloaded tiles for this area.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.offline_manager.remove_offline_area(area_name):
                QMessageBox.information(self, "Area Deleted",
                                      f"Offline area '{area_name}' has been deleted.")
            else:
                QMessageBox.warning(self, "Delete Failed",
                                  f"Failed to delete area '{area_name}'.")

    def cancel_all_downloads(self):
        """Enhanced cancel all downloads."""
        active_downloads = [area['name'] for area in self.offline_manager.get_offline_areas()
                          if self.offline_manager.is_downloading(area['name'])]

        if not active_downloads:
            QMessageBox.information(self, "No Downloads", "No downloads are currently active.")
            return

        reply = QMessageBox.question(
            self, "Cancel All Downloads",
            f"Are you sure you want to cancel all {len(active_downloads)} active downloads?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            for area_name in active_downloads:
                self.offline_manager.cancel_download(area_name)
                # Clean up tracking
                self.active_downloads.discard(area_name)
                if area_name in self.download_progress:
                    del self.download_progress[area_name]
                if area_name in self.last_progress_update:
                    del self.last_progress_update[area_name]

            QMessageBox.information(self, "Downloads Cancelled",
                                  f"Cancelled {len(active_downloads)} downloads.")

    @pyqtSlot(str)
    def on_download_started(self, area_name: str):
        """Enhanced download started handler."""
        try:
            self.active_downloads.add(area_name)
            self.refresh_areas_list()
            logger.debug(f"Download started for {area_name}")
        except Exception as e:
            logger.error(f"Error handling download started: {e}")

    @pyqtSlot(str, int, int, str)
    def on_download_progress_throttled(self, area_name: str, current: int, total: int, status: str):
        """Throttled progress update to prevent UI hanging."""
        try:
            current_time = time.time()

            # Throttle updates per area
            if area_name in self.last_progress_update:
                if current_time - self.last_progress_update[area_name] < self.progress_update_interval:
                    return

            self.last_progress_update[area_name] = current_time

            # Process the update
            self.on_download_progress(area_name, current, total, status)

            # Process pending events to keep UI responsive
            QApplication.processEvents()

        except Exception as e:
            logger.error(f"Error in throttled progress update: {e}")

    def on_download_progress(self, area_name: str, current: int, total: int, status: str):
        """Enhanced download progress handler."""
        try:
            # Store progress for display
            progress = current / total if total > 0 else 0
            self.download_progress[area_name] = {
                'current': current,
                'total': total,
                'progress': progress,
                'status': status,
                'last_update': time.time()
            }

            # Update the table efficiently (avoid full refresh)
            self.update_area_progress_in_table(area_name, progress)

        except Exception as e:
            logger.error(f"Error handling download progress: {e}")

    def update_area_progress_in_table(self, area_name: str, progress: float):
        """Efficiently update progress in table without full refresh."""
        try:
            for row in range(self.areas_table.rowCount()):
                name_item = self.areas_table.item(row, 0)
                if name_item and name_item.text() == area_name:
                    progress_item = self.areas_table.item(row, 2)
                    if progress_item:
                        progress_item.setText(f"{progress*100:.1f}%")
                    break
        except Exception as e:
            logger.error(f"Error updating table progress: {e}")

    @pyqtSlot(str, bool, str)
    def on_download_completed(self, area_name: str, success: bool, message: str):
        """Enhanced download completed handler with cleanup."""
        try:
            # Remove from active downloads and clean up tracking
            self.active_downloads.discard(area_name)
            if area_name in self.download_progress:
                del self.download_progress[area_name]
            if area_name in self.last_progress_update:
                del self.last_progress_update[area_name]

            # Show notification (but don't block if dialog is closing)
            if self.isVisible():
                if success:
                    QMessageBox.information(self, "Download Complete",
                                          f"Download completed for area '{area_name}': {message}")
                else:
                    QMessageBox.warning(self, "Download Failed",
                                      f"Download failed for area '{area_name}': {message}")

            # Refresh areas list
            self.refresh_areas_list()

            logger.info(f"Download completed for {area_name}: success={success}")

        except Exception as e:
            logger.error(f"Error handling download completion: {e}")

    def cleanup_old_progress(self):
        """Clean up old progress data to prevent memory leaks."""
        try:
            current_time = time.time()
            timeout = 300  # 5 minutes

            to_remove = []
            for area_name, data in self.download_progress.items():
                if current_time - data.get('last_update', 0) > timeout:
                    to_remove.append(area_name)

            for area_name in to_remove:
                del self.download_progress[area_name]
                if area_name in self.last_progress_update:
                    del self.last_progress_update[area_name]

            if to_remove:
                logger.debug(f"Cleaned up progress data for {len(to_remove)} areas")

        except Exception as e:
            logger.error(f"Error cleaning up progress data: {e}")

    def refresh_storage_stats(self):
        """Enhanced storage stats refresh with error handling."""
        try:
            # Skip if dialog is not visible or being destroyed
            if not self.isVisible() or not hasattr(self, 'offline_manager'):
                return

            stats = self.offline_manager.get_storage_stats()

            # Update storage tab
            total_mb = stats.get('total_size_mb', 0)
            if total_mb < 1024:
                self.total_size_label.setText(f"{total_mb:.1f} MB")
            else:
                self.total_size_label.setText(f"{total_mb/1024:.1f} GB")

            areas_count = len(stats.get('areas', {}))
            self.total_areas_label.setText(str(areas_count))

            # Update cache location
            if hasattr(self.offline_manager.database, 'db_path'):
                import os
                cache_dir = os.path.dirname(self.offline_manager.database.db_path)
                self.cache_location_label.setText(cache_dir)

        except Exception as e:
            logger.error(f"Error refreshing storage stats: {e}")

    def cleanup_old_tiles(self):
        """Clean up old tiles."""
        days = self.cleanup_days_spin.value()

        reply = QMessageBox.question(
            self, "Clean Up Tiles",
            f"This will delete map tiles that haven't been accessed in {days} days "
            f"(except tiles that are part of offline areas). Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.offline_manager.cleanup_old_tiles(days)
                QMessageBox.information(self, "Cleanup Complete",
                                      "Old tiles have been cleaned up.")
                self.refresh_storage_stats()
            except Exception as e:
                QMessageBox.critical(self, "Cleanup Failed", f"Failed to clean up tiles: {str(e)}")

    def clear_all_cache(self):
        """Clear all map cache."""
        reply = QMessageBox.warning(
            self, "Clear All Cache",
            "This will delete ALL cached map tiles, including offline areas. "
            "This action cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.map_manager.clear_cache()
                QMessageBox.information(self, "Cache Cleared",
                                      "All map cache has been cleared.")
                self.refresh_storage_stats()
                self.refresh_areas_list()
            except Exception as e:
                QMessageBox.critical(self, "Clear Failed", f"Failed to clear cache: {str(e)}")

    def export_areas_list(self):
        """Export offline areas list to JSON file."""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Areas List",
                f"offline_areas_{time.strftime('%Y%m%d_%H%M%S')}.json",
                "JSON Files (*.json)"
            )

            if filename:
                import json
                areas = self.offline_manager.get_offline_areas()

                # Remove internal fields for export
                export_areas = []
                for area in areas:
                    export_area = {
                        'name': area['name'],
                        'min_lat': area['min_lat'],
                        'min_lon': area['min_lon'],
                        'max_lat': area['max_lat'],
                        'max_lon': area['max_lon'],
                        'min_zoom': area['min_zoom'],
                        'max_zoom': area['max_zoom'],
                        'server': area['server']
                    }
                    export_areas.append(export_area)

                with open(filename, 'w') as f:
                    json.dump(export_areas, f, indent=2)

                QMessageBox.information(self, "Export Complete",
                                      f"Exported {len(export_areas)} areas to {filename}")

        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export areas: {str(e)}")

    def import_areas_list(self):
        """Import offline areas list from JSON file."""
        try:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Import Areas List", "",
                "JSON Files (*.json)"
            )

            if filename:
                import json

                with open(filename, 'r') as f:
                    import_areas = json.load(f)

                imported_count = 0
                for area_data in import_areas:
                    try:
                        from offline_map_manager import OfflineArea

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

                        if self.offline_manager.add_offline_area(area):
                            imported_count += 1

                    except Exception as e:
                        logger.error(f"Error importing area {area_data.get('name', 'unknown')}: {e}")

                QMessageBox.information(self, "Import Complete",
                                      f"Imported {imported_count} areas from {filename}")
                self.refresh_areas_list()

        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Failed to import areas: {str(e)}")

    def closeEvent(self, event):
        """Enhanced close event with cleanup and active download warning."""
        try:
            # Stop timers
            if hasattr(self, 'refresh_timer'):
                self.refresh_timer.stop()
            if hasattr(self, 'cleanup_timer'):
                self.cleanup_timer.stop()

            # Warn about active downloads
            if self.active_downloads:
                reply = QMessageBox.question(
                    self, "Active Downloads",
                    f"There are {len(self.active_downloads)} active downloads. "
                    f"Closing this dialog will not stop the downloads. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return

            logger.info("OfflineMapsDialog closing - cleanup completed")
            super().closeEvent(event)

        except Exception as e:
            logger.error(f"Error during dialog close: {e}")
            super().closeEvent(event)
