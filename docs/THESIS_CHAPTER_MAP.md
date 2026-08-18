# Thesis chapter map

## Chapter 1 — Introduction

Problem context, QAU CS advising pain points, objectives, scope, constraints,
and contributions.

## Chapter 2 — Literature review

Academic advising systems, intent classification, multilingual NLP, entity
recognition, rule engines, RAG, vector retrieval, explainable answers, and
privacy-aware student systems.

## Chapter 3 — Requirements and data governance

Use `academic-data/README.md`, the source registry, the department data request,
and `docs/REQUIREMENTS_TRACEABILITY.csv`. Explain source priority, effective
dates, verification, and safe fallback behavior.

## Chapter 4 — System design

Use `database/ERD.md`, the FastAPI structure, NLP pipeline, rule engine, RAG
pipeline, and React interface. Include the structured-query vs policy-query
routing decision.

## Chapter 5 — Implementation

Describe PostgreSQL/pgvector, API endpoints, multilingual DistilBERT classifier, entity
extractor, deterministic rules, document ingestion, and frontend.

## Chapter 6 — Evaluation

Use `backend/evaluation/nlp_report.json`, the test suite results, and the final
evaluation protocol. Report dataset composition and limitations honestly.

## Chapter 7 — Conclusion and future work

Complete prerequisite matrix, current operational feeds, CMS integration,
transformer comparison, response generation, admin authentication, and privacy
controls.
