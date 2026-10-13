"""Weekly timetable PDF → searchable records.

The department's timetable is a merged-cell grid: rows are (day, room), columns are time
slots, and the header exists only on the first page. Reading it by *column index* gives
wrong answers (pages disagree on column counts), so cells are mapped to time slots by their
x-coordinates against the header geometry instead.

Three views are produced, because students ask three different questions:

* per **course** – "when/where is CS-211, who teaches it?"
* per **day** – "what is scheduled on Monday in room 201?"
* per **class** – "what does BS Semester III (Regular) study and who teaches each course?"
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

from advisor.ingest.model import Block, Document

log = logging.getLogger("advisor.timetable")

DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
TIME_RANGE = re.compile(r"\d{1,2}[:.]\d{2}\s*-\s*\d{1,2}[:.]\d{2}")
COURSE = re.compile(r"\b([A-Z]{2,4})-(\d{3}[A-Z]?)\b")
ROOMS = {
    "seminarroom": "Seminar room", "bslab": "BS Lab", "cslab": "CS Lab", "lab234": "Lab 234",
    "lab3": "Lab 3", "online": "online", "f8": "F8", "f6": "F6",
}
GROUP_HEADER = re.compile(
    r"^(BS Semester|MS-?DS|MS-?IST|MPhil|PhD|Deficiency|MS\b|BS\s)", re.I
)


def _join(lines: list[str]) -> str:
    """Join wrapped cell lines; numeric fragments ('13:3' + '0 - 15:30') are glued."""
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if out and (
            (out[-1].isdigit() or out[-1] in ":-(") and (ln[0].isdigit() or ln[0] in ":-)")
        ):
            out += ln
        elif out and ln == "/":
            continue
        else:
            out += (" " if out else "") + ln
    return re.sub(r"\s+", " ", out.replace(" / ", " ")).strip()


def cell_text(raw: str | None) -> str:
    return _join((raw or "").split("\n"))


def norm_day(text: str) -> str | None:
    squeezed = re.sub(r"[^A-Za-z]", "", text).upper()
    for d in DAYS:
        if squeezed.startswith(d[:5]) and (len(squeezed) >= 5):
            return d
    return None


def norm_room(text: str) -> str:
    text = re.sub(r"\bm#|\b(Roo|Room)\b|#", " ", text)  # header text merged into the first cell
    key = re.sub(r"[\s/]+", "", text).lower()
    if key in ROOMS:
        return ROOMS[key]
    # merged cells can carry two labels ("Lab 3" + "Lab 234"): keep both, visibly
    found = [ROOMS[k] for k in ROOMS if k in key and k not in ("f8", "f6")]
    if len(found) > 1:
        return " / ".join(dict.fromkeys(found))
    return re.sub(r"\s+", " ", cell_text(text)).strip()


def _canon(code: str) -> str:
    """CS-211 and CSC-211 name the same course; the PDF mixes both spellings."""
    return re.sub(r"^CS-", "CSC-", code)


def _alt(code: str) -> str:
    return re.sub(r"^CSC-", "CS-", code)


def section_of(label: str) -> str:
    """R = Regular (morning) programme, S = Self-support (evening) programme (department convention)."""
    t = label.strip()
    if re.search(r"R\s*\+\s*S\b", t):
        return "Regular (morning) + Self-support (evening)"
    if re.search(r"\bRep\b", t):
        return "Repeaters"
    if re.search(r"(?<![A-Za-z])S\b", t) and not re.search(r"\bR\b|[A-Z]-?\d{3}R\b", t):
        return "Self-support (evening)"
    if re.search(r"(?<![A-Za-z])R\b|\d{3}R\b", t):
        return "Regular (morning)"
    return ""


def norm_name(text: str) -> str:
    text = re.sub(r"\bDr[.,]\s*", "Dr. ", text)
    return re.sub(r"\s+", " ", text).strip(" ,")


def _slots_from_header(page) -> list[tuple[float, float, str]]:
    """Time-slot x-ranges and labels, read from the first page's header band."""
    table = max(page.find_tables(), key=lambda t: len(t.rows))
    day_row = None
    for row in table.rows:
        first = next((c for c in row.cells if c), None)
        text = page.crop(first).extract_text() if first else ""
        if text and norm_day(text) == "MONDAY":
            day_row = row
            break
    if day_row is None:
        return []
    header_bottom = day_row.bbox[1]
    slots = []
    for cell in day_row.cells:
        if not cell or cell[0] < 120:  # skip day / room columns
            continue
        band = page.crop((cell[0], table.bbox[1], cell[2], header_bottom)).extract_text() or ""
        label = re.sub(r"\s+", "", band.split("\n")[0] if "\n" not in band.strip() else band.replace("\n", ""))
        m = TIME_RANGE.search(label)
        if m:
            slots.append((cell[0], cell[2], m.group(0).replace(".", ":").replace(" ", "")))
    return slots


