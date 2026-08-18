"""Evaluate intent classification and language detection on a labeled CSV."""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.nlp.language import detect_language
from app.nlp.service import analyze_query


def evaluate(path: Path) -> dict:
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    labels = [row["intent"] for row in rows]
    predictions = [analyze_query(row["text"]) for row in rows]
    predicted_labels = [item["intent"] for item in predictions]
    language_correct = sum(detect_language(row["text"]) == row["language"] for row in rows)
    accuracy = sum(a == b for a, b in zip(labels, predicted_labels, strict=True)) / len(rows)
    classes = sorted(set(labels) | set(predicted_labels))
    per_intent = {}
    for label in classes:
        tp = sum(a == label and b == label for a, b in zip(labels, predicted_labels, strict=True))
        fp = sum(a != label and b == label for a, b in zip(labels, predicted_labels, strict=True))
        fn = sum(a == label and b != label for a, b in zip(labels, predicted_labels, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_intent[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    macro_f1 = sum(item["f1"] for item in per_intent.values()) / len(per_intent)
    confusion = Counter((actual, predicted) for actual, predicted in zip(labels, predicted_labels, strict=True))
    return {
        "samples": len(rows),
        "intent_accuracy": accuracy,
        "language_accuracy": language_correct / len(rows),
        "macro_f1": macro_f1,
        "per_intent": per_intent,
        "confusion_pairs": {f"{actual}->{predicted}": count for (actual, predicted), count in confusion.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("evaluation/nlp_test_set.csv"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = evaluate(args.input)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
