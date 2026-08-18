import math

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rag.embedding import embed_text, vector_literal


def retrieve_local(query: str, chunks: list[dict], limit: int = 5) -> list[dict]:
    """Retrieve from an in-memory chunk list for deterministic tests and previews."""
    query_vector = embed_text(query)
    scored = []
    for chunk in chunks:
        vector = chunk.get("embedding") or embed_text(chunk["content"])
        score = sum(a * b for a, b in zip(query_vector, vector, strict=True))
        scored.append({**chunk, "similarity": score})
    return sorted(scored, key=lambda item: item["similarity"], reverse=True)[:limit]


def retrieve_chunks(db: Session, query: str, limit: int = 5) -> list[dict]:
    vector = vector_literal(embed_text(query))
    rows = db.execute(
        text("""
            SELECT dc.content, dc.page_number, dc.section_title,
                   kd.title AS document_title, sr.source_code, sr.source_url,
                   sr.last_verified_at::text AS last_verified_at,
                   1 - (dc.embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM document_chunks dc
            JOIN knowledge_documents kd ON kd.id = dc.document_id
            JOIN source_records sr ON sr.id = kd.source_id
            WHERE dc.embedding IS NOT NULL AND kd.processing_status = 'ready'
            ORDER BY dc.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """),
        {"embedding": vector, "limit": limit},
    ).mappings()
    results = [dict(row) for row in rows]
    if results:
        return results
    # Seed/demo documents may be loaded before an embedding job is run. Compute
    # the same deterministic vectors in-process so retrieval remains functional.
    candidates = [dict(row) for row in db.execute(text("""
        SELECT dc.content, dc.page_number, dc.section_title,
               kd.title AS document_title, sr.source_code, sr.source_url,
               sr.last_verified_at::text AS last_verified_at
        FROM document_chunks dc JOIN knowledge_documents kd ON kd.id=dc.document_id
        JOIN source_records sr ON sr.id=kd.source_id
        WHERE kd.processing_status='ready' LIMIT 500
    """)).mappings()]
    return retrieve_local(query, candidates, limit)
