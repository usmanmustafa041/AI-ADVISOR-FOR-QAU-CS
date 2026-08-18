from pathlib import Path

from app.rag.chunking import TextChunk, chunk_text


def extract_document_text(path: Path) -> list[tuple[int | None, str]]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        return [(None, path.read_text(encoding="utf-8"))]
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [(index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)]
    raise ValueError(f"Unsupported document type: {suffix}")


def document_chunks(path: Path, chunk_size: int = 1200, overlap: int = 180) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    index = 0
    for page_number, text in extract_document_text(path):
        for chunk in chunk_text(text, chunk_size=chunk_size, overlap=overlap, page_number=page_number):
            chunks.append(TextChunk(index=index, content=chunk.content, page_number=page_number))
            index += 1
    return chunks

