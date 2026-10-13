"""Conservative extraction: unknown fields stay null and retain source text.

Line references describe normalized extracted text, never the PDF's visual lines.
OCR is opt-in and uses an installed Tesseract via PyMuPDF; nothing is downloaded.
"""

import re
from io import BytesIO
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.rag.corpus import clean_text, extract_html, text_problem

PARSER_VERSION = 4
COURSE_CODE = re.compile(r"\b([A-Z]{2,4})[ -]?(\d{3})\b", re.I)
TERM = re.compile(r"\b(Fall|Spring|Summer)\s*[- ]\s*(20\d{2})\b", re.I)


def normalize_code(value: str) -> str | None:
    match = COURSE_CODE.fullmatch(value.strip())
    return f"{match[1].upper()}-{match[2]}" if match else None


def credit_hours(value: str) -> tuple[int | None, int | None, int | None]:
    """Return total/lecture/lab only for unambiguous published notation."""
    value = value.strip()
    if re.fullmatch(r"\d{1,2}", value):
        total = int(value)
        return (total, None, None) if total <= 12 else (None, None, None)
    match = re.fullmatch(r"(\d)\s*\+\s*(\d)", value)
    if match:
        lecture, lab = map(int, match.groups())
        return lecture + lab, lecture, lab
    match = re.fullmatch(r"(\d{1,2})\s*\(\s*(\d)\s*\+\s*(\d)\s*\)", value)
    if match:
        total, lecture, lab = map(int, match.groups())
        if total == lecture + lab and total <= 12:
            return total, lecture, lab
    return None, None, None


def document_metadata(title: str, url: str, content: str) -> dict:
    identity = title + " " + unquote(urlsplit(url).path)
    lower = identity.lower()
    category = "general"
    for pattern, label in (
        (r"scheme|curricul", "curriculum"),
        (r"time.?table", "timetable"),
        (r"date.?sheet|exam.*schedule", "exam_schedule"),
        (r"fee|tuition", "fees"),
        (r"semester.?schedule|calendar|registration", "registration"),
        (r"rule|regulation|polic", "academic_policy"),
        (r"faculty|profile", "faculty"),
        (r"admission", "admissions"),
        (r"research", "research"),
        (r"programme|program|academics|bs\.(?:php|html)|mphil|phd|ms[-_]", "programme"),
    ):
        if re.search(pattern, lower):
            category = label
            break
    if category == "general":
        # PDF metadata often contains only a Word filename such as TT_v7.docx.
        # An explicit opening heading establishes type; arbitrary body dates do not.
        header = "\n".join(content.splitlines()[:3])
        if re.search(r"^\s*time\s*table\b", header, re.I | re.M):
            category = "timetable"
        elif re.search(r"^\s*(?:date\s*sheet|examination schedule)\b", header, re.I | re.M):
            category = "exam_schedule"
    program = "ALL"
    for pattern, label in (
        (r"\bph\.?d\b", "PhD"),
        (r"\bm\.?phil\b", "MPhil"),
        (r"ms[-_ ]?ds|\bms\b.*data science", "MS-DS"),
        (r"\bist\b|information science", "MS-IST"),
        (r"\bbs\b|\bbscs\b|bachelor", "BSCS"),
    ):
        if re.search(pattern, lower.replace("_", " ")):
            program = label
            break
    # A date mentioned in the body may describe an unrelated event. Only an
    # explicit applicability label can supply a term from body text.
    terms = set(f"{m[1].title()} {m[2]}" for m in TERM.finditer(identity))
    applicability = re.findall(
        r"(?:applicable\s+(?:to|from)|effective\s+(?:from|for)|admission\s+batch|batch|w\.e\.f\.?)"
        r"\s*[:\-]?\s*((?:Fall|Spring|Summer)\s*[- ]\s*20\d{2})",
        content,
        re.I,
    )
    for label in applicability:
        match = TERM.search(label)
        if match:
            terms.add(f"{match[1].title()} {match[2]}")
    term = next(iter(terms)) if len(terms) == 1 else None
    if not terms and category in {"timetable", "exam_schedule", "registration"}:
        for line in content.splitlines()[:8]:
            if re.search(r"time.?table|dateshee+t|schedule|calendar", line, re.I):
                terms.update(f"{m[1].title()} {m[2]}" for m in TERM.finditer(line))
        term = next(iter(terms)) if len(terms) == 1 else None
    if not terms and category == "curriculum":
        years = set(re.findall(r"\b20\d{2}\b", identity))
        term = next(iter(years)) if len(years) == 1 else None
    return {
        "category": category,
        "program": program,
        "effective_term": term,
        "applicability_candidates": sorted(terms),
        "publication_date": None,
        "verification_status": "archived",
        "is_time_sensitive": category
        in {"fees", "admissions", "timetable", "exam_schedule", "registration"}
        or urlsplit(url).path in {"", "/"},
    }


