"""Runtime selection for the trained multilingual DistilBERT intent model."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings
from app.nlp.classifier import get_baseline_classifier


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Classifier(Protocol):
    backend: str
    model_name: str

    def predict(self, text: str) -> tuple[str, float]: ...


def resolve_model_path(configured_path: str) -> Path:
    path = Path(configured_path)
    return path if path.is_absolute() else BACKEND_ROOT / path


class TransformerIntentClassifier:
    backend = "multilingual_distilbert"

    def __init__(self, model_path: Path, max_length: int = 128) -> None:
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Transformer runtime is not installed; install backend requirements."
            ) from exc

        if not (model_path / "config.json").exists():
            raise RuntimeError(
                f"Trained intent model artifact is missing at {model_path}. "
                "Run scripts/train_transformer.py first."
            )
        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            model_path, local_files_only=True
        )
        self._model.eval()
        self._max_length = max_length
        metadata_path = model_path / "training_metadata.json"
        self.metadata = (
            json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata_path.exists()
            else {}
        )
        self.model_name = self.metadata.get(
            "base_model", str(getattr(self._model.config, "_name_or_path", model_path.name))
        )

    def predict(self, text: str) -> tuple[str, float]:
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=self._max_length,
        )
        with self._torch.inference_mode():
            logits = self._model(**inputs).logits[0]
            probabilities = self._torch.softmax(logits, dim=-1)
        index = int(self._torch.argmax(probabilities).item())
        label = self._model.config.id2label.get(index)
        if label is None:
            label = self._model.config.id2label.get(str(index), f"LABEL_{index}")
        return str(label), float(probabilities[index].item())


@lru_cache
def get_intent_classifier() -> Classifier:
    settings = get_settings()
    requested = settings.nlp_classifier_backend.strip().lower()
    if requested not in {"auto", "transformer", "baseline"}:
        raise RuntimeError(
            "NLP_CLASSIFIER_BACKEND must be one of: auto, transformer, baseline"
        )
    if requested == "baseline":
        return get_baseline_classifier()
    try:
        return TransformerIntentClassifier(
            resolve_model_path(settings.nlp_model_path), settings.nlp_max_length
        )
    except (RuntimeError, OSError, ValueError):
        if requested == "transformer":
            raise
        return get_baseline_classifier()


def model_status() -> dict:
    settings = get_settings()
    model_path = resolve_model_path(settings.nlp_model_path)
    artifact_ready = (model_path / "config.json").exists()
    try:
        classifier = get_intent_classifier()
        active_backend = classifier.backend
        active_model = classifier.model_name
        error = None
    except (RuntimeError, OSError, ValueError) as exc:
        active_backend = "unavailable"
        active_model = settings.nlp_model_name
        error = str(exc)
    return {
        "requested_backend": settings.nlp_classifier_backend,
        "active_backend": active_backend,
        "model_name": active_model,
        "configured_base_model": settings.nlp_model_name,
        "artifact_path": str(model_path),
        "artifact_ready": artifact_ready,
        "fallback_active": active_backend == "ngram_naive_bayes",
        "error": error,
    }
