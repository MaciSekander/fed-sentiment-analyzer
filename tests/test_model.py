import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from src.sentiment.model import TransformerScorer  # noqa: E402

HAWKISH_EXAMPLE = (
    "Such a directive would imply that any tightening should be implemented "
    "promptly if developments were perceived as pointing to rising inflation."
)
DOVISH_EXAMPLE = (
    "The Committee decided to lower the target range and remain highly "
    "accommodative to support economic activity given downside risks to growth."
)
NEUTRAL_EXAMPLE = "The meeting was held in the offices of the Board of Governors in Washington, D.C."


@pytest.fixture(scope="module")
def scorer():
    try:
        return TransformerScorer()
    except OSError as exc:
        pytest.skip(f"could not download model weights (offline?): {exc}")


def test_hawkish_example_classified_hawkish(scorer):
    result = scorer.score(HAWKISH_EXAMPLE)
    assert result.label == "hawkish"
    assert result.score > 0


def test_dovish_example_classified_dovish(scorer):
    result = scorer.score(DOVISH_EXAMPLE)
    assert result.label == "dovish"
    assert result.score < 0


def test_neutral_example_classified_neutral(scorer):
    result = scorer.score(NEUTRAL_EXAMPLE)
    assert result.label == "neutral"