def structured_records(pages: list[dict], metadata: dict) -> list[dict]:
    """Extract explicit pipe-delimited course columns and auditable source items.

    PDF columns without reliable headers remain text. Sequencing is never
    interpreted as a prerequisite. A missing prerequisite column means unknown.
    """
    records = []
    aliases = {
        "course code": "course_code",
        "code": "course_code",
        "course title": "course_name",
        "course name": "course_name",
        "credit hours": "credits",
        "credit hour": "credits",
        "credits": "credits",
        "cr. hrs.": "credits",
        "prerequisites": "prerequisites",
        "prerequisite": "prerequisites",
        "pre-requisites": "prerequisites",
        "semester": "semester",
        "category": "category",
        "day": "day",
        "time": "time",
        "timing": "time",
        "room": "room",
        "venue": "room",
        "instructor": "instructor",
        "teacher": "instructor",
        "section": "section",
    }
    for page in pages:
        headers = []
        for number, line in enumerate(page["content"].splitlines(), 1):
            provenance = {
                "page_number": page["page_number"],
                "line_start": number,
                "line_end": number,
                "quote": line,
                "extraction_method": page["extraction_method"],
            }
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            proposed = [aliases.get(c.lower()) for c in cells]
            if "course_code" in proposed and (
                "course_name" in proposed or ("day" in proposed and "time" in proposed)
            ):
                headers = proposed
                continue
            if len(cells) > 1 and headers and len(cells) == len(headers):
                values = {k: v for k, v in zip(headers, cells, strict=True) if k}
                code = normalize_code(values.get("course_code", ""))
                if code:
                    if metadata["category"] in {"timetable", "exam_schedule"} and {
                        "day",
                        "time",
                    }.issubset(values):
                        records.append(
                            {
                                "record_type": "timetable_entry",
                                "course_code": code,
                                "course_name": values.get("course_name"),
                                "day_raw": values["day"],
                                "time_raw": values["time"],
                                "room": values.get("room"),
                                "instructor": values.get("instructor"),
                                "section": values.get("section"),
                                "effective_term": metadata.get("effective_term"),
                                "requires_review": True,
                                "source": provenance,
                            }
                        )
                        continue
                    total, lecture, lab = credit_hours(values.get("credits", ""))
                    semester = values.get("semester", "")
                    records.append(
                        {
                            "record_type": "course",
                            "course_code": code,
                            "course_name": values.get("course_name"),
                            "credit_hours": total,
                            "lecture_hours": lecture,
                            "lab_hours": lab,
                            "credit_hours_raw": values.get("credits"),
                            "semester": int(semester) if semester.isdigit() else None,
                            "category": values.get("category"),
                            "prerequisites_raw": values.get("prerequisites"),
                            "prerequisites": (
                                sorted(
                                    {
                                        f"{m[1].upper()}-{m[2]}"
                                        for m in COURSE_CODE.finditer(values["prerequisites"])
                                    }
                                )
                                if "prerequisites" in values
                                else None
                            ),
                            "prerequisite_logic": "preserved_in_raw_text",
                            "source": provenance,
                        }
                    )
                    continue
            if len(cells) > 1:
                records.append({"record_type": "table_row", "cells": cells, "source": provenance})
            emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", line)
            if metadata["category"] == "faculty" and emails:
                records.append(
                    {
                        "record_type": "faculty_contact",
                        "name": None,
                        "public_emails": sorted(set(emails)),
                        "source": provenance,
                    }
                )
            if metadata["category"] in {"academic_policy", "registration", "exam_schedule"}:
                if len(line) >= 30:
                    records.append(
                        {
                            "record_type": "policy_item"
                            if metadata["category"] == "academic_policy"
                            else "calendar_item",
                            "description": line,
                            "date_mentions": re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", line),
                            "effective_date": None,
                            "source": provenance,
                        }
                    )
    return records


def pdf_course_records(layout: str, content: str, page_number: int) -> list[dict]:
    """Recognize explicit code:title/category/credit rows in digital PDF layouts.

    Side-by-side semester columns are assigned only when both semester headings
    are present. Other layouts remain text; no prerequisite is inferred.
    """
    records, semesters = [], []
    normalized_lines = content.splitlines()
    pattern = re.compile(
        r"\b([A-Z]{2,4})[ -](\d{3}):\s*(.+?)\s{2,}([A-Z]{2})\s+(\d(?:\s*\+\s*\d)?)"
        r"(?=\s{2,}|$)"
    )
    for line in layout.splitlines():
        headings = list(re.finditer(r"\bSemester\s+(\d{1,2})\b", line, re.I))
        if headings:
            semesters = [(m.start(), int(m[1])) for m in headings if 1 <= int(m[1]) <= 12]
            continue
        quote = clean_text(line)
        if not quote or quote not in normalized_lines:
            continue
        for match in pattern.finditer(line):
            total, lecture, lab = credit_hours(match[5])
            if total is None:
                continue
            semester = (
                min(semesters, key=lambda pair: abs(pair[0] - match.start()))[1]
                if semesters
                else None
            )
            records.append(
                {
                    "record_type": "course",
                    "course_code": f"{match[1]}-{match[2]}",
                    "course_name": match[3].strip(),
                    "category": match[4],
                    "credit_hours": total,
                    "lecture_hours": lecture,
                    "lab_hours": lab,
                    "credit_hours_raw": match[5],
                    "semester": semester,
                    "prerequisites": None,
                    "prerequisites_raw": None,
                    "prerequisite_logic": "unknown",
                    "requires_review": True,
                    "source": {
                        "page_number": page_number,
                        "line_start": normalized_lines.index(quote) + 1,
                        "line_end": normalized_lines.index(quote) + 1,
                        "quote": quote,
                        "extraction_method": "pdf_layout_columns",
                    },
                }
            )
    return records


