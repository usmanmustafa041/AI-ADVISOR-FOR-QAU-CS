-- ============================================================================
-- SPRING 2026 TIMETABLE - COMPLETE AUTO-GENERATED SEED
-- ============================================================================
-- Generated from JSON timetable data
-- Total entries: 109
-- Academic Session: Spring 2026
-- Effective From: 2026-04-20
-- Coordinator: Ifrah Farrukh Khan
-- ============================================================================

-- First, ensure the schema is created
\i backend/scripts/init_timetable_schema.sql

BEGIN;

-- ============================================================================
-- STEP 1: CREATE ACADEMIC SESSION
-- ============================================================================

INSERT INTO academic_sessions (session_name, effective_from, is_current)
VALUES ('Spring 2026', '2026-04-20', true)
ON CONFLICT (session_name) 
DO UPDATE SET 
    effective_from = EXCLUDED.effective_from,
    is_current = EXCLUDED.is_current,
    updated_at = NOW();

-- ============================================================================
-- STEP 2: INSERT INSTRUCTORS
-- ============================================================================

INSERT INTO instructors (name, title, department) VALUES
('Dr. Abdul Jalil', 'Dr.', 'Statistics'),
('Dr. Abdul Rasheed', 'Dr.', 'Social Sciences'),
('Dr. Adeel Ur Rehman', 'Dr.', 'Computer Science'),
('Dr. Akmal Saeed Khattak', 'Dr.', 'Computer Science'),
('Dr. Arshad Qayyum', 'Dr.', 'Islamic Studies'),
('Dr. Ayyaz Hussain', 'Dr.', 'Computer Science'),
('Dr. Ghazanfar Farooq', 'Dr.', 'Computer Science'),
('Dr. Khalid Saleem', 'Dr.', 'Computer Science'),
('Dr. Muazzam Khattak', 'Dr.', 'Computer Science'),
('Dr. Muddassar Sindhu', 'Dr.', 'Computer Science'),
('Dr. Muhammad Shafiq', 'Dr.', 'Physics'),
('Dr. Nadia Saeed', 'Dr.', 'Computer Science'),
('Dr. Nasreen Kousar', 'Dr.', 'Social Work'),
('Dr. Onaiza Maqbool', 'Dr.', 'Computer Science'),
('Dr. Rabeeh Ayaz Abbasi', 'Dr.', 'Computer Science'),
('Dr. S. M. Naqi', 'Dr.', 'Computer Science'),
('Dr. Saghir Ahmed', 'Dr.', 'Computer Science'),
('Dr. Shuaib Karim', 'Dr.', 'Computer Science'),
('Dr. Umer Rashid', 'Dr.', 'Computer Science'),
('Dr. Waseem Siddiqui', 'Dr.', 'Mathematics'),
('Mr. Abdul Wahid', 'Mr.', 'Islamic Studies'),
('Mr. Muhammad Tauseef', 'Mr.', 'Computer Science'),
('Ms. Farwa Haider', 'Ms.', 'Mathematics'),
('Ms. Fouzia Qureshi', 'Ms.', 'Computer Science'),
('Ms. Ifrah Farrukh Khan', 'Ms.', 'Computer Science'),
('Ms. Memoona Afsheen', 'Ms.', 'Computer Science'),
('Ms. Rida Nawaz', 'Ms.', 'Computer Science'),
('Ms. Tahira Shabir', 'Ms.', 'English')

ON CONFLICT (name, department) DO NOTHING;

-- ============================================================================
-- STEP 3: INSERT TEACHING ASSISTANTS
-- ============================================================================

INSERT INTO teaching_assistants (name) VALUES
('Mr. Abdur Rehman'),
('Mr. Hammad'),
('Mr. Zain'),
('Ms. Safeena')

ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- STEP 4: HELPER FUNCTION FOR INSERTING SCHEDULE ENTRIES
-- ============================================================================

CREATE OR REPLACE FUNCTION insert_schedule_entry(
    p_session_name VARCHAR,
    p_day VARCHAR,
    p_time_slot VARCHAR,
    p_shift VARCHAR,
    p_room VARCHAR,
    p_course_code VARCHAR,
    p_abbr VARCHAR,
    p_course_name VARCHAR,
    p_section_type VARCHAR,
    p_program VARCHAR,
    p_semester VARCHAR,
    p_credit_hours VARCHAR,
    p_instructors TEXT[],
    p_tas TEXT[]
) RETURNS void AS $$
DECLARE
    v_session_id UUID;
    v_schedule_id UUID;
    v_instructor_id UUID;
    v_ta_id UUID;
    v_instructor TEXT;
    v_ta TEXT;
