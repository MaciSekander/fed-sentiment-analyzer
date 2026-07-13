# Fed Sentiment Analyzer

Analyze whether FOMC minutes and Federal Reserve speeches lean **hawkish**
(favoring tighter policy / higher rates to fight inflation) or **dovish**
(favoring looser policy / lower rates to support growth), using historical
reports as the data source, and track how that stance shifts over time.

## How it works

Two scoring signals, combined:

1. **Lexicon baseline** (`src/sentiment/lexicon.py`) — counts weighted
   occurrences of phrases known to signal a hawkish or dovish stance (e.g.
   "raise the target range", "restrictive stance" vs. "accommodative
   stance", "downside risks"), normalized by document length. No training
   data or network access required; fully transparent — you can see
   exactly which phrases drove a score.
2. **Transformer model** (`src/sentiment/model.py`) — defaults to
   [`tim9510019/FOMC-RoBERTa`](https://huggingface.co/tim9510019/FOMC-RoBERTa),
   a public mirror of `gtfintechlab/FOMC-RoBERTa`: a RoBERTa-large model
   fine-tuned specifically to classify hawkish/dovish/neutral stance in
   FOMC communication (the original gtfintechlab checkpoint is
   access-gated on HuggingFace; this mirror has identical weights and is
   freely downloadable). Its label mapping (`LABEL_0`=dovish,
   `LABEL_1`=hawkish, `LABEL_2`=neutral) is hard-coded in `model.py` after
   verifying it empirically against known example sentences —
   `tests/test_model.py` checks it.

   This model classifies one **sentence** at a time (that's what it was
   trained on), so `score_document()` splits longer text into sentences,
   scores each, and aggregates — a single truncated 512-token call on a
   multi-paragraph document would silently ignore everything past the
   first ~400 words.

   You can point `--model-name` / the `HF_MODEL_NAME` env var at a
   different model. General sentiment models like `yiyanghkust/finbert-tone`
   (positive/negative/neutral) are supported as a fallback via a
   positive→hawkish/negative→dovish heuristic, but that's only a rough
   proxy — general financial tone isn't the same as policy stance (a
   sentence about "persistently high inflation" is hawkish policy
   language but reads as negative-tone to a generic model). Prefer the
   default unless you have a specific reason not to.

`src/sentiment/pipeline.py` combines the lexicon and model scores into a
single `combined_score` in `[-1, 1]` (positive = hawkish, negative =
dovish), weighted 80% model / 20% lexicon by default. The model is
optional — everything works with `--no-model` using the lexicon alone if
you don't want the `transformers`/`torch` dependency.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The `transformers`/`torch` lines in `requirements.txt` are only needed for
the model-based scorer — skip them if you only want the lexicon baseline.

## Usage

### 1. Get historical data

**Option A — ingest the pre-collected archives in `data/archives/` (no
network required):**

```bash
python -m src.cli ingest-local
```

This reassembles per-meeting `.txt` files into `data/raw/minutes/` and
`data/raw/statements/` from three source archives:

| Archive | Contents | Coverage |
|---|---|---|
| `data/archives/fomc_minutes_1967_2008.zip` | Full FOMC minutes, one file per meeting | 1967–2008 |
| `data/archives/fomc_statements_1994_2008.zip` | Short post-meeting policy statements | 1994–2008 |
| `data/archives/fed_scrape_2015_2023.zip` | CSV of minutes paragraphs (reassembled per meeting; release-announcement blurbs are filtered out) | 2015–2023 |

Note there's a **2009–2014 gap** — no archive here covers it. `trend`
plots break the line across gaps wider than ~6 months rather than drawing
a misleading straight line through missing data. Fill the gap with
Option B if you need it.

**Option B — scrape it live from federalreserve.gov** (requires outbound
network access to federalreserve.gov):

```bash
python -m src.cli scrape-minutes --start 2009-01-01 --end 2014-12-31 --out data/raw/minutes
python -m src.cli scrape-speeches --start 2015-01-01 --end 2024-12-31 --out data/raw/speeches
```

These discover document links dynamically from the Fed's calendar/archive
pages rather than hard-coding every URL. If every fetch fails, the
scraper now prints an explicit `[error]` explaining it couldn't reach
federalreserve.gov at all (network/proxy issue) versus reaching it but
finding no matching links (site layout changed) — check
`src/scraper/utils.py::extract_main_text` and the link regexes in
`src/scraper/fomc_minutes.py` / `fed_speeches.py` in the latter case.

Or skip both: drop your own `.txt` files into `data/raw/minutes/`,
`data/raw/speeches/`, or `data/raw/statements/`. Name them with a date
(`YYYY-MM-DD-whatever.txt`) so the pipeline can plot them on a timeline.

### 2. Score documents

```bash
python -m src.cli analyze --input-dir data/raw/minutes --out data/processed/minutes_scores.csv
# lexicon-only, no transformers/torch dependency:
python -m src.cli analyze --input-dir data/raw/minutes --out data/processed/minutes_scores.csv --no-model
```

Running the lexicon baseline over the full 1967–2023 minutes archive
(`--no-model`) produces a plausible real signal: mostly flat/neutral
before the mid-1990s (see limitations below), a sharp dovish trough
during the 2007–2008 financial crisis, and a clear hawkish turn starting
March 2022 that tracks the actual 2022 rate-hiking cycle.

### 3. Plot the trend

```bash
python -m src.cli trend --input data/processed/minutes_scores.csv --plot data/processed/minutes_trend.png
```

## Website (live text analyzer)

A FastAPI backend + React frontend for pasting arbitrary text (a speech
excerpt, a statement, a minutes paragraph) and getting a live hawkish/
dovish/neutral classification, with the lexicon phrase matches and the
per-sentence model breakdown both shown so you can see *why* it scored
the way it did.

```bash
# Terminal 1 -- backend (needs the root requirements.txt + backend/requirements.txt)
pip install -r requirements.txt -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 -- frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies `/api/*` to the
backend on port 8000 (see `frontend/vite.config.ts`). The first request
after starting the backend takes a few seconds while it downloads/loads
the model; `GET /api/health` reports whether it loaded successfully
(`model_loaded`) and, if not, why (`model_load_error`) — the UI falls
back to lexicon-only scoring in that case rather than failing outright.

```
backend/
  app/main.py           # FastAPI app + CORS
  app/routers/analyze.py # POST /api/analyze, GET /api/health
  app/schemas.py         # request/response models
frontend/
  src/App.tsx            # textarea + example buttons + results
  src/components/        # ScoreGauge, SentenceBreakdown, LexiconHits
  src/api.ts              # fetch wrappers
```

The backend imports directly from `src/sentiment/*` (same lexicon and
model code the CLI uses) rather than duplicating logic — run it from the
repo root so the `src` package resolves.

### Deployment (HuggingFace Spaces)

`Dockerfile` builds the frontend and backend into a single container
(multi-stage: Node builds `frontend/dist`, then the Python image serves
it plus the API from one FastAPI process on port 7860 — see
`backend/app/main.py`, which mounts the built frontend as static files
when present and falls back to a JSON status page in local dev, where
there is no build). `.github/workflows/deploy-space.yml` pushes that to
a HuggingFace Space automatically on every push to `main`.

One-time setup (I can't create accounts or hold tokens on your behalf —
this part is manual):

1. Create a free account at [huggingface.co](https://huggingface.co) if
   you don't have one.
2. Create a new Space (huggingface.co/new-space): pick any name, **SDK:
   Docker**, any hardware tier (free CPU basic works).
3. Generate an access token with **write** scope: Settings → Access
   Tokens → New token.
4. In this GitHub repo's Settings → Secrets and variables → Actions:
   - Add **secret** `HF_TOKEN` = the token from step 3.
   - Add **variable** `HF_SPACE_ID` = `your-hf-username/your-space-name`
     (from step 2).
5. Push to `main` (or run the workflow manually from the Actions tab) —
   the Action builds a fresh deploy directory (backend + src + frontend
   + Dockerfile + a Space-specific `README.md` with the required HF
   config header) and force-pushes it to the Space's git repo.

Your Space will be live at
`https://huggingface.co/spaces/your-hf-username/your-space-name`. The
first request after a cold start takes 10-30 seconds while the model
loads.

To test the container locally before relying on the Action (requires
Docker):

```bash
docker build -t fed-sentiment-analyzer .
docker run -p 7860:7860 fed-sentiment-analyzer
# open http://localhost:7860
```

## Project layout

```
src/
  ingestion/     # local_archives.py -- reassembles data/archives/*.zip into per-date .txt
  scraper/       # fomc_minutes.py, fed_speeches.py, utils.py
  sentiment/     # lexicon.py (baseline), model.py (transformer), pipeline.py (combines both)
  analysis/      # trends.py (rolling average + plotting, with gap-aware line breaks)
  cli.py         # ingest-local / scrape-minutes / scrape-speeches / analyze / trend
backend/         # FastAPI app serving the live analyzer (see Website section)
frontend/        # React + Vite UI for the live analyzer
Dockerfile       # single-container build for deployment (see Deployment section)
deploy/          # space_README.md -- HF Spaces config header, copied in at deploy time
.github/workflows/deploy-space.yml  # auto-deploy to HF Spaces on push to main
tests/           # pytest suite for the lexicon, pipeline, model, and ingestion
data/archives/   # pre-collected source zips (committed -- this is the primary data source)
data/raw/        # ingested/scraped/manually-added per-document .txt (gitignored, regenerable)
data/processed/  # scored CSVs and trend plots (gitignored)
```

## Testing

```bash
pytest tests/
```

`tests/test_model.py` downloads the real transformer model and is
skipped automatically if `transformers`/`torch` aren't installed or the
model can't be reached.

## Limitations / next steps

- The lexicon is a hand-built starting point, not exhaustive — extend
  `HAWKISH_PHRASES`/`DOVISH_PHRASES` in `src/sentiment/lexicon.py` as you
  find gaps.
- **Pre-1994 minutes score as almost entirely neutral.** The lexicon is
  tuned to the Fed's modern communication style (post-Greenspan-era
  phrasing like "target range", "restrictive stance"). 1960s–1980s
  minutes use very different language ("desk was directed to conduct
  operations with a view to..."), so those documents mostly won't match
  either phrase list. If you need signal that far back, expect to add a
  second, era-specific phrase list rather than extending the modern one.
- **2009–2014 has no local archive coverage** — `ingest-local` leaves
  that range empty; scrape it (Option B above) if you need it, or supply
  your own files.
- Very short documents (e.g. emergency intermeeting action minutes, like
  the Jan 2008 75bp cut) can saturate to ±1 off just one or two phrase
  hits — that's the confidence-scaling design working as intended on a
  low word count, not a bug, but treat single-digit-word-count-vs-score
  outliers as lower-confidence than a full multi-thousand-word minutes
  document.
- The transformer classifies **individual sentences** — accuracy on a
  full paragraph depends on aggregating those sentence-level calls
  (`score_document()` does this), and an isolated sentence pulled out of
  its surrounding context can occasionally get misclassified even when
  the model is generally reliable (e.g. a short fragment like "the labor
  market remains historically tight" can read as ambiguous without the
  sentence before/after it). This is a real limitation of sentence-level
  classification, not a bug — it's part of why the combined score blends
  in the lexicon rather than trusting the model alone.
- Scoring a long document sentence-by-sentence is much slower than one
  truncated call, so `score_document()` caps at 150 sentences (evenly
  sampled across the document) to keep batch runs over the full archive
  from taking too long on CPU.
- The scraper is best-effort against a real, evolving government website;
  treat scrape failures as "check the selectors," not "the tool is
  broken."
