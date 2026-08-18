from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_points_to_docs() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "qau-cs-academic-advisor-api",
    }


def test_openapi_exposes_academic_endpoints() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/programs" in paths
    assert "/api/v1/programs/{program_code}/study-plan" in paths
    assert "/api/v1/courses/{course_code}" in paths
    assert "/api/v1/courses" in paths
    assert "/api/v1/courses/{course_code}/prerequisites" in paths
    assert "/api/v1/fees" in paths
    assert "/api/v1/timetable" in paths
    assert "/api/v1/nlp/analyze" in paths
    assert "/api/v1/nlp/model" in paths
    assert "/api/v1/nlp/entities" in paths
    assert "/api/v1/rules/prerequisite-check" in paths
    assert "/api/v1/rules/semester-load" in paths
    assert "/api/v1/rules/progression" in paths
    assert "/api/v1/rules/exemption" in paths
    assert "/api/v1/rag/search" in paths
    assert "/api/v1/chat" in paths


def test_database_health_is_safe_when_database_is_down() -> None:
    response = client.get("/api/v1/health/database", timeout=10)
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}


def test_nlp_analyzes_roman_urdu_prerequisite_query() -> None:
    response = client.post(
        "/api/v1/nlp/analyze",
        json={"text": "CSC-486 ki prerequisite kya hai?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "course_prerequisite"
    assert payload["language"] == "roman_urdu"
    assert payload["entities"]["course_code"] == ["CSC-486"]
    assert payload["model_backend"] in {"multilingual_distilbert", "ngram_naive_bayes"}
    assert payload["model_name"]


def test_nlp_model_status_is_auditable() -> None:
    response = client.get("/api/v1/nlp/model")
    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_backend"] in {"auto", "transformer", "baseline"}
    assert payload["active_backend"] in {
        "multilingual_distilbert", "ngram_naive_bayes", "unavailable"
    }
    assert isinstance(payload["artifact_ready"], bool)
    assert isinstance(payload["fallback_active"], bool)


def test_nlp_supports_urdu_script() -> None:
    response = client.post(
        "/api/v1/nlp/analyze",
        json={"text": "مشین لرننگ کی prerequisite کیا ہے؟"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "urdu"
    assert payload["intent"] == "course_prerequisite"


def test_nlp_routes_short_fee_question() -> None:
    response = client.post("/api/v1/nlp/analyze", json={"text": "What is the BSCS fee?"})
    assert response.status_code == 200
    assert response.json()["intent"] == "fee_information"


def test_nlp_routes_roman_urdu_prerequisite_follow_up() -> None:
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "Iska prerequisite pata hai apko?",
            "context_course_code": "CSC-104",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "course_prerequisite"
    assert payload["language"] == "roman_urdu"
    assert payload["entities"]["course_code"] == ["CSC-104"]
    assert payload["confidence"] >= 0.9


def test_nlp_routes_explicit_timetable_at_useful_confidence() -> None:
    response = client.post(
        "/api/v1/nlp/analyze",
        json={"text": "Acha mujhy CSC-104 ka timetable janna hai"},
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "timetable_query"
    assert response.json()["confidence"] >= 0.9


def test_entity_endpoint_extracts_academic_fields() -> None:
    response = client.post(
        "/api/v1/nlp/entities",
        json={"text": "What is the BSCS evening semester 6 timetable for 6 credit hours on Monday?"},
    )
    assert response.status_code == 200
    entities = response.json()["entities"]
    assert entities["program"] == ["BSCS"]
    assert entities["shift"] == ["evening"]
    assert entities["semester"] == ["6"]
    assert entities["credit_hours"] == ["6"]
    assert entities["day"] == ["monday"]


def test_prerequisite_rule_refuses_incomplete_dataset() -> None:
    response = client.post(
        "/api/v1/rules/prerequisite-check",
        json={
            "course_code": "CSC-459",
            "completed_grades": {"CSC-211": "A"},
            "requirements": [],
            "dataset_complete": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "unverified"
    assert response.json()["eligible"] is None


def test_semester_load_and_progression_rules() -> None:
    normal = client.post("/api/v1/rules/semester-load", json={"requested_credit_hours": 18})
    assert normal.json()["allowed"] is True
    exceptional = client.post(
        "/api/v1/rules/semester-load",
        json={"requested_credit_hours": 21, "approval_for_exception": True},
    )
    assert exceptional.json()["category"] == "exceptional"
    probation = client.post("/api/v1/rules/progression", json={"cgpa": 1.5})
    assert probation.json()["status"] == "probation"


def test_rag_embedding_and_chunking_are_deterministic() -> None:
    from app.rag.chunking import chunk_text
    from app.rag.embedding import embed_text

    chunks = chunk_text("Academic policy. " * 200, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert len(embed_text(chunks[0].content)) == 384
    assert embed_text("same text") == embed_text("same text")


def test_chat_endpoint_is_safe_for_unknown_prerequisite_data() -> None:
    response = client.post("/api/v1/chat", json={"message": "Can I take CSC-459?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "course_prerequisite"
    assert payload["verified"] is False
    assert "cannot safely confirm" in payload["answer"]
