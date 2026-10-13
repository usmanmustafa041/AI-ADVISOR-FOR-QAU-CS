"""Manual timetable edits, layered over the timetable that is read from the department's PDF.

The PDF-derived timetable (``timetable.json`` inside the index bundle) is never modified. Edits live in
the operational database as an *overlay* and are merged on every read:

* ``added``   – sessions typed in (or imported from CSV/Excel),
* ``edited``  – changes to a PDF session's day / time / room / section / teacher (keyed by a stable session id),
* ``removed`` – PDF sessions that are hidden (cancelled),
* ``courses`` – teacher / title changes of a course of a class,
* ``mode``    – ``pdf_plus_edits`` (default), ``manual_only`` (ignore the PDF) or ``pdf_only`` (edits paused).

Because overlay entries refer to PDF sessions by id, a re-crawl that changes a cell leaves the old edit
*orphaned* (reported in the admin screen, never applied blindly), while added sessions always survive.
Every save keeps a snapshot of the previous overlay, which is what "Undo" restores.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import re
import threading
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from advisor.db import Database
from advisor.rag.timetable_qa import DAY_ORDER, ROMAN_OUT, Timetable, _name_tokens, _split

MODES = ("pdf_plus_edits", "manual_only", "pdf_only")
SECTIONS = ("", "R", "S", "RS", "Rep")
PROGRAMS = ("BS", "MS-DS", "MS-IST", "MPhil/PhD", "Deficiency")
SECTION_WORDS = {
    "": "", "r": "R", "regular": "R", "morning": "R", "s": "S", "self": "S", "self support": "S", "self-support": "S",
    "selfsupport": "S", "evening": "S", "rs": "RS", "r+s": "RS", "both": "RS", "regular+self": "RS",
    "regular & self-support": "RS", "rep": "Rep", "repeater": "Rep", "repeaters": "Rep",
}
DAY_WORDS = {
    "mon": "MONDAY", "monday": "MONDAY", "tue": "TUESDAY", "tues": "TUESDAY", "tuesday": "TUESDAY",
    "wed": "WEDNESDAY", "wednesday": "WEDNESDAY", "thu": "THURSDAY", "thur": "THURSDAY", "thurs": "THURSDAY",
    "thursday": "THURSDAY", "fri": "FRIDAY", "friday": "FRIDAY", "sat": "SATURDAY", "saturday": "SATURDAY",
    "sun": "SUNDAY", "sunday": "SUNDAY",
}
MAX_IMPORT_ROWS = 3000
MAX_IMPORT_BYTES = 2 * 1024 * 1024


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_overlay() -> dict:
    return {"mode": "pdf_plus_edits", "meta": {"term": "", "effective": ""}, "added": {}, "edited": {},
            "removed": [], "courses": {}, "stamps": {}}


def fill_defaults(doc: dict) -> dict:
    out = default_overlay()
    out.update({k: v for k, v in doc.items() if k in out})
    out["meta"] = {**default_overlay()["meta"], **(doc.get("meta") or {})}
    return out


# ---------------------------------------------------------------------------------- validation
def sid_of(s: dict) -> str:
    """Stable id of a PDF session: the same cell gets the same id after every re-crawl."""
    raw = f"{s['day']}|{s['room']}|{s.get('slot') or s.get('time') or ''}|{s.get('text') or ''}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def parse_clock(text: str) -> tuple[int, int] | None:
    """'8:30', '08.30', '1:35 PM', '13:35' → (hour, minute) in 24-hour time."""
    t = str(text or "").strip().lower().replace(".", ":")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if not m:
        return None
    h, mi = int(m[1]), int(m[2] or 0)
    if m[3] == "pm" and h < 12:
        h += 12
    elif m[3] == "am" and h == 12:
        h = 0
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return h, mi


def fmt_time(start: tuple[int, int], end: tuple[int, int]) -> str:
    return f"{start[0]}:{start[1]:02d}-{end[0]}:{end[1]:02d}"


def split_time(rng: str) -> tuple[str, str]:
    sp = _split(rng or "")
    if not sp:
        return "", ""
    return f"{sp[0] // 60:02d}:{sp[0] % 60:02d}", f"{sp[1] // 60:02d}:{sp[1] % 60:02d}"


def canon_code(code: str) -> str:
    """'cs 413' / 'CS-413' / 'CSC413' → 'CS-413' (the printed form); '' when it is not a course code."""
    m = re.fullmatch(r"\s*([A-Za-z]{2,4})[\s-]?(\d{3})([A-Za-z]?)\s*", code or "")
    return f"{m[1].upper()}-{m[2]}{m[3].upper()}" if m else ""


def key_of(code: str, title: str) -> str:
    m = re.match(r"([A-Z]{2,4})-(\d{3})", canon_code(code))
    if m:
        return re.sub(r"^CS-", "CSC-", f"{m[1]}-{m[2]}")
    return "MANUAL-" + re.sub(r"[^a-z0-9]+", "-", (title or code).lower()).strip("-")[:40]


def clean_session(raw: dict, *, require_course: bool = True, partial: bool = False) -> tuple[dict, list[str]]:
    """Normalise one session typed in the admin screen or read from a file. Returns (clean fields, errors)."""
    errors: list[str] = []
    out: dict = {}

    def has(name: str) -> bool:
        return (not partial) or (name in raw and raw[name] is not None)

    if has("day"):
        d = DAY_WORDS.get(str(raw.get("day", "")).strip().lower())
        if d:
            out["day"] = d
        else:
            errors.append("Day must be Monday–Sunday.")
    if has("start") or has("end"):
        a, b = parse_clock(raw.get("start", "")), parse_clock(raw.get("end", ""))
        if not a or not b:
            errors.append("Start and end time must look like 8:30 and 10:00 (or 1:35 PM).")
        elif (a[0] * 60 + a[1]) >= (b[0] * 60 + b[1]):
            errors.append("The end time must be after the start time.")
        elif a[0] < 6 or b[0] > 23 or (b[0] == 23 and b[1] > 0):
            errors.append("Times must be between 6:00 and 23:00.")
        else:
            out["time"] = fmt_time(a, b)
    if has("room"):
        room = re.sub(r"\s+", " ", str(raw.get("room", ""))).strip()
        if not room or len(room) > 40:
            errors.append("Room is required (up to 40 characters).")
        else:
            out["room"] = room
    if has("section"):
        sec = SECTION_WORDS.get(re.sub(r"\s+", " ", str(raw.get("section") or "").strip().lower()))
        if sec is None:
            errors.append("Section must be Regular (R), Self-support (S), both (RS), Repeaters (Rep) or blank.")
        else:
            out["section"] = sec
    if not partial:
        program = str(raw.get("program") or "BS").strip()
        match = next((p for p in PROGRAMS if p.lower() == program.lower()), None)
        if not match:
            errors.append(f"Program must be one of {', '.join(PROGRAMS)}.")
        else:
            out["program"] = match
            sem = raw.get("semester")
            sem = None if sem in (None, "") else sem
            try:
                sem = None if sem is None else int(str(sem).strip().rstrip(".").lower().replace("th", "").replace("st", "").replace("nd", "").replace("rd", ""))
            except ValueError:
                sem = ROMAN_TO_INT.get(str(raw.get("semester")).strip().lower())
                if sem is None:
                    errors.append("Semester must be a number from 1 to 12 (or I–VIII).")
            if match == "BS" and sem is None and not any("Semester" in e for e in errors):
                errors.append("Semester is required for BS classes.")
            if sem is not None and not (1 <= sem <= 12):
                errors.append("Semester must be between 1 and 12.")
            out["semester"] = sem
        code_raw = str(raw.get("code") or "").strip()
        code = canon_code(code_raw)
        if code_raw and not code:
            errors.append("Course code must look like CS-413 or CSC-413.")
        title = re.sub(r"\s+", " ", str(raw.get("title") or "")).strip()
        if len(title) > 120:
            errors.append("Course title is longer than 120 characters.")
        if require_course and not code and not title:
            errors.append("Enter the course code or the course title.")
        out["code"], out["title"] = code, title[:120]
    teacher = re.sub(r"\s+", " ", str(raw.get("teacher") or "")).strip()
    if partial and "teacher" not in raw:
        pass
    elif len(teacher) > 80:
        errors.append("Teacher name is longer than 80 characters.")
    else:
        out["teacher"] = teacher
    if not partial or "note" in raw:
        note = re.sub(r"\s+", " ", str(raw.get("note") or "")).strip()
        out["note"] = note[:200]
    return out, errors


ROMAN_TO_INT = {v.lower(): k for k, v in ROMAN_OUT.items()}


# ---------------------------------------------------------------------------------- merge
def _class_group(program: str, semester: int | None, sec: str) -> str:
    sem = f"Semester {ROMAN_OUT.get(semester, semester)}" if semester else ""
    tag = {"R": "Regular", "S": "Self Support", "Rep": "Repeater"}.get(sec, "")
    return " ".join(x for x in (program if program != "MPhil/PhD" else "MPhil & PhD", sem, tag) if x)


def _ensure_course(data: dict, m: dict) -> None:
    secs = {"RS": ["R", "S"], "": ["R", "S"]}.get(m["section"], [m["section"]])
    program, sem = m["program"], m.get("semester")
    key = key_of(m["code"], m["title"])
    for sec in secs:
        cls = next((c for c in data["classes"] if c["program"] == program and sec in c["sections"]
                    and ((sem in c["semesters"]) if sem else not c["semesters"])), None)
        if cls is None:
            cls = {"group": _class_group(program, sem, sec), "program": program, "semesters": [sem] if sem else [],
                   "sections": [sec], "courses": [], "manual": True}
            data["classes"].append(cls)
        if not any(c.get("key") == key for c in cls["courses"]):
            cls["courses"].append({"label": m["code"] or m["title"], "code": m["code"], "key": key,
                                   "title": m["title"] or m["code"], "teacher": m.get("teacher", "")})


def build_effective(base: dict | None, ov: dict) -> dict:
    """The timetable the chatbot answers from: PDF data + overlay (according to the mode)."""
    ov = fill_defaults(ov)
    mode = ov["mode"] if ov["mode"] in MODES else "pdf_plus_edits"
    base = base or {}
    pdf_used = mode != "manual_only" and bool(base)
    data = copy.deepcopy(base) if pdf_used else {"term": "", "effective": "", "url": "", "classes": [], "sessions": []}
    data.setdefault("classes", [])
    data.setdefault("sessions", [])
    data["mode"] = mode
    data["pdf_term"] = base.get("term", "")
    edits_on = mode != "pdf_only"
    if edits_on:
        if ov["meta"].get("term"):
            data["term"] = ov["meta"]["term"]
        if ov["meta"].get("effective"):
            data["effective"] = ov["meta"]["effective"]
    data["term"] = data.get("term") or "Timetable"
    data["manual_only"] = mode == "manual_only"
    data["hidden"], data["orphans"] = [], []
    data["updated"] = ""
    if not edits_on:
        for s in data["sessions"]:
            s["id"], s["src"] = sid_of(s), "pdf"
        return data

    seen_ids = set()
    kept = []
    for s in data["sessions"]:
        s["id"] = sid_of(s)
        s["src"] = "pdf"
        seen_ids.add(s["id"])
        if s["id"] in ov["removed"]:
            data["hidden"].append(s)
            continue
        change = ov["edited"].get(s["id"])
        if change:
            s["orig"] = {k: s.get(k) for k in ("day", "time", "room", "section", "teacher") if k in change}
            s.update({k: v for k, v in change.items() if k in ("day", "time", "room", "section", "teacher", "note")})
            s["src"] = "edited"
            s["stamp"] = ov["stamps"].get(s["id"], "")
        kept.append(s)
    data["sessions"] = kept
    for sid_ in list(ov["removed"]) + list(ov["edited"]):
        if sid_ not in seen_ids and pdf_used:
            data["orphans"].append({"id": sid_, "kind": "removed" if sid_ in ov["removed"] else "edited"})

    for ckey, change in ov["courses"].items():
        group, _, label = ckey.partition("|")
        hit = False
        for cls in data["classes"]:
            if cls["group"] == group:
                for c in cls["courses"]:
                    if c["label"] == label:
                        c["pdf_teacher"] = c.get("teacher", "")
                        c.update({k: v for k, v in change.items() if k in ("teacher", "title")})
                        c["edited"] = True
                        hit = True
        if not hit and pdf_used:
            data["orphans"].append({"id": ckey, "kind": "course"})

    for aid, m in ov["added"].items():
        _ensure_course(data, m)
        code = m["code"]
        data["sessions"].append({
            "id": aid, "day": m["day"], "room": m["room"], "time": m["time"], "slot": "",
            "text": f"{code} {m['title']}".strip(), "code": code, "key": key_of(code, m["title"]),
            "section": m["section"], "teacher": m.get("teacher", ""), "title": m["title"], "note": m.get("note", ""),
            "src": "manual", "stamp": ov["stamps"].get(aid, ""), "program": m["program"], "semester": m.get("semester"),
        })
    data["updated"] = max(ov["stamps"].values(), default="")
    return data


# ---------------------------------------------------------------------------------- clash checks
def _minutes(s: dict) -> tuple[int, int] | None:
    return _split(s.get("time") or "")


def teacher_of(tt: Timetable, s: dict) -> str:
    if s.get("teacher"):
        return s["teacher"]
    rows = tt._rows(s)
    return rows[0][1].get("teacher", "") if rows else ""


def clashes(eff: dict, session: dict) -> list[str]:
    """Room / teacher conflicts of ``session`` with the rest of the effective timetable (warnings, not errors)."""
    tt = Timetable.from_json(eff)
    mine = _minutes(session)
    if not mine:
        return []
    my_teacher = set(_name_tokens(session.get("teacher") or teacher_of(tt, session)))
    out: list[str] = []
    for other in eff["sessions"]:
        if other.get("id") == session.get("id") or other["day"] != session["day"]:
            continue
        theirs = _minutes(other)
        if not theirs or not (mine[0] < theirs[1] and theirs[0] < mine[1]):
            continue
        same_course = other.get("key") and other.get("key") == session.get("key")
        label = f"{other.get('code') or other['text']} ({other['day'].title()} {other['time']}, room {other['room']})"
        if other["room"] == session["room"] and not same_course:
            out.append(f"Room {session['room']} is already used by {label}.")
        their_teacher = set(_name_tokens(other.get("teacher") or teacher_of(tt, other)))
        if my_teacher and my_teacher == their_teacher and not same_course:
            out.append(f"{session.get('teacher') or teacher_of(tt, session)} is also teaching {label}.")
    return list(dict.fromkeys(out))[:6]


# ---------------------------------------------------------------------------------- CSV / Excel
HEADERS = ["day", "start", "end", "room", "program", "semester", "section", "course_code", "course_title", "teacher", "note"]
HEADER_ALIASES = {
    "day": "day", "start": "start", "from": "start", "start time": "start", "end": "end", "to": "end", "end time": "end",
    "time": "time", "room": "room", "program": "program", "programme": "program", "semester": "semester", "sem": "semester",
    "class": "semester", "section": "section", "course_code": "code", "course code": "code", "code": "code",
    "course_title": "title", "course title": "title", "course": "title", "title": "title", "teacher": "teacher",
    "faculty": "teacher", "instructor": "teacher", "note": "note", "notes": "note",
}


def _rows_to_sessions(table: list[list[str]]) -> tuple[list[dict], list[dict]]:
    if not table:
        return [], [{"row": 1, "message": "The file is empty."}]
    header = [HEADER_ALIASES.get(re.sub(r"\s+", " ", str(h)).strip().lower(), "") for h in table[0]]
    if "day" not in header:
        return [], [{"row": 1, "message": "The first row must be a header containing at least: day, start, end, room, semester, course_code."}]
    good, bad = [], []
    for i, cells in enumerate(table[1:], start=2):
        if not any(str(c).strip() for c in cells):
            continue
        raw = {}
        for name, value in zip(header, cells):
            if name:
                raw[name] = re.sub(r"^'(?=[=+@-])", "", str(value).strip())
        if raw.get("time") and not (raw.get("start") and raw.get("end")):
            parts = re.split(r"\s*[-–—to]+\s*", raw["time"].lower().replace(" to ", "-"), maxsplit=1)
            if len(parts) == 2:
                raw["start"], raw["end"] = parts
        clean, errors = clean_session(raw)
        if errors:
            bad.append({"row": i, "message": " ".join(errors), "raw": raw})
        else:
            good.append({**clean, "row": i})
    return good, bad


def parse_csv(text: str) -> tuple[list[dict], list[dict]]:
    text = text.lstrip("﻿")
    sample = text[:2000]
    delim = ";" if sample.count(";") > sample.count(",") else "\t" if sample.count("\t") > sample.count(",") else ","
    table = [row for row in csv.reader(io.StringIO(text), delimiter=delim)]
    if len(table) > MAX_IMPORT_ROWS:
        return [], [{"row": 0, "message": f"Too many rows (limit {MAX_IMPORT_ROWS})."}]
    return _rows_to_sessions(table)


def _col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def parse_xlsx(raw: bytes) -> tuple[list[dict], list[dict]]:
    """First worksheet of an .xlsx file (standard library only). Time cells arrive as day fractions."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        if sum(i.file_size for i in zf.infolist()) > 30 * 1024 * 1024:
            return [], [{"row": 0, "message": "The Excel file is too large once unpacked."}]
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        names = sorted(n for n in zf.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        if not names:
            return [], [{"row": 0, "message": "No worksheet found in the Excel file."}]
        sheet = ET.fromstring(zf.read(names[0]))
    except (zipfile.BadZipFile, ET.ParseError, KeyError):
        return [], [{"row": 0, "message": "This is not a valid .xlsx file (try Save As → CSV)."}]
    table: list[list[str]] = []
    for row in sheet.iter(f"{{{ns['m']}}}row"):
        cells: dict[int, str] = {}
        for c in row.findall("m:c", ns):
            idx = _col_index(c.get("r", "A1"))
            kind, v = c.get("t"), c.find("m:v", ns)
            if kind == "s" and v is not None:
                val = shared[int(v.text)]
            elif kind == "inlineStr":
                val = "".join(t.text or "" for t in c.iter(f"{{{ns['m']}}}t"))
            else:
                val = v.text if v is not None else ""
                try:  # a time-formatted cell is a fraction of a day
                    f = float(val)
                    if 0 < f < 1:
                        mins = round(f * 24 * 60)
                        val = f"{mins // 60}:{mins % 60:02d}"
                    elif f == int(f):
                        val = str(int(f))
                except (TypeError, ValueError):
                    pass
            cells[idx] = val or ""
        table.append([cells.get(i, "") for i in range(max(cells, default=-1) + 1)])
        if len(table) > MAX_IMPORT_ROWS + 1:
            return [], [{"row": 0, "message": f"Too many rows (limit {MAX_IMPORT_ROWS})."}]
    return _rows_to_sessions(table)


def _safe_cell(value) -> str:
    """Excel/Sheets run a cell that starts with = + - @ as a formula; a leading apostrophe keeps it plain text."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "@") or (text[:1] == "-" and not re.match(r"-\d", text)) else text


def to_csv(sessions: list[dict]) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(HEADERS)
    for s in sessions:
        a, b = (s["start"], s["end"]) if s.get("start") else split_time(s.get("time", ""))
        w.writerow([_safe_cell(v) for v in (s["day"].title(), a, b, s["room"], s.get("program") or "BS", s.get("semester") or "",
                                            s.get("section", ""), canon_code(s.get("code", "")), s.get("title", ""),
                                            s.get("teacher", ""), s.get("note", ""))])
    return out.getvalue()


TEMPLATE_CSV = (
    ",".join(HEADERS) + "\n"
    "Monday,11:55,13:25,217,BS,8,S,CS-413,Introduction to Information Security,Dr. Muazzam Khattak,\n"
    "Wednesday,08:30,10:00,Lab 234,BS,5,R,CS-414,Artificial Intelligence,Dr. Ayyaz Hussain,make-up class\n"
)


# ---------------------------------------------------------------------------------- store
class TimetableError(ValueError):
    """A request the admin should fix (shown to them as-is)."""


class TimetableStore:
    def __init__(self, db: Database, kb):
        self.db = db
        self.kb = kb
        self._lock = threading.RLock()
        self._cache: tuple | None = None
        self.on_change = None  # called after every committed change (the service clears its answer cache here)

    # ---- persistence
    def _load(self) -> tuple[dict, int]:
        row = self.db.one("SELECT doc, version FROM timetable_state WHERE id=1")
        if not row:
            return default_overlay(), 0
        try:
            return fill_defaults(json.loads(row["doc"])), int(row["version"])
        except (ValueError, TypeError):
            return default_overlay(), int(row["version"])

    def overlay(self) -> dict:
        return self._load()[0]

    def _save(self, doc: dict, who: str, action: str, detail: str = "") -> int:
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                before, version = self._load()
                self.db.execute(
                    "INSERT INTO timetable_audit(actor, action, detail, before) VALUES(?,?,?,?)",
                    (who, action, detail[:300], json.dumps(before, ensure_ascii=False)),
                )
                self.db.execute(
                    "INSERT INTO timetable_state(id, doc, version, updated_at, updated_by) VALUES(1,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET doc=excluded.doc, version=excluded.version, "
                    "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                    (json.dumps(doc, ensure_ascii=False), version + 1, now(), who),
                )
                self.db.execute("DELETE FROM timetable_audit WHERE id NOT IN (SELECT id FROM timetable_audit ORDER BY id DESC LIMIT 200)")
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise
            self._cache = None
            self._changed()
            return version + 1

    def _changed(self) -> None:
        if self.on_change:
            try:
                self.on_change()
            except Exception:  # a cache problem must never undo a saved change
                pass

    # ---- reads
    def base(self) -> dict | None:
        tt = getattr(self.kb.bundle, "timetable", None) if self.kb.bundle else None
        return tt.data if tt is not None else None

    def effective(self) -> dict:
        ov, version = self._load()
        return build_effective(self.base(), ov)

    def current(self) -> Timetable | None:
        """The timetable the chatbot uses right now (cached until the PDF build or an edit changes)."""
        ov, version = self._load()
        build = getattr(self.kb.bundle, "build_id", None) if self.kb.bundle else None
        key = (build, version)
        if self._cache and self._cache[0] == key:
            return self._cache[1]
        eff = build_effective(self.base(), ov)
        tt = Timetable.from_json(eff) if (eff["sessions"] or eff["classes"]) else None
        self._cache = (key, tt)
        return tt

    def pdf_ignored(self) -> bool:
        """True in 'Manual only' mode: the PDF's timetable text must not leak into free-text answers either."""
        return self._load()[0]["mode"] == "manual_only"

    def history(self, limit: int = 15) -> list[dict]:
        rows = self.db.all("SELECT id, at, actor, action, detail, undone FROM timetable_audit ORDER BY id DESC LIMIT ?", (limit,))
        return [{"id": r["id"], "at": r["at"], "by": r["actor"], "action": r["action"], "detail": r["detail"], "undone": bool(r["undone"])} for r in rows]

    def can_undo(self) -> bool:
        return bool(self.db.scalar("SELECT COUNT(*) FROM timetable_audit WHERE undone=0", default=0))

    # ---- admin view
    def admin_view(self) -> dict:
        ov, version = self._load()
        eff = build_effective(self.base(), ov)
        tt = Timetable.from_json(eff) if (eff["sessions"] or eff["classes"]) else None

        def row(s: dict, hidden: bool = False) -> dict:
            rows = tt._rows(s) if tt else []
            start, end = split_time(s.get("time", ""))
            cls = " / ".join(dict.fromkeys(tt._class_label(c, "en") for c, _x in rows)) if tt and rows else ""
            title = s.get("title") or (rows[0][1]["title"] if rows else s.get("text", ""))
            code = s.get("code") or (rows[0][1].get("code", "") if rows else "")
            return {
                "id": s["id"], "src": "hidden" if hidden else s["src"], "day": s["day"], "start": start, "end": end,
                "room": s["room"], "section": s.get("section", ""), "code": code, "title": title,
                "teacher": teacher_of(tt, s) if tt else s.get("teacher", ""), "class": cls, "note": s.get("note", ""),
                "program": s.get("program") or (rows[0][0]["program"] if rows else ""),
                "semester": s.get("semester") if s.get("semester") is not None else (rows[0][0]["semesters"][0] if rows and rows[0][0]["semesters"] else None),
                "orig": s.get("orig"), "text": s.get("text", ""),
            }

        sessions = [row(s) for s in eff["sessions"]] + [row(s, True) for s in eff["hidden"]]
        sessions.sort(key=lambda r: (DAY_ORDER.index(r["day"]), r["start"], r["room"]))
        courses = [{"group": cls["group"], "label": c["label"], "code": c.get("code", ""), "title": c["title"],
                    "teacher": c.get("teacher", ""), "pdf_teacher": c.get("pdf_teacher"), "edited": bool(c.get("edited"))}
                   for cls in eff["classes"] for c in cls["courses"]]
        base = self.base()
        return {
            "version": version, "mode": ov["mode"], "term": eff["term"], "effective": eff.get("effective", ""),
            "meta": ov["meta"], "pdf": {"available": bool(base), "term": (base or {}).get("term", ""),
                                       "effective": (base or {}).get("effective", ""), "sessions": len((base or {}).get("sessions", []))},
            "counts": {"total": len(eff["sessions"]), "pdf": sum(1 for s in eff["sessions"] if s["src"] == "pdf"),
                       "edited": sum(1 for s in eff["sessions"] if s["src"] == "edited"),
                       "manual": sum(1 for s in eff["sessions"] if s["src"] == "manual"), "hidden": len(eff["hidden"])},
            "sessions": sessions, "courses": courses, "orphans": eff["orphans"], "updated": eff["updated"],
            "history": self.history(), "can_undo": self.can_undo(),
            "classes": sorted({(c["program"], c["semesters"][0] if c["semesters"] else 0) for c in eff["classes"]}),
        }

    # ---- writes (all go through _save, so each is audited and undoable)
    def _preview_clashes(self, doc: dict, session_id: str) -> list[str]:
        eff = build_effective(self.base(), doc)
        target = next((s for s in eff["sessions"] if s["id"] == session_id), None)
        return clashes(eff, target) if target else []

    def add_session(self, raw: dict, who: str, force: bool = False) -> dict:
        clean, errors = clean_session(raw)
        if errors:
            raise TimetableError(" ".join(errors))
        with self._lock:
            doc = self.overlay()
            sid = uuid.uuid4().hex[:10]
            doc["added"][sid] = clean
            doc["stamps"][sid] = now()
            warns = self._preview_clashes(doc, sid)
            if warns and not force:
                return {"saved": False, "warnings": warns}
            self._save(doc, who, "add session", f"{clean['day']} {clean['time']} {clean['code'] or clean['title']}")
            return {"saved": True, "id": sid, "warnings": warns}

    def update_session(self, sid: str, raw: dict, who: str, force: bool = False) -> dict:
        clean, errors = clean_session(raw, partial=True, require_course=False)
        if errors:
            raise TimetableError(" ".join(errors))
        with self._lock:
            doc = self.overlay()
            if sid in doc["added"]:
                merged = {**doc["added"][sid]}
                # manual sessions may change everything, including their course and class
                full, errs = clean_session({**_to_raw(merged), **{k: v for k, v in raw.items() if v is not None}})
                if errs:
                    raise TimetableError(" ".join(errs))
                doc["added"][sid] = full
            else:
                if sid not in {sid_of(s) for s in (self.base() or {}).get("sessions", [])}:
                    raise TimetableError("This session is not in the PDF timetable any more.")
                allowed = {k: v for k, v in clean.items() if k in ("day", "time", "room", "section", "teacher", "note")}
                if not allowed:
                    raise TimetableError("Nothing to change.")
                doc["edited"][sid] = {**doc["edited"].get(sid, {}), **allowed}
            doc["stamps"][sid] = now()
            warns = self._preview_clashes(doc, sid)
            if warns and not force:
                return {"saved": False, "warnings": warns}
            self._save(doc, who, "edit session", sid)
            return {"saved": True, "id": sid, "warnings": warns}

    def delete_session(self, sid: str, who: str) -> None:
        with self._lock:
            doc = self.overlay()
            if sid in doc["added"]:
                del doc["added"][sid]
                doc["stamps"].pop(sid, None)
                action = "delete manual session"
            elif sid in {sid_of(s) for s in (self.base() or {}).get("sessions", [])}:
                if sid not in doc["removed"]:
                    doc["removed"].append(sid)
                doc["stamps"][sid] = now()
                action = "hide PDF session"
            else:
                raise TimetableError("Session not found.")
            self._save(doc, who, action, sid)

    def restore_session(self, sid: str, who: str) -> None:
        with self._lock:
            doc = self.overlay()
            if sid not in doc["removed"] and sid not in doc["edited"]:
                raise TimetableError("This session has no edits to undo.")
            doc["removed"] = [x for x in doc["removed"] if x != sid]
            doc["edited"].pop(sid, None)
            doc["stamps"].pop(sid, None)
            self._save(doc, who, "restore PDF session", sid)

    def set_course(self, group: str, label: str, teacher: str | None, title: str | None, who: str) -> None:
        eff = self.effective()
        if not any(c["group"] == group and any(x["label"] == label for x in c["courses"]) for c in eff["classes"]):
            raise TimetableError("Course not found in that class.")
        change = {}
        if teacher is not None:
            if len(teacher.strip()) > 80:
                raise TimetableError("Teacher name is longer than 80 characters.")
            change["teacher"] = re.sub(r"\s+", " ", teacher).strip()
        if title is not None and title.strip():
            change["title"] = re.sub(r"\s+", " ", title).strip()[:120]
        if not change:
            raise TimetableError("Nothing to change.")
        with self._lock:
            doc = self.overlay()
            key = f"{group}|{label}"
            doc["courses"][key] = {**doc["courses"].get(key, {}), **change}
            doc["stamps"][key] = now()
            self._save(doc, who, "edit course", f"{group} / {label}")

    def set_settings(self, mode: str | None, term: str | None, effective: str | None, who: str) -> None:
        with self._lock:
            doc = self.overlay()
            if mode is not None:
                if mode not in MODES:
                    raise TimetableError("Mode must be pdf_plus_edits, manual_only or pdf_only.")
                if mode == "pdf_only" and not self.base():
                    raise TimetableError("There is no PDF timetable to use.")
                doc["mode"] = mode
            if term is not None:
                doc["meta"]["term"] = term.strip()[:60]
            if effective is not None:
                doc["meta"]["effective"] = effective.strip()[:80]
            self._save(doc, who, "settings", f"mode={doc['mode']}")

    def import_rows(self, rows: list[dict], who: str, replace: bool) -> dict:
        with self._lock:
            doc = self.overlay()
            if replace:
                for sid in list(doc["added"]):
                    doc["stamps"].pop(sid, None)
                doc["added"] = {}
            stamp = now()
            for r in rows:
                clean = {k: v for k, v in r.items() if k != "row"}
                sid = uuid.uuid4().hex[:10]
                doc["added"][sid] = clean
                doc["stamps"][sid] = stamp
            self._save(doc, who, "import", f"{len(rows)} rows ({'replace' if replace else 'add'})")
        return {"imported": len(rows)}

    def import_warnings(self, rows: list[dict], replace: bool) -> list[str]:
        """Clashes inside the imported rows themselves (shown in the preview)."""
        doc = self.overlay()
        if replace:
            doc["added"] = {}
        ids = []
        for r in rows:
            sid = uuid.uuid4().hex[:10]
            doc["added"][sid] = {k: v for k, v in r.items() if k != "row"}
            doc["stamps"][sid] = now()
            ids.append((sid, r.get("row")))
        eff = build_effective(self.base(), doc)
        by_id = {s["id"]: s for s in eff["sessions"]}
        out = []
        for sid, rownum in ids[:400]:
            if sid in by_id:
                for w in clashes(eff, by_id[sid])[:2]:
                    out.append(f"Row {rownum}: {w}")
        return out[:25]

    def export_csv(self) -> str:
        view = self.admin_view()
        return to_csv([s for s in view["sessions"] if s["src"] != "hidden"])

    def undo(self, who: str) -> dict:
        with self._lock:
            row = self.db.one("SELECT id, action, before FROM timetable_audit WHERE undone=0 ORDER BY id DESC LIMIT 1")
            if not row:
                raise TimetableError("Nothing to undo.")
            self.db.execute("BEGIN IMMEDIATE")
            try:
                _current, version = self._load()
                self.db.execute("UPDATE timetable_audit SET undone=1 WHERE id=?", (row["id"],))
                self.db.execute(
                    "INSERT INTO timetable_state(id, doc, version, updated_at, updated_by) VALUES(1,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET doc=excluded.doc, version=excluded.version, "
                    "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                    (row["before"], version + 1, now(), who),
                )
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise
            self._cache = None
            self._changed()
            return {"undone": row["action"]}

    def reset(self, who: str) -> None:
        """Back to the PDF: every edit, added session and setting is cleared (still undoable)."""
        with self._lock:
            self._save(default_overlay(), who, "reset to PDF")


def _to_raw(m: dict) -> dict:
    """A stored manual session as the raw form fields clean_session() expects."""
    a, b = split_time(m.get("time", ""))
    return {"day": m["day"], "start": a, "end": b, "room": m["room"], "program": m["program"], "semester": m.get("semester"),
            "section": m.get("section", ""), "code": m.get("code", ""), "title": m.get("title", ""),
            "teacher": m.get("teacher", ""), "note": m.get("note", "")}
