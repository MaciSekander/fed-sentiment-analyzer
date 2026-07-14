from __future__ import annotations

import logging
import os

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


def _low_memory_host(threshold_mb: int = 1024) -> bool:
    """Best-effort check for constrained hosts (e.g. a free tier capped
    around 512MB) where loading the ~1.4GB RoBERTa-large model wouldn't
    raise a catchable error -- it would get the whole process OOM-killed,
    which resets these module-level globals on restart and retries (and
    fails) the load again on the next request, forever. Reads
    /proc/meminfo (Linux containers only -- this is exactly the kind of
    host this guards against; harmlessly returns False everywhere else,
    e.g. local macOS dev or a host with plenty of RAM) so low-RAM hosts
    are safe automatically, without depending on DISABLE_MODEL having
    been set correctly on every deploy target.
    """
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) < threshold_mb * 1024
    except (OSError, ValueError, IndexError):
        pass
    return False


def _get_scorer():
    """Lazily load the transformer once per process, remembering failure
    reason so /api/health can report it instead of retrying every request.
    """
    global _scorer, _scorer_load_error
    if _scorer is not None or _scorer_load_error is not None:
        return _scorer

    if os.environ.get("DISABLE_MODEL"):
        # Set on low-RAM deploy targets (e.g. free tiers capped around
        # 512MB) where the RoBERTa-large weights won't fit -- skips the
        # torch/transformers import entirely rather than attempting a load
        # that would get OOM-killed. /api/health and /api/analyze both
        # already treat a load failure as "fall back to lexicon-only".
        _scorer_load_error = "model disabled via DISABLE_MODEL env var"
        return None

    if _low_memory_host():
        _scorer_load_error = "model disabled automatically: host has less RAM than the model needs"
        return None

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
