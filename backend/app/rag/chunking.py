from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    page_number: int | None = None
    section_title: str | None = None


def chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 180,
    page_number: int | None = None,
) -> list[TextChunk]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks = []
    start = 0
    index = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary
        content = normalized[start:end].strip()
        if content:
            chunks.append(TextChunk(index=index, content=content, page_number=page_number))
            index += 1
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks

