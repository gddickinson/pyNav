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
