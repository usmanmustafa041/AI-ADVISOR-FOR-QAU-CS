"""Administrator endpoints: sign-in, AI provider settings, knowledge refresh, analytics."""

from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from advisor.api.deps import admin_required, client_ip, get_ctx
from advisor.context import Context
from advisor.knowledge_build import refresh_knowledge
from advisor.llm.base import GenParams, Message, ProviderError
from advisor.llm.gemini import GeminiProvider
from advisor.llm.ollama import OllamaProvider
from advisor.retrieval.bundle import list_builds, load_bundle, set_current
from advisor.runtime_settings import SPECS
from advisor.security import hash_password, new_token, token_hash, verify_password

log = logging.getLogger("advisor.admin")
router = APIRouter(prefix="/api/v1/admin")

MAX_FAILED = 5
LOCK_SECONDS = 300


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class SettingsIn(BaseModel):
    values: dict[str, object] = Field(default_factory=dict)
    clear: list[str] = Field(default_factory=list)


class VerifyGeminiIn(BaseModel):
    api_key: str | None = Field(default=None, max_length=256)
    model: str | None = Field(default=None, max_length=100)


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=256)


class RefreshIn(BaseModel):
    crawl: bool = True


class RollbackIn(BaseModel):
    build_id: str


# ---------------------------------------------------------------------------- auth
@router.post("/login")
async def login(body: LoginIn, request: Request, ctx: Context = Depends(get_ctx)):
    row = ctx.db.one("SELECT * FROM admins WHERE username=?", (body.username,))
    now = time.time()
    if row and row["locked_until"] and row["locked_until"] > now:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")
    # constant-ish work whether or not the user exists
    stored = row["password_hash"] if row else hash_password("not-a-real-password")
    ok = verify_password(body.password, stored) and row is not None
    if not ok:
        if row:
            failed = row["failed_logins"] + 1
            locked = now + LOCK_SECONDS if failed >= MAX_FAILED else None
            ctx.db.execute(
                "UPDATE admins SET failed_logins=?, locked_until=? WHERE id=?",
                (0 if locked else failed, locked, row["id"]),
            )
        log.warning("failed admin login for %r from %s", body.username, client_ip(request))
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = new_token()
    expires = now + ctx.settings.session_hours * 3600
    ctx.db.execute(
        "INSERT INTO admin_sessions(token_hash, admin_id, expires_at) VALUES(?,?,?)",
        (token_hash(token), row["id"], expires),
    )
    ctx.db.execute(
        "UPDATE admins SET failed_logins=0, locked_until=NULL, last_login_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
        (row["id"],),
    )
    ctx.db.execute("DELETE FROM admin_sessions WHERE expires_at < ?", (now,))
    return {"token": token, "expires_at": expires, "username": row["username"]}


