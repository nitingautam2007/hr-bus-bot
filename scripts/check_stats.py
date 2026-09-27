import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_db_connection
from src.database.queries import search_stations, find_routes_and_departures

conn = get_db_connection()
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM stations")
print("Total stations in DB:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM routes")
print("Total routes in DB:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM departures")
print("Total departures in DB:", cur.fetchone()[0])

st_chd = search_stations("chandigarh")[0]
st_del = search_stations("delhi")[0]
deps = find_routes_and_departures(st_chd["id"], st_del["id"], current_time="10:00")
print(f"\nDepartures from {st_chd['name']} to {st_del['name']}: {len(deps)}")
if deps:
    print("Sample departure:", dict(deps[0]))
