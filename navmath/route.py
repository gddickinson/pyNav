"""Straight-line (offline) routes and turn-by-turn route following, as used by PyNav's RoutingEngine (pure Python).

Steps are dicts or objects with latitude, longitude, instruction, distance_to_next (m), bearing and turn_type
(navigation.core.routing_engine.RoutePoint has exactly these fields).
"""
from .geo import bearing_to_direction, haversine_m, initial_bearing_deg

OFFLINE_SPEED_KMH = 50  # assumed average speed for offline durations and the remaining-time estimate


def _f(step, name):
    return step[name] if isinstance(step, dict) else getattr(step, name)


def offline_steps(points):
    """Steps for a straight-line route through [(lat, lon), ...]: one per leg plus 'Arrive' at the destination."""
    steps = []
    for i in range(len(points) - 1):
        (lat1, lon1), (lat2, lon2) = points[i], points[i + 1]
        bearing = initial_bearing_deg(lat1, lon1, lat2, lon2)
        verb = "Head" if i == 0 else "Continue"
        steps.append({"latitude": lat1, "longitude": lon1,
                      "instruction": f"{verb} {bearing_to_direction(bearing)}",
                      "distance_to_next": haversine_m(lat1, lon1, lat2, lon2),
                      "bearing": bearing, "turn_type": "straight"})
    steps.append({"latitude": points[-1][0], "longitude": points[-1][1], "instruction": "Arrive at destination",
                  "distance_to_next": 0.0, "bearing": 0.0, "turn_type": "arrive"})
    return steps


def offline_route(points, speed_kmh=OFFLINE_SPEED_KMH):
    """Route dict (coordinates, steps, distance m, duration s, geometry [lon, lat]) like OfflineRoutingService."""
    points = [(float(a), float(b)) for a, b in points]
    if len(points) < 2:
        raise ValueError("a route needs at least two points")
    steps = offline_steps(points)
    distance = sum(s["distance_to_next"] for s in steps)
    return {"coordinates": points, "steps": steps, "distance": distance,
            "duration": distance / (speed_kmh * 1000 / 3600),
            "geometry": [[lon, lat] for lat, lon in points], "service": "Offline"}


def remaining_distance(steps, step_index, lat, lon):
    """Distance to the current step plus the lengths of all later legs (RoutingEngine's remaining distance)."""
    if not steps:
        return 0
    total = 0
    if step_index < len(steps):
        total += haversine_m(lat, lon, _f(steps[step_index], "latitude"), _f(steps[step_index], "longitude"))
    for i in range(step_index, len(steps) - 1):
        total += _f(steps[i], "distance_to_next")
    return total


def route_progress(steps, step_index, lat, lon, speed_kmh=OFFLINE_SPEED_KMH):
    """One RoutingEngine.update_location step: the closest of steps [i-1, i+5) becomes current if it is ahead.

    Returns step_index (never decreases), distance_to_turn (m to the current step), distance_remaining (m) and
    time_remaining (s at speed_kmh).
    """
    closest_distance = float("inf")
    closest = step_index
    for i in range(max(0, step_index - 1), min(len(steps), step_index + 5)):
        d = haversine_m(lat, lon, _f(steps[i], "latitude"), _f(steps[i], "longitude"))
        if d < closest_distance:
            closest_distance, closest = d, i
    if closest > step_index:
        step_index = closest
    current = steps[step_index] if step_index < len(steps) else None
    to_turn = haversine_m(lat, lon, _f(current, "latitude"), _f(current, "longitude")) if current is not None else 0
    remaining = remaining_distance(steps, step_index, lat, lon)
    return {"step_index": step_index, "total_steps": len(steps), "distance_to_turn": to_turn,
            "distance_remaining": remaining, "time_remaining": remaining / (speed_kmh * 1000 / 3600)}


def follow_route(steps, positions, speed_kmh=OFFLINE_SPEED_KMH):
    """route_progress for each (lat, lon) in order, starting at step 0 (a replayed navigation session)."""
    out, idx = [], 0
    for lat, lon in positions:
        p = route_progress(steps, idx, lat, lon, speed_kmh)
        idx = p["step_index"]
        out.append(p)
    return out


def waypoints_from_track(positions, legs=6):
    """Evenly spaced track positions (first and last included) to plan a straight-line route along a log."""
    n = len(positions)
    if n < 2:
        raise ValueError("need at least two positions")
    legs = max(1, min(int(legs), n - 1))
    idx = sorted({int(k * (n - 1) / legs + 0.5) for k in range(legs + 1)})  # round half up, as JS Math.round
    return [tuple(positions[i]) for i in idx]
