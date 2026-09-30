"""
Navigation Map Widget - Interactive map display with navigation features
Handles map rendering, user interaction, route display, and navigation overlays
Fixed for PyQt6 type strictness
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (QPainter, QPen, QColor, QBrush, QPixmap, QPolygonF,
                        QFont, QPainterPath, QLinearGradient, QRadialGradient)

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

class NavigationMapWidget(QWidget):
    """Interactive map widget with navigation capabilities."""

    # Signals
    location_clicked = pyqtSignal(float, float)  # lat, lon
    poi_selected = pyqtSignal(dict)  # POI data
    route_clicked = pyqtSignal(dict)  # Route segment data
    zoom_changed = pyqtSignal(int)
    center_changed = pyqtSignal(float, float)  # lat, lon

    def __init__(self, map_manager, location_manager, routing_engine):
        super().__init__()

        self.map_manager = map_manager
        self.location_manager = location_manager
        self.routing_engine = routing_engine

        # Map state
        self.zoom_level = 15
        self.center_lat = 40.7589  # Default to NYC
        self.center_lon = -73.9851
        self.viewport_bounds = None

        # Interaction state
        self.dragging = False
        self.last_drag_pos = None
        self.zoom_gesture_active = False

        # Navigation state
        self.navigation_mode = False
        self.current_route = None
        self.user_location = None
        self.user_heading = 0
        self.route_progress = 0  # 0-1

        # Display options
        self.layers = {
            'satellite': False,
            'traffic': False,
            'poi': True
        }

        # Markers and overlays
        self.search_markers = []
        self.poi_markers = []
        self.route_waypoints = []

        # Setup UI
        self.setup_ui()
        self.setup_interactions()

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(100)  # 10 FPS

        logger.info("Navigation map widget initialized")

    def setup_ui(self):
        """Setup the UI components."""
        self.setMinimumSize(600, 400)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Calculate initial viewport bounds
        self.calculate_viewport_bounds()

    def setup_interactions(self):
        """Setup mouse and keyboard interactions."""
        # Enable mouse wheel for zooming
        self.setEnabled(True)

    def calculate_viewport_bounds(self):
        """Calculate current viewport bounds in lat/lon."""
        if self.width() <= 0 or self.height() <= 0:
            return

        # Calculate degrees per pixel at current zoom and latitude
        meters_per_pixel = (156543.03392 * math.cos(math.radians(self.center_lat)) /
                           (2 ** self.zoom_level))

        # Convert to approximate degrees (very rough)
        lat_degrees_per_pixel = meters_per_pixel / 111320  # meters per degree latitude
        lon_degrees_per_pixel = meters_per_pixel / (111320 * math.cos(math.radians(self.center_lat)))

        # Calculate bounds
        half_width_deg = self.width() / 2 * lon_degrees_per_pixel
        half_height_deg = self.height() / 2 * lat_degrees_per_pixel

        self.viewport_bounds = (
            self.center_lon - half_width_deg,  # min_lon
            self.center_lat - half_height_deg,  # min_lat
            self.center_lon + half_width_deg,   # max_lon
            self.center_lat + half_height_deg   # max_lat
        )

    def paintEvent(self, event):
        """Paint the map."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            # Fill background
            painter.fillRect(self.rect(), QColor(240, 240, 240))

            if not self.viewport_bounds:
                self.calculate_viewport_bounds()
                return

            # Render base map tiles
            self.render_map_tiles(painter)

            # Render additional layers
            if self.layers['satellite']:
                self.render_satellite_layer(painter)

            if self.layers['traffic']:
                self.render_traffic_layer(painter)

            # Render route
            if self.current_route:
                self.render_route(painter)

            # Render POIs
            if self.layers['poi']:
                self.render_pois(painter)

            # Render markers
            self.render_markers(painter)

            # Render user location
            if self.user_location:
                self.render_user_location(painter)

            # Render navigation overlays
            if self.navigation_mode:
                self.render_navigation_overlays(painter)

            # Render UI overlays (zoom controls, scale, etc.)
            self.render_ui_overlays(painter)

        except Exception as e:
            logger.error(f"Error painting map: {e}")
            painter.fillRect(self.rect(), QColor(255, 200, 200))
            painter.setPen(QColor(100, 0, 0))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"Map Error: {str(e)}")

    def render_map_tiles(self, painter):
        """Render the base map tiles."""
        if not self.viewport_bounds:
            return

        try:
            self.map_manager.render_layers(
                painter, self.viewport_bounds,
                self.zoom_level, self.width(), self.height()
            )
        except Exception as e:
            logger.error(f"Error rendering map tiles: {e}")

    def render_satellite_layer(self, painter):
        """Render satellite imagery layer."""
        # This would be handled by map_manager with satellite tiles
        pass

    def render_traffic_layer(self, painter):
        """Render traffic information layer."""
        # Placeholder for traffic layer rendering
        painter.setOpacity(0.7)
        painter.setPen(QPen(QColor(255, 100, 100), 3))

        # Example: draw some traffic lines (in real implementation,
        # this would come from traffic data)
        if self.zoom_level >= 12:
            # Draw sample traffic congestion - using QPointF for PyQt6 compatibility
            painter.drawLine(QPointF(100, 200), QPointF(300, 250))
            painter.drawLine(QPointF(150, 100), QPointF(400, 150))

        painter.setOpacity(1.0)

    def render_route(self, painter):
        """Render the current route."""
        if not self.current_route or not self.viewport_bounds:
            return

        coordinates = self.current_route.get('coordinates', [])
        if len(coordinates) < 2:
            return

        try:
            # Convert route coordinates to screen points
            screen_points = []
            for lat, lon in coordinates:
                screen_x, screen_y = self.world_to_screen(lat, lon)
                screen_points.append(QPointF(screen_x, screen_y))

            # Draw route line
            if len(screen_points) >= 2:
                # Main route line
                painter.setPen(QPen(QColor(0, 100, 255), 6))
                for i in range(len(screen_points) - 1):
                    painter.drawLine(screen_points[i], screen_points[i + 1])

                # Route outline for better visibility
                painter.setPen(QPen(QColor(255, 255, 255), 8))
                for i in range(len(screen_points) - 1):
                    painter.drawLine(screen_points[i], screen_points[i + 1])

                painter.setPen(QPen(QColor(0, 100, 255), 4))
                for i in range(len(screen_points) - 1):
                    painter.drawLine(screen_points[i], screen_points[i + 1])

            # Draw route waypoints/turn points
            steps = self.current_route.get('steps', [])
            for step in steps:
                if hasattr(step, 'latitude') and hasattr(step, 'longitude'):
                    screen_x, screen_y = self.world_to_screen(step.latitude, step.longitude)

                    # Draw turn indicator
                    if step.turn_type != 'straight':
                        painter.setBrush(QBrush(QColor(255, 255, 0)))
                        painter.setPen(QPen(QColor(0, 0, 0), 2))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 8, 8)

        except Exception as e:
            logger.error(f"Error rendering route: {e}")

    def render_pois(self, painter):
        """Render points of interest."""
        if self.zoom_level < 12:  # Don't show POIs at low zoom
            return

        try:
            # Example POI rendering (in real implementation,
            # POIs would come from database or map_manager)
            poi_color_map = {
                'restaurant': QColor(255, 100, 100),
                'gas_station': QColor(100, 255, 100),
                'hospital': QColor(255, 255, 100),
                'hotel': QColor(100, 100, 255)
            }

            for poi in self.poi_markers:
                lat, lon = poi.get('latitude', 0), poi.get('longitude', 0)
                if not self.is_point_in_viewport(lat, lon):
                    continue

                screen_x, screen_y = self.world_to_screen(lat, lon)
                category = poi.get('category', 'other')
                color = poi_color_map.get(category, QColor(128, 128, 128))

                # Draw POI marker
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                painter.drawEllipse(QPointF(screen_x, screen_y), 6, 6)

                # Draw POI label at higher zoom levels
                if self.zoom_level >= 15:
                    painter.setPen(QColor(0, 0, 0))
                    painter.drawText(int(screen_x + 10), int(screen_y + 4), poi.get('name', ''))

        except Exception as e:
            logger.error(f"Error rendering POIs: {e}")

    def render_markers(self, painter):
        """Render search markers and custom markers."""
        try:
            for marker in self.search_markers:
                lat, lon = marker['latitude'], marker['longitude']
                if not self.is_point_in_viewport(lat, lon):
                    continue

                screen_x, screen_y = self.world_to_screen(lat, lon)

                # Draw search marker
                painter.setBrush(QBrush(QColor(255, 0, 0)))
                painter.setPen(QPen(QColor(255, 255, 255), 2))

                # Draw marker pin shape
                pin_path = QPainterPath()
                pin_path.addEllipse(QPointF(screen_x, screen_y - 15), 8, 8)
                pin_path.moveTo(screen_x, screen_y - 7)
                pin_path.lineTo(screen_x, screen_y)
                painter.drawPath(pin_path)

                # Draw label
                if 'label' in marker:
                    painter.setPen(QColor(0, 0, 0))
                    painter.drawText(int(screen_x + 15), int(screen_y - 10), marker['label'])

        except Exception as e:
            logger.error(f"Error rendering markers: {e}")

    def render_user_location(self, painter):
        """Render current user location."""
        if not self.user_location:
            return

        try:
            lat = self.user_location.get('latitude', 0)
            lon = self.user_location.get('longitude', 0)

            if not self.is_point_in_viewport(lat, lon):
                return

            screen_x, screen_y = self.world_to_screen(lat, lon)

            # Draw accuracy circle if available
            accuracy = self.user_location.get('accuracy', 0)
            if accuracy and accuracy > 0:  # Check for None and > 0
                # Convert accuracy (meters) to screen pixels (approximate)
                meters_per_pixel = (156543.03392 * math.cos(math.radians(lat)) /
                                   (2 ** self.zoom_level))
                accuracy_pixels = accuracy / meters_per_pixel

                if accuracy_pixels > 5:  # Only draw if visible
                    painter.setBrush(QBrush(QColor(0, 100, 255, 50)))
                    painter.setPen(QPen(QColor(0, 100, 255, 100), 1))
                    painter.drawEllipse(QPointF(screen_x, screen_y),
                                       accuracy_pixels, accuracy_pixels)

            # Draw user location dot
            painter.setBrush(QBrush(QColor(0, 100, 255)))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(QPointF(screen_x, screen_y), 8, 8)

            # Draw heading indicator if available
            heading = self.user_location.get('heading')
            speed = self.user_location.get('speed')

            # Only draw heading if both heading and speed are available and speed > 1
            if (heading is not None and speed is not None and
                isinstance(heading, (int, float)) and isinstance(speed, (int, float)) and
                speed > 1):
                self.draw_heading_indicator(painter, screen_x, screen_y, heading)

        except Exception as e:
            logger.error(f"Error rendering user location: {e}")

    def draw_heading_indicator(self, painter, x, y, heading):
        """Draw heading/direction indicator."""
        try:
            # Convert heading to radians
            heading_rad = math.radians(heading)

            # Calculate arrow points
            length = 15
            arrow_x = x + length * math.sin(heading_rad)
            arrow_y = y - length * math.cos(heading_rad)

            # Draw arrow - use QPointF for PyQt6 compatibility
            painter.setPen(QPen(QColor(255, 255, 255), 3))
            painter.drawLine(QPointF(x, y), QPointF(arrow_x, arrow_y))

            # Draw arrow head
            head_length = 6
            head_angle = math.pi / 6  # 30 degrees

            left_x = arrow_x - head_length * math.sin(heading_rad - head_angle)
            left_y = arrow_y + head_length * math.cos(heading_rad - head_angle)
            right_x = arrow_x - head_length * math.sin(heading_rad + head_angle)
            right_y = arrow_y + head_length * math.cos(heading_rad + head_angle)

            arrow_head = QPolygonF([
                QPointF(arrow_x, arrow_y),
                QPointF(left_x, left_y),
                QPointF(right_x, right_y)
            ])

            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.drawPolygon(arrow_head)

        except Exception as e:
            logger.error(f"Error drawing heading indicator: {e}")

    def render_navigation_overlays(self, painter):
        """Render navigation-specific overlays."""
        if not self.navigation_mode or not self.current_route:
            return

        try:
            # Draw navigation progress bar
            self.draw_navigation_progress(painter)

            # Draw next turn indicator
            self.draw_next_turn_indicator(painter)

            # Draw speed and distance info
            self.draw_navigation_info(painter)

        except Exception as e:
            logger.error(f"Error rendering navigation overlays: {e}")

    def draw_navigation_progress(self, painter):
        """Draw route progress bar."""
        try:
            # Progress bar at top of screen
            bar_height = 6
            bar_width = self.width() - 20
            bar_x = 10
            bar_y = 10

            # Background
            painter.setBrush(QBrush(QColor(200, 200, 200, 180)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(bar_x, bar_y, bar_width, bar_height)

            # Progress
            progress_width = int(bar_width * self.route_progress)
            painter.setBrush(QBrush(QColor(0, 150, 0)))
            painter.drawRect(bar_x, bar_y, progress_width, bar_height)

        except Exception as e:
            logger.error(f"Error drawing navigation progress: {e}")

    def draw_next_turn_indicator(self, painter):
        """Draw next turn indicator."""
        try:
            # Example turn indicator in top-right corner
            if not self.current_route or not self.current_route.get('steps'):
                return

            # Find next turn (simplified)
            next_step = None
            for step in self.current_route['steps']:
                if hasattr(step, 'turn_type') and step.turn_type != 'straight':
                    next_step = step
                    break

            if not next_step:
                return

            # Draw turn indicator
            indicator_size = 60
            indicator_x = self.width() - indicator_size - 20
            indicator_y = 30

            # Background circle
            painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(indicator_x, indicator_y, indicator_size, indicator_size)

            # Turn arrow (simplified - would need proper turn icons)
            painter.setPen(QPen(QColor(255, 255, 255), 4))
            center_x = indicator_x + indicator_size // 2
            center_y = indicator_y + indicator_size // 2

            if 'left' in next_step.turn_type:
                # Draw left arrow
                painter.drawLine(QPointF(center_x + 10, center_y), QPointF(center_x - 10, center_y))
                painter.drawLine(QPointF(center_x - 10, center_y), QPointF(center_x - 5, center_y - 5))
                painter.drawLine(QPointF(center_x - 10, center_y), QPointF(center_x - 5, center_y + 5))
            elif 'right' in next_step.turn_type:
                # Draw right arrow
                painter.drawLine(QPointF(center_x - 10, center_y), QPointF(center_x + 10, center_y))
                painter.drawLine(QPointF(center_x + 10, center_y), QPointF(center_x + 5, center_y - 5))
                painter.drawLine(QPointF(center_x + 10, center_y), QPointF(center_x + 5, center_y + 5))

        except Exception as e:
            logger.error(f"Error drawing next turn indicator: {e}")

    def draw_navigation_info(self, painter):
        """Draw navigation information panel."""
        try:
            # Info panel in bottom-left corner
            panel_width = 200
            panel_height = 80
            panel_x = 20
            panel_y = self.height() - panel_height - 20

            # Background
            painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(panel_x, panel_y, panel_width, panel_height, 5, 5)

            # Text
            painter.setPen(QColor(255, 255, 255))
            font = QFont()
            font.setPointSize(12)
            painter.setFont(font)

            # Speed (if available)
            if self.user_location and 'speed' in self.user_location:
                speed_kmh = self.user_location['speed'] * 3.6  # Convert m/s to km/h
                painter.drawText(panel_x + 10, panel_y + 20, f"Speed: {speed_kmh:.0f} km/h")

            # Remaining distance/time (would come from routing_engine)
            painter.drawText(panel_x + 10, panel_y + 40, "Distance: 2.3 km")
            painter.drawText(panel_x + 10, panel_y + 60, "Time: 8 min")

        except Exception as e:
            logger.error(f"Error drawing navigation info: {e}")

    def render_ui_overlays(self, painter):
        """Render UI overlays like scale bar, attributions, etc."""
        try:
            # Scale bar
            self.draw_scale_bar(painter)

            # Attribution
            self.draw_attribution(painter)

            # Zoom level indicator
            if not self.navigation_mode:  # Hide in nav mode to reduce clutter
                painter.setPen(QColor(100, 100, 100))
                font = QFont()
                font.setPointSize(10)
                painter.setFont(font)
                painter.drawText(10, self.height() - 10, f"Zoom: {self.zoom_level}")

        except Exception as e:
            logger.error(f"Error rendering UI overlays: {e}")

    def draw_scale_bar(self, painter):
        """Draw scale bar."""
        if not self.viewport_bounds:
            return

        try:
            # Calculate scale at current zoom and latitude
            meters_per_pixel = (156543.03392 * math.cos(math.radians(self.center_lat)) /
                               (2 ** self.zoom_level))

            # Scale bar in bottom-right
            scale_pixels = 100
            scale_meters = meters_per_pixel * scale_pixels

            # Round to nice number
            if scale_meters >= 1000:
                scale_meters = round(scale_meters / 1000) * 1000
                scale_label = f"{scale_meters/1000:.0f} km"
            else:
                scale_meters = round(scale_meters / 100) * 100
                scale_label = f"{scale_meters:.0f} m"

            # Adjust pixels for rounded distance
            actual_pixels = scale_meters / meters_per_pixel

            # Draw scale bar
            bar_x = self.width() - 120
            bar_y = self.height() - 40

            painter.setPen(QPen(QColor(0, 0, 0), 2))
            # Use QPointF for line drawing to avoid PyQt6 type issues
            painter.drawLine(QPointF(bar_x, bar_y), QPointF(bar_x + actual_pixels, bar_y))
            painter.drawLine(QPointF(bar_x, bar_y - 3), QPointF(bar_x, bar_y + 3))
            painter.drawLine(QPointF(bar_x + actual_pixels, bar_y - 3),
                            QPointF(bar_x + actual_pixels, bar_y + 3))

            # Draw label
            font = QFont()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(int(bar_x), bar_y - 8, scale_label)

        except Exception as e:
            logger.error(f"Error drawing scale bar: {e}")

    def draw_attribution(self, painter):
        """Draw map attribution."""
        try:
            attribution = "© OpenStreetMap contributors"  # Would come from map_manager

            painter.setPen(QColor(100, 100, 100))
            font = QFont()
            font.setPointSize(8)
            painter.setFont(font)

            text_width = painter.fontMetrics().horizontalAdvance(attribution)
            painter.drawText(self.width() - text_width - 10, self.height() - 5, attribution)

        except Exception as e:
            logger.error(f"Error drawing attribution: {e}")

    def world_to_screen(self, lat, lon):
        """Convert world coordinates to screen coordinates."""
        if not self.viewport_bounds:
            return (0, 0)

        min_lon, min_lat, max_lon, max_lat = self.viewport_bounds

        x = ((lon - min_lon) / (max_lon - min_lon)) * self.width()
        y = ((max_lat - lat) / (max_lat - min_lat)) * self.height()

        return (x, y)

    def screen_to_world(self, x, y):
        """Convert screen coordinates to world coordinates."""
        if not self.viewport_bounds:
            return (0, 0)

        min_lon, min_lat, max_lon, max_lat = self.viewport_bounds

        lon = min_lon + (x / self.width()) * (max_lon - min_lon)
        lat = max_lat - (y / self.height()) * (max_lat - min_lat)

        return (lat, lon)

    def is_point_in_viewport(self, lat, lon):
        """Check if a point is in the current viewport."""
        if not self.viewport_bounds:
            return False

        min_lon, min_lat, max_lon, max_lat = self.viewport_bounds
        return (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon)

    # Public interface methods
    def set_map_type(self, map_type):
        """Change map type."""
        try:
            self.map_manager.set_map_type(map_type)
            self.update()
        except Exception as e:
            logger.error(f"Error setting map type: {e}")

    def toggle_layer(self, layer_name, enabled):
        """Toggle layer visibility."""
        try:
            if layer_name in self.layers:
                self.layers[layer_name] = enabled
                self.update()
        except Exception as e:
            logger.error(f"Error toggling layer: {e}")

    def center_on_location(self, latitude, longitude):
        """Center map on specific coordinates."""
        try:
            self.center_lat = latitude
            self.center_lon = longitude
            self.calculate_viewport_bounds()
            self.center_changed.emit(latitude, longitude)
            self.update()
            logger.info(f"Map centered on: {latitude:.6f}, {longitude:.6f}")
        except Exception as e:
            logger.error(f"Error centering on location: {e}")

    def set_zoom_level(self, zoom):
        """Set map zoom level."""
        try:
            self.zoom_level = max(1, min(19, zoom))
            self.calculate_viewport_bounds()
            self.zoom_changed.emit(self.zoom_level)
            self.update()
        except Exception as e:
            logger.error(f"Error setting zoom level: {e}")

    def add_search_marker(self, latitude, longitude, label=""):
        """Add a search result marker."""
        try:
            marker = {
                'latitude': latitude,
                'longitude': longitude,
                'label': label,
                'type': 'search'
            }
            self.search_markers.append(marker)
            self.update()
        except Exception as e:
            logger.error(f"Error adding search marker: {e}")

    def clear_search_markers(self):
        """Clear all search markers."""
        try:
            self.search_markers.clear()
            self.update()
        except Exception as e:
            logger.error(f"Error clearing search markers: {e}")

    def display_route(self, route):
        """Display a route on the map."""
        try:
            self.current_route = route

            # Zoom to fit route
            if route and 'coordinates' in route:
                self.zoom_to_fit_route(route['coordinates'])

            self.update()
        except Exception as e:
            logger.error(f"Error displaying route: {e}")

    def zoom_to_fit_route(self, coordinates):
        """Zoom and center to fit the entire route."""
        if not coordinates:
            return

        try:
            # Find bounds
            lats = [coord[0] for coord in coordinates]
            lons = [coord[1] for coord in coordinates]

            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)

            # Add padding
            lat_padding = (max_lat - min_lat) * 0.1
            lon_padding = (max_lon - min_lon) * 0.1

            min_lat -= lat_padding
            max_lat += lat_padding
            min_lon -= lon_padding
            max_lon += lon_padding

            # Center on route
            self.center_lat = (min_lat + max_lat) / 2
            self.center_lon = (min_lon + max_lon) / 2

            # Find appropriate zoom level
            lat_span = max_lat - min_lat
            lon_span = max_lon - min_lon

            # Calculate zoom level to fit bounds
            for zoom in range(1, 20):
                # Calculate viewport at this zoom level
                meters_per_pixel = (156543.03392 * math.cos(math.radians(self.center_lat)) /
                                   (2 ** zoom))
                lat_degrees_per_pixel = meters_per_pixel / 111320
                lon_degrees_per_pixel = meters_per_pixel / (111320 * math.cos(math.radians(self.center_lat)))

                viewport_lat_span = self.height() * lat_degrees_per_pixel
                viewport_lon_span = self.width() * lon_degrees_per_pixel

                if viewport_lat_span >= lat_span and viewport_lon_span >= lon_span:
                    self.zoom_level = max(1, zoom - 1)  # Back off one level for padding
                    break
            else:
                self.zoom_level = 19  # Max zoom if nothing fits

            self.calculate_viewport_bounds()
            self.update()

        except Exception as e:
            logger.error(f"Error zooming to fit route: {e}")

    def update_user_location(self, location):
        """Update user location display."""
        try:
            self.user_location = location

            # Auto-center in navigation mode
            if self.navigation_mode and location:
                self.center_on_location(location['latitude'], location['longitude'])

            self.update()
        except Exception as e:
            logger.error(f"Error updating user location: {e}")

    def set_navigation_mode(self, enabled):
        """Enable/disable navigation mode."""
        try:
            self.navigation_mode = enabled

            if enabled:
                # Switch to navigation-optimized view
                self.zoom_level = max(16, self.zoom_level)  # Ensure good detail

            self.update()
        except Exception as e:
            logger.error(f"Error setting navigation mode: {e}")

    def update_navigation_progress(self, location):
        """Update navigation progress."""
        try:
            if not self.current_route or not location:
                return

            # Calculate progress along route (simplified)
            # In real implementation, this would be more sophisticated
            coordinates = self.current_route.get('coordinates', [])
            if coordinates:
                total_distance = self.current_route.get('distance', 1)

                # Find closest point on route and calculate progress
                # This is a simplified version
                self.route_progress = min(1.0, self.route_progress + 0.01)  # Fake progress

        except Exception as e:
            logger.error(f"Error updating navigation progress: {e}")

    def update_display(self):
        """Periodic display update."""
        try:
            # Preload tiles around current view
            if self.viewport_bounds:
                self.map_manager.preload_tiles(
                    self.center_lat, self.center_lon, self.zoom_level, 1
                )
        except Exception as e:
            logger.debug(f"Error in display update: {e}")

    # Event handlers
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self.dragging = True
                self.last_drag_pos = event.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
        except Exception as e:
            logger.error(f"Error in mouse press: {e}")

    def mouseMoveEvent(self, event):
        """Handle mouse move events."""
        try:
            if self.dragging and self.last_drag_pos:
                # Calculate drag delta
                dx = event.pos().x() - self.last_drag_pos.x()
                dy = event.pos().y() - self.last_drag_pos.y()

                # Convert to world coordinates
                if self.viewport_bounds:
                    min_lon, min_lat, max_lon, max_lat = self.viewport_bounds

                    world_width = max_lon - min_lon
                    world_height = max_lat - min_lat

                    # Update center
                    self.center_lon -= (dx / self.width()) * world_width
                    self.center_lat += (dy / self.height()) * world_height

                    self.calculate_viewport_bounds()
                    self.update()

                self.last_drag_pos = event.pos()
        except Exception as e:
            logger.error(f"Error in mouse move: {e}")

    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self.dragging = False
                self.setCursor(Qt.CursorShape.ArrowCursor)

                # If it was just a click (not drag), emit location_clicked
                if self.last_drag_pos and (event.pos() - self.last_drag_pos).manhattanLength() < 5:
                    lat, lon = self.screen_to_world(event.pos().x(), event.pos().y())
                    self.location_clicked.emit(lat, lon)
        except Exception as e:
            logger.error(f"Error in mouse release: {e}")

    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming."""
        try:
            delta = event.angleDelta().y()

            if delta > 0:
                new_zoom = min(19, self.zoom_level + 1)
            else:
                new_zoom = max(1, self.zoom_level - 1)

            if new_zoom != self.zoom_level:
                # Zoom toward mouse cursor
                mouse_pos = event.position()
                lat_before, lon_before = self.screen_to_world(mouse_pos.x(), mouse_pos.y())

                self.zoom_level = new_zoom
                self.calculate_viewport_bounds()

                # Adjust center to keep mouse position stable
                lat_after, lon_after = self.screen_to_world(mouse_pos.x(), mouse_pos.y())
                self.center_lat += lat_before - lat_after
                self.center_lon += lon_before - lon_after

                self.calculate_viewport_bounds()
                self.zoom_changed.emit(self.zoom_level)
                self.update()
        except Exception as e:
            logger.error(f"Error in wheel event: {e}")

    def resizeEvent(self, event):
        """Handle widget resize."""
        try:
            super().resizeEvent(event)
            self.calculate_viewport_bounds()
            self.update()
        except Exception as e:
            logger.error(f"Error in resize event: {e}")
