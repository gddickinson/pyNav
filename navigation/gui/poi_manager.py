"""
POI Manager - Points of Interest management widget
Handles creation, editing, and organization of custom points of interest
"""

from typing import Dict, List, Optional
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                           QPushButton, QLineEdit, QListWidget, QListWidgetItem,
                           QFrame, QComboBox, QTextEdit, QGroupBox, QFormLayout,
                           QCheckBox, QSpinBox, QDoubleSpinBox, QMessageBox,
                           QInputDialog, QMenu, QDialog, QDialogButtonBox,
                           QTabWidget, QTreeWidget, QTreeWidgetItem)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QAction, QColor

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

class POIItem(QListWidgetItem):
    """Custom list item for POIs."""

    def __init__(self, poi_data: Dict):
        super().__init__()
        self.poi_data = poi_data

        # Format display text
        name = poi_data.get('name', 'Unnamed POI')
        category = poi_data.get('category', 'Other')

        self.setText(f"{name} ({category})")

        # Set icon based on category (could be enhanced with actual icons)
        self.update_icon()

        # Set color for favorites
        if poi_data.get('is_favorite', False):
            self.setForeground(QColor(255, 215, 0))  # Gold color for favorites

    def update_icon(self):
        """Update item icon based on category."""
        # Placeholder for category-based icons
        category = self.poi_data.get('category', 'Other').lower()

        # In a real implementation, you would load actual icons here
        # For now, just set different text prefixes
        icon_map = {
            'restaurant': '🍽️ ',
            'gas station': '⛽ ',
            'hotel': '🏨 ',
            'hospital': '🏥 ',
            'shop': '🛍️ ',
            'tourist attraction': '🎯 ',
            'park': '🌳 ',
            'other': '📍 '
        }

        prefix = icon_map.get(category, '📍 ')
        current_text = self.text()
        if not current_text.startswith(prefix):
            # Remove any existing emoji prefix
            for emoji in icon_map.values():
                if current_text.startswith(emoji):
                    current_text = current_text[len(emoji):]
                    break
            self.setText(prefix + current_text)

