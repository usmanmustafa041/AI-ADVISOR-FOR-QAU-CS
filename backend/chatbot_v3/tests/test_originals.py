import sqlite3

import pytest
from chatbot_v3.ingest import source_metadata
from chatbot_v3.parsing import course_rows, parse
from chatbot_v3.settings import ROOT


@pytest.mark.parametrize("batch", [2023, 2025])
def test_actual_parallel_scheme_columns_preserve_codes_and_semesters(batch):
    archive = ROOT / "academic-data/crawl-archive"
    if not (archive / "catalogue.sqlite3").exists():
        pytest.skip("Archived university originals not present")
    with sqlite3.connect(f"file:{archive / 'catalogue.sqlite3'}?mode=ro", uri=True) as c:
        row = c.execute(
            "SELECT raw_path FROM versions WHERE url=? LIMIT 1",
            (f"https://cs.qau.edu.pk/doc/scheme-{batch}.pdf",),
        ).fetchone()
    title, parts, warnings = parse(archive / row[0])
    assert str(batch) in title and "onwards" in title
    semesters = {p.semester: p for p in parts if p.semester}
    assert set(semesters) == set(range(1, 9))
    assert "CSC-104" in semesters[1].content and "CSC-121" not in semesters[1].content
    assert "CSC-121" in semesters[2].content and "CSC-104" not in semesters[2].content
    assert "CSC-322" in semesters[5].content and "CSC-325" not in semesters[5].content
    assert "CSC-325" in semesters[6].content and "CSC-322" not in semesters[6].content
    rows = course_rows(semesters[1])
    psp = next(r for r in rows if r["code"] == "CSC-104")
    assert (psp["lecture"], psp["lab"], psp["total"]) == (3, 1, 4)
    meta = source_metadata(
        f"https://cs.qau.edu.pk/doc/scheme-{batch}.pdf", title, "\n".join(p.content for p in parts)
    )
    assert meta["cohort_start"] == batch and meta["applies_onwards"] == 1
    assert all(p.page == 1 for p in semesters.values())
