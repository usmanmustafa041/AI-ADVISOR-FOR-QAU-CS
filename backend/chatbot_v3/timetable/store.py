import hashlib
import io
import json
import re
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pdfplumber
from pdfminer.pdftypes import PDFStream, resolve1
from pdfminer.psparser import PSLiteral

from chatbot_v3.settings import settings
from chatbot_v3.timetable.contracts import UploadMetadata

MAX_BYTES = 20 * 1024 * 1024


def now():
    return datetime.now(UTC).isoformat()


def dump(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def scope_key(metadata):
    return dump(
        [metadata[k] for k in ("department", "campus", "academic_term", "kind")]
        + [sorted(metadata["programmes"])]
    )


def inspect_pdf(data):
    if len(data) > MAX_BYTES or not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]:
        raise ValueError("Upload must be a complete PDF, at most 20 MiB")
    # Inspect decoded dictionaries as well as raw bytes (object streams may be compressed).
    prohibited = {
        "JavaScript",
        "JS",
        "OpenAction",
        "AA",
        "Launch",
        "EmbeddedFiles",
        "XFA",
        "RichMedia",
        "SubmitForm",
        "GoToR",
    }

    seen = set()

    def inspect(value, depth=0):
        value = resolve1(value)
        if isinstance(value, PSLiteral) and value.name in prohibited:
            raise ValueError("Active PDF action is not accepted")
        if isinstance(value, PDFStream):
            value = value.attrs
        if isinstance(value, dict | list | tuple):
            if id(value) in seen:
                return
            seen.add(id(value))
        if depth > 30:
            raise ValueError("PDF object nesting exceeds safe bounds")
        if isinstance(value, dict):
            if prohibited.intersection(value):
                raise ValueError("Active content or embedded files are not accepted")
            for key, item in value.items():
                if key not in {"Parent", "Pages", "Kids", "Resources", "Font"}:
                    inspect(item, depth + 1)
        elif isinstance(value, list | tuple):
            for item in value[:10000]:
                inspect(item, depth + 1)

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if pdf.doc.encryption:
            raise ValueError("Encrypted PDFs are not accepted")
        if not 1 <= len(pdf.pages) <= 40:
            raise ValueError("PDF must have 1–40 pages")
        if resolve1(pdf.doc.catalog.get("Pages", {})).get("Count") != len(pdf.pages):
            raise ValueError("PDF page-tree count is inconsistent; a page may be damaged")
        inspect(pdf.doc.catalog)
        for page in pdf.pages:
            if page.width > 3000 or page.height > 3000 or page.width * page.height > 4_000_000:
                raise ValueError("PDF page dimensions exceed preview limits")
            inspect(page.page_obj.attrs)
        return len(pdf.pages)


def check_pdf(data):
    import tempfile

    if len(data) > MAX_BYTES or not data.startswith(b"%PDF-"):
        raise ValueError("Upload must be a PDF, at most 20 MiB")
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp:
        temp.write(data)
        temp.flush()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "chatbot_v3.timetable.validate_pdf", temp.name],
                capture_output=True,
                timeout=20,
                check=True,
            )
            return int(result.stdout)
        except (subprocess.SubprocessError, ValueError):
            raise ValueError("PDF failed safety, page-count or processing limits") from None


