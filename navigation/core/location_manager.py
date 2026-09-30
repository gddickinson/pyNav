"""
Location Manager - Handles multiple location sources for navigation
Supports GPS, IP geolocation, and manual location input
FIXED: Now properly includes GPS quality data (satellites, fix quality, HDOP, altitude)
"""

import time
import requests
import serial
import platform
import glob
import math
from typing import Optional, Dict, List, Tuple
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QMessageBox

try:
    import pynmea2
except ImportError:
    pynmea2 = None

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

class LocationProvider:
    """Base class for location providers."""

    def __init__(self, name: str):
        self.name = name
        self.is_active = False
        self.last_location = None
        self.last_update = 0

    def get_location(self) -> Optional[Dict]:
        """Get current location. Override in subclasses."""
        raise NotImplementedError

    def start(self):
        """Start the location provider."""
        self.is_active = True
        return True

    def stop(self):
        """Stop the location provider."""
        self.is_active = False

    def cleanup(self):
        """Cleanup resources."""
        self.stop()

class GPSProvider(LocationProvider):
    """GPS location provider via serial connection."""

    def __init__(self, port: str, baudrate: int = 115200):
        super().__init__(f"GPS ({port})")
        self.port = port
        self.baudrate = baudrate
        self.serial_connection = None

        # GPS quality data - store current values
        self.fix_quality = 0
        self.satellites = 0
        self.hdop = 0.0
        self.altitude = 0.0

        # Basic location data
        self.current_latitude = None
        self.current_longitude = None
        self.current_speed = None
        self.current_heading = None

    def start(self):
        """Start GPS connection."""
        if pynmea2 is None:
            logger.error("pynmea2 not available for GPS parsing")
            return False

        super().start()
        try:
            self.serial_connection = serial.Serial(
                self.port,
                self.baudrate,
                timeout=1
            )
            logger.info(f"GPS connected on {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect GPS on {self.port}: {e}")
            return False

    def stop(self):
        """Stop GPS connection."""
        super().stop()
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()

    def get_location(self) -> Optional[Dict]:
        """Get location from GPS."""
        if not self.is_active or not self.serial_connection or pynmea2 is None:
            return None

        try:
            line = self.serial_connection.readline().decode('ascii', errors='replace')

            if not line.strip():
                return self.last_location

            if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                # Parse RMC sentence for basic location data
                msg = pynmea2.parse(line)
                if msg.status == 'A':  # Valid fix
                    self.current_latitude = float(msg.latitude)
                    self.current_longitude = float(msg.longitude)
                    self.current_speed = float(msg.spd_over_grnd) if msg.spd_over_grnd else 0
                    self.current_heading = float(msg.true_course) if msg.true_course else 0

                    # Create location dict with all available data
                    location = {
                        'latitude': self.current_latitude,
                        'longitude': self.current_longitude,
                        'speed': self.current_speed,
                        'heading': self.current_heading,
                        'altitude': self.altitude,
                        'timestamp': time.time(),
                        'accuracy': self._estimate_accuracy(),
                        'source': self.name,
                        # GPS-specific fields
                        'fix_quality': self.fix_quality,
                        'satellites': self.satellites,
                        'hdop': self.hdop
                    }

                    self.last_location = location
                    self.last_update = time.time()
                    return location

            elif line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                # Parse GGA sentence for GPS quality data
                msg = pynmea2.parse(line)

                # Update GPS quality fields
                self.fix_quality = int(msg.gps_qual) if msg.gps_qual else 0
                self.satellites = int(msg.num_sats) if msg.num_sats else 0
                self.hdop = float(msg.horizontal_dil) if msg.horizontal_dil else 0.0
                self.altitude = float(msg.altitude) if msg.altitude else 0.0

                # If we have valid location data, update last_location with new quality data
                if (self.last_location and
                    self.current_latitude is not None and
                    self.current_longitude is not None):

                    updated_location = self.last_location.copy()
                    updated_location.update({
                        'fix_quality': self.fix_quality,
                        'satellites': self.satellites,
                        'hdop': self.hdop,
                        'altitude': self.altitude,
                        'accuracy': self._estimate_accuracy(),
                        'timestamp': time.time()
                    })

                    self.last_location = updated_location
                    return updated_location

        except Exception as e:
            logger.debug(f"GPS parsing error: {e}")

        return self.last_location

    def _estimate_accuracy(self) -> float:
        """Estimate GPS accuracy based on fix quality, satellites, and HDOP."""
        if self.fix_quality == 0:
            return 999  # No fix

        # Base accuracy estimate from fix quality
        if self.fix_quality == 1:
            base_accuracy = 5.0  # Standard GPS
        elif self.fix_quality == 2:
            base_accuracy = 2.0  # Differential GPS
        elif self.fix_quality >= 3:
            base_accuracy = 1.0  # RTK or other high-precision
        else:
            base_accuracy = 10.0

        # Adjust based on number of satellites
        if self.satellites >= 8:
            sat_multiplier = 0.8
        elif self.satellites >= 6:
            sat_multiplier = 1.0
        elif self.satellites >= 4:
            sat_multiplier = 1.5
        else:
            sat_multiplier = 3.0

        # Adjust based on HDOP (Horizontal Dilution of Precision)
        if self.hdop > 0:
            if self.hdop < 2:
                hdop_multiplier = 1.0  # Excellent
            elif self.hdop < 5:
                hdop_multiplier = 1.2  # Good
            elif self.hdop < 10:
                hdop_multiplier = 1.5  # Moderate
            elif self.hdop < 20:
                hdop_multiplier = 2.0  # Fair
            else:
                hdop_multiplier = 3.0  # Poor
        else:
            hdop_multiplier = 1.0

        return base_accuracy * sat_multiplier * hdop_multiplier

