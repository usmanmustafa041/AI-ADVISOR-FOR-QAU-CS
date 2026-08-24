"""Document detection and classification module."""

from .detector import TimetableDetector
from .patterns import (
    # Pattern constants
    COURSE_CODE_PATTERN,
    DAY_NAME_PATTERN,
    TIME_PATTERN,
    TIME_12HR_PATTERN,
    TIME_24HR_PATTERN,
    CREDIT_HOURS_PATTERN,
    SEMESTER_REFERENCE_PATTERN,
    SECTION_PATTERN,
    COURSE_TYPE_PATTERN,
    SPECIAL_STATUS_PATTERN,
    ROOM_PATTERN,
    
    # Counting functions
    count_course_codes,
    count_day_names,
    count_time_patterns,
    count_credit_hours,
    count_semester_references,
    
    # Extraction functions
    extract_course_codes,
    extract_day_names,
    extract_times,
    extract_credit_hours,
    extract_semester_numbers,
    
    # Normalization functions
    normalize_course_type,
    normalize_section,
    normalize_special_status,
    
    # Validation functions
    validate_course_code,
    validate_time_format,
    has_structured_layout,
)

__all__ = [
    # Detector class
    'TimetableDetector',
    
    # Pattern constants
    'COURSE_CODE_PATTERN',
    'DAY_NAME_PATTERN',
    'TIME_PATTERN',
    'TIME_12HR_PATTERN',
    'TIME_24HR_PATTERN',
    'CREDIT_HOURS_PATTERN',
    'SEMESTER_REFERENCE_PATTERN',
    'SECTION_PATTERN',
    'COURSE_TYPE_PATTERN',
    'SPECIAL_STATUS_PATTERN',
    'ROOM_PATTERN',
    
    # Counting functions
    'count_course_codes',
    'count_day_names',
    'count_time_patterns',
    'count_credit_hours',
    'count_semester_references',
    
    # Extraction functions
    'extract_course_codes',
    'extract_day_names',
    'extract_times',
    'extract_credit_hours',
    'extract_semester_numbers',
    
    # Normalization functions
    'normalize_course_type',
    'normalize_section',
    'normalize_special_status',
    
    # Validation functions
    'validate_course_code',
    'validate_time_format',
    'has_structured_layout',
]
