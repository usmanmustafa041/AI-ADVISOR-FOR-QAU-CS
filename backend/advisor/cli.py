"""Operational command line: ``python -m advisor.cli <command>``."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def cmd_crawl(args) -> int:
    from advisor.config import get_settings
    from advisor.ingest.crawler import Crawler
    from advisor.ingest.snapshots import SnapshotStore

    s = get_settings()
    store = SnapshotStore(s.snapshot_dir)
    report = asyncio.run(Crawler(s, store).run(force=args.force))
    print(report.summary())
    for url, err in report.failed:
        print("  FAILED", url, err)
    return 0 if not report.failed else 2


def cmd_ingest(args) -> int:
    """Extract documents from the snapshot store and write chunks.jsonl (no embeddings)."""
    import json
    from collections import Counter
    from dataclasses import asdict

    from advisor.config import get_settings
    from advisor.ingest.pipeline import IngestReport, build_chunks, collect_documents
    from advisor.ingest.snapshots import SnapshotStore

    s = get_settings()
    store = SnapshotStore(s.snapshot_dir)
    report = IngestReport()
    docs = collect_documents(store, report)
    chunks = build_chunks(docs, report)
    out = s.data_dir / "chunks.preview.jsonl"
    with out.open("w") as fh:
        for c in chunks:
            fh.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
    print(report.summary())
    sizes = [len(c.text) for c in chunks]
    print(f"chunk chars: min={min(sizes)} median={sorted(sizes)[len(sizes)//2]} max={max(sizes)}")
    for url, why in report.skipped[:10]:
        print("  skipped", url, why)
    for url, err in report.errors:
        print("  ERROR", url, err)
    print("by source:", Counter(c.url for c in chunks).most_common(8))
    return 0


def cmd_index(args) -> int:
    from advisor.config import get_settings
    from advisor.knowledge_build import build_index

    res = build_index(get_settings(), args.model, progress=print)
    print(f"built {res['build_id']}: {res['summary']}")
    return 0


def cmd_refresh(args) -> int:
    from advisor.config import get_settings
    from advisor.knowledge_build import refresh_knowledge

    res = refresh_knowledge(get_settings(), crawl=not args.no_crawl, model_name=args.model, progress=print)
    print(f"published {res['build_id']}: {res['summary']} | crawl: {res['crawl']}")
    return 0


def cmd_search(args) -> int:
    from advisor.config import get_settings
    from advisor.retrieval.bundle import load_bundle
    from advisor.retrieval.models import Encoder, Reranker
    from advisor.retrieval.retriever import Retriever

    s = get_settings()
    bundle = load_bundle(s.index_dir)
    enc = Encoder(bundle.manifest["embedding_model"], s.embedding_device, s.models_local_only)
    rr = Reranker(s.reranker_model, s.embedding_device, s.models_local_only) if args.rerank else None
    r = Retriever(bundle, enc, rr)
    print("entities:", r.entities(args.query))
    for h in r.search(args.query)[: args.n]:
        print(f"{h.score:.4f} {h.chunk['kind']:12s} {h.chunk['url']} | {h.chunk['heading'][:80]}")
        print("      ", h.chunk["text"][:160].replace("\n", " "), "|", {k: v for k, v in h.parts.items()})
    return 0


def cmd_eval_retrieval(args) -> int:
    from advisor.config import get_settings
    from advisor.eval.retrieval_eval import load_golden, run, validate_gold
    from advisor.retrieval.bundle import load_bundle
    from advisor.retrieval.models import Encoder, Reranker
    from advisor.retrieval.retriever import Retriever

    s = get_settings()
    bundle = load_bundle(s.index_dir)
    items = load_golden(args.set)
    for msg in validate_gold(bundle, items):
        print("GOLD-INVALID", msg)
    enc = Encoder(bundle.manifest["embedding_model"], s.embedding_device, s.models_local_only)
    rr = Reranker(args.reranker or s.reranker_model, s.embedding_device, s.models_local_only) if args.rerank else None
    r = Retriever(bundle, enc, rr)
    r.rerank_top = args.rerank_top
    res = run(r, items, k_context=args.k, char_budget=s.context_char_budget)
    print(f"retrieval pass {res['passed']}/{res['total']} = {res['rate']:.1%}  ({res['seconds']}s)  mean-rank {res['mean_gold_rank']}")
    print(res["per_cat"])
    for f in res["failures"]:
        print("  FAIL", f)
    return 0


def cmd_ask(args) -> int:
    from advisor.context import build_context

    ctx = build_context()

    async def go():
        cid = None
        async for ev in ctx.service.stream_answer(args.question, cid):
            if ev["event"] == "delta":
                print(ev["text"], end="", flush=True)
            elif ev["event"] == "reset":
                print("\n[reset]\n", end="")
            elif ev["event"] == "replace":
                print("\n[corrected answer]\n" + ev["text"], end="")
            elif ev["event"] == "sources":
                print("\n\nSources:")
                for src in ev["sources"]:
                    print(f"  [{src['n']}] {src['title']} — {src['url']}")
            elif ev["event"] == "done":
                print(f"\n(provider={ev.get('provider')} outcome={ev['outcome']} {ev.get('latency_ms')}ms)")
            elif ev["event"] == "error":
                print("ERROR", ev["message"])

    asyncio.run(go())
    return 0


def cmd_eval_answers(args) -> int:
    from pathlib import Path

    from advisor.context import build_context
    from advisor.eval import answer_eval
    from advisor.eval.retrieval_eval import load_golden

    ctx = build_context()
    only = set(args.only.split(",")) if args.only else None
    out = Path(args.out)
    summary = asyncio.run(answer_eval.run(ctx, load_golden(args.set), out, only))
    print(json.dumps(summary, indent=1))
    return 0


def cmd_create_admin(args) -> int:
    import getpass

    from advisor.config import get_settings
    from advisor.db import Database
    from advisor.security import hash_password

    password = args.password or getpass.getpass("New admin password (min 10 chars): ")
    if len(password) < 10:
        print("Password must be at least 10 characters.")
        return 1
    db = Database(get_settings().db_path)
    db.execute(
        "INSERT INTO admins(username, password_hash) VALUES(?,?) "
        "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash, failed_logins=0, locked_until=NULL",
        (args.username, hash_password(password)),
    )
    print(f"Administrator '{args.username}' is ready.")
    return 0


def cmd_serve(args) -> int:
    import uvicorn

    uvicorn.run("advisor.api.app:get_app", factory=True, host=args.host, port=args.port, log_level="info")
    return 0


def cmd_add_document(args) -> int:
    import json
    import shutil
    from pathlib import Path

    from advisor.config import get_settings
    from advisor.ingest.local_docs import SUPPORTED

    src = Path(args.path)
    if src.suffix.lower() not in SUPPORTED:
        print(f"Unsupported type {src.suffix}; use one of {', '.join(sorted(SUPPORTED))}")
        return 1
    target_dir = get_settings().data_dir / "documents"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / src.name
    shutil.copy(src, target)
    side = {k: v for k, v in (("title", args.title), ("note", args.note), ("effective", args.effective)) if v}
    if side:
        (target_dir / (src.name + ".meta.json")).write_text(json.dumps(side, ensure_ascii=False))
    print(f"Added {target.name}. Run: python -m advisor.cli index   (or Admin → Knowledge → Rebuild only)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="advisor")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("crawl", help="Download the website and linked documents")
    p.add_argument("--force", action="store_true", help="ignore cached validators")
    p.set_defaults(func=cmd_crawl)
    p = sub.add_parser("ingest", help="Extract + chunk snapshots (preview, no embeddings)")
    p.set_defaults(func=cmd_ingest)
    p = sub.add_parser("index", help="Build a new embedding index bundle")
    p.add_argument("--model", default=None)
    p.set_defaults(func=cmd_index)
    p = sub.add_parser("refresh", help="Crawl the site and publish a fresh index (what the scheduler runs)")
    p.add_argument("--no-crawl", action="store_true")
    p.add_argument("--model", default=None)
    p.set_defaults(func=cmd_refresh)
    p = sub.add_parser("search", help="Debug retrieval for a query")
    p.add_argument("query")
    p.add_argument("-n", type=int, default=8)
    p.add_argument("--rerank", action="store_true")
    p.set_defaults(func=cmd_search)
    p = sub.add_parser("eval-retrieval", help="Measure retrieval against the golden set")
    p.add_argument("-k", type=int, default=8)
    p.add_argument("--rerank", action="store_true")
    p.add_argument("--reranker", default=None)
    p.add_argument("--rerank-top", type=int, default=14)
    p.add_argument("--set", default="golden", help="golden | golden_holdout")
    p.set_defaults(func=cmd_eval_retrieval)
    p = sub.add_parser("ask", help="Ask the assistant a question from the terminal")
    p.add_argument("question")
    p.set_defaults(func=cmd_ask)
    p = sub.add_parser("eval-answers", help="Run the golden questions end-to-end")
    p.add_argument("--only", default="")
    p.add_argument("--set", default="golden")
    p.add_argument("--out", default="var/advisor/answer_eval.json")
    p.set_defaults(func=cmd_eval_answers)
    p = sub.add_parser("add-document", help="Add a department document that is not on the website")
    p.add_argument("path")
    p.add_argument("--title", default=None)
    p.add_argument("--note", default=None)
    p.add_argument("--effective", default=None, help='e.g. "Fall 2026 onwards"')
    p.set_defaults(func=cmd_add_document)
    p = sub.add_parser("create-admin", help="Create or reset an administrator account")
    p.add_argument("username")
    p.add_argument("--password", default=None, help="omit to be prompted")
    p.set_defaults(func=cmd_create_admin)
    p = sub.add_parser("serve", help="Run the API server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
