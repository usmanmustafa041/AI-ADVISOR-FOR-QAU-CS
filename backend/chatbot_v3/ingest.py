"""Import originals read-only into isolated staging; never import old answers/rules/vectors."""

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from chatbot_v3.parsing import PARSER_VERSION, course_rows, parse
from chatbot_v3.settings import ROOT, settings
from chatbot_v3.store import Store


def now():
    return datetime.now(UTC).isoformat()


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def source_metadata(uri, title, text, hint=None):
    hint = hint or {}
    path = urlsplit(uri).path.lower()
    # Source classification is acquisition metadata, never a student query handler.
    topic = "general"
    groups = [
        ("faculty", ["/faculty", "/people"]),
        ("curriculum", ["scheme", "course-outline", "/courses"]),
        ("fees", ["fee-structure", "tuition-fee", "hostel-fee"]),
        ("academic_policy", ["rules", "regulations", "policy"]),
        ("admissions", ["admission", "eligibility", "sample-paper"]),
        ("timetable", ["timetable", "tt_v", "/tt."]),
        ("exam_schedule", ["date-sheet", "datesheet", "exam-schedule"]),
        ("research", ["research"]),
        (
            "procedures",
            [
                "/download/",
                "/downloads",
                "/examination",
                "transcript",
                "degree-form",
                "/degree-issuance",
                "clearance",
                "proforma",
                "synopsis",
                "thesis",
                "project-guideline",
                "/forms",
                "/student-services",
            ],
        ),
        (
            "services",
            [
                "hostel",
                "accommodation",
                "transport",
                "scholarship",
                "financial-assistance",
                "contact-list",
                "/students",
                "/contact",
            ],
        ),
        ("programme", ["/bs", "/ms", "/mphil", "/phd"]),
        ("programme", ["/course/"]),
    ]
    for category, needles in groups:
        if any(n in path for n in needles):
            topic = category
            break
    if re.search(r"\b(?:rules|regulations|policy|handbook)\b", title, re.I):
        topic = "academic_policy"
    programme = None
    if (
        "scheme" in path
        or "bachelor" in path
        or "undergraduate" in path
        or "bs-program" in path
        or "bs-cs" in path
        or path in {"/bs", "/bs.php"}
    ):
        programme = "BSCS"
    elif "mphil" in path:
        programme = "MPhil"
    elif "phd" in path:
        programme = "PhD"
    elif "ms-ds" in path or "ms_ds" in path or "data-science" in path:
        programme = "MS-DS"
    elif "ms-ist" in path or "ms_ist" in path or "information-sciences" in path:
        programme = "MS-IST"
    if not programme and topic == "procedures":
        if re.search(r"\bM\.?Phil\b", title, re.I):
            programme = "MPhil"
        elif re.search(r"\bPh\.?D\b", title, re.I):
            programme = "PhD"
        elif re.search(r"\bBS\b", title):
            programme = "BSCS"
    if "/course/" in path:
        printed = re.search(r"(?:^|\n)(BS|MPhil|PhD|MS-DS|MS-IST)\s*(?:\n|$)", text[:1200])
        if printed:
            programme = "BSCS" if printed[1] == "BS" else printed[1]
    # Applicability must be stated in the actual document; capture dates/URL years are insufficient.
    explicit = re.search(
        r"(?:scheme of study.{0,50}?|effective.{0,30}?|for semesters?\s+)(Fall|Spring)?\s*(20\d{2})\s*(onwards)?",
        text[:1800],
        re.I,
    )
    cohort, onwards, effective = None, False, None
    if explicit and topic == "curriculum":
        cohort = int(explicit[2])
        onwards = bool(explicit[3])
        effective = f"{explicit[1] or ''} {cohort}".strip()
    if not effective and topic in {"admissions", "fees", "timetable", "exam_schedule"}:
        explicit = re.search(
            r"\b(Fall|Spring)\s*(?:Semester[\s-]*)?[- ]?(20\d{2})\b",
            title + "\n" + text[:1500],
            re.I,
        )
        if explicit:
            effective = f"{explicit[1].title()} {explicit[2]}"
    # Never reuse legacy parser's guessed cohort or publication date.
    return {
        "topic": topic,
        "programme": programme,
        "cohort_start": cohort,
        "applies_onwards": int(onwards),
        "effective_term": effective,
    }


