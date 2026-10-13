# QAU CS Advisor

A production-oriented assistant for the **Department of Computer Sciences, Quaid-i-Azam University**.
It answers students' questions from the department website (<https://cs.qau.edu.pk>) and the PDFs it
links to — courses, prerequisites, schemes of study, faculty, admissions, fees, the academic calendar,
timetables and regulations — in English, Urdu and Roman Urdu, with citations.

**Start here:** [docs/ADVISOR.md](docs/ADVISOR.md) (architecture, operations, admin guide, limits) and
[docs/PREREQUISITES.md](docs/PREREQUISITES.md) (prerequisite chains, data sources, adding schemes).

| Part | Where |
|---|---|
| Chatbot engine: ingestion, retrieval, answering, API, admin | `backend/advisor/` (Python ≥ 3.12) |
| **Portal interface (the one students and admins use)** | `frontend/` (React + Vite) — its Chat page and *Chatbot Engine* admin page are served by the engine |
| Portal accounts, study plan, fees, timetable pages | `backend/app/` (legacy portal API, unchanged) |
| Standalone minimal UI (optional, no portal needed) | `web/` |
| Tests | `backend/tests_advisor/` (214), `frontend/src/**/*.test.jsx` (33), `web/src/*.test.js` (6) |
| Evaluation sets | `backend/advisor/eval/golden.json`, `golden_holdout.json`, `golden_prereq.json` |
| Deployment | `deploy/advisor/` (Docker, systemd, nginx) |

The portal keeps its familiar interface (sidebar with Chat, Study Plan, Courses, Fees, Timetable,
Policies, History, and the admin panel). Only the engine behind **Chat** changed; it is reached through
`/advisor/*` so it never collides with the portal's own `/api/v1` routes.

## Quick start (the whole portal on one machine)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-advisor-dev.txt
.venv/bin/python -m advisor.cli refresh                 # crawl the site, build the index (~5 min, once)
cd ../frontend && npm ci && cd ..
./scripts/run-all.sh                                    # portal API :8001, engine :8010, portal UI :5173
```

Open <http://127.0.0.1:5173>. Guests chat without anything being stored; signed-in students get
saved conversations and History (the engine asks the portal who the caller is, so there is one
account system). Portal administrators open **Chatbot Engine** in the admin panel and paste the
Gemini API key under *AI providers* (verified, encrypted, never shown again). Without a key the
assistant uses the local Ollama model (`ollama pull qwen3:8b`); if both are down students still
receive the matching passages.

Switching back is one setting: `VITE_CHAT_ENGINE=legacy` in the frontend environment restores the old
chat engine untouched. The standalone UI is still available: `ADVISOR_SERVE_FRONTEND_DIR=../web/dist`.

## Measured quality

Questions were written from verified source text (never from the bot's own output) and graded
automatically: every required fact must appear in the answer, forbidden claims must not, and
unanswerable questions must be declined. Run with the **local `qwen3:8b` model only** (the weakest
supported configuration — no Gemini key was available while building).

| Set | Questions | End-to-end pass |
|---|---|---|
| General — tuning set (used while developing) | 109 | 108 (99.1%) |
| General — **held-out** (written afterwards, never tuned on) | 40 | 39 (97.5%) |
| Prerequisite chains (written once the engine was designed, then tuned against) | 24 | 24 (100%) — *optimistic; treat as a regression suite* |

The misses: `cal-07` ("when will results be declared?" — the model answered with admission merit-list
dates instead of the exam result date, a real miss) and `h-37` (the bot correctly declined, in wording
the answer grader did not recognise). Across earlier runs a few other questions flipped between pass and
fail (sampling at temperature 0.2), so treat each figure as ±2 questions.

Capacity of the retrieval stage on this laptop (M1 Max, CPU): ~2.4 questions/s, ≈0.4 s CPU each;
hosted-LLM generation scales independently. Median end-to-end latency with the local model is ~12 s (prompt processing dominates); cached repeats are
instant. Hosted Gemini is expected to be faster and better at long lists and Urdu — but that was
**not measured here**; run `python -m advisor.cli eval-answers` after adding a key to measure it.
