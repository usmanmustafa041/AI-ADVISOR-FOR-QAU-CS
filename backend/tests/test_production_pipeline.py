"""Release-relevant review, provenance, context and arithmetic regressions."""

import io
from zipfile import ZipFile

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import advisor
from app.core.auth import admin_user
from app.ingestion.archive import SourceArchive
from app.ingestion.crawler import CrawlConfig, PublicCrawler
from app.ingestion.parsing import parse_document
from app.main import app
from app.nlp.query_pipeline import plan_query
from app.rag.corpus import EvidenceChunk, build_corpus
from app.rag.encoding import texts_for_model
from app.rag.evidence import EvidenceIndex, Hit, diversify
from app.response.calculation import calculate_gpa
from app.response.educational import is_educational
from app.response.grounded import curriculum_credit_answer, supported_numbers, validate_claims


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        (
            "CSC-104 BSCS Fall 2025 course\nFollow-up: Iska prerequisite kya hai?\n"
            "Programme: BS Computer Science\nAdmission batch: Fall 2025",
            "CSC-104 is offered in Fall 2025.",
        ),
        ("How long is the MS Data Science programme?", "The programme requires 30 credits."),
    ],
)
def test_related_course_facts_cannot_replace_the_requested_requirement(question, answer):
    hit = Hit(
        EvidenceChunk(
            chunk_id="course",
            document_id="course",
            title="Programme",
            content=answer,
            source_url="https://cs.qau.edu.pk/academics",
        ),
        1,
    )
    with pytest.raises(ValueError, match="does not answer|do not answer"):
        validate_claims(
            {"claims": [{"text": answer, "support": [{"source": 1, "quote": answer}]}]},
            [hit],
            question,
        )


def test_missing_prerequisite_followup_abstains_without_model_or_local_override(monkeypatch):
    from app.response.grounded import generate_answer

    hit = Hit(
        EvidenceChunk(
            chunk_id="local",
            document_id="local",
            title="Provided plan",
            content="CSC-104 prerequisite: CSC-100",
            source_url="provided:///unverified.docx",
        ),
        1,
    )
    answer = generate_answer(
        "CSC-104 BSCS Fall 2025\nFollow-up: Iska prerequisite kya hai?", [hit], "roman_urdu"
    )
    assert answer.grounding_status == "insufficient_evidence"
    assert "nahi mile" in answer.answer and not answer.citations


def test_timetable_columns_preserve_published_values_without_inferring_current_assignments():
    parsed = parse_document(
        b"""<title>Timetable Spring 2026</title><table>
        <tr><th>Course Code</th><th>Day</th><th>Time</th><th>Room</th><th>Instructor</th></tr>
        <tr><td>CSC-104</td><td>Monday</td><td>09:00-10:30</td>
        <td>Lab 2</td><td>Published Name</td></tr>
        </table>""",
        "https://cs.qau.edu.pk/timetable",
        "text/html",
    )
    row = next(r for r in parsed["records"] if r["record_type"] == "timetable_entry")
    assert row["time_raw"] == "09:00-10:30" and row["room"] == "Lab 2"
    assert row["requires_review"] and row["effective_term"] == "Spring 2026"


def test_undated_schedule_cannot_answer_future_year_even_with_unknown_document_type():
    chunk = EvidenceChunk(
        chunk_id="unknown",
        document_id="unknown",
        title="TT_v7 fall 26.docx",
        content="CSC-104 Monday 09:00-10:30",
        category="general",
        source_url="https://cs.qau.edu.pk/uploads/example.pdf",
    )
    assert not EvidenceIndex([chunk])._eligible(chunk, "CSC-104 timetable for Spring 2030")


