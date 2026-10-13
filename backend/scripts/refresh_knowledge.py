"""Crawl, stage a corpus, evaluate and optionally publish with a rollback copy.

Default is staging only. Intended for a Linux/macOS systemd timer or cron job.
Corpus replacement is last; readers with mismatched dense files use BM25.
"""

import argparse
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import atomic_write, utc_now
from app.rag.corpus import PROJECT_ROOT


def publish_snapshot(candidate: Path, target: Path, rollback: Path):
    artifacts = [".vectors.npy", ".vectors.json", ".audit.json", None]
    for suffix in artifacts:
        previous = target.with_suffix(suffix) if suffix else target
        if previous.exists():
            backup = rollback.with_suffix(suffix) if suffix else rollback
            atomic_write(backup, previous.read_bytes())
    for suffix in artifacts:
        source = candidate.with_suffix(suffix) if suffix else candidate
        if source.exists():
            destination = target.with_suffix(suffix) if suffix else target
            mode = destination.stat().st_mode & 0o777 if destination.exists() else 0o644
            atomic_write(destination, source.read_bytes(), mode=mode)


def main():
    backend = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--snapshots", type=Path, default=backend / "data/rag/snapshots")
    parser.add_argument("--output", type=Path, default=backend / "data/rag/corpus.jsonl")
    parser.add_argument("--offline", action="store_true", help="Build from already archived files")
    parser.add_argument("--seed", action="append", default=[])
    parser.add_argument("--allow-host", action="append", default=[])
    parser.add_argument("--max-pages", type=int, default=300)
    parser.add_argument("--max-seconds", type=int, default=900)
    parser.add_argument("--resume-pending", action="store_true")
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument(
        "--ocr", action="store_true", help="Use installed optional OCR dependencies"
    )
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--approved-only", action="store_true")
    parser.add_argument("--questions", type=Path, default=backend / "evaluation/rag_questions.json")
    parser.add_argument("--min-recall", type=float, default=0.90)
    args = parser.parse_args()
    for field in ("root", "snapshots", "output", "questions"):
        setattr(args, field, getattr(args, field).resolve())
    if not 0 <= args.min_recall <= 1:
        parser.error("--min-recall must be between 0 and 1")
    archive = (args.archive or args.root / "academic-data/crawl-archive").resolve()
    args.snapshots.mkdir(parents=True, exist_ok=True)
    with (args.snapshots / ".refresh.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another refresh is active; no changes made", file=sys.stderr)
            return 3
        run_id = uuid4().hex
        directory = args.snapshots / run_id
        directory.mkdir()
        candidate = directory / "corpus.jsonl"
        report = {
            "run_id": run_id,
            "started_at": utc_now(),
            "published": False,
            "candidate": str(candidate),
            "status": "running",
        }

        def run(script, arguments, *, environment=None):
            subprocess.run(
                [sys.executable, str(backend / "scripts" / script), *arguments],
                cwd=args.root,
                env=environment,
                check=True,
                timeout=3600,
            )

        try:
            if not args.offline:
                arguments = [
                    "--archive",
                    str(archive),
                    "--max-pages",
                    str(args.max_pages),
                    "--max-seconds",
                    str(args.max_seconds),
                ]
                for seed in args.seed:
                    arguments += ["--seed", seed]
                for host in args.allow_host:
                    arguments += ["--allow-host", host]
                if args.ocr:
                    arguments.append("--ocr")
                if args.resume_pending:
                    arguments.append("--resume-pending")
                run("crawl_sources.py", arguments)
            elif args.ocr:
                run("reprocess_source_archive.py", ["--archive", str(archive), "--ocr"])
            local_arguments = ["--root", str(args.root), "--archive", str(archive)]
            if args.ocr:
                local_arguments.append("--ocr")
            run("import_workspace_documents.py", local_arguments)
            run(
                "report_crawl_coverage.py",
                ["--archive", str(archive), "--output", str(directory / "crawl_coverage.json")],
            )
            arguments = [
                "--root",
                str(args.root),
                "--crawl-archive",
                str(archive),
                "--output",
                str(candidate),
            ]
            if args.semantic:
                arguments.append("--semantic")
            if args.allow_download:
                arguments.append("--allow-download")
            if args.approved_only or args.publish:
                arguments.append("--approved-only")
            run("build_rag_corpus.py", arguments)
            environment = {
                **os.environ,
                "RAG_CORPUS_PATH": str(candidate),
                "LLM_PROVIDER": "unconfigured",
            }
            regression_path = directory / "retrieval_report.json"
            arguments = ["--questions", str(args.questions), "--output", str(regression_path)]
            if not args.semantic:
                arguments.append("--lexical-only")
            run("evaluate_rag.py", arguments, environment=environment)
            summary = json.loads(regression_path.read_text())["summary"]
            report["retrieval_regression"] = summary
            eligible = (
                summary["questions"] >= 25 and summary["evidence_recall_at_6"] >= args.min_recall
            )
            report["retrieval_gate_passed"] = eligible
            report["status"] = "staged" if eligible else "regression_failed"
            report["limitation"] = (
                "Development retrieval gate only; no answer accuracy or "
                "production approval is inferred."
            )
            if args.publish:
                if not eligible:
                    raise ValueError("Candidate failed retrieval gate; live corpus retained")
                from app.ingestion.archive import SourceArchive
                from app.rag.corpus import load_corpus

                review_archive = SourceArchive(archive)
                try:
                    approved = {v["version_id"] for v in review_archive.approved_documents()}
                    if any(c.source_version_id not in approved for c in load_corpus(candidate)):
                        raise ValueError("A source review changed; live corpus retained")
                finally:
                    review_archive.close()
                publish_snapshot(candidate, args.output, directory / "previous.jsonl")
                report.update(published=True, status="published", output=str(args.output))
            return 0 if eligible else 1
        except KeyboardInterrupt:
            report.update(status="interrupted")
            return 130
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            report.update(status="failed", error=str(exc))
            print(f"Refresh failed: {exc}", file=sys.stderr)
            return 1
        finally:
            report["finished_at"] = utc_now()
            atomic_write(directory / "refresh_report.json", json.dumps(report, indent=2).encode())
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
