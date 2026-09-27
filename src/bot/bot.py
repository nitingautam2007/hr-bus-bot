import json
import logging
import re
from datetime import datetime
import pytz
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from src.config import BOT_TOKEN
from src.database.queries import (
    search_stations,
    get_station_by_id,
    get_station_by_name,
    find_routes_and_departures,
    find_departures_by_names,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

DISCLAIMER_TEXT = (
    "DISCLAIMER:\n"
    "This bot is an unofficial timetable reference tool and is NOT affiliated with, "
    "endorsed by, or operated by the Department of State Transport or Government of Haryana. "
    "All timetable data is sourced directly from publicly available official depot records on hartrans.gov.in."
)

# Canonical list of all Haryana Roadways bus depots & major stands, in strict alphabetical order
DEPOTS = [
    "Ambala Cantt",
    "Ambala City",
    "Bahadurgarh",
    "Bhiwani",
    "Chandigarh",
    "Charkhi Dadri",
    "Dabwali",
    "Delhi (ISBT)",
    "Faridabad",
    "Fatehabad",
    "Gohana",
    "Gurugram",
    "Hansi",
    "Hisar",
    "Jhajjar",
    "Jind",
    "Kaithal",
    "Kalka",
    "Karnal",
    "Kurukshetra",
    "Narnaul",
    "Narwana",
    "Nuh",
    "Palwal",
    "Panchkula",
    "Panipat",
    "Pehowa",
    "Rewari",
    "Rohtak",
    "Sirsa",
    "Sonipat",
    "Tohana",
    "Yamunanagar",
]

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Clean main keyboard with 1. Search Bus, 2. Help, and 3. Suggestion."""
    keyboard = [
        ["1. Search Bus"],
        ["2. Help", "3. Suggestion"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_depot_keyboard(exclude_depot: str = None, show_back: bool = False) -> ReplyKeyboardMarkup:
    """Builds a clean 3-column keyboard for bus depots in strict alphabetical order."""
    depots = [d for d in DEPOTS if not exclude_depot or d.lower() != exclude_depot.lower()]
    keyboard = []
    
    # 3 buttons per row for compact, clean alphabetical layout
    for i in range(0, len(depots), 3):
        row = depots[i:i + 3]
        keyboard.append(row)

    if show_back:
        keyboard.append(["Back", "Cancel"])
    else:
        keyboard.append(["Cancel"])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Time slots: 3-hour windows across the full day
TIME_SLOTS = [
    ("12AM - 3AM",  "00:00", "02:59"),
    ("3AM - 6AM",   "03:00", "05:59"),
    ("6AM - 9AM",   "06:00", "08:59"),
    ("9AM - 12PM",  "09:00", "11:59"),
    ("12PM - 3PM",  "12:00", "14:59"),
    ("3PM - 6PM",   "15:00", "17:59"),
    ("6PM - 9PM",   "18:00", "20:59"),
    ("9PM - 12AM",  "21:00", "23:59"),
    ("All Times",   None,    None),
]

def get_time_keyboard() -> ReplyKeyboardMarkup:
    """Builds a 2-column time range keyboard."""
    labels = [slot[0] for slot in TIME_SLOTS]
    keyboard = []
    for i in range(0, len(labels) - 1, 2):
        keyboard.append(labels[i:i+2])
    # "All Times" gets its own row at the bottom
    keyboard.append(["All Times"])
    keyboard.append(["Back", "Cancel"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_ist_time() -> str:
    """Returns current time in Indian Standard Time (IST) as HH:MM."""
    ist = pytz.timezone("Asia/Kolkata")
    return datetime.now(ist).strftime("%H:%M")

def format_timetable_response(
    from_name: str,
    to_name: str,
    departures: list,
    current_time: str,
    time_label: str = None,
    show_all: bool = False,
) -> tuple[str, int]:
    """
    Formats departure records in a clean, readable layout.
    Returns (message_text, has_more_count) where has_more_count > 0 means
    there are more buses beyond the shown limit (used to add inline button).
    """
    time_info = f"Time  : {time_label}" if time_label and time_label != "All Times" else f"Time  : {current_time} IST"

    if not departures:
        text = (
            f"No Buses Found\n\n"
            f"From : {from_name.title()}\n"
            f"To      : {to_name.title()}\n"
            f"{time_info}\n\n"
            "No buses found for this route and time window.\n\n"
            "Try a different time range or check connecting routes via Ambala, Karnal, Panipat, or Rohtak."
        )
        return text, 0

    total = len(departures)
    if time_label and time_label != "All Times":
        pool = departures         # Specific window: all in chronological order
        later = []
        section_label = "--- Buses in this window ---"
    elif time_label == "All Times":
        pool = departures         # All buses sorted upcoming-first (already sorted by query)
        later = []
        section_label = "--- All Buses (Upcoming First) ---"
    else:
        # No time_label at all (direct text search): show upcoming / earlier split
        pool = [d for d in departures if d["departure_time"] >= current_time]
        later = [d for d in departures if d["departure_time"] < current_time]
        section_label = "--- Upcoming Buses ---"

    max_show = total if show_all else 15
    show_pool = pool[:max_show]
    has_more = len(pool) - max_show if not show_all else 0

    lines = [
        "Haryana Roadways",
        f"From : {from_name.title()}",
        f"To      : {to_name.title()}",
        f"{time_info}  |  Total: {total}",
        "",
    ]

    if show_pool:
        lines.append(section_label)
        for dep in show_pool:
            t = dep["departure_time"]
            btype = dep.get("bus_type", "ORDINARY").title()
            via = dep.get("route_via", "").strip()
            if via and via.upper() not in ("", "NIL", "DIRECT", "-"):
                lines.append(f"  {t}  {btype}  (via {via.title()})")
            else:
                lines.append(f"  {t}  {btype}")

    # Earlier buses section — only for direct text search (no time_label)
    show_later = later[-5:] if (later and not show_all) else (later if show_all else [])
    if show_later:
        lines.append("")
        lines.append("--- Earlier Today ---")
        for dep in show_later:
            t = dep["departure_time"]
            btype = dep.get("bus_type", "ORDINARY").title()
            lines.append(f"  {t}  {btype}")

    lines.append("")
    lines.append("Source: hartrans.gov.in  |  Data refreshed every 7 days")

    return "\n".join(lines), has_more

SUGGESTION_URL = "https://t.me/nitingautam2007"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start command with polite welcome, timetable info, emergency notice, and navigation."""
    context.user_data.clear()

    message = (
        "Welcome to Haryana Roadways Timetable Assistant! 🚌\n\n"
        "I am a student passionate about building helpful community projects. "
        "This bot provides timetable reference data sourced directly from official Haryana Roadways depot records (hartrans.gov.in).\n\n"
        "📌 Key Information:\n"
        "• Timetable Reliability: Bus schedules generally remain stable throughout the season and rarely change day-to-day. The bot automatically refreshes data weekly from official records.\n"
        "• Important Notice: For urgent or emergency travel, please verify timings directly with your local bus stand inquiry or the official website, as operational changes, maintenance, or bot errors can occur.\n\n"
        "💡 Suggestions & Feedback:\n"
        "Have an idea, found an issue, or want to suggest a route? Tap '3. Suggestion' below to reach out directly!"
    )

    await update.message.reply_text(
        message,
        reply_markup=get_main_keyboard(),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /help command."""
    help_text = (
        "Haryana Roadways Timetable Help:\n\n"
        "1. Tap '1. Search Bus' to pick origin, destination, and departure time.\n"
        "2. Or type your route directly: 'Chandigarh to Delhi'.\n"
        "3. Tap '3. Suggestion' to send feedback or report issues.\n\n"
        f"{DISCLAIMER_TEXT}"
    )
    await update.message.reply_text(
        help_text,
        reply_markup=get_main_keyboard()
    )

async def suggestion_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles 3. Suggestion command with direct Telegram link."""
    text = (
        "💡 Suggestions & Feedback\n\n"
        "Thank you for using this bot! Since this is a student project, your feedback and suggestions help make it better for everyone.\n\n"
        "If you noticed incorrect timings, missing routes, or have ideas for new features, feel free to send a message:\n\n"
        "👉 Profile: @nitingautam2007"
    )
    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Send Suggestion (@nitingautam2007)", url=SUGGESTION_URL)]
    ])
    await update.message.reply_text(
        text,
        reply_markup=inline_kb
    )

