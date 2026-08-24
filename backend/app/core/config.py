from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "QAU CS Academic Advisor API"
    app_env: str = "development"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg://qau_advisor:qau_advisor_local@localhost:55432/qau_advisor"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )
    embedding_provider: str = "deterministic"
    embedding_model: str = "deterministic-sha256-384"
    nlp_classifier_backend: str = "transformer"
    nlp_model_name: str = "distilbert-base-multilingual-cased"
    nlp_model_path: str = "models/qau-intent-distilmbert"
    nlp_max_length: int = Field(default=128, ge=16, le=512)
    llm_provider: str = "unconfigured"
    llm_model: str = ""
    cms_enabled: bool = False
    student_allowed_fields: list[str] = Field(default_factory=list)
    data_retention_days: int = Field(default=30, ge=1, le=3650)
    auth_secret: str = "local-development-secret-change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
