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
2. **Transformer model** (`src/sentiment/model.py`) — wraps a HuggingFace
   `transformers` sequence-classification model. Defaults to
   `yiyanghkust/finbert-tone` (general financial tone: positive / negative
   / neutral), used as a rough proxy for hawkish/dovish. If you have
   access to a model fine-tuned specifically for FOMC hawkish/dovish/
   neutral classification, point `--model-name` at it instead — the
   wrapper reads the model's own label mapping and maps any label
   containing "hawk"/"dov" directly, no code changes needed.

`src/sentiment/pipeline.py` combines the two into a single `combined_score`
in `[-1, 1]` (positive = hawkish, negative = dovish) and a 3-way label. The
model is optional — everything works with `--no-model` using the lexicon
alone if you don't want the `transformers`/`torch` dependency.

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

## Project layout

```
src/
  ingestion/     # local_archives.py -- reassembles data/archives/*.zip into per-date .txt
  scraper/       # fomc_minutes.py, fed_speeches.py, utils.py
  sentiment/     # lexicon.py (baseline), model.py (transformer), pipeline.py (combines both)
  analysis/      # trends.py (rolling average + plotting, with gap-aware line breaks)
  cli.py         # ingest-local / scrape-minutes / scrape-speeches / analyze / trend
tests/           # pytest suite for the lexicon and pipeline
data/archives/   # pre-collected source zips (committed -- this is the primary data source)
data/raw/        # ingested/scraped/manually-added per-document .txt (gitignored, regenerable)
data/processed/  # scored CSVs and trend plots (gitignored)
```

## Testing

```bash
pytest tests/
```

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
- The default transformer model (`finbert-tone`) reports general
  positive/negative tone, which is only a proxy for hawkish/dovish stance.
  For real accuracy here, the natural next step is fine-tuning (or finding
  a pretrained model already fine-tuned) on a labeled hawkish/dovish/
  neutral FOMC sentence dataset — academic work on FOMC communication
  analysis has produced such datasets/models; swap the model name into
  `--model-name` once you've identified and validated one.
- The scraper is best-effort against a real, evolving government website;
  treat scrape failures as "check the selectors," not "the tool is
  broken."
