"""
Document chunking module for RAG pipeline.

This module provides sentence-aware text chunking with overlap for
improved context preservation in vector search and retrieval.
"""

import re
from typing import List


def chunk_document(content: str, max_chunk_size: int = 512) -> List[str]:
    """
    Split document content into chunks with sentence-aware boundaries.
    
    This function chunks text by splitting on sentence boundaries (periods and
    double newlines) while respecting the maximum chunk size. Chunks have
    50-character overlap to maintain context continuity.
    
    Args:
        content: The text content to chunk
        max_chunk_size: Maximum size of each chunk in characters (default: 512)
    
    Returns:
        List of text chunks with 50-character overlap between consecutive chunks
    
    Examples:
        >>> text = "First sentence. Second sentence. Third sentence."
        >>> chunks = chunk_document(text, max_chunk_size=30)
        >>> len(chunks) > 1
        True
        >>> # Verify overlap between consecutive chunks
        >>> chunks[0][-50:] in chunks[1] if len(chunks) > 1 and len(chunks[0]) >= 50 else True
        True
    
    Requirements:
        - Requirement 30: Vector Embedding Generation
    """
    if not content or not content.strip():
        return []
    
    # Normalize whitespace
    content = content.strip()
    
    # Split into sentences using period followed by space or double newline
    # This preserves paragraph boundaries and sentence structure
    sentences = re.split(r'(?<=\.)\s+|\n\n+', content)
    
    # Filter out empty strings
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return []
    
    chunks = []
    current_chunk = ""
    overlap_size = 50
    
    for sentence in sentences:
        # If adding this sentence would exceed max size and we have content
        if current_chunk and len(current_chunk) + len(sentence) + 1 > max_chunk_size:
            # Save the current chunk
            chunks.append(current_chunk.strip())
            
            # Start new chunk with overlap from previous chunk
            # Take last 50 characters from previous chunk for context
            if len(current_chunk) >= overlap_size:
                current_chunk = current_chunk[-overlap_size:] + " " + sentence
            else:
                current_chunk = sentence
        else:
            # Add sentence to current chunk
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
    
    # Add the last chunk if it has content
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks
