"""
Manual test script for VectorStore implementation
Run this to verify the vector store works correctly
"""

import sys
import numpy as np
from uuid import uuid4
from sqlalchemy import text

# Add app to path
sys.path.insert(0, '/Users/mm/AI-ADVISOR-FOR-QAU-CS/backend')

from app.rag.vector_store import VectorStore, create_vector_store
from app.core.database import get_db


def test_vector_store():
    """Test the VectorStore implementation"""
    print("=" * 60)
    print("Testing VectorStore Implementation")
    print("=" * 60)
    
    # Get database session
    print("\n1. Getting database session...")
    db = next(get_db())
    
    try:
        # Create vector store
        print("2. Creating VectorStore instance...")
        vector_store = create_vector_store(db)
        print("   ✓ VectorStore created successfully")
        
        # Create a test document
        print("\n3. Creating test document...")
        
        # First ensure we have a source_record
        source_result = db.execute(
            text("""
                INSERT INTO source_records (source_code, title, category, authority, verification_status)
                VALUES ('TEST-VECTOR', 'Test Vector Source', 'document', 'system', 'verified')
                ON CONFLICT (source_code) DO UPDATE SET source_code = EXCLUDED.source_code
                RETURNING id
            """)
        )
        source_id = source_result.scalar_one()
        print(f"   ✓ Source record created: {source_id}")
        
        # Create knowledge_documents record
        doc_result = db.execute(
            text("""
                INSERT INTO knowledge_documents (source_id, title, category, storage_path, processing_status)
                VALUES (:source_id, 'Test Document', 'test', '/test/path', 'pending')
                RETURNING id
            """),
            {"source_id": str(source_id)}
        )
        db.commit()
        document_id = doc_result.scalar_one()
        print(f"   ✓ Knowledge document created: {document_id}")
        
        # Test 1: Store embeddings
        print("\n4. Testing store_embedding()...")
        test_embeddings = []
        test_contents = [
            "Machine learning is a subset of artificial intelligence",
            "Deep learning uses neural networks with multiple layers",
            "Natural language processing enables computers to understand text"
        ]
        
        for i, content in enumerate(test_contents):
            embedding = np.random.rand(384)
            test_embeddings.append(embedding)
            metadata = {"index": i, "topic": "AI"}
            
            chunk_id = vector_store.store_embedding(
                document_id=document_id,
                chunk_index=i,
                content=content,
                embedding=embedding,
                metadata=metadata
            )
            print(f"   ✓ Stored chunk {i}: {chunk_id}")
        
        # Test 2: Count chunks
        print("\n5. Testing count_chunks()...")
        count = vector_store.count_chunks(document_id)
        print(f"   ✓ Total chunks: {count}")
        assert count == 3, f"Expected 3 chunks, got {count}"
        
        # Test 3: Similarity search
        print("\n6. Testing similarity_search()...")
        query_embedding = test_embeddings[0]  # Use first embedding as query
        results = vector_store.similarity_search(query_embedding, top_k=3)
        
        print(f"   ✓ Found {len(results)} results")
        for i, (chunk, score) in enumerate(results):
            print(f"   Result {i+1}: score={score:.4f}, content='{chunk.content[:50]}...'")
        
        # The first result should be highly similar (same embedding)
        if results:
            top_chunk, top_score = results[0]
            print(f"   ✓ Top result similarity: {top_score:.4f}")
            assert top_score > 0.99, f"Expected similarity > 0.99, got {top_score}"
        
        # Test 4: Similarity search with filters
        print("\n7. Testing similarity_search() with min_similarity filter...")
        filtered_results = vector_store.similarity_search(
            query_embedding,
            top_k=10,
            filters={"min_similarity": 0.7}
        )
        print(f"   ✓ Found {len(filtered_results)} results with similarity >= 0.7")
        
        # Test 5: Get specific chunk
        print("\n8. Testing get_chunk()...")
        if results:
            first_chunk_id = results[0][0].id
            retrieved_chunk = vector_store.get_chunk(first_chunk_id)
            print(f"   ✓ Retrieved chunk: {retrieved_chunk.id}")
            assert retrieved_chunk is not None
            assert str(retrieved_chunk.id) == str(first_chunk_id)
        
        # Test 6: Delete document
        print("\n9. Testing delete_document()...")
        deleted_count = vector_store.delete_document(document_id)
        print(f"   ✓ Deleted {deleted_count} chunks")
        assert deleted_count == 3, f"Expected to delete 3 chunks, deleted {deleted_count}"
        
        # Verify deletion
        count_after = vector_store.count_chunks(document_id)
        print(f"   ✓ Chunks remaining: {count_after}")
        assert count_after == 0, f"Expected 0 chunks after deletion, got {count_after}"
        
        # Cleanup
        print("\n10. Cleaning up test data...")
        db.execute(
            text("DELETE FROM knowledge_documents WHERE id = :doc_id"),
            {"doc_id": str(document_id)}
        )
        db.commit()
        print("   ✓ Cleanup complete")
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()
    
    return True


if __name__ == "__main__":
    success = test_vector_store()
    sys.exit(0 if success else 1)
