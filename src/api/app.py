from fastapi import FastAPI, Query, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from pathlib import Path
from datetime import datetime, timezone
import pytz
import hmac
import hashlib

from src.database.queries import (
    search_stations,
    get_station_by_id,
    find_routes_and_departures,
    get_all_stations,
)
from src.config import BASE_DIR, WEBHOOK_SECRET

app = FastAPI(
    title="Haryana Roadways Timetable API",
    description="Official timetable lookup and controlled-vocabulary autocomplete API",
    version="1.0.0"
)

# Shared bot application reference — set by run_server.py at startup
_bot_app = None

def set_bot_app(bot_application):
    global _bot_app
    _bot_app = bot_application

# Enable CORS for Telegram Mini App webview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Webapp static files directory
WEBAPP_DIR = BASE_DIR / "src" / "webapp"
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")

@app.get("/")
def root():
    """Redirect root to the Mini App interface."""
    return RedirectResponse(url="/webapp/")

@app.get("/api/health")
def health_check():
    """Service health and timestamp."""
    return {
        "status": "healthy",
        "service": "HR Roadways Timetable Backend",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/telegram-webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default="")
):
    """Receives Telegram updates via webhook (used on Render / production)."""
    # Verify the secret token to reject fake requests
    if x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    if _bot_app is None:
        raise HTTPException(status_code=503, detail="Bot not initialized yet")

    from telegram import Update
    data = await request.json()
    update = Update.de_json(data, _bot_app.bot)
    await _bot_app.process_update(update)
    return {"ok": True}

@app.get("/api/stations/search")
def api_search_stations(
    q: str = Query(..., min_length=1, description="Station name query"),
    limit: int = Query(15, ge=1, le=50)
):
    """Controlled vocabulary search for bus stands/stops."""
    stations = search_stations(q, limit=limit)
    return {"query": q, "count": len(stations), "results": stations}

@app.get("/api/stations/all")
def api_all_stations():
    """Returns list of all known bus stands."""
    stations = get_all_stations()
    return {"total": len(stations), "stations": stations}

@app.get("/api/routes/departures")
def api_get_departures(
    from_id: int = Query(..., description="Origin station ID"),
    to_id: int = Query(..., description="Destination station ID"),
    time: str = Query(None, description="Current time filter in HH:MM")
):
    """
    Looks up verified departures between from_id and to_id.
    If time is not provided, defaults to current Indian Standard Time (IST).
    """
    from_st = get_station_by_id(from_id)
    to_st = get_station_by_id(to_id)

    if not from_st:
        raise HTTPException(status_code=404, detail=f"Origin station ID {from_id} not found")
    if not to_st:
        raise HTTPException(status_code=404, detail=f"Destination station ID {to_id} not found")

    if not time:
        ist_tz = pytz.timezone("Asia/Kolkata")
        time = datetime.now(ist_tz).strftime("%H:%M")

    departures = find_routes_and_departures(from_id, to_id, current_time=time)
    return {
        "from_station": from_st,
        "to_station": to_st,
        "query_time_ist": time,
        "count": len(departures),
        "departures": departures
    }
