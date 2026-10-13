"""The canonical chat endpoint. Intent labels never gate knowledge retrieval."""

import json
import logging
import re
import time
from threading import BoundedSemaphore
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import optional_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.nlp.entities import extract_entities
from app.nlp.language import detect_language
from app.nlp.query_pipeline import plan_query
from app.rag.evidence import Hit, get_index, query_programs, retrieve
from app.response.calculation import calculate_gpa
from app.response.conversation import conversational_reply
from app.response.educational import educational_answer
from app.response.grounded import generate_answer
from app.response.policy_lookup import policy_excerpt_answer
from app.response.privacy import private_record_answer
from app.response.structured_lookup import structured_answer
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])
_request_slots = BoundedSemaphore(get_settings().chat_max_concurrent)


def retrieval_question(message: str, history: list[dict], course: str | None) -> str:
    """Resolve short references from user turns; history is never factual evidence."""
    followup = re.search(
        r"\b(it|its|this|that|their|them|those|iska|iski|uska|unke|same)\b|^(and|what about|aur)\b",
        message,
        re.I,
    )
    query = message
    last_assistant = next((h["content"] for h in reversed(history) if h["role"] == "assistant"), "")
    answering_clarification = query_programs(message) and any(
        prompt in last_assistant
        for prompt in ("Which programme and admission year", "Aap kis programme", "آپ کس پروگرام")
    )
    if followup or answering_clarification:
        previous = next(
            (
                h["content"]
                for h in reversed(history)
                if h["role"] == "user" and conversational_reply(h["content"], "english") is None
            ),
            "",
        )
        if previous:
            query = previous[-500:] + "\nFollow-up: " + message
        if course and course.lower() not in query.lower():
            query += "\nCourse: " + course
    return query


def load_history(db, user: dict | None, session_id) -> list[dict]:
    if not user or not session_id:
        return []
    row = db.execute(
        text("""SELECT id FROM chat_sessions
        WHERE id=:id AND user_id=:user_id AND ended_at IS NULL"""),
        {"id": str(session_id), "user_id": user["id"]},
    ).first()
    if row is None:
        raise HTTPException(404, "Active conversation not found")
    return [
        dict(r)
        for r in db.execute(
            text("""
        SELECT role, content FROM (
            SELECT role, content, created_at, id FROM chat_messages
            WHERE session_id=:id ORDER BY created_at DESC, id DESC LIMIT 8
        ) recent ORDER BY created_at, id
    """),
            {"id": str(session_id)},
        ).mappings()
    ]


def save_turn(db, user, session_id, request, result):
    if not user:
        return None
    if not session_id:
        session_id = db.execute(
            text("""INSERT INTO chat_sessions (user_id, language, title)
            VALUES (:user_id, :language, :title) RETURNING id::text"""),
            {"user_id": user["id"], "language": result["language"], "title": request.message[:80]},
        ).scalar_one()
    session_id = str(session_id)
    metadata = {k: result[k] for k in ("citations", "grounding_status", "notices", "verified")}
    for role, content in (("user", request.message), ("assistant", result["answer"])):
        saved_message = db.execute(
            text("""INSERT INTO chat_messages
            (session_id, role, content, intent, intent_confidence, entities,
             response_engine, response_time_ms, response_metadata, created_at)
            VALUES (:session_id, :role, :content, :intent, :confidence,
                    CAST(:entities AS jsonb), :engine, :elapsed,
                    CAST(:metadata AS jsonb), clock_timestamp()) RETURNING id::text"""),
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "intent": result["intent"],
                "confidence": result["confidence"],
                "entities": json.dumps(result["entities"]),
                "engine": "fallback"
                if result["response_engine"] == "conversation"
                else result["response_engine"],
                "elapsed": result["response_time_ms"],
                "metadata": json.dumps(metadata if role == "assistant" else {}),
            },
        ).scalar_one()
        if role == "assistant":
            result["message_id"] = saved_message
    db.execute(text("UPDATE chat_sessions SET updated_at=NOW() WHERE id=:id"), {"id": session_id})
    db.commit()
    return session_id


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict | None, Depends(optional_current_user)],
) -> dict:
    if not _request_slots.acquire(blocking=False):
        raise HTTPException(
            503, "The advisor is busy. Please retry shortly.", headers={"Retry-After": "3"}
        )
    try:
        return handle_chat(request, db, user)
    finally:
        _request_slots.release()


