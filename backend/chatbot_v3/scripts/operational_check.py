"""Real preview HTTP capacity and cancellation checks; no answer-accuracy scoring."""

import asyncio
import json
import time

import httpx

from chatbot_v3.settings import settings


async def main():
    headers = {"X-Developer-Token": settings().developer_token}
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8010", timeout=240, trust_env=False
    ) as client:

        async def request():
            started = time.perf_counter()
            response = await client.post(
                "/api/v3/chat", json={"message": "Explain recursion in one short sentence."}
            )
            return {
                "status": response.status_code,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "retry_after": response.headers.get("retry-after"),
                "response": response.json(),
            }

        capacity = await asyncio.gather(*(request() for _ in range(3)))
        before = (await client.get("/api/v3/development/metrics", headers=headers)).json()
        trace_id = None
        async with client.stream(
            "POST",
            "/api/v3/chat/stream",
            json={"message": "Explain merge sort with a detailed worked example and pseudocode."},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    trace_id = json.loads(line[6:]).get("trace_id", trace_id)
                if line == "event: token":
                    break
        for _ in range(50):
            after = (await client.get("/api/v3/development/metrics", headers=headers)).json()
            if after["queue_depth"] == 0 and after["cancelled"] > before["cancelled"]:
                break
            await asyncio.sleep(0.2)
        following = await request()
        trace = (
            (await client.get("/api/v3/development/traces/" + trace_id, headers=headers)).json()
            if trace_id
            else None
        )
        report = {
            "capacity": capacity,
            "cancelled_trace_id": trace_id,
            "cancelled_counter_delta": after["cancelled"] - before["cancelled"],
            "queue_depth_after_disconnect": after["queue_depth"],
            "cancelled_trace": trace,
            "following_request": following,
            "capacity_passed": sorted(r["status"] for r in capacity) == [200, 200, 503],
            "cancellation_passed": after["cancelled"] > before["cancelled"]
            and after["queue_depth"] == 0
            and following["status"] == 200,
            "reviewed_answer_accuracy": None,
        }
        (settings().data_dir / "evaluation/recovery-operational-check.json").write_text(
            json.dumps(report, indent=2)
        )
        print(
            json.dumps(
                {
                    k: v
                    for k, v in report.items()
                    if k not in {"capacity", "cancelled_trace", "following_request"}
                }
            )
        )
        if not report["capacity_passed"] or not report["cancellation_passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
