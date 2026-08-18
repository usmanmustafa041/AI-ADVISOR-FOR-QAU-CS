BEGIN;

-- Official QAU bachelor fee structure effective Fall 2026.
-- Source: https://qau.edu.pk/bachelor-fee-structure/
INSERT INTO source_records
    (source_code, title, category, authority, source_url, effective_from,
     last_verified_at, verification_status, is_time_sensitive, notes)
VALUES (
    'SRC-FEES-F2026',
    'QAU Bachelor Fee Structure effective Fall 2026',
    'fees',
    'Quaid-i-Azam University',
    'https://qau.edu.pk/bachelor-fee-structure/',
    '2026-08-01',
    '2026-08-17 00:00:00+05',
    'verified',
    TRUE,
    'Official national and foreign bachelor fee tables. Field/lab charges and advance tax may apply separately.'
)
ON CONFLICT (source_code) DO UPDATE SET
    title=EXCLUDED.title, source_url=EXCLUDED.source_url,
    effective_from=EXCLUDED.effective_from,
    last_verified_at=EXCLUDED.last_verified_at,
    verification_status='verified', notes=EXCLUDED.notes;

-- The former synthetic fee examples are superseded by the official table.
DELETE FROM fee_structures
WHERE source_id=(SELECT id FROM source_records WHERE source_code='MOCK-QAU-F26');

UPDATE fee_structures SET effective_to='2026-07-31'
WHERE source_id=(SELECT id FROM source_records WHERE source_code='SRC-FEES-F2025')
  AND effective_to IS NULL;

WITH program AS (SELECT id FROM programs WHERE code='BSCS'),
src AS (SELECT id FROM source_records WHERE source_code='SRC-FEES-F2026')
INSERT INTO fee_structures
    (program_id, official_fee_category, shift, fee_type, amount, currency,
     effective_from, source_id)
SELECT program.id, v.category, v.shift, v.fee_type, v.amount, v.currency,
       '2026-08-01', src.id
FROM program, src
CROSS JOIN (VALUES
 -- National students: Computer Science / Law / IT category.
 ('BS Computer Science - National Students','Regular/Morning','admission_fee',38040.00,'PKR'),
 ('BS Computer Science - National Students','Regular/Morning','semester_total',68490.00,'PKR'),
 ('BS Computer Science - National Students','Regular/Morning','initial_total_a_plus_b',106530.00,'PKR'),
 ('BS Computer Science - National Students','Self Finance/Evening','admission_fee',38480.00,'PKR'),
 ('BS Computer Science - National Students','Self Finance/Evening','semester_total',142140.00,'PKR'),
 ('BS Computer Science - National Students','Self Finance/Evening','initial_total_a_plus_b',180620.00,'PKR'),

 -- Category C/service charges published with the national table.
 ('Bachelor Category C - National Students','Regular/Morning','admission_processing',3090.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','admission_processing',3090.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','non_credit_course_per_course',2930.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','non_credit_course_per_course',3090.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','grade_result_card_regular',680.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','grade_result_card_regular',680.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','grade_result_card_urgent',1360.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','grade_result_card_urgent',1360.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','degree_regular',6800.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','degree_regular',6800.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','degree_urgent',13600.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','degree_urgent',13600.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','duplicate_degree',13600.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','duplicate_degree',13600.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','migration_certificate',4080.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','migration_certificate',4080.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','detailed_marks_urgent',2040.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','detailed_marks_urgent',2040.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','duplicate_detailed_marks',4080.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','duplicate_detailed_marks',4080.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','degree_folder_optional',680.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','degree_folder_optional',680.00,'PKR'),
 ('Bachelor Category C - National Students','Regular/Morning','verification',2040.00,'PKR'),
 ('Bachelor Category C - National Students','Self Finance/Evening','verification',2040.00,'PKR'),
 ('Bachelor Summer Course - National Students','Regular/Morning','summer_course_per_course',10670.00,'PKR'),
 ('Bachelor Summer Course - National Students','Self Finance/Evening','summer_course_per_course',11620.00,'PKR'),

 -- Foreign students (all bachelor programmes).
 ('Bachelor - Foreign Students','Foreign Student','admission_total',181.00,'USD'),
 ('Bachelor - Foreign Students','Foreign Student','semester_total',378.00,'USD'),
 ('Bachelor - Foreign Students','Foreign Student','one_time_total',174.00,'USD'),
 ('Bachelor - Foreign Students','Foreign Student','initial_total_a_plus_b_plus_c',733.00,'USD'),
 ('Bachelor Category C - Foreign Students','Foreign Student','degree_urgent',63.00,'USD'),
 ('Bachelor Category C - Foreign Students','Foreign Student','duplicate_degree',63.00,'USD'),
 ('Bachelor Category C - Foreign Students','Foreign Student','degree_folder_optional',7.00,'USD'),
 ('Bachelor Category C - Foreign Students','Foreign Student','verification',13.00,'USD'),
 ('Bachelor Category C - Foreign Students','Foreign Student','migration_certificate',25.00,'USD'),
 ('Bachelor Category C - Foreign Students','Foreign Student','duplicate_detailed_marks',25.00,'USD'),
 ('Bachelor Summer Course - Foreign Students','Foreign Student Regular','summer_course_per_course',58.00,'USD'),
 ('Bachelor Summer Course - Foreign Students','Foreign Student Evening','summer_course_per_course',70.00,'USD')
) AS v(category,shift,fee_type,amount,currency)
ON CONFLICT (program_id, official_fee_category, shift, fee_type, effective_from)
DO UPDATE SET amount=EXCLUDED.amount, currency=EXCLUDED.currency,
              source_id=EXCLUDED.source_id, effective_to=NULL;

COMMIT;
