# RAG layer — Step 8

The retrieval pipeline now supports:

- PDF, TXT, Markdown, and CSV text extraction.
- Overlapping chunks with page metadata.
- 384-dimensional deterministic embeddings for development.
- pgvector cosine retrieval from `document_chunks`.
- Citation-ready source code, URL, document title, page, and section metadata.
- JSONL ingestion for review before records are inserted into PostgreSQL.

Run the ingestion preview after placing official documents in the data folders:

```powershell
cd backend
python scripts/ingest_documents.py ..\academic-data\university-policies --output ..\rag-chunks.jsonl
```

The fallback embedding is deterministic and portable, not a claim of semantic
quality. For the research comparison, pin a multilingual sentence-transformer
that outputs 384 dimensions and replace `embed_text` while preserving the API
and pgvector contract. Retrieval is source-aware; response generation belongs
after retrieval and must cite the returned official chunks.

