"""Read-only HTTP dependency checks and a bounded guest concurrency exercise."""

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import atomic_write, utc_now


async def check(base_url, frontend_url, parallel):
    checks = []
    async with httpx.AsyncClient(base_url=base_url, timeout=80) as client:
        for route in (
            "/api/v1/health/ready",
            "/api/v1/programs",
            "/api/v1/courses",
            "/api/v1/fees",
            "/api/v1/timetable?academic_year=2026&term=Spring",
            "/api/v1/policies",
            "/api/v1/deadlines",
            "/api/v1/exams?academic_year=2026&term=Spring",
        ):
            response = await client.get(route)
            row = {"route": route, "status": response.status_code}
            if route.endswith("/ready"):
                row["readiness"] = response.json()
            checks.append(row)
        response = await client.get(frontend_url)
        checks.append({"route": frontend_url, "status": response.status_code})
        start = asyncio.Event()

        async def request(number):
            await start.wait()
            began = time.perf_counter()
            response = await client.post(
                "/api/v1/chat",
                json={
                    "message": "How long is the MS Data Science programme and what research "
                    "areas are available?",
                    "history": [],
                },
            )
            data = response.json()
            return {
                "request": number,
                "status": response.status_code,
                "wall_ms": round((time.perf_counter() - began) * 1000),
                "retry_after": response.headers.get("Retry-After"),
                "backend": data.get("model_backend"),
                "model": data.get("model_name"),
                "grounding_status": data.get("grounding_status"),
                "notices": data.get("notices", []),
                "citations": len(data.get("citations", [])),
            }

        tasks = [asyncio.create_task(request(i + 1)) for i in range(parallel)]
        start.set()
        rows = await asyncio.gather(*tasks)
    return {
        "created_at": utc_now(),
        "endpoint": base_url,
        "http_checks": checks,
        "http_checks_passed": all(r["status"] == 200 for r in checks),
        "concurrent_requests": parallel,
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "bounded_overload_observed": any(r["status"] == 503 for r in rows),
        "overload_has_retry_after": all(r["retry_after"] for r in rows if r["status"] == 503)
        if any(r["status"] == 503 for r in rows)
        else None,
        "no_server_errors": all(r["status"] in {200, 503} for r in rows),
        "results": rows,
        "limitation": "Eight local guest requests exercise overload handling; this is not "
        "a sustained load test or a factual quality assessment.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    parser.add_argument("--parallel", type=int, default=8, choices=range(2, 17))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(check(args.base_url, args.frontend_url, args.parallel))
    atomic_write(args.output, json.dumps(report, indent=2).encode())
    print(json.dumps(report, indent=2))
    return 0 if report["http_checks_passed"] and report["no_server_errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
