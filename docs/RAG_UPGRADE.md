# QAU advisor: evidence pipeline and deployment

The subsequent ingestion/versioning, refresh, feedback and evaluation additions
are documented in [the knowledge pipeline guide](KNOWLEDGE_PIPELINE.md).

The active `/api/v1/chat` endpoint now retrieves evidence for every academic
question. Intent labels no longer select a fixed answer menu. The previous chat
implementations remain in the repository for reference and are not mounted.
Complete conversational turns, including punctuation variants such as `hi'`,
greetings, thanks and acknowledgements, bypass retrieval and generation. A
greeting followed by an academic question still uses the evidence pipeline.

## What the audit found

- The website scrape contains duplicate pages and PDF files decoded as strings.
  Those strings are not document text and cannot be repaired reliably.
- Query and document embeddings used different implementations, including hash
  vectors. Comparing them produces meaningless semantic rankings.
- Broad interceptors such as `is`, `take`, `required`, and `how much` diverted
  ordinary questions into unrelated handlers before retrieval.
- Generated answers received fixed confidence values and `verified=True` without
  evidence checks. Conversation reloads also discarded citation information.
- The main app had overlapping programme routes and a conflicting hard-coded
  study plan. The database-backed academic router is now the single API authority.
- Docker mounted two directories named `baseline_seed.sql` and
  `verify_baseline_seed.sql` as SQL files. These invalid mounts were removed.
- An operational seed said 131 credits, conflicting with the actual 2025
  semester totals. Its text now identifies their calculated sum as 134.
- The local database also predates the checked-in academic schema. The additive
  migration supplies missing optional programme fields and empty curriculum,
  deadline and examination tables. It preserves existing records and leaves
  unknown facts null. A missing structured study plan points users to the
  archived PDF through chat; it is not replaced with an invented course list.

## Evidence and retrieval

`app/rag/corpus.py` builds an inspectable JSONL snapshot from the scraped pages,
the archived official PDFs/HTML, and the provided prerequisite DOCX. It rejects
binary/corrupt text, extracts PDF pages, preserves HTML table rows, keeps FAQ and
degree sections together, bounds passage sizes, and records source URL, page,
programme, term, capture time, and verification status. Original data is retained.
The provided Fall 2021 DOCX is explicitly unverified and is never treated as a
current official prerequisite matrix.

The official 2021 PDF needs OCR. Portions of the MPhil/PhD regulation PDFs have
broken font extraction; affected passages are rejected and listed in the audit.
Adding a file to the source registry does not authenticate its contents.

Retrieval combines BM25 with normalized sentence-transformer vectors using
reciprocal rank fusion, programme/year/course filters, metadata preferences, and
source diversity. Names and course numbers are preserved. Small, explicit query
aliases support common typos, Roman Urdu, and some Urdu academic terms; they are
not a complete Urdu translation system. Optional cross-encoder reranking is
available through `RAG_RERANKER_MODEL`. It is disabled unless a model is supplied.

Dense vectors have a corpus/model fingerprint. A missing model or mismatched
index falls back visibly to BM25; existing unknown pgvector embeddings are never
compared with the new query encoder. Approved database and CMS text is searched
lexically alongside the snapshot. Unverified and non-official database entries
are excluded. Larger deployments should replace the bounded database scan with
an indexed, versioned snapshot or validated pgvector ingestion.

This follows the retrieval/reranking separation in the
[Sentence Transformers documentation](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).
The current dense model is English-focused; a multilingual encoder and native
Urdu evaluation are still needed before claiming broad Urdu accuracy.

## Grounded answers and limits

