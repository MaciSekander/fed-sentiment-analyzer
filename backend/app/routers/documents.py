from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.app.schemas import DocumentDetailResponse

router = APIRouter(prefix="/api", tags=["documents"])

_DOC_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_DOCUMENTS_DIR = Path(__file__).resolve().parent.parent / "static" / "documents"

# Lazily grows as documents are actually requested -- never a bulk load of
# the whole (~15-20MB) corpus, unlike history.json's single-file cache.
_document_cache: dict[str, DocumentDetailResponse] = {}


@router.get("/documents/{doc_id}", response_model=DocumentDetailResponse)
def get_document(doc_id: str) -> DocumentDetailResponse:
    # Validate before ever touching the filesystem -- doc_id comes straight
    # from the URL path, so without this a value like "../../etc/passwd"
    # could otherwise escape _DOCUMENTS_DIR.
    if not _DOC_ID_RE.match(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")

    if doc_id not in _document_cache:
        path = _DOCUMENTS_DIR / f"{doc_id}.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Document not found")
        _document_cache[doc_id] = DocumentDetailResponse.model_validate_json(path.read_text())

    return _document_cache[doc_id]
