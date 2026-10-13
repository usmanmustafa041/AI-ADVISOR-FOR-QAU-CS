"""Archive public QAU sources; never modifies the live search corpus.

Run from any directory: backend/.venv/bin/python backend/scripts/crawl_sources.py
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import SourceArchive
from app.ingestion.crawler import CrawlConfig, PublicCrawler, public_url
from app.rag.corpus import PROJECT_ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, default=PROJECT_ROOT / "academic-data/crawl-archive"
    )
    parser.add_argument("--seed", action="append", default=[])
    parser.add_argument("--max-pages", type=int, default=300)
    parser.add_argument("--max-depth", type=int, default=10)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-seconds", type=float, default=900)
    parser.add_argument("--allow-host", action="append", default=[])
    parser.add_argument("--no-sitemaps", action="store_true")
    parser.add_argument(
        "--resume-pending",
        action="store_true",
        help="Resume unvisited links from previous bounded runs",
    )
    parser.add_argument(
        "--ocr", action="store_true", help="Requires optional PyMuPDF and installed Tesseract"
    )
    args = parser.parse_args()
    seeds = args.seed or ["https://cs.qau.edu.pk/", "https://qau.edu.pk/"]
    if not args.seed:
        with (PROJECT_ROOT / "academic-data/source-registry/source_inventory.csv").open() as stream:
            seeds += [
                r["source_url"] for r in csv.DictReader(stream) if public_url(r["source_url"])
            ]
    config = CrawlConfig(
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        delay_seconds=args.delay,
        max_seconds=args.max_seconds,
        ocr=args.ocr,
        discover_sitemaps=not args.no_sitemaps,
        resume_pending=args.resume_pending,
        allowed_hosts=tuple(sorted(set(CrawlConfig().allowed_hosts) | set(args.allow_host))),
    )
    archive = SourceArchive(args.archive)
    try:
        report = PublicCrawler(archive, config).crawl(list(dict.fromkeys(seeds)))
        print(json.dumps({k: v for k, v in report.items() if k != "observations"}, indent=2))
        usable = sum(
            report["counts"].get(k, 0) for k in ("new", "changed", "unchanged", "not_modified")
        )
        return 0 if usable else 1
    finally:
        archive.close()


if __name__ == "__main__":
    raise SystemExit(main())
