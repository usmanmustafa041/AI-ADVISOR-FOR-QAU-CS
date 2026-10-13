"""Administrator review of immutable ingestion versions; no automatic policy approval."""

import json
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.auth import admin_user
from app.core.config import get_settings
from app.ingestion.archive import SourceArchive, atomic_write, utc_now
from app.rag.corpus import BACKEND_ROOT, PROJECT_ROOT, corpus_path, load_corpus
from app.rag.evidence import fingerprint

router = APIRouter(prefix="/knowledge-review", tags=["knowledge review"])
Admin = Annotated[dict, Depends(admin_user)]


def archive_dependency():
    root = Path(get_settings().knowledge_archive_path)
    # FastAPI may run dependency setup, handler and teardown on different worker
    # threads. Each request owns one connection and uses it sequentially.
    archive = SourceArchive(
        root if root.is_absolute() else PROJECT_ROOT / root, thread_handoff=True
    )
    try:
        yield archive
    finally:
        archive.close()


Archive = Annotated[SourceArchive, Depends(archive_dependency)]


@router.get("")
def overview(_: Admin, archive: Archive):
    versions = archive.versions()
    reviews = Counter(archive.review_status(v["version_id"])["decision"] for v in versions)
    counts = Counter(r[0] for r in archive.db.execute("SELECT status FROM observations"))
    conflicts = archive.root / "cohort_changes.json"
    workspace = archive.root / "workspace_coverage.json"
    source_conflicts = archive.root / "source_conflicts.json"
    return {
        "versions": len(versions),
        "reviews": dict(reviews),
        "observations": dict(counts),
        "conflicts": json.loads(conflicts.read_text()) if conflicts.exists() else {},
        "workspace": json.loads(workspace.read_text()) if workspace.exists() else {},
        "source_conflicts": json.loads(source_conflicts.read_text())
        if source_conflicts.exists()
        else {},
        "notice": "Review approves an exact extraction version. New versions remain pending.",
    }


@router.get("/versions")
def list_versions(
    _: Admin, archive: Archive, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)
):
    versions = list(reversed(archive.versions()))
    items = []
    for version in versions[offset : offset + limit]:
        document = archive.parsed(version)
        items.append(
            {
                "version_id": version["version_id"],
                "url": version["url"],
                "sha256": version["raw_sha256"],
                "title": document["title"],
                "metadata": document["metadata"],
                "warnings": document["warnings"],
                "records": len(document["records"]),
                "review": archive.review_status(version["version_id"]),
            }
        )
    return {"items": items, "total": len(versions), "offset": offset}


@router.get("/versions/{version_id}")
def version_detail(version_id: str, _: Admin, archive: Archive):
    row = archive.db.execute("SELECT * FROM versions WHERE version_id=?", (version_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown source version")
    version = dict(row)
    parsed = archive.parsed(version)
    changes = []
    for path in sorted((archive.root / "changes").glob(f"*-{version_id}.json"))[:5]:
        changes.append(json.loads(path.read_text()))
    return {
        "version_id": version_id,
        "url": version["url"],
        "sha256": version["raw_sha256"],
        "document": {
            **parsed,
            "records": parsed["records"][:300],
            "pages": [{**p, "content": p["content"][:12000]} for p in parsed["pages"][:20]],
        },
        "review": archive.review_status(version_id),
        "changes": changes,
        "truncated": len(parsed["pages"]) > 20
        or len(parsed["records"]) > 300
        or any(len(p["content"]) > 12000 for p in parsed["pages"]),
    }


@router.get("/versions/{version_id}/original")
def original_document(version_id: str, _: Admin, archive: Archive):
    row = archive.db.execute(
        "SELECT raw_path FROM versions WHERE version_id=?", (version_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown source version")
    path = (archive.root / row["raw_path"]).resolve()
    if not path.is_relative_to(archive.root) or not path.is_file():
        raise HTTPException(404, "Original object unavailable")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=version_id + path.suffix,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


class ReviewRequest(BaseModel):
    decision: Literal["approved", "rejected", "pending"]
    note: str = Field(min_length=5, max_length=2000)
    acknowledge_warnings: bool = False


@router.put("/versions/{version_id}")
def review_version(version_id: str, request: ReviewRequest, user: Admin, archive: Archive):
    try:
        return archive.review(
            version_id, request.decision, user["id"], request.note, request.acknowledge_warnings
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.get("/runs")
def runs(_: Admin, archive: Archive):
    files = sorted(
        (archive.root / "runs").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )[:20]
    return [
        {
            "file": p.stem,
            **{
                k: v
                for k, v in json.loads(p.read_text()).items()
                if k not in {"observations", "resources"}
            },
        }
        for p in files
    ]


@router.get("/runs/{run_id}")
def run_detail(run_id: str, _: Admin, archive: Archive):
    if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        raise HTTPException(404, "Unknown run")
    path = archive.root / "runs" / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(404, "Unknown run")
    return json.loads(path.read_text())


class PublicationRequest(BaseModel):
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    note: str = Field(min_length=10, max_length=2000)


@router.post("/publish")
def publish(request: PublicationRequest, user: Admin, archive: Archive):
    import fcntl

    from scripts.refresh_knowledge import publish_snapshot

    snapshots = BACKEND_ROOT / "data/rag/snapshots"
    directory = snapshots / request.snapshot_id
    candidate = directory / "corpus.jsonl"
    if not candidate.is_file():
        raise HTTPException(404, "Snapshot not found")
    with (snapshots / ".refresh.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise HTTPException(409, "A knowledge refresh is active") from None
        report_path = directory / "refresh_report.json"
        report = json.loads(report_path.read_text()) if report_path.exists() else {}
        if not report.get("retrieval_gate_passed"):
            raise HTTPException(409, "Snapshot has not passed its retrieval gate")
        chunks = load_corpus(candidate)
        approved = {v["version_id"] for v in archive.approved_documents()}
        if not chunks or any(c.source_version_id not in approved for c in chunks):
            raise HTTPException(409, "Snapshot includes unreviewed or superseded source versions")
        manifest_path = candidate.with_suffix(".vectors.json")
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        if (
            manifest.get("model") != get_settings().embedding_model
            or manifest.get("fingerprint") != fingerprint(chunks, get_settings().embedding_model)
            or not candidate.with_suffix(".vectors.npy").is_file()
        ):
            raise HTTPException(409, "Snapshot embeddings do not match the configured model")
        target = corpus_path(get_settings().rag_corpus_path)
        publish_snapshot(candidate, target, directory / "previous.jsonl")
        report.update(
            published=True,
            status="published",
            published_at=utc_now(),
            published_by=user["id"],
            publication_note=request.note,
        )
        atomic_write(report_path, json.dumps(report, indent=2).encode())
    return {"published": True, "snapshot_id": request.snapshot_id}
