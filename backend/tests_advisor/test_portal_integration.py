import dataclasses
import json

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from advisor.api import identity
from advisor.api.app import create_app
from advisor.config import Settings
from advisor.context import build_context
from advisor.ingest.model import Chunk
from advisor.retrieval.bundle import Bundle
from advisor.retrieval.retriever import Retriever

USERS = {
    "Bearer student-a-token-0001": {"id": "u1", "email": "a@example.test", "role": "student", "full_name": "A"},
    "Bearer student-b-token-0002": {"id": "u2", "email": "b@example.test", "role": "student", "full_name": "B"},
    "Bearer admin-token-000000003": {"id": "u9", "email": "root@example.test", "role": "admin"},
}
A = {"Authorization": "Bearer student-a-token-0001"}
B = {"Authorization": "Bearer student-b-token-0002"}
ADMIN = {"Authorization": "Bearer admin-token-000000003"}


class Echo:
    name, model = "fake", "fake-1"

    def __init__(self):
        self.prompts = []

    async def stream(self, messages, params):
        self.prompts.append(messages)
        yield "The prerequisite is CSC-121 [1]."

    async def complete(self, messages, params):
        return "".join([c async for c in self.stream(messages, params)])


@pytest.fixture
def env(tmp_path, monkeypatch):
    identity._clear_cache()
    real = httpx.AsyncClient

    def handler(request: httpx.Request):
        user = USERS.get(request.headers.get("authorization", ""))
        return httpx.Response(200, json=user) if user else httpx.Response(401, json={"detail": "no"})

    monkeypatch.setattr(identity.httpx, "AsyncClient", lambda *a, **k: real(*a, transport=httpx.MockTransport(handler), **k))
    settings = Settings(data_dir=tmp_path, auth_verify_url="http://portal.test/auth/me", rate_limit_per_minute=1000, rate_limit_burst=1000)
    ctx = build_context(settings, load_kb=False)
    rows = [dataclasses.asdict(Chunk("c0", "d0", 0, "https://cs.qau.edu.pk/0", "Doc", "course", "h",
            "Course CSC-211: Data Structures\nPrerequisites: CSC-121", "Course CSC-211: Data Structures Prerequisites CSC-121",
            {"course_code": "CSC-211", "course_name": "Data Structures"}, 5))]
    bundle = Bundle(None, rows, np.zeros((1, 4), dtype=np.float32), {"build_id": "t", "chunks": 1})
    ctx.kb.bundle, ctx.kb.retriever = bundle, Retriever(bundle, None, None)
    provider = Echo()
    ctx.router.candidates = lambda: [provider]  # type: ignore[method-assign]
    with TestClient(create_app(ctx)) as client:
        yield client, ctx, provider


def chat(client, q, headers=None, **extra):
    r = client.post("/api/v1/chat", json={"message": q, **extra}, headers=headers or {})
    assert r.status_code == 200, r.text
    return r.json()


def test_signed_in_conversations_are_listed_titled_and_persisted(env):
    client, ctx, _ = env
    first = chat(client, "What are the prerequisites of Data Structures?", A)
    chat(client, "and the credits?", A, conversation_id=first["conversation_id"])
    listing = client.get("/api/v1/me/conversations", headers=A).json()["conversations"]
    assert len(listing) == 1 and listing[0]["title"].startswith("What are the prerequisites")
    msgs = client.get(f"/api/v1/conversations/{first['conversation_id']}", headers=A).json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]


def test_a_student_cannot_read_or_continue_another_students_conversation(env):
    client, ctx, _ = env
    cid = chat(client, "What are the prerequisites of Data Structures?", A)["conversation_id"]
    assert client.get(f"/api/v1/conversations/{cid}", headers=B).status_code == 404
    assert client.get(f"/api/v1/conversations/{cid}").status_code == 404  # anonymous either
    hijack = chat(client, "hello there friend", B, conversation_id=cid)
    assert hijack["conversation_id"] != cid  # B gets a fresh conversation, A's is untouched
    assert len(client.get("/api/v1/me/conversations", headers=A).json()["conversations"]) == 1


def test_my_conversations_requires_a_verified_session(env):
    client, *_ = env
    assert client.get("/api/v1/me/conversations").status_code == 401
    assert client.get("/api/v1/me/conversations", headers={"Authorization": "Bearer forged-token-000000"}).status_code == 401


