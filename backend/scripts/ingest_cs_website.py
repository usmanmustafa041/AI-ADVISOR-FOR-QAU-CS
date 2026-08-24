"""
Ingest scraped CS website data into knowledge base.
"""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import get_db
from app.rag.embedder import get_embedder

def ingest_cs_website():
    """Ingest all scraped CS website pages."""
    
    # Load scraped data
    scraped_file = Path(__file__).parent.parent.parent / "academic-data/scraped/cs_website_full.json"
    
    with open(scraped_file, 'r', encoding='utf-8') as f:
        pages = json.load(f)
    
    print(f"Loaded {len(pages)} pages from CS website")
    
    # Get database and embedder
    db = next(get_db())
    embedder = get_embedder()
    
    ingested = 0
    total_chunks = 0
    
    for page in pages:
        url = page['url']
        title = page['title']
        content = page['content']
        word_count = page['word_count']
        
        # Skip empty or very short content
        if word_count < 50:
            print(f"Skipping {title} (too short: {word_count} words)")
            continue
        
        # Determine category from URL
        category = 'general'
        if 'faculty' in url.lower():
            category = 'faculty'
        elif 'academics' in url.lower() or 'programme' in url.lower() or 'bs.html' in url.lower():
            category = 'academics'
        elif 'admission' in url.lower():
            category = 'admission'
        elif 'research' in url.lower():
            category = 'research'
        
        # Check if already exists by title
        existing = db.execute(text("""
            SELECT id FROM knowledge_documents 
            WHERE title = :title
        """), {"title": title}).fetchone()
        
        if existing:
            print(f"Skipping {title} (already exists)")
            continue
        
        try:
            # Create knowledge document
            doc_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO knowledge_documents (id, title, category, storage_path, processing_status, processed_at)
                VALUES (:id, :title, :category, :storage_path, 'completed', NOW())
            """), {
                "id": doc_id,
                "title": title,
                "category": category,
                "storage_path": url
            })
            
            # Chunk content (max 400 words per chunk)
            words = content.split()
            chunk_size = 400
            page_chunks = 0
            
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i:i + chunk_size]
                chunk_content = ' '.join(chunk_words)
                
                # Generate embedding
                embedding = embedder.embed_text(chunk_content)
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                
                # Insert chunk
                chunk_id = str(uuid.uuid4())
                db.execute(text("""
                    INSERT INTO document_chunks (id, source_id, content, metadata, embedding, created_at)
                    VALUES (:id, :source_id, :content, :metadata::jsonb, :embedding::vector, NOW())
                """), {
                    "id": chunk_id,
                    "source_id": doc_id,
                    "content": chunk_content,
                    "metadata": json.dumps({
                        "title": title,
                        "url": url,
                        "category": category,
                        "chunk_index": i // chunk_size,
                        "word_count": len(chunk_words)
                    }),
                    "embedding": embedding_str
                })
                page_chunks += 1
                total_chunks += 1
            
            db.commit()
            ingested += 1
            print(f"✓ Ingested: {title} ({category}) - {page_chunks} chunks")
            
        except Exception as e:
            print(f"✗ Error ingesting {title}: {e}")
            db.rollback()
            continue
    
    print(f"\n=== Summary ===")
    print(f"Ingested {ingested} new pages with {total_chunks} chunks")
    
    # Show totals
    result = db.execute(text("SELECT COUNT(*) FROM knowledge_documents"))
    print(f"Total knowledge_documents: {result.scalar()}")
    
    result = db.execute(text("SELECT COUNT(*) FROM document_chunks"))
    print(f"Total document_chunks: {result.scalar()}")


if __name__ == "__main__":
    ingest_cs_website()
