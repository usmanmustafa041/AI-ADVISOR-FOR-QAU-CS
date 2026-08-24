# Document Detection and Classification Module

This module provides pattern detection utilities for classifying and extracting structured data from academic documents including timetables and scheme of study PDFs.

## Overview

The `patterns.py` module contains regex patterns and utility functions for:
- **Course codes**: 4-10 alphanumeric characters with at least one letter and digit
- **Day names**: Full names (Monday-Sunday) and 3-letter abbreviations (Mon-Sun)
- **Time formats**: Both 12-hour (9:30 AM) and 24-hour (14:30) formats
- **Credit hours**: Various formats (3 credits, 4 Cr, 2 CH, etc.)
- **Semester references**: Integers 1-12 or "Semester N" format
- **Section designations**: Regular, Self-Support
- **Course types**: Lab, Lecture, Tutorial
- **Special status**: Repeater, Deficiency, Special

## API Reference

### Counting Functions

- `count_course_codes(text: str) -> int`: Count unique course code patterns
- `count_day_names(text: str) -> int`: Count distinct day name references
- `count_time_patterns(text: str) -> int`: Count time pattern occurrences
- `count_credit_hours(text: str) -> int`: Count credit hour patterns
- `count_semester_references(text: str) -> int`: Count distinct semester numbers (1-12)

### Extraction Functions

- `extract_course_codes(text: str) -> List[str]`: Extract all course codes
- `extract_day_names(text: str) -> List[str]`: Extract and normalize day names to full names
- `extract_times(text: str) -> List[str]`: Extract time values preserving exact format
- `extract_credit_hours(text: str) -> List[Tuple[int, str]]`: Extract (value, full_text) tuples
- `extract_semester_numbers(text: str) -> List[int]`: Extract valid semester numbers (1-12)

### Normalization Functions

- `normalize_course_type(text: str) -> str`: Returns "Lab", "Lecture", "Tutorial", or "Unknown"
- `normalize_section(text: str) -> str`: Returns "Regular", "Self-Support", or "Unknown"
- `normalize_special_status(text: str) -> str`: Returns "Repeater", "Deficiency", "Special", or None

### Validation Functions

- `validate_course_code(code: str) -> bool`: Validate course code format and constraints
- `validate_time_format(time_str: str) -> bool`: Validate time string format
- `has_structured_layout(text: str, min_rows: int = 3) -> bool`: Check for tabular/structured data

## Usage Examples

### Timetable Detection

```python
from app.rag.structured_extraction.detectors import (
    count_course_codes,
    count_day_names,
    count_time_patterns,
    has_structured_layout
)

timetable_text = """
CS301 Data Structures    Lecture  Monday    9:00 AM - 11:00 AM   Room A-101
MATH201 Calculus II      Lecture  Tuesday   10:00 AM - 12:00 PM  Room B-205
"""

# Detection thresholds from requirements:
# - Course codes: >= 3
# - Day names: >= 2
# - Time patterns: >= 3

if (count_course_codes(timetable_text) >= 3 and
    count_day_names(timetable_text) >= 2 and
    count_time_patterns(timetable_text) >= 3 and
    has_structured_layout(timetable_text)):
    print("Document classified as: timetable")
```

### Scheme of Study Detection

```python
from app.rag.structured_extraction.detectors import (
    count_course_codes,
    count_semester_references,
    count_credit_hours,
    has_structured_layout
)

scheme_text = """
Semester 1
CS101 Introduction to Computing    3 credits    Core
MATH101 Calculus I                 3 credits    Core
"""

# Detection thresholds from requirements:
# - Semester references: >= 5
# - Course codes: >= 10
# - Credit hours: >= 8

if (count_semester_references(scheme_text) >= 5 and
    count_course_codes(scheme_text) >= 10 and
    count_credit_hours(scheme_text) >= 8 and
    has_structured_layout(scheme_text)):
    print("Document classified as: scheme_of_study")
```

### Data Extraction

```python
from app.rag.structured_extraction.detectors import (
    extract_course_codes,
    extract_day_names,
    extract_times,
    normalize_course_type,
    normalize_section
)

text = "CS301 Data Structures Lab Monday 9:00 AM - 11:00 AM Regular section"

codes = extract_course_codes(text)  # ['CS301']
days = extract_day_names(text)      # ['Monday']
times = extract_times(text)         # ['9:00 AM', '11:00 AM']
course_type = normalize_course_type(text)  # 'Lab'
section = normalize_section(text)   # 'Regular'
```

## Pattern Details

### Course Code Pattern
- **Format**: 4-10 alphanumeric characters
- **Constraints**: Must contain at least one letter AND one digit
- **Examples**: `CS101`, `MATH2201`, `BIO123A`, `ENG1234`
- **Invalid**: `CS1` (too short), `COURSE` (no digit), `12345` (no letter)

### Day Name Pattern
- **Full names**: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
- **Abbreviations**: Mon, Tue, Wed, Thu, Fri, Sat, Sun
- **Case-insensitive**: Matches any case variation
- **Normalization**: Abbreviations are expanded to full names

### Time Pattern
- **12-hour format**: `9:30 AM`, `2:45 PM`, `01:15 pm`
- **24-hour format**: `09:30`, `14:45`, `23:59`
- **Preservation**: Extract functions preserve exact character sequences
- **Validation**: Validates hour (0-23) and minute (0-59) ranges

### Credit Hours Pattern
- **Formats**: `3 credits`, `4 credit`, `3 Cr`, `4 CH`, `3 Credit Hours`
- **Case-insensitive**: Matches any case variation
- **Extraction**: Returns integer value and full matched text

### Semester Reference Pattern
- **With keyword**: `Semester 1`, `Semester 5`, `Semester 12`
- **Number only**: `1`, `5`, `12` (in appropriate context)
- **Range**: Only accepts integers 1-12
- **Out-of-range**: Semester 0, 13, 15, etc. are rejected

## Testing

Run the comprehensive test suite:

```bash
# Using pytest (if available)
cd backend
python -m pytest app/rag/structured_extraction/detectors/patterns.test.py -v

# Or run manual verification
python3 -c "
from app.rag.structured_extraction.detectors import count_course_codes
text = 'CS101 MATH2201 BIO123A'
print(f'Found {count_course_codes(text)} course codes')
"
```

## Requirements Coverage

This module implements pattern detection utilities for the following requirements:

- **Requirement 1.3**: Course code pattern matching (4-10 alphanumeric with letter and digit)
- **Requirement 1.4**: Day name detection (full names and 3-letter abbreviations)
- **Requirement 1.5**: Time pattern detection (12-hour and 24-hour formats)
- **Requirement 5.3**: Semester reference patterns (1-12 or "Semester N")
- **Requirement 5.4**: Course code pattern for scheme of study documents
- **Requirement 5.5**: Credit hours pattern detection

## Performance Considerations

- All regex patterns are pre-compiled for efficiency
- Counting functions return unique/distinct matches to avoid duplicate counting
- Extraction functions preserve original text formatting when required
- Pattern matching is optimized for typical academic document structures

## Future Enhancements

- Add support for time ranges (9:00 AM - 11:00 AM as single unit)
- Enhance room number pattern matching
- Add faculty name extraction patterns
- Support for international time formats (e.g., 24-hour with periods)
