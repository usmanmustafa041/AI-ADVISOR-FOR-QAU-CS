"""Authenticated, owner-scoped conversation history. Guests are never persisted."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.core.database import get_db

router = APIRouter(prefix="/history", tags=["query history"])


@router.get("/sessions")
def get_sessions(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text("""SELECT id::text, title, started_at AS created_at, updated_at
        FROM chat_sessions WHERE user_id=:user_id ORDER BY updated_at DESC LIMIT :limit"""),
        {"user_id": user["id"], "limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


@router.get("/sessions/{session_id}")
def get_session_messages(
    session_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    session = db.execute(
        text("SELECT id FROM chat_sessions WHERE id=:id AND user_id=:user_id"),
        {"id": str(session_id), "user_id": user["id"]},
    ).first()
    if not session:
        raise HTTPException(404, "Conversation not found")
    rows = db.execute(
        text("""SELECT * FROM (
        SELECT id::text, role, content, created_at, intent, intent_confidence,
               response_engine, response_time_ms, response_metadata
        FROM chat_messages WHERE session_id=:id
        ORDER BY created_at DESC, id DESC LIMIT :limit
    ) recent ORDER BY created_at, id"""),
        {"id": str(session_id), "limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: UUID, user: dict = Depends(current_user), db: Session = Depends(get_db)
):
    count = db.execute(
        text("DELETE FROM chat_sessions WHERE id=:id AND user_id=:user_id"),
        {"id": str(session_id), "user_id": user["id"]},
    ).rowcount
    if not count:
        raise HTTPException(404, "Conversation not found")
    db.commit()
    return {"deleted": True}


@router.get("")
def history(
    search: str | None = None,
    session_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    search = search.strip() or None if search is not None else None
    rows = db.execute(
        text("""SELECT s.id::text AS session_id, m.id::text AS message_id,
            m.role, m.content, m.intent, m.created_at::text AS created_at
        FROM chat_sessions s JOIN chat_messages m ON m.session_id=s.id
        WHERE s.user_id=:user_id
          AND (CAST(:search AS text) IS NULL OR m.content ILIKE :pattern OR m.intent ILIKE :pattern)
          AND (CAST(:session_id AS uuid) IS NULL OR s.id=CAST(:session_id AS uuid))
        ORDER BY m.created_at DESC LIMIT :limit OFFSET :offset"""),
        {
            "user_id": user["id"],
            "search": search,
            "pattern": f"%{search}%" if search else None,
            "session_id": str(session_id) if session_id else None,
            "limit": limit,
            "offset": offset,
        },
    ).mappings()
    return [dict(row) for row in rows]


@router.delete("")
def clear_history(user: dict = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    count = db.execute(
        text("DELETE FROM chat_sessions WHERE user_id=:user_id"), {"user_id": user["id"]}
    ).rowcount
    db.commit()
    return {"deleted_sessions": count}


@router.post("/{session_id}/close")
def close_session(
    session_id: UUID, user: dict = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    row = db.execute(
        text("""UPDATE chat_sessions SET ended_at=NOW()
        WHERE id=:id AND user_id=:user_id AND ended_at IS NULL RETURNING id::text"""),
        {"id": str(session_id), "user_id": user["id"]},
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Active conversation not found")
    db.commit()
    return {"closed": True, "session_id": row}


class SessionBatchRequest(BaseModel):
    session_ids: list[UUID] = Field(max_length=100)


@router.post("/sessions/batch")
def get_sessions_batch(
    request: SessionBatchRequest, user: dict = Depends(current_user), db: Session = Depends(get_db)
):
    if not request.session_ids:
        return []
    rows = db.execute(
        text("""SELECT id::text, title, started_at AS created_at, updated_at
        FROM chat_sessions WHERE user_id=:user_id AND id = ANY(CAST(:ids AS uuid[]))
        ORDER BY updated_at DESC"""),
        {"user_id": user["id"], "ids": [str(i) for i in request.session_ids]},
    ).mappings()
    return [dict(row) for row in rows]
