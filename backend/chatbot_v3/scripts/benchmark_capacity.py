"""Small real-model queue trial; no inference from HTTP status to answer quality."""

import asyncio
import json
import time

import httpx

from chatbot_v3.settings import settings


async def main():
    async with httpx.AsyncClient(timeout=240, trust_env=False) as client:

        async def request(i):
            start = time.perf_counter()
            response = await client.post(
                "http://127.0.0.1:8010/api/v3/chat",
                json={"message": "Explain a stack in two short sentences."},
            )
            return {
                "request": i,
                "status": response.status_code,
                "client_latency_ms": round((time.perf_counter() - start) * 1000),
                "raw_response": response.json(),
            }

        responses = await asyncio.gather(*(request(i) for i in range(3)))
        memory = (await client.get(settings().model_url + "/api/ps")).json()
    report = {
        "concurrent_requests": 3,
        "effective_model": settings().model,
        "queue_size_including_active": settings().queue_size,
        "responses": responses,
        "ollama_memory": memory,
        "limitation": "Single-process three-request trial only. Busy rejections are intentional; this is not a production throughput estimate or factual quality score.",
    }
    path = settings().data_dir / "evaluation/capacity-benchmark.json"
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({"artifact": str(path), "statuses": [r["status"] for r in responses]}))


if __name__ == "__main__":
    asyncio.run(main())
