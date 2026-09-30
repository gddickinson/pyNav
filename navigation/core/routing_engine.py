"""
Routing Engine - Handles route calculation and turn-by-turn navigation
Supports multiple routing services and offline routing capabilities
"""

import json
import math
import time
import requests
from typing import Dict, List, Tuple, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from dataclasses import dataclass

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class RoutePoint:
    """A point along a route with navigation information."""
    latitude: float
    longitude: float
    instruction: str = ""
    distance_to_next: float = 0  # meters
    bearing: int = 0  # degrees
    turn_type: str = "straight"  # straight, left, right, sharp_left, etc.
    street_name: str = ""

class RoutingService:
    """Base class for routing services."""

    def __init__(self, name: str):
        self.name = name
        self.api_key = ""

    def calculate_route(self, start_lat: float, start_lon: float,
                       end_lat: float, end_lon: float,
                       waypoints: List[Tuple[float, float]] = None,
                       avoid_tolls: bool = False,
                       avoid_highways: bool = False,
                       vehicle_type: str = "car") -> Optional[Dict]:
        """Calculate route. Override in subclasses."""
        raise NotImplementedError

class OSRMRoutingService(RoutingService):
    """OpenStreetMap Routing Machine (OSRM) service."""

    def __init__(self, server_url: str = "http://router.project-osrm.org"):
        super().__init__("OSRM")
        self.server_url = server_url.rstrip('/')

    def calculate_route(self, start_lat: float, start_lon: float,
                       end_lat: float, end_lon: float,
                       waypoints: List[Tuple[float, float]] = None,
                       avoid_tolls: bool = False,
                       avoid_highways: bool = False,
                       vehicle_type: str = "car") -> Optional[Dict]:
        """Calculate route using OSRM."""
        try:
            # Build coordinate string
            coords = f"{start_lon},{start_lat}"

            # Add waypoints
            if waypoints:
                for lat, lon in waypoints:
                    coords += f";{lon},{lat}"

            coords += f";{end_lon},{end_lat}"

            # Build URL
            profile = "driving" if vehicle_type == "car" else vehicle_type
            url = f"{self.server_url}/route/v1/{profile}/{coords}"

            # Parameters
            params = {
                'overview': 'full',
                'geometries': 'geojson',
                'steps': 'true',
                'alternatives': 'false'
            }

            # Add routing options
            if avoid_highways:
                params['exclude'] = 'motorway'

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if data['code'] == 'Ok' and data['routes']:
                return self._parse_osrm_route(data['routes'][0])

        except Exception as e:
            logger.error(f"OSRM routing error: {e}")

        return None

    def _parse_osrm_route(self, route_data: Dict) -> Dict:
        """Parse OSRM route response."""
        try:
            geometry = route_data['geometry']['coordinates']
            legs = route_data['legs']

            # Convert coordinates to lat/lon
            coordinates = [(coord[1], coord[0]) for coord in geometry]

            # Parse steps
            steps = []
            total_distance = 0
            total_duration = 0

            for leg in legs:
                for step in leg['steps']:
                    maneuver = step['maneuver']

                    route_point = RoutePoint(
                        latitude=maneuver['location'][1],
                        longitude=maneuver['location'][0],
                        instruction=self._format_instruction(step),
                        distance_to_next=step['distance'],
                        bearing=maneuver.get('bearing_after', 0),
                        turn_type=maneuver['type'],
                        street_name=step.get('name', '')
                    )
                    steps.append(route_point)

                total_distance += leg['distance']
                total_duration += leg['duration']

            return {
                'coordinates': coordinates,
                'steps': steps,
                'distance': total_distance,
                'duration': total_duration,
                'geometry': geometry,
                'service': 'OSRM'
            }

        except Exception as e:
            logger.error(f"Error parsing OSRM route: {e}")
            return None

    def _format_instruction(self, step: Dict) -> str:
        """Format turn-by-turn instruction."""
        maneuver = step['maneuver']
        instruction_type = maneuver['type']
        modifier = maneuver.get('modifier', '')
        name = step.get('name', '')

        # Format based on maneuver type
        if instruction_type == 'depart':
            return f"Head {self._format_direction(maneuver.get('bearing_after', 0))}"
        elif instruction_type == 'arrive':
            return "Arrive at destination"
        elif instruction_type == 'turn':
            direction = modifier.replace('_', ' ').title()
            return f"Turn {direction}" + (f" onto {name}" if name else "")
        elif instruction_type == 'merge':
            return f"Merge {modifier}" + (f" onto {name}" if name else "")
        elif instruction_type == 'on ramp':
            return f"Take the ramp" + (f" onto {name}" if name else "")
        elif instruction_type == 'off ramp':
            return f"Take the exit" + (f" to {name}" if name else "")
        elif instruction_type == 'roundabout':
            return f"Take the roundabout" + (f" to {name}" if name else "")
        else:
            return f"Continue" + (f" on {name}" if name else "")

    def _format_direction(self, bearing: float) -> str:
        """Convert bearing to compass direction."""
        directions = ["North", "Northeast", "East", "Southeast",
                     "South", "Southwest", "West", "Northwest"]
        index = int((bearing + 22.5) / 45) % 8
        return directions[index]