def test_offline_processing_cannot_hide_a_failed_live_crawl(tmp_path):
    import json

    from scripts.report_crawl_coverage import report_coverage

    root = tmp_path / "archive"
    archive = SourceArchive(root)
    url = "https://cs.qau.edu.pk/example.pdf"
    archive.observe("web", url, "http_error", detail={"http_status": 503})
    archive.observe("offline", url, "new")
    (root / "runs").mkdir()
    (root / "runs/web.json").write_text(
        json.dumps(
            {
                "run_id": "web",
                "visited": 1,
                "resources": [{"url": url, "status": "http_error"}],
            }
        )
    )
    archive.close()
    report = report_coverage(root)
    assert report["discovered_in_scope"] == 1
    assert report["failed"] == 1 and report["successfully_processed"] == 0


def test_backup_has_consistent_sqlite_and_detects_tampering(tmp_path):
    import json
    import sqlite3
    import tarfile

    from scripts.backup_pipeline import make_backup, verify_backup

    archive = tmp_path / "archive"
    archive.mkdir()
    with sqlite3.connect(archive / "catalogue.sqlite3") as db:
        db.execute("CREATE TABLE example(value TEXT)")
        db.execute("INSERT INTO example VALUES ('preserved')")
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text("evidence")
    output = tmp_path / "private/backup.tar.gz"
    make_backup(output, archive, corpus)
    assert output.stat().st_mode & 0o777 == 0o600
    assert "source-archive/catalogue.sqlite3" in verify_backup(output)["files"]
    with tarfile.open(output, "r:gz") as tar:
        records = [(m, tar.extractfile(m).read()) for m in tar.getmembers()]
    changed = tmp_path / "tampered.tar.gz"
    with tarfile.open(changed, "w:gz") as tar:
        for member, data in records:
            if member.name == "manifest.json":
                manifest = json.loads(data)
                manifest["files"]["live-library/corpus.jsonl"]["sha256"] = "0" * 64
                data = json.dumps(manifest).encode()
                member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    with pytest.raises(ValueError, match="integrity failure"):
        verify_backup(changed)


def test_probation_cannot_be_supported_by_the_separate_dismissal_rule():
    hit = Hit(
        EvidenceChunk(
            chunk_id="rule",
            document_id="rules",
            title="BS rules",
            content="If a student scores CGPA less than 1.0, they shall be dropped from the rolls.",
            source_url="https://qau.edu.pk/rules",
            program="BSCS",
        ),
        1,
    )
    with pytest.raises(ValueError, match="rule type"):
        validate_claims(
            {
                "claims": [
                    {
                        "text": "BS probation is triggered below 1.0 CGPA.",
                        "support": [{"source": 1, "quote": hit.chunk.content}],
                    }
                ]
            },
            [hit],
        )


def test_rule_lookup_reads_changed_values_and_preserves_lateral_scope():
    from app.response.policy_lookup import policy_excerpt_answer

    wording = (
        "Whenever a student's CGPA is 1.2 or more but less than 2.3 "
        "they shall be placed on probation."
    )
    regular = Hit(
        EvidenceChunk(
            chunk_id="regular",
            document_id="regular",
            title="Rules/Regulations relating to BS Program (Morning/Evening)",
            content=wording,
            source_url="https://qau.edu.pk/bs-rules",
            category="academic_policy",
            program="BSCS",
        ),
        1,
    )
    result = policy_excerpt_answer("BS probation CGPA range kya hai?", [regular], "roman_urdu")
    assert wording in result.answer and result.citations[0]["quotes"] == [wording]
    assert policy_excerpt_answer("BS lateral entry probation range?", [regular], "english") is None
    assert policy_excerpt_answer("MS probation range?", [regular], "english") is None


