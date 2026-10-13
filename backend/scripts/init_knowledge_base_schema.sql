-- ============================================================================
-- ADMIN CMS KNOWLEDGE BASE SCHEMA (NON-DESTRUCTIVE / ZERO-DATA-LOSS)
-- ============================================================================
-- This script creates the knowledge_base table and related structures
-- using ONLY safe, additive operations (IF NOT EXISTS clauses).
--
-- SAFETY GUARANTEES:
-- 1. No DROP statements
-- 2. No TRUNCATE statements
-- 3. All CREATE use IF NOT EXISTS
-- 4. All ALTER use IF NOT EXISTS (PostgreSQL 9.6+)
-- 5. Existing data is NEVER deleted
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- MAIN KNOWLEDGE BASE TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS knowledge_base (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Unique identifier for upsert operations
    sub_key VARCHAR(100) UNIQUE NOT NULL,
    
    -- Category classification
    category VARCHAR(50) NOT NULL CHECK (category IN (
        'scheme',
        'admission',
        'fee_structure',
        'timetable',
        'course',
        'policy',
        'general_notice',
        'faq',
        'contact',
        'other'
    )),
    
    -- Content fields
    title VARCHAR(300) NOT NULL,
    content_markdown TEXT NOT NULL,
    structured_data JSONB DEFAULT '{}'::jsonb,
    
    -- Metadata
    source_url TEXT,
    source_document TEXT,
    language VARCHAR(10) DEFAULT 'en',
    
    -- Status flags
    is_active BOOLEAN DEFAULT true NOT NULL,
    is_verified BOOLEAN DEFAULT false NOT NULL,
    priority INTEGER DEFAULT 100 NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by UUID,
    updated_by UUID,
    
    -- Full-text search
    search_vector tsvector
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Unique index on sub_key (already created by UNIQUE constraint, but explicit for clarity)
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_base_sub_key 
    ON knowledge_base(sub_key);

-- Index for category filtering
CREATE INDEX IF NOT EXISTS idx_knowledge_base_category 
    ON knowledge_base(category);

-- Index for active records
CREATE INDEX IF NOT EXISTS idx_knowledge_base_active 
    ON knowledge_base(is_active) WHERE is_active = true;

-- Combined index for common queries
CREATE INDEX IF NOT EXISTS idx_knowledge_base_category_active 
    ON knowledge_base(category, is_active) WHERE is_active = true;

-- Index for priority sorting
CREATE INDEX IF NOT EXISTS idx_knowledge_base_priority 
    ON knowledge_base(priority DESC, updated_at DESC);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_knowledge_base_search 
    ON knowledge_base USING GIN(search_vector);

-- JSONB index for structured data queries
CREATE INDEX IF NOT EXISTS idx_knowledge_base_structured_data 
    ON knowledge_base USING GIN(structured_data);

-- ============================================================================
-- AUDIT TABLE FOR KNOWLEDGE BASE CHANGES
-- ============================================================================

CREATE TABLE IF NOT EXISTS knowledge_base_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_base_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE', 'RESTORE')),
    changed_by UUID,
    changed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    before_data JSONB,
    after_data JSONB,
    change_reason TEXT
);

