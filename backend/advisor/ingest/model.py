"""Data model shared by the ingestion pipeline."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def stable_id(*parts: str, length: int = 16) -> str:
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:length]


@dataclass(slots=True)
class Block:
    """A semantically coherent unit of text (a section, an FAQ entry, a table, ...)."""

    heading: str
    text: str
    # "text" blocks may be merged with neighbours; "atomic" blocks (FAQ entries, course
    # records, schedule rows) are never merged or split mid-record.
    atomic: bool = False
    meta: dict = field(default_factory=dict)


@dataclass(slots=True)
class Document:
    url: str
    title: str
    kind: str  # course | faculty | programme | scheme | faq | page | policy | timetable | ...
    blocks: list[Block]
    source_type: str = "web"  # web | pdf
    fetched_at: str = ""
    # Entity / context facts used for retrieval boosts and shown to the model.
    meta: dict = field(default_factory=dict)
    # Lower = less authoritative when sources disagree (derived indexes < primary pages).
    priority: int = 5
    # Structured data parsed alongside the text (kept out of the index; saved next to it by the build).
    payload: dict = field(default_factory=dict)

    @property
    def doc_id(self) -> str:
        return stable_id(self.url, self.kind, self.meta.get("variant", ""))

    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)


@dataclass(slots=True)
class Chunk:
    chunk_id: str
    doc_id: str
    ord: int
    url: str
    title: str
    kind: str
    heading: str
    text: str  # content shown to the model
    index_text: str  # text used for lexical + dense indexing (adds title/aliases)
    meta: dict
    priority: int = 5
    source_type: str = "web"
    fetched_at: str = ""
    atomic: bool = False
