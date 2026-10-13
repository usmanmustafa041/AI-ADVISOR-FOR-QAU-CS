from functools import lru_cache

from pydantic import Field, model_validator
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
    embedding_provider: str = "sentence-transformer"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_local_files_only: bool = True
    embedding_cache_path: str = ""
    embedding_device: str = "cpu"
    nlp_classifier_backend: str = "transformer"
    nlp_model_name: str = "distilbert-base-multilingual-cased"
    nlp_model_path: str = "models/qau-intent-distilmbert"
    nlp_max_length: int = Field(default=128, ge=16, le=512)
    llm_provider: str = "unconfigured"
    llm_model: str = ""
    llm_base_url: str = "http://localhost:11434"
    llm_timeout_seconds: int = Field(default=25, ge=1, le=90)
    llm_check_claims: bool = True
    llm_keep_alive: str = "15m"
    rag_corpus_path: str = "data/rag/corpus.jsonl"
    rag_top_k: int = Field(default=6, ge=1, le=15)
    rag_candidate_k: int = Field(default=40, ge=10, le=100)
    rag_context_chars: int = Field(default=7000, ge=2000, le=40000)
    rag_semantic_min_score: float = Field(default=0.35, ge=0, le=1)
    rag_reranker_model: str = ""
    rag_include_database: bool = True
    knowledge_archive_path: str = "academic-data/crawl-archive"
    chat_request_timeout_seconds: int = Field(default=65, ge=10, le=180)
    chat_max_concurrent: int = Field(default=2, ge=1, le=16)
    educational_chat_enabled: bool = True
    cms_enabled: bool = False
    student_allowed_fields: list[str] = Field(default_factory=list)
    data_retention_days: int = Field(default=30, ge=1, le=3650)
    auth_secret: str = "local-development-secret-change-me"

    @model_validator(mode="after")
    def production_secret(self):
        if self.app_env == "production" and (
            len(self.auth_secret) < 32
            or self.auth_secret.startswith(("local-development", "qau-local-demo", "replace-"))
        ):
            raise ValueError(
                "Set AUTH_SECRET to a unique random value of at least 32 characters for production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
