from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: UUID | None = None
    history: list[ConversationTurn] = Field(default_factory=list, max_length=8)
    language: Literal["english", "roman_urdu", "urdu"] | None = None
    context_course_code: str | None = Field(
        default=None, pattern=r"^[A-Za-z]{2,4}-?\d{3}$"
    )

    @field_validator("message")
    @classmethod
    def nonblank_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must contain text")
        return value


class ChatResponse(BaseModel):
    answer: str
    intent: str
    language: str
    confidence: float
    entities: dict[str, list[str]]
    model_backend: str
    model_name: str
    response_engine: str
    citations: list[dict]
    verified: bool
    session_id: str | None = None
    message_id: str | None = None
    query_scope: dict = Field(default_factory=dict)
    grounding_status: str = "insufficient_evidence"
    response_time_ms: int = 0
    retrieval_query: str = ""
    notices: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
