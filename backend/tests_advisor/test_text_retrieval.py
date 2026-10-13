import numpy as np

from advisor.ingest.model import Chunk
from advisor.retrieval.bundle import Bundle
from advisor.retrieval.lexical import BM25
from advisor.retrieval.retriever import Retriever
from advisor.retrieval.text import detect_language, extract_codes, tokenize


def test_codes_normalise_across_generations():
    assert extract_codes("What is CS-211? or csc 211 / CSC211") == ["CSC-211"]
    assert extract_codes("MA-101 and MA 203") == ["MA-101", "MA-203"]


def test_tokenizer_keeps_code_tokens():
    toks = tokenize("Prerequisites of CSC-211 and data structures")
    assert "csc-211" in toks and "211" in toks and "data" in toks


def test_language_detection():
    assert detect_language("What is the fee?") == "en"
    assert detect_language("پی ایچ ڈی کی مدت کتنی ہے؟") == "ur"
    assert detect_language("data structures ka prerequisite kya hai?") == "roman-ur"


def test_bm25_ranks_exact_term_first():
    bm = BM25(["operating systems process scheduling", "data structures trees graphs", "compiler construction"])
    scores = bm.scores("graphs")
    assert int(scores.argmax()) == 1 and scores[0] == 0


def _chunk(i, kind, text, meta=None, title="T"):
    return Chunk(f"c{i}", f"d{i}", 0, f"https://x/{i}", title, kind, "h", text, text, meta or {}, 5)


def _retriever():
    chunks = [
        _chunk(0, "course", "Course CSC-211: Data Structures\nPrerequisites: CSC-121", {"course_code": "CSC-211", "course_name": "Data Structures"}),
        _chunk(1, "course", "Course CSC-226: Operating Systems\nPrerequisites: CSC-211", {"course_code": "CSC-226", "course_name": "Operating Systems"}),
        _chunk(2, "faculty", "Faculty member: Dr. Rabeeh Ayaz Abbasi\nOffice: Room 222", {"faculty_name": "Dr. Rabeeh Ayaz Abbasi"}),
        _chunk(3, "document", "Students need 80% attendance to sit the terminal exam."),
    ]
    import dataclasses

    rows = [dataclasses.asdict(c) for c in chunks]
    return Retriever(Bundle(None, rows, np.zeros((4, 4), dtype=np.float32), {"build_id": "t"}), None, None)


def test_course_code_query_finds_course_record_first():
    hits = _retriever().search("prerequisites of csc 211")
    assert hits[0].chunk["meta"]["course_code"] == "CSC-211"


def test_course_name_and_faculty_name_are_resolved():
    r = _retriever()
    assert r.entities("tell me about data structures").course_name_codes == ["CSC-211"]
    assert r.entities("where is rabeeh sir sitting").faculty == ["dr. rabeeh ayaz abbasi"]
    assert r.search("where is Dr Rabeeh's office")[0].chunk["kind"] == "faculty"


def test_attendance_question_hits_policy_text():
    assert _retriever().search("how much attendance for terminal exam")[0].chunk["kind"] == "document"
