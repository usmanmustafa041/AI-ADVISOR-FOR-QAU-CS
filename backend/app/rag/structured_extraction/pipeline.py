"""Main orchestration pipeline for structured document ingestion."""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.rag.extractors.timetable_extractor import TimetableExtractor
from app.rag.extractors.scheme_extractor import SchemeOfStudyExtractor
from app.rag.chunk_generators.timetable_chunk_generator import TimetableChunkGenerator
from app.rag.chunk_generators.scheme_chunk_generator import SchemeOfStudyChunkGenerator
from app.rag.structured_extraction.detectors.detector import TimetableDetector
from app.rag.structured_extraction.metadata_enricher import MetadataEnricher
from app.rag.structured_extraction.embedding_generator import EmbeddingGenerator
from app.rag.structured_extraction.source_handler import SourceRecordHandler
from app.rag.structured_extraction.jsonl_writer import JSONLWriter
from app.rag.documents import document_chunks
from app.rag.embedding import embed_text
from .constants import (
    MAX_EXTRACTION_TIME_SECONDS,
    MAX_VALIDATION_ERRORS_PER_DOCUMENT,
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessingSummary:
    """Summary of batch processing results."""
    total_documents: int = 0
    successful_documents: int = 0
    failed_documents: int = 0
    total_chunks_created: int = 0
    total_entries_skipped: int = 0
    failed_file_paths: list[str] = None
    
    def __post_init__(self):
        if self.failed_file_paths is None:
            self.failed_file_paths = []
    
    def to_dict(self) -> dict:
        """Convert summary to dictionary."""
        return {
            "total_documents": self.total_documents,
            "successful_documents": self.successful_documents,
            "failed_documents": self.failed_documents,
            "total_chunks_created": self.total_chunks_created,
            "total_entries_skipped": self.total_entries_skipped,
            "failed_file_paths": self.failed_file_paths,
        }


class StructuredIngestionPipeline:
    """Orchestrates the complete structured document ingestion process."""
    
    def __init__(self):
        """Initialize pipeline components."""
        self.detector = TimetableDetector()
        self.timetable_extractor = TimetableExtractor()
        self.scheme_extractor = SchemeOfStudyExtractor()
        self.timetable_chunk_gen = TimetableChunkGenerator()
        self.scheme_chunk_gen = SchemeOfStudyChunkGenerator()
        self.metadata_enricher = MetadataEnricher()
        self.summary = ProcessingSummary()
    
    def process_document(self, file_path: str, output_jsonl: str) -> bool:
        """
        Process a single structured document end-to-end.
        
        Args:
            file_path: Path to the PDF document
            output_jsonl: Path to output JSONL file
            
        Returns:
            True if processing succeeded, False otherwise
            
        Requirements:
            - 10.1-10.10: Complete pipeline integration
            - 11.1-11.4: Routing and fallback behavior
            - 14.1-14.9: Error handling and logging
        """
        self.summary.total_documents += 1
        start_time = time.time()
        
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            self.summary.failed_documents += 1
            self.summary.failed_file_paths.append(file_path)
            return False
        
        try:
            # Step 1: Classify document (Requirement 11.1, 10.1)
            logger.info(f"Processing document: {file_path}")
            classification = self.detector.classify_document(file_path)
            logger.info(f"Classified as: {classification.document_type}")
            
            # Step 2: Route to appropriate extraction path (Requirement 10.2-10.4)
            chunks = []
            
            if classification.document_type == "timetable":
                chunks = self._process_timetable(file_path)
            elif classification.document_type == "scheme_of_study":
                chunks = self._process_scheme(file_path)
            else:
                # Generic document (Requirement 10.4, 11.3)
                logger.info("Processing as generic document")
                chunks = self._process_generic(file_path)
            
            # Step 3: Write to JSONL output (Requirement 10.5-10.6, 15.9)
            if chunks:
                written_count = self._write_output(chunks, output_jsonl)
                self.summary.total_chunks_created += written_count
                self.summary.successful_documents += 1
                elapsed = time.time() - start_time
                logger.info(
                    f"Successfully processed {file_path} in {elapsed:.2f}s "
                    f"({written_count} chunks)"
                )
                return True
            else:
                logger.warning(f"No chunks generated from {file_path}")
                self.summary.failed_documents += 1
                self.summary.failed_file_paths.append(file_path)
                return False
        
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}", exc_info=True)
            # Fallback to generic processing (Requirement 10.9, 11.3)
            try:
                chunks = self._process_generic(file_path)
                if chunks:
                    self._write_output(chunks, output_jsonl)
                    self.summary.successful_documents += 1
                    logger.info(f"Successfully recovered {file_path} with generic processing")
                    return True
            except Exception as fallback_error:
                logger.error(f"Generic fallback also failed for {file_path}: {fallback_error}")
            
            self.summary.failed_documents += 1
            self.summary.failed_file_paths.append(file_path)
            return False
    
    def _process_timetable(self, file_path: str) -> list[dict]:
        """Process a timetable document."""
        try:
            # Create source record (Requirement 8.1-8.2)
            source_record = SourceRecordHandler.create_source_record(file_path)
            source_id = source_record.source_id if source_record else None
            
            # Extract structured data (Requirement 2.1-2.17)
            extracted = self.timetable_extractor.extract_from_pdf(file_path)
            
            if not extracted.timetable_entries:
                logger.warning(f"No timetable entries extracted from {file_path}")
                return []
            
            self.summary.total_entries_skipped += extracted.skipped_entries
            
            # Generate chunks (Requirement 3.1-3.10)
            chunk_records = self.timetable_chunk_gen.generate_chunks(
                extracted.timetable_entries,
                source_id=source_id
            )
            
            # Enrich metadata and generate embeddings
            output_chunks = []
            for chunk_record in chunk_records:
                metadata = self.metadata_enricher.enrich_timetable_chunk(chunk_record.metadata)
                embedding = EmbeddingGenerator.generate_embedding(chunk_record.content)
                
                output_chunks.append({
                    "id": chunk_record.id,
                    "source_id": chunk_record.source_id,
                    "content": chunk_record.content,
                    "metadata": metadata,
                    "embedding": embedding,
                })
            
            return output_chunks
        
        except Exception as e:
            logger.error(f"Error processing timetable {file_path}: {e}", exc_info=True)
            return []
    
    def _process_scheme(self, file_path: str) -> list[dict]:
        """Process a scheme of study document."""
        try:
            # Create source record
            source_record = SourceRecordHandler.create_source_record(file_path)
            source_id = source_record.source_id if source_record else None
            
            # Extract structured data (Requirement 6.1-6.12)
            extracted = self.scheme_extractor.extract_from_pdf(file_path)
            
            if not extracted.scheme_entries:
                logger.warning(f"No scheme entries extracted from {file_path}")
                return []
            
            self.summary.total_entries_skipped += extracted.skipped_entries
            
            # Generate chunks (Requirement 7.1-7.9)
            chunk_records = self.scheme_chunk_gen.generate_chunks(
                extracted.scheme_entries,
                source_id=source_id
            )
            
            # Enrich metadata and generate embeddings
            output_chunks = []
            for chunk_record in chunk_records:
                metadata = self.metadata_enricher.enrich_scheme_chunk(chunk_record.metadata)
                embedding = EmbeddingGenerator.generate_embedding(chunk_record.content)
                
                output_chunks.append({
                    "id": chunk_record.id,
                    "source_id": chunk_record.source_id,
                    "content": chunk_record.content,
                    "metadata": metadata,
                    "embedding": embedding,
                })
            
            return output_chunks
        
        except Exception as e:
            logger.error(f"Error processing scheme document {file_path}: {e}", exc_info=True)
            return []
    
    def _process_generic(self, file_path: str) -> list[dict]:
        """Process a generic document using existing pipeline (Requirement 10.4)."""
        try:
            path = Path(file_path)
            generic_chunks = document_chunks(path)
            
            output_chunks = []
            for chunk in generic_chunks:
                embedding = embed_text(chunk.content)
                output_chunks.append({
                    "id": None,  # Will be generated by database
                    "source_id": None,
                    "content": chunk.content,
                    "metadata": {"page_number": chunk.page_number},
                    "embedding": embedding,
                })
            
            return output_chunks
        
        except Exception as e:
            logger.error(f"Error in generic processing for {file_path}: {e}", exc_info=True)
            return []
    
    def _write_output(self, chunks: list[dict], output_jsonl: str) -> int:
        """Write chunks to JSONL output file."""
        try:
            with JSONLWriter(output_jsonl) as writer:
                for chunk in chunks:
                    writer.write_chunk(chunk)
                return writer.get_chunk_count()
        except Exception as e:
            logger.error(f"Error writing to JSONL: {e}")
            return 0
    
    def process_batch(self, input_dir: str, output_jsonl: str) -> ProcessingSummary:
        """
        Process a batch of documents.
        
        Args:
            input_dir: Directory containing PDF documents to process
            output_jsonl: Path to output JSONL file
            
        Returns:
            ProcessingSummary with batch statistics
            
        Requirements:
            - 15.5: Sequential processing (one at a time)
            - 14.8-14.9: Summary generation and error logging
        """
        input_path = Path(input_dir)
        if not input_path.exists():
            logger.error(f"Input directory not found: {input_dir}")
            return self.summary
        
        # Find all PDF files (Requirement 15.5: sequential)
        pdf_files = sorted(input_path.rglob("*.pdf"))
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {input_dir}")
            return self.summary
        
        logger.info(f"Starting batch processing: {len(pdf_files)} files")
        
        # Process documents sequentially
        for file_path in pdf_files:
            self.process_document(str(file_path), output_jsonl)
        
        # Write summary and error log (Requirement 14.8-14.9)
        self._write_summary_and_errors()
        
        return self.summary
    
    def _write_summary_and_errors(self) -> None:
        """Write processing summary and error log file."""
        logger.info(f"Batch processing complete:")
        logger.info(f"  Total documents: {self.summary.total_documents}")
        logger.info(f"  Successful: {self.summary.successful_documents}")
        logger.info(f"  Failed: {self.summary.failed_documents}")
        logger.info(f"  Total chunks: {self.summary.total_chunks_created}")
        logger.info(f"  Skipped entries: {self.summary.total_entries_skipped}")
        
        # Write error log if there are failures (Requirement 14.9)
        if self.summary.failed_documents > 0:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            error_log_path = f"ingestion_errors_{timestamp}.log"
            
            try:
                with open(error_log_path, 'w') as f:
                    f.write(f"Ingestion Errors Log - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(f"Failed documents ({len(self.summary.failed_file_paths)}):\n")
                    for file_path in self.summary.failed_file_paths:
                        f.write(f"  - {file_path}\n")
                
                logger.info(f"Error log written to {error_log_path}")
            except Exception as e:
                logger.error(f"Failed to write error log: {e}")
