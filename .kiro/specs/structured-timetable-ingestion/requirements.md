# Requirements Document

## Introduction

**Feature:** Structured Timetable and Scheme of Study Ingestion

This document specifies requirements for enhancing the RAG (Retrieval-Augmented Generation) ingestion pipeline to process structured academic documents including timetables and scheme of study PDFs. The enhancement enables the AI academic advisor to accurately answer queries about course schedules, locations, and curriculum requirements by extracting structured data and generating optimized embeddings for semantic retrieval.

## Glossary

- **Ingestion_Pipeline**: The system component that processes documents from file paths into database-stored chunks with embeddings
- **Timetable**: A structured academic schedule document containing course codes, times, days, rooms, and faculty assignments organized by semester and section
- **Scheme_Of_Study**: A curriculum document specifying required courses, credit hours, prerequisites, and course categories for a degree program
- **Document_Chunk**: A text segment with associated metadata and embedding vector stored in the document_chunks database table
- **Embedding_Vector**: A 384-dimensional numerical representation of text content used for semantic similarity search
- **Timetable_Detector**: Component that identifies whether a PDF document is a timetable based on content patterns
- **Structure_Extractor**: Component that parses structured data from timetables and scheme of study documents
- **Metadata_Enricher**: Component that attaches structured metadata fields to document chunks
- **Chunk_Generator**: Component that produces normalized text representations optimized for semantic retrieval
- **Source_Record**: Database entry linking processed chunks back to the original PDF document
- **Section**: Academic grouping identifier such as Regular or Self-Support
- **Course_Type**: Classification of class session as Lab, Lecture, or Tutorial
- **Semester_Number**: Integer identifier for academic semester (e.g., 1-8 for undergraduate program)

## Requirements

### Requirement 1: Timetable Detection

**User Story:** As the Ingestion_Pipeline, I want to automatically identify timetable documents, so that structured extraction logic is applied only to appropriate documents.

#### Acceptance Criteria

1. WHEN the Ingestion_Pipeline processes a PDF document, THE Timetable_Detector SHALL complete pattern analysis within 30 seconds
2. WHEN pattern analysis exceeds 30 seconds, THE Timetable_Detector SHALL classify the document as a generic document and return the classification result
3. WHEN a document contains at least 3 patterns matching course code format (alphanumeric sequences of 4 to 10 characters containing at least one letter and one digit), THE Timetable_Detector SHALL consider the course code criterion satisfied
4. WHEN a document contains at least 2 distinct day name references (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday, or their 3-letter abbreviations), THE Timetable_Detector SHALL consider the day name criterion satisfied
5. WHEN a document contains at least 3 time patterns in 12-hour format (HH:MM AM/PM) or 24-hour format (HH:MM), THE Timetable_Detector SHALL consider the time pattern criterion satisfied
6. WHEN a document satisfies all three criteria (course codes, day names, and time patterns) AND these elements appear in structured rows or columns, THE Timetable_Detector SHALL classify it as a timetable document
7. WHEN a document satisfies fewer than all three criteria, THE Timetable_Detector SHALL classify it as a generic document
8. IF a PDF document cannot be read due to encryption, corruption, or unsupported format, THEN THE Timetable_Detector SHALL classify it as a generic document
9. THE Timetable_Detector SHALL return a classification result containing a document type field with value "timetable" or "generic" before content extraction begins

### Requirement 2: Timetable Structure Extraction

**User Story:** As the Ingestion_Pipeline, I want to extract structured data from timetables, so that course schedule information is available for precise retrieval.

#### Acceptance Criteria

