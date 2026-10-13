"""Optional PostgreSQL validation, contained in a rolled-back transaction."""

import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.feedback import FeedbackRequest, remove_feedback, save_feedback
from app.core.database import get_engine

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_RAG_DB_TESTS") != "1", reason="Requires initialized PostgreSQL"
)


def test_postgres_feedback_ownership_upsert_and_cascade():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            owner, outsider, session_id, message_id = [str(uuid4()) for _ in range(4)]
            for user_id in (owner, outsider):
                connection.execute(
                    text("""INSERT INTO app_users
                        (id,full_name,email,password_hash,role,active)
                        VALUES(:id,'Synthetic validation',:email,'disabled','student',FALSE)"""),
                    {"id": user_id, "email": f"pipeline-{user_id}@example.invalid"},
                )
            connection.execute(
                text(
                    "INSERT INTO chat_sessions(id,user_id,language) VALUES(:id,:user_id,'english')"
                ),
                {"id": session_id, "user_id": owner},
            )
            connection.execute(
                text("""INSERT INTO chat_messages(id,session_id,role,content)
                    VALUES(:id,:session_id,'assistant','Synthetic feedback validation')"""),
                {"id": message_id, "session_id": session_id},
            )
            vote = FeedbackRequest(rating=-1, reason="outdated")
            assert save_feedback(message_id, vote, {"id": owner}, db) == {"saved": True}
            assert save_feedback(message_id, vote, {"id": owner}, db) == {"saved": True}
            assert (
                db.execute(
                    text("SELECT COUNT(*) FROM chat_feedback WHERE message_id=:id"),
                    {"id": message_id},
                ).scalar_one()
                == 1
            )
            with pytest.raises(HTTPException) as denied:
                save_feedback(message_id, vote, {"id": outsider}, db)
            assert denied.value.status_code == 404
            with pytest.raises(HTTPException) as denied:
                remove_feedback(message_id, {"id": outsider}, db)
            assert denied.value.status_code == 404
            assert remove_feedback(message_id, {"id": owner}, db) == {"deleted": True}
            save_feedback(message_id, vote, {"id": owner}, db)
            db.execute(text("DELETE FROM chat_messages WHERE id=:id"), {"id": message_id})
            assert (
                db.execute(
                    text("SELECT COUNT(*) FROM chat_feedback WHERE message_id=:id"),
                    {"id": message_id},
                ).scalar_one()
                == 0
            )
        finally:
            db.close()
            transaction.rollback()
