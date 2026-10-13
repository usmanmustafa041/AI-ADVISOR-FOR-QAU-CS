PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS document (
 id TEXT PRIMARY KEY, uri TEXT NOT NULL UNIQUE, origin TEXT NOT NULL,
 visibility TEXT NOT NULL DEFAULT 'public' CHECK(visibility='public')
);
CREATE TABLE IF NOT EXISTS document_version (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES document(id),
 checksum TEXT NOT NULL, raw_path TEXT NOT NULL, parser_version TEXT NOT NULL,
 captured_at TEXT NOT NULL, published_at TEXT, title TEXT NOT NULL,
 programme TEXT, topic TEXT NOT NULL, effective_term TEXT, cohort_start INTEGER,
 applies_onwards INTEGER NOT NULL DEFAULT 0,
 review_status TEXT NOT NULL, warnings TEXT NOT NULL, UNIQUE(document_id,checksum,parser_version)
);
CREATE TABLE IF NOT EXISTS evidence_chunk (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES document_version(id),
 page INTEGER, section TEXT, content TEXT NOT NULL CHECK(length(content)>0),
 semester INTEGER, coordinates TEXT, UNIQUE(version_id,page,section,content)
);
CREATE INDEX IF NOT EXISTS chunk_version ON evidence_chunk(version_id);
CREATE INDEX IF NOT EXISTS version_scope ON document_version(programme,cohort_start,topic);
CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(chunk_id UNINDEXED,title,section,content,tokenize='unicode61');
CREATE TABLE IF NOT EXISTS source_review (
 id INTEGER PRIMARY KEY, version_id TEXT NOT NULL REFERENCES document_version(id),
 decision TEXT NOT NULL CHECK(decision IN ('approved','rejected','needs_review')),
 reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS program (code TEXT PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admission_cohort (
 programme TEXT NOT NULL REFERENCES program(code), batch TEXT NOT NULL,
 PRIMARY KEY(programme,batch)
);
CREATE TABLE IF NOT EXISTS study_scheme (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES document_version(id),
 programme TEXT NOT NULL REFERENCES program(code), effective_start INTEGER,
 applies_onwards INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS semester (
 scheme_id TEXT NOT NULL REFERENCES study_scheme(id), number INTEGER NOT NULL CHECK(number BETWEEN 1 AND 12),
 PRIMARY KEY(scheme_id,number)
);
CREATE TABLE IF NOT EXISTS course (code TEXT PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scheme_course (
 scheme_id TEXT NOT NULL, semester INTEGER NOT NULL, course_code TEXT NOT NULL REFERENCES course(code),
 lecture_credits INTEGER, lab_credits INTEGER, total_credits INTEGER,
 chunk_id TEXT NOT NULL REFERENCES evidence_chunk(id),
 PRIMARY KEY(scheme_id,semester,course_code), FOREIGN KEY(scheme_id,semester) REFERENCES semester(scheme_id,number)
);
CREATE TABLE IF NOT EXISTS prerequisite_rule (
 id TEXT PRIMARY KEY, course_code TEXT NOT NULL REFERENCES course(code),
 operator TEXT NOT NULL CHECK(operator IN ('AND','OR','SINGLE')),
 expression TEXT NOT NULL, chunk_id TEXT NOT NULL REFERENCES evidence_chunk(id)
);
CREATE TABLE IF NOT EXISTS conflict (
 id TEXT PRIMARY KEY, left_version TEXT NOT NULL REFERENCES document_version(id),
 right_version TEXT NOT NULL REFERENCES document_version(id), description TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', CHECK(left_version<>right_version)
);
CREATE TABLE IF NOT EXISTS ingestion_run (
 id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, report TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversation (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
 state TEXT NOT NULL, title TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS conversation_owner ON conversation(owner,updated_at);
CREATE TABLE IF NOT EXISTS message (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
 role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
 metadata TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
 id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES message(id), owner TEXT NOT NULL,
 helpful INTEGER NOT NULL, reason TEXT, created_at REAL NOT NULL,
 UNIQUE(message_id,owner)
);
