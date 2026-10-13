-- ============================================================================
-- TIMETABLE SYSTEM SCHEMA (NON-DESTRUCTIVE / ZERO-DATA-LOSS)
-- ============================================================================
-- This script creates the timetable tables and related structures
-- using ONLY safe, additive operations (IF NOT EXISTS clauses).
--
-- SAFETY GUARANTEES:
-- 1. No DROP statements for tables
-- 2. No TRUNCATE statements
-- 3. All CREATE use IF NOT EXISTS
-- 4. Existing data is NEVER deleted
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- ACADEMIC SESSION TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS academic_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_name VARCHAR(50) UNIQUE NOT NULL,  -- e.g., "Spring 2026", "Fall 2025"
    effective_from DATE NOT NULL,
    effective_to DATE,
    is_current BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Index for current session
CREATE INDEX IF NOT EXISTS idx_academic_sessions_current 
    ON academic_sessions(is_current) WHERE is_current = true;

-- ============================================================================
-- INSTRUCTORS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS instructors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    title VARCHAR(50),  -- Dr., Ms., Mr., Prof.
    email VARCHAR(200),
    department VARCHAR(100) DEFAULT 'Computer Science',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    UNIQUE(name, department)
);

-- Index for active instructors
CREATE INDEX IF NOT EXISTS idx_instructors_active 
    ON instructors(is_active) WHERE is_active = true;

-- Index for name search
CREATE INDEX IF NOT EXISTS idx_instructors_name 
    ON instructors(name);

-- ============================================================================
-- TEACHING ASSISTANTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS teaching_assistants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    email VARCHAR(200),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    UNIQUE(name)
);

-- Index for active TAs
CREATE INDEX IF NOT EXISTS idx_teaching_assistants_active 
    ON teaching_assistants(is_active) WHERE is_active = true;

-- ============================================================================
-- COURSE SCHEDULE TABLE (Main Timetable)
-- ============================================================================

CREATE TABLE IF NOT EXISTS course_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Session reference
    academic_session_id UUID NOT NULL REFERENCES academic_sessions(id) ON DELETE CASCADE,
    
    -- Course information
    course_code VARCHAR(20) NOT NULL,  -- e.g., "CS-104"
    course_abbreviation VARCHAR(20),   -- e.g., "PSP (R)"
    course_name VARCHAR(300) NOT NULL, -- e.g., "Problem Solving & Programming"
    credit_hours VARCHAR(10),          -- e.g., "3+1"
    
    -- Program and semester
    program VARCHAR(50) NOT NULL,      -- e.g., "BS", "MPhil", "MS-DS"
    semester VARCHAR(50),              -- e.g., "Semester 1", "MPhil 2nd and PhD"
    section_type VARCHAR(50),          -- e.g., "Regular", "Self Support", "Deficiency"
    
    -- Schedule details
    day_of_week VARCHAR(20) NOT NULL CHECK (day_of_week IN (
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
    )),
    time_slot VARCHAR(50) NOT NULL,    -- e.g., "08:35-10:05"
    shift VARCHAR(20),                 -- e.g., "Morning", "Afternoon", "Evening"
    room VARCHAR(100),                 -- e.g., "Room 201", "CS Lab", "Online"
    
    -- Metadata
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Unique constraint to prevent duplicate schedules
    UNIQUE(academic_session_id, course_code, section_type, day_of_week, time_slot, room)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_course_schedules_session 
    ON course_schedules(academic_session_id);

CREATE INDEX IF NOT EXISTS idx_course_schedules_course_code 
    ON course_schedules(course_code);

CREATE INDEX IF NOT EXISTS idx_course_schedules_day 
    ON course_schedules(day_of_week);

CREATE INDEX IF NOT EXISTS idx_course_schedules_program 
    ON course_schedules(program);

CREATE INDEX IF NOT EXISTS idx_course_schedules_semester 
    ON course_schedules(semester);

CREATE INDEX IF NOT EXISTS idx_course_schedules_room 
    ON course_schedules(room);

CREATE INDEX IF NOT EXISTS idx_course_schedules_active 
    ON course_schedules(is_active) WHERE is_active = true;

-- Combined index for common searches
CREATE INDEX IF NOT EXISTS idx_course_schedules_search 
    ON course_schedules(academic_session_id, day_of_week, is_active) 
    WHERE is_active = true;

-- ============================================================================
-- COURSE SCHEDULE INSTRUCTORS (Many-to-Many)
-- ============================================================================

