from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.core.database import get_db

router = APIRouter(prefix="/history", tags=["query history"])


@router.get("")
def history(search: str | None = None, session_id: str | None = None,
            limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
            user: dict = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    search = search.strip() or None if search is not None else None
    session_id = session_id.strip() or None if session_id is not None else None
    rows = db.execute(text("""
        SELECT s.id::text AS session_id, m.id::text AS message_id, m.role, m.content,
               m.intent, m.created_at::text AS created_at
        FROM chat_sessions s JOIN chat_messages m ON m.session_id=s.id
        WHERE s.user_id=:user_id
          AND (CAST(:search AS text) IS NULL OR m.content ILIKE CAST(:pattern AS text)
               OR m.intent ILIKE CAST(:pattern AS text))
          AND (CAST(:session_id AS text) IS NULL OR s.id=CAST(:session_id AS uuid))
        ORDER BY m.created_at DESC LIMIT :limit OFFSET :offset
    """), {"user_id": user["id"], "search": search,
             "pattern": f"%{search}%" if search else None, "session_id": session_id,
             "limit": limit, "offset": offset}).mappings()
    return [dict(row) for row in rows]


@router.delete("")
def clear_history(user: dict = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    count = db.execute(text("DELETE FROM chat_sessions WHERE user_id=:user_id RETURNING id"), {"user_id": user["id"]}).rowcount
    db.commit()
    return {"deleted_sessions": count}


@router.post("/{session_id}/close")
def close_session(session_id: str, user: dict = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.execute(text("""
        UPDATE chat_sessions SET ended_at=NOW()
        WHERE id=:session_id AND user_id=:user_id AND ended_at IS NULL
        RETURNING id::text
    """), {"session_id": session_id, "user_id": user["id"]}).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Active chat session was not found")
    db.commit()
    return {"closed": True, "session_id": row}
