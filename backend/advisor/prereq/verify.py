"""Check a prerequisite JSON file for internal consistency and against its source document."""

from __future__ import annotations

import html
import json
import re
import zipfile
from pathlib import Path

from advisor.prereq.graph import canon


def docx_text(path: Path) -> str:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>|</w:tr>|<w:tab/>", " ", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s)).strip().lower()


def verify(json_path: Path, source_doc: Path | None = None) -> dict:
    """Return ``{"errors": [...], "warnings": [...], "stats": {...}}``.

    Errors mean a row cannot be trusted (unknown course, self-prerequisite, quote not found in
    the source document); warnings are things an administrator should look at.
    """
    data = json.loads(json_path.read_text())
    errors: list[str] = []
    warnings: list[str] = []
    codes = {canon(c["code"]) for c in data["courses"] if canon(c["code"])}
    alt = {canon(a) for c in data["courses"] for a in c.get("alt_codes", []) if canon(a)}
    source_text = _squash(docx_text(source_doc)) if source_doc and source_doc.exists() else None
    edges = set()
    for p in data["prerequisites"]:
        a, b = canon(p["course_code"]), canon(p.get("prereq_code") or "")
        where = f"{p['course_code']} ← {p.get('prereq_code')}"
        if a is None:
            errors.append(f"{where}: course code not recognised")
            continue
        if a not in codes | alt:
            errors.append(f"{where}: course is not defined in 'courses'")
        if p.get("prereq_code"):
            if b is None:
                errors.append(f"{where}: prerequisite code not recognised")
            elif b == a:
                errors.append(f"{where}: a course cannot be its own prerequisite")
            elif b not in codes | alt:
                warnings.append(f"{where}: prerequisite is not defined in 'courses'")
            edges.add((a, b))
        if not p.get("source_quote"):
            errors.append(f"{where}: missing source_quote")
        elif source_text is not None and _squash(p["source_quote"]) not in source_text:
            errors.append(f"{where}: quote not found verbatim in {source_doc.name}")
    # cycles would make "which must be passed first" meaningless
    graph: dict[str, set[str]] = {}
    for a, b in edges:
        graph.setdefault(a, set()).add(b)

    def has_cycle(n: str, stack: set[str], done: set[str]) -> bool:
        if n in stack:
            return True
        if n in done:
            return False
        stack.add(n)
        hit = any(has_cycle(m, stack, done) for m in graph.get(n, ()))
        stack.discard(n)
        done.add(n)
        return hit

    done: set[str] = set()
    if any(has_cycle(n, set(), done) for n in list(graph)):
        errors.append("the prerequisites contain a cycle")
    unresolved = data.get("unresolved", [])
    if unresolved:
        warnings.append(f"{len(unresolved)} items were flagged 'unresolved' by the extractor")
    return {
        "errors": errors, "warnings": warnings,
        "stats": {
            "courses": len(data["courses"]), "prerequisite_rows": len(data["prerequisites"]),
            "quotes_checked_against_source": source_text is not None,
        },
    }
