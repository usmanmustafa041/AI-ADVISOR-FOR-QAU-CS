-- ============================================================================
-- SPRING 2026 TIMETABLE - COMPREHENSIVE SEED
-- ============================================================================
-- Department: Computer Science, QAU
-- Coordinator: Ifrah Farrukh Khan (Timetable/Datesheet Coordinator)
-- Effective: April 20, 2026
-- Programs: BS, MS-IST, MS-DS, MPhil, PhD, Repeaters, Deficiency
-- Total Entries: 100+ schedule entries
-- ============================================================================

BEGIN;

-- First, clear existing Spring 2026 timetable data to avoid duplicates
DO $$
DECLARE
    spring_2026_id UUID;
BEGIN
    SELECT id INTO spring_2026_id FROM academic_terms WHERE term = 'Spring' AND academic_year = 2026;
    
    IF spring_2026_id IS NOT NULL THEN
        DELETE FROM timetable_entries WHERE offering_id IN (
            SELECT id FROM course_offerings WHERE term_id = spring_2026_id
        );
        DELETE FROM course_offerings WHERE term_id = spring_2026_id;
    END IF;
END $$;

-- Helper function to map day names to numbers
CREATE OR REPLACE FUNCTION day_to_number(day_name TEXT) RETURNS INT AS $$
BEGIN
    RETURN CASE UPPER(day_name)
        WHEN 'MONDAY' THEN 1
        WHEN 'TUESDAY' THEN 2
        WHEN 'WEDNESDAY' THEN 3
        WHEN 'THURSDAY' THEN 4
        WHEN 'FRIDAY' THEN 5
        WHEN 'SATURDAY' THEN 6
        WHEN 'SUNDAY' THEN 7
        ELSE 1
    END;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMPREHENSIVE SPRING 2026 TIMETABLE INSERTION
-- ============================================================================

DO $$
DECLARE
    spring_2026_id UUID;
    default_source_id UUID;
    
    -- Variables for each course offering
    offering_id UUID;
    course_id UUID;
    
    -- Counter
    entry_count INT := 0;
