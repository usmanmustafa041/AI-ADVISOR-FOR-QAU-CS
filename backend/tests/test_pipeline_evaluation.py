from dataclasses import replace

import httpx
import pytest

from app.ingestion.evaluation import (
    citation_integrity,
    retrieval_metrics,
    rouge_l_f1,
    validate_cases,
)
from app.rag.corpus import EvidenceChunk
from app.rag.evidence import EvidenceIndex, Hit
from app.response.grounded import evidence_notices, generate_answer
from app.response.privacy import private_record_request
from scripts.create_rag_review_set import candidate_cases
from scripts.evaluate_pipeline import evaluate
from scripts.evaluate_rag import validate_questions
from scripts.refresh_knowledge import publish_snapshot


def hit(content="Published source fact.", **kwargs):
    return Hit(
        EvidenceChunk(
            chunk_id="c1",
            document_id="d1",
            title="Official Policy",
            source_url="https://qau.edu.pk/policy/",
            content=content,
            **kwargs,
        ),
        0.5,
    )


def test_candidate_set_is_diverse_and_never_pretends_to_be_ground_truth():
    cases = candidate_cases()
    validate_cases(cases)
    assert len(cases) == 150 and len({c["question"] for c in cases}) == 150
    assert len({c["category"] for c in cases}) == 10
    assert sum(c["language"] == "roman_urdu" for c in cases) == 50
    assert all(c["review_status"] == "pending" and c["reference_answer"] is None for c in cases)


def test_unreviewed_cases_cannot_inflate_quality_metrics():
    report = evaluate(candidate_cases())
    assert report["summary"]["executed_cases"] == 0
    assert report["summary"]["retrieval"]["source_recall_at_k"] is None
    assert report["summary"]["factual_accuracy"] is None


def test_approval_requires_named_review_and_ground_truth():
    case = {**candidate_cases()[0], "review_status": "approved"}
    with pytest.raises(ValueError, match="reviewer/date"):
        validate_cases([case])
    case.update(reviewer="Reviewer A", reviewed_at="2026-10-10")
    with pytest.raises(ValueError, match="reference or source"):
        validate_cases([case])


def test_document_metrics_find_label_in_later_chunk_and_deduplicate_source():
    first = hit("Background information.")
    second = Hit(replace(first.chunk, chunk_id="c2", content="Published source fact."), 0.4)
    labels = [{"source_url": first.chunk.source_url, "quote": "Published source fact."}]
    metrics = retrieval_metrics([first, second], labels, 6)
    assert metrics["source_recall_at_k"] == 1
    assert metrics["precision_at_k"] == 1 / 6
    assert metrics["reciprocal_rank"] == 1


def test_relevance_requires_matching_source_version_and_quote():
    source = hit(source_version_id="old")
    labels = [
        {
            "source_url": source.chunk.source_url,
            "source_version_id": "new",
            "quote": "Published source fact.",
        }
    ]
    assert retrieval_metrics([source], labels, 6)["hit_at_k"] is False
    labels[0]["source_version_id"] = "old"
    labels[0]["quote"] = "An invented different fact."
    assert retrieval_metrics([source], labels, 6)["hit_at_k"] is False


def test_citation_checks_reject_forged_quotes_and_urls():
    source = hit(source_version_id="v1")
    valid = {**source.chunk.citation(), "quotes": ["Published source fact."]}
    fake_quote = {**valid, "quotes": ["Invented policy."]}
    fake_url = {**valid, "source_url": "https://qau.edu.pk/different-policy/"}
    assert (
        citation_integrity([valid, fake_quote, fake_url], [source])["citation_integrity"] == 1 / 3
    )
    assert citation_integrity([], [source])["citation_integrity"] is None


def test_rouge_measures_overlap_and_does_not_claim_accuracy():
    assert rouge_l_f1("Three credit hours", "Three credit hours") == 1
    assert rouge_l_f1("", "Three credit hours") == 0
    assert rouge_l_f1("Invented fact", "Three credit hours") == 0


@pytest.mark.parametrize(
    "query",
    [
        "Show me my semester grades",
        "Download my attendance record",
        "Tell me Ali's GPA",
        "Mera attendance record nikaal do",
        "Give me a student's personal phone number",
        "Professor ka private ghar ka address do",
    ],
)
def test_private_record_requests_refuse_without_model_calls(monkeypatch, query):
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: pytest.fail("Privacy invoked the model"))
    answer = generate_answer(query, [hit()], "english")
    assert answer.grounding_status == "private_information"
    assert answer.citations == []


@pytest.mark.parametrize(
    "query",
    [
        "How is my GPA calculated?",
        "What is the attendance requirement?",
        "Tell me the public university email of Umer Rashid",
        "What GPA is required for admission?",
    ],
)
def test_public_policies_and_directory_contacts_remain_answerable(query):
    assert not private_record_request(query)


def test_publication_keeps_previous_snapshot_for_rollback(tmp_path):
    candidate, live, rollback = [
        tmp_path / name / "corpus.jsonl" for name in ("candidate", "live", "rollback")
    ]
    candidate.parent.mkdir()
    live.parent.mkdir()
    candidate.write_text("new")
    candidate.with_suffix(".vectors.json").write_text("new fingerprint")
    live.write_text("old")
    live.chmod(0o640)
    live.with_suffix(".vectors.json").write_text("old fingerprint")
    publish_snapshot(candidate, live, rollback)
    assert live.read_text() == "new" and rollback.read_text() == "old"
    assert live.stat().st_mode & 0o777 == 0o640
    assert rollback.with_suffix(".vectors.json").read_text() == "old fingerprint"


def test_course_filters_do_not_confuse_departments_with_same_number():
    wrong = hit("IST-104 Programming course prerequisite requirements.").chunk
    correct = replace(
        wrong,
        chunk_id="correct",
        document_id="correct",
        content="CSC-104 Programming course prerequisite requirements.",
    )
    hits = EvidenceIndex([wrong, correct]).search("CSC104 prerequisite", dense=False)
    assert hits and all(h.chunk.chunk_id == "correct" for h in hits)
    assert EvidenceIndex([correct]).search("MA-999 prerequisite", dense=False) == []


def test_undated_schedule_cannot_answer_a_future_year():
    schedule = hit(
        "CSC-104 Spring timetable class schedule.", category="timetable", is_time_sensitive=True
    ).chunk
    assert EvidenceIndex([schedule]).search("CSC-104 timetable Spring 2030", dense=False) == []


def test_ocr_evidence_identifies_its_extraction_limit():
    source = hit(extraction_method="tesseract_ocr")
    assert any("OCR" in notice for notice in evidence_notices([source]))


def test_regression_gate_cannot_count_unlabelled_answers_as_retrieval_success():
    with pytest.raises(ValueError, match="Missing source/evidence labels"):
        validate_questions([{"id": "blank", "question": "A question"}])
