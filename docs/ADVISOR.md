# QAU CS Advisor — architecture and operations

A retrieval-augmented assistant that answers student questions **only from what the Department of
Computer Sciences has published**: the pages of <https://cs.qau.edu.pk> and the PDFs linked from
them. It replaces the earlier layered chatbots (`backend/app`, `backend/chatbot_v3`), which are left
untouched for reference.

```
cs.qau.edu.pk (pages + PDFs)                                         students (React web UI, SSE)
        │                                                                     │
  ┌─────▼─────┐   ┌───────────┐   ┌──────────┐   ┌────────────┐      ┌────────▼────────┐
  │ Crawler   │──▶│ Extractors│──▶│ Chunker  │──▶│ Index      │◀─────│ Retriever       │
  │ robots,   │   │ HTML, PDF,│   │ headings,│   │ bundle:    │      │ BM25 + dense +  │
  │ retries,  │   │ OCR, grids│   │ tables,  │   │ chunks +   │      │ entity boosts + │
  │ ETag      │   │ + derived │   │ aliases  │   │ vectors    │      │ re-rank         │
  └───────────┘   │ directories│  └──────────┘   │ (versioned)│      └────────┬────────┘
   snapshots/     └───────────┘                  └────────────┘               │ evidence
   (raw, hashed)                                                     ┌────────▼────────┐
                                                                     │ Answer service  │
   Admin console ── settings (Gemini key, models, notice) ──────────▶│ rewrite → cite →│
                                                                     │ validate → log  │
                                                                     └────────┬────────┘
                                                              Gemini ◀── router ──▶ Ollama ──▶ extractive
```

## Why answers are accurate

| Mechanism | Purpose |
|---|---|
| **Structure-preserving extraction** | Course pages become one self-describing record (code, credits, prerequisites, instructors, semester). FAQ accordions become one Q/A chunk each. Tabbed scheme panels, merged-cell timetables, two-column scheme PDFs and scanned PDFs (OCR) are each handled explicitly. |
| **Derived directories** | "List all…" and "who works on X" questions can't be answered from top-k pages, so faculty directory, research-interest map, per-programme course catalogues, prerequisite graph and scheme index are generated from the primary records at build time. |
| **Hybrid retrieval** | BM25 (with domain synonyms, ordinals, course-code normalisation `CS-211 ≡ CSC-211`) fused with multilingual dense vectors, then entity boosts (course codes/names, faculty names, intent) and an optional cross-encoder re-ranker. |
| **Grounded generation** | The model sees numbered SOURCES and must cite `[n]`; invented citation numbers are stripped. Facts must come from sources; gaps are admitted with the office contact. Scheme/term/programme differences must be labelled, not blended. |
| **Grounding guards (code, not model)** | After generation, any sentence naming an organisation, bracketed acronym or titled person that appears nowhere in the sources or the student's message is removed; uncited generalisations about "how the university usually works" are removed; an uncited answer that makes university claims is replaced by "I couldn't find that". Added after a local model invented a "Faculty of Computing and Informatics". Deliberately narrow: a per-sentence "must cite" rule would have damaged a third of correct answers. |
| **Freshness honesty** | Each source carries its own note ("2012 University Calendar", "scanned notice read with OCR"). OCR'd text is down-ranked below clean pages. |
| **Privacy** | Merit lists naming applicants are never indexed. Conversations/logs are deleted after `ADVISOR_HISTORY_RETENTION_DAYS` (90). |

## AI providers (Gemini → Ollama → extractive)

Set the Gemini key in **Admin → AI providers** (stored encrypted; never shown again; *Check key*
verifies it before saving and lists the models it can use). Order per request:

1. **Gemini** if a key is saved and enabled (or forced via *Preferred provider*).
2. **Ollama** (local, default `qwen3:8b`) if Gemini is missing, rate-limited, down or blocked.
3. **Extractive fallback** – if neither works the student still gets the best passages verbatim.

Failures before the first token fail over silently; a failure mid-answer restarts the answer on the
next provider. A circuit breaker pauses a failing provider (configuration errors for longer). The
Ollama context is smaller than Gemini's because a local 8B model reads ~400 tokens/s.

