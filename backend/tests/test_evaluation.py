from pathlib import Path

from scripts.evaluate_nlp import evaluate


def test_labeled_multilingual_evaluation_set_meets_baseline() -> None:
    report = evaluate(Path(__file__).parents[1] / "evaluation" / "nlp_test_set.csv")
    assert report["samples"] == 27
    assert report["intent_accuracy"] >= 0.70
    assert report["language_accuracy"] == 1.0
    assert report["macro_f1"] >= 0.60