1. WHEN a document is classified as a timetable, THE Structure_Extractor SHALL extract all semester numbers represented as integers between 1 and 12
2. WHEN the Structure_Extractor identifies a semester number outside the range 1 to 12, THE Structure_Extractor SHALL log a warning and skip that section
3. WHEN the Structure_Extractor processes a timetable section, THE Structure_Extractor SHALL extract course codes matching the pattern of 4 to 10 alphanumeric characters containing at least one letter and one digit
4. WHEN the Structure_Extractor processes a timetable section, THE Structure_Extractor SHALL extract course names as text strings of 5 to 200 characters associated with each course code
5. WHEN the Structure_Extractor processes a timetable section header, THE Structure_Extractor SHALL identify the section designation as exactly "Regular" or exactly "Self-Support" using case-insensitive matching
6. WHEN the Structure_Extractor cannot identify a section designation, THE Structure_Extractor SHALL assign the value "Unknown" and log the occurrence
7. WHEN the Structure_Extractor processes a timetable entry, THE Structure_Extractor SHALL extract the day of week as one of Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, or Sunday
8. WHEN the Structure_Extractor processes a timetable entry, THE Structure_Extractor SHALL extract start time and end time preserving the exact character sequence from the source document
9. WHEN the Structure_Extractor identifies time values, THE Structure_Extractor SHALL validate that start time occurs before end time within the same 24-hour period
10. IF a timetable entry contains start time equal to or after end time, THEN THE Structure_Extractor SHALL log a validation error and skip that entry
11. WHEN the Structure_Extractor processes a timetable entry, THE Structure_Extractor SHALL identify the course type as exactly "Lab", "Lecture", or "Tutorial" using case-insensitive matching
12. WHEN the Structure_Extractor cannot determine course type, THE Structure_Extractor SHALL assign the value "Unknown" and log the occurrence
13. WHERE room numbers are present in the timetable entry, THE Structure_Extractor SHALL extract room numbers as text strings of 1 to 50 characters
14. WHERE faculty names are present in the timetable entry, THE Structure_Extractor SHALL extract faculty names as text strings of 2 to 100 characters
15. WHERE special status markers exist in the timetable entry, THE Structure_Extractor SHALL extract special status as exactly "Repeater", "Deficiency", or "Special" using case-insensitive matching
16. WHEN the Structure_Extractor encounters a timetable entry with missing mandatory fields (course code, day, or time), THE Structure_Extractor SHALL skip that entry and log the occurrence
17. WHEN the Structure_Extractor completes processing a timetable document, THE Structure_Extractor SHALL return a data structure containing arrays of extracted entries organized by semester number

### Requirement 3: Timetable Chunk Generation

**User Story:** As the Ingestion_Pipeline, I want to generate normalized text chunks from timetable data, so that semantic retrieval returns accurate schedule information.

#### Acceptance Criteria

1. WHEN the Chunk_Generator processes timetable data for multiple semesters, THE Chunk_Generator SHALL sort entries by semester number in ascending order before generating chunks
2. WHEN the Chunk_Generator creates a chunk for a timetable entry, THE Chunk_Generator SHALL include exactly these fields in this order: semester number, section, course code, course name, course type, day, start time, end time, and room number
3. WHEN the Chunk_Generator formats a chunk, THE Chunk_Generator SHALL separate fields with the delimiter " | "
4. WHEN the Chunk_Generator formats time information, THE Chunk_Generator SHALL copy the exact character sequence from the extracted start time and end time without reformatting or interpretation
5. WHERE a timetable entry contains optional fields (room number, faculty name), THE Chunk_Generator SHALL include those fields in the chunk text after the mandatory fields
6. WHERE a timetable entry lacks an optional field, THE Chunk_Generator SHALL omit that field from the chunk text without inserting placeholder values
7. WHEN the Chunk_Generator creates chunks for a semester, THE Chunk_Generator SHALL generate exactly one chunk per extracted timetable entry
8. WHEN the Chunk_Generator processes a single timetable document, THE Chunk_Generator SHALL produce between 1 and 500 chunks
9. IF the Chunk_Generator would exceed 500 chunks for a single document, THEN THE Chunk_Generator SHALL log an error and process only the first 500 entries
10. WHEN the Chunk_Generator completes processing, THE Chunk_Generator SHALL return an array of chunk objects containing text content and position metadata

### Requirement 4: Timetable Metadata Storage

**User Story:** As the Ingestion_Pipeline, I want to store rich metadata with timetable chunks, so that retrieval can be filtered and ranked by structured attributes.

#### Acceptance Criteria

