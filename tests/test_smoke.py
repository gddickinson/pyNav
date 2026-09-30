"""
Smoke tests for pyNav navigation application.

Tests core functionality with mocked network responses.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import asdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRoutingEngine:
    """Tests for the routing engine module."""

    def test_route_point_dataclass(self):
        from navigation.core.routing_engine import RoutePoint
        point = RoutePoint(
            latitude=40.7128,
            longitude=-74.0060,
            instruction="Turn left",
            distance_to_next=150.0,
            bearing=90,
            turn_type="left",
            street_name="Broadway"
        )
        assert point.latitude == 40.7128
        assert point.turn_type == "left"

    def test_osrm_service_init(self):
        from navigation.core.routing_engine import OSRMRoutingService
        service = OSRMRoutingService()
        assert service.name == "OSRM"
        assert "osrm" in service.server_url

    def test_osrm_service_custom_url(self):
        from navigation.core.routing_engine import OSRMRoutingService
        service = OSRMRoutingService(server_url="http://localhost:5000/")
        assert service.server_url == "http://localhost:5000"

    @patch('navigation.core.routing_engine.requests.get')
    def test_osrm_route_calculation_network_error(self, mock_get):
        """Test that network errors are handled gracefully."""
        from navigation.core.routing_engine import OSRMRoutingService
        mock_get.side_effect = Exception("Connection refused")
        service = OSRMRoutingService()
        result = service.calculate_route(40.7128, -74.0060, 40.7580, -73.9855)
        assert result is None


class TestGeocodingService:
    """Tests for the geocoding service module."""

    def test_geocoding_result_dataclass(self):
        from navigation.core.geocoding_service import GeocodingResult
        result = GeocodingResult(
            address="123 Main St",
            latitude=40.7128,
            longitude=-74.0060,
            confidence=0.95,
            place_type="address"
        )
        assert result.address == "123 Main St"
        assert result.confidence == 0.95

    def test_poi_result_dataclass(self):
        from navigation.core.geocoding_service import POIResult
        poi = POIResult(
            name="Coffee Shop",
            latitude=40.7128,
            longitude=-74.0060,
            category="cafe"
        )
        assert poi.name == "Coffee Shop"
        assert poi.distance == 0.0  # default

    def test_geocoding_provider_rate_limit(self):
        from navigation.core.geocoding_service import GeocodingProvider
        provider = GeocodingProvider("test")
        assert provider.rate_limit_delay == 0.1


class TestNavigationImports:
    """Test that core navigation modules can be imported."""

    def test_import_routing_engine(self):
        from navigation.core import routing_engine
        assert hasattr(routing_engine, 'RoutingEngine')

    def test_import_geocoding_service(self):
        from navigation.core import geocoding_service
        assert hasattr(geocoding_service, 'GeocodingResult')

    def test_import_location_manager(self):
        from navigation.core import location_manager
        assert hasattr(location_manager, 'LocationManager')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
