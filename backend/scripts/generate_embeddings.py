"""
Generate embeddings for knowledge documents.

This script processes knowledge_documents with processing_status='pending',
chunks their content, generates embeddings, and stores them in the
document_chunks table.

Usage:
    python backend/scripts/generate_embeddings.py

Requirements: 30
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.rag.chunking import chunk_text
from app.rag.embedder import get_embedder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Path to scraped data JSON
SCRAPED_DATA_PATH = Path(__file__).parent.parent.parent / "academic-data" / "scraped" / "cs_website_full.json"

# Cache for scraped data (load once)
_scraped_data_cache: Optional[dict[str, dict]] = None


def load_scraped_data() -> dict[str, dict]:
    """
    Load and cache scraped data from JSON file.
    
    Returns:
        Dictionary mapping URLs to their content data
    """
    global _scraped_data_cache
    
    if _scraped_data_cache is not None:
        return _scraped_data_cache
    
    logger.info(f"Loading scraped data from {SCRAPED_DATA_PATH}")
    
    if not SCRAPED_DATA_PATH.exists():
        raise FileNotFoundError(f"Scraped data not found at {SCRAPED_DATA_PATH}")
    
    with open(SCRAPED_DATA_PATH, 'r', encoding='utf-8') as f:
        scraped_list = json.load(f)
    
    # Build URL -> content mapping
    _scraped_data_cache = {item['url']: item for item in scraped_list}
    
    logger.info(f"Loaded {len(_scraped_data_cache)} pages from scraped data")
    return _scraped_data_cache


def get_content_from_storage_path(storage_path: str, title: str, category: str) -> str:
    """
    Get content from storage_path (URL or special path).
    
    Args:
        storage_path: URL from scraped data or special path like 'database://...'
        title: Document title (for fallback)
        category: Document category (for fallback)
        
    Returns:
        Content string
    """
    # Handle special storage paths
    if storage_path.startswith('database://'):
        # This is the demo/seed document - return placeholder
        return f"{title}\n\nCategory: {category}\n\nThis is a seed document for operational guidance."
    
    # Load scraped data
    scraped_data = load_scraped_data()
    
    # Try to find content by URL
    if storage_path in scraped_data:
        content = scraped_data[storage_path].get('content', '')
        if content:
            # Skip PDF and other binary content (starts with %PDF)
            if content.startswith('%PDF') or '\x00' in content[:100]:
                logger.warning(f"Skipping binary content for: {storage_path}")
                return f"{title}\n\nCategory: {category}\n\n[Binary content - PDF or other format]"
            return content
    
    # Fallback: return title + category
    logger.warning(f"No content found for storage_path: {storage_path}, using title as fallback")
    return f"{title}\n\nCategory: {category}"


def chunk_document(content: str, max_chunk_size: int = 512) -> list[str]:
    """
    Chunk document content with sentence-aware splitting.
    
    Uses the existing chunk_text function but adapts parameters
    to meet the requirements of task 5.1.
    
    Args:
        content: The document content to chunk
        max_chunk_size: Maximum characters per chunk (default 512)
        
    Returns:
        List of text chunks with overlap for continuity
    """
    # Use 50-character overlap as specified in requirements
    overlap = 50
    
    # chunk_text returns list of TextChunk objects
    chunks = chunk_text(content, chunk_size=max_chunk_size, overlap=overlap)
    
    # Extract just the content strings
    return [chunk.content for chunk in chunks]


def generate_embeddings_for_document(
    db: Session,
    document: dict[str, Any],
    embedder: Any
) -> tuple[int, bool]:
    """
    Generate and store embeddings for a single document.
    
    Args:
        db: Database session
        document: Dictionary with document data (id, title, category, storage_path)
        embedder: Embedder instance for generating embeddings
        
    Returns:
        Tuple of (num_chunks_created, success)
    """
    document_id = document['id']
    storage_path = document['storage_path']
    title = document['title']
    category = document['category']
    
    try:
        # Step 1: Get content from storage_path
        content = get_content_from_storage_path(storage_path, title, category)
        
        if not content or len(content.strip()) < 10:
            logger.warning(f"Document {document_id} has insufficient content")
            # Update status to ready even if no content
            db.execute(
                text("""
                    UPDATE knowledge_documents
                    SET processing_status = 'ready',
                        processed_at = NOW(),
                        processing_error = 'Insufficient content'
                    WHERE id = :document_id
                """),
                {"document_id": document_id}
            )
            db.commit()
            return 0, True
        
        # Step 2: Chunk the document content
        chunks = chunk_document(content, max_chunk_size=512)
        
        if not chunks:
            logger.warning(f"Document {document_id} produced no chunks")
            # Update status to ready even if no chunks (empty document)
            db.execute(
                text("""
                    UPDATE knowledge_documents
                    SET processing_status = 'ready',
                        processed_at = NOW(),
                        processing_error = 'Document produced no chunks'
                    WHERE id = :document_id
                """),
                {"document_id": document_id}
            )
            db.commit()
            return 0, True
        
        # Step 3: Generate embeddings for all chunks in batch
        embeddings = embedder.embed_batch(chunks)
        
        # Step 4: Store chunks and embeddings in database
        for chunk_index, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
            # Convert numpy array to list for PostgreSQL
            embedding_list = embedding.tolist()
            
            # Clean content - remove NUL bytes that PostgreSQL can't handle
            clean_content = chunk_content.replace('\x00', '')
            
            db.execute(
                text("""
                    INSERT INTO document_chunks (
                        document_id,
                        chunk_index,
                        content,
                        embedding,
                        metadata
                    ) VALUES (
                        :document_id,
                        :chunk_index,
                        :content,
                        CAST(:embedding AS vector),
                        '{}'::jsonb
                    )
                """),
                {
                    "document_id": str(document_id),
                    "chunk_index": chunk_index,
                    "content": clean_content,
                    "embedding": str(embedding_list)
                }
            )
        
        # Step 5: Update processing_status to 'ready'
        db.execute(
            text("""
                UPDATE knowledge_documents
                SET processing_status = 'ready',
                    processed_at = NOW(),
                    processing_error = NULL
                WHERE id = :document_id
            """),
            {"document_id": document_id}
        )
        
        db.commit()
        logger.debug(f"Successfully processed document {document_id}: {len(chunks)} chunks")
        return len(chunks), True
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
        
        # Update status to 'failed' with error message
        try:
            db.execute(
                text("""
                    UPDATE knowledge_documents
                    SET processing_status = 'failed',
                        processed_at = NOW(),
                        processing_error = :error
                    WHERE id = :document_id
                """),
                {
                    "document_id": document_id,
                    "error": str(e)[:500]  # Limit error message length
                }
            )
            db.commit()
        except Exception as inner_e:
            logger.error(f"Failed to update error status: {inner_e}")
            db.rollback()
        
        return 0, False


def main():
    """
    Main function to process all pending knowledge documents.
    
    Queries all documents with processing_status='pending',
    processes them in order, and logs progress every 10 documents.
    """
    logger.info("Starting embedding generation process")
    start_time = time.time()
    
    # Initialize embedder (loads model once)
    logger.info("Loading embedding model...")
    embedder = get_embedder()
    logger.info(f"Embedding model loaded: {embedder.model_name} (dimension: {embedder.dimension})")
    
    # Get database session
    session_factory = get_session_factory()
    db = session_factory()
    
    try:
        # Query all pending documents
        result = db.execute(
            text("""
                SELECT id, title, category, storage_path
                FROM knowledge_documents
                WHERE processing_status = 'pending'
            """)
        )
        
        pending_documents = [dict(row._mapping) for row in result]
        total_documents = len(pending_documents)
        
        if total_documents == 0:
            logger.info("No pending documents to process")
            return
        
        logger.info(f"Found {total_documents} pending documents to process")
        
        # Process each document
        processed_count = 0
        failed_count = 0
        total_chunks = 0
        
        for i, document in enumerate(pending_documents, 1):
            num_chunks, success = generate_embeddings_for_document(db, document, embedder)
            
            if success:
                processed_count += 1
                total_chunks += num_chunks
            else:
                failed_count += 1
            
            # Log progress every 10 documents
            if i % 10 == 0:
                elapsed = time.time() - start_time
                docs_per_sec = i / elapsed if elapsed > 0 else 0
                logger.info(
                    f"Progress: {i}/{total_documents} documents processed "
                    f"({processed_count} successful, {failed_count} failed, "
                    f"{total_chunks} total chunks, "
                    f"{docs_per_sec:.2f} docs/sec)"
                )
        
        # Final summary
        elapsed = time.time() - start_time
        logger.info("=" * 80)
        logger.info("Embedding generation completed")
        logger.info(f"Total documents: {total_documents}")
        logger.info(f"Successfully processed: {processed_count}")
        logger.info(f"Failed: {failed_count}")
        logger.info(f"Total chunks created: {total_chunks}")
        logger.info(f"Total time: {elapsed:.2f} seconds")
        logger.info(f"Average: {elapsed/total_documents:.2f} seconds per document")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Fatal error in main process: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
