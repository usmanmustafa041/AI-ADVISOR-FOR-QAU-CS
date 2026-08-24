"""Constants and validation rules for structured extraction."""

# Semester validation
MIN_SEMESTER = 1
MAX_SEMESTER = 12

# Credit hours validation
MIN_CREDIT_HOURS = 0
MAX_CREDIT_HOURS = 12

# Field length limits
MIN_COURSE_CODE_LENGTH = 4
MAX_COURSE_CODE_LENGTH = 10

MIN_COURSE_NAME_LENGTH = 5
MAX_COURSE_NAME_LENGTH = 200

MIN_FACULTY_NAME_LENGTH = 2
MAX_FACULTY_NAME_LENGTH = 100

MAX_ROOM_LENGTH = 50

MIN_CATEGORY_LENGTH = 3
MAX_CATEGORY_LENGTH = 50

# Detection thresholds for timetable documents
TIMETABLE_COURSE_CODE_THRESHOLD = 3
TIMETABLE_DAY_NAME_THRESHOLD = 2
TIMETABLE_TIME_PATTERN_THRESHOLD = 3

# Detection thresholds for scheme of study documents
SCHEME_SEMESTER_REF_THRESHOLD = 5
SCHEME_COURSE_CODE_THRESHOLD = 10
SCHEME_CREDIT_HOUR_THRESHOLD = 8

# Processing limits
MAX_CHUNKS_PER_DOCUMENT = 500
MAX_METADATA_SIZE_BYTES = 10 * 1024  # 10 KB
MAX_EXTRACTION_TIME_SECONDS = 300  # 5 minutes
MAX_DETECTION_TIME_SECONDS = 30
MAX_MEMORY_PER_DOCUMENT_MB = 500

# Error handling
MAX_VALIDATION_ERRORS_PER_DOCUMENT = 50

# Embedding configuration
EMBEDDING_DIMENSION = 384
MAX_EMBEDDING_TOKEN_LENGTH = 512

# Day names
VALID_DAY_NAMES = {
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
}

DAY_NAME_ABBREVIATIONS = {
    "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"
}

# Section designations
VALID_SECTIONS = {"Regular", "Self-Support", "Unknown"}

# Course types
VALID_COURSE_TYPES = {"Lab", "Lecture", "Tutorial", "Unknown"}

# Special status markers
VALID_SPECIAL_STATUS = {"Repeater", "Deficiency", "Special"}

# Default values
DEFAULT_SECTION = "Unknown"
DEFAULT_COURSE_TYPE = "Unknown"
DEFAULT_CATEGORY = "Unspecified"

# Chunk formatting
CHUNK_FIELD_DELIMITER = " | "
PREREQUISITE_PREFIX = "Prerequisites: "

# File handling
SUPPORTED_FILE_EXTENSIONS = {".pdf", ".txt", ".md", ".csv"}
