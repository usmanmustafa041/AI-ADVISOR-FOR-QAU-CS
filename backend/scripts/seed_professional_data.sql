-- ============================================================================
-- PROFESSIONAL DATA SEED FOR QAU CS ACADEMIC ADVISOR
-- ============================================================================
-- This script populates Courses, Fees, Timetable, and Policies pages
-- with comprehensive professional data from official QAU CS documents
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: CREATE ADDITIONAL REQUIRED TABLES
-- ============================================================================

-- Academic terms (semesters)
CREATE TABLE IF NOT EXISTS academic_terms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term VARCHAR(20) NOT NULL CHECK (term IN ('Spring', 'Fall', 'Summer')),
    academic_year INT NOT NULL,
    starts_on DATE,
    ends_on DATE,
    active BOOLEAN DEFAULT FALSE,
    UNIQUE(term, academic_year)
);

-- Course offerings (specific instance of a course in a term)
CREATE TABLE IF NOT EXISTS course_offerings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    term_id UUID REFERENCES academic_terms(id) ON DELETE CASCADE,
    section VARCHAR(10) DEFAULT 'A',
    instructor TEXT,
    max_enrollment INT DEFAULT 60,
    UNIQUE(course_id, term_id, section)
);

-- Timetable entries
CREATE TABLE IF NOT EXISTS timetable_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offering_id UUID REFERENCES course_offerings(id) ON DELETE CASCADE,
    session_type VARCHAR(20) CHECK (session_type IN ('class', 'lab', 'tutorial')),
    day_of_week INT CHECK (day_of_week BETWEEN 1 AND 7),
    starts_at TIME NOT NULL,
    ends_at TIME NOT NULL,
    room VARCHAR(20),
    lab_group VARCHAR(10)
);

-- Academic rules and policies
CREATE TABLE IF NOT EXISTS academic_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code VARCHAR(50) UNIQUE NOT NULL,
    category VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,
    priority INT DEFAULT 100,
    source_id UUID REFERENCES source_records(id),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- STEP 2: INSERT COURSES (BSCS Scheme 2025 - All 8 Semesters)
-- ============================================================================

-- Get default source ID
DO $$
DECLARE
    default_source_id UUID;
