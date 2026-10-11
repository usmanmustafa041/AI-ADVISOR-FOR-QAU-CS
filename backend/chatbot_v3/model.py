import json
from contextlib import asynccontextmanager

import httpx

from chatbot_v3.settings import settings


class ModelUnavailable(RuntimeError):
    pass


class Ollama:
    def __init__(self, config=None):
        self.config = config or settings()

    @asynccontextmanager
    async def client(self):
        async with httpx.AsyncClient(
            base_url=self.config.model_url,
            timeout=httpx.Timeout(self.config.timeout_seconds, connect=5),
            trust_env=False,
        ) as client:
            yield client

    async def available(self):
        try:
            async with self.client() as c:
                r = await c.get("/api/tags", timeout=5)
                r.raise_for_status()
                models = r.json().get("models", [])
                item = next((m for m in models if m["name"] == self.config.model), None)
                if not item or item.get("remote_host") or item.get("remote_model"):
                    return False
                detail = await c.post("/api/show", json={"model": self.config.model}, timeout=5)
                detail.raise_for_status()
                info = detail.json()
                return not (info.get("remote_host") or info.get("remote_model"))
        except (httpx.HTTPError, ValueError):
            return False

    async def structured(self, messages, schema):
        payload = {
            "model": self.config.model,
            "messages": messages,
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": "20m",
            "options": {
                "temperature": 0,
                "num_ctx": self.config.context_tokens,
                "num_predict": 1800,
            },
        }
        try:
            async with self.client() as c:
                r = await c.post("/api/chat", json=payload)
                r.raise_for_status()
                return json.loads(r.json()["message"]["content"])
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise ModelUnavailable(
                "Local model could not interpret the question. Please retry shortly."
            ) from e

    async def stream(self, messages, schema=None):
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "think": False,
            "keep_alive": "20m",
            "options": {
                "temperature": 0.25,
                "num_ctx": self.config.context_tokens,
                "num_predict": self.config.output_tokens,
            },
        }
        if schema:
            payload["format"] = schema
        try:
            finished = False
            async with self.client() as c:
                async with c.stream("POST", "/api/chat", json=payload) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get("error"):
                            raise ModelUnavailable(
                                "Local model could not finish this answer. Please retry."
                            )
                        if data.get("message", {}).get("content"):
                            yield data["message"]["content"]
                        if data.get("done") and data.get("done_reason") == "length":
                            raise ModelUnavailable(
                                "The answer exceeded the local model budget. Please narrow the question."
                            )
                        if data.get("done"):
                            finished = True
                if not finished:
                    raise ModelUnavailable(
                        "The local model stream ended before completion. Please retry."
                    )
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise ModelUnavailable(
                "The local model is temporarily unavailable. Please retry shortly."
            ) from e
