import re
import fitz
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from src.database.db import get_db_connection

TIME_REGEX = re.compile(r"^\d{1,2}:\d{2}$")

def normalize_station_name(raw: str) -> str:
    """Cleans and standardizes station names."""
    if not raw:
        return ""
    name = raw.strip().upper()
    # Normalize multiple spaces, tabs, newlines
    name = re.sub(r"\s+", " ", name)
    # Remove trailing dashes or dots
    name = name.strip(" -.,")
    
    # Common standardizations
    if name in ("GURGAON", "GURGAON BUS STAND"):
        return "GURUGRAM"
    if name in ("DELHI", "DELHI ISBT", "ISBT DELHI", "ISBT KASHMERE GATE", "KASHMERE GATE"):
        return "DELHI (ISBT)"
    if name in ("CHANDIGARH", "CHANDIGARH SEC 17", "CHANDIGARH ISBT"):
        return "CHANDIGARH"
    return name

def get_or_create_station(conn: sqlite3.Connection, name: str, depot: str = "") -> Optional[int]:
    """Returns the station ID for a normalized name, inserting if not present."""
    name = normalize_station_name(name)
    if not name or name in ("VIA", "NIL", "NONE", "NA", "-", "--"):
        return None

    cur = conn.cursor()
    cur.execute("SELECT id FROM stations WHERE LOWER(name) = LOWER(?)", (name,))
    row = cur.fetchone()
    if row:
        return row[0]

    # Insert new station
    try:
        cur.execute(
            "INSERT INTO stations (name, depot) VALUES (?, ?)",
            (name, depot.strip().upper())
        )
        return cur.lastrowid
    except sqlite3.IntegrityError:
        cur.execute("SELECT id FROM stations WHERE LOWER(name) = LOWER(?)", (name,))
        row = cur.fetchone()
        return row[0] if row else None

def normalize_time(raw: str) -> Optional[str]:
    """Standardizes time strings formatted with colons, dots, or dashes (e.g. 5:40, 5.40, 5-40)."""
    if not raw:
        return None
    raw = raw.strip()
    m = re.match(r"^(\d{1,2})[:.\-](\d{2})$", raw)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        if 0 <= hh < 24 and 0 <= mm < 60:
            return f"{hh:02d}:{mm:02d}"
    return None

def parse_depot_pdf(pdf_path: Path | str, default_depot: str = "") -> List[Dict[str, Any]]:
    """
    Extracts structured timetable records from a Haryana Roadways depot PDF.
    Dynamically maps columns based on detected header row to support all depot formats.
    """
    doc = fitz.open(str(pdf_path))
    records = []
    col_map = {}

    for page in doc:
        tabs = page.find_tables()
        for tab in tabs.tables:
            rows = tab.extract()
            for row in rows:
                if not row:
                    continue

                cells = [str(c or "").strip().replace("\n", " ") for c in row]
                cells_upper = [c.upper() for c in cells]

                # Check if this row is a column header row
                if any("FROM" in c for c in cells_upper):
                    col_map = {}
                    for idx, c in enumerate(cells_upper):
                        if "FROM TO VIA" in c or ("FROM" in c and "TO" in c and "VIA" in c):
                            col_map["from"] = idx
                            col_map["to"] = idx + 1
                            col_map["via"] = idx + 2
                        elif "FROM" in c and "from" not in col_map:
                            col_map["from"] = idx
                        elif (c == "TO" or c.startswith("TO ") or c.endswith(" TO")) and "to" not in col_map:
                            col_map["to"] = idx
                        elif "TO" in c and "ROUTE" not in c and "to" not in col_map:
                            col_map["to"] = idx
                        elif "VIA" in c and "via" not in col_map:
                            col_map["via"] = idx
                        elif any(t in c for t in ("TIME", "DEPARTURE", "DEPARTU")) and "time" not in col_map:
                            col_map["time"] = idx
                        elif any(t in c for t in ("TYPE", "SERVICE")) and "type" not in col_map:
                            col_map["type"] = idx
                        elif "OPERAT" in c and "operator" not in col_map:
                            col_map["operator"] = idx
                        elif "DEPOT" in c and "depot" not in col_map:
                            col_map["depot"] = idx
                    continue

                # Fallback standard if no header found yet
                if not col_map or "from" not in col_map or "to" not in col_map:
                    col_map = {"depot": 0, "from": 1, "to": 2, "via": 3, "time": 4, "type": 5, "operator": 6}

                # Locate departure time
                time_idx = col_map.get("time", 4)
                time_val = None
                if time_idx < len(cells):
                    time_val = normalize_time(cells[time_idx])
                if not time_val:
                    for c in cells:
                        t = normalize_time(c)
                        if t:
                            time_val = t
                            break

                if not time_val:
                    continue

                from_st = cells[col_map["from"]] if col_map["from"] < len(cells) else ""
                to_st = cells[col_map["to"]] if col_map["to"] < len(cells) else ""
                via_st = cells[col_map["via"]] if ("via" in col_map and col_map["via"] < len(cells)) else ""
                bus_type = cells[col_map["type"]] if ("type" in col_map and col_map["type"] < len(cells)) else "ORDINARY"
                operator = cells[col_map["operator"]] if ("operator" in col_map and col_map["operator"] < len(cells)) else "HR"
                depot_val = cells[col_map["depot"]] if ("depot" in col_map and col_map["depot"] < len(cells)) else default_depot

                # Exclude header echoes or blank stations
                if from_st.upper() == "FROM" or to_st.upper() == "TO" or not from_st or not to_st:
                    continue

                formatted_time = time_val


                records.append({
                    "depot": (depot_val or default_depot).strip().upper(),
                    "from": from_st.strip(),
                    "to": to_st.strip(),
                    "via": via_st.strip(),
                    "departure_time": formatted_time,
                    "bus_type": bus_type.strip().upper() or "ORDINARY",
                    "operator": operator.strip().upper() or "HR",
                    "service_day": "ALL DAY"
                })

    doc.close()
    return records


