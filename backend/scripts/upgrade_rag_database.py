"""Check schema readiness; --apply runs the additive RAG/portal compatibility migration.

Uses DATABASE_URL from backend/.env. Never drops tables or replaces records.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import get_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    engine = get_engine()
    if args.apply:
        directory = Path(__file__).resolve().parents[2] / "database"
        with engine.connect() as connection:
            # The checked-in migration includes its own BEGIN/COMMIT; execute
            # statements through SQLAlchemy's transaction rather than nesting it.
            for name in ("rag_upgrade.sql", "pipeline_feedback.sql", "pipeline_source_compat.sql"):
                script = re.sub(r"(?m)^--.*$", "", (directory / name).read_text())
                for statement in script.split(";"):
                    if statement.strip() and statement.strip() not in {"BEGIN", "COMMIT"}:
                        connection.execute(text(statement))
            connection.commit()
    with engine.connect() as connection:
        columns = {
            (r[0], r[1])
            for r in connection.execute(
                text("""
            SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name IN ('chat_sessions','chat_messages')
        """)
            )
        }
        required = {
            ("chat_sessions", "title"),
            ("chat_sessions", "updated_at"),
            ("chat_messages", "response_metadata"),
        }
        missing = sorted(required - columns)
        tables = list(
            connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            ).scalars()
        )
        print(
            json.dumps(
                {
                    "database": "reachable",
                    "rag_history_ready": not missing,
                    "answer_feedback_ready": "chat_feedback" in tables,
                    "missing_columns": missing,
                    "tables": tables,
                }
            )
        )
        if missing:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
