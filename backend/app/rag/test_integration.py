"""Integration tests for the complete structured extraction pipeline."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.rag.structured_extraction.pipeline import StructuredIngestionPipeline
from app.rag.structured_extraction.detectors.detector import TimetableDetector
from app.rag.extractors.timetable_extractor import TimetableExtractor
from app.rag.extractors.scheme_extractor import SchemeOfStudyExtractor


def test_detector_with_real_documents():
    """Test detector with real academic documents."""
    detector = TimetableDetector()
    
    timetable_path = Path("academic-data/timetable/cs_timetable_spring-2026.pdf")
    scheme_path = Path("academic-data/bs/bscs_scheme_fall-2025.pdf")
    
    print("Testing document classification...")
    
    if timetable_path.exists():
        result = detector.classify_document(str(timetable_path))
        assert result.document_type in ["timetable", "generic"]
        print(f"  Timetable classified as: {result.document_type} ({result.analysis_time_seconds:.2f}s)")
    
    if scheme_path.exists():
        result = detector.classify_document(str(scheme_path))
        assert result.document_type in ["scheme_of_study", "generic"]
        print(f"  Scheme classified as: {result.document_type} ({result.analysis_time_seconds:.2f}s)")


def test_timetable_extraction():
    """Test timetable extraction from real document."""
    timetable_path = Path("academic-data/timetable/cs_timetable_spring-2026.pdf")
    
    if not timetable_path.exists():
        print("  Skipping (no timetable PDF found)")
        return
    
    print("\nTesting timetable extraction...")
    extractor = TimetableExtractor()
    extracted = extractor.extract_from_pdf(str(timetable_path))
    
    assert extracted.document_type == "timetable"
    print(f"  Extracted {len(extracted.timetable_entries)} entries")
    print(f"  Skipped {extracted.skipped_entries} entries")
    
    if extracted.timetable_entries:
        entry = extracted.timetable_entries[0]
        assert entry.semester >= 1
        assert entry.course_code
        assert entry.day
        assert entry.start_time
        assert entry.end_time
        print(f"  Sample entry: {entry.course_code} on {entry.day} at {entry.start_time}")


def test_pipeline_single_document():
    """Test complete pipeline on a single document."""
    timetable_path = Path("academic-data/timetable/cs_timetable_spring-2026.pdf")
    
    if not timetable_path.exists():
        print("  Skipping (no timetable PDF found)")
        return
    
    print("\nTesting full pipeline on single document...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as tmp:
        output_path = tmp.name
    
    try:
        pipeline = StructuredIngestionPipeline()
        success = pipeline.process_document(str(timetable_path), output_path)
        
        assert success
        print(f"  Processing successful")
        print(f"  Summary: {pipeline.summary.successful_documents} successful, "
              f"{pipeline.summary.failed_documents} failed")
        print(f"  Generated {pipeline.summary.total_chunks_created} chunks")
        
        # Verify output
        with open(output_path) as f:
            lines = f.readlines()
            assert len(lines) > 0
            
            # Verify JSONL format
            for line in lines:
                record = json.loads(line)
                assert "id" in record
                assert "content" in record
                assert "metadata" in record
                assert "embedding" in record
                
                # Verify embedding is 384-dimensional
                if record["embedding"]:
                    assert len(record["embedding"]) == 384
            
            print(f"  Output validated: {len(lines)} valid JSONL records")
    finally:
        Path(output_path).unlink()


def test_pipeline_batch():
    """Test batch processing on a directory."""
    input_dir = Path("academic-data/timetable")
    
    if not input_dir.exists() or not list(input_dir.glob("*.pdf")):
        print("  Skipping (no timetable PDFs found)")
        return
    
    print("\nTesting batch processing...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as tmp:
        output_path = tmp.name
    
    try:
        pipeline = StructuredIngestionPipeline()
        summary = pipeline.process_batch(str(input_dir), output_path)
        
        print(f"  Total documents: {summary.total_documents}")
        print(f"  Successful: {summary.successful_documents}")
        print(f"  Failed: {summary.failed_documents}")
        print(f"  Total chunks: {summary.total_chunks_created}")
        
        # Verify output
        if Path(output_path).exists():
            with open(output_path) as f:
                lines = f.readlines()
                print(f"  Output: {len(lines)} chunks in JSONL format")
    finally:
        if Path(output_path).exists():
            Path(output_path).unlink()


def main():
    """Run all integration tests."""
    print("="*70)
    print("STRUCTURED EXTRACTION PIPELINE - INTEGRATION TESTS")
    print("="*70)
    
    try:
        test_detector_with_real_documents()
        test_timetable_extraction()
        test_pipeline_single_document()
        test_pipeline_batch()
        
        print("\n" + "="*70)
        print("✓ All integration tests passed!")
        print("="*70)
        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
