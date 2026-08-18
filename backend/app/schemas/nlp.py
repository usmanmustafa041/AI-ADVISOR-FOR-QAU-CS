from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class AnalyzeResponse(BaseModel):
    text: str
    language: str
    intent: str
    confidence: float
    entities: dict[str, list[str]]
    model_backend: str
    model_name: str


class ModelStatusResponse(BaseModel):
    requested_backend: str
    active_backend: str
    model_name: str
    configured_base_model: str
    artifact_path: str
    artifact_ready: bool
    fallback_active: bool
    error: str | None = None
