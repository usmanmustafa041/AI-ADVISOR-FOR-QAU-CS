# Final evaluation pack — Step 12

## Current verified evidence

The repository now contains the complete Step 1–11 foundation:

- Versioned academic-data collection and source registry.
- PostgreSQL/pgvector schema and verified public-source seed data.
- FastAPI academic-data API.
- Intent classification, language detection, and entity extraction.
- Deterministic prerequisite, workload, progression, and exemption rules.
- RAG document extraction, chunking, embeddings, and citation-ready retrieval.
- React/Vite student portal with English/Urdu interface toggle.
- Automated regression tests and a multilingual evaluation script.
- Chat orchestration endpoint with safe unverified responses.
- PostgreSQL integration test gate, frontend component tests, latency/security
  tests, and local RAG retrieval tests.

Current classifier evaluation (`backend/evaluation/nlp_report.json` and
`backend/evaluation/distilmbert_report.json`):

| Measure | Result | Dataset |
|---|---:|---:|
| Intent accuracy | 85.19% | 27 labeled queries |
| Language detection accuracy | 100.00% | English, Roman Urdu, Urdu |
| Multilingual DistilBERT intent accuracy | 77.78% | 27-example independent set: 9 English, 9 Roman Urdu, 9 Urdu |
| Multilingual DistilBERT macro F1 | 62.55% | Independent set; report in `backend/evaluation/distilmbert_report.json` |
| Macro F1 | 71.04% | 11 represented evaluation intents |
| Automated regression tests | 24 passed, 1 conditional skip | Backend |
| Frontend component tests | 3 passed | Vitest + Testing Library |
| Frontend production build | Passed | Vite |

These are engineering results, not final thesis claims. The evaluation
set must be expanded and independently reviewed before reporting final model
performance.

A 200-row candidate queue is available at
`backend/evaluation/review_queue_200.csv`; all rows are marked `needs_review` and
must be independently annotated and adjudicated before thesis use.

## Final evaluation protocol

1. Freeze a versioned test set of 200–500 queries, balanced across intents and
   English/Roman Urdu/Urdu.
2. Keep training, development, and held-out test queries separate.
3. Report intent accuracy, precision, recall, macro/micro F1, language accuracy,
   entity exact-match/F1, retrieval Recall@k, citation correctness, and API
   response latency (p50/p95).
4. Test deterministic rules against approved examples for prerequisites, credit
   limits, probation, exemptions, and graduation progression.
5. Test refusal behavior for missing or stale prerequisites, timetables, fees,
   and exam schedules.
6. Run usability testing with representative students and record task success,
   time-on-task, and a short satisfaction score.
7. Record the exact source version and database seed revision used in every run.

## Known release gates

The advisor must not be presented as production-ready for personalized
registration decisions until the department supplies and approves:

- The complete prerequisite/co-requisite matrix.
- Current class and lab timetables.
- Current registration/add-drop schedule.
- Current exam date sheet.
- Authorized student-record fields and privacy approval.

Until then, the application’s safe `unverified` and `data unavailable` responses
are the correct behavior.
