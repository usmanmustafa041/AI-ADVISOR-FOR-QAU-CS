"""
Unit tests for VectorStore implementation
Tests embedding storage, similarity search, and document deletion
"""

import pytest
import numpy as np
from uuid import uuid4, UUID
from sqlalchemy import text
from app.rag.vector_store import VectorStore, DocumentChunk, create_vector_store
from app.core.database import get_db


@pytest.fixture
def db_session():
    """Get database session for testing"""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def vector_store(db_session):
    """Create VectorStore instance for testing"""
    return VectorStore(db_session)


@pytest.fixture
def sample_document_id(db_session):
    """Create a sample knowledge_documents record for testing"""
    # First ensure we have a source_record
    source_result = db_session.execute(
        text("""
            INSERT INTO source_records (source_code, title, source_type, verification_status)
            VALUES ('TEST-001', 'Test Source', 'document', 'verified')
            ON CONFLICT (source_code) DO UPDATE SET source_code = EXCLUDED.source_code
            RETURNING id
        """)
    )
    source_id = source_result.scalar_one()
    
    # Create knowledge_documents record
    doc_result = db_session.execute(
        text("""
            INSERT INTO knowledge_documents (source_id, document_type, content, processing_status)
            VALUES (:source_id, 'test', 'Test document content', 'pending')
            RETURNING id
        """),
        {"source_id": str(source_id)}
    )
    db_session.commit()
    
    doc_id = doc_result.scalar_one()
    yield UUID(doc_id)
    
    # Cleanup
    db_session.execute(
        text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
        {"doc_id": str(doc_id)}
    )
    db_session.execute(
        text("DELETE FROM knowledge_documents WHERE id = :doc_id"),
        {"doc_id": str(doc_id)}
    )
    db_session.commit()


def test_store_embedding(vector_store, sample_document_id):
    """Test storing an embedding in the vector store"""
    # Create a sample embedding (384 dimensions)
    embedding = np.random.rand(384)
    content = "This is a test document chunk about machine learning."
    metadata = {"topic": "test", "importance": "high"}
    
    # Store the embedding
    chunk_id = vector_store.store_embedding(
        document_id=sample_document_id,
        chunk_index=0,
        content=content,
        embedding=embedding,
        metadata=metadata
    )
    
    # Verify it was stored
    assert isinstance(chunk_id, UUID)
    
    # Verify we can retrieve it
    chunk = vector_store.get_chunk(chunk_id)
    assert chunk is not None
    assert chunk.content == content
    assert chunk.chunk_index == 0
    assert chunk.metadata == metadata


def test_similarity_search(vector_store, sample_document_id):
    """Test similarity search returns relevant results"""
    # Create and store multiple embeddings
    embeddings = [
        np.random.rand(384) for _ in range(5)
    ]
    contents = [
        "Machine learning algorithms",
        "Deep neural networks",
        "Computer science fundamentals",
        "Data structures and algorithms",
        "Artificial intelligence research"
    ]
    
    for i, (embedding, content) in enumerate(zip(embeddings, contents)):
        vector_store.store_embedding(
            document_id=sample_document_id,
            chunk_index=i,
            content=content,
            embedding=embedding
        )
    
    # Search with the first embedding (should match itself best)
    query_embedding = embeddings[0]
    results = vector_store.similarity_search(query_embedding, top_k=3)
    
    # Verify results structure
    assert len(results) <= 3
    assert all(isinstance(chunk, DocumentChunk) for chunk, score in results)
    assert all(isinstance(score, float) for chunk, score in results)
    
    # Verify results are sorted by score (descending)
    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)
    
    # The top result should be the exact match
    if results:
        top_chunk, top_score = results[0]
        assert top_chunk.content == contents[0]
        assert top_score > 0.99  # Should be nearly identical


