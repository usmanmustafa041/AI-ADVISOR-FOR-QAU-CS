"""Compare lexical engines using temporary PostgreSQL tables in the isolated restore DB."""

import json
import statistics
import time

from app.core.config import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from chatbot_v3.settings import settings
from chatbot_v3.store import Store

QUERIES = [
    "attendance examination",
    "software engineering faculty",
    "hostel fees",
    "semester courses",
    "admission eligibility mathematics",
    "CSC-104",
    "scholarship financial assistance",
    "probation repeat CGPA",
]


def main():
    store = Store()
    chunks = store.chunks()
    engine = create_engine(
        make_url(get_settings().database_url).set(database="qau_chat_v3_restore_20261011")
    )
    pg_times = []
    sqlite_times = []
    with engine.begin() as conn:
        available = conn.execute(
            text("SELECT count(*) FROM pg_available_extensions WHERE name='vector'")
        ).scalar_one()
        conn.execute(
            text(
                "CREATE TEMPORARY TABLE v3_search_trial (id text PRIMARY KEY, content text, search tsvector GENERATED ALWAYS AS (to_tsvector('simple',content)) STORED) ON COMMIT DROP"
            )
        )
        conn.execute(
            text("INSERT INTO v3_search_trial (id,content) VALUES (:id,:content)"),
            [{"id": c["id"], "content": c["title"] + "\n" + c["content"]} for c in chunks],
        )
        conn.execute(text("CREATE INDEX ON v3_search_trial USING gin(search)"))
        for q in QUERIES:
            start = time.perf_counter()
            conn.execute(
                text(
                    "SELECT id FROM v3_search_trial WHERE search @@ plainto_tsquery('simple',:q) LIMIT 10"
                ),
                {"q": q},
            ).all()
            pg_times.append((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            with store.connect() as db:
                db.execute(
                    "SELECT chunk_id FROM evidence_fts WHERE evidence_fts MATCH ? LIMIT 10",
                    (" OR ".join('"' + w + '"' for w in q.split()),),
                ).fetchall()
            sqlite_times.append((time.perf_counter() - start) * 1000)
    report = {
        "chunks": len(chunks),
        "queries": len(QUERIES),
        "postgres_fts_median_ms": statistics.median(pg_times),
        "sqlite_fts_median_ms": statistics.median(sqlite_times),
        "pgvector_available_on_development_postgres": bool(available),
        "dense_matrix_bytes_for_e5": len(chunks) * 384 * 4,
        "preview_store": "isolated SQLite FTS5 plus matching dense numpy matrix",
        "limitation": "Small local latency comparison; query semantics differ (AND versus OR). This does not establish production scaling. PostgreSQL auth and operational tables are preserved.",
    }
    path = settings().data_dir / "evaluation/storage-benchmark.json"
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