class TimetableStore:
    def __init__(self, root=None):
        self.root = Path(root or settings().data_dir / "timetables")
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "timetable.sqlite3"
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.chmod(0o600)
        with self.connect() as c:
            c.executescript((Path(__file__).with_name("schema.sql")).read_text())
            c.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def connect(self, write=False):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def audit(self, c, actor, action, version, detail):
        c.execute(
            "INSERT INTO tt_audit(actor,action,version_id,timestamp,detail) VALUES(?,?,?,?,?)",
            (actor, action, version, now(), dump(detail)),
        )

    def upload(self, data, filename, metadata: UploadMetadata, actor):
        pages = check_pdf(data)
        meta = metadata.model_dump(mode="json")
        sha = hashlib.sha256(data).hexdigest()
        scope = scope_key(meta)
        with self.connect(write=True) as c:
            source = c.execute("SELECT * FROM tt_source_document WHERE sha256=?", (sha,)).fetchone()
            if source:
                duplicate = c.execute(
                    "SELECT id FROM tt_version WHERE source_id=? AND scope=?", (source["id"], scope)
                ).fetchone()
                if duplicate:
                    existing = self.version(duplicate["id"], c)
                    if existing["metadata"] != meta:
                        raise ValueError(
                            "Identical PDF/scope already exists with different metadata; inspect that version"
                        )
                    return duplicate["id"], False
                source_id = source["id"]
            else:
                source_id = str(uuid4())
                target = self.root / "originals" / (sha + ".pdf")
                target.parent.mkdir(exist_ok=True)
                # Exclusive creation: source bytes are never replaced by re-extraction or edits.
                if not target.exists():
                    with target.open("xb") as f:
                        f.write(data)
                    target.chmod(0o400)
                if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                    raise ValueError("Stored source checksum mismatch")
                c.execute(
                    "INSERT INTO tt_source_document VALUES(?,?,?,?,?,?)",
                    (source_id, sha, Path(filename).name[:180], str(target), pages, now()),
                )
            version = str(uuid4())
            c.execute(
                "INSERT INTO tt_version(id,source_id,scope,metadata,status,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                (version, source_id, scope, dump(meta), "queued", actor, now()),
            )
            self.audit(c, actor, "upload", version, {"sha256": sha, "metadata": meta})
        return version, True

    def versions(self):
        with self.connect() as c:
            return [
                dict(r) | {"metadata": json.loads(r["metadata"])}
                for r in c.execute(
                    "SELECT v.*,s.filename,s.pages,s.sha256,(SELECT count(*) FROM tt_meeting m WHERE m.version_id=v.id AND omitted=0) meeting_count,(SELECT count(*) FROM tt_issue i WHERE i.version_id=v.id AND resolution IS NULL) unresolved,(SELECT count(*) FROM tt_active a WHERE a.version_id=v.id) is_active FROM tt_version v JOIN tt_source_document s ON s.id=v.source_id ORDER BY v.created_at DESC"
                )
            ]

    def version(self, version, c=None):
        if c is None:
            with self.connect() as connection:
                return self.version(version, connection)
        row = c.execute(
            "SELECT v.*,s.filename,s.pages,s.path,s.sha256 FROM tt_version v JOIN tt_source_document s ON s.id=v.source_id WHERE v.id=?",
            (version,),
        ).fetchone()
        if row is None:
            raise KeyError(version)
        return dict(row) | {
            "metadata": json.loads(row["metadata"]),
            "extraction": json.loads(row["extraction"]),
        }

    def parse(self, version, actor="parser"):
        with self.connect(write=True) as c:
            v = self.version(version, c)
            if v["status"] not in {"queued", "failed"}:
                return
            c.execute("UPDATE tt_version SET status='parsing' WHERE id=?", (version,))
        result_path = self.root / (version + ".extraction.json")
        try:
            subprocess.run(
                [sys.executable, "-m", "chatbot_v3.timetable.parser", v["path"], str(result_path)],
                check=True,
                timeout=105,
                capture_output=True,
            )
            result = json.loads(result_path.read_text())
            self.stage(version, result, actor)
        except Exception as error:
            with self.connect(write=True) as c:
                c.execute(
                    "UPDATE tt_version SET status='failed',extraction=? WHERE id=?",
                    (
                        dump(
                            {
                                "error": type(error).__name__,
                                "message": "Extraction failed; active versions were retained",
                            }
                        ),
                        version,
                    ),
                )
                self.audit(c, actor, "parse_failed", version, {"error": type(error).__name__})

    def stage(self, version, result, actor):
        with self.connect(write=True) as c:
            v = self.version(version, c)
            if v["status"] != "parsing":
                raise ValueError("Only an ingestion job can stage records")
            ids = []
            for o in result["offerings"]:
                oid = str(uuid4())
                ids.append(oid)
                c.execute(
                    "INSERT INTO tt_offering VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        oid,
                        version,
                        o["code"],
                        o["programme"],
                        o["semester"],
                        o["section"],
                        o["title"],
                        dump(o["aliases"]),
                        dump({k: o[k] for k in ("page", "bbox", "raw")}),
                    ),
                )
                faculty = o.get("faculty", "")
                for part in re.split(r"/|(?=TA )", faculty):
                    part = part.strip()
                    if part:
                        role = "TA" if part.startswith("TA ") else "faculty"
                        c.execute(
                            "INSERT OR IGNORE INTO tt_teacher_assignment VALUES(?,?,?)",
                            (oid, part.removeprefix("TA "), role),
                        )
            for m in result["meetings"]:
                mid = str(uuid4())
                c.execute(
                    "INSERT INTO tt_meeting(id,version_id,weekday,start_time,end_time,room,mode,class_kind,page,bbox,raw,confidence,time_source,provenance) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        mid,
                        version,
                        m["weekday"],
                        m["start_time"],
                        m["end_time"],
                        m["room"],
                        m["mode"],
                        m["class_kind"],
                        m["page"],
                        dump(m["bbox"]),
                        m["raw"],
                        m["confidence"],
                        m["time_source"],
                        dump(m["provenance"]),
                    ),
                )
                for link in m["links"]:
                    c.execute(
                        "INSERT INTO tt_meeting_course VALUES(?,?,?)",
                        (
                            mid,
                            link["code"],
                            ids[link["offering"]] if link["offering"] is not None else None,
                        ),
                    )
                for flag in sorted(set(m["flags"])):
                    self.issue(c, version, mid, flag, m["raw"])
            for issue in result["issues"]:
                self.issue(c, version, None, issue["kind"], issue["detail"])
            text_term = re.search(r"(Spring|Fall|Summer)\s+20\d{2}", result["title"])
            if text_term and text_term[0] != v["metadata"]["academic_term"]:
                self.issue(
                    c, version, None, "term_mismatch", "Printed term differs from upload metadata"
                )
            if not result["meetings"] or not result["offerings"]:
                self.issue(
                    c, version, None, "empty_extraction", "Missing schedule or course legend"
                )
            if result["pages"] != v["pages"]:
                self.issue(c, version, None, "coverage", "Page count differs from source")
            c.execute(
                "UPDATE tt_version SET status='review',revision=revision+1,extraction=? WHERE id=?",
                (
                    dump(
                        {k: val for k, val in result.items() if k not in {"meetings", "offerings"}}
                    ),
                    version,
                ),
            )
            self.validate(c, version)
            self.audit(
                c,
                actor,
                "parsed",
                version,
                {"meetings": len(result["meetings"]), "offerings": len(ids)},
            )

    def issue(self, c, version, meeting, kind, detail):
        if c.execute(
            "SELECT 1 FROM tt_issue WHERE version_id=? AND meeting_id IS ? AND kind=? AND detail=?",
            (version, meeting, kind, detail),
        ).fetchone():
            return
        c.execute(
            "INSERT INTO tt_issue(id,version_id,meeting_id,kind,detail) VALUES(?,?,?,?,?)",
            (str(uuid4()), version, meeting, kind, detail),
        )

    def validate(self, c, version):
        rows = c.execute(
            "SELECT * FROM tt_meeting WHERE version_id=? AND omitted=0", (version,)
        ).fetchall()
        for m in rows:
            if m["end_time"] <= m["start_time"]:
                self.issue(c, version, m["id"], "invalid_time", "Meeting end must follow start")
            hours = (int(m["end_time"][:2]) * 60 + int(m["end_time"][3:])) - (
                int(m["start_time"][:2]) * 60 + int(m["start_time"][3:])
            )
            if hours < 30 or hours > 240:
                self.issue(c, version, m["id"], "abnormal_duration", f"Duration {hours} minutes")
            for n in rows:
                if (
                    m["id"] < n["id"]
                    and m["weekday"] == n["weekday"]
                    and m["mode"] == n["mode"] == "physical"
                    and m["room"] == n["room"]
                    and max(m["start_time"], n["start_time"]) < min(m["end_time"], n["end_time"])
                ):
                    self.issue(
                        c,
                        version,
                        m["id"],
                        "room_overlap",
                        f"Overlaps meeting {n['id']}; confirm co-scheduling or correct times",
                    )
        for row in c.execute(
            "SELECT o.id,o.code FROM tt_offering o WHERE o.version_id=? AND NOT EXISTS(SELECT 1 FROM tt_teacher_assignment t WHERE t.offering_id=o.id)",
            (version,),
        ):
            self.issue(c, version, None, "missing_faculty", row["code"] + ": no instructor printed")
        active = c.execute(
            "SELECT version_id FROM tt_active WHERE scope=(SELECT scope FROM tt_version WHERE id=?)",
            (version,),
        ).fetchone()
        if active:
            previous_offerings = c.execute(
                "SELECT count(*) FROM tt_offering WHERE version_id=?", (active[0],)
            ).fetchone()[0]
            new_offerings = c.execute(
                "SELECT count(*) FROM tt_offering WHERE version_id=?", (version,)
            ).fetchone()[0]
            if previous_offerings and new_offerings < previous_offerings * 0.8:
                self.issue(
                    c,
                    version,
                    None,
                    "legend_drop",
                    f"{new_offerings} legend rows versus {previous_offerings}; verify missing programme/semester coverage",
                )
            previous = c.execute(
                "SELECT count(*) FROM tt_meeting WHERE version_id=? AND omitted=0", (active[0],)
            ).fetchone()[0]
            if previous and len(rows) < previous * 0.7:
                self.issue(
                    c,
                    version,
                    None,
                    "suspicious_drop",
                    f"{len(rows)} meetings versus {previous} in active version",
                )

    def detail(self, version):
        with self.connect() as c:
            v = self.version(version, c)
            v.pop("path")
            v["meetings"] = [
                dict(r)
                | {
                    "bbox": json.loads(r["bbox"]),
                    "provenance": json.loads(r["provenance"]),
                    "courses": [
                        dict(x)
                        for x in c.execute(
                            "SELECT mc.code,mc.offering_id,o.title,o.programme,o.semester,o.section FROM tt_meeting_course mc LEFT JOIN tt_offering o ON o.id=mc.offering_id WHERE mc.meeting_id=?",
                            (r["id"],),
                        )
                    ],
                }
                for r in c.execute(
                    "SELECT * FROM tt_meeting WHERE version_id=? ORDER BY weekday,start_time,room",
                    (version,),
                )
            ]
            v["offerings"] = [
                dict(r)
                | {
                    "teachers": [
                        dict(t)
                        for t in c.execute(
                            "SELECT name,role FROM tt_teacher_assignment WHERE offering_id=?",
                            (r["id"],),
                        )
                    ]
                }
                for r in c.execute("SELECT * FROM tt_offering WHERE version_id=?", (version,))
            ]
            v["issues"] = [
                dict(r) for r in c.execute("SELECT * FROM tt_issue WHERE version_id=?", (version,))
            ]
            active = c.execute(
                "SELECT version_id FROM tt_active WHERE scope=?", (v["scope"],)
            ).fetchone()
            v["active_version"] = active[0] if active else None
            v["diff"] = self.diff(c, v["active_version"], version)
            v["audit"] = [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM tt_audit WHERE version_id=? ORDER BY id DESC", (version,)
                )
            ]
            return v

    def diff(self, c, before, after):
        def records(version):
            return (
                {
                    dump(dict(r))
                    for r in c.execute(
                        "SELECT m.weekday,m.start_time,m.end_time,m.room,m.mode,mc.code,o.programme,o.semester,o.section,group_concat(t.name) teachers FROM tt_meeting m JOIN tt_meeting_course mc ON mc.meeting_id=m.id LEFT JOIN tt_offering o ON o.id=mc.offering_id LEFT JOIN tt_teacher_assignment t ON t.offering_id=o.id WHERE m.version_id=? AND m.omitted=0 GROUP BY m.id,mc.code,o.id",
                        (version,),
                    )
                }
                if version
                else set()
            )

        old, new = records(before), records(after)
        return {
            "before": before,
            "after": after,
            "removed": [json.loads(x) for x in sorted(old - new)],
            "added": [json.loads(x) for x in sorted(new - old)],
            "unchanged": len(old & new),
        }

    def editable(self, c, version, revision):
        v = self.version(version, c)
        if v["status"] != "review" or v["revision"] != revision:
            raise ValueError(
                "Version is immutable after publication, busy, or changed; reload preview"
            )
        return v

    def edit(self, version, meeting, body, actor):
        allowed = {
            "start_time",
            "end_time",
            "room",
            "mode",
            "class_kind",
            "omitted",
            "offering_ids",
            "source_annotation",
        }
        if not body.changes or set(body.changes) - allowed:
            raise ValueError("Unknown editable meeting field")
        with self.connect(write=True) as c:
            self.editable(c, version, body.expected_revision)
            old = c.execute(
                "SELECT * FROM tt_meeting WHERE id=? AND version_id=?", (meeting, version)
            ).fetchone()
            if not old:
                raise KeyError(meeting)
            for key, val in body.changes.items():
                if key == "offering_ids":
                    if not isinstance(val, list) or not val:
                        raise ValueError("Select at least one source legend offering")
                    offers = [
                        c.execute(
                            "SELECT * FROM tt_offering WHERE id=? AND version_id=?", (oid, version)
                        ).fetchone()
                        for oid in val
                    ]
                    if any(o is None for o in offers):
                        raise ValueError("Offering must belong to this source version")
                    c.execute("DELETE FROM tt_meeting_course WHERE meeting_id=?", (meeting,))
                    for offer in offers:
                        c.execute(
                            "INSERT INTO tt_meeting_course VALUES(?,?,?)",
                            (meeting, offer["code"], offer["id"]),
                        )
                elif key == "source_annotation":
                    if (
                        not isinstance(val, dict)
                        or set(val) != {"page", "bbox", "raw"}
                        or not isinstance(val["page"], int)
                        or not 1 <= val["page"] <= self.version(version, c)["pages"]
                        or not isinstance(val["raw"], str)
                        or not 1 <= len(val["raw"]) <= 2000
                        or not isinstance(val["bbox"], list)
                        or len(val["bbox"]) != 4
                        or any(
                            not isinstance(x, int | float) or not 0 <= x <= 3000
                            for x in val["bbox"]
                        )
                    ):
                        raise ValueError(
                            "Provide a valid source page, bounding box and printed annotation"
                        )
                    provenance = json.loads(old["provenance"])
                    provenance.append(
                        val | {"actor": actor, "reason": body.reason, "corrected_at": now()}
                    )
                    c.execute(
                        "UPDATE tt_meeting SET provenance=? WHERE id=?", (dump(provenance), meeting)
                    )
                else:
                    if key in {"start_time", "end_time"} and not re.fullmatch(
                        r"(?:[01]\d|2[0-3]):[0-5]\d", str(val)
                    ):
                        raise ValueError("Use HH:MM in 24-hour time")
                    if key == "mode" and val not in {"physical", "online"}:
                        raise ValueError("Unknown mode")
                    if key == "class_kind" and val not in {"lab", "lecture", "unknown"}:
                        raise ValueError("Unknown class kind")
                    if key == "omitted" and not isinstance(val, bool):
                        raise ValueError("Omitted must be boolean")
                    if key == "room" and (not isinstance(val, str) or not 1 <= len(val) <= 80):
                        raise ValueError("Invalid room label")
                    c.execute(f"UPDATE tt_meeting SET {key}=? WHERE id=?", (val, meeting))
            c.execute("UPDATE tt_version SET revision=revision+1 WHERE id=?", (version,))
            self.validate(c, version)
            self.audit(
                c,
                actor,
                "correct_meeting",
                version,
                {"before": dict(old), "changes": body.changes, "reason": body.reason},
            )

    def edit_offering(self, version, offering, body, actor):
        allowed = {"title", "aliases", "teachers", "programme", "semester", "section"}
        if not body.changes or set(body.changes) - allowed:
            raise ValueError("Unknown offering field")
        with self.connect(write=True) as c:
            self.editable(c, version, body.expected_revision)
            old = c.execute(
                "SELECT * FROM tt_offering WHERE id=? AND version_id=?", (offering, version)
            ).fetchone()
            if old is None:
                raise KeyError(offering)
            for key, value in body.changes.items():
                if key == "teachers":
                    if not isinstance(value, list) or len(value) > 10:
                        raise ValueError("Provide a bounded teacher list")
                    for teacher in value:
                        if (
                            set(teacher) != {"name", "role"}
                            or teacher["role"] not in {"faculty", "TA"}
                            or not isinstance(teacher["name"], str)
                            or not 1 <= len(teacher["name"]) <= 150
                        ):
                            raise ValueError(
                                "Each teacher needs a printed name and faculty/TA role"
                            )
                    c.execute("DELETE FROM tt_teacher_assignment WHERE offering_id=?", (offering,))
                    for teacher in value:
                        c.execute(
                            "INSERT INTO tt_teacher_assignment VALUES(?,?,?)",
                            (offering, teacher["name"], teacher["role"]),
                        )
                else:
                    if key == "aliases":
                        if (
                            not isinstance(value, list)
                            or len(value) > 20
                            or any(not isinstance(v, str) or not 1 <= len(v) <= 150 for v in value)
                        ):
                            raise ValueError("Invalid aliases")
                        value = dump(value)
                    elif (
                        key == "semester"
                        and value is not None
                        and (not isinstance(value, int) or not 1 <= value <= 12)
                    ):
                        raise ValueError("Invalid semester")
                    elif key == "programme" and value not in {
                        "BSCS",
                        "MPhil/PhD",
                        "MPhil",
                        "PhD",
                        "MS-DS",
                        "MS-IST",
                        "deficiency",
                    }:
                        raise ValueError("Invalid programme")
                    elif key == "section" and value not in {
                        "regular",
                        "self support",
                        "combined",
                        "unknown",
                    }:
                        raise ValueError("Invalid section")
                    elif key == "title" and (
                        not isinstance(value, str) or not 1 <= len(value) <= 300
                    ):
                        raise ValueError("Invalid title")
                    c.execute(f"UPDATE tt_offering SET {key}=? WHERE id=?", (value, offering))
            c.execute("UPDATE tt_version SET revision=revision+1 WHERE id=?", (version,))
            self.validate(c, version)
            self.audit(
                c,
                actor,
                "correct_offering",
                version,
                {"before": dict(old), "changes": body.changes, "reason": body.reason},
            )

    def resolve(self, version, issue, body, actor):
        with self.connect(write=True) as c:
            self.editable(c, version, body.expected_revision)
            issue_row = c.execute(
                "SELECT * FROM tt_issue WHERE id=? AND version_id=?", (issue, version)
            ).fetchone()
            if not issue_row:
                raise KeyError(issue)
            if (
                issue_row["kind"] in {"ambiguous_ownership", "missing_legend"}
                and c.execute(
                    "SELECT 1 FROM tt_meeting_course WHERE meeting_id=? AND offering_id IS NULL",
                    (issue_row["meeting_id"],),
                ).fetchone()
                and not c.execute(
                    "SELECT omitted FROM tt_meeting WHERE id=?", (issue_row["meeting_id"],)
                ).fetchone()[0]
            ):
                raise ValueError("Link a verified offering or omit the unresolved meeting first")
            c.execute(
                "UPDATE tt_issue SET resolution=?,resolved_by=?,resolved_at=? WHERE id=?",
                (body.reason, actor, now(), issue),
            )
            c.execute("UPDATE tt_version SET revision=revision+1 WHERE id=?", (version,))
            self.audit(c, actor, "resolve_issue", version, {"issue": issue, "reason": body.reason})

    def publish(self, version, body, actor, rollback=False):
        with self.connect(write=True) as c:
            v = self.version(version, c)
            if not rollback:
                self.editable(c, version, body.expected_revision)
            elif (
                v["status"] not in {"published", "archived"}
                or v["revision"] != body.expected_revision
            ):
                raise ValueError("Rollback requires an unchanged previously published version")
            if not body.confirm_complete or set(body.reviewed_pages) != set(
                range(1, v["pages"] + 1)
            ):
                raise ValueError("Confirm the complete document and inspect every page")
            if c.execute(
                "SELECT 1 FROM tt_issue WHERE version_id=? AND resolution IS NULL", (version,)
            ).fetchone():
                raise ValueError("Resolve extraction issues before publication")
            if c.execute(
                "SELECT 1 FROM tt_meeting WHERE version_id=? AND omitted=0 AND end_time<=start_time",
                (version,),
            ).fetchone():
                raise ValueError("Invalid intervals remain")
            if not c.execute(
                "SELECT 1 FROM tt_meeting WHERE version_id=? AND omitted=0", (version,)
            ).fetchone():
                raise ValueError("An empty schedule cannot be published")
            if c.execute(
                "SELECT 1 FROM tt_meeting_course mc JOIN tt_meeting m ON m.id=mc.meeting_id WHERE m.version_id=? AND m.omitted=0 AND mc.offering_id IS NULL",
                (version,),
            ).fetchone():
                raise ValueError("Unresolved meeting ownership cannot be published")
            # Prevent overlapping ownership scopes from silently mixing programme versions.
            meta = v["metadata"]
            for offering in c.execute(
                "SELECT DISTINCT programme FROM tt_offering WHERE version_id=?", (version,)
            ):
                covered = {"MPhil", "PhD"} if offering[0] == "MPhil/PhD" else {offering[0]}
                if not covered <= set(meta["programmes"]):
                    raise ValueError(
                        "Upload coverage does not include every extracted programme; re-upload with correct ownership metadata"
                    )
            for row in c.execute(
                "SELECT a.scope,a.version_id,v.metadata FROM tt_active a JOIN tt_version v ON v.id=a.version_id WHERE a.scope<>?",
                (v["scope"],),
            ):
                other = json.loads(row["metadata"])
                if all(
                    meta[k] == other[k] for k in ("department", "campus", "academic_term", "kind")
                ) and set(meta["programmes"]) & set(other["programmes"]):
                    raise ValueError(
                        "Programme ownership overlaps an active scope; use identical coverage or a disjoint upload"
                    )
            previous = c.execute(
                "SELECT version_id FROM tt_active WHERE scope=?", (v["scope"],)
            ).fetchone()
            before = previous[0] if previous else None
            if before != body.expected_active_version:
                raise ValueError("Active timetable changed; reload the diff before publishing")
            diff = self.diff(c, before, version)
            c.execute(
                "INSERT INTO tt_active(scope,version_id) VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET version_id=excluded.version_id,generation=generation+1",
                (v["scope"], version),
            )
            if before and before != version:
                c.execute("UPDATE tt_version SET status='archived' WHERE id=?", (before,))
            c.execute("UPDATE tt_version SET status='published' WHERE id=?", (version,))
            self.audit(
                c,
                actor,
                "rollback" if rollback else "publish",
                version,
                {
                    "before": before,
                    "reason": body.reason,
                    "reviewed_pages": body.reviewed_pages,
                    "diff": diff,
                },
            )
        return {"active_version_id": version, "previous_version_id": before, "diff": diff}

    def recover_jobs(self):
        # Restart interrupted parsers; no active pointer is changed.
        with self.connect(write=True) as c:
            c.execute("UPDATE tt_version SET status='queued' WHERE status='parsing'")
            return [r[0] for r in c.execute("SELECT id FROM tt_version WHERE status='queued'")]
