-- Add missing provenance columns to legacy databases. No facts or approvals are seeded.
BEGIN;
ALTER TABLE source_records ADD COLUMN IF NOT EXISTS authority TEXT;
ALTER TABLE source_records ADD COLUMN IF NOT EXISTS local_path TEXT;
ALTER TABLE source_records ADD COLUMN IF NOT EXISTS checksum_sha256 CHAR(64);
ALTER TABLE source_records ADD COLUMN IF NOT EXISTS effective_from DATE;
ALTER TABLE source_records ADD COLUMN IF NOT EXISTS effective_to DATE;
ALTER TABLE source_records ADD COLUMN IF NOT EXISTS is_time_sensitive BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE source_records ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE source_records ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE source_records ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_number INTEGER;
COMMIT;
