"""Measure multilingual retrieval with exact source labels and isolated model processes."""

import argparse
import hashlib
import json
import resource
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.ingestion.archive import atomic_write, utc_now
from app.ingestion.evaluation import retrieval_metrics
from app.rag.corpus import load_corpus
from app.rag.encoding import encode_documents, encode_query
from app.rag.evidence import EvidenceIndex, Hit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-path")
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--split", choices=["development", "held_out", "all"], default="development"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reranker")
    args = parser.parse_args()
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(4)
    started = time.perf_counter()
    encoder = SentenceTransformer(
        args.model_path or args.model, local_files_only=True, device=args.device
    )
    load_ms = (time.perf_counter() - started) * 1000
    chunks = load_corpus(args.corpus)
    started = time.perf_counter()
    vectors = encode_documents(
        encoder,
        [c.title + "\n" + c.content for c in chunks],
        args.model,
        batch_size=32,
        show_progress_bar=False,
    )
    indexing_seconds = time.perf_counter() - started
    index = EvidenceIndex(chunks)
    index.encoder, index.vectors, index._dense_attempted = encoder, vectors, True
    get_settings().embedding_model = args.model
    reranker = None
    if args.reranker:
        from sentence_transformers import CrossEncoder

        reranker = CrossEncoder(args.reranker, local_files_only=True, device=args.device)
    cases = json.loads(args.questions.read_text())
    cases = [c for c in cases if args.split == "all" or c["split"] == args.split]
    results = []
    for case in cases:
        started = time.perf_counter()
        # Hybrid uses exactly the production query normalizer/fusion/metadata filters.
        hits = index.search(case["question"], limit=20 if reranker else 5)
        if reranker and hits:
            scores = reranker.predict(
                [(case["question"], h.chunk.title + "\n" + h.chunk.content) for h in hits]
            )
            hits = [
                h
                for _, h in sorted(zip(scores, hits, strict=True), key=lambda pair: -float(pair[0]))
            ][:5]
        elapsed = (time.perf_counter() - started) * 1000
        hybrid = retrieval_metrics(hits, case["relevant_sources"], 5)
        # Raw semantic-only is reported separately so aliases cannot hide language gaps.
        vector = encode_query(encoder, case["question"], args.model)
        similarities = vectors @ vector
        eligible = [i for i, c in enumerate(chunks) if index._eligible(c, case["question"])]
        best = sorted(eligible, key=lambda i: -float(similarities[i]))[:5]
        semantic = retrieval_metrics(
            [Hit(chunks[i], float(similarities[i])) for i in best], case["relevant_sources"], 5
        )
        results.append(
            {
                "id": case["id"],
                "language": case["language"],
                "retrieval_ms": elapsed,
                "hybrid": hybrid,
                "semantic_only": semantic,
            }
        )
    summaries = {}
    for language in ["all", "english", "roman_urdu", "urdu"]:
        rows = [r for r in results if language == "all" or r["language"] == language]
        summaries[language] = {
            "cases": len(rows),
            "latency_ms_p50": statistics.median(r["retrieval_ms"] for r in rows),
            "latency_ms_p95": sorted(r["retrieval_ms"] for r in rows)[
                min(len(rows) - 1, int(len(rows) * 0.95))
            ],
        }
        for mode in ("hybrid", "semantic_only"):
            summaries[language][mode] = {
                metric: sum(r[mode][metric] for r in rows) / len(rows)
                for metric in ("source_recall_at_k", "reciprocal_rank")
            }
    report = {
        "created_at": utc_now(),
        "model": args.model,
        "reranker": args.reranker,
        "corpus_sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
        "questions_sha256": hashlib.sha256(args.questions.read_bytes()).hexdigest(),
        "device": args.device,
        "split": args.split,
        "chunks": len(chunks),
        "dimensions": int(vectors.shape[1]),
        "load_ms": load_ms,
        "indexing_seconds": indexing_seconds,
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * (1 if sys.platform == "darwin" else 1024),
        "vector_bytes": int(vectors.nbytes),
        "parameter_bytes": sum(p.numel() * p.element_size() for p in encoder.parameters()),
        "summary": summaries,
        "results": results,
        "limitation": "AI source-checked engineering set, not independent human ground truth. "
        "Development split is for model selection; held-out fact groups stay separate.",
    }
    atomic_write(args.output, json.dumps(report, indent=2).encode())
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
