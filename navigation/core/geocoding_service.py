"""
Geocoding Service - Handles address search, reverse geocoding, and POI search
Supports multiple geocoding providers with fallback capabilities
"""

import json
import time
import requests
from typing import Dict, List, Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from dataclasses import dataclass

from navigation.utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class GeocodingResult:
    """Result from geocoding operation."""
    address: str
    latitude: float
    longitude: float
    confidence: float  # 0-1, higher is better
    place_type: str  # 'address', 'poi', 'city', etc.
    country: str = ""
    state: str = ""
    city: str = ""
    postal_code: str = ""
    house_number: str = ""
    street: str = ""

@dataclass
class POIResult:
    """Point of Interest search result."""
    name: str
    latitude: float
    longitude: float
    category: str
    address: str = ""
    phone: str = ""
    website: str = ""
    rating: float = 0.0
    distance: float = 0.0  # Distance from search point in meters

class GeocodingProvider:
    """Base class for geocoding providers."""

    def __init__(self, name: str):
        self.name = name
        self.api_key = ""
        self.rate_limit_delay = 0.1  # seconds between requests
        self.last_request_time = 0

    def _respect_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def geocode_address(self, address: str) -> List[GeocodingResult]:
        """Geocode an address. Override in subclasses."""
        raise NotImplementedError

    def reverse_geocode(self, latitude: float, longitude: float) -> Optional[GeocodingResult]:
        """Reverse geocode coordinates. Override in subclasses."""
        raise NotImplementedError

    def search_nearby_pois(self, latitude: float, longitude: float,
                          query: str, radius: int = 1000) -> List[POIResult]:
        """Search for nearby POIs. Override in subclasses."""
        raise NotImplementedError

