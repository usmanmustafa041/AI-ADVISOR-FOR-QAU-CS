"""Local Ollama server (chat API, streaming NDJSON)."""

from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncIterator

import httpx

from advisor.llm.base import GenParams, Message, MidStreamError, ProviderError, ProviderStatus, Usage


class _ThinkFilter:
    """Drops <think>…</think> blocks that some models emit despite think=false."""

    def __init__(self):
        self.buf = ""
        self.inside = False

    def feed(self, text: str) -> str:
        self.buf += text
        out = ""
        while True:
            if self.inside:
                end = self.buf.find("</think>")
                if end < 0:
                    self.buf = self.buf[-8:] if len(self.buf) > 8 else self.buf
                    return out
                self.buf = self.buf[end + 8 :].lstrip("\n")
                self.inside = False
            else:
                start = self.buf.find("<think>")
                if start >= 0:
                    out += self.buf[:start]
                    self.buf = self.buf[start + 7 :]
                    self.inside = True
                    continue
                # keep a possible partial tag at the end
                keep = 0
                for n in range(min(6, len(self.buf)), 0, -1):
                    if "<think>".startswith(self.buf[-n:]):
                        keep = n
                        break
                out += self.buf[: len(self.buf) - keep]
                self.buf = self.buf[len(self.buf) - keep :]
                return out

    def flush(self) -> str:
        out = "" if self.inside else self.buf
        self.buf = ""
        return out


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str, num_ctx: int = 12288, keep_alive: str = "30m"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self.last_usage = Usage()

    def _body(self, messages: list[Message], params: GenParams, stream: bool) -> dict:
        body = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "think": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": params.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": params.max_tokens,
                # small models can fall into repetition loops (seen with Urdu); damp them
                "repeat_penalty": 1.12,
                "top_p": 0.9,
                "top_k": 40,
            },
        }
        if params.json_mode:
            body["format"] = "json"
        return body

    async def stream(self, messages: list[Message], params: GenParams) -> AsyncIterator[str]:
        filt = _ThinkFilter()
        emitted = False
        started = time.monotonic()
        try:
            timeout = httpx.Timeout(params.timeout, connect=5)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=self._body(messages, params, True)
                ) as resp:
                    if resp.status_code != 200:
                        payload = (await resp.aread()).decode("utf-8", "replace")
                        msg = payload[:300]
                        try:
                            msg = json.loads(payload).get("error", msg)
                        except json.JSONDecodeError:
                            pass
                        if resp.status_code == 404 or "not found" in msg.lower():
                            raise ProviderError(
                                self.name, "model_missing",
                                f"model '{self.model}' is not installed in Ollama ({msg})", retryable=False,
                            )
                        raise ProviderError(self.name, "unavailable", f"HTTP {resp.status_code}: {msg}")
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if event.get("error"):
                            raise ProviderError(self.name, "unavailable", str(event["error"]))
                        piece = (event.get("message") or {}).get("content", "")
                        if piece:
                            text = filt.feed(piece)
                            if text:
                                if not emitted:
                                    self.last_usage = Usage(first_token_ms=int((time.monotonic() - started) * 1000))
                                emitted = True
                                yield text
                        if event.get("done"):
                            self.last_usage.prompt_tokens = event.get("prompt_eval_count")
                            self.last_usage.completion_tokens = event.get("eval_count")
                            break
            tail = filt.flush()
            if tail:
                yield tail
        except httpx.ConnectError as exc:
            raise ProviderError(self.name, "unavailable", f"cannot reach Ollama at {self.base_url}") from exc
        except httpx.TimeoutException as exc:
            err = ProviderError(self.name, "timeout", "model did not answer in time")
            raise (MidStreamError(self.name, "timeout", err.message) if emitted else err) from exc
        except httpx.HTTPError as exc:
            err = ProviderError(self.name, "unavailable", str(exc))
            raise (MidStreamError(self.name, "unavailable", err.message) if emitted else err) from exc

    async def complete(self, messages: list[Message], params: GenParams) -> str:
        text = "".join([c async for c in self.stream(messages, params)])
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    async def installed_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        return sorted(m["name"] for m in resp.json().get("models", []) if not m["name"].endswith("-cloud"))

    async def status(self) -> ProviderStatus:
        try:
            models = await self.installed_models()
        except httpx.HTTPError as exc:
            return ProviderStatus(self.name, True, False, self.model, f"Ollama not reachable: {exc}")
        ok = any(m == self.model or m.split(":")[0] == self.model for m in models)
        return ProviderStatus(
            self.name, True, ok, self.model,
            "ready" if ok else f"model '{self.model}' is not installed (run: ollama pull {self.model})",
            models,
        )
