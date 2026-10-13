"""Exercise the running HTTP chatbot with source-labelled questions and real inference.

Reference-pattern checks, provenance validity and human factual review are separate.
"""

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import atomic_write, utc_now
from app.ingestion.evaluation import citation_integrity
from app.rag.corpus import load_corpus
from app.rag.evidence import EvidenceIndex, Hit


def evaluate(cases, base_url, corpus, checkpoint=None):
    index = EvidenceIndex(load_corpus(corpus))
    by_id = {c.chunk_id: c for c in index.chunks}
    results = []
    with httpx.Client(base_url=base_url, timeout=80) as client:
        for number, case in enumerate(cases, 1):
            started = time.perf_counter()
            payload = {"message": case["question"], "history": case.get("history", [])}
            try:
                response = client.post("/api/v1/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                answer = data["answer"]
                citations = data.get("citations", [])
                cited = [
                    Hit(by_id[c["chunk_id"]], 1) for c in citations if c.get("chunk_id") in by_id
                ]
                checks = citation_integrity(citations, cited)
                patterns = case.get("required_patterns", [])
                exact = all(re.search(p, answer, re.I) for p in patterns) if patterns else None
                if case.get("expected_behavior") == "private":
                    exact = data["model_backend"] == "privacy" and not citations
                if case.get("expected_behavior") == "abstain":
                    exact = data["grounding_status"] in {"insufficient_evidence", "source_excerpts"}
                requires_citation = case.get("expected_behavior") == "answer" and bool(
                    case.get("relevant_sources")
                )
                results.append(
                    {
                        "id": case["id"],
                        "question": case["question"],
                        "language": case.get("language"),
                        "category": case.get("category"),
                        "split": case.get("split"),
                        "http_status": response.status_code,
                        "wall_ms": round((time.perf_counter() - started) * 1000),
                        "reference_pattern_pass": exact,
                        "citation_checks": checks,
                        "requires_official_citation": requires_citation,
                        "official_citation_present": bool(citations)
                        and checks["valid_citations"] == len(citations)
                        if requires_citation
                        else None,
                        "human_factual_review": None,
                        **data,
                    }
                )
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                results.append(
                    {
                        "id": case["id"],
                        "question": case["question"],
                        "error": str(exc),
                        "requires_official_citation": case.get("expected_behavior") == "answer"
                        and bool(case.get("relevant_sources")),
                        "official_citation_present": False,
                        "wall_ms": round((time.perf_counter() - started) * 1000),
                        "reference_pattern_pass": False,
                    }
                )
            if checkpoint:
                with checkpoint.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(results[-1], ensure_ascii=False) + "\n")
            print(
                f"{number}/{len(cases)} {case['id']} {results[-1].get('reference_pattern_pass')}",
                flush=True,
            )
    scored = [r for r in results if r.get("reference_pattern_pass") is not None]
    citation_count = sum(r.get("citation_checks", {}).get("citations", 0) for r in results)
    valid = sum(r.get("citation_checks", {}).get("valid_citations", 0) for r in results)
    latencies = sorted(r["wall_ms"] for r in results)
    official_cases = [r for r in results if r.get("requires_official_citation")]
    groups = {}
    for language in {c.get("language", "english") for c in cases}:
        rows = [r for r in scored if r.get("language") == language]
        groups[language] = {
            "cases": len(rows),
            "reference_pattern_pass_rate": sum(bool(r["reference_pattern_pass"]) for r in rows)
            / len(rows)
            if rows
            else None,
        }
    return {
        "summary": {
            "created_at": utc_now(),
            "endpoint": base_url,
            "cases": len(cases),
            "http_errors": sum("error" in r for r in results),
            "reference_pattern_pass_rate": sum(bool(r["reference_pattern_pass"]) for r in scored)
            / len(scored)
            if scored
            else None,
            "citation_provenance_validity": valid / citation_count if citation_count else None,
            "citations": citation_count,
            "official_answer_cases": len(official_cases),
            "official_answers_with_valid_citations": sum(
                bool(r["official_citation_present"]) for r in official_cases
            ),
            "required_citation_coverage": sum(
                bool(r["official_citation_present"]) for r in official_cases
            )
            / len(official_cases)
            if official_cases
            else None,
            "latency_ms_p50": statistics.median(latencies),
            "latency_ms_p95": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
            "by_language": groups,
            "human_factual_accuracy": None,
            "evidence_entailment": None,
            "independent_human_approved_cases": sum(
                c.get("review_status") == "approved" for c in cases
            ),
            "limitation": "AI source-checked reference-pattern tests do not establish full factual "
            "accuracy or entailment. Independent human review remains required.",
        },
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cases = json.loads(args.questions.read_text())
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        parser.error("At least one case is required")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = args.output.with_suffix(".jsonl")
    if checkpoint.exists():
        checkpoint = checkpoint.with_name(checkpoint.stem + "-" + str(time.time_ns()) + ".jsonl")
    report = evaluate(cases, args.base_url, args.corpus, checkpoint)
    atomic_write(args.output, json.dumps(report, ensure_ascii=False, indent=2).encode())
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
