"""
Hybrid search combining keyword (BM25) and semantic (vector) search.

Implements weighted fusion of keyword and semantic search results with
configurable weights and document filtering.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rag.embedder import get_embedder

logger = logging.getLogger(__name__)


class SearchResult:
    """Represents a single search result with score and metadata."""
    
    def __init__(
        self,
        document_id: UUID,
        chunk_id: UUID,
        chunk_index: int,
        content: str,
        score: float,
        metadata: dict[str, Any] | None = None
    ):
        self.document_id = document_id
        self.chunk_id = chunk_id
        self.chunk_index = chunk_index
        self.content = content
        self.score = score
        self.metadata = metadata or {}
    
    def __repr__(self) -> str:
        return f"SearchResult(doc={self.document_id}, score={self.score:.3f})"


class HybridSearchEngine:
    """
    Hybrid search engine combining keyword and semantic search.
    
    Uses PostgreSQL full-text search for keyword matching and pgvector
    for semantic similarity. Results are combined using weighted fusion.
    """
    
    def __init__(
        self,
        db: Session,
        keyword_weight: float = 0.6,
        semantic_weight: float = 0.4
    ):
        """
        Initialize hybrid search engine.
        
        Args:
            db: Database session
            keyword_weight: Weight for keyword search scores (default: 0.6)
            semantic_weight: Weight for semantic search scores (default: 0.4)
        """
        self.db = db
        self.keyword_weight = keyword_weight
        self.semantic_weight = semantic_weight
        self.embedder = get_embedder()
        
        # Validate weights
        if abs((keyword_weight + semantic_weight) - 1.0) > 0.01:
            logger.warning(
                f"Weights don't sum to 1.0: keyword={keyword_weight}, "
                f"semantic={semantic_weight}. Normalizing..."
            )
            total = keyword_weight + semantic_weight
            self.keyword_weight = keyword_weight / total
            self.semantic_weight = semantic_weight / total
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        category_filter: str | None = None,
        min_score: float = 0.0
    ) -> list[SearchResult]:
        """
        Perform hybrid search.
        
        Args:
            query: Search query string
            top_k: Number of results to return
            category_filter: Optional category to filter documents (e.g., 'faculty', 'news')
            min_score: Minimum combined score threshold
            
        Returns:
            List of SearchResult objects, sorted by descending score
        """
        logger.info(f"Hybrid search: query='{query}', top_k={top_k}, category={category_filter}")
        
        # Perform keyword search
        keyword_results = self._keyword_search(query, top_k=top_k * 2, category_filter=category_filter)
        
        # Perform semantic search
        semantic_results = self._semantic_search(query, top_k=top_k * 2, category_filter=category_filter)
        
        # Combine results
        combined_results = self._combine_results(keyword_results, semantic_results)
        
        # Filter by minimum score
        filtered_results = [r for r in combined_results if r.score >= min_score]
        
        # Return top_k
        final_results = filtered_results[:top_k]
        
        logger.info(f"Hybrid search returned {len(final_results)} results")
        return final_results
    
    def _keyword_search(
        self,
        query: str,
        top_k: int = 20,
        category_filter: str | None = None
    ) -> dict[UUID, tuple[float, dict]]:
        """
        Perform keyword-based search using PostgreSQL full-text search.
        
        Args:
            query: Search query
            top_k: Number of results
            category_filter: Optional category filter
            
        Returns:
            Dict mapping chunk_id to (score, metadata)
        """
        try:
            # Build query with optional category filter
            sql = """
                SELECT 
                    dc.id as chunk_id,
                    dc.document_id,
                    dc.chunk_index,
                    dc.content,
                    kd.title,
                    kd.category,
                    ts_rank(to_tsvector('english', dc.content), plainto_tsquery('english', :query)) as rank
                FROM document_chunks dc
                JOIN knowledge_documents kd ON dc.document_id = kd.id
                WHERE to_tsvector('english', dc.content) @@ plainto_tsquery('english', :query)
            """
            
            params = {'query': query, 'top_k': top_k}
            
            if category_filter:
                sql += " AND kd.category = :category"
                params['category'] = category_filter
            
            sql += " ORDER BY rank DESC LIMIT :top_k"
            
            result = self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            # Normalize scores to [0, 1]
            if rows:
                max_rank = max(row[6] for row in rows)
                if max_rank > 0:
                    results = {
                        row[0]: (  # chunk_id
                            row[6] / max_rank,  # normalized score
                            {
                                'document_id': row[1],
                                'chunk_index': row[2],
                                'content': row[3],
                                'title': row[4],
                                'category': row[5]
                            }
                        )
                        for row in rows
                    }
                else:
                    results = {}
            else:
                results = {}
            
            logger.debug(f"Keyword search found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Keyword search error: {e}")
            return {}
    
    def _semantic_search(
        self,
        query: str,
        top_k: int = 20,
        category_filter: str | None = None
    ) -> dict[UUID, tuple[float, dict]]:
        """
        Perform semantic search using vector similarity.
        
        Args:
            query: Search query
            top_k: Number of results
            category_filter: Optional category filter
            
        Returns:
            Dict mapping chunk_id to (score, metadata)
        """
        try:
            # Generate query embedding
            query_embedding = self.embedder.embed(query)
            embedding_list = query_embedding.tolist()
            
            # Build query with optional category filter
            sql = """
                SELECT 
                    dc.id as chunk_id,
                    dc.document_id,
                    dc.chunk_index,
                    dc.content,
                    kd.title,
                    kd.category,
                    1 - (dc.embedding <=> CAST(:embedding AS vector)) as similarity
                FROM document_chunks dc
                JOIN knowledge_documents kd ON dc.document_id = kd.id
                WHERE dc.embedding IS NOT NULL
            """
            
            params = {'embedding': str(embedding_list), 'top_k': top_k}
            
            if category_filter:
                sql += " AND kd.category = :category"
                params['category'] = category_filter
            
            sql += " ORDER BY dc.embedding <=> CAST(:embedding AS vector) LIMIT :top_k"
            
            result = self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            # Scores are already in [0, 1] range (cosine similarity)
            results = {
                row[0]: (  # chunk_id
                    max(0.0, row[6]),  # similarity score (clamp to >= 0)
                    {
                        'document_id': row[1],
                        'chunk_index': row[2],
                        'content': row[3],
                        'title': row[4],
                        'category': row[5]
                    }
                )
                for row in rows
            }
            
            logger.debug(f"Semantic search found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return {}
    
    def _combine_results(
        self,
        keyword_results: dict[UUID, tuple[float, dict]],
        semantic_results: dict[UUID, tuple[float, dict]]
    ) -> list[SearchResult]:
        """
        Combine keyword and semantic search results using weighted fusion.
        
        Args:
            keyword_results: Dict of chunk_id -> (score, metadata)
            semantic_results: Dict of chunk_id -> (score, metadata)
            
        Returns:
            List of SearchResult objects sorted by combined score
        """
        # Get all unique chunk IDs
        all_chunk_ids = set(keyword_results.keys()) | set(semantic_results.keys())
        
        combined = []
        
        for chunk_id in all_chunk_ids:
            # Get scores (0.0 if not present)
            keyword_score, keyword_meta = keyword_results.get(chunk_id, (0.0, {}))
            semantic_score, semantic_meta = semantic_results.get(chunk_id, (0.0, {}))
            
            # Weighted combination
            combined_score = (
                self.keyword_weight * keyword_score +
                self.semantic_weight * semantic_score
            )
            
            # Use metadata from whichever search found it (prefer keyword if both)
            metadata = keyword_meta if keyword_meta else semantic_meta
            
            # Create result object
            result = SearchResult(
                document_id=metadata['document_id'],
                chunk_id=chunk_id,
                chunk_index=metadata['chunk_index'],
                content=metadata['content'],
                score=combined_score,
                metadata={
                    'title': metadata['title'],
                    'category': metadata['category'],
                    'keyword_score': keyword_score,
                    'semantic_score': semantic_score
                }
            )
            
            combined.append(result)
        
        # Sort by combined score (descending)
        combined.sort(key=lambda x: x.score, reverse=True)
        
        return combined


def create_hybrid_search_engine(
    db: Session,
    keyword_weight: float = 0.6,
    semantic_weight: float = 0.4
) -> HybridSearchEngine:
    """
    Factory function to create a HybridSearchEngine.
    
    Args:
        db: Database session
        keyword_weight: Weight for keyword search (default: 0.6)
        semantic_weight: Weight for semantic search (default: 0.4)
        
    Returns:
        Configured HybridSearchEngine instance
    """
    return HybridSearchEngine(
        db=db,
        keyword_weight=keyword_weight,
        semantic_weight=semantic_weight
    )
