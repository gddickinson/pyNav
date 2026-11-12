"""Web interface tests: every exported endpoint answers, the static build is complete, and the JS engine tests pass.

Run: python -m pytest -q tests/test_web.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web.app import STATIC, STATIC_ENDPOINTS, app  # noqa: E402

client = TestClient(app)


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200 and "static/main.js" in r.text


@pytest.mark.parametrize("path", STATIC_ENDPOINTS)
def test_endpoint(path):
    r = client.get("/api" + path)
    assert r.status_code == 200, r.text
    assert r.json() is not None


def test_static_build(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_static
    build_static.build(tmp_path / "site")
    assert (tmp_path / "site" / "index.html").read_text().count("APP_STATIC") == 1
    for path in STATIC_ENDPOINTS:
        assert (tmp_path / "site" / "api" / (path.strip("/") + ".json")).exists()


def test_static_assets_referenced_exist():
    html = (STATIC / "index.html").read_text()
    for name in ("style.css", "main.js"):
        assert f"static/{name}" in html and (STATIC / name).exists()


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_engine():
    tests = sorted(STATIC.glob("*.test.mjs"))
    for t in tests:
        r = subprocess.run(["node", str(t)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


# --- PyNav-specific API tests ------------------------------------------------------------------------------------
FIX = ROOT / "tests" / "fixtures"


def test_demo_is_synthetic_and_analysed():
    r = client.get("/api/demo").json()
    assert r["synthetic"] is True and r["format"] == "nmea" and r["skipped"] == 0
    assert r["stats"]["n"] == len(r["points"]) == len(r["cumdist"]) > 100
    assert r["route"]["steps"][-1]["instruction"] == "Arrive at destination"


@pytest.mark.parametrize("name", ["sample.nmea", "sample_gga_only.nmea", "sample.gpx"])
def test_analyse_upload(name):
    r = client.post("/api/analyse", json={"text": (FIX / name).read_text(), "name": name, "legs": 3})
    assert r.status_code == 200, r.text
    assert len(r.json()["points"]) >= 3


def test_analyse_rejects_files_without_a_track():
    r = client.post("/api/analyse", json={"text": "hello", "name": "x.nmea"})
    assert r.status_code == 400 and "no track" in r.text
    r = client.post("/api/analyse", json={"text": "<gpx><broken", "name": "x.gpx"})
    assert r.status_code == 400


def test_live_sources():
    r = client.get("/api/live/sources").json()
    assert r["default_baud"] == 115200 and isinstance(r["serial_ports"], list)


def test_serial_reader_with_a_fake_port():
    import time as _t
    from web import live
    lines = [l for l in (FIX / "sample.nmea").read_text().splitlines()]

    class FakePort:
        def __init__(self, *a):
            self.it = iter(lines)

        def readline(self):
            try:
                return (next(self.it) + "\r\n").encode()
            except StopIteration:
                _t.sleep(0.01)
                return b""

        def close(self):
            pass

    src = live.LiveSources()
    src.start_serial("/dev/fake", 9600, opener=FakePort)
    for _ in range(200):
        st = src.serial_state()
        if st["lines_read"] == len(lines):
            break
        _t.sleep(0.01)
    src.stop_serial()
    assert st["fix"]["lat"] == pytest.approx(-1 / 60) and st["skipped"] == 1 and st["error"] is None


def test_serial_start_refuses_unknown_ports():
    assert client.post("/api/live/serial/start", json={"port": "/etc/passwd"}).status_code == 400
    assert client.get("/api/live/serial").json() == {"reader": None}


def test_iphone_only_local_addresses(monkeypatch):
    from web import live
    assert client.get("/api/live/iphone", params={"url": "http://8.8.8.8:8000"}).status_code == 400
    assert client.get("/api/live/iphone", params={"url": "https://127.0.0.1"}).status_code == 400

    class Resp:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return b'{"latitude": 1.5, "longitude": 2.5}'

    monkeypatch.setattr(live, "urlopen", Resp)
    r = client.get("/api/live/iphone", params={"url": "http://localhost:8000"}).json()
    assert r["ok"] and r["position"]["latitude"] == 1.5 and r["server"] == "http://127.0.0.1:8000"
