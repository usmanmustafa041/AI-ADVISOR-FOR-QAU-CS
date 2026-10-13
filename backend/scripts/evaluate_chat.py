"""Run chat acceptance checks against a local API or inspect a saved response set.

These checks catch regressions in conversation handling, source selection and
obvious factual scope errors. Passing them is not a general accuracy certificate.
"""

import argparse
import json
import time
from pathlib import Path

import httpx

CASES = {
    "hi'": {"status": ["conversational"], "contains": ["Hi!"], "max_ms": 1000},
    "Hi, how are you?": {"status": ["conversational"], "max_ms": 1000},
    "Thanks!": {"status": ["conversational"], "max_ms": 1000},
    "السلام علیکم": {"status": ["conversational"], "max_ms": 1000},
    "Hi, what are the research groups in the department?": {
        "status": ["cited_lookup", "cited_generation"],
        "contains": [
            "Human Information Interaction",
            "Knowledge Engineering",
            "Networking and Communication",
        ],
    },
    "What is the BSCS morning semester fee?": {
        "status": ["cited_lookup", "cited_generation"],
        "contains": ["60,860", "Fall 2025"],
        "excludes": ["35,460"],
    },
    "What are the BSCS admission eligibility requirements?": {
        "status": ["cited_generation"],
        "contains": ["USAT", "Mathematics"],
    },
    "Who is Rabeeh Ayaz Abbasi and what does he research?": {
        "status": ["cited_generation"],
        "contains": ["social media", "network science"],
    },
    "What are the prerequisites for CSC-483?": {
        "status": ["cited_generation"],
        "contains": ["CSC-322", "not been authenticated"],
    },
    "How many credit hours can I take this semester?": {
        "status": ["insufficient_evidence"],
        "contains": ["Which programme"],
    },
    "What are the FYP submission rules?": {
        "status": ["cited_generation", "source_excerpts", "insufficient_evidence"],
        "excludes": ["five copies", "3rd semester", "MPhil"],
    },
    "Who is the king of Mars?": {"status": ["insufficient_evidence"]},
}


def check(row, expected):
    problems = []
    if row.get("http_status") != 200:
        problems.append("HTTP request failed")
    if row.get("grounding_status") not in expected["status"]:
        problems.append("Unexpected grounding status")
    answer = row.get("answer", "").casefold()
    for text in expected.get("contains", []):
        if text.casefold() not in answer:
            problems.append("Missing expected content: " + text)
    for text in expected.get("excludes", []):
        if text.casefold() in answer:
            problems.append("Incorrect scope/content: " + text)
    if row.get("response_time_ms", 0) > expected.get("max_ms", 60000):
        problems.append("Exceeded acceptance latency")
    if row.get("grounding_status", "").startswith("cited_") and not row.get("citations"):
        problems.append("Cited answer has no sources")
    if row.get("grounding_status") == "conversational" and row.get("citations"):
        problems.append("Conversation incorrectly invoked evidence")
    if row.get("verified"):
        problems.append("Answer incorrectly labelled automatically verified")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--check-report", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("evaluation/chat_acceptance_report.json")
    )
    args = parser.parse_args()
    if args.check_report:
        saved = json.loads(args.check_report.read_text())
        rows = saved.get("results", []) if isinstance(saved, dict) else saved
    else:
        rows = []
        with httpx.Client(base_url=args.base_url, timeout=50) as client:
            for question in CASES:
                started = time.perf_counter()
                response = client.post("/api/v1/chat", json={"message": question})
                rows.append(
                    {
                        "question": question,
                        "http_status": response.status_code,
                        "wall_seconds": round(time.perf_counter() - started, 3),
                        **response.json(),
                    }
                )
    results = []
    by_question = {row["question"]: row for row in rows}
    for question, expected in CASES.items():
        row = by_question.get(question, {"question": question})
        problems = check(row, expected)
        results.append({**row, "passed": not problems, "problems": problems})
        print(f"{'FAIL' if problems else 'PASS'} {question}: {', '.join(problems)}", flush=True)
    summary = {
        "questions": len(CASES),
        "passed": sum(r["passed"] for r in results),
        "limitation": (
            "Small development acceptance set. Human review and unseen questions remain required."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2)
    )
    print(json.dumps(summary))
    raise SystemExit(0 if summary["passed"] == summary["questions"] else 1)


if __name__ == "__main__":
    main()