## Running it

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-advisor.txt   # + tesseract for OCR
.venv/bin/python -m advisor.cli refresh                  # crawl cs.qau.edu.pk, build the index
.venv/bin/python -m advisor.cli create-admin admin       # prompts for a password (10+ chars)
cd ../web && npm ci && npm run build && cd ../backend
ADVISOR_SERVE_FRONTEND_DIR=../web/dist .venv/bin/python -m advisor.cli serve --port 8000
# students: http://host:8000/     admin: http://host:8000/#/admin
```

Docker: `docker compose -f deploy/advisor/docker-compose.yml --profile local-llm up -d`.
Production notes: terminate TLS in nginx/Caddy (`deploy/advisor/nginx.conf` disables buffering for
streaming), set `ADVISOR_TRUST_PROXY_HEADERS=true`, schedule `advisor.cli refresh` nightly
(`deploy/advisor/advisor-refresh.timer`), back up `ADVISOR_DATA_DIR`.

### Inside the portal (recommended)

`./scripts/run-all.sh` starts the portal API (:8001), the engine (:8010, with `ADVISOR_AUTH_VERIFY_URL`
pointing at the portal's `/api/v1/auth/me`) and the portal interface (:5173). Single sign-on works by the
engine forwarding the caller's bearer token to that URL; nothing is trusted unless the portal confirms it.

* **Guests**: the browser sends its own recent turns and `ephemeral: true`; the server stores nothing
  (a question is logged only if it was abstained, errored or degraded, so gaps can be fixed).
* **Students**: conversations are owned by the portal user id; one student can never read or delete
  another's (404), and feedback is checked the same way. History uses `/me/history`.
* **Administrators**: a portal admin is accepted by the engine's admin API through the same check, so the
  admin panel's *Chatbot Engine* page needs no second login. Without single sign-on that page falls back to
  the engine's own admin login (`advisor.cli create-admin`).
* **Frontend wiring**: the portal calls `/advisor/api/v1/*`. In development Vite proxies `/advisor` to the
  engine (`VITE_ADVISOR_PROXY`, default `http://127.0.0.1:8010`) and `/api` to the portal API
  (`VITE_API_PROXY`). In production nginx does the same (see `deploy/advisor/nginx.conf`); streaming
  needs `proxy_buffering off`. Set `ADVISOR_TRUST_PROXY_HEADERS=true` behind a proxy.
* `VITE_CHAT_ENGINE=legacy` restores the previous chat engine inside the same interface.

### Command line

| Command | Purpose |
|---|---|
| `crawl` / `ingest` / `index` | the pipeline stages individually |
| `refresh [--no-crawl]` | crawl → extract → embed → atomically publish; refuses an obviously broken crawl |
| `search "q" [--rerank]` | debug retrieval (scores and why each chunk ranked) |
| `ask "q"` | answer from the terminal |
| `eval-retrieval`, `eval-answers` | measure quality (`--set golden` or `golden_holdout`) |
| `create-admin`, `serve` | operations |

## Operating model

* **Index bundles** live in `indexes/<build>/` (chunks + vectors + manifest). `CURRENT` is switched
  atomically; Admin → Knowledge can roll back. Three builds are kept.
* **Caching**: identical single-turn questions are served from memory (6 h, cleared on index change,
  evicted on 👎).
* **Capacity**: the retrieval stage (query embedding, BM25, re-rank of 12 candidates) costs ≈0.4 s CPU
  per question — about 2.4 questions/s on an M1 Max with the LLM excluded. Scale out with
  `uvicorn --workers N` (each worker holds its own models, ≈1 GB) or more replicas; SQLite WAL
  handles the logging writes. Identical questions never reach the model twice (6 h cache).
* **Concurrency/limits**: per-IP sliding-window rate limit; bounded concurrent local generations;
  queue shedding falls over to the next provider.
* **Observability**: Admin → Overview (volume, answer rate, latency percentiles, providers,
  languages), *Questions → "Couldn't find"* shows exactly which information the website is missing,
  *Feedback* lists 👎 with the question and answer.
* **Security**: scrypt passwords, revocable server-side admin sessions, lock-out after 5 failures,
  secrets encrypted with a key outside the database, CSP and hardening headers, no secrets in URLs
  or error messages.

## Evaluation

`advisor/eval/golden.json` (tuning set) and `golden_holdout.json` (written afterwards from randomly
sampled chunks and never tuned against). Every gold pattern is validated against the corpus, so the
test cannot silently rot. See the results table in the repository README.

## Timetable questions (exact lookup)

The timetable PDF is a grid, so day/class/teacher/room questions are answered by **lookup, not generation**
(`backend/advisor/rag/timetable_qa.py`). At index time the PDF's grid cells are joined to the course-allocation
tables and saved as `timetable.json` in the index bundle. A question such as *"monday ko 8th semester ki kon
kon c classes hai"* is parsed into filters — day (also today/aaj/kal), semester (8th / VIII / eighth / آٹھویں),
section (regular/morning, self-support/evening), teacher (fuzzy first/last name), room, time ("10 baje") and
course (code, abbreviation or title) — in English, Roman Urdu or Urdu, and rendered as a table with
12-hour times, one per day, plus "Other days" chips. Follow-ups ("aur Wednesday?") inherit the class from the
previous question. Anything that is not clearly a timetable lookup (exam dates, "who teaches DS", "when was
Dr X appointed") is left to normal retrieval. Rebuild after a new timetable is published
(`advisor.cli refresh`, or *Rebuild* in the admin console); `tests_advisor/data/timetable_fall2026.json` is the
test fixture.

### Editing the timetable by hand

Admin → Chatbot Engine → **Timetable** lets the department correct or fully enter the timetable without a PDF.
The PDF-derived data is never modified; edits are stored in the operational database
(`timetable_state` / `timetable_audit`) as an overlay that is merged each time a student asks
(`backend/advisor/timetable_store.py`), so a re-crawl or rebuild never overwrites them and changes apply instantly.

* **Modes** — *PDF + my edits* (default), *Manual only* (the PDF is ignored, including its text in free-form answers),
  *PDF only* (edits kept but paused).
* **What can be done** — add a session; change the day / time / room / section / teacher of a PDF class; hide
  (cancel) a PDF class and restore it; change the teacher of a course for a whole class; set the term name and
  effective date; import a CSV / Excel file (preview first, bad rows are listed, nothing is applied until confirmed);
  download the effective timetable as CSV; **Undo** the last change (every save keeps a snapshot, 200 kept);
  **Reset to PDF**.
* **Safety** — every entry is validated (day, time order and range, room, semester, course code); room and teacher
  clashes are shown as warnings that must be confirmed ("Save anyway"); exported cells that start with `= + @ -` are
  neutralised against spreadsheet formulas; only administrators can use these endpoints.
* **Edits that no longer match** — PDF cells are identified by a stable id. If a new PDF changes a cell that was
  edited, that edit is reported as *orphaned* and ignored (never applied to the wrong class); added sessions always
  survive.
* **What students see** — edited / added rows carry a ✎ and a note "updated by the department on <date>".
* **Backups** — the edits live in `<data dir>/advisor.sqlite3`; include it in backups.

## Fee questions (exact lookup)

The three fee pages (Bachelor, MPhil, PhD) each hold several look-alike tables: the one for **Computer Science**
(with IT, Law, Pharmacy …, and rows that are themselves split per programme), one for all *other* programmes, and one
for *foreign* students in US dollars. Read as running text they get mixed up, so at index time
(`backend/advisor/ingest/fees.py`) each table is parsed separately, with its heading, term and columns, saved as
`fees.json` in the index bundle, and rendered as clearly labelled text for search ("… — NOT for Computer Science
students"). `backend/advisor/rag/fees_qa.py` then answers fee questions by lookup, in English, Roman Urdu or Urdu:
*per-semester fee* (Category B), *admission fee* (Category A, once), *first-semester total* (A+B), *summer tuition per
course*, *one-time charges* (degree, migration certificate, grade card …) and *foreign-student fees*, for BS morning
/ evening, MPhil and PhD. A bare "fee structure" question shows the per-semester / admission / first-semester table
for every programme with each programme's term (BS is Fall 2026, MPhil/PhD Fall 2025 on the pages). Follow-ups
("aur evening ki?") inherit the previous fee question. The **MS fee page is not available** to the crawler (it sits
behind a Cloudflare challenge), so the assistant says so and points to the department office instead of guessing.
Refunds, waivers, scholarships, hostel fees and "how to pay" are not fee amounts and go through normal answering.
After the fee pages change, rebuild (`advisor.cli refresh` or *Rebuild* in the admin console).

## Department documents (not on the website)

Official files such as **FYP submission rules**, SOPs or circulars can be added as PDF, Word, text or
Markdown: Admin → Knowledge → *Department documents* (give it a title, optional "effective from" and note),
or `python -m advisor.cli add-document file.docx --title "BS FYP submission rules" --effective "Fall 2026"`,
then *Rebuild only*. They rank as official sources and are cited by their title. Without such a document the
assistant says the detailed rules are not published, and shows only what the website does say (the FYP
course description, the 22 Jan 2027 submission deadline, the internship rule).

## Prerequisites

Chains such as PSP → OOP → Data Structures are computed by code from the department's verified
prerequisite list plus the website's course pages, with source disagreements always reported. See
[PREREQUISITES.md](PREREQUISITES.md).

## Known limits (be honest with users)

* Source of truth is the website: if a fact isn't published there the assistant says so — that is
  the intended behaviour, and the *Couldn't find* report tells staff what to publish.
* The weekly timetable grid is reconstructed from the PDF layout; the answer cites the PDF so students
  can verify. Scanned PDFs are OCR text and may contain errors.
* Regulations come from the 2012 University Calendar; amendments after that are not on the site.
* Grounding guards remove invented *named* entities, not every possible invented claim (a plausible-sounding
  but uncited sentence without hedging words can still slip through). Hosted Gemini is expected to need them less.
* Small local models (8B) occasionally omit an item from a long list and write weaker Urdu than
  Gemini. Configuring Gemini is recommended for production quality; Ollama is a safety net.
* Student-specific data (grades, registration, personal eligibility) is intentionally out of scope.
