"""Provider selection, failover, circuit breaking and concurrency control.

Order is decided per request from the administrator's settings: Gemini first when a key is
configured (or when forced), then local Ollama. Failures that happen *before* any text has
been streamed fail over silently; a failure after streaming began surfaces as
:class:`MidStreamError` so the caller can restart the answer cleanly on the next provider.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from advisor.config import Settings
from advisor.llm.base import GenParams, LLMProvider, Message, MidStreamError, ProviderError
from advisor.llm.gemini import GeminiProvider
from advisor.llm.ollama import OllamaProvider
from advisor.runtime_settings import RuntimeSettings

log = logging.getLogger("advisor.llm")

BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN = 45.0
MAX_WAITING = 24  # queued requests per local provider before we shed load


@dataclass
class Health:
    failures: int = 0
    open_until: float = 0.0
    last_error: str = ""
    ok: int = 0
    fail: int = 0
    latency_ms: list[int] = field(default_factory=list)

    def record_ok(self, ms: int) -> None:
        self.failures = 0
        self.ok += 1
        self.latency_ms = (self.latency_ms + [ms])[-200:]

    def record_fail(self, err: ProviderError) -> None:
        self.fail += 1
        self.last_error = f"{err.kind}: {err.message}"[:300]
        # Config errors should not hammer the API; transient ones trip the breaker.
        self.failures += 3 if not err.retryable else 1
        if self.failures >= BREAKER_THRESHOLD:
            self.open_until = time.monotonic() + (BREAKER_COOLDOWN * (4 if not err.retryable else 1))

    @property
    def open(self) -> bool:
        return time.monotonic() < self.open_until


class NoProviderAvailable(Exception):
    def __init__(self, errors: list[ProviderError]):
        super().__init__("; ".join(str(e) for e in errors) or "no AI provider is configured")
        self.errors = errors


class ProviderRouter:
    def __init__(self, settings: Settings, runtime: RuntimeSettings):
        self.s = settings
        self.rt = runtime
        self.health: dict[str, Health] = defaultdict(Health)
        self._sems: dict[str, asyncio.Semaphore] = {}
        self._waiting: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------ provider construction
    def candidates(self) -> list[LLMProvider]:
        rt = self.rt
        gemini = ollama = None
        key = rt.get("gemini.api_key")
        if key and rt.get("gemini.enabled"):
            gemini = GeminiProvider(key, rt.get("gemini.model"), int(rt.get("gemini.thinking_budget")))
        if rt.get("ollama.enabled"):
            ollama = OllamaProvider(
                rt.get("ollama.base_url"), rt.get("ollama.model"),
                self.s.ollama_num_ctx, self.s.ollama_keep_alive,
            )
        primary = rt.get("llm.primary")
        order = {"gemini": [gemini, ollama], "ollama": [ollama, gemini]}.get(primary, [gemini, ollama])
        return [p for p in order if p is not None]

    def _sem(self, name: str) -> asyncio.Semaphore:
        if name not in self._sems:
            n = self.s.llm_max_concurrency_remote if name == "gemini" else self.s.llm_max_concurrency_local
            self._sems[name] = asyncio.Semaphore(n)
        return self._sems[name]

    # ------------------------------------------------------------------ generation
    async def stream(
        self, messages: list[Message], params: GenParams, *, skip: set[str] | None = None
    ) -> AsyncIterator[tuple[str, str, str]]:
        """Yield ``(provider, model, text)``. Raises :class:`NoProviderAvailable` if all fail
        before producing text, or MidStreamError if a provider dies after producing some."""
        errors: list[ProviderError] = []
        providers = [p for p in self.candidates() if p.name not in (skip or set())]
        if not providers:
            raise NoProviderAvailable([ProviderError("router", "unavailable", "no AI provider is configured")])
        for idx, provider in enumerate(providers):
            h = self.health[provider.name]
            last = idx == len(providers) - 1
            if h.open and not last:
                errors.append(ProviderError(provider.name, "unavailable", f"paused after errors: {h.last_error}"))
                continue
            if self._waiting[provider.name] >= MAX_WAITING and not last:
                errors.append(ProviderError(provider.name, "unavailable", "queue full"))
                continue
            self._waiting[provider.name] += 1
            queued = True
            started = time.monotonic()
            try:
                async with self._sem(provider.name):
                    self._waiting[provider.name] -= 1
                    queued = False
                    got = False
                    async for text in provider.stream(messages, params):
                        got = True
                        yield provider.name, provider.model, text
                    if not got:
                        raise ProviderError(provider.name, "unavailable", "empty response")
                    h.record_ok(int((time.monotonic() - started) * 1000))
                    return
            except ProviderError as exc:
                h.record_fail(exc)
                log.warning("provider %s failed: %s", provider.name, exc)
                if isinstance(exc, MidStreamError):
                    raise
                errors.append(exc)
            finally:
                if queued:
                    self._waiting[provider.name] -= 1
        raise NoProviderAvailable(errors)

    async def complete(self, messages: list[Message], params: GenParams) -> tuple[str, str, str]:
        text = []
        name = model = ""
        async for name, model, chunk in self.stream(messages, params):
            text.append(chunk)
        return name, model, "".join(text).strip()

    # ------------------------------------------------------------------ diagnostics
    async def statuses(self) -> list[dict]:
        out = []
        rt = self.rt
        providers: list[LLMProvider] = []
        key = rt.get("gemini.api_key")
        if key:
            providers.append(GeminiProvider(key, rt.get("gemini.model"), 0))
        providers.append(OllamaProvider(rt.get("ollama.base_url"), rt.get("ollama.model")))
        results = await asyncio.gather(*(p.status() for p in providers), return_exceptions=True)
        for p, res in zip(providers, results, strict=True):
            h = self.health[p.name]
            if isinstance(res, Exception):
                item = {"name": p.name, "configured": True, "healthy": False, "model": p.model, "detail": str(res), "models": []}
            else:
                item = {
                    "name": res.name, "configured": res.configured, "healthy": res.healthy,
                    "model": res.model, "detail": res.detail, "models": res.models,
                }
            lat = sorted(h.latency_ms)
            item["stats"] = {
                "ok": h.ok, "failed": h.fail, "last_error": h.last_error,
                "paused": h.open, "p50_ms": lat[len(lat) // 2] if lat else None,
            }
            out.append(item)
        if not key:
            out.insert(0, {"name": "gemini", "configured": False, "healthy": False,
                           "model": rt.get("gemini.model"), "detail": "No API key set", "models": [], "stats": {}})
        return out
