CREATE TABLE IF NOT EXISTS evidence_resource (
    chunk_id TEXT NOT NULL REFERENCES evidence_chunk(id),
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    PRIMARY KEY (chunk_id, url)
);
