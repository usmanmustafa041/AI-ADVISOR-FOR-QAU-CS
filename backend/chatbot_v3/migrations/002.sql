CREATE TABLE IF NOT EXISTS faculty_member (
 id TEXT PRIMARY KEY, published_name TEXT NOT NULL,
 version_id TEXT NOT NULL REFERENCES document_version(id),
 chunk_id TEXT NOT NULL REFERENCES evidence_chunk(id)
);
CREATE TABLE IF NOT EXISTS published_contact (
 id TEXT PRIMARY KEY, faculty_id TEXT NOT NULL REFERENCES faculty_member(id),
 contact_type TEXT NOT NULL CHECK(contact_type IN ('email','office_phone')),
 value TEXT NOT NULL, chunk_id TEXT NOT NULL REFERENCES evidence_chunk(id),
 UNIQUE(faculty_id,contact_type,value)
);
CREATE TABLE IF NOT EXISTS policy_version (
 id TEXT PRIMARY KEY REFERENCES document_version(id), title TEXT NOT NULL,
 programme TEXT, effective_term TEXT
);
CREATE TABLE IF NOT EXISTS fee_schedule (
 id TEXT PRIMARY KEY REFERENCES document_version(id), title TEXT NOT NULL,
 programme TEXT, effective_term TEXT, review_status TEXT NOT NULL
);
