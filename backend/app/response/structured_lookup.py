"""Exact course facts from approved versions; ambiguity is reported, never guessed."""

import re
from pathlib import Path

from app.core.config import get_settings
from app.ingestion.archive import SourceArchive
from app.rag.corpus import PROJECT_ROOT
from app.rag.evidence import query_programs
from app.response.grounded import GroundedAnswer


def structured_answer(query, scope, language="english"):
    code = scope.get("course")
    if len(re.findall(r"\b(?:Fall|Spring|Summer)\s*20\d{2}\b", query, re.I)) > 1:
        return None
    if not code or not re.search(r"credit|prereq|pre.?req|کریڈٹ|شرط", query, re.I):
        return None
    path = Path(get_settings().knowledge_archive_path)
    path = path if path.is_absolute() else PROJECT_ROOT / path
    if not (path / "catalogue.sqlite3").exists():
        return None
    archive = SourceArchive(path)
    field = (
        "prerequisites_raw" if re.search(r"prereq|pre.?req|شرط", query, re.I) else "credit_hours"
    )
    candidates = []
    try:
        for version in archive.approved_documents():
            document = version["document"]
            term = document["metadata"]["effective_term"]
            if scope.get("term") and term != scope["term"]:
                continue
            programs = query_programs(document["metadata"]["program"])
            if scope.get("programs") and programs and not programs.intersection(scope["programs"]):
                continue
            for record in document["records"]:
                if record["record_type"] != "course" or record["course_code"] != code:
                    continue
                if record.get(field) is not None:
                    candidates.append((version, record, term))
    finally:
        archive.close()
    if not candidates:
        return None
    if not scope.get("term") and len({c[2] for c in candidates}) > 1:
        return GroundedAnswer(
            "Which admission batch and scheme should I use for this course?",
            model="structured-clarification",
        )
    values = {str(record[field]) for _, record, _ in candidates}
    conflict = len(values) > 1
    citations, lines = [], []
    seen = set()
    for version, record, term in candidates:
        key = (version["version_id"], str(record[field]))
        if key in seen:
            continue
        seen.add(key)
        number = len(citations) + 1
        provenance = record["source"]
        citations.append(
            {
                "number": number,
                "chunk_id": "structured-" + version["version_id"] + "-" + code,
                "document_id": version["version_id"],
                "source_version_id": version["version_id"],
                "source_sha256": version["raw_sha256"],
                "source_url": version["url"],
                "title": version["document"]["title"],
                "effective_term": term,
                "page_number": provenance.get("page_number"),
                "quotes": [provenance["quote"]],
                "verification_status": "approved",
            }
        )
        label = "credit hours" if field == "credit_hours" else "published prerequisites"
        lines.append(f"{code} · {term or 'undated source'}: {record[field]} {label}. [{number}]")
    prefix = (
        "The approved official sources disagree. Please confirm with the department.\n\n"
        if conflict
        else ""
    )
    return GroundedAnswer(
        prefix + "\n".join(lines),
        citations,
        engine="rag",
        grounding_status="source_conflict" if conflict else "cited_lookup",
        notices=["Exact lookup from reviewed source records."],
        model="structured",
    )
