BEGIN;

-- Demonstration data for development and FYP evaluation only.
-- These records are realistic examples based on common Pakistani university
-- practices. They are NOT published or approved QAU records.
INSERT INTO source_records
    (source_code, title, category, authority, effective_from, last_verified_at,
     verification_status, is_time_sensitive, notes)
VALUES
    ('MOCK-QAU-F26', ' QAU CS Fall 2026 operational dataset', 'demonstration',
     'Synthetic FYP demonstration data - not QAU authority', '2026-08-01', NULL,
     'unverified', TRUE,
     'Mock timetable, exams, deadlines and fees. Replace with department-approved records.'),
    ('MOCK-QAU-GUIDES', ' QAU CS student and project guidelines', 'demonstration',
     'Synthetic FYP demonstration data - not QAU authority', '2026-08-01', NULL,
     'unverified', FALSE,
     'Mock FYP guidance based on common Pakistani university practices.')
ON CONFLICT (source_code) DO NOTHING;

INSERT INTO academic_terms (academic_year, term, starts_on, ends_on, active, source_id)
VALUES (2026, 'Fall', '2026-09-07', '2027-01-15', TRUE,
        (SELECT id FROM source_records WHERE source_code='MOCK-QAU-F26'))
ON CONFLICT (academic_year, term) DO UPDATE
SET starts_on=EXCLUDED.starts_on, ends_on=EXCLUDED.ends_on,
    active=EXCLUDED.active, source_id=EXCLUDED.source_id;

WITH term AS (SELECT id FROM academic_terms WHERE academic_year=2026 AND term='Fall'),
program AS (SELECT id FROM programs WHERE code='BSCS'),
src AS (SELECT id FROM source_records WHERE source_code='MOCK-QAU-F26')
INSERT INTO course_offerings (term_id, course_id, program_id, section, instructor, capacity, source_id)
SELECT term.id, c.id, program.id, v.section, v.instructor, v.capacity, src.id
FROM term, program, src
CROSS JOIN (VALUES
 ('CSC-104','A','Dr. Sara Khan',45), ('CSC-211','A','Dr. Ahmed Raza',45),
 ('CSC-224','A','Dr. Hina Ali',40), ('CSC-226','A','Dr. Bilal Shah',40),
 ('CSC-311','A','Dr. Ayesha Malik',40), ('CSC-322','A','Mr. Hamza Qureshi',40),
 ('CSC-414','A','Dr. Zainab Noor',35), ('CSC-489','A','FYP Committee',50),
 ('CSC-490','A','FYP Committee',50)
) AS v(course_code, section, instructor, capacity)
JOIN courses c ON c.code=v.course_code
ON CONFLICT (term_id, course_id, program_id, section) DO UPDATE
SET instructor=EXCLUDED.instructor, capacity=EXCLUDED.capacity, source_id=EXCLUDED.source_id;

WITH offering AS (
  SELECT o.id, c.code FROM course_offerings o
  JOIN courses c ON c.id=o.course_id JOIN academic_terms t ON t.id=o.term_id
  WHERE t.academic_year=2026 AND t.term='Fall' AND o.section='A'
)
INSERT INTO timetable_entries
    (offering_id, session_type, day_of_week, starts_at, ends_at, room, lab_group)
SELECT o.id, v.session_type, v.day_no, v.starts_at::time, v.ends_at::time, v.room, v.lab_group
FROM (VALUES
 ('CSC-104','class',1,'09:00','10:20','CS-101',NULL),
 ('CSC-104','lab',3,'14:00','16:40','Programming Lab','G1'),
 ('CSC-211','class',2,'09:00','10:20','CS-102',NULL),
 ('CSC-211','lab',4,'14:00','16:40','Programming Lab','G1'),
 ('CSC-224','class',1,'10:30','11:50','CS-103',NULL),
 ('CSC-224','lab',5,'09:00','11:40','Database Lab','G1'),
 ('CSC-226','class',3,'09:00','10:20','CS-102',NULL),
 ('CSC-226','lab',5,'14:00','16:40','Systems Lab','G1'),
 ('CSC-311','class',2,'10:30','11:50','CS-201',NULL),
 ('CSC-322','class',4,'10:30','11:50','CS-201',NULL),
 ('CSC-322','lab',2,'14:00','16:40','Software Lab','G1'),
 ('CSC-414','class',1,'12:00','13:20','CS-202',NULL),
 ('CSC-489','class',5,'12:00','13:20','Seminar Hall',NULL),
 ('CSC-490','class',5,'13:30','14:50','Seminar Hall',NULL)
) AS v(course_code, session_type, day_no, starts_at, ends_at, room, lab_group)
JOIN offering o ON o.code=v.course_code
ON CONFLICT (offering_id, session_type, day_of_week, starts_at, lab_group) DO UPDATE
SET ends_at=EXCLUDED.ends_at, room=EXCLUDED.room;

