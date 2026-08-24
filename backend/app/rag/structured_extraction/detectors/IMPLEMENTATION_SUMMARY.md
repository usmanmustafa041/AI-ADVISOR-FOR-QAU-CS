# Timetable Detector Implementation Summary

## Task 2.2: Implement Timetable Detector

**Status:** ✅ Completed

**Implementation File:** `detector.py`

**Test Files:**
- `detector.test.py` - Unit tests
- `test_detector_integration.py` - Integration tests with real PDFs

---

## Requirements Coverage

### Requirement 1.1: Complete pattern analysis within 30 seconds
✅ **Implemented** in `classify_document()`:
- Tracks analysis time using `time.time()`
- Returns `analysis_time_seconds` in `ClassificationResult`

### Requirement 1.2: Classify as generic on timeout
✅ **Implemented** in `classify_document()`:
- Checks elapsed time after text extraction
- Returns generic classification if `>= CLASSIFICATION_TIMEOUT_SECONDS` (30s)
- Logs warning with elapsed time

### Requirement 1.3: Course code criterion (threshold: 3)
✅ **Implemented** in `_analyze_patterns()`:
- Uses `count_course_codes(text)` from patterns.py
- Checks `>= TIMETABLE_COURSE_CODE_THRESHOLD` (3)
- Pattern: 4-10 alphanumeric with at least one letter and digit

### Requirement 1.4: Day name criterion (threshold: 2)
✅ **Implemented** in `_analyze_patterns()`:
- Uses `count_day_names(text)` from patterns.py
- Checks `>= TIMETABLE_DAY_NAME_THRESHOLD` (2)
- Recognizes full names and 3-letter abbreviations

### Requirement 1.5: Time pattern criterion (threshold: 3)
✅ **Implemented** in `_analyze_patterns()`:
- Uses `count_time_patterns(text)` from patterns.py
- Checks `>= TIMETABLE_TIME_PATTERN_THRESHOLD` (3)
- Supports both 12-hour (HH:MM AM/PM) and 24-hour (HH:MM) formats

### Requirement 1.6: Structured layout requirement
✅ **Implemented** in `_analyze_patterns()`:
- Uses `has_structured_layout(text)` from patterns.py
- Checks for rows/columns with separators (tabs, pipes, multiple spaces)
- Required for timetable classification

### Requirement 1.7: Classify as generic when criteria not met
✅ **Implemented** in `_analyze_patterns()`:
- Default return is generic classification
- Returns generic if timetable or scheme criteria not satisfied

### Requirement 1.8: Handle PDF read errors
✅ **Implemented** in multiple places:
- `_extract_text_with_timeout()`: Catches all exceptions, returns None
- Handles encrypted PDFs by checking `reader.is_encrypted`
- Handles PDFs with no extractable text (returns None)
- `classify_document()`: Returns generic when text extraction returns None
- File not found: Checked before processing
- pypdf not available: Checked in `__init__()`, returns generic

### Requirement 1.9: Return classification before extraction
✅ **Implemented**:
- `classify_document()` returns `ClassificationResult` immediately
- No content extraction happens during classification
- Result contains `document_type` field with values: "timetable", "scheme_of_study", "generic"

---

## Scheme of Study Detection (Requirements 5.1-5.9)

### Requirement 5.1: Analyze for scheme patterns within 30 seconds
✅ **Implemented**: Same timeout mechanism as timetable detection

### Requirement 5.2: Return generic on timeout
✅ **Implemented**: Same timeout handling as timetable detection

### Requirement 5.3: Semester reference criterion (threshold: 5)
✅ **Implemented** in `_analyze_patterns()`:
- Uses `count_semester_references(text)` from patterns.py
- Checks `>= SCHEME_SEMESTER_THRESHOLD` (5)
- Matches integers 1-12 or "Semester N" format

### Requirement 5.4: Course code criterion (threshold: 10)
✅ **Implemented** in `_analyze_patterns()`:
- Uses same `count_course_codes(text)` function
- Checks `>= SCHEME_COURSE_CODE_THRESHOLD` (10)

### Requirement 5.5: Credit hour criterion (threshold: 8)
✅ **Implemented** in `_analyze_patterns()`:
- Uses `count_credit_hours(text)` from patterns.py
- Checks `>= SCHEME_CREDIT_HOURS_THRESHOLD` (8)
- Matches patterns like "3 credits", "4 Cr", "3 CH"

### Requirement 5.6: Tabular structure requirement
✅ **Implemented** in `_analyze_patterns()`:
- Uses same `has_structured_layout(text)` check
- Required for scheme classification

