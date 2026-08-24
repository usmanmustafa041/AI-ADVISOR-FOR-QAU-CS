"""
Timetable + Scheme of Study PDF ingestion script.

Parses the real QAU CS timetable and scheme PDFs, then loads data into:
  - source_records
  - academic_terms
  - course_offerings
  - timetable_entries
  - knowledge_documents + document_chunks  (for RAG retrieval)

Usage (run from repo root with PYTHONPATH set):
    cd backend
    python scripts/ingest_timetable.py

Or with explicit DB URL:
    DATABASE_URL=postgresql://... python scripts/ingest_timetable.py
"""

import os
import re
import sys
import uuid
import json
from pathlib import Path

# Ensure the backend package is importable
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import pdfplumber
from sqlalchemy import create_engine, text
from app.core.config import get_settings
from app.rag.embedding import embed_text

# ── Time slot mapping ────────────────────────────────────────────────────────
TIME_COLS = [
    ("08:35", "10:05"),
    ("10:15", "11:45"),
    ("11:55", "13:25"),
    ("13:35", "15:05"),
    ("15:15", "16:45"),
    ("17:00", "18:30"),
    ("18:30", "20:00"),
]
# Grid columns in the PDF: index 4..10 map to TIME_COLS[0..6]
TIMECOL_START = 4

DAY_MAP = {
    "MONDAY": 1, "TUESDAY": 2, "WEDNESDAY": 3,
    "THURSDAY": 4, "FRIDAY": 5, "SATURDAY": 6, "SUNDAY": 7,
}

TIMETABLE_PDF = Path(__file__).resolve().parents[2] / "TT_v4.1 20-4-26-sp 26.docx.pdf"
SCHEME_PDFS = [
    Path(__file__).resolve().parents[2] / "academic-data/bs/bscs_scheme_fall-2025.pdf",
    Path(__file__).resolve().parents[2] / "academic-data/bs/bscs_scheme_fall-2023.pdf",
    Path(__file__).resolve().parents[2] / "academic-data/bs/bscs_scheme_fall-2021.pdf",
]