class NominatimProvider(GeocodingProvider):
    """OpenStreetMap Nominatim geocoding provider (free)."""

    def __init__(self, server_url: str = "https://nominatim.openstreetmap.org"):
        super().__init__("Nominatim")
        self.server_url = server_url.rstrip('/')
        self.rate_limit_delay = 1.0  # Nominatim requires 1 second between requests

    def geocode_address(self, address: str) -> List[GeocodingResult]:
        """Geocode address using Nominatim."""
        self._respect_rate_limit()

        try:
            params = {
                'q': address,
                'format': 'json',
                'limit': 5,
                'addressdetails': 1,
                'extratags': 1
            }

            headers = {'User-Agent': 'PyNav/1.0'}
            response = requests.get(
                f"{self.server_url}/search",
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()

            results = []
            for item in response.json():
                result = GeocodingResult(
                    address=item.get('display_name', ''),
                    latitude=float(item['lat']),
                    longitude=float(item['lon']),
                    confidence=float(item.get('importance', 0.5)),
                    place_type=item.get('type', 'unknown'),
                    country=item.get('address', {}).get('country', ''),
                    state=item.get('address', {}).get('state', ''),
                    city=item.get('address', {}).get('city', ''),
                    postal_code=item.get('address', {}).get('postcode', ''),
                    house_number=item.get('address', {}).get('house_number', ''),
                    street=item.get('address', {}).get('road', '')
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Nominatim geocoding error: {e}")
            return []

    def reverse_geocode(self, latitude: float, longitude: float) -> Optional[GeocodingResult]:
        """Reverse geocode using Nominatim."""
        self._respect_rate_limit()

        try:
            params = {
                'lat': latitude,
                'lon': longitude,
                'format': 'json',
                'addressdetails': 1
            }

            headers = {'User-Agent': 'PyNav/1.0'}
            response = requests.get(
                f"{self.server_url}/reverse",
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            if 'error' not in data:
                return GeocodingResult(
                    address=data.get('display_name', ''),
                    latitude=float(data['lat']),
                    longitude=float(data['lon']),
                    confidence=float(data.get('importance', 0.5)),
                    place_type=data.get('type', 'unknown'),
                    country=data.get('address', {}).get('country', ''),
                    state=data.get('address', {}).get('state', ''),
                    city=data.get('address', {}).get('city', ''),
                    postal_code=data.get('address', {}).get('postcode', ''),
                    house_number=data.get('address', {}).get('house_number', ''),
                    street=data.get('address', {}).get('road', '')
                )

        except Exception as e:
            logger.error(f"Nominatim reverse geocoding error: {e}")

        return None

    def search_nearby_pois(self, latitude: float, longitude: float,
                          query: str, radius: int = 1000) -> List[POIResult]:
        """Search for nearby POIs using Overpass API."""
        self._respect_rate_limit()

        try:
            # Use Overpass API for POI search
            overpass_url = "https://overpass-api.de/api/interpreter"

            # Build Overpass query
            bbox_size = radius / 111000  # Rough conversion to degrees
            south = latitude - bbox_size
            north = latitude + bbox_size
            west = longitude - bbox_size
            east = longitude + bbox_size

            # Map common search terms to OSM tags
            tag_mapping = {
                'restaurant': 'amenity~"^(restaurant|cafe|fast_food)$"',
                'food': 'amenity~"^(restaurant|cafe|fast_food|bar|pub)$"',
                'gas': 'amenity="fuel"',
                'fuel': 'amenity="fuel"',
                'hotel': 'tourism~"^(hotel|motel|guest_house)$"',
                'hospital': 'amenity="hospital"',
                'pharmacy': 'amenity="pharmacy"',
                'bank': 'amenity="bank"',
                'atm': 'amenity="atm"',
                'shop': 'shop',
                'store': 'shop'
            }

            # Get appropriate tag for query
            tag_filter = tag_mapping.get(query.lower(), f'name~"{query}"')

            overpass_query = f"""
            [out:json][timeout:25];
            (
              node[{tag_filter}]({south},{west},{north},{east});
              way[{tag_filter}]({south},{west},{north},{east});
              relation[{tag_filter}]({south},{west},{north},{east});
            );
            out center meta;
            """

            response = requests.post(
                overpass_url,
                data=overpass_query,
                headers={'User-Agent': 'PyNav/1.0'},
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            results = []

            for element in data.get('elements', []):
                # Get coordinates
                if element['type'] == 'node':
                    poi_lat = element['lat']
                    poi_lon = element['lon']
                elif 'center' in element:
                    poi_lat = element['center']['lat']
                    poi_lon = element['center']['lon']
                else:
                    continue

                # Get tags
                tags = element.get('tags', {})
                name = tags.get('name', tags.get('brand', 'Unknown'))

                # Determine category
                category = self._determine_poi_category(tags)

                # Calculate distance
                distance = self._calculate_distance(latitude, longitude, poi_lat, poi_lon)

                if distance <= radius:  # Filter by radius
                    poi = POIResult(
                        name=name,
                        latitude=poi_lat,
                        longitude=poi_lon,
                        category=category,
                        address=self._format_address(tags),
                        phone=tags.get('phone', ''),
                        website=tags.get('website', ''),
                        distance=distance
                    )
                    results.append(poi)

            # Sort by distance
            results.sort(key=lambda x: x.distance)
            return results[:20]  # Limit to 20 results

        except Exception as e:
            logger.error(f"POI search error: {e}")
            return []

    def _determine_poi_category(self, tags: Dict) -> str:
        """Determine POI category from OSM tags."""
        if 'amenity' in tags:
            amenity = tags['amenity']
            if amenity in ['restaurant', 'cafe', 'fast_food']:
                return 'Food & Dining'
            elif amenity == 'fuel':
                return 'Gas Station'
            elif amenity in ['hospital', 'clinic']:
                return 'Healthcare'
            elif amenity in ['bank', 'atm']:
                return 'Banking'
            elif amenity == 'pharmacy':
                return 'Pharmacy'
            else:
                return amenity.title()

        elif 'shop' in tags:
            return f"Shop - {tags['shop'].title()}"

        elif 'tourism' in tags:
            return f"Tourism - {tags['tourism'].title()}"

        else:
            return 'Other'

    def _format_address(self, tags: Dict) -> str:
        """Format address from OSM tags."""
        address_parts = []

        if 'addr:housenumber' in tags:
            address_parts.append(tags['addr:housenumber'])
        if 'addr:street' in tags:
            address_parts.append(tags['addr:street'])
        if 'addr:city' in tags:
            address_parts.append(tags['addr:city'])

        return ' '.join(address_parts)

    def _calculate_distance(self, lat1: float, lon1: float,
                          lat2: float, lon2: float) -> float:
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

class HereGeocodingProvider(GeocodingProvider):
    """HERE geocoding provider (requires API key)."""

    def __init__(self, api_key: str):
        super().__init__("HERE")
        self.api_key = api_key
        self.base_url = "https://geocode.search.hereapi.com/v1"

    def geocode_address(self, address: str) -> List[GeocodingResult]:
        """Geocode address using HERE API."""
        if not self.api_key:
            return []

        self._respect_rate_limit()

        try:
            params = {
                'q': address,
                'apiKey': self.api_key,
                'limit': 5
            }

            response = requests.get(f"{self.base_url}/geocode", params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            results = []

            for item in data.get('items', []):
                position = item['position']
                address_obj = item.get('address', {})

                result = GeocodingResult(
                    address=item.get('title', ''),
                    latitude=position['lat'],
                    longitude=position['lng'],
                    confidence=item.get('scoring', {}).get('queryScore', 0.5),
                    place_type=item.get('resultType', 'unknown'),
                    country=address_obj.get('countryName', ''),
                    state=address_obj.get('stateCode', ''),
                    city=address_obj.get('city', ''),
                    postal_code=address_obj.get('postalCode', ''),
                    house_number=address_obj.get('houseNumber', ''),
                    street=address_obj.get('street', '')
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"HERE geocoding error: {e}")
            return []

    def reverse_geocode(self, latitude: float, longitude: float) -> Optional[GeocodingResult]:
        """Reverse geocode using HERE API."""
        if not self.api_key:
            return None

        self._respect_rate_limit()

        try:
            params = {
                'at': f"{latitude},{longitude}",
                'apiKey': self.api_key
            }

            response = requests.get(f"{self.base_url}/revgeocode", params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            items = data.get('items', [])

            if items:
                item = items[0]
                position = item['position']
                address_obj = item.get('address', {})

                return GeocodingResult(
                    address=item.get('title', ''),
                    latitude=position['lat'],
                    longitude=position['lng'],
                    confidence=1.0,  # HERE doesn't provide confidence for reverse geocoding
                    place_type='address',
                    country=address_obj.get('countryName', ''),
                    state=address_obj.get('stateCode', ''),
                    city=address_obj.get('city', ''),
                    postal_code=address_obj.get('postalCode', ''),
                    house_number=address_obj.get('houseNumber', ''),
                    street=address_obj.get('street', '')
                )

        except Exception as e:
            logger.error(f"HERE reverse geocoding error: {e}")

        return None

class GeocodingThread(QThread):
    """Background thread for geocoding operations."""

    geocoding_completed = pyqtSignal(list)  # List of GeocodingResult
    reverse_geocoding_completed = pyqtSignal(object)  # GeocodingResult or None
    poi_search_completed = pyqtSignal(list)  # List of POIResult
    operation_failed = pyqtSignal(str)

    def __init__(self, provider, operation, *args):
        super().__init__()
        self.provider = provider
        self.operation = operation
        self.args = args

    def run(self):
        """Execute geocoding operation."""
        try:
            if self.operation == 'geocode':
                results = self.provider.geocode_address(self.args[0])
                self.geocoding_completed.emit(results)

            elif self.operation == 'reverse_geocode':
                result = self.provider.reverse_geocode(self.args[0], self.args[1])
                self.reverse_geocoding_completed.emit(result)

            elif self.operation == 'search_pois':
                results = self.provider.search_nearby_pois(*self.args)
                self.poi_search_completed.emit(results)

        except Exception as e:
            self.operation_failed.emit(str(e))

class GeocodingService(QObject):
    """Main geocoding service that manages multiple providers."""

    result_ready = pyqtSignal(object)  # GeocodingResult for single results
    results_ready = pyqtSignal(list)   # List of results
    poi_results_ready = pyqtSignal(list)  # List of POI results
    operation_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        # Initialize providers
        self.providers = {
            'nominatim': NominatimProvider()
        }

        # Add HERE if API key is available
        here_api_key = self._get_api_key('here')
        if here_api_key:
            self.providers['here'] = HereGeocodingProvider(here_api_key)

        # Set preferred provider order
        self.provider_priority = ['here', 'nominatim'] if 'here' in self.providers else ['nominatim']

        # Cache for recent results
        self.geocoding_cache = {}  # address -> results
        self.reverse_cache = {}    # (lat, lon) -> result
        self.cache_timeout = 3600  # 1 hour

    def _get_api_key(self, service: str) -> str:
        """Get API key from environment."""
        import os
        key_map = {
            'here': 'HERE_API_KEY',
            'mapbox': 'MAPBOX_API_KEY',
            'google': 'GOOGLE_MAPS_API_KEY'
        }
        return os.environ.get(key_map.get(service, ''), '')

    def geocode_address(self, address: str):
        """Geocode an address using the best available provider."""
        # Check cache first
        cache_key = address.lower().strip()
        if cache_key in self.geocoding_cache:
            cached_result = self.geocoding_cache[cache_key]
            if time.time() - cached_result['timestamp'] < self.cache_timeout:
                self.results_ready.emit(cached_result['results'])
                return

        # Use highest priority available provider
        provider = None
        for provider_name in self.provider_priority:
            if provider_name in self.providers:
                provider = self.providers[provider_name]
                break

        if not provider:
            self.operation_failed.emit("No geocoding provider available")
            return

        # Start background geocoding
        self.geocoding_thread = GeocodingThread(provider, 'geocode', address)
        self.geocoding_thread.geocoding_completed.connect(
            lambda results: self._cache_and_emit_geocoding(address, results)
        )
        self.geocoding_thread.operation_failed.connect(self.operation_failed.emit)
        self.geocoding_thread.start()

    def _cache_and_emit_geocoding(self, address: str, results: List[GeocodingResult]):
        """Cache geocoding results and emit pyqtSignal."""
        cache_key = address.lower().strip()
        self.geocoding_cache[cache_key] = {
            'results': results,
            'timestamp': time.time()
        }

        self.results_ready.emit(results)

        # Also emit single result for convenience
        if results:
            self.result_ready.emit(results[0])
        else:
            self.result_ready.emit(None)

    def reverse_geocode(self, latitude: float, longitude: float):
        """Reverse geocode coordinates."""
        # Check cache first
        cache_key = (round(latitude, 4), round(longitude, 4))  # Round for cache efficiency
        if cache_key in self.reverse_cache:
            cached_result = self.reverse_cache[cache_key]
            if time.time() - cached_result['timestamp'] < self.cache_timeout:
                self.result_ready.emit(cached_result['result'])
                return

        # Use best available provider
        provider = None
        for provider_name in self.provider_priority:
            if provider_name in self.providers:
                provider = self.providers[provider_name]
                break

        if not provider:
            self.operation_failed.emit("No geocoding provider available")
            return

        # Start background reverse geocoding
        self.reverse_thread = GeocodingThread(provider, 'reverse_geocode', latitude, longitude)
        self.reverse_thread.reverse_geocoding_completed.connect(
            lambda result: self._cache_and_emit_reverse(latitude, longitude, result)
        )
        self.reverse_thread.operation_failed.connect(self.operation_failed.emit)
        self.reverse_thread.start()

    def _cache_and_emit_reverse(self, latitude: float, longitude: float, result: GeocodingResult):
        """Cache reverse geocoding result and emit pyqtSignal."""
        cache_key = (round(latitude, 4), round(longitude, 4))
        self.reverse_cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }

        self.result_ready.emit(result)

    def search_nearby_places(self, latitude: float, longitude: float, query: str = "",
                           radius: int = 1000) -> List[POIResult]:
        """Search for nearby places/POIs."""
        # Use Nominatim for POI search (it's free and works well)
        provider = self.providers.get('nominatim')
        if not provider:
            self.operation_failed.emit("No POI provider available")
            return []

        # Start background POI search
        self.poi_thread = GeocodingThread(provider, 'search_pois', latitude, longitude, query, radius)
        self.poi_thread.poi_search_completed.connect(self.poi_results_ready.emit)
        self.poi_thread.operation_failed.connect(self.operation_failed.emit)
        self.poi_thread.start()

    def get_nearby_places(self, latitude: float, longitude: float) -> List[POIResult]:
        """Get general nearby places (restaurants, gas stations, etc.)."""
        # Search for common categories
        common_searches = ['restaurant', 'gas', 'hotel', 'hospital', 'pharmacy', 'bank']

        # For now, just search for restaurants as an example
        # In a real implementation, you might want to search multiple categories
        self.search_nearby_places(latitude, longitude, 'restaurant', 2000)

        # Return empty list since this is async - results come via pyqtSignal
        return []

    def clear_cache(self):
        """Clear geocoding caches."""
        self.geocoding_cache.clear()
        self.reverse_cache.clear()
        logger.info("Geocoding cache cleared")

    def get_provider_info(self) -> Dict[str, Dict]:
        """Get information about available providers."""
        info = {}
        for name, provider in self.providers.items():
            info[name] = {
                'name': provider.name,
                'has_api_key': bool(provider.api_key),
                'rate_limit_delay': provider.rate_limit_delay
            }
        return info
