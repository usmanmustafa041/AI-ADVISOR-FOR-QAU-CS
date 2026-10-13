-- Additive migration. Deleting a saved answer or user also deletes its vote.
BEGIN;
CREATE TABLE IF NOT EXISTS chat_feedback (
    message_id UUID PRIMARY KEY REFERENCES chat_messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
    reason TEXT NOT NULL CHECK (reason IN
        ('helpful', 'incorrect', 'outdated', 'missing_information', 'unclear')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_user ON chat_feedback(user_id);
COMMIT;
