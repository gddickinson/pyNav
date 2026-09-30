"""
Route Planning Panel - GUI component for route planning and management
Allows users to plan routes, add waypoints, and manage saved routes
"""

from typing import Dict, List, Optional, Tuple
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                           QPushButton, QLineEdit, QListWidget, QListWidgetItem,
                           QFrame, QComboBox, QCheckBox, QSpinBox, QTabWidget,
                           QMessageBox, QInputDialog, QMenu, QTextEdit, QGroupBox,
                           QFormLayout, QDateTimeEdit, QSlider)
from PyQt6.QtCore import Qt, pyqtSignal, QDateTime
from PyQt6.QtGui import QIcon, QFont, QAction

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

class WaypointItem(QListWidgetItem):
    """Custom list item for waypoints."""

    def __init__(self, waypoint_data: Dict):
        super().__init__()
        self.waypoint_data = waypoint_data

        # Format display text
        if 'address' in waypoint_data and waypoint_data['address']:
            display_text = waypoint_data['address']
        else:
            lat = waypoint_data.get('latitude', 0)
            lon = waypoint_data.get('longitude', 0)
            display_text = f"{lat:.6f}, {lon:.6f}"

        self.setText(display_text)
        self.setToolTip(f"Lat: {waypoint_data.get('latitude', 0):.6f}, "
                       f"Lon: {waypoint_data.get('longitude', 0):.6f}")

class SavedRouteItem(QListWidgetItem):
    """Custom list item for saved routes."""

    def __init__(self, route_data: Dict):
        super().__init__()
        self.route_data = route_data

        # Format display text
        name = route_data.get('name', 'Unnamed Route')
        distance = route_data.get('distance', 0)
        if distance > 1000:
            distance_text = f"{distance/1000:.1f} km"
        else:
            distance_text = f"{distance:.0f} m"

        duration = route_data.get('duration', 0)
        if duration > 3600:
            duration_text = f"{duration//3600:.0f}h {(duration%3600)//60:.0f}m"
        else:
            duration_text = f"{duration//60:.0f}m"

        self.setText(f"{name} ({distance_text}, {duration_text})")
        self.setToolTip(f"Created: {route_data.get('created_at', 'Unknown')}")

