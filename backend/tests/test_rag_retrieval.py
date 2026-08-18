from app.rag.embedding import embed_text
from app.rag.retriever import retrieve_local


def test_retrieval_returns_relevant_chunk_first() -> None:
    chunks = [
        {"content": "Students need at least 80 percent attendance for examinations."},
        {"content": "The BS degree has a maximum duration of twelve regular semesters."},
        {"content": "The library is open from eight in the morning."},
    ]
    results = retrieve_local("What attendance is needed for exams?", chunks)
    assert results[0]["content"].startswith("Students need at least 80 percent")


def test_retrieval_accepts_precomputed_embeddings() -> None:
    content = "A BS student may take 15 to 18 normal credit hours."
    results = retrieve_local(
        "normal credit hours",
        [{"content": content, "embedding": embed_text(content)}],
    )
    assert results[0]["similarity"] > 0.0
