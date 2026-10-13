"""
Admin CMS API - Knowledge Base Management (CRUD with Audit Trail)
Non-destructive operations with full audit logging
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import admin_user
from app.core.database import get_db
from app.schemas.cms import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseBulkImport,
    KnowledgeBaseBulkImportResult,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResult,
    KnowledgeBaseStats,
    KnowledgeCategory,
    CacheInvalidationRequest,
    PromptAssemblyPreview,
)

router = APIRouter(prefix="/admin/cms", tags=["admin-cms"])


def _audit(
    db: Session,
    user_id: str,
    action: str,
    knowledge_base_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None
) -> None:
    """Log CMS operations to knowledge_base_audit table"""
    db.execute(
        text("""
            INSERT INTO knowledge_base_audit
            (knowledge_base_id, action, changed_by, before_data, after_data, change_reason)
            VALUES (
                CAST(:kb_id AS uuid),
                :action,
                CAST(:user_id AS uuid),
                CAST(:before AS jsonb),
                CAST(:after AS jsonb),
                :reason
            )
        """),
        {
            "kb_id": knowledge_base_id,
            "action": action,
            "user_id": user_id,
            "before": json.dumps(before) if before else None,
            "after": json.dumps(after) if after else None,
            "reason": reason,
        },
    )


def _commit(db: Session, message: str = "Operation failed due to constraint violation") -> None:
    """Safe commit with integrity error handling"""
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=message) from e


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert SQLAlchemy row to dictionary"""
    return dict(row._mapping)


# ============================================================================
# LIST & RETRIEVE
# ============================================================================


