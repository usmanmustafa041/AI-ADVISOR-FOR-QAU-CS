DO $$
DECLARE
    mock_sources integer;
    fall_offerings integer;
    fall_timetable integer;
    fall_exams integer;
    fall_deadlines integer;
BEGIN
    SELECT COUNT(*) INTO mock_sources FROM source_records WHERE source_code LIKE 'MOCK-%';
    SELECT COUNT(*) INTO fall_offerings FROM course_offerings o JOIN academic_terms t ON t.id=o.term_id
      WHERE t.academic_year=2026 AND t.term='Fall';
    SELECT COUNT(*) INTO fall_timetable FROM timetable_entries e JOIN course_offerings o ON o.id=e.offering_id
      JOIN academic_terms t ON t.id=o.term_id WHERE t.academic_year=2026 AND t.term='Fall';
    SELECT COUNT(*) INTO fall_exams FROM exam_schedules e JOIN course_offerings o ON o.id=e.offering_id
      JOIN academic_terms t ON t.id=o.term_id WHERE t.academic_year=2026 AND t.term='Fall';
    SELECT COUNT(*) INTO fall_deadlines FROM deadlines d JOIN academic_terms t ON t.id=d.term_id
      WHERE t.academic_year=2026 AND t.term='Fall';
    IF mock_sources < 2 OR fall_offerings < 9 OR fall_timetable < 14 OR fall_exams < 7 OR fall_deadlines < 4 THEN
        RAISE EXCEPTION 'Mock seed validation failed: sources %, offerings %, timetable %, exams %, deadlines %',
          mock_sources, fall_offerings, fall_timetable, fall_exams, fall_deadlines;
    END IF;
END $$;

SELECT 'mock_sources' AS entity, COUNT(*) AS rows FROM source_records WHERE source_code LIKE 'MOCK-%'
UNION ALL SELECT 'fall_2026_offerings', COUNT(*) FROM course_offerings o JOIN academic_terms t ON t.id=o.term_id WHERE t.academic_year=2026 AND t.term='Fall'
UNION ALL SELECT 'fall_2026_timetable', COUNT(*) FROM timetable_entries e JOIN course_offerings o ON o.id=e.offering_id JOIN academic_terms t ON t.id=o.term_id WHERE t.academic_year=2026 AND t.term='Fall'
UNION ALL SELECT 'fall_2026_exams', COUNT(*) FROM exam_schedules e JOIN course_offerings o ON o.id=e.offering_id JOIN academic_terms t ON t.id=o.term_id WHERE t.academic_year=2026 AND t.term='Fall'
UNION ALL SELECT 'fall_2026_deadlines', COUNT(*) FROM deadlines d JOIN academic_terms t ON t.id=d.term_id WHERE t.academic_year=2026 AND t.term='Fall';