class GraphHopperRoutingService(RoutingService):
    """GraphHopper routing service."""

    def __init__(self, api_key: str = ""):
        super().__init__("GraphHopper")
        self.api_key = api_key
        self.base_url = "https://graphhopper.com/api/1/route"

    def calculate_route(self, start_lat: float, start_lon: float,
                       end_lat: float, end_lon: float,
                       waypoints: List[Tuple[float, float]] = None,
                       avoid_tolls: bool = False,
                       avoid_highways: bool = False,
                       vehicle_type: str = "car") -> Optional[Dict]:
        """Calculate route using GraphHopper."""
        if not self.api_key:
            logger.warning("GraphHopper API key required")
            return None

        try:
            params = {
                'point': [f"{start_lat},{start_lon}"],
                'vehicle': vehicle_type,
                'locale': 'en',
                'instructions': 'true',
                'calc_points': 'true',
                'debug': 'false',
                'elevation': 'false',
                'points_encoded': 'false',
                'type': 'json',
                'key': self.api_key
            }

            # Add waypoints
            if waypoints:
                for lat, lon in waypoints:
                    params['point'].append(f"{lat},{lon}")

            params['point'].append(f"{end_lat},{end_lon}")

            # Add avoidance options
            if avoid_tolls:
                params.setdefault('avoid', []).append('toll')
            if avoid_highways:
                params.setdefault('avoid', []).append('motorway')

            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if 'paths' in data and data['paths']:
                return self._parse_graphhopper_route(data['paths'][0])

        except Exception as e:
            logger.error(f"GraphHopper routing error: {e}")

        return None

    def _parse_graphhopper_route(self, path_data: Dict) -> Dict:
        """Parse GraphHopper route response."""
        try:
            points = path_data['points']['coordinates']
            instructions = path_data['instructions']

            # Convert coordinates
            coordinates = [(point[1], point[0]) for point in points]

            # Parse instructions
            steps = []
            for instruction in instructions:
                route_point = RoutePoint(
                    latitude=points[instruction['interval'][0]][1],
                    longitude=points[instruction['interval'][0]][0],
                    instruction=instruction['text'],
                    distance_to_next=instruction['distance'],
                    bearing=instruction.get('heading', 0),
                    turn_type=self._map_turn_type(instruction['sign']),
                    street_name=instruction.get('street_name', '')
                )
                steps.append(route_point)

            return {
                'coordinates': coordinates,
                'steps': steps,
                'distance': path_data['distance'],
                'duration': path_data['time'] / 1000,  # Convert from ms
                'geometry': points,
                'service': 'GraphHopper'
            }

        except Exception as e:
            logger.error(f"Error parsing GraphHopper route: {e}")
            return None

    def _map_turn_type(self, sign: int) -> str:
        """Map GraphHopper turn signs to turn types."""
        turn_map = {
            -3: 'sharp_left',
            -2: 'left',
            -1: 'slight_left',
            0: 'straight',
            1: 'slight_right',
            2: 'right',
            3: 'sharp_right',
            4: 'arrive',
            5: 'via',
            6: 'roundabout'
        }
        return turn_map.get(sign, 'straight')

