from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import analyze

app = FastAPI(
    title="Fed Sentiment Analyzer API",
    description="Classifies text as hawkish, dovish, or neutral using a FOMC-specific transformer plus a lexicon baseline.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "fed-sentiment-analyzer", "docs": "/docs"}
