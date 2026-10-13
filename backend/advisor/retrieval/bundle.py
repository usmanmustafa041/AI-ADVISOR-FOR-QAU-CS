"""Immutable, versioned index bundle: chunks + vectors + entity tables.

A bundle lives in ``indexes/<build_id>/``. ``indexes/CURRENT`` names the live one; it is
replaced atomically, so a running server never sees a half-written index and a bad build
can be rolled back by pointing CURRENT at the previous directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np

from advisor.ingest.model import Chunk
from advisor.retrieval.lexical import BM25
from advisor.retrieval.text import extract_codes


class Bundle:
    def __init__(self, path: Path, chunks: list[dict], vectors: np.ndarray, manifest: dict):
        self.path = path
        self.chunks = chunks
        self.vectors = vectors
        self.manifest = manifest
        self.bm25 = BM25([c["index_text"] for c in chunks])
        self.prereq = None
        self.prereq_resolver = None
        if path is not None and (Path(path) / "prereq_graph.json").exists():
            from advisor.prereq.graph import Graph, Resolver

            self.prereq = Graph.from_json(json.loads((Path(path) / "prereq_graph.json").read_text()))
            self.prereq_resolver = Resolver(self.prereq)
        self.timetable = None
        if path is not None and (Path(path) / "timetable.json").exists():
            from advisor.rag.timetable_qa import Timetable

            self.timetable = Timetable.from_json(json.loads((Path(path) / "timetable.json").read_text()))
        self.fees = None
        if path is not None and (Path(path) / "fees.json").exists():
            from advisor.rag.fees_qa import Fees

            self.fees = Fees.from_json(json.loads((Path(path) / "fees.json").read_text()))
        self.by_id = {c["chunk_id"]: i for i, c in enumerate(chunks)}
        self.code_chunks: dict[str, list[int]] = defaultdict(list)
        self.course_record: dict[str, int] = {}
        self.course_names: dict[str, str] = {}
        self.faculty: dict[str, dict] = {}  # lower name -> {name, chunks}
        for i, c in enumerate(chunks):
            for code in extract_codes(c["text"]):
                self.code_chunks[code].append(i)
            meta = c["meta"]
            if c["kind"] == "course" and meta.get("course_code"):
                from advisor.retrieval.text import CODE_RE, norm_code

                m = CODE_RE.match(meta["course_code"])
                key = norm_code(m.group(1), m.group(2)) if m else meta["course_code"]
                self.course_record[key] = i
                self.course_names[key] = meta.get("course_name", "")
            if meta.get("faculty_name"):
                ent = self.faculty.setdefault(
                    meta["faculty_name"].lower(), {"name": meta["faculty_name"], "chunks": []}
                )
                ent["chunks"].append(i)

    @property
    def build_id(self) -> str:
        return self.manifest["build_id"]


def content_hash(chunks: list[Chunk]) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(c.chunk_id.encode())
        h.update(c.text.encode())
    return h.hexdigest()[:12]


def write_bundle(
    index_dir: Path, chunks: list[Chunk], vectors: np.ndarray, extra: dict, files: dict[str, str] | None = None
) -> Path:
    index_dir.mkdir(parents=True, exist_ok=True)
    build_id = time.strftime("%Y%m%d-%H%M%S") + "-" + content_hash(chunks)
    target = index_dir / build_id
    tmp = index_dir / f".{build_id}.tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    with (tmp / "chunks.jsonl").open("w") as fh:
        for c in chunks:
            fh.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
    np.save(tmp / "vectors.npy", vectors.astype(np.float16))
    for name, content in (files or {}).items():
        (tmp / name).write_text(content)
    manifest = {
        "build_id": build_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "chunks": len(chunks),
        "dim": int(vectors.shape[1]),
        **extra,
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2))
    tmp.rename(target)
    set_current(index_dir, build_id)
    return target


def set_current(index_dir: Path, build_id: str) -> None:
    pointer = index_dir / "CURRENT"
    tmp = index_dir / "CURRENT.tmp"
    tmp.write_text(build_id)
    os.replace(tmp, pointer)


def list_builds(index_dir: Path) -> list[str]:
    if not index_dir.exists():
        return []
    return sorted(p.name for p in index_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def load_bundle(index_dir: Path, build_id: str | None = None) -> Bundle | None:
    pointer = index_dir / "CURRENT"
    if build_id is None:
        if not pointer.exists():
            return None
        build_id = pointer.read_text().strip()
    path = index_dir / build_id
    if not (path / "manifest.json").exists():
        return None
    chunks = [json.loads(line) for line in (path / "chunks.jsonl").read_text().splitlines() if line]
    vectors = np.load(path / "vectors.npy").astype(np.float32)
    manifest = json.loads((path / "manifest.json").read_text())
    return Bundle(path, chunks, vectors, manifest)


def prune_builds(index_dir: Path, keep: int = 3) -> None:
    builds = list_builds(index_dir)
    current = (index_dir / "CURRENT").read_text().strip() if (index_dir / "CURRENT").exists() else ""
    for name in builds[:-keep]:
        if name != current:
            for f in (index_dir / name).iterdir():
                f.unlink()
            (index_dir / name).rmdir()
