"""Combine the lexicon baseline and (optional) transformer model into a
single hawkish/dovish score per document, and run that over a corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

from src.scraper.utils import extract_date_from_filename
from src.sentiment.lexicon import score_text as lexicon_score_text

DEFAULT_MODEL_WEIGHT = 0.8  # 0 = lexicon only, 1 = model only


@dataclass
class DocumentScore:
    doc_id: str
    date: str | None
    lexicon_score: float
    lexicon_label: str
    model_score: float | None
    model_label: str | None
    combined_score: float
    combined_label: str
    word_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def label_from_score(score: float, threshold: float = 0.15) -> str:
    if score > threshold:
        return "hawkish"
    if score < -threshold:
        return "dovish"
    return "neutral"


def analyze_document(
    text: str,
    doc_id: str,
    date: str | None = None,
    use_model: bool = True,
    model_name: str | None = None,
    model_weight: float = DEFAULT_MODEL_WEIGHT,
) -> DocumentScore:
    lex = lexicon_score_text(text)

    model_score = None
    model_label = None
    if use_model:
        try:
            from src.sentiment.model import get_scorer, DEFAULT_MODEL_NAME

            scorer = get_scorer(model_name or DEFAULT_MODEL_NAME)
            result = scorer.score_document(text)
            model_score = result.score
            model_label = result.label
        except ImportError:
            # transformers/torch not installed -- silently fall back to lexicon-only.
            pass

    if model_score is None:
        combined_score = lex.score
    else:
        combined_score = (1 - model_weight) * lex.score + model_weight * model_score

    return DocumentScore(
        doc_id=doc_id,
        date=date,
        lexicon_score=lex.score,
        lexicon_label=lex.label,
        model_score=model_score,
        model_label=model_label,
        combined_score=round(combined_score, 4),
        combined_label=label_from_score(combined_score),
        word_count=lex.word_count,
    )


def analyze_corpus(
    input_dir: Path,
    use_model: bool = True,
    model_name: str | None = None,
    model_weight: float = DEFAULT_MODEL_WEIGHT,
) -> list[DocumentScore]:
    results = []
    for path in sorted(Path(input_dir).glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        doc_id = path.stem
        date = extract_date_from_filename(path.name)
        results.append(
            analyze_document(
                text,
                doc_id=doc_id,
                date=date,
                use_model=use_model,
                model_name=model_name,
                model_weight=model_weight,
            )
        )
    return results