-- Index for audit queries
CREATE INDEX IF NOT EXISTS idx_knowledge_base_audit_kb_id 
    ON knowledge_base_audit(knowledge_base_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_base_audit_changed_at 
    ON knowledge_base_audit(changed_at DESC);

-- ============================================================================
-- TRIGGER FOR AUTOMATIC SEARCH VECTOR UPDATE
-- ============================================================================

-- Function to update search vector
CREATE OR REPLACE FUNCTION knowledge_base_search_vector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.content_markdown, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.sub_key, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger (DROP IF EXISTS is safe as it's just recreating)
DROP TRIGGER IF EXISTS trigger_knowledge_base_search_vector_update 
    ON knowledge_base;

CREATE TRIGGER trigger_knowledge_base_search_vector_update
    BEFORE INSERT OR UPDATE ON knowledge_base
    FOR EACH ROW
    EXECUTE FUNCTION knowledge_base_search_vector_update();

-- ============================================================================
-- TRIGGER FOR AUTOMATIC TIMESTAMP UPDATE
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_knowledge_base_updated_at 
    ON knowledge_base;

CREATE TRIGGER trigger_knowledge_base_updated_at
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- TRIGGER FOR AUDIT LOGGING
-- ============================================================================

-- Function to log changes to audit table
CREATE OR REPLACE FUNCTION knowledge_base_audit_log()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO knowledge_base_audit (knowledge_base_id, action, after_data)
        VALUES (NEW.id, 'INSERT', row_to_json(NEW)::jsonb);
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO knowledge_base_audit (knowledge_base_id, action, before_data, after_data)
        VALUES (NEW.id, 'UPDATE', row_to_json(OLD)::jsonb, row_to_json(NEW)::jsonb);
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO knowledge_base_audit (knowledge_base_id, action, before_data)
        VALUES (OLD.id, 'DELETE', row_to_json(OLD)::jsonb);
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_knowledge_base_audit_log 
    ON knowledge_base;

CREATE TRIGGER trigger_knowledge_base_audit_log
    AFTER INSERT OR UPDATE OR DELETE ON knowledge_base
    FOR EACH ROW
    EXECUTE FUNCTION knowledge_base_audit_log();

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- View for active knowledge entries
CREATE OR REPLACE VIEW v_active_knowledge AS
SELECT 
    id,
    sub_key,
    category,
    title,
    content_markdown,
    structured_data,
    priority,
    updated_at
FROM knowledge_base
WHERE is_active = true
ORDER BY priority DESC, updated_at DESC;

-- View for scheme entries
CREATE OR REPLACE VIEW v_scheme_knowledge AS
SELECT 
    id,
    sub_key,
    title,
    content_markdown,
    structured_data,
    priority,
    updated_at
FROM knowledge_base
WHERE is_active = true AND category = 'scheme'
ORDER BY 
    CASE 
        WHEN sub_key LIKE '%2025%' THEN 1
        WHEN sub_key LIKE '%2023%' THEN 2
        WHEN sub_key LIKE '%2021%' THEN 3
        ELSE 4
    END,
    priority DESC;

-- View for admission entries
CREATE OR REPLACE VIEW v_admission_knowledge AS
SELECT 
    id,
    sub_key,
    title,
    content_markdown,
    structured_data,
    priority,
    updated_at
FROM knowledge_base
WHERE is_active = true AND category = 'admission'
ORDER BY updated_at DESC;

-- View for fee structure entries
CREATE OR REPLACE VIEW v_fee_knowledge AS
SELECT 
    id,
    sub_key,
    title,
    content_markdown,
    structured_data,
    priority,
    updated_at
FROM knowledge_base
WHERE is_active = true AND category = 'fee_structure'
ORDER BY updated_at DESC;

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function for safe upsert
CREATE OR REPLACE FUNCTION upsert_knowledge(
    p_sub_key VARCHAR(100),
    p_category VARCHAR(50),
    p_title VARCHAR(300),
    p_content_markdown TEXT,
    p_structured_data JSONB DEFAULT '{}'::jsonb,
    p_source_url TEXT DEFAULT NULL,
    p_priority INTEGER DEFAULT 100
)
RETURNS UUID AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO knowledge_base (
        sub_key,
        category,
        title,
        content_markdown,
        structured_data,
        source_url,
        priority,
        is_active,
        is_verified
    ) VALUES (
        p_sub_key,
        p_category,
        p_title,
        p_content_markdown,
        p_structured_data,
        p_source_url,
        p_priority,
        true,
        true
    )
    ON CONFLICT (sub_key) DO UPDATE SET
        title = EXCLUDED.title,
        content_markdown = EXCLUDED.content_markdown,
        structured_data = EXCLUDED.structured_data,
        source_url = EXCLUDED.source_url,
        priority = EXCLUDED.priority,
        updated_at = NOW()
    RETURNING id INTO v_id;
    
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Function to soft delete (set is_active = false)
CREATE OR REPLACE FUNCTION soft_delete_knowledge(p_sub_key VARCHAR(100))
RETURNS BOOLEAN AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE knowledge_base
    SET is_active = false, updated_at = NOW()
    WHERE sub_key = p_sub_key;
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count > 0;
END;
$$ LANGUAGE plpgsql;

-- Function to restore soft-deleted entry
CREATE OR REPLACE FUNCTION restore_knowledge(p_sub_key VARCHAR(100))
RETURNS BOOLEAN AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE knowledge_base
    SET is_active = true, updated_at = NOW()
    WHERE sub_key = p_sub_key;
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    
    IF v_count > 0 THEN
        INSERT INTO knowledge_base_audit (
            knowledge_base_id,
            action,
            change_reason
        )
        SELECT id, 'RESTORE', 'Restored via restore_knowledge function'
        FROM knowledge_base
        WHERE sub_key = p_sub_key;
    END IF;
    
    RETURN v_count > 0;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PERMISSIONS (OPTIONAL - ADJUST AS NEEDED)
-- ============================================================================

-- Grant permissions to application user (if specific user exists)
-- GRANT SELECT, INSERT, UPDATE ON knowledge_base TO qau_advisor;
-- GRANT SELECT ON knowledge_base_audit TO qau_advisor;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO qau_advisor;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify table creation
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'knowledge_base') THEN
        RAISE NOTICE '✅ knowledge_base table created successfully';
    ELSE
        RAISE EXCEPTION '❌ knowledge_base table creation failed';
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'knowledge_base_audit') THEN
        RAISE NOTICE '✅ knowledge_base_audit table created successfully';
    ELSE
        RAISE EXCEPTION '❌ knowledge_base_audit table creation failed';
    END IF;
END $$;

-- Show table structure
\d knowledge_base
\d knowledge_base_audit

-- Show indexes
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE tablename IN ('knowledge_base', 'knowledge_base_audit')
ORDER BY tablename, indexname;

-- Show triggers
SELECT tgname, tgtype, tgenabled 
FROM pg_trigger 
WHERE tgrelid IN ('knowledge_base'::regclass, 'knowledge_base_audit'::regclass);

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
