"""Opt-in integration against the configured DB; only temporary test users are changed."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.auth import current_user, optional_current_user
from app.core.database import get_session_factory
from app.main import app
from app.rag.corpus import EvidenceChunk
from app.rag.evidence import Hit

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RAG_DB_TESTS") != "1",
    reason="Set RUN_RAG_DB_TESTS=1 for owned-history integration",
)


def test_saved_citations_owner_isolation_and_order(monkeypatch):
    users = [{"id": str(uuid4()), "role": "student"} for _ in range(2)]
    selected = [users[0]]
    session_id = None
    factory = get_session_factory()
    with factory() as db:
        for user in users:
            db.execute(
                text("""INSERT INTO app_users (id, email, full_name, password_hash, role)
                VALUES (:id, :email, 'RAG integration test', 'disabled-test-password', 'student')"""),
                {"id": user["id"], "email": f"rag-test-{user['id']}@example.invalid"},
            )
        db.commit()
    sample = EvidenceChunk(
        chunk_id="test-evidence",
        document_id="test-document",
        title="Official test excerpt",
        content="BS students study Mathematics and programming during the degree.",
        source_url="https://cs.qau.edu.pk/Bs.php",
    )
    monkeypatch.setattr(
        "app.api.advisor.retrieve", lambda *args, **kwargs: ([Hit(sample, 0.5, coverage=0.5)], [])
    )
    app.dependency_overrides[optional_current_user] = lambda: selected[0]
    app.dependency_overrides[current_user] = lambda: selected[0]
    try:
        client = TestClient(app)
        response = client.post("/api/v1/chat", json={"message": "Tell me about BS Mathematics"})
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        assert session_id and response.json()["citations"]
        history = client.get(f"/api/v1/history/sessions/{session_id}")
        assert history.status_code == 200
        assert [m["role"] for m in history.json()] == ["user", "assistant"]
        assert history.json()[1]["response_metadata"]["citations"][0]["chunk_id"] == "test-evidence"
        selected[0] = users[1]
        assert client.get(f"/api/v1/history/sessions/{session_id}").status_code == 404
        assert client.delete(f"/api/v1/history/sessions/{session_id}").status_code == 404
        assert (
            client.post(
                "/api/v1/chat", json={"message": "Continue", "session_id": session_id}
            ).status_code
            == 404
        )
        assert (
            client.post("/api/v1/history/sessions/batch", json={"session_ids": [session_id]}).json()
            == []
        )
        selected[0] = users[0]
        assert client.delete(f"/api/v1/history/sessions/{session_id}").status_code == 200
    finally:
        app.dependency_overrides.clear()
        with factory() as db:
            for user in users:
                db.execute(text("DELETE FROM chat_sessions WHERE user_id=:id"), {"id": user["id"]})
                db.execute(text("DELETE FROM app_users WHERE id=:id"), {"id": user["id"]})
            db.commit()


def test_structured_portal_endpoints_handle_legacy_schema_without_fabricating_a_plan():
    client = TestClient(app)
    for endpoint in (
        "/programs",
        "/courses",
        "/fees",
        "/deadlines",
        "/exams?academic_year=2026&term=Spring",
        "/timetable/sessions",
        "/timetable/schedule?session_name=Spring%202026",
    ):
        response = client.get("/api/v1" + endpoint)
        assert response.status_code == 200, (endpoint, response.text)
    plan = client.get("/api/v1/programs/BSCS/study-plan")
    assert plan.status_code in {200, 404}
    if plan.status_code == 200:
        assert plan.json()["source"]["source_url"]
    else:
        assert "source-backed" in plan.json()["detail"]
    fees = client.get("/api/v1/fees").json()
    if any(not item["source"]["source_url"] for item in fees["fees"]):
        assert "lack authenticated" in fees["notice"]
