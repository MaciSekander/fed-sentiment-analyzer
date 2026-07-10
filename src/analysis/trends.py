"""Turn a corpus of per-document scores into a hawkish/dovish time series."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.sentiment.pipeline import DocumentScore


def scores_to_dataframe(scores: list[DocumentScore]) -> pd.DataFrame:
    df = pd.DataFrame([s.to_dict() for s in scores])
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date")
    return df


def rolling_trend(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """Add a rolling-average column smoothing combined_score over `window` docs."""
    df = df.copy()
    df["combined_score_rolling"] = df["combined_score"].rolling(window=window, min_periods=1).mean()
    return df


def _with_gap_breaks(df: pd.DataFrame, threshold_days: int = 180) -> pd.DataFrame:
    """Insert a NaN-scored row at the midpoint of any date gap wider than
    threshold_days, so the plotted line breaks instead of drawing a
    misleading straight line across a period with no source documents
    (e.g. this repo's archives have no coverage between 2009 and 2014).
    """
    if "date" not in df.columns or not df["date"].notna().any():
        return df

    df = df.sort_values("date").reset_index(drop=True)
    gap_days = df["date"].diff().dt.days
    break_rows = []
    for i in range(1, len(df)):
        if gap_days.iloc[i] > threshold_days:
            midpoint = df["date"].iloc[i - 1] + (df["date"].iloc[i] - df["date"].iloc[i - 1]) / 2
            break_rows.append({"date": midpoint, "combined_score": float("nan"), "combined_score_rolling": float("nan")})

    if not break_rows:
        return df
    return pd.concat([df, pd.DataFrame(break_rows)], ignore_index=True).sort_values("date").reset_index(drop=True)


def plot_trend(df: pd.DataFrame, out_path: Path, window: int = 3) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    df = rolling_trend(df, window=window)
    has_dates = "date" in df.columns and df["date"].notna().any()
    if has_dates:
        df = _with_gap_breaks(df)
    x = df["date"] if has_dates else range(len(df))

    fig, ax = plt.subplots(figsize=(12, 5))
    marker_size = 4 if len(df) > 60 else 6
    ax.plot(x, df["combined_score"], marker="o", markersize=marker_size, linewidth=0.8, alpha=0.35, label="Per-document score")
    ax.plot(x, df["combined_score_rolling"], linewidth=2, label=f"{window}-doc rolling average")
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_ylabel("Hawkish (+) / Dovish (-)")
    ax.set_title("Fed Communication Hawkish-Dovish Index")
    ax.legend()

    if has_dates:
        locator = mdates.AutoDateLocator(minticks=6, maxticks=12)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    fig.tight_layout()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
