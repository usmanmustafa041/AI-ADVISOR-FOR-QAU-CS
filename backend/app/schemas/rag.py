from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class RagCitation(BaseModel):
    document_title: str
    source_code: str
    source_url: str | None
    page_number: int | None
    section_title: str | None
    similarity: float


class RagSearchResult(BaseModel):
    content: str
    citation: RagCitation


class RagSearchResponse(BaseModel):
    query: str
    results: list[RagSearchResult]
    verified_sources_only: bool = True
    notice: str | None = None

