"""PDF → :class:`Document` extraction.

Handlers (chosen per document):

* **scheme** – the two-column "Scheme of Study" handouts. Each page is cropped into left
  and right halves *before* text extraction so semesters never interleave.
* **timetable** – the weekly grid. See :mod:`advisor.ingest.timetable`.
* **regulations / generic** – single-column prose; headers/footers removed, wrapped lines
  re-joined, numbered clauses turned into headed blocks.
* **scanned** – pages without a text layer are OCR'd with Tesseract.

Anything that lists individual applicants (merit lists) is deliberately *not* indexed.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import pdfplumber

from advisor.ingest.model import Block, Document
from advisor.ingest.web_extract import fix_mojibake

log = logging.getLogger("advisor.pdf")

CATEGORY_LEGEND = (
    "Category codes: CC = Computing Core, DC = Domain Core, DE = Domain Elective, "
    "MS = Maths & Supporting, ES = Elective Supporting, GE = General Education. "
    "Credit notation \"3+1\" means 3 theory credit hours + 1 lab credit hour."
)

PRIVATE_LIST = re.compile(r"provisional\s+list\s+of\s+(recommended\s+)?candidates", re.I)


# ---------------------------------------------------------------------------- OCR
def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_page(pdf_path: Path, page_index: int, psm: int = 4, dpi: int = 300) -> str:
    """Render one page and run Tesseract on it."""
    import pypdfium2 as pdfium

    if not tesseract_available():
        raise RuntimeError("tesseract is not installed; cannot OCR scanned PDF")
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        image = pdf[page_index].render(scale=dpi / 72).to_pil().convert("L")
    finally:
        pdf.close()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "page.png"
        image.save(src)
        out = Path(tmp) / "out"
        subprocess.run(
            ["tesseract", str(src), str(out), "--psm", str(psm), "-l", "eng"],
            check=True, capture_output=True, timeout=180,
        )
        return (out.with_suffix(".txt")).read_text(errors="replace")


def ocr_halves(pdf_path: Path, page_index: int, dpi: int = 300) -> tuple[str, str]:
    """OCR a two-column page, returning ``(left_column, right_column)`` text.

    Cropping at the page centre cuts words when the scan is offset, so the whole page is
    OCR'd to word boxes (TSV) and the words are partitioned at the whitespace valley that
    separates the columns. Lines are rebuilt per column from the box coordinates.
    """
    import numpy as np
    import pypdfium2 as pdfium

    if not tesseract_available():
        raise RuntimeError("tesseract is not installed; cannot OCR scanned PDF")
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        image = pdf[page_index].render(scale=dpi / 72).to_pil().convert("L")
    finally:
        pdf.close()
    width = image.size[0]
    dark = np.array(image) < 140
    profile = np.convolve(dark.sum(axis=0).astype(float), np.ones(25) / 25, mode="same")
    lo, hi = int(width * 0.4), int(width * 0.6)
    split = lo + int(profile[lo:hi].argmin())

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "page.png"
        image.save(src)
        out = Path(tmp) / "out"
        subprocess.run(
            ["tesseract", str(src), str(out), "--psm", "6", "-l", "eng", "tsv"],
            check=True, capture_output=True, timeout=240,
        )
        rows = (out.with_suffix(".tsv")).read_text(errors="replace").split("\n")[1:]
    words = []
    for row in rows:
        f = row.split("\t")
        if len(f) < 12 or not f[11].strip() or float(f[10]) < 0:
            continue
        left, top, w, h = (int(f[6]), int(f[7]), int(f[8]), int(f[9]))
        words.append((left + w / 2, top + h / 2, left, h, f[11]))
    if not words:
        return "", ""
    tol = max(8.0, float(np.median([w[3] for w in words])) * 0.6)

    def build(sel):
        lines: list[list[tuple[float, float, str]]] = []
        for cx, cy, left, _h, text in sorted(sel, key=lambda w: w[1]):
            if lines and abs(lines[-1][0][1] - cy) <= tol:
                lines[-1].append((left, cy, text))
            else:
                lines.append([(left, cy, text)])
        return "\n".join(" ".join(t for _l, _y, t in sorted(ln)) for ln in lines)

    return (
        build([w for w in words if w[0] < split]),
        build([w for w in words if w[0] >= split]),
    )


# ---------------------------------------------------------------------------- text cleanup
def strip_repeated_lines(pages: list[str]) -> list[str]:
    """Drop running headers / footers / bare page numbers that repeat across pages."""
    if len(pages) < 2:
        return [re.sub(r"^\s*\d{1,4}\s*$", "", p, flags=re.M) for p in pages]
    counts: Counter[str] = Counter()
    for p in pages:
        for ln in {x.strip() for x in p.split("\n") if x.strip()}:
            counts[ln] += 1
    threshold = max(2, int(len(pages) * 0.5))
    noisy = {ln for ln, c in counts.items() if c >= threshold and len(ln) < 90}
    cleaned = []
    for p in pages:
        lines = [
            ln for ln in p.split("\n")
            if ln.strip() not in noisy and not re.fullmatch(r"\s*\(?\d{1,4}\)?\s*", ln)
        ]
        cleaned.append("\n".join(lines))
    return cleaned


SENTENCE_END = re.compile(r"[.:;!?)\]”\"']\s*$")
CLAUSE_START = re.compile(r"^(\(?[0-9]+(\.[0-9]+)*\.?\)?|\([a-z]\)|\([ivx]+\)|[a-z]\)|[-•●▪])\s")


def reflow(text: str) -> str:
    """Re-join hard-wrapped lines into paragraphs; keep clauses, headings and tables apart."""
    out: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue
        if not out or out[-1] == "":
            out.append(line)
            continue
        prev = out[-1]
        starts_new = bool(CLAUSE_START.match(line)) or line.isupper() or prev.isupper()
        looks_tabular = "  " in raw.strip() or bool(re.search(r"\s\d+(\.\d+)?$", prev) and len(prev) < 50)
        if starts_new or looks_tabular or SENTENCE_END.search(prev) and line[:1].isupper():
            out.append(line)
        else:
            joined = prev
            joined = joined[:-1] if joined.endswith("-") and line[:1].islower() else joined + " "
            out[-1] = (joined + line).strip()
    return "\n".join(out)


HEADING_TOP = re.compile(r"^(\d{1,2})\.\s+([A-Z][A-Za-z0-9,&/'’() \-]{2,80})$")
HEADING_SUB = re.compile(r"^(\d{1,2}\.\d{1,2})\.?\s+([A-Z][A-Za-z0-9,&/'’() \-]{2,70})$")
HEADING_ROMAN = re.compile(r"^([IVX]{1,5})\.\s+([A-Z][A-Za-z0-9 ,&/'’()\-]{3,80})$")
HEADING_CAPS = re.compile(r"^[A-Z][A-Z0-9 ,&/'’()\-]{6,90}$")


def prose_to_blocks(text: str, doc_title: str) -> list[Block]:
    """Group reflowed prose by numbered headings / ALL-CAPS headings."""
    blocks: list[Block] = []
    top = ""
    sub = ""
    buf: list[str] = []

    def flush():
        body = "\n".join(buf).strip()
        buf.clear()
        if body:
            path = " › ".join(x for x in (doc_title, top, sub) if x)
            blocks.append(Block(heading=path, text=body))

    for line in text.split("\n"):
        s = line.strip()
        if not s:
            buf.append("")
            continue
        if m := HEADING_TOP.match(s):
            flush()
            top, sub = f"{m.group(1)}. {m.group(2).strip()}", ""
            continue
        if (m := HEADING_ROMAN.match(s)) and sum(c.isupper() for c in m.group(2)) >= len(m.group(2)) * 0.6:
            flush()
            top, sub = f"{m.group(1)}. {m.group(2).strip().title()}", ""
            continue
        if m := HEADING_SUB.match(s):
            # sub-heading only if the line has no sentence punctuation (i.e. a title)
            if not s.endswith((".", ",", ";")) and len(s) < 80:
                flush()
                sub = f"{m.group(1)} {m.group(2).strip()}"
                continue
        if HEADING_CAPS.match(s) and len(s.split()) <= 14 and not re.search(r"\d{4}", s):
            flush()
            top, sub = s.title(), ""
            continue
        buf.append(s)
    flush()
    return blocks


# ---------------------------------------------------------------------------- scheme PDFs
SEM_HEADER = re.compile(r"^\s*(?:semester|SEMESTER)[\s\-:]*([IVX]+|\d+)\b\s*$", re.I)
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}


def _semester_no(token: str) -> int:
    token = token.upper()
    return ROMAN.get(token) or int(token)


def _scheme_term(text: str, url: str) -> str:
    m = re.search(r"(?:Fall|Spring)\s*(20\d\d)", text, re.I)
    if m:
        return f"Fall {m.group(1)}"
    m = re.search(r"scheme-(20\d\d)", url)
    if m:
        return f"Fall {m.group(1)}"
    m = re.search(r"Effective From\s*(20\d\d)", text, re.I)
    return f"Fall {m.group(1)}" if m else "unspecified term"


CREDIT_TOTAL = re.compile(r"^\W*(Total\s+Credits?|Credit\s+Hours)\b", re.I)


def normalise_ocr_codes(text: str) -> str:
    """Repair course codes that OCR splits or mis-punctuates (``CS 103``, ``CS-41 1``)."""
    text = re.sub(r"\b([A-Z]{2,4})[ :](\d{3}[A-Za-z]?)\b(?=:|\s)", r"\1-\2", text)
    return re.sub(r"\b([A-Z]{2,4}-\d{2}) (\d)\b", r"\1\2", text)


def split_semesters(text: str) -> tuple[list[tuple[int, list[str]]], list[str]]:
    """Return per-semester course lines (each ending at its credit total) and leftover lines."""
    sems: list[tuple[int, list[str]]] = []
    extras: list[str] = []
    cur: tuple[int, list[str]] | None = None
    closed = True
    for ln in text.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        m = SEM_HEADER.match(ln)
        if m:
            cur = (_semester_no(m.group(1)), [])
            sems.append(cur)
            closed = False
        elif cur is not None and not closed:
            cur[1].append(ln)
            if CREDIT_TOTAL.match(ln):
                closed = True
        elif cur is not None and closed:
            extras.append(ln)
    return sems, extras


def extract_scheme_pdf(path: Path, url: str, fetched_at: str) -> list[Document]:
    columns: list[str] = []
    full_text: list[str] = []
    ocr_used = False
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            native = (page.extract_text() or "").strip()
            if len(native) < 40:
                left, right = ocr_halves(path, i)
                ocr_used = True
                columns += [left, right]
                full_text.append(left + "\n" + right)
                continue
            full_text.append(native)
            mid = page.width / 2
            two_col = len(re.findall(r"Semester\s*\d", native, re.I)) >= 2 and any(
                re.search(r"Semester\s*\d.*Semester\s*\d", ln, re.I) for ln in native.split("\n")
            )
            if two_col:
                columns.append(page.crop((0, 0, mid, page.height)).extract_text() or "")
                columns.append(page.crop((mid, 0, page.width, page.height)).extract_text() or "")
            else:
                columns.append(native)
    term = _scheme_term("\n".join(full_text), url)
    title = f"BS Computer Science — Scheme of Study ({term} onwards)"
    sems: list[tuple[int, list[str]]] = []
    extras: list[str] = []
    for col in columns:
        found, rest = split_semesters(normalise_ocr_codes(col) if ocr_used else col)
        sems += found
        extras += rest
    sems.sort(key=lambda sem: sem[0])
    blocks: list[Block] = []
    overview: list[str] = []
    seen: set[int] = set()
    for no, lines in sems:
        if no in seen:  # same semester repeated in another crop
            continue
        seen.add(no)
        body_lines: list[str] = []
        codes: list[str] = []
        for ln in lines:
            if re.match(r"^(Sr\.|S\.?No)\b", ln) or ln.startswith("COURSE"):
                continue
            body_lines.append(fix_mojibake(ln))
            codes += re.findall(r"\b[A-Z]{2,4}[-\s]\d{3}\b", ln)
        # Trailing prose (e.g. the internship note) is not part of the last semester table.
        text = "\n".join(body_lines)
        legend = (
            "\n" + CATEGORY_LEGEND
            if re.search(r"\s(CC|DC|DE|MS|ES|GE)\s+\d", text)
            else ""
        )
        blocks.append(
            Block(
                heading=f"{title} › Semester {no}",
                text=f"{title} — Semester {no}\n{text}{legend}",
                atomic=True,
                meta={"semester": no, "term": term, "codes": codes},
            )
        )
        overview.append(f"Semester {no}: " + (", ".join(dict.fromkeys(codes)) or "(see table)"))
    # Anything after a semester's credit total: elective course lists, internship notes ...
    tail = "\n".join(
        ln for ln in extras if not re.search(r"Scheme of Study|Effective From|batch", ln, re.I)
    ).strip()
    if tail:
        blocks.append(
            Block(heading=f"{title} › Notes and elective courses", text=f"{title} — notes\n{tail}")
        )
    if overview:
        blocks.insert(
            0,
            Block(
                heading=f"{title} › Overview",
                text=f"{title}. Course codes per semester:\n" + "\n".join(overview),
                atomic=True,
            ),
        )
    doc = Document(
        url=url,
        title=title,
        kind="scheme",
        blocks=blocks,
        source_type="pdf",
        fetched_at=fetched_at,
        meta={"term": term, "ocr": ocr_used, "programme": "BS Computer Science"},
        priority=9,
    )
    return [doc] if blocks else []


# ---------------------------------------------------------------------------- generic PDFs
def pdf_title(first_page: str, url: str) -> str:
    lines = [ln.strip() for ln in first_page.split("\n") if ln.strip()]
    calendar = next((ln for ln in lines if re.search(r"Calendar\s+20\d\d", ln)), "")
    if calendar:
        # University-calendar extracts: name the regulation, not the running header.
        parts = []
        for ln in lines:
            if re.match(r"^(REGULATIONS|RULES|PROCEDURE)", ln) or (parts and ln.isupper() and len(parts) < 3):
                parts.append(ln)
        if parts:
            return f"{' '.join(parts).title()[:150]} ({calendar})"
    for ln in lines:
        if len(ln) > 8 and not re.fullmatch(r"[\d\W]+", ln):
            return ln[:120]
    return Path(url).name


def _pdfium_text(path: Path, index: int) -> str:
    """Second text engine for pages whose fonts pdfplumber cannot map (``(cid:72)`` noise)."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        text = pdf[index].get_textpage().get_text_range()
    finally:
        pdf.close()
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_generic_pdf(path: Path, url: str, fetched_at: str, ocr_psm: int = 4) -> list[Document]:
    pages: list[str] = []
    ocr_used = False
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(x_tolerance=1.5) or ""
            if text.count("(cid:") > 3:
                alt = _pdfium_text(path, i)
                if alt.count("(cid:") < text.count("(cid:"):
                    text = alt
            if len(text.strip()) < 40:
                try:
                    text = ocr_page(path, i, psm=ocr_psm)
                    ocr_used = True
                except Exception as exc:  # OCR is best-effort
                    log.warning("OCR failed for %s p%d: %s", url, i + 1, exc)
            pages.append(fix_mojibake(text))
    if not any(p.strip() for p in pages):
        return []
    first = pages[0]
    if PRIVATE_LIST.search(first):
        return []  # applicant names: personal data, never indexed
    title = pdf_title(first, url)
    body = reflow("\n".join(strip_repeated_lines(pages)))
    blocks = prose_to_blocks(body, title)
    return [
        Document(
            url=url,
            title=title,
            kind="document",
            blocks=blocks,
            source_type="pdf",
            fetched_at=fetched_at,
            meta={"ocr": ocr_used, "pages": len(pages)},
            priority=8,
        )
    ]


def first_page_text(path: Path) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            return (pdf.pages[0].extract_text() or "") if pdf.pages else ""
    except Exception:  # corrupt PDFs are skipped by the caller
        return ""


def extract_pdf(path: Path, url: str, fetched_at: str = "") -> list[Document]:
    from advisor.ingest.registry import apply_registry

    return [apply_registry(d) for d in _extract_pdf(path, url, fetched_at)]


def _extract_pdf(path: Path, url: str, fetched_at: str = "") -> list[Document]:
    head = first_page_text(path)
    name = url.lower()
    if PRIVATE_LIST.search(head):
        return []
    if "scheme-20" in name or re.search(r"scheme of stud", head, re.I):
        return extract_scheme_pdf(path, url, fetched_at)
    if re.match(r"\s*time\s*table", head, re.I):
        from advisor.ingest.timetable import extract_timetable_pdf

        return extract_timetable_pdf(path, url, fetched_at)
    return extract_generic_pdf(path, url, fetched_at)
