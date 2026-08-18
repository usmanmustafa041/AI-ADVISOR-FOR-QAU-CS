# Database — Step 2

This directory defines the PostgreSQL and pgvector foundation for the QAU CS
Academic Advisor. `schema.sql` implements Step 2. Step 3 is implemented by the
idempotent `seed.sql` plus the database assertions in `verify_seed.sql`.

## Design decisions

- PostgreSQL is the single transactional database.
- pgvector stores document embeddings alongside their source metadata.
- Academic facts reference `source_records` so answers can be traced.
- Curricula, prerequisites, fees, and rules are effective-date/version aware.
- Official fee-category labels are stored separately from academic programs; the
  public `MS (CS)` fee category is not silently assigned to MS IST or MS Data
  Science without departmental confirmation.
- Timetables and examinations are attached to semester-specific offerings.
- Rule conditions and outcomes use JSONB while identity and relationships remain
  relational.
- Student records are separate from public academic data.
- Chat diagnostics retain intent, entities, routing engine, sources, and latency.

## Start locally

1. Copy `.env.example` to `.env` and change the development password.
2. Run `docker compose up -d postgres`.
3. Check readiness with `docker compose ps`.

The schema is applied automatically only when the database volume is created for
the first time. Later schema changes should use migrations rather than editing a
live database manually.

On a fresh volume, initialization runs in this order:

1. `001-schema.sql`
2. `002-seed.sql`
3. `003-verify-seed.sql`

`seed.sql` contains authoritative/source-tracked records. `mock_seed.sql` adds a
separate, clearly marked demonstration layer with synthetic Fall 2026
timetables, exams, deadlines, fees, prerequisites, and FYP guidelines. Every
mock record references an `unverified` `MOCK-*` source and must be replaced by
department-approved data before deployment.

`official_fee_seed_2026.sql` supersedes the synthetic fee examples with the
official QAU bachelor fee table effective Fall 2026, including the Computer
Science national-student admission/semester totals, published service charges,
summer-course charges, and foreign-student amounts. Its exact primary amounts
are asserted by `verify_official_fees_2026.sql`.

`progression_seed_2025.sql` derives non-binding planning links from the official
eight-semester sequence. They remain `verified=FALSE` because the scheme does
not publish a formal prerequisite matrix. The API and UI label these as inferred
progression guidance and keep them separate from published prerequisites.

## Embedding dimension

`document_chunks.embedding` is currently `VECTOR(384)`, matching common compact
sentence-transformer models. If the final embedding model uses another dimension,
change this before production data is indexed and record the model name/version.

## Step 2 acceptance criteria

- Schema covers authoritative sources, programs, curricula, courses,
  prerequisites, fees, academic terms, deadlines, offerings, timetables, exams,
  rules, RAG documents, users, students, chat history, and audit events.
- Foreign keys and checks reject inconsistent records.
- Frequently used advisor lookups have indexes.
- pgvector is enabled and the embedding index is defined.
- No unverified academic facts are seeded during this step.
