BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE source_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_code VARCHAR(30) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    category VARCHAR(60) NOT NULL,
    authority TEXT NOT NULL,
    source_url TEXT,
    local_path TEXT,
    checksum_sha256 CHAR(64),
    effective_from DATE,
    effective_to DATE,
    last_verified_at TIMESTAMPTZ,
    verification_status VARCHAR(20) NOT NULL DEFAULT 'unverified'
        CHECK (verification_status IN ('unverified', 'referenced', 'verified', 'expired', 'rejected')),
    is_time_sensitive BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)
);

CREATE TABLE programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(20) NOT NULL UNIQUE,
    name TEXT NOT NULL,
    level VARCHAR(20) NOT NULL CHECK (level IN ('BS', 'MS', 'MPhil', 'PhD')),
    study_mode VARCHAR(80),
    normal_semesters SMALLINT CHECK (normal_semesters > 0),
    maximum_semesters SMALLINT CHECK (maximum_semesters > 0),
    minimum_cgpa NUMERIC(3,2) CHECK (minimum_cgpa BETWEEN 0 AND 4),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    source_id UUID REFERENCES source_records(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (maximum_semesters IS NULL OR normal_semesters IS NULL OR maximum_semesters >= normal_semesters)
);

CREATE TABLE curriculum_schemes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    total_credit_hours NUMERIC(5,1) NOT NULL CHECK (total_credit_hours > 0),
    minimum_semester_credits NUMERIC(4,1) CHECK (minimum_semester_credits > 0),
    maximum_semester_credits NUMERIC(4,1) CHECK (maximum_semester_credits > 0),
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (program_id, name),
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CHECK (maximum_semester_credits IS NULL OR minimum_semester_credits IS NULL OR maximum_semester_credits >= minimum_semester_credits)
);

CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(20) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    theory_credit_hours NUMERIC(3,1) NOT NULL DEFAULT 0 CHECK (theory_credit_hours >= 0),
    lab_credit_hours NUMERIC(3,1) NOT NULL DEFAULT 0 CHECK (lab_credit_hours >= 0),
    total_credit_hours NUMERIC(3,1) GENERATED ALWAYS AS (theory_credit_hours + lab_credit_hours) STORED,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    source_id UUID REFERENCES source_records(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (theory_credit_hours + lab_credit_hours > 0)
);

CREATE TABLE curriculum_courses (
    curriculum_id UUID NOT NULL REFERENCES curriculum_schemes(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    semester_number SMALLINT CHECK (semester_number BETWEEN 1 AND 20),
    requirement_type VARCHAR(20) NOT NULL
        CHECK (requirement_type IN ('core', 'elective', 'general', 'supporting', 'internship', 'project', 'thesis', 'deficiency')),
    display_order SMALLINT,
    PRIMARY KEY (curriculum_id, course_id)
);

CREATE TABLE curriculum_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id UUID NOT NULL REFERENCES curriculum_schemes(id) ON DELETE CASCADE,
    semester_number SMALLINT NOT NULL CHECK (semester_number BETWEEN 1 AND 20),
    title TEXT NOT NULL,
    requirement_type VARCHAR(20) NOT NULL
        CHECK (requirement_type IN ('elective', 'general', 'supporting', 'internship', 'project', 'thesis', 'deficiency')),
    credit_hours NUMERIC(3,1) NOT NULL CHECK (credit_hours > 0),
    display_order SMALLINT,
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    UNIQUE (curriculum_id, semester_number, title)
);

CREATE TABLE course_prerequisites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id UUID NOT NULL REFERENCES curriculum_schemes(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    prerequisite_course_id UUID NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    relation_type VARCHAR(20) NOT NULL DEFAULT 'prerequisite'
        CHECK (relation_type IN ('prerequisite', 'corequisite')),
    minimum_grade VARCHAR(5),
    waiver_condition TEXT,
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (curriculum_id, course_id, prerequisite_course_id, relation_type),
    CHECK (course_id <> prerequisite_course_id)
);

CREATE TABLE focus_areas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE course_focus_areas (
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    focus_area_id UUID NOT NULL REFERENCES focus_areas(id) ON DELETE CASCADE,
    PRIMARY KEY (course_id, focus_area_id)
);

CREATE TABLE academic_terms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    academic_year SMALLINT NOT NULL CHECK (academic_year BETWEEN 2000 AND 2200),
    term VARCHAR(15) NOT NULL CHECK (term IN ('Spring', 'Summer', 'Fall', 'Winter')),
    starts_on DATE,
    ends_on DATE,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    source_id UUID REFERENCES source_records(id) ON DELETE RESTRICT,
    UNIQUE (academic_year, term),
    CHECK (ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on)
);

CREATE TABLE fee_structures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID REFERENCES programs(id) ON DELETE CASCADE,
    official_fee_category TEXT NOT NULL,
    shift VARCHAR(30) NOT NULL,
    fee_type VARCHAR(50) NOT NULL,
    amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'PKR',
    effective_from DATE NOT NULL,
    effective_to DATE,
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE NULLS NOT DISTINCT (program_id, official_fee_category, shift, fee_type, effective_from),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE deadlines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term_id UUID REFERENCES academic_terms(id) ON DELETE CASCADE,
    program_id UUID REFERENCES programs(id) ON DELETE CASCADE,
    deadline_type VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    opens_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    notes TEXT,
    CHECK (opens_at IS NULL OR closes_at >= opens_at),
    CHECK (expires_at >= closes_at)
);

CREATE TABLE course_offerings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term_id UUID NOT NULL REFERENCES academic_terms(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    section VARCHAR(20) NOT NULL,
    instructor TEXT,
    capacity INTEGER CHECK (capacity IS NULL OR capacity > 0),
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    UNIQUE (term_id, course_id, program_id, section)
);

