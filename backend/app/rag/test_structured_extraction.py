"""Unit tests for structured extraction components."""

import json
import tempfile
from pathlib import Path
from uuid import UUID

from app.rag.chunk_generators.timetable_chunk_generator import TimetableChunkGenerator
from app.rag.chunk_generators.scheme_chunk_generator import SchemeOfStudyChunkGenerator
from app.rag.structured_extraction.entities import TimetableEntry, SchemeOfStudyEntry
from app.rag.structured_extraction.metadata_enricher import MetadataEnricher
from app.rag.structured_extraction.embedding_generator import EmbeddingGenerator
from app.rag.structured_extraction.jsonl_writer import JSONLWriter
from app.rag.structured_extraction.source_handler import SourceRecordHandler


class TestTimetableChunkGenerator:
    """Tests for timetable chunk generation."""
    
    def test_generate_chunks_single_entry(self):
        """Test chunk generation from a single timetable entry."""
        entry = TimetableEntry(
            semester=1,
            section="Regular",
            course_code="CS101",
            course_name="Introduction to Computer Science",
            course_type="Lecture",
            day="Monday",
            start_time="09:00",
            end_time="10:30",
            room="Lab-101"
        )
        
        generator = TimetableChunkGenerator()
        chunks = generator.generate_chunks([entry])
        
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.id  # Has UUID
        assert chunk.content
        assert "CS101" in chunk.content
        assert "Monday" in chunk.content
        assert "09:00" in chunk.content
        assert chunk.metadata["semester"] == 1
        assert chunk.metadata["course_code"] == "CS101"
    
    def test_generate_chunks_sorting_by_semester(self):
        """Test that chunks are sorted by semester."""
        entries = [
            TimetableEntry(
                semester=2, section="Regular", course_code="CS201",
                course_name="Data Structures", course_type="Lecture",
                day="Tuesday", start_time="10:00", end_time="11:30"
            ),
            TimetableEntry(
                semester=1, section="Regular", course_code="CS101",
                course_name="Introduction to CS", course_type="Lecture",
                day="Monday", start_time="09:00", end_time="10:30"
            ),
        ]
        
        generator = TimetableChunkGenerator()
        chunks = generator.generate_chunks(entries)
        
        assert len(chunks) == 2
        assert chunks[0].metadata["semester"] == 1
        assert chunks[1].metadata["semester"] == 2
    
    def test_chunk_contains_required_fields(self):
        """Test that chunk contains all required fields in correct order."""
        entry = TimetableEntry(
            semester=1, section="Self-Support", course_code="CS101",
            course_name="Intro to CS", course_type="Lab",
            day="Wednesday", start_time="14:00", end_time="16:00",
            room="Lab-205", faculty="Dr. Smith"
        )
        
        generator = TimetableChunkGenerator()
        chunks = generator.generate_chunks([entry])
        chunk = chunks[0]
        
        # Verify field order and delimiter
        parts = chunk.content.split(" | ")
        assert parts[0] == "1"  # semester
        assert parts[1] == "Self-Support"  # section
        assert parts[2] == "CS101"  # course_code
        assert parts[3] == "Intro to CS"  # course_name
        assert parts[4] == "Lab"  # course_type
        assert parts[5] == "Wednesday"  # day
        assert parts[6] == "14:00"  # start_time
        assert parts[7] == "16:00"  # end_time
        assert parts[8] == "Lab-205"  # room (optional)


class TestSchemeChunkGenerator:
    """Tests for scheme of study chunk generation."""
    
    def test_generate_chunks_with_prerequisites(self):
        """Test chunk generation including prerequisites."""
        entry = SchemeOfStudyEntry(
            semester=3,
            course_code="CS301",
            course_name="Algorithms",
            credit_hours=3,
            category="Core",
            prerequisites=["CS201", "CS101"]
        )
        
        generator = SchemeOfStudyChunkGenerator()
        chunks = generator.generate_chunks([entry])
        
        assert len(chunks) == 1
        chunk = chunks[0]
        assert "Prerequisites: " in chunk.content
        assert "CS201" in chunk.content
        assert "CS101" in chunk.content
    
    def test_chunk_formatting_without_prerequisites(self):
        """Test chunk formatting when prerequisites are absent."""
        entry = SchemeOfStudyEntry(
            semester=1,
            course_code="CS101",
            course_name="Intro to CS",
            credit_hours=4,
            category="Core"
        )
        
        generator = SchemeOfStudyChunkGenerator()
        chunks = generator.generate_chunks([entry])
        chunk = chunks[0]
        
        # Should not have "Prerequisites:" prefix
        assert "Prerequisites: " not in chunk.content
        
        # Verify field order
        parts = chunk.content.split(" | ")
        assert parts[0] == "1"  # semester
        assert parts[1] == "CS101"  # course_code
        assert parts[2] == "Intro to CS"  # course_name
        assert parts[3] == "4"  # credit_hours
        assert parts[4] == "Core"  # category


