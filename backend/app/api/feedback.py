"""Owner-scoped votes on saved assistant answers; no duplicate transcripts."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import admin_user, current_user
from app.core.database import get_db

router = APIRouter(prefix="/feedback", tags=["answer feedback"])


class FeedbackRequest(BaseModel):
    rating: Literal[-1, 1]
    reason: Literal["helpful", "incorrect", "outdated", "missing_information", "unclear"]


@router.put("/{message_id}")
def save_feedback(
    message_id: UUID,
    request: FeedbackRequest,
    user: Annotated[dict, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        result = db.execute(
            text("""INSERT INTO chat_feedback(message_id,user_id,rating,reason)
                SELECT m.id, s.user_id, :rating, :reason
                FROM chat_messages m JOIN chat_sessions s ON s.id=m.session_id
                WHERE m.id=:message_id AND s.user_id=:user_id AND m.role='assistant'
                ON CONFLICT(message_id) DO UPDATE SET
                    rating=excluded.rating, reason=excluded.reason, updated_at=CURRENT_TIMESTAMP
            """),
            {
                "message_id": str(message_id),
                "user_id": user["id"],
                "rating": request.rating,
                "reason": request.reason,
            },
        )
        if not result.rowcount:
            db.rollback()
            raise HTTPException(404, "Saved assistant answer not found")
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Answer feedback is temporarily unavailable") from None
    return {"saved": True}


@router.delete("/{message_id}")
def remove_feedback(
    message_id: UUID,
    user: Annotated[dict, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        result = db.execute(
            text("DELETE FROM chat_feedback WHERE message_id=:message_id AND user_id=:user_id"),
            {"message_id": str(message_id), "user_id": user["id"]},
        )
        if not result.rowcount:
            db.rollback()
            raise HTTPException(404, "Answer feedback not found")
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Answer feedback is temporarily unavailable") from None
    return {"deleted": True}


@router.get("")
def feedback_summary(
    _: Annotated[dict, Depends(admin_user)], db: Annotated[Session, Depends(get_db)]
):
    try:
        rows = db.execute(
            text("""SELECT rating,reason,COUNT(*) AS votes
            FROM chat_feedback GROUP BY rating,reason ORDER BY rating,reason""")
        ).mappings()
        return [dict(row) for row in rows]
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Answer feedback is temporarily unavailable") from None