def import_one(
    store, path, uri, captured_at, expected_sha=None, mime="", official=False, ocr=False
):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 30_000_000:
        raise ValueError("Missing, symlinked or oversized original")
    checksum = digest(path.read_bytes())
    if expected_sha and checksum != expected_sha:
        raise ValueError("Original checksum differs from acquisition catalogue")
    title, parts, warnings = parse(path, mime, source_uri=uri)
    parser_version = PARSER_VERSION
    if not parts and ocr and path.suffix.lower() == ".pdf":
        title, parts, warnings = parse(path, mime, ocr=True, source_uri=uri)
        parser_version += "-ocr1"
    if not parts:
        raise ValueError("No searchable text; OCR or another parser required")
    joined = "\n".join(p.content for p in parts)
    meta = source_metadata(uri, title, joined)
    review = "observed_official" if official else "needs_review"
    if warnings or meta["topic"] in {
        "academic_policy",
        "admissions",
        "fees",
        "timetable",
        "exam_schedule",
        "curriculum",
    }:
        review = "needs_review"
    doc_id, version = digest(uri), digest(uri + checksum + parser_version)
    with store.connect() as c:
        c.execute(
            "INSERT OR IGNORE INTO document(id,uri,origin) VALUES(?,?,?)",
            (doc_id, uri, "official_archive" if official else "workspace_unverified"),
        )
        c.execute(
            """INSERT OR IGNORE INTO document_version
           (id,document_id,checksum,raw_path,parser_version,captured_at,published_at,title,programme,topic,effective_term,cohort_start,applies_onwards,review_status,warnings)
           VALUES(?,?,?,?,?,?,NULL,?,?,?,?,?,?,?,?)""",
            (
                version,
                doc_id,
                checksum,
                str(path.resolve()),
                parser_version,
                captured_at,
                title,
                meta["programme"],
                meta["topic"],
                meta["effective_term"],
                meta["cohort_start"],
                meta["applies_onwards"],
                review,
                json.dumps(warnings),
            ),
        )
        for idx, p in enumerate(parts):
            chunk_id = digest(version + str(idx) + p.content)
            if not c.execute("SELECT 1 FROM evidence_chunk WHERE id=?", (chunk_id,)).fetchone():
                c.execute(
                    "INSERT INTO evidence_chunk VALUES(?,?,?,?,?,?,?)",
                    (chunk_id, version, p.page, p.heading, p.content, p.semester, p.coordinates),
                )
                c.execute(
                    "INSERT INTO evidence_fts VALUES(?,?,?,?)",
                    (chunk_id, title, p.heading or "", p.content),
                )
            for link in p.resources:
                c.execute(
                    "INSERT OR IGNORE INTO evidence_resource VALUES(?,?,?)",
                    (chunk_id, link["url"], link["title"]),
                )
            if meta["topic"] == "curriculum" and meta["programme"] and p.semester:
                programme = meta["programme"]
                c.execute("INSERT OR IGNORE INTO program VALUES(?,?)", (programme, programme))
                c.execute(
                    "INSERT OR IGNORE INTO study_scheme VALUES(?,?,?,?,?)",
                    (version, version, programme, meta["cohort_start"], meta["applies_onwards"]),
                )
                c.execute("INSERT OR IGNORE INTO semester VALUES(?,?)", (version, p.semester))
                for r in course_rows(p):
                    c.execute("INSERT OR IGNORE INTO course VALUES(?,?)", (r["code"], r["title"]))
                    c.execute(
                        "INSERT OR IGNORE INTO scheme_course VALUES(?,?,?,?,?,?,?)",
                        (
                            version,
                            p.semester,
                            r["code"],
                            r["lecture"],
                            r["lab"],
                            r["total"],
                            chunk_id,
                        ),
                    )
    return {
        "uri": uri,
        "version_id": version,
        "chunks": len(parts),
        "review_status": review,
        "warnings": warnings,
        **meta,
    }