def _slot_for(x_center: float, slots) -> str | None:
    for x0, x1, label in slots:
        if x0 - 1 <= x_center <= x1 + 1:
            return label
    return None


def parse_grid(pdf) -> list[dict]:
    first = pdf.pages[0]
    slots = _slots_from_header(first)
    if not slots:
        return []
    sessions: list[dict] = []
    day = None
    for page in pdf.pages:
        for table in page.find_tables():
            for row in table.rows:
                cells = [c for c in row.cells if c]
                if not cells:
                    continue
                room_label = None
                label_text = {}
                for c in cells:
                    txt = cell_text(page.crop(c).extract_text())
                    label_text[c] = txt
                    if c[0] < 100 and c[2] <= 130 and c[0] > 90:  # room column
                        room_label = txt
                    elif c[0] < 100 and c[2] <= 100:  # day column
                        d = norm_day(txt)
                        if d:
                            day = d
                if not day or not room_label:
                    continue
                room = norm_room(room_label)
                for c in cells:
                    if c[0] < 126:
                        continue
                    txt = label_text[c]
                    if not txt or not COURSE.search(txt):
                        continue
                    slot = _slot_for((c[0] + c[2]) / 2, slots)
                    sessions.append({"day": day, "room": room, "slot": slot, "text": txt})
    return sessions


def parse_allocation(pdf) -> list[dict]:
    """(class group, course label, title, teacher) rows from the allocation tables."""
    rows: list[dict] = []
    group = "Unspecified class"
    for page in pdf.pages[1:]:
        for table in page.extract_tables():
            for raw in table:
                cells = [cell_text(c) for c in raw if c and cell_text(c)]
                if not cells:
                    continue
                if cells[0] == "Course Code":
                    continue
                if len(cells) == 1 and GROUP_HEADER.match(cells[0]):
                    group = cells[0]
                    continue
                if len(cells) == 1:
                    continue
                if len(cells) == 2 and GROUP_HEADER.match(cells[1]) and not COURSE.search(cells[0]):
                    group = cells[1]
                    continue
                label = cells[0]
                if not (COURSE.search(label) or re.match(r"^[A-Z]{2,4}-\d", label)):
                    # group header followed by data (e.g. "BS Semester IV" + code in other cell)
                    if GROUP_HEADER.match(cells[0]) and len(cells) > 1:
                        group = cells[0]
                        label, rest = cells[1], cells[2:]
                        cells = [label, *rest]
                    else:
                        continue
                title = cells[1] if len(cells) > 1 else ""
                teacher = norm_name(cells[2]) if len(cells) > 2 else ""
                rows.append({"group": group, "label": label, "title": title, "teacher": teacher})
    return rows


ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}


def parse_group(header: str) -> dict:
    """'BS Semester VIII Self Support' → program, semester(s), section(s)."""
    h = re.sub(r"\s+", " ", header).strip()
    if re.match(r"BS\b", h, re.I):
        program = "BS"
    elif re.match(r"MS-?DS", h, re.I):
        program = "MS-DS"
    elif re.match(r"MS-?IST", h, re.I):
        program = "MS-IST"
    elif re.match(r"MPhil|PhD", h, re.I):
        program = "MPhil/PhD"
    elif re.match(r"Deficiency", h, re.I):
        program = "Deficiency"
    else:
        program = h.split(" ")[0]
    sems = [ROMAN[r] for r in re.findall(r"\b(VIII|VII|VI|IV|IX|III|II|V|X|I)\b", h) if r in ROMAN]
    low = h.lower()
    has_r, has_s = "regular" in low, bool(re.search(r"self", low))
    repeater = "repeater" in low
    if repeater:
        sections = ["Rep"]
    elif has_r and has_s:
        sections = ["R", "S"]
    elif has_r:
        sections = ["R"]
    elif has_s:
        sections = ["S"]
    else:
        sections = ["R", "S"]
    return {"group": h, "program": program, "semesters": sems, "sections": sections}


