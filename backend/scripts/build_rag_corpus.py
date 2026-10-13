"""Build an audited evidence snapshot and optional matching dense vectors.

Run from backend: python scripts/build_rag_corpus.py --semantic
Model downloads occur only with --allow-download, never during a chat request.
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.rag.corpus import PROJECT_ROOT, build_corpus, corpus_path
from app.rag.encoding import encode_documents
from app.rag.evidence import fingerprint


def atomic_text(path, content):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    os.replace(temp, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--crawl-archive", type=Path, help="Immutable public-source archive to include"
    )
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--approved-only", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    output = args.output or corpus_path(settings.rag_corpus_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    chunks, report = build_corpus(
        args.root, crawl_archive=args.crawl_archive, approved_only=args.approved_only
    )
    report["approved_only"] = args.approved_only
    if not chunks:
        raise SystemExit("No usable evidence found; refusing to replace corpus")
    if args.semantic:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            settings.embedding_model, local_files_only=not args.allow_download,
            cache_folder=settings.embedding_cache_path or None, device=settings.embedding_device,
        )
        vectors = encode_documents(
            model,
            [c.title + "\n" + c.content for c in chunks],
            settings.embedding_model,
            show_progress_bar=True,
            batch_size=32,
        )
        target = output.with_suffix(".vectors.npy")
        temp = target.with_suffix(".tmp")
        with temp.open("wb") as stream:
            np.save(stream, vectors, allow_pickle=False)
        os.replace(temp, target)
        atomic_text(
            output.with_suffix(".vectors.json"),
            json.dumps(
                {
                    "model": settings.embedding_model,
                    "fingerprint": fingerprint(chunks, settings.embedding_model),
                    "shape": list(vectors.shape),
                    "normalized": True,
                },
                indent=2,
            ),
        )
    # Write the corpus last. A failed model load leaves the previous corpus in
    # place; a reader during replacement safely falls back to lexical search
    # until the exact model/corpus fingerprint matches.
    atomic_text(output.with_suffix(".audit.json"), json.dumps(report, indent=2, ensure_ascii=False))
    atomic_text(output, "".join(json.dumps(asdict(c), ensure_ascii=False) + "\n" for c in chunks))
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "scraped_pages",
                    "duplicates",
                    "unique_documents",
                    "chunks",
                    "chunk_characters",
                )
            }
        )
    )
    print(
        f"Rejected records: {len(report['rejected'])}; "
        f"extraction warnings: {len(report['warnings'])}"
    )
    print(f"Corpus: {output}")


if __name__ == "__main__":
    main()