def test_guest_conversations_are_not_stored_at_all(env):
    client, ctx, provider = env
    history = [{"role": "user", "content": "Tell me about CSC-211"}, {"role": "assistant", "content": "It is Data Structures."}]
    out = chat(client, "What are its prerequisites?", ephemeral=True, history=history)
    assert out["conversation_id"] is None and "CSC-121" in out["answer"]
    assert ctx.db.scalar("SELECT COUNT(*) FROM messages", default=0) == 0
    assert ctx.db.scalar("SELECT COUNT(*) FROM conversations", default=0) == 0
    roles = [m.role for m in provider.prompts[-1]]
    assert roles.count("assistant") >= 1  # the browser-supplied history reached the model
    row = ctx.db.one("SELECT question FROM query_log ORDER BY id DESC")
    assert "not stored" in row["question"]  # not even the text of an answered question is kept


def test_guest_question_that_cannot_be_answered_is_logged_without_identity(env):
    client, ctx, provider = env

    async def nothing(messages, params):
        yield "I couldn't find that in the department's published pages."

    provider.stream = nothing  # type: ignore[method-assign]
    chat(client, "what is the wifi password", ephemeral=True)
    row = ctx.db.one("SELECT question, outcome FROM query_log ORDER BY id DESC")
    assert row["outcome"] == "abstained" and row["question"] == "what is the wifi password"
    assert ctx.db.scalar("SELECT COUNT(*) FROM messages", default=0) == 0


def test_urdu_toggle_sets_the_reply_language(env):
    client, _, provider = env
    chat(client, "What are the prerequisites of Data Structures?", language="urdu", ephemeral=True)
    assert "Urdu" in provider.prompts[-1][-1].content


def test_history_page_search_and_clear(env):
    client, *_ = env
    chat(client, "What are the prerequisites of Data Structures?", A)
    chat(client, "hello", B)
    rows = client.get("/api/v1/me/history?search=prerequisites", headers=A).json()
    assert rows and all("prerequisites" in r["content"].lower() for r in rows)
    assert client.get("/api/v1/me/history", headers=B).json() and not any("Data Structures" in r["content"] for r in client.get("/api/v1/me/history", headers=B).json() if r["role"] == "user")
    assert client.delete("/api/v1/me/history", headers=A).status_code == 200
    assert client.get("/api/v1/me/history", headers=A).json() == []
    assert client.get("/api/v1/me/history", headers=B).json()  # B's history survives A's clear


def test_feedback_component_routes_and_owner_check(env):
    client, ctx, _ = env
    mid = chat(client, "What are the prerequisites of Data Structures?", A)["message_id"]
    assert client.put(f"/api/v1/feedback/{mid}", json={"rating": -1, "reason": "outdated"}, headers=B).status_code == 404
    assert client.put(f"/api/v1/feedback/{mid}", json={"rating": -1, "reason": "outdated"}, headers=A).status_code == 200
    row = ctx.db.one("SELECT rating, reason FROM feedback WHERE message_id=?", (mid,))
    assert (row["rating"], row["reason"]) == (-1, "outdated")
    assert client.put(f"/api/v1/feedback/{mid}", json={"rating": 7}, headers=A).status_code == 422
    assert client.delete(f"/api/v1/feedback/{mid}", headers=A).status_code == 200
    assert ctx.db.one("SELECT 1 FROM feedback WHERE message_id=?", (mid,)) is None


def test_portal_admin_can_manage_the_chatbot_without_a_second_login(env):
    client, *_ = env
    assert client.get("/api/v1/admin/settings", headers=ADMIN).status_code == 200
    assert client.get("/api/v1/admin/settings", headers=A).status_code == 401  # a student is not an admin
    assert client.get("/api/v1/admin/settings", headers={"Authorization": "Bearer forged-admin-token-0"}).status_code == 401
    pw = client.post("/api/v1/admin/password", headers=ADMIN, json={"current_password": "x", "new_password": "y" * 12})
    assert pw.status_code == 403  # SSO admins change their password in the portal


def test_sso_is_off_unless_configured(tmp_path):
    identity._clear_cache()
    ctx = build_context(Settings(data_dir=tmp_path), load_kb=False)
    with TestClient(create_app(ctx)) as client:
        assert client.get("/api/v1/me/conversations", headers=ADMIN).status_code == 401
        assert client.get("/api/v1/admin/settings", headers=ADMIN).status_code == 401
