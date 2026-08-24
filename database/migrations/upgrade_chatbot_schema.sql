-- Migration: Chatbot Intelligence Upgrade Schema Extensions
-- Description: Add tables for faculty information, research areas, news, events, 
--              web scraper tracking, and enhanced feedback capabilities
-- Requirements: 27, 28, 22
-- Date: 2025-01-XX
-- Dependencies: Requires base schema.sql with source_records and pgvector extension

BEGIN;

-- ==============================================================================
-- Faculty Information Tables
-- ==============================================================================

-- Faculty Members
-- Stores faculty profile information extracted from department website
CREATE TABLE IF NOT EXISTS faculty_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    full_name TEXT NOT NULL,
    title TEXT NOT NULL,  -- Professor, Associate Professor, Assistant Professor, etc.
    email TEXT UNIQUE,
    phone TEXT,
    office_location TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE faculty_members IS 'Faculty profile information scraped from cs.qau.edu.pk';
COMMENT ON COLUMN faculty_members.title IS 'Academic title/rank such as Professor, Associate Professor, Assistant Professor';
COMMENT ON COLUMN faculty_members.source_id IS 'References the source_records entry for the faculty page';

-- Indexes for faculty members
CREATE INDEX IF NOT EXISTS idx_faculty_email ON faculty_members(email);
CREATE INDEX IF NOT EXISTS idx_faculty_name_gin ON faculty_members USING gin(to_tsvector('english', full_name));
CREATE INDEX IF NOT EXISTS idx_faculty_source ON faculty_members(source_id);

-- Faculty Research Interests (free text)
-- Stores research interests as extracted text from faculty pages
CREATE TABLE IF NOT EXISTS faculty_research_interests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    faculty_id UUID NOT NULL REFERENCES faculty_members(id) ON DELETE CASCADE,
    interest_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE faculty_research_interests IS 'Free-text research interests extracted from faculty profiles';

-- Index for text search on research interests
CREATE INDEX IF NOT EXISTS idx_faculty_interests_gin ON faculty_research_interests USING gin(to_tsvector('english', interest_text));
CREATE INDEX IF NOT EXISTS idx_faculty_interests_faculty ON faculty_research_interests(faculty_id);

-- Research Areas (structured)
-- Normalized research areas for organization-wide categorization
CREATE TABLE IF NOT EXISTS research_areas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE research_areas IS 'Structured research areas/domains for the department (e.g., AI, Networks, HCI)';

-- Faculty to Research Areas (many-to-many)
-- Links faculty members to structured research areas
CREATE TABLE IF NOT EXISTS faculty_research_areas (
    faculty_id UUID NOT NULL REFERENCES faculty_members(id) ON DELETE CASCADE,
    research_area_id UUID NOT NULL REFERENCES research_areas(id) ON DELETE CASCADE,
    PRIMARY KEY (faculty_id, research_area_id)
);

COMMENT ON TABLE faculty_research_areas IS 'Many-to-many relationship between faculty and structured research areas';

CREATE INDEX IF NOT EXISTS idx_faculty_research_areas_faculty ON faculty_research_areas(faculty_id);
CREATE INDEX IF NOT EXISTS idx_faculty_research_areas_area ON faculty_research_areas(research_area_id);

-- ==============================================================================
-- News and Events Tables
-- ==============================================================================

-- News Articles
-- Department news and announcements with time-sensitivity
CREATE TABLE IF NOT EXISTS news_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    category TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE news_articles IS 'Department news articles and announcements scraped from website';
COMMENT ON COLUMN news_articles.expires_at IS 'Date after which this news is no longer relevant (optional)';
COMMENT ON COLUMN news_articles.category IS 'News category such as admissions, academics, events, general';

-- Indexes for news articles
CREATE INDEX IF NOT EXISTS idx_news_published ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_expires ON news_articles(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_news_content_gin ON news_articles USING gin(to_tsvector('english', title || ' ' || content));
CREATE INDEX IF NOT EXISTS idx_news_category ON news_articles(category);
CREATE INDEX IF NOT EXISTS idx_news_source ON news_articles(source_id);

-- Events
-- Department events with scheduling information
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    description TEXT,
    event_date DATE NOT NULL,
    event_time TIME,
    location TEXT,
    registration_url TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE events IS 'Department events such as seminars, workshops, orientations';
COMMENT ON COLUMN events.expires_at IS 'Date after which this event should no longer be displayed';
COMMENT ON COLUMN events.registration_url IS 'Optional URL for event registration';

-- Indexes for events
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date ASC);
CREATE INDEX IF NOT EXISTS idx_events_expires ON events(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_title_gin ON events USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_id);

