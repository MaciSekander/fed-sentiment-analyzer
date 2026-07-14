from io import StringIO
from unittest.mock import Mock, patch

import pandas as pd

from src.ingestion.fed_funds import build_fedfunds_payload, fetch_fedfunds

SAMPLE_CSV = "observation_date,FEDFUNDS\n1954-07-01,0.80\n1954-08-01,1.22\n"


def test_fetch_fedfunds_parses_and_renames_columns():
    mock_resp = Mock()
    mock_resp.text = SAMPLE_CSV
    mock_resp.raise_for_status = Mock()
    with patch("src.ingestion.fed_funds.requests.get", return_value=mock_resp) as mock_get:
        df = fetch_fedfunds()
    mock_get.assert_called_once()
    assert list(df.columns) == ["date", "rate"]
    assert len(df) == 2
    assert df.iloc[0]["rate"] == 0.80


def test_build_fedfunds_payload_shape():
    df = pd.read_csv(StringIO(SAMPLE_CSV)).rename(columns={"observation_date": "date", "FEDFUNDS": "rate"})
    df["date"] = pd.to_datetime(df["date"])
    payload = build_fedfunds_payload(df)
    assert payload["series_id"] == "FEDFUNDS"
    assert payload["points"] == [
        {"date": "1954-07-01", "rate": 0.80},
        {"date": "1954-08-01", "rate": 1.22},
    ]


def test_build_fedfunds_payload_skips_missing_values():
    df = pd.DataFrame({"date": pd.to_datetime(["2020-01-01", "2020-02-01"]), "rate": [1.5, float("nan")]})
    payload = build_fedfunds_payload(df)
    assert len(payload["points"]) == 1
