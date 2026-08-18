-- Completeness additions for the document's authentication and administration flows.
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_active
    ON auth_sessions (user_id, expires_at) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

UPDATE app_users SET full_name = CASE
    WHEN role='admin' THEN 'QAU CS Administrator'
    ELSE split_part(email, '@', 1)
END WHERE full_name IS NULL;

ALTER TABLE app_users ALTER COLUMN full_name SET NOT NULL;

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_by UUID REFERENCES app_users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO system_settings (key, value, description) VALUES
('advisor_name', '"QAU CS Academic Advisor"'::jsonb, 'Name displayed for the advisor'),
('low_confidence_threshold', '0.55'::jsonb, 'Confidence below which clarification is requested'),
('guest_access_enabled', 'true'::jsonb, 'Allow chat without signing in'),
('data_disclaimer', '"Synthetic records are clearly labelled DEMO DATA."'::jsonb, 'Public data-quality notice')
ON CONFLICT (key) DO NOTHING;
