# Rule engine — Step 7

The rule engine is deterministic and does not call an LLM. It currently covers
the published BS rules represented in the database seed:

- 15–18 credit hours as the normal semester load.
- 12–21 credit hours only with the documented exceptional approvals.
- CGPA below 1.0 as dropped and 1.0–<2.0 as probation.
- Three maximum probation chances.
- Up to 51 course-exemption credit hours.
- Explicit prerequisite checks with minimum-grade support.

`dataset_complete=false` deliberately returns `decision=unverified` for
eligibility checks. This protects students from a false “eligible” answer while
the department’s complete prerequisite matrix is still missing.

API endpoints:

- `POST /api/v1/rules/prerequisite-check`
- `POST /api/v1/rules/semester-load`
- `POST /api/v1/rules/progression`
- `POST /api/v1/rules/exemption`