def clean(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def parse_course_cell(cell: str):
    """
    Parse a timetable cell like 'CS-104 PSP\nR' or 'CS-222\nADSS S'
    Returns (course_code, section) or (None, None)
    """
    if not cell:
        return None, None
    cell = clean(cell)
    m = re.search(r"\b([A-Z]{2,5}-\d{3,4}(?:[A-Z])?)\b", cell)
    if not m:
        return None, None
    code = m.group(1)
    section = "Regular"
    if re.search(r"\bS\b", cell) and not re.search(r"\bR\b", cell):
        section = "Self-Support"
    elif re.search(r"\bR\b", cell) and re.search(r"\bS\b", cell):
        section = "Regular+Self-Support"
    elif re.search(r"\bS\b", cell):
        section = "Self-Support"
    return code, section


def parse_timetable_pdf(path: Path) -> list[dict]:
    """
    Returns list of dicts:
      {course_code, day_of_week, starts_at, ends_at, room, section}
    """
    entries = []
    with pdfplumber.open(str(path)) as pdf:
        # Page 1 has the main timetable grid
        page = pdf.pages[0]
        tables = page.extract_tables()
        if not tables:
            return entries
        grid = tables[0]
        current_day = None
        for row in grid:
            # Detect day name in col 0
            col0 = clean(row[0]) if row[0] else ""
            day_upper = col0.upper()
            if day_upper in DAY_MAP:
                current_day = DAY_MAP[day_upper]
            if not current_day:
                continue

            # Room is in column 1
            room_raw = clean(row[1]) if row[1] else ""
            room = room_raw.replace("\n", "").strip() or "TBA"

            # Time slots are in columns TIMECOL_START onwards
            for ti, (start, end) in enumerate(TIME_COLS):
                col_idx = TIMECOL_START + ti
                if col_idx >= len(row):
                    break
                cell = row[col_idx]
                if not cell or not clean(cell):
                    continue
                code, section = parse_course_cell(cell)
                if not code:
                    continue
                entries.append({
                    "course_code": code,
                    "day_of_week": current_day,
                    "starts_at": start,
                    "ends_at": end,
                    "room": room,
                    "section": section,
                    "session_type": "lab" if "lab" in room.lower() else "class",
                })

        # Page 2 – Thursday/Friday continued
        for page_idx in [1]:
            if page_idx >= len(pdf.pages):
                continue
            page2 = pdf.pages[page_idx]
            tables2 = page2.extract_tables()
            if not tables2:
                continue
            grid2 = tables2[0]
            for row in grid2:
                col0 = clean(row[0]) if row[0] else ""
                day_upper = col0.upper().split("\n")[0].strip()
                if day_upper in DAY_MAP:
                    current_day = DAY_MAP[day_upper]
                if not current_day:
                    continue
                room_raw = clean(row[1]) if len(row) > 1 and row[1] else ""
                room = room_raw.replace("\n", "").strip() or "TBA"
                for ti, (start, end) in enumerate(TIME_COLS):
                    col_idx = TIMECOL_START + ti
                    if col_idx >= len(row):
                        break
                    cell = row[col_idx]
                    if not cell or not clean(cell):
                        continue
                    code, section = parse_course_cell(cell)
                    if not code:
                        continue
                    entries.append({
                        "course_code": code,
                        "day_of_week": current_day,
                        "starts_at": start,
                        "ends_at": end,
                        "room": room,
                        "section": section,
                        "session_type": "lab" if "lab" in room.lower() else "class",
                    })

    return entries


def parse_course_list_from_timetable(path: Path) -> list[dict]:
    """
    Parse the course list table on pages 2-3.
    Returns list of {code, title, semester, section, faculty, credit_theory, credit_lab}
    """
    courses = []
    with pdfplumber.open(str(path)) as pdf:
        current_semester = None
        current_section = "Regular"
        for page_idx in [1, 2]:
            if page_idx >= len(pdf.pages):
                continue
            tables = pdf.pages[page_idx].extract_tables()
            for table in tables:
                for row in table:
                    if not row or not row[0]:
                        continue
                    col0 = clean(row[0])
                    col1 = clean(row[1]) if row[1] else ""

                    # Detect semester header rows
                    sem_match = re.search(r"BS\s+Semester\s+(\w+)", col0, re.I)
                    if sem_match:
                        sem_str = sem_match.group(1).strip()
                        try:
                            current_semester = int(sem_str)
                        except ValueError:
                            nums = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
                                    "VI": 6, "VII": 7, "VIII": 8, "IX": 9}
                            current_semester = nums.get(sem_str.upper(), None)
                        current_section = "Self-Support" if "self support" in col0.lower() else "Regular"
                        continue
                    if "mphil" in col0.lower() or "phd" in col0.lower() or "ms-ds" in col0.lower():
                        current_semester = None
                        continue
                    if col0.lower() in {"course code", "deficiency courses"}:
                        continue
                    if current_semester is None:
                        continue

                    # Parse course row
                    code_match = re.match(r"([A-Z]{2,5}-\d{3,4}[A-Z]?)", col0)
                    if not code_match:
                        continue
                    code = code_match.group(1)
                    # Extract title and credits from col1
                    credit_match = re.search(r"(\d+)(?:\+(\d+))?$", col1)
                    theory = int(credit_match.group(1)) if credit_match else 3
                    lab = int(credit_match.group(2)) if credit_match and credit_match.group(2) else 0
                    title = re.sub(r"\s*\d+(?:\+\d+)?$", "", col1).strip()
                    # Remove trailing section letters like "R" from title
                    title = re.sub(r"\s+[RS]$", "", title).strip()
                    faculty = clean(row[2]) if len(row) > 2 and row[2] else ""
                    courses.append({
                        "code": code,
                        "title": title,
                        "semester": current_semester,
                        "section": current_section,
                        "faculty": faculty,
                        "credit_theory": theory,
                        "credit_lab": lab,
                    })
    return courses


