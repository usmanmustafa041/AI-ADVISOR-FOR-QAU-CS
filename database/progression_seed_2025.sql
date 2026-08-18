BEGIN;

-- The official Fall 2025 scheme publishes semester placement, not a formal
-- prerequisite matrix. These unverified links are planning recommendations
-- inferred from direct subject progression and must not be used to block
-- registration without departmental confirmation.
DELETE FROM course_prerequisites cp
USING source_records s
WHERE cp.source_id=s.id AND s.source_code='MOCK-QAU-GUIDES';

-- Correct semester placement/order from the two-column source layout.
WITH scheme AS (SELECT id FROM curriculum_schemes WHERE name='Fall 2025 onward'),
placement(code, semester_no, display_no) AS (VALUES
 ('MA-203',3,1),('EN-299',3,2),('CSC-103',3,3),('CSC-211',3,4),('CSC-212',3,5),
 ('SW-100',4,1),('PS-101',4,2),('MA-104',4,3),('CSC-222',4,4),('CSC-224',4,5),('CSC-313',4,6)
)
UPDATE curriculum_courses cc
SET semester_number=placement.semester_no, display_order=placement.display_no
FROM placement, scheme, courses c
WHERE cc.curriculum_id=scheme.id AND cc.course_id=c.id AND c.code=placement.code;

WITH scheme AS (SELECT id FROM curriculum_schemes WHERE name='Fall 2025 onward'),
src AS (SELECT id FROM source_records WHERE source_code='SRC-BS-SCHEME-2025')
INSERT INTO course_prerequisites
    (curriculum_id, course_id, prerequisite_course_id, relation_type, minimum_grade,
     waiver_condition, source_id, verified)
SELECT scheme.id, target.id, prior.id, 'prerequisite', NULL,
       'Recommended prior learning inferred from semester placement; not a formally published prerequisite.',
       src.id, FALSE
FROM scheme, src
CROSS JOIN (VALUES
 ('EN-200','EN-100'),
 ('FQ-102','FQ-101'),
 ('MA-202','MA-101'),
 ('CSC-121','CSC-104'),
 ('CSC-211','CSC-121'),
 ('CSC-222','CSC-121'),
 ('CSC-224','CSC-211'),
 ('CSC-313','CSC-103'),
 ('CSC-322','CSC-222'),
 ('CSC-226','CSC-211'),
 ('CSC-311','CSC-211'),
 ('CSC-414','CSC-211'),
 ('CSC-331','MA-203'),
 ('CSC-325','CSC-224'),
 ('CSC-215','CSC-313'),
 ('CSC-312','CSC-226'),
 ('CSC-411','CSC-331'),
 ('CSC-489','CSC-322'),
 ('CSC-412','CSC-312'),
 ('CSC-490','CSC-489')
) AS v(course_code, prior_code)
JOIN courses target ON target.code=v.course_code
JOIN courses prior ON prior.code=v.prior_code
ON CONFLICT (curriculum_id, course_id, prerequisite_course_id, relation_type)
DO UPDATE SET minimum_grade=NULL, waiver_condition=EXCLUDED.waiver_condition,
              source_id=EXCLUDED.source_id, verified=FALSE;

COMMIT;
