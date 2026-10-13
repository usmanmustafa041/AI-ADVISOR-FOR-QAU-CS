"""Encoder/reranker trial with source-linked questions; draft labels are explicitly not gold."""

import argparse
import json
import resource
import time
from pathlib import Path

from chatbot_v3.contracts import Task
from chatbot_v3.embeddings import Encoder, Reranker
from chatbot_v3.index import Index, build_index
from chatbot_v3.settings import ROOT, settings
from chatbot_v3.store import Store


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="intfloat/multilingual-e5-small")
    p.add_argument("--reranker")
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--output", required=True)
    p.add_argument("--cases", type=Path)
    p.add_argument("--approved-only", action="store_true")
    a = p.parse_args()
    config = settings()
    config.embedding_model = a.model
    store = Store()
    start = time.perf_counter()
    encoder = Encoder(a.model, config.embedding_device, True)
    load_ms = (time.perf_counter() - start) * 1000
    reranker = Reranker(a.reranker, config.embedding_device, True) if a.reranker else None
    # Never mutate the active pointer during model selection.
    active = settings().data_dir / "active-index.json"
    can_load = False
    if active.exists():
        bundle = json.loads(active.read_text())
        manifest = json.loads(
            (settings().data_dir / "indexes" / bundle["folder"] / "manifest.json").read_text()
        )
        can_load = (
            manifest["model"] == a.model and manifest.get("encoding_signature") == encoder.signature
        )
    index = Index(store, encoder, reranker, load_bundle=can_load)
    if index.manifest is None or index.manifest["model"] != a.model:
        manifest, folder = build_index(store, encoder, False)
        import numpy as np

        index.chunks = json.loads((folder / "chunks.json").read_text())
        index.vectors = np.load(folder / "vectors.npy", allow_pickle=False)
        index.manifest = manifest
        index.by_id = {c["id"]: i for i, c in enumerate(index.chunks)}
    payload = json.loads(
        (a.cases or ROOT / "backend/evaluation/source_checked_questions.json").read_text()
    )
    original = payload.get("cases", []) if isinstance(payload, dict) else payload
    if a.approved_only:
        original = [
            c
            for c in original
            if c.get("review_status") == "approved"
            and c.get("reviewer")
            and c.get("reviewed_at")
            and c.get("critical_assertions")
            and c.get("approved_reference_answer")
        ]
    cases = [
        c
        for c in original
        if c.get("split") in {"held_out", "held-out"}
        and (not a.approved_only or c.get("approved_relevant_sources"))
    ][: a.limit]
    if not cases and not a.approved_only:
        cases = original[-a.limit :]
    if not cases:
        raise SystemExit(
            "No independently approved held-out retrieval cases; no score was produced"
        )
    results = []
    for case in cases:
        expected = {
            s.get("source_url", "").rstrip("/")
            for s in case.get(
                "approved_relevant_sources" if a.approved_only else "relevant_sources", []
            )
            if s.get("source_url")
        }
        topic = "general"
        # Benchmark scope is obtained from source metadata, not from answer patterns.
        matched = [c for c in index.chunks if c["uri"].rstrip("/") in expected]
        if matched and not a.cases:
            topic = matched[0]["topic"]
        task = Task(
            **{
                "question": case["question"],
                "search_query": case["question"],
                "topic": topic,
                **case.get("retrieval_scope", {}),
            }
        )
        t = time.perf_counter()
        hits, diag = index.search(task, 10)
        elapsed = (time.perf_counter() - t) * 1000
        retrieved = [c["uri"].rstrip("/") for c in hits]
        rank = next((i + 1 for i, u in enumerate(retrieved) if u in expected), None)
        results.append(
            {
                "id": case["id"],
                "language": case.get("language"),
                "source_recall_at_5": len(expected & set(retrieved[:5])) / len(expected)
                if expected
                else None,
                "source_recall_at_10": len(expected & set(retrieved[:10])) / len(expected)
                if expected
                else None,
                "mrr": 1 / rank if rank else 0,
                "source_precision_at_5": sum(u in expected for u in retrieved[:5])
                / min(5, len(retrieved))
                if retrieved
                else 0,
                "latency_ms": elapsed,
                "sources": retrieved,
                "draft_expected_sources": sorted(expected),
            }
        )
    report = {
        "model": a.model,
        "reranker": a.reranker,
        "corpus_checksum": index.manifest["corpus_checksum"],
        "load_ms": load_ms,
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "cases": len(results),
        "metrics": {
            key: sum(r[key] for r in results if r[key] is not None)
            / len([r for r in results if r[key] is not None])
            for key in [
                "source_recall_at_5",
                "source_recall_at_10",
                "mrr",
                "source_precision_at_5",
                "latency_ms",
            ]
        },
        "results": results,
        "limitation": "Retrieval against independently supplied source labels; not end-to-end factual accuracy or production model certification."
        if a.approved_only
        else "Engineering retrieval trial using old AI source-linked draft labels. Not independently reviewed factual accuracy; no production model selection is certified.",
        "independent_reference_labels": bool(a.cases and a.approved_only),
    }
    path = settings().data_dir / "evaluation" / a.output
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "results"}))


if __name__ == "__main__":
    main()
