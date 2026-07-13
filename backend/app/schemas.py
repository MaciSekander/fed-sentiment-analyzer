from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000)
    use_model: bool = True


class LexiconResultOut(BaseModel):
    score: float
    label: str
    hawkish_hits: dict[str, int]
    dovish_hits: dict[str, int]
    word_count: int


class SentenceResultOut(BaseModel):
    sentence: str
    label: str
    score: float


class ModelResultOut(BaseModel):
    model_name: str
    score: float
    label: str
    hawkish_count: int
    dovish_count: int
    neutral_count: int
    sentences: list[SentenceResultOut]


class AnalyzeResponse(BaseModel):
    combined_score: float
    combined_label: str
    lexicon: LexiconResultOut
    model: ModelResultOut | None


class HealthResponse(BaseModel):
    status: str
    model_name: str
    model_loaded: bool
    model_load_error: str | None = None