@router.post("/logout")
async def logout(request: Request, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    token = request.headers.get("authorization", "")[7:].strip()
    ctx.db.execute("DELETE FROM admin_sessions WHERE token_hash=?", (token_hash(token),))
    return {"ok": True}


@router.get("/me")
async def me(admin=Depends(admin_required)):
    return admin


@router.post("/password")
async def change_password(body: PasswordIn, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    if admin.get("sso"):
        raise HTTPException(status_code=403, detail="You are signed in through the portal; change the password there")
    row = ctx.db.one("SELECT password_hash FROM admins WHERE id=?", (admin["id"],))
    if not verify_password(body.current_password, row["password_hash"]):
        raise HTTPException(status_code=403, detail="Current password is incorrect")
    ctx.db.execute("UPDATE admins SET password_hash=? WHERE id=?", (hash_password(body.new_password), admin["id"]))
    ctx.db.execute("DELETE FROM admin_sessions WHERE admin_id=?", (admin["id"],))  # sign out everywhere
    return {"ok": True}


# ---------------------------------------------------------------------------- settings
@router.get("/settings")
async def get_settings(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    return {"settings": ctx.runtime.public_view()}


@router.put("/settings")
async def put_settings(body: SettingsIn, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    changed = []
    try:
        for key, value in body.values.items():
            spec = SPECS.get(key)
            if spec is None:
                raise HTTPException(status_code=422, detail=f"Unknown setting: {key}")
            if spec.secret and (value is None or str(value).strip() == ""):
                continue  # blank secret field = leave unchanged
            ctx.runtime.set(key, value, admin["username"])
            changed.append(key)
        for key in body.clear:
            spec = SPECS.get(key)
            if spec is None or not spec.secret:
                raise HTTPException(status_code=422, detail=f"Cannot clear: {key}")
            ctx.runtime.set(key, "", admin["username"])
            changed.append(key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # A new key/model deserves an immediate try, and old answers may no longer apply.
    for provider in ("gemini", "ollama"):
        if any(k.startswith(provider) or k == "llm.primary" for k in changed):
            ctx.router.health.pop(provider, None)
    ctx.service.cache.clear()
    return {"changed": changed, "settings": ctx.runtime.public_view()}


# ---------------------------------------------------------------------------- AI providers
@router.get("/providers")
async def providers(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    return {"providers": await ctx.router.statuses()}


@router.post("/providers/gemini/verify")
async def verify_gemini(body: VerifyGeminiIn, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    """Check a key (typed in the form, or the saved one) before saving it."""
    key = (body.api_key or "").strip() or ctx.runtime.get("gemini.api_key")
    if not key:
        raise HTTPException(status_code=422, detail="Enter a Gemini API key first")
    model = (body.model or "").strip() or ctx.runtime.get("gemini.model")
    provider = GeminiProvider(key, model)
    status = await provider.status()
    return {
        "ok": status.healthy, "detail": status.detail, "model": model,
        "models": [m for m in status.models if "gemini" in m],
    }


@router.post("/providers/test")
async def test_providers(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    """Send a tiny real request through every configured provider and report the outcome."""
    results = []
    probe = [Message("user", "Reply with exactly: OK")]
    params = GenParams(temperature=0, max_tokens=20, timeout=60)
    for provider in ctx.router.candidates():
        started = time.monotonic()
        try:
            text = await asyncio.wait_for(provider.complete(probe, params), timeout=70)
            results.append(
                {
                    "provider": provider.name, "model": provider.model, "ok": bool(text.strip()),
                    "ms": int((time.monotonic() - started) * 1000), "reply": text.strip()[:60],
                }
            )
        except (ProviderError, TimeoutError) as exc:
            results.append(
                {
                    "provider": provider.name, "model": provider.model, "ok": False,
                    "ms": int((time.monotonic() - started) * 1000),
                    "error": exc.message if isinstance(exc, ProviderError) else "timed out",
                    "kind": exc.kind if isinstance(exc, ProviderError) else "timeout",
                }
            )
    active = next((r["provider"] for r in results if r["ok"]), None)
    return {"results": results, "active": active}


@router.get("/providers/ollama/models")
async def ollama_models(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    p = OllamaProvider(ctx.runtime.get("ollama.base_url"), ctx.runtime.get("ollama.model"))
    try:
        return {"models": await p.installed_models()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ollama not reachable: {exc}") from exc


# ---------------------------------------------------------------------------- knowledge
def _run_refresh(ctx: Context, job_id: int, crawl: bool) -> None:
    def progress(msg: str) -> None:
        ctx.db.execute("UPDATE jobs SET detail=? WHERE id=?", (msg, job_id))

    try:
        result = refresh_knowledge(ctx.settings, crawl=crawl, progress=progress)
        ctx.kb.load()
        ctx.service.cache.clear()
        ctx.db.execute(
            "UPDATE jobs SET status='done', finished_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), detail=? WHERE id=?",
            (json.dumps(result, default=str), job_id),
        )
    except Exception as exc:
        log.exception("knowledge refresh failed")
        ctx.db.execute(
            "UPDATE jobs SET status='failed', finished_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), detail=? WHERE id=?",
            (f"{type(exc).__name__}: {exc}"[:800], job_id),
        )


@router.get("/knowledge")
async def knowledge(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    jobs = ctx.db.all("SELECT * FROM jobs ORDER BY id DESC LIMIT 10")
    builds = list_builds(ctx.settings.index_dir)
    docs = {}
    if ctx.kb.bundle:
        for c in ctx.kb.bundle.chunks:
            d = docs.setdefault(c["url"], {"url": c["url"], "title": c["title"], "kind": c["kind"], "chunks": 0})
            d["chunks"] += 1
    return {
        "info": ctx.kb.info(),
        "builds": builds,
        "jobs": [dict(j) for j in jobs],
        "documents": sorted(docs.values(), key=lambda d: (d["kind"], d["url"])),
    }


@router.post("/knowledge/refresh", status_code=202)
async def refresh(
    body: RefreshIn, tasks: BackgroundTasks, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)
):
    running = ctx.db.one("SELECT id FROM jobs WHERE status='running' AND kind='refresh'")
    if running:
        raise HTTPException(status_code=409, detail="A refresh is already running")
    job_id = ctx.db.execute(
        "INSERT INTO jobs(kind, status, detail) VALUES('refresh','running','starting')"
    ).lastrowid
    tasks.add_task(asyncio.to_thread, _run_refresh, ctx, job_id, body.crawl)
    return {"job_id": job_id}


@router.post("/knowledge/rollback")
async def rollback(body: RollbackIn, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    if body.build_id not in list_builds(ctx.settings.index_dir):
        raise HTTPException(status_code=404, detail="Unknown build")
    if load_bundle(ctx.settings.index_dir, body.build_id) is None:
        raise HTTPException(status_code=422, detail="That build is incomplete")
    set_current(ctx.settings.index_dir, body.build_id)
    await asyncio.to_thread(ctx.kb.load)
    ctx.service.cache.clear()
    return {"ok": True, "info": ctx.kb.info()}


# ---------------------------------------------------------------------------- prerequisite data
class PrereqUploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=80)
    content: dict


def _prereq_dir(ctx: Context):
    d = ctx.settings.data_dir / "prerequisites"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("/prerequisites")
async def prerequisites(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    from advisor.ingest.pipeline import prerequisite_files
    from advisor.prereq.graph import conflicts
    from advisor.prereq.verify import verify

    bundled = {f.name for f in prerequisite_files(None)}
    files = []
    for f in prerequisite_files(_prereq_dir(ctx)):
        doc = f.with_suffix(".docx")
        r = verify(f, doc if doc.exists() else None)
        files.append({
            "name": f.name, "bundled": f.name in bundled, "stats": r["stats"],
            "errors": r["errors"][:10], "warnings": r["warnings"][:10],
        })
    graph = ctx.kb.bundle.prereq if ctx.kb.bundle else None
    return {
        "files": files,
        "live": {
            "courses": len(graph.courses), "edges": len(graph.edges),
            "sources": [v["label"] for v in graph.sources.values()],
        } if graph else None,
        "conflicts": conflicts(graph) if graph else [],
        "notes": (ctx.kb.bundle.manifest.get("prerequisites") if ctx.kb.bundle else []),
    }


@router.post("/prerequisites")
async def upload_prerequisites(body: PrereqUploadIn, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    """Add a prerequisite file in the agreed JSON schema (for other schemes/batches)."""
    import re as _re
    import tempfile
    from pathlib import Path as _Path

    from advisor.prereq.verify import verify

    name = _re.sub(r"[^A-Za-z0-9_.-]+", "_", body.filename).strip("._") or "prerequisites"
    if not name.endswith(".json"):
        name += ".json"
    data = body.content
    if not isinstance(data.get("courses"), list) or not isinstance(data.get("prerequisites"), list):
        raise HTTPException(status_code=422, detail="File must contain 'courses' and 'prerequisites' lists")
    text = json.dumps(data, ensure_ascii=False)
    if len(text) > 4_000_000:
        raise HTTPException(status_code=413, detail="File is too large")
    with tempfile.TemporaryDirectory() as tmp:
        probe = _Path(tmp) / name
        probe.write_text(text)
        result = verify(probe, None)
    if result["errors"]:
        raise HTTPException(status_code=422, detail={"message": "Rows failed validation", "errors": result["errors"][:25]})
    (_prereq_dir(ctx) / name).write_text(text)
    return {"saved": name, "stats": result["stats"], "warnings": result["warnings"][:10], "needs_rebuild": True}


@router.delete("/prerequisites/{name}")
async def delete_prerequisites(name: str, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    target = _prereq_dir(ctx) / name
    if "/" in name or name.startswith(".") or not target.exists():
        raise HTTPException(status_code=404, detail="File not found (bundled files cannot be removed)")
    target.unlink()
    return {"deleted": name, "needs_rebuild": True}


# ---------------------------------------------------------------------------- department documents
class DocUploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    content_base64: str = Field(min_length=4)
    title: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=500)
    effective: str | None = Field(default=None, max_length=80)


def _docs_dir(ctx: Context):
    d = ctx.settings.data_dir / "documents"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("/documents")
async def department_documents(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    out = []
    for f in sorted(_docs_dir(ctx).iterdir()):
        if f.name.endswith(".meta.json") or f.name.startswith("."):
            continue
        side = f.with_name(f.name + ".meta.json")
        meta = json.loads(side.read_text()) if side.exists() else {}
        out.append({"name": f.name, "size": f.stat().st_size, **meta})
    return {"documents": out}


@router.post("/documents")
async def upload_document(body: DocUploadIn, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    import base64
    import binascii
    import re as _re
    from pathlib import Path as _Path

    from advisor.ingest.local_docs import SUPPORTED

    name = _re.sub(r"[^A-Za-z0-9_. -]+", "_", _Path(body.filename).name).strip("._ ")
    if _Path(name).suffix.lower() not in SUPPORTED:
        raise HTTPException(status_code=422, detail=f"Supported types: {', '.join(sorted(SUPPORTED))}")
    try:
        raw = base64.b64decode(body.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="File content is not valid base64") from exc
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File is larger than 15 MB")
    ext = _Path(name).suffix.lower()
    magic_ok = (
        raw.startswith(b"%PDF") if ext == ".pdf" else raw.startswith(b"PK") if ext == ".docx" else b"\x00" not in raw[:2000]
    )
    if not magic_ok:
        raise HTTPException(status_code=422, detail="The file content does not match its extension")
    target = _docs_dir(ctx) / name
    target.write_bytes(raw)
    side = {k: v for k, v in (("title", body.title), ("note", body.note), ("effective", body.effective)) if v}
    side_path = target.with_name(target.name + ".meta.json")
    if side:
        side_path.write_text(json.dumps(side, ensure_ascii=False))
    elif side_path.exists():
        side_path.unlink()
    return {"saved": name, "needs_rebuild": True}


@router.delete("/documents/{name}")
async def delete_document(name: str, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    target = _docs_dir(ctx) / name
    if "/" in name or name.startswith(".") or not target.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    target.unlink()
    side = target.with_name(target.name + ".meta.json")
    if side.exists():
        side.unlink()
    return {"deleted": name, "needs_rebuild": True}


@router.post("/cache/clear")
async def clear_cache(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    ctx.service.cache.clear()
    return {"ok": True}


# ---------------------------------------------------------------------------- analytics
def _pct(values: list[int], p: float) -> int | None:
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


@router.get("/stats")
async def stats(days: int = 7, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    days = max(1, min(days, 90))
    since = f"-{days} days"
    db = ctx.db
    total = db.scalar("SELECT COUNT(*) FROM query_log WHERE created_at >= datetime('now', ?)", (since,), 0)
    outcomes = {
        r["outcome"]: r["n"]
        for r in db.all(
            "SELECT outcome, COUNT(*) n FROM query_log WHERE created_at >= datetime('now', ?) GROUP BY outcome",
            (since,),
        )
    }
    providers = {
        (r["provider"] or "none"): r["n"]
        for r in db.all(
            "SELECT provider, COUNT(*) n FROM query_log WHERE created_at >= datetime('now', ?) "
            "AND outcome IN ('answered','abstained','degraded') GROUP BY provider",
            (since,),
        )
    }
    langs = {
        (r["language"] or "?"): r["n"]
        for r in db.all(
            "SELECT language, COUNT(*) n FROM query_log WHERE created_at >= datetime('now', ?) GROUP BY language",
            (since,),
        )
    }
    lat = [
        r[0]
        for r in db.all(
            "SELECT latency_ms FROM query_log WHERE created_at >= datetime('now', ?) "
            "AND outcome='answered' AND latency_ms IS NOT NULL",
            (since,),
        )
    ]
    daily = [
        dict(r)
        for r in db.all(
            "SELECT date(created_at) day, COUNT(*) n FROM query_log WHERE created_at >= datetime('now', ?) "
            "GROUP BY day ORDER BY day",
            (since,),
        )
    ]
    fb = db.one(
        "SELECT SUM(rating=1) up, SUM(rating=-1) down FROM feedback WHERE created_at >= datetime('now', ?)",
        (since,),
    )
    return {
        "days": days, "total": total, "outcomes": outcomes, "providers": providers, "languages": langs,
        "latency_ms": {"p50": _pct(lat, 0.5), "p95": _pct(lat, 0.95)},
        "daily": daily,
        "feedback": {"up": fb["up"] or 0, "down": fb["down"] or 0},
        "index": ctx.kb.info(),
    }


@router.get("/questions")
async def questions(
    outcome: str = "", limit: int = 100, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)
):
    limit = max(1, min(limit, 500))
    sql = "SELECT id, created_at, question, language, outcome, provider, latency_ms, sources FROM query_log"
    params: tuple = ()
    if outcome:
        sql += " WHERE outcome=?"
        params = (outcome,)
    sql += " ORDER BY id DESC LIMIT ?"
    rows = ctx.db.all(sql, (*params, limit))
    return {"questions": [dict(r) for r in rows]}


@router.get("/feedback")
async def feedback_list(limit: int = 100, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    rows = ctx.db.all(
        "SELECT f.id, f.created_at, f.rating, f.comment, f.message_id, "
        "(SELECT content FROM messages WHERE id=f.message_id) answer, "
        "(SELECT content FROM messages m2 WHERE m2.conversation_id="
        " (SELECT conversation_id FROM messages WHERE id=f.message_id) AND m2.role='user' "
        " AND m2.created_at <= (SELECT created_at FROM messages WHERE id=f.message_id) "
        " ORDER BY m2.created_at DESC, m2.rowid DESC LIMIT 1) question "
        "FROM feedback f ORDER BY f.id DESC LIMIT ?",
        (max(1, min(limit, 500)),),
    )
    return {"feedback": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------- timetable (manual edits over the PDF)
from advisor.timetable_store import (  # noqa: E402
    MAX_IMPORT_BYTES, TEMPLATE_CSV, TimetableError, parse_csv, parse_xlsx,
)


class TTSessionIn(BaseModel):
    day: str = Field(max_length=20)
    start: str = Field(max_length=12)
    end: str = Field(max_length=12)
    room: str = Field(max_length=60)
    program: str = Field(default="BS", max_length=20)
    semester: int | None = None
    section: str = Field(default="", max_length=30)
    code: str = Field(default="", max_length=20)
    title: str = Field(default="", max_length=160)
    teacher: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=300)
    force: bool = False  # save even when the room/teacher clashes with another class


class TTSessionPatch(BaseModel):
    day: str | None = Field(default=None, max_length=20)
    start: str | None = Field(default=None, max_length=12)
    end: str | None = Field(default=None, max_length=12)
    room: str | None = Field(default=None, max_length=60)
    program: str | None = Field(default=None, max_length=20)
    semester: int | None = None
    section: str | None = Field(default=None, max_length=30)
    code: str | None = Field(default=None, max_length=20)
    title: str | None = Field(default=None, max_length=160)
    teacher: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=300)
    force: bool = False


class TTCourseIn(BaseModel):
    group: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    teacher: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=160)


class TTSettingsIn(BaseModel):
    mode: str | None = Field(default=None, max_length=30)
    term: str | None = Field(default=None, max_length=60)
    effective: str | None = Field(default=None, max_length=80)


class TTImportIn(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    content_base64: str = Field(min_length=4)
    replace: bool = False
    dry_run: bool = True
    skip_errors: bool = False


def _tt(ctx: Context):
    return ctx.service.timetables


def _tt_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except TimetableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/timetable")
async def timetable_view(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    return _tt(ctx).admin_view()


@router.put("/timetable/settings")
async def timetable_settings(body: TTSettingsIn, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    _tt_call(_tt(ctx).set_settings, body.mode, body.term, body.effective, admin["username"])
    return _tt(ctx).admin_view()


@router.post("/timetable/sessions")
async def timetable_add(body: TTSessionIn, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    raw = body.model_dump(exclude={"force"})
    return _tt_call(_tt(ctx).add_session, raw, admin["username"], body.force)


@router.put("/timetable/sessions/{sid}")
async def timetable_update(sid: str, body: TTSessionPatch, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    raw = body.model_dump(exclude={"force"}, exclude_none=True)
    return _tt_call(_tt(ctx).update_session, sid, raw, admin["username"], body.force)


@router.delete("/timetable/sessions/{sid}")
async def timetable_delete(sid: str, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    _tt_call(_tt(ctx).delete_session, sid, admin["username"])
    return {"ok": True}


@router.post("/timetable/sessions/{sid}/restore")
async def timetable_restore(sid: str, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    _tt_call(_tt(ctx).restore_session, sid, admin["username"])
    return {"ok": True}


@router.put("/timetable/courses")
async def timetable_course(body: TTCourseIn, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    _tt_call(_tt(ctx).set_course, body.group, body.label, body.teacher, body.title, admin["username"])
    return {"ok": True}


@router.post("/timetable/undo")
async def timetable_undo(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    return _tt_call(_tt(ctx).undo, admin["username"])


@router.post("/timetable/reset")
async def timetable_reset(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    _tt(ctx).reset(admin["username"])
    return {"ok": True}


@router.get("/timetable/export")
async def timetable_export(admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    view = _tt(ctx).admin_view()
    name = "timetable-" + "".join(ch if ch.isalnum() else "-" for ch in (view["term"] or "current").lower()).strip("-") + ".csv"
    return {"filename": name, "csv": _tt(ctx).export_csv()}


@router.get("/timetable/template")
async def timetable_template(admin=Depends(admin_required)):
    return {"filename": "timetable-template.csv", "csv": TEMPLATE_CSV}


@router.post("/timetable/import")
async def timetable_import(body: TTImportIn, admin=Depends(admin_required), ctx: Context = Depends(get_ctx)):
    import base64
    import binascii
    from pathlib import Path as _Path

    ext = _Path(body.filename).suffix.lower()
    if ext not in (".csv", ".txt", ".xlsx"):
        raise HTTPException(status_code=422, detail="Upload a .csv or .xlsx file (in Excel: Save As → CSV).")
    try:
        raw = base64.b64decode(body.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="File content is not valid base64") from exc
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="The file is larger than 2 MB.")
    if ext == ".xlsx":
        rows, errors = parse_xlsx(raw)
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", "replace")
        rows, errors = parse_csv(text)
    store = _tt(ctx)
    result = {"ok_rows": len(rows), "errors": [{"row": e["row"], "message": e["message"]} for e in errors[:50]],
              "error_count": len(errors), "warnings": store.import_warnings(rows, body.replace) if rows else [],
              "sample": [{k: v for k, v in r.items() if k != "row"} for r in rows[:5]], "applied": False}
    if body.dry_run:
        return result
    if errors and not body.skip_errors:
        raise HTTPException(status_code=422, detail=f"{len(errors)} row(s) have problems; fix them or choose to skip them.")
    if not rows:
        raise HTTPException(status_code=422, detail="There are no valid rows to import.")
    store.import_rows(rows, admin["username"], body.replace)
    result["applied"] = True
    return result