BEGIN
    SELECT id INTO default_source_id FROM source_records WHERE source_code = 'DEFAULT';
    
    -- Semester 1 Courses
    INSERT INTO courses (code, title, description, theory_credit_hours, lab_credit_hours, source_id, active) VALUES
    ('EN-100', 'Functional English', 'Development of English language proficiency for academic and professional communication.', 3.0, 0.0, default_source_id, true),
    ('PK-100', 'Ideology & Constitution of Pakistan', 'Study of Pakistan''s ideological foundations and constitutional framework.', 2.0, 0.0, default_source_id, true),
    ('MA-101', 'Calculus & Analytical Geometry', 'Fundamental concepts of calculus and analytical geometry.', 3.0, 0.0, default_source_id, true),
    ('CSC-110', 'Applications of ICT', 'Introduction to Information and Communication Technology applications.', 2.0, 1.0, default_source_id, true),
    ('FQ-101', 'Understanding Quran-I', 'Introduction to Quranic studies and Islamic teachings.', 0.0, 1.0, default_source_id, true),
    ('CSC-104', 'Problem Solving & Programming', 'Introduction to programming logic and problem-solving techniques using C/C++.', 3.0, 1.0, default_source_id, true),
    
    -- Semester 2 Courses
    ('EN-200', 'Expository Writing', 'Advanced writing skills for academic and technical documentation.', 3.0, 0.0, default_source_id, true),
    ('IS-100', 'Islamic Studies/Ethics', 'Study of Islamic principles and ethical frameworks.', 2.0, 0.0, default_source_id, true),
    ('PH-110', 'Introductory Mechanics and Waves', 'Basic principles of classical mechanics and wave phenomena.', 3.0, 0.0, default_source_id, true),
    ('FQ-102', 'Understanding Quran-II', 'Advanced Quranic studies and interpretation.', 0.0, 1.0, default_source_id, true),
    ('MA-202', 'Multivariable Calculus', 'Calculus of functions with multiple variables.', 3.0, 0.0, default_source_id, true),
    ('CSC-121', 'Object Oriented Programming', 'Object-oriented programming concepts using Java or C++.', 3.0, 1.0, default_source_id, true),
    
    -- Semester 3 Courses
    ('MA-203', 'Discrete Mathematics', 'Mathematical structures and discrete systems for computer science.', 3.0, 0.0, default_source_id, true),
    ('EN-299', 'Technical and Business Writing', 'Professional technical and business communication skills.', 3.0, 0.0, default_source_id, true),
    ('CSC-103', 'Introduction to Computer Organization', 'Basic computer organization and digital logic design.', 3.0, 0.0, default_source_id, true),
    ('CSC-211', 'Data Structures', 'Implementation and analysis of fundamental data structures.', 3.0, 1.0, default_source_id, true),
    ('CSC-212', 'Human Computer Interaction', 'Principles of user interface design and usability.', 3.0, 0.0, default_source_id, true),
    
    -- Semester 4 Courses
    ('SW-100', 'Civics and Community Engagement', 'Civic responsibility and community participation.', 2.0, 0.0, default_source_id, true),
    ('PS-101', 'Pakistan Studies', 'Comprehensive study of Pakistan''s history, geography, and culture.', 2.0, 0.0, default_source_id, true),
    ('MA-104', 'Fundamentals of Linear Algebra', 'Vector spaces, matrices, and linear transformations.', 3.0, 0.0, default_source_id, true),
    ('CSC-222', 'Analysis & Design of Software Systems', 'Software engineering principles and system design methodologies.', 3.0, 0.0, default_source_id, true),
    ('CSC-224', 'Database Systems', 'Database design, SQL, and database management concepts.', 3.0, 1.0, default_source_id, true),
    ('CSC-313', 'Computer Architecture', 'Advanced computer architecture including pipelining and memory hierarchy.', 3.0, 0.0, default_source_id, true),
    
    -- Semester 5 Courses
    ('ST-101', 'Probability and Statistics', 'Probability theory and statistical methods for data analysis.', 3.0, 0.0, default_source_id, true),
    ('CSC-322', 'Software Construction', 'Software development methodologies and best practices.', 2.0, 1.0, default_source_id, true),
    ('CSC-226', 'Operating Systems', 'Operating system concepts including process management and memory management.', 2.0, 1.0, default_source_id, true),
    ('CSC-311', 'Analysis & Design of Algorithms', 'Algorithm design techniques and complexity analysis.', 3.0, 0.0, default_source_id, true),
    ('CSC-414', 'Artificial Intelligence', 'Introduction to AI including search algorithms, knowledge representation, and machine learning.', 3.0, 0.0, default_source_id, true),
    
    -- Semester 6 Courses
    ('CSC-331', 'Theory of Automata', 'Formal languages, automata theory, and computational complexity.', 3.0, 0.0, default_source_id, true),
    ('CSC-325', 'Advanced Database Systems', 'Advanced database concepts including distributed databases and NoSQL.', 2.0, 1.0, default_source_id, true),
    ('CSC-215', 'Computer Organization & Assembly Language', 'Assembly language programming and computer organization.', 2.0, 1.0, default_source_id, true),
    ('CSC-312', 'Computer Communications & Networks', 'Network protocols, architectures, and communication systems.', 3.0, 0.0, default_source_id, true),
    
    -- Semester 7 Courses
    ('MS-100', 'Entrepreneurship', 'Business creation and entrepreneurial mindset development.', 2.0, 0.0, default_source_id, true),
    ('CSC-411', 'Compiler Construction', 'Compiler design and implementation techniques.', 3.0, 0.0, default_source_id, true),
    ('CSC-489', 'Project-I', 'First phase of final year project including proposal and design.', 2.0, 0.0, default_source_id, true),
    
    -- Semester 8 Courses
    ('CSC-412', 'Introduction to Cyber Security', 'Fundamentals of cybersecurity, cryptography, and network security.', 3.0, 0.0, default_source_id, true),
    ('CSC-490', 'Project-II', 'Final phase of project including implementation, testing, and documentation.', 4.0, 0.0, default_source_id, true),
    
    -- Common Elective Courses
    ('CSC-324', 'Web Application Development', 'Modern web development using frameworks and best practices.', 2.0, 1.0, default_source_id, true),
    ('CSC-442', 'Mobile Application Development', 'Mobile app development for Android and iOS platforms.', 2.0, 1.0, default_source_id, true),
    ('CSC-458', 'Data Mining', 'Data mining techniques and knowledge discovery in databases.', 3.0, 0.0, default_source_id, true),
    ('CSC-459', 'Machine Learning', 'Machine learning algorithms and applications.', 3.0, 0.0, default_source_id, true),
    ('CSC-462', 'Cyber Security', 'Advanced cybersecurity concepts and practices.', 3.0, 0.0, default_source_id, true),
    ('CSC-455', 'Natural Language Processing', 'Computational processing of human languages.', 3.0, 0.0, default_source_id, true),
    ('CSC-445', 'Information Systems', 'Enterprise information systems and business intelligence.', 3.0, 0.0, default_source_id, true),
    ('CSC-456', 'Web Services', 'RESTful APIs and web service architectures.', 2.0, 1.0, default_source_id, true),
    ('CSC-482', 'Web Engineering', 'Advanced web engineering principles and frameworks.', 3.0, 0.0, default_source_id, true),
    ('CSC-474', 'Software Testing', 'Software testing methodologies and quality assurance.', 3.0, 0.0, default_source_id, true),
    ('CSC-484', 'Software Engineering', 'Advanced software engineering practices and project management.', 3.0, 0.0, default_source_id, true)
    
    ON CONFLICT (code) DO UPDATE SET
        title = EXCLUDED.title,
        description = EXCLUDED.description,
        theory_credit_hours = EXCLUDED.theory_credit_hours,
        lab_credit_hours = EXCLUDED.lab_credit_hours;