async def show_from_depots(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the list of all bus depots for Origin (From)."""
    context.user_data["awaiting"] = "from_depot"
    await update.message.reply_text(
        "Select Origin Bus Depot (FROM):",
        reply_markup=get_depot_keyboard(show_back=False)
    )

async def show_to_depots(update: Update, context: ContextTypes.DEFAULT_TYPE, from_depot: str) -> None:
    """Displays the list of all bus depots for Destination (To)."""
    context.user_data["from_depot"] = from_depot
    context.user_data["awaiting"] = "to_depot"

    await update.message.reply_text(
        f"From: {from_depot}\n\nSelect Destination Bus Depot (TO):",
        reply_markup=get_depot_keyboard(exclude_depot=from_depot, show_back=True)
    )

async def handle_search_result(update: Update, context: ContextTypes.DEFAULT_TYPE, from_name: str, to_name: str) -> None:
    """Queries DB and outputs the timetable (no time filter, called from direct text)."""
    current_time = get_ist_time()
    departures = find_departures_by_names(from_name, to_name, current_time=current_time)
    context.user_data.clear()
    # Store for "show all" callback
    context.user_data["last_search"] = {
        "from_name": from_name, "to_name": to_name,
        "departures": departures, "current_time": current_time, "time_label": None,
    }
    reply, has_more = format_timetable_response(from_name.upper(), to_name.upper(), departures, current_time)
    if has_more > 0:
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"Show all {len(departures)} buses", callback_data="show_all")]])
        await update.message.reply_text(reply, reply_markup=inline_kb)
        await update.message.reply_text("Search again:", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text(reply, reply_markup=get_main_keyboard())

async def show_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, to_depot: str) -> None:
    """Asks user to pick a time range after selecting FROM and TO depots."""
    context.user_data["to_depot"] = to_depot
    context.user_data["awaiting"] = "time_slot"
    from_depot = context.user_data.get("from_depot", "")
    await update.message.reply_text(
        f"From : {from_depot}\nTo      : {to_depot}\n\nSelect Time Range:",
        reply_markup=get_time_keyboard()
    )

async def handle_search_result_timed(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    from_name: str,
    to_name: str,
    time_from: str = None,
    time_to: str = None,
    time_label: str = None,
) -> None:
    """Queries DB and outputs the timetable, with optional time range filter."""
    current_time = get_ist_time()
    departures = find_departures_by_names(
        from_name, to_name,
        current_time=current_time if not time_from else None,
        time_from=time_from,
        time_to=time_to,
    )
    context.user_data.clear()
    # Store for "show all" callback
    context.user_data["last_search"] = {
        "from_name": from_name, "to_name": to_name,
        "departures": departures, "current_time": current_time, "time_label": time_label,
    }
    reply, has_more = format_timetable_response(
        from_name.upper(), to_name.upper(), departures, current_time, time_label=time_label,
    )
    if has_more > 0:
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"Show all {len(departures)} buses", callback_data="show_all")]])
        await update.message.reply_text(reply, reply_markup=inline_kb)
        await update.message.reply_text("Search again:", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text(reply, reply_markup=get_main_keyboard())

async def show_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'Show all buses' inline button — expands the message to show every departure."""
    query = update.callback_query
    await query.answer()

    search = context.user_data.get("last_search", {})
    departures = search.get("departures", [])
    from_name = search.get("from_name", "")
    to_name = search.get("to_name", "")
    current_time = search.get("current_time", get_ist_time())
    time_label = search.get("time_label")

    if not departures:
        await query.edit_message_text("No data available. Please search again.")
        return

    full_text, _ = format_timetable_response(
        from_name.upper(), to_name.upper(), departures, current_time,
        time_label=time_label, show_all=True,
    )
    await query.edit_message_text(full_text)


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unified handler for clean navigation and depot selection."""
    text = (update.message.text or "").strip()
    if not text:
        return

    # Cancel action
    if text.lower() in ("cancel", "/cancel"):
        context.user_data.clear()
        await update.message.reply_text("Cancelled.", reply_markup=get_main_keyboard())
        return

    # Back action
    if text.lower() in ("back", "/back"):
        awaiting = context.user_data.get("awaiting")
        if awaiting == "time_slot":
            # Go back to TO depot selection
            from_depot = context.user_data.get("from_depot", "")
            await show_to_depots(update, context, from_depot)
        else:
            await show_from_depots(update, context)
        return

    # 1. Search Bus
    if text in ("1. Search Bus", "1", "Search Bus", "Search", "/search"):
        await show_from_depots(update, context)
        return

    # 2. Help
    if text in ("2. Help", "2", "Help", "/help"):
        await help_command(update, context)
        return

    # 3. Suggestion
    if text in ("3. Suggestion", "3", "Suggestion", "Feedback", "/suggestion", "/feedback"):
        await suggestion_command(update, context)
        return

    # Direct "From to To" text (e.g. "Chandigarh to Delhi")
    if " to " in text.lower():
        parts = [p.strip() for p in text.lower().split(" to ", 1)]
        await handle_search_result(update, context, parts[0], parts[1])
        return

    awaiting = context.user_data.get("awaiting")

    # Step 1: Picking Origin (From)
    if awaiting == "from_depot":
        matched_depot = None
        for d in DEPOTS:
            if text.lower() == d.lower() or text.lower() in d.lower():
                matched_depot = d
                break

        if not matched_depot:
            results = search_stations(text, limit=1)
            if results:
                matched_depot = results[0]["name"]

        if matched_depot:
            await show_to_depots(update, context, matched_depot)
            return
        else:
            await update.message.reply_text(
                f"Depot '{text}' not recognized. Please choose from the list below:",
                reply_markup=get_depot_keyboard(show_back=False)
            )
            return

    # Step 2: Picking Destination (To) — then ask for time range
    if awaiting == "to_depot":
        from_depot = context.user_data.get("from_depot")
        matched_depot = None

        for d in DEPOTS:
            if text.lower() == d.lower() or text.lower() in d.lower():
                matched_depot = d
                break

        if not matched_depot:
            results = search_stations(text, limit=1)
            if results:
                matched_depot = results[0]["name"]

        if matched_depot:
            await show_time_selection(update, context, matched_depot)
            return
        else:
            await update.message.reply_text(
                f"Depot '{text}' not recognized. Please choose from the list below:",
                reply_markup=get_depot_keyboard(exclude_depot=from_depot, show_back=True)
            )
            return

    # Step 3: Picking Time Range
    if awaiting == "time_slot":
        from_depot = context.user_data.get("from_depot")
        to_depot = context.user_data.get("to_depot")

        # Match user's text to a time slot
        matched_slot = None
        for slot in TIME_SLOTS:
            if text.strip().lower() == slot[0].lower():
                matched_slot = slot
                break

        if matched_slot:
            label, t_from, t_to = matched_slot
            await handle_search_result_timed(
                update, context, from_depot, to_depot,
                time_from=t_from, time_to=t_to, time_label=label
            )
            return
        else:
            await update.message.reply_text(
                "Please select a time range from the buttons below:",
                reply_markup=get_time_keyboard()
            )
            return

    # If user sent any other text
    await update.message.reply_text(
        "Please select '1. Search Bus', '2. Help', or '3. Suggestion'.",
        reply_markup=get_main_keyboard()
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs unhandled exceptions."""
    logger.error(f"Exception while handling update: {context.error}", exc_info=context.error)


def create_bot_application() -> Application:
    """Initializes the Telegram Bot application."""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        raise ValueError(
            "BOT_TOKEN is not configured in .env! "
            "Please paste your Telegram Bot token from @BotFather into the .env file."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("suggestion", suggestion_command))
    app.add_handler(CommandHandler("feedback", suggestion_command))
    app.add_handler(CommandHandler("search", text_message_handler))
    app.add_handler(CallbackQueryHandler(show_all_callback, pattern="^show_all$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    app.add_error_handler(error_handler)

    return app

def run_bot() -> None:
    """Runs the bot via polling."""
    bot_app = create_bot_application()
    print("Telegram Bot is running (polling)... Press Ctrl+C to stop.")
    bot_app.run_polling()

if __name__ == "__main__":
    run_bot()
