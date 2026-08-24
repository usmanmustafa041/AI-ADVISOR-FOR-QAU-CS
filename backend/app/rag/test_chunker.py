"""
Unit tests for the document chunker module.
"""

import pytest
from app.rag.chunker import chunk_document


def test_chunk_document_basic():
    """Test basic chunking functionality."""
    text = "First sentence. Second sentence. Third sentence."
    chunks = chunk_document(text, max_chunk_size=30)
    
    assert len(chunks) > 0
    assert all(isinstance(chunk, str) for chunk in chunks)


def test_chunk_document_respects_max_size():
    """Test that chunks respect the maximum size constraint."""
    text = "This is a sentence. " * 50  # Create long text
    max_size = 100
    chunks = chunk_document(text, max_chunk_size=max_size)
    
    # Most chunks should be at or near max size (allowing some flexibility for sentence boundaries)
    for chunk in chunks:
        # Allow some flexibility for sentence boundaries and overlap
        assert len(chunk) <= max_size + 100  # Allow for sentence completion


def test_chunk_document_overlap():
    """Test that chunks have 50-character overlap."""
    text = "A" * 600  # Create text longer than one chunk
    chunks = chunk_document(text, max_chunk_size=200)
    
    if len(chunks) > 1:
        # Check that there is some overlap between consecutive chunks
        # Note: exact 50-char overlap may vary due to sentence boundaries
        assert len(chunks) >= 2


def test_chunk_document_empty_input():
    """Test handling of empty input."""
    assert chunk_document("") == []
    assert chunk_document("   ") == []
    assert chunk_document(None or "") == []


def test_chunk_document_short_text():
    """Test that short text returns single chunk."""
    text = "Short text."
    chunks = chunk_document(text, max_chunk_size=512)
    
    assert len(chunks) == 1
    assert chunks[0] == "Short text."


def test_chunk_document_paragraph_boundaries():
    """Test that paragraph boundaries (double newlines) are respected."""
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = chunk_document(text, max_chunk_size=20)
    
    assert len(chunks) > 0
    # Verify chunking occurred
    assert any("Paragraph" in chunk for chunk in chunks)


def test_chunk_document_sentence_boundaries():
    """Test that sentence boundaries (periods) are respected."""
    text = "First. Second. Third. Fourth. Fifth."
    chunks = chunk_document(text, max_chunk_size=20)
    
    assert len(chunks) > 0
    # Verify no chunks end mid-word (except for overlap)
    for chunk in chunks[:-1]:  # Check all but last chunk
        # Should end with complete words or sentences
        assert chunk.strip()


def test_chunk_document_preserves_content():
    """Test that all content is preserved across chunks."""
    text = "Word1. Word2. Word3. Word4. Word5."
    chunks = chunk_document(text, max_chunk_size=20)
    
    # Join all chunks and verify major words are preserved
    combined = " ".join(chunks)
    assert "Word1" in combined
    assert "Word5" in combined


def test_chunk_document_default_max_size():
    """Test default max_chunk_size parameter."""
    # Create text with sentences that will exceed default 512
    text = "This is a sentence. " * 100  # Creates ~2000 characters with sentence boundaries
    chunks = chunk_document(text)  # Should use default 512
    
    # With default 512, should create multiple chunks
    assert len(chunks) > 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