def test_similarity_search_with_filters(vector_store, sample_document_id, db_session):
    """Test similarity search with document_type filter"""
    # Create another document of different type
    source_result = db_session.execute(
        text("""
            SELECT id FROM source_records WHERE source_code = 'TEST-001'
        """)
    )
    source_id = source_result.scalar_one()
    
    other_doc_result = db_session.execute(
        text("""
            INSERT INTO knowledge_documents (source_id, document_type, content, processing_status)
            VALUES (:source_id, 'faculty', 'Faculty bio content', 'pending')
            RETURNING id
        """),
        {"source_id": str(source_id)}
    )
    db_session.commit()
    other_doc_id = UUID(other_doc_result.scalar_one())
    
    # Store embeddings in both documents
    embedding1 = np.random.rand(384)
    embedding2 = np.random.rand(384)
    
    vector_store.store_embedding(
        document_id=sample_document_id,
        chunk_index=0,
        content="Test content",
        embedding=embedding1
    )
    
    vector_store.store_embedding(
        document_id=other_doc_id,
        chunk_index=0,
        content="Faculty content",
        embedding=embedding2
    )
    
    # Search with filter
    results = vector_store.similarity_search(
        query_embedding=embedding1,
        top_k=10,
        filters={"document_type": "test"}
    )
    
    # Should only return chunks from 'test' document type
    for chunk, score in results:
        assert chunk.document_id == sample_document_id
    
    # Cleanup
    db_session.execute(
        text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
        {"doc_id": str(other_doc_id)}
    )
    db_session.execute(
        text("DELETE FROM knowledge_documents WHERE id = :doc_id"),
        {"doc_id": str(other_doc_id)}
    )
    db_session.commit()


def test_similarity_search_with_min_threshold(vector_store, sample_document_id):
    """Test similarity search with minimum similarity threshold"""
    # Create embeddings with known similarity
    embedding1 = np.ones(384) / np.sqrt(384)  # Normalized
    embedding2 = -embedding1  # Opposite direction (low similarity)
    
    vector_store.store_embedding(
        document_id=sample_document_id,
        chunk_index=0,
        content="Similar content",
        embedding=embedding1
    )
    
    vector_store.store_embedding(
        document_id=sample_document_id,
        chunk_index=1,
        content="Dissimilar content",
        embedding=embedding2
    )
    
    # Search with high threshold (only similar results)
    results = vector_store.similarity_search(
        query_embedding=embedding1,
        top_k=10,
        filters={"min_similarity": 0.75}
    )
    
    # Should filter out the dissimilar result
    assert all(score >= 0.75 for _, score in results)


def test_delete_document(vector_store, sample_document_id):
    """Test deleting all chunks for a document"""
    # Store multiple chunks
    for i in range(3):
        embedding = np.random.rand(384)
        vector_store.store_embedding(
            document_id=sample_document_id,
            chunk_index=i,
            content=f"Chunk {i}",
            embedding=embedding
        )
    
    # Verify chunks exist
    initial_count = vector_store.count_chunks(sample_document_id)
    assert initial_count == 3
    
    # Delete all chunks
    deleted_count = vector_store.delete_document(sample_document_id)
    assert deleted_count == 3
    
    # Verify chunks are gone
    final_count = vector_store.count_chunks(sample_document_id)
    assert final_count == 0


def test_count_chunks(vector_store, sample_document_id):
    """Test counting chunks"""
    # Initially should be 0
    assert vector_store.count_chunks(sample_document_id) == 0
    
    # Add some chunks
    for i in range(5):
        embedding = np.random.rand(384)
        vector_store.store_embedding(
            document_id=sample_document_id,
            chunk_index=i,
            content=f"Chunk {i}",
            embedding=embedding
        )
    
    # Should now be 5
    assert vector_store.count_chunks(sample_document_id) == 5


def test_create_vector_store_factory(db_session):
    """Test factory function creates valid VectorStore"""
    vs = create_vector_store(db_session)
    assert isinstance(vs, VectorStore)
    assert vs.db == db_session


def test_cosine_similarity_calculation(vector_store, sample_document_id):
    """Test that cosine similarity is calculated correctly"""
    # Create two identical embeddings
    embedding = np.random.rand(384)
    embedding = embedding / np.linalg.norm(embedding)  # Normalize
    
    vector_store.store_embedding(
        document_id=sample_document_id,
        chunk_index=0,
        content="Test content",
        embedding=embedding
    )
    
    # Search with same embedding
    results = vector_store.similarity_search(embedding, top_k=1)
    
    assert len(results) == 1
    chunk, score = results[0]
    
    # Identical embeddings should have similarity ~1.0
    assert score > 0.99
    assert score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
