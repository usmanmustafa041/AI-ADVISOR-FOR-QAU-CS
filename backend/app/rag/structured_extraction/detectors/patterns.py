"""Regex patterns and utility functions for document classification and extraction."""

import re
from typing import List, Tuple


# Course code pattern: 4-10 alphanumeric characters with at least one letter and one digit
# Examples: CS101, MATH2201, BIO123A, ENG1234
COURSE_CODE_PATTERN = re.compile(
    r'\b(?=(?:[A-Z]*\d)|(?:\d*[A-Z]))(?:[A-Z\d]{4,10})\b',
    re.IGNORECASE
)

# More lenient course code pattern for extraction contexts
# Matches common formats like CS-101, CS 101, CS101
COURSE_CODE_EXTRACTION_PATTERN = re.compile(
    r'\b([A-Z]{2,4})[\s\-]?(\d{3,4}[A-Z]?)\b',
    re.IGNORECASE
)

# Day names - full names
DAY_NAMES_FULL = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]

# Day names - 3-letter abbreviations
DAY_NAMES_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Combined day name pattern (full names and abbreviations)
DAY_NAME_PATTERN = re.compile(
    r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|'
    r'Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b',
    re.IGNORECASE
)

# Time pattern - 12-hour format (e.g., 9:30 AM, 12:00 PM, 01:15 pm)
TIME_12HR_PATTERN = re.compile(
    r'\b(1[0-2]|0?[1-9]):[0-5]\d\s?(?:AM|PM|am|pm|A\.M\.|P\.M\.)\b'
)

# Time pattern - 24-hour format (e.g., 09:30, 13:45, 23:59)
TIME_24HR_PATTERN = re.compile(
    r'\b([01]?\d|2[0-3]):[0-5]\d\b'
)

# Combined time pattern (matches both 12-hour and 24-hour formats)
TIME_PATTERN = re.compile(
    r'\b(1[0-2]|0?[1-9]):[0-5]\d\s?(?:AM|PM|am|pm|A\.M\.|P\.M\.)\b|'
    r'\b([01]?\d|2[0-3]):[0-5]\d\b'
)

# Credit hours pattern - matches various formats
# Examples: "3 credits", "4 credit", "3 Cr", "4 CH", "3 Credit Hours"
CREDIT_HOURS_PATTERN = re.compile(
    r'\b(\d{1,2})\s?(?:credit|credits|Cr|CH|Credit\s?Hours)\b',
    re.IGNORECASE
)

# Semester reference pattern - matches "Semester N" or just digit 1-12
# Examples: "Semester 1", "Semester 5", "1", "12"
SEMESTER_REFERENCE_PATTERN = re.compile(
    r'\b(?:Semester\s+)?([1-9]|1[0-2])\b',
    re.IGNORECASE
)

# More specific semester pattern for contexts where "Semester" keyword is present
SEMESTER_WITH_KEYWORD_PATTERN = re.compile(
    r'\bSemester\s+([1-9]|1[0-2])\b',
    re.IGNORECASE
)

# Section designation pattern
# Examples: "Regular", "Self-Support", "Self Support"
SECTION_PATTERN = re.compile(
    r'\b(Regular|Self[\s\-]?Support)\b',
    re.IGNORECASE
)

# Course type pattern
# Examples: "Lab", "Lecture", "Tutorial", "Lec", "Tut"
COURSE_TYPE_PATTERN = re.compile(
    r'\b(Lab|Laboratory|Lecture|Lec|Tutorial|Tut)\b',
    re.IGNORECASE
)

# Special status pattern
# Examples: "Repeater", "Deficiency", "Special"
SPECIAL_STATUS_PATTERN = re.compile(
    r'\b(Repeater|Deficiency|Special)\b',
    re.IGNORECASE
)

# Room number pattern
# Matches common room formats: "Room 101", "R-202", "Lab-3", "CS-Lab", "A-304"
ROOM_PATTERN = re.compile(
    r'\b(?:Room\s+)?([A-Z]?\d{1,4}[A-Z]?|[A-Z]{1,3}[\-\s]?\d{1,3}|[A-Z]{2,4}[\-\s]?Lab[\-\s]?\d?)\b',
    re.IGNORECASE
)


def count_course_codes(text: str) -> int:
    """
    Count the number of course code patterns in the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        Number of unique course code matches found
    """
    matches = COURSE_CODE_PATTERN.findall(text)
    # Return count of unique matches to avoid counting duplicates
    return len(set(match.upper() for match in matches))


def count_day_names(text: str) -> int:
    """
    Count the number of distinct day name references in the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        Number of distinct day names found (both full and abbreviated forms)
    """
    matches = DAY_NAME_PATTERN.findall(text)
    # Normalize day names to handle full names and abbreviations as same day
    normalized_days = set()
    for match in matches:
        day = match.strip().capitalize()
        # Normalize to first 3 characters to treat Mon and Monday as same
        normalized_days.add(day[:3])
    return len(normalized_days)


def count_time_patterns(text: str) -> int:
    """
    Count the number of time pattern occurrences in the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        Number of time patterns found (12-hour and 24-hour formats)
    """
    matches = TIME_PATTERN.findall(text)
    return len(matches)


def count_credit_hours(text: str) -> int:
    """
    Count the number of credit hour pattern occurrences in the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        Number of credit hour patterns found
    """
    matches = CREDIT_HOURS_PATTERN.findall(text)
    return len(matches)