1. WHEN the Metadata_Enricher processes a timetable chunk, THE Metadata_Enricher SHALL create a metadata object containing key-value pairs for all extracted fields
2. WHEN the Metadata_Enricher attaches semester number metadata, THE Metadata_Enricher SHALL store it with the key "semester" and an integer value between 1 and 12
3. WHEN the Metadata_Enricher attaches course code metadata, THE Metadata_Enricher SHALL store it with the key "course_code" and the exact alphanumeric string from extraction
4. WHEN the Metadata_Enricher attaches section designation metadata, THE Metadata_Enricher SHALL store it with the key "section" and a string value of "Regular", "Self-Support", or "Unknown"
5. WHEN the Metadata_Enricher attaches day of week metadata, THE Metadata_Enricher SHALL store it with the key "day" and a string value matching one of the seven day names
6. WHEN the Metadata_Enricher attaches course type metadata, THE Metadata_Enricher SHALL store it with the key "course_type" and a string value of "Lab", "Lecture", "Tutorial", or "Unknown"
7. WHEN the Metadata_Enricher attaches start time metadata, THE Metadata_Enricher SHALL store it with the key "start_time" and the exact time string from extraction
8. WHEN the Metadata_Enricher attaches end time metadata, THE Metadata_Enricher SHALL store it with the key "end_time" and the exact time string from extraction
9. WHERE room number exists in the extracted data, THE Metadata_Enricher SHALL store it with the key "room" and the extracted text string
10. WHERE faculty name exists in the extracted data, THE Metadata_Enricher SHALL store it with the key "faculty" and the extracted text string
11. WHERE special status exists in the extracted data, THE Metadata_Enricher SHALL store it with the key "special_status" and a string value of "Repeater", "Deficiency", or "Special"
12. WHEN the Metadata_Enricher serializes metadata for database storage, THE Metadata_Enricher SHALL produce a JSON object with string keys and values conforming to JSON primitive types
13. WHEN the Metadata_Enricher stores metadata in the document_chunks table, THE Metadata_Enricher SHALL place the JSON object in the metadata JSONB column
14. IF the metadata JSON exceeds 10 kilobytes, THEN THE Metadata_Enricher SHALL log an error and truncate optional fields to fit within the limit

### Requirement 5: Scheme of Study Detection

**User Story:** As the Ingestion_Pipeline, I want to automatically identify scheme of study documents, so that curriculum extraction logic is applied to appropriate documents.

#### Acceptance Criteria

1. WHEN the Ingestion_Pipeline processes a PDF document, THE Timetable_Detector SHALL analyze the content for scheme of study patterns within 30 seconds
2. WHEN pattern analysis for scheme of study exceeds 30 seconds, THE Timetable_Detector SHALL classify the document as a generic document and return the classification result
3. WHEN a document contains at least 5 distinct semester number references (integers 1 through 12 or text "Semester" followed by a number), THE Timetable_Detector SHALL consider the semester criterion satisfied
4. WHEN a document contains at least 10 course codes matching the pattern of 4 to 10 alphanumeric characters with at least one letter and one digit, THE Timetable_Detector SHALL consider the course code criterion satisfied
5. WHEN a document contains at least 8 instances of credit hour patterns (integer followed by "credit", "credits", "Cr", "CH", or "Credit Hours"), THE Timetable_Detector SHALL consider the credit hour criterion satisfied
6. WHEN a document satisfies all three criteria (semester references, course codes, and credit hour patterns) AND these elements appear in tabular or list structure, THE Timetable_Detector SHALL classify it as a scheme of study document
7. WHEN a document satisfies the timetable criteria from Requirement 1, THE Timetable_Detector SHALL classify it as a timetable document even if it also satisfies scheme of study criteria
8. WHEN a document satisfies fewer than all three scheme of study criteria and does not satisfy timetable criteria, THE Timetable_Detector SHALL classify it as a generic document
9. THE Timetable_Detector SHALL return a classification result containing a document type field with value "scheme_of_study", "timetable", or "generic" before content extraction begins

### Requirement 6: Scheme of Study Structure Extraction

