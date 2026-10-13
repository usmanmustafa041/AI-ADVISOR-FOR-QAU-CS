"""Stage matching vectors for existing corpus bytes without changing academic content."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.ingestion.archive import atomic_write, utc_now
from app.rag.corpus import load_corpus
from app.rag.encoding import encode_documents
from app.rag.evidence import fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.corpus.resolve() == args.output.resolve():
        parser.error("Use a separate staging output; this command never replaces the live bundle")
    import io

    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(4)
    settings = get_settings()
    data = args.corpus.read_bytes()
    chunks = load_corpus(args.corpus)
    model = SentenceTransformer(
        settings.embedding_model,
        cache_folder=settings.embedding_cache_path or None,
        local_files_only=True,
        device=settings.embedding_device,
    )
    vectors = encode_documents(
        model,
        [c.title + "\n" + c.content for c in chunks],
        settings.embedding_model,
        batch_size=32,
        show_progress_bar=True,
    )
    stream = io.BytesIO()
    np.save(stream, vectors, allow_pickle=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(args.output.with_suffix(".vectors.npy"), stream.getvalue())
    manifest = {
        "model": settings.embedding_model,
        "fingerprint": fingerprint(chunks, settings.embedding_model),
        "shape": list(vectors.shape),
        "normalized": True,
    }
    atomic_write(args.output.with_suffix(".vectors.json"), json.dumps(manifest, indent=2).encode())
    audit = args.corpus.with_suffix(".audit.json")
    if audit.exists():
        atomic_write(args.output.with_suffix(".audit.json"), audit.read_bytes())
    atomic_write(args.output, data)
    report = {
        "created_at": utc_now(),
        "model": settings.embedding_model,
        "chunks": len(chunks),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "academic_content_changed": False,
        "published": False,
    }
    atomic_write(
        args.output.parent / "embedding_migration.json", json.dumps(report, indent=2).encode()
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
