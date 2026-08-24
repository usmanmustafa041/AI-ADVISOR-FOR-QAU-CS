"""Data classes for structured extraction entities."""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class TimetableEntry:
    """Represents a single timetable entry with course schedule information.
    
    Attributes:
        semester: Semester number (1-12)
        section: Section designation ("Regular", "Self-Support", or "Unknown")
        course_code: Course identifier (4-10 alphanumeric characters)
        course_name: Full course name (5-200 characters)
        course_type: Type of class ("Lab", "Lecture", "Tutorial", or "Unknown")
        day: Day of week (Monday-Sunday)
        start_time: Start time as exact string from source
        end_time: End time as exact string from source
        room: Optional room number (1-50 characters)
        faculty: Optional faculty name (2-100 characters)
        special_status: Optional status ("Repeater", "Deficiency", or "Special")
    """
    
    semester: int
    section: str
    course_code: str
    course_name: str
    course_type: str
    day: str
    start_time: str
    end_time: str
    room: Optional[str] = None
    faculty: Optional[str] = None
    special_status: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate field constraints after initialization."""
        if not (1 <= self.semester <= 12):
            raise ValueError(f"Semester must be between 1 and 12, got {self.semester}")
        if len(self.course_code) < 4 or len(self.course_code) > 10:
            raise ValueError(f"Course code must be 4-10 characters, got {len(self.course_code)}")
        if len(self.course_name) < 5 or len(self.course_name) > 200:
            raise ValueError(f"Course name must be 5-200 characters, got {len(self.course_name)}")
        if self.room and len(self.room) > 50:
            raise ValueError(f"Room number must be at most 50 characters, got {len(self.room)}")
        if self.faculty and (len(self.faculty) < 2 or len(self.faculty) > 100):
            raise ValueError(f"Faculty name must be 2-100 characters, got {len(self.faculty)}")


@dataclass
class SchemeOfStudyEntry:
    """Represents a single scheme of study entry with curriculum information.
    
    Attributes:
        semester: Semester number (1-12)
        course_code: Course identifier (4-10 alphanumeric characters)
        course_name: Full course name (5-200 characters)
        credit_hours: Credit hours for the course (0-12)
        category: Course category (3-50 characters, or "Unspecified")
        prerequisites: Optional list of prerequisite course codes or text with logical operators
    """
    
    semester: int
    course_code: str
    course_name: str
    credit_hours: int
    category: str = "Unspecified"
    prerequisites: Optional[list[str]] = None
    
    def __post_init__(self) -> None:
        """Validate field constraints after initialization."""
        if not (1 <= self.semester <= 12):
            raise ValueError(f"Semester must be between 1 and 12, got {self.semester}")
        if len(self.course_code) < 4 or len(self.course_code) > 10:
            raise ValueError(f"Course code must be 4-10 characters, got {len(self.course_code)}")
        if len(self.course_name) < 5 or len(self.course_name) > 200:
            raise ValueError(f"Course name must be 5-200 characters, got {len(self.course_name)}")
        if not (0 <= self.credit_hours <= 12):
            raise ValueError(f"Credit hours must be between 0 and 12, got {self.credit_hours}")
        if len(self.category) < 3 or len(self.category) > 50:
            raise ValueError(f"Category must be 3-50 characters, got {len(self.category)}")


@dataclass
class ClassificationResult:
    """Result of document type classification.
    
    Attributes:
        document_type: Type of document ("timetable", "scheme_of_study", or "generic")
        confidence_score: Optional confidence score for the classification (0.0-1.0)
        analysis_time_seconds: Time taken for pattern analysis
    """
    
    document_type: Literal["timetable", "scheme_of_study", "generic"]
    confidence_score: Optional[float] = None
    analysis_time_seconds: float = 0.0
    
    def __post_init__(self) -> None:
        """Validate confidence score range."""
        if self.confidence_score is not None:
            if not (0.0 <= self.confidence_score <= 1.0):
                raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {self.confidence_score}")


@dataclass
class ExtractedData:
    """Container for extracted structured data from a document.
    
    Attributes:
        document_path: Path to the source document
        document_type: Type of document processed
        timetable_entries: List of timetable entries (for timetable documents)
        scheme_entries: List of scheme of study entries (for scheme documents)
        extraction_errors: List of error messages encountered during extraction
        skipped_entries: Count of entries skipped due to validation errors
    """
    
    document_path: str
    document_type: Literal["timetable", "scheme_of_study", "generic"]
    timetable_entries: list[TimetableEntry] = field(default_factory=list)
    scheme_entries: list[SchemeOfStudyEntry] = field(default_factory=list)
    extraction_errors: list[str] = field(default_factory=list)
    skipped_entries: int = 0
    
    def add_error(self, error_message: str) -> None:
        """Add an extraction error message."""
        self.extraction_errors.append(error_message)
    
    def increment_skipped(self) -> None:
        """Increment the skipped entries counter."""
        self.skipped_entries += 1
