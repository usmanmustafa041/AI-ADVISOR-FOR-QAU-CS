"""Generates normalized text chunks from scheme of study data."""

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from ..structured_extraction.entities import SchemeOfStudyEntry
from ..structured_extraction.constants import (
    CHUNK_FIELD_DELIMITER,
    PREREQUISITE_PREFIX,
    MAX_CHUNKS_PER_DOCUMENT,
)

logger = logging.getLogger(__name__)


@dataclass
class ChunkRecord:
    """Represents a chunk with all required fields for storage."""
    id: str
    source_id: Optional[str]
    content: str
    metadata: dict
    embedding: Optional[list[float]] = None
    position: int = 0


class SchemeOfStudyChunkGenerator:
    """Generates normalized text chunks from scheme of study entries."""
    
    def generate_chunks(self, entries: list[SchemeOfStudyEntry],
                       source_id: Optional[str] = None) -> list[ChunkRecord]:
        """
        Generate normalized text chunks from scheme of study entries.
        
        Args:
            entries: List of SchemeOfStudyEntry objects
            source_id: Optional source document UUID for linking
            
        Returns:
            List of ChunkRecord objects ready for storage
            
        Requirements:
            - 7.1-7.9: Chunk generation with field ordering and formatting
        """
        chunks = []
        
        # Sort by semester (Requirement 7.1)
        sorted_entries = sorted(entries, key=lambda e: e.semester)
        
        # Enforce chunk limit
        if len(sorted_entries) > MAX_CHUNKS_PER_DOCUMENT:
            logger.error(
                f"Document would generate {len(sorted_entries)} chunks, "
                f"exceeds limit of {MAX_CHUNKS_PER_DOCUMENT}. Processing only first {MAX_CHUNKS_PER_DOCUMENT}."
            )
            sorted_entries = sorted_entries[:MAX_CHUNKS_PER_DOCUMENT]
        
        # Generate one chunk per entry (Requirement 7.6)
        for position, entry in enumerate(sorted_entries):
            chunk = self._create_chunk(entry, source_id, position)
            chunks.append(chunk)
        
        return chunks
    
    def _create_chunk(self, entry: SchemeOfStudyEntry, source_id: Optional[str],
                     position: int) -> ChunkRecord:
        """Create a single chunk from a scheme of study entry."""
        # Format chunk content with mandatory fields in order
        # (Requirement 7.2): semester, course_code, course_name, credit_hours, category
        
        content_parts = [
            str(entry.semester),
            entry.course_code,
            entry.course_name,
            str(entry.credit_hours),
            entry.category,
        ]
        
        # Append prerequisite field if present (Requirement 7.4)
        if entry.prerequisites:
            prerequisites_text = PREREQUISITE_PREFIX + " ".join(entry.prerequisites)
            content_parts.append(prerequisites_text)
        
        # Format with delimiter (Requirement 7.3)
        content = CHUNK_FIELD_DELIMITER.join(content_parts)
        
        # Create metadata object (prepared for MetadataEnricher)
        metadata = {
            "semester": entry.semester,
            "course_code": entry.course_code,
            "credit_hours": entry.credit_hours,
            "category": entry.category,
        }
        
        if entry.prerequisites:
            metadata["prerequisites"] = entry.prerequisites
        
        return ChunkRecord(
            id=str(uuid4()),
            source_id=source_id,
            content=content,
            metadata=metadata,
            position=position
        )
