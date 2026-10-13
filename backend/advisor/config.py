"""Process-level configuration.

Only *infrastructure* settings live here (paths, ports, limits) and are read from the
environment. Settings an administrator changes at runtime (Gemini key, model names,
provider order, ...) are stored in the database; see :mod:`advisor.runtime_settings`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ADVISOR_",
        env_file=BACKEND_DIR / ".env.advisor",
        extra="ignore",
    )

    # --- storage -----------------------------------------------------------------
    data_dir: Path = BACKEND_DIR / "var" / "advisor"

    # --- website source ----------------------------------------------------------
    site_url: str = "https://cs.qau.edu.pk"
    # Hosts the crawler may follow *documents* (PDF etc.) on, besides the site itself.
    extra_hosts: list[str] = ["qau.edu.pk", "www.qau.edu.pk"]
    crawl_user_agent: str = "QAU-CS-Advisor-Indexer/1.0 (+mailto:cs@qau.edu.pk)"
    crawl_delay_seconds: float = 0.25
    crawl_concurrency: int = 4
    crawl_timeout_seconds: float = 45
    crawl_retries: int = 5
    crawl_max_pages: int = 900

    # --- retrieval ---------------------------------------------------------------
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_device: str = "cpu"
    # Cross-encoder reranker; empty string disables reranking.
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    models_local_only: bool = False
    retrieve_k: int = 40
    context_chunks: int = 8
    context_char_budget: int = 14000

    # --- generation --------------------------------------------------------------
    # Bootstrap defaults; the admin console overrides these at runtime.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    ollama_num_ctx: int = 12288
    ollama_keep_alive: str = "30m"
    llm_max_concurrency_local: int = 2
    llm_max_concurrency_remote: int = 24
    answer_timeout_seconds: float = 120

    # --- API / security ----------------------------------------------------------
    secret_key: str = ""  # master key for encrypting stored secrets; auto-generated if empty
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5180",
            "http://127.0.0.1:5180",
        ]
    )
    # Optional single sign-on with an existing student/admin portal: the URL of its "who am I" endpoint
    # (e.g. http://127.0.0.1:8001/api/v1/auth/me). The caller's Authorization header is forwarded to it.
    auth_verify_url: str = ""
    bootstrap_admin_user: str = ""
    bootstrap_admin_password: str = ""
    session_hours: int = 12
    rate_limit_per_minute: int = 20
    rate_limit_burst: int = 8
    trust_proxy_headers: bool = False
    history_retention_days: int = 90
    answer_cache_ttl_seconds: int = 6 * 3600
    max_question_chars: int = 1200
    serve_frontend_dir: Path | None = None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "advisor.sqlite3"

    @property
    def snapshot_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "indexes"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s


def reset_settings_cache() -> None:
    get_settings.cache_clear()