**User Story:** As the Ingestion_Pipeline, I want to extract structured curriculum data from scheme of study documents, so that course requirements and relationships are available for retrieval.

#### Acceptance Criteria

1. WHEN a document is classified as a scheme of study, THE Structure_Extractor SHALL extract all semester numbers represented as integers between 1 and 12
2. WHEN the Structure_Extractor identifies a semester number outside the range 1 to 12, THE Structure_Extractor SHALL log a warning and skip that section
3. WHEN the Structure_Extractor processes a scheme of study section, THE Structure_Extractor SHALL extract course codes matching the pattern of 4 to 10 alphanumeric characters containing at least one letter and one digit
4. WHEN the Structure_Extractor processes a scheme of study section, THE Structure_Extractor SHALL extract course names as text strings of 5 to 200 characters associated with each course code
5. WHEN the Structure_Extractor processes a scheme of study entry, THE Structure_Extractor SHALL extract credit hours as integer values between 0 and 12 for each course
6. IF a credit hour value is outside the range 0 to 12, THEN THE Structure_Extractor SHALL log a validation error and assign the value 0 to that course
7. WHERE prerequisite information is present as course code references, THE Structure_Extractor SHALL extract prerequisite course codes as an array of strings matching the course code pattern
8. WHERE prerequisite information contains logical operators (AND, OR), THE Structure_Extractor SHALL preserve the exact text sequence including operators
9. WHERE course category labels are present (such as "Core", "Elective", "Required", "Optional"), THE Structure_Extractor SHALL extract the category as a text string of 3 to 50 characters
10. WHEN the Structure_Extractor cannot determine a course category, THE Structure_Extractor SHALL assign the value "Unspecified" and log the occurrence
11. WHEN the Structure_Extractor encounters a scheme of study entry with missing mandatory fields (course code or credit hours), THE Structure_Extractor SHALL skip that entry and log the occurrence
12. WHEN the Structure_Extractor completes processing a scheme of study document, THE Structure_Extractor SHALL return a data structure containing arrays of extracted courses organized by semester number

### Requirement 7: Scheme of Study Chunk Generation

**User Story:** As the Ingestion_Pipeline, I want to generate normalized text chunks from scheme of study data, so that semantic retrieval returns accurate curriculum information.

#### Acceptance Criteria

1. WHEN the Chunk_Generator processes scheme of study data for multiple semesters, THE Chunk_Generator SHALL sort entries by semester number in ascending order before generating chunks
2. WHEN the Chunk_Generator creates a chunk for a scheme of study entry, THE Chunk_Generator SHALL include exactly these fields in this order: semester number, course code, course name, credit hours, and category
3. WHEN the Chunk_Generator formats a chunk, THE Chunk_Generator SHALL separate fields with the delimiter " | "
4. WHERE a scheme of study entry contains prerequisite information, THE Chunk_Generator SHALL append prerequisite data to the chunk text with the prefix "Prerequisites: "
5. WHERE a scheme of study entry lacks prerequisite information, THE Chunk_Generator SHALL omit the prerequisite field from the chunk text without inserting placeholder values
6. WHEN the Chunk_Generator creates chunks for a semester, THE Chunk_Generator SHALL generate exactly one chunk per extracted scheme of study entry
7. WHEN the Chunk_Generator processes a single scheme of study document, THE Chunk_Generator SHALL produce between 1 and 500 chunks
8. IF the Chunk_Generator would exceed 500 chunks for a single document, THEN THE Chunk_Generator SHALL log an error and process only the first 500 entries
9. WHEN the Chunk_Generator completes processing, THE Chunk_Generator SHALL return an array of chunk objects containing text content and position metadata

### Requirement 8: Dual Storage Strategy

**User Story:** As the system administrator, I want both original PDFs and normalized data available, so that users can access source documents while benefiting from structured retrieval.

#### Acceptance Criteria

