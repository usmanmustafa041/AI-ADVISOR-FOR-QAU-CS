"""Known documents: authoritative titles and honest freshness notes.

The department publishes a small, stable set of PDFs. Naming them explicitly (instead of
trusting the first line of extracted text) gives citations students can recognise, and the
``note`` travels with every chunk so the assistant can caveat dated sources.
"""

from __future__ import annotations

from advisor.ingest.model import Document

# suffix of the URL path -> (title, note)
KNOWN_DOCUMENTS: dict[str, tuple[str, str]] = {
    "/doc/Rules-BS.pdf": (
        "QAU Regulations Relating to BS Programmes (University Calendar 2012)",
        "Approved 2011 and printed in the 2012 University Calendar; later amendments may exist. "
        "Students should confirm with the department office.",
    ),
    "/doc/Rules-MPhil.pdf": (
        "QAU Regulations for the MPhil Programme (University Calendar 2012)",
        "From the 2012 University Calendar; later amendments may exist.",
    ),
    "/doc/Rules-PhD.pdf": (
        "QAU Regulations for the PhD Programme (University Calendar 2012)",
        "From the 2012 University Calendar; later amendments may exist.",
    ),
    "/doc/cs-mphil-phd-test-sample.pdf": (
        "MPhil / PhD (Computer Science) Sample Admission Test",
        "Sample questions from earlier admission tests; the real test may differ.",
    ),
    "/doc/ds_sample_test.pdf": (
        "MS (Data Science / Information Science & Technology) Sample Admission Test",
        "Sample questions from earlier admission tests; the real test may differ.",
    ),
    "/doc/ist_sample_test.pdf": (
        "MS (Data Science / Information Science & Technology) Sample Admission Test",
        "Sample questions from earlier admission tests; the real test may differ.",
    ),
    "/MS_ist.pdf": (
        "MS (Information Science & Technology) Programme Brochure",
        "Older brochure (dated 2018); faculty and details may be out of date.",
    ),
    "/uploads/documents/25301760be625825_1788575827.pdf": (
        "Information about Important Facilities at QAU",
        "",
    ),
    "/uploads/documents/b3e3289278471784_1790590705.pdf": (
        "CS Department Timetable — Fall 2026 (effective 28 September 2026)",
        "Timetables change; the PDF on the department website is authoritative.",
    ),
    "/uploads/documents/df536384e9b9dbe3_1788575182.pdf": (
        "QAU Schedule for Fall Semester 2026 (Directorate of Academics, 17 Aug 2026)",
        "Scanned notice read with OCR; dates should be confirmed against the Events page.",
    ),
}


def apply_registry(doc: Document) -> Document:
    for suffix, (title, note) in KNOWN_DOCUMENTS.items():
        if doc.url.endswith(suffix):
            old = doc.title
            doc.title = title
            if note:
                doc.meta["note"] = note
            for b in doc.blocks:
                if b.heading.startswith(old):
                    b.heading = title + b.heading[len(old):]
            break
    return doc