class OfflineRoutingService(RoutingService):
    """Basic offline routing using straight-line distance."""

    def __init__(self):
        super().__init__("Offline")

    def calculate_route(self, start_lat: float, start_lon: float,
                       end_lat: float, end_lon: float,
                       waypoints: List[Tuple[float, float]] = None,
                       avoid_tolls: bool = False,
                       avoid_highways: bool = False,
                       vehicle_type: str = "car") -> Optional[Dict]:
        """Calculate basic offline route."""
        try:
            points = [(start_lat, start_lon)]

            # Add waypoints
            if waypoints:
                points.extend(waypoints)

            points.append((end_lat, end_lon))

            # Calculate total distance and create steps
            steps = []
            total_distance = 0

            for i in range(len(points) - 1):
                current = points[i]
                next_point = points[i + 1]

                distance = self._calculate_distance(
                    current[0], current[1],
                    next_point[0], next_point[1]
                )
                bearing = self._calculate_bearing(
                    current[0], current[1],
                    next_point[0], next_point[1]
                )

                if i == 0:
                    instruction = f"Head {self._bearing_to_direction(bearing)}"
                elif i == len(points) - 2:
                    instruction = "Arrive at destination"
                else:
                    instruction = f"Continue {self._bearing_to_direction(bearing)}"

                route_point = RoutePoint(
                    latitude=current[0],
                    longitude=current[1],
                    instruction=instruction,
                    distance_to_next=distance,
                    bearing=bearing,
                    turn_type='straight'
                )
                steps.append(route_point)
                total_distance += distance

            # Estimate duration (assume 50 km/h average speed)
            estimated_duration = total_distance / (50 * 1000 / 3600)  # seconds

            return {
                'coordinates': points,
                'steps': steps,
                'distance': total_distance,
                'duration': estimated_duration,
                'geometry': [[lon, lat] for lat, lon in points],
                'service': 'Offline'
            }

        except Exception as e:
            logger.error(f"Offline routing error: {e}")
            return None

    def _calculate_distance(self, lat1: float, lon1: float,
                          lat2: float, lon2: float) -> float:
        """Calculate distance using Haversine formula."""
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

    def _calculate_bearing(self, lat1: float, lon1: float,
                          lat2: float, lon2: float) -> float:
        """Calculate bearing between two points."""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)

        y = math.sin(delta_lon) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))

        bearing = math.atan2(y, x)
        return (math.degrees(bearing) + 360) % 360

    def _bearing_to_direction(self, bearing: float) -> str:
        """Convert bearing to compass direction."""
        directions = ["North", "Northeast", "East", "Southeast",
                     "South", "Southwest", "West", "Northwest"]
        index = int((bearing + 22.5) / 45) % 8
        return directions[index]

class RouteCalculationThread(QThread):
    """Background thread for route calculation."""

    route_calculated = pyqtSignal(dict)
    calculation_failed = pyqtSignal(str)

    def __init__(self, routing_service, start_lat, start_lon, end_lat, end_lon, **kwargs):
        super().__init__()
        self.routing_service = routing_service
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.end_lat = end_lat
        self.end_lon = end_lon
        self.options = kwargs

    def run(self):
        """Calculate route in background."""
        try:
            route = self.routing_service.calculate_route(
                self.start_lat, self.start_lon,
                self.end_lat, self.end_lon,
                **self.options
            )

            if route:
                self.route_calculated.emit(route)
            else:
                self.calculation_failed.emit("Route calculation failed")

        except Exception as e:
            self.calculation_failed.emit(str(e))

