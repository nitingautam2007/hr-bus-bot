import sys
import os
import threading
import asyncio
import uvicorn
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import HOST, PORT, BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET
from src.database.db import init_db, get_db_connection
from src.api.app import app, set_bot_app
from src.bot.bot import create_bot_application

import logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("run_server")


# ─── Auto-ingest on first startup ────────────────────────────────────────────

def auto_ingest_if_empty():
    """If DB has no departures (fresh Render deploy), run ingestion in background."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM departures")
    count = cur.fetchone()[0]
    conn.close()

    if count == 0:
        logger.info("[Startup] DB is empty — starting auto-ingest in background...")
        thread = threading.Thread(target=_run_ingest, daemon=True)
        thread.start()
    else:
        logger.info(f"[Startup] DB ready with {count} departures.")

def _run_ingest():
    try:
        from src.ingestion.scraper import fetch_depot_pdf_list, download_depot_pdf
        from src.ingestion.parser import ingest_depot_data
        pdf_list = fetch_depot_pdf_list()
        conn = get_db_connection()
        total = 0
        for item in pdf_list:
            try:
                path = download_depot_pdf(item)
                _, d = ingest_depot_data(item, path, conn=conn)
                total += d
            except Exception as e:
                logger.warning(f"[Auto-ingest] Skipped {item.get('depot')}: {e}")
        conn.close()
        logger.info(f"[Auto-ingest] Done. Total departures: {total}")
    except Exception as e:
        logger.error(f"[Auto-ingest] Failed: {e}")


# ─── Weekly refresh ───────────────────────────────────────────────────────────

def run_weekly_refresh():
    """Background job: re-downloads all depot PDFs every 7 days."""
    try:
        logger.info("[Weekly Refresh] Starting scheduled timetable update...")
        from src.ingestion.scraper import fetch_depot_pdf_list, download_depot_pdf
        from src.ingestion.parser import ingest_depot_data
        pdf_list = fetch_depot_pdf_list()
        conn = get_db_connection()
        total = 0
        for item in pdf_list:
            try:
                path = download_depot_pdf(item, force_download=True)
                _, d = ingest_depot_data(item, path, conn=conn)
                total += d
            except Exception as e:
                logger.warning(f"[Weekly Refresh] Skipped {item.get('depot')}: {e}")
        conn.close()
        logger.info(f"[Weekly Refresh] Done. Total departures: {total}")
    except Exception as e:
        logger.error(f"[Weekly Refresh] Failed: {e}")

def start_weekly_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_weekly_refresh, trigger="interval", weeks=1,
                      id="weekly_timetable_refresh", replace_existing=True)
    scheduler.start()
    logger.info("Weekly auto-refresh scheduler started.")
    return scheduler


# ─── Webhook mode (Render / production) ──────────────────────────────────────

async def setup_webhook(bot_app, webhook_url: str):
    """Register the webhook URL with Telegram and start the bot application."""
    await bot_app.initialize()
    await bot_app.start()
    webhook_endpoint = f"{webhook_url.rstrip('/')}/telegram-webhook"
    await bot_app.bot.set_webhook(
        url=webhook_endpoint,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=["message", "callback_query"]
    )
    logger.info(f"[Webhook] Registered: {webhook_endpoint}")
    set_bot_app(bot_app)

def run_in_webhook_mode():
    """Runs FastAPI with the bot in webhook mode (for Render)."""
    bot_app = create_bot_application()

    # Register webhook asynchronously before server starts
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_webhook(bot_app, WEBHOOK_URL))

    logger.info(f"[Server] Starting in WEBHOOK mode on port {PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


# ─── Polling mode (local development) ────────────────────────────────────────

def run_in_polling_mode():
    """Runs FastAPI + Telegram bot in polling mode (for local dev)."""
    # FastAPI in background thread
    def run_api():
        logger.info(f"[Server] FastAPI at http://localhost:{PORT}")
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")

    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    # Bot polling on main thread
    if BOT_TOKEN and BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.info("[Bot] Starting in POLLING mode...")
        bot_app = create_bot_application()
        set_bot_app(bot_app)
        bot_app.run_polling()
    else:
        logger.warning("[Bot] BOT_TOKEN not set. Only API server is running.")
        api_thread.join()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    logger.info("Initializing database...")
    init_db()
    auto_ingest_if_empty()
    start_weekly_scheduler()

    if WEBHOOK_URL:
        # Production / Render
        run_in_webhook_mode()
    else:
        # Local development
        run_in_polling_mode()


if __name__ == "__main__":
    main()
