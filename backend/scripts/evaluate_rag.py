"""Measure evidence retrieval separately from live LLM answer generation.

The checked-in questions are a small regression set, not a production quality
certification. --live records generated responses for human correctness review.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.rag.evidence import retrieve
from app.response.grounded import generate_answer


def validate_questions(questions):
    seen = set()
    for item in questions:
        if not item.get("id") or item["id"] in seen or not item.get("question", "").strip():
            raise ValueError("Regression cases require unique IDs and nonblank questions")
        seen.add(item["id"])
        if not item.get("unanswerable"):
            for plural, singular in (("source_any", "source_contains"),
                                     ("evidence_any", "evidence_contains")):
                labels = item.get(plural, [item.get(singular, "")])
                if not labels or not all(isinstance(v, str) and v.strip() for v in labels):
                    raise ValueError(f"Missing source/evidence labels: {item['id']}")


def main():
    backend = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=backend / "evaluation/rag_questions.json")
    parser.add_argument("--output", type=Path, default=backend / "evaluation/rag_report.json")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--lexical-only", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    settings.rag_include_database = False
    if args.lexical_only:
        settings.embedding_provider = "disabled"
    if args.live:
        settings.llm_provider, settings.llm_model, settings.llm_base_url = (
            "ollama",
            args.model,
            args.base_url,
        )
    questions = json.loads(args.questions.read_text())
    validate_questions(questions)
    if args.limit:
        questions = questions[: args.limit]
    results = []
    for item in questions:
        started = time.perf_counter()
        hits, notices = retrieve(item["question"])
        expected = [
            n
            for n, h in enumerate(hits, 1)
            if any(value.lower() in h.chunk.source_url.lower() for value in item.get(
                "source_any", [item.get("source_contains", "")]
            ))
            and any(value.lower() in h.chunk.content.lower() for value in item.get(
                "evidence_any", [item.get("evidence_contains", "")]
            ))
        ]
        passed = not hits if item.get("unanswerable") else bool(expected)
        row = {
            **item,
            "retrieval_pass": passed,
            "first_relevant_rank": min(expected, default=None),
            "retrieval_ms": round((time.perf_counter() - started) * 1000),
            "sources": [h.citation(n) for n, h in enumerate(hits, 1)],
            "notices": notices,
        }
        if args.live:
            answer = generate_answer(item["question"], hits, "english")
            row.update(
                answer=answer.answer,
                grounding_status=answer.grounding_status,
                citations=answer.citations,
                total_ms=round((time.perf_counter() - started) * 1000),
            )
        results.append(row)
        print(
            f"{'PASS' if passed else 'FAIL'} {item['id']} rank={row['first_relevant_rank']}"
            + (f" {row['grounding_status']} {row['total_ms']}ms" if args.live else ""),
            flush=True,
        )
    answerable = [r for r in results if not r.get("unanswerable")]
    summary = {
        "questions": len(results),
        "passed": sum(r["retrieval_pass"] for r in results),
        "evidence_recall_at_6": round(
            sum(r["retrieval_pass"] for r in answerable) / max(len(answerable), 1), 3
        ),
        "mrr_at_6": round(
            sum(1 / r["first_relevant_rank"] if r["first_relevant_rank"] else 0 for r in answerable)
            / max(len(answerable), 1),
            3,
        ),
        "live_generation": args.live,
        "limitation": (
            "Small local regression set; retrieval hits and citation checks do not "
            "establish answer correctness. Live answers require human review."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2)
    )
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