def count_semester_references(text: str) -> int:
    """
    Count the number of distinct semester references in the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        Number of distinct semester numbers (1-12) found
    """
    matches = SEMESTER_REFERENCE_PATTERN.findall(text)
    # Return count of unique semester numbers
    unique_semesters = set()
    for match in matches:
        try:
            sem_num = int(match)
            if 1 <= sem_num <= 12:
                unique_semesters.add(sem_num)
        except ValueError:
            continue
    return len(unique_semesters)


def extract_course_codes(text: str) -> List[str]:
    """
    Extract all course codes from the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        List of course code strings found in the text
    """
    matches = COURSE_CODE_PATTERN.findall(text)
    return [match.upper() for match in matches]


def extract_day_names(text: str) -> List[str]:
    """
    Extract all day names from the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        List of day name strings found in the text
    """
    matches = DAY_NAME_PATTERN.findall(text)
    # Normalize to full day names
    normalized = []
    day_map = {
        'Mon': 'Monday', 'Tue': 'Tuesday', 'Wed': 'Wednesday',
        'Thu': 'Thursday', 'Fri': 'Friday', 'Sat': 'Saturday', 'Sun': 'Sunday'
    }
    for match in matches:
        day = match.strip().capitalize()
        # Check if it's an abbreviation
        if day in day_map:
            normalized.append(day_map[day])
        elif day in day_map.values():
            normalized.append(day)
    return normalized


def extract_times(text: str) -> List[str]:
    """
    Extract all time values from the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        List of time strings found in the text (preserving exact format)
    """
    matches = TIME_PATTERN.finditer(text)
    return [match.group(0) for match in matches]


def extract_credit_hours(text: str) -> List[Tuple[int, str]]:
    """
    Extract credit hour values from the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        List of tuples (credit_value, full_match_text)
    """
    matches = CREDIT_HOURS_PATTERN.finditer(text)
    results = []
    for match in matches:
        try:
            credit_value = int(match.group(1))
            results.append((credit_value, match.group(0)))
        except ValueError:
            continue
    return results


def extract_semester_numbers(text: str) -> List[int]:
    """
    Extract semester numbers from the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        List of semester numbers (1-12) found in the text
    """
    matches = SEMESTER_REFERENCE_PATTERN.findall(text)
    semesters = []
    for match in matches:
        try:
            sem_num = int(match)
            if 1 <= sem_num <= 12:
                semesters.append(sem_num)
        except ValueError:
            continue
    return semesters


def normalize_course_type(text: str) -> str:
    """
    Normalize course type to standard values: Lab, Lecture, Tutorial, or Unknown.
    
    Args:
        text: Input text containing course type
        
    Returns:
        Normalized course type string
    """
    match = COURSE_TYPE_PATTERN.search(text)
    if not match:
        return "Unknown"
    
    course_type = match.group(1).lower()
    if course_type in ['lab', 'laboratory']:
        return "Lab"
    elif course_type in ['lecture', 'lec']:
        return "Lecture"
    elif course_type in ['tutorial', 'tut']:
        return "Tutorial"
    else:
        return "Unknown"


def normalize_section(text: str) -> str:
    """
    Normalize section designation to standard values: Regular, Self-Support, or Unknown.
    
    Args:
        text: Input text containing section designation
        
    Returns:
        Normalized section string
    """
    match = SECTION_PATTERN.search(text)
    if not match:
        return "Unknown"
    
    section = match.group(1).lower().replace(' ', '-').replace('_', '-')
    if 'regular' in section:
        return "Regular"
    elif 'self' in section and 'support' in section:
        return "Self-Support"
    else:
        return "Unknown"


def normalize_special_status(text: str) -> str:
    """
    Normalize special status to standard values: Repeater, Deficiency, Special, or None.
    
    Args:
        text: Input text containing special status
        
    Returns:
        Normalized special status string or None if not found
    """
    match = SPECIAL_STATUS_PATTERN.search(text)
    if not match:
        return None
    
    status = match.group(1).lower()
    if status == 'repeater':
        return "Repeater"
    elif status == 'deficiency':
        return "Deficiency"
    elif status == 'special':
        return "Special"
    else:
        return None


def validate_course_code(code: str) -> bool:
    """
    Validate that a course code meets the requirements:
    - 4-10 alphanumeric characters
    - Contains at least one letter and one digit
    
    Args:
        code: Course code string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not code or len(code) < 4 or len(code) > 10:
        return False
    
    if not code.isalnum():
        return False
    
    has_letter = any(c.isalpha() for c in code)
    has_digit = any(c.isdigit() for c in code)
    
    return has_letter and has_digit


def validate_time_format(time_str: str) -> bool:
    """
    Validate that a time string matches expected formats.
    
    Args:
        time_str: Time string to validate
        
    Returns:
        True if valid 12-hour or 24-hour format, False otherwise
    """
    return bool(TIME_12HR_PATTERN.match(time_str) or TIME_24HR_PATTERN.match(time_str))


def has_structured_layout(text: str, min_rows: int = 3) -> bool:
    """
    Check if text appears to have a structured table/row layout.
    This is a heuristic check looking for repeated patterns that suggest tabular data.
    
    Args:
        text: Input text to analyze
        min_rows: Minimum number of rows to consider structured (default: 3)
        
    Returns:
        True if text appears to have structured layout, False otherwise
    """
    lines = text.split('\n')
    
    # Count lines that appear to be data rows (contain multiple separators or fields)
    data_rows = 0
    for line in lines:
        # Check for common separators: tabs, multiple spaces, pipes
        if '\t' in line or '|' in line or '  ' in line:
            data_rows += 1
    
    return data_rows >= min_rows
