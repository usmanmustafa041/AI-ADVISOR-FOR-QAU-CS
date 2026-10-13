from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.rag.evidence import get_index

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "qau-cs-academic-advisor-api"}


@router.get("/health/database")
def database_health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "reachable"}
    except SQLAlchemyError:
        db.rollback()
        return {"status": "degraded", "database": "unreachable"}


@router.get("/health/ready")
def readiness(db: Annotated[Session, Depends(get_db)]):
    settings = get_settings()
    index = get_index()
    if settings.embedding_provider in {"sentence-transformer", "sentence-transformers"}:
        index._load_dense()
    checks = {
        "evidence": bool(index.chunks),
        "semantic_retrieval": index.dense_status == "ready",
        "database": False,
        "history_schema": False,
        "generation": False,
    }
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
        checks["history_schema"] = db.execute(
            text("""
            SELECT COUNT(*) = 3 FROM information_schema.columns
            WHERE table_schema='public' AND
            ((table_name='chat_sessions' AND column_name IN ('title','updated_at'))
             OR (table_name='chat_messages' AND column_name='response_metadata'))
        """)
        ).scalar_one()
    except SQLAlchemyError:
        db.rollback()
    if settings.llm_provider == "ollama" and settings.llm_model:
        try:
            response = httpx.get(settings.llm_base_url.rstrip("/") + "/api/tags", timeout=2)
            response.raise_for_status()
            models = {m["name"] for m in response.json().get("models", [])}
            checks["generation"] = (
                settings.llm_model in models or settings.llm_model + ":latest" in models
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            pass
    ready = all(checks.values())
    return JSONResponse(
        {
            "status": "ready" if ready else "degraded",
            "checks": checks,
            "notice": None
            if ready
            else "Source excerpts may remain available while a dependency is unavailable.",
        },
        status_code=200 if ready else 503,
    )
