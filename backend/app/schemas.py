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


class HistoryPoint(BaseModel):
    doc_id: str | None
    date: str | None
    combined_score: float | None
    combined_score_rolling: float | None
    combined_label: str | None
    chair: str | None


class FedRegime(BaseModel):
    chair: str
    start: str
    end: str | None


class HistoryAnnotation(BaseModel):
    type: str
    start: str | None
    end: str | None
    label: str


class HistoryResponse(BaseModel):
    points: list[HistoryPoint]
    regimes: list[FedRegime]
    annotations: list[HistoryAnnotation]
    window: int
    generated_at: str
