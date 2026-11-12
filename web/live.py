"""Live GPS sources for the local web dashboard (never used by the static site).

SerialReader reads NMEA lines from a serial GPS in a background thread (pyserial, like the desktop GPSProvider) and
parses the most recent lines with navmath.nmea.parse_nmea_log. fetch_iphone() asks the iPhone tracking server
(iphoneTracking/macbook_server.py, GET /current) for its latest position; only loopback or private-network
addresses are allowed.
"""
import ipaddress
import json
import threading
import time
from collections import deque
from urllib.parse import urlparse
from urllib.request import urlopen

from navmath.nmea import parse_nmea_log
from navmath.ports import candidate_serial_ports

DEFAULT_BAUD = 115200  # GPSProvider's default
IPHONE_DEFAULT = "http://127.0.0.1:8000"  # macbook_server.py's port


class SerialReader:
    """One background reader per port; keeps the last `keep` lines and simple counters."""

    def __init__(self, port: str, baudrate: int = DEFAULT_BAUD, keep: int = 200, opener=None):
        self.port, self.baudrate = port, int(baudrate)
        self.lines = deque(maxlen=keep)
        self.n_lines, self.error, self.started = 0, None, time.time()
        self._stop = threading.Event()
        self._opener = opener
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _open(self):
        if self._opener:
            return self._opener(self.port, self.baudrate)
        import serial
        return serial.Serial(self.port, self.baudrate, timeout=1)

    def _run(self):
        try:
            conn = self._open()
        except Exception as e:  # port missing, busy, permission
            self.error = f"could not open {self.port}: {e}"
            return
        try:
            while not self._stop.is_set():
                raw = conn.readline()
                if not raw:
                    continue
                line = raw.decode("ascii", errors="replace").strip()
                if line:
                    self.lines.append(line)
                    self.n_lines += 1
        except Exception as e:
            self.error = f"read error on {self.port}: {e}"
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)

    def state(self):
        lines = list(self.lines)
        parsed = parse_nmea_log("\n".join(lines)) if lines else {"points": [], "skipped": 0, "sentences": 0}
        pts = parsed["points"]
        return {"port": self.port, "baudrate": self.baudrate, "running": self._thread.is_alive(), "error": self.error,
                "lines_read": self.n_lines, "uptime_s": time.time() - self.started, "fix": pts[-1] if pts else None,
                "recent_fixes": pts[-60:], "skipped": parsed["skipped"], "raw": lines[-15:]}


class LiveSources:
    """The dashboard's state: at most one serial reader at a time."""

    def __init__(self):
        self.reader = None
        self.lock = threading.Lock()

    def start_serial(self, port, baudrate=DEFAULT_BAUD, opener=None):
        with self.lock:
            if self.reader:
                self.reader.stop()
            self.reader = SerialReader(port, baudrate, opener=opener)
            return self.reader.state()

    def stop_serial(self):
        with self.lock:
            if self.reader:
                self.reader.stop()
            self.reader = None

    def serial_state(self):
        return self.reader.state() if self.reader else None


def sources():
    try:
        import serial  # noqa: F401
        has_serial = True
    except ImportError:
        has_serial = False
    return {"serial_ports": candidate_serial_ports(), "pyserial": has_serial, "default_baud": DEFAULT_BAUD,
            "iphone_default": IPHONE_DEFAULT}


def check_local_url(url: str) -> str:
    u = urlparse(url)
    if u.scheme != "http" or not u.hostname:
        raise ValueError("use an http:// address such as http://127.0.0.1:8000")
    host = "127.0.0.1" if u.hostname == "localhost" else u.hostname
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError("give the server's IP address (loopback or private network), not a host name")
    if not (ip.is_loopback or ip.is_private):
        raise ValueError("only this computer or the local network are allowed")
    return f"http://{host}:{u.port or 80}"


def fetch_iphone(url: str = IPHONE_DEFAULT, timeout: float = 2.0):
    """Latest position stored by macbook_server.py (its /current endpoint)."""
    base = check_local_url(url)
    try:
        with urlopen(base + "/current", timeout=timeout) as r:
            return {"ok": True, "server": base, "position": json.loads(r.read().decode("utf-8"))}
    except Exception as e:
        return {"ok": False, "server": base, "error": f"{type(e).__name__}: {e}"[:300]}
