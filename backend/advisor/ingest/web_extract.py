"""Turn crawled HTML pages into :class:`Document` objects.

Generic pages are converted to Markdown and split on headings. Pages with a known,
regular structure (course catalogue, faculty profiles, programme pages with tabbed
schemes, FAQ accordions) get dedicated extractors so each fact lands in a self-describing
record rather than a context-free fragment.
"""

from __future__ import annotations

import html as htmllib
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from advisor.ingest.htmlmd import html_to_markdown
from advisor.ingest.model import Block, Document

SITE_SUFFIX = re.compile(
    r"\s*[—–|-]\s*(CS QAU|Department of Computer Sciences.*|Quaid-i-Azam University.*|Faculty Profile)$",
    re.I,
)
COURSE_CODE = re.compile(r"\b([A-Z]{2,4})[- ]?(\d{3})\b")


def clean_title(title: str) -> str:
    title = htmllib.unescape(title or "").strip()
    for _ in range(2):
        title = SITE_SUFFIX.sub("", title).strip()
    return title


def fix_mojibake(text: str) -> str:
    """Repair UTF-8 text that some CMS fields stored as cp1252 (``â€“`` for an en dash)."""
    if not re.search(r"[âÃ][€\u0080-\u00bf]", text):
        return text
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Repair line by line so one bad character doesn't block the rest.
        out = []
        for ln in text.split("\n"):
            try:
                out.append(ln.encode("cp1252").decode("utf-8"))
            except (UnicodeEncodeError, UnicodeDecodeError):
                out.append(ln)
        return "\n".join(out)


