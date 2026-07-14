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

There's a **2009–2014 gap** — no archive here covers it — plus these zips
stop at 2008-03-18, leaving 2008's most consequential meetings (Bear
Stearns, Lehman, TARP, the cut to near-zero) uncovered too. `trend` plots
and the website's History tab break the line across gaps wider than ~6
months rather than drawing a misleading straight line through missing
data. Fill either with Option B.

**Option B — scrape it live from federalreserve.gov** (requires outbound
network access to federalreserve.gov):

```bash
python -m src.cli scrape-minutes --start 2008-04-01 --end 2008-12-31 --out data/raw/minutes
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
Note the scraper only follows `.htm` minutes links — the June 25, 2008
meeting is published on federalreserve.gov as a PDF only, so it's skipped;
that's the one remaining single-meeting gap after running both commands
above (fixing it would mean adding PDF text extraction, which nothing in
this repo does today).

`backend/app/static/history.json` (the website's History tab data, see
below) was built from the full combination of Option A + both Option B
commands above — 533 documents, 1967–2023, continuously covered aside
from that one PDF-only meeting.

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

### 4. Build the website's History tab data (optional)

```bash
python -m src.cli history --input data/processed/minutes_scores.csv --out backend/app/static/history.json
```

Builds the JSON the website's History tab (below) reads from -- the
rolling-average trend plus Fed Chair era labels, gap detection, and the
pre-1994 low-signal caveat, all in one payload. This is a one-time local
precompute, not something the backend recomputes per request: `history.json`
is a small, ordinary committed file (like `data/archives/`), served by
`GET /api/history` with a cached JSON parse and no pandas/model work on the
request path. Re-run it whenever `minutes_scores.csv` changes meaningfully
(e.g. after adding a new archive or extending the date range) or when
`src/analysis/fed_regimes.py`'s chair list needs a new entry.

## Website (live text analyzer + history)

A FastAPI backend + React frontend, two tabs:

- **Analyze** -- paste arbitrary text (a speech excerpt, a statement, a
  minutes paragraph) and get a live hawkish/dovish/neutral classification,
  with the lexicon phrase matches and the per-sentence model breakdown both
  shown so you can see *why* it scored the way it did.
- **History** -- the full 1967-2023 lexicon-scored minutes archive (533
  documents, continuously covered aside from one PDF-only meeting -- see
  "Get historical data" above) as an interactive chart
  (`frontend/src/components/Timeline.tsx`, via Recharts), annotated with
  every Fed Chair's tenure (`src/analysis/fed_regimes.py`) and the
  pre-1994 classic-era low-signal period, plus a plain always-visible
  legend (`RegimeLegend.tsx`) with the same information for anyone not
  hovering the chart. Deliberately scored with the lexicon
  baseline, not the transformer -- scoring all ~480 documents sentence-by-
  sentence on CPU would take a very long time, and the README's own
  "Usage" section above already documents the lexicon-only signal as a
  meaningful, validated result over the full archive on its own.

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
  app/main.py             # FastAPI app + CORS
  app/routers/analyze.py  # POST /api/analyze, GET /api/health
  app/routers/history.py  # GET /api/history (serves app/static/history.json)
  app/schemas.py          # request/response models
  app/static/history.json # precomputed by `src/cli.py history` -- see above
frontend/
  src/App.tsx             # tabs (Analyze / History), textarea + example buttons + results
  src/components/         # ScoreGauge, SentenceBreakdown, LexiconHits, Timeline, RegimeLegend
  src/api.ts              # fetch wrappers
```

`DISABLE_MODEL=1` (set on the Render free-tier deploy, see below) only
affects the Analyze tab's transformer scoring -- `/api/history` is
unaffected either way, since it never loads the model at all.

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

### Alternative: a free host with less RAM (e.g. Render)

