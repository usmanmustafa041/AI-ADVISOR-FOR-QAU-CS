import csv
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path


DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "intent_dataset.csv"
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _features(text: str) -> list[str]:
    normalized = f"  {text.lower()}  "
    chars = [normalized[i : i + 4] for i in range(len(normalized) - 3)]
    words = TOKEN_PATTERN.findall(normalized)
    return [f"c:{gram}" for gram in chars] + [f"w:{word}" for word in words]


class NgramIntentClassifier:
    """Small offline baseline retained as a controlled availability fallback."""

    backend = "ngram_naive_bayes"
    model_name = "qau-intent-char-word-ngram-v1"

    def __init__(self, dataset_path: Path = DATASET_PATH) -> None:
        self.class_counts: Counter[str] = Counter()
        self.feature_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.feature_totals: Counter[str] = Counter()
        self.vocabulary: set[str] = set()
        with dataset_path.open(encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                text, intent = (row.get("text", "").strip(), row.get("intent", "").strip())
                if not text or not intent:
                    continue
                features = _features(text)
                self.class_counts[intent] += 1
                self.feature_counts[intent].update(features)
                self.feature_totals[intent] += len(features)
                self.vocabulary.update(features)
        if not self.class_counts:
            raise ValueError(f"Intent dataset is empty: {dataset_path}")

    def predict(self, text: str) -> tuple[str, float]:
        feature_list = _features(text)
        total_examples = sum(self.class_counts.values())
        vocab_size = max(1, len(self.vocabulary))
        scores: dict[str, float] = {}
        for intent, class_count in self.class_counts.items():
            score = math.log(class_count / total_examples)
            denominator = self.feature_totals[intent] + vocab_size
            for feature in feature_list:
                score += math.log((self.feature_counts[intent][feature] + 1) / denominator)
            scores[intent] = score
        best_intent = max(scores, key=scores.get)
        max_score = scores[best_intent]
        exp_scores = {intent: math.exp(score - max_score) for intent, score in scores.items()}
        confidence = exp_scores[best_intent] / sum(exp_scores.values())
        return best_intent, float(confidence)


@lru_cache
def get_baseline_classifier() -> NgramIntentClassifier:
    return NgramIntentClassifier()


# Backwards-compatible name for code importing the original baseline directly.
IntentClassifier = NgramIntentClassifier


def get_classifier():
    from app.nlp.transformer import get_intent_classifier

    return get_intent_classifier()
