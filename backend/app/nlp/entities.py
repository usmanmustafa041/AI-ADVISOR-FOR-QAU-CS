import re

COURSE_CODE = re.compile(r"\b(?:CSC|CS|IST|DSC|EN|MA|PK|FQ|IS|PH|PS|SW|ST|MS)-?\d{3}\b", re.I)
DATE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b")
CREDIT_HOURS = re.compile(r"\b(\d{1,3})\s*(?:credit\s*hours?|credits?|cr\.?\s*hrs?)\b", re.I)
SEMESTER_WORD = re.compile(r"\b(?:semester|sem)\s*(?:no\.?\s*)?(\d{1,2})\b", re.I)

COURSE_NAMES = {
    "opp": "CSC-121",
    "object oriented programming": "CSC-121",
    "machine learning": "CSC-459",
    "data structures": "CSC-211",
    "artificial intelligence": "CSC-414",
    "ai": "CSC-414",
    "ml": "CSC-459",
    "oop": "CSC-121",
    "dsa": "CSC-211",
    "dbms": "CSC-224",
    "os": "CSC-226",
    "cn": "CSC-312",
    "computer networks": "CSC-312",
    "database systems": "CSC-224",
    "software construction": "CSC-322",
    "software quality assurance": "CSC-483",
    "software project management": "CSC-486",
}


def extract_entities(text: str) -> dict[str, list[str]]:
    lowered = text.lower()
    entities: dict[str, list[str]] = {}

    code_aliases = {"CS-201": "CSC-211", "CS201": "CSC-211"}
    codes = []
    for code in COURSE_CODE.findall(text):
        normalized_code = code.upper().replace(" ", "")
        codes.append(code_aliases.get(normalized_code, normalized_code))
    if codes:
        entities["course_code"] = codes

    names = [
        name for name in COURSE_NAMES
        if (re.search(rf"\b{re.escape(name)}\b", lowered) if len(name) <= 4 else name in lowered)
    ]
    if names:
        entities["course_name"] = names
        if "course_code" not in entities:
            entities["course_code"] = [COURSE_NAMES[name] for name in names]

    programs = []
    for phrase, canonical in {
        "bs computer science": "BSCS", "bscs": "BSCS", "bs cs": "BSCS",
        "ms data science": "MS-DS", "data science": "MS-DS", "ms ist": "MS-IST",
        "information science": "MS-IST", "mphil": "MPHIL-CS", "phd": "PHD-CS",
    }.items():
        if phrase in lowered and canonical not in programs:
            programs.append(canonical)
    if programs:
        entities["program"] = programs

    shifts = [shift for shift in ("morning", "evening", "regular", "self-support", "self finance") if shift in lowered]
    if shifts:
        entities["shift"] = shifts

    semesters = SEMESTER_WORD.findall(lowered)
    if not semesters:
        semesters = re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+semester\b", lowered)
    if semesters:
        entities["semester"] = semesters

    days = [day for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday") if day in lowered]
    if days:
        entities["day"] = days

    dates = DATE.findall(text)
    if dates:
        entities["date"] = dates

    credit_hours = CREDIT_HOURS.findall(text)
    if credit_hours:
        entities["credit_hours"] = credit_hours

    degree_levels = []
    for phrase, canonical in {
        "bachelor": "BS", "bscs": "BS", "bs cs": "BS", "bs computer science": "BS",
        "master": "MS", "ms ist": "MS", "ms data science": "MS", "mphil": "MPhil",
        "phd": "PhD", "doctorate": "PhD",
    }.items():
        if phrase in lowered and canonical not in degree_levels:
            degree_levels.append(canonical)
    if degree_levels:
        entities["degree_level"] = degree_levels

    return entities