def import_archive(store, archive):
    results = []
    if not (archive / "catalogue.sqlite3").exists():
        return results
    conn = sqlite3.connect(f"file:{archive / 'catalogue.sqlite3'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    for row in conn.execute("SELECT v.* FROM resources r JOIN versions v USING(version_id)"):
        uri = row["url"]
        if urlsplit(uri).scheme != "https" or urlsplit(uri).hostname not in {
            "qau.edu.pk",
            "www.qau.edu.pk",
            "cs.qau.edu.pk",
        }:
            results.append(
                {
                    "uri": uri,
                    "status": "excluded",
                    "reason": "Not an allowlisted official public original",
                }
            )
            continue
        if any(
            x in uri.lower()
            for x in ["login", "signin", "logout", "lostpassword", "cdn-cgi", "wp-admin"]
        ):
            results.append(
                {"uri": uri, "status": "excluded", "reason": "Authentication/action endpoint"}
            )
            continue
        path = (archive / row["raw_path"]).resolve()
        try:
            if not path.is_relative_to(archive.resolve()):
                raise ValueError("Archive path traversal")
            results.append(
                {
                    "status": "parsed",
                    **import_one(
                        store, path, uri, row["first_seen_at"], row["raw_sha256"], official=True
                    ),
                }
            )
        except Exception as e:
            results.append({"uri": uri, "status": "failed", "reason": str(e)[:300]})
    conn.close()
    return results


def import_workspace(store):
    results = []
    excluded = {
        "frontend",
        "chatbot_v3",
        "deploy",
        "database",
        ".git",
        ".runtime",
        ".venv",
        "node_modules",
        "dist",
        "__pycache__",
        ".model-cache",
        "crawl-archive",
        "scraped",
        "source-archive",
    }
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if (
            set(relative.parts) & excluded
            or any(x.startswith(".") for x in relative.parts)
            or path.is_symlink()
        ):
            continue
        if (
            path.suffix.lower() not in {".pdf", ".docx", ".xlsx", ".html", ".txt"}
            or not path.is_file()
        ):
            continue
        if (
            path.name.startswith("requirements")
            or "test-results" in relative.parts
            or "docs" in relative.parts
            or "evaluation" in relative.parts
        ):
            continue
        uri = "workspace:///" + str(relative)
        try:
            results.append({"status": "parsed", **import_one(store, path, uri, now())})
        except Exception as e:
            results.append({"uri": uri, "status": "failed", "reason": str(e)[:300]})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=ROOT / "academic-data/crawl-archive")
    parser.add_argument("--workspace", action="store_true")
    args = parser.parse_args()
    store, run_id, started = Store(), str(uuid4()), now()
    results = import_archive(store, args.archive)
    if args.workspace:
        results.extend(import_workspace(store))
    report = {
        "run_id": run_id,
        "started_at": started,
        "finished_at": now(),
        "counts": dict(Counter(x["status"] for x in results)),
        "sources": results,
        "limitations": [
            "Archived originals are re-parsed; capture date is not current validation or publication date.",
            "High-risk and workspace sources await review; no production index was changed.",
        ],
    }
    with store.connect() as c:
        c.execute(
            "INSERT INTO ingestion_run VALUES(?,?,?,?)",
            (run_id, started, report["finished_at"], json.dumps(report)),
        )
    dest = settings().data_dir / "evaluation"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "ingestion.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "run_id": run_id,
                "counts": report["counts"],
                "chunks": len(store.chunks()),
                "awaiting_review": len(store.review_queue()),
            }
        )
    )


if __name__ == "__main__":
    main()
