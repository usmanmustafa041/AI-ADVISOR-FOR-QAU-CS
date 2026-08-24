"""Storage module for web scraper data.

This module provides database storage functionality for scraped content from
cs.qau.edu.pk. It handles storing faculty information, news articles, events,
and maintaining source_records for traceability and incremental updates.

Requirements: 1, 26
"""

import hashlib
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


class ScraperStorage:
    """Database storage layer for scraped web content.
    
    Provides methods to store faculty, news, events, and manage source records
    with checksum-based incremental update detection and transaction support.
    
    Attributes:
        db: SQLAlchemy database session
    """
    
    def __init__(self, db: Session):
        """Initialize scraper storage with database session.
        
        Args:
            db: SQLAlchemy Session for database operations
        """
        self.db = db
    
    def store_faculty(self, data: dict[str, Any], source_url: str) -> UUID:
        """Store faculty member information in database.
        
        Creates or updates faculty_members record and associated research interests.
        Links to source_records for traceability.
        
        Args:
            data: Dictionary containing faculty information with keys:
                - full_name: str (required)
                - title: str (required, e.g., "Professor", "Associate Professor")
                - email: str (optional)
                - phone: str (optional)
                - office_location: str (optional)
                - research_interests: list[str] (optional)
                - checksum: str (required, SHA-256 hash for change detection)
            source_url: URL of the source page
        
        Returns:
            UUID of the created/updated faculty_members record
        
        Raises:
            KeyError: If required fields are missing from data
            SQLAlchemyError: If database operation fails
        
        Requirements: 1.6, 26
        """
        # Create or update source record
        source_id = self.create_or_update_source(
            url=source_url,
            title=f"Faculty Profile: {data['full_name']}",
            checksum=data['checksum'],
            category='faculty'
        )
        
        # Check if faculty member already exists
        existing = self.db.execute(
            text("""
                SELECT id FROM faculty_members 
                WHERE source_id = :source_id
            """),
            {"source_id": source_id}
        ).fetchone()
        
        if existing:
            # Update existing faculty member
            self.db.execute(
                text("""
                    UPDATE faculty_members
                    SET full_name = :full_name,
                        title = :title,
                        email = :email,
                        phone = :phone,
                        office_location = :office_location,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "id": existing[0],
                    "full_name": data['full_name'],
                    "title": data['title'],
                    "email": data.get('email'),
                    "phone": data.get('phone'),
                    "office_location": data.get('office_location')
                }
            )
            faculty_id = existing[0]
            
            # Delete old research interests
            self.db.execute(
                text("""
                    DELETE FROM faculty_research_interests
                    WHERE faculty_id = :faculty_id
                """),
                {"faculty_id": faculty_id}
            )
        else:
            # Insert new faculty member
            result = self.db.execute(
                text("""
                    INSERT INTO faculty_members (
                        source_id, full_name, title, email, phone, office_location
                    ) VALUES (
                        :source_id, :full_name, :title, :email, :phone, :office_location
                    ) RETURNING id
                """),
                {
                    "source_id": source_id,
                    "full_name": data['full_name'],
                    "title": data['title'],
                    "email": data.get('email'),
                    "phone": data.get('phone'),
                    "office_location": data.get('office_location')
                }
            )
            faculty_id = result.fetchone()[0]
        
        # Insert research interests
        if data.get('research_interests'):
            for interest in data['research_interests']:
                self.db.execute(
                    text("""
                        INSERT INTO faculty_research_interests (
                            faculty_id, interest_text
                        ) VALUES (
                            :faculty_id, :interest_text
                        )
                    """),
                    {
                        "faculty_id": faculty_id,
                        "interest_text": interest
                    }
                )
        
        self.db.commit()
        return faculty_id
    
    def store_news(self, data: dict[str, Any], source_url: str) -> UUID:
        """Store news article in database.
        
        Creates or updates news_articles record linked to source_records.
        
        Args:
            data: Dictionary containing news information with keys:
                - title: str (required)
                - content: str (required)
                - published_at: datetime (required)
                - category: str (optional)
                - expires_at: datetime (optional)
                - checksum: str (required, SHA-256 hash for change detection)
            source_url: URL of the source page
        
        Returns:
            UUID of the created/updated news_articles record
        
        Raises:
            KeyError: If required fields are missing from data
            SQLAlchemyError: If database operation fails
        
        Requirements: 1.8, 26
        """
        # Create or update source record
        source_id = self.create_or_update_source(
            url=source_url,
            title=data['title'],
            checksum=data['checksum'],
            category='news'
        )
        
        # Check if news article already exists
        existing = self.db.execute(
            text("""
                SELECT id FROM news_articles 
                WHERE source_id = :source_id
            """),
            {"source_id": source_id}
        ).fetchone()
        
        if existing:
            # Update existing news article
            self.db.execute(
                text("""
                    UPDATE news_articles
                    SET title = :title,
                        content = :content,
                        published_at = :published_at,
                        category = :category,
                        expires_at = :expires_at
                    WHERE id = :id
                """),
                {
                    "id": existing[0],
                    "title": data['title'],
                    "content": data['content'],
                    "published_at": data['published_at'],
                    "category": data.get('category'),
                    "expires_at": data.get('expires_at')
                }
            )
            news_id = existing[0]
        else:
            # Insert new news article
            result = self.db.execute(
                text("""
                    INSERT INTO news_articles (
                        source_id, title, content, published_at, category, expires_at
                    ) VALUES (
                        :source_id, :title, :content, :published_at, :category, :expires_at
                    ) RETURNING id
                """),
                {
                    "source_id": source_id,
                    "title": data['title'],
                    "content": data['content'],
                    "published_at": data['published_at'],
                    "category": data.get('category'),
                    "expires_at": data.get('expires_at')
                }
            )
            news_id = result.fetchone()[0]
        
        self.db.commit()
        return news_id
    
    def store_event(self, data: dict[str, Any], source_url: str) -> UUID:
        """Store event information in database.
        
        Creates or updates events record linked to source_records.
        
        Args:
            data: Dictionary containing event information with keys:
                - title: str (required)
                - description: str (optional)
                - event_date: date (required)
                - event_time: time (optional)
                - location: str (optional)
                - registration_url: str (optional)
                - expires_at: datetime (optional)
                - checksum: str (required, SHA-256 hash for change detection)
            source_url: URL of the source page
        
        Returns:
            UUID of the created/updated events record
        
        Raises:
            KeyError: If required fields are missing from data
            SQLAlchemyError: If database operation fails
        
        Requirements: 1.8, 26
        """
        # Create or update source record
        source_id = self.create_or_update_source(
            url=source_url,
            title=data['title'],
            checksum=data['checksum'],
            category='event'
        )
        
        # Check if event already exists
        existing = self.db.execute(
            text("""
                SELECT id FROM events 
                WHERE source_id = :source_id
            """),
            {"source_id": source_id}
        ).fetchone()
        
        if existing:
            # Update existing event
            self.db.execute(
                text("""
                    UPDATE events
                    SET title = :title,
                        description = :description,
                        event_date = :event_date,
                        event_time = :event_time,
                        location = :location,
                        registration_url = :registration_url,
                        expires_at = :expires_at
                    WHERE id = :id
                """),
                {
                    "id": existing[0],
                    "title": data['title'],
                    "description": data.get('description'),
                    "event_date": data['event_date'],
                    "event_time": data.get('event_time'),
                    "location": data.get('location'),
                    "registration_url": data.get('registration_url'),
                    "expires_at": data.get('expires_at')
                }
            )
            event_id = existing[0]
        else:
            # Insert new event
            result = self.db.execute(
                text("""
                    INSERT INTO events (
                        source_id, title, description, event_date, 
                        event_time, location, registration_url, expires_at
                    ) VALUES (
                        :source_id, :title, :description, :event_date,
                        :event_time, :location, :registration_url, :expires_at
                    ) RETURNING id
                """),
                {
                    "source_id": source_id,
                    "title": data['title'],
                    "description": data.get('description'),
                    "event_date": data['event_date'],
                    "event_time": data.get('event_time'),
                    "location": data.get('location'),
                    "registration_url": data.get('registration_url'),
                    "expires_at": data.get('expires_at')
                }
            )
            event_id = result.fetchone()[0]
        
        self.db.commit()
        return event_id
    
    def create_or_update_source(
        self,
        url: str,
        title: str,
        checksum: str,
        category: str
    ) -> UUID:
        """Create or update source_records entry for a scraped page.
        
        Implements incremental update logic: if checksum matches existing record,
        no update is performed. If checksum differs, the record is updated and
        updated_at timestamp is set.
        
        Args:
            url: Source URL of the content
            title: Title of the source document
            checksum: SHA-256 checksum of content for change detection
            category: Category of content (e.g., 'faculty', 'news', 'event')
        
        Returns:
            UUID of the created/updated source_records entry
        
        Raises:
            SQLAlchemyError: If database operation fails
        
        Requirements: 1.3, 1.4, 26
        """
        # Check if source already exists
        existing = self.db.execute(
            text("""
                SELECT id, checksum_sha256 FROM source_records
                WHERE source_url = :url
            """),
            {"url": url}
        ).fetchone()
        
        if existing:
            source_id, existing_checksum = existing
            
            # Only update if content changed (checksum differs)
            if existing_checksum != checksum:
                self.db.execute(
                    text("""
                        UPDATE source_records
                        SET checksum_sha256 = :checksum,
                            title = :title,
                            updated_at = NOW(),
                            verification_status = 'referenced',
                            is_time_sensitive = :is_time_sensitive
                        WHERE id = :id
                    """),
                    {
                        "id": source_id,
                        "checksum": checksum,
                        "title": title,
                        "is_time_sensitive": category in ('news', 'event')
                    }
                )
                self.db.commit()
        else:
            # Create new source record
            result = self.db.execute(
                text("""
                    INSERT INTO source_records (
                        source_code, title, category, authority, 
                        source_url, checksum_sha256, verification_status, is_time_sensitive
                    ) VALUES (
                        :source_code, :title, :category, :authority,
                        :url, :checksum, 'referenced', :is_time_sensitive
                    ) RETURNING id
                """),
                {
                    "source_code": self._generate_source_code(url, category),
                    "title": title,
                    "category": category,
                    "authority": "cs.qau.edu.pk",
                    "url": url,
                    "checksum": checksum,
                    "is_time_sensitive": category in ('news', 'event')
                }
            )
            source_id = result.fetchone()[0]
            self.db.commit()
        
        return source_id
    
    def log_scraper_run(self, stats: dict[str, Any]) -> UUID:
        """Log scraper run statistics to database.
        
        Records execution metrics for monitoring and debugging scraper performance.
        
        Args:
            stats: Dictionary containing scraper run statistics with keys:
                - started_at: datetime (required)
                - completed_at: datetime (optional, for in-progress runs)
                - duration_seconds: int (optional)
                - pages_processed: int (default: 0)
                - pages_changed: int (default: 0)
                - pages_new: int (default: 0)
                - errors_encountered: int (default: 0)
                - error_log: str (optional)
                - status: str (required, one of: 'running', 'completed', 'failed')
        
        Returns:
            UUID of the created scraper_runs record
        
        Raises:
            KeyError: If required fields are missing from stats
            SQLAlchemyError: If database operation fails
        
        Requirements: 1.9, 26.5
        """
        result = self.db.execute(
            text("""
                INSERT INTO scraper_runs (
                    started_at, completed_at, duration_seconds,
                    pages_processed, pages_changed, pages_new,
                    errors_encountered, error_log, status
                ) VALUES (
                    :started_at, :completed_at, :duration_seconds,
                    :pages_processed, :pages_changed, :pages_new,
                    :errors_encountered, :error_log, :status
                ) RETURNING id
            """),
            {
                "started_at": stats['started_at'],
                "completed_at": stats.get('completed_at'),
                "duration_seconds": stats.get('duration_seconds'),
                "pages_processed": stats.get('pages_processed', 0),
                "pages_changed": stats.get('pages_changed', 0),
                "pages_new": stats.get('pages_new', 0),
                "errors_encountered": stats.get('errors_encountered', 0),
                "error_log": stats.get('error_log'),
                "status": stats['status']
            }
        )
        
        run_id = result.fetchone()[0]
        self.db.commit()
        return run_id
    
    def _generate_source_code(self, url: str, category: str) -> str:
        """Generate unique source code for a URL.
        
        Creates a short, human-readable identifier for the source record.
        
        Args:
            url: Source URL
            category: Content category (e.g., 'faculty', 'news', 'event')
        
        Returns:
            Source code in format: CATEGORY_HASH (e.g., 'FACULTY_A3F2')
        """
        # Generate short hash from URL
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:8].upper()
        return f"{category.upper()}_{url_hash}"
