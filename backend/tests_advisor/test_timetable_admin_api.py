import base64
import dataclasses
import json
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from advisor.api import identity
from advisor.api.app import create_app
from advisor.config import Settings
from advisor.context import build_context
from advisor.ingest.model import Chunk
from advisor.rag.timetable_qa import Timetable
from advisor.retrieval.bundle import Bundle
from advisor.retrieval.retriever import Retriever
from advisor.timetable_store import TEMPLATE_CSV

BASE = json.loads((Path(__file__).parent / "data" / "timetable_fall2026.json").read_text())
USERS = {
    "Bearer student-token-000000001": {"id": "u1", "email": "s@example.test", "role": "student"},
    "Bearer admin-token-0000000002": {"id": "u9", "email": "head@example.test", "role": "admin"},
}
ADMIN = {"Authorization": "Bearer admin-token-0000000002"}
STUDENT = {"Authorization": "Bearer student-token-000000001"}
NEW = {"day": "Tuesday", "start": "9:00", "end": "10:30", "room": "Seminar Hall", "program": "BS", "semester": 8,
       "section": "S", "code": "CS-499", "title": "Special Topics", "teacher": "Dr. Test Teacher"}


class Quiet:
    name, model = "fake", "fake-1"

    def __init__(self):
        self.prompts = []

    async def stream(self, messages, params):
        self.prompts.append("\n".join(m.content for m in messages))
        yield "Not a timetable answer [1]."

    async def complete(self, messages, params):
        return "".join([c async for c in self.stream(messages, params)])


@pytest.fixture
def env(tmp_path, monkeypatch):
    identity._clear_cache()
    real = httpx.AsyncClient

    def handler(request):
        user = USERS.get(request.headers.get("authorization", ""))
        return httpx.Response(200, json=user) if user else httpx.Response(401, json={"detail": "no"})

    monkeypatch.setattr(identity.httpx, "AsyncClient", lambda *a, **k: real(*a, transport=httpx.MockTransport(handler), **k))
    settings = Settings(data_dir=tmp_path, auth_verify_url="http://portal.test/me", rate_limit_per_minute=1000, rate_limit_burst=1000)
    ctx = build_context(settings, load_kb=False)
    rows = [dataclasses.asdict(Chunk("c0", "d0", 0, "https://cs.qau.edu.pk/0", "Doc", "page", "h", "Some page", "Some page", {}, 5)),
            dataclasses.asdict(Chunk("c1", "d1", 0, "https://cs.qau.edu.pk/tt.pdf", "CS Department Timetable", "timetable", "h",
                                     "Spring zebra timetable PDFONLYMARKER weekly sessions", "Spring zebra timetable PDFONLYMARKER weekly sessions", {}, 9))]
    bundle = Bundle(None, rows, np.zeros((2, 4), dtype=np.float32), {"build_id": "t", "chunks": 2})
    bundle.timetable = Timetable.from_json(json.loads(json.dumps(BASE)))
    ctx.kb.bundle, ctx.kb.retriever = bundle, Retriever(bundle, None, None)
    provider = Quiet()
    ctx.router.candidates = lambda: [provider]  # type: ignore[method-assign]
    with TestClient(create_app(ctx)) as client:
        client.provider = provider
        yield client


def chat(client, q):
    r = client.post("/api/v1/chat", json={"message": q, "ephemeral": True})
    assert r.status_code == 200, r.text
    return r.json()["answer"]


def test_only_administrators_can_see_or_change_the_timetable(env):
    assert env.get("/api/v1/admin/timetable").status_code == 401
    assert env.get("/api/v1/admin/timetable", headers=STUDENT).status_code == 401
    assert env.post("/api/v1/admin/timetable/sessions", json=NEW, headers=STUDENT).status_code == 401
    assert env.get("/api/v1/admin/timetable", headers=ADMIN).status_code == 200


def test_view_lists_pdf_sessions_with_their_class_teacher_and_room(env):
    view = env.get("/api/v1/admin/timetable", headers=ADMIN).json()
    assert view["mode"] == "pdf_plus_edits" and view["counts"]["pdf"] == len(BASE["sessions"]) and view["pdf"]["available"]
    iis = next(r for r in view["sessions"] if r["code"] == "CS-413" and r["day"] == "MONDAY")
    assert iis["teacher"] == "Dr. Muazzam Khattak" and iis["room"] == "217" and iis["start"] == "11:55" and "VIII" in iis["class"]


