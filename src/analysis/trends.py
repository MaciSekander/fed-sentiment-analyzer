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


def plot_trend(df: pd.DataFrame, out_path: Path, window: int = 3) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = rolling_trend(df, window=window)

    fig, ax = plt.subplots(figsize=(10, 5))
    x = df["date"] if "date" in df.columns and df["date"].notna().any() else range(len(df))
    ax.plot(x, df["combined_score"], marker="o", alpha=0.4, label="Per-document score")
    ax.plot(x, df["combined_score_rolling"], linewidth=2, label=f"{window}-doc rolling average")
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_ylabel("Hawkish (+) / Dovish (-)")
    ax.set_title("Fed Communication Hawkish-Dovish Index")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
