"""Fresh page/layout-aware parsing. Originals and historical extractions are never edited."""

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

PARSER_VERSION = "v3-pdfplumber-html-3"


@dataclass
class Section:
    content: str
    page: int | None = None
    heading: str | None = None
    semester: int | None = None
    coordinates: str | None = None


def sections(text, page=None, prefix=None, coordinates=None):
    # Regex is used for document structure only, never student routing.
    result, lines, heading, semester = [], [], prefix, None
    for line in text.splitlines():
        match = re.match(r"^Semester\s+([1-9])\s*$", line.strip(), re.I)
        if match:
            if lines:
                result.append(Section("\n".join(lines), page, heading, semester, coordinates))
            lines, semester, heading = [line], int(match[1]), line.strip()
        else:
            lines.append(line)
    if lines and "\n".join(lines).strip():
        result.append(Section("\n".join(lines), page, heading, semester, coordinates))
    return result


def parse(path: Path, mime="", ocr=False):
    warnings, chunks, title = [], [], path.name
    if path.suffix.lower() == ".pdf" or "pdf" in mime:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            for n, page in enumerate(pdf.pages, 1):
                words = page.extract_words()
                semester_words = [w for w in words if w["text"].lower() == "semester"]
                two_columns = any(w["x0"] > page.width * 0.48 for w in semester_words) and any(
                    w["x0"] < page.width * 0.48 for w in semester_words
                )
                if two_columns:
                    # The 2023 gutter is asymmetric. Assign whole words, never clipped characters.
                    first_heading = min(w["top"] for w in semester_words)
                    header = page.crop((0, 0, page.width, first_heading - 1)).extract_text() or ""
                    chunks.extend(sections(header, n))
                    right_codes = [
                        w["x0"]
                        for w in words
                        if re.match(r"^[A-Z]{2,4}-\d{3}:?$", w["text"])
                        and w["x0"] > page.width * 0.40
                    ]
                    boundary = min(right_codes) - 2 if right_codes else page.width / 2
                    last_heading = max(w["top"] for w in semester_words)
                    footer_candidates = [
                        w["top"]
                        for w in words
                        if w["top"] > last_heading
                        and w["text"] in {"The", "Category"}
                        and w["x0"] < page.width * 0.45
                    ]
                    footer_top = min(footer_candidates) if footer_candidates else page.height
                    for left, right in [(0, boundary), (boundary, page.width)]:
                        selected = [
                            w
                            for w in words
                            if first_heading <= w["top"] < footer_top and left <= w["x0"] < right
                        ]
                        chunks.extend(
                            sections(
                                words_to_lines(selected),
                                n,
                                coordinates=str((left, first_heading, right, page.height)),
                            )
                        )
                    if footer_top < page.height:
                        footer = (
                            page.crop((0, footer_top - 1, page.width, page.height)).extract_text()
                            or ""
                        )
                        chunks.extend(sections(footer, n, prefix="Internship and credit summary"))
                else:
                    text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                    if text.strip():
                        chunks.extend(sections(text, n))
                    else:
                        if ocr:
                            import subprocess
                            import tempfile

                            with tempfile.TemporaryDirectory(prefix="qau-v3-ocr-") as temp:
                                image = Path(temp) / "page.png"
                                page.to_image(resolution=220).original.save(image)
                                output = subprocess.run(
                                    ["tesseract", str(image), "stdout", "-l", "eng", "--psm", "3"],
                                    capture_output=True,
                                    text=True,
                                    timeout=90,
                                    check=True,
                                )
                                if output.stdout.strip():
                                    chunks.extend(
                                        sections(
                                            output.stdout, n, prefix="OCR page — review required"
                                        )
                                    )
                            warnings.append(
                                f"page {n}: OCR extraction; numerical values and layout need review"
                            )
                        else:
                            warnings.append(
                                f"page {n}: no text; OCR required; excluded from evidence"
                            )
            warnings.append("PDF numerical/table extraction needs source review")
        if chunks:
            title = chunks[0].content.splitlines()[0][:180]
    elif path.suffix.lower() == ".docx":
        import zipfile
        from xml.etree import ElementTree as ET

        with zipfile.ZipFile(path) as z:
            if sum(x.file_size for x in z.infolist()) > 40_000_000:
                raise ValueError("DOCX decompression limit")
            tree = ET.fromstring(z.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            text = "\n".join(
                " ".join(t.text or "" for t in p.findall(".//w:t", ns))
                for p in tree.findall(".//w:p", ns)
            )
            chunks = sections(text)
            warnings.append("Workspace provenance and DOCX table extraction require review")
    elif path.suffix.lower() == ".xlsx":
        import openpyxl

        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for sheet in book:
            rows = list(sheet.iter_rows(values_only=True))
            for start in range(1, len(rows), 30):
                text = "\n".join(
                    " | ".join(str(v) if v is not None else "" for v in r)
                    for r in [rows[0]] + rows[start : start + 30]
                )
                chunks.append(
                    Section(
                        text,
                        heading=sheet.title,
                        coordinates=f"rows {start + 1}-{min(start + 30, len(rows))}",
                    )
                )
        warnings.append("Spreadsheet values and provenance require review")
        book.close()
    elif "html" in mime or path.suffix.lower() in {".html", ".htm"}:
        soup = BeautifulSoup(path.read_bytes(), "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else path.name
        for tag in soup(
            ["script", "style", "nav", "header", "footer", "form", "noscript", "aside"]
        ):
            tag.decompose()
        main = (
            soup.select_one(
                "article .entry-content, .entry-content, main, article, #content, .main-content"
            )
            or soup.body
            or soup
        )
        for table in main.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = tr.find_all(["th", "td"], recursive=False)
                if cells:
                    rows.append(" | ".join(x.get_text(" ", strip=True) for x in cells))
            # Keep the table together, including spanning row/column headers in original order.
            table.replace_with(soup.new_string("\n" + "\n".join(rows) + "\n"))
        heading, buf = title, []
        for el in main.children:
            if getattr(el, "name", None) in {"h1", "h2", "h3", "h4"}:
                if buf:
                    chunks.append(Section("\n".join(buf), heading=heading))
                heading, buf = el.get_text(" ", strip=True), []
            else:
                value = (
                    el.get_text("\n", strip=True) if hasattr(el, "get_text") else str(el).strip()
                )
                if value:
                    buf.append(value)
        if buf:
            chunks.append(Section("\n".join(buf), heading=heading))
    else:
        chunks = sections(path.read_text(errors="strict"))
    return title, split_large(chunks), warnings


def words_to_lines(words):
    rows = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if not rows or abs(rows[-1][0] - w["top"]) > 2:
            rows.append((w["top"], [w]))
        else:
            rows[-1][1].append(w)
    return "\n".join(
        " ".join(w["text"] for w in sorted(row, key=lambda w: w["x0"])) for _, row in rows
    )


def split_large(chunks, max_chars=4500):
    result = []
    for chunk in chunks:
        if len(chunk.content) <= max_chars or chunk.semester:
            result.append(chunk)
            continue
        # Preserve entire table with its header; never slice a table at a character boundary.
        if " | " in chunk.content:
            result.append(chunk)
            continue
        buf = []
        for line in chunk.content.splitlines():
            if sum(len(x) for x in buf) + len(line) > max_chars and buf:
                result.append(
                    Section(
                        "\n".join(buf), chunk.page, chunk.heading, chunk.semester, chunk.coordinates
                    )
                )
                buf = buf[-2:]
            buf.append(line)
        if buf:
            result.append(
                Section(
                    "\n".join(buf), chunk.page, chunk.heading, chunk.semester, chunk.coordinates
                )
            )
    return [c for c in result if c.content.strip()]


def course_rows(section):
    if not section.semester:
        return []
    rows = []
    for line in section.content.splitlines():
        match = re.match(
            r"^([A-Z]{2,4}-\d{3}):?\s+(.+?)\s+(?:GE|CC|DC|DE|MS|ES)\s+(\d)(?:\+(\d))?\s*$",
            line.strip(),
        )
        if match:
            code, title, lecture, lab = match.groups()
            rows.append(
                {
                    "code": code,
                    "title": title.strip(),
                    "lecture": int(lecture),
                    "lab": int(lab or 0),
                    "total": int(lecture) + int(lab or 0),
                }
            )
    return rows