WITH src AS (SELECT id FROM source_records WHERE source_code='MOCK-QAU-F26'),
offering AS (
  SELECT o.id, c.code FROM course_offerings o JOIN courses c ON c.id=o.course_id
  JOIN academic_terms t ON t.id=o.term_id
  WHERE t.academic_year=2026 AND t.term='Fall' AND o.section='A'
)
INSERT INTO exam_schedules
    (offering_id, exam_type, exam_date, starts_at, ends_at, room, source_id)
SELECT o.id, 'Terminal', v.exam_date::date, v.starts_at::time, v.ends_at::time, v.room, src.id
FROM src
CROSS JOIN (VALUES
 ('CSC-104','2027-01-04','09:00','12:00','Examination Hall A'),
 ('CSC-211','2027-01-05','09:00','12:00','Examination Hall A'),
 ('CSC-224','2027-01-06','09:00','12:00','Examination Hall B'),
 ('CSC-226','2027-01-07','09:00','12:00','Examination Hall B'),
 ('CSC-311','2027-01-08','09:00','12:00','Examination Hall A'),
 ('CSC-322','2027-01-11','09:00','12:00','Examination Hall B'),
 ('CSC-414','2027-01-12','09:00','12:00','Examination Hall A')
) AS v(course_code, exam_date, starts_at, ends_at, room)
JOIN offering o ON o.code=v.course_code
ON CONFLICT (offering_id, exam_type, exam_date, starts_at) DO UPDATE SET room=EXCLUDED.room;

WITH term AS (SELECT id FROM academic_terms WHERE academic_year=2026 AND term='Fall'),
program AS (SELECT id FROM programs WHERE code='BSCS'),
src AS (SELECT id FROM source_records WHERE source_code='MOCK-QAU-F26')
INSERT INTO deadlines
    (term_id, program_id, deadline_type, title, opens_at, closes_at, expires_at, source_id, notes)
SELECT term.id, program.id, v.kind, v.title, v.opens_at::timestamptz,
       v.closes_at::timestamptz, v.expires_at::timestamptz, src.id, v.notes
FROM term, program, src
CROSS JOIN (VALUES
 ('registration','Course registration without late fee','2026-08-24 09:00+05','2026-09-04 16:00+05','2026-09-05 00:00+05','Demo date'),
 ('course_change','Course add/drop deadline','2026-09-07 09:00+05','2026-09-18 16:00+05','2026-09-19 00:00+05','Advisor approval assumed'),
 ('fee','Semester fee payment deadline','2026-08-24 09:00+05','2026-09-11 16:00+05','2026-09-12 00:00+05','Demo date'),
 ('fyp_proposal','FYP-I proposal submission','2026-09-14 09:00+05','2026-10-02 16:00+05','2026-10-03 00:00+05','Submit to demo FYP portal')
) AS v(kind,title,opens_at,closes_at,expires_at,notes)
WHERE NOT EXISTS (
  SELECT 1 FROM deadlines d WHERE d.term_id=term.id AND d.deadline_type=v.kind AND d.title=v.title
);

WITH program AS (SELECT id FROM programs WHERE code='BSCS'),
src AS (SELECT id FROM source_records WHERE source_code='MOCK-QAU-GUIDES')
INSERT INTO academic_rules
    (rule_code, program_id, category, title, description, condition_json,
     outcome_json, effective_from, priority, source_id)
SELECT v.code, program.id, v.category, v.title, v.description,
       '{}'::jsonb, v.outcome::jsonb, '2026-08-01', v.priority, src.id
FROM program, src
CROSS JOIN (VALUES
 ('DEMO-FYP-ELIGIBILITY','fyp',' FYP-I eligibility',
  'Students should have completed at least 85 credit hours and the Software Construction course before registering for Project-I.',
  '{"minimum_earned_credits":85,"required_course":"CSC-322"}',60),
 ('DEMO-FYP-TEAM','fyp',' FYP team and supervision',
  'A project team normally contains two or three students and works under an approved departmental supervisor.',
  '{"minimum_team_size":2,"maximum_team_size":3}',70),
 ('DEMO-FYP-DELIVERABLES','fyp',' FYP assessment and deliverables',
  'Expected deliverables include an approved proposal, progress demonstrations, final report, source code, poster, and viva presentation.',
  '{"deliverables":["proposal","progress_demo","report","source_code","poster","viva"]}',80),
 ('DEMO-ATTENDANCE','attendance',' Attendance warning workflow',
  'Instructors issue an early warning when attendance is at risk; students remain responsible for meeting the official examination eligibility rule.',
  '{"warning_percent":85}',90)
) AS v(code,category,title,description,outcome,priority)
ON CONFLICT (rule_code, effective_from) DO UPDATE
SET title=EXCLUDED.title, description=EXCLUDED.description,
    outcome_json=EXCLUDED.outcome_json, source_id=EXCLUDED.source_id;

COMMIT;
