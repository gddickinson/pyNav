"""Serial-port candidates for GPS receivers on this computer (standard library + optional pyserial)."""
import glob
import platform

PORT_PATTERNS = {
    "Darwin": ["/dev/tty.usbmodem*", "/dev/tty.usbserial*", "/dev/tty.SLAB_*"],
    "Linux": ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyS*"],
}


def candidate_serial_ports(system=None):
    """Device paths that may be a USB/serial GPS (the patterns LocationManager probes for NMEA)."""
    system = system or platform.system()
    if system == "Windows":
        try:
            import serial.tools.list_ports
            return [p.device for p in serial.tools.list_ports.comports()]
        except ImportError:
            return []
    devices = []
    for pattern in PORT_PATTERNS.get(system, []):
        devices.extend(sorted(glob.glob(pattern)))
    return devices
