"""Create a human-review queue from the seed intent examples.

Generated rows are candidates only. They must be independently reviewed and
approved before being used as a thesis test set.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--output", type=Path, default=Path("evaluation/review_queue_200.csv"))
    args = parser.parse_args()
    if args.count < 1:
        raise SystemExit("count must be positive")
    source = Path("data/intent_dataset.csv")
    with source.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    candidates = []
    for index in range(args.count):
        row = rows[index % len(rows)]
        candidates.append(
            {
                "query_id": f"Q-{index + 1:04d}",
                "query": row["text"],
                "seed_intent": row["intent"],
                "language_guess": "urdu" if any("\u0600" <= char <= "\u06ff" for char in row["text"]) else "english_or_roman_urdu",
                "reviewer_1_intent": "",
                "reviewer_2_intent": "",
                "adjudicated_intent": "",
                "entity_review": "",
                "review_status": "needs_review",
                "notes": "Generated candidate; independently verify wording, intent, language, and entities.",
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=candidates[0].keys())
        writer.writeheader()
        writer.writerows(candidates)
    print(f"wrote {len(candidates)} review candidates to {args.output}")


if __name__ == "__main__":
    main()

