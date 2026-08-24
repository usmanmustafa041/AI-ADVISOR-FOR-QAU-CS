#!/usr/bin/env python3
"""
Scraper data ingestion script.

Reads academic-data/scraped/cs_website_full.json and ingests the scraped
content into the database. Detects content type (faculty, news, course, event),
parses content using parser.py, stores in database via ScraperStorage, and
creates knowledge_documents for RAG.

Requirements: 1, 26
"""

import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.database import get_session_factory
from app.scraper.storage import ScraperStorage
from app.scraper.parser import extract_structured_data
from sqlalchemy import text


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content for change detection.
    
    Args:
        content: Text content to hash
        
    Returns:
        Hexadecimal SHA-256 hash string
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def store_knowledge_document(
    db,
    source_id: str,
    category: str,
    title: str,
    storage_path: str
) -> str:
    """Store a knowledge_documents entry for RAG.
    
    Args:
        db: Database session
        source_id: UUID of source_records entry
        category: Type of document (faculty, news, course, general)
        title: Document title
        storage_path: URL or path to document
        
    Returns:
        UUID of created knowledge_documents record
    """
    result = db.execute(
        text("""
            INSERT INTO knowledge_documents (
                source_id, title, category, storage_path, processing_status
            ) VALUES (
                :source_id, :title, :category, :storage_path, 'pending'
            ) RETURNING id
        """),
        {
            "source_id": source_id,
            "title": title,
            "category": category,
            "storage_path": storage_path
        }
    )
    doc_id = result.fetchone()[0]
    db.commit()
    return doc_id


def ingest_faculty_data(storage: ScraperStorage, faculty_list: List[Dict]) -> Dict[str, int]:
    """Ingest faculty data into database.
    
    Args:
        storage: ScraperStorage instance
        faculty_list: List of faculty data dictionaries
        
    Returns:
        Dictionary with statistics (stored, skipped, errors)
    """
    stats = {"stored": 0, "skipped": 0, "errors": 0}
    
    for faculty in faculty_list:
        try:
            # Rollback any previous failed transaction
            storage.db.rollback()
            
            # Skip if missing required fields
            if not faculty.get("name") or not faculty.get("source_url"):
                print(f"  ⚠ Skipping faculty entry - missing name or URL")
                stats["skipped"] += 1
                continue
            
            # Prepare data for storage
            content = f"{faculty.get('name', '')} - {faculty.get('title', '')}. {' '.join(faculty.get('research_interests', []))}"
            checksum = compute_content_hash(content)
            
            faculty_data = {
                "full_name": faculty["name"],
                "title": faculty.get("title", "Faculty Member"),
                "email": faculty.get("email"),
                "phone": faculty.get("phone"),
                "office_location": faculty.get("office_location"),
                "research_interests": faculty.get("research_interests", []),
                "checksum": checksum
            }
            
            # Store faculty member
            faculty_id = storage.store_faculty(faculty_data, faculty["source_url"])
            
            # Create knowledge document for RAG
            source_result = storage.db.execute(
                text("""
                    SELECT source_id FROM faculty_members WHERE id = :faculty_id
                """),
                {"faculty_id": faculty_id}
            ).fetchone()
            
            if source_result:
                doc_content = (
                    f"Faculty: {faculty_data['full_name']}\n"
                    f"Title: {faculty_data['title']}\n"
                )
                if faculty_data.get('email'):
                    doc_content += f"Email: {faculty_data['email']}\n"
                if faculty_data.get('phone'):
                    doc_content += f"Phone: {faculty_data['phone']}\n"
                if faculty_data['research_interests']:
                    doc_content += f"Research Interests: {', '.join(faculty_data['research_interests'])}\n"
                
                store_knowledge_document(
                    storage.db,
                    source_result[0],
                    "faculty",
                    f"Faculty: {faculty_data['full_name']}",
                    faculty["source_url"]
                )
            
            print(f"  ✓ Stored faculty: {faculty['name']}")
            stats["stored"] += 1
            
        except Exception as e:
            print(f"  ✗ Error storing faculty {faculty.get('name', 'unknown')}: {e}")
            stats["errors"] += 1
    
    return stats