class TestMetadataEnricher:
    """Tests for metadata enrichment."""
    
    def test_enrich_timetable_metadata(self):
        """Test timetable metadata enrichment."""
        metadata = {
            "semester": 1,
            "section": "Regular",
            "course_code": "CS101",
            "day": "Monday",
            "course_type": "Lecture",
            "start_time": "09:00",
            "end_time": "10:30",
            "room": "Lab-101",
            "faculty": "Dr. Smith"
        }
        
        enriched = MetadataEnricher.enrich_timetable_chunk(metadata)
        
        assert enriched["semester"] == 1
        assert enriched["course_code"] == "CS101"
        assert enriched["room"] == "Lab-101"
        assert enriched["faculty"] == "Dr. Smith"
        assert "incomplete_extraction" not in enriched
    
    def test_incomplete_flag(self):
        """Test that incomplete flag is added when specified."""
        metadata = {"semester": 1, "course_code": "CS101"}
        
        enriched = MetadataEnricher.enrich_timetable_chunk(metadata, incomplete=True)
        
        assert enriched["incomplete_extraction"] is True


class TestEmbeddingGenerator:
    """Tests for embedding generation."""
    
    def test_generate_embedding_returns_384_dims(self):
        """Test that embedding has 384 dimensions."""
        text = "This is a test chunk for embedding generation."
        embedding = EmbeddingGenerator.generate_embedding(text)
        
        assert embedding is not None
        assert len(embedding) == 384
        assert all(isinstance(x, (int, float)) for x in embedding)
    
    def test_embedding_l2_normalized(self):
        """Test that embedding is L2 normalized."""
        text = "Test content for L2 normalization verification"
        embedding = EmbeddingGenerator.generate_embedding(text)
        
        import math
        norm = math.sqrt(sum(x * x for x in embedding))
        assert abs(norm - 1.0) < 0.02  # Within tolerance
    
    def test_validate_embedding_dimension(self):
        """Test embedding dimension validation."""
        valid_embedding = [0.1] * 384
        assert EmbeddingGenerator.validate_embedding(valid_embedding) is True
        
        invalid_embedding = [0.1] * 383
        assert EmbeddingGenerator.validate_embedding(invalid_embedding) is False


class TestSourceHandler:
    """Tests for source record handling."""
    
    def test_create_source_record(self):
        """Test source record creation."""
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            record = SourceRecordHandler.create_source_record(tmp.name)
            
            assert record is not None
            assert record.source_id
            # Verify UUID format
            UUID(record.source_id)  # Should not raise
            assert record.file_path == tmp.name
    
    def test_validate_source_file(self):
        """Test source file validation."""
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            assert SourceRecordHandler.validate_source_file(tmp.name) is True
        
        assert SourceRecordHandler.validate_source_file("/nonexistent/file.pdf") is False


class TestJSONLWriter:
    """Tests for JSONL output writing."""
    
    def test_write_chunks_to_jsonl(self):
        """Test writing chunks to JSONL format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            chunks = [
                {
                    "id": "uuid-1",
                    "source_id": "source-1",
                    "content": "Test content 1",
                    "metadata": {"key": "value1"},
                    "embedding": [0.1] * 384
                },
                {
                    "id": "uuid-2",
                    "source_id": "source-1",
                    "content": "Test content 2",
                    "metadata": {"key": "value2"},
                    "embedding": [0.2] * 384
                }
            ]
            
            with JSONLWriter(tmp_path) as writer:
                for chunk in chunks:
                    assert writer.write_chunk(chunk) is True
            
            # Verify output
            with open(tmp_path) as f:
                lines = f.readlines()
                assert len(lines) == 2
                
                record1 = json.loads(lines[0])
                assert record1["id"] == "uuid-1"
                assert record1["content"] == "Test content 1"
                
                record2 = json.loads(lines[1])
                assert record2["id"] == "uuid-2"
                assert record2["content"] == "Test content 2"
        finally:
            Path(tmp_path).unlink()


if __name__ == "__main__":
    # Run basic tests
    print("Running TimetableChunkGenerator tests...")
    TestTimetableChunkGenerator().test_generate_chunks_single_entry()
    TestTimetableChunkGenerator().test_generate_chunks_sorting_by_semester()
    TestTimetableChunkGenerator().test_chunk_contains_required_fields()
    print("✓ TimetableChunkGenerator tests passed")
    
    print("\nRunning SchemeChunkGenerator tests...")
    TestSchemeChunkGenerator().test_generate_chunks_with_prerequisites()
    TestSchemeChunkGenerator().test_chunk_formatting_without_prerequisites()
    print("✓ SchemeChunkGenerator tests passed")
    
    print("\nRunning MetadataEnricher tests...")
    TestMetadataEnricher().test_enrich_timetable_metadata()
    TestMetadataEnricher().test_incomplete_flag()
    print("✓ MetadataEnricher tests passed")
    
    print("\nRunning EmbeddingGenerator tests...")
    TestEmbeddingGenerator().test_generate_embedding_returns_384_dims()
    TestEmbeddingGenerator().test_embedding_l2_normalized()
    TestEmbeddingGenerator().test_validate_embedding_dimension()
    print("✓ EmbeddingGenerator tests passed")
    
    print("\nRunning SourceHandler tests...")
    TestSourceHandler().test_create_source_record()
    TestSourceHandler().test_validate_source_file()
    print("✓ SourceHandler tests passed")
    
    print("\nRunning JSONLWriter tests...")
    TestJSONLWriter().test_write_chunks_to_jsonl()
    print("✓ JSONLWriter tests passed")
    
    print("\n" + "="*50)
    print("✓ All unit tests passed successfully!")
    print("="*50)