END $$;

-- ============================================================================
-- STEP 3: INSERT FEE STRUCTURES (Fall 2025 - National Students)
-- ============================================================================

DO $$
DECLARE
    bscs_program_id UUID;
    default_source_id UUID;
BEGIN
    SELECT id INTO bscs_program_id FROM programs WHERE code = 'BSCS';
    SELECT id INTO default_source_id FROM source_records WHERE source_code = 'DEFAULT';
    
    -- BSCS Regular Basis Fees
    INSERT INTO fee_structures (program_id, official_fee_category, shift, fee_type, amount, currency, effective_from, source_id) VALUES
    (bscs_program_id, 'Tuition Fee', 'Regular', 'Per Semester', 96320.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Admission Processing Fee', 'Regular', 'One Time', 2860.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Security Deposit', 'Regular', 'One Time (Refundable)', 5000.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Prospectus Fee', 'Regular', 'One Time', 500.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Student Activity Fee', 'Regular', 'One Time', 2000.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Medical Fee', 'Regular', 'One Time', 1000.00, 'PKR', '2025-09-01', default_source_id),
    
    -- BSCS Self-Finance Fees
    (bscs_program_id, 'Tuition Fee', 'Self-Finance', 'Per Semester', 165230.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Admission Processing Fee', 'Self-Finance', 'One Time', 2860.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Security Deposit', 'Self-Finance', 'One Time (Refundable)', 5000.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Prospectus Fee', 'Self-Finance', 'One Time', 500.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Student Activity Fee', 'Self-Finance', 'One Time', 2000.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Medical Fee', 'Self-Finance', 'One Time', 1000.00, 'PKR', '2025-09-01', default_source_id),
    
    -- Additional Fees (Both)
    (bscs_program_id, 'Summer Course Fee', 'Regular', 'Per Course', 9880.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Summer Course Fee', 'Self-Finance', 'Per Course', 10760.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Re-examination Fee', 'Regular', 'Per Course', 2830.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Degree Fee (20 days)', 'Regular', 'One Time', 6300.00, 'PKR', '2025-09-01', default_source_id),
    (bscs_program_id, 'Urgent Degree Fee (5 days)', 'Regular', 'One Time', 12590.00, 'PKR', '2025-09-01', default_source_id)
    
    ON CONFLICT DO NOTHING;
END $$;

-- ============================================================================
-- STEP 4: INSERT ACADEMIC TERM (Spring 2026)
-- ============================================================================

INSERT INTO academic_terms (term, academic_year, starts_on, ends_on, active) VALUES
('Spring', 2026, '2026-02-01', '2026-06-30', true)
ON CONFLICT (term, academic_year) DO UPDATE SET active = EXCLUDED.active;

-- ============================================================================
-- STEP 5: INSERT TIMETABLE DATA (Spring 2026 - Sample from 6th Semester)
-- ============================================================================

DO $$
DECLARE
    spring_2026_id UUID;
    default_source_id UUID;
    
    -- Course IDs
    cs224_id UUID;
    cs226_id UUID;
    cs311_id UUID;
    cs312_id UUID;
    cs325_id UUID;
    cs425_id UUID := NULL; -- May not exist
    
    -- Offering IDs
    cs224_offering UUID;
    cs226_offering UUID;
    cs311_offering UUID;
    cs312_offering UUID;
    cs325_offering UUID;
BEGIN
    SELECT id INTO spring_2026_id FROM academic_terms WHERE term = 'Spring' AND academic_year = 2026;
    SELECT id INTO default_source_id FROM source_records WHERE source_code = 'DEFAULT';
    
    -- Get course IDs
    SELECT id INTO cs224_id FROM courses WHERE code = 'CSC-224';
    SELECT id INTO cs226_id FROM courses WHERE code = 'CSC-226';
    SELECT id INTO cs311_id FROM courses WHERE code = 'CSC-311';
    SELECT id INTO cs312_id FROM courses WHERE code = 'CSC-312';
    SELECT id INTO cs325_id FROM courses WHERE code = 'CSC-325';
    
    -- Create course offerings
    INSERT INTO course_offerings (course_id, term_id, section, instructor) VALUES
    (cs224_id, spring_2026_id, 'R', 'Dr. Shuaib Karim') RETURNING id INTO cs224_offering;
    
    INSERT INTO course_offerings (course_id, term_id, section, instructor) VALUES
    (cs224_id, spring_2026_id, 'S', 'Ms. Fouzia Qureshi') RETURNING id INTO cs224_offering;
    
    INSERT INTO course_offerings (course_id, term_id, section, instructor) VALUES
    (cs226_id, spring_2026_id, 'R', 'Dr. Muhammad Naeem') RETURNING id INTO cs226_offering;
    
    INSERT INTO course_offerings (course_id, term_id, section, instructor) VALUES
    (cs311_id, spring_2026_id, 'R', 'Dr. Zahid Halim') RETURNING id INTO cs311_offering;
    
    INSERT INTO course_offerings (course_id, term_id, section, instructor) VALUES
    (cs312_id, spring_2026_id, 'R', 'Dr. Kashif Kifayat') RETURNING id INTO cs312_offering;
    
    INSERT INTO course_offerings (course_id, term_id, section, instructor) VALUES
    (cs325_id, spring_2026_id, 'S', 'Dr. Adnan Abid') RETURNING id INTO cs325_offering;
    
    -- Insert timetable entries for Monday
    INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room) VALUES
    (cs224_offering, 'class', 1, '10:15:00', '11:45:00', '217'),
    (cs311_offering, 'class', 1, '08:35:00', '10:05:00', '201'),
    (cs312_offering, 'class', 1, '13:35:00', '15:05:00', '235');
    
    -- Insert timetable entries for Tuesday
    INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room) VALUES
    (cs226_offering, 'class', 2, '11:55:00', '13:25:00', 'F8'),
    (cs325_offering, 'class', 2, '15:15:00', '16:45:00', 'F6');
    
    -- Insert timetable entries for Wednesday
    INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room) VALUES
    (cs224_offering, 'class', 3, '10:15:00', '11:45:00', '217'),
    (cs311_offering, 'lab', 3, '14:00:00', '17:00:00', 'CS Lab');
    
    -- Insert timetable entries for Thursday
    INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room) VALUES
    (cs312_offering, 'lab', 4, '14:00:00', '17:00:00', 'BS Lab'),
    (cs226_offering, 'class', 4, '11:55:00', '13:25:00', 'F8');
    
    -- Insert timetable entries for Friday
    INSERT INTO timetable_entries (offering_id, session_type, day_of_week, starts_at, ends_at, room) VALUES
    (cs224_offering, 'lab', 5, '14:00:00', '17:00:00', 'CS Lab'),
    (cs325_offering, 'lab', 5, '14:00:00', '17:00:00', 'BS Lab');
    
