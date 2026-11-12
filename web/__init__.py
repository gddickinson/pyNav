"""PyNav web interface (FastAPI + plain ES modules, no build step).

    app.py        routes under /api, STATIC_ENDPOINTS for the GitHub Pages export
    live.py       live GPS sources for the local dashboard: serial NMEA reader thread, iPhone server (macbook_server.py)
    static/       front end: core.js (router), main.js, one module per page, nav_engine.js + nmea_engine.js (JS port of
                  navmath, node-tested), static_api.js (answers api() on the static site), demo/ (synthetic drive)
"""
