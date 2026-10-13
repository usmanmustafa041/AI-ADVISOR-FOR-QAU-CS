"""Readable paired raw responses and engineering failures, without self-awarded accuracy."""

import argparse
import json

from chatbot_v3.settings import settings


def read_rows(path):
    return {row["id"]: row for line in path.read_text().splitlines() if (row := json.loads(line))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--replacement", default="replacement-current")
    p.add_argument("--baseline", default="baseline")
    p.add_argument("--output", default="comparison.md")
    p.add_argument(
        "--overrides",
        nargs="*",
        default=[
            "replacement-final-regression",
            "replacement-final-retry",
            "response-language-check",
        ],
    )
    a = p.parse_args()
    out = settings().data_dir / "evaluation"
    baseline = read_rows(out / (a.baseline + ".jsonl"))
    replacements = read_rows(out / (a.replacement + ".jsonl"))
    for name in a.overrides:
        override = out / (name + ".jsonl")
        if override.exists():
            replacements.update(read_rows(override))
    parts = [
        "# Actual paired QAU conversations — independent review pending\n",
        "These are real API outputs, including errors. The old and new paths use preserved originals but different parsers and retrieval bundles; this is not a controlled same-index model experiment. New traces use interim qwen3:8b. No answer-quality pass rate is assigned here.\n",
        "Named override runs select the latest available result for that case. Per-case runtime details below distinguish source/parser revisions; all earlier raw trials remain retained.\n",
    ]
    for case_id, old in baseline.items():
        new = replacements.get(case_id, {})
        response = new.get("raw_response", {})
        parts.extend(
            [
                f"## {case_id}: {old['question']}\n",
                "History: ```json\n"
                + json.dumps(old.get("history", []), ensure_ascii=False)
                + "\n```\n",
                "### Old chatbot\n",
                old.get("raw_response", {}).get("answer", "No answer") + "\n",
                f"### Replacement (HTTP {new.get('status', 'not executed')})\n",
                response.get("answer") or json.dumps(response, ensure_ascii=False),
                "\n",
            ]
        )
        for source in response.get("cited_sources", []):
            parts.append(
                f"- [{source['number']}] [{source['document_title']}]({source['canonical_url']}) — page {source.get('page') or 'HTML'}, version `{source['source_version_id']}`, {source['review_status']}\n"
            )
        trace = new.get("trace") or {}
        parts.append(
            "\nReplacement runtime: "
            + json.dumps(
                {
                    "code_sha256": (trace.get("runtime") or {}).get("code_sha256"),
                    "parser_version": (
                        (trace.get("runtime") or {}).get("index_manifest") or {}
                    ).get("parser_version"),
                    "latency_ms": new.get("client_latency_ms"),
                }
            )
            + "\n"
        )
        parts.append(
            "\nObserved validation issues: "
            + json.dumps(trace.get("validation_errors", []), ensure_ascii=False)
            + "\n"
        )
        parts.append("Independent factual/helpfulness verdict: **pending**.\n")
    path = out / a.output
    path.write_text("\n".join(parts))
    print(
        json.dumps(
            {"paired_cases": len(baseline), "artifact": str(path), "human_quality_metrics": None}
        )
    )


if __name__ == "__main__":
    main()
