"""Embedding model and cross-encoder reranker wrappers (lazy, optional)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

log = logging.getLogger("advisor.models")


def _prepare_env(local_only: bool, model_name: str = "") -> None:
    cache = Path(__file__).resolve().parents[2] / ".model-cache"
    if cache.exists():
        os.environ.setdefault("HF_HOME", str(cache))
    hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    cached = bool(model_name) and (hub / ("models--" + model_name.replace("/", "--"))).exists()
    # A cached model never needs the network; skipping the hub check saves ~30 s per start-up.
    if local_only or cached:
        os.environ["HF_HUB_OFFLINE"] = "1"


class Encoder:
    def __init__(self, model_name: str, device: str = "cpu", local_only: bool = False):
        _prepare_env(local_only, model_name)
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self.model = SentenceTransformer(model_name, device=device)
        self.model.max_seq_length = min(self.model.max_seq_length or 512, 512)
        self.is_e5 = "e5" in model_name.lower()
        self.is_qwen = "qwen3" in model_name.lower()
        self.dim = self.model.get_sentence_embedding_dimension()

    def _q(self, text: str) -> str:
        if self.is_e5:
            return "query: " + text
        if self.is_qwen:
            return (
                "Instruct: Given a student's question about a university computer science "
                f"department, retrieve relevant passages\nQuery: {text}"
            )
        return text

    def _p(self, text: str) -> str:
        return "passage: " + text if self.is_e5 else text

    def encode_passages(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        return self.model.encode(
            [self._p(t[:2500]) for t in texts], batch_size=batch_size,
            normalize_embeddings=True, show_progress_bar=False,
        ).astype(np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        return self.model.encode(
            [self._q(text)], normalize_embeddings=True, show_progress_bar=False
        )[0].astype(np.float32)


class Reranker:
    def __init__(self, model_name: str, device: str = "cpu", local_only: bool = False):
        _prepare_env(local_only, model_name)
        from sentence_transformers import CrossEncoder

        self.name = model_name
        self.model = CrossEncoder(model_name, device=device, max_length=512)

    def score(self, query: str, passages: list[str]) -> np.ndarray:
        if not passages:
            return np.zeros(0, dtype=np.float32)
        pairs = [(query, p[:1800]) for p in passages]
        return np.asarray(self.model.predict(pairs, batch_size=16, show_progress_bar=False), dtype=np.float32)
