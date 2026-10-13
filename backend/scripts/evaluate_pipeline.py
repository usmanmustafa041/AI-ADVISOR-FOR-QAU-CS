"""Evaluate approved source-labelled cases; pending cases are diagnostics only.

The existing 28-question development regression remains in evaluate_rag.py.
This runner never counts unreviewed or unlabelled examples as correct answers.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.ingestion.archive import atomic_write, utc_now
from app.ingestion.evaluation import (
    citation_integrity,
    retrieval_metrics,
    rouge_l_f1,
    validate_cases,
)
from app.rag.evidence import retrieve
from app.response.grounded import generate_answer


def evaluate(cases, *, k=6, live=False, include_unreviewed=False):
    validate_cases(cases)
    rows = []
    for case in cases:
        approved = case.get("review_status") == "approved"
        if not approved and not include_unreviewed:
            continue
        started = time.perf_counter()
        hits, notices = retrieve(case["question"], limit=k)
        row = {
            "id": case["id"],
            "category": case["category"],
            "language": case["language"],
            "review_status": case["review_status"],
            "expected_behavior": case["expected_behavior"],
            "retrieval_ms": round((time.perf_counter() - started) * 1000),
            "sources": [h.citation(i) for i, h in enumerate(hits, 1)],
            "notices": notices,
            "retrieval_metrics": None,
            "human_review": {
                "factual_accuracy": None,
                "groundedness": None,
                "appropriate_abstention": None,
                "clarity": None,
                "reviewer": None,
            },
        }
        if approved and case["expected_behavior"] == "answer":
            row["retrieval_metrics"] = retrieval_metrics(hits, case["relevant_sources"], k)
        if live:
            answer = generate_answer(case["question"], hits, case["language"])
            row.update(
                answer=answer.answer,
                grounding_status=answer.grounding_status,
                citations=answer.citations,
                total_ms=round((time.perf_counter() - started) * 1000),
                citation_checks=citation_integrity(answer.citations, hits),
            )
            if approved and case.get("reference_answer"):
                row["rouge_l_f1"] = rouge_l_f1(answer.answer, case["reference_answer"])
        rows.append(row)
    scored = [r["retrieval_metrics"] for r in rows if r["retrieval_metrics"] is not None]
    summary = {
        "created_at": utc_now(),
        "dataset_cases": len(cases),
        "executed_cases": len(rows),
        "approved_cases": sum(c.get("review_status") == "approved" for c in cases),
        "scored_answerable_cases": len(scored),
        "k": k,
        "live_generation": live,
        "retrieval": {
            name: sum(r[name] for r in scored) / len(scored) if scored else None
            for name in ("precision_at_k", "source_recall_at_k", "reciprocal_rank", "hit_at_k")
        },
        "factual_accuracy": None,
        "groundedness": None,
        "limitation": (
            "Pending examples are diagnostics. Answer accuracy, entailment and refusal "
            "quality require human review. ROUGE-L measures wording overlap only."
        ),
    }
    return {"summary": summary, "results": rows}


def main():
    backend = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions", type=Path, default=backend / "evaluation/production_questions.json"
    )
    parser.add_argument("--output", type=Path, default=backend / "evaluation/pipeline_report.json")
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--k", type=int, default=6, choices=range(1, 16))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--lexical-only", action="store_true")
    parser.add_argument("--include-unreviewed", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    settings.rag_include_database = False
    if args.corpus:
        settings.rag_corpus_path = str(args.corpus.resolve())
    if args.lexical_only:
        settings.embedding_provider = "disabled"
    cases = json.loads(args.questions.read_text(encoding="utf-8"))
    report = evaluate(cases, k=args.k, live=args.live, include_unreviewed=args.include_unreviewed)
    atomic_write(args.output, json.dumps(report, ensure_ascii=False, indent=2).encode())
    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["executed_cases"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