class IPLocationProvider(LocationProvider):
    """IP-based location provider with multiple fallback services."""

    def __init__(self):
        super().__init__("IP Location")
        self.cache_duration = 300  # 5 minutes
        self.timeout = 5  # 5 second timeout

        # Multiple IP geolocation services for fallback
        self.services = [
            {
                'name': 'ipapi.co',
                'url': 'https://ipapi.co/json/',
                'lat_key': 'latitude',
                'lon_key': 'longitude',
                'city_key': 'city',
                'country_key': 'country_name'
            },
            {
                'name': 'ip-api.com',
                'url': 'http://ip-api.com/json/',
                'lat_key': 'lat',
                'lon_key': 'lon',
                'city_key': 'city',
                'country_key': 'country'
            },
            {
                'name': 'httpbin.org',
                'url': 'https://httpbin.org/ip',
                'ip_only': True  # Just gets IP, we'd need another service for location
            }
        ]

    def start(self):
        """Test IP location service availability."""
        super().start()
        try:
            # Quick test with a simple service
            response = requests.get('https://httpbin.org/ip', timeout=3)
            if response.status_code == 200:
                logger.info("IP location service available")
                return True
            else:
                logger.warning("IP location service test failed")
                return False
        except Exception as e:
            logger.warning(f"IP location service unavailable: {e}")
            return False

    def get_location(self) -> Optional[Dict]:
        """Get location from IP geolocation service."""
        if not self.is_active:
            return None

        # Use cached location if recent
        if (self.last_location and
            time.time() - self.last_update < self.cache_duration):
            return self.last_location

        # Try each service until one works
        for service in self.services:
            try:
                if service.get('ip_only'):
                    continue  # Skip IP-only services for now

                logger.debug(f"Trying IP location service: {service['name']}")

                response = requests.get(service['url'], timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                # Check if we got valid coordinates
                lat_key = service['lat_key']
                lon_key = service['lon_key']

                if lat_key in data and lon_key in data:
                    try:
                        latitude = float(data[lat_key])
                        longitude = float(data[lon_key])

                        # Validate coordinates
                        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                            location = {
                                'latitude': latitude,
                                'longitude': longitude,
                                'city': data.get(service['city_key'], ''),
                                'country': data.get(service['country_key'], ''),
                                'accuracy': 50000,  # IP location is very approximate
                                'timestamp': time.time(),
                                'source': f'IP ({service["name"]})',
                                # GPS fields set to N/A for IP location
                                'fix_quality': None,
                                'satellites': None,
                                'hdop': None,
                                'altitude': None,
                                'speed': None,
                                'heading': None
                            }

                            self.last_location = location
                            self.last_update = time.time()
                            logger.info(f"Got IP location from {service['name']}")
                            return location

                    except (ValueError, TypeError) as e:
                        logger.debug(f"Invalid coordinates from {service['name']}: {e}")
                        continue

            except requests.exceptions.Timeout:
                logger.debug(f"Timeout from {service['name']}")
                continue
            except requests.exceptions.RequestException as e:
                logger.debug(f"Request error from {service['name']}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Error from {service['name']}: {e}")
                continue

        logger.warning("All IP location services failed")
        return None

class ManualLocationProvider(LocationProvider):
    """Manual location input provider."""

    def __init__(self):
        super().__init__("Manual")

    def set_location(self, latitude: float, longitude: float, name: str = ""):
        """Set manual location."""
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Invalid coordinates")

        self.last_location = {
            'latitude': latitude,
            'longitude': longitude,
            'name': name,
            'accuracy': 1.0,  # Assume precise manual input
            'timestamp': time.time(),
            'source': 'Manual',
            # GPS fields set to N/A for manual location
            'fix_quality': None,
            'satellites': None,
            'hdop': None,
            'altitude': None,
            'speed': None,
            'heading': None
        }
        self.last_update = time.time()

    def get_location(self) -> Optional[Dict]:
        """Get manual location."""
        if not self.is_active:
            return None
        return self.last_location

class LocationManager(QObject):
    """Manages multiple location providers and provides unified location access."""

    location_changed = pyqtSignal(dict)
    status_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.providers = {}
        self.active_provider = None
        self.last_location = None
        self.location_history = []  # Store recent locations for tracking
        self.movement_threshold = 10  # meters

        # Initialize providers
        self._discover_gps_devices()
        self.providers['ip'] = IPLocationProvider()
        self.providers['manual'] = ManualLocationProvider()

        # Set default provider - try IP first, then manual
        if self.set_active_source('IP Location'):
            logger.info("Using IP location as default")
        else:
            logger.info("Falling back to manual location")
            self.set_active_source('Manual')

    def _discover_gps_devices(self):
        """Discover available GPS devices."""
        if pynmea2 is None:
            logger.info("pynmea2 not available, skipping GPS device discovery")
            return

        devices = []

        try:
            system = platform.system()
            if system == 'Darwin':  # macOS
                patterns = ['/dev/tty.usbmodem*', '/dev/tty.usbserial*', '/dev/tty.SLAB_*']
                for pattern in patterns:
                    devices.extend(glob.glob(pattern))
            elif system == 'Linux':
                patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyS*']
                for pattern in patterns:
                    devices.extend(glob.glob(pattern))
            elif system == 'Windows':
                try:
                    import serial.tools.list_ports
                    ports = serial.tools.list_ports.comports()
                    devices = [port.device for port in ports]
                except ImportError:
                    logger.warning("pyserial not available for Windows COM port detection")

            # Test each device for GPS data
            for device in devices:
                try:
                    gps = GPSProvider(device)
                    if gps.start():
                        # Test for NMEA data briefly
                        test_count = 0
                        while test_count < 5:  # Try for a shorter time
                            try:
                                line = gps.serial_connection.readline().decode('ascii', errors='replace')
                                if line.startswith('$GP') or line.startswith('$GN'):
                                    self.providers[f'gps_{device}'] = gps
                                    logger.info(f"Found GPS device: {device}")
                                    break
                            except:
                                pass
                            test_count += 1
                            time.sleep(0.1)
                        else:
                            gps.stop()
                except Exception as e:
                    logger.debug(f"Failed to test GPS device {device}: {e}")

        except Exception as e:
            logger.error(f"Error discovering GPS devices: {e}")

    def get_available_sources(self) -> List[str]:
        """Get list of available location sources."""
        return [provider.name for provider in self.providers.values()]

    def set_active_source(self, source_name: str) -> bool:
        """Set the active location source."""
        for provider in self.providers.values():
            if provider.name == source_name:
                # Stop current provider
                if self.active_provider:
                    self.active_provider.stop()

                # Start new provider
                self.active_provider = provider
                success = provider.start()

                if success:
                    self.status_changed.emit(f"Connected: {source_name}")
                    logger.info(f"Switched to location source: {source_name}")
                    return True
                else:
                    self.status_changed.emit(f"Failed: {source_name}")
                    logger.error(f"Failed to start location source: {source_name}")
                    return False

        logger.error(f"Unknown location source: {source_name}")
        return False

    def get_current_location(self) -> Optional[Dict]:
        """Get current location from active provider."""
        if not self.active_provider:
            return None

        try:
            location = self.active_provider.get_location()
            if location and location != self.last_location:
                self.last_location = location
                self.location_history.append(location)

                # Keep only recent history (last 100 points)
                if len(self.location_history) > 100:
                    self.location_history.pop(0)

                self.location_changed.emit(location)
                logger.debug(f"Location updated: {location['latitude']:.6f}, {location['longitude']:.6f}")

            return location

        except Exception as e:
            logger.error(f"Error getting current location: {e}")
            return None

    def has_moved_significantly(self, threshold: float = None) -> bool:
        """Check if user has moved significantly since last check."""
        if threshold is None:
            threshold = self.movement_threshold

        if len(self.location_history) < 2:
            return False

        last = self.location_history[-1]
        previous = self.location_history[-2]

        distance = self.calculate_distance(
            last['latitude'], last['longitude'],
            previous['latitude'], previous['longitude']
        )

        return distance > threshold

    def calculate_distance(self, lat1: float, lon1: float,
                          lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters using Haversine formula."""
        R = 6371000  # Earth's radius in meters

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def get_location_history(self) -> List[Dict]:
        """Get recent location history."""
        return self.location_history.copy()

    def set_manual_location(self, latitude: float, longitude: float, name: str = ""):
        """Set manual location and switch to manual provider."""
        if 'manual' in self.providers:
            try:
                manual_provider = self.providers['manual']
                manual_provider.set_location(latitude, longitude, name)
                self.set_active_source('Manual')
                return True
            except ValueError as e:
                logger.error(f"Invalid manual location: {e}")
                return False
        return False

    def get_location_accuracy(self) -> float:
        """Get current location accuracy in meters."""
        if self.last_location:
            return self.last_location.get('accuracy', 999)
        return 999

    def is_location_fresh(self, max_age_seconds: int = 30) -> bool:
        """Check if current location is fresh enough."""
        if not self.last_location:
            return False
        return time.time() - self.last_location['timestamp'] < max_age_seconds

    def cleanup(self):
        """Cleanup all providers."""
        if self.active_provider:
            self.active_provider.stop()
        for provider in self.providers.values():
            provider.cleanup()
        logger.info("Location manager cleaned up")
