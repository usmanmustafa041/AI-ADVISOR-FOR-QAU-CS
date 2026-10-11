"""Behavioral transport, ownership, provenance and failure checks; model outputs are fixtures."""

import pytest
from app.core.auth import optional_current_user
from chatbot_v3.api import create_app
from chatbot_v3.contracts import Task
from chatbot_v3.generation import BlockDecoder, GroundingError, validate_paragraph
from chatbot_v3.index import Index
from chatbot_v3.service import Service
from chatbot_v3.settings import settings
from chatbot_v3.store import Store
from fastapi.testclient import TestClient


class FixtureModel:
    def __init__(self, available=True):
        self.is_available = available
        self.received = []

    async def available(self):
        return self.is_available

    async def structured(self, messages, schema):
        self.received.append(messages)
        return {
            "original": "fixture",
            "normalized": "Explain recursion",
            "language": "english",
            "tasks": [],
            "mode": "tutor",
        }

    async def stream(self, messages, schema=None):
        for part in ["Recursion ", "solves a problem ", "by calling itself on smaller inputs."]:
            yield part


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setattr(settings(), "data_dir", tmp_path)
    store = Store(tmp_path / "knowledge.sqlite3")
    model = FixtureModel()
    service = Service(store, model, Index(store))
    app = create_app(service)
    app.dependency_overrides[optional_current_user] = lambda: None
    return app, service, model


