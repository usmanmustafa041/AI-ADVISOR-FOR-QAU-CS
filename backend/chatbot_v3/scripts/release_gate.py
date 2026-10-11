"""Evidence-based release check. Never switches routes or deletes existing components."""

import argparse
import json
from pathlib import Path


def evaluate(reviews, grades):
    approved = {
        c["id"]: c
        for c in reviews.get("cases", [])
        if c.get("review_status") == "approved"
        and c.get("reviewer")
        and c.get("reviewed_at")
        and c.get("approved_reference_answer")
        and c.get("critical_assertions")
    }
    # A repeated grade or omitted metric cannot inflate the denominator or pass rate.
    independent_by_case = {
        g["case_id"]: g
        for g in grades.get("cases", [])
        if g.get("case_id") in approved
        and g.get("reviewer")
        and g.get("reviewed_at")
        and g.get("review_kind") == "human"
        and all(
            type(g.get(k)) is bool
            for k in ["factually_correct", "citations_valid", "complete", "appropriate_behavior"]
        )
        and type(g.get("prefer_replacement")) in {int, float}
        and g["prefer_replacement"] in {0, 0.5, 1}
    }
    independent = list(independent_by_case.values())
    supported = [
        g for g in independent if approved[g["case_id"]].get("expected_behavior") == "answer"
    ]
    needs_abstain = [
        g
        for g in independent
        if approved[g["case_id"]].get("expected_behavior")
        in {"abstention", "clarification", "private_boundary"}
    ]

    def mean(rows, key):
        values = [r[key] for r in rows if isinstance(r.get(key), bool | int | float)]
        return sum(values) / len(values) if values else None

    metrics = {
        "factual_accuracy": mean(supported, "factually_correct"),
        "citation_validity": mean(independent, "citations_valid"),
        "completeness": mean(independent, "complete"),
        "appropriate_clarification_abstention": mean(needs_abstain, "appropriate_behavior"),
        "replacement_preference": mean(independent, "prefer_replacement"),
    }
    thresholds = {
        "factual_accuracy": 0.95,
        "citation_validity": 0.98,
        "completeness": 0.9,
        "appropriate_clarification_abstention": 0.9,
        "replacement_preference": 0.5,
    }
    failures = []
    if len(approved) < 200:
        failures.append("Fewer than 200 independently approved reference conversations")
    if len(independent) < 200:
        failures.append("Fewer than 200 independently human-graded paired answers")
    for key, target in thresholds.items():
        if (
            metrics[key] is None
            or metrics[key] < target
            or (key == "replacement_preference" and metrics[key] == target)
        ):
            failures.append(f"{key}: unmeasured or below {target}")
    return {
        "quality_gate_passed": not failures,
        "approved_references": len(approved),
        "human_graded_answers": len(independent),
        "metrics": metrics,
        "failures": failures,
        "failed_case_ids": [
            g["case_id"]
            for g in independent
            if g.get("factually_correct") is False
            or g.get("citations_valid") is False
            or g.get("complete") is False
            or g.get("appropriate_behavior") is False
        ],
        "production_cutover_authorized": False,
        "note": "A passing quality gate still requires explicit cutover approval, verified rollback, capacity testing and hardware/model selection.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reviews", type=Path, required=True)
    p.add_argument("--grades", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    reviews = json.loads(a.reviews.read_text())
    grades = json.loads(a.grades.read_text()) if a.grades else reviews.get("grades", {})
    report = evaluate(reviews, grades)
    if a.output:
        a.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["quality_gate_passed"] else 1)


if __name__ == "__main__":
    main()