def _code_key(label: str) -> str:
    """CS-413 / CSC-413 / MA-101R → a comparable key ('CSC-413', 'MA-101')."""
    m = re.search(r"\b([A-Z]{2,4})-(\d{3})", label)
    return _canon(f"{m.group(1)}-{m.group(2)}") if m else ""


def _section_key(text: str) -> str:
    t = text.strip()
    if re.search(r"R\s*\+\s*S\b", t):
        return "RS"
    if re.search(r"\bRep\b", t):
        return "Rep"
    sec = section_of(t)
    return {"Regular (morning)": "R", "Self-support (evening)": "S"}.get(sec, "")


def clean_room(room: str) -> str:
    """Merged cells sometimes carry fragments ("Lab Lab 3", "234 Lab 3", "room BS Lab"); the PDF's rooms are
    Lab 234 and Lab 3 (shared cell), so the fragments are restored to those names."""
    r = re.sub(r"\s+", " ", re.sub(r"(?i)^room\s+", "", room)).strip()
    if re.fullmatch(r"(?i)lab lab 3|234 lab 3|lab 234 lab 3", r):
        return "Lab 234 / Lab 3"
    return r


def build_structured(term: str, effective: str, url: str, sessions: list[dict], allocation: list[dict]) -> dict:
    """Plain-data timetable used for exact lookups (day / class / teacher / room / time)."""
    classes: dict[str, dict] = {}
    for r in allocation:
        g = classes.setdefault(r["group"], {**parse_group(r["group"]), "courses": []})
        code_m = COURSE.search(r["label"])
        g["courses"].append({
            "label": r["label"], "code": code_m.group(0) if code_m else "", "key": _code_key(r["label"]),
            "title": re.sub(r"\s*\([^)]*\)\s*$", "", r["title"]).strip() or r["title"],
            "teacher": r["teacher"],
        })
    out_sessions = []
    seen = set()
    for s in sessions:
        text = s["text"]
        override = TIME_RANGE.search(text)
        time_ = override.group(0).replace(".", ":").replace(" ", "") if override else (s["slot"] or "")
        code_m = COURSE.search(text)
        key = (s["day"], clean_room(s["room"]), time_, text)
        if key in seen:
            continue
        seen.add(key)
        out_sessions.append({
            "day": s["day"], "room": clean_room(s["room"]), "time": time_, "slot": s["slot"] or "", "text": text,
            "code": code_m.group(0) if code_m else "", "key": _code_key(text), "section": _section_key(text),
        })
    return {"term": term, "effective": effective, "url": url, "classes": list(classes.values()), "sessions": out_sessions}


