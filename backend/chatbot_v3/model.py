import asyncio
import json
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar

import httpx

from chatbot_v3.settings import settings


class ModelUnavailable(RuntimeError):
    pass


class OutputBudgetExceeded(ModelUnavailable):
    pass


call_metrics = ContextVar("qau_v3_model_call_metrics", default=None)


def record_call(metric, result=None):
    for key in ("load_duration", "prompt_eval_duration", "eval_duration", "total_duration"):
        if result and key in result:
            metric[key.replace("_duration", "_ms")] = round(result[key] / 1_000_000, 2)
    for key in ("prompt_eval_count", "eval_count", "done_reason"):
        if result and key in result:
            metric[key] = result[key]
    records = call_metrics.get()
    if records is not None:
        records.append(metric)


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
                local = not (info.get("remote_host") or info.get("remote_model"))
                return local
        except (httpx.HTTPError, ValueError):
            return False

    async def structured(self, messages, schema):
        started = time.perf_counter()
        result = None
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
            async with asyncio.timeout(self.config.timeout_seconds), self.client() as c:
                r = await c.post("/api/chat", json=payload)
                r.raise_for_status()
                result = r.json()
                if result.get("done_reason") == "length":
                    raise OutputBudgetExceeded("Local interpretation exceeded its output budget")
                return json.loads(result["message"]["content"])
        except TimeoutError as e:
            raise ModelUnavailable("Local interpretation exceeded its time budget") from e
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise ModelUnavailable(
                "Local model could not interpret the question. Please retry shortly."
            ) from e
        finally:
            record_call(
                {
                    "stage": "interpretation",
                    "wall_ms": round((time.perf_counter() - started) * 1000),
                },
                result,
            )

    async def stream(self, messages, schema=None):
        started, first, result = time.perf_counter(), None, None
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "think": False,
            "keep_alive": "20m",
            "options": {
                "temperature": 0 if schema else 0.2,
                "num_ctx": self.config.context_tokens,
                "num_predict": self.config.output_tokens
                if schema
                else min(self.config.output_tokens, 1200),
                "repeat_penalty": 1.1,
            },
        }
        if schema:
            payload["format"] = schema
        try:
            finished = False
            async with asyncio.timeout(self.config.timeout_seconds), self.client() as c:
                async with c.stream("POST", "/api/chat", json=payload) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        result = data
                        if data.get("error"):
                            raise ModelUnavailable(
                                "Local model could not finish this answer. Please retry."
                            )
                        if data.get("message", {}).get("content"):
                            if first is None:
                                first = round((time.perf_counter() - started) * 1000)
                            yield data["message"]["content"]
                        if data.get("done") and data.get("done_reason") == "length":
                            raise OutputBudgetExceeded(
                                "The model reached its answer budget before completing the response."
                            )
                        if data.get("done"):
                            finished = True
                if not finished:
                    raise ModelUnavailable(
                        "The local model stream ended before completion. Please retry."
                    )
        except TimeoutError as e:
            raise OutputBudgetExceeded("Local generation exceeded its time budget") from e
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise ModelUnavailable(
                "The local model is temporarily unavailable. Please retry shortly."
            ) from e
        finally:
            record_call(
                {
                    "stage": "generation",
                    "wall_ms": round((time.perf_counter() - started) * 1000),
                    "first_raw_token_ms": first,
                },
                result,
            )
