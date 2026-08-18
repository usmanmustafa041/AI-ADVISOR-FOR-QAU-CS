# Independent query review workflow

`review_queue_200.csv` is a generated candidate queue, not a validated test set.
For each row:

1. Reviewer 1 independently labels intent, language, and entities.
2. Reviewer 2 independently labels the same fields without seeing Reviewer 1.
3. An adjudicator resolves disagreements in `adjudicated_intent` and `notes`.
4. Set `review_status=approved` only after adjudication.
5. Export only approved rows into a held-out test file.

At least two reviewers are needed for an independent agreement measure. Record
reviewer identities, date, and annotation guide version outside the public test
file if privacy requires it.

