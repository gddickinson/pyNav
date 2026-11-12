"""Write the SYNTHETIC demo drive used by the web interface: web/static/demo/synthetic_drive.nmea.

Nothing here was recorded: a made-up car drive along straight legs from near the Texas Capitol to near Zilker Park
in Austin (the endpoints of the README's screenshot route; the path between them is invented and ignores roads),
simulated at 1 Hz with a seeded random generator (speed changes, a stop, GPS noise, varying satellites/HDOP) and
written as $GPGGA + $GPRMC sentences by navmath.nmea, the same writer the app uses.

Run: python scripts/make_demo_track.py
"""
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from navmath.geo import haversine_m, initial_bearing_deg  # noqa: E402
from navmath.nmea import format_gga, format_rmc  # noqa: E402

OUT = ROOT / "web" / "static" / "demo" / "synthetic_drive.nmea"
WAYPOINTS = [(30.2747, -97.7404), (30.2700, -97.7430), (30.2655, -97.7445), (30.2630, -97.7520),
             (30.2645, -97.7605), (30.2660, -97.7680), (30.2669, -97.7729)]
START = 1704099600  # 2024-01-01 09:00:00 UTC (arbitrary)
STOP_AT_WAYPOINT = 3  # wait at a 'junction' for STOP_S seconds
STOP_S = 15


def interpolate(a, b, f):
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


def simulate(seed=7):
    rnd = random.Random(seed)
    m_per_deg_lat = 111195.0
    t, speed, lines = START, 0.0, []
    for i, (a, b) in enumerate(zip(WAYPOINTS, WAYPOINTS[1:])):
        leg = haversine_m(*a, *b)
        course = initial_bearing_deg(*a, *b)
        s = 0.0
        while s < leg:
            to_end = leg - s
            target = 4.0 if to_end < 60 or s < 40 else 11.0 + 2.0 * math.sin(t / 37.0)
            speed += max(-2.0, min(1.5, target - speed))
            speed = max(speed, 1.0)
            s = min(leg, s + speed)
            lat, lon = interpolate(a, b, s / leg)
            noise = 2.5
            lat += rnd.gauss(0, noise) / m_per_deg_lat
            lon += rnd.gauss(0, noise) / (m_per_deg_lat * math.cos(math.radians(lat)))
            sats = rnd.randint(6, 11)
            hdop = round(rnd.uniform(0.7, 2.4), 1)
            lines.append(format_gga(lat, lon, t, altitude=150 + 10 * math.sin(s / 300), satellites=sats, hdop=hdop))
            lines.append(format_rmc(lat, lon, t, speed_ms=speed + rnd.gauss(0, 0.2), course=course))
            t += 1
        if i + 1 == STOP_AT_WAYPOINT:
            for _ in range(STOP_S):
                speed = 0.0
                lines.append(format_gga(*b, t, altitude=150, satellites=9, hdop=1.0))
                lines.append(format_rmc(*b, t, speed_ms=0.0, course=course))
                t += 1
    return lines


def main():
    lines = simulate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(lines) // 2} fixes")


if __name__ == "__main__":
    main()
