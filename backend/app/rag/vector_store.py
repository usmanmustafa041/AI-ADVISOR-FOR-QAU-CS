"""
Vector Store for RAG using pgvector
Implements semantic search using PostgreSQL vector embeddings
Provides methods for storing, searching, and deleting document embeddings
"""

from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from uuid import UUID
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class DocumentChunk:
    """Represents a document chunk with metadata"""
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    embedding: Optional[np.ndarray]
    metadata: Optional[Dict]
    score: Optional[float] = None


class VectorStore:
    """
    PostgreSQL-backed vector store using pgvector extension
    Stores document embeddings and performs semantic search using cosine similarity
    """
    
    def __init__(self, db: Session):
        """
        Initialize vector store with database session
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._ensure_pgvector_extension()
    
    def _ensure_pgvector_extension(self):
        """Ensure pgvector extension is enabled (safe to call multiple times)"""
        try:
            self.db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            self.db.commit()
        except Exception as e:
            # Extension may already exist or user may not have permissions
            # This is non-critical as migrations should handle this
            self.db.rollback()
    
    def store_embedding(
        self,
        document_id: UUID,
        chunk_index: int,
        content: str,
        embedding: np.ndarray,
        metadata: Optional[Dict] = None
    ) -> UUID:
        """
        Store a document chunk with its embedding
        
        Args:
            document_id: UUID of the parent knowledge_documents record
            chunk_index: Sequential index of this chunk within the document
            content: Text content of the chunk
            embedding: 384-dimensional embedding vector
            metadata: Optional metadata dict (stored as JSONB)
        
        Returns:
            UUID of the created document_chunks record
        """
        # Convert numpy array to list for PostgreSQL
        embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
        
        # Convert metadata to JSON-compatible format
        metadata_json = metadata if metadata else {}
        
        # Insert into document_chunks table
        result = self.db.execute(
            text("""
                INSERT INTO document_chunks (document_id, chunk_index, content, embedding, metadata)
                VALUES (:document_id, :chunk_index, :content, :embedding::vector, :metadata::jsonb)
                RETURNING id
            """),
            {
                "document_id": str(document_id),
                "chunk_index": chunk_index,
                "content": content,
                "embedding": str(embedding_list),
                "metadata": str(metadata_json).replace("'", '"')
            }
        )
        self.db.commit()
        
        chunk_id = result.scalar_one()
        return UUID(chunk_id)
    
    def similarity_search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Perform semantic similarity search using cosine distance
        
        Args:
            query_embedding: 384-dimensional query embedding vector
            top_k: Number of top results to return (default: 10)
            filters: Optional filters dict with keys:
                - document_type: Filter by knowledge_documents.document_type
                - min_similarity: Minimum cosine similarity threshold (0-1)
        
        Returns:
            List of tuples (DocumentChunk, similarity_score) sorted by relevance
            Similarity score is converted from distance: 1 - cosine_distance
        """
        # Convert numpy array to list for PostgreSQL
        embedding_list = query_embedding.tolist() if isinstance(query_embedding, np.ndarray) else query_embedding
        
        # Build query with optional filters
        where_clauses = []
        params = {
            "query_embedding": str(embedding_list),
            "top_k": top_k
        }
        
        # Apply document_type filter if specified
        if filters and "document_type" in filters:
            where_clauses.append("kd.document_type = :document_type")
            params["document_type"] = filters["document_type"]
        
        # Apply minimum similarity filter if specified
        if filters and "min_similarity" in filters:
            # Cosine distance <=> returns value in [0, 2]
            # Distance 0 = identical, Distance 2 = opposite
            # Similarity = 1 - (distance / 2)
            # So: similarity >= threshold means distance <= 2 * (1 - threshold)
            max_distance = 2 * (1 - filters["min_similarity"])
            where_clauses.append(f"(dc.embedding <=> :query_embedding::vector) <= {max_distance}")
        
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Execute similarity search using cosine distance operator <=>
        query_sql = f"""
            SELECT 
                dc.id,
                dc.document_id,
                dc.chunk_index,
                dc.content,
                dc.embedding,
                dc.metadata,
                (dc.embedding <=> :query_embedding::vector) AS distance
            FROM document_chunks dc
            LEFT JOIN knowledge_documents kd ON dc.document_id = kd.id
            {where_clause}
            ORDER BY dc.embedding <=> :query_embedding::vector
            LIMIT :top_k
        """
        
        result = self.db.execute(text(query_sql), params)
        
        # Convert results to DocumentChunk objects
        results = []
        for row in result.mappings():
            # Convert cosine distance to similarity score (1 - distance/2)
            # This normalizes to [0, 1] where 1 is identical
            distance = float(row["distance"])
            similarity_score = 1 - (distance / 2)
            
            # Parse embedding back to numpy array
            embedding_data = row["embedding"] if row["embedding"] else None
            
            chunk = DocumentChunk(
                id=UUID(row["id"]),
                document_id=UUID(row["document_id"]),
                chunk_index=int(row["chunk_index"]),
                content=str(row["content"]),
                embedding=embedding_data,
                metadata=dict(row["metadata"]) if row["metadata"] else {},
                score=similarity_score
            )
            
            results.append((chunk, similarity_score))
        
        return results
    
    def delete_document(self, document_id: UUID) -> int:
        """
        Delete all chunks for a given document
        
        Args:
            document_id: UUID of the knowledge_documents record
        
        Returns:
            Number of chunks deleted
        """
        result = self.db.execute(
            text("""
                DELETE FROM document_chunks
                WHERE document_id = :document_id
                RETURNING id
            """),
            {"document_id": str(document_id)}
        )
        self.db.commit()
        
        # Count deleted rows
        deleted_count = len(result.fetchall())
        return deleted_count
    
    def get_chunk(self, chunk_id: UUID) -> Optional[DocumentChunk]:
        """
        Retrieve a specific chunk by ID
        
        Args:
            chunk_id: UUID of the document_chunks record
        
        Returns:
            DocumentChunk object or None if not found
        """
        result = self.db.execute(
            text("""
                SELECT id, document_id, chunk_index, content, embedding, metadata
                FROM document_chunks
                WHERE id = :chunk_id
            """),
            {"chunk_id": str(chunk_id)}
        )
        
        row = result.mappings().first()
        if not row:
            return None
        
        return DocumentChunk(
            id=UUID(row["id"]),
            document_id=UUID(row["document_id"]),
            chunk_index=int(row["chunk_index"]),
            content=str(row["content"]),
            embedding=row["embedding"] if row["embedding"] else None,
            metadata=dict(row["metadata"]) if row["metadata"] else {}
        )
    
    def count_chunks(self, document_id: Optional[UUID] = None) -> int:
        """
        Count chunks in the vector store
        
        Args:
            document_id: Optional document ID to count chunks for specific document
        
        Returns:
            Number of chunks
        """
        if document_id:
            result = self.db.execute(
                text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :document_id"),
                {"document_id": str(document_id)}
            )
        else:
            result = self.db.execute(text("SELECT COUNT(*) FROM document_chunks"))
        
        return result.scalar_one()


# Factory function for creating VectorStore instances
def create_vector_store(db: Session) -> VectorStore:
    """
    Factory function to create a VectorStore instance
    
    Args:
        db: SQLAlchemy database session
    
    Returns:
        Initialized VectorStore instance
    """
    return VectorStore(db)