The configured Ollama model receives a bounded set of numbered evidence passages
and conversation context. It must return factual claims with source IDs and
verbatim supporting quotes using
[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
The application checks source IDs, quote presence (allowing typography/spacing
normalization), programme scope, and exact numerical support,
then asks the model to review claim support and scope. Invalid claims are removed.
Model review remains fallible; generated answers are not automatically verified.
For the archived bachelor fee table, an additional deterministic check binds
amounts to the Regular and S.F/Evening columns and distinguishes the admission
category from per-semester charges. This check also binds the requested scope
when a generated answer omits the word semester or uses morning for regular.
Simple BS semester-fee questions read the Category B total directly from the
retrieved national-student table. Research-group list questions read the
published directory headings. These paths return `cited_lookup`, preserve
citations and terms, and do not call the model. No fee amounts or group names
are encoded in application code. Complex questions continue to generation.

Final-year project questions stay within bachelor evidence rather than
inheriting MPhil/PhD thesis regulations. General project descriptions cannot
answer submission requirements. Missing departmental FYP procedures are stated
explicitly. Personal academic-rule questions with several possible programmes
ask for the programme/cohort before applying a rule; the user's reply carries
the original question forward.

Missing evidence produces a clarification. Model failure, overload, invalid
quotes, or timeout produces a short availability message and up to two related
sources in collapsed citation cards. Full passages are not repeated in the
answer body. Archived fees,
admissions, datesheets and timetables retain their original term and a freshness
notice. Historical documents do not establish today's university policy.
One generation request per worker is admitted at a time; additional requests can
still inspect related sources. Conversational and structured lookup answers
bypass that slot. The 25-second generation budget includes review; first-time
encoder loading and retrieval are additional. Compact evidence metadata, a
7,000-character context budget, bounded history and concise output constraints
reduce generation overhead. Ollama keeps the model loaded for 15 minutes by
default to reduce repeated cold starts; this is configurable.

There is no complete authenticated current prerequisite matrix, and the chatbot
does not grant registration eligibility. The MS Data Science page does not
explicitly establish programme duration; that remains a known evidence gap in
the regression report. Tables with complex PDF column layouts still need human
review before their values become operational timetable records.

## Local use

From the repository root:

```sh
backend/.venv/bin/python -m pip install -r backend/requirements.txt
backend/.venv/bin/python backend/scripts/build_rag_corpus.py --semantic
backend/.venv/bin/python backend/scripts/upgrade_rag_database.py --apply
```

If the encoder is not cached, add `--allow-download` to the build command.
Build-time model downloads are explicit; chat requests never download models.

Configure `backend/.env` without replacing existing database credentials:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
LLM_BASE_URL=http://localhost:11434
LLM_TIMEOUT_SECONDS=25
LLM_CHECK_CLAIMS=true
LLM_KEEP_ALIVE=15m
EMBEDDING_PROVIDER=sentence-transformer
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_LOCAL_FILES_ONLY=true
RAG_CORPUS_PATH=data/rag/corpus.jsonl
```

Start Ollama (`ollama serve`) and ensure the selected model is installed
(`ollama pull qwen3:8b`). Run the backend from `backend/` with
`.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`, and run `npm run dev`
from `frontend/`. The local development setup created during this upgrade uses
port 11435 for its isolated Ollama server; use the configured `.env` URL.

Useful diagnostics:

- `/api/v1/health`: process liveness, not a claim about data or model quality.
- `/api/v1/health/ready`: database, history schema, evidence, and installed
  answer-model readiness.
- `/api/v1/rag/status`: actual corpus counts and semantic/generation configuration.
- `/api/v1/rag/search`: inspect passages retrieved for a question.
- `backend/data/rag/corpus.audit.json`: rejected content and extraction warnings.

## Docker and university deployment

Copy `.env.example` to `.env` and set a unique random `AUTH_SECRET` and database
password. Production startup rejects the built-in placeholder signing secrets.
Use URL-safe database passwords or provide a correctly URL-encoded connection
URL. The database and backend ports bind to loopback; Nginx is the public entry.

```sh
docker compose --profile local-llm up -d --build
docker compose --profile local-llm exec ollama ollama pull qwen3:8b
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/health/ready').read().decode())"
```

Alternatively point `LLM_BASE_URL` at a managed local Ollama service and omit the
`local-llm` profile. GPU access is environment-specific; the compose service does
not promise GPU acceleration. Existing Docker database volumes do not rerun init
scripts: apply `database/rag_upgrade.sql` to that database separately. Never
remove a database volume to apply an upgrade.

The existing project bootstrap seed contains a development administrator. Change
its password and remove demo accounts before public use. Deploy behind university
HTTPS, configure your origin, restrict database access, and arrange backups.
The backend image includes the sentence encoder; the versioned corpus and vectors
are mounted read-only. Check `/health/ready`, then validate real university
questions with departmental reviewers before public release. Container builds
and a university deployment were not performed during this upgrade because the
local Docker daemon was not running.

## Evaluation

```sh
cd backend
LLM_PROVIDER=unconfigured .venv/bin/python -m pytest -q
RUN_RAG_DB_TESTS=1 LLM_PROVIDER=unconfigured .venv/bin/python -m pytest -q tests/test_rag_database.py
.venv/bin/python scripts/evaluate_rag.py
.venv/bin/python scripts/evaluate_rag.py --lexical-only --output evaluation/rag_lexical_report.json
.venv/bin/python scripts/evaluate_rag.py --live --base-url http://localhost:11434 --output evaluation/rag_live_report.json
.venv/bin/python scripts/evaluate_chat.py --base-url http://127.0.0.1:8000
.venv/bin/python scripts/evaluate_chat.py --check-report evaluation/chat_acceptance.json
```

`evaluation/rag_questions.json` contains a small 28-question regression set,
including typos, Roman Urdu, Urdu, faculty, curriculum, historical timetables,
and unknown questions. The report distinguishes evidence recall and ranking
from live generation. A retrieval pass means a matching source passage was
found within six results. It is not an answer correctness percentage. Review
live answers for correctness, completeness, source conflicts, appropriate
abstention, latency and freshness. Add independent unseen questions before
acceptance; this set was used to develop and debug retrieval.

`scripts/evaluate_chat.py` checks the running API for the reported greeting bug,
greetings followed by questions, fees, faculty, admissions, prerequisites,
programme ambiguity, missing FYP procedures and unsupported questions. The fee
expectation is deliberately tied to the archived Fall 2025 snapshot; update the
case after a reviewed data refresh. Passing these twelve checks does not mean
every university question is answered correctly. Browser regressions can run
against the local services with:

```sh
cd frontend
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm run test:e2e -- e2e/conversation.spec.js --output /tmp/qau-browser-results
```

Guest context stays in the browser and is bounded to eight turns. Signed-in
history uses database ownership checks. Saved messages retain citation metadata.
Greetings and thanks do not replace the last academic question when resolving
follow-ups. Changing the academic topic clears the browser's previous course
context so it cannot filter an unrelated programme question.
The frontend sanitizes model Markdown and displays inspectable source excerpts
instead of a misleading confidence percentage.
Portal fee and policy views display stored source status. Unauthenticated fee
records carry an explicit notice and are not presented as a current payment
quote. Unauthenticated prerequisite links are not labelled published rules.

## Results from this upgrade

The rebuilt snapshot contains 633 bounded passages from 35 distinct documents.
The final development regression found expected evidence for 27 of 28 questions
(recall@6 0.96, MRR@6 0.79). The remaining question requires an MS Data Science
duration that is absent from the supplied programme page. These are retrieval
measurements on a development set, not a certificate of answer accuracy.

The follow-up acceptance run exercised twelve actual API turns. The exact
reported `hi'` message returned a short greeting in 62 ms end to end (2 ms inside
the handler), without citations or a model call. The semester-fee question
returned the archived Regular total in 27 ms. Research groups returned the three
published names; the first request took 3.1 seconds while loading the encoder.
Admissions and faculty questions took approximately 12–16 seconds, and the
provided prerequisite lookup took about 23 seconds. A personal credit-load
question asked for the programme in 57 ms. FYP submission rules now return a
direct explanation of the missing departmental procedure without a model call:
95 ms with the encoder warm, or 3.1 seconds on the first request after restart.
All responses are retained in `backend/evaluation/chat_acceptance.json`.

These are local measurements, not production latency guarantees. Broader
generation and concurrent-user testing remain necessary before university-wide
rollout. A trial of the installed smaller Llama model was faster but failed the
evidence checks; the local configuration retains Qwen. The complete BS rules
PDF is absent from the archived originals: attempts to restore the official
download stalled and no partial PDF was added to the corpus. Scanned documents,
current approved policies and departmental FYP SOPs still need source review.

Validation passed: 156 backend tests, two opt-in PostgreSQL integration tests,
eight frontend tests, three browser regressions, the frontend production build,
and Compose configuration
validation. Three tests in the ordinary backend run are opt-in and skipped;
the two history/portal integration cases were run separately. The older full
pgvector bootstrap integration was not run against this legacy local database.
The frontend runtime dependency audit reported zero vulnerabilities.
The checked acceptance results are recorded in
`backend/evaluation/chat_acceptance_report.json`. They cover the reported failure
and selected university questions; they are not an independent accuracy audit.
