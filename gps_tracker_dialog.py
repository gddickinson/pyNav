"""
GPS Tracker Dialog - Comprehensive GPS monitoring and tracking window
Provides detailed GPS information, device management, and track recording
"""

import os
import csv
import time
from datetime import datetime
from typing import Dict, List, Optional
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                           QLabel, QPushButton, QComboBox, QTabWidget, QWidget,
                           QFrame, QGroupBox, QFileDialog, QMessageBox, QTextEdit,
                           QCheckBox, QSpinBox, QProgressBar, QListWidget,
                           QListWidgetItem, QSplitter, QTableWidget, QTableWidgetItem)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDateTime
from PyQt6.QtGui import QFont, QColor, QPalette

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

class GPSDataWidget(QWidget):
    """Widget displaying detailed GPS data in a grid layout."""

    def __init__(self):
        super().__init__()
        self.data_labels = {}  # Initialize this BEFORE calling setup_ui()
        self.setup_ui()

    def setup_ui(self):
        """Setup the GPS data display UI."""
        layout = QVBoxLayout(self)

        # Create GPS data grid
        grid_frame = QGroupBox("GPS Data")
        grid_layout = QGridLayout(grid_frame)

        # GPS data fields
        gps_fields = [
            ('Time', 'time'), ('Date', 'date'), ('Latitude', 'latitude'), ('Longitude', 'longitude'),
            ('Speed', 'speed'), ('Heading', 'heading'), ('Altitude', 'altitude'), ('Fix Quality', 'fix_quality'),
            ('Satellites', 'satellites'), ('HDOP', 'hdop'), ('Accuracy', 'accuracy'), ('Source', 'source')
        ]

        for i, (label_text, key) in enumerate(gps_fields):
            row = i % 6
            col = (i // 6) * 2

            label = QLabel(f"{label_text}:")
            value_label = QLabel("N/A")
            value_label.setStyleSheet("font-weight: bold; color: #2E8B57;")

            grid_layout.addWidget(label, row, col)
            grid_layout.addWidget(value_label, row, col + 1)

            self.data_labels[key] = value_label

        layout.addWidget(grid_frame)

    def update_gps_data(self, location_data: Dict):
        """Update GPS data display."""
        if not location_data:
            # Clear all fields if no data
            for label in self.data_labels.values():
                label.setText("N/A")
            return

        # Update each field
        if 'timestamp' in location_data:
            dt = datetime.fromtimestamp(location_data['timestamp'])
            self.data_labels['time'].setText(dt.strftime('%H:%M:%S'))
            self.data_labels['date'].setText(dt.strftime('%Y-%m-%d'))

        if 'latitude' in location_data and location_data['latitude']:
            self.data_labels['latitude'].setText(f"{location_data['latitude']:.6f}°")
        else:
            self.data_labels['latitude'].setText("N/A")

        if 'longitude' in location_data and location_data['longitude']:
            self.data_labels['longitude'].setText(f"{location_data['longitude']:.6f}°")
        else:
            self.data_labels['longitude'].setText("N/A")

        if 'speed' in location_data and location_data['speed'] is not None:
            # Convert m/s to knots if it's a number
            try:
                speed_ms = float(location_data['speed'])
                speed_knots = speed_ms * 1.944  # m/s to knots
                self.data_labels['speed'].setText(f"{speed_knots:.1f} kts")
            except (ValueError, TypeError):
                self.data_labels['speed'].setText(str(location_data['speed']))
        else:
            self.data_labels['speed'].setText("N/A")

        if 'heading' in location_data and location_data['heading'] is not None:
            self.data_labels['heading'].setText(f"{location_data['heading']:.1f}°")
        else:
            self.data_labels['heading'].setText("N/A")

        if 'altitude' in location_data and location_data['altitude'] is not None:
            self.data_labels['altitude'].setText(f"{location_data['altitude']:.1f}m")
        else:
            self.data_labels['altitude'].setText("N/A")

        # GPS-specific fields (may not be available for IP location)
        self.data_labels['fix_quality'].setText(str(location_data.get('fix_quality', 'N/A')))
        self.data_labels['satellites'].setText(str(location_data.get('satellites', 'N/A')))
        self.data_labels['hdop'].setText(str(location_data.get('hdop', 'N/A')))

        if 'accuracy' in location_data and location_data['accuracy']:
            accuracy = location_data['accuracy']
            if accuracy < 1000:
                self.data_labels['accuracy'].setText(f"{accuracy:.1f}m")
            else:
                self.data_labels['accuracy'].setText(f"{accuracy/1000:.1f}km")
        else:
            self.data_labels['accuracy'].setText("N/A")

        self.data_labels['source'].setText(str(location_data.get('source', 'Unknown')))

class RawDataWidget(QWidget):
    """Widget displaying raw NMEA sentences and debug information."""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        """Setup raw data display UI."""
        layout = QVBoxLayout(self)

        # Raw data display
        raw_group = QGroupBox("Raw NMEA Data")
        raw_layout = QVBoxLayout(raw_group)

        self.raw_text = QTextEdit()
        self.raw_text.setMaximumHeight(200)
        self.raw_text.setFont(QFont("Courier", 9))
        raw_layout.addWidget(self.raw_text)

        # Controls
        controls_layout = QHBoxLayout()

        self.pause_raw = QCheckBox("Pause Display")
        controls_layout.addWidget(self.pause_raw)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.raw_text.clear)
        controls_layout.addWidget(clear_btn)

        controls_layout.addStretch()
        raw_layout.addLayout(controls_layout)

        layout.addWidget(raw_group)

        # Connection status
        status_group = QGroupBox("Connection Status")
        status_layout = QGridLayout(status_group)

        self.status_labels = {}
        status_fields = [
            ('Connection', 'connection'), ('Baud Rate', 'baudrate'),
            ('Port', 'port'), ('Data Rate', 'data_rate')
        ]

        for i, (label_text, key) in enumerate(status_fields):
            label = QLabel(f"{label_text}:")
            value_label = QLabel("N/A")
            value_label.setStyleSheet("font-weight: bold;")

            status_layout.addWidget(label, i // 2, (i % 2) * 2)
            status_layout.addWidget(value_label, i // 2, (i % 2) * 2 + 1)

            self.status_labels[key] = value_label

        layout.addWidget(status_group)

    def add_raw_data(self, data: str):
        """Add raw NMEA data to display."""
        if not self.pause_raw.isChecked():
            # Add timestamp
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            self.raw_text.append(f"[{timestamp}] {data.strip()}")

            # Keep only last 100 lines
            if self.raw_text.document().blockCount() > 100:
                cursor = self.raw_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                cursor.select(cursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deletePreviousChar()  # Remove the newline

    def update_status(self, status: Dict):
        """Update connection status."""
        self.status_labels['connection'].setText(status.get('connection', 'Unknown'))
        self.status_labels['baudrate'].setText(str(status.get('baudrate', 'N/A')))
        self.status_labels['port'].setText(status.get('port', 'N/A'))
        self.status_labels['data_rate'].setText(status.get('data_rate', 'N/A'))

class TrackingWidget(QWidget):
    """Widget for track recording and management."""

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.track_points = []
        self.is_recording = False
        self.log_file = None
        self.csv_writer = None
        self.start_time = None

    def setup_ui(self):
        """Setup tracking UI."""
        layout = QVBoxLayout(self)

        # Recording controls
        recording_group = QGroupBox("Track Recording")
        recording_layout = QVBoxLayout(recording_group)

        # Status
        self.recording_status = QLabel("Not Recording")
        self.recording_status.setStyleSheet("font-weight: bold; color: red;")
        recording_layout.addWidget(self.recording_status)

        # Controls
        controls_layout = QHBoxLayout()

        self.record_btn = QPushButton("Start Recording")
        self.record_btn.clicked.connect(self.toggle_recording)
        controls_layout.addWidget(self.record_btn)

        self.save_track_btn = QPushButton("Save Track")
        self.save_track_btn.clicked.connect(self.save_track)
        self.save_track_btn.setEnabled(False)
        controls_layout.addWidget(self.save_track_btn)

        self.clear_track_btn = QPushButton("Clear Track")
        self.clear_track_btn.clicked.connect(self.clear_track)
        controls_layout.addWidget(self.clear_track_btn)

        recording_layout.addLayout(controls_layout)

        # Track statistics
        stats_layout = QGridLayout()

        self.stats_labels = {}
        stats_fields = [
            ('Points', 'points'), ('Duration', 'duration'),
            ('Distance', 'distance'), ('Avg Speed', 'avg_speed')
        ]

        for i, (label_text, key) in enumerate(stats_fields):
            label = QLabel(f"{label_text}:")
            value_label = QLabel("0")
            value_label.setStyleSheet("font-weight: bold; color: #1E90FF;")

            stats_layout.addWidget(label, i // 2, (i % 2) * 2)
            stats_layout.addWidget(value_label, i // 2, (i % 2) * 2 + 1)

            self.stats_labels[key] = value_label

        recording_layout.addLayout(stats_layout)
        layout.addWidget(recording_group)

        # Recent points list
        points_group = QGroupBox("Recent Track Points")
        points_layout = QVBoxLayout(points_group)

        self.points_list = QListWidget()
        self.points_list.setMaximumHeight(150)
        points_layout.addWidget(self.points_list)

        layout.addWidget(points_group)

    def toggle_recording(self):
        """Start or stop track recording."""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start track recording."""
        # Ask for save location
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Track Log",
            f"track_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )

        if filename:
            try:
                self.log_file = open(filename, 'w', newline='')
                fieldnames = ['timestamp', 'latitude', 'longitude', 'altitude',
                            'speed', 'heading', 'accuracy', 'source']
                self.csv_writer = csv.DictWriter(self.log_file, fieldnames=fieldnames)
                self.csv_writer.writeheader()

                self.is_recording = True
                self.start_time = time.time()
                self.record_btn.setText("Stop Recording")
                self.recording_status.setText("Recording...")
                self.recording_status.setStyleSheet("font-weight: bold; color: green;")
                self.save_track_btn.setEnabled(True)

                logger.info(f"Started track recording to: {filename}")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start recording: {e}")

    def stop_recording(self):
        """Stop track recording."""
        self.is_recording = False
        self.record_btn.setText("Start Recording")
        self.recording_status.setText("Not Recording")
        self.recording_status.setStyleSheet("font-weight: bold; color: red;")

        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.csv_writer = None

        logger.info("Stopped track recording")

    def add_track_point(self, location_data: Dict):
        """Add a new track point."""
        if not location_data or not location_data.get('latitude') or not location_data.get('longitude'):
            return

        # Add to track points
        self.track_points.append(location_data.copy())

        # Keep only last 1000 points in memory
        if len(self.track_points) > 1000:
            self.track_points.pop(0)

        # Log to file if recording
        if self.is_recording and self.csv_writer:
            try:
                self.csv_writer.writerow({
                    'timestamp': datetime.fromtimestamp(location_data.get('timestamp', time.time())).isoformat(),
                    'latitude': location_data.get('latitude'),
                    'longitude': location_data.get('longitude'),
                    'altitude': location_data.get('altitude'),
                    'speed': location_data.get('speed'),
                    'heading': location_data.get('heading'),
                    'accuracy': location_data.get('accuracy'),
                    'source': location_data.get('source')
                })
                self.log_file.flush()  # Ensure data is written
            except Exception as e:
                logger.error(f"Error writing track point: {e}")

        # Update UI
        self.update_track_display()

    def update_track_display(self):
        """Update track statistics and recent points display."""
        if not self.track_points:
            self.stats_labels['points'].setText("0")
            self.stats_labels['duration'].setText("0")
            self.stats_labels['distance'].setText("0")
            self.stats_labels['avg_speed'].setText("0")
            return

        # Update statistics
        self.stats_labels['points'].setText(str(len(self.track_points)))

        # Duration
        if self.start_time:
            duration = time.time() - self.start_time
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            self.stats_labels['duration'].setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        # Distance calculation (simplified)
        total_distance = 0
        if len(self.track_points) > 1:
            for i in range(1, len(self.track_points)):
                prev_point = self.track_points[i-1]
                curr_point = self.track_points[i]

                if (prev_point.get('latitude') and prev_point.get('longitude') and
                    curr_point.get('latitude') and curr_point.get('longitude')):

                    distance = self.calculate_distance(
                        prev_point['latitude'], prev_point['longitude'],
                        curr_point['latitude'], curr_point['longitude']
                    )
                    total_distance += distance

        if total_distance < 1000:
            self.stats_labels['distance'].setText(f"{total_distance:.0f}m")
        else:
            self.stats_labels['distance'].setText(f"{total_distance/1000:.2f}km")

        # Average speed
        if self.start_time and time.time() > self.start_time:
            duration_hours = (time.time() - self.start_time) / 3600
            avg_speed_kmh = (total_distance / 1000) / duration_hours if duration_hours > 0 else 0
            self.stats_labels['avg_speed'].setText(f"{avg_speed_kmh:.1f}km/h")

        # Update recent points list (show last 10)
        self.points_list.clear()
        for point in self.track_points[-10:]:
            timestamp = datetime.fromtimestamp(point.get('timestamp', time.time()))
            lat = point.get('latitude', 0)
            lon = point.get('longitude', 0)

            item_text = f"{timestamp.strftime('%H:%M:%S')} - {lat:.6f}, {lon:.6f}"
            self.points_list.addItem(item_text)

        # Scroll to bottom
        self.points_list.scrollToBottom()

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters."""
        import math

        R = 6371000  # Earth radius in meters
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def save_track(self):
        """Save current track to GPX file."""
        if not self.track_points:
            QMessageBox.information(self, "No Data", "No track points to save.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Track as GPX",
            f"track_{datetime.now().strftime('%Y%m%d_%H%M%S')}.gpx",
            "GPX Files (*.gpx)"
        )

        if filename:
            try:
                self.export_to_gpx(filename)
                QMessageBox.information(self, "Success", f"Track saved to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save track: {e}")

    def export_to_gpx(self, filename: str):
        """Export track points to GPX format."""
        with open(filename, 'w') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<gpx version="1.1" creator="PyNav GPS Tracker">\n')
            f.write('  <trk>\n')
            f.write('    <name>PyNav Track</name>\n')
            f.write('    <trkseg>\n')

            for point in self.track_points:
                if point.get('latitude') and point.get('longitude'):
                    timestamp = datetime.fromtimestamp(point.get('timestamp', time.time()))
                    f.write(f'      <trkpt lat="{point["latitude"]}" lon="{point["longitude"]}">\n')

                    if point.get('altitude'):
                        f.write(f'        <ele>{point["altitude"]}</ele>\n')

                    f.write(f'        <time>{timestamp.isoformat()}Z</time>\n')
                    f.write('      </trkpt>\n')

            f.write('    </trkseg>\n')
            f.write('  </trk>\n')
            f.write('</gpx>\n')

    def clear_track(self):
        """Clear current track data."""
        reply = QMessageBox.question(
            self, "Clear Track",
            "Are you sure you want to clear the current track?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.track_points.clear()
            self.points_list.clear()
            self.update_track_display()
            logger.info("Track data cleared")

class GPSTrackerDialog(QDialog):
    """Main GPS tracker dialog window."""

    def __init__(self, location_manager, parent=None):
        super().__init__(parent)
        self.location_manager = location_manager
        self.setup_ui()
        self.setup_timer()

        # Data collection
        self.last_location_time = 0
        self.data_update_interval = 1.0  # seconds

        logger.info("GPS Tracker dialog initialized")

    def setup_ui(self):
        """Setup the main UI."""
        self.setWindowTitle("GPS Tracker - Device Monitor & Data Logger")
        self.setGeometry(200, 200, 900, 700)

        layout = QVBoxLayout(self)

        # Location source controls
        source_frame = QFrame()
        source_frame.setFrameStyle(QFrame.Shape.Box)
        source_layout = QHBoxLayout(source_frame)

        source_layout.addWidget(QLabel("Location Source:"))

        self.source_combo = QComboBox()
        self.update_source_list()
        self.source_combo.currentTextChanged.connect(self.change_location_source)
        source_layout.addWidget(self.source_combo)

        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.clicked.connect(self.refresh_devices)
        source_layout.addWidget(refresh_btn)

        source_layout.addStretch()

        # Connection status indicator
        self.connection_status = QLabel("Status: Unknown")
        self.connection_status.setStyleSheet("font-weight: bold; padding: 5px;")
        source_layout.addWidget(self.connection_status)

        layout.addWidget(source_frame)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # GPS Data tab
        self.gps_data_widget = GPSDataWidget()
        self.tab_widget.addTab(self.gps_data_widget, "GPS Data")

        # Raw Data tab
        self.raw_data_widget = RawDataWidget()
        self.tab_widget.addTab(self.raw_data_widget, "Raw Data")

        # Tracking tab
        self.tracking_widget = TrackingWidget()
        self.tab_widget.addTab(self.tracking_widget, "Track Recording")

        layout.addWidget(self.tab_widget)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_layout.addWidget(close_btn)

        layout.addLayout(close_layout)

    def setup_timer(self):
        """Setup update timer."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # Update every second

    def update_source_list(self):
        """Update the location source combo box."""
        current_text = self.source_combo.currentText()
        self.source_combo.clear()

        if self.location_manager:
            sources = self.location_manager.get_available_sources()
            self.source_combo.addItems(sources)

            # Try to restore previous selection
            index = self.source_combo.findText(current_text)
            if index >= 0:
                self.source_combo.setCurrentIndex(index)

    def change_location_source(self, source_name: str):
        """Change the active location source."""
        if self.location_manager and source_name:
            success = self.location_manager.set_active_source(source_name)
            if success:
                self.connection_status.setText(f"Status: Connected to {source_name}")
                self.connection_status.setStyleSheet("font-weight: bold; color: green; padding: 5px;")
                logger.info(f"GPS tracker switched to: {source_name}")
            else:
                self.connection_status.setText(f"Status: Failed to connect to {source_name}")
                self.connection_status.setStyleSheet("font-weight: bold; color: red; padding: 5px;")

    def refresh_devices(self):
        """Refresh available location devices."""
        if self.location_manager:
            # This would require adding a refresh method to location manager
            logger.info("Refreshing GPS devices...")
            self.update_source_list()
            QMessageBox.information(self, "Devices Refreshed",
                                  "Location device list has been refreshed.")

    def update_display(self):
        """Update all display elements."""
        if not self.location_manager:
            return

        try:
            # Get current location data
            location_data = self.location_manager.get_current_location()

            if location_data:
                # Update GPS data display
                self.gps_data_widget.update_gps_data(location_data)

                # Add to tracking
                self.tracking_widget.add_track_point(location_data)

                # Update connection status
                source = location_data.get('source', 'Unknown')
                if 'GPS' in source:
                    self.connection_status.setText(f"Status: GPS Active - {source}")
                    self.connection_status.setStyleSheet("font-weight: bold; color: green; padding: 5px;")
                else:
                    self.connection_status.setText(f"Status: {source}")
                    self.connection_status.setStyleSheet("font-weight: bold; color: blue; padding: 5px;")

                # Update raw data status (simplified)
                self.raw_data_widget.update_status({
                    'connection': 'Connected',
                    'port': source,
                    'baudrate': '115200',
                    'data_rate': '1 Hz'
                })

                # Add simulated raw data for GPS sources
                if 'GPS' in source:
                    nmea_sample = f"$GPRMC,{datetime.now().strftime('%H%M%S')}.000,A,{location_data.get('latitude', 0):.6f},N,{location_data.get('longitude', 0):.6f},W,{location_data.get('speed', 0):.1f},{location_data.get('heading', 0):.1f},{datetime.now().strftime('%d%m%y')},,,A*7C"
                    self.raw_data_widget.add_raw_data(nmea_sample)

            else:
                # No location data
                self.connection_status.setText("Status: No data available")
                self.connection_status.setStyleSheet("font-weight: bold; color: orange; padding: 5px;")

        except Exception as e:
            logger.error(f"Error updating GPS tracker display: {e}")

    def closeEvent(self, event):
        """Handle dialog close."""
        # Stop any recording
        if hasattr(self.tracking_widget, 'is_recording') and self.tracking_widget.is_recording:
            self.tracking_widget.stop_recording()

        logger.info("GPS Tracker dialog closed")
        super().closeEvent(event)
