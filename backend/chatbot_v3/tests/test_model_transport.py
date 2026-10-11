import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest
from chatbot_v3.model import ModelUnavailable, Ollama
from chatbot_v3.settings import Settings


def client_for(monkeypatch, model, handler):
    @asynccontextmanager
    async def client():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://localhost:11434"
        ) as c:
            yield c

    monkeypatch.setattr(model, "client", client)


def test_remote_model_is_rejected_even_when_tag_does_not_disclose_it(monkeypatch):
    model = Ollama(Settings(model="test-local"))

    def handle(request):
        data = (
            {"models": [{"name": "test-local"}]}
            if request.url.path == "/api/tags"
            else {"remote_model": "hosted-model"}
        )
        return httpx.Response(200, json=data)

    client_for(monkeypatch, model, handle)
    assert asyncio.run(model.available()) is False


def test_model_stream_requires_explicit_completion(monkeypatch):
    model = Ollama(Settings(model="test-local"))

    def handle(request):
        return httpx.Response(
            200, text=json.dumps({"message": {"content": "Incomplete text"}}) + "\n"
        )

    client_for(monkeypatch, model, handle)

    async def trial():
        return [part async for part in model.stream([{"role": "user", "content": "Hi"}])]

    with pytest.raises(ModelUnavailable, match="before completion"):
        asyncio.run(trial())
