"""
Vector Tile Renderer - Renders Mapbox Vector Tiles (PBF format) using PyQt6
"""

import gzip
import mapbox_vector_tile
from typing import Dict, List, Tuple, Optional
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF, QPainterPath, QFont
from PyQt6.QtCore import QPointF, Qt
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, MultiLineString
from shapely import affinity
import math

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)


class VectorTileStyle:
    """Simple styling for vector tiles based on OpenMapTiles schema."""

    # Layer styling configuration
    STYLES = {
        'water': {
            'fill': QColor(170, 211, 223, 180),
            'stroke': QColor(140, 180, 200),
            'stroke_width': 0.5,
            'z_order': 1
        },
        'waterway': {
            'stroke': QColor(170, 211, 223),
            'stroke_width': 1.5,
            'z_order': 2
        },
        'landcover': {
            'fill': QColor(220, 240, 220, 100),
            'z_order': 3
        },
        'landuse': {
            'residential': QColor(230, 230, 230, 150),
            'commercial': QColor(240, 220, 220, 150),
            'industrial': QColor(235, 230, 240, 150),
            'park': QColor(200, 250, 200, 150),
            'z_order': 4
        },
        'park': {
            'fill': QColor(200, 250, 200, 180),
            'stroke': QColor(180, 230, 180),
            'z_order': 5
        },
        'boundary': {
            'stroke': QColor(200, 150, 200, 150),
            'stroke_width': 1.0,
            'z_order': 6
        },
        'building': {
            'fill': QColor(220, 215, 210, 200),
            'stroke': QColor(180, 175, 170),
            'stroke_width': 0.5,
            'z_order': 10
        },
        'transportation': {
            'motorway': {'stroke': QColor(252, 214, 164), 'width': 5.0},
            'trunk': {'stroke': QColor(252, 214, 164), 'width': 4.5},
            'primary': {'stroke': QColor(252, 214, 164), 'width': 4.0},
            'secondary': {'stroke': QColor(254, 254, 254), 'width': 3.5},
            'tertiary': {'stroke': QColor(254, 254, 254), 'width': 3.0},
            'street': {'stroke': QColor(254, 254, 254), 'width': 2.5},
            'path': {'stroke': QColor(200, 200, 200), 'width': 1.0},
            'z_order': 8
        },
        'transportation_name': {
            'text_color': QColor(100, 100, 100),
            'text_size': 10,
            'z_order': 15
        },
        'place': {
            'city': {'text_color': QColor(50, 50, 50), 'text_size': 14, 'bold': True},
            'town': {'text_color': QColor(60, 60, 60), 'text_size': 12, 'bold': True},
            'village': {'text_color': QColor(80, 80, 80), 'text_size': 10},
            'z_order': 20
        },
        'poi': {
            'text_color': QColor(100, 100, 100),
            'text_size': 9,
            'z_order': 18
        }
    }

    @classmethod
    def get_layer_style(cls, layer_name: str, properties: Dict = None) -> Dict:
        """Get style for a layer based on its properties."""
        if layer_name not in cls.STYLES:
            return {}

        style = cls.STYLES[layer_name].copy()

        # Handle special cases based on properties
        if properties:
            if layer_name == 'landuse' and 'class' in properties:
                land_class = properties['class']
                if land_class in style:
                    return {'fill': style[land_class], 'z_order': style['z_order']}

            if layer_name == 'transportation' and 'class' in properties:
                road_class = properties['class']
                if road_class in style:
                    return {**style[road_class], 'z_order': style['z_order']}

            if layer_name == 'place' and 'class' in properties:
                place_class = properties['class']
                if place_class in style:
                    return {**style[place_class], 'z_order': style['z_order']}

        return style


