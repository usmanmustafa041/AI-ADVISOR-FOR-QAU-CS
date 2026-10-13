-- ============================================================================
-- DATABASE SETUP (NON-DESTRUCTIVE)
-- ============================================================================
-- This script sets up the PostgreSQL database, user, and permissions
-- All operations are safe and idempotent
-- ============================================================================

-- Create user if not exists (PostgreSQL 9.1+)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'qau_advisor') THEN
        CREATE USER qau_advisor WITH PASSWORD 'qau_advisor_local';
        RAISE NOTICE '✅ Created user: qau_advisor';
    ELSE
        RAISE NOTICE '✅ User already exists: qau_advisor';
    END IF;
END
$$;

-- Create database if not exists
SELECT 'CREATE DATABASE qau_advisor OWNER qau_advisor'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'qau_advisor')\gexec

-- Connect message
\echo '✅ Database setup complete'
\echo ''
\echo 'Next steps:'
\echo '1. Connect to database: \\c qau_advisor'
\echo '2. Grant permissions: GRANT ALL ON SCHEMA public TO qau_advisor;'
\echo '3. Run schema: \\i backend/scripts/init_knowledge_base_schema.sql'
