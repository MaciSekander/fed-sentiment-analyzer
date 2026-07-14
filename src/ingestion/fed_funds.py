"""Fetch the historical effective Fed funds rate from FRED for the
website's small-multiples rate chart (paired with, but never plotted on
the same axis as, the sentiment score -- different units/scale entirely).

FRED (the St. Louis Fed's public data service) publishes a plain CSV
export with no API key required:
    https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS
FEDFUNDS is the monthly effective federal funds rate, 1954-present.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests

FRED_FEDFUNDS_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"


def fetch_fedfunds(url: str = FRED_FEDFUNDS_URL) -> pd.DataFrame:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    from io import StringIO

    df = pd.read_csv(StringIO(resp.text))
    df = df.rename(columns={"observation_date": "date", "FEDFUNDS": "rate"})
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def build_fedfunds_payload(df: pd.DataFrame) -> dict:
    points = [
        {"date": row["date"].date().isoformat(), "rate": float(row["rate"])}
        for _, row in df.iterrows()
        if pd.notna(row["rate"])
    ]
    return {
        "points": points,
        "series_id": "FEDFUNDS",
        "source": "FRED (Federal Reserve Bank of St. Louis)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
