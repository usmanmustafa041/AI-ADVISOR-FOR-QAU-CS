# Structured Timetable Ingestion - Quick Start Guide

## Installation & Setup

```bash
cd backend

# Verify dependencies are installed
pip install pdfplumber pypdf sqlalchemy psycopg2

# Verify imports work
python3 -c "from app.rag.structured_extraction.pipeline import StructuredIngestionPipeline; print('✓ Ready')"
```

---

## Usage

### Option 1: Command Line with Structured Extraction

Process timetable and scheme of study documents:

```bash
python scripts/ingest_documents.py academic-data/timetable \
    --output chunks_timetable.jsonl \
    --structured \
    --log-level INFO
```

### Option 2: Command Line Generic Processing (Backward Compatible)

Process any documents with existing pipeline:

```bash
python scripts/ingest_documents.py academic-data/university-policies \
    --output chunks_policy.jsonl
```

### Option 3: Programmatic Usage

```python
from app.rag.structured_extraction.pipeline import StructuredIngestionPipeline

# Initialize pipeline
pipeline = StructuredIngestionPipeline()

# Process single document
pipeline.process_document(
    "academic-data/timetable/cs_timetable_spring-2026.pdf",
    "output.jsonl"
)

# Or process entire directory
summary = pipeline.process_batch(
    "academic-data/timetable",
    "output.jsonl"
)

# Print results
print(f"Processed: {summary.total_documents} documents")
print(f"Success: {summary.successful_documents}")
print(f"Chunks: {summary.total_chunks_created}")
print(f"Skipped entries: {summary.total_entries_skipped}")
```

---

## Output Format

The pipeline generates JSONL files with records like:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "source_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "content": "1 | Regular | CS-101 | Problem Solving | Lecture | Monday | 08:35 | 10:05 | 201",
  "metadata": {
    "semester": 1,
    "section": "Regular",
    "course_code": "CS-101",
    "day": "Monday",
    "course_type": "Lecture",
    "start_time": "08:35",
    "end_time": "10:05",
    "room": "201"
  },
  "embedding": [0.127, -0.045, ... 384 total floats]
}
```

---

## Database Storage

### Load into document_chunks table

```python
import json
from sqlalchemy import text
from app.core.database import get_db

db = next(get_db())

with open("chunks_timetable.jsonl") as f:
    for line in f:
        record = json.loads(line)
        
        sql = """
            INSERT INTO document_chunks (id, source_id, content, metadata, embedding, created_at)
            VALUES (:id, :source_id, :content, :metadata::jsonb, :embedding::vector, NOW())
        """
        
        db.execute(text(sql), {
            "id": record["id"],
            "source_id": record["source_id"],
            "content": record["content"],
            "metadata": json.dumps(record["metadata"]),
            "embedding": record["embedding"]
        })

db.commit()
```

---

## Testing

### Run Unit Tests

```bash
python3 app/rag/test_structured_extraction.py
```

### Run Integration Tests

```bash
python3 app/rag/test_integration.py
```

---

## Component Reference

### TimetableDetector
Classifies documents as timetable, scheme_of_study, or generic.

```python
from app.rag.structured_extraction.detectors.detector import TimetableDetector

detector = TimetableDetector()
result = detector.classify_document("document.pdf")
print(result.document_type)  # "timetable" | "scheme_of_study" | "generic"
```

### TimetableExtractor / SchemeOfStudyExtractor
Extracts structured data from PDFs.

```python
from app.rag.extractors.timetable_extractor import TimetableExtractor

extractor = TimetableExtractor()
extracted = extractor.extract_from_pdf("timetable.pdf")

for entry in extracted.timetable_entries:
    print(f"{entry.course_code} on {entry.day}")

print(f"Skipped: {extracted.skipped_entries} entries")
print(f"Errors: {extracted.extraction_errors}")
```

### Chunk Generators
Create normalized text chunks from extracted data.

```python
from app.rag.chunk_generators.timetable_chunk_generator import TimetableChunkGenerator

generator = TimetableChunkGenerator()
chunks = generator.generate_chunks(extracted.timetable_entries)

for chunk in chunks:
    print(f"ID: {chunk.id}")
    print(f"Content: {chunk.content}")
    print(f"Metadata: {chunk.metadata}")
```

### MetadataEnricher
Enriches chunks with structured metadata.

```python
from app.rag.structured_extraction.metadata_enricher import MetadataEnricher

metadata = MetadataEnricher.enrich_timetable_chunk(chunk.metadata)
```

### EmbeddingGenerator
Generates 384-dimensional embeddings for chunks.

```python
from app.rag.structured_extraction.embedding_generator import EmbeddingGenerator

embedding = EmbeddingGenerator.generate_embedding("text content")
print(len(embedding))  # 384
```

---

## Configuration

### Detection Thresholds
Edit `app/rag/structured_extraction/constants.py`:

```python
TIMETABLE_COURSE_CODE_THRESHOLD = 3      # Minimum course codes
TIMETABLE_DAY_NAME_THRESHOLD = 2         # Minimum distinct days
TIMETABLE_TIME_PATTERN_THRESHOLD = 3     # Minimum time patterns

