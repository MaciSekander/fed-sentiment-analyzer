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

Scrape it from federalreserve.gov:

```bash
python -m src.cli scrape-minutes --start 2015-01-01 --end 2024-12-31 --out data/raw/minutes
python -m src.cli scrape-speeches --start 2015-01-01 --end 2024-12-31 --out data/raw/speeches
```

These discover document links dynamically from the Fed's calendar/archive
pages rather than hard-coding every URL, but federalreserve.gov's HTML has
changed layout over the years — if a run comes back empty or truncated,
check `src/scraper/utils.py::extract_main_text` and adjust the CSS
selectors for the page(s) in question.

Or skip scraping entirely: drop your own `.txt` files into
`data/raw/minutes/` or `data/raw/speeches/`. Name them with a date
(`YYYY-MM-DD-whatever.txt`) so the pipeline can plot them on a timeline.

### 2. Score documents

```bash
python -m src.cli analyze --input-dir data/raw/minutes --out data/processed/minutes_scores.csv
# lexicon-only, no transformers/torch dependency:
python -m src.cli analyze --input-dir data/raw/minutes --out data/processed/minutes_scores.csv --no-model
```

### 3. Plot the trend

```bash
python -m src.cli trend --input data/processed/minutes_scores.csv --plot data/processed/minutes_trend.png
```

## Project layout

```
src/
  scraper/       # fomc_minutes.py, fed_speeches.py, utils.py
  sentiment/     # lexicon.py (baseline), model.py (transformer), pipeline.py (combines both)
  analysis/      # trends.py (rolling average + plotting)
  cli.py         # scrape-minutes / scrape-speeches / analyze / trend
tests/           # pytest suite for the lexicon and pipeline
data/raw/        # scraped or manually-added source text (gitignored)
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
