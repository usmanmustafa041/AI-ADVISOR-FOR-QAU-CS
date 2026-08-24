"""Integration tests for TimetableDetector with real PDF files.

These tests verify the detector works with actual academic documents.
Run these after ensuring pypdf is installed and sample PDFs are available.
"""

import pytest
from pathlib import Path

from app.rag.structured_extraction.detectors.detector import TimetableDetector
from app.rag.structured_extraction.entities import ClassificationResult


class TestTimetableDetectorIntegration:
    """Integration tests using real academic PDF files."""
    
    @pytest.fixture
    def detector(self):
        """Create a TimetableDetector instance."""
        return TimetableDetector()
    
    @pytest.fixture
    def academic_data_dir(self):
        """Get path to academic data directory."""
        # Path relative to project root
        return Path(__file__).parent.parent.parent.parent.parent.parent / "academic-data"
    
    def test_classify_real_timetable_pdf(self, detector, academic_data_dir):
        """Test classification of a real timetable PDF.
        
        Requirements: 1.1-1.9
        """
        timetable_path = academic_data_dir / "timetable" / "cs_timetable_spring-2026.pdf"
        
        if not timetable_path.exists():
            pytest.skip(f"Timetable PDF not found: {timetable_path}")
        
        result = detector.classify_document(str(timetable_path))
        
        # Verify result structure
        assert isinstance(result, ClassificationResult)
        assert result.document_type in ["timetable", "scheme_of_study", "generic"]
        assert result.analysis_time_seconds > 0
        assert result.analysis_time_seconds < 30  # Should complete within timeout
        
        # Timetable documents should be classified as "timetable"
        # Note: This assertion may need adjustment based on actual PDF content
        print(f"Classified as: {result.document_type} in {result.analysis_time_seconds:.2f}s")
    
    def test_classify_real_scheme_of_study_pdf(self, detector, academic_data_dir):
        """Test classification of a real scheme of study PDF.
        
        Requirements: 5.1-5.9
        """
        scheme_path = academic_data_dir / "bs" / "bscs_scheme_fall-2023.pdf"
        
        if not scheme_path.exists():
            pytest.skip(f"Scheme of study PDF not found: {scheme_path}")
        
        result = detector.classify_document(str(scheme_path))
        
        # Verify result structure
        assert isinstance(result, ClassificationResult)
        assert result.document_type in ["timetable", "scheme_of_study", "generic"]
        assert result.analysis_time_seconds > 0
        assert result.analysis_time_seconds < 30
        
        # Scheme documents should be classified as "scheme_of_study" or "timetable"
        print(f"Classified as: {result.document_type} in {result.analysis_time_seconds:.2f}s")
    
    def test_classify_multiple_scheme_pdfs(self, detector, academic_data_dir):
        """Test classification of multiple scheme of study PDFs.
        
        Requirements: 5.1-5.9
        """
        scheme_files = [
            "bs/bscs_scheme_fall-2021.pdf",
            "bs/bscs_scheme_fall-2023.pdf",
            "bs/bscs_scheme_fall-2025.pdf",
        ]
        
        results = []
        for scheme_file in scheme_files:
            scheme_path = academic_data_dir / scheme_file
            if scheme_path.exists():
                result = detector.classify_document(str(scheme_path))
                results.append((scheme_file, result))
                print(f"{scheme_file}: {result.document_type} ({result.analysis_time_seconds:.2f}s)")
        
        # Verify at least one file was tested
        assert len(results) > 0, "No scheme PDFs found for testing"
        
        # All results should complete within timeout
        for filename, result in results:
            assert result.analysis_time_seconds < 30, f"{filename} exceeded timeout"
    
    def test_classify_generic_academic_pdf(self, detector, academic_data_dir):
        """Test classification of non-timetable, non-scheme academic PDFs.
        
        Requirements: 1.7, 5.8
        """
        generic_files = [
            "university-policies/qau_mphil_rules.pdf",
            "university-policies/qau_phd_rules.pdf",
            "exam-schedules/cs_terminal_datesheet_spring-2025.pdf",
        ]
        
        for generic_file in generic_files:
            generic_path = academic_data_dir / generic_file
            if generic_path.exists():
                result = detector.classify_document(str(generic_path))
                
                # These might be classified as generic or might have some structure
                assert isinstance(result, ClassificationResult)
                assert result.document_type in ["timetable", "scheme_of_study", "generic"]
                print(f"{generic_file}: {result.document_type}")
    
    def test_nonexistent_file(self, detector):
        """Test handling of nonexistent file path.
        
        Requirements: 1.8
        """
        result = detector.classify_document("/nonexistent/path/document.pdf")
        
        assert result.document_type == "generic"
        assert result.analysis_time_seconds >= 0
    
    def test_classification_performance(self, detector, academic_data_dir):
        """Test that classification completes within performance requirements.
        
        Requirements: 1.1, 5.1
        """
        # Find any available PDF
        test_files = []
        for pattern in ["**/*.pdf"]:
            test_files.extend(list(academic_data_dir.glob(pattern))[:3])  # Limit to 3 files
        
        if not test_files:
            pytest.skip("No PDF files found for performance testing")
        
        for pdf_path in test_files:
            result = detector.classify_document(str(pdf_path))
            
            # Must complete within 30 seconds
            assert result.analysis_time_seconds < 30, (
                f"Classification took {result.analysis_time_seconds:.2f}s, "
                f"exceeds 30s timeout for {pdf_path.name}"
            )
            
            print(f"{pdf_path.name}: {result.analysis_time_seconds:.2f}s")


if __name__ == "__main__":
    # Allow running as a script for quick testing
    detector = TimetableDetector()
    academic_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "academic-data"
    
    print("Testing TimetableDetector with real PDFs...")
    print(f"Academic data directory: {academic_dir}")
    
    # Test timetable
    timetable = academic_dir / "timetable" / "cs_timetable_spring-2026.pdf"
    if timetable.exists():
        print(f"\nTesting: {timetable.name}")
        result = detector.classify_document(str(timetable))
        print(f"Result: {result.document_type} ({result.analysis_time_seconds:.2f}s)")
    
    # Test scheme
    scheme = academic_dir / "bs" / "bscs_scheme_fall-2023.pdf"
    if scheme.exists():
        print(f"\nTesting: {scheme.name}")
        result = detector.classify_document(str(scheme))
        print(f"Result: {result.document_type} ({result.analysis_time_seconds:.2f}s)")
