"""
Ingest scraped CS website directly into document_chunks.
"""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import get_db
from app.rag.embedder import get_embedder

def ingest_cs_website_direct():
    """Ingest all scraped CS website pages directly as chunks."""
    
    # Load scraped data
    scraped_file = Path(__file__).parent.parent.parent / "academic-data/scraped/cs_website_full.json"
    
    with open(scraped_file, 'r', encoding='utf-8') as f:
        pages = json.load(f)
    
    print(f"Loaded {len(pages)} pages from CS website")
    
    # Get database and embedder
    db = next(get_db())
    embedder = get_embedder()
    
    # Get or create a source record for CS website
    source_result = db.execute(text("""
        SELECT id FROM source_records WHERE source_code = 'SRC-PACK-001'
    """)).fetchone()
    
    if not source_result:
        print("Error: Source record SRC-PACK-001 not found")
        return
    
    source_id = source_result[0]
    print(f"Using source record SRC-PACK-001: {source_id}")
    
    ingested = 0
    total_chunks = 0
    
    for page in pages:
        url = page['url']
        title = page['title']
        content = page['content']
        word_count = page['word_count']
        
        # Skip empty or very short content
        if word_count < 30:
            print(f"Skipping {title} (too short: {word_count} words)")
            continue
        
        # Determine category from URL
        category = 'general'
        if 'faculty' in url.lower():
            category = 'faculty'
        elif 'academics' in url.lower() or 'programme' in url.lower() or 'bs.html' in url.lower() or 'mphil' in url.lower() or 'phd' in url.lower() or 'ms-' in url.lower():
            category = 'academics'
        elif 'admission' in url.lower():
            category = 'admission'
        elif 'research' in url.lower():
            category = 'research'
        elif url == 'https://cs.qau.edu.pk/':
            category = 'general'
        
        # Check if already exists by checking content substring
        existing = db.execute(text("""
            SELECT COUNT(*) FROM document_chunks 
            WHERE metadata->>'url' = :url
        """), {"url": url}).scalar()
        
        if existing > 0:
            print(f"Skipping {title} (already exists - {existing} chunks)")
            continue
        
        try:
            # Chunk content (max 350 words per chunk for better retrieval)
            words = content.split()
            chunk_size = 350
            page_chunks = 0
            
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i:i + chunk_size]
                chunk_content = ' '.join(chunk_words)
                
                # Skip very short chunks
                if len(chunk_words) < 30:
                    continue
                
                # Generate embedding
                embedding = embedder.embed_text(chunk_content)
                
                # Insert chunk
                chunk_id = str(uuid.uuid4())
                db.execute(text("""
                    INSERT INTO document_chunks (id, source_id, content, metadata, embedding, created_at)
                    VALUES (:id, :source_id, :content, CAST(:metadata AS jsonb), CAST(:embedding AS vector), NOW())
                """), {
                    "id": chunk_id,
                    "source_id": source_id,
                    "content": chunk_content,
                    "metadata": json.dumps({
                        "title": title,
                        "url": url,
                        "category": category,
                        "chunk_index": i // chunk_size,
                        "word_count": len(chunk_words),
                        "source": "CS Website Scraper"
                    }),
                    "embedding": str(embedding)
                })
                page_chunks += 1
                total_chunks += 1
            
            if page_chunks > 0:
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
    result = db.execute(text("SELECT COUNT(*) FROM document_chunks"))
    print(f"Total document_chunks: {result.scalar()}")
    
    # Show category breakdown
    result = db.execute(text("""
        SELECT metadata->>'category' as cat, COUNT(*) 
        FROM document_chunks 
        WHERE metadata->>'source' = 'CS Website Scraper'
        GROUP BY cat
        ORDER BY COUNT(*) DESC
    """))
    print(f"\n=== CS Website Chunks by Category ===")
    for row in result:
        print(f"{row[0]}: {row[1]} chunks")


if __name__ == "__main__":
    ingest_cs_website_direct()