def parse_document(raw: bytes, url: str, mime_type: str, *, ocr: bool = False) -> dict:
    warnings, pages, links, pdf_records = [], [], [], []
    filename = unquote(urlsplit(url).path.rsplit("/", 1)[-1]) or url
    title = filename
    publication_date = None
    if raw.lstrip().startswith(b"%PDF-"):
        mime_type = "application/pdf"
        reader = PdfReader(BytesIO(raw))
        if len(reader.pages) > 500:
            raise ValueError("PDF exceeds 500-page extraction limit")
        title = str((reader.metadata or {}).get("/Title") or filename)
        for number, page in enumerate(reader.pages, 1):
            layout = page.extract_text(extraction_mode="layout") or ""
            text = clean_text(layout)
            method = "pdf_text"
            if len(text) < 30 or text_problem(text):
                if ocr:
                    # Optional dependency with a different licence; see the guide.
                    import pymupdf

                    with pymupdf.open(stream=raw, filetype="pdf") as document:
                        pdf_page = document.load_page(number - 1)
                        textpage = pdf_page.get_textpage_ocr(language="eng", dpi=150, full=True)
                        text = clean_text(pdf_page.get_text(textpage=textpage))
                    method = "tesseract_ocr"
                else:
                    warnings.append({"page": number, "reason": "needs_ocr_or_empty_page"})
            problem = text_problem(text)
            if problem:
                warnings.append({"page": number, "reason": problem})
                continue
            pages.append({"page_number": number, "content": text, "extraction_method": method})
            if method == "pdf_text":
                pdf_records.extend(pdf_course_records(layout, text, number))
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from xml.etree import ElementTree
        from zipfile import ZipFile

        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with ZipFile(BytesIO(raw)) as package:
            if sum(i.file_size for i in package.infolist()) > 50 * 1024 * 1024:
                raise ValueError("DOCX expanded content exceeds extraction limit")
            xml = package.read("word/document.xml")
            if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                raise ValueError("DOCX entity declarations are unsupported")
            body = ElementTree.fromstring(xml).find(namespace + "body")
            lines = []
            for node in body if body is not None else []:
                if node.tag == namespace + "tbl":
                    for row in node.findall(namespace + "tr"):
                        lines.append(
                            " | ".join(
                                " ".join(t.text or "" for t in cell.iter(namespace + "t"))
                                for cell in row.findall(namespace + "tc")
                            )
                        )
                else:
                    lines.append(" ".join(t.text or "" for t in node.iter(namespace + "t")))
            pages.append(
                {
                    "page_number": None,
                    "content": clean_text("\n".join(lines)),
                    "extraction_method": "docx_xml",
                }
            )
        warnings.append({"page": None, "reason": "docx_has_no_stable_pdf_page_numbers"})
    elif mime_type == "text/plain":
        text = clean_text(raw.decode("utf-8-sig"))
        if text_problem(text):
            raise ValueError("Unsupported or corrupt plain text")
        pages.append({"page_number": None, "content": text, "extraction_method": "plain_text"})
    elif mime_type.split(";", 1)[0].lower() in {"text/html", "application/xhtml+xml"}:
        soup = BeautifulSoup(raw, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else filename
        base = soup.find("base", href=True)
        base_url = urljoin(url, base["href"]) if base else url
        # Collect before extracting text so footer/navigation links remain discoverable.
        links = sorted({urljoin(base_url, a["href"]) for a in soup.find_all("a", href=True)})
        published = soup.select_one(
            'meta[property="article:published_time"], meta[name="date"], time[datetime]'
        )
        publication_date = (
            (published.get("content") or published.get("datetime")) if published else None
        )
        text = clean_text(extract_html(str(soup)))
        if text_problem(text):
            warnings.append({"page": None, "reason": text_problem(text)})
        else:
            pages.append({"page_number": None, "content": text, "extraction_method": "html"})
    else:
        raise ValueError(f"Unsupported content type: {mime_type}")
    content = "\n\n".join(page["content"] for page in pages)
    if mime_type == "application/pdf" and pages:
        for line in pages[0]["content"].splitlines()[:5]:
            if re.search(r"scheme of study|curriculum", line, re.I) and re.search(
                r"\bbs\b|\bbscs\b|\bmphil\b|\bphd\b|\bms\b", line, re.I
            ):
                title = line[:300]
                break
    metadata = document_metadata(title, url, content)
    metadata["publication_date"] = publication_date
    return {
        "parser_version": PARSER_VERSION,
        "title": title,
        "mime_type": mime_type,
        "metadata": metadata,
        "pages": pages,
        "links": links,
        "records": structured_records(pages, metadata) + pdf_records,
        "warnings": warnings,
    }
