# NLP layer — multilingual intent classification

The primary classifier is a fine-tuned `distilbert-base-multilingual-cased`
sequence-classification model:

1. Normalize whitespace.
2. Detect English, Roman Urdu, or Urdu script.
3. Tokenize and classify one of the project intents with multilingual
   DistilBERT.
4. Extract course codes, known course names, programmes, shifts, semesters,
   days, dates, credit-hour references, and degree levels.

Create the deployable artifact from `backend/` with:

```powershell
python scripts/train_transformer.py
```

The runtime loads local trained artifacts; it never downloads a model during a
student request. `NLP_CLASSIFIER_BACKEND=transformer` makes the artifact
mandatory. `auto` uses the n-gram classifier only as an availability fallback
and reports that fact in every NLP/chat response. Inspect the active model at
`GET /api/v1/nlp/model`. The supplied deployment defaults to strict
`transformer` mode, so it fails visibly if its trained artifact is removed.

## Current intent set

`course_prerequisite`, `course_information`, `registration_process`,
`registration_deadline`, `credit_hour_limit`, `fee_information`,
`timetable_query`, `exam_schedule`, `thesis_information`, `course_exemption`,
`degree_requirement`, `gpa_requirement`, `probation_rule`,
`program_information`, `semester_information`, `greeting`, `help`, and
`fallback`.

## API example

```json
POST /api/v1/nlp/analyze
{"text":"CSC-486 ki prerequisite kya hai?"}
```

The response includes normalized text, language, intent, confidence, entities,
`model_backend`, and `model_name`. Intent confidence is a routing signal, not
proof that an academic fact is true; facts still come from SQL, rules, or
retrieval.

For workflows that only need slot filling, use `POST /api/v1/nlp/entities`.
Entity extraction is deterministic and does not infer eligibility.