def generate_chunk_text(entry: dict, course_title: str, faculty: str) -> str:
    days = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
            5: "Friday", 6: "Saturday", 7: "Sunday"}
    day_name = days.get(entry["day_of_week"], "Unknown")
    section = entry.get("section", "Regular")
    return (
        f"Semester: Spring 2026 | "
        f"Course: {entry['course_code']} {course_title} | "
        f"Section: {section} | "
        f"Day: {day_name} | "
        f"Time: {entry['starts_at']}-{entry['ends_at']} | "
        f"Room: {entry['room']} | "
        f"Type: {entry['session_type'].title()} | "
        f"Instructor: {faculty or 'TBA'}"
    )


def main():
    settings = get_settings()
    engine = create_engine(settings.database_url)

    with engine.begin() as conn:
        print("Step 1: Parsing timetable PDF...")
        timetable_entries = parse_timetable_pdf(TIMETABLE_PDF)
        course_list = parse_course_list_from_timetable(TIMETABLE_PDF)
        print(f"  Found {len(timetable_entries)} timetable slots")
        print(f"  Found {len(course_list)} course-section listings")

        # Build lookup: code -> {title, faculty, semester}
        course_info: dict[str, dict] = {}
        for c in course_list:
            key = c["code"]
            if key not in course_info:
                course_info[key] = {"title": c["title"], "faculty": c["faculty"],
                                     "semester": c["semester"], "theory": c["credit_theory"],
                                     "lab": c["credit_lab"]}

        # Step 2: Ensure source record exists
        print("Step 2: Upserting source record...")
        conn.execute(text("""
            INSERT INTO source_records
                (source_code, title, category, authority, local_path,
                 effective_from, last_verified_at, verification_status, is_time_sensitive)
            VALUES
                ('SRC-TT-SP2026', 'BSCS/MS/MPhil/PhD Timetable Spring 2026',
                 'timetable', 'QAU Computer Science Department',
                 'TT_v4.1 20-4-26-sp 26.docx.pdf',
                 '2026-04-20', NOW(), 'verified', TRUE)
            ON CONFLICT (source_code) DO UPDATE
              SET last_verified_at = NOW(), verification_status = 'verified'
        """))

        src_id = conn.execute(text(
            "SELECT id FROM source_records WHERE source_code='SRC-TT-SP2026'"
        )).scalar_one()

        # Step 3: Ensure academic term
        print("Step 3: Upserting academic term Spring 2026...")
        conn.execute(text("""
            INSERT INTO academic_terms (academic_year, term, starts_on, ends_on, active, source_id)
            VALUES (2026, 'Spring', '2026-02-01', '2026-06-30', TRUE, :sid)
            ON CONFLICT (academic_year, term) DO UPDATE
              SET active = TRUE, source_id = :sid
        """), {"sid": src_id})

        term_id = conn.execute(text(
            "SELECT id FROM academic_terms WHERE academic_year=2026 AND term='Spring'"
        )).scalar_one()

        # Step 4: Get BSCS program id
        bscs_id = conn.execute(text(
            "SELECT id FROM programs WHERE code='BSCS'"
        )).scalar_one()

        # Step 5: Upsert courses into the courses table
        print("Step 4: Upserting courses...")
        upserted_courses = 0
        for info in course_info.values():
            code = None
            for c in course_list:
                if c["title"] == info["title"]:
                    code = c["code"]
                    break
        for c in course_list:
            code = c["code"]
            title = c["title"] or code
            theory = c["credit_theory"] if c["credit_theory"] else 3
            lab = c["credit_lab"] if c["credit_lab"] else 0
            if not title:
                continue
            conn.execute(text("""
                INSERT INTO courses (code, title, theory_credit_hours, lab_credit_hours, source_id)
                VALUES (:code, :title, :theory, :lab, :sid)
                ON CONFLICT (code) DO UPDATE
                  SET title = EXCLUDED.title,
                      theory_credit_hours = EXCLUDED.theory_credit_hours,
                      lab_credit_hours = EXCLUDED.lab_credit_hours
            """), {"code": code, "title": title, "theory": theory, "lab": lab, "sid": src_id})
            upserted_courses += 1
        print(f"  Upserted {upserted_courses} courses")

        # Step 6: Delete old offerings/entries for this term to avoid duplicates
        print("Step 5: Clearing old Spring 2026 timetable data...")
        conn.execute(text("""
            DELETE FROM timetable_entries
            WHERE offering_id IN (
                SELECT id FROM course_offerings WHERE term_id = :tid
            )
        """), {"tid": term_id})
        conn.execute(text(
            "DELETE FROM course_offerings WHERE term_id = :tid"
        ), {"tid": term_id})

        # Step 7: Insert course offerings + timetable entries
        print("Step 6: Inserting course offerings and timetable entries...")
        # Build a set of (course_code, section) to deduplicate offerings
        offering_map: dict[tuple, str] = {}  # (code, section) -> offering_id
        inserted_entries = 0
        skipped = 0

        for entry in timetable_entries:
            code = entry["course_code"]
            section = entry.get("section", "Regular")
            # Simplify section for offering key
            sec_key = "Regular" if "Regular" in section else "Self-Support"
            key = (code, sec_key)

            # Get or create offering
            if key not in offering_map:
                # Check course exists
                c_row = conn.execute(text(
                    "SELECT id FROM courses WHERE code=:code"
                ), {"code": code}).mappings().one_or_none()
                if not c_row:
                    # Try to upsert a minimal course record
                    info = course_info.get(code, {})
                    title = info.get("title") or code
                    conn.execute(text("""
                        INSERT INTO courses (code, title, theory_credit_hours, lab_credit_hours, source_id)
                        VALUES (:code, :title, 3, 0, :sid)
                        ON CONFLICT (code) DO NOTHING
                    """), {"code": code, "title": title, "sid": src_id})
                    c_row = conn.execute(text(
                        "SELECT id FROM courses WHERE code=:code"
                    ), {"code": code}).mappings().one_or_none()

                if not c_row:
                    skipped += 1
                    continue

                info = course_info.get(code, {})
                faculty = info.get("faculty", "")

                off_id = str(uuid.uuid4())
                conn.execute(text("""
                    INSERT INTO course_offerings
                        (id, term_id, course_id, program_id, section, instructor, source_id)
                    VALUES (:id, :tid, :cid, :pid, :sec, :instr, :sid)
                """), {
                    "id": off_id,
                    "tid": term_id,
                    "cid": c_row["id"],
                    "pid": bscs_id,
                    "sec": sec_key,
                    "instr": faculty[:200] if faculty else None,
                    "sid": src_id,
                })
                offering_map[key] = off_id

            off_id = offering_map[key]
            # Insert timetable entry (ignore duplicates)
            try:
                conn.execute(text("""
                    INSERT INTO timetable_entries
                        (offering_id, session_type, day_of_week, starts_at, ends_at, room)
                    VALUES (:oid, :stype, :dow, :start, :end, :room)
                    ON CONFLICT (offering_id, session_type, day_of_week, starts_at, lab_group)
                    DO NOTHING
                """), {
                    "oid": off_id,
                    "stype": entry["session_type"],
                    "dow": entry["day_of_week"],
                    "start": entry["starts_at"],
                    "end": entry["ends_at"],
                    "room": entry["room"],
                })
                inserted_entries += 1
            except Exception as e:
                skipped += 1

        print(f"  Inserted {inserted_entries} timetable entries, skipped {skipped}")

        # Step 8: Build RAG document chunks for the timetable
        print("Step 7: Building RAG document chunks...")

        # Ensure knowledge_document exists
        conn.execute(text("""
            INSERT INTO knowledge_documents
                (source_id, program_id, title, category, mime_type, storage_path, processing_status, processed_at)
            VALUES
                (:sid, :pid, 'BSCS Timetable Spring 2026', 'timetable',
                 'application/pdf', :path, 'ready', NOW())
            ON CONFLICT (source_id) DO UPDATE
              SET processing_status = 'ready', processed_at = NOW()
        """), {
            "sid": src_id,
            "pid": bscs_id,
            "path": str(TIMETABLE_PDF),
        })

        doc_id = conn.execute(text(
            "SELECT id FROM knowledge_documents WHERE source_id=:sid"
        ), {"sid": src_id}).scalar_one()

        # Delete old chunks
        conn.execute(text("DELETE FROM document_chunks WHERE document_id=:did"), {"did": doc_id})

        # Generate one chunk per timetable entry
        chunk_idx = 0
        days = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
                5: "Friday", 6: "Saturday", 7: "Sunday"}

        for entry in timetable_entries:
            code = entry["course_code"]
            info = course_info.get(code, {})
            title = info.get("title", code)
            faculty = info.get("faculty", "")
            semester = info.get("semester")
            day_name = days.get(entry["day_of_week"], "Unknown")
            section = entry.get("section", "Regular")

            chunk_text = generate_chunk_text(entry, title, faculty)
            embedding = embed_text(chunk_text)
            metadata = {
                "semester": semester,
                "course_code": code,
                "course_title": title,
                "section": section,
                "day": day_name,
                "start_time": entry["starts_at"],
                "end_time": entry["ends_at"],
                "room": entry["room"],
                "course_type": entry["session_type"],
                "instructor": faculty,
                "term": "Spring 2026",
                "doc_type": "timetable",
            }

            conn.execute(text("""
                INSERT INTO document_chunks
                    (document_id, chunk_index, content, metadata, embedding)
                VALUES (:did, :idx, :content, CAST(:meta AS jsonb),
                        CAST(:emb AS vector))
            """), {
                "did": doc_id,
                "idx": chunk_idx,
                "content": chunk_text,
                "meta": json.dumps(metadata),
                "emb": "[" + ",".join(f"{v:.8f}" for v in embedding) + "]",
            })
            chunk_idx += 1

        print(f"  Created {chunk_idx} RAG chunks for timetable")

        # Step 9: Also create summary chunks per day
        day_summary: dict[int, list[str]] = {}
        for entry in timetable_entries:
            d = entry["day_of_week"]
            code = entry["course_code"]
            info = course_info.get(code, {})
            title = info.get("title", code)
            section = entry.get("section", "Regular")
            day_summary.setdefault(d, []).append(
                f"{code} {title} ({section}) at {entry['starts_at']}-{entry['ends_at']} in {entry['room']}"
            )

        for dow, course_strs in day_summary.items():
            day_name = days[dow]
            content = f"Spring 2026 {day_name} Schedule: " + " | ".join(set(course_strs))
            embedding = embed_text(content)
            metadata = {
                "day": day_name,
                "term": "Spring 2026",
                "doc_type": "timetable_day_summary",
            }
            conn.execute(text("""
                INSERT INTO document_chunks
                    (document_id, chunk_index, content, metadata, embedding)
                VALUES (:did, :idx, :content, CAST(:meta AS jsonb),
                        CAST(:emb AS vector))
            """), {
                "did": doc_id,
                "idx": chunk_idx,
                "content": content,
                "meta": json.dumps(metadata),
                "emb": "[" + ",".join(f"{v:.8f}" for v in embedding) + "]",
            })
            chunk_idx += 1

        print(f"  Total chunks created: {chunk_idx}")
        print("\nDone! Timetable ingested successfully.")
        print(f"  Academic term: Spring 2026")
        print(f"  Timetable entries: {inserted_entries}")
        print(f"  RAG chunks: {chunk_idx}")


if __name__ == "__main__":
    main()