def ingest_depot_data(
    pdf_info: Dict[str, Any],
    pdf_path: Path | str,
    conn: Optional[sqlite3.Connection] = None
) -> Tuple[int, int]:
    """
    Parses a downloaded PDF and ingests stations, routes, and departures into SQLite.
    Returns (inserted_routes_count, inserted_departures_count).
    """
    default_depot = pdf_info.get("depot", "").replace(" Depot", "").strip()
    records = parse_depot_pdf(pdf_path, default_depot=default_depot)
    if not records:
        return (0, 0)

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    routes_count = 0
    departures_count = 0
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    source_label = pdf_info.get("source", f"hartrans.gov.in - {pdf_info.get('depot', 'Depot')}")
    source_url = pdf_info.get("pdf_url", "https://hartrans.gov.in/bus-time-table-depot-wise/")

    try:
        cur = conn.cursor()
        for rec in records:
            from_id = get_or_create_station(conn, rec["from"], rec["depot"])
            to_id = get_or_create_station(conn, rec["to"], rec["depot"])
            via_id = get_or_create_station(conn, rec["via"], rec["depot"]) if rec["via"] else None

            if not from_id or not to_id or from_id == to_id:
                continue

            # Insert or fetch route
            cur.execute("""
                INSERT INTO routes (
                    depot, from_station_id, to_station_id, via_station_id, bus_type, operator, service_day
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(depot, from_station_id, to_station_id, via_station_id, bus_type, service_day)
                DO UPDATE SET operator = excluded.operator
                RETURNING id
            """, (rec["depot"], from_id, to_id, via_id, rec["bus_type"], rec["operator"], rec["service_day"]))
            
            route_row = cur.fetchone()
            if route_row:
                route_id = route_row[0]
                routes_count += 1
            else:
                cur.execute("""
                    SELECT id FROM routes
                    WHERE depot = ? AND from_station_id = ? AND to_station_id = ?
                      AND (via_station_id IS ? OR via_station_id = ?)
                      AND bus_type = ? AND service_day = ?
                """, (rec["depot"], from_id, to_id, via_id, via_id, rec["bus_type"], rec["service_day"]))
                r = cur.fetchone()
                if not r:
                    continue
                route_id = r[0]

            # Insert departure
            try:
                cur.execute("""
                    INSERT INTO departures (
                        route_id, departure_time, source, source_url, last_verified_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(route_id, departure_time)
                    DO UPDATE SET last_verified_at = excluded.last_verified_at
                """, (route_id, rec["departure_time"], source_label, source_url, now_iso))
                departures_count += 1
            except sqlite3.Error:
                pass

        conn.commit()
    finally:
        if should_close:
            conn.close()

    return (routes_count, departures_count)
