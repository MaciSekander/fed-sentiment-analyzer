"""Build the per-document JSON detail served by GET /api/documents/{doc_id}.

Joins a document's raw text with its row in the scores CSV and its
lexicon phrase-match spans (src/sentiment/lexicon.py's find_phrase_spans)
into one JSON-ready dict, so the website's document drill-down can show
the actual source text with the matched phrases highlighted. This runs
once, offline, as a local precompute step (see src/cli.py's `documents`
subcommand) -- same philosophy as src/analysis/history.py's history.json.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.fed_regimes import chair_for_date
from src.sentiment.lexicon import find_phrase_spans


def build_document_detail(text: str, doc_id: str, date: str | None, score_row: dict) -> dict:
    matches = find_phrase_spans(text, date=date)
    return {
        "doc_id": doc_id,
        "date": date,
        "chair": chair_for_date(date),
        "combined_score": float(score_row["combined_score"]),
        "combined_label": score_row["combined_label"],
        "lexicon_score": float(score_row["lexicon_score"]),
        "word_count": int(score_row["word_count"]),
        "text": text,
        "matches": [
            {
                "phrase": m.phrase,
                "category": m.category,
                "start": m.start,
                "end": m.end,
                "weight": m.weight,
            }
            for m in matches
        ],
    }


def build_all_document_details(input_dir: Path, scores_csv: Path) -> list[dict]:
    scores = pd.read_csv(scores_csv, dtype={"date": str}).set_index("doc_id")
    details = []
    for path in sorted(Path(input_dir).glob("*.txt")):
        doc_id = path.stem
        if doc_id not in scores.index:
            continue  # e.g. statements/speeches ingested into a different dir, or a doc not scored
        row = scores.loc[doc_id]
        text = path.read_text(encoding="utf-8")
        details.append(build_document_detail(text, doc_id, row.get("date"), row.to_dict()))
    return details
