"""Holds the live retriever and hot-swaps it when a new index bundle is published."""

from __future__ import annotations

import asyncio
import logging
import threading

from advisor.config import Settings
from advisor.retrieval.bundle import Bundle, load_bundle
from advisor.retrieval.models import Encoder, Reranker
from advisor.retrieval.retriever import Retriever

log = logging.getLogger("advisor.knowledge")


class KnowledgeBase:
    def __init__(self, settings: Settings):
        self.s = settings
        self.retriever: Retriever | None = None
        self.bundle: Bundle | None = None
        self.encoder: Encoder | None = None
        self.reranker: Reranker | None = None
        self.reranker_error = ""
        self._compute = asyncio.Semaphore(2)  # bound concurrent CPU-heavy embedding/rerank work
        self._lock = threading.Lock()

    def load(self) -> None:
        """Blocking load (run in a thread at start-up and after a re-index)."""
        import os

        import torch

        # Two compute slots share the CPU; letting each use every core just oversubscribes it.
        torch.set_num_threads(max(2, (os.cpu_count() or 4) // 2))
        with self._lock:
            bundle = load_bundle(self.s.index_dir)
            if bundle is None:
                log.warning("no index bundle found in %s", self.s.index_dir)
                return
            model = bundle.manifest.get("embedding_model", self.s.embedding_model)
            if self.encoder is None or self.encoder.name != model:
                self.encoder = Encoder(model, self.s.embedding_device, self.s.models_local_only)
            if self.reranker is None and self.s.reranker_model:
                try:
                    self.reranker = Reranker(
                        self.s.reranker_model, self.s.embedding_device, self.s.models_local_only
                    )
                except Exception as exc:  # reranking is an optional quality boost
                    self.reranker_error = str(exc)[:200]
                    log.warning("reranker unavailable: %s", exc)
            self.retriever = Retriever(bundle, self.encoder, self.reranker)
            self.bundle = bundle
            log.info("knowledge base ready: build %s (%d chunks)", bundle.build_id, len(bundle.chunks))

    @property
    def ready(self) -> bool:
        return self.retriever is not None

    def info(self) -> dict:
        if not self.bundle:
            return {"ready": False}
        m = self.bundle.manifest
        return {
            "ready": True, "build_id": m["build_id"], "created_at": m.get("created_at"),
            "chunks": m["chunks"], "embedding_model": m.get("embedding_model"),
            "reranker": self.reranker.name if self.reranker else None,
            "reranker_error": self.reranker_error,
        }
