"""Extracts structured data from scheme of study PDF documents."""

import logging
import re
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from ..structured_extraction.entities import SchemeOfStudyEntry, ExtractedData
from ..structured_extraction.constants import (
    MIN_SEMESTER,
    MAX_SEMESTER,
    MIN_CREDIT_HOURS,
    MAX_CREDIT_HOURS,
    MIN_COURSE_CODE_LENGTH,
    MAX_COURSE_CODE_LENGTH,
    MIN_COURSE_NAME_LENGTH,
    MAX_COURSE_NAME_LENGTH,
    MIN_CATEGORY_LENGTH,
    MAX_CATEGORY_LENGTH,
    DEFAULT_CATEGORY,
)
from ..structured_extraction.detectors.patterns import (
    COURSE_CODE_PATTERN,
    CREDIT_HOURS_PATTERN,
    validate_course_code,
)

logger = logging.getLogger(__name__)


class SchemeOfStudyExtractor:
    """Extracts structured scheme of study data from PDF documents."""
    
    def extract_from_pdf(self, file_path: str) -> ExtractedData:
        """
        Extract scheme of study structured data from a PDF file.
        
        Args:
            file_path: Path to the PDF document
            
        Returns:
            ExtractedData containing extracted scheme of study entries
            
        Requirements:
            - 6.1-6.12: Full scheme of study extraction logic
        """
        path = Path(file_path)
        extracted = ExtractedData(
            document_path=str(path),
            document_type="scheme_of_study"
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
        """Extract scheme entries from a single page."""
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
        """Extract scheme entries from a table."""
        if not table or len(table) < 3:
            logger.debug("Table too small, skipping")
            return
        
        current_semester = None
        
        for row_idx, row in enumerate(table):
            if not row:
                continue
            
            # Try to extract semester from this row
            sem = self._extract_semester_from_row(row, extracted)
            if sem is not None:
                current_semester = sem
                logger.debug(f"Found semester {current_semester}")
                continue
            
            # Try to extract scheme entry
            if current_semester:
                entry = self._extract_entry_from_row(row, current_semester, page_num, extracted)
                if entry:
                    extracted.scheme_entries.append(entry)
    
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
    
    def _extract_entry_from_row(self, row, semester: int, page_num: int,
                               extracted: ExtractedData) -> Optional[SchemeOfStudyEntry]:
        """Extract a complete scheme of study entry from a table row."""
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
            
            # Extract credit hours (mandatory)
            credit_hours = self._extract_credit_hours_from_row(row, extracted)
            if credit_hours is None:
                extracted.add_error(f"No credit hours found for {course_code}")
                extracted.increment_skipped()
                return None
            
            # Extract optional fields
            category = self._extract_category_from_row(row)
            prerequisites = self._extract_prerequisites_from_row(row)
            
            # Create entry
            entry = SchemeOfStudyEntry(
                semester=semester,
                course_code=course_code,
                course_name=course_name,
                credit_hours=credit_hours,
                category=category,
                prerequisites=prerequisites
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
    
    def _extract_credit_hours_from_row(self, row, extracted: ExtractedData) -> Optional[int]:
        """Extract credit hours from row (Requirement 6.5-6.6)."""
        for cell in row:
            if not cell:
                continue
            text = str(cell).strip()
            match = CREDIT_HOURS_PATTERN.search(text)
            if match:
                try:
                    credits = int(match.group(1))
                    if MIN_CREDIT_HOURS <= credits <= MAX_CREDIT_HOURS:
                        return credits
                    else:
                        extracted.add_error(
                            f"Credit hours {credits} out of range {MIN_CREDIT_HOURS}-{MAX_CREDIT_HOURS}, "
                            "assigning 0"
                        )
                        return 0
                except ValueError:
                    continue
        return None
    
    def _extract_category_from_row(self, row) -> str:
        """Extract course category from row (Requirement 6.9-6.10)."""
        for cell in row:
            if not cell:
                continue
            text = str(cell).strip()
            # Look for category keywords
            for keyword in ["Core", "Elective", "Required", "Optional", "Compulsory", "Major"]:
                if keyword.lower() in text.lower():
                    return keyword if len(keyword) >= MIN_CATEGORY_LENGTH else DEFAULT_CATEGORY
        
        return DEFAULT_CATEGORY
    
    def _extract_prerequisites_from_row(self, row) -> Optional[list[str]]:
        """Extract prerequisites from row (Requirement 6.7-6.8)."""
        for cell in row:
            if not cell:
                continue
            text = str(cell).strip()
            # Look for prerequisite keywords
            if "prerequisite" in text.lower() or "pre-requisite" in text.lower():
                # Extract course codes with logical operators
                prereqs = []
                matches = COURSE_CODE_PATTERN.findall(text)
                for match in matches:
                    prereqs.append(match.upper())
                
                # Also preserve logical operators if present
                if "and" in text.lower() or "or" in text.lower():
                    # Return the full text to preserve operators
                    return [text]
                
                return prereqs if prereqs else None
        
        return None
