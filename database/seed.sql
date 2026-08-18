BEGIN;

-- Step 3 contains only facts present in the Phase 1 public-source data pack.
-- Missing operational datasets are intentionally not fabricated.

INSERT INTO source_records
    (source_code, title, category, authority, source_url, local_path, effective_from,
     last_verified_at, verification_status, is_time_sensitive, notes)
VALUES
    ('SRC-PACK-001', 'Phase 1 Official Data Pack', 'research_pack',
     'Compiled from official QAU public sources', NULL,
     'QAU_CS_Academic_Advisor_Phase1_Official_Data_Pack.docx', '2026-08-11',
     '2026-08-11 00:00:00+05', 'verified', FALSE,
     'Compilation and provenance map; not itself an official QAU regulation'),
    ('SRC-BS-SCHEME-2025', 'BSCS Scheme of Study for Fall 2025 onward', 'curriculum',
     'QAU Computer Science Department', 'https://cs.qau.edu.pk/doc/scheme-2025.pdf',
     NULL, '2025-09-01', '2026-08-11 00:00:00+05', 'verified', FALSE,
     'Specific 134-credit scheme takes precedence over older 130-credit webpage text'),
    ('SRC-BS-PAGE', 'BS Computer Science programme and electives', 'programme',
     'QAU Computer Science Department', 'https://cs.qau.edu.pk/Bs.php', NULL,
     NULL, '2026-08-11 00:00:00+05', 'verified', FALSE, NULL),
    ('SRC-BS-RULES', 'Rules and Regulations relating to BS Program', 'academic_policy',
     'Quaid-i-Azam University',
     'https://qau.edu.pk/rules-regulations-relating-to-bs-program-morning-evening/',
     NULL, NULL, '2026-08-11 00:00:00+05', 'verified', FALSE, NULL),
    ('SRC-CS-PROGRAMMES', 'QAU CS programme pages', 'programme',
     'QAU Computer Science Department', 'https://cs.qau.edu.pk/', NULL,
     NULL, '2026-08-11 00:00:00+05', 'verified', FALSE,
     'Programme structures cross-referenced with individual official programme pages'),
    ('SRC-FEES-F2025', 'QAU national student fee tables effective Fall 2025', 'fees',
     'Quaid-i-Azam University', 'https://qau.edu.pk/bachelor-fee-structure/', NULL,
     '2025-09-01', '2026-08-11 00:00:00+05', 'verified', TRUE,
     'Amounts require re-verification before use for a later semester')
ON CONFLICT (source_code) DO NOTHING;

INSERT INTO programs
    (code, name, level, study_mode, normal_semesters, maximum_semesters,
     minimum_cgpa, source_id)
