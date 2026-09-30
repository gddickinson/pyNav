"""
Local OSM Settings Dialog - UI for configuring local OpenStreetMap tile sources
Allows users to enable/disable local tiles and configure MBTiles database path
"""

import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
                           QLabel, QPushButton, QLineEdit, QCheckBox,
                           QFileDialog, QMessageBox, QTextEdit, QFormLayout,
                           QProgressBar, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)


class LocalOSMSettingsDialog(QDialog):
    """Dialog for configuring local OSM tile sources."""

    def __init__(self, map_manager, parent=None):
        super().__init__(parent)
        self.map_manager = map_manager

        self.setWindowTitle("Local OSM Tile Settings")
        self.setModal(False)
        self.resize(700, 600)

        self.setup_ui()
        self.load_current_settings()

        # Auto-refresh timer for statistics
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_statistics)
        self.refresh_timer.start(2000)  # Refresh every 2 seconds

        logger.info("Local OSM settings dialog opened")

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("Configure Local OpenStreetMap Tiles")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        info_label = QLabel(
            "Use a local MBTiles database for offline map access. "
            "This allows you to use OpenStreetMap data without downloading tiles online."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addWidget(self._create_separator())

        # Enable/Disable section
        enable_group = QGroupBox("Local Tile Source")
        enable_layout = QVBoxLayout(enable_group)

        self.enable_checkbox = QCheckBox("Enable Local OSM Tiles")
        self.enable_checkbox.setStyleSheet("QCheckBox { font-weight: bold; }")
        self.enable_checkbox.stateChanged.connect(self.on_enable_changed)
        enable_layout.addWidget(self.enable_checkbox)

        enable_info = QLabel(
            "When enabled, PyNav will use tiles from your local MBTiles database first, "
            "then fall back to online sources if a tile is not available locally."
        )
        enable_info.setWordWrap(True)
        enable_info.setStyleSheet("color: #666; font-size: 10px;")
        enable_layout.addWidget(enable_info)

        layout.addWidget(enable_group)

        # MBTiles path section
        path_group = QGroupBox("MBTiles Database")
        path_layout = QVBoxLayout(path_group)

        path_form = QFormLayout()

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Path to .mbtiles file...")
        self.path_edit.textChanged.connect(self.on_path_changed)
        path_form.addRow("MBTiles Path:", self.path_edit)

        path_layout.addLayout(path_form)

        # Browse button
        browse_layout = QHBoxLayout()
        browse_layout.addStretch()

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_mbtiles)
        browse_layout.addWidget(browse_btn)

        path_layout.addLayout(browse_layout)

        # Path help text
        path_help = QLabel(
            "Select the MBTiles database file. You can create one by converting "
            "an OSM PBF file using the convert_osm_to_mbtiles.py utility."
        )
        path_help.setWordWrap(True)
        path_help.setStyleSheet("color: #666; font-size: 10px;")
        path_layout.addWidget(path_help)

        layout.addWidget(path_group)

        # Status section
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)

        self.status_label = QLabel("Not configured")
        self.status_label.setStyleSheet("font-weight: bold; color: orange;")
        status_layout.addWidget(self.status_label)

        # Info grid
        info_form = QFormLayout()

        self.tile_count_label = QLabel("-")
        info_form.addRow("Total Tiles:", self.tile_count_label)

        self.zoom_range_label = QLabel("-")
        info_form.addRow("Zoom Range:", self.zoom_range_label)

        self.bounds_label = QLabel("-")
        info_form.addRow("Coverage:", self.bounds_label)

        self.format_label = QLabel("-")
        info_form.addRow("Format:", self.format_label)

        status_layout.addLayout(info_form)
        layout.addWidget(status_group)

        # Statistics section
        stats_group = QGroupBox("Usage Statistics")
        stats_layout = QVBoxLayout(stats_group)

        stats_form = QFormLayout()

        self.local_hits_label = QLabel("0")
        stats_form.addRow("Local Tile Hits:", self.local_hits_label)

        self.local_misses_label = QLabel("0")
        stats_form.addRow("Local Tile Misses:", self.local_misses_label)

        self.hit_ratio_label = QLabel("0%")
        stats_form.addRow("Hit Ratio:", self.hit_ratio_label)

        stats_layout.addLayout(stats_form)

        # Progress bar for hit ratio
        self.hit_ratio_bar = QProgressBar()
        self.hit_ratio_bar.setMaximum(100)
        self.hit_ratio_bar.setValue(0)
        stats_layout.addWidget(self.hit_ratio_bar)

        reset_stats_btn = QPushButton("Reset Statistics")
        reset_stats_btn.clicked.connect(self.reset_statistics)
        stats_layout.addWidget(reset_stats_btn)

        layout.addWidget(stats_group)

        # Help section
        help_group = QGroupBox("How to Get MBTiles")
        help_layout = QVBoxLayout(help_group)

        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(120)
        help_text.setHtml("""
        <h4>Converting OSM PBF to MBTiles:</h4>
        <ol>
            <li><b>Extract your region</b> from the planet file (optional but recommended)</li>
            <li><b>Convert to MBTiles</b> using:<br/>
                • tilemaker (recommended)<br/>
                • planetiler (Java-based, very fast)<br/>
                • tippecanoe
            </li>
            <li><b>Use the conversion utility:</b><br/>
                <code>python convert_osm_to_mbtiles.py planet.osm.pbf output.mbtiles --bbox=-97.9,30.1,-97.6,30.4</code>
            </li>
        </ol>
        <p><b>Quick Example (Austin, TX):</b><br/>
        <code>python convert_osm_to_mbtiles.py /Volumes/GeorgeDrive/planet-latest.osm.pbf austin.mbtiles --bbox=-97.9,30.1,-97.6,30.4</code></p>
        """)
        help_layout.addWidget(help_text)

        layout.addWidget(help_group)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()

        test_btn = QPushButton("Test Configuration")
        test_btn.clicked.connect(self.test_configuration)
        button_layout.addWidget(test_btn)

        button_layout.addStretch()

        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        apply_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(apply_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _create_separator(self):
        """Create a horizontal separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        return separator

    def load_current_settings(self):
        """Load current settings from map manager."""
        try:
            if not hasattr(self.map_manager, 'local_tile_source'):
                return

            # Load enabled state
            enabled = self.map_manager.local_tile_source.enabled
            self.enable_checkbox.setChecked(enabled)

            # Load path
            path = self.map_manager.local_tile_source.mbtiles_path
            if path:
                self.path_edit.setText(path)

            # Refresh status
            self.refresh_status()
            self.refresh_statistics()

        except Exception as e:
            logger.error(f"Error loading current settings: {e}")

    def on_enable_changed(self, state):
        """Handle enable checkbox state change."""
        enabled = state == Qt.CheckState.Checked.value
        logger.info(f"Local OSM tiles {'enabled' if enabled else 'disabled'}")

    def on_path_changed(self, text):
        """Handle path text change."""
        # Expand user home directory
        expanded = os.path.expanduser(text)
        if os.path.exists(expanded) and expanded != text:
            # Path exists and was expanded
            pass

    def browse_mbtiles(self):
        """Browse for MBTiles file."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select MBTiles Database",
            os.path.expanduser("~"),
            "MBTiles Files (*.mbtiles);;All Files (*)"
        )

        if filename:
            self.path_edit.setText(filename)

    def test_configuration(self):
        """Test the current configuration."""
        try:
            path = self.path_edit.text().strip()

            if not path:
                QMessageBox.warning(self, "No Path", "Please select an MBTiles file first.")
                return

            expanded_path = os.path.expanduser(path)

            if not os.path.exists(expanded_path):
                QMessageBox.warning(
                    self, "File Not Found",
                    f"MBTiles file not found:\n{expanded_path}"
                )
                return

            # Try to initialize
            from local_tile_source import MBTilesReader

            reader = MBTilesReader(expanded_path)

            info = {
                'tile_count': reader.get_tile_count(),
                'min_zoom': reader.get_min_zoom(),
                'max_zoom': reader.get_max_zoom(),
                'bounds': reader.get_bounds(),
                'format': reader.get_format(),
                'is_vector': reader.is_vector
            }

            reader.close()

            # Show success message
            tile_type = "Vector" if info['is_vector'] else "Raster"
            message = f"✓ MBTiles database is valid!\n\n"
            message += f"Type: {tile_type} tiles\n"
            message += f"Format: {info['format']}\n"
            message += f"Tiles: {info['tile_count']:,}\n"
            message += f"Zoom: {info['min_zoom']}-{info['max_zoom']}\n"
            if info['bounds']:
                message += f"Bounds: {info['bounds']}"

            QMessageBox.information(self, "Test Successful", message)

        except Exception as e:
            QMessageBox.critical(
                self, "Test Failed",
                f"Failed to load MBTiles database:\n\n{str(e)}"
            )

    def apply_settings(self):
        """Apply settings to map manager."""
        try:
            enabled = self.enable_checkbox.isChecked()
            path = self.path_edit.text().strip()

            if enabled and not path:
                QMessageBox.warning(
                    self, "Missing Configuration",
                    "Please select an MBTiles file before enabling local tiles."
                )
                return

            # Validate format before applying
            if enabled and path:
                expanded_path = os.path.expanduser(path)

                try:
                    from local_tile_source import MBTilesReader
                    # Quick validation
                    test_reader = MBTilesReader(expanded_path)
                    test_reader.close()
                except ValueError as e:
                    # Format validation error
                    QMessageBox.critical(
                        self, "Incompatible Format",
                        f"Cannot use this MBTiles file:\n\n{str(e)}"
                    )
                    return
                except Exception as e:
                    QMessageBox.critical(
                        self, "Error",
                        f"Failed to validate MBTiles file:\n\n{str(e)}"
                    )
                    return

            # Apply to map manager
            if hasattr(self.map_manager, 'set_local_osm_enabled'):
                self.map_manager.set_local_osm_enabled(enabled)

            if path and hasattr(self.map_manager, 'set_local_osm_path'):
                success = self.map_manager.set_local_osm_path(path)

                if not success and enabled:
                    QMessageBox.warning(
                        self, "Configuration Failed",
                        "Failed to load MBTiles database. Check the path and try again."
                    )
                    return

            # Refresh display
            self.refresh_status()

            QMessageBox.information(
                self, "Settings Applied",
                "Local OSM tile settings have been applied successfully."
            )

            logger.info("Applied local OSM settings")

        except Exception as e:
            logger.error(f"Error applying settings: {e}")
            QMessageBox.critical(
                self, "Error",
                f"Failed to apply settings:\n\n{str(e)}"
            )

    def refresh_status(self):
        """Refresh the status display."""
        try:
            if not hasattr(self.map_manager, 'local_tile_source'):
                return

            info = self.map_manager.get_local_osm_info()

            if info['available']:
                tile_type = "Vector" if info.get('is_vector', False) else "Raster"
                self.status_label.setText(f"✓ Local OSM tiles available ({tile_type})")
                self.status_label.setStyleSheet("font-weight: bold; color: green;")

                # Update info fields
                self.tile_count_label.setText(f"{info['tile_count']:,}")

                # Show format with type
                format_text = f"{info.get('format', 'Unknown')} ({tile_type})"
                self.format_label.setText(format_text)

                self.zoom_range_label.setText(f"{info['min_zoom']}-{info['max_zoom']}")

                bounds = info.get('bounds')
                if bounds:
                    self.bounds_label.setText(
                        f"{bounds[0]:.2f}, {bounds[1]:.2f} to {bounds[2]:.2f}, {bounds[3]:.2f}"
                    )
                else:
                    self.bounds_label.setText("Unknown")

            elif info['enabled'] and info['path']:
                self.status_label.setText("✗ MBTiles file not accessible")
                self.status_label.setStyleSheet("font-weight: bold; color: red;")

                # Clear info fields
                self.tile_count_label.setText("-")
                self.zoom_range_label.setText("-")
                self.bounds_label.setText("-")
                self.format_label.setText("-")

            else:
                self.status_label.setText("Not configured")
                self.status_label.setStyleSheet("font-weight: bold; color: orange;")

                # Clear info fields
                self.tile_count_label.setText("-")
                self.zoom_range_label.setText("-")
                self.bounds_label.setText("-")
                self.format_label.setText("-")

        except Exception as e:
            logger.error(f"Error refreshing status: {e}")

    def refresh_statistics(self):
        """Refresh usage statistics display."""
        try:
            if not hasattr(self.map_manager, 'local_tile_source'):
                return

            stats = self.map_manager.local_tile_source.get_statistics()

            self.local_hits_label.setText(str(stats['local_hits']))
            self.local_misses_label.setText(str(stats['local_misses']))

            hit_ratio = stats['hit_ratio'] * 100
            self.hit_ratio_label.setText(f"{hit_ratio:.1f}%")
            self.hit_ratio_bar.setValue(int(hit_ratio))

            # Color code the progress bar
            if hit_ratio >= 80:
                self.hit_ratio_bar.setStyleSheet("QProgressBar::chunk { background-color: green; }")
            elif hit_ratio >= 50:
                self.hit_ratio_bar.setStyleSheet("QProgressBar::chunk { background-color: orange; }")
            else:
                self.hit_ratio_bar.setStyleSheet("QProgressBar::chunk { background-color: red; }")

        except Exception as e:
            logger.error(f"Error refreshing statistics: {e}")

    def reset_statistics(self):
        """Reset usage statistics."""
        try:
            if hasattr(self.map_manager, 'local_tile_source'):
                self.map_manager.local_tile_source.reset_statistics()
                self.refresh_statistics()
                QMessageBox.information(self, "Statistics Reset", "Usage statistics have been reset.")
        except Exception as e:
            logger.error(f"Error resetting statistics: {e}")

    def closeEvent(self, event):
        """Handle dialog close."""
        self.refresh_timer.stop()
        logger.info("Local OSM settings dialog closed")
        super().closeEvent(event)
