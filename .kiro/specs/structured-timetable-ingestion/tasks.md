# Implementation Plan: Structured Timetable and Scheme of Study Ingestion

## Overview

This implementation plan breaks down the development of an enhanced RAG ingestion pipeline that processes structured academic documents (timetables and scheme of study PDFs). The pipeline will extract structured data, generate optimized embeddings, and store metadata for accurate semantic retrieval of course schedules and curriculum information.

The implementation uses Python for document processing, leveraging libraries like pdfplumber for PDF extraction and existing embedding infrastructure.

## Tasks

- [x] 1. Set up project structure and core interfaces
  - Create directory structure for new modules: `structured_extraction/`, `detectors/`, `extractors/`, `chunk_generators/`
  - Define Python data classes for structured entities: TimetableEntry, SchemeOfStudyEntry, ClassificationResult, ExtractedData
  - Set up logging configuration for the structured extraction components
  - Define constants for validation rules (semester ranges, credit hour ranges, field length limits)
  - _Requirements: 10.1, 10.8_

- [x] 2. Implement document classification and detection logic
  - [x] 2.1 Implement pattern detection utilities
    - Create regex patterns for course codes (4-10 alphanumeric with letter and digit)
    - Create regex patterns for day names (full and 3-letter abbreviations)
    - Create regex patterns for time formats (12-hour and 24-hour)
    - Create regex patterns for credit hours (integer + "credit"/"credits"/"Cr"/"CH")
    - Create regex patterns for semester references (integers 1-12 or "Semester N")
    - _Requirements: 1.3, 1.4, 1.5, 5.3, 5.4, 5.5_

  - [x] 2.2 Implement timetable detector
    - Create TimetableDetector class with classify_document method
    - Implement PDF content extraction with 30-second timeout
    - Count course code patterns (threshold: 3), day names (threshold: 2), time patterns (threshold: 3)
    - Check for structured row/column layout of detected patterns
    - Return classification result with document type: "timetable", "scheme_of_study", or "generic"
    - Handle PDF read errors by returning "generic" classification
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9_

  - [x] 2.3 Implement scheme of study detector
    - Add scheme of study detection logic to TimetableDetector
    - Count semester references (threshold: 5), course codes (threshold: 10), credit hour patterns (threshold: 8)
    - Check for tabular or list structure of detected elements
    - Prioritize timetable classification when both criteria are met
    - Return classification with scheme_of_study type when criteria satisfied
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [ ]* 2.4 Write unit tests for document classification
    - Test course code pattern matching with valid and invalid formats
    - Test day name detection with full names and abbreviations
    - Test time pattern detection for 12-hour and 24-hour formats
    - Test timetable classification with documents meeting all criteria
    - Test scheme of study classification with documents meeting all criteria
    - Test generic classification fallback for documents not meeting criteria
    - Test timeout behavior for slow PDF processing
    - Test error handling for corrupted/encrypted PDFs
    - _Requirements: 1.1-1.9, 5.1-5.9_

- [ ] 3. Implement timetable structure extraction
  - [ ] 3.1 Create timetable structure extractor
    - Create TimetableExtractor class with extract_from_pdf method
    - Extract semester numbers (validate range 1-12, log warnings for out-of-range)
    - Extract course codes matching pattern (4-10 alphanumeric)
    - Extract course names (5-200 characters) associated with course codes
    - Extract section designations ("Regular" or "Self-Support", case-insensitive, default "Unknown")
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 3.2 Implement timetable schedule data extraction
    - Extract day of week (Monday-Sunday) from timetable entries
    - Extract start time and end time preserving exact character sequences
    - Validate start time occurs before end time within 24-hour period
    - Extract course type ("Lab", "Lecture", or "Tutorial", case-insensitive, default "Unknown")
    - Log validation errors and skip entries with invalid time ranges
    - _Requirements: 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 13.1, 13.2, 13.3, 13.5, 13.6_

  - [ ] 3.3 Implement extraction of optional timetable fields
    - Extract room numbers as text strings (1-50 characters)
    - Extract faculty names as text strings (2-100 characters)
    - Extract special status markers ("Repeater", "Deficiency", "Special", case-insensitive)
    - Skip entries with missing mandatory fields (course code, day, time)
    - Return data structure with arrays of entries organized by semester number
    - _Requirements: 2.13, 2.14, 2.15, 2.16, 2.17_

  - [ ]* 3.4 Write unit tests for timetable extraction
    - Test semester number extraction and validation (valid range 1-12)
    - Test course code and course name extraction
    - Test section designation extraction with case variations
    - Test day and time extraction with various formats
    - Test time validation logic (start before end)
    - Test course type extraction with case variations
    - Test optional field extraction (room, faculty, special status)
    - Test skipping of entries with missing mandatory fields
    - _Requirements: 2.1-2.17, 13.1-13.6_

