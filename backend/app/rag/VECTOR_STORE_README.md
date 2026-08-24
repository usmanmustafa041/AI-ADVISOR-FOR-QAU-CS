# VectorStore Implementation

## Overview

This module implements a PostgreSQL-backed vector store using the pgvector extension for semantic similarity search. It provides methods for storing document embeddings, performing cosine similarity searches, and managing document chunks.

## Requirements Implemented

- **Requirement 3**: Hybrid Search Implementation - Vector similarity search using cosine distance
- **Requirement 30**: Vector Embedding Generation - Storage and retrieval of embeddings

## Features

### Core Functionality

1. **Store Embeddings**: Store document chunks with 384-dimensional embeddings
2. **Similarity Search**: Perform semantic search using cosine similarity (`<=>` operator)
3. **Delete Documents**: Remove all chunks for a given document
4. **Filtering**: Support for document_type and minimum similarity filters
5. **Chunk Retrieval**: Get specific chunks by ID
6. **Counting**: Count chunks per document or globally

### Performance Optimizations

- Uses pgvector's HNSW index for fast approximate nearest neighbor search
- Cosine similarity operator `<=>` for efficient vector comparisons
- Database connection pooling via SQLAlchemy
- JSONB metadata storage for flexible chunk attributes

## Usage

### Basic Example

```python
from app.rag.vector_store import create_vector_store
from app.core.database import get_db
import numpy as np
from uuid import UUID

# Get database session
db = next(get_db())

# Create vector store
vector_store = create_vector_store(db)

# Store an embedding
document_id = UUID("...")  # Your knowledge_documents ID
embedding = np.random.rand(384)  # Your 384-dim embedding
content = "This is a document chunk about machine learning"
metadata = {"topic": "AI", "importance": "high"}

chunk_id = vector_store.store_embedding(
    document_id=document_id,
    chunk_index=0,
    content=content,
    embedding=embedding,
    metadata=metadata
)

# Search for similar chunks
query_embedding = np.random.rand(384)
results = vector_store.similarity_search(
    query_embedding=query_embedding,
    top_k=10,
    filters={"min_similarity": 0.75}
)

for chunk, score in results:
    print(f"Score: {score:.4f}")
    print(f"Content: {chunk.content}")
    print(f"Metadata: {chunk.metadata}")
```

### Filtering

```python
# Filter by document type (requires JOIN with knowledge_documents)
results = vector_store.similarity_search(
    query_embedding=embedding,
    top_k=10,
    filters={"document_type": "faculty"}
)

# Filter by minimum similarity threshold
results = vector_store.similarity_search(
    query_embedding=embedding,
    top_k=10,
    filters={"min_similarity": 0.80}
)

# Combine filters
results = vector_store.similarity_search(
    query_embedding=embedding,
    top_k=10,
    filters={
        "document_type": "news",
        "min_similarity": 0.70
    }
)
```

### Deleting Documents

```python
# Delete all chunks for a document
deleted_count = vector_store.delete_document(document_id)
print(f"Deleted {deleted_count} chunks")
```

## Database Schema

The vector store uses the existing `document_chunks` table:

```sql
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    content TEXT NOT NULL,
    page_number INTEGER CHECK (page_number IS NULL OR page_number > 0),
    section_title TEXT,
    token_count INTEGER CHECK (token_count IS NULL OR token_count > 0),
    embedding VECTOR(384),
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_embedding_hnsw 
    ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

## Similarity Score Calculation

The cosine similarity score is calculated from the cosine distance:

1. PostgreSQL `<=>` operator returns cosine distance in range [0, 2]
   - Distance 0 = identical vectors
   - Distance 2 = opposite vectors

2. We convert to similarity score in range [0, 1]:
   ```
   similarity = 1 - (distance / 2)
   ```

3. Result interpretation:
   - Score = 1.0: Identical embeddings
   - Score = 0.5: Orthogonal (unrelated)
   - Score = 0.0: Opposite embeddings

## Testing

### Manual Test Script

A manual test script is provided at `backend/test_vector_store_manual.py`:

```bash
cd backend
source .venv/bin/activate
python test_vector_store_manual.py
```

This tests:
- Embedding storage
- Similarity search
- Filtering
- Chunk retrieval
- Document deletion
- Count operations

### Unit Tests

Unit tests are available at `backend/app/rag/test_vector_store.py`. Requires pytest:

```bash
cd backend
source .venv/bin/activate
pytest app/rag/test_vector_store.py -v
```

## Integration with Hybrid Search

This VectorStore is designed to be used by the HybridSearchEngine:

```python
from app.rag.hybrid_search import HybridSearchEngine

# Create hybrid search engine
search_engine = HybridSearchEngine(db=db, vector_store=vector_store)

# Execute hybrid search (combines SQL keyword + vector semantic search)
results = await search_engine.search(
    query="machine learning algorithms",
    filters={"document_type": "course"},
    top_k=10
)
```

## Performance Considerations

1. **Index Type**: The HNSW index provides fast approximate nearest neighbor search
   - Trade-off: Slight accuracy reduction for significant speed improvement
   - Suitable for RAG applications with large document collections

2. **Embedding Dimensionality**: Uses 384 dimensions (sentence-transformers/all-MiniLM-L6-v2)
   - Good balance between performance and quality
   - ~4x faster than 768-dim models with comparable accuracy

3. **Batch Operations**: For bulk inserts, consider using database transactions:
   ```python
   for chunk in chunks:
       vector_store.store_embedding(...)
   db.commit()  # Commit once after all inserts
   ```

4. **Connection Pooling**: SQLAlchemy connection pooling is automatically configured
   - Pre-ping enabled for connection health checks
   - Pool recycle at 1800 seconds

## Error Handling

The VectorStore includes robust error handling:

1. **pgvector Extension**: Automatically attempts to enable extension (safe to call multiple times)
2. **Transaction Management**: Uses database commits for atomic operations
3. **Type Conversion**: Handles both numpy arrays and lists for embeddings
4. **Null Handling**: Gracefully handles missing embeddings or metadata

## Future Enhancements

Potential improvements for future iterations:

1. **Batch Insert**: Add method for bulk embedding storage
2. **Partial Updates**: Update embedding without re-storing content
3. **Metadata Filtering**: Support JSONB queries in filters
4. **Temporal Filtering**: Filter by chunk creation/update timestamps
5. **Multi-vector Search**: Search across multiple embedding spaces
6. **Reranking**: Add cross-encoder reranking for top results

## Dependencies

- SQLAlchemy 2.0+
- psycopg[binary] 3.2+
- numpy
- pgvector extension (PostgreSQL)

## References

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Sentence Transformers](https://www.sbert.net/)
