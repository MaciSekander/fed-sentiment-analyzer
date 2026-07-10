"""Ingest locally-provided historical Fed archives (zip files) into the same
per-date .txt layout the scrapers produce, so the rest of the pipeline
(src/sentiment/*, src/analysis/*, src/cli.py) doesn't need to know or care
whether a document was scraped live or came from a pre-collected archive.

Three archive shapes are supported, matching what shipped in this repo
under data/archives/:

1. fomc_minutes_1967_2008.zip
   One .txt file per meeting, named e.g. "txt/19670620.txt". Plain-text
   minutes, 1967-2008. A handful of these files were saved with Windows
   codepage (cp1252) punctuation rather than UTF-8 -- decoding falls back
   through utf-8 -> cp1252 -> latin-1 (replace) to handle that.

2. fomc_statements_1994_2008.zip
   Same layout, one .txt file per meeting (e.g. "txt_statements/
   19940204.txt"), but these are the short post-meeting policy statements
   rather than the full minutes -- kept in a separate output folder
   (data/raw/statements/) since they're a distinct document type.

3. fed_scrape_2015_2023.zip
   Contains a single CSV (Fed_Scrape-2015-2023.csv) with columns
   [index, Date, Type, Text] -- one row per paragraph. Date is the
   *meeting* date (YYYYMMDD) for Type == 1 rows, which is the actual
   minutes text; Type == 0 rows are just the short "the Fed released
   minutes for the meeting held on ..." release-announcement blurb and
   are not meeting content, so they're skipped. Paragraphs are
   concatenated per meeting date, in their original row order, into one
   document per meeting.

Combined, these cover minutes from 1967-2008 and 2015-2023, plus
statements from 1994-2008. There's a 2009-2014 gap where no local archive
was provided -- that range would need scraping (src/scraper/) or another
source if you want it filled in.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

DATE_RE = re.compile(r"(\d{4})(\d{2})(\d{2})")


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _iso_date_from_name(name: str) -> str | None:
    match = DATE_RE.search(Path(name).stem)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{year}-{month}-{day}"


def ingest_per_file_zip(zip_path: Path, out_dir: Path, filename_suffix: str) -> list[Path]:
    """Ingest a zip containing one .txt file per document, named with an
    embedded YYYYMMDD date, into out_dir/{iso_date}-{filename_suffix}.txt.
    """
    out_dir = Path(out_dir)
    saved: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".txt"):
                continue
            iso_date = _iso_date_from_name(name)
            if iso_date is None:
                print(f"  [skip] {name}: no YYYYMMDD date found in filename")
                continue
            text = _decode(zf.read(name))
            out_path = out_dir / f"{iso_date}-{filename_suffix}.txt"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
            saved.append(out_path)
    return sorted(saved)


def ingest_csv_archive(
    zip_path: Path,
    out_dir: Path,
    csv_name: str | None = None,
    content_type: int = 1,
    filename_suffix: str = "fomc-minutes",
) -> list[Path]:
    """Ingest the paragraph-level CSV archive, reassembling one document per
    meeting date from its Type == content_type rows (default 1 = actual
    minutes text; Type 0 rows are just release-announcement blurbs).
    """
    import pandas as pd

    out_dir = Path(out_dir)
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if csv_name is None:
            if not names:
                raise ValueError(f"No CSV found in {zip_path}")
            csv_name = names[0]
        with zf.open(csv_name) as f:
            df = pd.read_csv(f)

    required = {"Date", "Type", "Text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{csv_name} is missing expected columns: {missing}")

    df = df[df["Type"] == content_type]
    saved: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for date, group in df.groupby("Date", sort=True):
        iso_date = f"{str(int(date))[0:4]}-{str(int(date))[4:6]}-{str(int(date))[6:8]}"
        text = "\n\n".join(str(t) for t in group["Text"].tolist())
        out_path = out_dir / f"{iso_date}-{filename_suffix}.txt"
        out_path.write_text(text, encoding="utf-8")
        saved.append(out_path)
    return sorted(saved)


def ingest_all(
    archives_dir: Path,
    minutes_out: Path,
    statements_out: Path,
) -> dict[str, list[Path]]:
    """Convenience entrypoint wiring up the three known archives shipped in
    data/archives/. Silently skips any archive that isn't present.
    """
    archives_dir = Path(archives_dir)
    results: dict[str, list[Path]] = {"minutes": [], "statements": []}

    minutes_zip = archives_dir / "fomc_minutes_1967_2008.zip"
    if minutes_zip.exists():
        saved = ingest_per_file_zip(minutes_zip, minutes_out, "fomc-minutes")
        print(f"  ingested {len(saved)} documents from {minutes_zip.name}")
        results["minutes"].extend(saved)

    statements_zip = archives_dir / "fomc_statements_1994_2008.zip"
    if statements_zip.exists():
        saved = ingest_per_file_zip(statements_zip, statements_out, "fomc-statement")
        print(f"  ingested {len(saved)} documents from {statements_zip.name}")
        results["statements"].extend(saved)

    csv_zip = archives_dir / "fed_scrape_2015_2023.zip"
    if csv_zip.exists():
        saved = ingest_csv_archive(csv_zip, minutes_out, content_type=1, filename_suffix="fomc-minutes")
        print(f"  ingested {len(saved)} meeting documents from {csv_zip.name}")
        results["minutes"].extend(saved)

    return results
