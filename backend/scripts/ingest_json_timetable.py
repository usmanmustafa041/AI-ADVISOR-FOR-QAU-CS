"""
Timetable ingestion from JSON for Spring 2026
"""

import sys
import uuid
import json
from pathlib import Path

# Ensure the backend package is importable
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text
from app.core.config import get_settings
from app.rag.embedding import embed_text

TIMETABLE_JSON = BACKEND / "data" / "timetable_spring_2026.json"

def main():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    with open(TIMETABLE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    with engine.begin() as conn:
        print("Ensuring source record...")
        conn.execute(text("""
            INSERT INTO source_records (source_code, title, category, authority, local_path, effective_from, last_verified_at, verification_status, is_time_sensitive)
            VALUES ('SRC-TT-SP2026', 'Timetable Spring 2026', 'timetable', 'QAU CS', 'timetable_spring_2026.json', '2026-04-20', NOW(), 'verified', TRUE)
            ON CONFLICT (source_code) DO UPDATE SET last_verified_at = NOW(), verification_status = 'verified'
        """))
        src_id = conn.execute(text("SELECT id FROM source_records WHERE source_code='SRC-TT-SP2026'")).scalar_one()

        print("Ensuring academic term...")
        conn.execute(text("""
            INSERT INTO academic_terms (academic_year, term, starts_on, ends_on, active, source_id)
            VALUES (2026, 'Spring', '2026-02-01', '2026-06-30', TRUE, :sid)
            ON CONFLICT (academic_year, term) DO UPDATE SET active = TRUE, source_id = :sid
        """), {"sid": src_id})
        term_id = conn.execute(text("SELECT id FROM academic_terms WHERE academic_year=2026 AND term='Spring'")).scalar_one()

        bscs_id = conn.execute(text("SELECT id FROM programs WHERE code='BSCS'")).scalar_one()

        print("Upserting courses...")
        for c in data.get("courses", []):
            code = c["course_code"]
            title = c["course_title"]
            conn.execute(text("""
                INSERT INTO courses (code, title, theory_credit_hours, lab_credit_hours, source_id)
                VALUES (:code, :title, 3, 0, :sid)
                ON CONFLICT (code) DO UPDATE SET title = EXCLUDED.title
            """), {"code": code, "title": title, "sid": src_id})
            
        print("Clearing old timetable data...")
        conn.execute(text("DELETE FROM timetable_entries WHERE offering_id IN (SELECT id FROM course_offerings WHERE term_id = :tid)"), {"tid": term_id})
        conn.execute(text("DELETE FROM course_offerings WHERE term_id = :tid"), {"tid": term_id})
        
        print("Inserting timetable entries...")
        offering_map = {}
        for slot in data.get("schedule_slots", []):
            code = slot["course_code"]
            c_info = next((c for c in data.get("courses", []) if c["course_code"] == code), {})
            section = "Self-Support" if "(S)" in slot.get("course_title", "") else "Regular"
            
            key = (code, section)
            if key not in offering_map:
                # Use .first() to handle missing courses gracefully
                c_row = conn.execute(text("SELECT id FROM courses WHERE code=:code"), {"code": code}).first()
                if not c_row:
                    title = slot.get("course_title", code)
                    conn.execute(text("""
                        INSERT INTO courses (code, title, theory_credit_hours, lab_credit_hours, source_id)
                        VALUES (:code, :title, 3, 0, :sid)
                    """), {"code": code, "title": title, "sid": src_id})
                    c_row = conn.execute(text("SELECT id FROM courses WHERE code=:code"), {"code": code}).first()
                
                c_id = c_row[0]
                instr = c_info.get("instructors", ["Staff"])[0] if c_info.get("instructors") else "Staff"
                off_id = str(uuid.uuid4())
                conn.execute(text("""
                    INSERT INTO course_offerings (id, term_id, course_id, program_id, section, instructor, source_id)
                    VALUES (:id, :tid, :cid, :pid, :sec, :instr, :sid)
                """), {"id": off_id, "tid": term_id, "cid": c_id, "pid": bscs_id, "sec": section, "instr": instr, "sid": src_id})
                offering_map[key] = off_id
                
            off_id = offering_map[key]
            times = slot.get("time_slot", "00:00-00:00").split("-")
            start = times[0] if len(times)>0 else "00:00"
            end = times[1] if len(times)>1 else "00:00"
            day_map = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4, "Friday": 5}
            dow = day_map.get(slot.get("day"), 1)
            
            stype = "lab" if "Lab" in slot.get("room", "") else "class"
            
            try:
                conn.execute(text("""
                    INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
                    VALUES (:oid, :stype, :dow, :start, :end, :room)
                    ON CONFLICT DO NOTHING
                """), {"oid": off_id, "stype": stype, "dow": dow, "start": start, "end": end, "room": slot.get("room")})
            except Exception as e:
                pass
                
        print("Done successfully!")

if __name__ == "__main__":
    main()
