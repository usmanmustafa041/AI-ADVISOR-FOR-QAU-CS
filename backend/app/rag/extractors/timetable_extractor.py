"""Extracts structured data from timetable PDF documents."""

import logging
import re
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from ..structured_extraction.entities import TimetableEntry, ExtractedData
from ..structured_extraction.constants import (
    MIN_SEMESTER,
    MAX_SEMESTER,
    MIN_COURSE_CODE_LENGTH,
    MAX_COURSE_CODE_LENGTH,
    MIN_COURSE_NAME_LENGTH,
    MAX_COURSE_NAME_LENGTH,
    VALID_DAY_NAMES,
    DAY_NAME_ABBREVIATIONS,
    DEFAULT_SECTION,
    DEFAULT_COURSE_TYPE,
    VALID_SECTIONS,
    VALID_COURSE_TYPES,
    VALID_SPECIAL_STATUS,
)
from ..structured_extraction.detectors.patterns import (
    COURSE_CODE_PATTERN,
    DAY_NAME_PATTERN,
    TIME_PATTERN,
    COURSE_TYPE_PATTERN,
    SPECIAL_STATUS_PATTERN,
    SECTION_PATTERN,
    validate_course_code,
    normalize_course_type,
    normalize_section,
    normalize_special_status,
)

logger = logging.getLogger(__name__)