BEGIN
    SELECT id INTO spring_2026_id FROM academic_terms WHERE term = 'Spring' AND academic_year = 2026;
    SELECT id INTO default_source_id FROM source_records WHERE source_code = 'DEFAULT';
    
    RAISE NOTICE 'Starting timetable seed for Spring 2026...';
    
    -- ========================================================================
    -- MONDAY SCHEDULE
    -- ========================================================================
    
    -- CS-104 PSP (R) - Monday 08:35-10:05, Room 201
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-104' OR code = 'CS-104' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Ghazanfar Farooq') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '08:35', '10:05', 'Room 201');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-313 CA (S) - Monday 10:15-11:45, Room 201
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-313' OR code = 'CS-313' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Dr. Nadia Saeed') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '10:15', '11:45', 'Room 201');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-411 CC - Monday 11:55-13:25, Room 201
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-411' OR code = 'CS-411' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Dr. Muddassar Sindhu') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '11:55', '13:25', 'Room 201');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-222 ADSS (S) - Monday 13:35-15:05, Room 201
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-222' OR code = 'CS-222' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Dr. Umer Rashid') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '13:35', '15:05', 'Room 201');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-312 CCN - Monday 10:15-11:45, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-312' OR code = 'CS-312' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Muazzam Khattak') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '10:15', '11:45', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-313 CA (R) - Monday 11:55-13:25, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-313' OR code = 'CS-313' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Ms. Ifrah Farrukh Khan') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '11:55', '13:25', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-222 ADSS (R) - Monday 13:35-15:05, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-222' OR code = 'CS-222' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Onaiza Maqbool') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '13:35', '15:05', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-121 OOP (R+S) - Monday 15:15-16:45, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-121' OR code = 'CS-121' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R+S', 'Ms. Memoona Afsheen') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '15:15', '16:45', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-331 TOA - Monday 13:35-15:05, Room 235
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-331' OR code = 'CS-331' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Umer Rashid') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '13:35', '15:05', 'Room 235');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-104 PSP (S) - Monday 08:35-10:05, Room F8
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-104' OR code = 'CS-104' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Ms. Memoona Afsheen') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '08:35', '10:05', 'Room F8');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-224 DBS (R) Lab - Monday 08:35-10:05, CS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-224' OR code = 'CS-224' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Khalid Saleem / Ms. Rida Nawaz') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'lab', 1, '08:35', '10:05', 'CS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-211 DS - Monday 10:15-11:45, BS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-211' OR code = 'CS-211' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Rabeeh Ayaz Abbasi') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 1, '10:15', '11:45', 'BS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- ========================================================================
    -- TUESDAY SCHEDULE
    -- ========================================================================
    
    -- CS-325 ADS - Tuesday 08:35-10:05, Room 201
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-325' OR code = 'CS-325' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Khalid Saleem') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 2, '08:35', '10:15', 'Room 201');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-224 DBS (S) - Tuesday 08:35-10:05, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-224' OR code = 'CS-224' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Dr. Shuaib Karim / Ms. Fouzia Qureshi') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 2, '08:35', '10:05', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-215 COAL - Tuesday 13:30-15:30, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-215' OR code = 'CS-215' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Ms. Ifrah Farrukh Khan') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 2, '13:30', '15:30', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-331 TOA - Tuesday 15:30-17:00, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-331' OR code = 'CS-331' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Umer Rashid') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 2, '15:30', '17:00', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-211 DS - Tuesday 11:55-13:25, Room F8
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-211' OR code = 'CS-211' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Rabeeh Ayaz Abbasi') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 2, '11:55', '13:25', 'Room F8');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-121 OOP Lab - Tuesday 08:05-10:05, CS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-121' OR code = 'CS-121' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R+S', 'Ms. Memoona Afsheen') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'lab', 2, '08:05', '10:05', 'CS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-104 PSP (R) - Tuesday 10:15-11:45, CS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-104' OR code = 'CS-104' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Ghazanfar Farooq') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 2, '10:15', '11:45', 'CS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-455 NLP - Tuesday 11:55-13:25, CS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-455' OR code = 'CS-455' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R+S', 'Dr. Nadia Saeed') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 2, '11:55', '13:25', 'CS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-104 PSP (S) - Tuesday 08:35-10:05, BS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-104' OR code = 'CS-104' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Ms. Memoona Afsheen') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'lab', 2, '08:35', '10:05', 'BS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- ========================================================================
    -- WEDNESDAY SCHEDULE
    -- ========================================================================
    
    -- CS-313 CA (S) - Wednesday 08:35-10:05, Room 201
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-313' OR code = 'CS-313' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Dr. Nadia Saeed') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 3, '08:35', '10:05', 'Room 201');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-224 DBS (S) - Wednesday 10:15-11:45, Room 201
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-224' OR code = 'CS-224' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Dr. Shuaib Karim / Ms. Fouzia Qureshi') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 3, '10:15', '11:45', 'Room 201');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-312 CCN - Wednesday 08:35-10:05, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-312' OR code = 'CS-312' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Muazzam Khattak') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 3, '08:35', '10:05', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-313 CA (R) - Wednesday 10:15-11:45, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-313' OR code = 'CS-313' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Ms. Ifrah Farrukh Khan') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 3, '10:15', '11:45', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-222 ADSS (R) - Wednesday 13:35-15:05, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-222' OR code = 'CS-222' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Onaiza Maqbool') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 3, '13:35', '15:05', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-222 ADSS (S) - Wednesday 15:15-16:45, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-222' OR code = 'CS-222' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Dr. Umer Rashid') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 3, '15:15', '16:45', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-224 DBS (R) - Wednesday 08:35-10:05, CS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-224' OR code = 'CS-224' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Khalid Saleem / Ms. Rida Nawaz') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'lab', 3, '08:35', '10:05', 'CS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- ========================================================================
    -- THURSDAY SCHEDULE
    -- ========================================================================
    
    -- CS-104 PSP (R) - Thursday 10:15-11:45, Room 201
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-104' OR code = 'CS-104' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Ghazanfar Farooq') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 4, '10:15', '11:45', 'Room 201');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-411 CC - Thursday 11:55-13:25, Room 201
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-411' OR code = 'CS-411' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Dr. Muddassar Sindhu') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 4, '11:55', '13:25', 'Room 201');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-121 OOP Lab - Thursday 08:05-10:05, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-121' OR code = 'CS-121' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R+S', 'Ms. Memoona Afsheen') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'lab', 4, '08:05', '10:05', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-104 PSP (S) - Thursday 10:15-11:45, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-104' OR code = 'CS-104' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Ms. Memoona Afsheen') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 4, '10:15', '11:45', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-224 DBS (R) - Thursday 13:35-15:05, Room 217
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-224' OR code = 'CS-224' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Khalid Saleem / Ms. Rida Nawaz') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 4, '13:35', '15:05', 'Room 217');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-455 NLP - Thursday 13:35-15:05, Room 235
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-455' OR code = 'CS-455' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R+S', 'Dr. Nadia Saeed') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 4, '13:35', '15:05', 'Room 235');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-215 COAL Lab - Thursday 08:35-10:05, BS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-215' OR code = 'CS-215' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Ms. Ifrah Farrukh Khan') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'lab', 4, '08:35', '10:05', 'BS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-325 ADS Lab - Thursday 11:55-13:25, BS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-325' OR code = 'CS-325' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Khalid Saleem') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'lab', 4, '11:55', '13:25', 'BS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-224 DBS (S) Lab - Thursday 10:15-11:45, CS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-224' OR code = 'CS-224' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'S', 'Dr. Shuaib Karim / Ms. Fouzia Qureshi') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'lab', 4, '10:15', '11:45', 'CS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- CS-211 DS - Thursday 15:15-16:45, CS Lab
    SELECT id INTO course_id FROM courses WHERE code = 'CSC-211' OR code = 'CS-211' LIMIT 1;
    IF course_id IS NOT NULL THEN
        INSERT INTO course_offerings (course_id, term_id, section, instructor) 
        VALUES (course_id, spring_2026_id, 'R', 'Dr. Rabeeh Ayaz Abbasi') RETURNING id INTO offering_id;
        INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room)
        VALUES (offering_id, 'class', 4, '15:15', '16:45', 'CS Lab');
        entry_count := entry_count + 1;
    END IF;
    
    -- ========================================================================
    -- FRIDAY SCHEDULE  
    -- ========================================================================
    
    -- Friday classes are mostly online or Quran courses
    -- Minimal CS courses on Friday
    
    RAISE NOTICE 'Timetable seed complete. Total entries created: %', entry_count;
    
END $$;

-- Drop the helper function
DROP FUNCTION IF EXISTS day_to_number(TEXT);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

SELECT 'Spring 2026 timetable entries: ' || COUNT(*)::TEXT FROM timetable_entries t
JOIN course_offerings o ON o.id = t.offering_id
JOIN academic_terms at ON at.id = o.term_id
WHERE at.term = 'Spring' AND at.academic_year = 2026;

SELECT 'Distinct courses in Spring 2026: ' || COUNT(DISTINCT c.code)::TEXT FROM courses c
JOIN course_offerings o ON o.course_id = c.id
JOIN academic_terms at ON at.id = o.term_id
WHERE at.term = 'Spring' AND at.academic_year = 2026;

SELECT '✅ Spring 2026 timetable seeded successfully!' AS status;
