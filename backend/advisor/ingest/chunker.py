"""Block → chunk splitting, with context headers and retrieval aliases."""

from __future__ import annotations

import re

from advisor.ingest.model import Block, Chunk, Document, stable_id

MAX_CHARS = 1500
TARGET_CHARS = 1100
MAX_ATOMIC_CHARS = 3200
MIN_CHARS = 220

TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[“\"])")
CODE = re.compile(r"\b([A-Z]{2,4})[- ]?(\d{3}[A-Z]?)\b")


# ---------------------------------------------------------------------------- aliasing
def code_aliases(text: str) -> list[str]:
    """Course codes appear as CS-211 *and* CSC-211 across the site's generations.

    Adding the sibling spelling to the index text lets a query for either find both.
    """
    out: list[str] = []
    for prefix, num in CODE.findall(text):
        forms = {f"{prefix}-{num}", f"{prefix}{num}"}
        if prefix == "CS":
            forms |= {f"CSC-{num}", f"CSC{num}"}
        elif prefix == "CSC":
            forms |= {f"CS-{num}", f"CS{num}"}
        out.extend(sorted(forms))
    return list(dict.fromkeys(out))


def name_aliases(meta: dict) -> list[str]:
    name = meta.get("faculty_name")
    if not name:
        return []
    bare = re.sub(r"^(Dr|Prof|Mr|Ms|Mrs|Engr)\.?\s+", "", name, flags=re.I)
    bare = re.sub(r"\s*\(.*?\)\s*", " ", bare).strip()
    parts = bare.split()
    aliases = [bare]
    if len(parts) >= 2:
        aliases.append(f"{parts[0]} {parts[-1]}")  # first + last
        aliases.append(parts[-1])
    return list(dict.fromkeys(aliases))


# ---------------------------------------------------------------------------- splitting
def _split_table(lines: list[str], limit: int) -> list[str]:
    """Split a Markdown table by rows, repeating its header lines in every part."""
    header: list[str] = []
    body = list(lines)
    if len(lines) >= 2 and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[1]):
        header, body = lines[:2], lines[2:]
    parts, cur = [], []
    size = sum(len(x) for x in header)
    for row in body:
        if cur and size + len(row) > limit:
            parts.append("\n".join(header + cur))
            cur, size = [], sum(len(x) for x in header)
        cur.append(row)
        size += len(row) + 1
    if cur:
        parts.append("\n".join(header + cur))
    return parts


def split_text(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Split on paragraph → line → sentence boundaries; tables by row."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    # Group into paragraphs and table runs first.
    units: list[str] = []
    para: list[str] = []
    table: list[str] = []

    def flush_para():
        if para:
            units.append("\n".join(para).strip())
            para.clear()

    def flush_table():
        if table:
            units.extend(_split_table(table, limit))
            table.clear()

    for ln in text.split("\n"):
        if TABLE_LINE.match(ln):
            flush_para()
            table.append(ln)
        elif not ln.strip():
            flush_table()
            flush_para()
        else:
            flush_table()
            para.append(ln)
    flush_table()
    flush_para()

    # Break any unit that is still too long on sentence/line boundaries.
    pieces: list[str] = []
    for u in units:
        if len(u) <= limit:
            pieces.append(u)
            continue
        if TABLE_LINE.match(u.split("\n")[0]):
            pieces.append(u)  # table parts are already sized; leave header-bearing rows whole
            continue
        parts = u.split("\n") if u.count("\n") > 2 else SENT_SPLIT.split(u)
        buf = ""
        for part in parts:
            if buf and len(buf) + len(part) + 1 > limit:
                pieces.append(buf.strip())
                buf = ""
            if len(part) > limit:  # pathological run-on text
                for i in range(0, len(part), limit):
                    pieces.append(part[i : i + limit])
                continue
            buf = f"{buf}\n{part}" if buf and "\n" in u else f"{buf} {part}".strip()
        if buf.strip():
            pieces.append(buf.strip())

    # Pack pieces up to TARGET.
    chunks, cur = [], ""
    for piece in pieces:
        if cur and len(cur) + len(piece) + 2 > limit:
            chunks.append(cur.strip())
            cur = ""
        cur = f"{cur}\n\n{piece}" if cur else piece
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def chunk_document(doc: Document) -> list[Chunk]:
    chunks: list[Chunk] = []
    pending: list[Block] = []

    def emit(heading: str, text: str, atomic: bool = False):
        text = text.strip()
        if not text:
            return
        ordinal = len(chunks)
        extra = []
        aliases = code_aliases(text + " " + heading + " " + doc.title)
        if aliases:
            extra.append("Course code forms: " + " ".join(aliases[:12]))
        names = name_aliases(doc.meta)
        if names:
            extra.append("Name forms: " + "; ".join(names))
        context = f"{doc.title} › {heading}" if heading and heading != doc.title else doc.title
        index_text = "\n".join([context, text, *extra])
        meta = {k: v for k, v in doc.meta.items() if k in _KEEP_META}
        chunks.append(
            Chunk(
                chunk_id=stable_id(doc.doc_id, str(ordinal), text[:80]),
                doc_id=doc.doc_id,
                ord=ordinal,
                url=doc.url,
                title=doc.title,
                kind=doc.kind,
                heading=heading,
                text=text,
                index_text=index_text,
                meta=meta,
                priority=doc.priority,
                source_type=doc.source_type,
                fetched_at=doc.fetched_at,
                atomic=atomic,
            )
        )

    def flush_pending():
        if not pending:
            return
        heading = pending[0].heading
        merged = "\n\n".join(b.text for b in pending)
        pending.clear()
        for part in split_text(merged):
            emit(heading, part)

    for block in doc.blocks:
        if block.atomic:
            flush_pending()
            if len(block.text) <= MAX_ATOMIC_CHARS:
                emit(block.heading, block.text, atomic=True)
            else:
                for i, part in enumerate(split_text(block.text, MAX_ATOMIC_CHARS - 400)):
                    head = block.heading if i == 0 else f"{block.heading} (part {i + 1})"
                    # Re-state the first line (identity of the record) on continuation parts.
                    lead = block.text.split("\n", 1)[0]
                    emit(head, part if i == 0 else f"{lead} (continued)\n{part}", atomic=True)
            continue
        if pending and (
            sum(len(b.text) for b in pending) + len(block.text) > TARGET_CHARS
            or _top(pending[0].heading) != _top(block.heading)
        ):
            flush_pending()
        pending.append(block)
        if sum(len(b.text) for b in pending) >= TARGET_CHARS:
            flush_pending()
    flush_pending()
    return _merge_tiny(chunks)


def _top(heading: str) -> str:
    parts = heading.split(" › ")
    return " › ".join(parts[:2])


_KEEP_META = {
    "course_code", "course_name", "faculty_name", "designation", "email", "term", "semester",
    "programme", "slug", "credits_total", "ocr", "day", "variant", "note", "position", "room",
}


def _merge_tiny(chunks: list[Chunk]) -> list[Chunk]:
    """Fold chunks that are too small to stand alone into their predecessor."""
    out: list[Chunk] = []
    for c in chunks:
        if (
            out
            and len(c.text) < MIN_CHARS
            and out[-1].doc_id == c.doc_id
            and len(out[-1].text) + len(c.text) < MAX_CHARS
            and not c.atomic
            and not out[-1].atomic
        ):
            prev = out[-1]
            prev.text = f"{prev.text}\n\n{c.text}"
            prev.index_text = f"{prev.index_text}\n{c.text}"
            continue
        out.append(c)
    for i, c in enumerate(out):
        c.ord = i
    return out
