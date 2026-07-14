import pandas as pd

from src.analysis.fed_regimes import FED_CHAIRS, chair_for_date
from src.analysis.history import build_history


def _df(rows):
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_chair_for_date_matches_known_eras():
    assert chair_for_date("1975-01-01") == "Arthur Burns"
    assert chair_for_date("2020-06-01") == "Jerome Powell"
    assert chair_for_date("2026-06-01") == "Kevin Warsh"


def test_chair_for_date_none_when_out_of_range():
    assert chair_for_date(None) is None
    assert chair_for_date("1900-01-01") is None


def test_build_history_includes_all_regimes():
    df = _df([{"date": "2000-01-01", "combined_score": 0.1}])
    payload = build_history(df)
    assert payload["regimes"] == FED_CHAIRS
    assert len(payload["points"]) == 1
    assert payload["points"][0]["chair"] == "Alan Greenspan"


def test_build_history_detects_gap_and_low_signal_annotations():
    df = _df(
        [
            {"date": "2007-01-01", "combined_score": -0.2},
            {"date": "2016-01-01", "combined_score": 0.1},
        ]
    )
    payload = build_history(df, gap_threshold_days=180)
    types = {a["type"] for a in payload["annotations"]}
    assert "gap" in types
    assert "low_signal" in types

    gap = next(a for a in payload["annotations"] if a["type"] == "gap")
    assert gap["start"] == "2007-01-01"
    assert gap["end"] == "2016-01-01"

    # a synthetic NaN-scored row should be inserted at the gap's midpoint
    null_score_points = [p for p in payload["points"] if p["combined_score"] is None]
    assert len(null_score_points) == 1
    assert null_score_points[0]["date"] is not None


def test_build_history_no_gap_when_dates_are_close():
    df = _df(
        [
            {"date": "2020-01-01", "combined_score": 0.1},
            {"date": "2020-02-01", "combined_score": 0.2},
        ]
    )
    payload = build_history(df, gap_threshold_days=180)
    types = {a["type"] for a in payload["annotations"]}
    assert "gap" not in types
    assert all(p["combined_score"] is not None for p in payload["points"])