def test_pending_snapshot_cannot_publish_even_after_passing_retrieval(tmp_path, monkeypatch):
    import json
    from dataclasses import asdict

    from fastapi import HTTPException

    from app.api import knowledge_review

    monkeypatch.setattr(knowledge_review, "BACKEND_ROOT", tmp_path)
    identifier = "a" * 32
    directory = tmp_path / "data/rag/snapshots" / identifier
    directory.mkdir(parents=True)
    archive = SourceArchive(tmp_path / "archive")
    row = archive.save("run", "https://cs.qau.edu.pk/scheme", b"original", document(), {})
    chunk = EvidenceChunk(
        chunk_id="pending",
        document_id="scheme",
        title="Pending scheme",
        content="Official course information.",
        source_url="https://cs.qau.edu.pk/scheme",
        source_version_id=row["version_id"],
    )
    (directory / "corpus.jsonl").write_text(json.dumps(asdict(chunk)) + "\n")
    (directory / "refresh_report.json").write_text('{"retrieval_gate_passed": true}')
    try:
        with pytest.raises(HTTPException) as error:
            knowledge_review.publish(
                knowledge_review.PublicationRequest(
                    snapshot_id=identifier, note="Testing the pending source gate"
                ),
                {"id": "admin"},
                archive,
            )
        assert error.value.status_code == 409 and "unreviewed" in error.value.detail
        assert not (directory / "previous.jsonl").exists()
    finally:
        archive.close()


def test_probation_retrieval_prefers_the_rule_sentence_over_a_dismissal_heading():
    common = dict(
        title="BS Morning/Evening rules",
        program="BSCS",
        category="academic_policy",
        source_url="https://qau.edu.pk/rules",
    )
    dismissal = EvidenceChunk(
        chunk_id="dismissal",
        document_id="rules",
        content="If CGPA is less than 1.0, the student is dropped.\nProbation",
        **common,
    )
    probation = EvidenceChunk(
        chunk_id="probation",
        document_id="rules",
        content=(
            "If CGPA is 1.0 or more but less than 2.0, the student shall be placed on probation."
        ),
        **common,
    )
    hits = EvidenceIndex([dismissal, probation]).search(
        "What are the BS probation rules?", dense=False
    )
    assert hits[0].chunk.chunk_id == "probation"


def test_password_recovery_never_returns_a_reset_secret_in_production(monkeypatch):
    from types import SimpleNamespace

    from app.api import auth
    from app.schemas.auth import ForgotPasswordRequest

    class Database:
        def execute(self, *args):
            return self

        def mappings(self):
            return self

        def one_or_none(self):
            return {"id": "synthetic-user"}

        def commit(self):
            pass

    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(app_env="production"))
    response = auth.forgot_password(ForgotPasswordRequest(email="test@example.com"), Database())
    assert "demo_reset_token" not in response


def document(text="Official course information."):
    return parse_document(
        f"<title>BSCS Fall 2025</title><main>{text}</main>".encode(),
        "https://cs.qau.edu.pk/scheme",
        "text/html",
    )


