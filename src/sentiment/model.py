"""Transformer-based hawkish/dovish/neutral classifier.

Default model: "tim9510019/FOMC-RoBERTa", a public mirror of
gtfintechlab/FOMC-RoBERTa -- a RoBERTa-large model fine-tuned specifically
to classify hawkish/dovish/neutral monetary-policy stance in FOMC
communication (from academic work on FOMC sentence-level stance
classification). The original gtfintechlab checkpoint is access-gated on
HuggingFace (requires a logged-in, approved account); this mirror has the
identical weights/config but is publicly downloadable, so the tool works
out of the box with no HF token.

Its config ships with generic labels (LABEL_0/1/2, since the mirror
dropped the original's label names), so this module hard-codes the
correct mapping for that model rather than guessing. That mapping was
verified empirically against the model card's own example sentences plus
several hand-written hawkish/dovish/neutral test sentences (see
tests/test_model.py) -- LABEL_0=dovish, LABEL_1=hawkish, LABEL_2=neutral.

Any other model can be used via `model_name`: if it exposes label
strings containing "hawk"/"dov"/"neutral" they're read directly; general
sentiment models (e.g. "yiyanghkust/finbert-tone", Positive/Negative/
Neutral) fall back to a positive->hawkish/negative->dovish heuristic --
but that's only a rough proxy (general financial tone isn't the same as
policy stance) so prefer the default model unless you have a reason not
to.

`transformers`/`torch` are optional dependencies: importing this module
without them installed raises a clear ImportError only when you actually
try to load a model, so the rest of the package still works.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

# Naive sentence splitter: break on ./!/? followed by whitespace and a
# capital letter or opening quote. Good enough for FOMC-style prose;
# doesn't need a full NLP sentence tokenizer dependency for this.
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z"“])')

DEFAULT_MODEL_NAME = "tim9510019/FOMC-RoBERTa"

# Hard-coded label mappings for models whose config.json doesn't expose
# meaningful label strings (e.g. LABEL_0/1/2). Keyed by model name;
# values are {label_index: "hawkish" | "dovish" | "neutral"}.
_KNOWN_LABEL_MAPS: dict[str, dict[int, str]] = {
    "tim9510019/FOMC-RoBERTa": {0: "dovish", 1: "hawkish", 2: "neutral"},
    "gtfintechlab/FOMC-RoBERTa": {0: "dovish", 1: "hawkish", 2: "neutral"},
}

# Best-effort mapping from a model's own label strings to our 3-way scale,
# used when the model isn't in _KNOWN_LABEL_MAPS above. Checked
# case-insensitively against substrings, in order.
_LABEL_HEURISTICS: list[tuple[str, str]] = [
    ("hawk", "hawkish"),
    ("dov", "dovish"),
    ("positive", "hawkish"),   # general-sentiment-model proxy -- see module docstring
    ("negative", "dovish"),    # general-sentiment-model proxy -- see module docstring
    ("neutral", "neutral"),
]


@dataclass
class ModelResult:
    label: str  # "hawkish" | "dovish" | "neutral"
    score: float  # confidence in [-1, 1], positive=hawkish, negative=dovish
    raw_label: str
    raw_score: float
    sentence: str | None = None  # populated when produced via score_document()


@dataclass
class DocumentModelResult:
    """Aggregate of per-sentence ModelResults for a longer piece of text."""

    label: str
    score: float  # mean signed score across sentences, [-1, 1]
    hawkish_count: int
    dovish_count: int
    neutral_count: int
    sentences: list[ModelResult] = field(default_factory=list)


def split_sentences(text: str) -> list[str]:
    text = " ".join(text.split())  # collapse whitespace/newlines
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _map_label(raw_label: str) -> str:
    lowered = raw_label.lower()
    for needle, mapped in _LABEL_HEURISTICS:
        if needle in lowered:
            return mapped
    return "neutral"


class TransformerScorer:
    """Loads a HF sequence-classification model once and scores text with it.

    Raises ImportError at construction time if transformers/torch aren't
    installed -- callers should catch this and fall back to the lexicon
    scorer (see pipeline.py) if they want the tool to work without these
    heavier dependencies.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, device: str = "cpu"):
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "transformers/torch are required for TransformerScorer. "
                "Install them (see requirements.txt) or use the lexicon-only "
                "path in src/sentiment/pipeline.py."
            ) from exc

        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(device)
        self.device = device
        self.model.eval()

        known_map = _KNOWN_LABEL_MAPS.get(model_name)
        if known_map is not None:
            self._label_map = known_map
            self.id2label = {idx: known_map[idx] for idx in known_map}
        else:
            raw_id2label = self.model.config.id2label
            self.id2label = raw_id2label
            self._label_map = {int(idx): _map_label(label) for idx, label in raw_id2label.items()}

    def score(self, text: str, max_length: int = 512) -> ModelResult:
        import torch

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=max_length,
        ).to(self.device)

        with torch.no_grad():
            logits = self.model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0]

        top_idx = int(torch.argmax(probs).item())
        raw_label = str(self.id2label[top_idx])
        raw_score = float(probs[top_idx].item())
        mapped_label = self._label_map[top_idx]

        hawkish_p = sum(float(probs[idx].item()) for idx, lab in self._label_map.items() if lab == "hawkish")
        dovish_p = sum(float(probs[idx].item()) for idx, lab in self._label_map.items() if lab == "dovish")

        if hawkish_p or dovish_p:
            signed_score = hawkish_p - dovish_p
        else:
            signed_score = raw_score if mapped_label == "hawkish" else -raw_score if mapped_label == "dovish" else 0.0

        return ModelResult(
            label=mapped_label,
            score=round(signed_score, 4),
            raw_label=raw_label,
            raw_score=round(raw_score, 4),
        )

    def score_document(self, text: str, threshold: float = 0.15, max_sentences: int = 150) -> DocumentModelResult:
        """Score arbitrary-length text by classifying it sentence-by-sentence
        and aggregating -- this model was trained on individual sentences,
        so a single `score()` call on a long document truncates to its
        first ~512 tokens and effectively ignores the rest. For a single
        short sentence (the common case for this repo's live analyzer),
        this reduces to one `score()` call.

        `max_sentences` bounds runtime on very long documents (a full FOMC
        minutes can run 200+ sentences, and this model runs one forward
        pass per sentence on CPU) by evenly sampling across the document
        rather than just taking the first N, so the aggregate score still
        reflects the whole document's arc, not just its opening.
        """
        sentences = split_sentences(text)
        if not sentences:
            sentences = [text.strip()] if text.strip() else []
        if not sentences:
            return DocumentModelResult(label="neutral", score=0.0, hawkish_count=0, dovish_count=0, neutral_count=0)

        if len(sentences) > max_sentences:
            step = len(sentences) / max_sentences
            sentences = [sentences[int(i * step)] for i in range(max_sentences)]

        results = []
        for s in sentences:
            r = self.score(s)
            r.sentence = s
            results.append(r)
        mean_score = sum(r.score for r in results) / len(results)
        hawkish_count = sum(1 for r in results if r.label == "hawkish")
        dovish_count = sum(1 for r in results if r.label == "dovish")
        neutral_count = sum(1 for r in results if r.label == "neutral")

        if mean_score > threshold:
            label = "hawkish"
        elif mean_score < -threshold:
            label = "dovish"
        else:
            label = "neutral"

        return DocumentModelResult(
            label=label,
            score=round(mean_score, 4),
            hawkish_count=hawkish_count,
            dovish_count=dovish_count,
            neutral_count=neutral_count,
            sentences=results,
        )


@lru_cache(maxsize=4)
def get_scorer(model_name: str = DEFAULT_MODEL_NAME) -> TransformerScorer:
    """Cache scorers by model name so repeated calls don't reload weights."""
    return TransformerScorer(model_name=model_name)
