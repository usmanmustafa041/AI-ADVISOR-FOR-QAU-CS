PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS tt_source_document (
 id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, filename TEXT NOT NULL,
 path TEXT NOT NULL, pages INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tt_version (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES tt_source_document(id),
 scope TEXT NOT NULL, metadata TEXT NOT NULL, status TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 0, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 extraction TEXT NOT NULL DEFAULT '{}', UNIQUE(source_id,scope)
);
CREATE TABLE IF NOT EXISTS tt_offering (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES tt_version(id),
 code TEXT NOT NULL, programme TEXT NOT NULL, semester INTEGER, section TEXT NOT NULL,
 title TEXT NOT NULL, aliases TEXT NOT NULL, provenance TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tt_offering_scope ON tt_offering(version_id,programme,semester,section,code);
CREATE TABLE IF NOT EXISTS tt_teacher_assignment (
 offering_id TEXT NOT NULL REFERENCES tt_offering(id), name TEXT NOT NULL, role TEXT NOT NULL,
 PRIMARY KEY(offering_id,name,role)
);
CREATE TABLE IF NOT EXISTS tt_meeting (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES tt_version(id),
 weekday TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
 room TEXT NOT NULL, mode TEXT NOT NULL, class_kind TEXT NOT NULL,
 page INTEGER NOT NULL, bbox TEXT NOT NULL, raw TEXT NOT NULL,
 confidence REAL NOT NULL, time_source TEXT NOT NULL, provenance TEXT NOT NULL,
 omitted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS tt_meeting_interval ON tt_meeting(version_id,weekday,start_time,end_time,room);
CREATE TABLE IF NOT EXISTS tt_meeting_course (
 meeting_id TEXT NOT NULL REFERENCES tt_meeting(id), code TEXT NOT NULL,
 offering_id TEXT REFERENCES tt_offering(id),
 UNIQUE(meeting_id,code,offering_id)
);
CREATE TABLE IF NOT EXISTS tt_issue (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES tt_version(id),
 meeting_id TEXT, kind TEXT NOT NULL, detail TEXT NOT NULL,
 resolution TEXT, resolved_by TEXT, resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS tt_active (
 scope TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES tt_version(id),
 generation INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS tt_current_term (
 department TEXT NOT NULL, campus TEXT NOT NULL, academic_term TEXT NOT NULL,
 valid_from TEXT NOT NULL, valid_until TEXT NOT NULL, PRIMARY KEY(department,campus)
);
CREATE TABLE IF NOT EXISTS tt_audit (
 id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL,
 version_id TEXT, timestamp TEXT NOT NULL, detail TEXT NOT NULL
);
