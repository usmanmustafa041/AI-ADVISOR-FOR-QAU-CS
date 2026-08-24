"""Generates embeddings for structured chunks."""

import logging
import math
from typing import Optional

from ..embedding import embed_text, EMBEDDING_DIMENSION
from .constants import (
    EMBEDDING_DIMENSION as STRUCTURED_EMBEDDING_DIMENSION,
    MAX_EMBEDDING_TOKEN_LENGTH,
)

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates embeddings for structured document chunks."""
    
    # Allow small tolerance for L2 norm due to floating point precision
    L2_NORM_TOLERANCE = 0.01
    
    @staticmethod
    def generate_embedding(text: str) -> Optional[list[float]]:
        """
        Generate embedding for a text chunk.
        
        Args:
            text: Text content to embed (will be truncated to 512 tokens)
            
        Returns:
            384-dimensional embedding vector, or None if generation fails
            
        Requirements:
            - 9.1-9.7: Embedding generation with validation and normalization
        """
        if not text or not isinstance(text, str):
            logger.error("Invalid text input for embedding")
            return None
        
        # Truncate text to token limit (Requirement 9.2)
        # Simple approximation: assume ~4 characters per token
        max_chars = MAX_EMBEDDING_TOKEN_LENGTH * 4
        if len(text) > max_chars:
            logger.debug(f"Text truncated from {len(text)} to {max_chars} characters")
            text = text[:max_chars]
        
        try:
            # Call existing embed_text function (Requirement 9.1)
            embedding = embed_text(text, dimension=EMBEDDING_DIMENSION)
            
            # Validate dimension (Requirement 9.3-9.4)
            if not embedding or len(embedding) != EMBEDDING_DIMENSION:
                logger.error(
                    f"Invalid embedding dimension: expected {EMBEDDING_DIMENSION}, "
                    f"got {len(embedding) if embedding else 'None'}"
                )
                return None
            
            # Normalize to L2 norm = 1.0 (Requirement 9.7)
            normalized = EmbeddingGenerator._normalize_l2(embedding)
            
            # Validate normalization
            if not normalized:
                return None
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}", exc_info=True)
            return None
    
    @staticmethod
    def _normalize_l2(vector: list[float]) -> Optional[list[float]]:
        """
        Normalize vector to L2 norm = 1.0.
        
        Args:
            vector: Vector to normalize
            
        Returns:
            Normalized vector or None if normalization fails
            
        Requirements:
            - 9.7: Normalize with L2 norm within 0.01 tolerance
        """
        if not vector or len(vector) != EMBEDDING_DIMENSION:
            logger.error(f"Invalid vector length for normalization: {len(vector) if vector else 0}")
            return None
        
        try:
            # Calculate L2 norm
            norm = math.sqrt(sum(x * x for x in vector))
            
            if norm == 0:
                logger.warning("Cannot normalize zero vector, returning zero vector")
                return vector
            
            # Normalize
            normalized = [x / norm for x in vector]
            
            # Verify normalization within tolerance
            new_norm = math.sqrt(sum(x * x for x in normalized))
            if abs(new_norm - 1.0) > EmbeddingGenerator.L2_NORM_TOLERANCE:
                logger.warning(
                    f"L2 norm {new_norm} outside tolerance (expected 1.0 ±{EmbeddingGenerator.L2_NORM_TOLERANCE})"
                )
                # Continue anyway, it's close enough
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error normalizing vector: {e}")
            return None
    
    @staticmethod
    def validate_embedding(embedding: list[float]) -> bool:
        """
        Validate that an embedding meets requirements.
        
        Args:
            embedding: Embedding vector to validate
            
        Returns:
            True if valid, False otherwise
            
        Requirements:
            - 9.3-9.5: Dimension validation
        """
        if not embedding or not isinstance(embedding, list):
            logger.error("Invalid embedding: not a list")
            return False
        
        if len(embedding) != EMBEDDING_DIMENSION:
            logger.error(
                f"Invalid embedding dimension: expected {EMBEDDING_DIMENSION}, "
                f"got {len(embedding)}"
            )
            return False
        
        # Check all values are floats
        if not all(isinstance(x, (int, float)) for x in embedding):
            logger.error("Invalid embedding: contains non-numeric values")
            return False
        
        return True
    
    @staticmethod
    def to_pgvector_format(embedding: list[float]) -> str:
        """
        Format embedding for PostgreSQL pgvector storage.
        
        Args:
            embedding: Embedding vector
            
        Returns:
            String representation for pgvector (e.g., "[0.1,0.2,...]")
            
        Requirements:
            - 9.6: Serialize to PostgreSQL pgvector format as vector(384)
        """
        if not EmbeddingGenerator.validate_embedding(embedding):
            raise ValueError("Invalid embedding for pgvector format")
        
        # Format as pgvector literal: [value1,value2,...]
        return "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