class TimetableExtractor:
    """Extracts structured timetable data from PDF documents."""
    
    def extract_from_pdf(self, file_path: str) -> ExtractedData:
        """
        Extract timetable structured data from a PDF file.
        
        Args:
            file_path: Path to the PDF document
            
        Returns:
            ExtractedData containing extracted timetable entries
            
        Requirements:
            - 2.1-2.17: Full timetable extraction logic
            - 13.1-13.6: Data integrity validation
        """
        path = Path(file_path)
        extracted = ExtractedData(
            document_path=str(path),
            document_type="timetable"
        )
        
        if not pdfplumber:
            extracted.add_error("pdfplumber not installed")
            return extracted
        
        if not path.exists():
            extracted.add_error(f"File not found: {file_path}")
            return extracted
        
        try:
            with pdfplumber.open(str(path)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    self._extract_from_page(page, page_num, extracted)
        except Exception as e:
            extracted.add_error(f"Failed to read PDF: {str(e)}")
            logger.error(f"Error extracting from {file_path}: {e}", exc_info=True)
        
        return extracted
    
    def _extract_from_page(self, page, page_num: int, extracted: ExtractedData) -> None:
        """Extract timetable entries from a single page."""
        try:
            tables = page.extract_tables()
            if not tables:
                return
            
            for table in tables:
                self._extract_from_table(table, page_num, extracted)
        except Exception as e:
            extracted.add_error(f"Error extracting table from page {page_num}: {str(e)}")
            logger.warning(f"Could not extract table from page {page_num}: {e}")
    
    def _extract_from_table(self, table, page_num: int, extracted: ExtractedData) -> None:
        """Extract timetable entries from a table."""
        if not table or len(table) < 3:
            logger.debug("Table too small, skipping")
            return
        
        current_semester = None
        current_section = DEFAULT_SECTION
        current_day = None
        
        for row_idx, row in enumerate(table):
            if not row:
                continue
            
            # Try to extract semester from this row
            sem = self._extract_semester_from_row(row, extracted)
            if sem is not None:
                current_semester = sem
                # Update section if present in semester row
                sec = self._extract_section_from_row(row)
                if sec:
                    current_section = sec
                logger.debug(f"Found semester {current_semester}, section {current_section}")
                continue
            
            # Try to extract day name from first column
            day = self._extract_day_from_row(row)
            if day:
                current_day = day
                logger.debug(f"Found day: {day}")
                continue
            
            # Try to extract timetable entry
            if current_semester and current_day:
                entry = self._extract_entry_from_row(row, current_semester, current_section, current_day, page_num, extracted)
                if entry:
                    extracted.timetable_entries.append(entry)
    
    def _extract_semester_from_row(self, row, extracted: ExtractedData) -> Optional[int]:
        """Extract semester number from a table row."""
        if not row or not row[0]:
            return None
        
        text = str(row[0]).strip()
        match = re.search(r'\b(?:Semester\s+)?(\d{1,2})\b', text, re.IGNORECASE)
        
        if not match:
            return None
        
        try:
            sem = int(match.group(1))
            if MIN_SEMESTER <= sem <= MAX_SEMESTER:
                return sem
            else:
                extracted.add_error(f"Semester {sem} out of range {MIN_SEMESTER}-{MAX_SEMESTER}")
                logger.warning(f"Semester {sem} out of valid range")
                return None
        except ValueError:
            return None
    
    def _extract_section_from_row(self, row) -> Optional[str]:
        """Extract section designation from a table row."""
        text = " ".join(str(cell or "") for cell in row[:min(3, len(row))])
        section = normalize_section(text)
        return section if section != DEFAULT_SECTION else None
    
    def _extract_day_from_row(self, row) -> Optional[str]:
        """Extract day name from first column of row."""
        if not row or not row[0]:
            return None
        
        text = str(row[0]).strip().lower()
        
        # Check full day names
        for day in VALID_DAY_NAMES:
            if day.lower() in text:
                return day
        
        # Check abbreviations
        for abbr, full_day in [("mon", "Monday"), ("tue", "Tuesday"), ("wed", "Wednesday"),
                                ("thu", "Thursday"), ("fri", "Friday"), ("sat", "Saturday"),
                                ("sun", "Sunday")]:
            if abbr in text:
                return full_day
        
        return None
    
    def _extract_entry_from_row(self, row, semester: int, section: str, day: str,
                                page_num: int, extracted: ExtractedData) -> Optional[TimetableEntry]:
        """Extract a complete timetable entry from a table row."""
        try:
            # Extract course code
            course_code = self._extract_course_code_from_row(row, extracted)
            if not course_code:
                extracted.increment_skipped()
                return None
            
            # Extract course name
            course_name = self._extract_course_name_from_row(row)
            if not course_name:
                extracted.add_error(f"No course name found for {course_code}")
                extracted.increment_skipped()
                return None
            
            # Extract times
            start_time, end_time = self._extract_times_from_row(row, extracted)
            if not start_time or not end_time:
                extracted.add_error(f"Invalid times for {course_code}")
                extracted.increment_skipped()
                return None
            
            # Validate time ordering
            if not self._validate_time_ordering(start_time, end_time, course_code, day, extracted):
                extracted.increment_skipped()
                return None
            
            # Extract optional fields
            course_type = self._extract_course_type_from_row(row)
            room = self._extract_room_from_row(row)
            faculty = self._extract_faculty_from_row(row)
            special_status = self._extract_special_status_from_row(row)
            
            # Create entry
            entry = TimetableEntry(
                semester=semester,
                section=section,
                course_code=course_code,
                course_name=course_name,
                course_type=course_type,
                day=day,
                start_time=start_time,
                end_time=end_time,
                room=room,
                faculty=faculty,
                special_status=special_status
            )
            
            return entry
            
        except ValueError as e:
            extracted.add_error(f"Invalid entry data: {str(e)}")
            extracted.increment_skipped()
            return None
        except Exception as e:
            extracted.add_error(f"Error extracting entry: {str(e)}")
            extracted.increment_skipped()
            logger.warning(f"Error extracting entry: {e}")
            return None
    
    def _extract_course_code_from_row(self, row, extracted: ExtractedData) -> Optional[str]:
        """Extract course code from row (search all columns)."""
        for cell in row:
            if not cell:
                continue
            text = str(cell).strip()
            match = COURSE_CODE_PATTERN.search(text)
            if match:
                code = match.group(0).upper()
                if validate_course_code(code):
                    return code
        return None
    
    def _extract_course_name_from_row(self, row) -> Optional[str]:
        """Extract course name from row (typically after course code)."""
        for cell in row:
            if not cell:
                continue
            text = str(cell).strip()
            # Remove course code if present
            text = re.sub(r'\b[A-Z\d]{4,10}\b', '', text).strip()
            if (MIN_COURSE_NAME_LENGTH <= len(text) <= MAX_COURSE_NAME_LENGTH 
                and not any(c.isdigit() for c in text.split()[-1])):
                return text[:MAX_COURSE_NAME_LENGTH]
        return None
    
    def _extract_times_from_row(self, row, extracted: ExtractedData) -> tuple:
        """Extract start and end times from row."""
        times = []
        for cell in row:
            if not cell:
                continue
            text = str(cell).strip()
            matches = TIME_PATTERN.finditer(text)
            for match in matches:
                times.append(match.group(0))
        
        if len(times) >= 2:
            return times[0], times[1]
        return None, None
    
    def _validate_time_ordering(self, start_time: str, end_time: str, course_code: str,
                               day: str, extracted: ExtractedData) -> bool:
        """Validate that start time is before end time (Requirement 2.9, 13.5-13.6)."""
        # Simple string comparison for basic validation
        # In production, proper time parsing would be needed
        if start_time >= end_time:
            extracted.add_error(
                f"Invalid time range for {course_code} on {day}: {start_time}-{end_time}"
            )
            logger.warning(f"Invalid time range: {start_time} >= {end_time}")
            return False
        return True
    
    def _extract_course_type_from_row(self, row) -> str:
        """Extract course type from row."""
        for cell in row:
            if not cell:
                continue
            text = str(cell)
            ctype = normalize_course_type(text)
            if ctype != DEFAULT_COURSE_TYPE:
                return ctype
        return DEFAULT_COURSE_TYPE
    
    def _extract_room_from_row(self, row) -> Optional[str]:
        """Extract room number from row."""
        for cell in row:
            if not cell:
                continue
            text = str(cell).strip()
            # Simple room extraction (can be enhanced)
            if re.match(r'^[A-Z0-9\-\s]{1,50}$', text) and len(text) <= 50:
                if any(c.isdigit() for c in text):  # Must contain at least one digit
                    return text
        return None
    
    def _extract_faculty_from_row(self, row) -> Optional[str]:
        """Extract faculty name from row."""
        for cell in row:
            if not cell:
                continue
            text = str(cell).strip()
            # Check if looks like a name (contains mostly letters)
            if (2 <= len(text) <= 100 and
                sum(c.isalpha() for c in text) / len(text) > 0.7):
                # Exclude common non-name patterns
                if not re.search(r'\b\d{1,2}:\d{2}\b', text):  # No times
                    return text[:100]
        return None
    
    def _extract_special_status_from_row(self, row) -> Optional[str]:
        """Extract special status marker from row."""
        for cell in row:
            if not cell:
                continue
            text = str(cell)
            status = normalize_special_status(text)
            if status:
                return status
        return None
