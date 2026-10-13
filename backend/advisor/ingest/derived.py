"""Aggregate documents derived from primary records.

Top-k retrieval over individual pages cannot answer "list all ..." or "who works on X"
questions reliably: the answer is spread over a dozen pages. These documents are built
mechanically from the already-extracted course and faculty records, so they inherit
exactly what the primary pages say (nothing is invented) and each one names its sources.
"""

from __future__ import annotations

import re
from collections import defaultdict

from advisor.ingest.model import Block, Document

SITE = "https://cs.qau.edu.pk"


def _programme_name(entry: str) -> str:
    return re.split(r"\s+(?:Semester\s+\d+|Electives Pool)", entry)[0].strip()


def _faculty_docs(docs: list[Document]) -> list[Document]:
    return [d for d in docs if d.kind == "faculty"]


def faculty_directory(docs: list[Document]) -> list[Document]:
    people = sorted(_faculty_docs(docs), key=lambda d: d.meta.get("faculty_name", ""))
    people = [p for p in people if p.meta.get("faculty_name")]
    if not people:
        return []
    order = ["Professor", "Associate Professor", "Assistant Professor", "Lecturer"]

    def rank(p):
        des = p.meta.get("designation", "")
        for i, o in enumerate(order):
            if des.startswith(o):
                return i
        return len(order)

    people.sort(key=lambda p: (rank(p), p.meta["faculty_name"]))
    names = "\n".join(
        f"- {p.meta['faculty_name']} — {p.meta.get('position') or p.meta.get('designation') or 'position not listed'}"
        for p in people
    )
    blocks = [
        Block(
            heading="Faculty directory › All faculty members",
            text=(
                f"Faculty of the Department of Computer Sciences, QAU ({len(people)} faculty profiles "
                f"on the department website):\n{names}"
            ),
            atomic=True,
        )
    ]
    # Contact + interests table, a few people per block so each stays focused.
    for i in range(0, len(people), 5):
        group = people[i : i + 5]
        rows = []
        for p in group:
            m = p.meta
            rows.append(
                f"{m['faculty_name']} ({m.get('position') or m.get('designation') or 'n/a'}) — "
                f"office: {m.get('room') or 'not listed'}; email: "
                f"{m.get('email') or 'not listed'}; phone: {m.get('phone') or 'not listed'}; "
                f"research interests: {', '.join(m.get('interests') or []) or 'not listed'}"
            )
        blocks.append(
            Block(
                heading=f"Faculty directory › Contacts and interests ({i + 1}-{i + len(group)})",
                text="Faculty contact details and research interests:\n"
                + "\n".join(f"- {r}" for r in rows),
                atomic=True,
            )
        )
    return [
        Document(
            url=f"{SITE}/faculty",
            title="Faculty directory",
            kind="directory",
            blocks=blocks,
            meta={"variant": "faculty-directory"},
            priority=9,
        )
    ]


def research_interest_directory(docs: list[Document]) -> list[Document]:
    by_interest: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for d in _faculty_docs(docs):
        for interest in d.meta.get("interests", []):
            by_interest[interest.strip()].append((d.meta["faculty_name"], d.url))
    if not by_interest:
        return []
    blocks = []
    for interest, people in sorted(by_interest.items(), key=lambda kv: kv[0].lower()):
        names = "; ".join(sorted({n for n, _ in people}))
        blocks.append(
            Block(
                heading=f"Research interest › {interest}",
                text=(
                    f"Faculty with the declared research interest \"{interest}\": {names}. "
                    f"(Based on the 'Research Interests' lists on faculty profile pages.)"
                ),
                atomic=True,
            )
        )
    return [
        Document(
            url=f"{SITE}/faculty",
            title="Research interests of faculty",
            kind="directory",
            blocks=blocks,
            meta={"variant": "research-interests"},
            priority=9,
        )
    ]


def course_catalogues(docs: list[Document]) -> list[Document]:
    courses = [d for d in docs if d.kind == "course"]
    by_prog: dict[str, list[Document]] = defaultdict(list)
    for c in courses:
        progs = {_programme_name(p) for p in c.meta.get("programmes", [])} or {"Programme not listed"}
        for p in progs:
            by_prog[p].append(c)
    out: list[Document] = []
    blocks_all: list[Block] = []
    for prog, items in sorted(by_prog.items()):
        items.sort(key=lambda c: c.meta["course_code"])
        lines = []
        for c in items:
            m = c.meta
            place = [
                re.sub(r"^.*?\)\s*", "", p)  # drop the repeated programme name
                for p in m.get("programmes", [])
                if _programme_name(p) == prog
            ]
            lines.append(
                f"- {m['course_code']}: {m['course_name']} "
                f"({m.get('credits_total', '?')} cr.hr)"
                + (f" — {place[0]}" if place else "")
            )
        for i in range(0, len(lines), 30):
            part = lines[i : i + 30]
            blocks_all.append(
                Block(
                    heading=f"Course catalogue › {prog} ({i + 1}-{i + len(part)} of {len(lines)})",
                    text=f"Courses listed for {prog} on the department course catalogue "
                    f"({len(lines)} total):\n" + "\n".join(part),
                    atomic=True,
                )
            )
    if blocks_all:
        out.append(
            Document(
                url=f"{SITE}/courses",
                title="Course catalogue by programme",
                kind="directory",
                blocks=blocks_all,
                meta={"variant": "course-catalogue"},
                priority=9,
            )
        )
    return out


