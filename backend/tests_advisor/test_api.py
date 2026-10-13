import dataclasses
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from advisor.api.app import create_app
from advisor.config import Settings
from advisor.context import build_context
from advisor.ingest.model import Chunk
from advisor.llm.base import ProviderError
from advisor.retrieval.bundle import Bundle
from advisor.retrieval.retriever import Retriever
from advisor.security import hash_password


class FakeProvider:
    name, model = "fake", "fake-1"

    def __init__(self):
        self.calls = []
        self.fail = None

    async def stream(self, messages, params):
        self.calls.append(messages)
        if self.fail:
            raise self.fail
        user = messages[-1].content
        if "Prerequisites: CSC-121" in user:
            yield "The prerequisite is **CSC-121** [1]. "
            yield "See also [9]."  # [9] does not exist and must be stripped
        else:
            yield "I couldn't find that in the department's published pages."

    async def complete(self, messages, params):
        return "".join([c async for c in self.stream(messages, params)])


def chunks():
    rows = [
        ("course", "Course CSC-211: Data Structures\nPrerequisites: CSC-121 — Object Oriented Programming",
         {"course_code": "CSC-211", "course_name": "Data Structures"}),
        ("document", "Students must attend at least 80% of classes to sit terminal exams.", {}),
    ]
    return [
        dataclasses.asdict(Chunk(f"c{i}", f"d{i}", 0, f"https://cs.qau.edu.pk/{i}", f"Doc {i}", k, "h", t, t, m, 5))
        for i, (k, t, m) in enumerate(rows)
    ]


@pytest.fixture
def env(tmp_path):
    settings = Settings(data_dir=tmp_path, rate_limit_per_minute=1000, rate_limit_burst=1000)
    ctx = build_context(settings, load_kb=False)
    bundle = Bundle(None, chunks(), np.zeros((2, 4), dtype=np.float32), {"build_id": "test", "chunks": 2, "created_at": "2026-10-12T00:00:00"})
    ctx.kb.bundle = bundle
    ctx.kb.retriever = Retriever(bundle, None, None)
    provider = FakeProvider()
    ctx.router.candidates = lambda: [provider]  # type: ignore[method-assign]
    ctx.db.execute("INSERT INTO admins(username, password_hash) VALUES('root', ?)", (hash_password("a-long-password"),))
    with TestClient(create_app(ctx)) as client:
        yield client, ctx, provider


def read_sse(resp):
    events, name = [], None
    for line in resp.iter_lines():
        if line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            events.append((name, json.loads(line[5:])))
    return events


def ask(client, q, cid=None):
    with client.stream("POST", "/api/v1/chat/stream", json={"message": q, "conversation_id": cid}) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        return read_sse(r)


def test_streaming_answer_has_citations_and_sources(env):
    client, *_ = env
    events = ask(client, "What are the prerequisites of CSC-211?")
    names = [n for n, _ in events]
    assert names[0] == "meta" and names[-1] == "done" and "delta" in names and "sources" in names
    text = "".join(d["text"] for n, d in events if n == "delta")
    assert "[1]" in text
    final = [d for n, d in events if n == "replace"]
    assert final and "[9]" not in final[-1]["text"]  # invented citation numbers are removed
    sources = next(d for n, d in events if n == "sources")["sources"]
    assert sources[0]["url"].endswith("/0") and sources[0]["cited"]


def test_unknown_question_is_logged_as_abstained(env):
    client, ctx, _ = env
    events = ask(client, "what is the wifi password")
    assert dict(events)["done"]["outcome"] == "abstained"
    assert ctx.db.one("SELECT outcome FROM query_log ORDER BY id DESC")["outcome"] == "abstained"


def test_smalltalk_skips_the_model(env):
    client, _, provider = env
    events = ask(client, "hello")
    assert dict(events)["done"]["outcome"] == "smalltalk" and provider.calls == []


def test_repeat_question_is_served_from_cache(env):
    client, _, provider = env
    ask(client, "What are the prerequisites of CSC-211?")
    n = len(provider.calls)
    again = ask(client, "what are the prerequisites of csc-211")
    assert dict(again)["done"]["outcome"] == "cached" and len(provider.calls) == n


def test_followup_uses_conversation_history(env):
    client, _, provider = env
    first = ask(client, "Tell me about CSC-211")
    cid = dict(first)["meta"]["conversation_id"]
    ask(client, "and its prerequisites?", cid)
    roles = [m.role for m in provider.calls[-1]]
    assert roles.count("assistant") >= 1  # earlier turn was passed to the model
    hist = client.get(f"/api/v1/conversations/{cid}").json()
    assert [m["role"] for m in hist["messages"]] == ["user", "assistant", "user", "assistant"]