- [ ] 4. Implement scheme of study structure extraction
  - [ ] 4.1 Create scheme of study structure extractor
    - Create SchemeOfStudyExtractor class with extract_from_pdf method
    - Extract semester numbers (validate range 1-12, log warnings for out-of-range)
    - Extract course codes matching pattern (4-10 alphanumeric)
    - Extract course names (5-200 characters) associated with course codes
    - Extract credit hours as integers (validate range 0-12, default to 0 for invalid)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ] 4.2 Implement prerequisite and category extraction
    - Extract prerequisite course codes as arrays of strings
    - Preserve logical operators (AND, OR) in prerequisite text sequences
    - Extract course category labels ("Core", "Elective", "Required", "Optional", 3-50 characters)
    - Default category to "Unspecified" when cannot be determined
    - Skip entries with missing mandatory fields (course code or credit hours)
    - Return data structure with arrays of courses organized by semester number
    - _Requirements: 6.7, 6.8, 6.9, 6.10, 6.11, 6.12_

  - [ ]* 4.3 Write unit tests for scheme of study extraction
    - Test semester number extraction and validation
    - Test course code and course name extraction
    - Test credit hours extraction and validation (range 0-12)
    - Test prerequisite extraction with single and multiple prerequisites
    - Test prerequisite extraction with logical operators (AND, OR)
    - Test category extraction with various category labels
    - Test default category assignment when unspecified
    - Test skipping entries with missing mandatory fields
    - _Requirements: 6.1-6.12_

- [ ] 5. Implement chunk generation for timetables
  - [ ] 5.1 Create timetable chunk generator
    - Create TimetableChunkGenerator class with generate_chunks method
    - Sort timetable entries by semester number ascending before processing
    - Format chunks with fields in order: semester, section, course code, course name, course type, day, start time, end time, room
    - Use delimiter " | " to separate fields
    - Copy exact time character sequences without reformatting
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 13.1_

  - [ ] 5.2 Implement optional field handling in chunks
    - Include optional fields (room, faculty) after mandatory fields when present
    - Omit optional fields from chunk text when not present (no placeholders)
    - Generate exactly one chunk per timetable entry
    - Enforce maximum 500 chunks per document (log error if exceeded)
    - Return array of chunk objects with text content and position metadata
    - _Requirements: 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

  - [ ]* 5.3 Write unit tests for timetable chunk generation
    - Test chunk formatting with all mandatory fields
    - Test field ordering in generated chunks
    - Test delimiter usage between fields
    - Test time preservation without reformatting
    - Test optional field inclusion when present
    - Test optional field omission when absent
    - Test chunk count limits (500 max per document)
    - Test sorting by semester number
    - _Requirements: 3.1-3.10, 13.1_

- [ ] 6. Implement chunk generation for scheme of study
  - [ ] 6.1 Create scheme of study chunk generator
    - Create SchemeOfStudyChunkGenerator class with generate_chunks method
    - Sort scheme of study entries by semester number ascending before processing
    - Format chunks with fields in order: semester, course code, course name, credit hours, category
    - Use delimiter " | " to separate fields
    - Append prerequisite data with prefix "Prerequisites: " when present
    - Omit prerequisite field when not present (no placeholders)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 6.2 Implement chunk generation limits and output
    - Generate exactly one chunk per scheme of study entry
    - Enforce maximum 500 chunks per document (log error if exceeded)
    - Return array of chunk objects with text content and position metadata
    - _Requirements: 7.6, 7.7, 7.8, 7.9_

  - [ ]* 6.3 Write unit tests for scheme of study chunk generation
    - Test chunk formatting with mandatory fields
    - Test field ordering in generated chunks
    - Test delimiter usage between fields
    - Test prerequisite field inclusion with prefix
    - Test prerequisite field omission when absent
    - Test chunk count limits (500 max per document)
    - Test sorting by semester number
    - _Requirements: 7.1-7.9_