def prerequisite_map(docs: list[Document]) -> list[Document]:
    courses = [d for d in docs if d.kind == "course"]
    required_by: dict[str, list[str]] = defaultdict(list)
    names = {c.meta["course_code"]: c.meta["course_name"] for c in courses}
    for c in courses:
        for pre in c.meta.get("prerequisites", []):
            m = re.match(r"([A-Z]{2,5}-\w+)", pre)
            if m:
                required_by[m.group(1)].append(f"{c.meta['course_code']} ({c.meta['course_name']})")
    blocks = []
    for code, dependents in sorted(required_by.items()):
        blocks.append(
            Block(
                heading=f"Prerequisite of › {code}",
                text=(
                    f"{code}{' (' + names[code] + ')' if code in names else ''} is listed as a "
                    f"prerequisite for: {'; '.join(sorted(set(dependents)))}."
                ),
                atomic=True,
            )
        )
    # One consolidated table for "what are all the prerequisites" questions.
    rows = []
    for c in sorted(courses, key=lambda c: c.meta["course_code"]):
        pres = c.meta.get("prerequisites")
        if pres:
            rows.append(f"- {c.meta['course_code']} {c.meta['course_name']}: requires " + "; ".join(pres))
    for i in range(0, len(rows), 25):
        blocks.append(
            Block(
                heading=f"Prerequisites list ({i + 1}-{min(i + 25, len(rows))} of {len(rows)})",
                text="Courses with prerequisites listed on their course pages:\n"
                + "\n".join(rows[i : i + 25]),
                atomic=True,
            )
        )
    if not blocks:
        return []
    return [
        Document(
            url=f"{SITE}/courses",
            title="Course prerequisites",
            kind="directory",
            blocks=blocks,
            meta={"variant": "prerequisites"},
            priority=9,
        )
    ]


def teaching_map(docs: list[Document]) -> list[Document]:
    """Who teaches which course according to the course pages (not the timetable)."""
    rows = []
    for c in sorted((d for d in docs if d.kind == "course"), key=lambda d: d.meta["course_code"]):
        teachers = c.meta.get("teachers") or []
        if teachers:
            rows.append(f"- {c.meta['course_code']} {c.meta['course_name']}: " + "; ".join(teachers))
    blocks = [
        Block(
            heading=f"Course instructors ({i + 1}-{min(i + 25, len(rows))} of {len(rows)})",
            text="Instructors listed on course pages:\n" + "\n".join(rows[i : i + 25]),
            atomic=True,
        )
        for i in range(0, len(rows), 25)
    ]
    if not blocks:
        return []
    return [
        Document(
            url=f"{SITE}/courses",
            title="Course instructors",
            kind="directory",
            blocks=blocks,
            meta={"variant": "instructors"},
            priority=8,
        )
    ]


def scheme_index(docs: list[Document]) -> list[Document]:
    """One place that says which schemes of study exist, where, and which applies to whom."""
    entries = []
    for d in docs:
        if d.kind == "scheme":
            entries.append((d.meta.get("term", ""), d.url, "PDF"))
    for d in docs:
        if d.kind == "programme" and d.meta.get("slug") == "bs-cs":
            for b in d.blocks:
                if "Scheme of Study — Fall 2026" in b.heading:
                    entries.append(("Fall 2026", d.url, "programme page (latest scheme)"))
                    break
    if not entries:
        return []
    entries = sorted(set(entries), reverse=True)
    lines = [f"- {t} onwards: {u} ({kind})" for t, u, kind in entries]
    text = (
        "BS Computer Science schemes of study published by the department (newest first). "
        "A student follows the scheme of the Fall semester in which they were admitted:\n"
        + "\n".join(lines)
    )
    return [
        Document(
            url=f"{SITE}/programme/bs-cs",
            title="BS Computer Science — available schemes of study",
            kind="directory",
            blocks=[Block(heading="Schemes of study overview", text=text, atomic=True)],
            meta={"variant": "scheme-index"},
            priority=9,
        )
    ]


def derive_documents(docs: list[Document]) -> list[Document]:
    out: list[Document] = []
    for fn in (
        faculty_directory,
        research_interest_directory,
        course_catalogues,
        prerequisite_map,
        teaching_map,
        scheme_index,
    ):
        out += fn(docs)
    return out