SCHEME_SEMESTER_REF_THRESHOLD = 5        # Minimum semester references
SCHEME_COURSE_CODE_THRESHOLD = 10        # Minimum course codes
SCHEME_CREDIT_HOUR_THRESHOLD = 8         # Minimum credit hour instances
```

### Field Limits
```python
MIN_COURSE_CODE_LENGTH = 4
MAX_COURSE_CODE_LENGTH = 10
MIN_COURSE_NAME_LENGTH = 5
MAX_COURSE_NAME_LENGTH = 200
MIN_CREDIT_HOURS = 0
MAX_CREDIT_HOURS = 12
```

### Processing Limits
```python
MAX_CHUNKS_PER_DOCUMENT = 500            # Chunks per document
MAX_METADATA_SIZE_BYTES = 10 * 1024      # 10 KB
MAX_EXTRACTION_TIME_SECONDS = 300        # 5 minutes total
MAX_DETECTION_TIME_SECONDS = 30          # Classification timeout
MAX_MEMORY_PER_DOCUMENT_MB = 500
```

---

## Error Handling

The pipeline handles errors gracefully:

1. **PDF Read Errors** → Falls back to generic document processing
2. **Classification Timeout** → Treats as generic document
3. **Extraction Errors** → Skips problematic entries and logs
4. **Embedding Failures** → Skips chunk and continues
5. **Database Errors** → Logged but doesn't halt batch

Error logs are written to `ingestion_errors_{timestamp}.log` when failures occur.

---

## Troubleshooting

### "No entries extracted from document"
- Document may not match timetable/scheme patterns
- Check with detector first: `detector.classify_document(file)`
- If classified as generic, extraction won't attempt structured parsing

### "Timeout during classification"
- Large or complex PDF took >30 seconds
- Falls back to generic processing
- Increase timeout in constants.py if needed

### "Embedding dimension mismatch"
- Embedding didn't return 384 dimensions
- Check embed_text() function compatibility
- Verify EMBEDDING_DIMENSION constant

### "Metadata size exceeds limit"
- Large number of optional fields in metadata
- Optional fields are truncated to fit 10 KB limit
- Check incomplete_extraction flag in metadata

---

## Performance Tips

1. **Batch Processing**
   - Use `process_batch()` for directories
   - Sequential processing (not parallel) by design

2. **Memory Usage**
   - 500 MB limit per document
   - Files cleaned up after processing
   - Monitor with system tools

3. **Output Size**
   - Typical timetable: 100-200 chunks (≈50-100 KB JSONL)
   - Each chunk: ~2 KB JSON + 1.5 KB embedding

4. **Database Loading**
   - Use batch inserts for large JSONL files
   - Index on metadata.semester for query speed
   - Vector similarity search uses pgvector extension

---

## API Reference

### StructuredIngestionPipeline

```python
pipeline = StructuredIngestionPipeline()

# Single document
success: bool = pipeline.process_document(file_path: str, output_jsonl: str)

# Batch processing
summary: ProcessingSummary = pipeline.process_batch(input_dir: str, output_jsonl: str)

# Access results
summary.total_documents      # int
summary.successful_documents # int
summary.failed_documents     # int
summary.total_chunks_created # int
summary.total_entries_skipped # int
summary.failed_file_paths    # list[str]
```

### Classification Result

```python
result: ClassificationResult = detector.classify_document(file_path: str)

result.document_type          # "timetable" | "scheme_of_study" | "generic"
result.confidence_score       # float (0.0-1.0) or None
result.analysis_time_seconds  # float
```

### Extracted Data

```python
extracted: ExtractedData = extractor.extract_from_pdf(file_path: str)

extracted.document_type        # "timetable" | "scheme_of_study" | "generic"
extracted.timetable_entries    # list[TimetableEntry]
extracted.scheme_entries       # list[SchemeOfStudyEntry]
extracted.extraction_errors    # list[str]
extracted.skipped_entries      # int
```

---

## Next Steps

1. **Prepare Documents**
   - Place timetable PDFs in `academic-data/timetable/`
   - Place scheme PDFs in `academic-data/bs/`

2. **Run Ingestion**
   ```bash
   python scripts/ingest_documents.py academic-data/timetable \
       --output timetable_chunks.jsonl \
       --structured
   ```

3. **Load into Database**
   - Execute SQL inserts from JSONL
   - Run queries with semantic similarity

4. **Enable RAG Retrieval**
   - Update retrieval pipeline to use structured metadata
   - Implement schedule/curriculum queries

---

## References

- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Requirements**: See `.kiro/specs/structured-timetable-ingestion/requirements.md`
- **Source Code**: `app/rag/structured_extraction/` and `app/rag/extractors/`
- **Tests**: `app/rag/test_*.py`

---

## Support

For issues or questions:
1. Check error logs: `ingestion_errors_*.log`
2. Enable debug logging: `--log-level DEBUG`
3. Run integration tests to verify setup
4. Review implementation summary for design details
