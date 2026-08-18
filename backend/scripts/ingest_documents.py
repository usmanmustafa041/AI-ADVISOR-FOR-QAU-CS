"""Extract and chunk official documents into JSONL for database ingestion.

Usage:
    python scripts/ingest_documents.py academic-data/university-policies --output chunks.jsonl
"""

import argparse
import json
from pathlib import Path

from app.rag.documents import document_chunks
from app.rag.embedding import embed_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = []
    for path in sorted(args.input_dir.rglob("*")):
        if path.suffix.lower() not in {".pdf", ".txt", ".md", ".csv"}:
            continue
        for chunk in document_chunks(path):
            records.append(
                {
                    "document_path": str(path),
                    "chunk_index": chunk.index,
                    "content": chunk.content,
                    "page_number": chunk.page_number,
                    "embedding": embed_text(chunk.content),
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} chunks to {args.output}")


if __name__ == "__main__":
    main()

