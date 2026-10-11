from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="V3_", env_file=ROOT / "backend/.env.v3", extra="ignore"
    )
    data_dir: Path = ROOT / ".runtime/chatbot-v3"
    model: str = "qwen3.5:27b"
    model_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 180
    queue_timeout_seconds: float = 120
    queue_size: int = Field(default=2, ge=1, le=32)
    context_tokens: int = 16384
    output_tokens: int = 3200
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_device: str = "cpu"
    reranker_model: str = ""
    local_files_only: bool = True
    developer_token: str = ""
    cors_origins: list[str] = ["http://127.0.0.1:5180", "http://localhost:5180"]
    store_traces: bool = False
    guest_ttl_seconds: int = 3600
    history_days: int = 90

    @model_validator(mode="after")
    def local_inference(self):
        from urllib.parse import urlsplit

        u = urlsplit(self.model_url)
        if (
            u.scheme != "http"
            or u.hostname not in {"localhost", "127.0.0.1", "ollama", "host.docker.internal"}
            or u.username
        ):
            raise ValueError(
                "Only explicitly local Ollama inference is supported; hosted adapters are disabled"
            )
        if "cloud" in self.model.lower():
            raise ValueError("Cloud model tags are prohibited")
        return self


@lru_cache
def settings():
    return Settings()
