"""Chunk generators for creating normalized text chunks."""

from .timetable_chunk_generator import TimetableChunkGenerator, ChunkRecord
from .scheme_chunk_generator import SchemeOfStudyChunkGenerator

__all__ = ["TimetableChunkGenerator", "SchemeOfStudyChunkGenerator", "ChunkRecord"]
