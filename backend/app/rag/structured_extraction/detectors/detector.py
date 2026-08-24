"""Document classification detector for timetables and scheme of study documents."""

import time
import logging
from pathlib import Path
from typing import Optional

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from ..entities import ClassificationResult
from .patterns import (
    count_course_codes,
    count_day_names,
    count_time_patterns,
    count_credit_hours,
    count_semester_references,
    has_structured_layout,
)

logger = logging.getLogger(__name__)


class TimetableDetector:
    """
    Detects and classifies documents as timetable, scheme of study, or generic.
    
    Classification Rules:
    1. Timetable: Needs 3+ course codes, 2+ day names, 3+ time patterns, structured layout
    2. Scheme of Study: Needs 5+ semester references, 10+ course codes, 8+ credit hours, structured layout
    3. Priority: Timetable classification takes precedence over scheme of study
    4. Timeout: 30 seconds maximum for classification, returns generic on timeout
    """
    
    # Classification thresholds
    TIMETABLE_COURSE_CODE_THRESHOLD = 3
    TIMETABLE_DAY_NAME_THRESHOLD = 2
    TIMETABLE_TIME_PATTERN_THRESHOLD = 3
    
    SCHEME_SEMESTER_THRESHOLD = 5
    SCHEME_COURSE_CODE_THRESHOLD = 10
    SCHEME_CREDIT_HOURS_THRESHOLD = 8
    
    CLASSIFICATION_TIMEOUT_SECONDS = 30
    
    def __init__(self):
        """Initialize the detector."""
        if PdfReader is None:
            logger.warning("pypdf not installed, all documents will be classified as generic")
    
    def classify_document(self, file_path: str) -> ClassificationResult:
        """
        Classify a PDF document as timetable, scheme of study, or generic.
        
        Args:
            file_path: Path to the PDF document to classify
            
        Returns:
            ClassificationResult with document_type and analysis_time_seconds
            
        Requirements:
            - 1.1: Complete analysis within 30 seconds
            - 1.2: Return generic on timeout
            - 1.3-1.6: Timetable detection criteria
            - 1.7-1.9: Return classification result
            - 5.1: Analyze for scheme of study patterns within 30 seconds
            - 5.2: Return generic on timeout
            - 5.3-5.6: Scheme of study detection criteria
            - 5.7: Prioritize timetable classification
            - 5.8-5.9: Return classification result
        """
        start_time = time.time()
        
        # Check if pypdf is available
        if PdfReader is None:
            logger.error(f"Cannot classify {file_path}: pypdf not installed")
            return ClassificationResult(
                document_type="generic",
                analysis_time_seconds=time.time() - start_time
            )
        
        # Check if file exists
        if not Path(file_path).exists():
            logger.error(f"File not found: {file_path}")
            return ClassificationResult(
                document_type="generic",
                analysis_time_seconds=time.time() - start_time
            )
        
        try:
            # Extract text from PDF with timeout handling
            text = self._extract_text_with_timeout(file_path)
            
            # Check if we exceeded timeout during extraction
            elapsed = time.time() - start_time
            if elapsed >= self.CLASSIFICATION_TIMEOUT_SECONDS:
                logger.warning(
                    f"Classification timeout for {file_path} ({elapsed:.2f}s), "
                    "classifying as generic"
                )
                return ClassificationResult(
                    document_type="generic",
                    analysis_time_seconds=elapsed
                )
            
            if text is None:
                logger.warning(f"Could not extract text from {file_path}, classifying as generic")
                return ClassificationResult(
                    document_type="generic",
                    analysis_time_seconds=time.time() - start_time
                )
            
            # Perform pattern analysis
            result = self._analyze_patterns(text, file_path)
            result.analysis_time_seconds = time.time() - start_time
            
            logger.info(
                f"Classified {file_path} as {result.document_type} "
                f"in {result.analysis_time_seconds:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error classifying {file_path}: {e}", exc_info=True)
            return ClassificationResult(
                document_type="generic",
                analysis_time_seconds=time.time() - start_time
            )
    
    def _extract_text_with_timeout(self, file_path: str) -> Optional[str]:
        """
        Extract text from PDF with error handling.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text or None on failure
            
        Note: Timeout is handled at the caller level by checking elapsed time
        """
        try:
            reader = PdfReader(file_path)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            return "\n".join(text_parts) if text_parts else None
                
        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {e}")
            return None
    
    def _analyze_patterns(self, text: str, file_path: str) -> ClassificationResult:
        """
        Analyze text patterns to determine document type.
        
        Args:
            text: Extracted text content
            file_path: Path to document (for logging)
            
        Returns:
            ClassificationResult with appropriate document_type
            
        Classification Logic:
            1. Check timetable criteria first (Requirement 5.7)
            2. Check scheme of study criteria second
            3. Default to generic if neither matches
        """
        # Count patterns for timetable detection
        course_code_count = count_course_codes(text)
        day_name_count = count_day_names(text)
        time_pattern_count = count_time_patterns(text)
        
        # Count patterns for scheme of study detection
        semester_ref_count = count_semester_references(text)
        credit_hours_count = count_credit_hours(text)
        
        # Check for structured layout
        has_structure = has_structured_layout(text)
        
        logger.debug(
            f"Pattern counts for {file_path}: "
            f"course_codes={course_code_count}, days={day_name_count}, "
            f"times={time_pattern_count}, semesters={semester_ref_count}, "
            f"credits={credit_hours_count}, structured={has_structure}"
        )
        
        # Check timetable criteria first (Requirements 1.3-1.6, 5.7)
        is_timetable = (
            course_code_count >= self.TIMETABLE_COURSE_CODE_THRESHOLD and
            day_name_count >= self.TIMETABLE_DAY_NAME_THRESHOLD and
            time_pattern_count >= self.TIMETABLE_TIME_PATTERN_THRESHOLD and
            has_structure
        )
        
        if is_timetable:
            logger.info(f"Document {file_path} classified as timetable")
            return ClassificationResult(document_type="timetable")
        
        # Check scheme of study criteria (Requirements 5.3-5.6)
        is_scheme = (
            semester_ref_count >= self.SCHEME_SEMESTER_THRESHOLD and
            course_code_count >= self.SCHEME_COURSE_CODE_THRESHOLD and
            credit_hours_count >= self.SCHEME_CREDIT_HOURS_THRESHOLD and
            has_structure
        )
        
        if is_scheme:
            logger.info(f"Document {file_path} classified as scheme of study")
            return ClassificationResult(document_type="scheme_of_study")
        
        # Default to generic (Requirements 1.7, 5.8)
        logger.info(
            f"Document {file_path} classified as generic "
            f"(timetable criteria not met: courses={course_code_count}>={self.TIMETABLE_COURSE_CODE_THRESHOLD}, "
            f"days={day_name_count}>={self.TIMETABLE_DAY_NAME_THRESHOLD}, "
            f"times={time_pattern_count}>={self.TIMETABLE_TIME_PATTERN_THRESHOLD}; "
            f"scheme criteria not met: semesters={semester_ref_count}>={self.SCHEME_SEMESTER_THRESHOLD}, "
            f"courses={course_code_count}>={self.SCHEME_COURSE_CODE_THRESHOLD}, "
            f"credits={credit_hours_count}>={self.SCHEME_CREDIT_HOURS_THRESHOLD})"
        )
        return ClassificationResult(document_type="generic")
