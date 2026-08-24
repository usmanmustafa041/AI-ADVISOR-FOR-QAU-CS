"""
Fast in-memory timetable + scheme of study data loader.
Parses PDFs once and serves via simple dicts - no database needed for MVP.
"""

import re
from pathlib import Path
import pdfplumber

TIMETABLE_PDF = Path(__file__).resolve().parents[3] / "TT_v4.1 20-4-26-sp 26.docx.pdf"

# Cached data
_timetable_cache = None
_courses_cache = None

def parse_timetable():
    """Returns list of {course_code, day, start_time, end_time, room, section, instructor}"""
    entries = []
    times = [
        ("08:35", "10:05"),
        ("10:15", "11:45"),
        ("11:55", "13:25"),
        ("13:35", "15:05"),
        ("15:15", "16:45"),
        ("17:00", "18:30"),
        ("18:30", "20:00"),
    ]
    days_map = {
        "MONDAY": "Monday", "TUESDAY": "Tuesday", "WEDNESDAY": "Wednesday",
        "THURSDAY": "Thursday", "FRIDAY": "Friday", "SATURDAY": "Saturday", "SUNDAY": "Sunday",
    }
    
    try:
        with pdfplumber.open(str(TIMETABLE_PDF)) as pdf:
            grid = pdf.pages[0].extract_tables()[0]
            current_day = None
            for row in grid:
                col0 = str(row[0] or "").upper().strip()
                if col0 in days_map:
                    current_day = days_map[col0]
                if not current_day:
                    continue
                    
                room = str(row[1] or "").strip().replace("\n", "") or "TBA"
                
                for ti, (start, end) in enumerate(times):
                    col_idx = 4 + ti
                    if col_idx >= len(row):
                        break
                    cell = str(row[col_idx] or "")
                    if not cell.strip():
                        continue
                    
                    m = re.search(r'\b([A-Z]{2,5}-\d{3,4}[A-Z]?)\b', cell)
                    if not m:
                        continue
                    
                    code = m.group(1)
                    section = "Self-Support" if " S" in cell and " R" not in cell else "Regular"
                    
                    entries.append({
                        "course_code": code,
                        "day": current_day,
                        "start_time": start,
                        "end_time": end,
                        "room": room,
                        "section": section,
                        "instructor": "Staff",
                        "term": "Spring 2026",
                    })
    except:
        pass
    
    return entries

def parse_courses():
    """Returns {code: {title, semester, section, instructor}}"""
    courses = {}
    try:
        with pdfplumber.open(str(TIMETABLE_PDF)) as pdf:
            current_sem = None
            current_sec = "Regular"
            for table in pdf.pages[1].extract_tables():
                for row in table:
                    if not row or not row[0]:
                        continue
                    col0 = str(row[0] or "").strip()
                    
                    if "Semester" in col0:
                        m = re.search(r"Semester\s+(\w+)", col0)
                        if m:
                            sem_str = m.group(1)
                            try:
                                current_sem = int(sem_str)
                            except:
                                nums = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
                                current_sem = nums.get(sem_str, None)
                        if "Self" in col0.lower():
                            current_sec = "Self-Support"
                        else:
                            current_sec = "Regular"
                        continue
                    
                    m = re.match(r"([A-Z]{2,5}-\d{3,4}[A-Z]?)", col0)
                    if not m or not current_sem:
                        continue
                    
                    code = m.group(1)
                    col1 = str(row[1] or "")
                    title = re.sub(r'\s*\d+(?:\+\d+)?$', '', col1).strip()
                    
                    courses[code] = {
                        "title": title or code,
                        "semester": current_sem,
                        "section": current_sec,
                        "instructor": str(row[2] or "Staff"),
                    }
    except:
        pass
    
    return courses

def get_timetable():
    """Get cached or parsed timetable data"""
    global _timetable_cache
    if _timetable_cache is None:
        _timetable_cache = parse_timetable()
    return _timetable_cache

def get_courses():
    """Get cached or parsed course data"""
    global _courses_cache
    if _courses_cache is None:
        _courses_cache = parse_courses()
    return _courses_cache

def search_timetable(query_lower: str):
    """Search timetable for matching entries"""
    results = []
    timetable = get_timetable()
    courses = get_courses()
    
    # Extract day if present
    day_match = re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', query_lower)
    search_day = day_match.group(1).capitalize() if day_match else None
    
    # Extract course code if present
    code_match = re.search(r'\b([A-Z]{2,5}-\d{3,4}[A-Z]?)\b', query_lower.upper())
    search_code = code_match.group(1) if code_match else None
    
    for entry in timetable:
        match = False
        if search_code and entry["course_code"] == search_code:
            match = True
        elif search_day and search_day.lower() in entry["day"].lower():
            match = True
        elif "semester" in query_lower and search_code:
            match = True
        
        if match:
            course_info = courses.get(entry["course_code"], {})
            entry["title"] = course_info.get("title", entry["course_code"])
            entry["instructor"] = course_info.get("instructor", "Staff")
            results.append(entry)
    
    return results[:10]
