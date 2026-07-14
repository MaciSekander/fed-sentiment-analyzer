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

# Pre-1994 FOMC minutes don't use modern phrasing ("target range",
# "restrictive stance") at all -- see the module docstring in
# src/analysis/history.py for how this repo surfaces that as a documented
# limitation rather than silently mis-scoring. This classic-era list was
# derived by grepping the actual 1967-1993 minutes archive in this repo for
# recurring, unambiguous language rather than guessed from general
# knowledge of the era. Two things stood out:
#
# 1. The era's boilerplate "somewhat greater/lesser reserve restraint"
#    asymmetric-directive language almost always appears as a same-sentence
#    contingency ("greater restraint IF X, lesser restraint IF Y"), so
#    counting both sides just cancels out -- deliberately excluded here,
#    it isn't a useful signal despite being common.
# 2. Sentences reporting an actual discount-rate change use a small,
#    consistent set of phrasings across decades (Martin through Greenspan)
#    and are an unambiguous, discrete policy action -- this list targets
#    those specifically. Most meetings didn't announce a rate change, so
#    most classic-era documents will still legitimately score neutral (no
#    hits) -- that's an honest "no action this meeting", not a gap.
CLASSIC_ERA_CUTOFF = "1994-01-01"

CLASSIC_HAWKISH_PHRASES: dict[str, float] = {
    "discount rates were increased": 2.0,
    "discount rates were raised": 2.0,
    "discount rate was increased": 2.0,
    "increase in the discount rate": 1.8,
    "increase in Federal Reserve discount rates": 1.8,
    "increases in Federal Reserve discount rates": 1.8,
}

CLASSIC_DOVISH_PHRASES: dict[str, float] = {
    "discount rates were reduced": 2.0,
    "discount rate was reduced": 2.0,
    "reduction in the discount rate": 1.8,
    "reduction in Federal Reserve discount rates": 1.8,
    "reductions in Federal Reserve discount rates": 1.8,
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
_CLASSIC_HAWKISH_COMPILED = _compile(CLASSIC_HAWKISH_PHRASES)
_CLASSIC_DOVISH_COMPILED = _compile(CLASSIC_DOVISH_PHRASES)


def _count_hits(text: str, compiled: list[tuple[re.Pattern, float]]) -> tuple[dict[str, int], float]:
    hits: dict[str, int] = {}
    weighted = 0.0
    for pattern, weight in compiled:
        count = len(pattern.findall(text))
        if count:
            hits[pattern.pattern] = count
            weighted += count * weight
    return hits, weighted


def _score_modern(text: str, word_count: int, threshold: float) -> LexiconResult:
    hawkish_hits, hawkish_weighted = _count_hits(text, _HAWKISH_COMPILED)
    dovish_hits, dovish_weighted = _count_hits(text, _DOVISH_COMPILED)

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

    return _build_result(score, hawkish_hits, dovish_hits, word_count, threshold)


def _score_classic(text: str, word_count: int, threshold: float) -> LexiconResult:
    hawkish_hits, hawkish_weighted = _count_hits(text, _CLASSIC_HAWKISH_COMPILED)
    dovish_hits, dovish_weighted = _count_hits(text, _CLASSIC_DOVISH_COMPILED)

    total = hawkish_weighted + dovish_weighted
    if total == 0:
        score = 0.0
    else:
        # Unlike modern tone-language phrases, a hit here is a discrete,
        # unambiguous action (an announced discount-rate change) -- it
        # isn't diluted by these documents running thousands of words
        # regardless of whether a policy action happened, so this doesn't
        # use the modern scorer's word-count density confidence. Instead,
        # confidence comes from how one-sided the hits are: a document
        # reporting only a hike (the overwhelmingly common case) scores
        # near +-1; one that mentions both (e.g. reviewing prior history)
        # scores more moderately.
        imbalance = abs(hawkish_weighted - dovish_weighted) / total
        score = ((hawkish_weighted - dovish_weighted) / total) * min(0.5 + imbalance, 1.0)

    return _build_result(score, hawkish_hits, dovish_hits, word_count, threshold)


def _build_result(
    score: float, hawkish_hits: dict[str, int], dovish_hits: dict[str, int], word_count: int, threshold: float
) -> LexiconResult:
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


def score_text(text: str, date: str | None = None, threshold: float = DEFAULT_THRESHOLD) -> LexiconResult:
    """Score a document's hawkish/dovish lean using the phrase lexicon.

    `date` (an ISO date string, e.g. from a document's filename) is
    optional and defaults to the modern phrase list -- the live web
    analyzer never has a real document date for arbitrary pasted text, so
    its behavior is unchanged. Pass a pre-1994 date (batch-scoring the
    historical archive, see src/sentiment/pipeline.py) to use the
    classic-era discount-rate-based scorer instead.
    """
    word_count = max(len(text.split()), 1)
    # Normalize whitespace before matching: these documents (especially the
    # pre-1994 archive) are hard-wrapped at a fixed column, so a phrase can
    # land with a newline where a space belongs -- e.g. "target\nrange"
    # instead of "target range" -- which would otherwise silently fail to
    # match even though the phrase is right there in the source text.
    normalized = re.sub(r"\s+", " ", text)
    if date is not None and date < CLASSIC_ERA_CUTOFF:
        return _score_classic(normalized, word_count, threshold)
    return _score_modern(normalized, word_count, threshold)
