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


def build_history(df: pd.DataFrame, window: int = 3, gap_threshold_days: int = 180) -> dict:
    df = _carry_forward_classic_signal(df, gap_threshold_days=gap_threshold_days)
    df = rolling_trend(df, window=window)
    annotations = _detect_gaps(df, threshold_days=gap_threshold_days)
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
        "window": window,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
