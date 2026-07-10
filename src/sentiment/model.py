"""Transformer-based hawkish/dovish/neutral classifier.

Wraps a HuggingFace `transformers` sequence-classification model. Two
kinds of models work here:

1. A model fine-tuned specifically to classify hawkish/dovish/neutral
   monetary-policy stance (several exist on the HuggingFace Hub from
   academic work on FOMC communication analysis, e.g. RoBERTa variants
   trained on labeled FOMC sentences). Point `model_name` at one of
   those and this wrapper will read its label mapping directly.

2. A general financial-tone/sentiment model such as
   "yiyanghkust/finbert-tone" (Positive/Negative/Neutral). This is only
   a rough proxy for hawkish/dovish -- positive economic tone doesn't
   always mean hawkish -- so treat model_source="finbert-tone" results
   as a secondary signal, not ground truth. Combine with the lexicon
   score in pipeline.py for a more reliable read.

`transformers`/`torch` are optional dependencies: importing this module
without them installed raises a clear ImportError only when you actually
try to load a model, so the rest of the package still works.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

DEFAULT_MODEL_NAME = "yiyanghkust/finbert-tone"

# Best-effort mapping from a model's own label strings to our 3-way scale.
# Checked case-insensitively against substrings, in order.
_LABEL_HEURISTICS: list[tuple[str, str]] = [
    ("hawk", "hawkish"),
    ("dov", "dovish"),
    ("positive", "hawkish"),   # finbert-tone proxy -- see module docstring
    ("negative", "dovish"),    # finbert-tone proxy -- see module docstring
    ("neutral", "neutral"),
]


@dataclass
class ModelResult:
    label: str  # "hawkish" | "dovish" | "neutral"
    score: float  # confidence in [-1, 1], positive=hawkish, negative=dovish
    raw_label: str
    raw_score: float


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
        self.id2label = self.model.config.id2label

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
        raw_label = self.id2label[top_idx]
        raw_score = float(probs[top_idx].item())
        mapped_label = _map_label(raw_label)

        # Build a signed score: hawkish probability minus dovish probability
        # (falling back to +/-confidence of the single top label if the
        # model doesn't expose separate hawkish/dovish classes).
        hawkish_p = 0.0
        dovish_p = 0.0
        for idx, label in self.id2label.items():
            mapped = _map_label(label)
            p = float(probs[int(idx)].item())
            if mapped == "hawkish":
                hawkish_p += p
            elif mapped == "dovish":
                dovish_p += p

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


@lru_cache(maxsize=4)
def get_scorer(model_name: str = DEFAULT_MODEL_NAME) -> TransformerScorer:
    """Cache scorers by model name so the CLI doesn't reload weights per document."""
    return TransformerScorer(model_name=model_name)
