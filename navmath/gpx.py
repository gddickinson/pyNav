"""GPX 1.0/1.1 reading and writing for track logs (pure Python, standard library only)."""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_time(s):
    """ISO 8601 time -> UNIX seconds; a time without a zone is taken as UTC (as GPX requires)."""
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _num(el, name):
    for c in el:
        if _local(c.tag) == name and c.text and c.text.strip():
            try:
                return float(c.text)
            except ValueError:
                return None
    return None


def _text(el, name):
    for c in el:
        if _local(c.tag) == name:
            return (c.text or "").strip()
    return None


def _point(el):
    return {"t": parse_time(_text(el, "time")), "lat": float(el.get("lat")), "lon": float(el.get("lon")),
            "speed": _num(el, "speed"), "course": _num(el, "course"), "fix_quality": None, "satellites": None,
            "hdop": _num(el, "hdop"), "altitude": _num(el, "ele"), "accuracy": None}


def parse_gpx(text: str):
    """Track points (all <trkpt> in order; if there are none, <rtept>, else <wpt>) and the route (<rtept>) of a GPX."""
    root = ET.fromstring(text.strip().encode("utf-8"))
    found = {"trkpt": [], "rtept": [], "wpt": []}
    for el in root.iter():
        name = _local(el.tag)
        if name in found and el.get("lat") is not None and el.get("lon") is not None:
            found[name].append(_point(el))
    points = found["trkpt"] or found["rtept"] or found["wpt"]
    route = [(p["lat"], p["lon"]) for p in found["rtept"]]
    return {"format": "gpx", "points": points, "gpx_route": route, "skipped": 0, "sentences": 0,
            "time_basis": "utc"}


def to_gpx(points, name="PyNav Track", creator="PyNav"):
    """GPX 1.1 track with UTC times; coordinates to 7 decimals (about 1 cm), elevation to 0.1 m."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<gpx version="1.1" creator="{creator}" xmlns="http://www.topografix.com/GPX/1/1">',
           "  <trk>", f"    <name>{name}</name>", "    <trkseg>"]
    for p in points:
        out.append(f'      <trkpt lat="{p["lat"]:.7f}" lon="{p["lon"]:.7f}">')
        if p.get("altitude") is not None:
            out.append(f'        <ele>{p["altitude"]:.1f}</ele>')
        if p.get("t") is not None:
            t = datetime.fromtimestamp(p["t"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            out.append(f"        <time>{t}</time>")
        out.append("      </trkpt>")
    out += ["    </trkseg>", "  </trk>", "</gpx>", ""]
    return "\n".join(out)
