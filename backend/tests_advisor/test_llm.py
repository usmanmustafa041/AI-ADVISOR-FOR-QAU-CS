import asyncio
import json

import httpx
import pytest

from advisor.llm import gemini as gemini_mod
from advisor.llm import ollama as ollama_mod
from advisor.llm.base import GenParams, Message, MidStreamError, ProviderError
from advisor.llm.gemini import GeminiProvider
from advisor.llm.ollama import OllamaProvider, _ThinkFilter

MSGS = [Message("system", "be brief"), Message("user", "hi"), Message("assistant", "hello"), Message("user", "again")]
P = GenParams(max_tokens=50, timeout=5)


def sse(*events):
    return "".join(f"data: {json.dumps(e)}\n\n" for e in events).encode()


def patch_client(monkeypatch, module, handler):
    real = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        return real(*a, **kw)

    monkeypatch.setattr(module.httpx, "AsyncClient", factory)


def collect(provider):
    async def go():
        return "".join([c async for c in provider.stream(MSGS, P)])

    return asyncio.run(go())


def test_gemini_streams_text_and_hides_thought_parts(monkeypatch):
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["key"], seen["body"] = str(req.url), req.headers.get("x-goog-api-key"), json.loads(req.content)
        return httpx.Response(200, content=sse(
            {"candidates": [{"content": {"parts": [{"text": "plan", "thought": True}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "Hello "}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "world"}]}, "finishReason": "STOP"}]},
        ))

    patch_client(monkeypatch, gemini_mod, handler)
    assert collect(GeminiProvider("SECRETKEY", "gemini-2.5-flash")) == "Hello world"
    assert seen["key"] == "SECRETKEY" and "SECRETKEY" not in seen["url"]  # key in header, never in the URL
    body = seen["body"]
    assert body["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}


@pytest.mark.parametrize(
    "status,payload,kind",
    [
        (400, {"error": {"message": "API key not valid. Please pass a valid API key."}}, "auth"),
        (403, {"error": {"message": "denied"}}, "auth"),
        (429, {"error": {"message": "quota"}}, "quota"),
        (404, {"error": {"message": "model not found"}}, "model_missing"),
        (503, {"error": {"message": "overloaded"}}, "unavailable"),
    ],
)
def test_gemini_error_classification(monkeypatch, status, payload, kind):
    patch_client(monkeypatch, gemini_mod, lambda req: httpx.Response(status, json=payload))
    with pytest.raises(ProviderError) as exc:
        collect(GeminiProvider("test-key-123", "gemini-2.5-flash"))
    assert exc.value.kind == kind


def test_gemini_retries_without_thinking_config_when_model_rejects_it(monkeypatch):
    calls = []

    def handler(req):
        body = json.loads(req.content)
        calls.append("thinkingConfig" in body["generationConfig"])
        if calls[-1]:
            return httpx.Response(400, json={"error": {"message": "Thinking can't be disabled for this model"}})
        return httpx.Response(200, content=sse({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}))

    patch_client(monkeypatch, gemini_mod, handler)
    assert collect(GeminiProvider("test-key-123", "gemini-2.5-pro")) == "ok" and calls == [True, False]


def test_gemini_safety_block_is_reported(monkeypatch):
    patch_client(monkeypatch, gemini_mod, lambda r: httpx.Response(200, content=sse({"promptFeedback": {"blockReason": "SAFETY"}})))
    with pytest.raises(ProviderError) as exc:
        collect(GeminiProvider("test-key-123", "gemini-2.5-flash"))
    assert exc.value.kind == "blocked"


def test_gemini_never_leaks_key_in_errors(monkeypatch):
    def handler(req):
        raise httpx.ConnectError("failed connecting with key=SUPERSECRET")

    patch_client(monkeypatch, gemini_mod, handler)
    with pytest.raises(ProviderError) as exc:
        collect(GeminiProvider("SUPERSECRET", "gemini-2.5-flash"))
    assert "SUPERSECRET" not in str(exc.value)


def ndjson(*events):
    return "".join(json.dumps(e) + "\n" for e in events).encode()


def test_ollama_streams_and_sets_think_false(monkeypatch):
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, content=ndjson(
            {"message": {"content": "<think>hidden"}}, {"message": {"content": " reasoning</think>Hel"}},
            {"message": {"content": "lo"}}, {"done": True, "prompt_eval_count": 10, "eval_count": 2},
        ))

    patch_client(monkeypatch, ollama_mod, handler)
    assert collect(OllamaProvider("http://x", "qwen3:8b")) == "Hello"
    assert seen["body"]["think"] is False and seen["body"]["options"]["num_ctx"] == 12288


def test_ollama_missing_model(monkeypatch):
    patch_client(monkeypatch, ollama_mod, lambda r: httpx.Response(404, json={"error": "model 'x' not found"}))
    with pytest.raises(ProviderError) as exc:
        collect(OllamaProvider("http://x", "x"))
    assert exc.value.kind == "model_missing" and not exc.value.retryable


def test_ollama_unreachable(monkeypatch):
    def handler(req):
        raise httpx.ConnectError("refused")

    patch_client(monkeypatch, ollama_mod, handler)
    with pytest.raises(ProviderError) as exc:
        collect(OllamaProvider("http://x", "m"))
    assert exc.value.kind == "unavailable"


def test_think_filter_handles_split_tags():
    f = _ThinkFilter()
    out = "".join(f.feed(p) for p in ["a<th", "ink>zzz</th", "ink>b"]) + f.flush()
    assert out == "ab"
