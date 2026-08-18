-- Clearly-labelled synthetic fallback knowledge. Administrators can replace it
-- from the Knowledge module without changing application code.
INSERT INTO source_records
    (source_code, title, category, authority, source_url, verification_status, notes)
VALUES
    ('MOCK-QAU-COMPLETE', 'DEMO QAU CS operational knowledge pack',
     'operational_guidance', 'Synthetic project fallback',
     'https://qau.edu.pk/computer-science/', 'unverified',
     'Synthetic project-completion data. Replace with department-approved records.')
ON CONFLICT (source_code) DO NOTHING;

INSERT INTO academic_rules
    (rule_code, program_id, category, title, description, effective_from,
     priority, source_id, active)
SELECT 'DEMO-REGISTRATION-PROCESS', p.id, 'registration',
       '[DEMO] Course registration procedure',
       'Select offered courses, review prerequisite and credit-load checks, submit the registration request, and obtain the required academic approval. Replace these workflow steps with an approved QAU portal notice.',
       DATE '2026-01-01', 1, sr.id, TRUE
FROM programs p CROSS JOIN source_records sr
WHERE p.code='BSCS' AND sr.source_code='MOCK-QAU-COMPLETE'
ON CONFLICT (rule_code, effective_from) DO UPDATE SET
    title=EXCLUDED.title, description=EXCLUDED.description, active=TRUE;

INSERT INTO academic_rules
    (rule_code, program_id, category, title, description, effective_from,
     priority, source_id, active)
SELECT 'BSCS-DEGREE-CREDITS-2025', cs.program_id, 'graduation',
       'BSCS credit and internship requirement',
       'The Fall 2025 onward BSCS study plan contains 131 credit hours and requires a six-to-eight-week internship during the degree, coordinated by the internship coordinator.',
       DATE '2025-08-01', 1, cs.source_id, TRUE
FROM curriculum_schemes cs WHERE cs.name='Fall 2025 onward'
ON CONFLICT (rule_code, effective_from) DO UPDATE SET
    title=EXCLUDED.title, description=EXCLUDED.description, active=TRUE;

INSERT INTO knowledge_documents
    (source_id, program_id, title, category, mime_type, storage_path, processing_status, processed_at)
SELECT sr.id, p.id, 'DEMO QAU CS operational knowledge pack', 'operational-guidance',
       'text/plain', 'database://completeness-seed', 'ready', NOW()
FROM source_records sr LEFT JOIN programs p ON p.code='BSCS'
WHERE sr.source_code='MOCK-QAU-COMPLETE'
ON CONFLICT (source_id) DO UPDATE SET processing_status='ready', processed_at=NOW();

WITH document AS (
    SELECT kd.id FROM knowledge_documents kd JOIN source_records sr ON sr.id=kd.source_id
    WHERE sr.source_code='MOCK-QAU-COMPLETE'
), chunks(chunk_index, section_title, content) AS (VALUES
    (0, 'Demo registration process', 'DEMO DATA: A student selects offered courses, checks prerequisite and credit-hour constraints, submits the registration request, and obtains departmental approval. Exact QAU portal steps must be replaced with an approved notice.'),
    (1, 'Demo timetable and examinations', 'DEMO DATA: Fall 2026 class timetable, rooms, instructors, registration deadlines, and examination dates are synthetic workflow data. They are not official QAU schedules.'),
    (2, 'Prerequisite safety', 'The Fall 2025 onward BSCS semester sequence is official, but semester placement alone is not a formally published prerequisite. Unverified prerequisite links are labelled planning guidance and require department confirmation.'),
    (3, 'Guest and authenticated use', 'Students may use the AI advisor without signing in. Guest conversations are not stored. A student signs in only to maintain private query history.'),
    (4, 'Roman Urdu support', 'The advisor accepts English, Urdu script, and common Roman Urdu questions such as mujhy timetable batao, fees kitni hai, and iska prerequisite kya hai.'),
    (5, 'Degree planning', 'The BSCS Fall 2025 onward study plan contains eight semesters and 131 credit hours, including six to eight weeks of internship coordinated by the internship coordinator.'),
    (6, 'FYP guidance', 'DEMO OPERATIONAL DATA: Final Year Project workflows include topic selection, supervisor coordination, proposal, progress review, report submission, demonstration, and evaluation. Replace dates with approved departmental schedules.'),
    (7, 'Data provenance', 'Official fee records link to the QAU bachelor fee structure page. Every synthetic timetable, deadline, examination, or inferred prerequisite record must display DEMO DATA or unverified guidance.')
)
INSERT INTO document_chunks
    (document_id, chunk_index, section_title, content, token_count, metadata)
SELECT document.id, chunks.chunk_index, chunks.section_title, chunks.content,
       array_length(regexp_split_to_array(chunks.content, '\\s+'), 1),
       '{"demo_data":true,"replaceable":true}'::jsonb
FROM document CROSS JOIN chunks
ON CONFLICT (document_id, chunk_index) DO UPDATE SET
    section_title=EXCLUDED.section_title, content=EXCLUDED.content,
    token_count=EXCLUDED.token_count, metadata=EXCLUDED.metadata;
