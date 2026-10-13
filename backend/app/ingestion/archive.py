"""Content-addressed originals, immutable parsed versions and crawl observations.

SQLite is the ingestion catalogue, independent of the application's PostgreSQL.
Observation timestamps never stand in for publication or policy validity dates.
"""

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import UTC, datetime
from difflib import unified_diff
from pathlib import Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def atomic_write(path: Path, content: bytes, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            permissions = (
                mode
                if mode is not None
                else (path.stat().st_mode & 0o777 if path.exists() else 0o600)
            )
            os.fchmod(stream.fileno(), permissions)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def structured_diff(before: list[dict], after: list[dict]) -> list[dict]:
    """Compare uniquely identified courses; duplicate/ambiguous rows stay unmerged."""

    def courses(records):
        grouped = {}
        for record in records:
            if record["record_type"] == "course":
                key = (record["course_code"], record["semester"])
                grouped.setdefault(key, []).append(record)
        return {k: v[0] for k, v in grouped.items() if len(v) == 1}

    old, new = courses(before), courses(after)
    changes = []
    for key in sorted(old.keys() | new.keys(), key=str):
        fields = {}
        for field in (
            "course_name",
            "credit_hours",
            "lecture_hours",
            "lab_hours",
            "category",
            "prerequisites_raw",
        ):
            left, right = old.get(key, {}).get(field), new.get(key, {}).get(field)
            if left != right:
                fields[field] = {"before": left, "after": right}
        if fields:
            changes.append({"course_code": key[0], "semester": key[1], "fields": fields})
    return changes


class SourceArchive:
    def __init__(self, root: Path, *, thread_handoff: bool = False):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(
            self.root / "catalogue.sqlite3", timeout=30, check_same_thread=not thread_handoff
        )
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS versions (
                version_id TEXT PRIMARY KEY, url TEXT NOT NULL,
                raw_sha256 TEXT NOT NULL, text_sha256 TEXT NOT NULL,
                raw_path TEXT NOT NULL, parsed_path TEXT NOT NULL,
                first_seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS resources (
                url TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES versions,
                etag TEXT, last_modified TEXT, last_seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, url TEXT NOT NULL,
                observed_at TEXT NOT NULL, status TEXT NOT NULL,
                version_id TEXT REFERENCES versions, detail TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS version_url ON versions(url);
            CREATE TABLE IF NOT EXISTS review_events (
                id INTEGER PRIMARY KEY, version_id TEXT NOT NULL REFERENCES versions,
                decision TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL,
                note TEXT NOT NULL, acknowledged_warnings INTEGER NOT NULL DEFAULT 0
            );
        """)

    def close(self):
        self.db.close()

    def latest(self, url: str) -> dict | None:
        row = self.db.execute(
            "SELECT v.*, r.etag, r.last_modified, r.last_seen_at FROM resources r "
            "JOIN versions v USING(version_id) WHERE r.url=?",
            (url,),
        ).fetchone()
        return dict(row) if row else None

    def parsed(self, version: dict) -> dict:
        path = (self.root / version["parsed_path"]).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Archive path escapes its root")
        encoded = path.read_bytes()
        expected = hashlib.sha256(
            version["url"].encode() + version["raw_sha256"].encode() + encoded
        ).hexdigest()
        raw = (self.root / version["raw_path"]).resolve()
        if not raw.is_relative_to(self.root):
            raise ValueError("Archive path escapes its root")
        if (
            expected != version["version_id"]
            or hashlib.sha256(raw.read_bytes()).hexdigest() != version["raw_sha256"]
        ):
            raise ValueError("Archive integrity check failed")
        return json.loads(encoded)

    def observe(self, run_id: str, url: str, status: str, *, version_id=None, detail=None):
        with self.db:
            self.db.execute(
                "INSERT INTO observations(run_id,url,observed_at,status,version_id,detail) "
                "VALUES(?,?,?,?,?,?)",
                (run_id, url, utc_now(), status, version_id, json.dumps(detail or {})),
            )

    def not_modified(self, run_id: str, url: str):
        previous = self.latest(url)
        if not previous:
            raise ValueError("304 response without an archived version")
        with self.db:
            self.db.execute("UPDATE resources SET last_seen_at=? WHERE url=?", (utc_now(), url))
            self.db.execute(
                "INSERT INTO observations(run_id,url,observed_at,status,version_id,detail) "
                "VALUES(?,?,?,?,?,?)",
                (run_id, url, utc_now(), "not_modified", previous["version_id"], "{}"),
            )
        return previous

    def save(
        self,
        run_id: str,
        url: str,
        raw: bytes,
        parsed: dict,
        headers: dict,
        *,
        make_current: bool = True,
        previous_version: dict | None = None,
    ) -> dict:
        previous = previous_version or self.latest(url)
        raw_hash = hashlib.sha256(raw).hexdigest()
        text = "\n\n".join(p["content"] for p in parsed["pages"])
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        encoded = json.dumps(parsed, ensure_ascii=False, sort_keys=True).encode()
        # A parser/OCR update creates a separate extraction version of the same original.
        version_id = hashlib.sha256(url.encode() + raw_hash.encode() + encoded).hexdigest()
        extension = {
            "application/pdf": ".pdf",
            "text/plain": ".txt",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        }.get(parsed["mime_type"], ".html")
        raw_path = f"objects/{raw_hash[:2]}/{raw_hash}{extension}"
        parsed_path = f"parsed/{version_id}.json"
        for relative, data in ((raw_path, raw), (parsed_path, encoded)):
            destination = self.root / relative
            if not destination.exists():
                atomic_write(destination, data)
            elif destination.read_bytes() != data:
                raise ValueError("Archive object changed outside the ingestion pipeline")
        changed = previous is not None and previous["version_id"] != version_id
        change = None
        if changed:
            old = self.parsed(previous)
            old_text = "\n\n".join(p["content"] for p in old["pages"])
            change = {
                "url": url,
                "previous_version_id": previous["version_id"],
                "version_id": version_id,
                "observed_at": utc_now(),
                "text_changed": previous["text_sha256"] != text_hash,
                "metadata_changed": old["metadata"] != parsed["metadata"],
                "structured_changes": structured_diff(old["records"], parsed["records"]),
                "text_diff": list(
                    unified_diff(
                        old_text.splitlines(),
                        text.splitlines(),
                        fromfile=previous["version_id"],
                        tofile=version_id,
                        n=3,
                        lineterm="",
                    )
                )[:2000],
                "diff_truncated": False,
                "note": "Observed change; this does not establish supersession or policy validity.",
            }
            change["diff_truncated"] = len(change["text_diff"]) == 2000
            atomic_write(
                self.root / "changes" / f"{previous['version_id']}-{version_id}.json",
                json.dumps(change, ensure_ascii=False, indent=2).encode(),
            )
        timestamp = utc_now()
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO versions VALUES(?,?,?,?,?,?,?)",
                (version_id, url, raw_hash, text_hash, raw_path, parsed_path, timestamp),
            )
            if make_current:
                self.db.execute(
                    "INSERT INTO resources VALUES(?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET "
                    "version_id=excluded.version_id,etag=excluded.etag,"
                    "last_modified=excluded.last_modified,last_seen_at=excluded.last_seen_at",
                    (url, version_id, headers.get("etag"), headers.get("last-modified"), timestamp),
                )
            self.db.execute(
                "INSERT INTO observations(run_id,url,observed_at,status,version_id,detail) "
                "VALUES(?,?,?,?,?,?)",
                (
                    run_id,
                    url,
                    timestamp,
                    "changed" if changed else "unchanged" if previous else "new",
                    version_id,
                    json.dumps(
                        {"previous_version_id": previous["version_id"] if previous else None}
                    ),
                ),
            )
        return {
            "version_id": version_id,
            "new": previous is None,
            "changed": changed,
            "change": change,
        }

    def versions(self) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute("SELECT * FROM versions ORDER BY first_seen_at, version_id")
        ]

    def review(self, version_id, decision, reviewer, note, acknowledge_warnings=False):
        from app.rag.corpus import is_official_url

        row = self.db.execute("SELECT * FROM versions WHERE version_id=?", (version_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown source version")
        document = self.parsed(dict(row))
        if decision not in {"approved", "rejected", "pending"} or not reviewer or not note.strip():
            raise ValueError("A decision, reviewer and review note are required")
        if decision == "approved":
            if not is_official_url(row["url"]):
                raise ValueError("Unverified local documents cannot be approved as official rules")
            if not document["pages"]:
                raise ValueError("Empty extraction cannot be approved")
            if document["warnings"] and not acknowledge_warnings:
                raise ValueError("Extraction warnings must be explicitly acknowledged")
        with self.db:
            self.db.execute(
                "INSERT INTO review_events(version_id,decision,reviewer,reviewed_at,note,"
                "acknowledged_warnings) VALUES(?,?,?,?,?,?)",
                (version_id, decision, reviewer, utc_now(), note, bool(acknowledge_warnings)),
            )
        return self.review_status(version_id)

    def review_status(self, version_id):
        row = self.db.execute(
            "SELECT * FROM review_events WHERE version_id=? ORDER BY id DESC LIMIT 1",
            (version_id,),
        ).fetchone()
        return dict(row) if row else {"version_id": version_id, "decision": "pending"}

    def approved_documents(self):
        # Approval belongs to an immutable version; a new crawl never inherits approval.
        approved = [(self.review_status(row["version_id"]), row) for row in self.versions()]
        grouped = {}
        for review, row in sorted(approved, key=lambda pair: pair[0].get("id", 0)):
            if review["decision"] != "approved":
                continue
            document = self.parsed(row)
            grouped[(row["url"], document["metadata"]["effective_term"])] = {
                **row,
                "document": document,
            }
        return list(grouped.values())

    def corpus_documents(self) -> list[dict]:
        """Newest observation per URL and explicitly identified cohort.

        The archive retains all observations. Replacing a URL cannot delete a
        distinct historical cohort from search. Undated revisions use the last
        observed version without assigning an invented effective date.
        """
        grouped = {}
        rows = self.db.execute(
            "SELECT v.* FROM versions v ORDER BY "
            "(SELECT MAX(o.id) FROM observations o WHERE o.version_id=v.version_id), v.version_id"
        )
        for stored in rows:
            row = dict(stored)
            document = self.parsed(row)
            key = (row["url"], document["metadata"]["effective_term"])
            grouped[key] = {**row, "document": document}
        # A rollback to a previously seen version is still the current observation.
        for resource in self.db.execute("SELECT url,version_id FROM resources"):
            row = dict(
                self.db.execute(
                    "SELECT * FROM versions WHERE version_id=?", (resource["version_id"],)
                ).fetchone()
            )
            document = self.parsed(row)
            grouped[(row["url"], document["metadata"]["effective_term"])] = {
                **row,
                "document": document,
            }
        parser_versions = {}
        for version in grouped.values():
            key = (version["url"], version["raw_sha256"])
            parser_versions[key] = max(
                parser_versions.get(key, 0), version["document"]["parser_version"]
            )
        return [
            version
            for version in grouped.values()
            if version["document"]["parser_version"]
            == parser_versions[(version["url"], version["raw_sha256"])]
        ]

    def run_summary(self, run_id: str) -> dict:
        rows = [
            dict(row)
            for row in self.db.execute(
                "SELECT url,status,version_id,detail FROM observations WHERE run_id=? ORDER BY id",
                (run_id,),
            )
        ]
        counts = {}
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
            row["detail"] = json.loads(row["detail"])
        return {"run_id": run_id, "counts": counts, "observations": rows}

    def export_records(self, output: Path) -> int:
        records = []
        for version in self.corpus_documents():
            for record in version["document"]["records"]:
                records.append(
                    {
                        **record,
                        "source_url": version["url"],
                        "source_version_id": version["version_id"],
                        "source_sha256": version["raw_sha256"],
                        "applicability": version["document"]["metadata"]["effective_term"],
                        "verification_status": version["document"]["metadata"][
                            "verification_status"
                        ],
                    }
                )
        atomic_write(
            output, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode()
        )
        self.export_cohort_changes(self.root / "cohort_changes.json")
        self.export_conflicts(self.root / "source_conflicts.json")
        return len(records)

    def export_conflicts(self, output):
        grouped = {}
        for version in self.corpus_documents():
            metadata = version["document"]["metadata"]
            if not metadata["effective_term"]:
                continue
            for record in version["document"]["records"]:
                if record["record_type"] != "course":
                    continue
                key = (metadata["program"], metadata["effective_term"], record["course_code"])
                grouped.setdefault(key, []).append((version, record))
        conflicts = []
        for (program, term, code), rows in grouped.items():
            for field in ("credit_hours", "prerequisites_raw"):
                values = {str(r[field]) for _, r in rows if r.get(field) is not None}
                if len(values) > 1:
                    conflicts.append(
                        {
                            "program": program,
                            "term": term,
                            "course_code": code,
                            "field": field,
                            "requires_review": True,
                            "sources": [
                                {
                                    "url": v["url"],
                                    "version_id": v["version_id"],
                                    "value": r.get(field),
                                    "quote": r["source"]["quote"],
                                }
                                for v, r in rows
                            ],
                        }
                    )
        atomic_write(
            output,
            json.dumps(
                {
                    "conflicts": conflicts,
                    "note": "Source disagreement; no automatic winner or supersession.",
                },
                indent=2,
            ).encode(),
        )

    def export_cohort_changes(self, output: Path):
        """Flag curriculum changes across distinct URLs as well as URL revisions."""
        groups, warnings, changes = {}, [], []
        for version in self.corpus_documents():
            metadata = version["document"]["metadata"]
            term = metadata["effective_term"] or ""
            if metadata["category"] != "curriculum" or metadata["program"] == "ALL":
                continue
            year = re.search(r"\b20\d{2}\b", term)
            courses = [r for r in version["document"]["records"] if r["record_type"] == "course"]
            if not year or not courses:
                warnings.append(
                    {
                        "version_id": version["version_id"],
                        "reason": "Missing cohort or reliably extracted course records",
                    }
                )
                continue
            groups.setdefault(metadata["program"], {}).setdefault(term, []).append(version)
        for program, cohorts in groups.items():
            ordered = sorted(
                cohorts,
                key=lambda t: (
                    int(re.search(r"20\d{2}", t)[0]),
                    0 if "spring" in t.lower() else 1 if "summer" in t.lower() else 2,
                    t,
                ),
            )
            for before, after in zip(ordered, ordered[1:], strict=False):
                if len(cohorts[before]) != 1 or len(cohorts[after]) != 1:
                    warnings.append(
                        {
                            "program": program,
                            "terms": [before, after],
                            "reason": "Multiple sources for one cohort require review",
                        }
                    )
                    continue
                left, right = cohorts[before][0], cohorts[after][0]
                differences = structured_diff(
                    left["document"]["records"], right["document"]["records"]
                )
                if differences:
                    changes.append(
                        {
                            "program": program,
                            "before_term": before,
                            "after_term": after,
                            "before_version_id": left["version_id"],
                            "after_version_id": right["version_id"],
                            "courses": differences,
                            "requires_review": True,
                        }
                    )
        atomic_write(
            output,
            json.dumps(
                {
                    "changes": changes,
                    "warnings": warnings,
                    "note": (
                        "Extracted cohort differences do not establish policy "
                        "supersession or eligibility."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ).encode(),
        )