-- ==============================================================================
-- Enhanced Knowledge Documents and Chunks
-- ==============================================================================

-- Note: The base schema already has knowledge_documents and document_chunks tables
-- This migration adds indexes and constraints for the enhanced RAG pipeline

-- Additional indexes for knowledge_documents (if not already present)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'knowledge_documents' 
        AND indexname = 'idx_knowledge_type'
    ) THEN
        CREATE INDEX idx_knowledge_type ON knowledge_documents(category);
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'knowledge_documents' 
        AND indexname = 'idx_knowledge_status'
    ) THEN
        CREATE INDEX idx_knowledge_status ON knowledge_documents(processing_status);
    END IF;
END$$;

-- Additional indexes for document_chunks (if not already present)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'document_chunks' 
        AND indexname = 'idx_chunk_content_gin'
    ) THEN
        CREATE INDEX idx_chunk_content_gin ON document_chunks USING gin(to_tsvector('english', content));
    END IF;
END$$;

-- ==============================================================================
-- Web Scraper Tracking Tables
-- ==============================================================================

-- Scraper Run Log
-- Tracks web scraping runs with statistics and error logging
CREATE TABLE IF NOT EXISTS scraper_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    pages_processed INTEGER DEFAULT 0 CHECK (pages_processed >= 0),
    pages_changed INTEGER DEFAULT 0 CHECK (pages_changed >= 0),
    pages_new INTEGER DEFAULT 0 CHECK (pages_new >= 0),
    errors_encountered INTEGER DEFAULT 0 CHECK (errors_encountered >= 0),
    error_log TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (completed_at IS NULL OR completed_at >= started_at),
    CHECK (duration_seconds IS NULL OR duration_seconds >= 0)
);

COMMENT ON TABLE scraper_runs IS 'Audit log for web scraper execution with statistics';
COMMENT ON COLUMN scraper_runs.pages_processed IS 'Total number of pages processed in this run';
COMMENT ON COLUMN scraper_runs.pages_changed IS 'Number of pages with content changes detected';
COMMENT ON COLUMN scraper_runs.pages_new IS 'Number of newly discovered pages';
COMMENT ON COLUMN scraper_runs.errors_encountered IS 'Count of errors during scraping';
COMMENT ON COLUMN scraper_runs.error_log IS 'Detailed error messages and stack traces';

-- Index for scraper runs
CREATE INDEX IF NOT EXISTS idx_scraper_runs_started ON scraper_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraper_runs_status ON scraper_runs(status);

-- ==============================================================================
-- Enhanced Chat Feedback Table
-- ==============================================================================

-- Chat Feedback
-- Allows users to rate and provide feedback on chatbot responses
CREATE TABLE IF NOT EXISTS chat_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE chat_feedback IS 'User feedback on chatbot responses for quality tracking';
COMMENT ON COLUMN chat_feedback.rating IS 'Rating from 1 (poor) to 5 (excellent)';

-- Indexes for feedback
CREATE INDEX IF NOT EXISTS idx_feedback_message ON chat_feedback(message_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON chat_feedback(rating);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON chat_feedback(created_at DESC);

-- ==============================================================================
-- Data Validation and Constraints
-- ==============================================================================

-- Ensure pgvector extension is available (required for embeddings)
-- This should already be present from base schema, but we verify
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'pgvector extension is required but not installed. Please install pgvector before running this migration.';
    END IF;
END$$;

-- Verify base tables exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'source_records') THEN
        RAISE EXCEPTION 'Base table source_records not found. Please run schema.sql first.';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
        RAISE EXCEPTION 'Base table chat_messages not found. Please run schema.sql first.';
    END IF;
END$$;

-- ==============================================================================
-- Migration Completion
-- ==============================================================================

-- Insert migration record (if you have a migrations tracking table)
-- This is optional and depends on your migration tracking strategy

COMMIT;

-- ==============================================================================
-- Verification Queries (to run after migration)
-- ==============================================================================

-- Check all new tables were created
SELECT 
    table_name, 
    (SELECT count(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
AND table_name IN (
    'faculty_members',
    'faculty_research_interests', 
    'research_areas',
    'faculty_research_areas',
    'news_articles',
    'events',
    'scraper_runs',
    'chat_feedback'
)
ORDER BY table_name;

-- Check indexes were created
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN (
    'faculty_members',
    'faculty_research_interests',
    'research_areas', 
    'faculty_research_areas',
    'news_articles',
    'events',
    'scraper_runs',
    'chat_feedback'
)
ORDER BY tablename, indexname;
