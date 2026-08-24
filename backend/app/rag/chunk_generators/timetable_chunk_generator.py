"""Generates normalized text chunks from timetable data."""

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from ..structured_extraction.entities import TimetableEntry
from ..structured_extraction.constants import (
    CHUNK_FIELD_DELIMITER,
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


class TimetableChunkGenerator:
    """Generates normalized text chunks from timetable entries."""
    
    def generate_chunks(self, entries: list[TimetableEntry],
                       source_id: Optional[str] = None) -> list[ChunkRecord]:
        """
        Generate normalized text chunks from timetable entries.
        
        Args:
            entries: List of TimetableEntry objects
            source_id: Optional source document UUID for linking
            
        Returns:
            List of ChunkRecord objects ready for storage
            
        Requirements:
            - 3.1-3.10: Chunk generation with field ordering and formatting
            - 13.1: Time preservation without reformatting
        """
        chunks = []
        
        # Sort by semester (Requirement 3.1)
        sorted_entries = sorted(entries, key=lambda e: e.semester)
        
        # Enforce chunk limit
        if len(sorted_entries) > MAX_CHUNKS_PER_DOCUMENT:
            logger.error(
                f"Document would generate {len(sorted_entries)} chunks, "
                f"exceeds limit of {MAX_CHUNKS_PER_DOCUMENT}. Processing only first {MAX_CHUNKS_PER_DOCUMENT}."
            )
            sorted_entries = sorted_entries[:MAX_CHUNKS_PER_DOCUMENT]
        
        # Generate one chunk per entry (Requirement 3.7)
        for position, entry in enumerate(sorted_entries):
            chunk = self._create_chunk(entry, source_id, position)
            chunks.append(chunk)
        
        return chunks
    
    def _create_chunk(self, entry: TimetableEntry, source_id: Optional[str],
                     position: int) -> ChunkRecord:
        """Create a single chunk from a timetable entry."""
        # Format chunk content with mandatory fields in order
        # (Requirement 3.2): semester, section, course_code, course_name, 
        # course_type, day, start_time, end_time, room
        
        content_parts = [
            str(entry.semester),
            entry.section,
            entry.course_code,
            entry.course_name,
            entry.course_type,
            entry.day,
            entry.start_time,  # Preserve exact character sequence (Requirement 3.4, 13.1)
            entry.end_time,    # Preserve exact character sequence
        ]
        
        # Add optional fields if present (Requirement 3.5-3.6)
        if entry.room:
            content_parts.append(entry.room)
        if entry.faculty:
            content_parts.append(entry.faculty)
        if entry.special_status:
            content_parts.append(entry.special_status)
        
        # Format with delimiter (Requirement 3.3)
        content = CHUNK_FIELD_DELIMITER.join(content_parts)
        
        # Create metadata object (prepared for MetadataEnricher)
        metadata = {
            "semester": entry.semester,
            "section": entry.section,
            "course_code": entry.course_code,
            "day": entry.day,
            "course_type": entry.course_type,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
        }
        
        if entry.room:
            metadata["room"] = entry.room
        if entry.faculty:
            metadata["faculty"] = entry.faculty
        if entry.special_status:
            metadata["special_status"] = entry.special_status
        
        return ChunkRecord(
            id=str(uuid4()),
            source_id=source_id,
            content=content,
            metadata=metadata,
            position=position
        )
