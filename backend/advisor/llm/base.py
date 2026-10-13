"""Provider-neutral LLM interface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class Message:
    role: str  # system | user | assistant
    content: str


@dataclass(slots=True)
class GenParams:
    temperature: float = 0.2
    max_tokens: int = 1400
    timeout: float = 90.0
    json_mode: bool = False


@dataclass(slots=True)
class Usage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    first_token_ms: int | None = None


class ProviderError(Exception):
    """A provider failed. ``kind`` drives failover and what the admin is told."""

    def __init__(self, provider: str, kind: str, message: str, retryable: bool = True):
        super().__init__(f"[{provider}] {kind}: {message}")
        self.provider = provider
        self.kind = kind  # auth | quota | timeout | unavailable | blocked | bad_request | model_missing
        self.message = message
        self.retryable = retryable


class MidStreamError(ProviderError):
    """Failure after some text was already streamed to the user."""


@dataclass(slots=True)
class ProviderStatus:
    name: str
    configured: bool
    healthy: bool
    model: str = ""
    detail: str = ""
    models: list[str] = field(default_factory=list)


class LLMProvider(Protocol):
    name: str
    model: str

    def stream(self, messages: list[Message], params: GenParams) -> AsyncIterator[str]: ...

    async def complete(self, messages: list[Message], params: GenParams) -> str: ...

    async def status(self) -> ProviderStatus: ...