class RoutePlanningPanel(QWidget):
    """Main route planning panel widget."""

    # pyqtSignals
    route_requested = pyqtSignal(dict, dict)  # start, end locations
    waypoint_added = pyqtSignal(dict)  # waypoint data
    route_loaded = pyqtSignal(dict)  # route data

    def __init__(self, parent=None):
        super().__init__(parent)

        # Route planning state
        self.start_location = None
        self.end_location = None
        self.waypoints = []
        self.route_options = {
            'avoid_tolls': False,
            'avoid_highways': False,
            'vehicle_type': 'car',
            'route_preference': 'fastest'
        }

        self.setup_ui()
        logger.info("Route planning panel initialized")

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Create tab widget for different route planning functions
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Plan Route tab
        self.setup_plan_route_tab()

        # Saved Routes tab
        self.setup_saved_routes_tab()

        # Route Options tab
        self.setup_route_options_tab()

    def setup_plan_route_tab(self):
        """Set up the route planning tab."""
        plan_widget = QWidget()
        layout = QVBoxLayout(plan_widget)

        # Route points section
        points_group = QGroupBox("Route Points")
        points_layout = QVBoxLayout(points_group)

        # Start location
        start_frame = QFrame()
        start_layout = QHBoxLayout(start_frame)
        start_layout.addWidget(QLabel("From:"))

        self.start_input = QLineEdit()
        self.start_input.setPlaceholderText("Enter start address or coordinates...")
        self.start_input.returnPressed.connect(self.set_start_from_input)
        start_layout.addWidget(self.start_input)

        self.use_current_start = QPushButton("Use Current Location")
        self.use_current_start.clicked.connect(self.use_current_as_start)
        start_layout.addWidget(self.use_current_start)

        points_layout.addWidget(start_frame)

        # Waypoints section
        waypoints_label = QLabel("Waypoints:")
        points_layout.addWidget(waypoints_label)

        self.waypoints_list = QListWidget()
        self.waypoints_list.setMaximumHeight(100)
        self.waypoints_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.waypoints_list.customContextMenuRequested.connect(self.show_waypoint_context_menu)
        points_layout.addWidget(self.waypoints_list)

        # Waypoint controls
        waypoint_controls = QHBoxLayout()

        self.waypoint_input = QLineEdit()
        self.waypoint_input.setPlaceholderText("Add waypoint...")
        self.waypoint_input.returnPressed.connect(self.add_waypoint_from_input)
        waypoint_controls.addWidget(self.waypoint_input)

        add_waypoint_btn = QPushButton("Add")
        add_waypoint_btn.clicked.connect(self.add_waypoint_from_input)
        waypoint_controls.addWidget(add_waypoint_btn)

        clear_waypoints_btn = QPushButton("Clear")
        clear_waypoints_btn.clicked.connect(self.clear_waypoints)
        waypoint_controls.addWidget(clear_waypoints_btn)

        points_layout.addLayout(waypoint_controls)

        # End location
        end_frame = QFrame()
        end_layout = QHBoxLayout(end_frame)
        end_layout.addWidget(QLabel("To:"))

        self.end_input = QLineEdit()
        self.end_input.setPlaceholderText("Enter destination address or coordinates...")
        self.end_input.returnPressed.connect(self.set_end_from_input)
        end_layout.addWidget(self.end_input)

        self.pick_end_btn = QPushButton("Pick on Map")
        self.pick_end_btn.clicked.connect(self.pick_destination_on_map)
        end_layout.addWidget(self.pick_end_btn)

        points_layout.addWidget(end_frame)
        layout.addWidget(points_group)

        # Quick route options
        quick_options = QGroupBox("Quick Options")
        quick_layout = QHBoxLayout(quick_options)

        self.avoid_tolls_cb = QCheckBox("Avoid tolls")
        self.avoid_tolls_cb.stateChanged.connect(self.update_route_options)
        quick_layout.addWidget(self.avoid_tolls_cb)

        self.avoid_highways_cb = QCheckBox("Avoid highways")
        self.avoid_highways_cb.stateChanged.connect(self.update_route_options)
        quick_layout.addWidget(self.avoid_highways_cb)

        layout.addWidget(quick_options)

        # Route actions
        actions_layout = QHBoxLayout()

        self.calculate_btn = QPushButton("Calculate Route")
        self.calculate_btn.clicked.connect(self.calculate_route)
        self.calculate_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        actions_layout.addWidget(self.calculate_btn)

        self.save_route_btn = QPushButton("Save Route")
        self.save_route_btn.clicked.connect(self.save_current_route)
        self.save_route_btn.setEnabled(False)
        actions_layout.addWidget(self.save_route_btn)

        self.clear_route_btn = QPushButton("Clear")
        self.clear_route_btn.clicked.connect(self.clear_route)
        actions_layout.addWidget(self.clear_route_btn)

        layout.addLayout(actions_layout)

        # Route summary
        self.route_summary = QTextEdit()
        self.route_summary.setMaximumHeight(80)
        self.route_summary.setReadOnly(True)
        self.route_summary.setPlaceholderText("Route summary will appear here...")
        layout.addWidget(self.route_summary)

        layout.addStretch()
        self.tab_widget.addTab(plan_widget, "Plan Route")

    def setup_saved_routes_tab(self):
        """Set up the saved routes tab."""
        saved_widget = QWidget()
        layout = QVBoxLayout(saved_widget)

        # Saved routes list
        routes_label = QLabel("Saved Routes:")
        layout.addWidget(routes_label)

        self.saved_routes_list = QListWidget()
        self.saved_routes_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.saved_routes_list.customContextMenuRequested.connect(self.show_saved_route_context_menu)
        self.saved_routes_list.itemDoubleClicked.connect(self.load_saved_route)
        layout.addWidget(self.saved_routes_list)

        # Saved route controls
        saved_controls = QHBoxLayout()

        load_btn = QPushButton("Load Route")
        load_btn.clicked.connect(self.load_selected_route)
        saved_controls.addWidget(load_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_selected_route)
        saved_controls.addWidget(delete_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_saved_routes)
        saved_controls.addWidget(refresh_btn)

        layout.addLayout(saved_controls)

        # Load saved routes
        self.refresh_saved_routes()

        self.tab_widget.addTab(saved_widget, "Saved Routes")

    def setup_route_options_tab(self):
        """Set up the route options tab."""
        options_widget = QWidget()
        layout = QVBoxLayout(options_widget)

        # Vehicle type
        vehicle_group = QGroupBox("Vehicle Type")
        vehicle_layout = QFormLayout(vehicle_group)

        self.vehicle_combo = QComboBox()
        self.vehicle_combo.addItems(["Car", "Motorcycle", "Bicycle", "Walking"])
        self.vehicle_combo.currentTextChanged.connect(self.update_route_options)
        vehicle_layout.addRow("Vehicle:", self.vehicle_combo)

        layout.addWidget(vehicle_group)

        # Route preferences
        pref_group = QGroupBox("Route Preferences")
        pref_layout = QFormLayout(pref_group)

        self.route_pref_combo = QComboBox()
        self.route_pref_combo.addItems(["Fastest", "Shortest", "Most Fuel Efficient", "Scenic"])
        self.route_pref_combo.currentTextChanged.connect(self.update_route_options)
        pref_layout.addRow("Preference:", self.route_pref_combo)

        layout.addWidget(pref_group)

        # Avoidance options
        avoid_group = QGroupBox("Avoid")
        avoid_layout = QVBoxLayout(avoid_group)

        self.avoid_tolls_detailed = QCheckBox("Toll roads")
        self.avoid_tolls_detailed.stateChanged.connect(self.update_route_options)
        avoid_layout.addWidget(self.avoid_tolls_detailed)

        self.avoid_highways_detailed = QCheckBox("Highways/Motorways")
        self.avoid_highways_detailed.stateChanged.connect(self.update_route_options)
        avoid_layout.addWidget(self.avoid_highways_detailed)

        self.avoid_ferries = QCheckBox("Ferries")
        self.avoid_ferries.stateChanged.connect(self.update_route_options)
        avoid_layout.addWidget(self.avoid_ferries)

        self.avoid_unpaved = QCheckBox("Unpaved roads")
        self.avoid_unpaved.stateChanged.connect(self.update_route_options)
        avoid_layout.addWidget(self.avoid_unpaved)

        layout.addWidget(avoid_group)

        # Time preferences
        time_group = QGroupBox("Time Preferences")
        time_layout = QFormLayout(time_group)

        self.departure_time = QDateTimeEdit(QDateTime.currentDateTime())
        time_layout.addRow("Departure time:", self.departure_time)

        self.use_traffic = QCheckBox("Consider traffic conditions")
        self.use_traffic.setChecked(True)
        time_layout.addRow(self.use_traffic)

        layout.addWidget(time_group)

        layout.addStretch()
        self.tab_widget.addTab(options_widget, "Options")

    def set_start_from_input(self):
        """Set start location from input field."""
        address = self.start_input.text().strip()
        if address:
            # TODO: Geocode the address
            # For now, just store as text
            self.start_location = {'address': address}
            self.update_calculate_button_state()

    def set_end_from_input(self):
        """Set end location from input field."""
        address = self.end_input.text().strip()
        if address:
            # TODO: Geocode the address
            # For now, just store as text
            self.end_location = {'address': address}
            self.update_calculate_button_state()

    def use_current_as_start(self):
        """Use current location as start point."""
        # TODO: Get current location from location manager
        # For now, use placeholder
        self.start_location = {
            'latitude': 40.7589,
            'longitude': -73.9851,
            'address': 'Current Location'
        }
        self.start_input.setText('Current Location')
        self.update_calculate_button_state()

    def pick_destination_on_map(self):
        """Enable map picking mode for destination."""
        # TODO: pyqtSignal to main window to enable map picking mode
        QMessageBox.information(self, "Pick Destination",
                              "Click on the map to set destination")

    def add_waypoint_from_input(self):
        """Add waypoint from input field."""
        address = self.waypoint_input.text().strip()
        if address:
            waypoint = {'address': address}
            self.add_waypoint(waypoint)
            self.waypoint_input.clear()

    def add_waypoint(self, waypoint_data: Dict):
        """Add a waypoint to the route."""
        self.waypoints.append(waypoint_data)

        item = WaypointItem(waypoint_data)
        self.waypoints_list.addItem(item)

        self.waypoint_added.emit(waypoint_data)

    def clear_waypoints(self):
        """Clear all waypoints."""
        self.waypoints.clear()
        self.waypoints_list.clear()

    def show_waypoint_context_menu(self, position):
        """Show context menu for waypoint list."""
        item = self.waypoints_list.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(lambda: self.edit_waypoint(item))
        menu.addAction(edit_action)

        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self.remove_waypoint(item))
        menu.addAction(remove_action)

        menu.addSeparator()

        move_up_action = QAction("Move Up", self)
        move_up_action.triggered.connect(lambda: self.move_waypoint_up(item))
        menu.addAction(move_up_action)

        move_down_action = QAction("Move Down", self)
        move_down_action.triggered.connect(lambda: self.move_waypoint_down(item))
        menu.addAction(move_down_action)

        menu.exec(self.waypoints_list.mapToGlobal(position))

    def edit_waypoint(self, item):
        """Edit a waypoint."""
        if isinstance(item, WaypointItem):
            current_address = item.waypoint_data.get('address', '')
            new_address, ok = QInputDialog.getText(
                self, "Edit Waypoint", "Address:",
                text=current_address
            )

            if ok and new_address.strip():
                item.waypoint_data['address'] = new_address.strip()
                item.setText(new_address.strip())

    def remove_waypoint(self, item):
        """Remove a waypoint."""
        if isinstance(item, WaypointItem):
            row = self.waypoints_list.row(item)
            if 0 <= row < len(self.waypoints):
                self.waypoints.pop(row)
                self.waypoints_list.takeItem(row)

    def move_waypoint_up(self, item):
        """Move waypoint up in the list."""
        row = self.waypoints_list.row(item)
        if row > 0:
            # Swap in data list
            self.waypoints[row], self.waypoints[row-1] = self.waypoints[row-1], self.waypoints[row]

            # Rebuild list
            self.rebuild_waypoints_list()

    def move_waypoint_down(self, item):
        """Move waypoint down in the list."""
        row = self.waypoints_list.row(item)
        if 0 <= row < len(self.waypoints) - 1:
            # Swap in data list
            self.waypoints[row], self.waypoints[row+1] = self.waypoints[row+1], self.waypoints[row]

            # Rebuild list
            self.rebuild_waypoints_list()

    def rebuild_waypoints_list(self):
        """Rebuild the waypoints list widget."""
        self.waypoints_list.clear()
        for waypoint in self.waypoints:
            item = WaypointItem(waypoint)
            self.waypoints_list.addItem(item)

    def update_route_options(self):
        """Update route options from UI controls."""
        self.route_options['avoid_tolls'] = (
            self.avoid_tolls_cb.isChecked() or
            self.avoid_tolls_detailed.isChecked()
        )
        self.route_options['avoid_highways'] = (
            self.avoid_highways_cb.isChecked() or
            self.avoid_highways_detailed.isChecked()
        )

        vehicle_map = {
            'Car': 'car',
            'Motorcycle': 'motorcycle',
            'Bicycle': 'bicycle',
            'Walking': 'walking'
        }
        self.route_options['vehicle_type'] = vehicle_map.get(
            self.vehicle_combo.currentText(), 'car'
        )

        pref_map = {
            'Fastest': 'fastest',
            'Shortest': 'shortest',
            'Most Fuel Efficient': 'eco',
            'Scenic': 'scenic'
        }
        self.route_options['route_preference'] = pref_map.get(
            self.route_pref_combo.currentText(), 'fastest'
        )

    def calculate_route(self):
        """Calculate route with current settings."""
        if not self.start_location or not self.end_location:
            QMessageBox.warning(self, "Missing Information",
                              "Please set both start and end locations")
            return

        # Emit route calculation request
        self.route_requested.emit(self.start_location, self.end_location)

        # Update UI
        self.calculate_btn.setEnabled(False)
        self.calculate_btn.setText("Calculating...")

    def on_route_calculated(self, route_data: Dict):
        """Handle route calculation result."""
        # Update UI
        self.calculate_btn.setEnabled(True)
        self.calculate_btn.setText("Calculate Route")
        self.save_route_btn.setEnabled(True)

        # Update route summary
        self.update_route_summary(route_data)

        # Store current route for saving
        self.current_route = route_data

    def update_route_summary(self, route_data: Dict):
        """Update the route summary display."""
        try:
            distance = route_data.get('distance', 0)
            duration = route_data.get('duration', 0)
            service = route_data.get('service', 'Unknown')

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
            summary = f"Distance: {distance_text}\n"
            summary += f"Duration: {duration_text}\n"
            summary += f"Route service: {service}"

            if 'steps' in route_data:
                summary += f"\nTurns: {len(route_data['steps'])}"

            self.route_summary.setPlainText(summary)

        except Exception as e:
            logger.error(f"Error updating route summary: {e}")
            self.route_summary.setPlainText("Error displaying route summary")

    def save_current_route(self):
        """Save the current route."""
        if not hasattr(self, 'current_route') or not self.current_route:
            QMessageBox.warning(self, "No Route", "No route to save")
            return

        name, ok = QInputDialog.getText(
            self, "Save Route", "Enter route name:",
            text=f"Route to {self.end_location.get('address', 'destination')}"
        )

        if ok and name.strip():
            # TODO: Save route to database
            # For now, just add to saved routes list
            route_item = {
                'name': name.strip(),
                'start_location': self.start_location,
                'end_location': self.end_location,
                'waypoints': self.waypoints.copy(),
                'route_data': self.current_route,
                'distance': self.current_route.get('distance', 0),
                'duration': self.current_route.get('duration', 0),
                'created_at': QDateTime.currentDateTime().toString()
            }

            item = SavedRouteItem(route_item)
            self.saved_routes_list.addItem(item)

            QMessageBox.information(self, "Route Saved", f"Route '{name}' saved successfully")

    def clear_route(self):
        """Clear the current route and reset form."""
        self.start_location = None
        self.end_location = None
        self.waypoints.clear()

        self.start_input.clear()
        self.end_input.clear()
        self.waypoints_list.clear()
        self.route_summary.clear()

        self.save_route_btn.setEnabled(False)
        self.update_calculate_button_state()

    def refresh_saved_routes(self):
        """Refresh the saved routes list."""
        # TODO: Load from database
        # For now, keep existing items
        pass

    def show_saved_route_context_menu(self, position):
        """Show context menu for saved routes."""
        item = self.saved_routes_list.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        load_action = QAction("Load Route", self)
        load_action.triggered.connect(lambda: self.load_saved_route(item))
        menu.addAction(load_action)

        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(lambda: self.rename_saved_route(item))
        menu.addAction(rename_action)

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_saved_route(item))
        menu.addAction(delete_action)

        menu.exec(self.saved_routes_list.mapToGlobal(position))

    def load_selected_route(self):
        """Load the selected saved route."""
        current_item = self.saved_routes_list.currentItem()
        if current_item:
            self.load_saved_route(current_item)

    def load_saved_route(self, item):
        """Load a saved route."""
        if isinstance(item, SavedRouteItem):
            route_data = item.route_data

            # Load route points
            if 'start_location' in route_data:
                self.start_location = route_data['start_location']
                self.start_input.setText(self.start_location.get('address', ''))

            if 'end_location' in route_data:
                self.end_location = route_data['end_location']
                self.end_input.setText(self.end_location.get('address', ''))

            # Load waypoints
            self.waypoints = route_data.get('waypoints', []).copy()
            self.rebuild_waypoints_list()

            # Switch to planning tab
            self.tab_widget.setCurrentIndex(0)

            # Emit route loaded pyqtSignal
            if 'route_data' in route_data:
                self.route_loaded.emit(route_data['route_data'])
                self.current_route = route_data['route_data']
                self.update_route_summary(self.current_route)
                self.save_route_btn.setEnabled(True)

            self.update_calculate_button_state()

    def rename_saved_route(self, item):
        """Rename a saved route."""
        if isinstance(item, SavedRouteItem):
            current_name = item.route_data.get('name', '')
            new_name, ok = QInputDialog.getText(
                self, "Rename Route", "New name:", text=current_name
            )

            if ok and new_name.strip():
                item.route_data['name'] = new_name.strip()
                # Update display
                distance = item.route_data.get('distance', 0)
                duration = item.route_data.get('duration', 0)

                if distance > 1000:
                    distance_text = f"{distance/1000:.1f} km"
                else:
                    distance_text = f"{distance:.0f} m"

                if duration > 3600:
                    duration_text = f"{duration//3600:.0f}h {(duration%3600)//60:.0f}m"
                else:
                    duration_text = f"{duration//60:.0f}m"

                item.setText(f"{new_name.strip()} ({distance_text}, {duration_text})")

    def delete_selected_route(self):
        """Delete the selected saved route."""
        current_item = self.saved_routes_list.currentItem()
        if current_item:
            self.delete_saved_route(current_item)

    def delete_saved_route(self, item):
        """Delete a saved route."""
        if isinstance(item, SavedRouteItem):
            route_name = item.route_data.get('name', 'this route')
            reply = QMessageBox.question(
                self, "Delete Route",
                f"Are you sure you want to delete '{route_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                row = self.saved_routes_list.row(item)
                self.saved_routes_list.takeItem(row)

    def update_calculate_button_state(self):
        """Update the calculate button enabled state."""
        can_calculate = bool(self.start_location and self.end_location)
        self.calculate_btn.setEnabled(can_calculate)

    def get_destination(self) -> Optional[Dict]:
        """Get the current destination for navigation."""
        return self.end_location

    def set_start_location(self, location_data: Dict):
        """Set start location from external source."""
        self.start_location = location_data
        address = location_data.get('address', '')
        if not address and 'latitude' in location_data:
            address = f"{location_data['latitude']:.6f}, {location_data['longitude']:.6f}"
        self.start_input.setText(address)
        self.update_calculate_button_state()

    def set_end_location(self, location_data: Dict):
        """Set end location from external source."""
        self.end_location = location_data
        address = location_data.get('address', '')
        if not address and 'latitude' in location_data:
            address = f"{location_data['latitude']:.6f}, {location_data['longitude']:.6f}"
        self.end_input.setText(address)
        self.update_calculate_button_state()

    def get_route_options(self) -> Dict:
        """Get current route calculation options."""
        self.update_route_options()
        return self.route_options.copy()
