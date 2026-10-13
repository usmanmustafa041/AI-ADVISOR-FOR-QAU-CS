"""Student-facing endpoints."""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from advisor import __version__
from advisor.api.deps import get_ctx, rate_limited
from advisor.api.identity import User, resolve_user
from advisor.context import Context

log = logging.getLogger("advisor.api")
router = APIRouter(prefix="/api/v1")

STARTERS = [
    "What are the admission requirements for BS Computer Science?",
    "Who teaches Data Structures this semester?",
    "What are the prerequisites of Operating Systems?",
    "What is the minimum attendance required for exams?",
    "When do terminal exams start?",
    "Who is the chairperson of the department?",
]


class HistoryItem(BaseModel):
    role: str = Field(max_length=12)
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=64)
    # Guests: send the recent turns yourself and nothing is stored on the server.
    ephemeral: bool = False
    history: list[HistoryItem] | None = Field(default=None, max_length=16)
    language: str | None = Field(default=None, max_length=12)


class FeedbackIn(BaseModel):
    message_id: str = Field(min_length=8, max_length=64)
    rating: int
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackPut(BaseModel):
    rating: int
    reason: str | None = Field(default=None, max_length=60)
    comment: str | None = Field(default=None, max_length=1000)


async def require_user(request: Request) -> User:
    user = await resolve_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to use this feature")
    return user


def _chat_args(body: ChatIn, user: User | None) -> dict:
    return {
        "owner": user.id if user else None,
        "ephemeral": body.ephemeral and user is None,
        "history": [(h.role, h.content) for h in (body.history or [])],
        "language": body.language,
    }


def _clean_message(ctx: Context, text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text).strip()
    if not text:
        raise HTTPException(status_code=422, detail="Please type a question.")
    if len(text) > ctx.settings.max_question_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Please keep questions under {ctx.settings.max_question_chars} characters.",
        )
    return text


@router.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


@router.get("/ready")
async def ready(ctx: Context = Depends(get_ctx)):
    return {
        "ready": ctx.kb.ready,
        "knowledge": ctx.kb.info(),
    }


@router.get("/config")
async def public_config(ctx: Context = Depends(get_ctx)):
    return {
        "notice": ctx.runtime.get("assistant.notice"),
        "chat_enabled": bool(ctx.runtime.get("chat.enabled")),
        "starters": STARTERS,
        "knowledge_updated": (ctx.kb.info().get("created_at") or "")[:10],
        "max_chars": ctx.settings.max_question_chars,
    }


def _sse(event: dict) -> str:
    name = event["event"]
    payload = {k: v for k, v in event.items() if k != "event"}
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream", dependencies=[Depends(rate_limited)])
async def chat_stream(body: ChatIn, request: Request, ctx: Context = Depends(get_ctx)):
    question = _clean_message(ctx, body.message)
    args = _chat_args(body, await resolve_user(request))

    async def gen() -> AsyncIterator[str]:
        try:
            async for ev in ctx.service.stream_answer(question, body.conversation_id, **args):
                yield _sse(ev)
        except Exception:
            log.exception("chat stream failed")
            yield _sse(
                {
                    "event": "error",
                    "message": "Something went wrong while answering. Please try again.",
                    "retryable": True,
                }
            )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/chat", dependencies=[Depends(rate_limited)])
async def chat(body: ChatIn, request: Request, ctx: Context = Depends(get_ctx)):
    """Non-streaming variant for simple clients and integrations."""
    question = _clean_message(ctx, body.message)
    args = _chat_args(body, await resolve_user(request))
    text, sources, done, cid = "", [], {}, body.conversation_id
    async for ev in ctx.service.stream_answer(question, cid, **args):
        if ev["event"] == "meta":
            cid = ev["conversation_id"]
        elif ev["event"] == "delta":
            text += ev["text"]
        elif ev["event"] in ("reset",):
            text = ""
        elif ev["event"] == "replace":
            text = ev["text"]
        elif ev["event"] == "sources":
            sources = ev["sources"]
        elif ev["event"] == "done":
            done = ev
        elif ev["event"] == "error":
            raise HTTPException(status_code=503, detail=ev["message"])
    return {
        "conversation_id": cid, "message_id": done.get("message_id"), "answer": text,
        "sources": sources, "outcome": done.get("outcome"),
    }


def _messages_out(rows) -> list[dict]:
    out = []
    for r in rows:
        meta = json.loads(r["meta"]) if r["meta"] else {}
        out.append({"id": r["id"], "role": r["role"], "content": r["content"],
                    "sources": meta.get("sources", []), "created_at": r["created_at"]})
    return out