BEGIN
    SELECT id INTO v_session_id FROM academic_sessions WHERE session_name = p_session_name;
    
    IF v_session_id IS NULL THEN
        RAISE EXCEPTION 'Academic session % not found', p_session_name;
    END IF;
    
    INSERT INTO course_schedules (
        academic_session_id, course_code, course_abbreviation, course_name,
        credit_hours, program, semester, section_type, day_of_week,
        time_slot, shift, room
    ) VALUES (
        v_session_id, p_course_code, p_abbr, p_course_name,
        p_credit_hours, p_program, p_semester, p_section_type, p_day,
        p_time_slot, p_shift, p_room
    )
    ON CONFLICT (academic_session_id, course_code, section_type, day_of_week, time_slot, room)
    DO UPDATE SET
        course_abbreviation = EXCLUDED.course_abbreviation,
        course_name = EXCLUDED.course_name,
        credit_hours = EXCLUDED.credit_hours,
        program = EXCLUDED.program,
        semester = EXCLUDED.semester,
        shift = EXCLUDED.shift,
        updated_at = NOW()
    RETURNING id INTO v_schedule_id;
    
    DELETE FROM course_schedule_instructors WHERE course_schedule_id = v_schedule_id;
    DELETE FROM course_schedule_tas WHERE course_schedule_id = v_schedule_id;
    
    FOREACH v_instructor IN ARRAY p_instructors
    LOOP
        SELECT id INTO v_instructor_id FROM instructors WHERE name = v_instructor;
        IF v_instructor_id IS NOT NULL THEN
            INSERT INTO course_schedule_instructors (course_schedule_id, instructor_id)
            VALUES (v_schedule_id, v_instructor_id)
            ON CONFLICT (course_schedule_id, instructor_id) DO NOTHING;
        END IF;
    END LOOP;
    
    FOREACH v_ta IN ARRAY p_tas
    LOOP
        SELECT id INTO v_ta_id FROM teaching_assistants WHERE name = v_ta;
        IF v_ta_id IS NOT NULL THEN
            INSERT INTO course_schedule_tas (course_schedule_id, ta_id)
            VALUES (v_schedule_id, v_ta_id)
            ON CONFLICT (course_schedule_id, ta_id) DO NOTHING;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- STEP 5: INSERT ALL SCHEDULE ENTRIES
-- Total: 109 entries
-- ============================================================================

