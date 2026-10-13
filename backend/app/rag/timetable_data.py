"""
Fast in-memory timetable + scheme of study data loader.
Parses JSON instead of PDF for perfect accuracy.
"""

import json
import re
from pathlib import Path

TIMETABLE_JSON = Path(__file__).resolve().parents[2] / "data" / "timetable_spring_2026.json"

# Cached data
_timetable_cache = None
_courses_cache = None

def _load_json():
    try:
        with open(TIMETABLE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"courses": [], "schedule_slots": []}

def parse_timetable():
    """Returns list of {course_code, day, start_time, end_time, room, section, instructor}"""
    data = _load_json()
    entries = []
    
    courses_map = parse_courses()
    
    for slot in data.get("schedule_slots", []):
        try:
            start_time, end_time = slot.get("time_slot", "00:00-00:00").split("-")
        except ValueError:
            start_time, end_time = "TBA", "TBA"
            
        code = slot.get("course_code")
        c_info = courses_map.get(code, {})
        section = slot.get("course_title", "").split("(")[-1].replace(")", "") if "(" in slot.get("course_title", "") else "Regular"
        if section == "R": section = "Regular"
        if section == "S": section = "Self-Support"
        
        entries.append({
            "course_code": code,
            "day": slot.get("day"),
            "start_time": start_time,
            "end_time": end_time,
            "room": slot.get("room"),
            "section": section,
            "instructor": c_info.get("instructor", "TBA"),
            "term": "Spring 2026",
            "title": c_info.get("title", slot.get("course_title", code))
        })
    return entries

def parse_courses():
    """Returns {code: {title, semester, section, instructor, abbreviation}}"""
    data = _load_json()
    courses = {}
    
    for c in data.get("courses", []):
        instructors = c.get("instructors", [])
        instr = instructors[0] if instructors else "TBA"
        
        sem_str = c.get("program_semester", "")
        sem = None
        if "Semester" in sem_str:
            try:
                sem_roman = sem_str.split("Semester")[-1].strip().split()[0]
                nums = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "9": 9}
                sem = nums.get(sem_roman, sem_roman)
            except:
                pass
                
        raw_abbr = c.get("abbreviation", "")
        clean_abbr = re.sub(r'\s*\([RS]\)\s*', '', raw_abbr).strip()
            
        courses[c.get("course_code")] = {
            "title": c.get("course_title"),
            "semester": sem,
            "section": "Regular" if "(R)" in raw_abbr else ("Self-Support" if "(S)" in raw_abbr else "Regular"),
            "instructor": instr,
            "abbreviation": clean_abbr
        }
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
    """Search timetable for matching entries intelligently"""
    results = []
    timetable = get_timetable()
    courses_info = get_courses()
    
    # Check for days
    day_match = re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', query_lower)
    search_day = day_match.group(1).capitalize() if day_match else None
    
    # Check for exact course code
    code_match = re.search(r'\b([a-z]{2,5}-\d{3,4}[a-z]?)\b', query_lower)
    search_code = code_match.group(1).upper() if code_match else None

    # Check for semester
    sem_match = re.search(r'\bsemester\s+(\d+|one|two|three|four|five|six|seven|eight|nine)\b', query_lower)
    search_sem = None
    if sem_match:
        val = sem_match.group(1)
        word_to_num = {"one":1, "two":2, "three":3, "four":4, "five":5, "six":6, "seven":7, "eight":8, "nine":9}
        search_sem = int(val) if val.isdigit() else word_to_num.get(val)
        
    # Remove filler words to get pure keywords
    clean_query = re.sub(r'\b(what|is|the|time|table|for|when|in|class|classes|course)\b', ' ', query_lower)
    query_tokens = set(word for word in clean_query.split() if len(word) > 1)
        
    for entry in timetable:
        match = False
        
        c_info = courses_info.get(entry["course_code"], {})
        
        # Exact code match is strongest
        if search_code and entry["course_code"] == search_code:
            match = True
            
        # Match by semester
        elif search_sem:
            if str(c_info.get("semester")) == str(search_sem):
                match = True
                
        # Match by day (if user specifies ONLY the day, or we match it strongly)
        elif search_day and len(query_tokens) == 1 and list(query_tokens)[0] == search_day.lower():
            match = True
            
        # Token-based text matching for course names, abbreviations, and instructors
        else:
            if query_tokens:
                # Build a search document from entry attributes
                search_text = (
                    entry["title"] + " " + 
                    entry["course_code"] + " " + 
                    entry["instructor"] + " " +
                    c_info.get("abbreviation", "")
                ).lower()
                
                # To handle "ICTS" -> Check if any query token is in the search text
                # We require ALL tokens in the query to be present in the search text for a strong match
                # OR if it's a single token, it must be in the search text
                token_matches = sum(1 for token in query_tokens if token in search_text)
                if token_matches > 0 and token_matches >= len(query_tokens) - 1: 
                    # Matches most tokens
                    match = True
                    
        # If user explicitly asked for a day along with course, filter it
        if match and search_day and search_day.lower() not in entry["day"].lower():
            match = False

        if match:
            results.append(entry)
            
    # Remove duplicates
    unique_results = []
    seen = set()
    for r in results:
        sig = (r["course_code"], r["day"], r["start_time"], r["section"])
        if sig not in seen:
            seen.add(sig)
            unique_results.append(r)
            
    return unique_results[:15]
