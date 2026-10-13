-- Additive, idempotent migration for existing installations and fresh compose.
BEGIN;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS response_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
    ON chat_messages (session_id, created_at DESC);

-- Legacy installations omitted these optional structured-data fields.
-- Keep missing facts NULL; this migration does not authenticate or seed data.
ALTER TABLE programs ADD COLUMN IF NOT EXISTS level VARCHAR(20);
ALTER TABLE programs ADD COLUMN IF NOT EXISTS study_mode VARCHAR(80);
ALTER TABLE programs ADD COLUMN IF NOT EXISTS source_id UUID REFERENCES source_records(id);
ALTER TABLE curriculum_schemes ADD COLUMN IF NOT EXISTS total_credit_hours NUMERIC(5,1);
ALTER TABLE curriculum_schemes ADD COLUMN IF NOT EXISTS source_id UUID REFERENCES source_records(id);

CREATE TABLE IF NOT EXISTS curriculum_courses (
    curriculum_id UUID NOT NULL REFERENCES curriculum_schemes(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    semester_number SMALLINT,
    requirement_type VARCHAR(20) NOT NULL,
    display_order SMALLINT,
    PRIMARY KEY (curriculum_id, course_id)
);
CREATE TABLE IF NOT EXISTS curriculum_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id UUID NOT NULL REFERENCES curriculum_schemes(id) ON DELETE CASCADE,
    semester_number SMALLINT NOT NULL,
    title TEXT NOT NULL,
    requirement_type VARCHAR(20) NOT NULL,
    credit_hours NUMERIC(3,1) NOT NULL CHECK (credit_hours > 0),
    display_order SMALLINT,
    source_id UUID NOT NULL REFERENCES source_records(id),
    UNIQUE (curriculum_id, semester_number, title)
);
CREATE TABLE IF NOT EXISTS deadlines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term_id UUID REFERENCES academic_terms(id) ON DELETE CASCADE,
    program_id UUID REFERENCES programs(id) ON DELETE CASCADE,
    deadline_type VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    opens_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    source_id UUID NOT NULL REFERENCES source_records(id),
    notes TEXT,
    CHECK (opens_at IS NULL OR closes_at >= opens_at),
    CHECK (expires_at >= closes_at)
);
CREATE TABLE IF NOT EXISTS exam_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offering_id UUID NOT NULL REFERENCES course_offerings(id) ON DELETE CASCADE,
    exam_type VARCHAR(30) NOT NULL,
    exam_date DATE NOT NULL,
    starts_at TIME NOT NULL,
    ends_at TIME,
    room TEXT,
    source_id UUID NOT NULL REFERENCES source_records(id),
    CHECK (ends_at IS NULL OR ends_at > starts_at),
    UNIQUE (offering_id, exam_type, exam_date, starts_at)
);
COMMIT;
