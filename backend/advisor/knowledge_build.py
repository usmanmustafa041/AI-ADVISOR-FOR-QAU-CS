"""Crawl → extract → chunk → embed → publish. Shared by the CLI and the admin console."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from advisor.config import Settings
from advisor.ingest.crawler import Crawler
from advisor.ingest.pipeline import IngestReport, build_chunks, collect_documents
from advisor.ingest.snapshots import SnapshotStore
from advisor.retrieval.bundle import prune_builds, write_bundle
from advisor.retrieval.models import Encoder

log = logging.getLogger("advisor.build")

Progress = Callable[[str], None]


def build_index(settings: Settings, model_name: str | None = None, progress: Progress | None = None) -> dict:
    say = progress or (lambda _m: None)
    store = SnapshotStore(settings.snapshot_dir)
    report = IngestReport()
    say("extracting documents")
    docs = collect_documents(store, report, settings.data_dir / "prerequisites", settings.data_dir / "documents")
    chunks = build_chunks(docs, report)
    if len(chunks) < 50:
        raise RuntimeError(f"refusing to publish an index of only {len(chunks)} chunks (extraction problem?)")
    model_name = model_name or settings.embedding_model
    say(f"embedding {len(chunks)} passages with {model_name}")
    enc = Encoder(model_name, settings.embedding_device, settings.models_local_only)
    vectors = enc.encode_passages([c.index_text for c in chunks])
    files = {}
    if report.prereq_graph is not None:
        import json

        files["prereq_graph.json"] = json.dumps(report.prereq_graph.to_json(), ensure_ascii=False)
    if report.fee_pages:
        import json

        files["fees.json"] = json.dumps({"pages": report.fee_pages}, ensure_ascii=False)
    if report.timetable:
        import json

        files["timetable.json"] = json.dumps(report.timetable, ensure_ascii=False)
    path = write_bundle(
        settings.index_dir, chunks, vectors,
        {"embedding_model": model_name, "ingest": report.summary(), "errors": report.errors[:20],
         "prerequisites": report.prereq_notes},
        files,
    )
    prune_builds(settings.index_dir)
    return {"build_id": path.name, "summary": report.summary(), "errors": report.errors[:20]}


def refresh_knowledge(
    settings: Settings, *, crawl: bool = True, model_name: str | None = None, progress: Progress | None = None
) -> dict:
    say = progress or (lambda _m: None)
    crawl_summary = ""
    if crawl:
        say("downloading the website and documents")
        store = SnapshotStore(settings.snapshot_dir)
        report = asyncio.run(Crawler(settings, store).run())
        crawl_summary = report.summary()
        if report.fetched + report.unchanged < 50:
            raise RuntimeError(
                f"crawl looks incomplete ({crawl_summary}); keeping the current index. "
                f"First failures: {report.failed[:3]}"
            )
        store.close()
    result = build_index(settings, model_name, say)
    result["crawl"] = crawl_summary
    return result