def test_when_every_ai_provider_fails_student_still_gets_the_passages(env):
    client, _, provider = env
    provider.fail = ProviderError("fake", "unavailable", "down")
    done = dict(ask(client, "prerequisites of CSC-211"))["done"]
    assert done["outcome"] == "degraded"


def test_feedback_and_validation(env):
    client, *_ = env
    mid = dict(ask(client, "What are the prerequisites of CSC-211?"))["done"]["message_id"]
    assert client.post("/api/v1/feedback", json={"message_id": mid, "rating": -1, "comment": "wrong"}).status_code == 200
    assert client.post("/api/v1/feedback", json={"message_id": mid, "rating": 5}).status_code == 422
    assert client.post("/api/v1/feedback", json={"message_id": "f" * 32, "rating": 1}).status_code == 404
    assert client.post("/api/v1/chat/stream", json={"message": "   "}).status_code == 422
    assert client.post("/api/v1/chat/stream", json={"message": "x" * 5000}).status_code == 422
    assert client.get("/api/v1/conversations/../etc/passwd").status_code in (404, 422)


def test_admin_endpoints_require_a_session(env):
    client, *_ = env
    for path in ("/api/v1/admin/settings", "/api/v1/admin/stats", "/api/v1/admin/knowledge", "/api/v1/admin/questions"):
        assert client.get(path).status_code == 401
    assert client.put("/api/v1/admin/settings", json={"values": {}}).status_code == 401
    assert client.get("/api/v1/admin/settings", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def login(client, password="a-long-password"):
    return client.post("/api/v1/admin/login", json={"username": "root", "password": password})


def test_admin_can_set_gemini_key_which_is_never_returned(env):
    client, ctx, _ = env
    token = login(client).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    r = client.put("/api/v1/admin/settings", headers=h, json={"values": {"gemini.api_key": "AIzaSyTESTKEY000111222", "gemini.model": "gemini-2.5-flash"}})
    assert r.status_code == 200 and "TESTKEY" not in r.text
    listed = client.get("/api/v1/admin/settings", headers=h)
    assert "TESTKEY" not in listed.text
    key = next(s for s in listed.json()["settings"] if s["key"] == "gemini.api_key")
    assert key["configured"] and key["hint"].startswith("AIza")
    assert ctx.runtime.get("gemini.api_key") == "AIzaSyTESTKEY000111222"
    # blank secret field means "leave unchanged"
    client.put("/api/v1/admin/settings", headers=h, json={"values": {"gemini.api_key": ""}})
    assert ctx.runtime.get("gemini.api_key") == "AIzaSyTESTKEY000111222"
    bad = client.put("/api/v1/admin/settings", headers=h, json={"values": {"llm.primary": "bing"}})
    assert bad.status_code == 422
    assert client.put("/api/v1/admin/settings", headers=h, json={"values": {"nope": 1}}).status_code == 422


def test_login_lockout_after_repeated_failures(env):
    client, *_ = env
    for _ in range(5):
        assert login(client, "wrong").status_code == 401
    assert login(client).status_code == 429  # even the right password is refused while locked


def test_logout_revokes_the_token(env):
    client, *_ = env
    token = login(client).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/me", headers=h).status_code == 200
    client.post("/api/v1/admin/logout", headers=h)
    assert client.get("/api/v1/admin/me", headers=h).status_code == 401


def test_rate_limit_applies_per_client(tmp_path):
    settings = Settings(data_dir=tmp_path, rate_limit_per_minute=3, rate_limit_burst=3)
    ctx = build_context(settings, load_kb=False)
    bundle = Bundle(None, chunks(), np.zeros((2, 4), dtype=np.float32), {"build_id": "t", "chunks": 2})
    ctx.kb.bundle, ctx.kb.retriever = bundle, Retriever(bundle, None, None)
    ctx.router.candidates = lambda: [FakeProvider()]  # type: ignore[method-assign]
    with TestClient(create_app(ctx)) as client:
        codes = [client.post("/api/v1/chat", json={"message": f"question {i}"}).status_code for i in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429


def test_chat_switch_off_shows_maintenance_message(env):
    client, ctx, provider = env
    ctx.runtime.set("chat.enabled", False)
    done = dict(ask(client, "anything"))["done"]
    assert done["outcome"] == "refused" and provider.calls == []


def test_security_headers_and_public_config(env):
    client, ctx, _ = env
    ctx.runtime.set("assistant.notice", "Classes closed Monday")
    r = client.get("/api/v1/config")
    assert r.json()["notice"] == "Classes closed Monday"
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
