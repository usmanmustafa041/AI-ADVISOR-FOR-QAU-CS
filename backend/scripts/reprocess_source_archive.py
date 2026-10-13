"""Reprocess archived originals offline without overwriting source/extraction versions."""

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import SourceArchive, atomic_write
from app.ingestion.parsing import parse_document
from app.rag.corpus import PROJECT_ROOT


def reprocess(archive: SourceArchive, *, ocr=False):
    run_id, errors = uuid4().hex, []
    documents = archive.corpus_documents()
    current = {v["url"]: archive.latest(v["url"]) for v in documents}
    for version in documents:
        previous = version["document"]
        metadata = previous["metadata"]
        try:
            parsed = parse_document(
                (archive.root / version["raw_path"]).read_bytes(),
                previous.get("final_url", version["url"]),
                previous["mime_type"],
                ocr=ocr,
            )
            if previous.get("final_url"):
                parsed["final_url"] = previous["final_url"]
            if metadata.get("ingestion_method") == "local_archive_import":
                parsed["title"] = previous["title"]
                for key in (
                    "program",
                    "category",
                    "effective_term",
                    "source_captured_at",
                    "ingestion_method",
                ):
                    if metadata.get(key) is not None:
                        parsed["metadata"][key] = metadata[key]
            parsed["metadata"]["verification_status"] = metadata["verification_status"]
            resource = current[version["url"]]
            archive.save(
                run_id,
                version["url"],
                (archive.root / version["raw_path"]).read_bytes(),
                parsed,
                {"etag": resource["etag"], "last-modified": resource["last_modified"]},
                make_current=resource["raw_sha256"] == version["raw_sha256"],
                previous_version=version,
            )
        except Exception as exc:
            errors.append({"version_id": version["version_id"], "error": str(exc)[:500]})
            archive.observe(run_id, version["url"], "error", detail=errors[-1])
    records = archive.export_records(archive.root / "structured_records.jsonl")
    report = {**archive.run_summary(run_id), "errors": errors, "structured_records": records}
    atomic_write(archive.root / "runs" / f"{run_id}.json", json.dumps(report, indent=2).encode())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, default=PROJECT_ROOT / "academic-data/crawl-archive"
    )
    parser.add_argument("--ocr", action="store_true")
    args = parser.parse_args()
    archive = SourceArchive(args.archive)
    try:
        report = reprocess(archive, ocr=args.ocr)
        print(json.dumps({k: v for k, v in report.items() if k != "observations"}, indent=2))
        return 1 if report["errors"] else 0
    finally:
        archive.close()


if __name__ == "__main__":
    raise SystemExit(main())
