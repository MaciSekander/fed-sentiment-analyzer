"""Shared HTTP + text-extraction helpers for the scrapers."""

from __future__ import annotations

import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "fed-sentiment-analyzer/0.1 "
    "(research tool; contact via GitHub repo issues)"
)

REQUEST_TIMEOUT = 20
REQUEST_DELAY_SECONDS = 1.0  # be polite to federalreserve.gov


def fetch(url: str, session: requests.Session | None = None) -> str:
    """GET a URL and return the response body as text, raising on error."""
    session = session or requests.Session()
    headers = {"User-Agent": USER_AGENT}
    resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return resp.text


def extract_main_text(html: str) -> str:
    """Best-effort extraction of the main article text from a Fed web page.

    federalreserve.gov pages don't expose a stable single selector across
    all sections/years, so this tries a few known containers before
    falling back to concatenating every <p> tag on the page.
    """
    soup = BeautifulSoup(html, "lxml")

    for selector in ("div#article", "div.col-xs-12.col-sm-8.col-md-8", "main"):
        node = soup.select_one(selector)
        if node is not None:
            text = node.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return _clean(text)

    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    return _clean("\n".join(p for p in paragraphs if p))


def _clean(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def save_text(text: str, out_dir: Path, filename: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(text, encoding="utf-8")
    return path


def extract_date_from_filename(filename: str) -> str | None:
    """Pull a YYYYMMDD or YYYY-MM-DD date out of a filename, if present."""
    match = re.search(r"(\d{4})-?(\d{2})-?(\d{2})", filename)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{year}-{month}-{day}"
