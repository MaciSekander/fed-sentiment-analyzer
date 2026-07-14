from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.routers import analyze, history

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
app.include_router(history.router)

# In production (the Docker image built for deployment), the frontend is
# pre-built to frontend/dist and served by this same process. In local dev,
# that directory doesn't exist -- you run `npm run dev` separately instead,
# proxying /api/* to this backend (see frontend/vite.config.ts) -- so this
# mount is skipped and "/" just isn't served by FastAPI at all.
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "fed-sentiment-analyzer", "docs": "/docs", "frontend": "run `npm run dev` in frontend/"}