1. WHEN the Ingestion_Pipeline processes a timetable or scheme of study document, THE Ingestion_Pipeline SHALL create a Source_Record containing the absolute file path to the original PDF
2. WHEN the Ingestion_Pipeline creates a Source_Record, THE Ingestion_Pipeline SHALL assign a unique identifier of type UUID version 4 to that record
3. WHEN the Ingestion_Pipeline stores document chunks in the document_chunks table, THE Ingestion_Pipeline SHALL populate the source_id foreign key column with the UUID from the Source_Record
4. WHEN a retrieval query returns chunks from the document_chunks table, THE retrieval system SHALL join with the sources table to include the file_path field in the results
5. WHEN the Ingestion_Pipeline accesses the original PDF file, THE Ingestion_Pipeline SHALL open the file in read-only mode
6. WHEN the Ingestion_Pipeline completes processing a PDF document, THE Ingestion_Pipeline SHALL close all file handles to that document
7. THE Ingestion_Pipeline SHALL NOT modify, move, or delete the original PDF file at any point during processing

### Requirement 9: Embedding Generation for Structured Content

**User Story:** As the Ingestion_Pipeline, I want to generate embeddings from normalized text, so that semantic similarity search works effectively for structured data.

#### Acceptance Criteria

1. WHEN the Chunk_Generator produces a normalized text chunk, THE Ingestion_Pipeline SHALL pass the text content string to the embed_text function
2. WHEN the embed_text function receives text content exceeding 512 tokens, THE embed_text function SHALL truncate the content to exactly 512 tokens before generating the embedding
3. WHEN the embed_text function processes timetable or scheme of study content, THE embed_text function SHALL return an Embedding_Vector containing exactly 384 floating-point values
4. WHEN the Ingestion_Pipeline receives an Embedding_Vector, THE Ingestion_Pipeline SHALL validate that the vector contains exactly 384 dimensions
5. IF the Embedding_Vector does not contain exactly 384 dimensions, THEN THE Ingestion_Pipeline SHALL log an error and skip storage of that chunk
6. WHEN the Ingestion_Pipeline stores a Document_Chunk in the document_chunks table, THE Ingestion_Pipeline SHALL serialize the Embedding_Vector to PostgreSQL pgvector format as a vector(384) type
7. WHEN the Ingestion_Pipeline writes to the embedding column, THE Ingestion_Pipeline SHALL ensure the vector data is normalized with L2 norm equal to 1.0 within a tolerance of 0.01

### Requirement 10: Integration with Existing Ingestion Pipeline

**User Story:** As a developer, I want the structured ingestion to integrate seamlessly with existing code, so that deployment requires minimal changes to the current system.

#### Acceptance Criteria

1. WHEN ingest_documents.py processes a file from the input file list, THE Ingestion_Pipeline SHALL invoke the Timetable_Detector with the file path before applying generic document processing
2. WHEN the Timetable_Detector returns document type "timetable", THE Ingestion_Pipeline SHALL invoke the Structure_Extractor for timetable processing instead of the generic document_chunks function
3. WHEN the Timetable_Detector returns document type "scheme_of_study", THE Ingestion_Pipeline SHALL invoke the Structure_Extractor for scheme of study processing instead of the generic document_chunks function
4. WHEN the Timetable_Detector returns document type "generic", THE Ingestion_Pipeline SHALL invoke the existing document_chunks function without modification
5. WHEN the Ingestion_Pipeline completes processing a timetable or scheme of study document, THE Ingestion_Pipeline SHALL write output to a JSONL file with one JSON object per line
6. WHEN the Ingestion_Pipeline writes a chunk to JSONL format, THE Ingestion_Pipeline SHALL include fields: id (UUID), source_id (UUID), content (string), metadata (JSON object), and embedding (array of 384 floats)
7. WHEN the Ingestion_Pipeline invokes the embed_text function, THE Ingestion_Pipeline SHALL pass a single string argument and expect an array of 384 floating-point values as the return value
8. WHEN the Ingestion_Pipeline stores chunks in the document_chunks table, THE Ingestion_Pipeline SHALL use the existing table schema with columns: id, source_id, content, metadata, embedding, created_at
9. WHEN the Ingestion_Pipeline encounters an error during structured extraction, THE Ingestion_Pipeline SHALL log the error and fall back to processing the document with the generic document_chunks function
10. THE Ingestion_Pipeline SHALL NOT modify the signature or behavior of the existing embed_text function