- [ ] 7. Implement metadata enrichment
  - [ ] 7.1 Create timetable metadata enricher
    - Create MetadataEnricher class with enrich_timetable_chunk method
    - Add metadata key-value pairs for: semester (int), course_code (str), section (str), day (str), course_type (str)
    - Add time metadata: start_time (str), end_time (str)
    - Add optional metadata when present: room (str), faculty (str), special_status (str)
    - Serialize metadata to JSON object with string keys and JSON primitive values
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12_

  - [ ] 7.2 Create scheme of study metadata enricher
    - Add enrich_scheme_chunk method to MetadataEnricher
    - Add metadata for: semester (int), course_code (str), credit_hours (int), category (str)
    - Add optional metadata when present: prerequisites (array of str)
    - Serialize metadata to JSON with proper type handling
    - _Requirements: 4.1, 4.12_

  - [ ] 7.3 Implement metadata validation and storage
    - Validate JSON metadata size (max 10 KB, truncate optional fields if exceeded)
    - Ensure metadata conforms to JSONB column format for PostgreSQL
    - Add incomplete_extraction flag (bool) when data is incomplete
    - Log errors when metadata exceeds size limits
    - _Requirements: 4.13, 4.14, 14.7_

  - [ ]* 7.4 Write unit tests for metadata enrichment
    - Test timetable metadata creation with all fields
    - Test scheme of study metadata creation with all fields
    - Test optional field handling in metadata
    - Test JSON serialization format
    - Test metadata size validation and truncation
    - Test incomplete_extraction flag logic
    - _Requirements: 4.1-4.14, 14.7_

- [ ] 8. Implement embedding generation integration
  - [ ] 8.1 Create embedding generator wrapper
    - Create EmbeddingGenerator class wrapping existing embed_text function
    - Accept normalized chunk text as string input
    - Truncate text exceeding 512 tokens before embedding
    - Call embed_text function and receive 384-dimensional float array
    - Validate returned embedding has exactly 384 dimensions
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 10.7_

  - [ ] 8.2 Implement embedding normalization and validation
    - Validate embedding vector contains exactly 384 dimensions
    - Normalize vector to L2 norm = 1.0 (tolerance 0.01)
    - Serialize embedding to PostgreSQL pgvector format as vector(384)
    - Log errors and skip chunks with invalid embeddings
    - _Requirements: 9.4, 9.5, 9.6, 9.7_

  - [ ]* 8.3 Write unit tests for embedding generation
    - Test embedding generation for normal text chunks
    - Test text truncation for content exceeding 512 tokens
    - Test dimension validation (384 dims required)
    - Test L2 normalization within tolerance
    - Test error handling for invalid embeddings
    - Test pgvector serialization format
    - _Requirements: 9.1-9.7_

- [ ] 9. Implement source record management
  - [ ] 9.1 Create source record handler
    - Create SourceRecordHandler class with create_source_record method
    - Generate UUID v4 for each new source record
    - Store absolute file path to original PDF
    - Create database record in sources table with UUID and file_path
    - Return source_id UUID for linking with chunks
    - _Requirements: 8.1, 8.2_

  - [ ] 9.2 Implement file access safety
    - Open PDF files in read-only mode
    - Close all file handles after processing completes
    - Never modify, move, or delete original PDF files
    - _Requirements: 8.5, 8.6, 8.7_

  - [ ] 9.3 Implement chunk-to-source linking
    - Populate source_id foreign key in document_chunks table
    - Link each chunk to its source document via UUID
    - Enable retrieval system to join chunks with sources table
    - Include file_path in query results through table join
    - _Requirements: 8.3, 8.4_

  - [ ]* 9.4 Write unit tests for source record management
    - Test UUID v4 generation for source records
    - Test source record creation in database
    - Test source_id linking in chunks
    - Test file path storage and retrieval
    - Test read-only file access
    - Test file handle cleanup after processing
    - _Requirements: 8.1-8.7_

