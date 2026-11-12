"""NMEA 0183 helpers: checksum, coordinate formatting and GGA/RMC sentence writers (pure Python)."""
import time
from functools import reduce

KNOTS_TO_MS = 1852 / 3600  # 1 knot = 1852 m per hour


def checksum(body: str) -> str:
    """XOR of the characters between '$' and '*', as two upper-case hex digits."""
    return f"{reduce(lambda a, c: a ^ ord(c), body, 0):02X}"


def sentence(body: str) -> str:
    """'$' + body + '*' + checksum (no line ending)."""
    return f"${body}*{checksum(body)}"


def format_coord(value: float, is_lat: bool, decimals: int = 4):
    """Signed decimal degrees -> ('ddmm.mmmm' or 'dddmm.mmmm', hemisphere letter).

    Minutes are rounded first so that e.g. 59.99996 minutes carries into the degrees instead of printing 60.0000.
    """
    hemi = ("N" if value >= 0 else "S") if is_lat else ("E" if value >= 0 else "W")
    scale = 10 ** decimals
    total = round(abs(value) * 60 * scale)  # whole units of 10^-decimals minutes
    deg, minutes = divmod(total, 60 * scale)
    width = 2 if is_lat else 3
    return f"{deg:0{width}d}{minutes / scale:0{decimals + 3}.{decimals}f}", hemi


def format_gga(lat, lon, timestamp, altitude=0.0, fix_quality=1, satellites=8, hdop=1.0, decimals=4) -> str:
    """$GPGGA sentence for a fix at UNIX time `timestamp` (UTC)."""
    hms = time.strftime("%H%M%S", time.gmtime(timestamp))
    la, ns = format_coord(lat, True, decimals)
    lo, ew = format_coord(lon, False, decimals)
    body = (f"GPGGA,{hms},{la},{ns},{lo},{ew},{int(fix_quality)},{int(satellites):02d},{float(hdop):.1f},"
            f"{float(altitude or 0):.1f},M,0.0,M,,")
    return sentence(body)


def format_rmc(lat, lon, timestamp, speed_ms=0.0, course=0.0, decimals=4) -> str:
    """$GPRMC sentence (status A) for a fix at UNIX time `timestamp`; speed is given in m/s, written in knots."""
    t = time.gmtime(timestamp)
    la, ns = format_coord(lat, True, decimals)
    lo, ew = format_coord(lon, False, decimals)
    knots = float(speed_ms or 0) / KNOTS_TO_MS
    body = (f"GPRMC,{time.strftime('%H%M%S', t)},A,{la},{ns},{lo},{ew},{knots:.1f},{float(course or 0):.1f},"
            f"{time.strftime('%d%m%y', t)},,")
    return sentence(body)


def _num(v, cast=float):
    try:
        return cast(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _seconds_of_day(t):
    return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6


def parse_nmea_log(text: str):
    """Parse an NMEA 0183 log with pynmea2 (as the serial GPS provider does) into track points.

    Every valid RMC fix (status A) becomes a point: t (UNIX s, UTC, when the date is known), lat, lon, speed (m/s,
    from knots), course. GGA sentences carry fix quality, satellites, HDOP and altitude onto the current fix (the
    same-second RMC point, else the next ones), and the GPS accuracy estimate is computed from them. A log with no
    RMC fixes falls back to GGA positions (fix quality > 0), timed by time of day only. Lines with a bad checksum or
    that do not parse are counted in 'skipped'; other sentence types are ignored.
    """
    import calendar
    import pynmea2
    from .geo import estimate_gps_accuracy

    rmc, gga, skipped, n_sentences = [], [], 0, 0
    q = {"fix_quality": None, "satellites": None, "hdop": None, "altitude": None}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("$"):
            continue
        n_sentences += 1
        try:
            msg = pynmea2.parse(line)
            kind = msg.sentence_type
            if kind == "RMC":
                if msg.status != "A":
                    continue
                sod = _seconds_of_day(msg.timestamp) if msg.timestamp else None
                t = None
                if msg.timestamp and msg.datestamp:
                    t = calendar.timegm(msg.datestamp.timetuple()) + sod
                rmc.append({"t": t, "sod": sod, "lat": float(msg.latitude), "lon": float(msg.longitude),
                            "speed": (_num(msg.spd_over_grnd) or 0.0) * KNOTS_TO_MS,
                            "course": _num(msg.true_course), **q})
            elif kind == "GGA":
                q = {"fix_quality": _num(msg.gps_qual, int) or 0, "satellites": _num(msg.num_sats, int),
                     "hdop": _num(msg.horizontal_dil), "altitude": _num(msg.altitude)}
                sod = _seconds_of_day(msg.timestamp) if msg.timestamp else None
                if rmc and rmc[-1]["sod"] == sod:
                    rmc[-1].update(q)
                if q["fix_quality"] > 0 and msg.lat:
                    gga.append({"t": sod, "sod": sod, "lat": float(msg.latitude), "lon": float(msg.longitude),
                                "speed": None, "course": None, **q})
        except pynmea2.SentenceTypeError:
            continue  # a sentence type pynmea2 does not know: ignored like GSV
        except (pynmea2.ParseError, ValueError, TypeError, AttributeError):
            skipped += 1
    points = rmc or gga
    if not rmc:  # time of day only: keep it increasing across midnight
        day = 0.0
        for i, p in enumerate(points):
            if i and p["t"] is not None and points[i - 1]["t"] is not None and p["sod"] + day < points[i - 1]["t"]:
                day += 86400
            p["t"] = None if p["t"] is None else p["sod"] + day
    for p in points:
        p.pop("sod")
        p["accuracy"] = (estimate_gps_accuracy(p["fix_quality"], p["satellites"], p["hdop"])
                         if p["fix_quality"] is not None else None)
    return {"format": "nmea", "points": points, "gpx_route": [], "skipped": skipped, "sentences": n_sentences,
            "time_basis": "utc" if rmc else "time of day"}
