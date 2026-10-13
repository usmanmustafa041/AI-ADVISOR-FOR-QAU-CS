"""Execute feedback ownership/upsert SQL against an isolated local database."""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.feedback import router
from app.core.auth import current_user
from app.core.database import get_db


@pytest.fixture
def feedback_app():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db = Session(engine)
    for statement in (
        "CREATE TABLE chat_sessions(id TEXT PRIMARY KEY,user_id TEXT)",
        "CREATE TABLE chat_messages(id TEXT PRIMARY KEY,session_id TEXT,role TEXT)",
        "CREATE TABLE chat_feedback(message_id TEXT PRIMARY KEY,user_id TEXT,rating INTEGER,"
        "reason TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,"
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    ):
        db.execute(text(statement))
    user = {"id": str(uuid4()), "role": "student"}
    other_user = str(uuid4())
    session_id, other_session = str(uuid4()), str(uuid4())
    own, other, user_message = [str(uuid4()) for _ in range(3)]
    db.execute(
        text("INSERT INTO chat_sessions VALUES(:id,:user_id)"),
        [
            {"id": session_id, "user_id": user["id"]},
            {"id": other_session, "user_id": other_user},
        ],
    )
    db.execute(
        text("INSERT INTO chat_messages VALUES(:id,:session_id,:role)"),
        [
            {"id": own, "session_id": session_id, "role": "assistant"},
            {"id": other, "session_id": other_session, "role": "assistant"},
            {"id": user_message, "session_id": session_id, "role": "user"},
        ],
    )
    db.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: user
    with TestClient(app) as client:
        yield client, db, user, own, other, user_message, app
    db.close()
    engine.dispose()


def test_feedback_requires_authentication(feedback_app):
    client, _, _, own, _, _, app = feedback_app
    app.dependency_overrides.pop(current_user)
    assert (
        client.put(f"/feedback/{own}", json={"rating": 1, "reason": "helpful"}).status_code == 401
    )


def test_feedback_is_limited_to_owned_assistant_messages(feedback_app):
    client, db, _, own, other, user_message, _ = feedback_app
    for denied in (other, user_message, str(uuid4())):
        assert (
            client.put(
                f"/feedback/{denied}", json={"rating": -1, "reason": "incorrect"}
            ).status_code
            == 404
        )
    assert db.execute(text("SELECT COUNT(*) FROM chat_feedback")).scalar_one() == 0
    assert (
        client.put(f"/feedback/{own}", json={"rating": 1, "reason": "helpful"}).status_code == 200
    )


def test_vote_updates_are_idempotent_and_removable(feedback_app):
    client, db, _, own, _, _, _ = feedback_app
    client.put(f"/feedback/{own}", json={"rating": 1, "reason": "helpful"})
    assert (
        client.put(f"/feedback/{own}", json={"rating": -1, "reason": "outdated"}).status_code == 200
    )
    rows = db.execute(text("SELECT rating,reason FROM chat_feedback")).all()
    assert rows == [(-1, "outdated")]
    assert client.delete(f"/feedback/{own}").status_code == 200
    assert client.delete(f"/feedback/{own}").status_code == 404


def test_other_users_cannot_remove_a_vote(feedback_app):
    client, db, user, own, _, _, _ = feedback_app
    client.put(f"/feedback/{own}", json={"rating": 1, "reason": "helpful"})
    user["id"] = str(uuid4())
    assert client.delete(f"/feedback/{own}").status_code == 404
    assert db.execute(text("SELECT COUNT(*) FROM chat_feedback")).scalar_one() == 1


def test_feedback_summary_requires_admin_and_returns_only_counts(feedback_app):
    client, _, user, own, _, _, _ = feedback_app
    client.put(f"/feedback/{own}", json={"rating": -1, "reason": "incorrect"})
    assert client.get("/feedback").status_code == 403
    user["role"] = "admin"
    assert client.get("/feedback").json() == [{"rating": -1, "reason": "incorrect", "votes": 1}]


def test_missing_feedback_migration_returns_a_safe_availability_error(feedback_app):
    client, db, _, own, _, _, _ = feedback_app
    db.execute(text("DROP TABLE chat_feedback"))
    db.commit()
    assert (
        client.put(f"/feedback/{own}", json={"rating": 1, "reason": "helpful"}).status_code == 503
    )