@router.get("/entries", response_model=KnowledgeBaseListResponse)
def list_knowledge_entries(
    category: KnowledgeCategory | None = None,
    language: str | None = None,
    is_active: bool | None = None,
    is_verified: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    List knowledge base entries with pagination and filters
    """
    offset = (page - 1) * page_size
    
    # Build filter conditions
    conditions = []
    params: dict[str, Any] = {"limit": page_size, "offset": offset}
    
    if category:
        conditions.append("category = :category")
        params["category"] = category.value
    if language:
        conditions.append("language = :language")
        params["language"] = language
    if is_active is not None:
        conditions.append("is_active = :is_active")
        params["is_active"] = is_active
    if is_verified is not None:
        conditions.append("is_verified = :is_verified")
        params["is_verified"] = is_verified
    
    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    
    # Count total
    count_query = f"SELECT COUNT(*)::int AS total FROM knowledge_base WHERE {where_clause}"
    total = db.execute(text(count_query), params).scalar_one()
    
    # Fetch records
    query = f"""
        SELECT 
            id, sub_key, category, title, content_markdown,
            structured_data, source_url, source_document, language,
            is_active, is_verified, priority, created_at, updated_at,
            created_by, updated_by
        FROM knowledge_base
        WHERE {where_clause}
        ORDER BY priority ASC, updated_at DESC
        LIMIT :limit OFFSET :offset
    """
    rows = db.execute(text(query), params).mappings().all()
    
    items = []
    for row in rows:
        item = dict(row)
        # Parse JSONB structured_data
        if isinstance(item.get("structured_data"), str):
            item["structured_data"] = json.loads(item["structured_data"])
        items.append(item)
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (page * page_size) < total,
        "has_prev": page > 1,
    }


@router.get("/entries/{entry_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_entry(
    entry_id: str,
    _: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Retrieve a single knowledge base entry by ID
    """
    row = db.execute(
        text("""
            SELECT 
                id, sub_key, category, title, content_markdown,
                structured_data, source_url, source_document, language,
                is_active, is_verified, priority, created_at, updated_at,
                created_by, updated_by
            FROM knowledge_base
            WHERE id = CAST(:id AS uuid)
        """),
        {"id": entry_id},
    ).mappings().one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    result = dict(row)
    if isinstance(result.get("structured_data"), str):
        result["structured_data"] = json.loads(result["structured_data"])
    
    return result


@router.get("/entries/by-key/{sub_key}", response_model=KnowledgeBaseResponse)
def get_knowledge_entry_by_key(
    sub_key: str,
    _: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Retrieve a knowledge base entry by sub_key
    """
    row = db.execute(
        text("""
            SELECT 
                id, sub_key, category, title, content_markdown,
                structured_data, source_url, source_document, language,
                is_active, is_verified, priority, created_at, updated_at,
                created_by, updated_by
            FROM knowledge_base
            WHERE sub_key = :sub_key
        """),
        {"sub_key": sub_key.lower()},
    ).mappings().one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"Knowledge entry with key '{sub_key}' not found")
    
    result = dict(row)
    if isinstance(result.get("structured_data"), str):
        result["structured_data"] = json.loads(result["structured_data"])
    
    return result


# ============================================================================
# CREATE (UPSERT)
# ============================================================================


@router.post("/entries", status_code=201, response_model=KnowledgeBaseResponse)
def create_knowledge_entry(
    payload: KnowledgeBaseCreate,
    user: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Create a new knowledge base entry (UPSERT by sub_key)
    If sub_key exists, updates the existing record (non-destructive)
    """
    # Check if entry exists
    existing = db.execute(
        text("SELECT id, sub_key FROM knowledge_base WHERE sub_key = :sub_key"),
        {"sub_key": payload.sub_key.lower()},
    ).mappings().one_or_none()
    
    if existing:
        # UPSERT: Update existing record
        entry_id = existing["id"]
        
        # Get before state for audit
        before_row = db.execute(
            text("""
                SELECT id, sub_key, category, title, content_markdown, 
                       structured_data, is_active, is_verified, priority
                FROM knowledge_base WHERE id = CAST(:id AS uuid)
            """),
            {"id": entry_id},
        ).mappings().one()
        before = dict(before_row)
        
        # Update
        db.execute(
            text("""
                UPDATE knowledge_base
                SET 
                    category = :category,
                    title = :title,
                    content_markdown = :content_markdown,
                    structured_data = CAST(:structured_data AS jsonb),
                    source_url = :source_url,
                    source_document = :source_document,
                    language = :language,
                    is_active = :is_active,
                    is_verified = :is_verified,
                    priority = :priority,
                    updated_by = CAST(:user_id AS uuid),
                    updated_at = NOW()
                WHERE id = CAST(:id AS uuid)
            """),
            {
                "id": entry_id,
                "category": payload.category.value,
                "title": payload.title,
                "content_markdown": payload.content_markdown,
                "structured_data": json.dumps(payload.structured_data),
                "source_url": payload.source_url,
                "source_document": payload.source_document,
                "language": payload.language,
                "is_active": payload.is_active,
                "is_verified": payload.is_verified,
                "priority": payload.priority,
                "user_id": user["id"],
            },
        )
        
        after = payload.model_dump()
        _audit(db, user["id"], "upsert_update", str(entry_id), before, after, "Upserted via sub_key")
        _commit(db, "Failed to update knowledge entry")
        
        # Fetch updated record
        updated = db.execute(
            text("""
                SELECT 
                    id, sub_key, category, title, content_markdown,
                    structured_data, source_url, source_document, language,
                    is_active, is_verified, priority, created_at, updated_at,
                    created_by, updated_by
                FROM knowledge_base WHERE id = CAST(:id AS uuid)
            """),
            {"id": entry_id},
        ).mappings().one()
        
        result = dict(updated)
        if isinstance(result.get("structured_data"), str):
            result["structured_data"] = json.loads(result["structured_data"])
        return result
    
    else:
        # INSERT new record
        row = db.execute(
            text("""
                INSERT INTO knowledge_base (
                    sub_key, category, title, content_markdown, structured_data,
                    source_url, source_document, language, is_active, is_verified,
                    priority, created_by, updated_by
                )
                VALUES (
                    :sub_key, :category, :title, :content_markdown,
                    CAST(:structured_data AS jsonb), :source_url, :source_document,
                    :language, :is_active, :is_verified, :priority,
                    CAST(:user_id AS uuid), CAST(:user_id AS uuid)
                )
                RETURNING id::text
            """),
            {
                "sub_key": payload.sub_key.lower(),
                "category": payload.category.value,
                "title": payload.title,
                "content_markdown": payload.content_markdown,
                "structured_data": json.dumps(payload.structured_data),
                "source_url": payload.source_url,
                "source_document": payload.source_document,
                "language": payload.language,
                "is_active": payload.is_active,
                "is_verified": payload.is_verified,
                "priority": payload.priority,
                "user_id": user["id"],
            },
        ).scalar_one()
        
        entry_id = row
        _audit(db, user["id"], "create", entry_id, None, payload.model_dump(), "New entry created")
        _commit(db, "Knowledge entry with this sub_key already exists")
        
        # Fetch created record
        created = db.execute(
            text("""
                SELECT 
                    id, sub_key, category, title, content_markdown,
                    structured_data, source_url, source_document, language,
                    is_active, is_verified, priority, created_at, updated_at,
                    created_by, updated_by
                FROM knowledge_base WHERE id = CAST(:id AS uuid)
            """),
            {"id": entry_id},
        ).mappings().one()
        
        result = dict(created)
        if isinstance(result.get("structured_data"), str):
            result["structured_data"] = json.loads(result["structured_data"])
        return result


# ============================================================================
# UPDATE
# ============================================================================


@router.patch("/entries/{entry_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_entry(
    entry_id: str,
    payload: KnowledgeBaseUpdate,
    user: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Update an existing knowledge base entry (partial update)
    """
    # Get before state
    before_row = db.execute(
        text("""
            SELECT id, sub_key, category, title, content_markdown, 
                   structured_data, source_url, source_document, language,
                   is_active, is_verified, priority
            FROM knowledge_base WHERE id = CAST(:id AS uuid)
        """),
        {"id": entry_id},
    ).mappings().one_or_none()
    
    if not before_row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    before = dict(before_row)
    
    # Build update query dynamically
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")
    
    set_clauses = []
    params: dict[str, Any] = {"id": entry_id, "user_id": user["id"]}
    
    for key, value in updates.items():
        if key == "structured_data":
            set_clauses.append(f"{key} = CAST(:{key} AS jsonb)")
            params[key] = json.dumps(value)
        else:
            set_clauses.append(f"{key} = :{key}")
            params[key] = value
    
    set_clauses.append("updated_by = CAST(:user_id AS uuid)")
    set_clauses.append("updated_at = NOW()")
    
    update_query = f"""
        UPDATE knowledge_base
        SET {', '.join(set_clauses)}
        WHERE id = CAST(:id AS uuid)
        RETURNING id::text
    """
    
    result_id = db.execute(text(update_query), params).scalar_one_or_none()
    
    if not result_id:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    _audit(db, user["id"], "update", result_id, before, updates, "Partial update")
    _commit(db, "Failed to update knowledge entry")
    
    # Fetch updated record
    updated = db.execute(
        text("""
            SELECT 
                id, sub_key, category, title, content_markdown,
                structured_data, source_url, source_document, language,
                is_active, is_verified, priority, created_at, updated_at,
                created_by, updated_by
            FROM knowledge_base WHERE id = CAST(:id AS uuid)
        """),
        {"id": result_id},
    ).mappings().one()
    
    result = dict(updated)
    if isinstance(result.get("structured_data"), str):
        result["structured_data"] = json.loads(result["structured_data"])
    return result


# ============================================================================
# SOFT DELETE (DEACTIVATE)
# ============================================================================


@router.delete("/entries/{entry_id}")
def deactivate_knowledge_entry(
    entry_id: str,
    user: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Soft delete: Set is_active = false (non-destructive)
    """
    before_row = db.execute(
        text("SELECT id, sub_key, title, is_active FROM knowledge_base WHERE id = CAST(:id AS uuid)"),
        {"id": entry_id},
    ).mappings().one_or_none()
    
    if not before_row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    before = dict(before_row)
    
    row = db.execute(
        text("""
            UPDATE knowledge_base
            SET is_active = FALSE, updated_by = CAST(:user_id AS uuid), updated_at = NOW()
            WHERE id = CAST(:id AS uuid)
            RETURNING id::text, sub_key, title
        """),
        {"id": entry_id, "user_id": user["id"]},
    ).mappings().one()
    
    result = dict(row)
    _audit(db, user["id"], "soft_delete", entry_id, before, {"is_active": False}, "Entry deactivated")
    db.commit()
    
    return {"deleted": True, "deactivated": True, **result}


@router.post("/entries/{entry_id}/activate")
def activate_knowledge_entry(
    entry_id: str,
    user: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Reactivate a soft-deleted entry
    """
    row = db.execute(
        text("""
            UPDATE knowledge_base
            SET is_active = TRUE, updated_by = CAST(:user_id AS uuid), updated_at = NOW()
            WHERE id = CAST(:id AS uuid)
            RETURNING id::text, sub_key, title
        """),
        {"id": entry_id, "user_id": user["id"]},
    ).mappings().one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    result = dict(row)
    _audit(db, user["id"], "reactivate", entry_id, None, {"is_active": True}, "Entry reactivated")
    db.commit()
    
    return {"activated": True, **result}


# ============================================================================
# BULK OPERATIONS
# ============================================================================


@router.post("/bulk-import", response_model=KnowledgeBaseBulkImportResult)
def bulk_import_entries(
    payload: KnowledgeBaseBulkImport,
    user: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Bulk import knowledge entries (UPSERT mode)
    """
    success_count = 0
    error_count = 0
    errors = []
    warnings = []
    
    for idx, entry in enumerate(payload.entries):
        try:
            # Check if exists
            existing = db.execute(
                text("SELECT id FROM knowledge_base WHERE sub_key = :sub_key"),
                {"sub_key": entry.sub_key.lower()},
            ).scalar_one_or_none()
            
            if existing and not payload.overwrite_existing:
                warnings.append(f"Row {idx + 1}: Entry '{entry.sub_key}' already exists, skipped")
                continue
            
            if existing:
                # Update
                db.execute(
                    text("""
                        UPDATE knowledge_base
                        SET 
                            category = :category, title = :title,
                            content_markdown = :content_markdown,
                            structured_data = CAST(:structured_data AS jsonb),
                            source_url = :source_url, source_document = :source_document,
                            language = :language, is_active = :is_active,
                            is_verified = :is_verified, priority = :priority,
                            updated_by = CAST(:user_id AS uuid), updated_at = NOW()
                        WHERE id = CAST(:id AS uuid)
                    """),
                    {
                        "id": existing,
                        "category": entry.category.value,
                        "title": entry.title,
                        "content_markdown": entry.content_markdown,
                        "structured_data": json.dumps(entry.structured_data),
                        "source_url": entry.source_url,
                        "source_document": entry.source_document,
                        "language": entry.language,
                        "is_active": entry.is_active,
                        "is_verified": entry.is_verified,
                        "priority": entry.priority,
                        "user_id": user["id"],
                    },
                )
                _audit(db, user["id"], "bulk_upsert_update", str(existing), None, entry.model_dump(), "Bulk import")
            else:
                # Insert
                entry_id = db.execute(
                    text("""
                        INSERT INTO knowledge_base (
                            sub_key, category, title, content_markdown, structured_data,
                            source_url, source_document, language, is_active, is_verified,
                            priority, created_by, updated_by
                        )
                        VALUES (
                            :sub_key, :category, :title, :content_markdown,
                            CAST(:structured_data AS jsonb), :source_url, :source_document,
                            :language, :is_active, :is_verified, :priority,
                            CAST(:user_id AS uuid), CAST(:user_id AS uuid)
                        )
                        RETURNING id::text
                    """),
                    {
                        "sub_key": entry.sub_key.lower(),
                        "category": entry.category.value,
                        "title": entry.title,
                        "content_markdown": entry.content_markdown,
                        "structured_data": json.dumps(entry.structured_data),
                        "source_url": entry.source_url,
                        "source_document": entry.source_document,
                        "language": entry.language,
                        "is_active": entry.is_active,
                        "is_verified": entry.is_verified,
                        "priority": entry.priority,
                        "user_id": user["id"],
                    },
                ).scalar_one()
                _audit(db, user["id"], "bulk_insert", entry_id, None, entry.model_dump(), "Bulk import")
            
            success_count += 1
            
        except Exception as e:
            error_count += 1
            errors.append({
                "row": idx + 1,
                "sub_key": entry.sub_key,
                "error": str(e),
            })
            db.rollback()
            continue
    
    if success_count > 0:
        db.commit()
    
    return {
        "success_count": success_count,
        "error_count": error_count,
        "errors": errors,
        "warnings": warnings,
    }


# ============================================================================
# SEARCH & STATS
# ============================================================================


@router.post("/search", response_model=list[KnowledgeBaseSearchResult])
def search_knowledge(
    payload: KnowledgeBaseSearchRequest,
    _: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Search knowledge base entries (full-text search on title and content)
    """
    offset = (payload.page - 1) * payload.page_size
    
    conditions = ["is_active = TRUE"] if payload.is_active else []
    params: dict[str, Any] = {
        "query": f"%{payload.query}%",
        "limit": payload.page_size,
        "offset": offset,
    }
    
    if payload.categories:
        placeholders = ", ".join(f":cat_{i}" for i in range(len(payload.categories)))
        conditions.append(f"category IN ({placeholders})")
        for i, cat in enumerate(payload.categories):
            params[f"cat_{i}"] = cat.value
    
    if payload.language:
        conditions.append("language = :language")
        params["language"] = payload.language
    
    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    
    query = f"""
        SELECT 
            id, sub_key, category, title,
            LEFT(content_markdown, 200) AS content_preview,
            priority, updated_at
        FROM knowledge_base
        WHERE {where_clause}
          AND (title ILIKE :query OR content_markdown ILIKE :query OR sub_key ILIKE :query)
        ORDER BY priority ASC, updated_at DESC
        LIMIT :limit OFFSET :offset
    """
    
    rows = db.execute(text(query), params).mappings().all()
    
    return [dict(row) for row in rows]


@router.get("/stats", response_model=KnowledgeBaseStats)
def get_knowledge_stats(
    _: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Get knowledge base statistics
    """
    # Total counts
    counts = db.execute(
        text("""
            SELECT 
                COUNT(*)::int AS total_entries,
                COUNT(*) FILTER (WHERE is_active = TRUE)::int AS active_entries,
                COUNT(*) FILTER (WHERE is_active = FALSE)::int AS inactive_entries,
                COUNT(*) FILTER (WHERE is_verified = FALSE AND is_active = TRUE)::int AS pending_verification
            FROM knowledge_base
        """)
    ).mappings().one()
    
    # By category
    by_category = db.execute(
        text("""
            SELECT category, COUNT(*)::int AS count
            FROM knowledge_base
            WHERE is_active = TRUE
            GROUP BY category
            ORDER BY count DESC
        """)
    ).mappings().all()
    
    # By language
    by_language = db.execute(
        text("""
            SELECT language, COUNT(*)::int AS count
            FROM knowledge_base
            WHERE is_active = TRUE
            GROUP BY language
            ORDER BY count DESC
        """)
    ).mappings().all()
    
    # Recent updates
    recent = db.execute(
        text("""
            SELECT 
                id, sub_key, category, title, content_markdown,
                structured_data, source_url, source_document, language,
                is_active, is_verified, priority, created_at, updated_at,
                created_by, updated_by
            FROM knowledge_base
            WHERE is_active = TRUE
            ORDER BY updated_at DESC
            LIMIT 5
        """)
    ).mappings().all()
    
    recent_entries = []
    for row in recent:
        entry = dict(row)
        if isinstance(entry.get("structured_data"), str):
            entry["structured_data"] = json.loads(entry["structured_data"])
        recent_entries.append(entry)
    
    return {
        **dict(counts),
        "by_category": {row["category"]: row["count"] for row in by_category},
        "by_language": {row["language"]: row["count"] for row in by_language},
        "recent_updates": recent_entries,
    }


# ============================================================================
# CACHE & PROMPT PREVIEW
# ============================================================================


@router.post("/cache/invalidate")
def invalidate_cache(
    payload: CacheInvalidationRequest,
    user: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Invalidate prompt assembly cache
    (To be implemented with Redis/memory cache layer)
    """
    # Placeholder for cache invalidation logic
    # This will trigger prompt reassembly on next chat request
    
    categories = payload.categories if payload.categories else ["all"]
    
    _audit(
        db,
        user["id"],
        "cache_invalidate",
        "system",
        None,
        {"categories": [c.value for c in categories] if payload.categories else ["all"]},
        "Cache invalidated by admin"
    )
    db.commit()
    
    return {
        "invalidated": True,
        "categories": [c.value for c in categories] if payload.categories else ["all"],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/prompt-preview/{category}", response_model=PromptAssemblyPreview)
def preview_prompt_assembly(
    category: KnowledgeCategory,
    _: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Preview how knowledge entries will be assembled into system prompt
    """
    rows = db.execute(
        text("""
            SELECT sub_key, title, content_markdown, structured_data
            FROM knowledge_base
            WHERE category = :category AND is_active = TRUE
            ORDER BY priority ASC, updated_at DESC
        """),
        {"category": category.value},
    ).mappings().all()
    
    if not rows:
        return {
            "category": category,
            "included_entries": [],
            "assembled_content": f"[No active {category.value} entries found - fallback will be used]",
            "fallback_used": True,
            "total_tokens": None,
        }
    
    # Assemble content
    included = []
    content_parts = [f"======== {category.value.upper().replace('_', ' ')} ========\n"]
    
    for row in rows:
        included.append(row["sub_key"])
        content_parts.append(f"\n## {row['title']}\n")
        content_parts.append(row["content_markdown"])
        content_parts.append("\n")
    
    assembled = "\n".join(content_parts)
    
    # Rough token estimation (1 token ≈ 4 chars)
    token_estimate = len(assembled) // 4
    
    return {
        "category": category,
        "included_entries": included,
        "assembled_content": assembled,
        "fallback_used": False,
        "total_tokens": token_estimate,
    }


# ============================================================================
# AUDIT LOG
# ============================================================================


@router.get("/audit-log")
def get_audit_log(
    entry_id: str | None = None,
    action: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(admin_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Retrieve audit log for knowledge base operations
    """
    conditions = []
    params: dict[str, Any] = {"limit": limit}
    
    if entry_id:
        conditions.append("knowledge_base_id = CAST(:entry_id AS uuid)")
        params["entry_id"] = entry_id
    if action:
        conditions.append("action = :action")
        params["action"] = action
    
    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    
    query = f"""
        SELECT 
            id, knowledge_base_id, action, changed_by, changed_at,
            before_data, after_data, change_reason
        FROM knowledge_base_audit
        WHERE {where_clause}
        ORDER BY changed_at DESC
        LIMIT :limit
    """
    
    rows = db.execute(text(query), params).mappings().all()
    
    return [dict(row) for row in rows]
