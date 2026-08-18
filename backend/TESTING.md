# Step 11 — testing and evaluation

## Automated checks

From `backend/`:

```powershell
python -m pytest -q
python scripts/evaluate_nlp.py --output evaluation/nlp_report.json
```

The test suite covers API contracts, English/Roman Urdu/Urdu NLP, entities,
rule-engine decisions, chunking, deterministic embeddings, and the database
degraded-health path.

PostgreSQL integration tests are included but skipped by default when no database
is available. Run them after Docker initialization with:

```powershell
$env:RUN_DB_TESTS = "1"
$env:DATABASE_URL = "postgresql+psycopg://qau_advisor:qau_advisor_local@localhost:5432/qau_advisor"
python -m pytest tests/test_postgres_integration.py -q
```

## Evaluation measures

`evaluate_nlp.py` reports:

- Intent accuracy
- Language-detection accuracy
- Per-intent precision, recall, and F1
- Macro F1
- Confusion pairs

The labeled set is a smoke/evaluation baseline, not a final research dataset.
Before the thesis evaluation, expand it to at least 200–500 independently
reviewed queries across all supported intents and keep a held-out test split.
Use `python scripts/generate_review_queue.py --count 200` to create a candidate
queue, then follow `evaluation/REVIEW_WORKFLOW.md`. Generated candidates are not
independent labels until two human reviewers and an adjudicator complete them.

## Current limitations

- PostgreSQL integration tests require Docker and the initialized database.
- Timetable/exam tests remain unavailable until official operational data is
  supplied.
- Accuracy from a small hand-labeled set must not be presented as final model
  performance.
