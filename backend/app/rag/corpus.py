"""Versioned, inspectable evidence corpus. No network calls during ingestion.

The scrape contains PDFs decoded as HTML/text. Those strings cannot be repaired:
use the original archived PDFs and report missing originals instead.
"""

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from xml.etree import ElementTree
from zipfile import ZipFile

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
CORPUS_VERSION = 3


def repair_typography(content: str) -> str:
    """Repair known UTF-8 punctuation decoded as Windows-1252 in old scrapes."""
    for broken, correct in {
        "â€™": "’",
        "â€˜": "‘",
        "â€œ": "“",
        "â€\u009d": "”",
        "â€“": "–",
        "â€”": "—",
        "Â ": " ",
    }.items():
        content = content.replace(broken, correct)
    return content


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = quote(unquote(parts.path), safe="/.-_").rstrip("/") or "/"
    return urlunsplit(("https", host, path, parts.query, ""))


def is_official_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        return (parts.scheme in {"https", "http"} and not parts.username and not parts.password
                and parts.port in {None, 80, 443}
                and (host == "qau.edu.pk" or host.endswith(".qau.edu.pk")))
    except ValueError:
        return False


def text_problem(content: str) -> str | None:
    if content.lstrip().startswith("%PDF-") or re.search(r"\b(?:endobj|FlateDecode)\b", content):
        return "binary_pdf_decoded_as_text"
    if not content.strip():
        return "empty_text"
    if content.count("\ufffd") / max(len(content), 1) > 0.005:
        return "corrupt_text"
    if sum(ord(c) < 32 and c not in "\n\r\t" for c in content) > len(content) * 0.01:
        return "binary_control_characters"
    return None