### Requirement 11: Retrieval Accuracy for Schedule Queries

**User Story:** As a student, I want to ask questions about my class schedule, so that I receive accurate course times and locations.

#### Acceptance Criteria

1. WHEN a user queries for courses on a specific day using day names (Monday through Sunday), THE retrieval system SHALL filter chunks where the metadata "day" field matches the queried day name using case-insensitive comparison
2. WHEN a user queries for a specific course code, THE retrieval system SHALL perform semantic similarity search on chunk content and filter results where metadata "course_code" field matches the course code pattern using case-insensitive comparison
3. WHEN a user queries for a semester schedule using semester numbers 1 through 12, THE retrieval system SHALL filter chunks where the metadata "semester" field equals the queried semester number
4. WHEN a user queries for course location using room identifiers, THE retrieval system SHALL return chunks where metadata "room" field contains the queried room identifier as a substring
5. WHEN a user queries for course timing, THE retrieval system SHALL return chunks where metadata "start_time" or "end_time" fields contain time values matching the query pattern
6. WHEN the retrieval system ranks results, THE retrieval system SHALL compute a combined score using 70% semantic similarity (cosine distance on embeddings) and 30% metadata match count
7. WHEN the retrieval system returns results, THE retrieval system SHALL limit output to the top 20 chunks ordered by combined score descending
8. WHEN multiple chunks have identical combined scores, THE retrieval system SHALL order those chunks by semester number ascending, then by course code alphabetically

### Requirement 12: Retrieval Accuracy for Curriculum Queries

**User Story:** As a student, I want to ask questions about curriculum requirements, so that I understand course prerequisites and credit hour requirements.

#### Acceptance Criteria

1. WHEN a user queries for courses in a specific semester using semester numbers 1 through 12, THE retrieval system SHALL filter chunks where the metadata "semester" field equals the queried semester number
2. WHEN a user queries for prerequisites of a specific course, THE retrieval system SHALL return chunks where the content contains the substring "Prerequisites: " followed by course codes
3. WHEN a user queries for credit hours of courses, THE retrieval system SHALL return chunks where the content contains digit patterns followed by the term "credit" or "credits"
4. WHEN a user queries for course categories (Core, Elective, Required, Optional), THE retrieval system SHALL return chunks where metadata "category" field matches the queried category using case-insensitive comparison
5. WHEN the retrieval system ranks results for curriculum queries, THE retrieval system SHALL order results by semantic similarity (cosine distance on embeddings) descending
6. WHEN the retrieval system returns results for curriculum queries, THE retrieval system SHALL limit output to the top 20 chunks
7. WHEN a user queries for total credit hours in a semester, THE retrieval system SHALL return all chunks for that semester and include metadata enabling credit hour summation

### Requirement 13: Timetable Data Integrity

**User Story:** As a system administrator, I want the extraction process to preserve schedule accuracy, so that students receive correct class times and avoid scheduling conflicts.

#### Acceptance Criteria

1. WHEN the Structure_Extractor parses time data from a timetable entry, THE Structure_Extractor SHALL copy the exact character sequence including whitespace, colons, and AM/PM indicators without reformatting
2. WHEN the Structure_Extractor encounters a timetable entry with unparseable time format, THE Structure_Extractor SHALL skip that entry and log the occurrence with the raw text content
3. WHEN the Structure_Extractor encounters a timetable entry where start time and end time cannot be determined to have a chronological ordering, THE Structure_Extractor SHALL skip that entry and log the occurrence
4. WHEN the Structure_Extractor identifies overlapping time slots for the same course code on the same day, THE Structure_Extractor SHALL create separate chunk entries for each time slot without merging
5. WHEN the Structure_Extractor parses start time and end time values, THE Structure_Extractor SHALL validate that start time represents an earlier time than end time within a 24-hour period
6. IF start time is equal to or later than end time, THEN THE Structure_Extractor SHALL log a validation error with the course code, day, and time values, and skip that entry
7. WHEN the Ingestion_Pipeline logs a skipped entry, THE Ingestion_Pipeline SHALL include the document file path, page number if available, and the reason for skipping
8. WHEN the Ingestion_Pipeline completes processing a timetable document, THE Ingestion_Pipeline SHALL continue processing remaining documents without halting on individual entry failures
9. WHEN the Ingestion_Pipeline encounters more than 50 validation errors in a single document, THE Ingestion_Pipeline SHALL log a warning that the document may be malformed and skip remaining entries in that document