def test_sitemap_discovery_reports_pending_resources_and_obeys_robots(tmp_path):
    requested = []

    def handler(request):
        requested.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /private\n"
                "Sitemap: https://cs.qau.edu.pk/sitemap.xml",
            )
        if request.url.path == "/sitemap.xml":
            return httpx.Response(
                200,
                text="<urlset><url><loc>https://cs.qau.edu.pk/policy</loc>"
                "</url><url><loc>https://cs.qau.edu.pk/private</loc></url></urlset>",
            )
        return httpx.Response(
            200,
            text="<title>Academic policies</title><main>Official policy.</main>",
            headers={"content-type": "text/html"},
        )

    archive = SourceArchive(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = PublicCrawler(
            archive,
            CrawlConfig(max_pages=2, delay_seconds=0.2, discover_sitemaps=True),
            client=client,
        ).crawl(["https://cs.qau.edu.pk/"])
    assert report["counts"]["sitemap_processed"] == 1
    assert report["discovered"] == 3 and report["pending"] == 1
    assert "/private" not in requested
    assert any(r["status"] == "pending" for r in report["resources"])
    archive.close()


def test_approval_does_not_follow_new_version_or_erase_approved_previous(tmp_path):
    archive = SourceArchive(tmp_path)
    url = "https://cs.qau.edu.pk/scheme"
    first = archive.save("one", url, b"old", document("Old official course info"), {})
    archive.review(first["version_id"], "approved", "admin-test", "Checked original")
    second = archive.save("two", url, b"new", document("New official course info"), {})
    assert archive.review_status(second["version_id"])["decision"] == "pending"
    assert [v["version_id"] for v in archive.approved_documents()] == [first["version_id"]]
    archive.review(second["version_id"], "approved", "admin-test", "Checked updated original")
    assert [v["version_id"] for v in archive.approved_documents()] == [second["version_id"]]
    archive.close()


def test_unverified_workspace_document_cannot_be_approved_as_policy(tmp_path):
    archive = SourceArchive(tmp_path)
    row = archive.save("one", "provided:///rules.html", b"html", document(), {})
    with pytest.raises(ValueError, match="local documents"):
        archive.review(row["version_id"], "approved", "admin", "Approve local doc")
    assert build_corpus(tmp_path, crawl_archive=tmp_path, approved_only=True)[0] == []
    archive.close()


def test_docx_preserves_table_prerequisite_conditions_and_has_no_fabricated_pages():
    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    rows = [
        ["Course Code", "Course Name", "Credit Hours", "Prerequisites"],
        ["CSC-400", "Systems", "3+1", "CSC-200 OR CSC-201"],
    ]
    xml = f'<w:document xmlns:w="{namespace}"><w:body><w:tbl>'
    for row in rows:
        xml += (
            "<w:tr>"
            + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in row)
            + "</w:tr>"
        )
    xml += "</w:tbl></w:body></w:document>"
    stream = io.BytesIO()
    with ZipFile(stream, "w") as package:
        package.writestr("word/document.xml", xml)
    result = parse_document(
        stream.getvalue(),
        "provided:///test.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    record = next(r for r in result["records"] if r["record_type"] == "course")
    assert record["credit_hours"] == 4
    assert record["prerequisites_raw"] == "CSC-200 OR CSC-201"
    assert record["source"]["page_number"] is None


def test_multiturn_scope_keeps_batch_for_curriculum_without_repeating_it():
    history = [
        {"role": "user", "content": "BSCS Fall 2024 scheme"},
        {"role": "assistant", "content": "How can I help?"},
    ]
    plan = plan_query("What are the total credit hours?", history)
    assert plan.scope["term"] == "Fall 2024" and plan.scope["programs"] == ["bs"]
    assert "Fall 2024" in plan.rewritten
    fees = plan_query("What is the current morning fee?", history)
    assert "Fall 2024" not in fees.rewritten
    changed = plan_query("How long is the PhD programme?", history)
    assert changed.scope["programs"] == ["phd"] and "term" not in changed.scope


def test_generated_scope_metadata_is_not_a_second_question():
    from app.response.grounded import generate_answer

    chunk = EvidenceChunk(
        chunk_id="sum",
        document_id="scheme",
        title="BSCS Fall 2025",
        content="Semester 1: 16 credit hours\nCalculated total: 16 + 118 = 134 credit hours.",
        category="curriculum",
        program="BSCS",
        effective_term="Fall 2025",
        evidence_type="derived_arithmetic",
        source_url="https://cs.qau.edu.pk/scheme.pdf",
    )
    plan = plan_query(
        "What about semester 1 credit hours?",
        [{"role": "user", "content": "How many total credits in the BSCS Fall 2025 scheme?"}],
    )
    result = generate_answer(plan.rewritten, [Hit(chunk, 1)], "english")
    assert result.model == "source-calculator" and "Semester 1: 16 credit hours" in result.answer


def test_request_archive_allows_sequential_worker_thread_handoff(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    archive = SourceArchive(tmp_path, thread_handoff=True)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(archive.versions).result() == []
    finally:
        archive.close()


def test_arithmetic_is_exact_and_does_not_claim_university_grade_conversion():
    result = calculate_gpa("Calculate GPA: 3 credits at 4.0, 4 credits at 3.0")
    assert "**3.43**" in result.answer and result.citations == []
    assert result.grounding_status == "calculated"
    assert calculate_gpa("Calculate my GPA with grades A and B") is None


def test_educational_questions_are_separate_from_official_rules():
    assert is_educational("Explain binary search with an example")
    assert not is_educational("Explain the QAU grading policy")
    assert not is_educational("What is the prerequisite for CSC-104 programming?")
    assert not is_educational("What is the MS Data Science programme duration?")
    assert not is_educational("تعلیمی صفحے پر پی ایچ ڈی کمپیوٹر سائنس کی کم از کم مدت کیا ہے؟")
    assert is_educational("بائنری سرچ الگورتھم کیا ہے؟")


def test_programme_total_does_not_use_individual_semester_credit_value():
    chunk = EvidenceChunk(
        chunk_id="sum",
        document_id="scheme",
        title="BSCS scheme Fall 2025",
        content=(
            "Semester 1: 16 credit hours\nCalculated total: "
            "16 + 18 + 16 + 17 + 18 + 18 + 15 + 16 = 134 credit hours."
        ),
        source_url="https://cs.qau.edu.pk/doc/scheme-2025.pdf",
        effective_term="Fall 2025",
        category="curriculum",
        program="BSCS",
        evidence_type="derived_arithmetic",
    )
    answer = curriculum_credit_answer(
        "What are the BSCS credit hours for Fall 2025?", [Hit(chunk, 1)], "english"
    )
    assert "**134 credit hours**" in answer.answer
    assert answer.citations[0]["quotes"][0].endswith("134 credit hours")


def test_undated_programme_summary_cannot_establish_a_batch_scheme():
    chunk = EvidenceChunk(
        chunk_id="general",
        document_id="academics",
        title="BS Computer Science",
        content="BS Computer Science requires 130 credit hours.",
        source_url="https://cs.qau.edu.pk/academics",
        category="programme",
    )
    assert (
        EvidenceIndex([chunk]).search("BSCS Fall 2024 curriculum credit hours", dense=False) == []
    )


def test_e5_prefixes_match_index_and_query_semantics():
    assert texts_for_model(["hello"], "intfloat/multilingual-e5-small") == ["passage: hello"]
    assert texts_for_model(["hello"], "intfloat/multilingual-e5-small", query=True) == [
        "query: hello"
    ]
    assert texts_for_model(["hello"], "sentence-transformers/all-MiniLM-L6-v2") == ["hello"]


def test_chat_capacity_rejects_without_retrieval_when_busy(monkeypatch):
    class Busy:
        def acquire(self, **kwargs):
            return False

    monkeypatch.setattr(advisor, "_request_slots", Busy())
    result = TestClient(app).post("/api/v1/chat", json={"message": "BSCS fee?"})
    assert result.status_code == 503 and result.headers["retry-after"] == "3"


def test_ingestion_review_requires_administrator():
    app.dependency_overrides.pop(admin_user, None)
    assert TestClient(app).get("/api/v1/knowledge-review").status_code == 401


def test_local_duplicate_cannot_suppress_identical_official_evidence():
    official = EvidenceChunk(
        chunk_id="official",
        document_id="official",
        title="Scheme",
        content="CSC-104 carries four credits.",
        source_url="https://cs.qau.edu.pk/doc/scheme-2025.pdf",
    )
    local = EvidenceChunk(
        chunk_id="local",
        document_id="local",
        title="Local scheme",
        content=official.content,
        source_url="",
        verification_status="provided_unverified",
    )
    assert diversify([Hit(local, 2), Hit(official, 1)], 5)[0].chunk.chunk_id == "official"


def test_faithful_numerical_translation_preserves_provenance():
    quote = "Each regular semester shall be spread over eighteen weeks."
    chunk = EvidenceChunk(
        chunk_id="weeks",
        document_id="rules",
        title="BS rules",
        content=quote,
        source_url="https://qau.edu.pk/bs-rules",
    )
    claims = {
        "claims": [
            {
                "text": "The regular semester has 18 weeks.",
                "support": [{"source": 1, "quote": quote}],
            }
        ]
    }
    assert validate_claims(claims, [Hit(chunk, 1)])[0]
    claims["claims"][0]["text"] = "The regular semester has 19 weeks."
    with pytest.raises(ValueError, match="Numerical"):
        validate_claims(claims, [Hit(chunk, 1)])
    assert "2000" in supported_numbers("two thousand rupees")