CREATE TABLE IF NOT EXISTS course_schedule_instructors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_schedule_id UUID NOT NULL REFERENCES course_schedules(id) ON DELETE CASCADE,
    instructor_id UUID NOT NULL REFERENCES instructors(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    UNIQUE(course_schedule_id, instructor_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_course_schedule_instructors_schedule 
    ON course_schedule_instructors(course_schedule_id);

CREATE INDEX IF NOT EXISTS idx_course_schedule_instructors_instructor 
    ON course_schedule_instructors(instructor_id);

-- ============================================================================
-- COURSE SCHEDULE TEACHING ASSISTANTS (Many-to-Many)
-- ============================================================================

CREATE TABLE IF NOT EXISTS course_schedule_tas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_schedule_id UUID NOT NULL REFERENCES course_schedules(id) ON DELETE CASCADE,
    ta_id UUID NOT NULL REFERENCES teaching_assistants(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    UNIQUE(course_schedule_id, ta_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_course_schedule_tas_schedule 
    ON course_schedule_tas(course_schedule_id);

CREATE INDEX IF NOT EXISTS idx_course_schedule_tas_ta 
    ON course_schedule_tas(ta_id);

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC TIMESTAMP UPDATE
-- ============================================================================

-- Trigger for academic_sessions
DROP TRIGGER IF EXISTS trigger_academic_sessions_updated_at ON academic_sessions;
CREATE TRIGGER trigger_academic_sessions_updated_at
    BEFORE UPDATE ON academic_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for instructors
DROP TRIGGER IF EXISTS trigger_instructors_updated_at ON instructors;
CREATE TRIGGER trigger_instructors_updated_at
    BEFORE UPDATE ON instructors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for teaching_assistants
DROP TRIGGER IF EXISTS trigger_teaching_assistants_updated_at ON teaching_assistants;
CREATE TRIGGER trigger_teaching_assistants_updated_at
    BEFORE UPDATE ON teaching_assistants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for course_schedules
DROP TRIGGER IF EXISTS trigger_course_schedules_updated_at ON course_schedules;
CREATE TRIGGER trigger_course_schedules_updated_at
    BEFORE UPDATE ON course_schedules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- HELPFUL VIEWS
-- ============================================================================

-- Complete timetable view with all details
CREATE OR REPLACE VIEW v_timetable_complete AS
SELECT 
    cs.id,
    asess.session_name,
    cs.day_of_week,
    cs.time_slot,
    cs.shift,
    cs.room,
    cs.course_code,
    cs.course_abbreviation,
    cs.course_name,
    cs.credit_hours,
    cs.program,
    cs.semester,
    cs.section_type,
    -- Aggregate instructors
    COALESCE(
        array_agg(DISTINCT i.name ORDER BY i.name) FILTER (WHERE i.name IS NOT NULL),
        ARRAY[]::VARCHAR[]
    ) as instructors,
    -- Aggregate TAs
    COALESCE(
        array_agg(DISTINCT ta.name ORDER BY ta.name) FILTER (WHERE ta.name IS NOT NULL),
        ARRAY[]::VARCHAR[]
    ) as teaching_assistants,
    cs.created_at,
    cs.updated_at
FROM course_schedules cs
JOIN academic_sessions asess ON cs.academic_session_id = asess.id
LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
LEFT JOIN instructors i ON csi.instructor_id = i.id
LEFT JOIN course_schedule_tas csta ON cs.id = csta.course_schedule_id
LEFT JOIN teaching_assistants ta ON csta.ta_id = ta.id
WHERE cs.is_active = true
GROUP BY 
    cs.id, asess.session_name, cs.day_of_week, cs.time_slot, cs.shift,
    cs.room, cs.course_code, cs.course_abbreviation, cs.course_name,
    cs.credit_hours, cs.program, cs.semester, cs.section_type,
    cs.created_at, cs.updated_at
ORDER BY 
    CASE cs.day_of_week
        WHEN 'Monday' THEN 1
        WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5
        WHEN 'Saturday' THEN 6
        WHEN 'Sunday' THEN 7
    END,
    cs.time_slot;

-- Current session timetable
CREATE OR REPLACE VIEW v_current_timetable AS
SELECT * FROM v_timetable_complete
WHERE session_name IN (
    SELECT session_name FROM academic_sessions WHERE is_current = true
);

-- Instructor schedule view
CREATE OR REPLACE VIEW v_instructor_schedule AS
SELECT 
    i.name as instructor_name,
    asess.session_name,
    cs.day_of_week,
    cs.time_slot,
    cs.room,
    cs.course_code,
    cs.course_name,
    cs.program,
    cs.semester
FROM instructors i
JOIN course_schedule_instructors csi ON i.id = csi.instructor_id
JOIN course_schedules cs ON csi.course_schedule_id = cs.id
JOIN academic_sessions asess ON cs.academic_session_id = asess.id
WHERE cs.is_active = true AND i.is_active = true
ORDER BY 
    i.name,
    CASE cs.day_of_week
        WHEN 'Monday' THEN 1
        WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5
        WHEN 'Saturday' THEN 6
        WHEN 'Sunday' THEN 7
    END,
    cs.time_slot;

-- Room utilization view
CREATE OR REPLACE VIEW v_room_schedule AS
SELECT 
    cs.room,
    asess.session_name,
    cs.day_of_week,
    cs.time_slot,
    cs.course_code,
    cs.course_name,
    cs.program,
    array_agg(DISTINCT i.name) as instructors
FROM course_schedules cs
JOIN academic_sessions asess ON cs.academic_session_id = asess.id
LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
LEFT JOIN instructors i ON csi.instructor_id = i.id
WHERE cs.is_active = true
GROUP BY 
    cs.room, asess.session_name, cs.day_of_week, 
    cs.time_slot, cs.course_code, cs.course_name, cs.program
ORDER BY 
    cs.room,
    CASE cs.day_of_week
        WHEN 'Monday' THEN 1
        WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5
        WHEN 'Saturday' THEN 6
        WHEN 'Sunday' THEN 7
    END,
    cs.time_slot;

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to get courses by day
CREATE OR REPLACE FUNCTION get_courses_by_day(
    p_day VARCHAR(20),
    p_session_name VARCHAR(50) DEFAULT NULL
)
RETURNS TABLE (
    course_code VARCHAR,
    course_name VARCHAR,
    time_slot VARCHAR,
    room VARCHAR,
    instructors TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cs.course_code,
        cs.course_name,
        cs.time_slot,
        cs.room,
        array_agg(DISTINCT i.name) as instructors
    FROM course_schedules cs
    JOIN academic_sessions asess ON cs.academic_session_id = asess.id
    LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
    LEFT JOIN instructors i ON csi.instructor_id = i.id
    WHERE cs.day_of_week = p_day
        AND cs.is_active = true
        AND (p_session_name IS NULL OR asess.session_name = p_session_name)
    GROUP BY cs.course_code, cs.course_name, cs.time_slot, cs.room
    ORDER BY cs.time_slot;
END;
$$ LANGUAGE plpgsql;

-- Function to search schedules
CREATE OR REPLACE FUNCTION search_schedule(
    p_search_term VARCHAR(200)
)
RETURNS TABLE (
    day_of_week VARCHAR,
    time_slot VARCHAR,
    course_code VARCHAR,
    course_name VARCHAR,
    room VARCHAR,
    program VARCHAR,
    semester VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cs.day_of_week,
        cs.time_slot,
        cs.course_code,
        cs.course_name,
        cs.room,
        cs.program,
        cs.semester
    FROM course_schedules cs
    WHERE cs.is_active = true
        AND (
            cs.course_code ILIKE '%' || p_search_term || '%' OR
            cs.course_name ILIKE '%' || p_search_term || '%' OR
            cs.course_abbreviation ILIKE '%' || p_search_term || '%' OR
            cs.room ILIKE '%' || p_search_term || '%'
        )
    ORDER BY cs.day_of_week, cs.time_slot;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'academic_sessions') THEN
        RAISE NOTICE '✅ academic_sessions table created successfully';
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'instructors') THEN
        RAISE NOTICE '✅ instructors table created successfully';
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'teaching_assistants') THEN
        RAISE NOTICE '✅ teaching_assistants table created successfully';
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'course_schedules') THEN
        RAISE NOTICE '✅ course_schedules table created successfully';
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'course_schedule_instructors') THEN
        RAISE NOTICE '✅ course_schedule_instructors table created successfully';
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'course_schedule_tas') THEN
        RAISE NOTICE '✅ course_schedule_tas table created successfully';
    END IF;
END $$;

-- ============================================================================
-- END OF TIMETABLE SCHEMA
-- ============================================================================
