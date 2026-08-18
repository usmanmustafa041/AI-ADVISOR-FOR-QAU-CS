# Privacy and production-provider decision record

This is a decision template, not an approval. It prevents deployment from
silently assuming access to student records or an unapproved AI vendor.

| Decision | Safe default | Required before production |
|---|---|---|
| Stored student fields | None; public academic data only | Department/CMS owner signs an allowed-field list |
| CMS integration | Disabled (`CMS_ENABLED=false`) | Written API, consent, and access approval |
| Retention | 30 days for diagnostics; no transcript storage | Privacy owner confirms period and deletion process |
| Admin access | No production admin writes | Named roles, MFA, least privilege, two-person approval |
| Embeddings | Deterministic 384-dimensional fallback for tests only | Pin provider, model, dimension, region, and version |
| Response LLM | Unconfigured; safe fallback responses only | Approve vendor, model, data terms, and outage behavior |

Set approved values in a private `.env`; never commit keys or student records.
The readiness script intentionally fails while `LLM_PROVIDER` is unconfigured
or critical official-data rows are missing.

## Production selection record

- Embedding provider/model/version: `TBD — department approval required`
- Embedding dimension and indexing migration: `TBD`
- LLM provider/model/version: `TBD — department approval required`
- Data residency and subprocessors review: `TBD`
- CMS fields, consent, retention, deletion owner: `TBD`
- Admin roles and approval workflow: `TBD`
- Decision owner/date: `TBD`
