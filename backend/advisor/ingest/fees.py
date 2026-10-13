"""Fee-structure pages (qau.edu.pk/*-fee-structure) → structured fee tables.

The three pages (Bachelor, MPhil, PhD) each carry several tables that look alike but mean different things:

* the one for **Computer Science** (together with IT, Law, Pharmacy, QASMS Business Administration …)
  — its rows are *also* split by programme ("Except Pharmacy, Law, Comp. Sc.", "Law, Comp. Science & IT",
  "Pharmacy"), and only the Computer Science row applies to our students;
* the one for all *other* programmes (not Computer Science);
* the one for *foreign* students, in US dollars.

Reading them as running text mixes the tables up (a language model once reported a BS evening line under
PhD, and the summer per-course tuition instead of the semester fee). This module keeps every table apart,
with its heading, term and columns, so answers can be looked up instead of guessed. It also renders the
tables as clearly labelled text for the search index.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from advisor.ingest.model import Block, Document

FEE_URL = re.compile(r"/(bachelor|mphil-programme|phd)-fee-structure/?$", re.I)
LEVELS = {"bachelor": "BS", "mphil-programme": "MPhil", "phd": "PhD"}
NUM = re.compile(r"^(?:[\d,]+(?:\.\d+)?\s*(?:/-)?|[–—-]|#)$")
TERM = re.compile(r"\b(Fall|Spring|Summer)[\s-]*(?:20)?(\d{2})\b", re.I)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _value(cell: str):
    """'35,040 /-' → 35040; '–' → None (not charged); '#' → 'formula' (calculated by the department)."""
    c = cell.strip()
    if c == "#":
        return "formula"
    if c in ("–", "—", "-"):
        return None
    m = re.match(r"[\d,]+(?:\.\d+)?", c)
    return int(m.group(0).replace(",", "")) if m and "." not in m.group(0) else (float(m.group(0).replace(",", "")) if m else None)


def _term(text: str) -> str:
    m = TERM.search(text)
    return f"{m.group(1).title()} 20{m.group(2)}" if m else ""


def _heading_before(table) -> str:
    """The "Fee Structure …" caption that precedes a table (the page has no wrapper element for it)."""
    pieces = [_clean(s) for s in table.find_all_previous(string=True, limit=60) if _clean(s)]
    text = " ".join(reversed(pieces))[-900:]
    hits = [m.start() for m in re.finditer(r"Fee Structure", text)]
    return text[hits[-1]:] if hits else text[-300:]


def _group_id(heading: str) -> str:
    if re.search(r"foreign", heading, re.I):
        return "foreign"
    if re.search(r"Computer Science", heading, re.I):
        return "cs"
    return "other"


def _is_cs_row(head: str) -> bool:
    return bool(re.search(r"Comp", head, re.I)) and not re.search(r"Except", head, re.I)


def parse_table(table, heading: str) -> dict | None:
    rows, notes, summer = [], [], None
    category = ""
    for tr in table.find_all("tr"):
        cells = [_clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c != ""]
        if not cells:
            continue
        if len(cells) == 1:
            text = cells[0]
            m = re.match(r"Categ\w*\s*([ABC])\b", text, re.I)
            if m:
                category = m.group(1).upper()
                continue
            if re.search(r"Tuition Fee\s*@", text, re.I):
                nums = [int(n.replace(",", "")) for n in re.findall(r"(?:Rs\.?\s*|\$\s*|@\s*)([\d,]{2,})", text)]
                summer = {"text": text.rstrip(". "), "values": nums}
                continue
            if len(text) > 25:
                notes.append(text)
            continue
        tail = []
        for c in reversed(cells):
            if NUM.match(c):
                tail.insert(0, c)
            else:
                break
        if not tail or len(tail) == len(cells):
            continue  # header rows ("S.No | Fee Heads | B.S & B.S 5th Semester", "Regular | S.F/Evening")
        lead = [c for c in cells[: len(cells) - len(tail)] if re.search(r"[A-Za-z]{3}", c) and not re.fullmatch(r"\(?[a-c]\)?", c, re.I)]
        if not lead:
            continue
        head = max(lead, key=len)
        if head.lower() in ("fee heads",):
            continue
        rows.append({"cat": category, "head": head.rstrip(" :"), "values": [_value(v) for v in tail]})
    if not rows:
        return None
    width = max(len(r["values"]) for r in rows)
    return {
        "id": _group_id(heading), "label": heading, "term": _term(heading),
        "currency": "USD" if _group_id(heading) == "foreign" else "PKR",
        "columns": ["R", "S"] if width == 2 else ["ALL"],
        "rows": rows, "summer": summer, "notes": list(dict.fromkeys(notes)),
    }


def parse_fee_page(url: str, html: str, fetched_at: str = "") -> dict | None:
    m = FEE_URL.search(url)
    if not m:
        return None
    soup = BeautifulSoup(html, "html.parser")
    title = _clean(soup.title.get_text()) if soup.title else ""
    groups = []
    for table in soup.find_all("table"):
        if not table.find(string=re.compile(r"Fee Heads", re.I)):
            continue  # layout tables (navigation)
        g = parse_table(table, _heading_before(table))
        if g:
            groups.append(g)
    if not groups:
        return None
    return {"level": LEVELS[m.group(1).lower()], "url": url.rstrip("/"), "title": title or f"{LEVELS[m.group(1).lower()]} fee structure",
            "fetched": fetched_at, "groups": groups}


# ---------------------------------------------------------------------------------- lookups
def _cs_pick(rows: list[dict], pattern: str, cat: str | None = None) -> dict | None:
    """The Computer Science variant of a row that is listed once per programme group."""
    hits = [r for r in rows if re.search(pattern, r["head"], re.I) and (cat is None or r["cat"] == cat)]
    cs = [r for r in hits if _is_cs_row(r["head"])]
    return (cs or hits[:1] or [None])[0] if (cs or len(hits) == 1) else None


def core_rows(group: dict) -> dict:
    """admission / per-semester / first-semester totals for one group (the Computer Science variant for 'cs')."""
    rows = group["rows"]
    if group["id"] == "cs":
        admission = _cs_pick(rows, r"^(Admission Fee|Total-?\s*a\b)", "A")
        total = _cs_pick(rows, r"^Total.*A\s*\+\s*(?:Category\s*)?B", None)
    else:
        admission = next((r for r in rows if r["cat"] == "A" and re.search(r"Total", r["head"], re.I)), None)
        total = next((r for r in rows if re.search(r"Total.*A\s*\+\s*(?:Category\s*)?B", r["head"], re.I)), None)
    per_sem = next((r for r in rows if r["cat"] == "B" and re.search(r"^Total\s*\(?-?b", r["head"], re.I)), None)
    return {"admission": admission, "per_semester": per_sem, "first_total": total}


def one_time_rows(group: dict) -> list[dict]:
    return [r for r in group["rows"] if r["cat"] == "C"]


# ---------------------------------------------------------------------------------- text for the search index
def _fmt(v, currency: str) -> str:
    if v is None:
        return "not charged (–)"
    if v == "formula":
        return "calculated by the department's dealing official (formula)"
    return f"{v:,.0f} {currency}" if isinstance(v, (int, float)) else str(v)


GROUP_LABEL = {
    "cs": "Computer Science (also IT, Law, Pharmacy, QASMS Business Administration, English, SP&IR) — national students",
    "other": "all OTHER programmes — NOT for Computer Science students — national students",
    "foreign": "foreign students (US dollars)",
}
COL_LABEL = {"R": "Regular (morning) programme", "S": "Self-finance / evening programme", "ALL": "all students"}


def fee_documents(page: dict) -> list[Document]:
    """Clearly labelled text blocks (one per table) so retrieval and the model cannot mix the tables up."""
    docs_blocks: list[Block] = []
    level = page["level"]
    for g in page["groups"]:
        cur = g["currency"]
        cols = [COL_LABEL[c] for c in g["columns"]]
        head = f"{level} fee structure — {GROUP_LABEL[g['id']]} — {g['term'] or 'term not stated'}"
        lines = [f"{head}. Amounts in {cur}." + (f" Columns: {' | '.join(cols)}." if len(cols) > 1 else "")]
        core = core_rows(g)
        if g["id"] == "cs":
            lines.append("Use the Computer Science rows below; rows marked 'Except … Comp. Sc.' or 'Pharmacy' are NOT for Computer Science students.")
        for key, label in (("per_semester", "Fee per semester (Category B, charged every semester)"),
                           ("admission", "Admission fee (Category A, charged once at admission)"),
                           ("first_total", "Total at admission = admission fee + first semester fee (A+B)")):
            r = core[key]
            if r:
                lines.append(f"{label}: " + "; ".join(f"{c} = {_fmt(v, cur)}" for c, v in zip(cols, r["values"])))
        if g["summer"]:
            lines.append("Summer semester: " + g["summer"]["text"])
        docs_blocks.append(Block(heading=f"{level} fee structure › {GROUP_LABEL[g['id']].split(' — ')[0]} › {g['term']}",
                                 text="\n".join(lines), atomic=True, meta={"variant": f"fees-core-{g['id']}"}))
        other = [r for r in g["rows"] if r not in core.values()]
        if other:
            body = [f"{head} — all fee heads:"]
            for r in other:
                body.append(f"- {r['head']} (Category {r['cat'] or '—'}): " + "; ".join(f"{c} = {_fmt(v, cur)}" for c, v in zip(cols, r["values"])))
            body += [f"- Note: {n}" for n in g["notes"][:5]]
            docs_blocks.append(Block(heading=f"{level} fee structure › {GROUP_LABEL[g['id']].split(' — ')[0]} › all fee heads › {g['term']}",
                                     text="\n".join(body), atomic=True, meta={"variant": f"fees-all-{g['id']}"}))
    return [Document(url=page["url"], title=page["title"], kind="fees", blocks=docs_blocks, source_type="web",
                     fetched_at=page.get("fetched", ""), meta={"variant": "fees", "level": level}, priority=9)]