@router.get("/conversations/{conversation_id}")
async def conversation(conversation_id: str, request: Request, ctx: Context = Depends(get_ctx)):
    if not re.fullmatch(r"[0-9a-f]{32}", conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv = ctx.db.one("SELECT owner_id FROM conversations WHERE id=?", (conversation_id,))
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv["owner_id"]:  # a signed-in student's conversation: only that student may read it
        user = await resolve_user(request)
        if user is None or user.id != conv["owner_id"]:
            raise HTTPException(status_code=404, detail="Conversation not found")
    rows = ctx.db.all(
        "SELECT id, role, content, meta, created_at FROM messages WHERE conversation_id=? ORDER BY created_at, rowid",
        (conversation_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation_id": conversation_id, "messages": _messages_out(rows)}


@router.get("/me/conversations")
async def my_conversations(user: User = Depends(require_user), ctx: Context = Depends(get_ctx)):
    rows = ctx.db.all(
        "SELECT id, title, created_at, updated_at FROM conversations WHERE owner_id=? "
        "AND EXISTS (SELECT 1 FROM messages WHERE conversation_id=conversations.id) "
        "ORDER BY updated_at DESC LIMIT 100",
        (user.id,),
    )
    return {"conversations": [dict(r) for r in rows]}


@router.delete("/me/conversations/{conversation_id}")
async def delete_my_conversation(conversation_id: str, user: User = Depends(require_user), ctx: Context = Depends(get_ctx)):
    ctx.db.execute("DELETE FROM conversations WHERE id=? AND owner_id=?", (conversation_id, user.id))
    return {"ok": True}


@router.get("/me/history")
async def my_history(search: str = "", user: User = Depends(require_user), ctx: Context = Depends(get_ctx)):
    like = f"%{search.strip()}%"
    rows = ctx.db.all(
        "SELECT m.id AS message_id, m.role, m.content, m.created_at FROM messages m "
        "JOIN conversations c ON c.id=m.conversation_id WHERE c.owner_id=? AND m.content LIKE ? "
        "ORDER BY m.created_at DESC, m.rowid DESC LIMIT 300",
        (user.id, like),
    )
    return [{**dict(r), "intent": None} for r in rows]


@router.delete("/me/history")
async def clear_my_history(user: User = Depends(require_user), ctx: Context = Depends(get_ctx)):
    ctx.db.execute("DELETE FROM conversations WHERE owner_id=?", (user.id,))
    return {"ok": True}


async def _check_feedback_target(ctx: Context, request: Request, message_id: str) -> None:
    row = ctx.db.one(
        "SELECT c.owner_id FROM messages m JOIN conversations c ON c.id=m.conversation_id "
        "WHERE m.id=? AND m.role='assistant'",
        (message_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if row["owner_id"]:
        user = await resolve_user(request)
        if user is None or user.id != row["owner_id"]:
            raise HTTPException(status_code=404, detail="Message not found")


def _save_feedback(ctx: Context, message_id: str, rating: int, comment: str | None, reason: str | None) -> None:
    if rating not in (-1, 1):
        raise HTTPException(status_code=422, detail="rating must be 1 or -1")
    ctx.db.execute(
        "INSERT INTO feedback(message_id, rating, comment, reason) VALUES(?,?,?,?) "
        "ON CONFLICT(message_id) DO UPDATE SET rating=excluded.rating, comment=excluded.comment, reason=excluded.reason",
        (message_id, rating, (comment or "").strip() or None, reason),
    )
    if rating < 0:
        ctx.service.cache.drop_for_message(message_id)  # don't keep serving a disliked answer


@router.post("/feedback", dependencies=[Depends(rate_limited)])
async def feedback(body: FeedbackIn, request: Request, ctx: Context = Depends(get_ctx)):
    if body.rating not in (-1, 1):
        raise HTTPException(status_code=422, detail="rating must be 1 or -1")
    await _check_feedback_target(ctx, request, body.message_id)
    _save_feedback(ctx, body.message_id, body.rating, body.comment, None)
    return {"ok": True, "id": uuid.uuid4().hex[:8]}


@router.put("/feedback/{message_id}", dependencies=[Depends(rate_limited)])
async def put_feedback(message_id: str, body: FeedbackPut, request: Request, ctx: Context = Depends(get_ctx)):
    await _check_feedback_target(ctx, request, message_id)
    _save_feedback(ctx, message_id, body.rating, body.comment, body.reason)
    return {"ok": True}


@router.delete("/feedback/{message_id}", dependencies=[Depends(rate_limited)])
async def delete_feedback(message_id: str, request: Request, ctx: Context = Depends(get_ctx)):
    await _check_feedback_target(ctx, request, message_id)
    ctx.db.execute("DELETE FROM feedback WHERE message_id=?", (message_id,))
    return {"ok": True}
