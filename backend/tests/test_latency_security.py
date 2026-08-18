import time

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_nlp_latency_budget() -> None:
    started = time.perf_counter()
    assert client.get("/api/v1/health").status_code == 200
    assert client.post("/api/v1/nlp/analyze", json={"text": "What is the BSCS fee?"}).status_code == 200
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert elapsed_ms < 3000


def test_input_size_and_cors_security_boundaries() -> None:
    oversized = client.post("/api/v1/nlp/analyze", json={"text": "x" * 2001})
    assert oversized.status_code == 422
    preflight = client.options(
        "/api/v1/chat",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_chat_does_not_echo_sensitive_fields_or_claim_eligibility() -> None:
    response = client.post(
        "/api/v1/chat",
        json={"message": "Can I take CSC-459? student ID 04072313001"},
    )
    body = response.json()
    assert "04072313001" not in body["answer"]
    assert body["verified"] is False
