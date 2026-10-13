"""Conversational turns must never invoke retrieval or the answer model."""

import pytest
from fastapi.testclient import TestClient

from app.api import advisor
from app.main import app
from app.rag.corpus import EvidenceChunk
from app.rag.evidence import EvidenceIndex
from app.response.conversation import conversational_reply
from app.response.grounded import GroundedAnswer


@pytest.mark.parametrize(
    "message",
    [
        "hi'",
        '"Hi!"',
        "hi 👋",
        "HELLO???",
        "hey there!",
        "good morning",
        "thanks!",
        "thank you so much",
        "how are you?",
        "okay",
        "bye!",
        "Assalam o Alaikum!",
        "السلام علیکم",
        "help",
        "Who are you?",
        "Hi, how are you?",
        "Hello, can you help me?",
        "Hello QAU!",
    ],
)
def test_conversation_bypasses_retrieval_and_model_even_with_academic_history(monkeypatch, message):
    def forbidden(*args, **kwargs):
        pytest.fail("A conversational turn invoked academic retrieval or generation")

    monkeypatch.setattr(advisor, "retrieve", forbidden)
    monkeypatch.setattr(advisor, "generate_answer", forbidden)
    response = TestClient(app).post(
        "/api/v1/chat",
        json={
            "message": message,
            "history": [{"role": "user", "content": "CSC-483 prerequisites?"}],
            "context_course_code": "CSC-483",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["grounding_status"] == "conversational"
    assert data["citations"] == [] and data["model_backend"] == "conversation"
    assert len(data["answer"]) < 350


def test_exact_reported_greeting_is_short_and_natural():
    assert conversational_reply("hi'", "english").answer == "Hi! How can I help you with QAU today?"


@pytest.mark.parametrize(
    "message",
    [
        "Hi, what is the BSCS fee?",
        "Hello, who is Rabeeh Ayaz Abbasi?",
        "Thanks, and what about its eligibility?",
        "Can you help me with CSC-483?",
        "What are the library opening hours?",
    ],
)
def test_greeting_prefix_does_not_swallow_real_questions(monkeypatch, message):
    queries = []
    monkeypatch.setattr(advisor, "retrieve", lambda query, db: (queries.append(query) or [], []))
    monkeypatch.setattr(advisor, "generate_answer", lambda *a: GroundedAnswer("Academic response"))
    result = TestClient(app).post("/api/v1/chat", json={"message": message}).json()
    assert queries == [message]
    assert result["answer"] == "Academic response"


@pytest.mark.parametrize("message", ["hi'", "hello!", "thanks", "???", "👋"])
def test_retrieval_noise_cannot_match_bibliography_or_load_encoder(monkeypatch, message):
    record = EvidenceChunk(
        chunk_id="bibliography",
        document_id="faculty",
        title="Faculty publications",
        content="An article published in Library Hi Tech, volume 35.",
        source_url="https://cs.qau.edu.pk/faculty_details.php?id=4",
    )
    index = EvidenceIndex([record])
    monkeypatch.setattr(index, "_load_dense", lambda: pytest.fail("Noise loaded the encoder"))
    assert index.search(message) == []
