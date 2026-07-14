from src.sentiment.lexicon import find_phrase_spans, score_text

HAWKISH_EXAMPLE = """
Members judged that it would be appropriate to continue raising the target
range for the federal funds rate, noting that inflation remains too high
and that upside risks to inflation warrant a restrictive stance of
monetary policy. Several participants observed that the strong labor
market and persistent wage pressures argued for further tightening.
"""

DOVISH_EXAMPLE = """
Participants agreed that downside risks to growth and a softening labor
market called for an accommodative stance of monetary policy. The
Committee decided to lower the target range for the federal funds rate
and to remain patient, noting that inflation is running below the
Committee's objective and that continued support for economic activity
is warranted.
"""

NEUTRAL_EXAMPLE = """
The Committee discussed recent developments in financial markets and
reviewed the staff's economic projections. Members received a briefing
on payment system operations and discussed the schedule for upcoming
meetings.
"""


def test_hawkish_text_scores_positive():
    result = score_text(HAWKISH_EXAMPLE)
    assert result.score > 0
    assert result.label == "hawkish"
    assert result.hawkish_hits


def test_dovish_text_scores_negative():
    result = score_text(DOVISH_EXAMPLE)
    assert result.score < 0
    assert result.label == "dovish"
    assert result.dovish_hits


def test_neutral_text_scores_near_zero():
    result = score_text(NEUTRAL_EXAMPLE)
    assert result.label == "neutral"
    assert -0.15 <= result.score <= 0.15


CLASSIC_HAWKISH_EXAMPLE = """
On October 6 the Federal Reserve announced an increase in Federal Reserve
discount rates from 10 to 10-1/2 percent, reflecting the Committee's
concern about continued rapid growth of the monetary aggregates.
"""

CLASSIC_DOVISH_EXAMPLE = """
On October 8 the Federal Reserve announced a reduction in the discount
rate from 10 percent to 9-1/2 percent, in light of the slowing pace of
economic activity.
"""

CLASSIC_NO_ACTION_EXAMPLE = """
The Committee reviewed staff projections for output and prices and
discussed the outlook for the balance of the year. No change in reserve
conditions was proposed at this meeting.
"""


def test_classic_era_scores_hawkish_on_discount_rate_increase():
    result = score_text(CLASSIC_HAWKISH_EXAMPLE, date="1979-09-18")
    assert result.score > 0
    assert result.label == "hawkish"
    assert result.hawkish_hits


def test_classic_era_scores_dovish_on_discount_rate_reduction():
    result = score_text(CLASSIC_DOVISH_EXAMPLE, date="1982-11-16")
    assert result.score < 0
    assert result.label == "dovish"
    assert result.dovish_hits


def test_classic_era_neutral_when_no_rate_change_mentioned():
    result = score_text(CLASSIC_NO_ACTION_EXAMPLE, date="1980-01-09")
    assert result.label == "neutral"
    assert result.score == 0.0


def test_date_on_or_after_cutoff_uses_modern_lexicon():
    # The cutoff date itself, and anything after, should use the modern
    # phrase list -- a classic-era phrase shouldn't fire post-cutoff.
    result = score_text(CLASSIC_HAWKISH_EXAMPLE, date="1994-01-01")
    assert not result.hawkish_hits
    assert result.label == "neutral"


def test_find_phrase_spans_offsets_match_original_text():
    spans = find_phrase_spans(HAWKISH_EXAMPLE)
    assert spans
    for span in spans:
        # Compare with whitespace collapsed -- a phrase can legitimately
        # span a hard line-wrap in the source text (see the next test), so
        # the sliced text may contain a newline where the phrase has a
        # plain space.
        matched = " ".join(HAWKISH_EXAMPLE[span.start : span.end].split())
        assert matched.lower() == span.phrase.lower()
        assert span.category == "hawkish"


def test_find_phrase_spans_tolerates_a_hard_line_wrap():
    text = "The Committee decided to raise the target\nrange for the federal funds rate."
    spans = find_phrase_spans(text)
    assert any(s.phrase == "raise the target range" for s in spans)
    match = next(s for s in spans if s.phrase == "raise the target range")
    assert text[match.start : match.end] == "raise the target\nrange"


def test_find_phrase_spans_merges_overlapping_matches():
    text = "The Committee cited downside risks to growth in several regions."
    spans = find_phrase_spans(text)
    # "downside risks" is a prefix of "downside risks to growth" -- only
    # the longer match should survive, not both.
    matching = [s for s in spans if "downside risks" in s.phrase]
    assert len(matching) == 1
    assert matching[0].phrase == "downside risks to growth"


def test_find_phrase_spans_uses_classic_lexicon_before_cutoff():
    text = "An increase in the discount rate was announced this week."
    spans = find_phrase_spans(text, date="1979-09-18")
    assert any(s.phrase == "increase in the discount rate" for s in spans)
