"""FastAPI web app for PyNav: serves the front end in static/ and the JSON API under /api.

Run with `python run_web.py` (http://127.0.0.1:8179, local only). `scripts/build_static.py` exports every path in
STATIC_ENDPOINTS to JSON for the GitHub Pages site, so keep that list in step with the GET routes below. Track logs
are analysed by navmath (Python) here and by its JS port (nmea_engine.js) on the static site.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from navmath.route import OFFLINE_SPEED_KMH
from navmath.track import analyse_log
from web import live

STATIC = Path(__file__).resolve().parent / "static"
DEMO = STATIC / "demo" / "synthetic_drive.nmea"
MAX_LOG_BYTES = 20_000_000

app = FastAPI(title="PyNav")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
LIVE = live.LiveSources()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/info")
def info():
    """Project summary for the home page (demo numbers computed by navmath)."""
    demo = analyse_log(DEMO.read_text(), DEMO.name)
    return {"title": "PyNav", "offline_speed_kmh": OFFLINE_SPEED_KMH,
            "demo": {"file": f"static/demo/{DEMO.name}", "n": demo["stats"]["n"],
                     "distance_m": demo["stats"]["distance_m"], "duration_s": demo["stats"]["duration_s"],
                     "steps": len(demo["route"]["steps"])},
            "formats": ["NMEA 0183 ($GPRMC/$GNRMC fixes + $GPGGA quality)", "GPX 1.0/1.1 (track, route or waypoints)"]}


@app.get("/api/demo")
def demo():
    """The synthetic demo drive, analysed by navmath (Python)."""
    r = analyse_log(DEMO.read_text(), DEMO.name)
    r["synthetic"] = True
    return r


class LogIn(BaseModel):
    text: str = Field(max_length=MAX_LOG_BYTES)
    name: str = ""
    legs: int = Field(6, ge=1, le=50)


@app.post("/api/analyse")
def analyse(body: LogIn):
    """Analyse a GPX/NMEA log sent by this computer's browser (the local app only; nothing is stored)."""
    try:
        return analyse_log(body.text, body.name, body.legs)
    except Exception as e:  # malformed XML, no fixes
        raise HTTPException(400, f"could not read {body.name or 'the file'}: {e}")


# --- live GPS (local app only) ----------------------------------------------------------------------------------
@app.get("/api/live/sources")
def live_sources():
    return live.sources()


class SerialIn(BaseModel):
    port: str
    baudrate: int = Field(live.DEFAULT_BAUD, ge=1200, le=921600)


@app.post("/api/live/serial/start")
def serial_start(body: SerialIn):
    if body.port not in live.candidate_serial_ports():
        raise HTTPException(400, f"{body.port} is not one of this computer's serial GPS candidates")
    return LIVE.start_serial(body.port, body.baudrate)


@app.post("/api/live/serial/stop")
def serial_stop():
    LIVE.stop_serial()
    return {"stopped": True}


@app.get("/api/live/serial")
def serial_state():
    return {"reader": LIVE.serial_state()}


@app.get("/api/live/iphone")
def iphone(url: str = live.IPHONE_DEFAULT):
    try:
        return live.fetch_iphone(url)
    except ValueError as e:
        raise HTTPException(400, str(e))


# GET paths (without the /api prefix) written to the static site as api/<path>.json.
STATIC_ENDPOINTS = ["/info", "/demo"]