def handle_chat(request, db, user):
    started = time.perf_counter()
    language = request.language or detect_language(request.message)
    entities = extract_entities(request.message)
    history = [h.model_dump() for h in request.history] if not user else []
    notices = []
    session_id = request.session_id if user else None
    try:
        if user:
            history = load_history(db, user, session_id)
    except SQLAlchemyError:
        db.rollback()
        # Don't continue an inaccessible authenticated conversation or accept
        # client-supplied history as that user's stored history.
        if session_id:
            raise HTTPException(503, "Saved conversation is temporarily unavailable") from None
        notices.append("Conversation history is unavailable; this answer may not be saved.")
    plan = plan_query(request.message, history, request.context_course_code, language)
    query = plan.rewritten
    entities = plan.entities
    if request.context_course_code and query != request.message:
        entities.setdefault("course_code", [request.context_course_code.upper()])
    result = conversational_reply(request.message, language)
    conversational = result is not None
    result = result or private_record_answer(request.message, language)
    result = result or calculate_gpa(request.message, language)
    result = result or educational_answer(request.message, language)
    if len(plan.subquestions) == 1:
        result = result or structured_answer(request.message, plan.scope, language)
        if result is None:
            index = get_index()
            # Exact rule lookup uses only the current, scope-filtered evidence
            # library. It never reads unpublished newer archive versions.
            rule_hits = [
                Hit(c, 1)
                for c in index.chunks
                if c.category == "academic_policy" and index._eligible(c, query)
            ]
            result = policy_excerpt_answer(query, rule_hits, language)
    if result is not None:
        hits = []
    else:
        hits, retrieval_notices = retrieve(query, db)
        if len(plan.subquestions) > 1:
            groups = []
            for part in plan.subquestions:
                partial, _ = retrieve(part, db)
                groups.append(partial[:3])
            # Interleave so each independent question contributes early evidence.
            combined = [group[rank] for rank in range(3) for group in groups if len(group) > rank]
            by_id = {h.chunk.chunk_id: h for h in combined + hits}
            hits = list(by_id.values())[:9]
        notices.extend(retrieval_notices)
        result = generate_answer(query, hits, language, history)
    notices.extend(result.notices)
    intent = (
        "greeting"
        if conversational
        else "private_record"
        if result.model == "privacy-guard"
        else plan.intent
    )
    if re.search(r"prereq|pre.?req|can i (?:take|register|enrol)", request.message, re.I):
        intent = "course_prerequisite"
        # Advice is useful, but registration approval requires facts this chat
        # has not independently established.
        if re.search(r"can i|eligible|register|enrol", request.message, re.I):
            caution = (
                "I cannot safely confirm your registration eligibility "
                "from this conversation alone. "
                "Published prerequisites, your curriculum and your complete academic record "
                "must be checked."
            )
            result.answer = caution + "\n\n" + result.answer
    payload = {
        "answer": result.answer,
        "intent": intent,
        "language": language,
        # Evidence strength is a ranking heuristic, not a probability of correctness.
        "confidence": round(min(0.85, max((h.coverage for h in hits), default=0)), 3),
        "entities": entities,
        "model_backend": "conversation"
        if conversational
        else "privacy"
        if result.model == "privacy-guard"
        else "calculation"
        if result.model == "calculator"
        else "education"
        if result.grounding_status == "educational"
        else "retrieval"
        if result.model
        in {
            "source-table",
            "source-directory",
            "source-gap",
            "source-calculator",
            "source-rule",
            "structured",
            "structured-clarification",
        }
        else ("ollama" if result.model not in {"", "extractive"} else "extractive"),
        "model_name": result.model or "none",
        "response_engine": result.engine,
        "citations": result.citations,
        "verified": result.verified,
        "session_id": None,
        "message_id": None,
        "query_scope": plan.scope,
        "grounding_status": result.grounding_status,
        "response_time_ms": round((time.perf_counter() - started) * 1000),
        "retrieval_query": query,
        "notices": notices,
    }
    try:
        payload["session_id"] = save_turn(db, user, session_id, request, payload)
    except SQLAlchemyError:
        db.rollback()
        logger.warning("Chat response served, but history could not be saved")
        payload["session_id"] = str(session_id) if session_id else None
        payload["notices"].append("This answer could not be saved to conversation history.")
    logger.info(
        "chat_complete engine=%s grounding=%s sources=%d latency_ms=%d",
        payload["response_engine"],
        payload["grounding_status"],
        len(result.citations),
        payload["response_time_ms"],
    )
    return payload