-- MONDAY ENTRIES (23 entries)
SELECT insert_schedule_entry('Spring 2026', 'Monday', '08:35-10:05', 'Morning', 'Room 201', 'CS-104', 'PSP (R)', 'Problem Solving & Programming', 'Regular', 'BS', 'Semester 1', '3+1', ARRAY['Dr. Ghazanfar Farooq'], ARRAY['Mr. Hammad']);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '10:15-11:45', 'Morning', 'Room 201', 'CS-313', 'CA (S)', 'Computer Architecture', 'Self Support', 'BS', 'Semester 4', '3', ARRAY['Dr. Nadia Saeed'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '11:55-13:25', 'Morning', 'Room 201', 'CS-411', 'CC', 'Compiler Construction', 'Self Support', 'BS', 'Semester 7', '3', ARRAY['Dr. Muddassar Sindhu'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '13:35-15:05', 'Afternoon', 'Room 201', 'CS-222', 'ADSS (S)', 'Analysis and Design for Software Systems', 'Self Support', 'BS', 'Semester 4', '3', ARRAY['Dr. Umer Rashid'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '15:15-16:45', 'Afternoon', 'Room 201', 'CS-332', 'NCP', 'Net Centric Programming', 'Self Support', 'BS', 'Semester 7', '3', ARRAY['Dr. Adeel Ur Rehman'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '08:35-10:05', 'Morning', 'Room 217', 'CS-425', 'CV', 'Computer Vision', 'Regular', 'BS', 'Semester 6', '3', ARRAY['Dr. S. M. Naqi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '10:15-11:45', 'Morning', 'Room 217', 'CS-312', 'CCN', 'Computer Communications and Networks', 'Regular', 'BS', 'Semester 6', '3', ARRAY['Dr. Muazzam Khattak'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '11:55-13:25', 'Morning', 'Room 217', 'CS-313', 'CA (R)', 'Computer Architecture', 'Regular', 'BS', 'Semester 4', '3', ARRAY['Ms. Ifrah Farrukh Khan'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '13:35-15:05', 'Afternoon', 'Room 217', 'CS-222', 'ADSS (R)', 'Analysis and Design for Software Systems', 'Regular', 'BS', 'Semester 4', '3', ARRAY['Dr. Onaiza Maqbool'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '15:15-16:45', 'Afternoon', 'Room 217', 'CS-121', 'OOP (R+S)', 'Object Oriented Programming', 'Regular & Self Support', 'BS', 'Semester 2', '3+1', ARRAY['Ms. Memoona Afsheen'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '08:35-10:05', 'Morning', 'Room 235', 'CS-460', 'DL', 'Deep Learning', 'Regular', 'BS', 'Semester 8', '3', ARRAY['Dr. Ayyaz Hussain'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '10:15-11:45', 'Morning', 'Room 235', 'CS-413', 'IIS', 'Introduction to Information Security', 'Regular', 'BS', 'Semester 8', '3', ARRAY['Dr. Muazzam Khattak'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '13:35-15:05', 'Afternoon', 'Room 235', 'CS-331', 'TOA', 'Theory of Automata', 'Regular', 'BS', 'Semester 6', '3', ARRAY['Dr. Umer Rashid'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '08:35-10:05', 'Morning', 'Room F8', 'CS-104', 'PSP (S)', 'Problem Solving & Programming', 'Self Support', 'BS', 'Semester 1', '3+1', ARRAY['Ms. Memoona Afsheen'], ARRAY['Mr. Abdur Rehman']);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '10:15-11:45', 'Morning', 'Room F8', 'PH-110', 'IMW (R)', 'Introduction to Mechanics and Waves', 'Regular', 'BS', 'Semester 2', '3', ARRAY['Dr. Muhammad Shafiq'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '10:15-12:15', 'Morning', 'Room F6', 'IS-100', 'IS (S)', 'Islamic Studies/ Ethics', 'Self Support', 'BS', 'Semester 2', '2', ARRAY['Dr. Arshad Qayyum'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '08:35-10:05', 'Morning', 'CS Lab', 'CS-224', 'DBS (R)', 'Database Systems', 'Regular', 'BS', 'Semester 4', '3+1', ARRAY['Dr. Khalid Saleem', 'Ms. Rida Nawaz'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '10:15-11:45', 'Morning', 'CS Lab', 'CSC-675', 'IRS', 'Information Retrieval Systems', 'Regular', 'MPhil / PhD', 'MPhil 2nd and PhD', '3', ARRAY['Dr. Akmal Saeed Khattak'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '11:55-13:25', 'Morning', 'CS Lab', 'CS-458', 'DM', 'Data Mining', 'Self Support', 'BS', 'Semester 7', '3', ARRAY['Dr. Onaiza Maqbool'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '17:00-18:30', 'Evening', 'CS Lab', 'CS-352', 'DSA', 'Data Structures & Algorithms', 'Deficiency', 'Deficiency Courses', 'Deficiency', '3', ARRAY['Dr. S. M. Naqi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '18:30-20:00', 'Evening', 'CS Lab', 'CS-352', 'DSA', 'Data Structures & Algorithms', 'Deficiency', 'Deficiency Courses', 'Deficiency', '3', ARRAY['Dr. S. M. Naqi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '08:35-10:05', 'Morning', 'BS Lab', 'CSC-614', 'SQAT', 'Software Quality Assurance and testing', 'Regular', 'MPhil / PhD', 'MPhil 2nd and PhD', '3', ARRAY['Dr. Muddassar Sindhu'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Monday', '10:15-11:45', 'Morning', 'BS Lab', 'CS-211', 'DS', 'Data Structures', 'Regular', 'BS', 'Semester 3', '3+1', ARRAY['Dr. Rabeeh Ayaz Abbasi'], ARRAY['Ms. Safeena']);

-- TUESDAY ENTRIES (24 entries)
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '08:35-10:05', 'Morning', 'Room 201', 'CS-483', 'SQA', 'Software Quality Assurance', 'Regular', 'BS', 'Semester 6', '3', ARRAY['Dr. Muddassar Sindhu'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '10:15-12:15', 'Morning', 'Room 201', 'CS-325', 'ADS', 'Advanced Database Systems', 'Regular', 'BS', 'Semester 6', '2+1', ARRAY['Dr. Khalid Saleem'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '08:35-10:05', 'Morning', 'Room 217', 'CS-224', 'DBS (S)', 'Database Systems', 'Self Support', 'BS', 'Semester 4', '3+1', ARRAY['Dr. Shuaib Karim', 'Ms. Fouzia Qureshi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '10:15-11:45', 'Morning', 'Room 217', 'MA-104', 'FLA (S)', 'Fundamentals of Linear Algebra', 'Self Support', 'BS', 'Semester 4', '3', ARRAY['Dr. Waseem Siddiqui'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '11:55-13:25', 'Morning', 'Room 217', 'CS-458', 'DM', 'Data Mining', 'Self Support', 'BS', 'Semester 7', '3', ARRAY['Dr. Onaiza Maqbool'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '13:30-15:30', 'Afternoon', 'Room 217', 'CS-215', 'COAL', 'Computer Organization and Assembly Language', 'Regular', 'BS', 'Semester 6', '2+1', ARRAY['Ms. Ifrah Farrukh Khan'], ARRAY['Mr. Zain']);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '15:30-17:00', 'Afternoon', 'Room 217', 'CS-331', 'TOA', 'Theory of Automata', 'Regular', 'BS', 'Semester 6', '3', ARRAY['Dr. Umer Rashid'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '08:35-10:05', 'Morning', 'Room 235', 'CS-449', 'ICTS', 'ICT and Society', 'Regular', 'BS', 'Semester 8', '3', ARRAY['Dr. Shuaib Karim'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '10:15-11:45', 'Morning', 'Room 235', 'CSC-741', 'CV', 'Computer Vision', 'Regular', 'MPhil / PhD', 'MPhil / PhD', '3', ARRAY['Dr. S. M. Naqi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '13:30-15:30', 'Afternoon', 'Room 235', 'CS-457', 'WAF', 'Web Application Framework', 'Self Support', 'BS', 'Semester 7', '2+1', ARRAY['Dr. Akmal Saeed Khattak'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '17:00-18:30', 'Evening', 'Room 235', 'DS-606', 'PSDS', 'Probability and Statistics for Data Science', 'Regular', 'MS-DS', 'MS-DS (1st+2nd+3rd+4th)', '3', ARRAY['Dr. Abdul Jalil'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '18:30-20:00', 'Evening', 'Room 235', 'DS-606', 'PSDS', 'Probability and Statistics for Data Science', 'Regular', 'MS-DS', 'MS-DS (1st+2nd+3rd+4th)', '3', ARRAY['Dr. Abdul Jalil'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '08:35-10:05', 'Morning', 'Room F8', 'PH-110', 'IMW (R)', 'Introduction to Mechanics and Waves', 'Regular', 'BS', 'Semester 2', '3', ARRAY['Dr. Muhammad Shafiq'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '10:15-11:45', 'Morning', 'Room F8', 'PH-110', 'IMW (S)', 'Introduction to Mechanics and Waves', 'Self Support', 'BS', 'Semester 2', '3', ARRAY['Dr. Muhammad Shafiq'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '11:55-13:25', 'Morning', 'Room F8', 'CS-211', 'DS', 'Data Structures', 'Regular', 'BS', 'Semester 3', '3+1', ARRAY['Dr. Rabeeh Ayaz Abbasi'], ARRAY['Ms. Safeena']);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '08:35-10:05', 'Morning', 'Room F6', 'MA-104', 'FLA (R)', 'Fundamentals of Linear Algebra', 'Regular', 'BS', 'Semester 4', '3', ARRAY['Dr. Waseem Siddiqui'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '11:55-13:55', 'Morning', 'Room F6', 'SW-100', 'CCE (R)', 'Civics and Community Engagement', 'Regular', 'BS', 'Semester 4', '2', ARRAY['Dr. Nasreen Kousar'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '08:05-10:05', 'Morning', 'CS Lab', 'CS-121', 'OOP Lab (R+S)', 'Object Oriented Programming Lab', 'Regular & Self Support', 'BS', 'Semester 2', '3+1', ARRAY['Ms. Memoona Afsheen'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '10:15-11:45', 'Morning', 'CS Lab', 'CS-104', 'PSP (R)', 'Problem Solving & Programming', 'Regular', 'BS', 'Semester 1', '3+1', ARRAY['Dr. Ghazanfar Farooq'], ARRAY['Mr. Hammad']);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '11:55-13:25', 'Morning', 'CS Lab', 'CS-455', 'NLP', 'Natural Language Processing', 'Regular & Self Support', 'BS', 'Semester 7 / 8', '3', ARRAY['Dr. Nadia Saeed'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '13:35-15:05', 'Afternoon', 'CS Lab', 'CSC-827', 'SNA', 'Social Network Analysis', 'Regular', 'MPhil / PhD', 'MPhil / PhD', '3', ARRAY['Dr. Rabeeh Ayaz Abbasi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '15:15-16:45', 'Afternoon', 'CS Lab', 'CS-104', 'PSP (R)', 'Problem Solving & Programming', 'Regular', 'BS', 'Semester 1', '3+1', ARRAY['Dr. Ghazanfar Farooq'], ARRAY['Mr. Hammad']);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '08:35-10:05', 'Morning', 'BS Lab', 'CS-104', 'PSP (S)', 'Problem Solving & Programming', 'Self Support', 'BS', 'Semester 1', '3+1', ARRAY['Ms. Memoona Afsheen'], ARRAY['Mr. Abdur Rehman']);
SELECT insert_schedule_entry('Spring 2026', 'Tuesday', '10:15-11:45', 'Morning', 'BS Lab', 'CS-104', 'PSP (S)', 'Problem Solving & Programming', 'Self Support', 'BS', 'Semester 1', '3+1', ARRAY['Ms. Memoona Afsheen'], ARRAY['Mr. Abdur Rehman']);

-- WEDNESDAY ENTRIES (28 entries)
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '08:35-10:05', 'Morning', 'Room 201', 'CS-313', 'CA (S)', 'Computer Architecture', 'Self Support', 'BS', 'Semester 4', '3', ARRAY['Dr. Nadia Saeed'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '10:15-11:45', 'Morning', 'Room 201', 'CS-224', 'DBS (S)', 'Database Systems', 'Self Support', 'BS', 'Semester 4', '3+1', ARRAY['Dr. Shuaib Karim', 'Ms. Fouzia Qureshi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '11:55-13:55', 'Morning', 'Room 201', 'SW-100', 'CCE (S)', 'Civics and Community Engagement', 'Self Support', 'BS', 'Semester 4', '2', ARRAY['Dr. Nasreen Kousar'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '15:15-16:45', 'Afternoon', 'Room 201', 'CS-332', 'NCP', 'Net Centric Programming', 'Self Support', 'BS', 'Semester 7', '3', ARRAY['Dr. Adeel Ur Rehman'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '08:35-10:05', 'Morning', 'Room 217', 'CS-312', 'CCN', 'Computer Communications and Networks', 'Regular', 'BS', 'Semester 6', '3', ARRAY['Dr. Muazzam Khattak'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '10:15-11:45', 'Morning', 'Room 217', 'CS-313', 'CA (R)', 'Computer Architecture', 'Regular', 'BS', 'Semester 4', '3', ARRAY['Ms. Ifrah Farrukh Khan'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '11:55-13:25', 'Morning', 'Room 217', 'CSC-614', 'SQAT', 'Software Quality Assurance and testing', 'Regular', 'MPhil / PhD', 'MPhil 2nd and PhD', '3', ARRAY['Dr. Muddassar Sindhu'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '13:35-15:05', 'Afternoon', 'Room 217', 'CS-222', 'ADSS (R)', 'Analysis and Design for Software Systems', 'Regular', 'BS', 'Semester 4', '3', ARRAY['Dr. Onaiza Maqbool'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '15:15-16:45', 'Afternoon', 'Room 217', 'CS-222', 'ADSS (S)', 'Analysis and Design for Software Systems', 'Self Support', 'BS', 'Semester 4', '3', ARRAY['Dr. Umer Rashid'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '08:35-10:05', 'Morning', 'Room 235', 'CSC-675', 'IRS', 'Information Retrieval Systems', 'Regular', 'MPhil / PhD', 'MPhil / PhD', '3', ARRAY['Dr. Akmal Saeed Khattak'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '10:15-11:45', 'Morning', 'Room 235', 'CS-413', 'IIS', 'Introduction to Information Security', 'Regular', 'BS', 'Semester 8', '3', ARRAY['Dr. Muazzam Khattak'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '11:55-13:25', 'Morning', 'Room 235', 'CS-460', 'DL', 'Deep Learning', 'Regular', 'BS', 'Semester 8', '3', ARRAY['Dr. Ayyaz Hussain'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '17:00-18:30', 'Evening', 'Room 235', 'DSC-675', 'IRS', 'Information Retrieval Systems', 'Regular', 'MS-DS', 'MS-DS (1st+2nd+3rd+4th)', '3', ARRAY['Dr. Umer Rashid'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '18:30-20:00', 'Evening', 'Room 235', 'DSC-675', 'IRS', 'Information Retrieval Systems', 'Regular', 'MS-DS', 'MS-DS (1st+2nd+3rd+4th)', '3', ARRAY['Dr. Umer Rashid'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '08:35-10:05', 'Morning', 'Room F8', 'EN-200', 'EW (R)', 'Expository Writing', 'Regular', 'BS', 'Semester 2', '3', ARRAY['Ms. Tahira Shabir'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '10:15-11:45', 'Morning', 'Room F8', 'EN-200', 'EW (S)', 'Expository Writing', 'Self Support', 'BS', 'Semester 2', '3', ARRAY['Ms. Tahira Shabir'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '11:55-13:25', 'Morning', 'Room F8', 'PH-110', 'IMW (S)', 'Introduction to Mechanics and Waves', 'Self Support', 'BS', 'Semester 2', '3', ARRAY['Dr. Muhammad Shafiq'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '10:15-11:45', 'Morning', 'Room F6', 'MA-202', 'MC (S)', 'Multivariable Calculus', 'Self Support', 'BS', 'Semester 2', '3', ARRAY['Ms. Farwa Haider'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '11:55-13:25', 'Morning', 'Room F6', 'MA-202', 'MC (R)', 'Multivariable Calculus', 'Regular', 'BS', 'Semester 2', '3', ARRAY['Ms. Farwa Haider'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '13:30-15:30', 'Afternoon', 'Room F6', 'IS-100', 'IS (R)', 'Islamic Studies/ Ethics', 'Regular', 'BS', 'Semester 2', '2', ARRAY['Dr. Arshad Qayyum'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '08:35-10:05', 'Morning', 'CS Lab', 'CS-224', 'DBS (R)', 'Database Systems', 'Regular', 'BS', 'Semester 4', '3+1', ARRAY['Dr. Khalid Saleem', 'Ms. Rida Nawaz'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '10:15-11:45', 'Morning', 'CS Lab', 'CS-224', 'DBS (R)', 'Database Systems', 'Regular', 'BS', 'Semester 4', '3+1', ARRAY['Dr. Khalid Saleem', 'Ms. Rida Nawaz'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '13:35-15:05', 'Afternoon', 'CS Lab', 'CS-423', 'CG', 'Computer Graphics', 'Repeaters', 'BS', 'Semester 9 Repeaters', '3', ARRAY['Dr. Ghazanfar Farooq'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '15:15-16:45', 'Afternoon', 'CS Lab', 'CS-483', 'SQA', 'Software Quality Assurance', 'Regular', 'BS', 'Semester 6', '3', ARRAY['Dr. Muddassar Sindhu'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '17:00-18:30', 'Evening', 'CS Lab', 'DSC-838', 'RS', 'Recommender Systems', 'Regular', 'MS-DS', 'MS-DS (1st+2nd+3rd+4th)', '3', ARRAY['Dr. Khalid Saleem'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '18:30-20:00', 'Evening', 'CS Lab', 'DSC-838', 'RS', 'Recommender Systems', 'Regular', 'MS-DS', 'MS-DS (1st+2nd+3rd+4th)', '3', ARRAY['Dr. Khalid Saleem'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '17:00-18:30', 'Evening', 'BS Lab', 'CS-225', 'DBS', 'Database Systems', 'Deficiency', 'Deficiency Courses', 'Deficiency', '3', ARRAY['Dr. Saghir Ahmed'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Wednesday', '18:30-20:00', 'Evening', 'BS Lab', 'CS-225', 'DBS', 'Database Systems', 'Deficiency', 'Deficiency Courses', 'Deficiency', '3', ARRAY['Dr. Saghir Ahmed'], ARRAY[]::TEXT[]);

-- THURSDAY ENTRIES (27 entries)
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '08:35-10:05', 'Morning', 'Room 201', 'CS-425', 'CV', 'Computer Vision', 'Regular', 'BS', 'Semester 6', '3', ARRAY['Dr. S. M. Naqi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '10:15-11:45', 'Morning', 'Room 201', 'CS-104', 'PSP (R)', 'Problem Solving & Programming', 'Regular', 'BS', 'Semester 1', '3+1', ARRAY['Dr. Ghazanfar Farooq'], ARRAY['Mr. Hammad']);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '11:55-13:25', 'Morning', 'Room 201', 'CS-411', 'CC', 'Compiler Construction', 'Self Support', 'BS', 'Semester 7', '3', ARRAY['Dr. Muddassar Sindhu'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '13:35-15:05', 'Afternoon', 'Room 201', 'MA-104', 'FLA (R)', 'Fundamentals of Linear Algebra', 'Regular', 'BS', 'Semester 4', '3', ARRAY['Dr. Waseem Siddiqui'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '08:05-10:05', 'Morning', 'Room 217', 'CS-121', 'OOP Lab (R+S)', 'Object Oriented Programming Lab', 'Regular & Self Support', 'BS', 'Semester 2', '3+1', ARRAY['Ms. Memoona Afsheen'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '10:15-11:45', 'Morning', 'Room 217', 'CS-104', 'PSP (S)', 'Problem Solving & Programming', 'Self Support', 'BS', 'Semester 1', '3+1', ARRAY['Ms. Memoona Afsheen'], ARRAY['Mr. Abdur Rehman']);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '11:55-13:25', 'Morning', 'Room 217', 'MA-104', 'FLA (S)', 'Fundamentals of Linear Algebra', 'Self Support', 'BS', 'Semester 4', '3', ARRAY['Dr. Waseem Siddiqui'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '13:35-15:05', 'Afternoon', 'Room 217', 'CS-224', 'DBS (R)', 'Database Systems', 'Regular', 'BS', 'Semester 4', '3+1', ARRAY['Dr. Khalid Saleem', 'Ms. Rida Nawaz'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '08:35-10:05', 'Morning', 'Room 235', 'CSC-741', 'CV', 'Computer Vision', 'Regular', 'MPhil / PhD', 'MPhil / PhD', '3', ARRAY['Dr. S. M. Naqi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '10:15-11:45', 'Morning', 'Room 235', 'CS-535', 'CD', 'Cloud DevOps', 'Regular', 'BS', 'Semester 8', '3', ARRAY['Mr. Muhammad Tauseef'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '11:55-13:25', 'Morning', 'Room 235', 'CS-535', 'CD', 'Cloud DevOps', 'Regular', 'BS', 'Semester 8', '3', ARRAY['Mr. Muhammad Tauseef'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '13:35-15:05', 'Afternoon', 'Room 235', 'CS-455', 'NLP', 'Natural Language Processing', 'Regular & Self Support', 'BS', 'Semester 7 / 8', '3', ARRAY['Dr. Nadia Saeed'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '15:15-16:45', 'Afternoon', 'Room 235', 'CS-449', 'ICTS', 'ICT and Society', 'Regular', 'BS', 'Semester 8', '3', ARRAY['Dr. Shuaib Karim'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '17:00-18:30', 'Evening', 'Room 235', 'CSC-827', 'SNA', 'Social Network Analysis', 'Regular', 'MPhil / PhD', 'MPhil / PhD', '3', ARRAY['Dr. Rabeeh Ayaz Abbasi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '09:45-11:45', 'Morning', 'Room F8', 'GEN-100', 'ISS (R)', 'Social Sciences', 'Regular', 'BS', 'Semester 2', '2', ARRAY['Dr. Abdul Rasheed'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '13:00-15:00', 'Afternoon', 'Room F8', 'GEN-100', 'ISS (S)', 'Social Sciences', 'Self Support', 'BS', 'Semester 2', '2', ARRAY['Dr. Abdul Rasheed'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '08:35-10:05', 'Morning', 'Room F6', 'MA-202', 'MC (R)', 'Multivariable Calculus', 'Regular', 'BS', 'Semester 2', '3', ARRAY['Ms. Farwa Haider'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '10:15-11:45', 'Morning', 'Room F6', 'MA-202', 'MC (S)', 'Multivariable Calculus', 'Self Support', 'BS', 'Semester 2', '3', ARRAY['Ms. Farwa Haider'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '08:35-10:05', 'Morning', 'BS Lab', 'CS-215', 'COAL', 'Computer Organization and Assembly Language', 'Regular', 'BS', 'Semester 6', '2+1', ARRAY['Ms. Ifrah Farrukh Khan'], ARRAY['Mr. Zain']);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '10:15-11:45', 'Morning', 'BS Lab', 'CS-215', 'COAL', 'Computer Organization and Assembly Language', 'Regular', 'BS', 'Semester 6', '2+1', ARRAY['Ms. Ifrah Farrukh Khan'], ARRAY['Mr. Zain']);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '11:55-13:25', 'Morning', 'BS Lab', 'CS-325', 'ADS', 'Advanced Database Systems', 'Regular', 'BS', 'Semester 6', '2+1', ARRAY['Dr. Khalid Saleem'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '13:35-15:05', 'Afternoon', 'BS Lab', 'CS-325', 'ADS', 'Advanced Database Systems', 'Regular', 'BS', 'Semester 6', '2+1', ARRAY['Dr. Khalid Saleem'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '08:35-10:05', 'Morning', 'CS Lab', 'CS-457', 'WAF', 'Web Application Framework', 'Self Support', 'BS', 'Semester 7', '2+1', ARRAY['Dr. Akmal Saeed Khattak'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '10:15-11:45', 'Morning', 'CS Lab', 'CS-224', 'DBS (S)', 'Database Systems', 'Self Support', 'BS', 'Semester 4', '3+1', ARRAY['Dr. Shuaib Karim', 'Ms. Fouzia Qureshi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '11:55-13:25', 'Morning', 'CS Lab', 'CS-224', 'DBS (S)', 'Database Systems', 'Self Support', 'BS', 'Semester 4', '3+1', ARRAY['Dr. Shuaib Karim', 'Ms. Fouzia Qureshi'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '15:05-17:15', 'Afternoon', 'CS Lab', 'CS-457', 'WAF Lab', 'Web Application Framework Lab', 'Self Support', 'BS', 'Semester 7', '2+1', ARRAY['Dr. Akmal Saeed Khattak'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Thursday', '15:15-16:45', 'Afternoon', 'CS Lab', 'CS-211', 'DS', 'Data Structures', 'Regular', 'BS', 'Semester 3', '3+1', ARRAY['Dr. Rabeeh Ayaz Abbasi'], ARRAY['Ms. Safeena']);

-- FRIDAY ENTRIES (7 entries)
SELECT insert_schedule_entry('Spring 2026', 'Friday', '08:35-10:05', 'Morning', 'Room 201', 'CS-423', 'CG', 'Computer Graphics', 'Repeaters', 'BS', 'Semester 9 Repeaters', '3', ARRAY['Dr. Ghazanfar Farooq'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Friday', '10:00-13:00', 'Morning', 'Room 217', 'FQ-102', 'FQ-102 (R)', 'Understanding Quran II', 'Regular', 'BS', 'Semester 2', '0+1', ARRAY['Mr. Abdul Wahid'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Friday', '14:00-17:00', 'Afternoon', 'Room 217', 'FQ-102 / FQ-602', 'FQ-102 (S) / FQ-602', 'Understanding Quran II', 'Self Support & Graduate', 'BS & MPhil/PhD', 'BS Sem 2 / MPhil-PhD', '0+1', ARRAY['Mr. Abdul Wahid'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Friday', '08:35-10:05', 'Morning', 'Online', 'EN-200', 'EW (R)', 'Expository Writing', 'Regular', 'BS', 'Semester 2', '3', ARRAY['Ms. Tahira Shabir'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Friday', '10:15-11:45', 'Morning', 'Online', 'EN-200', 'EW (S)', 'Expository Writing', 'Self Support', 'BS', 'Semester 2', '3', ARRAY['Ms. Tahira Shabir'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Friday', '17:00-18:30', 'Evening', 'Online', 'CS-105', 'PSP', 'Problem Solving and Programming', 'Deficiency', 'Deficiency Courses', 'Deficiency', '3', ARRAY['Dr. Ayyaz Hussain'], ARRAY[]::TEXT[]);
SELECT insert_schedule_entry('Spring 2026', 'Friday', '18:30-20:00', 'Evening', 'Online', 'CS-105', 'PSP', 'Problem Solving and Programming', 'Deficiency', 'Deficiency Courses', 'Deficiency', '3', ARRAY['Dr. Ayyaz Hussain'], ARRAY[]::TEXT[]);

-- Drop the helper function after use
DROP FUNCTION IF EXISTS insert_schedule_entry(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, TEXT[], TEXT[]);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

DO $$
DECLARE
    v_session_count INT;
    v_instructor_count INT;
    v_ta_count INT;
    v_schedule_count INT;
BEGIN
    SELECT COUNT(*) INTO v_session_count FROM academic_sessions WHERE session_name = 'Spring 2026';
    SELECT COUNT(*) INTO v_instructor_count FROM instructors WHERE is_active = true;
    SELECT COUNT(*) INTO v_ta_count FROM teaching_assistants WHERE is_active = true;
    SELECT COUNT(*) INTO v_schedule_count FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        WHERE asess.session_name = 'Spring 2026' AND cs.is_active = true;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ SPRING 2026 TIMETABLE SEEDED';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Academic Sessions: %', v_session_count;
    RAISE NOTICE 'Active Instructors: %', v_instructor_count;
    RAISE NOTICE 'Active Teaching Assistants: %', v_ta_count;
    RAISE NOTICE 'Schedule Entries: %', v_schedule_count;
    RAISE NOTICE '========================================';
END $$;

-- Show sample data by day
SELECT 
    day_of_week, 
    COUNT(*) as entry_count
FROM v_current_timetable
GROUP BY day_of_week
ORDER BY 
    CASE day_of_week
        WHEN 'Monday' THEN 1
        WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5
    END;

-- Show Monday schedule sample
SELECT 
    time_slot, 
    course_code, 
    course_name, 
    room,
    program,
    instructors
FROM v_current_timetable
WHERE day_of_week = 'Monday'
ORDER BY time_slot
LIMIT 10;

