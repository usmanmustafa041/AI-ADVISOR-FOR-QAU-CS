"""Import registered originals and explicitly provided PDFs without network access."""

import argparse
import csv
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import SourceArchive, atomic_write
from app.ingestion.parsing import document_metadata, parse_document
from app.rag.corpus import PROJECT_ROOT, is_official_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--archive", type=Path, default=PROJECT_ROOT / "academic-data/crawl-archive"
    )
    parser.add_argument("--provided-pdf", action="append", type=Path, default=[])
    parser.add_argument("--ocr", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    with (root / "academic-data/source-registry/source_inventory.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    for path in args.provided_pdf:
        path = path.resolve()
        if not path.is_relative_to(root) or path.suffix.lower() != ".pdf":
            parser.error("Provided PDFs must be inside the project root")
        rows.append(
            {
                "local_path": str(path.relative_to(root)),
                "source_url": "",
                "title": path.stem,
                "verification_status": "provided_unverified",
            }
        )
    run_id, skipped, errors = uuid4().hex, 0, []
    archive = SourceArchive(args.archive)
    try:
        for row in rows:
            path = (root / row.get("local_path", "")).resolve()
            url = row.get("source_url", "")
            provided = row.get("verification_status") == "provided_unverified"
            if (
                not path.is_relative_to(root)
                or not path.is_file()
                or path.suffix.lower() not in {".pdf", ".html"}
                or (not provided and not is_official_url(url))
            ):
                skipped += 1
                continue
            url = url or "provided:///" + path.relative_to(root).as_posix()
            raw = path.read_bytes()
            try:
                parsed = parse_document(
                    raw,
                    url,
                    "application/pdf" if path.suffix.lower() == ".pdf" else "text/html",
                    ocr=args.ocr,
                )
                parsed["title"] = row["title"]
                publication_date = parsed["metadata"]["publication_date"]
                parsed["metadata"] = {
                    **parsed["metadata"],
                    **document_metadata(
                        row["title"], url, "\n".join(p["content"] for p in parsed["pages"])
                    ),
                    "category": row.get("category") or parsed["metadata"]["category"],
                    "program": row.get("program") or parsed["metadata"]["program"],
                    "source_captured_at": row.get("last_verified_at") or None,
                    "verification_status": "provided_unverified" if provided else "archived",
                    "ingestion_method": "local_archive_import",
                    "publication_date": publication_date,
                }
                if not parsed["metadata"]["effective_term"]:
                    parsed["metadata"]["effective_term"] = row.get("effective_from") or None
                archive.save(run_id, url, raw, parsed, {})
            except Exception as exc:
                errors.append({"path": str(path.relative_to(root)), "error": str(exc)[:500]})
                archive.observe(run_id, url, "error", detail=errors[-1])
        count = archive.export_records(archive.root / "structured_records.jsonl")
        report = {
            **archive.run_summary(run_id),
            "skipped": skipped,
            "errors": errors,
            "structured_records": count,
        }
        atomic_write(
            archive.root / "runs" / f"{run_id}.json", json.dumps(report, indent=2).encode()
        )
        print(json.dumps({k: v for k, v in report.items() if k != "observations"}, indent=2))
        return 1 if errors else 0
    finally:
        archive.close()


if __name__ == "__main__":
    raise SystemExit(main())
