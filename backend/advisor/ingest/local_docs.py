"""Department documents that are *not* on the website (SOPs, FYP rules, circulars …).

Drop a PDF / Word / text / Markdown file into ``<data_dir>/documents`` (or upload it in the admin
console). An optional sidecar ``<file>.meta.json`` can carry ``title``, ``note`` and ``effective``.
These documents are treated as official, so they rank above generic pages when they match.
"""

from __future__ import annotations

import html
import json
import logging
import re
import zipfile
from pathlib import Path

from advisor.ingest.model import Block, Document
from advisor.ingest.pdf_extract import _extract_pdf
from advisor.ingest.web_extract import clean_text, markdown_to_blocks

log = logging.getLogger("advisor.localdocs")

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}
DEFAULT_NOTE = "Official department document supplied to the assistant; it is not published on the website."


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "document"


# ---------------------------------------------------------------------------- DOCX → Markdown
def docx_to_markdown(path: Path) -> str:
    """Headings, list items and tables of a .docx, as Markdown (no external dependency)."""
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "replace")
    body = xml[xml.find("<w:body"):]
    out: list[str] = []

    def para_text(p: str) -> str:
        p = re.sub(r"<w:tab/>", " ", p)
        p = re.sub(r"<w:br[^>]*/>", "\n", p)
        return html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))).strip()

    def para(p: str) -> str:
        text = para_text(p)
        if not text:
            return ""
        style = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        if style:
            m = re.match(r"(?i)heading\s*(\d)|title", style.group(1))
            if m:
                level = int(m.group(1)) if m.group(1) else 1
                return "\n" + "#" * min(level + 1, 6) + " " + text + "\n"
        if "<w:numPr>" in p:
            return "- " + text
        # short, fully bold paragraph = a heading in documents that don't use heading styles
        runs = re.findall(r"<w:r[ >].*?</w:r>", p, flags=re.S)
        if runs and len(text) < 90 and all("<w:b/>" in r or "<w:b " in r for r in runs if "<w:t" in r):
            return "\n### " + text + "\n"
        return text

    pos = 0
    for m in re.finditer(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>", body, flags=re.S):
        s = m.group(0)
        if s.startswith("<w:tbl>"):
            rows = []
            for tr in re.findall(r"<w:tr[ >].*?</w:tr>", s, flags=re.S):
                cells = [
                    re.sub(r"\s+", " ", " ".join(para_text(p) for p in re.findall(r"<w:p[ >].*?</w:p>", tc, flags=re.S))).strip()
                    for tc in re.findall(r"<w:tc>.*?</w:tc>", tr, flags=re.S)
                ]
                if any(cells):
                    rows.append(cells)
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                out.append("| " + " | ".join(rows[0]) + " |")
                out.append("|" + "|".join(["---"] * width) + "|")
                out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        else:
            line = para(s)
            if line:
                out.append(line)
        pos = m.end()
    del pos
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ---------------------------------------------------------------------------- loading
def load_document(path: Path) -> Document | None:
    ext = path.suffix.lower()
    meta_file = path.with_name(path.name + ".meta.json")
    side = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    title = side.get("title") or path.stem.replace("_", " ").replace("-", " ").strip()
    note = side.get("note") or DEFAULT_NOTE
    if side.get("effective"):
        note += f" Effective: {side['effective']}."
    url = f"doc://department/{slug(path.stem)}"
    if ext == ".pdf":
        docs = _extract_pdf(path, url, "")
        if not docs:
            return None
        doc = docs[0]
        doc.title = title
        for b in doc.blocks:
            b.heading = title + (b.heading[b.heading.find(" › "):] if " › " in b.heading else "")
    else:
        text = docx_to_markdown(path) if ext == ".docx" else path.read_text(errors="replace")
        text = clean_text(text)
        blocks = markdown_to_blocks(text, title)
        if not blocks:
            return None
        doc = Document(url=url, title=title, kind="department_document", blocks=blocks)
    doc.kind = "department_document"
    doc.url = url
    doc.priority = 10
    doc.meta = {**doc.meta, "note": note, "variant": f"local:{path.name}"}
    if not doc.blocks:
        doc.blocks = [Block(heading=title, text=title)]
    return doc


def local_documents(directory: Path | None) -> list[Document]:
    out: list[Document] = []
    if not directory or not Path(directory).exists():
        return out
    for path in sorted(Path(directory).iterdir()):
        if path.suffix.lower() not in SUPPORTED or path.name.startswith("."):
            continue
        try:
            doc = load_document(path)
        except Exception:  # a bad upload must never break the whole rebuild
            log.exception("could not read department document %s", path.name)
            continue
        if doc:
            out.append(doc)
    return out
