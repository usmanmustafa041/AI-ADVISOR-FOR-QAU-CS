# FYP specification implementation traceability

Source reviewed: `04072213047_USMANMUSTAFA_FYP_1_AI_BASED_ACADEMIC_ADVISOR.pdf`
(68 pages). This matrix maps the formal use cases in sections 2.6-2.7.1 and the
test cases in section 4.3 to executable system behavior.

| Use case | Implemented behavior | Primary implementation |
|---|---|---|
| UC1 Student Registration | Registration form, required-field validation, duplicate-email rejection, password hashing, student role, immediate authenticated session | `frontend/src/main.jsx` (`AuthScreen`); `POST /api/v1/auth/register` |
| UC2 Student Login | Credential validation, inactive-account rejection, signed expiring token, student portal routing, clear error state | `AuthScreen`; `POST /api/v1/auth/login`; `app/core/auth.py` |
| UC3 Ask Academic Query | Guest or authenticated query, validated input, language/intent/entity analysis, knowledge lookup, safe fallback, and response generation; only authenticated queries are persisted | `Chat`; `POST /api/v1/chat`; `app/nlp/*`; `app/rag/*` |
| UC4 View Chatbot Response | Conversational response, confidence/language/verification metadata, source links, follow-up queries within the same session | `Chat`; `ChatResponse` |
| UC5 View Query History | Login-gated, user-scoped stored queries and answers, no-history state, clear history, close-session API; guest conversations are never persisted | `History`; `GET/DELETE /api/v1/history`; `POST /history/{id}/close` |
| UC6 Admin Login | Same secure login, role-based routing, protected endpoints, 403 for non-admin users | `AdminPortal`; `admin_user` dependency |
| UC7 Admin Update Academic Data | Dashboard and validated management modules with audit records | `AdminDashboard`; `/api/v1/admin/*` |
| UC8 Search Course by Name | Name/code search, details drawer, published/inferred prerequisite labels, unknown-course and empty-result messages; separate official eight-semester study-plan view | `CourseSearch`, `StudyPlan`; `GET /api/v1/courses?search=`, `/courses/{code}/prerequisites`, `/programs/BSCS/study-plan` |
| UC9 Ask Policy / Fee / Timetable | Intent routing plus official Fall 2026 QAU bachelor fees, source-backed policies, deadlines, timetable, and exam endpoints; missing data is explicit | `Chat`, `Fees`, `Policies`, `Timetable`; academic API routes |
| UC10 Bilingual Query Input | English, Urdu script, and Roman Urdu detection; fine-tuned multilingual DistilBERT intent classification; auditable model identity; Urdu input/RTL control; controlled offline fallback | `Chat`; `app/nlp/language.py`; `app/nlp/transformer.py`; `scripts/train_transformer.py`; `GET /nlp/model` |
| UC11 Manage Course Information | List/add/edit/disable course records with credit validation, source selection, conflict handling, and audit | `AdminRecords`; `/admin/courses` CRUD |
| UC12 Manage Fee Structure | List/add/edit/delete effective-dated fee records, numeric validation, verified source selection | `AdminRecords`; `/admin/fees` CRUD |
| UC13 Manage Timetables | List/add/edit/delete schedule entries, offering selection, day/time/room validation, conflict handling | `AdminRecords`; `/admin/timetables` CRUD; `/admin/offerings` |
| UC14 Manage Policies & Guidelines | List/add/edit/disable effective-dated policy records with non-empty content and source selection | `AdminRecords`; `/admin/policies` CRUD |
| UC15 View Student Query Logs | Administrator-only chronological user-query table with student, intent, confidence, session, and time | `AdminRecords`; `GET /admin/query-logs` |
| UC16 Manage User Accounts | Administrator-only email/role/status editing, enable/disable, self-disable protection, password update API | `AdminEditForm`; `PATCH /admin/users/{id}` |
| UC17 Generate Reports | Date-range validation, totals, sessions, intent distribution, no-data warning, printable report | `Reports`; `GET /admin/report?start=&end=` |
| UC18 Admin Logout | Local credential/token removal and redirect to login; server rejects expired signed tokens | `Shell` logout; token expiry in `app/core/auth.py` |

## Verification evidence

- Backend: `python -m pytest -q` - 24 passed, 1 database integration test skipped
  when not explicitly enabled.
- Frontend component tests: `npm test` - 3 passed.
- Production bundle: `npm run build` - successful.
- Full-stack Playwright: registration -> chat -> persisted history, plus admin
  login -> query logs -> reports - 3 passed against Docker/PostgreSQL.
- The Docker web, API, and PostgreSQL services pass their health checks.

## Data availability boundary

The development environment includes synthetic Fall 2026 timetables,
examinations, prerequisites, deadlines, fees, and FYP guidance from
`database/mock_seed.sql`. These records are labeled `DEMO`, reference unverified
`MOCK-*` sources, and produce unverified answers. They demonstrate every workflow
but must be replaced by authorized QAU records before real academic use.
