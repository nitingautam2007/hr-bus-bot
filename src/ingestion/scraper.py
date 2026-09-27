import re
import os
import urllib.request
from pathlib import Path
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from src.config import HARTRANS_DEPOT_URL, BASE_DIR

PDF_CACHE_DIR = BASE_DIR / "data" / "pdfs"

def fetch_depot_pdf_list(base_url: str = HARTRANS_DEPOT_URL) -> List[Dict[str, Any]]:
    """
    Crawls the official hartrans.gov.in timetable pages (including pagination)
    to discover all depot PDF links.
    """
    results = []
    seen_urls = set()
    page = 1

    while True:
        url = f"{base_url.rstrip('/')}/page/{page}/" if page > 1 else base_url
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status != 200:
                    break
                html = resp.read().decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html, "html.parser")
                
                # Check all table rows or links
                found_on_page = 0
                for tr in soup.find_all("tr"):
                    cols = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                    pdf_links = [a["href"] for a in tr.find_all("a", href=True) if ".pdf" in a["href"].lower()]
                    
                    if cols and pdf_links:
                        depot_title = cols[0]
                        date_text = cols[1] if len(cols) > 1 else ""
                        for link in pdf_links:
                            if link not in seen_urls:
                                seen_urls.add(link)
                                results.append({
                                    "depot": depot_title,
                                    "date": date_text,
                                    "pdf_url": link,
                                    "source": f"hartrans.gov.in - {depot_title}"
                                })
                                found_on_page += 1
                
                if found_on_page == 0:
                    # No more links found, end pagination
                    break
                page += 1
        except Exception as e:
            # Reached end or network timeout
            break

    return results

def download_depot_pdf(pdf_info: Dict[str, Any], cache_dir: Path = PDF_CACHE_DIR, force_download: bool = False) -> Path:
    """
    Downloads a depot timetable PDF to local cache.
    If force_download=True, always re-downloads (used for weekly refresh).
    Returns the path to the downloaded file.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Safe filename
    clean_name = re.sub(r"[^\w\-_]", "_", pdf_info["depot"].lower())
    filename = f"{clean_name}.pdf"
    target_path = cache_dir / filename

    if not force_download and target_path.exists() and target_path.stat().st_size > 1024:
        return target_path

    req = urllib.request.Request(
        pdf_info["pdf_url"],
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        with open(target_path, "wb") as f:
            f.write(resp.read())

    return target_path
