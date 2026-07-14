import pandas as pd

from src.analysis.documents import build_all_document_details, build_document_detail

HAWKISH_TEXT = "The Committee decided to raise the target range for the federal funds rate."


def test_build_document_detail_shape():
    score_row = {
        "combined_score": 0.9,
        "combined_label": "hawkish",
        "lexicon_score": 1.0,
        "word_count": 12,
    }
    detail = build_document_detail(HAWKISH_TEXT, "2023-03-22-fomc-minutes", "2023-03-22", score_row)
    assert detail["doc_id"] == "2023-03-22-fomc-minutes"
    assert detail["chair"] == "Jerome Powell"
    assert detail["text"] == HAWKISH_TEXT
    assert detail["matches"]
    for m in detail["matches"]:
        matched = " ".join(HAWKISH_TEXT[m["start"] : m["end"]].split())
        assert matched.lower() == m["phrase"].lower()


def test_build_all_document_details_joins_text_and_scores(tmp_path):
    minutes_dir = tmp_path / "minutes"
    minutes_dir.mkdir()
    (minutes_dir / "1980-03-18-fomc-minutes.txt").write_text(
        "An increase in the discount rate was announced this week."
    )
    (minutes_dir / "no-score-for-this-doc.txt").write_text("Unrelated text with no matching scores row.")

    scores_csv = tmp_path / "scores.csv"
    pd.DataFrame(
        [
            {
                "doc_id": "1980-03-18-fomc-minutes",
                "date": "1980-03-18",
                "lexicon_score": 1.0,
                "combined_score": 1.0,
                "combined_label": "hawkish",
                "word_count": 10,
            }
        ]
    ).to_csv(scores_csv, index=False)

    details = build_all_document_details(minutes_dir, scores_csv)
    assert len(details) == 1  # the unscored doc is skipped, not errored on
    assert details[0]["doc_id"] == "1980-03-18-fomc-minutes"
    assert details[0]["chair"] == "Paul Volcker"
    assert any(m["phrase"] == "increase in the discount rate" for m in details[0]["matches"])