class POIEditDialog(QDialog):
    """Dialog for editing POI details."""

    def __init__(self, poi_data: Dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit POI" if poi_data else "New POI")
        self.setModal(True)
        self.resize(400, 500)

        self.poi_data = poi_data or {}
        self.setup_ui()
        self.populate_fields()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Basic information
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout(basic_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter POI name...")
        basic_layout.addRow("Name:", self.name_edit)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        categories = [
            "Restaurant", "Gas Station", "Hotel", "Hospital", "Pharmacy",
            "Bank", "Shop", "Tourist Attraction", "Park", "School",
            "Office", "Service", "Entertainment", "Other"
        ]
        self.category_combo.addItems(categories)
        basic_layout.addRow("Category:", self.category_combo)

        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("Enter address...")
        basic_layout.addRow("Address:", self.address_edit)

        layout.addWidget(basic_group)

        # Location
        location_group = QGroupBox("Location")
        location_layout = QFormLayout(location_group)

        self.latitude_spin = QDoubleSpinBox()
        self.latitude_spin.setRange(-90.0, 90.0)
        self.latitude_spin.setDecimals(6)
        self.latitude_spin.setSingleStep(0.000001)
        location_layout.addRow("Latitude:", self.latitude_spin)

        self.longitude_spin = QDoubleSpinBox()
        self.longitude_spin.setRange(-180.0, 180.0)
        self.longitude_spin.setDecimals(6)
        self.longitude_spin.setSingleStep(0.000001)
        location_layout.addRow("Longitude:", self.longitude_spin)

        # Pick on map button
        pick_btn = QPushButton("Pick on Map")
        pick_btn.clicked.connect(self.pick_on_map)
        location_layout.addRow(pick_btn)

        layout.addWidget(location_group)

        # Contact information
        contact_group = QGroupBox("Contact Information")
        contact_layout = QFormLayout(contact_group)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Phone number...")
        contact_layout.addRow("Phone:", self.phone_edit)

        self.website_edit = QLineEdit()
        self.website_edit.setPlaceholderText("Website URL...")
        contact_layout.addRow("Website:", self.website_edit)

        layout.addWidget(contact_group)

        # Additional details
        details_group = QGroupBox("Additional Details")
        details_layout = QVBoxLayout(details_group)

        # Rating
        rating_layout = QHBoxLayout()
        rating_layout.addWidget(QLabel("Rating:"))
        self.rating_spin = QDoubleSpinBox()
        self.rating_spin.setRange(0.0, 5.0)
        self.rating_spin.setSingleStep(0.1)
        self.rating_spin.setSuffix(" stars")
        rating_layout.addWidget(self.rating_spin)
        rating_layout.addStretch()
        details_layout.addLayout(rating_layout)

        # Favorite checkbox
        self.favorite_check = QCheckBox("Mark as favorite")
        details_layout.addWidget(self.favorite_check)

        # Notes
        details_layout.addWidget(QLabel("Notes:"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.setPlaceholderText("Additional notes about this POI...")
        details_layout.addWidget(self.notes_edit)

        layout.addWidget(details_group)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate_fields(self):
        """Populate fields with existing POI data."""
        if not self.poi_data:
            return

        self.name_edit.setText(self.poi_data.get('name', ''))

        category = self.poi_data.get('category', '')
        index = self.category_combo.findText(category)
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
        else:
            self.category_combo.setCurrentText(category)

        self.address_edit.setText(self.poi_data.get('address', ''))
        self.latitude_spin.setValue(self.poi_data.get('latitude', 0.0))
        self.longitude_spin.setValue(self.poi_data.get('longitude', 0.0))
        self.phone_edit.setText(self.poi_data.get('phone', ''))
        self.website_edit.setText(self.poi_data.get('website', ''))
        self.rating_spin.setValue(self.poi_data.get('rating', 0.0))
        self.favorite_check.setChecked(self.poi_data.get('is_favorite', False))
        self.notes_edit.setPlainText(self.poi_data.get('notes', ''))

    def pick_on_map(self):
        """Enable map picking mode for location."""
        # TODO: pyqtSignal to main window to enable map picking mode
        QMessageBox.information(self, "Pick Location",
                              "Click on the map to set POI location")

    def get_poi_data(self) -> Dict:
        """Get POI data from form fields."""
        return {
            'name': self.name_edit.text().strip(),
            'category': self.category_combo.currentText().strip(),
            'address': self.address_edit.text().strip(),
            'latitude': self.latitude_spin.value(),
            'longitude': self.longitude_spin.value(),
            'phone': self.phone_edit.text().strip(),
            'website': self.website_edit.text().strip(),
            'rating': self.rating_spin.value(),
            'is_favorite': self.favorite_check.isChecked(),
            'notes': self.notes_edit.toPlainText().strip()
        }

    def accept(self):
        """Validate and accept the dialog."""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation Error",
                              "POI name is required")
            return

        if (self.latitude_spin.value() == 0.0 and
            self.longitude_spin.value() == 0.0):
            reply = QMessageBox.question(
                self, "Location Warning",
                "Location is set to 0,0. Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        super().accept()

class CategoryTreeWidget(QTreeWidget):
    """Tree widget showing POIs organized by category."""

    def __init__(self):
        super().__init__()
        self.setHeaderLabels(["Name", "Distance"])
        self.setRootIsDecorated(True)
        self.category_items = {}

    def add_poi(self, poi_data: Dict):
        """Add a POI to the tree."""
        category = poi_data.get('category', 'Other')

        # Create category item if it doesn't exist
        if category not in self.category_items:
            category_item = QTreeWidgetItem([category, ""])
            category_item.setFlags(
                category_item.flags() & ~Qt.ItemFlag.ItemIsSelectable
            )
            font = QFont()
            font.setBold(True)
            category_item.setFont(0, font)
            self.addTopLevelItem(category_item)
            self.category_items[category] = category_item

        # Add POI item under category
        poi_item = QTreeWidgetItem([
            poi_data.get('name', 'Unnamed'),
            f"{poi_data.get('distance', 0):.1f} km" if 'distance' in poi_data else ""
        ])
        poi_item.setData(0, Qt.ItemDataRole.UserRole, poi_data)

        if poi_data.get('is_favorite', False):
            poi_item.setForeground(0, QColor(255, 215, 0))

        self.category_items[category].addChild(poi_item)

    def clear_pois(self):
        """Clear all POIs from the tree."""
        self.clear()
        self.category_items.clear()

    def get_selected_poi(self) -> Optional[Dict]:
        """Get the currently selected POI data."""
        current = self.currentItem()
        if current and current.parent():  # Ensure it's a POI item, not category
            return current.data(0, Qt.ItemDataRole.UserRole)
        return None

class POIManager(QWidget):
    """Main POI management widget."""

    # pyqtSignals
    poi_selected = pyqtSignal(dict)  # POI data
    poi_added = pyqtSignal(dict)     # New POI data
    poi_updated = pyqtSignal(dict)   # Updated POI data
    poi_deleted = pyqtSignal(int)    # POI ID

    def __init__(self, parent=None):
        super().__init__(parent)

        # POI data
        self.pois = []  # List of POI dictionaries
        self.filtered_pois = []  # Current filtered/searched POIs
        self.current_location = None  # For distance calculations

        self.setup_ui()
        logger.info("POI Manager initialized")

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Header
        header = QGroupBox("Points of Interest")
        header_layout = QVBoxLayout(header)

        # Search and filter controls
        controls_layout = QHBoxLayout()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search POIs...")
        self.search_edit.textChanged.connect(self.filter_pois)
        controls_layout.addWidget(self.search_edit)

        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories")
        self.category_filter.currentTextChanged.connect(self.filter_pois)
        controls_layout.addWidget(self.category_filter)

        self.favorites_only = QCheckBox("Favorites only")
        self.favorites_only.stateChanged.connect(self.filter_pois)
        controls_layout.addWidget(self.favorites_only)

        header_layout.addLayout(controls_layout)
        layout.addWidget(header)

        # Tab widget for different views
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # List view tab
        self.setup_list_view_tab()

        # Category tree view tab
        self.setup_tree_view_tab()

        # POI controls
        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame)

        self.add_btn = QPushButton("Add POI")
        self.add_btn.clicked.connect(self.add_new_poi)
        self.add_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        controls_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self.edit_selected_poi)
        self.edit_btn.setEnabled(False)
        controls_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_selected_poi)
        self.delete_btn.setEnabled(False)
        controls_layout.addWidget(self.delete_btn)

        self.navigate_btn = QPushButton("Navigate To")
        self.navigate_btn.clicked.connect(self.navigate_to_selected)
        self.navigate_btn.setEnabled(False)
        controls_layout.addWidget(self.navigate_btn)

        layout.addWidget(controls_frame)

        # Status
        self.status_label = QLabel("0 POIs")
        layout.addWidget(self.status_label)

    def setup_list_view_tab(self):
        """Set up the list view tab."""
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)

        self.poi_list = QListWidget()
        self.poi_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.poi_list.customContextMenuRequested.connect(self.show_context_menu)
        self.poi_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.poi_list.itemDoubleClicked.connect(self.edit_selected_poi)
        list_layout.addWidget(self.poi_list)

        self.tab_widget.addTab(list_widget, "List View")

    def setup_tree_view_tab(self):
        """Set up the tree view tab."""
        tree_widget = QWidget()
        tree_layout = QVBoxLayout(tree_widget)

        self.poi_tree = CategoryTreeWidget()
        self.poi_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.poi_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.poi_tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        self.poi_tree.itemDoubleClicked.connect(self.edit_selected_poi)
        tree_layout.addWidget(self.poi_tree)

        self.tab_widget.addTab(tree_widget, "By Category")

    def add_new_poi(self):
        """Add a new POI."""
        dialog = POIEditDialog(parent=self)

        # Pre-populate with current location if available
        if self.current_location:
            dialog.latitude_spin.setValue(self.current_location.get('latitude', 0))
            dialog.longitude_spin.setValue(self.current_location.get('longitude', 0))

        if dialog.exec() == QDialog.DialogCode.Accepted:
            poi_data = dialog.get_poi_data()

            # Add ID and timestamps
            poi_data['id'] = len(self.pois) + 1  # Simple ID assignment
            poi_data['created_at'] = QDateTime.currentDateTime().toString()
            poi_data['updated_at'] = poi_data['created_at']

            self.add_poi(poi_data)
            self.poi_added.emit(poi_data)

            QMessageBox.information(self, "POI Added",
                                  f"POI '{poi_data['name']}' added successfully")

    def add_poi(self, poi_data: Dict):
        """Add POI to the manager."""
        self.pois.append(poi_data)
        self.update_category_filter()
        self.refresh_displays()

    def edit_selected_poi(self):
        """Edit the selected POI."""
        poi_data = self.get_selected_poi()
        if not poi_data:
            return

        dialog = POIEditDialog(poi_data, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_data = dialog.get_poi_data()
            updated_data['id'] = poi_data['id']  # Preserve ID
            updated_data['created_at'] = poi_data.get('created_at')
            updated_data['updated_at'] = QDateTime.currentDateTime().toString()

            # Find and update in list
            for i, poi in enumerate(self.pois):
                if poi.get('id') == poi_data['id']:
                    self.pois[i] = updated_data
                    break

            self.refresh_displays()
            self.poi_updated.emit(updated_data)

            QMessageBox.information(self, "POI Updated",
                                  f"POI '{updated_data['name']}' updated successfully")

    def delete_selected_poi(self):
        """Delete the selected POI."""
        poi_data = self.get_selected_poi()
        if not poi_data:
            return

        reply = QMessageBox.question(
            self, "Delete POI",
            f"Are you sure you want to delete '{poi_data['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Remove from list
            self.pois = [poi for poi in self.pois if poi.get('id') != poi_data['id']]
            self.refresh_displays()
            self.poi_deleted.emit(poi_data['id'])

            QMessageBox.information(self, "POI Deleted",
                                  f"POI '{poi_data['name']}' deleted successfully")

    def navigate_to_selected(self):
        """Navigate to the selected POI."""
        poi_data = self.get_selected_poi()
        if poi_data:
            self.poi_selected.emit(poi_data)

    def get_selected_poi(self) -> Optional[Dict]:
        """Get the currently selected POI."""
        if self.tab_widget.currentIndex() == 0:  # List view
            current_item = self.poi_list.currentItem()
            if isinstance(current_item, POIItem):
                return current_item.poi_data
        else:  # Tree view
            return self.poi_tree.get_selected_poi()
        return None

    def show_context_menu(self, position):
        """Show context menu for POI items."""
        poi_data = self.get_selected_poi()
        if not poi_data:
            return

        menu = QMenu(self)

        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(self.edit_selected_poi)
        menu.addAction(edit_action)

        navigate_action = QAction("Navigate To", self)
        navigate_action.triggered.connect(self.navigate_to_selected)
        menu.addAction(navigate_action)

        menu.addSeparator()

        # Toggle favorite
        if poi_data.get('is_favorite', False):
            fav_action = QAction("Remove from Favorites", self)
            fav_action.triggered.connect(lambda: self.toggle_favorite(poi_data, False))
        else:
            fav_action = QAction("Add to Favorites", self)
            fav_action.triggered.connect(lambda: self.toggle_favorite(poi_data, True))
        menu.addAction(fav_action)

        menu.addSeparator()

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self.delete_selected_poi)
        menu.addAction(delete_action)

        # Show menu
        if self.tab_widget.currentIndex() == 0:
            menu.exec(self.poi_list.mapToGlobal(position))
        else:
            menu.exec(self.poi_tree.mapToGlobal(position))

    def toggle_favorite(self, poi_data: Dict, is_favorite: bool):
        """Toggle POI favorite status."""
        for poi in self.pois:
            if poi.get('id') == poi_data['id']:
                poi['is_favorite'] = is_favorite
                poi['updated_at'] = QDateTime.currentDateTime().toString()
                break

        self.refresh_displays()

    def on_selection_changed(self):
        """Handle selection changes in list view."""
        has_selection = bool(self.poi_list.currentItem())
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.navigate_btn.setEnabled(has_selection)

    def on_tree_selection_changed(self):
        """Handle selection changes in tree view."""
        poi_data = self.poi_tree.get_selected_poi()
        has_selection = bool(poi_data)
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.navigate_btn.setEnabled(has_selection)

    def filter_pois(self):
        """Filter POIs based on search criteria."""
        search_text = self.search_edit.text().lower()
        category_filter = self.category_filter.currentText()
        favorites_only = self.favorites_only.isChecked()

        self.filtered_pois = []

        for poi in self.pois:
            # Text search
            if search_text and search_text not in poi.get('name', '').lower():
                continue

            # Category filter
            if (category_filter != "All Categories" and
                poi.get('category', '') != category_filter):
                continue

            # Favorites filter
            if favorites_only and not poi.get('is_favorite', False):
                continue

            self.filtered_pois.append(poi)

        self.refresh_displays()

    def refresh_displays(self):
        """Refresh both list and tree displays."""
        self.refresh_list_view()
        self.refresh_tree_view()
        self.update_status()

    def refresh_list_view(self):
        """Refresh the list view."""
        self.poi_list.clear()

        pois_to_show = self.filtered_pois or self.pois
        for poi in pois_to_show:
            item = POIItem(poi)
            self.poi_list.addItem(item)

    def refresh_tree_view(self):
        """Refresh the tree view."""
        self.poi_tree.clear_pois()

        pois_to_show = self.filtered_pois or self.pois
        for poi in pois_to_show:
            # Calculate distance if current location is available
            if self.current_location:
                poi_copy = poi.copy()
                distance = self.calculate_distance(
                    self.current_location.get('latitude', 0),
                    self.current_location.get('longitude', 0),
                    poi.get('latitude', 0),
                    poi.get('longitude', 0)
                )
                poi_copy['distance'] = distance
                self.poi_tree.add_poi(poi_copy)
            else:
                self.poi_tree.add_poi(poi)

        # Expand all categories
        self.poi_tree.expandAll()

    def update_category_filter(self):
        """Update the category filter dropdown."""
        current_text = self.category_filter.currentText()

        # Get unique categories
        categories = set()
        for poi in self.pois:
            category = poi.get('category', 'Other')
            if category:
                categories.add(category)

        # Update combo box
        self.category_filter.clear()
        self.category_filter.addItem("All Categories")
        for category in sorted(categories):
            self.category_filter.addItem(category)

        # Restore previous selection if possible
        index = self.category_filter.findText(current_text)
        if index >= 0:
            self.category_filter.setCurrentIndex(index)

    def update_status(self):
        """Update the status label."""
        total = len(self.pois)
        shown = len(self.filtered_pois) if self.filtered_pois else total

        if shown == total:
            self.status_label.setText(f"{total} POIs")
        else:
            self.status_label.setText(f"{shown} of {total} POIs")

    def calculate_distance(self, lat1: float, lon1: float,
                          lat2: float, lon2: float) -> float:
        """Calculate distance between two points in kilometers."""
        import math

        R = 6371  # Earth radius in kilometers

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def update_current_location(self, location: Dict):
        """Update current location for distance calculations."""
        self.current_location = location

        # Refresh tree view to update distances
        if self.tab_widget.currentIndex() == 1:
            self.refresh_tree_view()

    def load_pois_from_database(self, database):
        """Load POIs from database."""
        # TODO: Load POIs from database
        # For now, add some sample POIs for demonstration
        sample_pois = [
            {
                'id': 1,
                'name': 'Central Park',
                'category': 'Park',
                'latitude': 40.7829,
                'longitude': -73.9654,
                'address': 'New York, NY',
                'notes': 'Great place for walking and relaxation',
                'is_favorite': True,
                'rating': 4.5,
                'created_at': QDateTime.currentDateTime().toString()
            },
            {
                'id': 2,
                'name': 'Times Square',
                'category': 'Tourist Attraction',
                'latitude': 40.7580,
                'longitude': -73.9855,
                'address': 'Times Square, New York, NY',
                'notes': 'Busy tourist area',
                'is_favorite': False,
                'rating': 3.5,
                'created_at': QDateTime.currentDateTime().toString()
            }
        ]

        for poi in sample_pois:
            self.add_poi(poi)

    def export_pois(self, file_path: str):
        """Export POIs to file."""
        import json

        try:
            with open(file_path, 'w') as f:
                json.dump(self.pois, f, indent=2)
            QMessageBox.information(self, "Export Success",
                                  f"Exported {len(self.pois)} POIs to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")

    def import_pois(self, file_path: str):
        """Import POIs from file."""
        import json

        try:
            with open(file_path, 'r') as f:
                imported_pois = json.load(f)

            count = 0
            for poi in imported_pois:
                if 'name' in poi and 'latitude' in poi and 'longitude' in poi:
                    # Assign new ID to avoid conflicts
                    poi['id'] = max([p.get('id', 0) for p in self.pois] + [0]) + 1
                    self.add_poi(poi)
                    count += 1

            QMessageBox.information(self, "Import Success",
                                  f"Imported {count} POIs from {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import: {str(e)}")
