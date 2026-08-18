DO $$
DECLARE
    invalid_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO invalid_count
    FROM curriculum_schemes cs
    JOIN programs p ON p.id = cs.program_id
    WHERE p.code = 'BSCS' AND cs.name = 'Fall 2025 onward'
      AND cs.total_credit_hours <> 134;
    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'BSCS Fall 2025 curriculum must total 134 credits';
    END IF;

    SELECT COUNT(*) INTO invalid_count
    FROM course_prerequisites cp
    WHERE cp.verified = FALSE;
    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'Step 3 must not seed unverified prerequisites';
    END IF;

    IF (SELECT COUNT(*) FROM programs) < 5 THEN
        RAISE EXCEPTION 'Expected five public CS programmes';
    END IF;

    IF (SELECT COUNT(*) FROM courses) < 45 THEN
        RAISE EXCEPTION 'Expected at least 45 verified coded courses';
    END IF;

    IF (SELECT COUNT(*) FROM course_prerequisites) <> 2 THEN
        RAISE EXCEPTION 'Only the two explicitly published prerequisites should be seeded';
    END IF;
END $$;

SELECT 'programs' AS entity, COUNT(*) AS rows FROM programs
UNION ALL SELECT 'curriculum_schemes', COUNT(*) FROM curriculum_schemes
UNION ALL SELECT 'courses', COUNT(*) FROM courses
UNION ALL SELECT 'curriculum_courses', COUNT(*) FROM curriculum_courses
UNION ALL SELECT 'curriculum_slots', COUNT(*) FROM curriculum_slots
UNION ALL SELECT 'course_prerequisites', COUNT(*) FROM course_prerequisites
UNION ALL SELECT 'fee_structures', COUNT(*) FROM fee_structures
UNION ALL SELECT 'grading_bands', COUNT(*) FROM grading_bands
UNION ALL SELECT 'academic_rules', COUNT(*) FROM academic_rules
ORDER BY entity;