def test_adding_a_session_changes_what_students_are_told_at_once(env):
    assert "Special Topics" not in chat(env, "Tuesday classes for semester 8")
    saved = env.post("/api/v1/admin/timetable/sessions", json=NEW, headers=ADMIN).json()
    assert saved["saved"] is True
    answer = chat(env, "Tuesday classes for semester 8")
    assert "Special Topics" in answer and "Dr. Test Teacher" in answer and "Updated by the department" in answer


def test_a_clash_is_returned_as_a_warning_and_only_saved_when_forced(env):
    busy = next(s for s in BASE["sessions"] if s["day"] == "MONDAY" and s["room"] == "217")
    a, b = busy["time"].split("-")
    body = {**NEW, "day": "Monday", "room": "217", "start": a, "end": b, "teacher": "Dr. Someone Else"}
    first = env.post("/api/v1/admin/timetable/sessions", json=body, headers=ADMIN).json()
    assert first["saved"] is False and first["warnings"]
    assert env.get("/api/v1/admin/timetable", headers=ADMIN).json()["counts"]["manual"] == 0
    assert env.post("/api/v1/admin/timetable/sessions", json={**body, "force": True}, headers=ADMIN).json()["saved"] is True


def test_invalid_input_is_a_clear_422(env):
    r = env.post("/api/v1/admin/timetable/sessions", json={**NEW, "start": "11:00", "end": "10:00"}, headers=ADMIN)
    assert r.status_code == 422 and "end time must be after" in r.json()["detail"]
    assert env.post("/api/v1/admin/timetable/sessions", json={**NEW, "day": "Funday"}, headers=ADMIN).status_code == 422
    assert env.put("/api/v1/admin/timetable/sessions/doesnotexist", json={"room": "F6"}, headers=ADMIN).status_code == 422
    assert env.delete("/api/v1/admin/timetable/sessions/doesnotexist", headers=ADMIN).status_code == 422


def test_edit_hide_restore_and_undo_a_pdf_session(env):
    view = env.get("/api/v1/admin/timetable", headers=ADMIN).json()
    sid = next(r["id"] for r in view["sessions"] if r["code"] == "CS-535" and r["day"] == "MONDAY")
    r = env.put(f"/api/v1/admin/timetable/sessions/{sid}", json={"room": "Seminar Hall", "force": True}, headers=ADMIN)
    assert r.json()["saved"] is True and "Seminar Hall" in chat(env, "Monday classes for semester 8")
    env.delete(f"/api/v1/admin/timetable/sessions/{sid}", headers=ADMIN)
    assert "CS-535" not in chat(env, "Monday classes for semester 8")
    assert env.get("/api/v1/admin/timetable", headers=ADMIN).json()["counts"]["hidden"] == 1
    env.post(f"/api/v1/admin/timetable/sessions/{sid}/restore", headers=ADMIN)
    assert "CS-535" in chat(env, "Monday classes for semester 8")
    assert env.post("/api/v1/admin/timetable/undo", headers=ADMIN).status_code == 200  # undoes the restore → hidden again
    assert "CS-535" not in chat(env, "Monday classes for semester 8")
    history = env.get("/api/v1/admin/timetable", headers=ADMIN).json()["history"]
    assert history[0]["by"] == "head@example.test" and history[0]["action"] == "restore PDF session" and history[0]["undone"]


def test_course_teacher_and_settings_endpoints(env):
    view = env.get("/api/v1/admin/timetable", headers=ADMIN).json()
    course = next(c for c in view["courses"] if c["code"] == "CS-413")
    r = env.put("/api/v1/admin/timetable/courses", json={"group": course["group"], "label": course["label"], "teacher": "Dr. Newman Teacher"}, headers=ADMIN)
    assert r.status_code == 200 and "Dr. Newman Teacher" in chat(env, "monday ko 8th semester ki classes")
    assert env.put("/api/v1/admin/timetable/courses", json={"group": "Nope", "label": "X", "teacher": "Y"}, headers=ADMIN).status_code == 422
    s = env.put("/api/v1/admin/timetable/settings", json={"term": "Fall 2026 (revised)", "effective": "19 Oct 2026"}, headers=ADMIN).json()
    assert s["term"] == "Fall 2026 (revised)" and "19 Oct 2026" in chat(env, "Monday classes for semester 8")
    assert env.put("/api/v1/admin/timetable/settings", json={"mode": "bogus"}, headers=ADMIN).status_code == 422


