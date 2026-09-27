import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.database.db import get_db_connection

def search_stations(query: str, limit: int = 15, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Searches stations by name or aliases, prioritizing exact/prefix matches."""
    q = query.strip()
    if not q:
        return []

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cur = conn.cursor()
        # Exact/prefix match first, then substring
        cur.execute("""
            SELECT id, name, aliases, depot,
                CASE 
                    WHEN LOWER(name) = LOWER(?) THEN 1
                    WHEN LOWER(name) LIKE LOWER(? || '%') THEN 2
                    WHEN LOWER(name) LIKE LOWER('%' || ? || '%') THEN 3
                    ELSE 4
                END as match_priority
            FROM stations
            WHERE LOWER(name) LIKE LOWER('%' || ? || '%')
               OR LOWER(aliases) LIKE LOWER('%' || ? || '%')
            ORDER BY match_priority, name ASC
            LIMIT ?
        """, (q, q, q, q, q, limit))
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        if should_close:
            conn.close()

def get_station_by_id(station_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    """Fetches a single station by primary key ID."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, aliases, depot FROM stations WHERE id = ?", (station_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()

def get_station_by_name(name: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    """Fetches station by exact name (case-insensitive)."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, aliases, depot FROM stations WHERE LOWER(name) = LOWER(?)", (name.strip(),))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()

def get_all_stations(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Returns all stations ordered alphabetically."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, aliases, depot FROM stations ORDER BY name ASC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        if should_close:
            conn.close()

def find_routes_and_departures(
    from_station_id: int,
    to_station_id: int,
    current_time: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Finds verified departures from from_station_id to to_station_id.
    Matches:
      1. Direct routes: from_station_id -> to_station_id
      2. Origin to intermediate via: from_station_id -> to_station_id (where to_station_id is via_station)
      3. Intermediate via to destination: from_station_id -> to_station_id (where from_station_id is via_station)
    Preserves strict directionality.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cur = conn.cursor()
        
        # We perform a union query to get direct and valid via matches with match explanation
        query = """
        SELECT 
            d.id as departure_id,
            d.departure_time,
            d.source,
            d.source_url,
            d.last_verified_at,
            r.id as route_id,
            r.depot,
            r.bus_type,
            r.operator,
            r.service_day,
            s_from.name as route_from,
            s_to.name as route_to,
            s_via.name as route_via,
            CASE
                WHEN r.from_station_id = ? AND r.to_station_id = ? THEN 'Direct'
                WHEN r.from_station_id = ? AND r.via_station_id = ? THEN 'Direct via ' || s_via.name
                WHEN r.via_station_id = ? AND r.to_station_id = ? THEN 'Originates from ' || s_from.name
                ELSE 'Connecting'
            END as route_note
        FROM departures d
        JOIN routes r ON d.route_id = r.id
        JOIN stations s_from ON r.from_station_id = s_from.id
        JOIN stations s_to ON r.to_station_id = s_to.id
        LEFT JOIN stations s_via ON r.via_station_id = s_via.id
        WHERE 
            (r.from_station_id = ? AND r.to_station_id = ?)
            OR (r.from_station_id = ? AND r.via_station_id = ?)
            OR (r.via_station_id = ? AND r.to_station_id = ?)
        ORDER BY d.departure_time ASC
        """
        params = (
            from_station_id, to_station_id,
            from_station_id, to_station_id,
            from_station_id, to_station_id,
            from_station_id, to_station_id,
            from_station_id, to_station_id,
            from_station_id, to_station_id
        )
        cur.execute(query, params)
        results = [dict(r) for r in cur.fetchall()]

        if not results:
            return []

        # Sort with respect to current_time (upcoming first)
        if current_time:
            upcoming = [r for r in results if r["departure_time"] >= current_time]
            past = [r for r in results if r["departure_time"] < current_time]
            return upcoming + past

        return results

    finally:
        if should_close:
            conn.close()

def get_top_stations(limit: int = 8, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Returns the most frequent bus stands in the network."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id, s.name, COUNT(*) as route_count
            FROM routes r
            JOIN stations s ON r.from_station_id = s.id
            GROUP BY s.id, s.name
            ORDER BY route_count DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        if should_close:
            conn.close()

def get_connected_destinations(from_station_id: int, limit: int = 12, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Returns valid destination bus stands reachable from from_station_id."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT s.id, s.name, COUNT(*) as dep_count
            FROM (
                SELECT r.to_station_id as dest_id, d.id as dep_id
                FROM routes r
                JOIN departures d ON d.route_id = r.id
                WHERE r.from_station_id = ?
                UNION ALL
                SELECT r.via_station_id as dest_id, d.id as dep_id
                FROM routes r
                JOIN departures d ON d.route_id = r.id
                WHERE r.from_station_id = ? AND r.via_station_id IS NOT NULL
                UNION ALL
                SELECT r.to_station_id as dest_id, d.id as dep_id
                FROM routes r
                JOIN departures d ON d.route_id = r.id
                WHERE r.via_station_id = ?
            ) dests
            JOIN stations s ON dests.dest_id = s.id
            WHERE s.id != ?
            GROUP BY s.id, s.name
            ORDER BY dep_count DESC, s.name ASC
            LIMIT ?
        """, (from_station_id, from_station_id, from_station_id, from_station_id, limit))
        return [dict(r) for r in cur.fetchall()]
    finally:
        if should_close:
            conn.close()

def get_station_ids_for_name(name: str, conn: sqlite3.Connection) -> List[int]:
    """Finds all station IDs that match or relate to the given depot/stand name."""
    import re
    clean = re.sub(r"\s*\(.*?\)", "", name).strip()
    clean_no_type = re.sub(r"\s+(Cantt|City|ISBT|Bus Stand)", "", clean, flags=re.IGNORECASE).strip()
    if clean_no_type.upper() == "CHARKHI DADRI":
        clean_no_type = "DADRI"

    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM stations
        WHERE LOWER(name) = LOWER(?)
           OR LOWER(name) = LOWER(?)
           OR LOWER(name) LIKE LOWER(? || '%')
           OR LOWER(name) LIKE LOWER('%' || ? || '%')
           OR LOWER(aliases) LIKE LOWER('%' || ? || '%')
    """, (name.strip(), clean, clean_no_type, clean_no_type, clean_no_type))
    return [r[0] for r in cur.fetchall()]

def find_departures_by_names(
    from_name: str,
    to_name: str,
    current_time: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Finds verified departures between two depot/station names by matching all
    applicable station IDs (e.g. Ambala Cantt, Ambala City, Ambala -> Delhi ISBT, Delhi).
    Optionally filters by a departure time window (time_from, time_to in HH:MM format).
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        from_ids = get_station_ids_for_name(from_name, conn)
        to_ids = get_station_ids_for_name(to_name, conn)

        if not from_ids or not to_ids:
            return []

        p_from = ",".join("?" for _ in from_ids)
        p_to = ",".join("?" for _ in to_ids)

        # Build optional time filter clause
        time_filter = ""
        time_params: list = []
        if time_from and time_to:
            if time_from <= time_to:
                time_filter = "AND d.departure_time >= ? AND d.departure_time <= ?"
                time_params = [time_from, time_to]
            else:
                # Wraps midnight e.g. 22:00 to 02:00
                time_filter = "AND (d.departure_time >= ? OR d.departure_time <= ?)"
                time_params = [time_from, time_to]

        query = f"""
        SELECT 
            d.id as departure_id,
            d.departure_time,
            d.source,
            d.source_url,
            d.last_verified_at,
            r.id as route_id,
            r.depot,
            r.bus_type,
            r.operator,
            r.service_day,
            s_from.name as route_from,
            s_to.name as route_to,
            s_via.name as route_via,
            CASE
                WHEN r.from_station_id IN ({p_from}) AND r.to_station_id IN ({p_to}) THEN 'Direct'
                WHEN r.from_station_id IN ({p_from}) AND r.via_station_id IN ({p_to}) THEN 'Direct via ' || s_via.name
                WHEN r.via_station_id IN ({p_from}) AND r.to_station_id IN ({p_to}) THEN 'Originates from ' || s_from.name
                ELSE 'Connecting'
            END as route_note
        FROM departures d
        JOIN routes r ON d.route_id = r.id
        JOIN stations s_from ON r.from_station_id = s_from.id
        JOIN stations s_to ON r.to_station_id = s_to.id
        LEFT JOIN stations s_via ON r.via_station_id = s_via.id
        WHERE 
            (
                (r.from_station_id IN ({p_from}) AND r.to_station_id IN ({p_to}))
                OR (r.from_station_id IN ({p_from}) AND r.via_station_id IN ({p_to}))
                OR (r.via_station_id IN ({p_from}) AND r.to_station_id IN ({p_to}))
            )
        {time_filter}
        ORDER BY d.departure_time ASC
        """
        params = (
            from_ids + to_ids +
            from_ids + to_ids +
            from_ids + to_ids +
            from_ids + to_ids +
            from_ids + to_ids +
            from_ids + to_ids +
            time_params
        )
        cur = conn.cursor()
        cur.execute(query, params)
        results = [dict(r) for r in cur.fetchall()]

        if not results:
            return []

        # Sort by current_time (upcoming first) only when no time filter applied
        if current_time and not time_from:
            upcoming = [r for r in results if r["departure_time"] >= current_time]
            past = [r for r in results if r["departure_time"] < current_time]
            return upcoming + past

        return results
    finally:
        if should_close:
            conn.close()


