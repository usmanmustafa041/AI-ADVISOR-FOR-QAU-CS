DO $$
DECLARE
    semester_count integer;
    plan_credits numeric;
    inferred_links integer;
BEGIN
    WITH scheme AS (SELECT id FROM curriculum_schemes WHERE name='Fall 2025 onward'),
    plan AS (
      SELECT cc.semester_number, c.total_credit_hours AS credits
      FROM curriculum_courses cc JOIN courses c ON c.id=cc.course_id, scheme
      WHERE cc.curriculum_id=scheme.id
      UNION ALL
      SELECT cs.semester_number, cs.credit_hours FROM curriculum_slots cs, scheme
      WHERE cs.curriculum_id=scheme.id
    )
    SELECT COUNT(DISTINCT semester_number), SUM(credits)
    INTO semester_count, plan_credits FROM plan;

    SELECT COUNT(*) INTO inferred_links
    FROM course_prerequisites cp JOIN curriculum_schemes cs ON cs.id=cp.curriculum_id
    JOIN source_records s ON s.id=cp.source_id
    WHERE cs.name='Fall 2025 onward' AND s.source_code='SRC-BS-SCHEME-2025'
      AND cp.verified=FALSE;

    IF semester_count <> 8 OR plan_credits <> 134 OR inferred_links <> 20 THEN
      RAISE EXCEPTION 'Fall 2025 progression validation failed: semesters %, credits %, guidance links %',
        semester_count, plan_credits, inferred_links;
    END IF;

    IF EXISTS (
      WITH scheme AS (SELECT id FROM curriculum_schemes WHERE name='Fall 2025 onward'),
      plan AS (
        SELECT cc.semester_number, c.total_credit_hours AS credits
        FROM curriculum_courses cc JOIN courses c ON c.id=cc.course_id, scheme WHERE cc.curriculum_id=scheme.id
        UNION ALL
        SELECT cs.semester_number, cs.credit_hours FROM curriculum_slots cs, scheme WHERE cs.curriculum_id=scheme.id
      ), actual AS (SELECT semester_number, SUM(credits) AS credits FROM plan GROUP BY semester_number),
      expected(semester_number, credits) AS (VALUES (1,16),(2,18),(3,16),(4,17),(5,18),(6,18),(7,15),(8,16))
      SELECT 1 FROM expected e LEFT JOIN actual a USING (semester_number) WHERE a.credits<>e.credits OR a.credits IS NULL
    ) THEN
      RAISE EXCEPTION 'Fall 2025 per-semester credit totals do not match the published scheme';
    END IF;
END $$;

SELECT cs.name, COUNT(DISTINCT plan.semester_number) AS semesters,
       SUM(plan.credits) AS total_credits
FROM curriculum_schemes cs
JOIN (
  SELECT cc.curriculum_id, cc.semester_number, c.total_credit_hours AS credits
  FROM curriculum_courses cc JOIN courses c ON c.id=cc.course_id
  UNION ALL
  SELECT curriculum_id, semester_number, credit_hours FROM curriculum_slots
) plan ON plan.curriculum_id=cs.id
WHERE cs.name='Fall 2025 onward'
GROUP BY cs.name;
