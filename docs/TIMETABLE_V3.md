# V3 timetable preview: operations and evidence

The timetable feature runs in the isolated replacement at <http://127.0.0.1:5180>. Sign in with an existing administrator account and open **Admin → Timetable Management**. The ordinary website and old timetable screen retain their existing routes. No production chatbot route has been switched and no original university document or operational PostgreSQL table has been deleted.

**The real upload is not published.** Its draft ID is `6113665f-d729-468f-9e4b-c43ae8040e3a`. It is Spring 2026, effective 20 April 2026, which is historical in October 2026. No current academic term is configured in the normal preview. Human source verification and the wider chatbot's independent accuracy gate remain open.

## Upload, verify and publish

1. Choose **Upload timetable (PDF)**. Confirm department, campus, term, kind, effective dates, source status and programme ownership. The supplied document was staged for BSCS, MPhil, PhD, MS Data Science and deficiency courses. A programme in a document heading alone does not establish extracted offerings. An official URL is a declared source location, not proof that the uploaded bytes were fetched from that URL.
2. Extraction starts automatically. The screen polls queued/parsing uploads and then displays source pages, extracted meetings, the faculty legend, unresolved issues and the diff from the active version in that scope. Unsupported or failed extraction remains staged and cannot replace active data. Duplicate bytes and metadata in the same scope return the existing version.
3. Filter by weekday, programme, semester, section, room or teacher. Click a meeting to inspect its original page and raw cell coordinates. Use **Correct / link** to change times, venue, mode, class kind, offering links or omit an erroneous meeting. Optional source annotations preserve a correction's page, coordinates and quoted text. Use **Correct legend** for verified faculty/TA, title, alias or ownership changes. Every correction requires a reason and records the actor and time.
4. Resolve each extraction flag only after checking the PDF. An ambiguous offering must be linked to verified ownership or explicitly omitted before its issue can be resolved. The real draft currently contains **95 provisional meeting groups, 57 legend offerings and 35 unresolved flags**. The printed joint Friday session has two course mappings but one meeting ID. These counts are extraction results, not an independently approved transcription.
5. Inspect every source page, the complete faculty legend and the before/after diff. Check the page checkboxes and complete-review assertion, enter a reason, then select **Publish this version**. The API independently enforces administrator role, revision, active pointer, complete-page review, resolved issues, valid times and programme ownership. Publication changes only the V3 preview's pointer for that exact scope in one transaction. Subsequent reads select the new snapshot; an in-flight read keeps a consistent previous snapshot.
6. To roll back, select the archived version, inspect its pages/diff, supply the review assertions and reason, then select **Rollback to this version**. Original uploads, records and audits remain. Published versions are immutable; upload an amended PDF for a new version. **Re-extract draft** is available for failed or unpublished versions and records the preceding preview in the audit.

Do not bulk-dismiss the real draft's flags. In particular, the two unqualified `CS-455 NLP` cells cannot be assigned between VII Self Support and VIII Regular from the shared code alone. Repeated adjacent lab cells need confirmation as extended meetings. Verify unusual printed overrides, Thursday's next-page lab annotation and Friday online mode. Projects I/II appear in the legend without identified grid times. The automated test publication omits the two NLP meetings; its 93 retained sessions are test data, not an approved official count.

**Confirm current academic term** is a separate action, based on authorized calendar information and a date interval. Publishing a historical timetable does not make that term current. Until current coverage is confirmed, “next class today” asks for coverage rather than silently using Spring 2026. Scheduled-class answers qualify holidays, cancellations and temporary room changes as unconfirmed.

## Storage, queries and access

The additive tables live in `.runtime/chatbot-v3/timetables/timetable.sqlite3`, with immutable checksum-named originals under that directory. SQLite transactions and indexed, application-owned SQL serve the 13 allowlisted query operations. The local model supplies validated filters; it never generates executable SQL or invents schedule arithmetic. Counts distinguish meeting IDs, course codes and mappings. Free-room queries consult occupancy across all relevant programme scopes and describe only published physical bookings, not guaranteed room availability.

Scope includes department, campus, term, kind and programme ownership. Disjoint programme uploads may coexist; overlapping ownership is rejected unless it replaces the identical scope. A department-wide answer may combine those disjoint scopes, with one active snapshot per scope and each row's own source version. It never combines superseded and replacement versions for the same ownership. Explicit dated queries check every relevant version's effective interval. Unavailable interval coverage produces clarification. Historical versions require an explicit historical query/version; they are excluded from ordinary timetable retrieval.

Timetable and teaching-assignment questions bypass the old timetable vectors. The V3 interpretation adapter resolves typed queries and carries semester, section, term and day across follow-ups. Application rendering produces English, Urdu or Roman Urdu introductory text and grounded schedule rows with PDF-page citations, teacher/TA information, exact printed codes and original-PDF links. Some structured labels remain in the source's English. Language quality and helpfulness still require human grading. Mixed timetable and other academic requests currently ask the student to separate the other academic part.

