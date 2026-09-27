import sqlite3
import pytest
from src.database.db import init_db, get_db_connection
from src.database.queries import (
    search_stations,
    get_station_by_id,
    get_station_by_name,
    find_routes_and_departures,
)

@pytest.fixture
def test_db(tmp_path):
    """Creates a fresh test database with sample stations, routes, and departures."""
    db_file = tmp_path / "test.db"
    init_db(db_file)
    conn = get_db_connection(db_file)

    with conn:
        # Insert stations
        cur = conn.cursor()
        cur.execute("INSERT INTO stations (name, aliases, depot) VALUES ('AMBALA', 'AMBALA CANTT', 'AMBALA')")
        ambala_id = cur.lastrowid
        cur.execute("INSERT INTO stations (name, aliases, depot) VALUES ('CHANDIGARH', 'SEC 17', 'CHANDIGARH')")
        chd_id = cur.lastrowid
        cur.execute("INSERT INTO stations (name, aliases, depot) VALUES ('DELHI (ISBT)', 'DELHI, KASHMERE GATE', 'DELHI')")
        delhi_id = cur.lastrowid
        cur.execute("INSERT INTO stations (name, aliases, depot) VALUES ('KARNAL', '', 'KARNAL')")
        karnal_id = cur.lastrowid

        # Insert routes:
        # Route 1: CHD -> DELHI via KARNAL
        cur.execute("""
            INSERT INTO routes (depot, from_station_id, to_station_id, via_station_id, bus_type)
            VALUES ('AMBALA', ?, ?, ?, 'ORDINARY')
        """, (chd_id, delhi_id, karnal_id))
        r1_id = cur.lastrowid

        # Departures for Route 1
        cur.execute("""
            INSERT INTO departures (route_id, departure_time, source, source_url, last_verified_at)
            VALUES (?, '06:00', 'Official Ambala PDF', 'http://test.pdf', '2026-09-06')
        """, (r1_id,))
        cur.execute("""
            INSERT INTO departures (route_id, departure_time, source, source_url, last_verified_at)
            VALUES (?, '14:30', 'Official Ambala PDF', 'http://test.pdf', '2026-09-06')
        """, (r1_id,))

    conn.close()
    return db_file

def test_station_search(test_db):
    conn = get_db_connection(test_db)
    # Prefix match priority
    results = search_stations("chan", conn=conn)
    assert len(results) >= 1
    assert results[0]["name"] == "CHANDIGARH"

    # Alias match
    alias_results = search_stations("kashmere", conn=conn)
    assert len(alias_results) >= 1
    assert alias_results[0]["name"] == "DELHI (ISBT)"
    conn.close()

def test_directionality_and_route_matching(test_db):
    conn = get_db_connection(test_db)
    chd = get_station_by_name("CHANDIGARH", conn=conn)
    delhi = get_station_by_name("DELHI (ISBT)", conn=conn)
    karnal = get_station_by_name("KARNAL", conn=conn)

    # 1. Direct search CHD -> DELHI
    deps = find_routes_and_departures(chd["id"], delhi["id"], conn=conn)
    assert len(deps) == 2
    assert deps[0]["departure_time"] == "06:00"
    assert deps[1]["departure_time"] == "14:30"
    assert deps[0]["route_via"] == "KARNAL"

    # 2. Intermediate search CHD -> KARNAL (From -> Via)
    deps_via1 = find_routes_and_departures(chd["id"], karnal["id"], conn=conn)
    assert len(deps_via1) == 2

    # 3. Intermediate search KARNAL -> DELHI (Via -> To)
    deps_via2 = find_routes_and_departures(karnal["id"], delhi["id"], conn=conn)
    assert len(deps_via2) == 2

    # 4. Strict reverse test: DELHI -> CHD should NOT return anything because route is one-way (CHD -> DELHI)
    deps_reverse = find_routes_and_departures(delhi["id"], chd["id"], conn=conn)
    assert len(deps_reverse) == 0

    conn.close()

def test_upcoming_departures_sorting(test_db):
    conn = get_db_connection(test_db)
    chd = get_station_by_name("CHANDIGARH", conn=conn)
    delhi = get_station_by_name("DELHI (ISBT)", conn=conn)

    # If queried at 10:00, 14:30 should appear before 06:00
    deps = find_routes_and_departures(chd["id"], delhi["id"], current_time="10:00", conn=conn)
    assert len(deps) == 2
    assert deps[0]["departure_time"] == "14:30"
    assert deps[1]["departure_time"] == "06:00"
    conn.close()
