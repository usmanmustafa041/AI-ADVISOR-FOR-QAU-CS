from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.rag.corpus import corpus_path
from app.rag.evidence import get_index, retrieve
from app.schemas.rag import RagSearchRequest, RagSearchResponse

router = APIRouter(tags=["knowledge retrieval"])


@router.post("/rag/search", response_model=RagSearchResponse)
def search_knowledge(request: RagSearchRequest, db: Session = Depends(get_db)) -> dict:
    try:
        hits, notices = retrieve(request.query, db, request.limit)
    except SQLAlchemyError:
        db.rollback()
        hits, notices = retrieve(request.query, limit=request.limit)
    results = [
        {
            "content": hit.chunk.content,
            "citation": {
                "document_title": hit.chunk.title,
                "source_code": hit.chunk.source_code,
                "source_url": hit.chunk.source_url,
                "page_number": hit.chunk.page_number,
                "section_title": hit.chunk.section_title,
                "similarity": hit.semantic_score,
                "retrieval_score": hit.score,
                "verification_status": hit.chunk.verification_status,
                "effective_term": hit.chunk.effective_term,
            },
        }
        for hit in hits
    ]
    return {
        "query": request.query,
        "results": results,
        "verified_sources_only": all(h.chunk.verification_status == "verified" for h in hits),
        "notice": " ".join(notices)
        if results
        else "No supporting evidence was found in the available QAU sources.",
    }


@router.get("/rag/status")
def retrieval_status() -> dict:
    index = get_index()
    settings = get_settings()
    index._load_dense()
    return {
        "status": "ready" if index.chunks else "degraded",
        "chunks": len(index.chunks),
        "documents": len({c.document_id for c in index.chunks}),
        "retrieval": "hybrid" if index.dense_status == "ready" else "bm25",
        "semantic_status": index.dense_status,
        "embedding_model": settings.embedding_model,
        "reranker_configured": bool(settings.rag_reranker_model),
        "generation_configured": settings.llm_provider == "ollama" and bool(settings.llm_model),
        "generation_model": settings.llm_model,
        "audit_available": corpus_path(settings.rag_corpus_path)
        .with_suffix(".audit.json")
        .exists(),
    }
