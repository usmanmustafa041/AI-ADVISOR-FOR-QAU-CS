"""Retrieval-only evaluation: does the evidence set contain the gold facts?"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path

from advisor.rag.query import rule_contextualize
from advisor.retrieval.bundle import Bundle
from advisor.retrieval.retriever import Retriever

GOLDEN = Path(__file__).with_name("golden.json")


def load_golden(name: str = "golden") -> list[dict]:
    return json.loads(GOLDEN.with_name(f"{name}.json").read_text())


def validate_gold(bundle: Bundle, items: list[dict]) -> list[str]:
    """Every gold pattern must exist somewhere in the corpus, or the test itself is wrong."""
    bad = []
    blob = [c["text"] + "\n" + c["heading"] + "\n" + c["url"] for c in bundle.chunks]
    for it in items:
        for pat in it.get("gold", []):
            rx = re.compile(pat, re.I)
            if not any(rx.search(b) for b in blob):
                bad.append(f"{it['id']}: gold pattern matches no chunk: {pat}")
    return bad


def run(retriever: Retriever, items: list[dict], *, k_context: int, char_budget: int, verbose=False):
    per_cat = defaultdict(lambda: [0, 0])
    failures = []
    ranks = []
    t0 = time.time()
    for it in items:
        if not it.get("gold"):
            continue
        history = [tuple(h) for h in it.get("history", [])]
        query = rule_contextualize(it["q"], history)
        hits = retriever.search(query)
        ctx = retriever.context(hits, max_chunks=k_context, char_budget=char_budget)
        texts = [h.chunk["text"] + "\n" + h.chunk["heading"] + "\n" + h.chunk["url"] for h in ctx]
        ok = True
        first_rank = []
        for pat in it["gold"]:
            rx = re.compile(pat, re.I)
            found = next((i for i, t in enumerate(texts) if rx.search(t)), None)
            if found is None:
                ok = False
            else:
                first_rank.append(found)
        per_cat[it["cat"]][1] += 1
        if ok:
            per_cat[it["cat"]][0] += 1
            ranks.append(max(first_rank) if first_rank else 0)
        else:
            full = [h.chunk["text"] + "\n" + h.chunk["heading"] for h in hits]
            where = []
            for pat in it["gold"]:
                rx = re.compile(pat, re.I)
                where.append(next((i for i, t in enumerate(full) if rx.search(t)), None))
            failures.append((it["id"], it["q"], where))
    total = sum(v[1] for v in per_cat.values())
    good = sum(v[0] for v in per_cat.values())
    return {
        "passed": good, "total": total, "rate": good / max(total, 1),
        "per_cat": {k: f"{v[0]}/{v[1]}" for k, v in sorted(per_cat.items())},
        "failures": failures, "seconds": round(time.time() - t0, 1),
        "mean_gold_rank": round(sum(ranks) / max(len(ranks), 1), 2),
    }
