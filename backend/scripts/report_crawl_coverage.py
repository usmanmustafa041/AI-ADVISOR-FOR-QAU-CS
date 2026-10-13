"""Consolidate measured coverage across bounded runs; pending is never success."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import SourceArchive, atomic_write, utc_now
from app.rag.corpus import PROJECT_ROOT, is_official_url


def report_coverage(root):
    archive = SourceArchive(root)
    try:
        resources, runs, web_runs = {}, [], set()
        for path in sorted((root / "runs").glob("*.json"), key=lambda p: p.stat().st_mtime):
            run = json.loads(path.read_text())
            if "visited" not in run:
                continue
            runs.append({k: run.get(k) for k in ("run_id", "visited", "pending", "bounded")})
            web_runs.add(run["run_id"])
            for resource in run.get("resources", []):
                # Later pending rediscovery must not erase a previously observed result.
                if resource["url"] not in resources or resource["status"] != "pending":
                    resources[resource["url"]] = resource
        for row in archive.db.execute("SELECT * FROM observations ORDER BY id"):
            # Reprocessing an old local copy cannot erase a failed live crawl.
            # Workspace imports have their own provenance/coverage inventory.
            if row["run_id"] not in web_runs:
                continue
            if not is_official_url(row["url"]):
                continue
            if row["status"] not in {"robots_policy", "sitemap_processed"}:
                if row["status"] in {
                    "new",
                    "changed",
                    "unchanged",
                    "not_modified",
                    "error",
                    "http_error",
                    "robots_denied",
                    "robots_unavailable",
                }:
                    resources[row["url"]] = {
                        "url": row["url"],
                        "status": row["status"],
                        "observed_at": row["observed_at"],
                        "detail": json.loads(row["detail"]),
                    }
        counts = Counter(r["status"] for r in resources.values())
        return {
            "created_at": utc_now(),
            "discovered_in_scope": len(resources),
            "status_counts": dict(counts),
            "successfully_processed": sum(
                counts[s] for s in ("new", "changed", "unchanged", "not_modified")
            ),
            "blocked": counts["robots_denied"] + counts["robots_unavailable"],
            "failed": counts["error"] + counts["http_error"],
            "pending": counts["pending"],
            "runs": runs,
            "resources": list(resources.values()),
            "complete": False,
            "scope": "Measured public HTTP crawl runs only; workspace imports and offline "
            "reprocessing are reported separately.",
            "note": "Measured discovered resources only. Unlinked/unavailable material "
            "and bounded pending resources prevent full-site coverage claims.",
        }
    finally:
        archive.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, default=PROJECT_ROOT / "academic-data/crawl-archive"
    )
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "backend/evaluation/crawl_coverage.json"
    )
    args = parser.parse_args()
    report = report_coverage(args.archive.resolve())
    atomic_write(args.output, json.dumps(report, indent=2).encode())
    print(json.dumps({k: v for k, v in report.items() if k not in {"resources", "runs"}}, indent=2))


if __name__ == "__main__":
    main()