def test_reset_to_pdf_removes_every_edit_and_is_undoable(env):
    env.post("/api/v1/admin/timetable/sessions", json=NEW, headers=ADMIN)
    env.put("/api/v1/admin/timetable/settings", json={"term": "Changed"}, headers=ADMIN)
    assert env.post("/api/v1/admin/timetable/reset", headers=ADMIN).status_code == 200
    view = env.get("/api/v1/admin/timetable", headers=ADMIN).json()
    assert view["counts"]["manual"] == 0 and view["term"] == BASE["term"]
    env.post("/api/v1/admin/timetable/undo", headers=ADMIN)
    assert env.get("/api/v1/admin/timetable", headers=ADMIN).json()["term"] == "Changed"


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def test_import_preview_then_apply_and_export(env):
    csv_text = TEMPLATE_CSV + "Someday,9:00,10:00,F6,BS,8,S,CS-1,x,y\n"
    preview = env.post("/api/v1/admin/timetable/import", json={"filename": "t.csv", "content_base64": _b64(csv_text)}, headers=ADMIN).json()
    assert preview["applied"] is False and preview["ok_rows"] == 2 and preview["error_count"] == 1 and preview["errors"][0]["row"] == 4
    assert env.get("/api/v1/admin/timetable", headers=ADMIN).json()["counts"]["manual"] == 0  # preview changes nothing
    refused = env.post("/api/v1/admin/timetable/import", json={"filename": "t.csv", "content_base64": _b64(csv_text), "dry_run": False}, headers=ADMIN)
    assert refused.status_code == 422 and "problems" in refused.json()["detail"]
    ok = env.post("/api/v1/admin/timetable/import", json={"filename": "t.csv", "content_base64": _b64(csv_text), "dry_run": False, "skip_errors": True}, headers=ADMIN).json()
    assert ok["applied"] is True
    assert env.get("/api/v1/admin/timetable", headers=ADMIN).json()["counts"]["manual"] == 2
    export = env.get("/api/v1/admin/timetable/export", headers=ADMIN).json()
    assert export["filename"].endswith(".csv") and "Dr. Muazzam Khattak" in export["csv"]
    assert env.get("/api/v1/admin/timetable/template", headers=ADMIN).json()["csv"] == TEMPLATE_CSV


def test_import_rejects_bad_files(env):
    post = lambda **kw: env.post("/api/v1/admin/timetable/import", json=kw, headers=ADMIN)  # noqa: E731
    assert post(filename="x.exe", content_base64=_b64("abc")).status_code == 422
    assert post(filename="x.csv", content_base64="!!notbase64!!").status_code == 422
    assert post(filename="x.xlsx", content_base64=_b64("not a zip")).json()["errors"][0]["message"].startswith("This is not a valid .xlsx")
    big = _b64("a" * (2 * 1024 * 1024 + 10))
    assert post(filename="x.csv", content_base64=big).status_code == 413


def test_manual_only_mode_replaces_the_pdf_completely(env):
    env.put("/api/v1/admin/timetable/settings", json={"mode": "manual_only", "term": "Spring 2027"}, headers=ADMIN)
    env.post("/api/v1/admin/timetable/sessions", json=NEW, headers=ADMIN)
    answer = chat(env, "Tuesday classes for semester 8")
    assert "Special Topics" in answer and "Spring 2027" in answer
    assert "CS-413" not in chat(env, "Monday classes for semester 8")  # the PDF is ignored
    sources = env.post("/api/v1/chat", json={"message": "Tuesday classes for semester 8", "ephemeral": True}).json()["sources"]
    assert sources and sources[0]["kind"] == "department timetable"


def test_in_manual_only_mode_pdf_timetable_text_never_reaches_the_model(env):
    ask = lambda: env.post("/api/v1/chat", json={"message": "tell me about the spring zebra weekly sessions", "ephemeral": True}).status_code  # noqa: E731
    assert ask() == 200
    assert "PDFONLYMARKER" in env.provider.prompts[-1]  # normally the PDF text is available to the model
    env.put("/api/v1/admin/timetable/settings", json={"mode": "manual_only"}, headers=ADMIN)
    assert ask() == 200
    assert "PDFONLYMARKER" not in env.provider.prompts[-1]


def test_a_timetable_change_clears_cached_answers(env):
    q = {"message": "tell me about the spring zebra weekly sessions", "ephemeral": True}
    env.post("/api/v1/chat", json=q)
    n = len(env.provider.prompts)
    env.post("/api/v1/chat", json=q)
    assert len(env.provider.prompts) == n  # identical question: served from the cache
    env.post("/api/v1/admin/timetable/sessions", json=NEW, headers=ADMIN)
    env.post("/api/v1/chat", json=q)
    assert len(env.provider.prompts) == n + 1  # the change cleared the cache, so the model is asked again
