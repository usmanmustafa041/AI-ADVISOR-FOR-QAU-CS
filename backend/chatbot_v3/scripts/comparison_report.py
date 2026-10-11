"""Readable paired raw responses and engineering failures, without self-awarded accuracy."""

import argparse
import json

from chatbot_v3.settings import settings


def read_rows(path):
    return {row["id"]: row for line in path.read_text().splitlines() if (row := json.loads(line))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--replacement", default="replacement-current")
    p.add_argument("--override", default="replacement-final-regression")
    a = p.parse_args()
    out = settings().data_dir / "evaluation"
    baseline = read_rows(out / "baseline.jsonl")
    replacements = read_rows(out / (a.replacement + ".jsonl"))
    override = out / (a.override + ".jsonl")
    if override.exists():
        replacements.update(read_rows(override))
    parts = [
        "# Actual paired QAU conversations — independent review pending\n",
        "These are real API outputs, including errors. The old and new paths use preserved originals but different parsers and retrieval bundles; this is not a controlled same-index model experiment. New traces use interim qwen3:8b. No answer-quality pass rate is assigned here.\n",
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
            "\nObserved validation issues: "
            + json.dumps(trace.get("validation_errors", []), ensure_ascii=False)
            + "\n"
        )
        parts.append("Independent factual/helpfulness verdict: **pending**.\n")
    path = out / "comparison.md"
    path.write_text("\n".join(parts))
    print(
        json.dumps(
            {"paired_cases": len(baseline), "artifact": str(path), "human_quality_metrics": None}
        )
    )


if __name__ == "__main__":
    main()
