"""Extract and chunk official documents into JSONL for database ingestion.

Supports both generic documents and structured academic documents (timetables, schemes).

Usage:
    python scripts/ingest_documents.py academic-data/university-policies --output chunks.jsonl
    python scripts/ingest_documents.py academic-data/timetable --output timetable.jsonl --structured
"""

import argparse
import json
import logging
from pathlib import Path

from app.rag.documents import document_chunks
from app.rag.embedding import embed_text
from app.rag.structured_extraction.pipeline import StructuredIngestionPipeline
from app.rag.structured_extraction.logging_config import configure_extraction_logger

# Configure logging
logger = configure_extraction_logger("ingest_documents", level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract and chunk documents into JSONL for database ingestion"
    )
    parser.add_argument("input_dir", type=Path, help="Input directory containing documents")
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL file path")
    parser.add_argument(
        "--structured",
        action="store_true",
        help="Use structured extraction for timetables and schemes of study"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logger.setLevel(getattr(logging, args.log_level))
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    if args.structured:
        # Use new structured extraction pipeline (Requirements 10-15)
        logger.info(f"Using structured extraction pipeline for {args.input_dir}")
        pipeline = StructuredIngestionPipeline()
        summary = pipeline.process_batch(str(args.input_dir), str(args.output))
        
        print(f"\nBatch Processing Summary:")
        print(f"  Total documents: {summary.total_documents}")
        print(f"  Successful: {summary.successful_documents}")
        print(f"  Failed: {summary.failed_documents}")
        print(f"  Total chunks: {summary.total_chunks_created}")
        print(f"  Entries skipped: {summary.total_entries_skipped}")
        print(f"\nOutput written to: {args.output}")
    else:
        # Use existing generic extraction pipeline
        logger.info(f"Using generic extraction pipeline for {args.input_dir}")
        records = []
        for path in sorted(args.input_dir.rglob("*")):
            if path.suffix.lower() not in {".pdf", ".txt", ".md", ".csv"}:
                continue
            logger.debug(f"Processing {path}")
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
        
        with args.output.open("w", encoding="utf-8") as output:
            for record in records:
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
        
        print(f"Wrote {len(records)} chunks to {args.output}")


if __name__ == "__main__":
    main()

