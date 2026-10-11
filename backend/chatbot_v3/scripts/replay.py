"""Replay a real request and fetch its protected diagnostic, without scoring it."""

import argparse
import json
import time

import httpx

from chatbot_v3.settings import settings


def main():
    p = argparse.ArgumentParser()
    p.add_argument("question")
    p.add_argument("--old", action="store_true")
    p.add_argument("--conversation-id")
    a = p.parse_args()
    url = "http://127.0.0.1:8000/api/v1/chat" if a.old else "http://127.0.0.1:8010/api/v3/chat"
    body = {"message": a.question}
    if a.conversation_id:
        body["conversation_id"] = a.conversation_id
    with httpx.Client(timeout=240, trust_env=False) as c:
        t = time.perf_counter()
        r = c.post(url, json=body)
        print(
            json.dumps(
                {
                    "status": r.status_code,
                    "elapsed_ms": round((time.perf_counter() - t) * 1000),
                    "response": r.json(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if not a.old and r.is_success and settings().developer_token:
            trace = c.get(
                "http://127.0.0.1:8010/api/v3/development/traces/" + r.json()["trace_id"],
                headers={"X-Developer-Token": settings().developer_token},
            )
            if trace.is_success:
                print(json.dumps({"trace": trace.json()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
