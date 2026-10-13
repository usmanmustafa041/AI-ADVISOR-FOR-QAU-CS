"""Expose all development failures, full pipeline inputs and pending human judgments."""

import argparse
import json

from chatbot_v3.scripts.comparison_report import read_rows
from chatbot_v3.scripts.live_evaluation import percentile
from chatbot_v3.settings import settings

# Engineering diagnoses of observed development runs, not independent answer labels.
DIAGNOSES = {
    1: "Semester scope must select the cohort's semester rows. An elective slot is required credit, not permission to omit it.",
    2: "The catalogue contains a unique observed CSC-104 identity. Needless code clarification and wrong-language generation obscured its printed 3+1 credits.",
    3: "Broad faculty retrieval let related subjects and directory membership appear as NLP expertise. Restrict evidence to the named profile's explicit Research Interests field.",
    4: "The actual request is hostel fees despite the opening thanks. Reviewed applicable fee evidence is absent; inventing a fact or asking for unrelated scope is unhelpful.",
    5: "Blanket review gating suppressed the regular BSCS admissions publication. Its degree heading must be separated from lateral-entry and graduate requirements.",
    6: "Whole-scheme retrieval supplied all semesters, but generation announced a list without actually giving it. Quotation duplication also consumed output budget.",
    7: "General recursion tutoring needs no university retrieval or programme clarification; assess the example's correctness independently.",
    8: "The degree was not stated. Interpretation assumed BSCS, and no reviewed repeat policy was available. A new CGPA also requires course grades and credits.",
    9: "Interpretation misrouted a personal registration action as tutoring, enabling an unsupported yes/no answer. It requires programme-specific published rules.",
    10: "There are four requested facts across two cohorts. Full-scheme context and duplicate quotes delayed generation; one run omitted both degree totals.",
    11: "A current teacher requires a dated teaching assignment. Scheme membership and historical Courses Taught fields cannot establish it.",
    12: "Fall 2026 is an operational fee term, not an admission cohort. Morning/evening and one-off/recurring charges need separate applicable evidence.",
    13: "The admissions source gap and Arabic-script generation must be checked separately. A successful HTTP response in Urdu is not proof of a complete admission answer.",
    14: "Roman Urdu attendance queries require the BS policy source and its exceptions. Pending source review must not be replaced by an invented percentage.",
    15: "A single unscoped admission task cannot compare MPhil with PhD. Retrieve each printed degree section and preserve their different test/interview requirements.",
    16: "A next deadline is a date question. Eligibility text and an expired archived deadline cannot establish the next open admission deadline.",
    17: "An admission batch does not determine an operational FYP submission date. The requested dated calendar remains unavailable without approved evidence.",
    18: "Private marks and unpublished personal contacts must use the private-record boundary immediately, without an irrelevant degree clarification.",
    19: "The conceptual meaning of 3+1 and the cohort's CSC-104 fact require mixed handling. One interpretation wrongly turned the conceptual part into a high-stakes policy request.",
    20: "The model sometimes asserted that study order implies a formal prerequisite. This is a generator reasoning failure even when no false university citation is attached.",
    21: "Research interests and published contacts need distinct profile fields. Courses Taught must not expand the software-engineering researcher list.",
    22: "Conflicts need actual applicable policy texts, with both sources and their exceptions. Pending extraction review is not proof that official policies conflict.",
    23: "A prompt-disclosure instruction is neither an academic lookup nor missing student scope. Preserve the boundary without exposing internal instructions.",
    24: "Explicit Roman Urdu was sometimes emitted in Urdu script, with repeated sentences until the token budget. Language selection, fluency and stopping behavior are separate failures.",
    25: "Resolve CSC-104 and Fall 2025 from history. CSC-110's presence in the same scheme does not establish a prerequisite; no verified relation is currently indexed.",
    26: "Keep the previous admission cohort for a semester follow-up. Do not add unsupported elective specialization or registration advice.",
    27: "The explicit Fall 2024 correction must replace Fall 2025. The generator must print the actual requested rows, rather than just introducing an absent list.",
    28: "A hostel-fee topic switch must discard curriculum cohort and semester filters, and state the actual evidence gap.",
    29: "The Python follow-up refers to binary search. Use server conversation context and general tutoring, with a working sorted-list example.",
    30: "In this fixture the degree-name reply answers an admission clarification. Complete that original request, preserve non-computing entry conditions and test/interview requirements, and do not misread evening scheduling as a part-time status. The separate student conversation 6 exercises a degree reply to a CGPA clarification.",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replacement", default="recovery-final")
    parser.add_argument("--baseline", default="recovery-old-current")
    parser.add_argument("--before", default="recovery-before")
    parser.add_argument("--overrides", nargs="*", default=[])
    args = parser.parse_args()
    folder = settings().data_dir / "evaluation"
    runs = {
        name: read_rows(folder / (prefix + ".jsonl"))
        for name, prefix in [
            ("old", args.baseline),
            ("before", args.before),
            ("replacement", args.replacement),
        ]
    }
    for name in args.overrides:
        runs["replacement"].update(read_rows(folder / (name + ".jsonl")))
    reports = []
    for case_id, row in runs["before"].items():
        new = runs["replacement"].get(case_id, {})
        trace = new.get("trace") or {}
        before_trace = row.get("trace") or {}
        reports.append(
            {
                "id": case_id,
                "question": row["question"],
                "history": row.get("history", []),
                "development_intent": row.get("desired_outcome"),
                "engineering_diagnosis": DIAGNOSES[int(case_id.rsplit("-", 1)[1])],
                "independent_review_status": "pending",
                "reviewed_correctness": None,
                "reviewed_completeness": None,
                "reviewed_language_quality": None,
                "reviewed_source_support": None,
                "old_status": runs["old"].get(case_id, {}).get("status"),
                "old_raw_response": runs["old"].get(case_id, {}).get("raw_response"),
                "before_raw_response": row.get("raw_response"),
                "before_interpretation": before_trace.get("interpretation"),
                "replacement_status": new.get("status"),
                "replacement_raw_response": new.get("raw_response"),
                "replacement_pipeline": {
                    key: trace.get(key)
                    for key in [
                        "runtime",
                        "entity_resolution",
                        "interpretation",
                        "tool_preconditions",
                        "retrieval",
                        "retrieved_evidence",
                        "generation_input",
                        "generated_blocks",
                        "generation_skipped",
                        "tool_gap_blocks",
                        "language_repairs",
                        "validation_errors",
                        "generation_incomplete",
                        "error",
                        "stages",
                        "model_calls",
                    ]
                },
            }
        )
    (folder / "recovery-failure-audit.json").write_text(
        json.dumps(
            {
                "cases": reports,
                "note": "Engineering diagnoses are not human-reviewed answer grades. Generator inputs are diagnostic copies with privacy redaction. Full source snapshots and immutable originals remain available.",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    parts = [
        "# Recovery audit: all thirty development failures",
        "",
        "Independent factual accuracy, semantic citation validity, completeness, language quality and usefulness remain pending. These diagnoses explain observed engineering failures; they are not approval labels.",
        "",
        "Every case's interpretation, tool scope, selected evidence, redacted generator input, raw output, validation failures and timings are in `recovery-failure-audit.json`. Full paired answers are in `recovery-comparison.md`.",
    ]
    for case in reports:
        pipeline = case["replacement_pipeline"]
        parts += [
            "",
            f"## {case['id']}: {case['question']}",
            "",
            case["engineering_diagnosis"],
            "",
            "Requested behavior: " + str(case["development_intent"]),
            "",
            "Latest interpretation:",
            "```json",
            json.dumps(pipeline["interpretation"], ensure_ascii=False),
            "```",
            "",
            "Selected source versions: "
            + ", ".join(
                dict.fromkeys(c["source_version_id"] for c in pipeline["retrieved_evidence"] or [])
            ),
            "",
            "Validation issues: " + json.dumps(pipeline["validation_errors"], ensure_ascii=False),
            "",
            "Latest answer:",
            "",
            (case["replacement_raw_response"] or {}).get("answer", "No completed answer."),
            "",
            "Human verdict: **pending**.",
        ]
    (folder / "recovery-failure-audit.md").write_text("\n".join(parts))
    stage_names = [
        "queue_ms",
        "availability_ms",
        "understanding_ms",
        "retrieval_ms",
        "reranking_ms",
        "generation_ms",
    ]
    stage_summary = {}
    for name in stage_names:
        values = [
            r["replacement_pipeline"]["stages"][name]
            for r in reports
            if name in (r["replacement_pipeline"]["stages"] or {})
        ]
        stage_summary[name] = {
            "n": len(values),
            "p50": percentile(values, 0.5),
            "p95": percentile(values, 0.95),
        }
    stage_file = (
        "recovery-stage-latencies-latest.json"
        if args.overrides
        else "recovery-stage-latencies.json"
    )
    (folder / stage_file).write_text(json.dumps(stage_summary, indent=2))
    print(
        json.dumps(
            {"cases": len(reports), "reviewed_accuracy": None, "stage_latencies": stage_summary}
        )
    )


if __name__ == "__main__":
    main()
