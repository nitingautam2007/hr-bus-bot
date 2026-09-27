# PRD: HR Roadways Timetable Bot

## 1. Summary

A Telegram bot that lets a user pick a "from" and "to" bus stand and returns the real, verified Haryana Roadways bus timetable for that route — pulled from official government sources only, never third-party aggregators. The core design constraint: **no mismatched routes**. This is solved by making stop selection a controlled-vocabulary tap (via a Telegram Mini App with autocomplete) instead of free-text input.

## 2. Problem

There is no existing Telegram chatbot for Haryana Roadways timetables. Riders currently have to dig through PDFs on hartrans.gov.in, use unofficial aggregator sites of unknown accuracy, or ask at the depot. Free-text search for bus stand names is error-prone — similar names, spelling variants, and ambiguous inputs lead to wrong-route results.

## 3. Goals

- Let a user query a route (from stop → to stop) and get accurate, sourced bus timings in under a few seconds.
- Guarantee every timing shown traces back to an official government source, with a visible "verified as of" date.
- Eliminate input-driven mismatches by having the user select from a known list of stops, not type free text.
- Keep the system maintainable by one person (no manual data entry per route).

### Non-goals (out of scope for v1)

- Live GPS bus tracking / ETA prediction.
- Ticket booking or payment.
- Coverage of every private/other-state operator — Haryana Roadways only.
- Route data for states other than Haryana (may extend later).

## 4. Data sources (must be official / verifiable)

| Source | What it gives | Format | Update frequency |
|---|---|---|---|
| `hartrans.gov.in` → "Bus Time Table (Depot Wise)" | Per-depot timetables (24+ depots) | PDF, hosted on gov S3 (`cdnbbsr.s3waas.gov.in`) | Infrequent (observed: months) |
| `timetable.hrtransport.org` ("Bus Time Table (Live)", linked from hartrans.gov.in) | Possibly live/near-real-time schedule data | JS single-page app — **must inspect browser Network tab for an underlying JSON/REST API before assuming it can be scraped** | Unknown, investigate |
| `ors.hartrans.gov.in` / `ebooking.hrtransport.gov.in` | Real departure times surfaced during ticket search | Web form / booking flow | Real-time-ish, but scraping is more fragile (sessions, possible CAPTCHA) |

**Explicitly excluded as data sources:** any third-party aggregator site (e.g. haryanabusinfo.in, myharyanaroadways.com, and similar) — not verifiable as official, must not be used to populate the database, even as a fallback.

Every stored timetable row must carry a `source` field and a `last_verified_at` timestamp, both of which are shown to the end user with every result.

## 5. User flow

1. User starts the bot (`/start`). The reply must open with an explicit disclaimer that this is an **unofficial** bot, not affiliated with or endorsed by the Government of Haryana or the Department of State Transport, and that timetable data is sourced from public official records (not government-run). After the disclaimer, the message shows a button to open the Mini App ("Search timetable").
2. Mini App shows two fields: **From** and **To**. As the user types, autocomplete suggests matching stops from the bot's own stations list (not live-queried from the gov site).
3. User taps a suggestion for From, then for To. This guarantees both are valid, known stop IDs — no typos, no ambiguous names.
4. Mini App sends `{from_stop_id, to_stop_id}` back to the bot via `Telegram.WebApp.sendData()`.
5. Bot backend looks up routes in its database that pass through both stops in the correct order.
6. Backend filters to upcoming departures (from current time), sorts by soonest, and returns a list: bus number, departure time, bus type (ordinary/express/AC/Volvo), via-stops, depot.
7. Each result includes: `Source: <site>, verified <date>`.
8. If no direct route exists: bot says so plainly and, if feasible, suggests the nearest known route or interchange point — never silently substitutes an unrelated route.

## 6. System architecture

**Components:**

- **Scraper/ingestion service** — scheduled job (e.g. daily) that:
  - Downloads and parses depot PDFs from hartrans.gov.in (PDF table extraction).
  - Investigates and, if viable, calls the underlying API of timetable.hrtransport.org.
  - Normalizes results into a single schema (see §7) and writes to the database, stamping `source` and `last_verified_at`.
  - Never runs synchronously inside a user request — the bot only ever reads from its own database.

- **Stations table** — the controlled vocabulary of all known bus stands/stops, each with canonical name + known aliases, used to power Mini App autocomplete. Built once from the scraped data, updated when new stops are discovered.

- **Backend API** — serves:
  - Autocomplete queries from the Mini App (search against the stations table).
  - Route lookups from the bot (given from_stop_id + to_stop_id → matching routes/timings).

- **Telegram bot** — handles `/start`, opens the Mini App via a `web_app` button, receives `web_app_data`, calls the backend API, formats and sends the reply.

- **Telegram Mini App (Web App)** — a small hosted web page (HTML/JS) using the Telegram Web App SDK, with two autocomplete inputs, calling the backend API for suggestions, and submitting via `sendData()`.

## 7. Data model (draft)

**stations**
- `id`
- `canonical_name`
- `aliases` (list/text)
- `depot` (nullable)

**routes**
- `id`
- `route_name` / `route_number` (if published)
- `bus_type` (ordinary / express / AC / Volvo)
- `depot`
- `stop_sequence` (ordered list of station IDs, so "from → to" can be checked for order and directness, not just co-membership)

**departures**
- `id`
- `route_id`
- `stop_id`
- `departure_time` (local time, HH:MM)
- `source`
- `last_verified_at`

## 8. Functional requirements

- FR1: Mini App autocomplete must only suggest values from the stations table — never freeform text passed through to route lookup.
- FR2: Every timetable result must display source + last-verified date.
- FR3: Route matching must respect stop order along a route (A→B must not match a route where B comes before A).
- FR4: No result may be sourced from a non-official site.
- FR5: If no verified direct route is found, the bot must say so explicitly rather than returning a partial or unrelated match.
- FR6: Scraper must run on a schedule, independent of user requests, and must not block or slow down bot responses.
- FR7: The bot's `/start` message, profile bio, and about text must all state clearly that it is unofficial and not affiliated with or endorsed by the Government of Haryana or the Department of State Transport. The bot must not use the official Haryana Roadways logo/emblem as its profile picture.

## 9. Non-functional requirements

- Respect hartrans.gov.in server load — scrape on a reasonable schedule (e.g. daily), not per-request.
- Bot response time for a route query should be near-instant (DB read, not live scrape).
- System should be maintainable by a single developer; avoid manual per-route data entry.

## 10. Milestones (suggested build order)

1. Manually collect 3–4 depot PDFs, parse into the DB schema, validate the data model.
2. Build a plain-text Telegram bot (typed from/to) matching against the DB — validates end-to-end flow without the Mini App yet.
3. Build and integrate the Telegram Mini App with autocomplete, wire up `sendData()`.
4. Automate the scraper/ingestion job on a schedule; investigate the timetable.hrtransport.org API.
5. Add polish: no-route handling, nearest-stop suggestions, source/verified-date display formatting.

## 11. Open questions

- Does timetable.hrtransport.org expose a usable JSON API? (Needs manual devtools inspection — not confirmed yet.)
- Are route numbers/names published anywhere, or only stop-level departure times per depot PDF?
- How should the stations list handle multiple bus stands within the same city/depot?
