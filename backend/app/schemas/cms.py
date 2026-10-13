"""
Pydantic schemas for Admin CMS (Knowledge Base Management)
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class KnowledgeCategory(str, Enum):
    """Knowledge base category enum"""
    SCHEME = "scheme"
    ADMISSION = "admission"
    FEE_STRUCTURE = "fee_structure"
    TIMETABLE = "timetable"
    COURSE = "course"
    POLICY = "policy"
    GENERAL_NOTICE = "general_notice"
    FAQ = "faq"
    CONTACT = "contact"
    OTHER = "other"


class KnowledgeBaseCreate(BaseModel):
    """Schema for creating a new knowledge base entry"""
    sub_key: str = Field(..., min_length=1, max_length=100, description="Unique identifier for upsert operations")
    category: KnowledgeCategory = Field(..., description="Knowledge category")
    title: str = Field(..., min_length=3, max_length=300, description="Entry title")
    content_markdown: str = Field(..., min_length=10, description="Markdown content")
    structured_data: dict[str, Any] = Field(default_factory=dict, description="Structured JSON data")
    source_url: str | None = Field(None, max_length=500, description="Source URL")
    source_document: str | None = Field(None, max_length=300, description="Source document reference")
    language: str = Field(default="en", min_length=2, max_length=10, description="Language code")
    is_active: bool = Field(default=True, description="Active status")
    is_verified: bool = Field(default=False, description="Verification status")
    priority: int = Field(default=100, ge=0, le=1000, description="Display priority")
    
    @field_validator('sub_key')
    @classmethod
    def validate_sub_key(cls, v: str) -> str:
        """Validate sub_key format"""
        # Only alphanumeric, underscore, hyphen
        if not all(c.isalnum() or c in ('_', '-') for c in v):
            raise ValueError("sub_key must contain only alphanumeric characters, underscores, and hyphens")
        return v.lower()


class KnowledgeBaseUpdate(BaseModel):
    """Schema for updating an existing knowledge base entry"""
    title: str | None = Field(None, min_length=3, max_length=300)
    content_markdown: str | None = Field(None, min_length=10)
    structured_data: dict[str, Any] | None = None
    source_url: str | None = Field(None, max_length=500)
    source_document: str | None = Field(None, max_length=300)
    language: str | None = Field(None, min_length=2, max_length=10)
    is_active: bool | None = None
    is_verified: bool | None = None
    priority: int | None = Field(None, ge=0, le=1000)


class KnowledgeBaseResponse(BaseModel):
    """Schema for knowledge base entry response"""
    id: UUID
    sub_key: str
    category: KnowledgeCategory
    title: str
    content_markdown: str
    structured_data: dict[str, Any]
    source_url: str | None
    source_document: str | None
    language: str
    is_active: bool
    is_verified: bool
    priority: int
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None
    
    class Config:
        from_attributes = True


class KnowledgeBaseListResponse(BaseModel):
    """Schema for paginated knowledge base list"""
    items: list[KnowledgeBaseResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class KnowledgeBaseBulkImport(BaseModel):
    """Schema for bulk import of knowledge entries"""
    entries: list[KnowledgeBaseCreate] = Field(..., min_length=1, max_length=100)
    overwrite_existing: bool = Field(default=False, description="Overwrite existing entries with same sub_key")


class KnowledgeBaseBulkImportResult(BaseModel):
    """Schema for bulk import result"""
    success_count: int
    error_count: int
    errors: list[dict[str, str]]
    warnings: list[str]


class KnowledgeBaseSearchRequest(BaseModel):
    """Schema for searching knowledge base"""
    query: str = Field(..., min_length=1, max_length=200)
    categories: list[KnowledgeCategory] | None = None
    language: str | None = None
    is_active: bool | None = True
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class KnowledgeBaseSearchResult(BaseModel):
    """Schema for search results"""
    id: UUID
    sub_key: str
    category: KnowledgeCategory
    title: str
    content_preview: str  # First 200 chars of content
    priority: int
    updated_at: datetime
    relevance_score: float | None = None


class KnowledgeBaseAuditLog(BaseModel):
    """Schema for knowledge base audit log entry"""
    id: UUID
    knowledge_base_id: UUID
    action: str
    changed_by: UUID | None
    changed_at: datetime
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    change_reason: str | None
    
    class Config:
        from_attributes = True


class KnowledgeBaseStats(BaseModel):
    """Schema for knowledge base statistics"""
    total_entries: int
    active_entries: int
    inactive_entries: int
    by_category: dict[str, int]
    by_language: dict[str, int]
    recent_updates: list[KnowledgeBaseResponse]
    pending_verification: int


class CacheInvalidationRequest(BaseModel):
    """Schema for cache invalidation request"""
    categories: list[KnowledgeCategory] | None = Field(None, description="Specific categories to invalidate")
    all: bool = Field(default=False, description="Invalidate entire cache")


class PromptAssemblyPreview(BaseModel):
    """Schema for previewing assembled system prompt"""
    category: KnowledgeCategory
    included_entries: list[str]  # sub_keys
    assembled_content: str
    fallback_used: bool
    total_tokens: int | None = None
