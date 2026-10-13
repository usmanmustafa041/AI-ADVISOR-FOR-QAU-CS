-- ============================================================================
-- AUTH TABLES SCHEMA
-- Quick fix for missing authentication tables
-- ============================================================================

-- Enable extensions if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- App Users Table
CREATE TABLE IF NOT EXISTS app_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL DEFAULT 'User',
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'admin')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auth Sessions Table
CREATE TABLE IF NOT EXISTS auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    user_agent TEXT
);

-- Password Reset Tokens Table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(lower(email));
CREATE INDEX IF NOT EXISTS idx_app_users_active ON app_users(active);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token_hash ON password_reset_tokens(token_hash);

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_app_users_updated_at ON app_users;
CREATE TRIGGER trigger_app_users_updated_at
    BEFORE UPDATE ON app_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create default admin user (password: admin123)
INSERT INTO app_users (full_name, email, password_hash, role)
VALUES (
    'Admin User',
    'admin@qau.edu.pk',
    'pbkdf2_sha256$240000$84a920c41bfa9df955d519515d6efdad$edfb2033197d91f5aa654af93fc2d24c808fc42ab12ecd75e3f5724d7bf0a761',
    'admin'
)
ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash;

-- Create test student user (password: student123)
INSERT INTO app_users (full_name, email, password_hash, role)
VALUES (
    'Test Student',
    'student@qau.edu.pk',
    'pbkdf2_sha256$240000$5929c4521e74f0999c4c2a15aba4ad3f$801fef0c56607331b935e8186f677fe6e372142c068c4ebb132a6b986df7f3cb',
    'student'
)
ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash;

-- Verification
DO $$
DECLARE
    user_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO user_count FROM app_users;
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ AUTH TABLES CREATED';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Total users: %', user_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Default credentials:';
    RAISE NOTICE 'Admin: admin@qau.edu.pk / admin123';
    RAISE NOTICE 'Student: student@qau.edu.pk / student123';
    RAISE NOTICE '========================================';
END $$;
