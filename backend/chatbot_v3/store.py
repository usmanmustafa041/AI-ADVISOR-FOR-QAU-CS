import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from chatbot_v3.settings import settings


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or settings().data_dir / "knowledge.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.chmod(0o600)
        with self.connect() as c:
            for migration in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                c.executescript(migration.read_text())
            c.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def chunks(self):
        from chatbot_v3.parsing import PARSER_VERSION

        with self.connect() as c:
            return [
                dict(r)
                for r in c.execute(
                    """SELECT e.*,d.id source_id,d.uri,d.origin,v.id source_version_id,
              v.checksum,v.raw_path,v.parser_version,v.captured_at,v.published_at,v.title,v.programme,v.topic,
              v.effective_term,v.cohort_start,v.applies_onwards,v.review_status,v.warnings
              FROM evidence_chunk e JOIN document_version v ON e.version_id=v.id JOIN document d ON v.document_id=d.id
              WHERE v.review_status<>'rejected' AND v.parser_version LIKE ?""",
                    (PARSER_VERSION + "%",),
                )
            ]

    def review(self, version, decision, reviewer, note):
        from datetime import UTC, datetime

        with self.connect() as c:
            if not c.execute("SELECT 1 FROM document_version WHERE id=?", (version,)).fetchone():
                raise KeyError(version)
            c.execute(
                "INSERT INTO source_review(version_id,decision,reviewer,reviewed_at,note) VALUES(?,?,?,?,?)",
                (version, decision, reviewer, datetime.now(UTC).isoformat(), note),
            )
            c.execute("UPDATE document_version SET review_status=? WHERE id=?", (decision, version))

    def review_queue(self):
        from chatbot_v3.parsing import PARSER_VERSION

        with self.connect() as c:
            return [
                dict(r)
                for r in c.execute(
                    """SELECT v.*,d.uri,d.origin,(SELECT count(*) FROM evidence_chunk e WHERE e.version_id=v.id) chunk_count
               FROM document_version v JOIN document d ON d.id=v.document_id WHERE
               (review_status='needs_review' OR (review_status='observed_official' AND topic IN ('admissions','programme')))
               AND parser_version LIKE ? ORDER BY topic,title""",
                    (PARSER_VERSION + "%",),
                )
            ]

    def history(self, conversation_id, owner):
        with self.connect() as c:
            row = c.execute(
                "SELECT * FROM conversation WHERE id=? AND owner=?", (conversation_id, owner)
            ).fetchone()
            if row is None:
                raise KeyError("Conversation not found")
            rows = c.execute(
                "SELECT * FROM (SELECT rowid,* FROM message WHERE conversation_id=? ORDER BY rowid DESC LIMIT 12) ORDER BY rowid",
                (conversation_id,),
            ).fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows], json.loads(
                row["state"]
            )

    def save_turn(self, owner, conversation_id, question, response, state):
        now = time.time()
        with self.connect() as c:
            if conversation_id:
                if not c.execute(
                    "SELECT 1 FROM conversation WHERE id=? AND owner=?", (conversation_id, owner)
                ).fetchone():
                    raise KeyError("Conversation not found")
            else:
                conversation_id = str(uuid4())
                c.execute(
                    "INSERT INTO conversation VALUES(?,?,?,?,?,?)",
                    (conversation_id, owner, now, now, json.dumps(state), question[:80]),
                )
            c.execute(
                "UPDATE conversation SET state=?,updated_at=? WHERE id=? AND owner=?",
                (json.dumps(state), now, conversation_id, owner),
            )
            user_id, answer_id = str(uuid4()), str(uuid4())
            for mid, role, content, meta in [
                (user_id, "user", question, {}),
                (answer_id, "assistant", response.answer, response.model_dump()),
            ]:
                c.execute(
                    "INSERT INTO message VALUES(?,?,?,?,?,?)",
                    (
                        mid,
                        conversation_id,
                        role,
                        content,
                        json.dumps(meta, ensure_ascii=False),
                        now,
                    ),
                )
            return conversation_id, answer_id

    def sessions(self, owner):
        with self.connect() as c:
            return [
                dict(r)
                for r in c.execute(
                    "SELECT id,title,created_at,updated_at FROM conversation WHERE owner=? ORDER BY updated_at DESC LIMIT 100",
                    (owner,),
                )
            ]

    def feedback(self, owner, message_id, helpful, reason):
        with self.connect() as c:
            if not c.execute(
                "SELECT 1 FROM message m JOIN conversation s ON s.id=m.conversation_id WHERE m.id=? AND s.owner=? AND m.role='assistant'",
                (message_id, owner),
            ).fetchone():
                raise KeyError("Message not found")
            c.execute(
                "INSERT INTO feedback VALUES(?,?,?,?,?,?) ON CONFLICT(message_id,owner) DO UPDATE SET helpful=excluded.helpful,reason=excluded.reason,created_at=excluded.created_at",
                (str(uuid4()), message_id, owner, int(helpful), reason, time.time()),
            )

    def prune(self):
        with self.connect() as c:
            c.execute(
                "DELETE FROM feedback WHERE message_id IN (SELECT m.id FROM message m JOIN conversation s ON s.id=m.conversation_id WHERE s.updated_at<?)",
                (time.time() - settings().history_days * 86400,),
            )
            c.execute(
                "DELETE FROM conversation WHERE updated_at<?",
                (time.time() - settings().history_days * 86400,),
            )
