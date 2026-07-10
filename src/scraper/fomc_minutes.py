"""Scraper for historical FOMC meeting minutes on federalreserve.gov.

The Fed publishes minutes at predictable URLs of the form
    https://www.federalreserve.gov/monetarypolicy/fomcminutesYYYYMMDD.htm
and links to them from per-year "calendar" / historical pages. Because the
Fed occasionally restructures its site, this scraper discovers links from
the listing pages rather than hard-coding every meeting date, and falls
back gracefully if a page's layout has changed.

Usage:
    python -m src.cli scrape-minutes --start 2015-01-01 --end 2024-12-31
"""

from __future__ import annotations

import argparse
import re
from datetime import date, datetime
from pathlib import Path

import requests

from src.scraper.utils import extract_main_text, fetch, save_text

BASE_URL = "https://www.federalreserve.gov"
CALENDAR_URL = f"{BASE_URL}/monetarypolicy/fomccalendars.htm"
# Historical FOMC materials are indexed by year on pages like:
#   https://www.federalreserve.gov/monetarypolicy/fomchistorical2015.htm
HISTORICAL_URL_TEMPLATE = f"{BASE_URL}/monetarypolicy/fomchistorical{{year}}.htm"

MINUTES_LINK_RE = re.compile(r"/monetarypolicy/(?:files/)?fomcminutes(\d{8})\.htm")


def discover_minutes_links(start_year: int, end_year: int, session: requests.Session) -> dict[str, str]:
    """Return {YYYY-MM-DD: absolute_url} for minutes published in [start_year, end_year]."""
    links: dict[str, str] = {}
    pages = [CALENDAR_URL] + [
        HISTORICAL_URL_TEMPLATE.format(year=year) for year in range(start_year, end_year + 1)
    ]
    for page_url in pages:
        try:
            html = fetch(page_url, session=session)
        except requests.RequestException:
            continue
        for match in MINUTES_LINK_RE.finditer(html):
            yyyymmdd = match.group(1)
            iso_date = f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
            links[iso_date] = f"{BASE_URL}{match.group(0)}"
    return links


def scrape_minutes(start: date, end: date, out_dir: Path) -> list[Path]:
    session = requests.Session()
    links = discover_minutes_links(start.year, end.year, session=session)
    saved: list[Path] = []
    for iso_date, url in sorted(links.items()):
        meeting_date = datetime.strptime(iso_date, "%Y-%m-%d").date()
        if not (start <= meeting_date <= end):
            continue
        try:
            html = fetch(url, session=session)
        except requests.RequestException as exc:
            print(f"  [skip] {url} ({exc})")
            continue
        text = extract_main_text(html)
        if len(text) < 200:
            print(f"  [warn] extracted text looks too short for {url}, skipping")
            continue
        filename = f"{iso_date}-fomc-minutes.txt"
        path = save_text(text, out_dir, filename)
        saved.append(path)
        print(f"  saved {path}")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape historical FOMC minutes")
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD")
    parser.add_argument("--out", default="data/raw/minutes", help="Output directory")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    saved = scrape_minutes(start, end, Path(args.out))
    print(f"Saved {len(saved)} minutes documents to {args.out}")


if __name__ == "__main__":
    main()
