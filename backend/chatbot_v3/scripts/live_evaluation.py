"""Paired actual API trials; record outputs and mechanical metrics, never pattern accuracy."""

import argparse
import json
import math
import time
from pathlib import Path

import httpx

from chatbot_v3.settings import settings


def percentile(values, p):
    return (
        sorted(values)[max(0, min(len(values) - 1, math.ceil(len(values) * p) - 1))]
        if values
        else None
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--output", default="replacement")
    p.add_argument("--cases", type=Path)
    p.add_argument("--old", action="store_true")
    p.add_argument("--approved-only", action="store_true")
    a = p.parse_args()
    out = settings().data_dir / "evaluation"
    payload = json.loads((a.cases or out / "failure-fixtures.json").read_text())
    cases = payload["cases"] if isinstance(payload, dict) else payload
    if a.approved_only:
        cases = [c for c in cases if c.get("review_status") == "approved"]
    cases = cases[: a.limit]
    if not cases:
        raise SystemExit("No eligible cases to execute; pending labels are not approved cases")
    endpoint = "http://127.0.0.1:8000/api/v1/chat" if a.old else "http://127.0.0.1:8010/api/v3/chat"
    rows = []
    with (
        httpx.Client(timeout=240, trust_env=False) as c,
        (out / (a.output + ".jsonl")).open("w") as f,
    ):
        for case in cases:
            started = time.perf_counter()
            try:
                r = c.post(
                    endpoint,
                    json={"message": case["question"], "history": case.get("history", [])},
                )
                response = r.json()
                trace = None
                if not a.old and response.get("trace_id") and settings().developer_token:
                    tr = c.get(
                        "http://127.0.0.1:8010/api/v3/development/traces/" + response["trace_id"],
                        headers={"X-Developer-Token": settings().developer_token},
                    )
                    if tr.is_success:
                        trace = tr.json()
                row = {
                    **case,
                    "status": r.status_code,
                    "raw_response": response,
                    "trace": trace,
                    "client_latency_ms": round((time.perf_counter() - started) * 1000),
                    "independent_review_status": "pending",
                }
            except Exception as e:
                row = {
                    **case,
                    "status": "transport_error",
                    "error_type": type(e).__name__,
                    "client_latency_ms": round((time.perf_counter() - started) * 1000),
                    "independent_review_status": "pending",
                }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            rows.append(row)
            print(case["id"], row["status"], row["client_latency_ms"], flush=True)
    successful = [r for r in rows if r["status"] == 200]
    metrics = {
        "trials": len(rows),
        "http_successes": len(successful),
        "http_error_rate": 1 - len(successful) / len(rows),
        "latency_p50_ms": percentile([r["client_latency_ms"] for r in rows], 0.5),
        "latency_p95_ms": percentile([r["client_latency_ms"] for r in rows], 0.95),
        "first_token_p50_ms": percentile(
            [
                r["raw_response"]["first_token_ms"]
                for r in successful
                if r["raw_response"].get("first_token_ms") is not None
            ],
            0.5,
        ),
        "reviewed_factual_accuracy": None,
        "helpfulness": None,
        "limitation": "Real outputs on the effective local model; human correctness and preference review are pending. HTTP success is not answer success.",
    }
    metrics["effective_model"] = settings().model
    metrics["encoder"] = settings().embedding_model
    (out / (a.output + "-metrics.json")).write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics), flush=True)
    if len(successful) != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
