"""Inventory university originals in the workspace, preserving local provenance."""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import SourceArchive, atomic_write, utc_now
from app.ingestion.parsing import parse_document
from app.rag.corpus import PROJECT_ROOT, canonical_url, is_official_url

MIMES = {
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}
EXCLUDE = {
    ".git",
    ".venv",
    "node_modules",
    ".model-cache",
    "crawl-archive",
    "snapshots",
    "dist",
    "build",
    ".pytest_cache",
    "test-results",
    "playwright-report",
}


def inventory(root):
    import os

    for directory, folders, files in os.walk(root):
        folders[:] = sorted(f for f in folders if f not in EXCLUDE and not f.startswith("."))
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(root)
            if path.is_symlink() or path.suffix.lower() not in MIMES:
                continue
            if relative.parts[0] in {"backend", "frontend"} and path.suffix.lower() not in {
                ".pdf",
                ".docx",
            }:
                continue
            if path.suffix.lower() == ".txt" and relative.parts[0] != "academic-data":
                continue
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--archive", type=Path, default=PROJECT_ROOT / "academic-data/crawl-archive"
    )
    parser.add_argument("--ocr", action="store_true")
    args = parser.parse_args()
    root, run_id = args.root.resolve(), uuid4().hex
    registry = root / "academic-data/source-registry/source_inventory.csv"
    registered = {}
    if registry.exists():
        with registry.open() as stream:
            registered = {r.get("local_path"): r for r in csv.DictReader(stream)}
    archive = SourceArchive(args.archive)
    resources = []
    try:
        for path in inventory(root):
            relative = path.relative_to(root).as_posix()
            raw = path.read_bytes()
            row = {
                "local_path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "source_url": None,
                "status": "pending",
            }
            resources.append(row)
            registration = registered.get(relative, {})
            official = registration.get("source_url", "")
            if is_official_url(official):
                matching = [
                    v
                    for v in archive.versions()
                    if v["raw_sha256"] == row["sha256"]
                    and canonical_url(v["url"]) == canonical_url(official)
                ]
                if matching:
                    row.update(
                        status="registered_original",
                        version_id=matching[-1]["version_id"],
                        source_url=official,
                    )
                    continue
            url = "provided:///" + relative
            row["source_url"] = url
            try:
                if len(raw) > 20 * 1024 * 1024:
                    raise ValueError("Document exceeds 20MB extraction limit")
                previous = archive.latest(url)
                if previous and previous["raw_sha256"] == row["sha256"]:
                    row.update(status="unchanged", version_id=previous["version_id"])
                    continue
                parsed = parse_document(raw, url, MIMES[path.suffix.lower()], ocr=args.ocr)
                parsed["metadata"].update(
                    verification_status="provided_unverified",
                    ingestion_method="workspace_discovery",
                    local_path=relative,
                )
                saved = archive.save(run_id, url, raw, parsed, {})
                row.update(
                    status="processed", version_id=saved["version_id"], warnings=parsed["warnings"]
                )
            except Exception as exc:
                row.update(status="failed", error=str(exc)[:300])
                archive.observe(run_id, url, "error", detail=row)
        report = {
            "run_id": run_id,
            "created_at": utc_now(),
            "resources": resources,
            "discovered": len(resources),
            "note": "Local files remain unverified.",
        }
        atomic_write(
            archive.root / "workspace_coverage.json", json.dumps(report, indent=2).encode()
        )
        archive.export_records(archive.root / "structured_records.jsonl")
        print(json.dumps(report, indent=2))
        return int(any(r["status"] == "failed" for r in resources))
    finally:
        archive.close()


if __name__ == "__main__":
    raise SystemExit(main())