Admin APIs use the existing authenticated administrator dependency, with no developer-token bypass. Students and guests have read-only published queries and source PDFs. Uploads require PDF MIME, actual PDF structure, a complete file, at most 20 MiB and 40 pages, bounded page dimensions, no encryption or detected active document actions, and bounded validation/extraction subprocesses. Those checks reduce document risk; they do not certify arbitrary PDFs as safe. Source pages are locally rendered; PDFs and student history are not sent to hosted inference.

Parsing uses digital PDF coordinates, discovered grid boundaries, faculty tables and cross-page annotations. Color is not the section authority. One warm direct-parser run took 0.420 seconds for the supplied PDF; that excludes upload, validation, queue and review time. Unknown layouts and scanned PDFs require review or an additional extraction implementation; automatic OCR/vision and unattended publication are not enabled. Extraction has a 105-second parent deadline. This remains a single-worker preview; shared job coordination, deployment packaging, production load and a real signed-in administrator session still need validation.

## Run and verify

The normal preview uses `backend/.env.v3` and the already installed environment. Keep secrets out of reports. From the repository root:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m uvicorn chatbot_v3.api:app \
  --host 127.0.0.1 --port 8010 --timeout-graceful-shutdown 5
```

In a separate terminal under `frontend/`:

```sh
./node_modules/.bin/vite --config vite.rebuild.config.js
```

The timetable schema is created additively at startup in its separate database. Back up that SQLite database using SQLite's backup API and copy the immutable originals before maintenance; do not copy only an active WAL database file. For code/data rollback, stop the replacement and keep using the original website. Never restore over the operational database or perform a production route cutover without the user's separate approval.

For engineering checks, the revised-PDF fixture uses the test-only dependency recorded in `backend/chatbot_v3/tests/requirements-timetable.txt`. Do not upgrade the legacy environment in place.

```sh
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/chatbot_v3/tests -q
```

The explicit **test-only** server uses synthetic roles, separate storage under `.runtime/timetable-test-only`, and an automated fixture publication. It must stay on loopback and must never be used as the normal preview or a deployment entry point:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m chatbot_v3.scripts.timetable_test_server --serve
PYTHONPATH=backend backend/.venv/bin/python -m chatbot_v3.scripts.timetable_conversations \
  --limit 110 --output timetable-development
```

For browser checks, start `vite --config vite.timetable-test.config.js` under `frontend/`, then run `playwright test --config playwright.timetable.config.js`. The isolated API is port 8012; the isolated browser preview is port 5182. Stop both test services afterward.

## Recorded evidence and remaining gate

- The pre-edit backup is `.runtime/backups/timetable-v3-20261011-224320/`. Its 103 archive entries were read and checksum-verified; SQLite databases were backed up through SQLite. A final audit checked 425 original university assets without checksum changes. Existing unrelated dirty work was preserved.
- The visual reference covers all 95 extracted grid groups across the three PDF pages, alongside targeted legend/override checks. It was transcribed during AI development and is explicitly **not human-approved gold data**; see `backend/chatbot_v3/tests/timetable_reference_notes.md`.
- All 159 backend checks passed. They cover extraction, SQL queries, section/alias ambiguity, dates, boundaries, co-scheduled counting, independent programme/term scope, role rejection, malformed documents, interrupted jobs, version A/B publication, historical lookup, rollback and concurrent snapshot consistency. All 12 frontend checks and the preview build passed. Two actual Chromium tests passed, including the upload/correction/publish/rollback workflow and a local-model student chat with captured source evidence. Browser auth used isolated synthetic dependencies; a real account/session remains a separate acceptance check.
- The first full local-model run exercised **110 English, Urdu, Roman Urdu and typo/follow-up questions**: 108 HTTP completions and 101 automatic filter-constraint passes. Median latency was 14.492 s and p95 18.592 s. Nine failed cases are retained. A corrected 30-case run completed 28 with 28 constraint passes; a section-correction guard and one temporary inference failure remained. The final six-case replay passed all six; the previously timed-out case 82 also passed individually. These subset replays are not a fresh full-suite accuracy result. The interpreter was interim `qwen3:8b` on local Ollama.
- Fixes included preserving filters through a standalone section correction, distinguishing lab rooms from course names, normalizing Karachi time offsets and improving the model's choices for day lists, weekly load, section comparison, clashes and PSP aliases. The revised test PDF initially had a malformed page tree; the fixture was corrected and declared/decoded page counts are now checked. Earlier browser failures and every raw trial remain available.

Read `.runtime/chatbot-v3/evaluation/timetable-delivery-report.md` for final test counts, raw-run links and remaining limitations. The transcripts contain returned rows, answers and source-version/page evidence; the browser screenshots are under `.runtime/chatbot-v3/timetable-inspection/`. No independently reviewed accuracy percentage has been measured. Human validation of the real PDF and benchmark answers, stronger-model selection, real-session testing and production deployment checks remain necessary before release. Neither production cutover nor retirement of old components has been authorized.
