from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from backend.app.schemas import FedFundsResponse

router = APIRouter(prefix="/api", tags=["fedfunds"])

_fedfunds_cache: FedFundsResponse | None = None
_FEDFUNDS_PATH = Path(__file__).resolve().parent.parent / "static" / "fedfunds.json"


def _load_fedfunds() -> FedFundsResponse:
    """Lazily load and cache the precomputed Fed funds rate payload (same
    lazy-singleton pattern as history.py's _load_history) -- fetched once,
    offline, from FRED (see src/cli.py's `fetch-fedfunds` subcommand), not
    on the request path.
    """
    global _fedfunds_cache
    if _fedfunds_cache is None:
        _fedfunds_cache = FedFundsResponse.model_validate_json(_FEDFUNDS_PATH.read_text())
    return _fedfunds_cache


@router.get("/fedfunds", response_model=FedFundsResponse)
def fedfunds() -> FedFundsResponse:
    return _load_fedfunds()
