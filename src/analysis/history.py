"""Build the JSON payload served by GET /api/history.

Combines the rolling-average trend (rolling_trend/with_gap_breaks, both
reused as-is from trends.py) with Fed Chair era labels (fed_regimes.py) into
one JSON-ready dict. This runs once, offline, as a local precompute step
(see src/cli.py's `history` subcommand and README.md) -- the backend just
serves the resulting static file (backend/app/routers/history.py), no
pandas/model work happens on the request path.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.analysis.fed_regimes import FED_CHAIRS, chair_for_date
from src.analysis.trends import rolling_trend, with_gap_breaks
from src.sentiment.lexicon import CLASSIC_ERA_CUTOFF
from src.sentiment.pipeline import label_from_score

# The classic-era lexicon only fires on discrete discount-rate-change
# announcements (see lexicon.py's module docstring) -- most meetings score
# exactly 0.0. Scored as isolated events, that reads as a sharp spike
# snapping straight back to zero at the very next meeting, which
# understates reality: a rate hike sets a policy stance that persists
# until the next action, not just for one meeting. CLASSIC_DECAY_PER_MEETING
# carries the last signal forward, fading it out over subsequent
# no-action meetings rather than dropping it to neutral immediately.
CLASSIC_DECAY_PER_MEETING = 0.85
CLASSIC_DECAY_FLOOR = 0.05


def _carry_forward_classic_signal(df: pd.DataFrame, gap_threshold_days: int) -> pd.DataFrame:
    df = df.sort_values("date").reset_index(drop=True)
    carried = 0.0
    prev_date = None
    for i in range(len(df)):
        date = df.at[i, "date"]
        if pd.isna(date):
            prev_date = None
            carried = 0.0
            continue
        if prev_date is not None and (date - prev_date).days > gap_threshold_days:
            carried = 0.0  # don't carry a stale signal across an archive gap
        prev_date = date

        if date.strftime("%Y-%m-%d") >= CLASSIC_ERA_CUTOFF:
            carried = 0.0
            continue

        score = df.at[i, "combined_score"]
        if pd.isna(score):
            continue
        if score != 0:
            carried = score
        else:
            carried *= CLASSIC_DECAY_PER_MEETING
            if abs(carried) < CLASSIC_DECAY_FLOOR:
                carried = 0.0
            df.at[i, "combined_score"] = round(carried, 4)
            df.at[i, "combined_label"] = label_from_score(carried)
    return df


def _detect_gaps(df: pd.DataFrame, threshold_days: int) -> list[dict]:
    """Find date gaps wider than threshold_days between consecutive documents
    (e.g. this repo's archives have no coverage between 2009 and 2014) --
    same detection rule as with_gap_breaks, but reporting the gap's real
    start/end dates for a human-readable annotation rather than inserting a
    synthetic plotting row.
    """
    if "date" not in df.columns or not df["date"].notna().any():
        return []
    df = df.sort_values("date").reset_index(drop=True)
    gap_days = df["date"].diff().dt.days
    gaps = []
    for i in range(1, len(df)):
        if gap_days.iloc[i] > threshold_days:
            gaps.append(
                {
                    "type": "gap",
                    "start": df["date"].iloc[i - 1].date().isoformat(),
                    "end": df["date"].iloc[i].date().isoformat(),
                    "label": "No archive coverage",
                }
            )
    return gaps


def _meeting_summary(row: pd.Series) -> dict:
    date_str = row["date"].date().isoformat()
    rolling = row.get("combined_score_rolling")
    return {
        "doc_id": row.get("doc_id") if pd.notna(row.get("doc_id")) else None,
        "date": date_str,
        "combined_score": float(row["combined_score"]),
        "combined_score_rolling": float(rolling) if pd.notna(rolling) else None,
        "combined_label": row["combined_label"],
        "chair": chair_for_date(date_str),
    }


def _longest_streak(real: pd.DataFrame, label: str) -> dict | None:
    best: tuple[int, int, int] | None = None
    start_idx = None
    run_len = 0
    for i, row in enumerate(real.itertuples()):
        if row.combined_label == label:
            if run_len == 0:
                start_idx = i
            run_len += 1
        else:
            if run_len and (best is None or run_len > best[0]):
                best = (run_len, start_idx, i - 1)
            run_len = 0
    if run_len and (best is None or run_len > best[0]):
        best = (run_len, start_idx, len(real) - 1)
    if best is None:
        return None
    length, start, end = best
    start_row, end_row = real.iloc[start], real.iloc[end]
    start_chair = chair_for_date(start_row["date"].date().isoformat())
    end_chair = chair_for_date(end_row["date"].date().isoformat())
    return {
        "length": length,
        "start_date": start_row["date"].date().isoformat(),
        "end_date": end_row["date"].date().isoformat(),
        "chair": start_chair,
        # A streak spanning a chair transition (e.g. 1977-1980, Burns into
        # Volcker) shouldn't be attributed to only the first chair --
        # end_chair differs from `chair` in that case.
        "end_chair": end_chair,
    }


def _build_highlights(df: pd.DataFrame) -> dict:
    """Summary stats for the website's highlights dashboard, computed over
    real meetings only. Must run on the rolling-averaged, classic-era-decayed
    dataframe (i.e. after rolling_trend()/_carry_forward_classic_signal(),
    which have already run by the time build_history() calls this) but
    *before* with_gap_breaks() inserts synthetic NaN-scored rows, which
    would otherwise corrupt streak/extreme/reversal math.
    """
    real = df[df["combined_score"].notna()].sort_values("date").reset_index(drop=True)

    latest = real.iloc[-1]
    current = _meeting_summary(latest)

    one_year_ago = latest["date"] - pd.Timedelta(days=365)
    trailing = real[real["date"] >= one_year_ago]
    trailing_year_average = float(trailing["combined_score"].mean()) if len(trailing) else None

    # Ranked by the *rolling* score, not the raw per-meeting score: a raw
    # discount-rate-change hit always starts at exactly +-1 (see
    # _score_classic in lexicon.py), so many meetings tie at the ceiling --
    # not a useful "most extreme" ranking. The rolling average instead
    # surfaces the most extreme *sustained* stance, which is the more
    # interesting headline (and ranks real ties, like two documents in the
    # same rolling window, no worse than the raw score would).
    rolling = real["combined_score_rolling"]
    most_hawkish = _meeting_summary(real.loc[rolling.idxmax()]) if rolling.notna().any() else None
    most_dovish = _meeting_summary(real.loc[rolling.idxmin()]) if rolling.notna().any() else None

    diffs = real["combined_score"].diff().abs()
    reversal = None
    if diffs.notna().any():
        idx = diffs.idxmax()
        reversal = {
            "delta": round(float(diffs.loc[idx]), 4),
            "before": _meeting_summary(real.loc[idx - 1]),
            "after": _meeting_summary(real.loc[idx]),
        }

    by_chair_df = (
        real.assign(chair=real["date"].apply(lambda d: chair_for_date(d.date().isoformat())))
        .groupby("chair", sort=False)["combined_score"]
        .agg(["mean", "count"])
        .reset_index()
        .sort_values("mean", ascending=False)
    )
    by_chair = [
        {"chair": row["chair"], "average_score": round(float(row["mean"]), 4), "meeting_count": int(row["count"])}
        for _, row in by_chair_df.iterrows()
    ]

    return {
        "current": current,
        "trailing_year_average": trailing_year_average,
        "hawkish_streak": _longest_streak(real, "hawkish"),
        "dovish_streak": _longest_streak(real, "dovish"),
        "most_hawkish": most_hawkish,
        "most_dovish": most_dovish,
        "sharpest_reversal": reversal,
        "by_chair": by_chair,
    }


def build_history(df: pd.DataFrame, window: int = 3, gap_threshold_days: int = 180) -> dict:
    df = _carry_forward_classic_signal(df, gap_threshold_days=gap_threshold_days)
    df = rolling_trend(df, window=window)
    annotations = _detect_gaps(df, threshold_days=gap_threshold_days)
    highlights = _build_highlights(df)
    df = with_gap_breaks(df, threshold_days=gap_threshold_days)

    points = []
    for _, row in df.iterrows():
        date = row["date"]
        date_str = date.date().isoformat() if pd.notna(date) else None
        score = row["combined_score"]
        rolling = row["combined_score_rolling"]
        points.append(
            {
                "doc_id": row.get("doc_id") if pd.notna(row.get("doc_id")) else None,
                "date": date_str,
                "combined_score": float(score) if pd.notna(score) else None,
                "combined_score_rolling": float(rolling) if pd.notna(rolling) else None,
                "combined_label": row.get("combined_label") if pd.notna(row.get("combined_label")) else None,
                "chair": chair_for_date(date_str),
            }
        )

    annotations.append(
        {
            "type": "low_signal",
            "start": None,
            "end": CLASSIC_ERA_CUTOFF,
            "label": "Classic-era lexicon: sparser signal, driven by discount-rate change "
            "announcements rather than continuous tone language",
        }
    )

    return {
        "points": points,
        "regimes": FED_CHAIRS,
        "annotations": annotations,
        "highlights": highlights,
        "window": window,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
