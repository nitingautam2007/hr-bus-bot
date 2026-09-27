# 🚌 Haryana Roadways Timetable Telegram Bot & Mini App

A Telegram Bot and Telegram Mini App that provides real, verified Haryana Roadways bus timetables extracted directly from official government publications on `hartrans.gov.in`.

---

## 🌟 Key Features

- **Strictly Official Data**: All schedules are scraped directly from official depot PDF publications uploaded by the Department of State Transport, Haryana.
- **Zero Route Mismatches**: Controlled-vocabulary station autocomplete in the Telegram Mini App prevents spelling errors and invalid route lookups.
- **Directional Accuracy**: Respects origin &rarr; via &rarr; destination order (e.g. Chandigarh to Delhi only shows southbound trips, never reverse trips).
- **Upcoming Departures**: Automatically sorts departures with upcoming buses shown first relative to Indian Standard Time (IST).
- **Official Source Traceability**: Every bus timing cites the exact depot source and government verification date.
- **Unofficial Disclaimer**: Strict compliance with government attribution guidelines (prominently displays unofficial assistant disclaimers).
- **Dual Mode**: Works via the Telegram Mini App button and built-in `/search <From> <To>` fallback command.

---

## 📂 Project Structure

```
Hr Bus/
├── .env                  # Environment config (add your BOT_TOKEN here)
├── .env.example          # Environment template
├── requirements.txt      # Python dependencies
├── hr-roadways-bot-prd.md# Product Requirement Document
├── data/
│   ├── roadways.db       # SQLite database storing stations, routes, and departures
│   └── pdfs/             # Downloaded official depot PDFs cache
├── src/
│   ├── config.py         # Application configuration
│   ├── database/
│   │   ├── db.py         # SQLite schema initialization and connection helpers
│   │   └── queries.py    # Controlled vocabulary search and directional route matcher
│   ├── ingestion/
│   │   ├── scraper.py    # Discovers depot PDFs on hartrans.gov.in
│   │   └── parser.py     # PyMuPDF table extraction and database population
│   ├── api/
│   │   └── app.py        # FastAPI server hosting autocomplete API and Mini App
│   ├── bot/
│   │   └── bot.py        # Telegram Bot handlers (/start, WebApp data, /search)
│   └── webapp/
│       ├── index.html    # Mini App UI (mobile-first, Telegram WebApp SDK)
│       ├── styles.css    # Responsive theme matching Telegram theme colors
│       └── app.js        # Autocomplete, swap, validation, sendData()
├── scripts/
│   ├── ingest_all.py     # Ingests all or subset of official government depot PDFs
│   ├── check_stats.py    # Inspects current database record counts
│   └── run_server.py     # Starts FastAPI and Telegram Bot concurrently
└── tests/
    ├── test_parser.py    # Tests station normalization
    └── test_queries.py   # Tests route matching, via stops, and time sorting
```

---

## 🚀 Quick Setup & Usage

### 1. Set Your Bot Token
Open `.env` and replace `YOUR_TELEGRAM_BOT_TOKEN_HERE` with your Telegram Bot token from [@BotFather](https://t.me/botfather):
```env
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
WEBAPP_URL=http://localhost:8000/webapp/
```

### 2. Ingest Depot Timetables
The database is already pre-populated with **4,000+ verified departures** from major depots (Ambala, Bhiwani, Chandigarh).

To ingest more depots (or all 25 official depots):
```bash
# Ingest next 5 depots
python scripts/ingest_all.py --limit 5

# Or ingest all available depots
python scripts/ingest_all.py
```

### 3. Launch Server & Bot
Run the unified server launcher:
```bash
python scripts/run_server.py
```
This will:
- Start the **FastAPI WebApp & Autocomplete API** at `http://localhost:8000/webapp/`.
- Start the **Telegram Bot** polling loop.

### 4. Running the Test Suite
```bash
python -m pytest tests/
```

---

## 📱 Telegram Mini App Setup (Production / HTTPS)
Telegram Web Apps require an HTTPS URL when opened inside Telegram clients:
- You can tunnel your local server using [ngrok](https://ngrok.com) or Cloudflare Tunnels:
  ```bash
  ngrok http 8000
  ```
- Copy the `https://...` URL into `.env`:
  ```env
  WEBAPP_URL=https://your-ngrok-subdomain.ngrok-free.app/webapp/
  ```
- Set your Web App URL in [@BotFather](https://t.me/botfather) under **Bot Settings > Menu Button > Configure menu button**.
