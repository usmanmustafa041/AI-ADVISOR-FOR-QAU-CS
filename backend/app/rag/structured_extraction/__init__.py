"""Structured extraction module for academic documents.

This module provides components for extracting structured data from
timetables and scheme of study documents.
"""

from .entities import (
    ClassificationResult,
    ExtractedData,
    SchemeOfStudyEntry,
    TimetableEntry,
)

__all__ = [
    "ClassificationResult",
    "ExtractedData",
    "SchemeOfStudyEntry",
    "TimetableEntry",
]