class HTMLText(HTMLParser):
    """Preserve table cell relationships and skip navigation and active content."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0
        self.cell_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "header", "footer", "aside", "noscript"}:
            self.hidden += 1
        if not self.hidden:
            if tag in {"td", "th"}:
                self.cell_depth += 1
            if tag in {"p", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br"}:
                self.parts.append(" " if self.cell_depth and tag != "tr" else "\n")
            elif tag in {"td", "th"}:
                self.parts.append(" | ")

    def handle_endtag(self, tag):
        if (
            tag in {"script", "style", "nav", "header", "footer", "aside", "noscript"}
            and self.hidden
        ):
            self.hidden -= 1
        if not self.hidden and tag in {"p", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "li"}:
            self.parts.append(" " if self.cell_depth and tag != "tr" else "\n")
        if not self.hidden and tag in {"td", "th"}:
            self.cell_depth = max(0, self.cell_depth - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(re.sub(r"\s+", " ", data))


def scoped_sections(content: str, category: str) -> list[tuple[str | None, str, str | None]]:
    """Keep degree sections and FAQ questions attached to their own answers."""
    lines = content.splitlines()
    degree = re.compile(r"^(BS|MPhil|PhD|MS)\s*\(([^)]+)\)(?:\s*-.*)?$", re.I)
    result = []
    body: list[str] = []
    heading, program = None, None
    summary_header = False
    for index, line in enumerate(lines):
        if summary_header and line.strip() == heading:
            body.append(line)
            summary_header = False
            continue
        match = degree.match(line.strip()) if category in {"admissions", "programme"} else None
        summary = (
            category == "programme"
            and not match
            and index + 1 < len(lines)
            and re.match(r"^(BS|MS|MPhil|PhD)\s+.*(?:years?|semesters?|credit hours)", line, re.I)
        )
        if summary:
            match = degree.match(lines[index + 1].strip())
            summary_header = match is not None
        faq = line.strip().endswith("?") and len(line.strip()) < 220
        fee_heading = category == "fees" and line.lower().startswith("fee structure")
        if match or faq or fee_heading:
            if body:
                result.append((heading, "\n".join(body), program))
            heading = lines[index + 1].strip() if summary_header else line.strip()
            if match:
                level, subject = match.group(1).lower(), match.group(2).lower()
                program = {"bs": "BSCS", "mphil": "MPhil", "phd": "PhD"}.get(
                    level, "MS-DS" if "data" in subject else "MS-IST"
                )
            body = [line]
        else:
            body.append(line)
    if body:
        result.append((heading, "\n".join(body), program))
    return result


def clean_text(content: str) -> str:
    lines = []
    boilerplate = {
        "Department of Computer Sciences",
        "Quaid-i-Azam University, Islamabad",
        "Quaid-i-Azam University Islamabad",
        "|",
        "Programme Details",
        "Apply Online",
        "Admission Details",
        "Copyright © Department of Computer Sciences",
    }
    for line in repair_typography(content).replace("\x00", "").splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line and line not in boilerplate and (not lines or line != lines[-1]):
            lines.append(line)
    return "\n".join(lines)


def extract_html(content: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "html.parser")
    main = soup.select_one(".gramotech-content-area, main, article")
    if main is not None:
        editors = main.select(".elementor-widget-text-editor")
        selected = "\n".join(str(node) for node in editors) if editors else str(main)
    else:
        selected = str(soup.body or soup)
    parser = HTMLText()
    parser.feed(selected)
    return "".join(parser.parts)


def extract_docx(path: Path) -> str:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    body = root.find(namespace + "body")
    lines = []
    for node in body if body is not None else []:
        if node.tag == namespace + "tbl":
            for row in node.findall(namespace + "tr"):
                cells = [
                    " ".join(t.text or "" for t in cell.iter(namespace + "t"))
                    for cell in row.findall(namespace + "tc")
                ]
                lines.append(" | ".join(cells))
        else:
            lines.append("".join(t.text or "" for t in node.iter(namespace + "t")))
    return "\n".join(lines)


def split_passages(content: str, size: int = 1000, overlap: int = 140) -> list[str]:
    """Prefer whole lines/sentences, enforce a bound even for a single long line."""
    if size < 100 or not 0 <= overlap < size:
        raise ValueError("size must be >= 100 and 0 <= overlap < size")
    text = content.strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            candidates = [text.rfind("\n", start, end), text.rfind(". ", start, end)]
            boundary = max(candidates)
            if boundary > start + size // 2:
                end = boundary + 1
            else:
                boundary = text.rfind(" ", start, end)
                if boundary > start + size // 2:
                    end = boundary
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end == len(text):
            break
        next_start = max(start + 1, end - overlap)
        # Begin at a word boundary; never grow beyond the configured bound.
        boundary = text.find(" ", next_start, end)
        start = boundary + 1 if boundary >= 0 else end
    return chunks


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    document_id: str
    title: str
    content: str
    source_url: str
    source_code: str = ""
    local_path: str = ""
    category: str = "general"
    program: str = "ALL"
    chunk_index: int = 0
    page_number: int | None = None
    section_title: str | None = None
    captured_at: str | None = None
    verification_status: str = "archived"
    effective_term: str | None = None
    is_time_sensitive: bool = False
    evidence_type: str = "source"
    source_version_id: str = ""
    source_sha256: str = ""
    extraction_method: str = ""

    def citation(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != "content"}


def corpus_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BACKEND_ROOT / path


def load_corpus(path: Path) -> list[EvidenceChunk]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return [EvidenceChunk(**json.loads(line)) for line in stream if line.strip()]


def calculated_credit_summary(title: str, content: str) -> str | None:
    hours = [int(value) for value in re.findall(r"Credit\s+Hours\s+(\d+)", content, re.I)]
    if len(hours) != 8:
        return None
    return (
        f"{title} — calculated semester credit summary.\n"
        + "\n".join(f"Semester {i}: {value} credit hours" for i, value in enumerate(hours, 1))
        + f"\nCalculated total: {' + '.join(map(str, hours))} = {sum(hours)} credit hours.\n"
        + "Method: sum the eight semester Credit Hours values printed on the cited PDF page. "
        "This is a derived calculation, not a separately published total; "
        "zero-credit requirements remain separate."
    )


def build_corpus(
    root: Path = PROJECT_ROOT, crawl_archive: Path | None = None, *, approved_only: bool = False
) -> tuple[list[EvidenceChunk], dict]:
    report = {
        "version": CORPUS_VERSION,
        "scraped_pages": 0,
        "duplicates": 0,
        "rejected": [],
        "documents": [],
        "warnings": [],
        "crawl_versions": 0,
    }
    registry_path = root / "academic-data/source-registry/source_inventory.csv"
    if registry_path.exists():
        with registry_path.open(encoding="utf-8") as stream:
            registry = list(csv.DictReader(stream))
    else:
        registry = []
    sources = {canonical_url(r["source_url"]): r for r in registry if r["source_url"]}
    chunks: list[EvidenceChunk] = []
    seen: set[tuple] = set()
    archived_url_terms: dict[str, set] = {}

    def add(title, content, url, local_path, metadata, page=None, document_id=None):
        content = clean_text(content)
        problem = text_problem(content)
        if problem:
            report["rejected"].append({"source": local_path or url, "reason": problem})
            return
        digest = hashlib.sha256(content.encode()).hexdigest()
        identity = (
            canonical_url(url) if url else local_path,
            metadata.get("effective_term"),
            digest,
        )
        if identity in seen:
            report["duplicates"] += 1
            return
        seen.add(identity)
        doc_id = (
            document_id
            or hashlib.sha256((canonical_url(url) if url else local_path).encode()).hexdigest()[:24]
        )
        passages = []
        for heading, section, program in scoped_sections(content, metadata.get("category")):
            section_size = max(500, 999 - len(heading[:280]) - 1) if heading else 1000
            for piece in split_passages(section, size=section_size):
                if len(piece.strip()) < 100:
                    continue
                # Repeating a heading is deliberate contextual metadata, not an
                # invented fact; it prevents answer fragments losing their scope.
                if heading and not piece.startswith(heading):
                    piece = heading[:280] + "\n" + piece
                passages.append((piece, heading, program))
        for i, (passage, heading, program) in enumerate(passages):
            problem = text_problem(passage)
            if problem:
                report["rejected"].append(
                    {"source": local_path or url, "page": page, "chunk_index": i, "reason": problem}
                )
                continue
            chunk_id = hashlib.sha256(f"{doc_id}:{page}:{i}:{passage}".encode()).hexdigest()[:24]
            scoped_metadata = {**metadata, "section_title": heading}
            if program:
                scoped_metadata["program"] = program
            chunks.append(
                EvidenceChunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    title=title,
                    content=passage,
                    source_url=canonical_url(url) if url else "",
                    local_path=local_path,
                    chunk_index=i,
                    page_number=page,
                    **scoped_metadata,
                )
            )
        report["documents"].append(
            {
                "title": title,
                "url": url,
                "page": page,
                "characters": len(content),
                "chunks": len(passages),
            }
        )

    # Archive originals and parser outputs remain immutable. Search uses the
    # latest observation for each URL/cohort, preserving distinct old cohorts.
    archive_root = crawl_archive or root / "academic-data/crawl-archive"
    if (archive_root / "catalogue.sqlite3").is_file():
        from app.ingestion.archive import SourceArchive

        archive = SourceArchive(archive_root)
        try:
            for version in (
                archive.approved_documents() if approved_only else archive.corpus_documents()
            ):
                document = version["document"]
                url = version["url"]
                provided = (
                    url.startswith("provided:///")
                    and document["metadata"]["verification_status"] == "provided_unverified"
                )
                if not is_official_url(url) and not provided:
                    report["rejected"].append({"source": url, "reason": "non_official_source"})
                    continue
                report["crawl_versions"] += 1
                parsed_metadata = document["metadata"]
                if document["pages"]:
                    archived_url_terms.setdefault(canonical_url(url), set()).add(
                        parsed_metadata["effective_term"]
                    )
                metadata = {
                    key: parsed_metadata[key]
                    for key in (
                        "category",
                        "program",
                        "effective_term",
                        "verification_status",
                        "is_time_sensitive",
                    )
                }
                metadata.update(
                    source_code="CRAWL-" + version["version_id"][:12],
                    source_version_id=version["version_id"],
                    source_sha256=version["raw_sha256"],
                    captured_at=(
                        parsed_metadata.get("source_captured_at") or version["first_seen_at"]
                    ),
                )
                if approved_only:
                    metadata["verification_status"] = "approved"
                report["warnings"].extend(
                    {"source": url, **warning} for warning in document["warnings"]
                )
                for page in document["pages"]:
                    add(
                        document["title"],
                        page["content"],
                        "" if provided else url,
                        str(archive_root / version["raw_path"]),
                        {**metadata, "extraction_method": page["extraction_method"]},
                        page=page["page_number"],
                        document_id=version["version_id"],
                    )
                    if metadata["category"] == "curriculum":
                        summary = calculated_credit_summary(document["title"], page["content"])
                        if summary:
                            add(
                                document["title"] + " (calculated credit total)",
                                summary,
                                url,
                                str(archive_root / version["raw_path"]),
                                {**metadata, "evidence_type": "derived_arithmetic"},
                                page=page["page_number"],
                                document_id=version["version_id"],
                            )
        finally:
            archive.close()

    scrape = root / "academic-data/scraped/cs_website_full.json"
    pages = (
        json.loads(scrape.read_text(encoding="utf-8"))
        if scrape.exists() and not approved_only
        else []
    )
    report["scraped_pages"] = len(pages)
    seen_urls = set()
    for page in pages:
        url = canonical_url(page["url"])
        if url in archived_url_terms:
            report["duplicates"] += 1
            continue
        problem = text_problem(page.get("content", ""))
        if problem:
            report["rejected"].append({"source": url, "reason": problem})
            continue
        if not is_official_url(url):
            report["rejected"].append({"source": url, "reason": "non_official_source"})
            continue
        if url in seen_urls:
            report["duplicates"] += 1
            continue
        seen_urls.add(url)
        r = sources.get(url, {})
        sensitive = "admissions" in url or url == "https://cs.qau.edu.pk/"
        category = r.get("category") or (
            "faculty"
            if "faculty" in url
            else "research"
            if "research" in url
            else "admissions"
            if sensitive
            else "programme"
        )
        program = r.get("program", "ALL")
        if program == "ALL":
            route = urlsplit(url).path.lower()
            program = {
                "/bs.php": "BSCS",
                "/bs.html": "BSCS",
                "/mphil.php": "MPhil",
                "/phd.php": "PhD",
                "/ms-ds.php": "MS-DS",
                "/ms.php": "MS-IST",
            }.get(route, "ALL")
        term = (
            re.search(r"\b(Fall|Spring)\s+(20\d{2})\b", page["content"], re.I)
            if sensitive
            else None
        )
        metadata = {
            "category": category,
            "source_code": r.get(
                "source_id", "SCRAPE-" + hashlib.sha256(url.encode()).hexdigest()[:8]
            ),
            "program": program,
            "captured_at": page.get("timestamp"),
            "verification_status": "archived",
            "is_time_sensitive": sensitive,
            "effective_term": term.group(0) if term else None,
        }
        extracted_pages = page.get("pages")
        if extracted_pages:
            for extracted in extracted_pages:
                add(
                    page["title"],
                    extracted["content"],
                    url,
                    page.get("local_path") or str(scrape.relative_to(root)),
                    metadata,
                    page=extracted["page_number"],
                )
        else:
            add(page["title"], page["content"], url, str(scrape.relative_to(root)), metadata)

    # Read archived originals, never the corrupted PDF strings from the scrape.
    archived_paths = set()
    for r in [] if approved_only else registry:
        relative = r.get("local_path", "")
        url = r.get("source_url", "")
        path = root / relative
        if not relative or not url or not path.is_file() or not is_official_url(url):
            continue
        if path.suffix.lower() not in {".pdf", ".html"}:
            continue
        if str(path.resolve()) in archived_paths:
            report["duplicates"] += 1
            continue
        archived_paths.add(str(path.resolve()))
        metadata = {
            "category": r["category"],
            "program": r.get("program", "ALL"),
            "source_code": r["source_id"],
            "captured_at": r.get("last_verified_at") or None,
            "verification_status": r.get("verification_status", "archived"),
            "effective_term": r.get("effective_from") or None,
            "is_time_sensitive": r.get("is_time_sensitive", "false").lower() == "true",
        }
        terms = archived_url_terms.get(canonical_url(url), set())
        if terms and (not metadata["effective_term"] or metadata["effective_term"] in terms):
            report["duplicates"] += 1
            continue
        try:
            if path.suffix.lower() == ".pdf":
                from pypdf import PdfReader

                for n, page in enumerate(PdfReader(path).pages, 1):
                    content = page.extract_text(extraction_mode="layout") or ""
                    if len(content.strip()) < 30:
                        report["warnings"].append(
                            {"source": relative, "page": n, "reason": "needs_ocr_or_empty_page"}
                        )
                        continue
                    add(r["title"], content, url, relative, metadata, page=n)
                    if r["category"] == "curriculum":
                        summary = calculated_credit_summary(r["title"], content)
                        if summary:
                            add(
                                r["title"] + " (calculated credit total)",
                                summary,
                                url,
                                relative,
                                {**metadata, "evidence_type": "derived_arithmetic"},
                                page=n,
                            )
            else:
                add(
                    r["title"],
                    extract_html(path.read_text(encoding="utf-8")),
                    url,
                    relative,
                    metadata,
                )
        except ImportError:
            raise
        except Exception as exc:
            report["rejected"].append({"source": relative, "reason": type(exc).__name__})
    provided = root / "BSCS Scheme of Study with PreRequisites.docx"
    if provided.is_file() and not approved_only:
        add(
            "Provided BSCS Fall 2021 scheme and prerequisite matrix (unverified)",
            extract_docx(provided),
            "",
            provided.name,
            {
                "category": "prerequisites",
                "program": "BSCS",
                "source_code": "PROVIDED-BSCS-2021",
                "verification_status": "provided_unverified",
                "effective_term": "Fall 2021",
                "is_time_sensitive": False,
            },
        )
    unique_chunks = {}
    for chunk in chunks:
        if chunk.chunk_id in unique_chunks:
            report["duplicates"] += 1
        # Prefer the registry-backed copy if an identical passage occurs in
        # both the scrape and an archived HTML snapshot.
        unique_chunks[chunk.chunk_id] = chunk
    chunks = list(unique_chunks.values())
    report["unique_documents"] = len({c.document_id for c in chunks})
    report["chunks"] = len(chunks)
    report["chunk_characters"] = {
        "min": min((len(c.content) for c in chunks), default=0),
        "max": max((len(c.content) for c in chunks), default=0),
        "mean": round(sum(len(c.content) for c in chunks) / max(len(chunks), 1)),
    }
    return chunks, report
