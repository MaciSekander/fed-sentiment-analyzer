import pandas as pd

from src.analysis.fed_regimes import FED_CHAIRS, chair_for_date
from src.analysis.history import build_history
from src.sentiment.pipeline import label_from_score


def _df(rows):
    for r in rows:
        r.setdefault("combined_label", label_from_score(r["combined_score"]))
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


def test_classic_era_signal_decays_after_a_spike_instead_of_snapping_to_zero():
    df = _df(
        [
            {"date": "1967-11-27", "combined_score": 1.0},
            {"date": "1967-12-12", "combined_score": 0.0},
            {"date": "1968-01-09", "combined_score": 0.0},
            {"date": "1968-02-06", "combined_score": 0.0},
        ]
    )
    scores = [p["combined_score"] for p in build_history(df)["points"]]
    assert scores[0] == 1.0
    assert 0 < scores[1] < scores[0]
    assert 0 < scores[2] < scores[1]
    assert 0 <= scores[3] < scores[2]


def test_classic_era_signal_resets_across_an_archive_gap():
    df = _df(
        [
            {"date": "1970-01-01", "combined_score": 1.0},
            {"date": "1971-06-01", "combined_score": 0.0},  # >180 days later
        ]
    )
    scores = [p["combined_score"] for p in build_history(df, gap_threshold_days=180)["points"] if p["combined_score"] is not None]
    assert scores[-1] == 0.0


def test_classic_era_decay_does_not_apply_after_the_cutoff():
    df = _df(
        [
            {"date": "2000-01-01", "combined_score": 0.3},
            {"date": "2000-02-01", "combined_score": 0.0},
        ]
    )
    scores = [p["combined_score"] for p in build_history(df)["points"]]
    assert scores == [0.3, 0.0]


def _highlights_df():
    # Modern-era (post-1994) dates only, so the classic-era decay path
    # never touches these -- keeps the numbers predictable for assertions.
    return _df(
        [
            {"date": "2020-01-01", "combined_score": 0.05},  # neutral
            {"date": "2020-02-01", "combined_score": 0.3},  # hawkish (streak start)
            {"date": "2020-03-01", "combined_score": 0.35},  # hawkish
            {"date": "2020-04-01", "combined_score": -0.6},  # dovish -- sharpest reversal from 0.35
            {"date": "2020-05-01", "combined_score": -0.4},  # dovish
            {"date": "2020-06-01", "combined_score": -0.5},  # dovish
            {"date": "2020-07-01", "combined_score": 0.02},  # neutral (current)
        ]
    )


def test_highlights_present_in_build_history_output():
    payload = build_history(_highlights_df(), window=1)
    assert "highlights" in payload
    h = payload["highlights"]
    assert h["current"]["date"] == "2020-07-01"
    assert h["current"]["combined_label"] == "neutral"


def test_highlights_streaks_and_extremes():
    h = build_history(_highlights_df(), window=1)["highlights"]
    assert h["hawkish_streak"] == {
        "length": 2,
        "start_date": "2020-02-01",
        "end_date": "2020-03-01",
        "chair": "Jerome Powell",
        "end_chair": "Jerome Powell",
    }
    assert h["dovish_streak"]["length"] == 3
    assert h["dovish_streak"]["start_date"] == "2020-04-01"
    assert h["most_hawkish"]["date"] == "2020-03-01"
    assert h["most_dovish"]["date"] == "2020-04-01"


def test_highlights_sharpest_reversal():
    h = build_history(_highlights_df(), window=1)["highlights"]
    assert h["sharpest_reversal"]["before"]["date"] == "2020-03-01"
    assert h["sharpest_reversal"]["after"]["date"] == "2020-04-01"
    assert h["sharpest_reversal"]["delta"] == 0.95


def test_highlights_by_chair_grouping():
    h = build_history(_highlights_df(), window=1)["highlights"]
    chairs = {c["chair"] for c in h["by_chair"]}
    assert chairs == {"Jerome Powell"}
    assert h["by_chair"][0]["meeting_count"] == 7


def test_highlights_ignore_synthetic_gap_break_rows():
    df = _df(
        [
            {"date": "2007-01-01", "combined_score": -0.2},
            {"date": "2016-01-01", "combined_score": 0.3},
        ]
    )
    # This gap inserts a synthetic NaN-scored row -- must not appear in any
    # highlight (streak/extreme/reversal), and must not crash the math.
    h = build_history(df, gap_threshold_days=180)["highlights"]
    assert h["most_hawkish"]["combined_score"] is not None
    assert h["most_dovish"]["combined_score"] is not None
    assert h["current"]["date"] == "2016-01-01"