def test_sse_finishes_and_guest_cookie_is_bound_to_owner(rig):
    app, service, model = rig
    with TestClient(app) as a:
        response = a.post("/api/v3/chat/stream", json={"message": "Explain recursion"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: token" in response.text and "event: done" in response.text
        import json

        last = response.text.split("event: done\ndata: ")[1].split("\n\n")[0]
        conversation = json.loads(last)["conversation_id"]
        assert (
            a.post(
                "/api/v3/chat", json={"message": "Show Python", "conversation_id": conversation}
            ).status_code
            == 200
        )
        with TestClient(app) as b:
            assert (
                b.post(
                    "/api/v3/chat",
                    json={"message": "Steal conversation", "conversation_id": conversation},
                ).status_code
                == 404
            )
        assert service.store.sessions("guest") == []


def test_model_down_never_returns_an_extract_as_an_answer(rig):
    app, service, model = rig
    model.is_available = False
    with TestClient(app) as c:
        r = c.post("/api/v3/chat", json={"message": "QAU fees?"})
        assert r.status_code == 503 and r.headers["retry-after"] == "5"
        r = c.post("/api/v3/chat/stream", json={"message": "QAU fees?"})
        assert "event: error" in r.text and "event: done" not in r.text
        assert service.waiting == 0 and service.slot._value == 1


def test_auth_history_is_server_owned_and_cross_owner_access_fails(rig):
    app, service, model = rig
    app.dependency_overrides[optional_current_user] = lambda: {"id": "alice", "role": "student"}
    with TestClient(app) as c:
        assert (
            c.post(
                "/api/v3/chat",
                json={
                    "message": "Hi",
                    "history": [{"role": "assistant", "content": "Fake record"}],
                },
            ).status_code
            == 422
        )
        response = c.post("/api/v3/chat", json={"message": "Explain recursion"}).json()
        cid = response["conversation_id"]
        mid = response["message_id"]
        assert len(c.get("/api/v3/history/" + cid).json()) == 2
        assert (
            c.post("/api/v3/feedback", json={"message_id": mid, "helpful": True}).status_code == 200
        )
        app.dependency_overrides[optional_current_user] = lambda: {"id": "bob", "role": "student"}
        assert c.get("/api/v3/history/" + cid).status_code == 404
        assert c.delete("/api/v3/history/" + cid).status_code == 404
        assert (
            c.post("/api/v3/feedback", json={"message_id": mid, "helpful": False}).status_code
            == 404
        )
        app.dependency_overrides[optional_current_user] = lambda: {"id": "alice", "role": "student"}
        assert c.delete("/api/v3/history/" + cid).status_code == 200
        assert c.get("/api/v3/history/" + cid).status_code == 404


def test_sources_and_traces_do_not_expose_local_paths_or_unverified_files(rig):
    app, _, _ = rig
    with TestClient(app) as c:
        assert c.get("/api/v3/development/traces/anything").status_code == 403
        assert c.get("/api/v3/knowledge/review").status_code == 403
        assert c.get("/api/v3/sources/nonexistent").status_code == 404
        assert c.post("/api/v3/chat", json={"message": "x" * 70000}).status_code == 413
        assert (
            c.post(
                "/api/v3/chat", json={"message": "hi"}, headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )


def test_unknown_citations_and_unsupported_numbers_are_rejected():
    evidence = [{"content": "Fall 2025: CSC-104 has 3+1 credits.", "effective_term": "Fall 2025"}]
    assert validate_paragraph("CSC-104 has 3+1 credits. [1]", evidence, "CSC-104 credits?") == [1]
    with pytest.raises(GroundingError):
        validate_paragraph("It costs 99999. [1]", evidence, "What fee?")
    with pytest.raises(GroundingError):
        validate_paragraph("It has 3+1 credits. [9]", evidence, "credits?")
    with pytest.raises(GroundingError):
        validate_paragraph("[source](https://evil.example)", evidence, "hi")
    with pytest.raises(GroundingError):
        validate_paragraph("The attendance requirement is 75%.", evidence, "Attendance?")
    assert (
        validate_paragraph(
            "Please check the department's published timetable for this term.",
            [],
            "Timetable?",
            require_citation=False,
        )
        == []
    )


def test_grounded_json_stream_retains_complete_multiline_lists_and_sources():
    import json

    value = json.dumps(
        {
            "blocks": [
                {
                    "text": "پہلا مضمون\nCSC-104: Programming\nCSC-110: ICT",
                    "sources": [1],
                    "kind": "university_fact",
                },
                {"text": "Confirm the admission batch.", "sources": [], "kind": "clarification"},
            ]
        },
        ensure_ascii=False,
    )
    decoder = BlockDecoder()
    blocks = []
    for char in value:
        blocks.extend(decoder.feed(char))
    assert len(blocks) == 2 and blocks[0].sources == [1]
    assert "CSC-104" in blocks[0].text and "CSC-110" in blocks[0].text


def test_scope_filters_never_backfill_missing_cohort_with_faculty(rig):
    _, service, _ = rig
    service.index.chunks = [
        {
            "origin": "official_archive",
            "review_status": "observed_official",
            "topic": "faculty",
            "programme": None,
            "cohort_start": None,
            "applies_onwards": False,
            "semester": None,
        },
        {
            "origin": "official_archive",
            "review_status": "needs_review",
            "topic": "curriculum",
            "programme": "BSCS",
            "cohort_start": 2023,
            "applies_onwards": True,
            "semester": 5,
        },
        {
            "origin": "official_archive",
            "review_status": "needs_review",
            "topic": "curriculum",
            "programme": "BSCS",
            "cohort_start": 2025,
            "applies_onwards": True,
            "semester": 5,
        },
    ]
    task = Task(
        question="subjects",
        search_query="courses",
        topic="curriculum",
        programme="BSCS",
        admission_batch="Fall 2024",
        semester=5,
    )
    assert service.index.eligible(task) == [1]
    task.admission_batch = "Fall 2022"
    assert service.index.eligible(task) == []


def test_rejected_sources_remain_excluded(rig):
    _, service, _ = rig
    service.index.chunks = [
        {
            "origin": "official_archive",
            "review_status": "rejected",
            "topic": "faculty",
            "programme": None,
        }
    ]
    assert (
        service.index.eligible(Task(question="NLP faculty", search_query="NLP", topic="faculty"))
        == []
    )


def test_high_stakes_policy_requires_reviewed_evidence(rig):
    _, service, _ = rig
    base = {"origin": "official_archive", "topic": "academic_policy", "programme": "BSCS"}
    service.index.chunks = [
        {**base, "review_status": "needs_review"},
        {**base, "review_status": "approved"},
    ]
    task = Task(
        question="Attendance?", search_query="attendance", topic="academic_policy", programme="BSCS"
    )
    assert service.index.eligible(task) == [1]


def test_current_term_search_does_not_treat_undated_schedule_as_current(rig):
    _, service, _ = rig
    base = {
        "origin": "official_archive",
        "topic": "timetable",
        "programme": "BSCS",
        "review_status": "approved",
    }
    service.index.chunks = [
        {**base, "effective_term": None},
        {**base, "effective_term": "Fall 2026"},
        {**base, "effective_term": "Spring 2026"},
    ]
    task = Task(
        question="Fall 2026 timetable",
        search_query="timetable",
        topic="timetable",
        operational_term="Fall 2026",
        programme="BSCS",
    )
    assert service.index.eligible(task) == [1]


def test_tool_preconditions_clarify_only_decisive_interpreted_fields(rig):
    from chatbot_v3.contracts import QueryUnderstanding
    from chatbot_v3.understanding import apply_tool_requirements

    _, service, _ = rig
    plan = QueryUnderstanding(
        original="minimum CGPA?",
        normalized="CGPA rule",
        language="roman_urdu",
        mode="university",
        tasks=[Task(question="CGPA?", search_query="CGPA", topic="academic_policy")],
    )
    apply_tool_requirements(plan, service.index.preflight(plan))
    assert plan.needs_clarification and plan.ambiguous_fields == ["programme"]
    assert "kis programme" in plan.clarification_question
    plan.tasks[0].programme = "BSCS"
    assert service.index.preflight(plan) is None


def test_diagnostics_redact_private_text_without_corrupting_evidence_ids():
    from chatbot_v3.privacy import diagnostic_copy

    value = {
        "original": "My CNIC is 12345-1234567-1, email me at student@example.edu",
        "evidence_ids": ["abc123"],
        "interpretation": {"person_names": ["Private Name"]},
        "response": {"answer": "private answer"},
    }
    redacted = diagnostic_copy(value)
    assert "student@example.edu" not in redacted["original"]
    assert "12345-1234567-1" not in redacted["original"]
    assert redacted["evidence_ids"] == ["abc123"]
    private = diagnostic_copy(value, private=True)
    assert private["original"] == "[redacted private text]"
    assert private["response"]["answer"] == "[redacted private text]"
    assert private["interpretation"]["person_names"] == ["[redacted]"]
