"""Compare installed Ollama models on identical source-grounded bilingual prompts."""

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.ingestion.archive import atomic_write, utc_now
from app.rag.corpus import load_corpus
from app.rag.evidence import Hit
from app.response.grounded import FORMAT, SYSTEM, normalized, validate_claims


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = {c["id"]: c for c in json.loads(args.questions.read_text())}
    selected = [
        cases[i]
        for i in [
            "source-001-english",
            "source-001-urdu",
            "source-005-english",
            "source-005-roman_urdu",
            "source-007-english",
            "source-007-urdu",
        ]
    ]
    chunks = load_corpus(args.corpus)
    settings = get_settings()
    results = []
    with httpx.Client(base_url=settings.llm_base_url, timeout=60) as client:
        installed = {m["name"] for m in client.get("/api/tags").json()["models"]}
        for model in args.model:
            if model not in installed:
                raise ValueError(f"Model is not installed locally: {model}")
            for case in selected:
                label = case["relevant_sources"][0]
                chunk = next(
                    c
                    for c in chunks
                    if c.source_url == label["source_url"]
                    and normalized(label["quote"]) in normalized(c.content)
                )
                started = time.perf_counter()
                row = {"model": model, "id": case["id"], "language": case["language"]}
                try:
                    response = client.post(
                        "/api/chat",
                        json={
                            "model": model,
                            "stream": False,
                            "think": False,
                            "keep_alive": "15m",
                            "format": FORMAT,
                            "options": {"temperature": 0, "num_predict": 500, "num_ctx": 4096},
                            "messages": [
                                {"role": "system", "content": SYSTEM},
                                {
                                    "role": "user",
                                    "content": json.dumps(
                                        {
                                            "question": case["question"],
                                            "language": case["language"],
                                            "EVIDENCE": [
                                                {
                                                    "source": 1,
                                                    "title": chunk.title,
                                                    "program": chunk.program,
                                                    "content": chunk.content,
                                                }
                                            ],
                                        },
                                        ensure_ascii=False,
                                    ),
                                },
                            ],
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    claims, _, _ = validate_claims(
                        json.loads(data["message"]["content"]), [Hit(chunk, 1)], case["question"]
                    )
                    answer = "\n".join(claims)
                    row.update(
                        answer=answer,
                        provenance_valid=bool(claims),
                        reference_pattern_pass=bool(claims)
                        and all(re.search(p, answer, re.I) for p in case["required_patterns"]),
                        generation_tokens_per_second=data.get("eval_count", 0)
                        / max(data.get("eval_duration", 1) / 1e9, 1e-9),
                    )
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    row.update(error=str(exc), reference_pattern_pass=False, provenance_valid=False)
                row["wall_ms"] = round((time.perf_counter() - started) * 1000)
                results.append(row)
                print(model, case["id"], row["reference_pattern_pass"], flush=True)
    summary = {}
    for model in args.model:
        rows = [r for r in results if r["model"] == model]
        summary[model] = {
            "cases": len(rows),
            "reference_pattern_pass_rate": sum(r["reference_pattern_pass"] for r in rows)
            / len(rows),
            "provenance_pass_rate": sum(r["provenance_valid"] for r in rows) / len(rows),
            "latency_ms_p50": statistics.median(r["wall_ms"] for r in rows),
        }
    report = {
        "created_at": utc_now(),
        "summary": summary,
        "results": results,
        "limitation": "Six engineering prompts with supplied gold evidence, not a full RAG "
        "benchmark or independent human accuracy measurement.",
    }
    atomic_write(args.output, json.dumps(report, ensure_ascii=False, indent=2).encode())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