- [ ] 10. Implement JSONL output generation
  - [ ] 10.1 Create JSONL writer for structured chunks
    - Create JSONLWriter class with write_chunk method
    - Generate chunk records with fields: id (UUID), source_id (UUID), content (str), metadata (JSON), embedding (array)
    - Write one JSON object per line to JSONL file
    - Flush file buffer after every 50 chunks to prevent data loss
    - _Requirements: 10.5, 10.6, 15.9_

  - [ ]* 10.2 Write unit tests for JSONL output
    - Test JSON object formatting per chunk
    - Test one-object-per-line format
    - Test all required fields present in output
    - Test file buffering and flushing behavior
    - _Requirements: 10.5, 10.6, 15.9_

- [ ] 11. Integrate with existing ingestion pipeline
  - [ ] 11.1 Modify ingest_documents.py to use classification
    - Add import statements for TimetableDetector and structure extractors
    - Invoke TimetableDetector before generic document processing
    - Route to TimetableExtractor when document type is "timetable"
    - Route to SchemeOfStudyExtractor when document type is "scheme_of_study"
    - Route to existing document_chunks function when document type is "generic"
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ] 11.2 Implement processing pipeline for structured documents
    - Create orchestration function that chains: detection → extraction → chunk generation → metadata enrichment → embedding generation → JSONL output
    - Pass chunks through existing embed_text function interface (single string arg, 384-float return)
    - Store chunks in document_chunks table using existing schema (id, source_id, content, metadata, embedding, created_at)
    - Maintain backward compatibility with existing pipeline
    - _Requirements: 10.6, 10.7, 10.8, 10.10_

  - [ ] 11.3 Implement fallback to generic processing
    - Catch exceptions during structured extraction
    - Log errors with document file path and error details
    - Fall back to generic document_chunks function on extraction failure
    - Continue processing remaining documents after errors
    - _Requirements: 10.9, 14.1, 14.8_

  - [ ]* 11.4 Write integration tests for pipeline
    - Test end-to-end processing of timetable documents
    - Test end-to-end processing of scheme of study documents
    - Test generic document fallback path
    - Test error handling and fallback behavior
    - Test database storage with existing schema
    - _Requirements: 10.1-10.10, 14.1, 14.8_

- [ ] 12. Checkpoint - Ensure all tests pass
  - Run all unit tests and integration tests
  - Verify core extraction and chunk generation functionality
  - Ensure all tests pass, ask the user if questions arise

- [ ] 13. Implement error handling and logging
  - [ ] 13.1 Implement comprehensive error logging
    - Log skipped entries with: document file path, page number (if available), reason for skipping
    - Log validation errors with: course code, day, time values, and specific error
    - Log warnings when >50% of expected fields are missing from tables
    - Log warnings when documents would exceed 500 chunk limit
    - Log errors for documents that exceed processing time limits
    - _Requirements: 2.2, 2.6, 2.12, 2.16, 6.2, 6.10, 13.7, 14.3, 14.4_

  - [ ] 13.2 Implement document-level error handling
    - Handle file system errors, encryption, unsupported formats by logging and continuing to next document
    - Implement 30-second timeout for classification, fall back to generic on timeout
    - Handle table parsing errors gracefully for tables with <3 columns/rows
    - Fall back to generic processing when >50% of fields are missing
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ] 13.3 Implement batch processing error handling
    - Skip entries with incomplete mandatory fields and log each occurrence
    - Create chunks only from entries with complete mandatory fields
    - Add incomplete_extraction metadata flag for chunks from incomplete data
    - Continue processing remaining documents after individual failures
    - _Requirements: 14.5, 14.6, 14.7, 13.8_

  - [ ] 13.4 Implement processing summary and error reporting
    - Track: total documents processed, successful count, failed count, total chunks created, entries skipped
    - Output processing summary after batch completes
    - Write list of failed file paths to ingestion_errors_{timestamp}.log when failures occur
    - Log summary with all tracked metrics
    - _Requirements: 14.8, 14.9_

  - [ ]* 13.5 Write unit tests for error handling
    - Test handling of encrypted/corrupted PDFs
    - Test timeout behavior for slow processing
    - Test handling of malformed table structures
    - Test fallback to generic processing
    - Test incomplete field handling
    - Test error summary generation
    - Test error log file creation
    - _Requirements: 14.1-14.9_