### Requirement 14: Error Handling for Malformed Documents

**User Story:** As a system administrator, I want graceful handling of malformed documents, so that ingestion continues for valid documents when encountering problematic files.

#### Acceptance Criteria

1. IF a PDF document cannot be opened due to file system errors, encryption, or unsupported format, THEN THE Ingestion_Pipeline SHALL log an error with the file path and error message, then continue processing the next document in the queue
2. IF the Timetable_Detector cannot parse PDF content within 30 seconds, THEN THE Ingestion_Pipeline SHALL classify the document as generic and apply the existing document_chunks function
3. IF the Structure_Extractor encounters table structures with fewer than 3 columns or rows, THEN THE Structure_Extractor SHALL log a warning and attempt to extract data from available cells
4. IF the Structure_Extractor encounters table structures where more than 50% of expected fields are missing, THEN THE Structure_Extractor SHALL log an error and fall back to generic document processing for that document
5. IF the Chunk_Generator receives structured data with missing mandatory fields (course code or semester for timetables, course code or credit hours for schemes of study), THEN THE Chunk_Generator SHALL skip those entries and log each occurrence
6. WHEN the Chunk_Generator processes incomplete structured data, THE Chunk_Generator SHALL create chunks from entries with complete mandatory fields
7. WHEN the Chunk_Generator creates a chunk from incomplete data, THE Chunk_Generator SHALL add a boolean metadata field "incomplete_extraction" with value true
8. WHEN the Ingestion_Pipeline completes processing all documents, THE Ingestion_Pipeline SHALL output a summary containing: total documents processed, successful document count, failed document count, total chunks created, and total entries skipped
9. WHEN the Ingestion_Pipeline summary shows failed document count greater than 0, THE Ingestion_Pipeline SHALL write the list of failed file paths to a separate error log file named "ingestion_errors_{timestamp}.log"

### Requirement 15: Performance for Large Timetable Documents

**User Story:** As a system administrator, I want efficient processing of large timetable PDFs, so that ingestion completes within reasonable time limits.

#### Acceptance Criteria

1. WHEN the Ingestion_Pipeline processes a timetable document containing entries for N semesters, THE Ingestion_Pipeline SHALL complete extraction within 30 * N seconds
2. IF extraction for a single timetable document exceeds 300 seconds total, THEN THE Ingestion_Pipeline SHALL log a timeout error, save chunks generated so far, and proceed to the next document
3. WHEN the Chunk_Generator creates chunks for a complete timetable document, THE Chunk_Generator SHALL produce no more than 500 chunks per document
4. IF a timetable document would generate more than 500 chunks, THEN THE Chunk_Generator SHALL process only the first 500 entries and log a warning with the document file path
5. WHEN the Ingestion_Pipeline processes a batch of N documents, THE Ingestion_Pipeline SHALL process documents sequentially one at a time
6. WHEN the Ingestion_Pipeline completes processing a single document, THE Ingestion_Pipeline SHALL release all file handles, close PDF readers, and free temporary memory buffers before processing the next document
7. WHEN the Ingestion_Pipeline allocates memory for PDF parsing, THE Ingestion_Pipeline SHALL limit memory usage to 500 megabytes per document
8. IF memory usage exceeds 500 megabytes during processing of a document, THEN THE Ingestion_Pipeline SHALL log an error, release resources, and skip to the next document
9. WHEN the Ingestion_Pipeline writes chunks to the JSONL output file, THE Ingestion_Pipeline SHALL flush the file buffer after every 50 chunks to prevent data loss on interruption

