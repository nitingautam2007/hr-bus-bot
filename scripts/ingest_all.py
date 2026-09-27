import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from src.database.db import init_db, get_db_connection
from src.ingestion.scraper import fetch_depot_pdf_list, download_depot_pdf
from src.ingestion.parser import ingest_depot_data

def main():
    parser = argparse.ArgumentParser(description="Ingest official Haryana Roadways timetable PDFs")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of depots to process (e.g. 3 for quick test)")
    parser.add_argument("--local-only", action="store_true", help="Only process existing PDFs in data/pdfs")
    args = parser.parse_args()

    print("Initializing database...")
    init_db()

    print("Fetching depot PDF list from hartrans.gov.in...")
    pdf_list = fetch_depot_pdf_list()
    print(f"Found {len(pdf_list)} depot PDFs.")

    if args.limit:
        pdf_list = pdf_list[:args.limit]
        print(f"Limiting to first {args.limit} depots for this run.")

    conn = get_db_connection()
    total_routes = 0
    total_departures = 0

    for idx, item in enumerate(pdf_list, 1):
        depot_name = item["depot"]
        print(f"\n[{idx}/{len(pdf_list)}] Processing {depot_name}...")
        try:
            pdf_path = download_depot_pdf(item)
            print(f"  Downloaded/Cached: {pdf_path.name}")
            routes_c, deps_c = ingest_depot_data(item, pdf_path, conn=conn)
            total_routes += routes_c
            total_departures += deps_c
            print(f"  Extracted: {routes_c} routes, {deps_c} departures.")
        except Exception as e:
            print(f"  Error processing {depot_name}: {e}")

    conn.close()
    print(f"\n[SUCCESS] Ingestion complete! Total routes: {total_routes}, Total departures: {total_departures}")

if __name__ == "__main__":
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