class VectorTileRenderer:
    """Renders vector tiles (PBF format) using PyQt6."""

    def __init__(self):
        self.tile_size = 256  # Standard tile size in pixels
        self.extent = 4096    # Vector tile extent (from OpenMapTiles)

    def decode_tile(self, tile_data: bytes, x: int, y: int, z: int) -> Optional[Dict]:
        """Decode a vector tile, handling gzip compression."""
        try:
            # Check if data is gzipped (common in MBTiles)
            if tile_data[:2] == b'\x1f\x8b':  # gzip magic number
                try:
                    tile_data = gzip.decompress(tile_data)
                    logger.debug(f"Decompressed gzipped tile {z}/{x}/{y}")
                except Exception as e:
                    logger.error(f"Failed to decompress tile {z}/{x}/{y}: {e}")
                    return None

            # Decode the PBF tile
            decoded = mapbox_vector_tile.decode(tile_data)
            return decoded

        except Exception as e:
            logger.error(f"Error decoding vector tile {z}/{x}/{y}: {e}")
            return None

    def render_tile(self, painter: QPainter, tile_data: bytes,
                    x: int, y: int, z: int,
                    screen_x: float, screen_y: float,
                    tile_screen_size: float) -> bool:
        """
        Render a vector tile to a QPainter.

        Args:
            painter: QPainter to draw on
            tile_data: Raw PBF tile data
            x, y, z: Tile coordinates
            screen_x, screen_y: Screen position to draw at
            tile_screen_size: Size of tile on screen in pixels
        """
        try:
            # Decode tile
            decoded = self.decode_tile(tile_data, x, y, z)
            if not decoded:
                return False

            # Calculate scale factor from tile extent to screen size
            scale = tile_screen_size / self.extent

            # Save painter state
            painter.save()

            # Translate to tile position
            painter.translate(screen_x, screen_y)

            # Sort layers by z-order
            layers = self._sort_layers_by_z_order(decoded)

            # Render each layer
            for layer_name in layers:
                layer = decoded[layer_name]
                self._render_layer(painter, layer_name, layer, scale)

            # Restore painter state
            painter.restore()

            return True

        except Exception as e:
            logger.error(f"Error rendering vector tile {z}/{x}/{y}: {e}")
            return False

    def _sort_layers_by_z_order(self, decoded: Dict) -> List[str]:
        """Sort layers by their z-order."""
        def get_z_order(layer_name):
            style = VectorTileStyle.get_layer_style(layer_name)
            return style.get('z_order', 0)

        return sorted(decoded.keys(), key=get_z_order)

    def _render_layer(self, painter: QPainter, layer_name: str,
                     layer: Dict, scale: float):
        """Render a single layer."""
        try:
            features = layer.get('features', [])

            for feature in features:
                geometry = feature.get('geometry')
                properties = feature.get('properties', {})
                geom_type = geometry.get('type')

                # Get style for this feature
                style = VectorTileStyle.get_layer_style(layer_name, properties)
                if not style:
                    continue

                # Render based on geometry type
                if geom_type == 'Polygon' or geom_type == 'MultiPolygon':
                    self._render_polygon(painter, geometry, style, scale)
                elif geom_type == 'LineString' or geom_type == 'MultiLineString':
                    self._render_linestring(painter, geometry, style, scale)
                elif geom_type == 'Point':
                    self._render_point(painter, geometry, properties, style, scale)

        except Exception as e:
            logger.debug(f"Error rendering layer {layer_name}: {e}")

    def _render_polygon(self, painter: QPainter, geometry: Dict,
                       style: Dict, scale: float):
        """Render a polygon feature."""
        try:
            coordinates = geometry.get('coordinates', [])
            if not coordinates:
                return

            # Set fill and stroke
            if 'fill' in style:
                painter.setBrush(QBrush(style['fill']))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)

            if 'stroke' in style:
                pen = QPen(style['stroke'])
                pen.setWidthF(style.get('stroke_width', 1.0))
                painter.setPen(pen)
            else:
                painter.setPen(Qt.PenStyle.NoPen)

            # Handle polygon rings (exterior + holes)
            for ring in coordinates:
                if not ring:
                    continue

                # Convert coordinates to QPointF
                points = []
                for coord in ring:
                    if len(coord) >= 2:
                        points.append(QPointF(coord[0] * scale, coord[1] * scale))

                if len(points) >= 3:
                    polygon = QPolygonF(points)
                    painter.drawPolygon(polygon)

        except Exception as e:
            logger.debug(f"Error rendering polygon: {e}")

    def _render_linestring(self, painter: QPainter, geometry: Dict,
                          style: Dict, scale: float):
        """Render a linestring feature."""
        try:
            coordinates = geometry.get('coordinates', [])
            if not coordinates or len(coordinates) < 2:
                return

            # Set pen style
            if 'stroke' in style:
                pen = QPen(style['stroke'])
                pen.setWidthF(style.get('width', style.get('stroke_width', 1.0)))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
            else:
                return

            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Draw line segments
            path = QPainterPath()
            first_point = True

            for coord in coordinates:
                if len(coord) >= 2:
                    point = QPointF(coord[0] * scale, coord[1] * scale)
                    if first_point:
                        path.moveTo(point)
                        first_point = False
                    else:
                        path.lineTo(point)

            painter.drawPath(path)

        except Exception as e:
            logger.debug(f"Error rendering linestring: {e}")

    def _render_point(self, painter: QPainter, geometry: Dict,
                     properties: Dict, style: Dict, scale: float):
        """Render a point feature (labels, POIs, etc.)."""
        try:
            coordinates = geometry.get('coordinates', [])
            if not coordinates or len(coordinates) < 2:
                return

            x = coordinates[0] * scale
            y = coordinates[1] * scale

            # Get label text
            name = properties.get('name', properties.get('name_en', ''))
            if not name:
                return

            # Set text style
            if 'text_color' in style:
                painter.setPen(style['text_color'])
            else:
                painter.setPen(QColor(100, 100, 100))

            font = QFont()
            font.setPointSize(style.get('text_size', 10))
            if style.get('bold', False):
                font.setBold(True)
            painter.setFont(font)

            # Draw text
            painter.drawText(int(x + 5), int(y), name)

        except Exception as e:
            logger.debug(f"Error rendering point: {e}")


class VectorTileCache:
    """Cache for decoded vector tiles."""

    def __init__(self, max_size: int = 100):
        self.cache = {}
        self.max_size = max_size
        self.access_order = []

    def get(self, key: Tuple[int, int, int]) -> Optional[Dict]:
        """Get cached decoded tile."""
        if key in self.cache:
            # Update access order
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None

    def put(self, key: Tuple[int, int, int], value: Dict):
        """Cache decoded tile."""
        if key in self.cache:
            self.access_order.remove(key)

        self.cache[key] = value
        self.access_order.append(key)

        # Remove oldest if over limit
        while len(self.cache) > self.max_size:
            oldest = self.access_order.pop(0)
            del self.cache[oldest]

    def clear(self):
        """Clear cache."""
        self.cache.clear()
        self.access_order.clear()