def extract_timetable_pdf(path: Path, url: str, fetched_at: str) -> list[Document]:
    with pdfplumber.open(path) as pdf:
        head = (pdf.pages[0].extract_text() or "").split("\n")
        banner = " ".join(head[:2]).strip()
        term_m = re.search(r"(Fall|Spring|Summer)\s*20\d\d", banner, re.I)
        term = term_m.group(0).title() if term_m else "current term"
        eff_m = re.search(r"w\.?e\.?f\.?\s*(.+)$", banner, re.I)
        effective = eff_m.group(1).strip() if eff_m else ""
        sessions = parse_grid(pdf)
        allocation = parse_allocation(pdf)

    title = f"CS Department Timetable — {term}"
    blocks: list[Block] = []
    note = (
        "Source: weekly timetable PDF of the Department of Computer Sciences"
        + (f" (effective {effective})" if effective else "")
        + ". Section letters: R = Regular (morning) programme, S = Self-support (evening), "
        "Rep = repeaters. A time in brackets in a cell overrides the column's time slot."
    )

    # --- per class: who teaches what ------------------------------------------------
    by_group: dict[str, list[dict]] = defaultdict(list)
    for r in allocation:
        by_group[r["group"]].append(r)
    teachers_by_code: dict[str, list[str]] = defaultdict(list)
    titles_by_code: dict[str, str] = {}
    for r in allocation:
        for _p, num in [(m.group(1), m.group(2)) for m in COURSE.finditer(r["label"])][:1]:
            code = COURSE.search(r["label"]).group(0)
            if r["teacher"]:
                teachers_by_code[code].append(f"{r['teacher']} [{r['label']}]")
            titles_by_code.setdefault(code, r["title"])
    for group, items in by_group.items():
        lines = [
            f"- {r['label']}: {r['title'] or 'title not listed'}"
            + (f" [{section_of(r['label'])} section]" if section_of(r["label"]) else "")
            + (f" — taught by {r['teacher']}" if r["teacher"] else " — teacher not listed")
            for r in items
        ]
        blocks.append(
            Block(
                heading=f"{title} › Course allocation › {group}",
                text=f"{term} course allocation for {group}:\n" + "\n".join(lines) + f"\n{note}",
                atomic=True,
                meta={"variant": "allocation"},
            )
        )

    # --- per course: weekly sessions -------------------------------------------------
    by_course: dict[str, list[dict]] = defaultdict(list)
    for s in sessions:
        for m in COURSE.finditer(s["text"]):
            by_course[_canon(m.group(0))].append(s)
    teachers_by_canon: dict[str, list[str]] = defaultdict(list)
    titles_by_canon: dict[str, str] = {}
    for code, vals in teachers_by_code.items():
        teachers_by_canon[_canon(code)] += vals
    for code, t in titles_by_code.items():
        titles_by_canon.setdefault(_canon(code), t)
    for code, items in sorted(by_course.items()):
        seen = set()
        lines = []
        for s in sorted(items, key=lambda s: (DAYS.index(s["day"]), s["slot"] or "")):
            key = (s["day"], s["room"], s["slot"], s["text"])
            if key in seen:
                continue
            seen.add(key)
            sec = section_of(s["text"])
            lines.append(
                f"- {s['day'].title()}, room {s['room']}, "
                f"{s['slot'] or 'time slot not identified'}: \"{s['text']}\""
                + (f" [{sec} section]" if sec else "")
            )
        teach = teachers_by_canon.get(code)
        titles_by_code_local = titles_by_canon
        blocks.append(
            Block(
                heading=f"{title} › Weekly sessions › {code}",
                text=(
                    f"{term} timetable — {code} (also written {_alt(code)} in this PDF)"
                    + (f" ({titles_by_canon[code]})" if titles_by_canon.get(code) else "")
                    + ".\n"
                    + ("Teacher(s): " + "; ".join(dict.fromkeys(teach)) + "\n" if teach else "")
                    + "Weekly sessions:\n"
                    + "\n".join(lines)
                    + f"\n{note}"
                ),
                atomic=True,
                meta={"variant": "course-sessions"},
            )
        )

    # --- per day ---------------------------------------------------------------------
    by_day: dict[str, list[dict]] = defaultdict(list)
    for s in sessions:
        by_day[s["day"]].append(s)
    for d in DAYS:
        if d not in by_day:
            continue
        by_room: dict[str, list[dict]] = defaultdict(list)
        for s in by_day[d]:
            by_room[s["room"]].append(s)
        lines = []
        for room, items in by_room.items():
            cells = "; ".join(
                f"{s['slot'] or '?'}: {s['text']}" for s in sorted(items, key=lambda s: s["slot"] or "")
            )
            lines.append(f"- Room {room}: {cells}")
        text = f"{term} timetable — {d.title()} (all rooms):\n" + "\n".join(lines) + f"\n{note}"
        for i in range(0, len(lines), 6):
            part = lines[i : i + 6]
            blocks.append(
                Block(
                    heading=f"{title} › {d.title()} ({i // 6 + 1})",
                    text=f"{term} timetable — {d.title()}:\n" + "\n".join(part) + f"\n{note}",
                    atomic=True,
                    meta={"variant": "day-grid"},
                )
            )
        del text
    if not blocks:
        log.warning("timetable parser produced nothing for %s", url)
    return [
        Document(
            url=url,
            title=title,
            kind="timetable",
            blocks=blocks,
            source_type="pdf",
            fetched_at=fetched_at,
            meta={"term": term, "effective": effective, "variant": "timetable"},
            priority=9,
            payload={"timetable": build_structured(term, effective, url, sessions, allocation)},
        )
    ] if blocks else []
