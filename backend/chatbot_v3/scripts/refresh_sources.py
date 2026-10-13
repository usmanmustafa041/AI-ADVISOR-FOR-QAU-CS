"""Reparse preserved official originals into staging; never publish automatically."""

import argparse
import json
import time

from chatbot_v3.index import atomic_json
from chatbot_v3.ingest import import_one
from chatbot_v3.settings import settings
from chatbot_v3.store import Store


def refresh(store):
    with store.connect() as c:
        rows = c.execute("""SELECT d.uri,v.* FROM document d JOIN document_version v ON d.id=v.document_id
          WHERE d.origin IN ('official_archive','official_live')
          AND NOT EXISTS(SELECT 1 FROM document_version n WHERE n.document_id=v.document_id
            AND (n.captured_at>v.captured_at OR (n.captured_at=v.captured_at AND n.rowid>v.rowid)))
          ORDER BY d.uri""").fetchall()
    results = []
    from pathlib import Path

    for row in rows:
        try:
            result = import_one(
                store,
                Path(row["raw_path"]),
                row["uri"],
                row["captured_at"],
                row["checksum"],
                official=True,
                ocr=row["parser_version"].endswith("-ocr1"),
            )
            results.append({"status": "parsed", **result})
        except Exception as e:
            results.append({"uri": row["uri"], "status": "failed", "error": str(e)[:300]})
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="source-refresh")
    a = p.parse_args()
    began = time.perf_counter()
    results = refresh(Store())
    report = {
        "results": results,
        "parsed": sum(r["status"] == "parsed" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "seconds": round(time.perf_counter() - began, 2),
        "publication": "staging only; original files and active pointer unchanged",
    }
    atomic_json(settings().data_dir / "evaluation" / (a.output + ".json"), report)
    print(json.dumps({k: v for k, v in report.items() if k != "results"}))


if __name__ == "__main__":
    main()