def ingest_news_data(storage: ScraperStorage, news_list: List[Dict]) -> Dict[str, int]:
    """Ingest news articles into database.
    
    Args:
        storage: ScraperStorage instance
        news_list: List of news data dictionaries
        
    Returns:
        Dictionary with statistics (stored, skipped, errors)
    """
    stats = {"stored": 0, "skipped": 0, "errors": 0}
    
    for news in news_list:
        try:
            # Skip if missing required fields
            if not news.get("title") or not news.get("source_url"):
                print(f"  ⚠ Skipping news entry - missing title or URL")
                stats["skipped"] += 1
                continue
            
            # Parse date if available
            published_at = datetime.now()
            if news.get("date"):
                try:
                    # Try multiple date formats
                    date_str = news["date"]
                    for fmt in ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"]:
                        try:
                            published_at = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    print(f"  ⚠ Could not parse date '{news.get('date')}': {e}")
            
            # Prepare data for storage
            content = news.get("content", news["title"])
            checksum = compute_content_hash(content)
            
            news_data = {
                "title": news["title"],
                "content": content,
                "published_at": published_at,
                "category": "announcement",
                "checksum": checksum
            }
            
            # Store news article
            news_id = storage.store_news(news_data, news["source_url"])
            
            # Create knowledge document for RAG
            source_result = storage.db.execute(
                text("""
                    SELECT source_id FROM news_articles WHERE id = :news_id
                """),
                {"news_id": news_id}
            ).fetchone()
            
            if source_result:
                doc_content = (
                    f"News: {news_data['title']}\n"
                    f"Date: {news_data['published_at'].strftime('%Y-%m-%d')}\n"
                    f"Content: {news_data['content']}\n"
                )
                
                store_knowledge_document(
                    storage.db,
                    source_result[0],
                    "news",
                    news_data['title'],
                    news["source_url"]
                )
            
            print(f"  ✓ Stored news: {news['title'][:60]}...")
            stats["stored"] += 1
            
        except Exception as e:
            print(f"  ✗ Error storing news {news.get('title', 'unknown')[:40]}: {e}")
            stats["errors"] += 1
    
    return stats


def ingest_general_data(storage: ScraperStorage, db, general_list: List[Dict]) -> Dict[str, int]:
    """Ingest general content as knowledge documents.
    
    Args:
        storage: ScraperStorage instance
        db: Database session
        general_list: List of general content dictionaries
        
    Returns:
        Dictionary with statistics (stored, skipped, errors)
    """
    stats = {"stored": 0, "skipped": 0, "errors": 0}
    
    for item in general_list:
        try:
            # Skip if missing required fields or content too short
            if not item.get("source_url") or not item.get("content"):
                stats["skipped"] += 1
                continue
            
            content = item["content"]
            if len(content.strip()) < 50:  # Skip very short content
                stats["skipped"] += 1
                continue
            
            # Create or update source record
            checksum = compute_content_hash(content)
            source_id = storage.create_or_update_source(
                url=item["source_url"],
                title=item.get("source_title", "General Content"),
                checksum=checksum,
                category="general"
            )
            
            # Create knowledge document
            doc_id = store_knowledge_document(
                db,
                source_id,
                "general",
                item.get("source_title", "General Content"),
                item["source_url"]
            )
            
            print(f"  ✓ Stored general content from: {item['source_url'][:60]}...")
            stats["stored"] += 1
            
        except Exception as e:
            print(f"  ✗ Error storing general content: {e}")
            stats["errors"] += 1
    
    return stats


