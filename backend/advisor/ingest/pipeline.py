"""Snapshot store → documents → chunks (the offline half of the knowledge pipeline)."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from advisor.ingest.chunker import chunk_document
from advisor.ingest.derived import derive_documents
from advisor.ingest.fees import fee_documents, parse_fee_page
from advisor.ingest.model import Chunk, Document
from advisor.ingest.pdf_extract import extract_pdf
from advisor.ingest.snapshots import PageRecord, SnapshotStore
from advisor.ingest.web_extract import canonical_url, extract_web

log = logging.getLogger("advisor.ingest")

# Pages that exist for navigation/forms only.
SKIP_URL = re.compile(r"(login|/alumni$|/search)", re.I)
SKIP_PDF_TITLE = re.compile(r"provisional list", re.I)


@dataclass
class IngestReport:
    pages: int = 0
    documents: int = 0
    chunks: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)
    by_kind: dict[str, int] = field(default_factory=dict)
    errors: list[tuple[str, str]] = field(default_factory=list)
    prereq_graph: object | None = None
    timetable: dict | None = None  # structured weekly timetable (newest term wins)
    fee_pages: list = field(default_factory=list)  # structured fee tables (Bachelor / MPhil / PhD pages)
    prereq_notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        kinds = ", ".join(f"{k}={v}" for k, v in sorted(self.by_kind.items()))
        return (
            f"pages={self.pages} documents={self.documents} chunks={self.chunks} "
            f"skipped={len(self.skipped)} errors={len(self.errors)} [{kinds}]"
        )


def _prefer(a: PageRecord, b: PageRecord) -> PageRecord:
    """Between duplicate-content URLs keep the cleaner, more canonical one."""

    def score(r: PageRecord):
        u = r.url
        numeric = bool(re.search(r"/faculty/\d+$", u))
        return (numeric, ".php" in u, len(u))

    return a if score(a) <= score(b) else b


def prerequisite_files(extra_dir: Path | None = None) -> list[Path]:
    bundled = sorted((Path(__file__).resolve().parents[1] / "prereq" / "data").glob("*.json"))
    extra = sorted(Path(extra_dir).glob("*.json")) if extra_dir and Path(extra_dir).exists() else []
    return bundled + extra


def collect_documents(
    store: SnapshotStore,
    report: IngestReport | None = None,
    prereq_dir: Path | None = None,
    documents_dir: Path | None = None,
) -> list[Document]:
    report = report or IngestReport()
    records = store.all_ok()
    # Duplicate-content URLs (legacy .php paths, numeric faculty ids) collapse to one.
    by_sha: dict[str, PageRecord] = {}
    for rec in records:
        if rec.sha256 is None:
            continue
        by_sha[rec.sha256] = _prefer(by_sha[rec.sha256], rec) if rec.sha256 in by_sha else rec
    docs: list[Document] = []
    for rec in sorted(by_sha.values(), key=lambda r: r.url):
        url = canonical_url(rec.final_url or rec.url)
        if rec.url != url and "cs.qau.edu.pk" in rec.url:
            url = canonical_url(rec.url)
        if SKIP_URL.search(url):
            report.skipped.append((url, "navigation/form page"))
            continue
        report.pages += 1
        try:
            raw_path = store.object_path(rec.sha256, rec.ext or "")
            if rec.ext == ".html":
                html = raw_path.read_bytes().decode("utf-8", "replace")
                fee_page = parse_fee_page(url, html, rec.fetched_at)
                if fee_page:  # fee tables are kept apart (CS / other programmes / foreign) instead of read as running text
                    report.fee_pages.append(fee_page)
                    docs += fee_documents(fee_page)
                else:
                    docs += extract_web(url, html, rec.fetched_at)
            elif rec.ext == ".pdf":
                docs += extract_pdf(Path(raw_path), url, rec.fetched_at)
            else:
                report.skipped.append((url, f"unsupported type {rec.content_type}"))
        except Exception as exc:  # one bad file must not block the rebuild
            log.exception("extraction failed: %s", url)
            report.errors.append((url, f"{type(exc).__name__}: {exc}"))
    docs = _dedupe_entities(docs)
    docs = _merge_faculty_listing(docs)
    docs += derive_documents(docs)
    docs += _prerequisites(docs, report, prereq_dir)
    tables = [d for d in docs if d.payload.get("timetable", {}).get("sessions")]
    if tables:  # several timetable PDFs may exist (old terms); the most recently fetched is current
        report.timetable = max(tables, key=lambda d: (d.fetched_at, len(d.payload["timetable"]["sessions"]))).payload["timetable"]
    from advisor.ingest.local_docs import local_documents

    local = local_documents(documents_dir)
    if local:
        report.prereq_notes.append(f"department documents: {', '.join(d.title for d in local)}")
    docs += local
    return docs


def _prerequisites(docs: list[Document], report: IngestReport, prereq_dir: Path | None) -> list[Document]:
    """Build the prerequisite graph from verified department files + course pages."""
    from advisor.prereq.graph import build_graph, prerequisite_documents
    from advisor.prereq.verify import verify

    good: list[Path] = []
    for f in prerequisite_files(prereq_dir):
        source_doc = f.with_suffix(".docx")
        result = verify(f, source_doc if source_doc.exists() else None)
        if result["errors"]:
            report.prereq_notes.append(f"REJECTED {f.name}: " + "; ".join(result["errors"][:5]))
            log.error("prerequisite file %s rejected: %s", f.name, result["errors"][:5])
            continue
        report.prereq_notes.append(
            f"loaded {f.name}: {result['stats']['prerequisite_rows']} rows, source-verified="
            f"{result['stats']['quotes_checked_against_source']}"
        )
        good.append(f)
    graph = build_graph([d for d in docs if d.kind == "course"], good)
    cycle = graph.has_cycle()
    if cycle:
        report.prereq_notes.append("WARNING prerequisite cycle: " + " → ".join(cycle))
    report.prereq_graph = graph
    return prerequisite_documents(graph)


def _dedupe_entities(docs: list[Document]) -> list[Document]:
    """The site serves each faculty profile under a numeric id *and* a name slug."""
    best: dict[tuple, Document] = {}
    rest: list[Document] = []
    for d in docs:
        name = d.meta.get("faculty_name")
        if d.kind in ("faculty", "publications") and name:
            key = (d.kind, name)
            cur = best.get(key)
            if cur is None or (re.search(r"/faculty/\d+$", cur.url) and not re.search(r"/faculty/\d+$", d.url)):
                best[key] = d
        else:
            rest.append(d)
    return rest + list(best.values())


def _merge_faculty_listing(docs: list[Document]) -> list[Document]:
    """Fold position / room / contact from the directory page into each profile card."""
    entries: dict[str, dict] = {}
    for d in docs:
        if d.kind == "faculty_listing":
            entries.update(d.meta.get("entries", {}))
    for d in docs:
        if d.kind != "faculty":
            continue
        rec = entries.get((d.meta.get("faculty_name") or "").lower())
        if not rec:
            continue
        d.meta["position"] = rec["position"]
        d.meta["room"] = rec.get("room", "")
        d.meta["email"] = d.meta.get("email") or rec.get("email", "")
        d.meta["phone"] = d.meta.get("phone") or rec.get("phone", "")
        card = d.blocks[0]
        lines = [ln for ln in card.text.split("\n") if not ln.startswith("Designation:")]
        lines.insert(1, f"Position: {rec['position']}")
        if rec.get("room"):
            lines.insert(2, f"Office: {rec['room']}")
        card.text = "\n".join(lines)
    return [d for d in docs if d.kind != "faculty_listing"]


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text).strip().lower()


def build_chunks(docs: list[Document], report: IngestReport | None = None) -> list[Chunk]:
    report = report or IngestReport()
    chunks: list[Chunk] = []
    seen: dict[str, Chunk] = {}
    for doc in sorted(docs, key=lambda d: (-d.priority, d.url, d.title)):
        for ch in chunk_document(doc):
            key = hashlib.sha1(_norm(ch.text).encode()).hexdigest()
            if key in seen:
                continue  # identical text already indexed from a higher-priority source
            seen[key] = ch
            chunks.append(ch)
    report.documents = len(docs)
    report.chunks = len(chunks)
    for ch in chunks:
        report.by_kind[ch.kind] = report.by_kind.get(ch.kind, 0) + 1
    return chunks
