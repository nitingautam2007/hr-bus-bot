import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8000/webapp/").strip()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Webhook config (set these on Render dashboard)
# WEBHOOK_URL = full public URL e.g. https://hr-bus-bot.onrender.com
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

# Database path resolution
_db_env = os.getenv("DB_PATH", "data/roadways.db")
if os.path.isabs(_db_env):
    DB_PATH = Path(_db_env)
else:
    DB_PATH = BASE_DIR / _db_env

# Official base URL
HARTRANS_DEPOT_URL = "https://hartrans.gov.in/bus-time-table-depot-wise/"
