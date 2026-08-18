# FastAPI backend — Step 4

The backend exposes verified structured academic data without using an LLM as a
source of truth.

## Run

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

API documentation is available at `http://localhost:8000/docs`.

## Implemented endpoints

- `GET /api/v1/health`
- `GET /api/v1/health/database`
- `GET /api/v1/programs`
- `GET /api/v1/courses/{course_code}`
- `GET /api/v1/courses/{course_code}/prerequisites`
- `GET /api/v1/fees`
- `GET /api/v1/timetable`
- `POST /api/v1/nlp/analyze`
- `GET /api/v1/nlp/model`
- `POST /api/v1/rules/prerequisite-check`
- `POST /api/v1/rules/semester-load`
- `POST /api/v1/rules/progression`
- `POST /api/v1/rules/exemption`
- `POST /api/v1/rag/search`

The NLP endpoint returns language, intent, confidence, extracted entities, and
the exact model backend/name that produced the classification. The primary
classifier is a trained multilingual DistilBERT model for English, Roman Urdu,
and Urdu script. A reproducible n-gram classifier is retained only as a clearly
reported availability fallback. Model readiness is inspectable through
`GET /api/v1/nlp/model`.

The prerequisite response always reports that the public prerequisite dataset is
incomplete. An empty prerequisite array must not be interpreted as academic
eligibility. Timetable responses similarly identify when no current verified
operational data is loaded.

## Tests

```powershell
cd backend
python -m pytest
```

Database-backed endpoint integration tests require PostgreSQL initialized from
the root `docker-compose.yml`.

## Complete FYP workflows

The API also implements registration/login, authenticated chat persistence,
query history, public policies/deadlines/exams, and administrator management for
courses, fees, timetables, policies, user accounts, query logs, and date-ranged
reports. A fresh development database seeds `admin@cs.qau.edu.pk` with bootstrap
password `ChangeMeAdmin123!`; change it immediately and never keep it in a
deployed environment.
