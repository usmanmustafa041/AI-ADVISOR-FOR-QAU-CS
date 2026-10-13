"""Optional selective OCR into a NEW version; OCR evidence is blocked until human approval."""

import json
import sqlite3

from chatbot_v3.ingest import import_one
from chatbot_v3.settings import ROOT, settings
from chatbot_v3.store import Store


def main():
    archive = ROOT / "academic-data/crawl-archive"
    store = Store()
    with sqlite3.connect(f"file:{archive / 'catalogue.sqlite3'}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT v.* FROM resources r JOIN versions v USING(version_id) WHERE v.url='https://cs.qau.edu.pk/doc/scheme-2021.pdf'"
        ).fetchall()
    result = []
    for row in rows:
        try:
            result.append(
                import_one(
                    store,
                    archive / row["raw_path"],
                    row["url"],
                    row["first_seen_at"],
                    row["raw_sha256"],
                    official=True,
                    ocr=True,
                )
            )
        except Exception as e:
            result.append({"uri": row["url"], "error_type": type(e).__name__, "detail": str(e)})
    path = settings().data_dir / "evaluation/ocr.json"
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