HuggingFace Spaces' free `cpu-basic` tier has 16GB RAM, plenty for the
transformer. Some other free hosts (Render's free web-service tier, for
one) cap around 512MB, which the RoBERTa-large model won't fit in
(~1.4GB+ just for the fp32 weights). `backend/app/routers/analyze.py`'s
`_get_scorer()` handles this two ways:

- **Automatically**: it reads `/proc/meminfo` and skips loading the model
  on any host with less than ~1GB RAM, before ever attempting the load --
  this is the important one, since a failed *attempt* on a 512MB host
  doesn't raise a catchable Python error the way a missing dependency
  does, it gets the whole process OOM-killed, which resets the
  in-process "already tried and failed" state on restart and repeats the
  failed load on the next request forever. This needs no configuration
  and works the same on Render, HF Spaces, or anywhere else.
- **Manually**: set the `DISABLE_MODEL` environment variable (to any
  non-empty value) to force the same fallback regardless of host RAM
  (e.g. for testing it locally).

Either way, the fallback is the exact same graceful-degradation path
already used when the model fails to load for any other reason, so the
frontend's "model unavailable" banner and lexicon-only combined score
work unchanged. `/api/history` is unaffected either way, since it never
loads the model.

The same `Dockerfile` works unmodified on Render (or any other
Docker-based host): connect the GitHub repo, environment **Docker**, no
build/start command or env var needed. Render's Docker builder already
reads the `PORT` it injects and this Dockerfile's `CMD` already listens
on `$PORT`, so no port configuration is needed either.

## Project layout

```
src/
  ingestion/     # local_archives.py -- reassembles data/archives/*.zip into per-date .txt
  scraper/       # fomc_minutes.py, fed_speeches.py, utils.py
  sentiment/     # lexicon.py (baseline), model.py (transformer), pipeline.py (combines both)
  analysis/      # trends.py (rolling average + plotting, gap-aware line breaks)
                 # fed_regimes.py (Fed Chair tenure dates)
                 # history.py (builds the /api/history JSON payload)
  cli.py         # ingest-local / scrape-minutes / scrape-speeches / analyze / trend / history
backend/         # FastAPI app serving the live analyzer + history (see Website section)
frontend/        # React + Vite UI -- Analyze and History tabs
Dockerfile       # single-container build for deployment (see Deployment section)
deploy/          # space_README.md -- HF Spaces config header, copied in at deploy time
.github/workflows/deploy-space.yml  # auto-deploy to HF Spaces on push to main
tests/           # pytest suite for the lexicon, pipeline, model, ingestion, and history builder
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
- **Pre-1994 minutes get a sparser signal from a separate classic-era
  lexicon, not the modern one.** The modern phrase list is tuned to the
  Fed's post-Greenspan communication style ("target range", "restrictive
  stance"); 1960s-1980s minutes use very different language ("desk was
  directed to conduct operations with a view to..."), so those documents
  don't match it at all. `src/sentiment/lexicon.py`'s `CLASSIC_HAWKISH_PHRASES`/
  `CLASSIC_DOVISH_PHRASES` (used automatically for any document dated
  before 1994, via `score_text`'s `date` argument) instead key off
  announced discount-rate changes -- validated against this repo's own
  1967-1993 archive by grepping for real recurring phrasing rather than
  guessed. This means most classic-era meetings still legitimately score
  neutral (most meetings didn't change the discount rate), but the ones
  that did line up well with actual history -- e.g. hawkish at the
  October 1979 Volcker shift and the 1980-81 tightening, dovish at the
  August 1982 pivot and the 1984-86 easing cycle. If you need denser
  signal than "was a rate change announced this meeting", that's still a
  real gap -- the boilerplate "somewhat greater/lesser reserve restraint"
  language from that era was investigated and deliberately excluded (see
  the comment above `CLASSIC_ERA_CUTOFF`): it almost always appears as a
  same-meeting contingency for both directions at once, so counting it
  doesn't discriminate hawkish from dovish.
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