END $$;

-- ============================================================================
-- STEP 6: INSERT ACADEMIC POLICIES & RULES
-- ============================================================================

DO $$
DECLARE
    default_source_id UUID;
BEGIN
    SELECT id INTO default_source_id FROM source_records WHERE source_code = 'DEFAULT';
    
    INSERT INTO academic_rules (rule_code, category, title, description, effective_from, priority, source_id, active) VALUES
    
    -- Attendance Policies
    ('ATT-001', 'attendance', '75% Attendance Requirement', 'Students must maintain at least 75% attendance in each course to be eligible to appear in final examinations. Failure to meet this requirement will result in an "F" grade.', '2025-09-01', 10, default_source_id, true),
    ('ATT-002', 'attendance', 'Medical Leave Policy', 'Medical leave will be granted only on submission of a medical certificate from a recognized hospital or medical practitioner. Maximum 10 days of medical leave can be granted per semester.', '2025-09-01', 20, default_source_id, true),
    
    -- Examination Policies
    ('EXAM-001', 'examination', 'Examination Eligibility', 'Students must clear all outstanding dues and maintain required attendance to be eligible for examinations. No student will be allowed to sit in exams without proper eligibility.', '2025-09-01', 10, default_source_id, true),
    ('EXAM-002', 'examination', 'Mid-Term Examination', 'Mid-term examination carries 30% weightage and is mandatory. Students missing mid-term without valid reason will receive zero marks.', '2025-09-01', 20, default_source_id, true),
    ('EXAM-003', 'examination', 'Final Examination', 'Final examination carries 50% weightage. Students must score at least 40% in final exam to pass the course, regardless of total marks.', '2025-09-01', 15, default_source_id, true),
    ('EXAM-004', 'examination', 'Retake Policy', 'Students failing a course can retake it in the next available semester. Maximum 2 retakes are allowed. Retake fee will apply.', '2025-09-01', 25, default_source_id, true),
    
    -- Grading Policies
    ('GRADE-001', 'grading', 'Grading Criteria', 'Grading is based on: Quizzes/Assignments (20%), Mid-term (30%), Final Exam (50%). Total 100 marks are distributed across these components.', '2025-09-01', 10, default_source_id, true),
    ('GRADE-002', 'grading', 'Grade Scale', 'A (85-100), B+ (80-84), B (75-79), C+ (70-74), C (65-69), D+ (60-64), D (50-59), F (below 50). Minimum passing grade is D (50%).', '2025-09-01', 11, default_source_id, true),
    ('GRADE-003', 'grading', 'CGPA Calculation', 'CGPA is calculated as weighted average of grade points. A=4.0, B+=3.5, B=3.0, C+=2.5, C=2.0, D+=1.5, D=1.0, F=0.0', '2025-09-01', 12, default_source_id, true),
    ('GRADE-004', 'grading', 'Minimum CGPA Requirement', 'Students must maintain minimum CGPA of 2.0 to remain in good academic standing. CGPA below 2.0 results in academic probation.', '2025-09-01', 13, default_source_id, true),
    
    -- Registration Policies
    ('REG-001', 'registration', 'Course Registration Period', 'Course registration is open for 2 weeks at the start of each semester. Late registration is subject to penalty fee of Rs. 5,000.', '2025-09-01', 10, default_source_id, true),
    ('REG-002', 'registration', 'Credit Hour Limits', 'Regular students: 15-18 credit hours per semester. Minimum 12 credits required for full-time status. Maximum 21 credits allowed with HOD permission.', '2025-09-01', 15, default_source_id, true),
    ('REG-003', 'registration', 'Course Prerequisites', 'Students must complete all prerequisite courses before registering for advanced courses. System will automatically block registration if prerequisites are not met.', '2025-09-01', 20, default_source_id, true),
    ('REG-004', 'registration', 'Add/Drop Period', 'Add/Drop period is 1 week from semester start. No courses can be added after this period. Course can be dropped until mid-term with "W" grade.', '2025-09-01', 25, default_source_id, true),
    
    -- Academic Probation
    ('PROB-001', 'probation', 'Probation Criteria', 'Students with CGPA below 2.0 will be placed on academic probation. Probation status requires academic counseling and limits course load to 12 credit hours.', '2025-09-01', 10, default_source_id, true),
    ('PROB-002', 'probation', 'Probation Period', 'Students have maximum 2 consecutive semesters to improve CGPA above 2.0. Failure to do so may result in dismissal from the program.', '2025-09-01', 15, default_source_id, true),
    
    -- Final Year Project
    ('FYP-001', 'fyp', 'FYP Eligibility', 'Students must complete at least 100 credit hours and maintain CGPA above 2.5 to register for FYP. FYP spans two semesters (6 credit hours total).', '2025-09-01', 10, default_source_id, true),
    ('FYP-002', 'fyp', 'FYP Supervision', 'Each FYP group (max 3 students) must have an assigned faculty supervisor. Monthly progress reports are mandatory.', '2025-09-01', 15, default_source_id, true),
    ('FYP-003', 'fyp', 'FYP Evaluation', 'FYP is evaluated by: Supervisor (40%), External Examiner (30%), Internal Committee (30%). Final presentation and working prototype are mandatory.', '2025-09-01', 20, default_source_id, true),
    ('FYP-004', 'fyp', 'Plagiarism Check', 'All FYP reports must pass Turnitin plagiarism check with similarity index below 20%. Reports with higher similarity will be rejected.', '2025-09-01', 25, default_source_id, true),
    
    -- Conduct & Discipline
    ('DISC-001', 'discipline', 'Code of Conduct', 'Students must maintain professional and ethical conduct at all times. Violations include: cheating, plagiarism, misconduct, or disrespecting faculty.', '2025-09-01', 10, default_source_id, true),
    ('DISC-002', 'discipline', 'Plagiarism Policy', 'Plagiarism is strictly prohibited. First offense: F grade in course. Second offense: Dismissal from program. Zero tolerance for intentional plagiarism.', '2025-09-01', 15, default_source_id, true),
    ('DISC-003', 'discipline', 'Examination Misconduct', 'Any form of cheating in exams results in: First offense: F grade. Second offense: Dismissal. Using unauthorized material or helping others is considered cheating.', '2025-09-01', 20, default_source_id, true),
    
    -- Degree Completion
    ('DEG-001', 'degree', 'Degree Requirements', 'To graduate, students must: Complete 134 credit hours, maintain minimum CGPA 2.0, complete FYP, clear all dues, and complete mandatory internship (6-8 weeks).', '2025-09-01', 10, default_source_id, true),
    ('DEG-002', 'degree', 'Maximum Duration', 'BSCS degree must be completed within 6 years (12 semesters) from enrollment. Extensions beyond this require special approval from Academic Council.', '2025-09-01', 15, default_source_id, true),
    ('DEG-003', 'degree', 'Degree Classification', 'First Class: CGPA 3.5-4.0, Second Class: CGPA 3.0-3.49, Third Class: CGPA 2.0-2.99. Students with CGPA below 2.0 will not graduate.', '2025-09-01', 20, default_source_id, true)
    
    ON CONFLICT (rule_code) DO UPDATE SET
        title = EXCLUDED.title,
        description = EXCLUDED.description,
        priority = EXCLUDED.priority;
END $$;

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

SELECT 'Courses seeded: ' || COUNT(*)::TEXT FROM courses;
SELECT 'Fee structures seeded: ' || COUNT(*)::TEXT FROM fee_structures;
SELECT 'Academic rules seeded: ' || COUNT(*)::TEXT FROM academic_rules;
SELECT 'Timetable entries seeded: ' || COUNT(*)::TEXT FROM timetable_entries;

SELECT '✅ Professional data seeding complete!' AS status;
