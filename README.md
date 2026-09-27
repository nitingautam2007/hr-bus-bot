# 🚌 Haryana Roadways Timetable Telegram Bot

An automated Telegram Bot and timetable reference tool that provides real, verified Haryana Roadways bus schedules extracted directly from official government records on [`hartrans.gov.in`](https://hartrans.gov.in).

Built as a student community project to help daily commuters, students, and travelers across Haryana! 🤝

---

## 🌟 Key Features

- **Official Government Data**: Direct timetable extraction from 25+ depot PDF publications uploaded by the Department of State Transport, Haryana.
- **Over 19,800+ Verified Departures**: Extensive route coverage across all Haryana Roadways depots and major bus stands.
- **Directional & Time Filtering**: Search buses by Origin, Destination, and 3-hour departure windows (e.g. `12PM - 3PM`, `6AM - 9AM`) or `All Times`.
- **🔄 Instant Return Bus**: 1-tap interactive button to immediately check reverse route timings with real-time Indian Standard Time (IST) departure sorting.
- **📞 Official Depot Enquiry Numbers**: Search results automatically display verified phone numbers for the origin & destination bus stands so passengers can call directly in urgent situations.
- **7-Day Automatic Auto-Refresh**: Background job (APScheduler) re-downloads and updates timetables weekly on autopilot.
- **Expandable Results**: Clean, clutter-free messages with a one-tap `[Show all buses]` inline expander.
- **Dual Mode (Local & Cloud)**: Supports local polling mode as well as production webhook deployment on free cloud platforms (Render.com).

---

## 📂 Project Structure

```
Hr Bus/
├── .env                  # Local environment config (git-ignored)
├── .env.example          # Environment template
├── Procfile              # Render / cloud process file
├── render.yaml           # Infrastructure-as-code config for Render.com
├── requirements.txt      # Python dependencies
├── data/
│   ├── roadways.db       # SQLite database (stations, routes, departures)
│   └── pdfs/             # Downloaded official depot PDFs cache
├── src/
│   ├── config.py         # Application configuration & env vars
│   ├── database/
│   │   ├── db.py         # SQLite schema initialization and connection helpers
│   │   └── queries.py    # Multi-station directional search & time filtering
│   ├── ingestion/
│   │   ├── scraper.py    # Discovers depot PDFs on hartrans.gov.in
│   │   └── parser.py     # Adaptive PyMuPDF table parser (handles dot/dash times)
│   ├── api/
│   │   └── app.py        # FastAPI backend serving health & webhook endpoints
│   ├── bot/
│   │   └── bot.py        # Telegram Bot handlers (navigation, search, callbacks)
│   └── webapp/           # Telegram Mini App frontend (HTML/CSS/JS)
├── scripts/
│   ├── ingest_all.py     # Ingestion script to crawl and parse all 25 depot PDFs
│   ├── check_stats.py    # Quick database statistics inspector
│   └── run_server.py     # Unified launcher (FastAPI + Bot + Scheduler)
└── tests/
    ├── test_parser.py    # Tests station normalization & parser logic
    └── test_queries.py   # Tests route matching and time filtering
```

---

## 🚀 Quick Setup & Local Development

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/nitingautam2007/hr-bus-bot.git
cd hr-bus-bot
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file from the template:
```bash
cp .env.example .env
```
Open `.env` and add your bot token from [@BotFather](https://t.me/botfather):
```env
BOT_TOKEN=your_telegram_bot_token_here
HOST=0.0.0.0
PORT=8000
DB_PATH=data/roadways.db
```

### 3. Ingest Depot Data (Optional locally)
If running locally with an empty database:
```bash
python scripts/ingest_all.py
```
*(On cloud deployment like Render, auto-ingestion runs automatically on first boot).*

### 4. Run the Bot
```bash
python scripts/run_server.py
```

---

## ☁️ 24/7 Free Deployment (Render.com)

1. **Push to GitHub**: Push this repository to your GitHub account.
2. **Deploy on Render**:
   - Create a free **Web Service** on [Render.com](https://render.com).
   - Connect your GitHub repository.
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python scripts/run_server.py`
3. **Set Environment Variables on Render**:
   - `BOT_TOKEN`: Your Telegram Bot token from @BotFather
   - `WEBHOOK_URL`: Your Render service URL (e.g. `https://your-service.onrender.com`)
   - `WEBHOOK_SECRET`: A secure passphrase for Telegram webhook validation
4. **Keep Awake**:
   - Set up a free HTTP monitor on [UptimeRobot](https://uptimerobot.com) pinging `https://your-service.onrender.com/api/health` every 5 minutes.

---

## ⚖️ Disclaimer

*This project is an unofficial community reference tool built for educational and public convenience purposes. It is **not** endorsed, operated, or officially affiliated with the Department of State Transport or Government of Haryana. All timetable data is publicly accessible and sourced from [hartrans.gov.in](https://hartrans.gov.in).*