CREATE TABLE timetable_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offering_id UUID NOT NULL REFERENCES course_offerings(id) ON DELETE CASCADE,
    session_type VARCHAR(15) NOT NULL CHECK (session_type IN ('class', 'lab', 'tutorial')),
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    starts_at TIME NOT NULL,
    ends_at TIME NOT NULL,
    room TEXT NOT NULL,
    lab_group VARCHAR(30),
    CHECK (ends_at > starts_at),
    UNIQUE (offering_id, session_type, day_of_week, starts_at, lab_group)
);

CREATE TABLE exam_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offering_id UUID NOT NULL REFERENCES course_offerings(id) ON DELETE CASCADE,
    exam_type VARCHAR(30) NOT NULL,
    exam_date DATE NOT NULL,
    starts_at TIME NOT NULL,
    ends_at TIME,
    room TEXT,
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    CHECK (ends_at IS NULL OR ends_at > starts_at),
    UNIQUE (offering_id, exam_type, exam_date, starts_at)
);

CREATE TABLE academic_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code VARCHAR(50) NOT NULL,
    program_id UUID REFERENCES programs(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    condition_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    outcome_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    effective_from DATE NOT NULL,
    effective_to DATE,
    priority SMALLINT NOT NULL DEFAULT 100,
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (rule_code, effective_from),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE grading_bands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID REFERENCES programs(id) ON DELETE CASCADE,
    minimum_marks NUMERIC(5,2) NOT NULL CHECK (minimum_marks BETWEEN 0 AND 100),
    maximum_marks NUMERIC(5,2) NOT NULL CHECK (maximum_marks BETWEEN 0 AND 100),
    letter_grade VARCHAR(5) NOT NULL,
    grade_points NUMERIC(3,2) NOT NULL CHECK (grade_points BETWEEN 0 AND 4),
    effective_from DATE NOT NULL,
    effective_to DATE,
    source_id UUID NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
    UNIQUE (program_id, letter_grade, effective_from),
    CHECK (maximum_marks >= minimum_marks),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL UNIQUE REFERENCES source_records(id) ON DELETE CASCADE,
    program_id UUID REFERENCES programs(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    mime_type VARCHAR(100),
    storage_path TEXT NOT NULL,
    processing_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processing', 'ready', 'failed')),
    processed_at TIMESTAMPTZ,
    processing_error TEXT
);

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

CREATE TABLE app_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL DEFAULT 'User',
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'admin')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    user_agent TEXT
);

CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_by UUID REFERENCES app_users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE student_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES app_users(id) ON DELETE CASCADE,
    student_number VARCHAR(30) NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE RESTRICT,
    curriculum_id UUID NOT NULL REFERENCES curriculum_schemes(id) ON DELETE RESTRICT,
    admission_term_id UUID REFERENCES academic_terms(id) ON DELETE RESTRICT,
    current_semester SMALLINT CHECK (current_semester BETWEEN 1 AND 20),
    current_cgpa NUMERIC(3,2) CHECK (current_cgpa BETWEEN 0 AND 4),
    data_consent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE student_course_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    term_id UUID REFERENCES academic_terms(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL CHECK (status IN ('registered', 'in_progress', 'passed', 'failed', 'withdrawn', 'exempted')),
    letter_grade VARCHAR(5),
    grade_points NUMERIC(3,2) CHECK (grade_points IS NULL OR grade_points BETWEEN 0 AND 4),
    source_reference TEXT,
    UNIQUE (student_id, course_id, term_id)
);

CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES app_users(id) ON DELETE SET NULL,
    language VARCHAR(20),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(15) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    intent VARCHAR(60),
    intent_confidence NUMERIC(5,4) CHECK (intent_confidence IS NULL OR intent_confidence BETWEEN 0 AND 1),
    entities JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_engine VARCHAR(20) CHECK (response_engine IS NULL OR response_engine IN ('sql', 'rule', 'rag', 'fallback')),
    source_ids UUID[] NOT NULL DEFAULT '{}',
    response_time_ms INTEGER CHECK (response_time_ms IS NULL OR response_time_ms >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_user_id UUID REFERENCES app_users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id TEXT,
    before_data JSONB,
    after_data JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sources_category_status ON source_records (category, verification_status);
CREATE INDEX idx_courses_title_lower ON courses (LOWER(title));
CREATE INDEX idx_curriculum_courses_semester ON curriculum_courses (curriculum_id, semester_number);
CREATE INDEX idx_curriculum_slots_semester ON curriculum_slots (curriculum_id, semester_number);
CREATE INDEX idx_prerequisites_course ON course_prerequisites (curriculum_id, course_id);
CREATE INDEX idx_fees_lookup ON fee_structures (program_id, official_fee_category, shift, effective_from DESC);
CREATE INDEX idx_deadlines_lookup ON deadlines (deadline_type, closes_at DESC);
CREATE INDEX idx_offerings_term_program ON course_offerings (term_id, program_id);
CREATE INDEX idx_timetable_day ON timetable_entries (day_of_week, starts_at);
CREATE INDEX idx_rules_lookup ON academic_rules (category, program_id, active, priority);
CREATE INDEX idx_rules_condition_gin ON academic_rules USING GIN (condition_json);
CREATE INDEX idx_grading_bands_lookup ON grading_bands (program_id, effective_from DESC, minimum_marks);
CREATE INDEX idx_chunks_document ON document_chunks (document_id, chunk_index);
CREATE INDEX idx_chunks_metadata_gin ON document_chunks USING GIN (metadata);
CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_history_student_status ON student_course_history (student_id, status);
CREATE INDEX idx_messages_session_time ON chat_messages (session_id, created_at);

COMMIT;
