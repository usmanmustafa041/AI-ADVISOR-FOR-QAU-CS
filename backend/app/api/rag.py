from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.rag.retriever import retrieve_chunks
from app.schemas.rag import RagSearchRequest, RagSearchResponse

router = APIRouter(tags=["knowledge retrieval"])


@router.post("/rag/search", response_model=RagSearchResponse)
def search_knowledge(request: RagSearchRequest, db: Session = Depends(get_db)) -> dict:
    try:
        rows = retrieve_chunks(db, request.query, request.limit)
    except SQLAlchemyError:
        rows = []
    results = [
        {
            "content": row["content"],
            "citation": {
                "document_title": row["document_title"],
                "source_code": row["source_code"],
                "source_url": row["source_url"],
                "page_number": row["page_number"],
                "section_title": row["section_title"],
                "similarity": float(row["similarity"]),
            },
        }
        for row in rows
    ]
    return {
        "query": request.query,
        "results": results,
        "notice": None if results else "No processed, verified knowledge chunks are available yet.",
    }