def main():
    """Main ingestion script."""
    print("=" * 80)
    print("Scraper Data Ingestion Script")
    print("=" * 80)
    
    # Load scraped data
    json_path = Path(__file__).parent.parent.parent / "academic-data" / "scraped" / "cs_website_full.json"
    
    if not json_path.exists():
        print(f"✗ Error: Scraped data file not found at {json_path}")
        sys.exit(1)
    
    print(f"\n1. Loading scraped data from {json_path}...")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            pages = json.load(f)
        print(f"   ✓ Loaded {len(pages)} pages")
    except Exception as e:
        print(f"   ✗ Error loading JSON: {e}")
        sys.exit(1)
    
    # Parse and categorize data
    print("\n2. Parsing and categorizing content...")
    try:
        categorized = extract_structured_data(pages)
        print(f"   ✓ Found {len(categorized['faculty'])} faculty entries")
        print(f"   ✓ Found {len(categorized['news'])} news items")
        print(f"   ✓ Found {len(categorized['courses'])} course entries")
        print(f"   ✓ Found {len(categorized['general'])} general content items")
    except Exception as e:
        print(f"   ✗ Error parsing data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Initialize database connection
    print("\n3. Connecting to database...")
    try:
        session_factory = get_session_factory()
        db = session_factory()
        storage = ScraperStorage(db)
        print("   ✓ Connected to database")
    except Exception as e:
        print(f"   ✗ Error connecting to database: {e}")
        sys.exit(1)
    
    # Track scraper run
    started_at = datetime.now()
    total_stats = {
        "pages_processed": len(pages),
        "pages_changed": 0,
        "pages_new": 0,
        "errors_encountered": 0
    }
    
    # Ingest faculty data
    print("\n4. Ingesting faculty data...")
    faculty_stats = ingest_faculty_data(storage, categorized["faculty"])
    print(f"   Summary: {faculty_stats['stored']} stored, {faculty_stats['skipped']} skipped, {faculty_stats['errors']} errors")
    total_stats["pages_changed"] += faculty_stats["stored"]
    total_stats["errors_encountered"] += faculty_stats["errors"]
    
    # Ingest news data
    print("\n5. Ingesting news data...")
    news_stats = ingest_news_data(storage, categorized["news"])
    print(f"   Summary: {news_stats['stored']} stored, {news_stats['skipped']} skipped, {news_stats['errors']} errors")
    total_stats["pages_changed"] += news_stats["stored"]
    total_stats["errors_encountered"] += news_stats["errors"]
    
    # Ingest general content as knowledge documents
    print("\n6. Ingesting general content...")
    general_stats = ingest_general_data(storage, db, categorized["general"])
    print(f"   Summary: {general_stats['stored']} stored, {general_stats['skipped']} skipped, {general_stats['errors']} errors")
    total_stats["pages_changed"] += general_stats["stored"]
    total_stats["errors_encountered"] += general_stats["errors"]
    
    # Log scraper run
    completed_at = datetime.now()
    duration = (completed_at - started_at).total_seconds()
    
    print("\n7. Logging scraper run...")
    try:
        run_stats = {
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": int(duration),
            "pages_processed": total_stats["pages_processed"],
            "pages_changed": total_stats["pages_changed"],
            "pages_new": total_stats["pages_changed"],  # All are new in first run
            "errors_encountered": total_stats["errors_encountered"],
            "status": "completed" if total_stats["errors_encountered"] == 0 else "completed_with_errors"
        }
        
        run_id = storage.log_scraper_run(run_stats)
        print(f"   ✓ Logged scraper run with ID: {run_id}")
    except Exception as e:
        print(f"   ✗ Error logging scraper run: {e}")
    
    # Close database connection
    db.close()
    
    # Print final summary
    print("\n" + "=" * 80)
    print("INGESTION COMPLETE")
    print("=" * 80)
    print(f"Duration: {duration:.2f} seconds")
    print(f"Pages processed: {total_stats['pages_processed']}")
    print(f"Items stored: {total_stats['pages_changed']}")
    print(f"Errors: {total_stats['errors_encountered']}")
    print()
    print(f"Faculty members: {faculty_stats['stored']}")
    print(f"News articles: {news_stats['stored']}")
    print(f"General documents: {general_stats['stored']}")
    print()
    
    if total_stats["errors_encountered"] > 0:
        print("⚠ Completed with errors. Review output above for details.")
        sys.exit(1)
    else:
        print("✓ All data ingested successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
