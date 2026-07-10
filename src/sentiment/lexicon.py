"""Lexicon-based hawkish/dovish scoring.

A transparent, no-training-data-required baseline: count weighted
occurrences of phrases associated with a "hawkish" (favoring tighter
policy / higher rates to fight inflation) versus "dovish" (favoring
looser policy / lower rates to support growth) stance, normalized by
document length.

This is deliberately simple and explainable. It won't catch nuance,
double negatives, or forward-guidance subtleties as well as a
fine-tuned model would -- see src/sentiment/model.py and
src/sentiment/pipeline.py for combining it with a transformer score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Weight reflects roughly how strongly a phrase signals a directional stance.
# Longer, more specific phrases are weighted higher than single words to
# reduce false positives (e.g. "rate" alone is too generic to score).
HAWKISH_PHRASES: dict[str, float] = {
    "raise the target range": 2.0,
    "raising the target range": 2.0,
    "increase in the target range": 2.0,
    "further tightening": 2.0,
    "additional policy firming": 2.0,
    "restrictive stance": 1.5,
    "restrictive monetary policy": 1.5,
    "elevated inflation": 1.2,
    "persistently high inflation": 1.8,
    "inflation risks": 1.2,
    "inflation remains too high": 1.8,
    "overheating": 1.5,
    "tighten monetary policy": 1.8,
    "tighter financial conditions": 1.2,
    "upside risks to inflation": 1.6,
    "combat inflation": 1.8,
    "reduce the size of the balance sheet": 1.3,
    "quantitative tightening": 1.5,
    "strong labor market": 0.8,
    "wage pressures": 1.0,
    "raise interest rates": 1.8,
    "higher for longer": 1.6,
}

DOVISH_PHRASES: dict[str, float] = {
    "lower the target range": 2.0,
    "lowering the target range": 2.0,
    "decrease in the target range": 2.0,
    "accommodative stance": 1.8,
    "accommodative monetary policy": 1.8,
    "highly accommodative": 2.0,
    "downside risks": 1.4,
    "downside risks to growth": 1.8,
    "downside risks to employment": 1.8,
    "support the economy": 1.4,
    "support economic activity": 1.4,
    "patient approach": 1.2,
    "remain patient": 1.2,
    "ample support": 1.3,
    "quantitative easing": 1.6,
    "expand the balance sheet": 1.4,
    "lower interest rates": 1.8,
    "cut interest rates": 1.8,
    "rate cut": 1.6,
    "weakness in the labor market": 1.4,
    "softening labor market": 1.4,
    "below the committee's objective": 1.2,
    "economic slack": 1.2,
}

HAWKISH_LABEL = "hawkish"
DOVISH_LABEL = "dovish"
NEUTRAL_LABEL = "neutral"

# Score above this -> hawkish, below its negative -> dovish, else neutral.
DEFAULT_THRESHOLD = 0.15


@dataclass
class LexiconResult:
    score: float  # in [-1, 1]; positive = hawkish, negative = dovish
    label: str
    hawkish_hits: dict[str, int]
    dovish_hits: dict[str, int]
    word_count: int


def _compile(phrases: dict[str, float]) -> list[tuple[re.Pattern, float]]:
    compiled = []
    for phrase, weight in phrases.items():
        pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
        compiled.append((pattern, weight))
    return compiled


_HAWKISH_COMPILED = _compile(HAWKISH_PHRASES)
_DOVISH_COMPILED = _compile(DOVISH_PHRASES)


def score_text(text: str, threshold: float = DEFAULT_THRESHOLD) -> LexiconResult:
    """Score a document's hawkish/dovish lean using the phrase lexicon."""
    word_count = max(len(text.split()), 1)

    hawkish_hits: dict[str, int] = {}
    hawkish_weighted = 0.0
    for pattern, weight in _HAWKISH_COMPILED:
        count = len(pattern.findall(text))
        if count:
            hawkish_hits[pattern.pattern] = count
            hawkish_weighted += count * weight

    dovish_hits: dict[str, int] = {}
    dovish_weighted = 0.0
    for pattern, weight in _DOVISH_COMPILED:
        count = len(pattern.findall(text))
        if count:
            dovish_hits[pattern.pattern] = count
            dovish_weighted += count * weight

    total = hawkish_weighted + dovish_weighted
    if total == 0:
        score = 0.0
    else:
        score = (hawkish_weighted - dovish_weighted) / total

    # Scale down documents with very few hits so a single stray phrase in a
    # long, otherwise-neutral document doesn't swing to +-1.
    density = total / (word_count / 100)  # weighted hits per 100 words
    confidence = min(density / 2.0, 1.0)
    score *= confidence

    if score > threshold:
        label = HAWKISH_LABEL
    elif score < -threshold:
        label = DOVISH_LABEL
    else:
        label = NEUTRAL_LABEL

    return LexiconResult(
        score=round(score, 4),
        label=label,
        hawkish_hits=hawkish_hits,
        dovish_hits=dovish_hits,
        word_count=word_count,
    )
