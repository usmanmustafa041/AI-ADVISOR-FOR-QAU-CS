-- ============================================================================
-- MISSING TABLES FOR ADMIN PANEL
-- Creates course_prerequisites, knowledge_documents, and related tables
-- ============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Source Records Table (for tracking data sources)
CREATE TABLE IF NOT EXISTS source_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_code VARCHAR(100) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    verification_status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (verification_status IN ('pending', 'verified', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_records_status ON source_records(verification_status);
CREATE INDEX IF NOT EXISTS idx_source_records_code ON source_records(source_code);

-- Curriculum Schemes Table
CREATE TABLE IF NOT EXISTS curriculum_schemes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    program_id UUID REFERENCES programs(id) ON DELETE RESTRICT,
    effective_from DATE NOT NULL,
    effective_to DATE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_curriculum_schemes_active ON curriculum_schemes(is_active);
CREATE INDEX IF NOT EXISTS idx_curriculum_schemes_program ON curriculum_schemes(program_id);

-- Course Prerequisites Table
CREATE TABLE IF NOT EXISTS course_prerequisites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id UUID NOT NULL REFERENCES curriculum_schemes(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    prerequisite_course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    relation_type VARCHAR(20) NOT NULL DEFAULT 'prerequisite' 
        CHECK (relation_type IN ('prerequisite', 'corequisite')),
    minimum_grade VARCHAR(5),
    waiver_condition TEXT,
    source_id UUID REFERENCES source_records(id) ON DELETE SET NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (curriculum_id, course_id, prerequisite_course_id)
);

CREATE INDEX IF NOT EXISTS idx_course_prerequisites_course ON course_prerequisites(course_id);
CREATE INDEX IF NOT EXISTS idx_course_prerequisites_prereq ON course_prerequisites(prerequisite_course_id);
CREATE INDEX IF NOT EXISTS idx_course_prerequisites_curriculum ON course_prerequisites(curriculum_id);
CREATE INDEX IF NOT EXISTS idx_course_prerequisites_verified ON course_prerequisites(verified);

-- Knowledge Documents Table
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    mime_type VARCHAR(100) DEFAULT 'text/plain',
    storage_path TEXT,
    processing_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processing', 'ready', 'failed')),
    processing_error TEXT,
    processed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_status ON knowledge_documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_knowledge_documents_category ON knowledge_documents(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_documents_source ON knowledge_documents(source_id);

-- Document Chunks Table (for RAG/embeddings)
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    section_title TEXT,
    token_count INTEGER CHECK (token_count IS NULL OR token_count > 0),
    embedding VECTOR(384),
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata ON document_chunks USING GIN (metadata);

-- Note: embedding index is created separately if pgvector is available
-- CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);

-- Insert default source record for admin-entered data
INSERT INTO source_records (source_code, title, verification_status)
VALUES 
    ('admin-manual', 'Manually Entered by Admin', 'verified'),
    ('system-default', 'System Default Data', 'verified')
ON CONFLICT (source_code) DO NOTHING;

-- Insert default curriculum scheme
INSERT INTO curriculum_schemes (name, effective_from, description, is_active)
VALUES 
    ('Fall 2025 onward', '2025-09-01', 'Current curriculum scheme effective from Fall 2025', TRUE)
ON CONFLICT (name) DO NOTHING;

-- Auto-update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
DROP TRIGGER IF EXISTS trigger_source_records_updated_at ON source_records;
CREATE TRIGGER trigger_source_records_updated_at
    BEFORE UPDATE ON source_records
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_curriculum_schemes_updated_at ON curriculum_schemes;
CREATE TRIGGER trigger_curriculum_schemes_updated_at
    BEFORE UPDATE ON curriculum_schemes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_course_prerequisites_updated_at ON course_prerequisites;
CREATE TRIGGER trigger_course_prerequisites_updated_at
    BEFORE UPDATE ON course_prerequisites
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_knowledge_documents_updated_at ON knowledge_documents;
CREATE TRIGGER trigger_knowledge_documents_updated_at
    BEFORE UPDATE ON knowledge_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Verification
DO $$
DECLARE
    source_count INTEGER;
    curriculum_count INTEGER;
    prereq_count INTEGER;
    knowledge_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO source_count FROM source_records;
    SELECT COUNT(*) INTO curriculum_count FROM curriculum_schemes;
    SELECT COUNT(*) INTO prereq_count FROM course_prerequisites;
    SELECT COUNT(*) INTO knowledge_count FROM knowledge_documents;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ MISSING TABLES CREATED';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Tables created/verified:';
    RAISE NOTICE '- source_records (% records)', source_count;
    RAISE NOTICE '- curriculum_schemes (% records)', curriculum_count;
    RAISE NOTICE '- course_prerequisites (% records)', prereq_count;
    RAISE NOTICE '- knowledge_documents (% records)', knowledge_count;
    RAISE NOTICE '- document_chunks';
    RAISE NOTICE '';
    RAISE NOTICE 'Default data inserted:';
    RAISE NOTICE '- Source: admin-manual';
    RAISE NOTICE '- Source: system-default';
    RAISE NOTICE '- Curriculum: Fall 2025 onward';
    RAISE NOTICE '========================================';
END $$;