- [ ] 14. Implement performance optimizations
  - [ ] 14.1 Implement time-based performance controls
    - Enforce 30 * N second limit for N-semester timetable documents
    - Implement 300-second total timeout per document
    - Save chunks generated before timeout and proceed to next document
    - Log timeout errors with document file path
    - _Requirements: 15.1, 15.2_

  - [ ] 14.2 Implement chunk count and memory limits
    - Enforce 500 chunk maximum per document
    - Process only first 500 entries when limit would be exceeded
    - Limit memory usage to 500 MB per document during PDF parsing
    - Release file handles, close PDF readers, free buffers after each document
    - Log errors when memory limit exceeded and skip to next document
    - _Requirements: 15.3, 15.4, 15.6, 15.7, 15.8_

  - [ ] 14.3 Implement sequential batch processing
    - Process documents sequentially one at a time (not parallel)
    - Release all resources between documents
    - Flush JSONL output buffer after every 50 chunks
    - _Requirements: 15.5, 15.9_

  - [ ]* 14.4 Write performance tests
    - Test processing time for multi-semester documents
    - Test timeout behavior at document level
    - Test chunk count limiting
    - Test memory usage stays within limits
    - Test resource cleanup between documents
    - Test buffer flushing behavior
    - _Requirements: 15.1-15.9_

- [ ] 15. Implement data integrity validation
  - [ ] 15.1 Implement time data integrity checks
    - Preserve exact character sequences for times (no reformatting)
    - Skip entries with unparseable time formats and log with raw text
    - Validate chronological ordering within 24-hour period
    - Create separate chunks for overlapping time slots (no merging)
    - Log validation errors with course code, day, and time values
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [ ] 15.2 Implement validation error limits
    - Count validation errors per document
    - Log warning when >50 validation errors in single document
    - Skip remaining entries in document after 50 errors
    - Continue processing other documents in batch
    - _Requirements: 13.8, 13.9_

  - [ ]* 15.3 Write data integrity tests
    - Test time preservation without reformatting
    - Test time validation and chronological ordering
    - Test handling of overlapping time slots
    - Test error logging with complete context
    - Test validation error limits per document
    - _Requirements: 13.1-13.9_

- [ ] 16. Final checkpoint and verification
  - Run complete test suite including unit, integration, and performance tests
  - Verify all requirements are covered by implementation
  - Test with sample timetable and scheme of study documents
  - Verify database schema compatibility
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional test-related sub-tasks that can be skipped for faster MVP delivery
- All core implementation tasks must be completed in order due to dependencies
- The implementation assumes the existing `embed_text` function and database schema remain unchanged
- Error handling is critical due to variability in PDF document formats and quality
- Performance optimizations prevent resource exhaustion when processing large document batches
- Data integrity validation ensures students receive accurate schedule information
- Checkpoints at tasks 12 and 16 allow for incremental validation and user feedback

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3"] },
    { "id": 3, "tasks": ["2.4", "3.1", "4.1"] },
    { "id": 4, "tasks": ["3.2", "4.2"] },
    { "id": 5, "tasks": ["3.3"] },
    { "id": 6, "tasks": ["3.4", "4.3", "5.1", "6.1"] },
    { "id": 7, "tasks": ["5.2", "6.2", "7.1", "7.2"] },
    { "id": 8, "tasks": ["5.3", "6.3", "7.3", "8.1", "9.1"] },
    { "id": 9, "tasks": ["7.4", "8.2", "9.2"] },
    { "id": 10, "tasks": ["8.3", "9.3", "10.1"] },
    { "id": 11, "tasks": ["9.4", "10.2", "11.1"] },
    { "id": 12, "tasks": ["11.2"] },
    { "id": 13, "tasks": ["11.3"] },
    { "id": 14, "tasks": ["11.4", "13.1"] },
    { "id": 15, "tasks": ["13.2", "13.3", "14.1"] },
    { "id": 16, "tasks": ["13.4", "14.2"] },
    { "id": 17, "tasks": ["13.5", "14.3", "15.1"] },
    { "id": 18, "tasks": ["14.4", "15.2"] },
    { "id": 19, "tasks": ["15.3"] }
  ]
}
```
