"""Content-addressed store for everything the crawler downloads.

Raw bytes are kept exactly as served (``objects/ab/abcdef….html``) so any parser
improvement can be re-run offline without touching the university's server again.
The catalogue records, per URL, the latest fetch outcome and validators used for
conditional requests.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    url            TEXT PRIMARY KEY,
    final_url      TEXT,
    status         INTEGER,
    content_type   TEXT,
    sha256         TEXT,
    ext            TEXT,
    bytes          INTEGER,
    etag           TEXT,
    last_modified  TEXT,
    fetched_at     TEXT NOT NULL,
    changed_at     TEXT,
    error          TEXT,
    discovered_from TEXT
);
CREATE INDEX IF NOT EXISTS pages_sha ON pages(sha256);
"""


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(slots=True)
class PageRecord:
    url: str
    final_url: str | None
    status: int | None
    content_type: str | None
    sha256: str | None
    ext: str | None
    bytes: int | None
    etag: str | None
    last_modified: str | None
    fetched_at: str
    changed_at: str | None
    error: str | None
    discovered_from: str | None

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300 and self.sha256 is not None


class SnapshotStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.root / "catalogue.sqlite3", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(_SCHEMA)
            self._db.commit()

    # -- objects ------------------------------------------------------------------
    def object_path(self, sha256: str, ext: str) -> Path:
        return self.objects / sha256[:2] / f"{sha256}{ext}"

    def put_bytes(self, data: bytes, ext: str) -> str:
        sha = hashlib.sha256(data).hexdigest()
        path = self.object_path(sha, ext)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        return sha

    def read_bytes(self, record: PageRecord) -> bytes:
        assert record.sha256 and record.ext is not None
        return self.object_path(record.sha256, record.ext).read_bytes()

    # -- catalogue ----------------------------------------------------------------
    def get(self, url: str) -> PageRecord | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM pages WHERE url=?", (url,)).fetchone()
        return PageRecord(**dict(row)) if row else None

    def upsert(self, rec: PageRecord) -> None:
        with self._lock:
            self._db.execute(
                """INSERT INTO pages(url, final_url, status, content_type, sha256, ext, bytes,
                       etag, last_modified, fetched_at, changed_at, error, discovered_from)
                   VALUES(:url,:final_url,:status,:content_type,:sha256,:ext,:bytes,:etag,
                       :last_modified,:fetched_at,:changed_at,:error,:discovered_from)
                   ON CONFLICT(url) DO UPDATE SET
                       final_url=excluded.final_url, status=excluded.status,
                       content_type=excluded.content_type, sha256=excluded.sha256,
                       ext=excluded.ext, bytes=excluded.bytes, etag=excluded.etag,
                       last_modified=excluded.last_modified, fetched_at=excluded.fetched_at,
                       changed_at=excluded.changed_at, error=excluded.error,
                       discovered_from=COALESCE(pages.discovered_from, excluded.discovered_from)""",
                {k: getattr(rec, k) for k in rec.__slots__},
            )
            self._db.commit()

    def all_ok(self) -> list[PageRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM pages WHERE status BETWEEN 200 AND 299 AND sha256 IS NOT NULL "
                "ORDER BY url"
            ).fetchall()
        return [PageRecord(**dict(r)) for r in rows]

    def failures(self) -> list[PageRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM pages WHERE NOT (status BETWEEN 200 AND 299) OR status IS NULL "
                "ORDER BY url"
            ).fetchall()
        return [PageRecord(**dict(r)) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._db.close()
