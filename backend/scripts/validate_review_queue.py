"""Validate the independent-review gate and export only adjudicated rows."""

import argparse
import csv
from pathlib import Path

REQUIRED = {
    "query_id", "query", "reviewer_1_intent", "reviewer_2_intent",
    "adjudicated_intent", "entity_review", "review_status", "notes",
}


def validate(source: Path, approved_output: Path | None = None) -> tuple[int, list[str]]:
    with source.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
        fields = set(rows[0]) if rows else set()
    errors = []
    missing = REQUIRED - fields
    if missing:
        errors.append(f"missing columns: {', '.join(sorted(missing))}")
    if len(rows) < 200:
        errors.append(f"expected at least 200 rows, found {len(rows)}")
    approved = []
    for number, row in enumerate(rows, start=2):
        if row.get("review_status") == "approved":
            if not row.get("reviewer_1_intent") or not row.get("reviewer_2_intent"):
                errors.append(f"line {number}: both independent reviewer labels are required")
            if not row.get("adjudicated_intent") or not row.get("entity_review"):
                errors.append(f"line {number}: adjudication and entity review are required")
            approved.append(row)
    if len(approved) < 200:
        errors.append(f"expected 200 adjudicated rows, found {len(approved)}")
    if approved_output and not errors:
        approved_output.parent.mkdir(parents=True, exist_ok=True)
        with approved_output.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(fields))
            writer.writeheader()
            writer.writerows(approved)
    return len(approved), errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, nargs="?", default=Path("evaluation/review_queue_200.csv"))
    parser.add_argument("--approved-output", type=Path)
    args = parser.parse_args()
    approved, errors = validate(args.source, args.approved_output)
    if errors:
        print("REVIEW GATE: BLOCKED")
        print("\n".join(f"- {error}" for error in errors))
        raise SystemExit(1)
    print(f"REVIEW GATE: PASSED ({approved} approved rows)")


if __name__ == "__main__":
    main()
