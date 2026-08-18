# Final demonstration checklist

## Before the demo

- [ ] Start PostgreSQL from the root Docker Compose file.
- [ ] Confirm `/api/v1/health/database` reports `ok`.
- [ ] Run `python -m pytest -q` from `backend/`.
- [ ] Run `python scripts/evaluate_nlp.py --output evaluation/nlp_report.json`.
- [ ] Run `npm run build` from `frontend/`.
- [ ] Run `npm test` from `frontend/`.
- [ ] Run the PostgreSQL integration test with `RUN_DB_TESTS=1` when Docker is available.
- [ ] Confirm the source registry and effective dates are visible to the team.
- [ ] Load only department-approved current timetable/exam/prerequisite files.

## Suggested live flow

1. Open the React student portal and show the verified-source indicator.
2. Ask in English: “What is the prerequisite for CSC-483?”
3. Ask in Roman Urdu: “Registration ki last date kya hai?”
4. Toggle the interface to Urdu and ask a basic Urdu question.
5. Show the NLP intent, language, confidence, and entities in the API docs.
6. Demonstrate the rule engine with an approved prerequisite/transcript example.
7. Demonstrate a safe `unverified` response using a course with no complete
   prerequisite record.
8. Search a policy document through RAG and show its source/page citation.
9. Open the timetable view and explain how it refuses to display unverified data.
10. Show the test report and requirements traceability matrix.

## Do not claim during the demo

- Do not claim that an empty prerequisite list means “no prerequisite.”
- Do not use Fall 2025 fees as current without re-verification.
- Do not display a fabricated timetable, exam date, or student transcript.
- Open `GET /api/v1/nlp/model` and verify `active_backend` is
  `multilingual_distilbert` before describing the demonstration as BERT-backed.
