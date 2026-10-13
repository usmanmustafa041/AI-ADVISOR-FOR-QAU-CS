"""Google Gemini via the public REST API (streaming SSE)."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

import httpx

from advisor.llm.base import GenParams, Message, MidStreamError, ProviderError, ProviderStatus, Usage

BASE = "https://generativelanguage.googleapis.com/v1beta"


def _safe(text: str, key: str) -> str:
    return text.replace(key, "***") if key else text


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, thinking_budget: int = 0, base_url: str = BASE):
        self.api_key = api_key
        self.model = model.removeprefix("models/")
        self.thinking_budget = thinking_budget
        self.base_url = base_url.rstrip("/")
        self.last_usage = Usage()

    # ------------------------------------------------------------------ request shaping
    def _body(self, messages: list[Message], params: GenParams, with_thinking: bool) -> dict:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        contents = []
        for m in messages:
            if m.role == "system":
                continue
            role = "model" if m.role == "assistant" else "user"
            if contents and contents[-1]["role"] == role:  # Gemini requires alternation
                contents[-1]["parts"][0]["text"] += "\n\n" + m.content
            else:
                contents.append({"role": role, "parts": [{"text": m.content}]})
        gen: dict = {"temperature": params.temperature, "maxOutputTokens": params.max_tokens}
        if params.json_mode:
            gen["responseMimeType"] = "application/json"
        if with_thinking and re.search(r"2\.5|3", self.model):
            gen["thinkingConfig"] = {"thinkingBudget": self.thinking_budget}
        body: dict = {"contents": contents, "generationConfig": gen}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        body["safetySettings"] = [
            {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
            for c in (
                "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ]
        return body

    def _raise_for(self, status: int, payload: str) -> None:
        detail = ""
        try:
            detail = json.loads(payload).get("error", {}).get("message", "")
        except (json.JSONDecodeError, AttributeError):
            detail = payload[:200]
        detail = _safe(detail, self.api_key)
        low = detail.lower()
        if status in (400, 401, 403) and ("api key" in low or "api_key" in low or status in (401, 403)):
            raise ProviderError(self.name, "auth", detail or "API key rejected", retryable=False)
        if status == 429:
            raise ProviderError(self.name, "quota", detail or "rate limit or quota exceeded")
        if status == 404:
            raise ProviderError(self.name, "model_missing", detail or f"model {self.model} not found", retryable=False)
        if status == 400:
            raise ProviderError(self.name, "bad_request", detail, retryable=False)
        raise ProviderError(self.name, "unavailable", detail or f"HTTP {status}")

    # ------------------------------------------------------------------ streaming
    async def stream(self, messages: list[Message], params: GenParams) -> AsyncIterator[str]:
        url = f"{self.base_url}/models/{self.model}:streamGenerateContent"
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        emitted = False
        attempts = [True, False]  # first with thinkingConfig, then without if rejected
        for with_thinking in attempts:
            body = self._body(messages, params, with_thinking)
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(params.timeout, connect=10)) as client:
                    async with client.stream(
                        "POST", url, params={"alt": "sse"}, headers=headers, json=body
                    ) as resp:
                        if resp.status_code != 200:
                            payload = (await resp.aread()).decode("utf-8", "replace")
                            if (
                                resp.status_code == 400
                                and with_thinking
                                and "thinking" in payload.lower()
                            ):
                                continue  # model can't disable thinking; retry plain
                            self._raise_for(resp.status_code, payload)
                        async for line in resp.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if not data or data == "[DONE]":
                                continue
                            try:
                                event = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            text = self._extract(event)
                            if text:
                                emitted = True
                                yield text
                        return
            except httpx.TimeoutException as exc:
                err = ProviderError(self.name, "timeout", f"timed out: {type(exc).__name__}")
                raise (MidStreamError(self.name, "timeout", err.message) if emitted else err) from exc
            except httpx.HTTPError as exc:
                err = ProviderError(self.name, "unavailable", _safe(str(exc), self.api_key))
                raise (MidStreamError(self.name, "unavailable", err.message) if emitted else err) from exc
        raise ProviderError(self.name, "bad_request", "request rejected by Gemini", retryable=False)

    def _extract(self, event: dict) -> str:
        fb = event.get("promptFeedback", {})
        if fb.get("blockReason"):
            raise ProviderError(self.name, "blocked", f"prompt blocked: {fb['blockReason']}", retryable=True)
        usage = event.get("usageMetadata")
        if usage:
            self.last_usage = Usage(usage.get("promptTokenCount"), usage.get("candidatesTokenCount"))
        out = []
        for cand in event.get("candidates", []):
            if cand.get("finishReason") in ("SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "RECITATION") and not (
                cand.get("content", {}).get("parts")
            ):
                raise ProviderError(self.name, "blocked", f"response blocked: {cand['finishReason']}")
            for part in cand.get("content", {}).get("parts", []):
                if part.get("thought"):
                    continue  # hidden reasoning summaries are not user-facing
                if "text" in part:
                    out.append(part["text"])
        return "".join(out)

    async def complete(self, messages: list[Message], params: GenParams) -> str:
        return "".join([chunk async for chunk in self.stream(messages, params)])

    # ------------------------------------------------------------------ diagnostics
    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{self.base_url}/models", params={"pageSize": 200}, headers={"x-goog-api-key": self.api_key}
            )
        if resp.status_code != 200:
            self._raise_for(resp.status_code, resp.text)
        names = []
        for m in resp.json().get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                names.append(m["name"].removeprefix("models/"))
        return sorted(names)

    async def status(self) -> ProviderStatus:
        try:
            models = await self.list_models()
        except ProviderError as exc:
            return ProviderStatus(self.name, True, False, self.model, f"{exc.kind}: {exc.message}")
        except httpx.HTTPError as exc:
            return ProviderStatus(self.name, True, False, self.model, _safe(str(exc), self.api_key))
        ok = self.model in models
        return ProviderStatus(
            self.name, True, ok, self.model,
            "ready" if ok else f"key works, but model '{self.model}' is not available to it",
            models,
        )
