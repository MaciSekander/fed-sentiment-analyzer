from src.sentiment.lexicon import score_text

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
