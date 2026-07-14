from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from backend.app.schemas import HistoryResponse

router = APIRouter(prefix="/api", tags=["history"])

_history_cache: HistoryResponse | None = None
_HISTORY_PATH = Path(__file__).resolve().parent.parent / "static" / "history.json"


def _load_history() -> HistoryResponse:
    """Lazily load and cache the precomputed history payload once per process
    (same lazy-singleton pattern as analyze.py's _get_scorer). No pandas or
    model work happens here -- that all ran offline when history.json was
    generated (see src/cli.py's `history` subcommand) -- this is just a
    cached JSON parse, cheap enough for the low-RAM free-tier deploy.
    """
    global _history_cache
    if _history_cache is None:
        _history_cache = HistoryResponse.model_validate_json(_HISTORY_PATH.read_text())
    return _history_cache


@router.get("/history", response_model=HistoryResponse)
def history() -> HistoryResponse:
    return _load_history()
