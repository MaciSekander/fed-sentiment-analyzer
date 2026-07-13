from __future__ import annotations

import logging

from fastapi import APIRouter

from backend.app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    HealthResponse,
    LexiconResultOut,
    ModelResultOut,
    SentenceResultOut,
)
from src.sentiment.lexicon import score_text
from src.sentiment.pipeline import DEFAULT_MODEL_WEIGHT, label_from_score

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analyze"])

_scorer = None
_scorer_load_error: str | None = None


def _get_scorer():
    """Lazily load the transformer once per process, remembering failure
    reason so /api/health can report it instead of retrying every request.
    """
    global _scorer, _scorer_load_error
    if _scorer is not None or _scorer_load_error is not None:
        return _scorer

    try:
        from src.sentiment.model import DEFAULT_MODEL_NAME, get_scorer

        _scorer = get_scorer(DEFAULT_MODEL_NAME)
    except Exception as exc:  # noqa: BLE001 -- any load failure should degrade to lexicon-only
        _scorer_load_error = str(exc)
        logger.warning("Transformer model failed to load, falling back to lexicon-only: %s", exc)
    return _scorer


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    from src.sentiment.model import DEFAULT_MODEL_NAME

    scorer = _get_scorer()
    return HealthResponse(
        status="ok",
        model_name=DEFAULT_MODEL_NAME,
        model_loaded=scorer is not None,
        model_load_error=_scorer_load_error,
    )


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    lex = score_text(request.text)
    lexicon_out = LexiconResultOut(
        score=lex.score,
        label=lex.label,
        hawkish_hits=lex.hawkish_hits,
        dovish_hits=lex.dovish_hits,
        word_count=lex.word_count,
    )

    model_out: ModelResultOut | None = None
    model_score: float | None = None

    if request.use_model:
        scorer = _get_scorer()
        if scorer is not None:
            doc_result = scorer.score_document(request.text)
            model_score = doc_result.score
            model_out = ModelResultOut(
                model_name=scorer.model_name,
                score=doc_result.score,
                label=doc_result.label,
                hawkish_count=doc_result.hawkish_count,
                dovish_count=doc_result.dovish_count,
                neutral_count=doc_result.neutral_count,
                sentences=[
                    SentenceResultOut(sentence=s.sentence or "", label=s.label, score=s.score)
                    for s in doc_result.sentences
                ],
            )

    if model_score is None:
        combined_score = lex.score
    else:
        combined_score = (1 - DEFAULT_MODEL_WEIGHT) * lex.score + DEFAULT_MODEL_WEIGHT * model_score

    return AnalyzeResponse(
        combined_score=round(combined_score, 4),
        combined_label=label_from_score(combined_score),
        lexicon=lexicon_out,
        model=model_out,
    )