VALUES
    ('BSCS', 'BS Computer Science', 'BS', 'Morning/Regular and Self-Support/Evening', 8, 12, 2.00,
     (SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('MPHIL-CS', 'MPhil Computer Science', 'MPhil', 'Full-time', 4, 6, 2.50,
     (SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ('MS-IST', 'MS Information Science and Technology', 'MS', 'Evening', NULL, NULL, NULL,
     (SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ('MS-DS', 'MS Data Science', 'MS', 'Evening/Part-time oriented', NULL, NULL, NULL,
     (SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ('PHD-CS', 'PhD Computer Science', 'PhD', 'Full-time', 6, 14, 3.00,
     (SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES'))
ON CONFLICT (code) DO NOTHING;

INSERT INTO curriculum_schemes
    (program_id, name, effective_from, total_credit_hours,
     minimum_semester_credits, maximum_semester_credits, source_id)
VALUES
    ((SELECT id FROM programs WHERE code='BSCS'), 'Fall 2025 onward', '2025-09-01', 134, 15, 18,
     (SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ((SELECT id FROM programs WHERE code='MPHIL-CS'), 'Public programme structure verified 2026', '2026-08-11', 50, NULL, NULL,
     (SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ((SELECT id FROM programs WHERE code='MS-IST'), 'Public programme structure verified 2026', '2026-08-11', 30, NULL, NULL,
     (SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ((SELECT id FROM programs WHERE code='MS-DS'), 'Public programme structure verified 2026', '2026-08-11', 30, NULL, NULL,
     (SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ((SELECT id FROM programs WHERE code='PHD-CS'), 'Current coursework structure verified 2026', '2026-08-11', 18, NULL, NULL,
     (SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES'))
ON CONFLICT (program_id, name) DO NOTHING;

INSERT INTO courses
    (code, title, theory_credit_hours, lab_credit_hours, source_id)
VALUES
    ('EN-100','Functional English',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('PK-100','Ideology and Constitution of Pakistan',2,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('MA-101','Calculus and Analytical Geometry',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-110','Applications of ICT',2,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('FQ-101','Understanding Quran-I',0,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-104','Problem Solving and Programming',3,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('EN-200','Expository Writing',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('IS-100','Islamic Studies / Ethics',2,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('PH-110','Introductory Mechanics and Waves',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('FQ-102','Understanding Quran-II',0,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('MA-202','Multivariable Calculus',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-121','Object Oriented Programming',3,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('MA-203','Discrete Mathematics',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('PS-101','Pakistan Studies',2,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('EN-299','Technical and Business Writing',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-103','Introduction to Computer Organization',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-211','Data Structures',3,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-212','Human Computer Interaction',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('SW-100','Civics and Community Engagement',2,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('MA-104','Fundamentals of Linear Algebra',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-222','Analysis and Design of Software Systems',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-224','Database Systems',3,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-313','Computer Architecture',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('ST-101','Probability and Statistics',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-322','Software Construction',2,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-226','Operating Systems',2,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-311','Analysis and Design of Algorithms',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-414','Artificial Intelligence',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-331','Theory of Automata',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-325','Advanced Database Systems',2,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-215','Computer Organization and Assembly Language',2,1,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-312','Computer Communications and Networks',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('MS-100','Entrepreneurship',2,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-411','Compiler Construction',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-489','Project-I',2,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-412','Introduction to Cyber Security',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-490','Project-II',4,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')),
    ('CSC-483','Software Quality Assurance',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-PAGE')),
    ('CSC-486','Software Project Management',3,0,(SELECT id FROM source_records WHERE source_code='SRC-BS-PAGE')),
    ('CSC-652','Advanced Analysis of Algorithms',3,0,(SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ('CSC-702','Advanced Operating Systems',3,0,(SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ('IST-611','Human and Information Interaction',3,0,(SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ('IST-631','Web Services',3,0,(SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ('DSC-605','Programming for Data Science',3,0,(SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES')),
    ('DSC-606','Probability and Statistics for Data Science',3,0,(SELECT id FROM source_records WHERE source_code='SRC-CS-PROGRAMMES'))
ON CONFLICT (code) DO NOTHING;

-- Map coded BSCS courses to their official semesters/categories.
WITH scheme AS (SELECT id FROM curriculum_schemes WHERE name='Fall 2025 onward')
INSERT INTO curriculum_courses (curriculum_id, course_id, semester_number, requirement_type, display_order)
SELECT scheme.id, c.id, v.semester_no, v.req_type, v.ord
FROM scheme
CROSS JOIN (VALUES
 ('EN-100',1,'general',1),('PK-100',1,'general',2),('MA-101',1,'general',3),('CSC-110',1,'general',4),('FQ-101',1,'general',5),('CSC-104',1,'core',6),
 ('EN-200',2,'general',1),('IS-100',2,'general',2),('PH-110',2,'general',4),('FQ-102',2,'general',5),('MA-202',2,'supporting',6),('CSC-121',2,'core',7),
 ('MA-203',3,'general',1),('EN-299',3,'supporting',2),('CSC-103',3,'core',3),('CSC-211',3,'core',4),('CSC-212',3,'core',5),
 ('SW-100',4,'general',1),('PS-101',4,'general',2),('MA-104',4,'supporting',3),('CSC-222',4,'core',4),('CSC-224',4,'core',5),('CSC-313',4,'core',6),
 ('ST-101',5,'supporting',1),('CSC-322',5,'core',2),('CSC-226',5,'core',3),('CSC-311',5,'core',4),('CSC-414',5,'core',5),
 ('CSC-331',6,'core',1),('CSC-325',6,'core',2),('CSC-215',6,'core',3),('CSC-312',6,'core',4),
 ('MS-100',7,'general',1),('CSC-411',7,'core',3),('CSC-489',7,'project',4),
 ('CSC-412',8,'core',2),('CSC-490',8,'project',3)
) AS v(code,semester_no,req_type,ord)
JOIN courses c ON c.code=v.code
ON CONFLICT (curriculum_id, course_id) DO NOTHING;

WITH scheme AS (SELECT id FROM curriculum_schemes WHERE name='Fall 2025 onward'),
src AS (SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')
INSERT INTO curriculum_slots
    (curriculum_id, semester_number, title, requirement_type, credit_hours, display_order, source_id)
SELECT scheme.id, v.semester_no, v.title, v.req_type, v.credits, v.ord, src.id
FROM scheme, src
CROSS JOIN (VALUES
 (2,'Social Sciences Elective','general',2.0,3),
 (5,'Domain Elective 1','elective',3.0,6),
 (6,'Domain Elective 2','elective',3.0,5),(6,'Domain Elective 3','elective',3.0,6),
 (7,'Arts and Humanities Elective','general',2.0,2),(7,'Domain Elective 4','elective',3.0,5),(7,'Domain Elective 5','elective',3.0,6),
 (8,'Elective Supporting','supporting',3.0,1),(8,'Domain Elective 6','elective',3.0,4),(8,'Domain Elective 7','elective',3.0,5)
) AS v(semester_no,title,req_type,credits,ord)
ON CONFLICT (curriculum_id, semester_number, title) DO NOTHING;

-- Publicly explicit prerequisites only; no semester-order inference.
WITH scheme AS (SELECT id FROM curriculum_schemes WHERE name='Fall 2025 onward'),
src AS (SELECT id FROM source_records WHERE source_code='SRC-BS-PAGE')
INSERT INTO course_prerequisites
    (curriculum_id, course_id, prerequisite_course_id, relation_type, source_id, verified)
SELECT scheme.id, target.id, prereq.id, 'prerequisite', src.id, TRUE
FROM scheme, src
CROSS JOIN (VALUES ('CSC-483','CSC-322'),('CSC-486','CSC-322')) AS v(target_code, prereq_code)
JOIN courses target ON target.code=v.target_code
JOIN courses prereq ON prereq.code=v.prereq_code
ON CONFLICT (curriculum_id, course_id, prerequisite_course_id, relation_type) DO NOTHING;

INSERT INTO focus_areas (name) VALUES
 ('Artificial Intelligence'),('Data Science'),('Software Engineering'),
 ('Human Centered Computing'),('Information Systems'),('Networks and Security')
ON CONFLICT (name) DO NOTHING;

-- Programme compulsory courses explicitly listed by public programme pages.
WITH mappings(program_code, scheme_name, course_code) AS (VALUES
 ('MPHIL-CS','Public programme structure verified 2026','CSC-652'),
 ('MPHIL-CS','Public programme structure verified 2026','CSC-702'),
 ('MS-IST','Public programme structure verified 2026','IST-611'),
 ('MS-IST','Public programme structure verified 2026','IST-631'),
 ('MS-DS','Public programme structure verified 2026','DSC-605'),
 ('MS-DS','Public programme structure verified 2026','DSC-606')
)
INSERT INTO curriculum_courses (curriculum_id, course_id, requirement_type)
SELECT cs.id, c.id, 'core'
FROM mappings m
JOIN programs p ON p.code=m.program_code
JOIN curriculum_schemes cs ON cs.program_id=p.id AND cs.name=m.scheme_name
JOIN courses c ON c.code=m.course_code
ON CONFLICT (curriculum_id, course_id) DO NOTHING;

INSERT INTO fee_structures
    (program_id, official_fee_category, shift, fee_type, amount, effective_from, source_id)
SELECT p.id, v.official_category, v.shift, v.fee_type, v.amount, '2025-09-01', s.id
FROM (VALUES
 ('BSCS','BS Computer Science - Regular','Regular/Morning','admission_time',35460.00),
 ('BSCS','BS Computer Science - Regular','Regular/Morning','semester',60860.00),
 ('BSCS','BS Computer Science - Self Finance/Evening','Self Finance/Evening','admission_time',35850.00),
 ('BSCS','BS Computer Science - Self Finance/Evening','Self Finance/Evening','semester',129380.00),
 ('MPHIL-CS','MPhil Computer Science','Regular/Full-time','admission_time',35210.00),
 ('MPHIL-CS','MPhil Computer Science','Regular/Full-time','semester',40040.00),
 (NULL,'MS (CS)','University fee category','admission_time',35210.00),
 (NULL,'MS (CS)','University fee category','semester',82170.00),
 ('PHD-CS','PhD Computer Science','Regular/Full-time','admission_time',35210.00),
 ('PHD-CS','PhD Computer Science','Regular/Full-time','semester',65390.00)
) AS v(program_code,official_category,shift,fee_type,amount)
LEFT JOIN programs p ON p.code=v.program_code
CROSS JOIN (SELECT id FROM source_records WHERE source_code='SRC-FEES-F2025') s
ON CONFLICT (program_id, official_fee_category, shift, fee_type, effective_from) DO NOTHING;

INSERT INTO grading_bands
    (program_id, minimum_marks, maximum_marks, letter_grade, grade_points, effective_from, source_id)
SELECT p.id, v.min_marks, v.max_marks, v.grade, v.points, '2026-08-11', s.id
FROM programs p
CROSS JOIN (VALUES
 (80,100,'A',4.00),(76,79.99,'A-',3.80),(72,75.99,'B+',3.50),
 (68,71.99,'B',3.00),(64,67.99,'B-',2.80),(60,63.99,'C+',2.50),
 (55,59.99,'C',2.00),(50,54.99,'D',1.00),(0,49.99,'F',0.00)
) AS v(min_marks,max_marks,grade,points)
CROSS JOIN (SELECT id FROM source_records WHERE source_code='SRC-BS-RULES') s
WHERE p.code='BSCS'
ON CONFLICT (program_id, letter_grade, effective_from) DO NOTHING;

INSERT INTO academic_rules
    (rule_code, program_id, category, title, description, condition_json,
     outcome_json, effective_from, priority, source_id)
SELECT v.rule_code, p.id, v.category, v.title, v.description,
       v.condition_json::jsonb, v.outcome_json::jsonb, '2026-08-11', v.priority, s.id
FROM (VALUES
 ('BS-NORMAL-LOAD','registration','Normal semester workload','The normal regular-semester course load is 15 to 18 credit hours.','{"semester_type":"regular"}','{"minimum_credits":15,"maximum_credits":18}',100),
 ('BS-EXCEPTIONAL-LOAD','registration','Exceptional semester workload','With Chair/Director permission, Dean approval, and the prescribed undertaking, a student may take 12 to 21 credits, or all remaining credits when fewer than 12 remain.','{"approval_required":true}','{"minimum_credits":12,"maximum_credits":21,"allow_all_remaining_below_minimum":true}',90),
 ('BS-NO-REGISTRATION-FREEZE','registration','No registration means frozen semester','A semester with no registered courses is deemed frozen.','{"registered_course_count":0}','{"semester_status":"frozen"}',80),
 ('BS-MAX-FREEZES','progression','Maximum semester freezes','A BS student may freeze at most two semesters.','{"requested_freeze":true}','{"maximum_frozen_semesters":2,"normal_application_days":45}',80),
 ('BS-MIN-ATTENDANCE','examination','Terminal examination attendance requirement','At least 80 percent attendance is required; up to 10 percent relaxation may be approved only under published conditions.','{"exam_type":"terminal"}','{"minimum_attendance_percent":80,"maximum_approved_relaxation_percent":10}',80),
 ('BS-SUMMER-COURSE-LIMIT','registration','Summer course limit','If a summer session is offered, a student may register at most two courses and must meet 80 percent attendance.','{"semester_type":"summer"}','{"maximum_courses":2,"minimum_attendance_percent":80}',80),
 ('BS-PROBATION','progression','Academic probation','A student with CGPA from 1.0 up to but below 2.0 is placed on probation.','{"cgpa_gte":1.0,"cgpa_lt":2.0}','{"status":"probation","maximum_chances":3}',50),
 ('BS-DROP-CGPA','progression','Drop for CGPA below 1.0','A student with CGPA below 1.0 at the end of a semester is dropped from university rolls; first-semester GPA applies to first-semester students.','{"cgpa_lt":1.0}','{"status":"dropped"}',40),
 ('BS-MAX-DURATION','graduation','Maximum degree duration','The BS degree must be completed within 12 regular semesters or six years.','{}','{"maximum_regular_semesters":12,"maximum_years":6}',80),
 ('BS-EXEMPTION-LIMIT','exemption','Maximum course exemption','Up to 51 credit hours may be exempted under the published transfer/exemption procedure, subject to eligibility conditions.','{"minimum_grade":"C","minimum_gpa":2.0,"institution_hec_recognized":true}','{"maximum_exempt_credits":51,"limited_to_first_two_year_courses":true}',80)
) AS v(rule_code,category,title,description,condition_json,outcome_json,priority)
CROSS JOIN programs p
CROSS JOIN (SELECT id FROM source_records WHERE source_code='SRC-BS-RULES') s
WHERE p.code='BSCS'
ON CONFLICT (rule_code, effective_from) DO NOTHING;

-- Local/bootstrap administrator. Change this password immediately outside development.
INSERT INTO app_users (email, password_hash, role, active)
VALUES (
  'admin@cs.qau.edu.pk',
  'pbkdf2_sha256$240000$fd1bf631edf9f305a5f0d9fd1aaa6a2d$4020ffab15ad7de4e42b61a83686ab98d7956fb4cbe80a2c65cfad510caef559',
  'admin', TRUE
)
ON CONFLICT (email) DO NOTHING;

COMMIT;
