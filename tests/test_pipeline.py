from src.sentiment.pipeline import analyze_document

HAWKISH_EXAMPLE = """
The Committee decided to raise interest rates further, citing persistently
high inflation and upside risks to inflation that call for a restrictive
stance of monetary policy.
"""


def test_analyze_document_lexicon_only_matches_lexicon_score():
    # use_model=False avoids requiring transformers/torch in the test env.
    result = analyze_document(HAWKISH_EXAMPLE, doc_id="test-doc", use_model=False)
    assert result.model_score is None
    assert result.model_label is None
    assert result.combined_score == result.lexicon_score
    assert result.combined_label == result.lexicon_label
    assert result.combined_label == "hawkish"


def test_analyze_document_carries_doc_id_and_date():
    result = analyze_document(
        HAWKISH_EXAMPLE, doc_id="2024-03-20-fomc-minutes", date="2024-03-20", use_model=False
    )
    assert result.doc_id == "2024-03-20-fomc-minutes"
    assert result.date == "2024-03-20"
