"""Small in-memory BM25 (the whole corpus is a few thousand chunks)."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np

from advisor.retrieval.text import tokenize


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.4, b: float = 0.72):
        self.k1, self.b = k1, b
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.doc_len = np.zeros(len(docs), dtype=np.float32)
        for i, text in enumerate(docs):
            toks = tokenize(text)
            self.doc_len[i] = len(toks)
            for term, tf in Counter(toks).items():
                self.postings[term].append((i, tf))
        self.n = len(docs)
        self.avg_len = float(self.doc_len.mean()) if self.n else 1.0
        self.idf = {
            t: math.log(1 + (self.n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()
        }

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(self.n, dtype=np.float32)
        for term, qtf in Counter(tokenize(query)).items():
            plist = self.postings.get(term)
            if not plist:
                continue
            idf = self.idf[term] * (1 + 0.15 * min(qtf - 1, 2))
            for i, tf in plist:
                norm = self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avg_len)
                out[i] += idf * tf * (self.k1 + 1) / (tf + norm)
        return out
