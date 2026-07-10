"""Command-line entrypoint.

    python -m src.cli scrape-minutes --start 2015-01-01 --end 2024-12-31
    python -m src.cli scrape-speeches --start 2015-01-01 --end 2024-12-31
    python -m src.cli analyze --input-dir data/raw/minutes --out data/processed/minutes_scores.csv
    python -m src.cli analyze --input-dir data/raw/minutes --out data/processed/minutes_scores.csv --no-model
    python -m src.cli trend --input data/processed/minutes_scores.csv --plot data/processed/minutes_trend.png
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from src.analysis.trends import plot_trend, scores_to_dataframe
from src.scraper.fed_speeches import scrape_speeches
from src.scraper.fomc_minutes import scrape_minutes
from src.sentiment.pipeline import analyze_corpus


def _cmd_scrape_minutes(args: argparse.Namespace) -> None:
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    saved = scrape_minutes(start, end, Path(args.out))
    print(f"Saved {len(saved)} minutes documents to {args.out}")


def _cmd_scrape_speeches(args: argparse.Namespace) -> None:
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    saved = scrape_speeches(start, end, Path(args.out))
    print(f"Saved {len(saved)} speech documents to {args.out}")


def _cmd_analyze(args: argparse.Namespace) -> None:
    scores = analyze_corpus(
        Path(args.input_dir),
        use_model=not args.no_model,
        model_name=args.model_name,
        model_weight=args.model_weight,
    )
    if not scores:
        print(f"No .txt documents found in {args.input_dir}")
        return

    df = scores_to_dataframe(scores)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} document scores to {out_path}")
    print(df[["doc_id", "date", "combined_score", "combined_label"]].to_string(index=False))


def _cmd_trend(args: argparse.Namespace) -> None:
    import pandas as pd

    df = pd.read_csv(args.input)
    out = plot_trend(df, Path(args.plot), window=args.window)
    print(f"Saved trend plot to {out}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fed-sentiment-analyzer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_minutes = subparsers.add_parser("scrape-minutes", help="Scrape historical FOMC minutes")
    p_minutes.add_argument("--start", required=True, help="Start date, YYYY-MM-DD")
    p_minutes.add_argument("--end", required=True, help="End date, YYYY-MM-DD")
    p_minutes.add_argument("--out", default="data/raw/minutes")
    p_minutes.set_defaults(func=_cmd_scrape_minutes)

    p_speeches = subparsers.add_parser("scrape-speeches", help="Scrape Fed speeches")
    p_speeches.add_argument("--start", required=True, help="Start date, YYYY-MM-DD")
    p_speeches.add_argument("--end", required=True, help="End date, YYYY-MM-DD")
    p_speeches.add_argument("--out", default="data/raw/speeches")
    p_speeches.set_defaults(func=_cmd_scrape_speeches)

    p_analyze = subparsers.add_parser("analyze", help="Score a directory of .txt documents")
    p_analyze.add_argument("--input-dir", required=True)
    p_analyze.add_argument("--out", required=True, help="Output CSV path")
    p_analyze.add_argument("--no-model", action="store_true", help="Lexicon-only, skip the transformer model")
    p_analyze.add_argument("--model-name", default=None, help="Override the HuggingFace model to use")
    p_analyze.add_argument("--model-weight", type=float, default=0.5, help="Weight of model score vs lexicon score, 0-1")
    p_analyze.set_defaults(func=_cmd_analyze)

    p_trend = subparsers.add_parser("trend", help="Plot hawkish/dovish trend over time from a scores CSV")
    p_trend.add_argument("--input", required=True, help="CSV produced by `analyze`")
    p_trend.add_argument("--plot", required=True, help="Output PNG path")
    p_trend.add_argument("--window", type=int, default=3, help="Rolling average window, in documents")
    p_trend.set_defaults(func=_cmd_trend)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
