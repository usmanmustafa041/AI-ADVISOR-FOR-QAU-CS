DO $$
DECLARE
    matched integer;
BEGIN
    SELECT COUNT(*) INTO matched
    FROM fee_structures f
    JOIN programs p ON p.id=f.program_id
    JOIN source_records s ON s.id=f.source_id
    WHERE p.code='BSCS' AND s.source_code='SRC-FEES-F2026'
      AND f.effective_from='2026-08-01'
      AND ((f.shift='Regular/Morning' AND f.fee_type='admission_fee' AND f.amount=38040)
        OR (f.shift='Regular/Morning' AND f.fee_type='semester_total' AND f.amount=68490)
        OR (f.shift='Regular/Morning' AND f.fee_type='initial_total_a_plus_b' AND f.amount=106530)
        OR (f.shift='Self Finance/Evening' AND f.fee_type='admission_fee' AND f.amount=38480)
        OR (f.shift='Self Finance/Evening' AND f.fee_type='semester_total' AND f.amount=142140)
        OR (f.shift='Self Finance/Evening' AND f.fee_type='initial_total_a_plus_b' AND f.amount=180620));
    IF matched <> 6 THEN
        RAISE EXCEPTION 'Official Fall 2026 BSCS primary fee validation failed: % of 6 rows matched', matched;
    END IF;
    IF EXISTS (
      SELECT 1 FROM fee_structures f JOIN source_records s ON s.id=f.source_id
      WHERE s.source_code='MOCK-QAU-F26'
    ) THEN
      RAISE EXCEPTION 'Synthetic fee records remain after importing official fees';
    END IF;
END $$;

SELECT shift, fee_type, amount, currency
FROM fee_structures f
JOIN programs p ON p.id=f.program_id
JOIN source_records s ON s.id=f.source_id
WHERE p.code='BSCS' AND s.source_code='SRC-FEES-F2026'
  AND f.official_fee_category='BS Computer Science - National Students'
ORDER BY shift, fee_type;
