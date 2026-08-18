# FYP PDF requirements implementation

The source document `04072213047_USMANMUSTAFA_FYP_1_AI_BASED_ACADEMIC_ADVISOR.pdf`
was reviewed page-by-page. The implementation status is:

| Requirement area | Implementation |
|---|---|
| Student registration/login | `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/me` |
| Password security | PBKDF2-SHA256 hashing and signed expiring bearer tokens |
| Academic chat/NLP | FastAPI chat plus trained multilingual DistilBERT intent pipeline, language detection, entities, model-status endpoint, and controlled offline fallback |
| Course search | `/api/v1/courses` and `/api/v1/courses/{course_code}` |
| Query history | Authenticated `/api/v1/history` endpoint backed by chat tables |
| Admin login/roles | Admin-only dependency with role enforcement |
| Course administration | Admin course listing and validated editable fields |
| Student/user administration | Admin user listing |
| Audit logs | Admin `/api/v1/admin/logs` endpoint |
| Reports | Admin `/api/v1/admin/report` usage summary |
| Fees/timetable/exams/policies | Versioned source-backed APIs with stale/unavailable safeguards |
| Bilingual input | English, Roman Urdu, and Urdu classifier/entity tests and multilingual transformer training examples |
| Mobile/desktop web UI | React/Vite responsive portal and Docker/Nginx deployment |

Department-approved credentials, student fields, current schedules, complete
prerequisites, departmental SOPs, and admin identities cannot be fabricated.
Those remain protected by the repository readiness gates.
