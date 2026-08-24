"""
Embedding generator module for RAG pipeline.

This module provides the Embedder class for generating vector embeddings
using sentence-transformers. The embeddings are used for semantic search
in the hybrid search pipeline.

Requirements: 30
"""

import numpy as np
from typing import Optional
from sentence_transformers import SentenceTransformer


class Embedder:
    """
    Generate embeddings for text using sentence-transformers.
    
    This class uses the sentence-transformers/all-MiniLM-L6-v2 model
    which produces 384-dimensional embeddings. The model is cached
    as a singleton to avoid repeated loading.
    
    Usage:
        embedder = Embedder()
        embedding = embedder.embed_text("Hello world")
        embeddings = embedder.embed_batch(["Hello", "world"])
    """
    
    # Class variable for singleton pattern
    _model: Optional[SentenceTransformer] = None
    _model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    def __init__(self):
        """Initialize the Embedder and load the model if not already loaded."""
        if Embedder._model is None:
            self._load_model()
    
    @classmethod
    def _load_model(cls) -> None:
        """
        Load the sentence-transformer model.
        
        The model is cached as a class variable (singleton pattern)
        to avoid loading it multiple times, which would waste memory
        and time.
        """
        if cls._model is None:
            cls._model = SentenceTransformer(cls._model_name)
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text string.
        
        Args:
            text: The input text to embed
            
        Returns:
            A numpy array of shape (384,) containing the embedding
            
        Example:
            >>> embedder = Embedder()
            >>> embedding = embedder.embed_text("What are the prerequisites for CS-301?")
            >>> embedding.shape
            (384,)
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return np.zeros(384, dtype=np.float32)
        
        # encode returns numpy array of shape (384,)
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding
    
    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """
        Generate embeddings for a batch of texts.
        
        This is more efficient than calling embed_text() multiple times
        as the model can process multiple texts in parallel.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of numpy arrays, each of shape (384,)
            
        Example:
            >>> embedder = Embedder()
            >>> embeddings = embedder.embed_batch([
            ...     "What are the prerequisites for CS-301?",
            ...     "Who teaches Data Structures?",
            ...     "When is the registration deadline?"
            ... ])
            >>> len(embeddings)
            3
            >>> embeddings[0].shape
            (384,)
        """
        if not texts:
            return []
        
        # Handle empty strings
        processed_texts = [text if text and text.strip() else " " for text in texts]
        
        # encode returns numpy array of shape (n, 384)
        embeddings = self._model.encode(processed_texts, convert_to_numpy=True, show_progress_bar=False)
        
        # Convert to list of individual arrays
        return [embeddings[i] for i in range(len(embeddings))]
    
    @property
    def dimension(self) -> int:
        """Return the embedding dimension (384 for all-MiniLM-L6-v2)."""
        return 384
    
    @property
    def model_name(self) -> str:
        """Return the name of the model being used."""
        return self._model_name


# Create a global instance for convenience
_global_embedder: Optional[Embedder] = None


def get_embedder() -> Embedder:
    """
    Get the global Embedder instance (singleton).
    
    This function provides a convenient way to get the embedder
    without having to manage instances manually.
    
    Returns:
        The global Embedder instance
        
    Example:
        >>> embedder = get_embedder()
        >>> embedding = embedder.embed_text("Hello world")
    """
    global _global_embedder
    if _global_embedder is None:
        _global_embedder = Embedder()
    return _global_embedder