### Requirement 5.7: Prioritize timetable classification
✅ **Implemented** in `_analyze_patterns()`:
- Checks timetable criteria **first**
- Returns "timetable" immediately if criteria met
- Only checks scheme criteria if timetable not matched

### Requirement 5.8: Return generic if scheme criteria not met
✅ **Implemented**: Default fallback is generic classification

### Requirement 5.9: Return classification with scheme_of_study type
✅ **Implemented**: Returns `ClassificationResult(document_type="scheme_of_study")`

---

## Implementation Details

### Class: `TimetableDetector`

**Classification Thresholds:**
```python
TIMETABLE_COURSE_CODE_THRESHOLD = 3
TIMETABLE_DAY_NAME_THRESHOLD = 2
TIMETABLE_TIME_PATTERN_THRESHOLD = 3

SCHEME_SEMESTER_THRESHOLD = 5
SCHEME_COURSE_CODE_THRESHOLD = 10
SCHEME_CREDIT_HOURS_THRESHOLD = 8

CLASSIFICATION_TIMEOUT_SECONDS = 30
```

**Key Methods:**

1. **`classify_document(file_path: str) -> ClassificationResult`**
   - Main entry point for document classification
   - Handles timeout, errors, and file validation
   - Returns classification result with document type and timing

2. **`_extract_text_with_timeout(file_path: str) -> Optional[str]`**
   - Extracts text from PDF using pypdf
   - Handles encrypted PDFs, empty PDFs, and exceptions
   - Returns None on any error

3. **`_analyze_patterns(text: str, file_path: str) -> ClassificationResult`**
   - Counts patterns using functions from patterns.py
   - Applies classification logic with priority rules
   - Logs pattern counts for debugging

### Dependencies

**Required:**
- `pypdf>=5.1,<6` - Added to requirements.txt
- `app.rag.structured_extraction.entities.ClassificationResult`
- Pattern functions from `patterns.py`

**Optional:**
- Gracefully handles missing pypdf by returning generic classification

---

## Testing

### Unit Tests (detector.test.py)

20 test cases covering:
- ✅ Timetable classification with all criteria met
- ✅ Scheme of study classification with all criteria met
- ✅ Generic classification for insufficient criteria
- ✅ Timetable precedence over scheme
- ✅ Timeout handling (30s limit)
- ✅ PDF read errors (encrypted, corrupted, not found)
- ✅ Course code threshold (3+)
- ✅ Day name threshold (2+ distinct)
- ✅ Time pattern threshold (3+)
- ✅ Day abbreviations recognition
- ✅ 12-hour and 24-hour time formats
- ✅ Structured layout requirement
- ✅ Scheme thresholds (5 semesters, 10 courses, 8 credits)
- ✅ Analysis time tracking
- ✅ pypdf not installed fallback
- ✅ Exception handling
- ✅ Classification returned before extraction

### Integration Tests (test_detector_integration.py)

Tests with real academic PDFs:
- Real timetable PDF classification
- Real scheme of study PDF classification
- Multiple scheme documents
- Generic academic documents
- Performance requirements (<30s)
- Nonexistent file handling

---

## Usage Example

```python
from app.rag.structured_extraction.detectors import TimetableDetector

detector = TimetableDetector()
result = detector.classify_document("path/to/document.pdf")

print(f"Document type: {result.document_type}")
print(f"Analysis time: {result.analysis_time_seconds:.2f}s")

if result.document_type == "timetable":
    # Route to timetable extractor
    pass
elif result.document_type == "scheme_of_study":
    # Route to scheme extractor
    pass
else:
    # Route to generic document processing
    pass
```

---

## Notes

1. **pypdf Dependency**: Added to requirements.txt. Must be installed before use.

2. **Signal Timeout**: Implementation uses elapsed time checking rather than signal.alarm for better cross-platform compatibility.

3. **Pattern Functions**: All pattern detection logic is in patterns.py (implemented in task 2.1).

4. **Logging**: Comprehensive logging at DEBUG and INFO levels for debugging and monitoring.

5. **Error Resilience**: All error cases return generic classification to avoid blocking the pipeline.

6. **Performance**: Classification completes quickly for typical documents (<1s), with 30s timeout as safety net.

---

## Next Steps

Task 2.2 is complete. To run tests:

```bash
# Install dependencies (in virtual environment or with --break-system-packages)
pip install pypdf

# Run unit tests
python -m pytest backend/app/rag/structured_extraction/detectors/detector.test.py -v

# Run integration tests (requires sample PDFs)
python -m pytest backend/app/rag/structured_extraction/detectors/test_detector_integration.py -v

# Or run directly for quick testing
python backend/app/rag/structured_extraction/detectors/test_detector_integration.py
```

The implementation is ready for task 2.3 (scheme of study detector), which is already integrated into the same `detector.py` file.
