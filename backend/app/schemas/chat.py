from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    context_course_code: str | None = Field(
        default=None, pattern=r"^[A-Za-z]{2,4}-?\d{3}$"
    )


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
