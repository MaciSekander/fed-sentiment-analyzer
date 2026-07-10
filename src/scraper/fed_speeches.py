"""Scraper for Federal Reserve governor/president speeches.

The Fed's speech archive lists speeches by year at pages such as
    https://www.federalreserve.gov/newsevents/speech/YYYY-speeches.htm
with links to individual speeches. As with the minutes scraper, this
discovers links dynamically rather than hard-coding a fragile URL list.

Usage:
    python -m src.cli scrape-speeches --start 2015-01-01 --end 2024-12-31
"""

from __future__ import annotations

import argparse
import re
from datetime import date, datetime
from pathlib import Path

import requests

from src.scraper.utils import extract_main_text, fetch, save_text

BASE_URL = "https://www.federalreserve.gov"
YEAR_INDEX_TEMPLATE = f"{BASE_URL}/newsevents/speech/{{year}}-speeches.htm"

# e.g. /newsevents/speech/powell20240320a.htm
SPEECH_LINK_RE = re.compile(r"/newsevents/speech/([a-z\-]+)(\d{8})[a-z]?\.htm")


def discover_speech_links(start_year: int, end_year: int, session: requests.Session) -> dict[str, tuple[str, str]]:
    """Return {url_id: (iso_date, absolute_url)} for speeches in [start_year, end_year]."""
    links: dict[str, tuple[str, str]] = {}
    years = list(range(start_year, end_year + 1))
    failures = 0
    for year in years:
        index_url = YEAR_INDEX_TEMPLATE.format(year=year)
        try:
            html = fetch(index_url, session=session)
        except requests.RequestException as exc:
            failures += 1
            print(f"  [warn] could not fetch {index_url}: {exc}")
            continue
        for match in SPEECH_LINK_RE.finditer(html):
            speaker_slug, yyyymmdd = match.groups()
            iso_date = f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
            url_id = f"{speaker_slug}-{yyyymmdd}"
            links[url_id] = (iso_date, f"{BASE_URL}{match.group(0)}")

    if not links and failures == len(years):
        print(
            "  [error] every year-index page failed to fetch -- this usually means "
            "this machine/environment can't reach federalreserve.gov (no outbound "
            "network access, a proxy/firewall blocking it, or SSL interception). "
            "Try `curl -I https://www.federalreserve.gov/newsevents/speech/2023-speeches.htm` "
            "to confirm connectivity before re-running the scraper."
        )
    elif not links:
        print(
            "  [warn] year-index pages fetched successfully but no speech links matched "
            f"the pattern {SPEECH_LINK_RE.pattern!r} -- the Fed may have changed its "
            "page layout; inspect the page HTML and update SPEECH_LINK_RE."
        )
    return links


def scrape_speeches(start: date, end: date, out_dir: Path) -> list[Path]:
    session = requests.Session()
    links = discover_speech_links(start.year, end.year, session=session)
    saved: list[Path] = []
    for url_id, (iso_date, url) in sorted(links.items(), key=lambda kv: kv[1][0]):
        speech_date = datetime.strptime(iso_date, "%Y-%m-%d").date()
        if not (start <= speech_date <= end):
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
        filename = f"{iso_date}-speech-{url_id}.txt"
        path = save_text(text, out_dir, filename)
        saved.append(path)
        print(f"  saved {path}")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Federal Reserve speeches")
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD")
    parser.add_argument("--out", default="data/raw/speeches", help="Output directory")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    saved = scrape_speeches(start, end, Path(args.out))
    print(f"Saved {len(saved)} speech documents to {args.out}")


if __name__ == "__main__":
    main()
