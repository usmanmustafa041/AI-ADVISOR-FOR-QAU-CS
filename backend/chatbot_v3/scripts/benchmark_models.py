"""Measure requested local generators; unavailable candidates remain explicitly unmeasured."""

import argparse
import asyncio
import json
import time

import httpx

from chatbot_v3.model import Ollama
from chatbot_v3.settings import Settings, settings

QUESTIONS = [
    ("tutor", "Explain recursion with a short Python factorial example."),
    (
        "roman_urdu",
        "Binary search ko Roman Urdu (Latin letters) mein ek chhoti example se samjhao.",
    ),
    ("urdu", "اسٹیک اور کیو میں فرق ایک سادہ مثال سے سمجھائیں۔"),
    ("followup", "Can you show the Python code for it?"),
    (
        "scope",
        "A student says: 5th sem ke subjects btado fall 2024 batch. Explain what information they are asking for; do not invent QAU courses.",
    ),
]


async def main_async():
    p = argparse.ArgumentParser()
    p.add_argument("--models", nargs="+", default=["qwen3:8b", "qwen3.5:9b", "qwen3.5:27b"])
    p.add_argument("--output", default="generation-benchmark.json")
    a = p.parse_args()
    report = []
    for name in a.models:
        model = Ollama(Settings(model=name))
        if not await model.available():
            report.append(
                {"model": name, "status": "not_installed", "quality": None, "latency": None}
            )
            continue
        for category, question in QUESTIONS:
            history = (
                [
                    {"role": "user", "content": "What is binary search?"},
                    {
                        "role": "assistant",
                        "content": "Binary search halves a sorted search interval.",
                    },
                ]
                if category == "followup"
                else []
            )
            started = time.perf_counter()
            first = None
            answer = ""
            try:
                async for token in model.stream(
                    [
                        {
                            "role": "system",
                            "content": "Be a clear and helpful computing tutor. Match the requested language. Do not invent university facts.",
                        },
                        *history,
                        {"role": "user", "content": question},
                    ]
                ):
                    if first is None:
                        first = round((time.perf_counter() - started) * 1000)
                    answer += token
                async with httpx.AsyncClient(trust_env=False) as c:
                    memory = (await c.get(settings().model_url + "/api/ps")).json()
                report.append(
                    {
                        "model": name,
                        "category": category,
                        "question": question,
                        "history": history,
                        "answer": answer,
                        "first_token_ms": first,
                        "latency_ms": round((time.perf_counter() - started) * 1000),
                        "loaded_model_memory": memory,
                        "independent_review_status": "pending",
                    }
                )
            except Exception as e:
                report.append(
                    {
                        "model": name,
                        "category": category,
                        "status": "error",
                        "error_type": type(e).__name__,
                    }
                )
    path = settings().data_dir / "evaluation" / a.output
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "trials": len(report),
                "artifact": str(path),
                "quality_selection": "Not certified until paired end-to-end human review and hardware measurements are complete.",
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main_async())
