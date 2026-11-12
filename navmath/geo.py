"""Spherical-earth geometry used throughout PyNav: haversine distance, initial bearing, compass direction,
slippy-map tile maths and the GPS accuracy estimate from fix quality, satellites and HDOP (pure Python)."""
import math

EARTH_RADIUS_M = 6371000  # mean Earth radius used by every PyNav distance
DIRECTIONS_8 = ["North", "Northeast", "East", "Southeast", "South", "Southwest", "West", "Northwest"]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres (haversine formula)."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from point 1 to point 2, degrees clockwise from north in [0, 360)."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def bearing_to_direction(bearing: float) -> str:
    """Eight-point compass name for a bearing in degrees."""
    return DIRECTIONS_8[int((bearing + 22.5) / 45) % 8]


def deg2tile(lat: float, lon: float, zoom: int):
    """Slippy-map (OSM) tile x, y containing a point."""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)


def tile2deg(x: int, y: int, zoom: int):
    """Bounds of tile x, y as (west lon, north lat, east lon, south lat) of its corners (x, y) and (x+1, y+1)."""
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_deg = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    next_lon_deg = (x + 1) / n * 360.0 - 180.0
    next_lat_deg = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return (lon_deg, lat_deg, next_lon_deg, next_lat_deg)


def estimate_gps_accuracy(fix_quality, satellites, hdop) -> float:
    """PyNav's horizontal accuracy estimate in metres from the GGA fix quality, satellite count and HDOP.

    999 means no fix. base (5 m GPS, 2 m DGPS, 1 m RTK) x satellite factor x HDOP factor.
    """
    fix_quality = fix_quality or 0
    satellites = satellites or 0
    hdop = hdop or 0.0
    if fix_quality == 0:
        return 999
    if fix_quality == 1:
        base_accuracy = 5.0
    elif fix_quality == 2:
        base_accuracy = 2.0
    elif fix_quality >= 3:
        base_accuracy = 1.0
    else:
        base_accuracy = 10.0

    if satellites >= 8:
        sat_multiplier = 0.8
    elif satellites >= 6:
        sat_multiplier = 1.0
    elif satellites >= 4:
        sat_multiplier = 1.5
    else:
        sat_multiplier = 3.0

    if hdop > 0:
        if hdop < 2:
            hdop_multiplier = 1.0
        elif hdop < 5:
            hdop_multiplier = 1.2
        elif hdop < 10:
            hdop_multiplier = 1.5
        elif hdop < 20:
            hdop_multiplier = 2.0
        else:
            hdop_multiplier = 3.0
    else:
        hdop_multiplier = 1.0
    return base_accuracy * sat_multiplier * hdop_multiplier