class RoutingEngine(QObject):
    """Main routing engine that manages multiple routing services."""

    route_calculated = pyqtSignal(dict)
    calculation_failed = pyqtSignal(str)
    navigation_update = pyqtSignal(dict)  # Current navigation status

    def __init__(self):
        super().__init__()

        # Initialize routing services
        self.services = {
            'OSRM': OSRMRoutingService(),
            'Offline': OfflineRoutingService()
        }

        # Add GraphHopper if API key is available
        graphhopper_key = self._get_api_key('graphhopper')
        if graphhopper_key:
            self.services['GraphHopper'] = GraphHopperRoutingService(graphhopper_key)

        self.preferred_service = 'OSRM'
        self.current_route = None
        self.current_step_index = 0
        self.is_navigating = False

    def _get_api_key(self, service: str) -> str:
        """Get API key from environment or config."""
        import os
        key_map = {
            'graphhopper': 'GRAPHHOPPER_API_KEY',
            'here': 'HERE_API_KEY',
            'mapbox': 'MAPBOX_API_KEY'
        }
        return os.environ.get(key_map.get(service, ''), '')

    def set_preferred_service(self, service_name: str):
        """Set preferred routing service."""
        if service_name in self.services:
            self.preferred_service = service_name

    def calculate_route(self, start: Dict, end: Dict, **options) -> None:
        """Calculate route between start and end points."""
        try:
            start_lat = start['latitude']
            start_lon = start['longitude']
            end_lat = end['latitude']
            end_lon = end['longitude']

            # Try preferred service first
            service = self.services.get(self.preferred_service)
            if not service:
                service = self.services['Offline']

            # Calculate in background thread
            self.calculation_thread = RouteCalculationThread(
                service, start_lat, start_lon, end_lat, end_lon, **options
            )
            self.calculation_thread.route_calculated.connect(self.on_route_calculated)
            self.calculation_thread.calculation_failed.connect(self.on_calculation_failed)
            self.calculation_thread.start()

        except Exception as e:
            logger.error(f"Route calculation setup failed: {e}")
            self.calculation_failed.emit(str(e))

    def on_route_calculated(self, route: Dict):
        """Handle successful route calculation."""
        self.current_route = route
        self.current_step_index = 0
        self.route_calculated.emit(route)
        logger.info(f"Route calculated: {route['distance']/1000:.1f} km, "
                   f"{route['duration']/60:.0f} min via {route['service']}")

    def on_calculation_failed(self, error: str):
        """Handle route calculation failure."""
        logger.error(f"Route calculation failed: {error}")

        # Try fallback to offline routing
        if self.preferred_service != 'Offline':
            logger.info("Trying offline routing as fallback")
            # Would need to restart calculation with offline service

        self.calculation_failed.emit(error)

    def start_navigation(self):
        """Start turn-by-turn navigation."""
        if not self.current_route:
            logger.warning("No route available for navigation")
            return False

        self.is_navigating = True
        self.current_step_index = 0
        logger.info("Navigation started")
        return True

    def stop_navigation(self):
        """Stop turn-by-turn navigation."""
        self.is_navigating = False
        logger.info("Navigation stopped")

    def update_location(self, location: Dict):
        """Update current location and navigation progress."""
        if not self.is_navigating or not self.current_route:
            return

        current_lat = location['latitude']
        current_lon = location['longitude']

        # Find closest point on route
        closest_distance = float('inf')
        closest_step_index = self.current_step_index

        steps = self.current_route['steps']

        # Check current and next few steps
        for i in range(max(0, self.current_step_index - 1),
                      min(len(steps), self.current_step_index + 5)):
            step = steps[i]
            distance = self._calculate_distance(
                current_lat, current_lon,
                step.latitude, step.longitude
            )

            if distance < closest_distance:
                closest_distance = distance
                closest_step_index = i

        # Update step if we've moved to a new one
        if closest_step_index > self.current_step_index:
            self.current_step_index = closest_step_index

        # Prepare navigation update
        current_step = steps[self.current_step_index] if self.current_step_index < len(steps) else None
        next_step = steps[self.current_step_index + 1] if self.current_step_index + 1 < len(steps) else None

        # Calculate distance to next turn
        distance_to_turn = 0
        if current_step:
            distance_to_turn = self._calculate_distance(
                current_lat, current_lon,
                current_step.latitude, current_step.longitude
            )

        nav_update = {
            'current_step': current_step,
            'next_step': next_step,
            'step_index': self.current_step_index,
            'total_steps': len(steps),
            'distance_to_turn': distance_to_turn,
            'distance_remaining': self._calculate_remaining_distance(current_lat, current_lon),
            'time_remaining': self._calculate_remaining_time(current_lat, current_lon)
        }

        self.navigation_update.emit(nav_update)

    def _calculate_distance(self, lat1: float, lon1: float,
                          lat2: float, lon2: float) -> float:
        """Calculate distance between two points."""
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

    def _calculate_remaining_distance(self, current_lat: float, current_lon: float) -> float:
        """Calculate remaining distance to destination."""
        if not self.current_route or not self.current_route['steps']:
            return 0

        remaining_distance = 0
        steps = self.current_route['steps']

        # Distance from current position to current step
        if self.current_step_index < len(steps):
            current_step = steps[self.current_step_index]
            remaining_distance += self._calculate_distance(
                current_lat, current_lon,
                current_step.latitude, current_step.longitude
            )

        # Add remaining step distances
        for i in range(self.current_step_index, len(steps) - 1):
            remaining_distance += steps[i].distance_to_next

        return remaining_distance

    def _calculate_remaining_time(self, current_lat: float, current_lon: float) -> float:
        """Estimate remaining time to destination."""
        remaining_distance = self._calculate_remaining_distance(current_lat, current_lon)

        # Estimate based on average speed (assuming 50 km/h in city, 80 km/h highway)
        average_speed = 50 * 1000 / 3600  # m/s
        return remaining_distance / average_speed

    def get_route_summary(self) -> Optional[Dict]:
        """Get summary of current route."""
        if not self.current_route:
            return None

        return {
            'total_distance': self.current_route['distance'],
            'total_duration': self.current_route['duration'],
            'service': self.current_route['service'],
            'steps_count': len(self.current_route['steps'])
        }

    def export_route(self, format: str = 'gpx') -> Optional[str]:
        """Export current route to specified format."""
        if not self.current_route:
            return None

        if format.lower() == 'gpx':
            return self._export_to_gpx()
        elif format.lower() == 'geojson':
            return self._export_to_geojson()
        else:
            logger.warning(f"Unsupported export format: {format}")
            return None

    def _export_to_gpx(self) -> str:
        """Export route to GPX format."""
        coordinates = self.current_route['coordinates']

        gpx = '<?xml version="1.0" encoding="UTF-8"?>\n'
        gpx += '<gpx version="1.1" creator="PyNav">\n'
        gpx += '  <rte>\n'
        gpx += '    <name>PyNav Route</name>\n'

        for lat, lon in coordinates:
            gpx += f'    <rtept lat="{lat}" lon="{lon}"></rtept>\n'

        gpx += '  </rte>\n'
        gpx += '</gpx>'

        return gpx

    def _export_to_geojson(self) -> str:
        """Export route to GeoJSON format."""
        coordinates = [[lon, lat] for lat, lon in self.current_route['coordinates']]

        geojson = {
            "type": "Feature",
            "properties": {
                "name": "PyNav Route",
                "distance": self.current_route['distance'],
                "duration": self.current_route['duration']
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            }
        }

        return json.dumps(geojson, indent=2)
