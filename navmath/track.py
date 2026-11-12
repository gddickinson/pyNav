"""Track-log loading and summary statistics: distance (haversine), duration, speeds, altitude (pure Python)."""
from .geo import haversine_m


def load_log(text: str, name: str = ""):
    """Parse a GPX or NMEA log, chosen by file extension or, failing that, by content."""
    low = name.lower()
    head = text.lstrip()[:200].lower()
    if low.endswith(".gpx") or head.startswith("<?xml") or "<gpx" in head:
        from .gpx import parse_gpx
        return parse_gpx(text)
    from .nmea import parse_nmea_log
    return parse_nmea_log(text)


def cumulative_distance(points):
    """Distance travelled (m) at each point, starting at 0."""
    out, total = [0.0], 0.0
    for a, b in zip(points, points[1:]):
        total += haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
        out.append(total)
    return out if points else []


def track_stats(points):
    """Summary of a track: point count, distance, duration and average speed (when timed), maximum recorded speed,
    altitude range and bounding box."""
    n = len(points)
    if n == 0:
        return {"n": 0, "distance_m": 0.0, "duration_s": None, "avg_speed_ms": None, "max_speed_ms": None,
                "min_alt": None, "max_alt": None, "bbox": None}
    dist = cumulative_distance(points)[-1]
    times = [p["t"] for p in points if p.get("t") is not None]
    duration = (times[-1] - times[0]) if len(times) >= 2 else None
    speeds = [p["speed"] for p in points if p.get("speed") is not None]
    alts = [p["altitude"] for p in points if p.get("altitude") is not None]
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    return {"n": n, "distance_m": dist, "duration_s": duration,
            "avg_speed_ms": dist / duration if duration else None,
            "max_speed_ms": max(speeds) if speeds else None,
            "min_alt": min(alts) if alts else None, "max_alt": max(alts) if alts else None,
            "bbox": [min(lats), min(lons), max(lats), max(lons)]}


def analyse_log(text: str, name: str = "", legs: int = 6):
    """Load a log, summarise it and plan a straight-line route along it (the GPX route if it has one, else `legs`
    evenly spaced track positions), as the web interface shows it."""
    from .route import offline_route, waypoints_from_track
    log = load_log(text, name)
    pts = log["points"]
    if len(pts) < 2:
        raise ValueError("no track found: the file needs at least two GPX points or valid NMEA fixes")
    positions = [(p["lat"], p["lon"]) for p in pts]
    from_gpx = len(log["gpx_route"]) >= 2
    via = log["gpx_route"] if from_gpx else waypoints_from_track(positions, legs)
    return {"name": name, **log, "stats": track_stats(pts), "cumdist": cumulative_distance(pts),
            "route_source": "the GPX file's route" if from_gpx else "evenly spaced points of the track",
            "route": offline_route(via)}
