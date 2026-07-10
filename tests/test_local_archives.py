import zipfile

from src.ingestion.local_archives import ingest_csv_archive, ingest_per_file_zip


def test_ingest_per_file_zip_extracts_dated_files(tmp_path):
    zip_path = tmp_path / "minutes.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("txt/19670620.txt", "Minutes of the meeting held June 20, 1967.")
        zf.writestr("txt/20080318.txt", "Minutes of the meeting held March 18, 2008.")
        zf.writestr("txt/README.md", "not a dated document")

    out_dir = tmp_path / "out"
    saved = ingest_per_file_zip(zip_path, out_dir, "fomc-minutes")

    names = sorted(p.name for p in saved)
    assert names == ["1967-06-20-fomc-minutes.txt", "2008-03-18-fomc-minutes.txt"]
    assert "1967" in (out_dir / "1967-06-20-fomc-minutes.txt").read_text()


def test_ingest_csv_archive_groups_by_date_and_filters_type(tmp_path):
    csv_content = (
        "Unnamed: 0,Date,Type,Text\n"
        "0,20230412,0,Release announcement blurb not meeting content\n"
        "1,20230322,1,First paragraph of the minutes.\n"
        "2,20230322,1,Second paragraph of the minutes.\n"
    )
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Fed_Scrape.csv", csv_content)

    out_dir = tmp_path / "out"
    saved = ingest_csv_archive(zip_path, out_dir)

    assert len(saved) == 1
    assert saved[0].name == "2023-03-22-fomc-minutes.txt"
    text = saved[0].read_text()
    assert "First paragraph" in text
    assert "Second paragraph" in text
    assert "Release announcement" not in text