def clean_text(text: str) -> str:
    """Undo double-escaped markup that leaks out of CMS fields (``&lt;br&gt;`` etc.)."""
    text = fix_mojibake(htmllib.unescape(text))
    text = re.sub(r"<\s*br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"</?(i|b|em|strong|span|p|div|u|font)[^>]*>", "", text, flags=re.I)
    text = text.replace(" ", " ")
    return re.sub(r"[ \t]{2,}", " ", text)


# ---------------------------------------------------------------------------- markdown → blocks
BOLD_HEADING = re.compile(r"^\*\*([^*]{3,70}?)\*\*$")
PROGRAMME_HEADING = re.compile(r"^(PhD|MPhil|MS|BS)\s*\(", re.I)
HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def markdown_to_blocks(
    md: str, title: str, label_lines: set[str] | None = None, bold_headings: bool = False
) -> list[Block]:
    """Split Markdown into blocks keyed by their heading path.

    ``label_lines`` lets an extractor promote standalone label lines (``Research
    Interests``) to headings when the source HTML doesn't use real heading tags.
    """
    blocks: list[Block] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []

    def flush():
        text = "\n".join(buf).strip()
        buf.clear()
        if not text:
            return
        path = " › ".join(h for _, h in stack) or title
        blocks.append(Block(heading=path, text=text))

    for line in md.split("\n"):
        m = HEADING.match(line)
        if not m and bold_headings:
            b = BOLD_HEADING.match(line.strip())
            if b and not b.group(1).startswith("Q:"):
                m = re.match(r"^(#{5})\s+(.*)$", f"##### {b.group(1).strip()}")
        label = None
        if not m and label_lines and line.strip() in label_lines:
            label = line.strip()
        if m or label:
            flush()
            level = len(m.group(1)) if m else 2
            text = re.sub(r"[*_`]+", "", (m.group(2) if m else label)).strip()
            # Programme sections are siblings of the FAQ blocks that precede them, even
            # though the site marks them up one level deeper.
            if m and PROGRAMME_HEADING.match(text):
                level = min(level, 3)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
        else:
            buf.append(line)
    flush()
    return blocks


# ---------------------------------------------------------------------------- URL classification
def classify(url: str) -> tuple[str, dict]:
    p = urlsplit(url)
    path = p.path.rstrip("/") or "/"
    host = (p.hostname or "").lower()
    if host != "cs.qau.edu.pk":
        return "external", {"host": host}
    if m := re.fullmatch(r"/course/([^/]+)", path):
        return "course", {"slug": m.group(1)}
    if m := re.fullmatch(r"/faculty/([^/]+)", path):
        return "faculty", {"slug": m.group(1)}
    if m := re.fullmatch(r"/programme/([^/]+)", path):
        return "programme", {"slug": m.group(1)}
    if m := re.fullmatch(r"/research-group/([^/]+)", path):
        return "research_group", {"slug": m.group(1)}
    if path.startswith("/explore"):
        return "topic", {}
    if path in ("/faculty", "/faculty.php"):
        return "faculty_listing", {}
    if path in ("/events", "/events.php"):
        return "events", {}
    if path in ("/admissions", "/admissions.php"):
        return "admissions", {}
    return "page", {}


# Legacy duplicates of the clean URLs (same content, different path).
CANONICAL_ALIASES = {
    "/faculty.php": "/faculty",
    "/admissions.php": "/admissions",
    "/research.php": "/research",
    "/courses.php": "/courses",
    "/academics.php": "/academics",
}


def canonical_url(url: str) -> str:
    p = urlsplit(url)
    if (p.hostname or "") == "cs.qau.edu.pk":
        path = CANONICAL_ALIASES.get(p.path.rstrip("/"), p.path)
        return f"https://cs.qau.edu.pk{path}" + (f"?{p.query}" if p.query else "")
    return url


# ---------------------------------------------------------------------------- course pages
LEVEL_LINE = re.compile(r"^(BS|MS|MPhil|PhD|MSc|MA)$")
DESIGNATION = re.compile(
    r"^(Assistant|Associate|Adjunct|Visiting|Senior)?\s*(Professor|Lecturer|Instructor|Researcher|"
    r"Scientist|Teaching Fellow)\b.*$|^(Assistant|Associate) Professor",
    re.I,
)


def _section(lines: list[str], start_pat: str, stop_pats: list[str]) -> list[str]:
    out, on = [], False
    for ln in lines:
        s = ln.strip()
        if not on and re.match(start_pat, s):
            on = True
            continue
        if on and any(re.match(p, s) for p in stop_pats):
            break
        if on:
            out.append(s)
    return [x for x in out if x]


def extract_course(url: str, title: str, md: str, meta: dict) -> Document | None:
    lines = [re.sub(r"^#{1,6}\s+", "", ln.rstrip()) if not ln.startswith("# ") else ln.rstrip()
             for ln in md.split("\n")]
    code = None
    code_pat = r"[A-Z]{2,5}-[0-9][0-9A-Za-z]{0,4}|[A-Z]{2,5}-[0-9A-Za-z]{1,5}"
    if m := re.match(rf"^({code_pat})\b", title):
        code = m.group(1)
    elif lines and re.fullmatch(code_pat, lines[0].strip()):
        code = lines[0].strip()
    name = ""
    for ln in lines:
        if ln.startswith("# "):
            name = ln[2:].strip()
            break
    if not (code and name):
        return None

    text = re.sub(r"\n?\s*Back to Course Catalog\s*$", "", "\n".join(lines))
    category = ""
    if m := re.search(r"^\((\w+)\)\s*([^\n]+)$", text, re.M):
        category = f"{m.group(2).strip()} ({m.group(1)})"
    theory = lab = total = None
    if m := re.search(r"Theory:\s*(\d+)", text):
        theory = int(m.group(1))
    if m := re.search(r"Lab:\s*(\d+)", text):
        lab = int(m.group(1))
    if m := re.search(r"Total:\s*(\d+)", text):
        total = int(m.group(1))
    if total is None and theory is not None:
        total = theory + (lab or 0)
    if theory is None and total is not None:
        theory = total - (lab or 0)

    def labelled(label: str, stops: list[str]) -> str:
        m = re.search(
            rf"\*\*{label}:?\*\*:?\s*(.*?)(?=\n\*\*(?:{'|'.join(stops)})|\nPrerequisites\n|\nIn Programmes\n|\nTaught By\n|\Z)",
            text,
            re.S,
        )
        return re.sub(r"\s*\n\s*", " ", m.group(1)).strip() if m else ""

    objectives = labelled("Objectives", ["Contents"])
    contents = labelled("Contents", ["Objectives"])
    description = ""
    if not objectives and not contents:
        # Unlabelled description paragraph between the credit lines and the next section.
        m = re.search(
            r"Total:[^\n]*\n+(.*?)(?=^Prerequisites$|^In Programmes$|^Taught By$|\Z)", text, re.S | re.M
        )
        if m:
            description = re.sub(r"\s*\n\s*", " ", m.group(1)).strip()

    prereq_lines = _section(lines, r"^Prerequisites$", [r"^In Programmes$", r"^Taught By$", r"^Back to"])
    prereqs = []
    for ln in prereq_lines:
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            prereqs.append(ln.replace(":", " —", 1) if re.match(r"^[A-Z]{2,4}-\d{3}:", ln) else ln)

    prog_lines = _section(lines, r"^In Programmes$", [r"^Taught By$", r"^Back to"])
    programmes: list[str] = []
    cur: list[str] = []
    for ln in prog_lines:
        if LEVEL_LINE.match(ln):
            if cur:
                programmes.append(" ".join(cur))
            cur = []
            continue
        cur.append(ln)
    if cur:
        programmes.append(" ".join(cur))
    programmes = [re.sub(r"\s+—\s*", " — ", re.sub(r"\s+", " ", x)).strip() for x in programmes]

    teacher_lines = _section(lines, r"^Taught By$", [r"^Back to"])
    teachers: list[str] = []
    needs_designation = False
    for t in teacher_lines:
        t = re.sub(r"\s+", " ", t).strip()
        if DESIGNATION.search(t) and teachers and needs_designation:
            teachers[-1] = f"{teachers[-1]} ({t})"  # name line followed by designation line
            needs_designation = False
        else:
            teachers.append(t)
            needs_designation = True

    head = f"Course {code}: {name}"
    facts = [head]
    if category:
        facts.append(f"Category: {category}")
    if total is not None:
        cr = f"Credit hours: {total} total"
        if theory is not None:
            cr += f" (theory {theory}, lab {lab or 0})"
        facts.append(cr)
    facts.append(
        "Prerequisites: " + "; ".join(prereqs) if prereqs else "Prerequisites: none listed on the course page"
    )
    if programmes:
        facts.append("Offered in: " + "; ".join(programmes))
    facts.append("Taught by: " + "; ".join(teachers) if teachers else "Taught by: not listed")
    body = "\n".join(facts)
    if objectives:
        body += f"\nObjectives: {objectives}"
    if contents:
        body += f"\nContents: {contents}"
    if description:
        body += f"\nDescription: {description}"

    doc_meta = {
        **meta,
        "course_code": code,
        "course_name": name,
        "credits_total": total,
        "credits_theory": theory,
        "credits_lab": lab or 0,
        "prerequisites": prereqs,
        "teachers": teachers,
        "programmes": programmes,
    }
    return Document(
        url=url,
        title=f"{code}: {name}",
        kind="course",
        blocks=[Block(heading=head, text=body, atomic=True)],
        meta=doc_meta,
        priority=8,
    )


# ---------------------------------------------------------------------------- faculty pages
FACULTY_LABELS = {
    "About", "Research Interests", "Education", "Scholarly Profiles", "Other Links",
    "Courses Taught", "Awards", "Projects", "Ongoing Research", "Supervised Theses", "Thesis Supervision",
    "Experience", "Biography", "Professional Experience", "Memberships",
}
PUB_SPLIT = re.compile(r"(?=^#{6} )", re.M)


def extract_faculty(url: str, title: str, md: str, meta: dict) -> list[Document]:
    name_m = re.search(r"^# (.+)$", md, re.M)
    name = clean_text(name_m.group(1)).strip() if name_m else clean_title(title)
    desig_m = re.search(r"^#### (.+)$", md, re.M)
    designation = desig_m.group(1).strip() if desig_m else ""
    email_m = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", md)
    phone_m = re.search(r"\+92[-\d\s()]{8,}", md)
    email = email_m.group(0) if email_m else ""
    phone = phone_m.group(0).strip() if phone_m else ""

    # Split publications off; they are numerous and need their own chunks.
    pub_idx = re.search(r"^Publications\s*\(\d+\)", md, re.M)
    main_md, pub_md = (md[: pub_idx.start()], md[pub_idx.start():]) if pub_idx else (md, "")

    # Header card: name / designation / contact.
    card = [f"Faculty member: {name}"]
    if designation:
        card.append(f"Designation: {designation}")
    card.append("Department: Computer Sciences, Quaid-i-Azam University, Islamabad")
    if email:
        card.append(f"Email: {email}")
    if phone:
        card.append(f"Phone: {phone}")

    # Strip the header (everything before the first label) from the labelled sections.
    first_label = re.search(
        r"^(" + "|".join(map(re.escape, FACULTY_LABELS)) + r")$", main_md, re.M
    )
    body_md = main_md[first_label.start():] if first_label else ""
    body_md = re.sub(r"^(Awards|Projects|Courses Taught|Education)\s*\(\d+\)$", r"\1", body_md, flags=re.M)
    body_md = re.sub(r"^#{5,6}\s+", "- ", body_md, flags=re.M)  # entries, not sections
    sections = markdown_to_blocks(clean_text(body_md), name, FACULTY_LABELS)

    blocks: list[Block] = []
    interests: list[str] = []
    courses: list[str] = []
    for b in sections:
        label = b.heading.split(" › ")[-1]
        text = re.sub(r"\n{2,}", "\n", b.text)
        if label == "Research Interests":
            interests = [ln.strip() for ln in text.split("\n") if ln.strip()]
            text = ", ".join(interests)
        elif label == "Courses Taught":
            courses = [
                re.sub(r"\s*\[(BS|MS|MPhil|PhD)\]\s*$", "", ln.lstrip("-# ").strip())
                for ln in text.split("\n")
                if ln.strip()
            ]
            text = "\n".join(f"- {c}" for c in courses)
        elif label in ("Scholarly Profiles", "Other Links"):
            text = "\n".join(f"- {ln}" for ln in text.split("\n") if ln.strip())
        blocks.append(
            Block(heading=f"{name} › {label}", text=f"{name} — {label}:\n{text}", atomic=label != "About")
        )
    if interests:
        card.append("Research interests: " + ", ".join(interests))
    if courses:
        card.append(f"Courses taught: {len(courses)} (see course list)")
    blocks.insert(0, Block(heading=f"{name} › Profile", text="\n".join(card), atomic=True))

    docs = [
        Document(
            url=url,
            title=f"{name} — Faculty profile",
            kind="faculty",
            blocks=blocks,
            meta={
                **meta,
                "faculty_name": name,
                "designation": designation,
                "email": email,
                "phone": phone,
                "interests": interests,
                "courses": courses,
            },
            priority=8,
        )
    ]

    # Publications: group into batches so each chunk stays focused.
    entries = [e.strip() for e in PUB_SPLIT.split(clean_text(pub_md)) if e.strip().startswith("######")]
    if entries:
        pubs: list[str] = []
        for e in entries:
            e = re.sub(r"^#{6}\s*", "", e)
            lines = [ln.strip() for ln in e.split("\n") if ln.strip() and not ln.startswith("DOI:")]
            pubs.append(" — ".join(lines))
        docs.append(
            Document(
                url=url,
                title=f"{name} — Publications",
                kind="publications",
                blocks=[
                    Block(
                        heading=f"{name} › Publications",
                        text=f"Publications of {name} ({len(pubs)} listed):\n"
                        + "\n".join(f"- {p}" for p in pubs),
                    )
                ],
                meta={**meta, "faculty_name": name, "variant": "publications"},
                priority=3,
            )
        )
    return docs


# ---------------------------------------------------------------------------- faculty listing
POSITION_WORD = re.compile(r"(Professor|Lecturer|Instructor|Chair|Director|Dean|Researcher)", re.I)


def parse_faculty_listing(md: str) -> dict[str, dict]:
    """Per-person records from the directory page.

    The listing carries facts profile pages omit: office room and the full position
    (for example "Professor, Chairperson").
    """
    lines = [ln.strip() for ln in clean_text(md).split("\n") if ln.strip()]
    entries: dict[str, dict] = {}
    i = 0
    while i < len(lines) - 2:
        if lines[i] == lines[i + 1] and POSITION_WORD.search(lines[i + 2]) and len(lines[i]) < 90:
            name = lines[i]
            rec = {"name": name, "position": lines[i + 2]}
            j = i + 3
            while j < len(lines) and not (
                j + 2 < len(lines) and lines[j] == lines[j + 1] and POSITION_WORD.search(lines[j + 2])
            ):
                ln = lines[j]
                if m := re.fullmatch(r"Room\s*([\w\- ]+)", ln):
                    rec["room"] = f"Room {m.group(1).strip()}"
                elif re.fullmatch(r"[\w.+-]+@[\w.-]+", ln):
                    rec["email"] = ln
                elif ln.startswith("+92"):
                    rec["phone"] = ln.split(" (")[0].strip()
                j += 1
            entries[name.lower()] = rec
            i = j
        else:
            i += 1
    return entries


# ---------------------------------------------------------------------------- programme pages
def label_scheme_panels(soup: BeautifulSoup) -> None:
    """Insert a visible heading naming each tabbed scheme-of-study panel."""
    labels: dict[str, str] = {}
    for btn in soup.find_all("button", onclick=True):
        if m := re.search(r"showScheme\('([^']+)'", btn["onclick"]):
            text = re.sub(r"\s+", " ", btn.get_text(" ")).strip()
            labels[m.group(1)] = text
    for panel in soup.find_all(class_="scheme-panel"):
        raw = labels.get(panel.get("id", ""), "")
        if not raw:
            continue
        latest = " (latest scheme)" if "Latest" in raw else ""
        term = raw.replace("Latest", "").strip()
        h = soup.new_tag("h3")
        h.string = f"Scheme of Study — {term} onwards{latest}"
        panel.insert(0, h)


def extract_programme(url: str, html: str, meta: dict) -> Document:
    soup = BeautifulSoup(html, "html.parser")
    label_scheme_panels(soup)
    title, md = html_to_markdown(str(soup), url)
    md = clean_text(md)
    title = clean_title(title)
    blocks = split_faq_blocks(markdown_to_blocks(md, title, bold_headings=True))
    return Document(url=url, title=title, kind="programme", blocks=blocks, meta=meta, priority=8)


# ---------------------------------------------------------------------------- generic pages
def split_faq_blocks(blocks: list[Block]) -> list[Block]:
    """FAQ entries are self-contained question/answer pairs: keep each one whole."""
    out: list[Block] = []
    for b in blocks:
        if "**Q:" not in b.text:
            out.append(b)
            continue
        parts = re.split(r"(?=^\*\*Q: )", b.text, flags=re.M)
        lead = parts[0].strip()
        if lead:
            out.append(Block(b.heading, lead))
        for part in parts[1:]:
            q = re.match(r"\*\*Q: (.*?)\*\*", part)
            out.append(
                Block(
                    heading=f"{b.heading} › FAQ" + (f": {q.group(1)}" if q else ""),
                    text=part.strip(),
                    atomic=True,
                )
            )
    return out


CS_ROW = re.compile(
    r"computer|\bCS\b|\bIT\b|informat|software|data science|\bAI\b|artificial|cyber|"
    r"all (disciplines|programmes|candidates|applicants)",
    re.I,
)
TABLE_HEADER_ROW = re.compile(r"discipline|S\.\s?#|S\.No|fee heads|eligibility requirement|sr\.", re.I)


def keep_department_rows(md: str) -> str:
    """University-wide notices tabulate 30+ departments; keep prose, headers and CS-relevant rows.

    Rows about other departments only dilute retrieval for a Computer Sciences assistant, and
    small models then overlook the one row that matters.
    """
    out = []
    for line in md.split("\n"):
        is_row = line.count(" | ") >= 3 and not line.startswith("|")
        if is_row and not TABLE_HEADER_ROW.search(line) and not CS_ROW.search(line):
            continue
        out.append(line)
    return "\n".join(out)


NUM_CELL = re.compile(r"^\**\s*(\d[\d,]*)\s*(/-)?\s*\**$|^\**[–-]\**$")


def label_fee_rows(md: str) -> str:
    """Turn fee-table rows into explicit sentences ("Total (A+B): Regular = 106,530; ...").

    In the source the programme columns ("Regular", "S.F/Evening") sit in a separate header
    row, so a row such as ``Total | 106,530 | 180,620`` is easy to mis-read. Spelling the
    column labels out on every row makes each fact self-contained.
    """
    labels: list[str] = []
    out: list[str] = []
    for line in md.split("\n"):
        stripped = line.replace("**", "").strip()
        if re.fullmatch(r"Regular\s*\|\s*S\.?F\.?\s*/\s*Evening", stripped, re.I):
            labels = ["Regular (morning) programme", "Self-finance / evening programme"]
            out.append(line)
            continue
        if labels and " | " in line:
            cells = [c.replace("**", "").strip() for c in line.split(" | ")]
            tail = cells[-len(labels):]
            if len(cells) > len(labels) and all(NUM_CELL.match(c) for c in tail):
                head_cells = cells[: -len(labels)]
                head = next((c for c in reversed(head_cells) if not re.fullmatch(r"\(?[a-z0-9]{1,3}\)?\.?", c, re.I)), head_cells[-1])
                # "(Except Pharmacy, Law, Comp. Sc. and IT)" EXCLUDES CS yet mentions it: say so plainly.
                head = re.sub(
                    r"\(\s*Except [^)]*?Comp[^)]*\)",
                    "(for programmes OTHER than Computer Science/IT — NOT for CS students)",
                    head,
                    flags=re.I,
                )
                head = re.sub(
                    r"\(?\s*Only for [^)]*?Computer Sc[^)]*\)?",
                    lambda m: m.group(0) + " [applies to Computer Science students]",
                    head,
                    flags=re.I,
                )
                values = "; ".join(f"{lab} = {re.sub(r'\s*/-', '', v).strip()} PKR" for lab, v in zip(labels, tail, strict=True))
                out.append(f"{head.rstrip(':').strip()}: {values}")
                continue
        out.append(line)
    return "\n".join(out)


def extract_generic(url: str, html: str, kind: str, meta: dict) -> Document:
    title, md = html_to_markdown(html, url)
    md = clean_text(md)
    if kind == "external" and "admission" in url.lower():
        md = keep_department_rows(md)
    if kind == "external" and "fee" in url.lower():
        md = label_fee_rows(md)
    title = clean_title(title)
    blocks = split_faq_blocks(markdown_to_blocks(md, title))
    return Document(url=url, title=title, kind=kind, blocks=blocks, meta=meta, priority=7)


EVENT = re.compile(
    r"(?m)^(\d{1,2})\n([A-Z][a-z]{2}) (\d{4})\n(\w+)\n+(?:Till ([^\n]+)\n+)?#{3,6} ([^\n]+)\n+([^\n]*)"
)
PAST_EVENT = re.compile(r"(?m)^(\w+)\n\*\*([^*\n]+)\*\*\n([A-Z][a-z]{2} \d{1,2}, \d{4})")


def extract_events(url: str, html: str) -> Document:
    """One dated record per event. On the page each event's date precedes its heading, so a
    generic heading split attaches dates to the *previous* event; parsing them explicitly fixes that."""
    title, md = html_to_markdown(html, url)
    md = clean_text(md)
    title = clean_title(title)
    blocks: list[Block] = []
    for m in EVENT.finditer(md):
        day, mon, year, kind, till, name, desc = m.groups()
        when = f"{int(day)} {mon} {year}" + (f" (runs until {till})" if till else "")
        text = f"Event: {name}. Date: {when}. Category: {kind}."
        if desc and not desc.startswith("Add to Calendar"):
            text += f" Details: {desc}"
        blocks.append(Block(heading=f"{title} › {name}", text=text, atomic=True))
    for m in PAST_EVENT.finditer(md):
        kind, name, date = m.groups()
        blocks.append(
            Block(heading=f"{title} › {name}", text=f"Past event: {name}. Date: {date}. Category: {kind}.", atomic=True)
        )
    if not blocks:  # layout changed: fall back to the generic extraction rather than lose the page
        return extract_generic(url, html, "events", {})
    intro = Block(
        heading=title,
        text="Academic calendar and events of the Department of Computer Sciences. Each entry below gives its date.",
    )
    return Document(url=url, title=title, kind="events", blocks=[intro, *blocks], meta={}, priority=9)


def extract_web(url: str, html: str, fetched_at: str = "") -> list[Document]:
    kind, meta = classify(url)
    docs: list[Document] = []
    if kind == "topic":
        return []  # derived index of mentions; primary pages are authoritative
    if kind == "events":
        docs = [extract_events(url, html)]
    elif kind == "programme":
        docs = [extract_programme(url, html, meta)]
    elif kind == "faculty_listing":
        _, md = html_to_markdown(html, url)
        docs = [
            Document(
                url=url, title="Faculty listing", kind="faculty_listing", blocks=[],
                meta={"entries": parse_faculty_listing(md)},
            )
        ]
    elif kind in ("course", "faculty"):
        title, md = html_to_markdown(html, url)
        md = clean_text(md)
        if kind == "course":
            doc = extract_course(url, title, md, meta)
            docs = [doc] if doc else [extract_generic(url, html, "page", meta)]
        else:
            docs = extract_faculty(url, title, md, meta)
    else:
        docs = [extract_generic(url, html, kind, meta)]
    for d in docs:
        d.fetched_at = fetched_at
    return docs
